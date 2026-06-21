"""Render-boundary tests for loop-marker-session-scoping P4 wiring.

These assert the new session-scoping machinery is actually WIRED into the
rendered harness — the gap the k-of-3 review caught (unit tests passed while the
feature was dead because the producers never invoked it; CLAUDE.md §8).
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
    out = tmp_path_factory.mktemp("rendered-wiring")
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


@pytest.fixture(scope="module")
def hooks_json(rendered_root: Path) -> str:
    return (rendered_root / "hooks" / "hooks.json").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def loop_md(rendered_root: Path) -> str:
    return (rendered_root / "commands" / "hm" / "loop.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def plan_md(rendered_root: Path) -> str:
    return (rendered_root / "commands" / "hm" / "plan.md").read_text(encoding="utf-8")


def test_sessionstart_hook_registered(hooks_json: str) -> None:
    """C1: the SessionStart hook that sets HM_SESSION_ID must be registered."""
    assert "sessionid_envfile" in hooks_json, (
        "hooks.json must register harness_maker.hooks.sessionid_envfile on "
        "SessionStart, else HM_SESSION_ID is never set and the feature is dead"
    )


def test_loop_create_passes_claude_session_id(loop_md: str) -> None:
    """C2: the loop's `worktree create` must pass --claude-session-id."""
    assert "worktree create execute" in loop_md
    assert "--claude-session-id" in loop_md, (
        "loop.md must pass --claude-session-id to `worktree create` so the marker "
        "content header is populated; without it the Stop-hook never matches"
    )
    assert "$HM_SESSION_ID" in loop_md


def test_loop_global_marker_is_conditional(loop_md: str) -> None:
    """C3: the session-blind global .hm-loop-active is degraded-path only.

    Asserts the EXACT guard literal wraps the touch (re-review: the old
    substring check was near-tautological — `-z`/`HM_SESSION_ID` occur elsewhere,
    so it would not catch a regression to an unconditional touch).
    """
    # The claude (`!...`) branch renders this exact guarded form.
    expected = '!if [ -z "$HM_SESSION_ID" ] || [ "<WT>" = "$(pwd)" ]; then touch .hm-loop-active'
    assert expected in loop_md, (
        "loop.md must guard the global-marker touch with the exact "
        "[ -z $HM_SESSION_ID ] || [ <WT> = $(pwd) ] test (degraded path only)"
    )
    # There must be no UNGUARDED `touch .hm-loop-active` line.
    for line in loop_md.splitlines():
        if "touch .hm-loop-active" in line:
            assert "-z" in line or "HM_SESSION_ID" in line, (
                f"unguarded global-marker touch found: {line!r}"
            )


def test_plan_loop_mode_detection_is_session_scoped(plan_md: str) -> None:
    """bug-2: plan loop-mode detection must use the session-scoped CLI."""
    assert "loop-mode-active" in plan_md, (
        "plan.md Step 1.5 must detect loop-mode via `worktree loop-mode-active "
        "--claude-session-id` so another session's loop can't skip the interview"
    )
