"""Render-surface guard for PLAN-sessionid-env-propagation (risk R2).

ADR-004's `probe_wired` signal catches an un-wired probe at RUNTIME, in a session the
user happens to be running. This catches it at CI, on the template that produces the
command. Both exist because the failure is silent in each other's absence: a template
edit that drops the flag leaves every static check green.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_TEMPLATES = Path(__file__).parents[2] / "src" / "harness_maker" / "templates"

_HEALTH = _TEMPLATES / "commands" / "hm" / "health.md.j2"


def _unescaped(line: str) -> str:
    """Codex branches wrap the command in `Bash("...")` and escape inner quotes, so the
    same instruction ships in two spellings. Normalise before asserting — a guard that
    only knows one spelling passes the other by accident."""
    return line.replace('\\"', '"')


def _read(path: Path) -> str:
    assert path.is_file(), f"template moved or was renamed: {path}"
    return path.read_text(encoding="utf-8")


def test_health_template_passes_the_session_id() -> None:
    """`hm cli health` is the only rendered consumer of the readiness tri-state."""
    body = _read(_HEALTH)
    assert "cli health" in body, "the health invocation moved — re-point this guard"
    assert '--session-id "$HM_SESSION_ID"' in body, (
        "health.md.j2 must forward the session id; without it every rendered harness "
        "lands in the probe_wired branch and the live probe can never pass"
    )


def test_session_id_is_quoted_in_every_template_that_passes_it() -> None:
    """An unquoted `$HM_SESSION_ID` collapses `""` into a missing argv element, which
    turns genuine degradation (hard-gated) into an unwired probe (not gated) — the two
    states ADR-001 exists to keep apart."""
    offenders: list[str] = []
    for path in _TEMPLATES.rglob("*.j2"):
        text = path.read_text(encoding="utf-8")
        if "--session-id" not in text:
            continue
        for line in text.splitlines():
            if (
                "--session-id" in line
                and '--session-id "$HM_SESSION_ID"' not in line
                and "$HM_SESSION_ID" in line
            ):
                offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, f"unquoted session id interpolation: {offenders}"


_STAGE_END = _TEMPLATES / "agents" / "_partials" / "stage_end_summary.md.j2"
_STEP_MANIFEST = _TEMPLATES / "agents" / "_partials" / "step_manifest.md.j2"


@pytest.mark.parametrize("subcommand", ["boundary", "gate-blocked"])
def test_every_autopilot_caps_call_passes_the_session_id(subcommand: str) -> None:
    """ADR-005 atomicity, enforced at CI.

    This partial renders into all seven stages, so one un-wired line here is fourteen
    un-wired call sites — and every one of them reads an id-bearing marker as foreign,
    which is `kill_switch`, which is autopilot off. The writer and the readers must land
    together; this is the check that says whether they did.
    """
    body = _read(_STAGE_END)
    lines = [ln for ln in body.splitlines() if f"autopilot_caps {subcommand}" in ln]
    assert lines, f"autopilot_caps {subcommand} invocation moved — re-point this guard"
    for line in lines:
        assert '--session-id "$HM_SESSION_ID"' in _unescaped(line), (
            f"un-wired `autopilot_caps {subcommand}`: {line.strip()}"
        )


@pytest.mark.parametrize("subcommand", ["autopilot status", "autopilot on"])
def test_the_picker_passes_the_session_id(subcommand: str) -> None:
    """The picker writes the marker. If it stamps an id the readers cannot match, it is
    the writer half of the same split — the one that turns autopilot off."""
    body = _read(_STEP_MANIFEST)
    lines = [ln for ln in body.splitlines() if f"hm {subcommand}" in ln]
    assert lines, f"`hm {subcommand}` invocation moved — re-point this guard"
    for line in lines:
        assert '--session-id "$HM_SESSION_ID"' in _unescaped(line), (
            f"un-wired picker: {line.strip()}"
        )


_PREFLIGHT = _TEMPLATES / "agents" / "_partials" / "worktree_preflight.md.j2"


def test_task_preflight_carries_the_span_session_id() -> None:
    """ADR-007's routing: the span id rides on `task-preflight`, never `worktree create`.

    `_cli_task_preflight` already parses `--claude-session-id` and threads it to
    `_emit_stage_span`; the template was the only missing link. `task-preflight` is the
    right carrier because the flag has NO loop meaning there — unlike on `create`, where
    its mere presence stamps the span `hm:loop`.
    """
    body = _read(_PREFLIGHT)
    lines = [ln for ln in body.splitlines() if "worktree task-preflight" in ln]
    assert lines, "task-preflight invocation moved — re-point this guard"
    for line in lines:
        assert '--claude-session-id "$HM_SESSION_ID"' in _unescaped(line), (
            f"span emitted without a session id: {line.strip()}"
        )


@pytest.mark.parametrize("template", ["stages/execute.md.j2"])
def test_worktree_create_never_gains_claude_session_id(template: str) -> None:
    """ADR-007, risk R9 — `--claude-session-id` is PRESENCE-overloaded.

    `worktree.py:2402` computes `is_loop_create = "--claude-session-id" in args` on the
    flag's presence, never its value, and `:2444` stamps the span `hm:loop` on that basis.
    Adding it to a `worktree create` call outside `loop.md.j2` would mislabel standalone
    spans AND write a session-bearing marker header, which makes the Stop-hook
    content-match and block a standalone `/hm:execute` from ever stopping.

    This asserts the obvious implementation of ADR-007 was NOT taken.
    """
    body = _read(_TEMPLATES / template)
    for line in body.splitlines():
        if "worktree create" in line:
            assert "--claude-session-id" not in line, (
                f"{template} must never pass --claude-session-id to `worktree create`; "
                "route the span id through task-preflight instead (ADR-007)"
            )
