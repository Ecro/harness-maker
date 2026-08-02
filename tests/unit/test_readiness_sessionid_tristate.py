"""Phase 1 of PLAN-sessionid-env-propagation — the session-id tri-state.

`HM_SESSION_ID` is written by the SessionStart hook as a SHELL variable and is never
exported, so `os.environ` reads it as absent in every subprocess. The fix routes the id
in as an explicit argument; these tests pin the three states that argument can carry and
the one invariant whose loss restores the original defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import Preset
from harness_maker.readiness import Signal, _dim_guardrails, compute_readiness

_LIVE = "sessionid_envfile_live"
_WIRED = "sessionid_envfile_probe_wired"


def _write_min_harness(project_dir: Path) -> None:
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        "preset: Production\ntargets:\n  - claude-code\n", encoding="utf-8"
    )


def _find(signals: list[Signal], sig_id: str) -> Signal | None:
    return next((s for s in signals if s.id == sig_id), None)


@pytest.fixture
def in_claude_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLAUDECODE set, HM_SESSION_ID absent — the real shape of a Claude Code subprocess."""
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("HM_SESSION_ID", raising=False)


# ── the tri-state ───────────────────────────────────────────────────────────


def test_argument_absent_emits_probe_wired_not_live(
    tmp_path: Path, in_claude_session: None
) -> None:
    """`session_id=None` means the caller never wired the probe — a stale render."""
    _write_min_harness(tmp_path)
    signals = _dim_guardrails(tmp_path).signals

    wired = _find(signals, _WIRED)
    assert wired is not None, "an unwired caller must self-accuse, never go silent"
    assert not wired.passed
    assert wired.weight == 0, "a <=45 weight moves this dimension by zero; declare the truth"
    assert not wired.hard_gate, "a stale render must not floor the dimension"
    assert _find(signals, _LIVE) is None, "live and probe_wired are mutually exclusive"


def test_argument_empty_is_genuine_degradation_and_hard_gates(
    tmp_path: Path, in_claude_session: None
) -> None:
    """`session_id=""` means the caller wired it and the value was really absent."""
    _write_min_harness(tmp_path)
    signals = _dim_guardrails(tmp_path, session_id="").signals

    live = _find(signals, _LIVE)
    assert live is not None
    assert not live.passed
    assert live.hard_gate, "genuine degradation self-stops /hm:loop after one iteration"
    assert _find(signals, _WIRED) is None


def test_argument_present_passes(tmp_path: Path, in_claude_session: None) -> None:
    _write_min_harness(tmp_path)
    signals = _dim_guardrails(tmp_path, session_id="abc123").signals

    live = _find(signals, _LIVE)
    assert live is not None
    assert live.passed
    assert _find(signals, _WIRED) is None


def test_none_and_empty_are_different_states(tmp_path: Path, in_claude_session: None) -> None:
    """THE invariant. Collapsing these two restores the bug this work removes."""
    _write_min_harness(tmp_path)
    absent = {s.id for s in _dim_guardrails(tmp_path).signals}
    empty = {s.id for s in _dim_guardrails(tmp_path, session_id="").signals}
    assert absent != empty
    assert _WIRED in absent
    assert _WIRED not in empty
    assert _LIVE in empty
    assert _LIVE not in absent


@pytest.mark.parametrize("session_id", [None, "", "abc123"])
def test_outside_a_claude_session_nothing_is_emitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, session_id: str | None
) -> None:
    """CLAUDECODE unset → true N-A for every argument state (CI, Cursor, Codex)."""
    monkeypatch.delenv("CLAUDECODE", raising=False)
    _write_min_harness(tmp_path)
    ids = {s.id for s in _dim_guardrails(tmp_path, session_id=session_id).signals}
    assert _LIVE not in ids
    assert _WIRED not in ids


