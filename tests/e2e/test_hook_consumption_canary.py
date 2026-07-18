"""Consumption canary — the real `claude` binary fires a PostToolUse hook that
harness-maker wired into `.claude/settings.json` (PLAN-permission-deny-and-hooks-wiring
Phase 9, ADR-009).

Every other test in this repo asserts what harness-maker *renders*. None proves
the rendered hook actually *fires* in Claude Code — the exact gap that let the
`.claude/hooks/hooks.json` location stay dead for 39 releases while every unit
test was green (a circular oracle: the tests read the same wrong location the
emitter wrote). This canary closes it by running the live binary and asserting a
`post_tool_use` telemetry entry appears where `_metrics_io` reads it.

It is deliberately paired: the positive test proves firing from settings.json;
the discriminator proves the SAME run with hooks in the retired
`.claude/hooks/hooks.json` location emits NOTHING — so a regression that moved
the hooks back would turn this suite red, not green. Both assert the tool call
demonstrably happened (the file's first line is in claude's output), so neither
can pass vacuously when claude fails to invoke a tool.

Requires `INTEGRATION=1` and the `claude` binary (a SKIP does not discharge the
Phase-9 exit criterion — run it on a machine that has both).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from harness_maker._metrics_io import iter_recent_entries

REPO_ROOT = Path(__file__).resolve().parents[2]
_FIRST_LINE = "FIRSTLINE-CANARY-8f2a"

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION") or shutil.which("claude") is None,
    reason="needs INTEGRATION=1 and the claude binary in PATH",
)

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "canary",
    "GIT_AUTHOR_EMAIL": "canary@test",
    "GIT_COMMITTER_NAME": "canary",
    "GIT_COMMITTER_EMAIL": "canary@test",
}


def _git(dst: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=dst,
        check=True,
        capture_output=True,
        env={**os.environ, **_GIT_ENV},
    )


def _prep_sandbox(dst: Path) -> None:
    """Render a fresh harness into `dst` via `make` (the fixture's `.claude/` is
    gitignored + generated, so a checkout does not carry it — rendering makes the
    canary self-contained and portable), then seed a git repo + a file to read.

    The rendered telemetry hook runs `uv run --with <this repo> python -m
    harness_maker.telemetry`, so it is self-contained on the machine under test.
    """
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "pyproject.toml").write_text(
        '[project]\nname = "canary"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n',
        encoding="utf-8",
    )
    (dst / "target.txt").write_text(f"{_FIRST_LINE}\nsecond line\n", encoding="utf-8")
    _git(dst, "init", "-b", "main")
    _git(dst, "add", "-A")
    _git(dst, "commit", "-m", "seed")
    subprocess.run(
        ["uv", "run", "python", "-m", "harness_maker.cli", "make", str(dst), "--autoloop"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    settings = dst / ".claude" / "settings.json"
    assert settings.is_file(), "make did not render .claude/settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "PostToolUse" in data.get("hooks", {}), (
        "rendered settings.json has no PostToolUse hook — the canary cannot fire"
    )
    obs = dst / ".claude" / "observability"
    if obs.is_dir():
        for f in obs.glob("metrics-*.jsonl"):
            f.unlink()


def _demote_hooks_to_dead_location(dst: Path) -> None:
    """Simulate the pre-Phase-1 layout (d895800b): hooks live ONLY in the retired
    `.claude/hooks/hooks.json`, which Claude Code never reads, and settings.json
    has no `hooks` key."""
    settings = dst / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    hooks = data.pop("hooks", {})
    assert hooks, "fixture settings.json must carry hooks to demote"
    settings.write_text(json.dumps(data, indent=2), encoding="utf-8")
    dead = dst / ".claude" / "hooks" / "hooks.json"
    dead.parent.mkdir(parents=True, exist_ok=True)
    dead.write_text(json.dumps({"hooks": hooks}, indent=2), encoding="utf-8")
    _git(dst, "add", "-A")
    _git(dst, "commit", "-m", "demote hooks to dead location")


def _run_claude_reading_target(dst: Path) -> str:
    """Force a single Read tool call; return claude's stdout."""
    proc = subprocess.run(
        [
            "claude",
            "-p",
            "Read the file target.txt and print only its first line.",
            "--allowedTools",
            "Read",
            "--setting-sources",
            "project,local",
            "--dangerously-skip-permissions",
            "--output-format",
            "text",
            "--no-session-persistence",
        ],
        cwd=dst,
        capture_output=True,
        text=True,
        timeout=240,
    )
    return proc.stdout


def _post_tool_use_count(dst: Path) -> int:
    obs = dst / ".claude" / "observability"
    return sum(1 for _ in iter_recent_entries(obs, days=1, event="post_tool_use"))


def test_posttooluse_hook_fires_from_settings_json(tmp_path: Path) -> None:
    """The Phase-1 wiring: a hook in settings.json actually fires in Claude Code."""
    dst = tmp_path / "sandbox"
    _prep_sandbox(dst)
    assert _post_tool_use_count(dst) == 0, "baseline telemetry must be empty"

    out = _run_claude_reading_target(dst)

    assert _FIRST_LINE in out, f"claude did not read target.txt (no tool call) — output was:\n{out}"
    assert _post_tool_use_count(dst) >= 1, (
        "a Read tool call happened but no post_tool_use telemetry appeared — the "
        "PostToolUse hook in .claude/settings.json did not fire"
    )


def test_hooks_in_dead_location_emit_nothing(tmp_path: Path) -> None:
    """Discriminator (the exit criterion's FAIL half): the SAME run with hooks in
    the retired .claude/hooks/hooks.json emits no telemetry — proving this canary
    tests the wiring, not something incidental. If this ever passes telemetry, the
    positive test above is worthless."""
    dst = tmp_path / "sandbox-old"
    _prep_sandbox(dst)
    _demote_hooks_to_dead_location(dst)
    assert _post_tool_use_count(dst) == 0, "baseline telemetry must be empty"

    out = _run_claude_reading_target(dst)

    # The tool call MUST have happened (else the 0 below is a vacuous pass).
    assert _FIRST_LINE in out, (
        f"claude did not read target.txt (no tool call) — the discriminator would "
        f"be vacuous. Output was:\n{out}"
    )
    assert _post_tool_use_count(dst) == 0, (
        "hooks in the retired .claude/hooks/hooks.json fired telemetry — Claude Code "
        "should never read that location (the whole premise of Phase 1)"
    )
