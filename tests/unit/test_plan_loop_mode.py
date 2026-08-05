"""Loop-mode branch of ``plan.md.j2`` (PLAN-loop-mid-stop-and-review-skip Phase 4).

When the ``.hm-loop-active`` marker is present, plan skips Step 2 (SPEC inheritance)
and Step 3 (deep interview) and writes a per-iter scoped plan to
``<WT>/work-docs/PLAN-{slug}-iter{N}.md`` with frontmatter linking back to the master.

Phase 4's other half — the ``plan-exec-rev`` fused-registry entry and its rendered
command file — was deleted with the fused-workflow axis (PLAN-harness-diet ADR-001/002).
Per-iter stage selection now lives in ``loop.md.j2``'s ``--per-iter-stages`` (ADR-014),
covered by ``tests/structural/test_no_fused_workflow_axis.py`` and the loop render tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


@pytest.fixture(scope="module")
def rendered_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("rendered-phase4")
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


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
    assert has_skip, "Loop-mode plan branch must explicitly state Step 2/3 (interview) is skipped"


def test_plan_template_writes_per_iter_file(plan_md: str) -> None:
    """Loop-mode plan must write to <WT>/work-docs/PLAN-{slug}-iter{N}.md."""
    # The literal path pattern must appear so the LLM driver knows where to write.
    has_per_iter_path = "PLAN-{slug}-iter{N}.md" in plan_md or "PLAN-{slug}-iter" in plan_md
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


# ── loop.md per-iter stage selection (ADR-014) ──────────────────────────────


def test_loop_md_gate0_derives_expected_stages_from_the_stage_list(rendered_root: Path) -> None:
    """Gate 0 must read EXPECTED_STAGES off `STAGES`, not off a fused command file.

    The old table mapped each fused name to its stage sequence. With the axis gone
    (ADR-001/002) there is no file to derive from, and ADR-014 makes `STAGES` — the
    list validated at loop start — the single source. That closes the drift the table
    made possible: expected set and invoked set are now the same object.
    """
    loop_md = (rendered_root / "commands" / "hm" / "loop.md").read_text(encoding="utf-8")
    gate0_idx = loop_md.find("Gate 0 — Receipt verification")
    assert gate0_idx > 0, "loop.md missing the Gate 0 heading"
    section = loop_md[gate0_idx : gate0_idx + 5000]
    assert "`EXPECTED_STAGES` **is** `STAGES`" in section
    assert "plan-exec-rev" not in loop_md, "a fused workflow name survived in loop.md"


def test_loop_md_rejects_wrapup_as_a_per_iter_stage(rendered_root: Path) -> None:
    """ADR-014 consequence: loop close owns wrapup; a per-iter wrapup commits every iter."""
    loop_md = (rendered_root / "commands" / "hm" / "loop.md").read_text(encoding="utf-8")
    assert "--per-iter-stages" in loop_md
    assert "--per-iter-workflow" not in loop_md.split("Breaking (PLAN-harness-diet")[-1][200:], (
        "the retired flag may only appear in the migration note"
    )
    assert "`wrapup` is rejected" in loop_md or "'wrapup' is not allowed per iter" in loop_md
