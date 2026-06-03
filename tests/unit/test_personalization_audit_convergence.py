"""Convergence-aware L2 stability tests (PLAN-audit-convergence-2026-05).

ADR-001: preset YAML template = source of truth for `current_defaults`.
ADR-002: `after=None` at a parent path is a clearing event (not divergent)
         when the subtree still exists in the default.
ADR-003: a single `recent_divergent` list feeds both L2 score and actions.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from harness_maker import personalization_audit as pa
from harness_maker.telemetry import OverrideRecord


def _jsonl(records: list[dict[str, object]]) -> str:
    return "".join(json.dumps(r) + "\n" for r in records)


# ── _load_preset_defaults ──────────────────────────────────────────────────


def test_load_preset_defaults_production_memory_shape() -> None:
    """ADR-001: rendered Production template must expose
    memory={enabled, dir, files} — the convergence baseline for the
    dogfood 2026-05-19 events."""
    defaults = pa._load_preset_defaults("production")

    assert isinstance(defaults, dict)
    assert defaults["memory"]["enabled"] is True
    assert defaults["memory"]["dir"] == ".claude/memory"
    assert defaults["memory"]["files"] == ["failures.md", "wiki.md"]


def test_load_preset_defaults_side_memory_shape() -> None:
    """Side preset must expose the same memory shape (template parity)."""
    defaults = pa._load_preset_defaults("side")

    assert defaults["memory"]["enabled"] is True
    assert defaults["memory"]["dir"] == ".claude/memory"
    assert defaults["memory"]["files"] == ["failures.md", "wiki.md"]


def test_load_preset_defaults_seeds_preset_specific_axes() -> None:
    """Regression (F22): the baseline must reflect interview preset seeding, not
    bare InterviewAnswers field defaults. A Production install has
    consensus=cross-check / default_workflow=exec-rev-ver-wrap; Side has
    single / exec-rev-wrap. The audit compared against the wrong baseline before."""
    prod = pa._load_preset_defaults("production")
    assert prod["reviewers"]["consensus"] == "cross-check"
    assert prod["default_workflow"] == "exec-rev-ver-wrap"

    side = pa._load_preset_defaults("side")
    assert side["reviewers"]["consensus"] == "single"
    assert side["default_workflow"] == "exec-rev-wrap"


# ── _walk_axis_path ────────────────────────────────────────────────────────


def test_walk_axis_path_top_level_hit() -> None:
    exists, value = pa._walk_axis_path({"memory": {"dir": "/x"}}, "memory")
    assert exists is True
    assert value == {"dir": "/x"}


def test_walk_axis_path_nested_hit() -> None:
    exists, value = pa._walk_axis_path({"memory": {"dir": "/x"}}, "memory.dir")
    assert exists is True
    assert value == "/x"


def test_walk_axis_path_missing_intermediate() -> None:
    """Path that dives through a missing key must report absence,
    not raise — audit input is user data."""
    exists, value = pa._walk_axis_path({"memory": {"dir": "/x"}}, "memory.failures")
    assert exists is False
    assert value is None


def test_walk_axis_path_missing_top_level() -> None:
    exists, value = pa._walk_axis_path({"memory": {}}, "telemetry.enabled")
    assert exists is False
    assert value is None


def test_walk_axis_path_walks_through_non_dict() -> None:
    """If an intermediate value is not a dict, the path cannot be walked
    further — report absence rather than raising."""
    exists, _ = pa._walk_axis_path({"memory": "a-string"}, "memory.dir")
    assert exists is False


# ── _converged_on_default ──────────────────────────────────────────────────


def _make_record(axis_path: str, after: object, before: object = None) -> OverrideRecord:
    return OverrideRecord(
        ts="2026-05-19T02:28:18.689752+00:00",
        axis_path=axis_path,
        before=before,
        after=after,
        source="configure-exit",
    )


def test_converged_exact_string_match() -> None:
    """memory.dir override that matches the default string value = converged."""
    defaults = {"memory": {"dir": ".claude/memory"}}
    record = _make_record("memory.dir", ".claude/memory")
    assert pa._converged_on_default(record, defaults) is True


def test_converged_list_equality() -> None:
    """List values must compare structurally — order matters."""
    defaults = {"memory": {"files": ["failures.md", "wiki.md"]}}
    record = _make_record("memory.files", ["failures.md", "wiki.md"])
    assert pa._converged_on_default(record, defaults) is True


def test_converged_after_none_with_subtree_in_default() -> None:
    """ADR-002: after=None at a parent path is a clearing event when the
    default still defines that subtree. The user nulled `memory.wiki`
    because the new schema doesn't have `wiki` as a sibling field — the
    default's `memory.*` subtree still exists, so this counts as convergent."""
    defaults = {"memory": {"enabled": True, "dir": ".claude/memory"}}
    record = _make_record("memory.wiki", None)
    assert pa._converged_on_default(record, defaults) is True


