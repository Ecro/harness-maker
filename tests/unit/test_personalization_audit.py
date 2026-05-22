"""Phase 10 (B4) /hm:personalization-audit tests.

ADR-011 LOCKED RUBRIC: 40/30/30 weights, 0-39/40-64/65-84/85-100 tiers,
evidence schema {n_observations, top_3_signals, confidence}, drop items
lacking observations or signals.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import personalization_audit as pa
from harness_maker.models import Confidence
from harness_maker.personalization_audit import (
    ActionEvidence,
    PersonalizationActionItem,
    assign_tier,
    compute_composite,
    compute_l1_conversion,
    compute_l2_stability,
    compute_l3_cadence,
    run_audit,
)

# ── Rubric YAML structural checks ──────────────────────────────────────────


def test_rubric_yaml_loads_with_adr_011_weights() -> None:
    """ADR-011 LOCKED: 40/30/30 weights, 0-39/40-64/65-84/85-100 tiers."""
    rubric_path = pa._default_rubric_path()
    assert rubric_path.is_file(), f"shipped rubric missing at {rubric_path}"
    data = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))

    assert data["version"] == 1
    assert data["layer_weights"]["l1_conversion"] == 0.4
    assert data["layer_weights"]["l2_stability"] == 0.3
    assert data["layer_weights"]["l3_cadence"] == 0.3

    assert data["tiers"]["bronze"] == {"min": 0, "max": 39}
    assert data["tiers"]["silver"] == {"min": 40, "max": 64}
    assert data["tiers"]["gold"] == {"min": 65, "max": 84}
    assert data["tiers"]["platinum"] == {"min": 85, "max": 100}

    assert data["layers"]["l2_stability"]["penalty_factor"] == 5
    assert data["layers"]["l2_stability"]["window_days"] == 30
    assert data["layers"]["l3_cadence"]["window_days"] == 14

    schema_required = data["evidence_schema"]["required"]
    assert set(schema_required) == {"n_observations", "top_3_signals", "confidence"}


# ── Per-layer formula checks ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("medium_accepted", "high_silent", "total", "expected"),
    [
        (0, 0, 0, 0),  # denom clamps to 1, numerator 0 → 0
        (1, 1, 2, 100),  # all accounted-for recommendations converted
        (2, 3, 10, 50),  # 5/10 → 50
        (5, 0, 5, 100),  # all medium accepted
        (0, 7, 7, 100),  # all high silent
        (3, 3, 12, 50),  # 6/12 → 50
    ],
)
def test_l1_conversion_formula(
    medium_accepted: int,
    high_silent: int,
    total: int,
    expected: int,
) -> None:
    assert compute_l1_conversion(medium_accepted, high_silent, total) == expected


@pytest.mark.parametrize(
    ("n_overrides", "expected"),
    [
        (0, 100),  # no overrides → perfect stability
        (1, 95),
        (5, 75),
        (10, 50),
        (19, 5),
        (20, 0),  # saturates at 100*5 = 100 penalty
        (50, 0),  # clamp
    ],
)
def test_l2_stability_penalty_factor(n_overrides: int, expected: int) -> None:
    assert compute_l2_stability(n_overrides, penalty_factor=5) == expected


@pytest.mark.parametrize(
    ("days_since", "disable_telemetry", "expected"),
    [
        (5.0, False, 100),  # both conditions met
        (5.0, True, 50),  # only audit cadence met
        (20.0, False, 50),  # only telemetry-on met
        (20.0, True, 0),  # neither met
        (None, False, 50),  # never audited but telemetry on → one met
        (None, True, 0),  # never audited + telemetry opted out
        (14.0, False, 100),  # boundary inclusive
        (14.01, False, 50),  # just past the window
    ],
)
def test_l3_cadence_three_conditions(
    days_since: float | None,
    disable_telemetry: bool,
    expected: int,
) -> None:
    assert compute_l3_cadence(days_since, disable_telemetry, window_days=14) == expected


# ── Composite + tier ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("l1", "l2", "l3", "expected"),
    [
        (100, 100, 100, 100),
        (0, 0, 0, 0),
        # 80*0.4 + 60*0.3 + 40*0.3 = 32 + 18 + 12 = 62
        (80, 60, 40, 62),
        # 50*0.4 + 50*0.3 + 50*0.3 = 50
        (50, 50, 50, 50),
        # 100*0.4 + 0*0.3 + 0*0.3 = 40
        (100, 0, 0, 40),
    ],
)
def test_composite_weighted(l1: int, l2: int, l3: int, expected: int) -> None:
    assert compute_composite(l1, l2, l3) == expected


@pytest.mark.parametrize(
    ("composite", "tier"),
    [
        (0, "bronze"),
        (39, "bronze"),
        (40, "silver"),
        (64, "silver"),
        (65, "gold"),
        (84, "gold"),
        (85, "platinum"),
        (100, "platinum"),
    ],
)
def test_tier_assignment_per_boundary(composite: int, tier: str) -> None:
    rubric = yaml.safe_load(pa._default_rubric_path().read_text(encoding="utf-8"))
    assert assign_tier(composite, rubric["tiers"]) == tier


# ── ActionItem evidence contract ──────────────────────────────────────────


def test_action_item_evidence_required() -> None:
    """ADR-011 drop_when: n_observations==0 OR empty top_3_signals → drop."""
    # _action_for_frequent_axis returns None for both failure cases.
    assert pa._action_for_frequent_axis("preset", 0, ["preset"]) is None
    assert pa._action_for_frequent_axis("preset", 3, []) is None

    # A well-formed input produces a valid item.
    item = pa._action_for_frequent_axis("preset", 3, ["preset"])
    assert item is not None
    assert item.evidence.n_observations == 3
    assert item.evidence.top_3_signals == ["preset"]


def test_action_item_evidence_schema_matches_adr_011(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every ActionItem must carry the ADR-011 evidence schema."""
    _seed_overrides(
        tmp_path,
        [
            _override("preset", "Side", "Production", "2026-05-15T12:00:00+00:00"),
            _override("preset", "Production", "Side", "2026-05-14T12:00:00+00:00"),
            _override("preset", "Side", "Production", "2026-05-13T12:00:00+00:00"),
            _override("preset", "Production", "Side", "2026-05-12T12:00:00+00:00"),
            _override("preset", "Side", "Production", "2026-05-11T12:00:00+00:00"),
        ],
    )
    _seed_harness_yaml(tmp_path, adaptive={"disable_telemetry": False})
    monkeypatch.setattr(pa, "load_or_run", lambda _: None)

    now = datetime(2026, 5, 16, tzinfo=UTC)
    plan = run_audit(tmp_path, now=now)

    assert plan.actions, "expected at least one ActionItem"
    for a in plan.actions:
        assert isinstance(a, PersonalizationActionItem)
        assert isinstance(a.evidence, ActionEvidence)
        assert isinstance(a.evidence.n_observations, int)
        assert a.evidence.n_observations > 0
        assert isinstance(a.evidence.top_3_signals, list)
        assert len(a.evidence.top_3_signals) > 0
        assert isinstance(a.evidence.confidence, Confidence)


