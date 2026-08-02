"""`hm cli health --session-id` — the CLI boundary of PLAN-sessionid-env-propagation.

`health_cmd` is the only rendered consumer of the readiness tri-state, and it has two
independent exits: the `--json-output` early return and the dashboard branch. Threading
the argument through one and not the other is a live failure mode, so both are asserted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness_maker.cli import app

_LIVE = "guardrails:sessionid_envfile_live"
_WIRED = "guardrails:sessionid_envfile_probe_wired"

_runner = CliRunner()


@pytest.fixture
def in_claude_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("HM_SESSION_ID", raising=False)


def _project(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        "preset: Production\ntargets:\n  - claude-code\n", encoding="utf-8"
    )
    return tmp_path


def _signals_failed(json_path: Path) -> list[str]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    failed: list[str] = payload["structural"]["signals_failed"]
    return failed


def test_json_output_branch_with_session_id(tmp_path: Path, in_claude_session: None) -> None:
    """The PLAN's Phase 1 exit criterion, run as the operator would run it."""
    project = _project(tmp_path)
    out = tmp_path / "health.json"
    result = _runner.invoke(
        app,
        [
            "health",
            str(project),
            "--session-id",
            "abc123",
            "--json-output",
            str(out),
            "--no-update-dashboard",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    failed = _signals_failed(out)
    # Name the two signals exactly. A `sessionid_envfile_` PREFIX also matches
    # `sessionid_envfile_registered` — the unrelated static hooks.json check, which
    # legitimately fails on a minimal fixture and has nothing to do with this contract.
    assert _LIVE not in failed, f"live must not fail for a healthy id; got {failed}"
    assert _WIRED not in failed, f"probe_wired must not fire when wired; got {failed}"


def test_json_output_branch_without_the_flag_self_accuses(
    tmp_path: Path, in_claude_session: None
) -> None:
    """A stale render omits the flag; the harness must say so rather than go quiet."""
    project = _project(tmp_path)
    out = tmp_path / "health.json"
    result = _runner.invoke(
        app,
        ["health", str(project), "--json-output", str(out), "--no-update-dashboard"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    failed = _signals_failed(out)
    assert _WIRED in failed, "an unwired probe must appear in signals_failed"
    assert _LIVE not in failed, "the hard-gating signal must not fire on a stale render"


def test_empty_session_id_reaches_the_hard_gate(tmp_path: Path, in_claude_session: None) -> None:
    """`--session-id "$HM_SESSION_ID"` with the shell var unset delivers `""`."""
    project = _project(tmp_path)
    out = tmp_path / "health.json"
    result = _runner.invoke(
        app,
        [
            "health",
            str(project),
            "--session-id",
            "",
            "--json-output",
            str(out),
            "--no-update-dashboard",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    failed = _signals_failed(out)
    assert _LIVE in failed
    assert _WIRED not in failed


def test_dashboard_branch_also_threads_the_argument(
    tmp_path: Path, in_claude_session: None
) -> None:
    """The second exit. `--json-output` returns early, so covering it proves nothing
    about the path a plain `/hm:health` takes."""
    project = _project(tmp_path)
    wired = _runner.invoke(
        app, ["health", str(project), "--session-id", "abc123"], catch_exceptions=False
    )
    assert wired.exit_code == 0, wired.output

    dashboard = project / ".claude" / "observability" / "dashboard.md"
    assert dashboard.is_file(), "the dashboard branch must have run"
    body = dashboard.read_text(encoding="utf-8")
    assert "sessionid_envfile_probe_wired" not in body
    assert "sessionid_envfile_live" not in body