def test_converged_after_none_whole_memory_when_default_has_memory() -> None:
    """ADR-002: `memory: -> None` when the default re-emits `memory: {...}`
    is convergent — the user's null is overwritten by the next re-render."""
    defaults = {"memory": {"enabled": True, "dir": ".claude/memory"}}
    record = _make_record("memory", None)
    assert pa._converged_on_default(record, defaults) is True


def test_divergent_value_mismatch() -> None:
    """Override that sets a value differing from the default = divergent."""
    defaults = {"memory": {"dir": ".claude/memory"}}
    record = _make_record("memory.dir", "/tmp/custom-memory")
    assert pa._converged_on_default(record, defaults) is False


def test_divergent_after_none_when_default_has_no_subtree() -> None:
    """If the default doesn't define the axis at all, after=None is
    a no-op — also convergent (clearing a field that's already absent)."""
    defaults = {"memory": {"dir": ".claude/memory"}}
    record = _make_record("telemetry.foo", None)
    assert pa._converged_on_default(record, defaults) is True


def test_divergent_axis_not_in_default_with_real_value() -> None:
    """Axis not in default + after=<some value> = divergent (user added
    a field the default doesn't ship)."""
    defaults = {"memory": {"dir": ".claude/memory"}}
    record = _make_record("memory.custom_field", "custom-value")
    assert pa._converged_on_default(record, defaults) is False


def test_converged_nested_dict_equality() -> None:
    """Whole-subtree override that exactly matches the default."""
    defaults = {"memory": {"enabled": True, "dir": ".claude/memory", "files": ["failures.md"]}}
    record = _make_record(
        "memory",
        {"enabled": True, "dir": ".claude/memory", "files": ["failures.md"]},
    )
    assert pa._converged_on_default(record, defaults) is True


# ── Dogfood regression: 2026-05-19 memory.* events ─────────────────────────


def test_dogfood_2026_05_19_memory_events_all_converge() -> None:
    """All five memory.* override events from this repo's 2026-05-19 entry
    must classify as convergent against the current Production default."""
    defaults = pa._load_preset_defaults("production")

    events = [
        _make_record("memory.dir", ".claude/memory", before=None),
        _make_record("memory.failures", None, before=".claude/memory/failures.md"),
        _make_record("memory.files", ["failures.md", "wiki.md"], before=None),
        _make_record("memory.session_dir", None, before=".claude/memory/session/"),
        _make_record("memory.wiki", None, before=".claude/memory/wiki.md"),
    ]
    for r in events:
        assert pa._converged_on_default(r, defaults) is True, (
            f"expected {r.axis_path}={r.after!r} to converge on Production default"
        )


def test_dogfood_2026_05_17_whole_block_null_converges() -> None:
    """The 2026-05-17/18 `memory: -> None` events: default still emits a
    memory block, so ADR-002 clearing-event applies."""
    defaults = pa._load_preset_defaults("production")
    record = _make_record("memory", None, before={"failures": ".claude/memory/failures.md"})
    assert pa._converged_on_default(record, defaults) is True


# ── compute_l2_stability: legacy int path (back-compat) ────────────────────


