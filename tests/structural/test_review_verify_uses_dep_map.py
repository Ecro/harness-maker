"""PLAN-dep-map-alias-imports Phase 4 — the review auto-fix verify step is dep-map driven.

The artifact set is DISCOVERED, never enumerated. Two hand-derivations of it were wrong
before this file existed:

  * A grep of the committed render was truncated by `| head -10` and reported 5 of 7.
  * The corrected derivation ("`_WORKFLOWS` + the atomic command + `.claude/stages/`")
    misses `exec-rev-ver-wrap`, a fused workflow absent from that table, and misses the
    codex skill entirely — `render()` writes codex artifacts to `root/.agents`, OUTSIDE
    the directory it is handed, so a scan of the render root finds nothing there.

The count itself is config-dependent (7 for this repo's own harness.yaml, 8 for the
default Production profile), so a magic number would be wrong too. What is asserted
instead is that all four FAMILIES are represented and that every discovered artifact
satisfies the property.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from tempfile import mkdtemp

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from tests.stage_surface import expand_references

#: The review stage's auto-fix loop. Present in every render that inlines the stage.
_LOOP_HEADING = "## Auto-Fix Loop"
#: Bounds of the verify step inside that loop.
# Anchored on the step NAMES, not their numbers. PLAN-review-round-inflation renumbered
# the Auto-Fix Loop (attribution and the trigger moved ahead of fix selection) and these
# constants — pinned as "3. …" / "4. …" — broke on a change that never touched the verify
# step's content, only its address. That is `[fail:test]
# test-pins-retired-implementation-name`, which this repo has hit before.
_STEP_START = "**Verify build**"
_STEP_END = "**Re-review"

_SKILL = "targeted-test-selection"


@cache
def _render_root() -> Path:
    """Render Production for claude + codex once for the module.

    Populated from inside a test so `conftest.py`'s autouse install-ref pin is active
    (`[fail:test] snapshot-regen-inside-worktree` instance 13).
    """
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CODEX]
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-review-verify-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


def _review_bearing_artifacts() -> dict[str, str]:
    """Every rendered document that inlines the review stage, discovered by content."""
    root = _render_root()
    return {
        str(path.relative_to(root)): text
        for path in sorted(root.rglob("*.md"))
        if _LOOP_HEADING
        in (text := expand_references(path.read_text(encoding="utf-8"), root / ".claude" / "hm"))
    }


def _verify_step(body: str) -> str:
    start = body.index(_STEP_START)
    return body[start : body.index(_STEP_END, start)]




def test_every_review_bearing_artifact_routes_verification_through_the_skill() -> None:
    """The property, asserted over the discovered set rather than a listed one."""
    offenders = {
        path: step
        for path, body in _review_bearing_artifacts().items()
        if _SKILL not in (step := _verify_step(body))
    }
    assert offenders == {}, f"verify step does not reference {_SKILL}: {sorted(offenders)}"


def test_no_review_bearing_artifact_runs_the_suite_unconditionally() -> None:
    """`uv run pytest -x` in the auto-fix verify step is the whole defect being removed."""
    offenders = [
        path
        for path, body in _review_bearing_artifacts().items()
        if "uv run pytest -x" in _verify_step(body)
    ]
    assert offenders == [], f"unconditional full-suite run survives in: {offenders}"


def test_the_verify_step_slice_is_non_empty_everywhere() -> None:
    """Guards the two assertions above against vacuity.

    `_verify_step` raises if either bound is missing, but a bound that drifted to a
    position yielding an empty slice would make `not in` trivially true and both checks
    would pass over nothing.
    """
    for path, body in _review_bearing_artifacts().items():
        assert len(_verify_step(body)) > 50, f"verify-step slice is degenerate in {path}"


