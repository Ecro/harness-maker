"""/hm:health loud smoke for the loop-marker SessionStart hook (P5).

A rendered harness whose hooks.json registers SessionStart but OMITS
`sessionid_envfile` silently degrades /hm:loop session-scoping (HM_SESSION_ID
never set). The smoke makes that loud rather than silent.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.readiness import _dim_guardrails

_SIG = "sessionid_envfile_registered"


def _write_hooks(project_dir: Path, sessionstart_cmds: list[str]) -> None:
    """Write the hooks where Claude Code actually reads them: settings.json.

    Phase 4 of PLAN-permission-deny-and-hooks-wiring retargeted these signals off
    `.claude/hooks/hooks.json`, which Claude Code never loads.
    """
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    data = {
        "permissions": {"allow": [], "deny": []},
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": c} for c in sessionstart_cmds]}
            ]
        },
        "preset": "Production",
    }
    (claude / "settings.json").write_text(json.dumps(data), encoding="utf-8")


def _find(signals: list, sig_id: str):  # type: ignore[no-untyped-def]
    return next((s for s in signals if s.id == sig_id), None)


def test_signal_passes_when_sessionid_envfile_registered(tmp_path: Path) -> None:
    _write_hooks(
        tmp_path,
        [
            "uv run python -m harness_maker.hooks.sessionstart_drift",
            "uv run python -m harness_maker.hooks.sessionid_envfile",
        ],
    )
    sig = _find(_dim_guardrails(tmp_path).signals, _SIG)
    assert sig is not None
    assert sig.passed is True


def test_signal_fails_loudly_when_missing(tmp_path: Path) -> None:
    # SessionStart present but sessionid_envfile absent → silent degradation.
    _write_hooks(tmp_path, ["uv run python -m harness_maker.hooks.sessionstart_drift"])
    sig = _find(_dim_guardrails(tmp_path).signals, _SIG)
    assert sig is not None
    assert sig.passed is False
    assert sig.action  # actionable remediation present


def test_signal_fails_when_settings_has_no_hooks_at_all(tmp_path: Path) -> None:
    """INVERTED at Phase 4 — this used to assert `passed is True`.

    The old contract was "no hooks.json → `hooks_json_present` owns that case; this one
    must not double-penalize." That reasoning made the signal fail OPEN, and Phase 4
    (which retires hooks.json) would have turned it into "passes forever, for every
    project" — the smoke alarm CLAUDE.md relies on, wired to always-quiet.

    Post-Phase-4 the absent case does not mean "nothing to judge yet"; it means the
    harness has NO live hooks, which is precisely the degradation this signal detects.
    Two signals firing on one root cause is the correct redundancy here, not
    double-penalization.
    """
    (tmp_path / ".claude").mkdir(parents=True)
    sig = _find(_dim_guardrails(tmp_path).signals, _SIG)
    assert sig is not None
    assert sig.passed is False
