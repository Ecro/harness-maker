"""Fix 4 (PLAN-multisession-10-fleet-hardening ADR-004) — live HM_SESSION_ID probe.

The static `sessionid_envfile_registered` signal proves the hook is in hooks.json
but not that HM_SESSION_ID actually reaches the environment at runtime. The new
`sessionid_envfile_live` signal probes the health command's own env and HARD-GATES
the guardrails dimension to 0 on Claude Code when it is unset — closing the
green-while-runtime-degraded blind spot — while staying N-A for Cursor/Codex-only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.readiness import Signal, _dim_guardrails, _score_signals

_SIG = "sessionid_envfile_live"


def _write_hooks(project_dir: Path) -> None:
    hooks_dir = project_dir / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "uv run python -m harness_maker.hooks.sessionid_envfile",
                        }
                    ]
                }
            ]
        },
        "preset": "Production",
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(data), encoding="utf-8")


def _write_targets(project_dir: Path, targets: list[str]) -> None:
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"  - {t}" for t in targets)
    (claude / "harness.yaml").write_text(f"targets:\n{lines}\n", encoding="utf-8")


def _find(signals: list[Signal], sig_id: str) -> Signal | None:
    return next((s for s in signals if s.id == sig_id), None)


# ── _score_signals hard-gate flooring (unit) ─────────────────────────────────


def test_failed_hard_gate_floors_score_to_zero() -> None:
    signals = [
        Signal(id="a", passed=True, weight=80, evidence="", action=None),
        Signal(id="hg", passed=False, weight=0, evidence="", action="fix", hard_gate=True),
    ]
    assert _score_signals(signals) == 0


def test_passed_hard_gate_does_not_floor() -> None:
    signals = [
        Signal(id="a", passed=True, weight=80, evidence="", action=None),
        Signal(id="hg", passed=True, weight=0, evidence="", action=None, hard_gate=True),
    ]
    assert _score_signals(signals) == 80


def test_failed_non_hard_gate_only_subtracts_weight() -> None:
    signals = [
        Signal(id="a", passed=True, weight=80, evidence="", action=None),
        Signal(id="b", passed=False, weight=20, evidence="", action="x"),
    ]
    assert _score_signals(signals) == 80  # not floored


# ── live signal in _dim_guardrails ───────────────────────────────────────────


def test_live_signal_fails_and_floors_on_claude_code_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")  # in a CC session
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _write_hooks(tmp_path)
    _write_targets(tmp_path, ["claude-code"])
    # `session_id=""` is the state this signal occupies since
    # PLAN-sessionid-env-propagation ADR-001: the caller WIRED the probe and the value
    # was genuinely absent. Omitting the argument now means "probe never wired" — a
    # stale render, which is `sessionid_envfile_probe_wired` and deliberately not gated.
    dim = _dim_guardrails(tmp_path, session_id="")
    sig = _find(dim.signals, _SIG)
    assert sig is not None
    assert sig.passed is False
    assert sig.hard_gate is True
    assert sig.action  # actionable remediation
    assert dim.score == 0  # hard-gate floored the dimension below green


def test_live_signal_passes_when_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("HM_SESSION_ID", "abc123def456")
    _write_hooks(tmp_path)
    _write_targets(tmp_path, ["claude-code"])
    dim = _dim_guardrails(tmp_path)
    sig = _find(dim.signals, _SIG)
    assert sig is not None
    assert sig.passed is True
    assert dim.score > 0  # not floored


def test_live_signal_na_for_cursor_codex_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")  # in session, but...
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _write_hooks(tmp_path)
    _write_targets(tmp_path, ["cursor", "codex"])  # ...not a claude-code target
    dim = _dim_guardrails(tmp_path)
    # Signal omitted entirely (N-A) — no penalty despite the var being unset.
    assert _find(dim.signals, _SIG) is None
    assert dim.score > 0


def test_live_signal_na_outside_claude_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No CLAUDECODE (unit test / CI / make audit / other tool) → N-A even on a
    claude-code harness, so the hard-gate never floors a static disk-scan."""
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _write_hooks(tmp_path)
    _write_targets(tmp_path, ["claude-code"])
    dim = _dim_guardrails(tmp_path)
    assert _find(dim.signals, _SIG) is None
    assert dim.score > 0


def test_live_signal_defaults_to_claude_code_when_no_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An old harness with no `targets` key defaults to claude-code → hard-gated."""
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _write_hooks(tmp_path)
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)  # no harness.yaml
    dim = _dim_guardrails(tmp_path, session_id="")  # wired + genuinely absent (ADR-001)
    sig = _find(dim.signals, _SIG)
    assert sig is not None
    assert sig.passed is False
    assert dim.score == 0
