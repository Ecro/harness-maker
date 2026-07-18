"""guard_when: pipeline_only — autopilot guard stays dormant in interactive sessions.

PLAN-autopilot-guard-interactive-scope. Under ``autonomy.guard_when: pipeline_only`` the
autopilot guard (PreToolUse never-auto block + Stop-hook backstop) must NOT fire while the
persistent marker is merely armed but no pipeline stage has started this session — the human
is present to approve. It re-arms the moment a stage stamps the ``.hm-pipeline-active`` crumb
for THIS session (or a loop marker appears). The crumb carries a PER-SESSION id (follow-up #1)
so a prior/parallel session's crumb reads as foreign → dormant, WITHOUT a clear-on-arm. The
default ``always`` (and an absent key) keep today's behavior: guard on whenever the marker is
active. Absent-case = feature-black-hole guard (never a silent guard-disable).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import autopilot
from harness_maker.hooks import autopilot_guard as guard
from harness_maker.models import AtomicStage

_PIPE = [AtomicStage.EXECUTE, AtomicStage.REVIEW]
_NEVER_AUTO = {"command": "rm -rf /etc"}
_SID_A = "session-alpha"
_SID_B = "session-beta"


@pytest.fixture(autouse=True)
def _no_ambient_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate from the test-runner's own HM_SESSION_ID (checklist #7): a bare
    ``mark_pipeline_active`` must stamp a deterministic EMPTY crumb, not the ambient id."""
    monkeypatch.delenv("HM_SESSION_ID", raising=False)


def _harness(root: Path, guard_when: str | None) -> None:
    """Write a minimal harness.yaml; guard_when=None omits the key (absent-case)."""
    (root / ".claude").mkdir(exist_ok=True)
    body = "autonomy:\n  level: auto_safe\n"
    if guard_when is not None:
        body += f"  guard_when: {guard_when}\n"
    (root / ".claude" / "harness.yaml").write_text(body, encoding="utf-8")


def _arm(root: Path) -> None:
    autopilot.write(root, level="auto_safe", pipeline=_PIPE)


# --- pipeline_only: dormant while interactive -------------------------------------


def test_pipeline_only_interactive_allows_never_auto(tmp_path: Path) -> None:
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    assert autopilot.active_marker(tmp_path) is not None
    assert autopilot.pipeline_active(tmp_path, session_id=_SID_A) is False
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id=_SID_A).allow is True


def test_pipeline_only_stophook_allows_stop_when_interactive(tmp_path: Path) -> None:
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    assert guard._stophook_reason({"cwd": str(tmp_path), "session_id": _SID_A}) is None


# --- pipeline_only: fires once a stage has started (same-session match) ------------


def test_pipeline_only_crumb_re_arms_guard(tmp_path: Path) -> None:
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.mark_pipeline_active(tmp_path, session_id=_SID_A)
    assert autopilot.pipeline_active(tmp_path, session_id=_SID_A) is True
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id=_SID_A).allow is False


def test_pipeline_only_stophook_blocks_when_pipeline_active(tmp_path: Path) -> None:
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.mark_pipeline_active(tmp_path, session_id=_SID_A)
    assert guard._stophook_reason({"cwd": str(tmp_path), "session_id": _SID_A}) is not None


def test_pipeline_only_loop_marker_re_arms_guard(tmp_path: Path) -> None:
    # A /hm:loop run touches a loop marker at loop START (before its first stage); the guard
    # must be active for the whole loop even without the autopilot crumb (existence, not id).
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    (tmp_path / ".claude" / ".hm-loop-somesession").write_text("x", encoding="utf-8")
    assert autopilot.pipeline_active(tmp_path, session_id=_SID_A) is True
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id=_SID_A).allow is False


# --- follow-up #1: per-session crumb identity (cross-session + parallel) -----------


def test_stale_crumb_from_prior_session_is_dormant(tmp_path: Path) -> None:
    # A crumb stamped by a PRIOR session bears that session's id; a NEW same-project session
    # (different id) reads it as foreign → dormant, with NO clear-on-arm needed. This is the
    # cross-session defeat the project-scoped uuid used to cause (REVIEW P1 / follow-up #1).
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.mark_pipeline_active(tmp_path, session_id="session-old")  # prior run
    assert autopilot.pipeline_active(tmp_path, session_id="session-new") is False
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id="session-new").allow is True
    # ...and the prior session itself would still be guarded (its own id still matches).
    assert autopilot.pipeline_active(tmp_path, session_id="session-old") is True


