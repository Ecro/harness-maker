"""Phase 5: the delegate-on wrapup artifact carries BOTH paths, and the git tail stays.

ADR-006's fallback only exists if the artifact it falls back INTO is reachable. Since stage 2b of
the light lane (SPEC-hm-light-lane-s2b) the inline body no longer sits in the command: the command
carries a pointer to `.claude/hm/wrapup-steps.md`, the same file the delegate reads, so the
degraded path and the dispatched path share one text. The tests that are about the body read the
command with that file expanded in place (`tests/stage_surface.py`).

These are render-GREP tests: they prove the instruction is PRESENT. They cannot
prove the interpreting model obeys it. That asymmetry is deliberate and is the same
position the economics prose layer takes.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import (
    DelegationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from tests.stage_surface import stage_text

# The `workflow` Production cap from `context_lint.THRESHOLDS`. Nothing ENFORCES it
# for an atomic stage command — `readiness._CONTEXT_LIMITS` has no command row — so
# this is a chosen yardstick, stated rather than discovered. See the note in
# `test_the_delegate_on_command_size_is_pinned_so_growth_is_a_decision`.
_WORKFLOW_PRODUCTION_CAP = 600


def _flat(text: str) -> str:
    """Collapse whitespace before matching prose.

    Markdown prose is hard-wrapped, so a phrase the template really contains can be
    split across a newline. Asserting the unwrapped form against the raw text fails for
    formatting rather than for content — and the fix would be to re-wrap the template
    to suit the test, which is backwards.
    """
    return " ".join(text.split())


def _wrapup(
    tmp_path: Path,
    *,
    preset: str = "Production",
    stages: list[str] | None = None,
    feature_branch: bool = True,
    expand: bool = True,
) -> str:
    # `feature_branch_workflow` must be set EXPLICITLY: constructing `InterviewAnswers`
    # directly bypasses `interview()`'s `_preset_extras`, so the flag-gated Step 7.7
    # (`task-land`) would simply not render and a test asserting its presence would be
    # measuring the fixture, not the template.
    answers = InterviewAnswers(
        preset=Preset(preset),
        targets=[Target.CLAUDE_CODE],
        delegation=DelegationConfig(stages=stages or []),
        worktree={"feature_branch_workflow": feature_branch},
    )
    render(synthesize(ProjectProfile(), answers), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    if not expand:
        return (tmp_path / "commands" / "hm" / "wrapup.md").read_text(encoding="utf-8")
    # Steps 1-5.6 live in `.claude/hm/wrapup-steps.md` on a delegated harness
    # (SPEC-hm-light-lane-s2b); the tests below that are about the body read it in place.
    return stage_text(tmp_path, "wrapup")


# ------------------------------------------------------------------ delegate OFF


def test_the_default_render_carries_no_dispatch_block(tmp_path: Path) -> None:
    """ADR-011 ships default-empty for one release. A dispatch block present in the
    default artifact would make the soak meaningless — and would mean every existing
    user's next `--update` silently switched their wrapup to a subagent."""
    body = _wrapup(tmp_path)

    assert "stage-delegate" not in body
    assert "wrapup_brief" not in body




# ------------------------------------------------------------------ delegate ON


def test_the_delegate_on_render_carries_the_dispatch(tmp_path: Path) -> None:
    body = _wrapup(tmp_path, stages=["wrapup"])

    assert "stage-delegate" in body
    assert "hm wrapup_brief" in body




def test_the_inline_body_is_labelled_as_the_degraded_path(tmp_path: Path) -> None:
    """Without the heading, a reader of the delegate-on artifact sees the body twice
    over and cannot tell which one runs."""
    body = _wrapup(tmp_path, stages=["wrapup"])

    assert "degraded" in body.lower()










# ------------------------------------------------------------------ size




# Expanded-stage cost of delegating wrapup: the dispatch block, the existence check and the
# pointer, with the moved body read back in place. Pinned as an equality, not a ceiling, so a
# line added here is a visible edit to this number rather than headroom someone spends silently.
#   +60 (ADR-006: "the cap exactly") → +66 (2026-10-14, SPEC-hm-light-lane-s2b: the Read-path
#   lines and the pointer) → +77 (2026-10-14, /hm:review round 1: S1's `!test -r` existence check
#   before the dispatch, +8, and K2's "fix the gap by the step that owns it" sentence, +3).
#   → +76 (2026-10-14, stage 2b confirmation pass: the mismatch bullet's sentence became the shared
#   one-line pointer, -2, and the existence check now names the delegate's `base_root` path, +1).
_DELEGATED_EXPANDED_DELTA = 76




# ------------------------------------------------- review round 2 (M-03, M-04)