def test_compute_l2_stability_legacy_int_path_unchanged() -> None:
    """Legacy callers pass an int count; behavior must be identical to pre-fix."""
    assert pa.compute_l2_stability(0) == 100
    assert pa.compute_l2_stability(1) == 95
    assert pa.compute_l2_stability(5) == 75
    assert pa.compute_l2_stability(20) == 0


def test_compute_l2_stability_legacy_int_with_custom_penalty() -> None:
    """Custom penalty factor still works on the int path."""
    assert pa.compute_l2_stability(3, penalty_factor=10) == 70


# ── compute_l2_stability: new list+defaults path (convergence-aware) ───────


def test_compute_l2_stability_all_convergent_yields_100() -> None:
    """Convergent overrides are filtered out — score is full marks."""
    defaults = {"memory": {"dir": ".claude/memory"}}
    events = [_make_record("memory.dir", ".claude/memory") for _ in range(5)]
    assert pa.compute_l2_stability(events, current_defaults=defaults) == 100


def test_compute_l2_stability_all_divergent_matches_legacy_penalty() -> None:
    """When every event diverges, the new path scores identical to the
    legacy int path for the same count."""
    defaults = {"memory": {"dir": ".claude/memory"}}
    events = [_make_record("memory.dir", f"/custom/{i}") for i in range(5)]
    assert pa.compute_l2_stability(events, current_defaults=defaults) == 75


def test_compute_l2_stability_mixed_only_counts_divergent() -> None:
    """3 convergent + 2 divergent → penalty applies only to the 2 divergent."""
    defaults = {"memory": {"dir": ".claude/memory"}}
    events = [
        _make_record("memory.dir", ".claude/memory"),  # converged
        _make_record("memory.dir", ".claude/memory"),  # converged
        _make_record("memory.dir", ".claude/memory"),  # converged
        _make_record("memory.dir", "/custom-a"),  # divergent
        _make_record("memory.dir", "/custom-b"),  # divergent
    ]
    assert pa.compute_l2_stability(events, current_defaults=defaults) == 90  # 100 - 2*5


# ── run_audit regression: dogfood overrides → L2=100, no action items ──────


def test_run_audit_dogfood_memory_overrides_score_100_no_actions(tmp_path: Path) -> None:
    """The 2026-05-19 memory.* override events from this repo's overrides.jsonl
    must NOT trigger an `override_stability` action item, and L2 must be 100."""
    # Build a minimal .claude/ tree with the dogfood-shape overrides + a
    # harness.yaml that selects the Production preset (matches the convergence
    # baseline used inside run_audit).
    claude_dir = tmp_path / ".claude"
    obs_dir = claude_dir / "observability" / "adaptive"
    obs_dir.mkdir(parents=True)
    claude_dir.mkdir(exist_ok=True)

    (claude_dir / "harness.yaml").write_text(
        "preset: Production\n"
        "locale: en\n"
        "targets: [claude-code]\n"
        "default_model: claude-opus-4-7\n"
        "dev_mode: spec-driven\n"
        "schema_version: 2\n"
        "memory: {enabled: true, dir: .claude/memory, files: [failures.md, wiki.md]}\n",
        encoding="utf-8",
    )

    # Five memory.* override events dated within the 30-day window, matching
    # the production default exactly (after `_load_preset_defaults` rendering).
    now = datetime(2026, 5, 22, tzinfo=UTC)
    ts = now.isoformat()
    records: list[dict[str, object]] = [
        {
            "schema_version": 1,
            "ts": ts,
            "axis_path": "memory.dir",
            "before": None,
            "after": ".claude/memory",
            "source": "configure-exit",
        },
        {
            "schema_version": 1,
            "ts": ts,
            "axis_path": "memory.failures",
            "before": ".claude/memory/failures.md",
            "after": None,
            "source": "configure-exit",
        },
        {
            "schema_version": 1,
            "ts": ts,
            "axis_path": "memory.files",
            "before": None,
            "after": ["failures.md", "wiki.md"],
            "source": "configure-exit",
        },
        {
            "schema_version": 1,
            "ts": ts,
            "axis_path": "memory.session_dir",
            "before": ".claude/memory/session/",
            "after": None,
            "source": "configure-exit",
        },
        {
            "schema_version": 1,
            "ts": ts,
            "axis_path": "memory.wiki",
            "before": ".claude/memory/wiki.md",
            "after": None,
            "source": "configure-exit",
        },
    ]
    (obs_dir / "overrides.jsonl").write_text(_jsonl(records), encoding="utf-8")

    plan = pa.run_audit(tmp_path, now=now)

    assert plan.layer_scores["l2_stability"] == 100, (
        f"expected L2=100 with all-convergent overrides, got {plan.layer_scores['l2_stability']}"
    )
    override_actions = [a for a in plan.actions if a.dimension == "override_stability"]
    assert override_actions == [], (
        f"convergent overrides must not seed an override_stability action; "
        f"got {[a.summary for a in override_actions]}"
    )


