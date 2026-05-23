"""Tests for PLAN-loop-mid-stop-and-review-skip Phase 4.

Phase 4 ships:
1. ``plan-exec-rev`` (3-stage: plan + execute + review) added to the fused
   workflow registry — distinct from the existing ``plan-exec-rev-wrap``
   (4-stage, includes wrapup) which is bad for per-iter loop use.
2. Loop-mode branch in ``plan.md.j2`` — when ``.hm-loop-active`` marker is
   present, skip Step 2 (SPEC inheritance) and Step 3 (deep interview);
   write per-iter scoped plan to ``<WT>/work-docs/PLAN-{slug}-iter{N}.md``
   with frontmatter linking back to the master PLAN.
3. ``loop.md.j2``'s Phase 3 EXPECTED_STAGES table now includes
   ``plan-exec-rev → plan,execute,review`` (re-added — Phase 3 review removed
   it because the registry entry didn't exist yet).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import (
    _PRODUCTION_STARTER,
    _SIDE_STARTER,
    interview,
)
from harness_maker.models import AtomicStage, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


# ── fused workflow registry ─────────────────────────────────────────────────


def test_plan_exec_rev_registered_in_side_starter() -> None:
    """SIDE preset must offer plan-exec-rev (3-stage) for loop per-iter planning."""
    assert "plan-exec-rev" in _SIDE_STARTER, (
        "plan-exec-rev (3-stage) must be in _SIDE_STARTER registry — "
        "loop-mode plan refinement needs it"
    )
    stages = _SIDE_STARTER["plan-exec-rev"]
    assert stages == [AtomicStage.PLAN, AtomicStage.EXECUTE, AtomicStage.REVIEW], (
        f"plan-exec-rev must be [PLAN, EXECUTE, REVIEW] only (no wrapup); got {stages}"
    )


def test_plan_exec_rev_registered_in_production_starter() -> None:
    assert "plan-exec-rev" in _PRODUCTION_STARTER, (
        "plan-exec-rev (3-stage) must be in _PRODUCTION_STARTER registry"
    )
    stages = _PRODUCTION_STARTER["plan-exec-rev"]
    assert stages == [AtomicStage.PLAN, AtomicStage.EXECUTE, AtomicStage.REVIEW]


def test_plan_exec_rev_wrap_still_exists_in_side() -> None:
    """plan-exec-rev (3-stage) is ADDITIONAL — the existing 4-stage variant must remain in SIDE."""
    # Note: pre-existing inconsistency — _PRODUCTION_STARTER never had
    # plan-exec-rev-wrap; out of Phase 4 scope to add it.
    assert "plan-exec-rev-wrap" in _SIDE_STARTER


# ── rendered fused workflow command file ────────────────────────────────────


@pytest.fixture(scope="module")
def rendered_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("rendered-phase4")
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def test_plan_exec_rev_command_file_rendered(rendered_root: Path) -> None:
    cmd = rendered_root / "commands" / "hm" / "plan-exec-rev.md"
    assert cmd.is_file(), (
        "plan-exec-rev.md fused workflow command file must be rendered "
        "when the registry has the entry"
    )
    body = cmd.read_text(encoding="utf-8")
    # Must fuse all 3 stages — receipt blocks (Phase 2) for each stage appear.
    assert "--stage plan" in body
    assert "--stage execute" in body
    assert "--stage review" in body
    # Must NOT include wrapup (the 4-stage variant is plan-exec-rev-wrap).
    assert "--stage wrapup" not in body, (
        "plan-exec-rev must not include wrapup stage — that's plan-exec-rev-wrap"
    )


# ── plan.md loop-mode branch ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def plan_md(rendered_root: Path) -> str:
    return (rendered_root / "commands" / "hm" / "plan.md").read_text(encoding="utf-8")


def test_plan_template_detects_loop_active_marker(plan_md: str) -> None:
    """Step 1.5 (or equivalent) must detect .hm-loop-active marker."""
    assert ".hm-loop-active" in plan_md, (
        "plan.md must reference .hm-loop-active marker for loop-mode detection"
    )


def test_plan_template_loop_mode_skips_interview(plan_md: str) -> None:
    """When in loop mode, deep interview (Step 3) must be explicitly skipped."""
    # Anchor on the Step 1.5 heading specifically (Step 1 short-circuit mentions
    # the marker first but is just a redirect; the real skip prose is in Step 1.5).
    step15_idx = plan_md.find("Step 1.5 — Loop-mode detection")
    assert step15_idx > 0, "plan.md missing Step 1.5 loop-mode detection heading"
    branch_section = plan_md[step15_idx : step15_idx + 2500]
    # Prose must say to skip the interview / Step 3.
    has_skip = (
        "skip Step 2" in branch_section
        or "skip Steps 2" in branch_section
        or "skip Step 3" in branch_section
        or "skip the interview" in branch_section
        or "no deep interview" in branch_section
    )
    assert has_skip, (
        "Loop-mode plan branch must explicitly state Step 2/3 (interview) is skipped"
    )


def test_plan_template_writes_per_iter_file(plan_md: str) -> None:
    """Loop-mode plan must write to <WT>/work-docs/PLAN-{slug}-iter{N}.md."""
    # The literal path pattern must appear so the LLM driver knows where to write.
    has_per_iter_path = (
        "PLAN-{slug}-iter{N}.md" in plan_md
        or "PLAN-{slug}-iter" in plan_md
    )
    assert has_per_iter_path, (
        "plan.md loop-mode branch must specify the per-iter PLAN path "
        "PLAN-{slug}-iter{N}.md (ADR-008)"
    )


def test_plan_template_per_iter_frontmatter_documented(plan_md: str) -> None:
    """ADR-008 frontmatter — derived_from + iter + phase — must be specified."""
    step15_idx = plan_md.find("Step 1.5 — Loop-mode detection")
    assert step15_idx > 0
    branch_section = plan_md[step15_idx : step15_idx + 2500]
    # All three frontmatter keys must be mentioned in the loop-mode prose.
    assert "derived_from" in branch_section, "loop-mode frontmatter missing derived_from"
    assert "iter:" in branch_section or "iter " in branch_section, (
        "loop-mode frontmatter missing iter"
    )
    assert "phase:" in branch_section or "phase " in branch_section, (
        "loop-mode frontmatter missing phase"
    )


def test_plan_template_loop_mode_reads_current_iter(plan_md: str) -> None:
    """Loop-mode must derive N from .current-iter (Phase 3 contract)."""
    step15_idx = plan_md.find("Step 1.5 — Loop-mode detection")
    assert step15_idx > 0
    branch_section = plan_md[step15_idx : step15_idx + 2500]
    assert ".current-iter" in branch_section, (
        "Loop-mode plan must read iter N from <WT>/.claude/.hm-iter-receipts/.current-iter"
    )


# ── loop.md EXPECTED_STAGES table re-includes plan-exec-rev ─────────────────


def test_loop_md_expected_stages_includes_plan_exec_rev(rendered_root: Path) -> None:
    """Now that plan-exec-rev exists in the registry, loop.md's Gate 0 table must list it.

    Phase 3 review removed it because the registry didn't have it; Phase 4 adds
    the registry entry, so the table must be re-amended.
    """
    loop_md = (rendered_root / "commands" / "hm" / "loop.md").read_text(encoding="utf-8")
    gate0_idx = loop_md.find("Gate 0 — Receipt verification")
    section = loop_md[gate0_idx : gate0_idx + 5000]
    assert "`plan-exec-rev`" in section, (
        "Gate 0 EXPECTED_STAGES table must list plan-exec-rev → plan,execute,review "
        "now that the registry has the entry (Phase 4 amendment to Phase 3's P0 fix)"
    )
