"""Phase 2 render tests for PLAN-spec-requirement-gate.

Asserts that:
(a) task-driven render of plan.md.j2 does NOT contain the Step 1.7 block /
    any spec_need reference (byte-unchanged path for task-driven users).
(b) spec-driven render DOES contain Step 1.7.
(c) seam grep: the spec-driven rendered prose contains the literal CLI calls
    the module exposes — proves wiring per the project's prose<>module lesson.
(d) the rendered prose contains the anti-loop guard phrase (surface-never-re-invoke).

Round 2 additions:
(FIX-1) spec-driven Step 5 frontmatter MUST include spec_need_verdict and spec_need_target
        keys; Step 6 MUST include the assertion that these are required.
(FIX-6) spec_need CLI calls MUST use --root <WT> (not --root .) so hashes are
        computed against the worktree files, not project-root files.
(FIX-2) re-entry [Waive] sub-path MUST call marker-clear after waiver-set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import DevMode, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _plan(tmp_path: Path, dev_mode: DevMode) -> str:
    """Render a full harness and return the plan stage command body."""
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE],
            dev_mode=dev_mode,
        ),
    )
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    # The plan stage is rendered as both stages/plan.md and commands/hm/plan.md;
    # assert against the command file — the canonical user-facing artifact.
    plan_files = list(tmp_path.rglob("commands/hm/plan.md"))
    assert plan_files, "plan.md command file not found in rendered output"
    return plan_files[0].read_text(encoding="utf-8")


# ── (a) task-driven: Step 1.7 ABSENT ────────────────────────────────────────


@pytest.fixture(scope="module")
def task_driven_plan(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("plan-task")
    return _plan(out, DevMode.TASK_DRIVEN)


def test_task_driven_omits_step_1_7_heading(task_driven_plan: str) -> None:
    """(a) Task-driven render must not contain the Step 1.7 heading."""
    assert "Step 1.7" not in task_driven_plan, (
        "task-driven plan.md must NOT contain Step 1.7 — spec-need detection is spec-driven-only"
    )


def test_task_driven_omits_spec_need_cli(task_driven_plan: str) -> None:
    """(a) Task-driven render must not reference the spec_need CLI module."""
    assert "harness_maker.spec_need" not in task_driven_plan, (
        "task-driven plan.md must NOT reference harness_maker.spec_need — "
        "byte-unchanged path for task-driven users"
    )


def test_task_driven_omits_marker_read(task_driven_plan: str) -> None:
    """(a) Task-driven render must not contain marker-read call."""
    # 'marker-read' also appears in ADR text sometimes; guard for CLI call form
    assert "spec_need marker-read" not in task_driven_plan, (
        "task-driven plan.md must not call spec_need marker-read"
    )


# ── (b) spec-driven: Step 1.7 PRESENT ───────────────────────────────────────


@pytest.fixture(scope="module")
def spec_driven_plan(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("plan-spec")
    return _plan(out, DevMode.SPEC_DRIVEN)


def test_spec_driven_includes_step_1_7_heading(spec_driven_plan: str) -> None:
    """(b) Spec-driven render must include the Step 1.7 heading."""
    assert "Step 1.7" in spec_driven_plan, (
        "spec-driven plan.md must contain Step 1.7 — SPEC-need detection block"
    )


def test_spec_driven_has_step_1_7_before_step_2(spec_driven_plan: str) -> None:
    """(b) Step 1.7 must appear before Step 2 in the rendered plan."""
    idx_17 = spec_driven_plan.find("Step 1.7")
    idx_2 = spec_driven_plan.find("### Step 2 — SPEC inheritance check")
    assert idx_17 > 0, "Step 1.7 heading not found"
    assert idx_2 > 0, "Step 2 heading not found"
    assert idx_17 < idx_2, f"Step 1.7 (at {idx_17}) must appear before Step 2 (at {idx_2})"


# ── (c) seam grep: literal CLI calls present ─────────────────────────────────


def test_spec_driven_seam_prefilter(spec_driven_plan: str) -> None:
    """(c) Spec-driven prose must contain the literal prefilter CLI call."""
    assert "python -m harness_maker.spec_need prefilter" in spec_driven_plan, (
        "spec-driven plan.md must call 'python -m harness_maker.spec_need prefilter' "
        "— proves module wiring (seam test per project memory lesson)"
    )


def test_spec_driven_seam_marker_read(spec_driven_plan: str) -> None:
    """(c) Spec-driven prose must contain the literal marker-read CLI call."""
    assert "python -m harness_maker.spec_need marker-read" in spec_driven_plan, (
        "spec-driven plan.md must call 'python -m harness_maker.spec_need marker-read' "
        "— proves module wiring"
    )


def test_spec_driven_seam_op_check(spec_driven_plan: str) -> None:
    """(c) Spec-driven prose must contain the literal op-check CLI call."""
    assert "python -m harness_maker.spec_need op-check" in spec_driven_plan, (
        "spec-driven plan.md must call 'python -m harness_maker.spec_need op-check' "
        "— proves module wiring"
    )


def test_spec_driven_seam_marker_write(spec_driven_plan: str) -> None:
    """(c) Spec-driven prose must contain the literal marker-write CLI call."""
    assert "python -m harness_maker.spec_need marker-write" in spec_driven_plan, (
        "spec-driven plan.md must call 'python -m harness_maker.spec_need marker-write' "
        "— proves module wiring"
    )


def test_spec_driven_seam_marker_clear(spec_driven_plan: str) -> None:
    """(c) Spec-driven prose must contain the literal marker-clear CLI call."""
    assert "python -m harness_maker.spec_need marker-clear" in spec_driven_plan, (
        "spec-driven plan.md must call 'python -m harness_maker.spec_need marker-clear' "
        "— proves module wiring"
    )


def test_spec_driven_seam_record(spec_driven_plan: str) -> None:
    """(c) Spec-driven prose must contain the literal record CLI call."""
    assert "python -m harness_maker.spec_need record" in spec_driven_plan, (
        "spec-driven plan.md must call 'python -m harness_maker.spec_need record' "
        "— proves module wiring"
    )


def test_spec_driven_seam_waiver_set(spec_driven_plan: str) -> None:
    """(c) Spec-driven prose must contain the literal waiver-set CLI call."""
    assert "python -m harness_maker.spec_need waiver-set" in spec_driven_plan, (
        "spec-driven plan.md must call 'python -m harness_maker.spec_need waiver-set' "
        "— proves module wiring"
    )


# ── (d) anti-loop guard phrase present ──────────────────────────────────────


def test_spec_driven_anti_loop_guard(spec_driven_plan: str) -> None:
    """(d) Spec-driven rendered prose must contain the anti-loop guard phrase."""
    # The PLAN specifies: surface-never-re-invoke as the hard guard phrase.
    assert "surface-never-re-invoke" in spec_driven_plan or (
        "NEVER auto-re-invoke" in spec_driven_plan
    ), (
        "spec-driven plan.md must contain the anti-loop guard phrase "
        "('surface-never-re-invoke' or 'NEVER auto-re-invoke') — "
        "ADR-009 one-shot safety contract"
    )


def test_spec_driven_adr_009_one_shot_text(spec_driven_plan: str) -> None:
    """(d) Step 1.7.0 must mention the one-shot skip semantics."""
    step_17_idx = spec_driven_plan.find("Step 1.7")
    assert step_17_idx > 0
    section = spec_driven_plan[step_17_idx : step_17_idx + 5000]
    assert "SKIP re-detection" in section or "skip re-detection" in section, (
        "Step 1.7.0 must explicitly state that re-entry skips re-detection "
        "(one-shot anti-loop contract, ADR-009)"
    )


# ── loop-mode halt prose ─────────────────────────────────────────────────────


def test_spec_driven_loop_mode_halt(spec_driven_plan: str) -> None:
    """Spec-driven plan must instruct loop-mode to HALT on SPEC-needed."""
    step_17_idx = spec_driven_plan.find("Step 1.7")
    assert step_17_idx > 0
    # Step 1.7 is long — use a larger window to cover both detection and the
    # loop-mode enforcement branch in §1.7.2.
    section = spec_driven_plan[step_17_idx : step_17_idx + 10000]
    assert "HALT" in section or "halt" in section, (
        "Step 1.7 must instruct loop-mode to HALT when a SPEC operation is needed"
    )
    assert "spec-required" in section or "spec_required" in section or "spec-needed" in section, (
        "Step 1.7 must set halt_reason indicating SPEC is required"
    )


# ── fail-closed not-evaluated semantics ─────────────────────────────────────


def test_spec_driven_fail_closed_not_evaluated(spec_driven_plan: str) -> None:
    """Spec-driven plan must explain not-evaluated as the fail-closed default."""
    step_17_idx = spec_driven_plan.find("Step 1.7")
    assert step_17_idx > 0
    # Use a 10000-char window — Step 1.7 is a large block covering §1.7.0–§1.7.3
    section = spec_driven_plan[step_17_idx : step_17_idx + 10000]
    assert "not-evaluated" in section, (
        "Step 1.7 must describe 'not-evaluated' as the fail-closed default verdict"
    )
    # Must distinguish from 'none' — none requires confident assertion
    assert "confident" in section, (
        "Step 1.7 must clarify that 'none' requires a confident assertion "
        "while 'not-evaluated' is the uncertain/empty-candidate default"
    )


# ── FIX-1: spec_need_verdict + spec_need_target in Step 5 frontmatter ────────


def test_spec_driven_frontmatter_includes_spec_need_verdict(spec_driven_plan: str) -> None:
    """FIX-1: spec-driven Step 5 frontmatter MUST include spec_need_verdict key.

    Without this key, an agent writing the frontmatter literally omits it →
    verify Check 6 sees no verdict → treats as N-A → gate defeated.
    """
    step5_idx = spec_driven_plan.find("### Step 5 — Write PLAN document")
    assert step5_idx > 0, "Step 5 heading not found"
    # Look in the frontmatter block (within 2000 chars of Step 5 heading)
    section = spec_driven_plan[step5_idx : step5_idx + 2000]
    assert "spec_need_verdict" in section, (
        "spec-driven Step 5 frontmatter MUST contain 'spec_need_verdict' key — "
        "absent key means agent omits it → Check 6 treats as N-A (FIX-1 Codex-1)"
    )


def test_spec_driven_frontmatter_includes_spec_need_target(spec_driven_plan: str) -> None:
    """FIX-1: spec-driven Step 5 frontmatter MUST include spec_need_target key."""
    step5_idx = spec_driven_plan.find("### Step 5 — Write PLAN document")
    assert step5_idx > 0, "Step 5 heading not found"
    section = spec_driven_plan[step5_idx : step5_idx + 2000]
    assert "spec_need_target" in section, (
        "spec-driven Step 5 frontmatter MUST contain 'spec_need_target' key — "
        "absent key means target is unknown at verify time (FIX-1)"
    )


def test_task_driven_frontmatter_does_not_include_spec_need_verdict(
    task_driven_plan: str,
) -> None:
    """FIX-1: task-driven Step 5 frontmatter must NOT include spec_need_verdict."""
    step5_idx = task_driven_plan.find("### Step 5 — Write PLAN document")
    assert step5_idx > 0, "Step 5 heading not found in task-driven plan"
    section = task_driven_plan[step5_idx : step5_idx + 2000]
    assert "spec_need_verdict" not in section, (
        "task-driven Step 5 frontmatter must NOT contain 'spec_need_verdict' — "
        "spec-driven-only key, byte-unchanged path for task-driven users"
    )


def test_spec_driven_step6_asserts_spec_need_verdict_present(spec_driven_plan: str) -> None:
    """FIX-1: spec-driven Step 6 MUST include an assertion that spec_need_verdict is present."""
    step6_idx = spec_driven_plan.find("### Step 6 — Verify write")
    assert step6_idx > 0, "Step 6 heading not found"
    section = spec_driven_plan[step6_idx : step6_idx + 2000]
    assert "spec_need_verdict" in section, (
        "spec-driven Step 6 verify-write MUST assert spec_need_verdict is present — "
        "closes the absent-case fail-open that defeats Check 6 (FIX-1)"
    )


# ── FIX-6: spec_need commands use --root <WT> not --root . ───────────────────


def test_spec_driven_spec_need_commands_use_root_wt(spec_driven_plan: str) -> None:
    """FIX-6: all spec_need CLI calls in spec-driven plan must use --root <WT>.

    Under feature_branch_workflow, files live in the worktree path <WT>.
    Using --root . reads project-root files (stale/absent for new add-case
    files), causing compute_subject_hash to raise → waiver breaks.
    """
    import re

    # Match single-line occurrences (the template has them on one line)
    single_line_pattern = re.compile(r"harness_maker\.spec_need \S+ .*?--root (\S+)")
    matches = single_line_pattern.findall(spec_driven_plan)
    # At minimum expect marker-read, marker-fresh, op-check, marker-clear,
    # record, marker-write, waiver-set to appear
    assert matches, "No spec_need --root arguments found in spec-driven plan"
    dot_roots = [m for m in matches if m.strip() in (".", "./", ".\\")]
    assert dot_roots == [], (
        f"spec_need CLI calls must use --root <WT>, not --root .; "
        f"found {len(dot_roots)} occurrences with '--root .' — FIX-6 (R2-P2b)"
    )


def test_task_driven_spec_need_commands_absent(task_driven_plan: str) -> None:
    """FIX-6: task-driven render must have no spec_need --root argument at all."""
    assert "--root" not in task_driven_plan or "harness_maker.spec_need" not in task_driven_plan, (
        "task-driven plan must not reference harness_maker.spec_need commands — byte-unchanged path"
    )


# ── FIX-2: re-entry [Waive] sub-path clears the marker ───────────────────────


def test_spec_driven_reentry_waive_clears_marker(spec_driven_plan: str) -> None:
    """FIX-2: the [Waive] sub-path in re-entry (§1.7.0) MUST call marker-clear.

    Without the clear, the marker persists → next /hm:plan re-enters §1.7.0 →
    op-check fails → waive prompt repeats forever (infinite dead-end loop).
    """
    step_17_idx = spec_driven_plan.find("Step 1.7")
    assert step_17_idx > 0
    # Use a large window to cover the whole §1.7.0–§1.7.3 block
    section_17 = spec_driven_plan[step_17_idx : step_17_idx + 15000]
    # Separate §1.7.0 from §1.7.1 by the section heading marker "#### 1.7.1"
    end_170 = section_17.find("#### 1.7.1")
    section_170 = section_17[:end_170] if end_170 > 0 else section_17[:8000]
    # The waive path in re-entry must include a marker-clear instruction
    assert "marker-clear" in section_170, (
        "§1.7.0 re-entry [Waive] sub-path must call marker-clear so the next "
        "/hm:plan run does not hit the fresh marker again (FIX-2 Codex-3)"
    )
