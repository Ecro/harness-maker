"""PLAN-fleet-10-20-parallel-safety Phase 1 — C1 loud degraded floor.

The Phase-0 spike (signal_present: false) proved the Stop-hook cannot attribute a
degraded empty-header marker to the stopping session (cwd is the project root, no
worktree field), so the ownership self-heal is dropped. The floor is the agreed
fix: both surfaces that already detect the degraded state must describe the REAL
WSL2/Claude symptom — the loop self-stops after one iteration — instead of the
inaccurate "peers block each other" wording (that is the Cursor/Codex
id-less-stdin case, not the Claude-on-WSL2 case the user runs).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.readiness import Signal, _dim_guardrails
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def loop_md(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("rendered-floor")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    render(
        synthesize(p, interview(p, autoloop_mode=True)),
        out,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return (out / "commands" / "hm" / "loop.md").read_text(encoding="utf-8")


def _degraded_block(loop_md: str) -> str:
    """Return the rendered degraded-path Bash region (the marker-touch guard).

    Anchored on the `touch .hm-loop-active` COMMAND (not the first prose mention
    of the marker), so the window always covers the rendered guard body.
    """
    idx = loop_md.find("touch .hm-loop-active")
    assert idx > 0, "loop.md missing the degraded global-marker guard command"
    return loop_md[idx : idx + 900]


def test_loop_degraded_block_warns_self_stop(loop_md: str) -> None:
    """The Claude+HM_SESSION_ID-empty branch must warn the loop STOPS after iter 1."""
    lowered = _degraded_block(loop_md).lower()
    assert "stop" in lowered, "degraded warning must say the loop stops"
    assert "one iteration" in lowered or "iteration 1" in lowered, (
        "degraded warning must state the loop self-stops after one iteration"
    )


def test_loop_degraded_block_splits_claude_vs_cursor(loop_md: str) -> None:
    """The branch must distinguish the Claude (CLAUDECODE) self-stop case from the
    non-Claude / no-isolation 'parallel not isolated' case — different symptoms."""
    block = _degraded_block(loop_md)
    assert "CLAUDECODE" in block, (
        "degraded guard must branch on CLAUDECODE to give the accurate Claude-WSL2 "
        "self-stop message vs the Cursor/Codex parallel-isolation caveat"
    )


def test_loop_degraded_block_keeps_peer_safe_note(loop_md: str) -> None:
    """The Claude self-stop case must NOT claim peers are affected (spike: a
    valid-id session ignores the global; peers are unaffected)."""
    block = _degraded_block(loop_md).lower()
    assert "peers are not affected" in block, (
        "the Claude self-stop branch must clarify peers are NOT affected"
    )


@pytest.fixture
def claude_session_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("HM_SESSION_ID", raising=False)


def _write_min_harness(project_dir: Path) -> None:
    hooks_dir = project_dir / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    command = "uv run python -m harness_maker.hooks.sessionid_envfile"
    (hooks_dir / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": command}]}]},
                "preset": "Production",
            }
        ),
        encoding="utf-8",
    )
    (project_dir / ".claude" / "harness.yaml").write_text(
        "targets:\n  - claude-code\n", encoding="utf-8"
    )


def _find(signals: list[Signal], sig_id: str) -> Signal | None:
    return next((s for s in signals if s.id == sig_id), None)


def test_readiness_live_message_describes_self_stop(
    tmp_path: Path, claude_session_unset: None
) -> None:
    """sessionid_envfile_live's failing message must describe the self-stop
    symptom, not the inaccurate 'peers block each other's Stop'."""
    _write_min_harness(tmp_path)
    sig = _find(_dim_guardrails(tmp_path).signals, "sessionid_envfile_live")
    assert sig is not None, "expected a live signal when CLAUDECODE set"
    assert not sig.passed, "live signal must fail when HM_SESSION_ID unset"
    detail = f"{sig.evidence} {sig.action or ''}".lower()
    assert "stop" in detail, f"live signal must mention stop; got {sig.evidence!r}"
    assert "one iteration" in detail or "self-stop" in detail or "iteration 1" in detail, (
        f"live signal must describe loop self-stop; got {sig.evidence!r}"
    )
    assert "peers block each other" not in detail, (
        "the inaccurate peer-block wording must be removed (spike: peers unaffected)"
    )
