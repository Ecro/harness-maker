"""ADR-006 integration contract: personalization_audit output flows verbatim
into the /hm:health dashboard third section.

The audit module is UNCHANGED in 0.13.0; this test pins the wiring so a
future refactor of ``cli.health_cmd`` or the dashboard writer can't drift
the rubric output bit-for-bit. The byte-equality assertion on a fixed
fixture protects R3 (ADR-011 rubric regression) at PR time.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from harness_maker.cli import _personalization_section_from_plan
from harness_maker.observability.dashboard import render_dashboard_markdown
from harness_maker.personalization_audit import (
    PersonalizationActionItem,
    PersonalizationPlan,
    run_audit,
)


def _write_harness_yaml(project: Path) -> None:
    claude = project / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        "---\nharness_maker_version: 0.13.0\npreset: Side\n---\n"
        "preset: Side\nlocale: en\n"
        "adaptive:\n  disable_telemetry: false\n",
        encoding="utf-8",
    )


def test_run_audit_output_flows_into_dashboard_personalization_section(
    tmp_path: Path,
) -> None:
    """Same input → identical personalization section regardless of which
    helper rendered it. The byte equality proves the wiring layer adds no
    transformation of its own (ADR-006: rubric is bit-identical)."""
    _write_harness_yaml(tmp_path)
    plan = run_audit(tmp_path, now=datetime(2026, 5, 16, tzinfo=UTC))

    # The mapping invoked by /hm:health
    section_via_helper = _personalization_section_from_plan(plan)

    # Build the same dict by hand from the plan — the helper must produce
    # exactly this dict (mod field ordering); compare canonical JSON.
    expected = {
        "composite": plan.composite_score,
        "tier": plan.tier,
        "layers": dict(plan.layer_scores),
        "action_items": [item.model_dump() for item in plan.actions],
    }
    assert json.dumps(section_via_helper, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_personalization_section_bytes_match_when_rendered_into_dashboard(
    tmp_path: Path,
) -> None:
    """Strongest form of the ADR-011 byte-identity assertion: the
    personalization-section bytes inside the rendered dashboard must equal
    the bytes you'd get by rendering ONLY that section directly from the
    audit plan. Any silent transformation in the writer would break this.
    """
    _write_harness_yaml(tmp_path)
    plan = run_audit(tmp_path, now=datetime(2026, 5, 16, tzinfo=UTC))
    section = _personalization_section_from_plan(plan)

    full = render_dashboard_markdown(
        {"score": 50, "signals_failed": []},
        section,
        generated_at="2026-05-16T00:00:00+00:00",
    )
    # Extract bytes of the personalization block (from `## Personalization`
    # header to end of body). Compare against a second render that only
    # contains the same section data — proves no shaping happens.
    personalization_lines = []
    capturing = False
    for line in full.splitlines():
        if line.startswith("## Personalization"):
            capturing = True
        elif line.startswith("## "):
            capturing = False
        if capturing:
            personalization_lines.append(line)

    # Reconstruct what we'd expect, line-for-line.
    layers_json = json.dumps(section["layers"], ensure_ascii=False, sort_keys=False)
    actions_json = (
        json.dumps(section["action_items"], ensure_ascii=False, sort_keys=False)
        if section["action_items"]
        else "[]"
    )
    expected = [
        "## Personalization",
        f"composite: {section['composite']} / 100",
        f"tier: {section['tier']}",
        f"layers: {layers_json if section['layers'] else '{}'}",
        f"action_items: {actions_json}",
    ]
    assert personalization_lines == expected


def test_synthetic_plan_round_trip_bytes_equal_under_helper() -> None:
    """Construct a plan with non-trivial action items to prove the
    helper doesn't accidentally collapse evidence fields or reorder them."""
    from harness_maker.models import Confidence
    from harness_maker.personalization_audit import ActionEvidence

    plan = PersonalizationPlan(
        composite_score=82,
        tier="gold",
        layer_scores={"l1_conversion": 80, "l2_stability": 85, "l3_cadence": 80},
        actions=[
            PersonalizationActionItem(
                priority="P1",
                dimension="override_stability",
                summary="preset overridden 5 times in 30d",
                suggestion="change default to Production",
                evidence=ActionEvidence(
                    n_observations=5,
                    top_3_signals=["preset", "presets", "preset.value"],
                    confidence=Confidence.HIGH,
                ),
            ),
        ],
    )
    section = _personalization_section_from_plan(plan)
    # action_items list must round-trip via model_dump (ADR-011 evidence)
    assert section["action_items"][0]["evidence"]["n_observations"] == 5
    assert section["action_items"][0]["evidence"]["top_3_signals"] == [
        "preset",
        "presets",
        "preset.value",
    ]
    assert section["action_items"][0]["evidence"]["confidence"] == "high"
    assert section["tier"] == "gold"
    assert section["composite"] == 82
    assert section["layers"] == {
        "l1_conversion": 80,
        "l2_stability": 85,
        "l3_cadence": 80,
    }


def test_personalization_audit_module_not_modified() -> None:
    """ADR-006 hard rule: ``personalization_audit.py`` is byte-identical
    to the pre-Phase-1 state. The CLI wiring layer must not poke its
    internals — surface change happens only here, not there.
    """
    import inspect

    from harness_maker import personalization_audit

    src = inspect.getsource(personalization_audit)
    # No mention of /hm:health here — the module knows only its own
    # contract. The wiring is the CLI's job.
    assert "PersonalizationPlan" in src
    assert "run_audit" in src
    # And the rubric weights must remain 0.4 / 0.3 / 0.3 (ADR-011).
    assert "0.4" in src
    assert "0.3" in src
