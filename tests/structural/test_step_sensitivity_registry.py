"""Step-sensitivity registry gates (PLAN-workflow-steps-vs-model-capability, SPEC S1/S2/S3/S7).

Every rendered `Step | Phase | Check` heading across `ARMS` (preset × dev_mode) must map to one
`step_sensitivity.REGISTRY` entry with a class in {COMP, HOST, INV, TUNE}; an unclassified
heading fails by name; the Side preset's knob defaults are never more aggressive than
Production's under each entry's declared ordering; and the docs carry the four classes.

Headings are taken from `test_command_size_budget.headings()` — the single definition of
"what counts as a heading" (`_instruction_baseline` imports it too), so a level-2
`## Phase 0` is seen (ADR-001). Side vs Production values come from two answers objects
built through `interview._build_answers(preset=…)`, the only path that materialises
`_preset_extras` (ADR-008) — `synthesize(preset=)` alone does not vary the knobs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import step_sensitivity as ss
from harness_maker.interview import _build_answers
from harness_maker.models import (
    DevMode,
    HarnessConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from .conftest import pin_install_ref
from .test_command_size_budget import headings

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGES = ("research", "spec", "plan", "execute", "review", "verify", "wrapup")


def _answers(preset: Preset, dev_mode: DevMode) -> InterviewAnswers:
    return _build_answers(
        locale="en", targets=[Target.CLAUDE_CODE], preset=preset, dev_mode=dev_mode
    )


def _render_arm(preset: Preset, dev_mode: DevMode, tmp: Path) -> dict[str, str]:
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(ProjectProfile(), _answers(preset, dev_mode), preset=preset),
            tmp,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
    root = tmp / "commands" / "hm"
    return {s: (root / f"{s}.md").read_text(encoding="utf-8") for s in STAGES}


@pytest.fixture(scope="module")
def rendered_arms(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[tuple[Preset, DevMode], dict[str, str]]:
    return {
        arm: _render_arm(arm[0], arm[1], tmp_path_factory.mktemp(f"{arm[0].value}-{arm[1].value}"))
        for arm in ss.ARMS
    }


@pytest.fixture(scope="module")
def ordinals_by_stage(
    rendered_arms: dict[tuple[Preset, DevMode], dict[str, str]],
) -> dict[str, set[str]]:
    union: dict[str, set[str]] = {s: set() for s in STAGES}
    for arm, texts in rendered_arms.items():
        for stage, text in texts.items():
            ords = ss.ordinals_from_headings(headings(text))
            dupes = sorted({o for o in ords if ords.count(o) > 1})
            # ADR-001: a second `Step 1` in one stage would collapse into the first's entry
            # and dodge classification — assert per-stage uniqueness before the set-union.
            assert not dupes, f"{arm} {stage}: duplicate ordinals {dupes}"
            union[stage].update(ords)
    return union


# ── S1 / AC-001 ──────────────────────────────────────────────────────────────


def test_arms_is_preset_times_dev_mode() -> None:
    """Hand-enumerated, not recomputed from the enums — a filtered or third-axis ARMS must
    fail here independently of the production expression."""
    assert set(ss.ARMS) == {
        (Preset.SIDE, DevMode.SPEC_DRIVEN),
        (Preset.SIDE, DevMode.TASK_DRIVEN),
        (Preset.PRODUCTION, DevMode.SPEC_DRIVEN),
        (Preset.PRODUCTION, DevMode.TASK_DRIVEN),
    }


def test_every_rendered_heading_is_classified(ordinals_by_stage: dict[str, set[str]]) -> None:
    failures = ss.coverage_failures(ordinals_by_stage, ss.REGISTRY)
    assert failures == [], f"unclassified headings: {failures}"
    keys = {(e.stage, e.ordinal) for e in ss.REGISTRY}
    for e in ss.REGISTRY:
        assert e.cls in ss.CLASSES
        if e.cls == "TUNE":
            assert e.remeasure_on, (e.stage, e.ordinal)
            assert e.measure_cmd, (e.stage, e.ordinal)
    assert len(keys) == len(ss.REGISTRY), "duplicate (stage, ordinal) keys"


def test_registry_has_no_orphan_entries(ordinals_by_stage: dict[str, set[str]]) -> None:
    orphans = ss.orphan_entries(ordinals_by_stage, ss.REGISTRY)
    assert orphans == [], (
        f"registry entries no ARMS render produces (add renders_when or delete): {orphans}"
    )


def test_orphan_entries_flags_a_dead_entry_and_exempts_renders_when(
    ordinals_by_stage: dict[str, set[str]],
) -> None:
    """Negative control for the orphan gate: an entry no ARMS render produces IS reported unless
    it declares `renders_when` (ADR-007 exemption)."""
    dead = ss.StepEntry(stage="verify", ordinal="Check 42", cls="INV", grade="*", source="x")
    assert ss.orphan_entries(ordinals_by_stage, (dead,)) == [("verify", "Check 42")]
    gated = ss.StepEntry(
        stage="verify",
        ordinal="Check 42",
        cls="INV",
        grade="*",
        source="x",
        renders_when="delegation.stages non-empty",
    )
    assert ss.orphan_entries(ordinals_by_stage, (gated,)) == []
    live = ss.StepEntry(stage="verify", ordinal="Check 2", cls="INV", grade="*", source="x")
    assert ss.orphan_entries(ordinals_by_stage, (live,)) == []


def test_registry_validates() -> None:
    ss.validate(ss.REGISTRY)
    bad_tune = ss.StepEntry(stage="review", ordinal="Step 99", cls="TUNE", grade="*", source="x")
    with pytest.raises(ValueError, match="TUNE"):
        ss.validate((bad_tune,))
    unprefixed = ss.StepEntry(
        stage="review",
        ordinal="Step 98",
        cls="TUNE",
        grade="*",
        source="x",
        remeasure_on=("model_release",),
        measure_cmd="bench run --exp x",
    )
    with pytest.raises(ValueError, match="repo"):
        ss.validate((unprefixed,))
    knob_without_ordering = ss.StepEntry(
        stage="review",
        ordinal="Step 97",
        cls="INV",
        grade="*",
        source="x",
        knob="reviewers.consensus",
    )
    with pytest.raises(ValueError, match="ordering"):
        ss.validate((knob_without_ordering,))


def test_extractor_matches_headings_helper(
    rendered_arms: dict[tuple[Preset, DevMode], dict[str, str]],
) -> None:
    """Every `Step|Phase|Check` heading `headings()` sees yields exactly one ordinal, and a
    level-2 heading is not skipped (the `#{3,5}` regex a first draft proposed would miss it)."""
    text = rendered_arms[(Preset.PRODUCTION, DevMode.SPEC_DRIVEN)]["execute"]
    hs = headings(text)
    expected = sorted(
        " ".join(h.lstrip("# ").split(" ")[:2]).rstrip(" —-")
        for h in hs
        if h.lstrip("# ").split(" ")[0] in {"Step", "Phase", "Check"}
    )
    assert sorted(ss.ordinals_from_headings(hs)) == expected
    assert ss.ordinals_from_headings({"## Phase 0 — Mechanical Pre-Checks"}) == ["Phase 0"]
    assert ss.ordinals_from_headings({"#### Step 4.4 — Measure (optional)"}) == ["Step 4.4"]
    assert ss.ordinals_from_headings({"### Not a step"}) == []


# ── S2 / AC-002 ──────────────────────────────────────────────────────────────


def test_unclassified_heading_fails(ordinals_by_stage: dict[str, set[str]]) -> None:
    injected = {s: set(v) for s, v in ordinals_by_stage.items()}
    injected["research"] |= set(ss.ordinals_from_headings({"### Step 9 — Foo"}))
    failures = ss.coverage_failures(injected, ss.REGISTRY)
    assert failures == [("research", "Step 9")]


# ── S3 / AC-003 ──────────────────────────────────────────────────────────────


def _configs() -> tuple[HarnessConfig, HarnessConfig]:
    side = synthesize(
        ProjectProfile(), _answers(Preset.SIDE, DevMode.SPEC_DRIVEN), preset=Preset.SIDE
    ).config
    prod = synthesize(
        ProjectProfile(), _answers(Preset.PRODUCTION, DevMode.SPEC_DRIVEN), preset=Preset.PRODUCTION
    ).config
    return side, prod


def test_side_defaults_consistent_with_registry() -> None:
    side, prod = _configs()
    violations = ss.side_ordering_violations(side, prod, ss.REGISTRY)
    assert violations == [], violations


def test_side_consistency_is_not_vacuous() -> None:
    """ADR-008: at least 3 compared knobs must actually differ, else the test cannot bind."""
    side, prod = _configs()
    differing = [
        e.knob
        for e in ss.knob_entries(ss.REGISTRY)
        if ss.knob_value(side, e) != ss.knob_value(prod, e)
    ]
    assert len(set(differing)) >= 3, differing


def test_side_more_aggressive_fails() -> None:
    """Negative control mutates the Side ANSWERS object, not a fixture string."""
    side_answers = _answers(Preset.SIDE, DevMode.SPEC_DRIVEN).model_copy(
        update={"max_review_rounds": 4}
    )
    side = synthesize(ProjectProfile(), side_answers, preset=Preset.SIDE).config
    _, prod = _configs()
    violations = ss.side_ordering_violations(side, prod, ss.REGISTRY)
    assert any(v[0] == "reviewers.max_review_rounds" for v in violations), violations


# ── S7 / AC-007 ──────────────────────────────────────────────────────────────


def test_docs_carry_classes() -> None:
    matrix = (REPO_ROOT / "work-docs" / "MATRIX-native-redundancy.md").read_text(encoding="utf-8")
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert ss.has_class_column(matrix)
    stripped = "| surface | native | cursor |\n|---|---|---|\n| /hm:loop | goal | parity |\n"
    assert not ss.has_class_column(stripped)
    assert ss.has_class_column("| surface | class | native |\n|---|---|---|\n| x | INV | y |\n")
    for cls in ss.CLASSES:
        assert cls in claude_md, cls
    assert "Side-preset only" in claude_md
    assert f"unsourced: {ss.unsourced_count(ss.REGISTRY)}" in claude_md
    assert "toggle" in claude_md
    assert "renders_when" in claude_md
    for row in ss.matrix_rows(ss.REGISTRY):
        assert row in matrix, row[:80]