def test_env_fallback_still_honoured_when_argument_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If some future Claude Code DOES export the var, the unwired path must see it.

    `session_id=None` is passed EXPLICITLY. Calling with no kwarg at all would exercise
    only the pre-existing env-read branch, which passes against the unimplemented tree —
    a false-RED that stays green after Phase C whether or not the preference order was
    written, so Phase D would get no signal from it either.
    """
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("HM_SESSION_ID", "from-env")
    _write_min_harness(tmp_path)
    signals = _dim_guardrails(tmp_path, session_id=None).signals

    live = _find(signals, _LIVE)
    assert live is not None
    assert live.passed
    assert _find(signals, _WIRED) is None


# ── the dimension score, which is the user-visible consequence ───────────────


def test_unwired_caller_does_not_floor_the_dimension(
    tmp_path: Path, in_claude_session: None
) -> None:
    """The regression this whole PLAN exists to remove: guardrails read 0 in every session."""
    _write_min_harness(tmp_path)
    assert _dim_guardrails(tmp_path).score > 0


def test_genuine_degradation_still_floors_the_dimension(
    tmp_path: Path, in_claude_session: None
) -> None:
    _write_min_harness(tmp_path)
    assert _dim_guardrails(tmp_path, session_id="").score == 0


# ── ADR-004's remediation channel is `action`-gated at improvement.py:102 ────


def test_probe_wired_carries_a_non_null_action(tmp_path: Path, in_claude_session: None) -> None:
    """`improvement.py:102` drops any signal with `action is None` before priority is
    ever computed, so a null action silently deletes the only remedy channel ADR-004 has."""
    _write_min_harness(tmp_path)
    wired = _find(_dim_guardrails(tmp_path).signals, _WIRED)
    assert wired is not None
    assert wired.action, "a null action removes this signal from /hm:ai-readiness entirely"
    assert "--update" in wired.action, "the remedy must name the re-render"


# ── the call chain: compute_readiness must actually accept and forward it ────


def test_compute_readiness_threads_the_argument(tmp_path: Path, in_claude_session: None) -> None:
    _write_min_harness(tmp_path)
    unwired = compute_readiness(tmp_path, Preset.PRODUCTION)
    wired = compute_readiness(tmp_path, Preset.PRODUCTION, session_id="abc123")

    unwired_ids = {s.id for s in unwired.dimensions["guardrails"].signals}
    wired_ids = {s.id for s in wired.dimensions["guardrails"].signals}
    assert _WIRED in unwired_ids
    assert _LIVE in wired_ids
    assert _WIRED not in wired_ids


def test_run_structural_threads_the_argument(tmp_path: Path, in_claude_session: None) -> None:
    """`cli.health_cmd` reaches readiness only through `ai_readiness.run_structural`.

    A kwarg added to `compute_readiness` alone transmits nothing — the intermediate hop
    is the whole reason the first draft of this PLAN could not have worked.
    """
    from harness_maker.ai_readiness import run_structural

    _write_min_harness(tmp_path)
    unwired = run_structural(tmp_path, preset=Preset.PRODUCTION)
    wired = run_structural(tmp_path, preset=Preset.PRODUCTION, session_id="abc123")

    assert any(s.endswith(f":{_WIRED}") for s in unwired["signals_failed"])
    assert not any(s.endswith(f":{_WIRED}") for s in wired["signals_failed"])
    assert not any(s.endswith(f":{_LIVE}") for s in wired["signals_failed"])


def test_probe_wired_reaches_ai_readiness_actions(tmp_path: Path, in_claude_session: None) -> None:
    """ADR-004's stated second channel, asserted end to end rather than assumed."""
    from harness_maker.ai_readiness import run_ai_readiness

    _write_min_harness(tmp_path)
    result = run_ai_readiness(tmp_path, preset=Preset.PRODUCTION, skip_llm=True)
    item = next((a for a in result.actions if a.source == f"layer1:{_WIRED}"), None)
    assert item is not None, "weight-0 must not mean absent from the action list"
    assert item.priority == "P2"
    assert "--update" in item.suggestion


def test_run_ai_readiness_threads_the_argument(tmp_path: Path, in_claude_session: None) -> None:
    """ADR-001 names THREE `compute_readiness` call sites in `ai_readiness.py`.

    `run_structural` (:128) is covered above; the siblings at :64 and :90 are separate
    entry points and threading one does not thread the others.
    """
    from harness_maker.ai_readiness import run_ai_readiness

    _write_min_harness(tmp_path)
    result = run_ai_readiness(
        tmp_path, preset=Preset.PRODUCTION, skip_llm=True, session_id="abc123"
    )
    assert not any(a.source == f"layer1:{_WIRED}" for a in result.actions)
    assert not any(a.source == f"layer1:{_LIVE}" for a in result.actions)


def test_run_ai_readiness_structural_threads_the_argument(
    tmp_path: Path, in_claude_session: None
) -> None:
    from harness_maker.ai_readiness import run_ai_readiness_structural

    _write_min_harness(tmp_path)
    payload = run_ai_readiness_structural(tmp_path, preset=Preset.PRODUCTION, session_id="abc123")
    guardrails = payload["readiness"]["dimensions"]["guardrails"]
    ids = {s["id"] for s in guardrails["signals"]}
    assert _LIVE in ids
    assert _WIRED not in ids


# ── a Cursor/Codex-only harness has no such variable to probe ────────────────


@pytest.mark.parametrize("session_id", [None, "", "abc123"])
def test_non_claude_target_emits_neither_signal(
    tmp_path: Path, in_claude_session: None, session_id: str | None
) -> None:
    """`targets` without `claude-code` → the variable is structurally absent, so the
    probe is N-A regardless of the argument. Emitting `probe_wired` here would tell a
    Cursor user to re-render for a hook their IDE never runs."""
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        "preset: Production\ntargets:\n  - cursor\n  - codex\n", encoding="utf-8"
    )
    ids = {s.id for s in _dim_guardrails(tmp_path, session_id=session_id).signals}
    assert _LIVE not in ids
    assert _WIRED not in ids
