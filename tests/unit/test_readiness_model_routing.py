"""Phase 6 — /hm:health Layer-1 model_routing_actionable sub-check.

ADR-010 (PLAN-model-routing-multi-ide):
 (a) Claude target + agent_models[*].claude set → #43869 advisory
 (b) removed in 0.63.0 with the Cursor target
 (c) Codex target + override missing reasoning_effort → coverage advisory

All checks advisory (weight-0) — surface signals without changing composite.
Multi-target test (W-6 fix) verifies the sub-checks fire independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness_maker.readiness import _dim_model_routing


def _write_harness_yaml(
    project_dir: Path,
    targets: list[str],
    agent_models: dict[str, Any] | None = None,
) -> None:
    """Helper: write a minimal v2 harness.yaml at .claude/harness.yaml."""
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    body_lines = [
        "---",
        "generated_by: harness-maker",
        'content_hash: "fixture-fake"',
        "---",
        "locale: en",
        f"targets: {targets!r}".replace("'", '"'),
        "preset: Production",
        "default_model: claude-opus-4-7",
        "schema_version: 2",
    ]
    if agent_models is not None:
        import yaml as _yaml

        am_yaml = _yaml.safe_dump({"agent_models": agent_models}, sort_keys=False)
        body_lines.append(am_yaml.rstrip())
    (claude / "harness.yaml").write_text("\n".join(body_lines) + "\n", encoding="utf-8")


def test_missing_harness_yaml_fails_check(tmp_path: Path) -> None:
    """No harness.yaml → returns failing signal pointing at /hm:make."""
    dim = _dim_model_routing(tmp_path)
    assert dim.name == "model_routing"
    assert dim.score < 100
    fail_sigs = [s for s in dim.signals if not s.passed]
    assert fail_sigs
    assert "missing" in fail_sigs[0].evidence.lower()


def test_claude_target_with_override_flags_43869(tmp_path: Path) -> None:
    """ADR-010 (a): claude target + agent_models[*].claude set fires advisory."""
    _write_harness_yaml(
        tmp_path,
        targets=["claude-code"],
        agent_models={"autoloop-coder": {"claude": "opus"}},
    )
    dim = _dim_model_routing(tmp_path)
    sig = next(s for s in dim.signals if s.id == "claude_subagent_routing_43869")
    assert not sig.passed
    assert "43869" in sig.evidence


def test_codex_target_missing_effort_flags_coverage(tmp_path: Path) -> None:
    """ADR-010 (c): codex target + override missing reasoning_effort fires advisory."""
    _write_harness_yaml(
        tmp_path,
        targets=["codex"],
        agent_models={"autoloop-coder": {"claude": "opus"}},  # no codex section
    )
    dim = _dim_model_routing(tmp_path)
    sig = next(s for s in dim.signals if s.id == "codex_reasoning_effort_coverage")
    assert not sig.passed
    assert "reasoning_effort" in sig.evidence


def test_multi_target_cross_product_both_fire(tmp_path: Path) -> None:
    """W-6 validator fix: both targets present → checks (a) and (c) fire independently."""
    _write_harness_yaml(
        tmp_path,
        targets=["claude-code", "codex"],
        agent_models={
            "autoloop-coder": {
                "claude": "opus",
                # no codex section → (c) fires
            }
        },
    )
    dim = _dim_model_routing(tmp_path)
    sig_a = next(s for s in dim.signals if s.id == "claude_subagent_routing_43869")
    sig_c = next(s for s in dim.signals if s.id == "codex_reasoning_effort_coverage")
    assert not sig_a.passed, "claude advisory (a) should fire"
    assert not sig_c.passed, "codex advisory (c) should fire on missing effort"


def test_the_cursor_advisory_is_gone(tmp_path: Path) -> None:
    """0.63.0: a 0.62 harness that still lists `cursor` and sets `agent_models.*.cursor`
    gets no Cursor signal — the target was removed and the key is inert."""
    _write_harness_yaml(
        tmp_path,
        targets=["claude-code", "cursor"],
        agent_models={"code-reviewer": {"cursor": "sonnet"}},
    )
    dim = _dim_model_routing(tmp_path)
    assert all("cursor" not in s.id for s in dim.signals), [s.id for s in dim.signals]


def test_no_overrides_all_checks_pass(tmp_path: Path) -> None:
    """No agent_models overrides → all 3 checks pass (preset map applies)."""
    _write_harness_yaml(tmp_path, targets=["claude-code", "codex"])
    dim = _dim_model_routing(tmp_path)
    assert all(s.passed for s in dim.signals)


def test_dim_weight_is_zero_advisory_only(tmp_path: Path) -> None:
    """ADR-010: model_routing is advisory (weight 0) — doesn't change composite."""
    from harness_maker.readiness import WEIGHTS_PROD, WEIGHTS_SIDE

    assert WEIGHTS_PROD["model_routing"] == 0.0
    assert WEIGHTS_SIDE["model_routing"] == 0.0