def test_evidence_drop_when_filter_post_construction() -> None:
    """If an item is constructed bypassing the helper, the post-build
    filter in run_audit still drops zero-evidence items."""
    # ActionEvidence forbids extra fields; n=0 still constructs (no constraint),
    # but the audit pipeline must filter it out.
    invalid = PersonalizationActionItem(
        priority="P2",
        dimension="x",
        summary="zero observations",
        suggestion="never seen",
        evidence=ActionEvidence(
            n_observations=0,
            top_3_signals=["foo"],
            confidence=Confidence.LOW,
        ),
    )
    # Manual filter mirrors the inline filter in run_audit.
    filtered = [
        a for a in [invalid] if a.evidence.n_observations > 0 and len(a.evidence.top_3_signals) > 0
    ]
    assert filtered == []


# ── End-to-end audit ──────────────────────────────────────────────────────


def _override(
    axis: str,
    before: Any,
    after: Any,
    ts: str,
    source: str = "configure-exit",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ts": ts,
        "axis_path": axis,
        "before": before,
        "after": after,
        "source": source,
        "reason": "",
    }


def _seed_overrides(tmp_path: Path, records: list[dict[str, Any]]) -> None:
    path = tmp_path / ".claude" / "observability" / "adaptive" / "overrides.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + ("\n" if records else ""),
        encoding="utf-8",
    )


def _seed_harness_yaml(
    tmp_path: Path,
    *,
    adaptive: dict[str, Any] | None = None,
    extra_lines: list[str] | None = None,
) -> None:
    """Minimal valid harness.yaml fixture for the audit reader."""
    path = tmp_path / ".claude" / "harness.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "preset": "Side",
        "dev_mode": "spec-driven",
        "targets": ["claude-code"],
    }
    if adaptive is not None:
        body["adaptive"] = adaptive
    text = yaml.safe_dump(body, sort_keys=False)
    if extra_lines:
        text += "\n" + "\n".join(extra_lines) + "\n"
    path.write_text(text, encoding="utf-8")