def test_parallel_arm_leaves_peer_crumb_intact(tmp_path: Path) -> None:
    # A peer session's SessionStart arm must NOT delete a live crumb (no clear-on-arm); the
    # peer's crumb stays and only its own session matches it (parallel non-interference).
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.mark_pipeline_active(tmp_path, session_id=_SID_A)
    _arm(tmp_path)  # a second session's autoarm re-arms via write()
    assert autopilot.pipeline_active_path(tmp_path).exists()
    assert autopilot.pipeline_active(tmp_path, session_id=_SID_A) is True


def test_cross_project_foreign_crumb_does_not_activate(tmp_path: Path) -> None:
    # A crumb bearing a different non-empty id (hand-edit / another repo's value) does not match
    # this caller's id → falls through to the (absent) loop check → dormant.
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.pipeline_active_path(tmp_path).write_text("ffffffffffff", encoding="utf-8")
    assert autopilot.pipeline_active(tmp_path, session_id=_SID_B) is False
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id=_SID_B).allow is True


def test_degraded_empty_crumb_honored(tmp_path: Path) -> None:
    # A degraded writer (no HM_SESSION_ID — Cursor/Codex/WSL2 env miss) stamps an EMPTY crumb;
    # it must block-bias to guarded (never a silent disarm), regardless of the reader's id.
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.mark_pipeline_active(tmp_path, session_id="")  # degraded → empty crumb
    assert autopilot.pipeline_active(tmp_path, session_id=_SID_B) is True
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id=_SID_B).allow is False


def test_degraded_reader_honors_crumb(tmp_path: Path) -> None:
    # A reader with no session_id (rare — payload lacked it) cannot verify the crumb's session,
    # so it block-biases to guarded rather than standing the guard down.
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.mark_pipeline_active(tmp_path, session_id=_SID_A)
    assert autopilot.pipeline_active(tmp_path, session_id=None) is True


# --- default / absent: unchanged (guard on) --------------------------------------


def test_always_mode_fires_even_interactive(tmp_path: Path) -> None:
    _harness(tmp_path, "always")
    _arm(tmp_path)
    assert autopilot.pipeline_active(tmp_path, session_id=_SID_A) is False
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id=_SID_A).allow is False


def test_absent_guard_when_defaults_to_always(tmp_path: Path) -> None:
    # absent-case = feature-black-hole guard: no key → guard stays ON (safe).
    _harness(tmp_path, None)
    _arm(tmp_path)
    assert guard._guard_when(tmp_path) == "always"
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id=_SID_A).allow is False


def test_no_harness_yaml_defaults_to_always(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    _arm(tmp_path)
    assert guard._guard_when(tmp_path) == "always"
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path).allow is False


# --- marker OFF: guard_when irrelevant (still a no-op) ----------------------------


def test_marker_off_allows_regardless_of_guard_when(tmp_path: Path) -> None:
    _harness(tmp_path, "pipeline_only")  # marker never armed
    assert guard.evaluate("Bash", _NEVER_AUTO, tmp_path, session_id=_SID_A).allow is True


# --- crumb lifecycle --------------------------------------------------------------


def test_clear_reaps_crumb(tmp_path: Path) -> None:
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.mark_pipeline_active(tmp_path, session_id=_SID_A)
    crumb = autopilot.pipeline_active_path(tmp_path)
    assert crumb.exists()
    autopilot.clear(tmp_path)
    assert not crumb.exists()


def test_unreadable_crumb_biases_guarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # REVIEW P2: a crumb that EXISTS but is unreadable must block-bias to guarded (True), not
    # fall through to dormant — True is the safe direction for this guard-arming predicate.
    _harness(tmp_path, "pipeline_only")
    _arm(tmp_path)
    autopilot.mark_pipeline_active(tmp_path, session_id=_SID_A)
    orig = Path.read_text

    def _boom(self: Path, *a: object, **k: object) -> str:
        if self.name == ".hm-pipeline-active":
            raise OSError("simulated read failure")
        return orig(self, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", _boom)
    assert autopilot.pipeline_active(tmp_path, session_id=_SID_A) is True
