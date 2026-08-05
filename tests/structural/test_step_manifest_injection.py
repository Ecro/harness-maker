"""P2 structural gate: the step-manifest preamble is injected into the command
wrappers (Claude + Codex) and excluded from skills.

ADR-003 of PLAN-latency-worktree-step-preview: every atomic + workflow command
echoes its intended Procedure steps before starting, suppressed under an active
loop (`.hm-loop-active`). Skills are deliberately excluded (they fire mid-task,
not as user-invoked commands). This is the wiring contract; the snapshot suite
locks the rendered output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TPL = REPO_ROOT / "src/harness_maker/templates"
PARTIAL_REL = "agents/_partials/step_manifest.md.j2"
PARTIAL = TPL / PARTIAL_REL

# The two fused wrappers (`workflow_command.md.j2`, `codex/workflow_skill.md.j2`) were
# deleted with the fused axis (PLAN-harness-diet ADR-001), leaving one wrapper per target.
WRAPPERS = (
    "commands/hm/atomic_command.md.j2",
    "codex/stage_skill.md.j2",
)


def test_partial_exists_with_suppression_and_intended_framing() -> None:
    assert PARTIAL.is_file(), f"missing step-manifest partial: {PARTIAL}"
    body = PARTIAL.read_text(encoding="utf-8")
    assert ".hm-loop-active" in body, (
        "manifest must reference the loop-suppression marker (ADR-003)"
    )
    assert "intended" in body.lower(), (
        "manifest must frame steps as INTENDED/conditional, not committed — "
        "else it collides with skip-heuristics and early-FAIL stops"
    )
    # P1 (REVIEW round 2): the suppression check must tell the LLM how to resolve
    # the project root from inside a worktree — a naive "at the project root"
    # check misses the marker when cwd is in .worktrees/<name>/.
    assert ".worktrees" in body, (
        "manifest suppression must explain project-root resolution from a "
        "worktree (cwd may be inside .worktrees/<name>/), not just say "
        "'at the project root'"
    )


@pytest.mark.parametrize("wrapper", WRAPPERS)
def test_wrapper_includes_step_manifest(wrapper: str) -> None:
    src = (TPL / wrapper).read_text(encoding="utf-8")
    # Trim-agnostic: match the include regardless of `{% ` vs `{%- ` whitespace control.
    assert f'include "{PARTIAL_REL}"' in src or f"include '{PARTIAL_REL}'" in src, (
        f"{wrapper} must {{% include %}} the step_manifest partial (ADR-003)"
    )


def test_skills_do_not_include_step_manifest() -> None:
    offenders = [
        str(p.relative_to(TPL))
        for p in (TPL / "skills").glob("*/SKILL.md.j2")
        if PARTIAL_REL in p.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"skills must NOT carry the step manifest (ADR-003 excludes them): {offenders}"
    )


def test_stages_do_not_include_step_manifest() -> None:
    """Stage fragments must stay manifest-free so a fused workflow emits exactly
    ONE manifest (from the wrapper), not one per fused stage (REVIEW round 1)."""
    offenders = [
        str(p.relative_to(TPL))
        for p in (TPL / "stages").glob("*.md.j2")
        if PARTIAL_REL in p.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"stage fragments must NOT include the manifest (one-per-workflow invariant): {offenders}"
    )