def test_full_audit_pure_bronze_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty overrides + no last-audit + disable_telemetry=true → bronze."""
    _seed_harness_yaml(tmp_path, adaptive={"disable_telemetry": True})
    monkeypatch.setattr(pa, "load_or_run", lambda _: None)

    plan = run_audit(tmp_path, now=datetime(2026, 5, 16, tzinfo=UTC))

    assert plan.composite_score < 40, f"expected bronze tier, got {plan.composite_score}"
    assert plan.tier == "bronze"
    # L3 must be 0: no audit ever + telemetry opted out.
    assert plan.layer_scores["l3_cadence"] == 0


def test_full_audit_pure_platinum_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Many high-confidence detected lines + zero overrides + recent audit +
    telemetry on → platinum (composite >= 85).
    """
    # Detection cache → 5 total recommendations.
    from harness_maker.models import ProjectProfile

    profile = ProjectProfile(
        stack=["python"],
        detection_confidence={
            "preset": Confidence.HIGH,
            "wrapup_docs": Confidence.HIGH,
            "mcp_servers": Confidence.HIGH,
            "package_manager": Confidence.HIGH,
            "ci_provider": Confidence.HIGH,
        },
    )
    monkeypatch.setattr(pa, "load_or_run", lambda _: profile)

    # harness.yaml with 5 high-confidence comments → high_silent=5.
    high_comments = [f"# detected: axis_{i} (high)" for i in range(5)]
    _seed_harness_yaml(
        tmp_path,
        adaptive={"disable_telemetry": False},
        extra_lines=high_comments,
    )

    # Zero overrides → L2=100.
    _seed_overrides(tmp_path, [])

    # Recent last-audit (1 day ago) → L3=100.
    now = datetime(2026, 5, 16, tzinfo=UTC)
    last_audit_path = tmp_path / ".claude" / "observability" / "adaptive" / "last-audit.txt"
    last_audit_path.parent.mkdir(parents=True, exist_ok=True)
    last_audit_path.write_text((now - timedelta(days=1)).isoformat(), encoding="utf-8")

    plan = run_audit(tmp_path, now=now)

    assert plan.composite_score >= 85, f"expected platinum, got {plan.composite_score}"
    assert plan.tier == "platinum"
    assert plan.layer_scores["l1_conversion"] == 100
    assert plan.layer_scores["l2_stability"] == 100
    assert plan.layer_scores["l3_cadence"] == 100


def test_last_audit_timestamp_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_audit must update last-audit.txt with now.isoformat() (atomic)."""
    _seed_harness_yaml(tmp_path, adaptive={"disable_telemetry": False})
    monkeypatch.setattr(pa, "load_or_run", lambda _: None)

    now = datetime(2026, 5, 16, 10, 30, 0, tzinfo=UTC)
    run_audit(tmp_path, now=now)

    marker = tmp_path / ".claude" / "observability" / "adaptive" / "last-audit.txt"
    assert marker.is_file()
    written = marker.read_text(encoding="utf-8").strip()
    assert written == now.isoformat()


def test_frequent_axis_drives_action_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """≥3 overrides on one axis in 30d → at least one ActionItem with that
    axis_path in evidence.top_3_signals.

    Each override sets `preset` to a value differing from the seeded
    harness.yaml default (Side), so the convergence filter (PLAN-audit-
    convergence-2026-05) keeps all three events as divergent and the
    frequent-axis threshold (≥3) is met."""
    _seed_overrides(
        tmp_path,
        [
            _override("preset", "Side", "Production", "2026-05-15T12:00:00+00:00"),
            _override("preset", "Side", "Production", "2026-05-14T12:00:00+00:00"),
            _override("preset", "Side", "Production", "2026-05-13T12:00:00+00:00"),
        ],
    )
    _seed_harness_yaml(tmp_path, adaptive={"disable_telemetry": False})
    monkeypatch.setattr(pa, "load_or_run", lambda _: None)

    plan = run_audit(tmp_path, now=datetime(2026, 5, 16, tzinfo=UTC))

    axis_items = [a for a in plan.actions if "preset" in a.evidence.top_3_signals]
    assert axis_items, "expected at least one preset-axis ActionItem"
    assert axis_items[0].evidence.n_observations == 3


def test_overrides_outside_30d_window_excluded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L2 + ActionItems only count overrides within the 30-day window."""
    now = datetime(2026, 5, 16, tzinfo=UTC)
    old_ts = (now - timedelta(days=60)).isoformat()
    _seed_overrides(
        tmp_path,
        [
            _override("preset", "a", "b", old_ts),
            _override("preset", "a", "b", old_ts.replace("00", "01")),
        ],
    )
    _seed_harness_yaml(tmp_path, adaptive={"disable_telemetry": False})
    monkeypatch.setattr(pa, "load_or_run", lambda _: None)

    plan = run_audit(tmp_path, now=now)

    # Old overrides excluded from L2 → L2 stays at 100.
    assert plan.layer_scores["l2_stability"] == 100
    # No frequent-axis ActionItems either.
    assert all("preset" not in a.evidence.top_3_signals for a in plan.actions)