def test_run_audit_unknown_preset_falls_back_to_legacy_l2(tmp_path: Path) -> None:
    """REVIEW P2 fix: an unknown preset string must NOT crash run_audit.
    Audit falls back to legacy un-filtered L2 counting + stderr warning."""
    claude_dir = tmp_path / ".claude"
    obs_dir = claude_dir / "observability" / "adaptive"
    obs_dir.mkdir(parents=True)

    (claude_dir / "harness.yaml").write_text(
        "preset: SomeUnknownPreset\n"
        "locale: en\n"
        "targets: [claude-code]\n"
        "default_model: claude-opus-4-7\n"
        "dev_mode: spec-driven\n"
        "schema_version: 2\n",
        encoding="utf-8",
    )

    now = datetime(2026, 5, 22, tzinfo=UTC)
    ts = now.isoformat()
    records: list[dict[str, object]] = [
        {
            "schema_version": 1,
            "ts": ts,
            "axis_path": "memory.dir",
            "before": None,
            "after": ".claude/memory",
            "source": "configure-exit",
        },
    ]
    (obs_dir / "overrides.jsonl").write_text(_jsonl(records), encoding="utf-8")

    # Must not raise. Legacy fallback counts the single event as instability.
    plan = pa.run_audit(tmp_path, now=now)
    assert plan.layer_scores["l2_stability"] == 95  # 100 - 1*5 (no convergence filter)


def test_run_audit_divergent_overrides_still_penalize(tmp_path: Path) -> None:
    """Regression guard: when overrides genuinely diverge from the default,
    the audit still penalizes L2 and surfaces an action item. The convergence
    filter must not swallow legitimate instability signals."""
    claude_dir = tmp_path / ".claude"
    obs_dir = claude_dir / "observability" / "adaptive"
    obs_dir.mkdir(parents=True)

    (claude_dir / "harness.yaml").write_text(
        "preset: Production\n"
        "locale: en\n"
        "targets: [claude-code]\n"
        "default_model: claude-opus-4-7\n"
        "dev_mode: spec-driven\n"
        "schema_version: 2\n",
        encoding="utf-8",
    )

    now = datetime(2026, 5, 22, tzinfo=UTC)
    ts = now.isoformat()
    # Three divergent overrides on the same axis — should produce a P2 action
    # and dock L2 by 5×3=15 points (penalty_factor=5, count=3).
    records: list[dict[str, object]] = [
        {
            "schema_version": 1,
            "ts": ts,
            "axis_path": "memory.dir",
            "before": None,
            "after": f"/custom-{tag}",
            "source": "configure-exit",
        }
        for tag in ("a", "b", "c")
    ]
    (obs_dir / "overrides.jsonl").write_text(_jsonl(records), encoding="utf-8")

    plan = pa.run_audit(tmp_path, now=now)

    assert plan.layer_scores["l2_stability"] == 85
    override_actions = [a for a in plan.actions if a.dimension == "override_stability"]
    assert len(override_actions) == 1
    assert override_actions[0].evidence.n_observations == 3
    assert "memory.dir" in override_actions[0].summary
