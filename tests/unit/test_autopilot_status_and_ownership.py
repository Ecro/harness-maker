"""PLAN-autopilot-advance-noop Phase 1 — status / GC / session-scoping / arm ownership.

The four defects under repair (see RESEARCH-autopilot-advance-noop):
  ADR-002  `hm autopilot status` is the sole arbiter of "is autopilot active?"
  ADR-007  the marker is keyed on HM_SESSION_ID, one-directional (loop_marker rule)
  ADR-008  GC deletes on TTL staleness ONLY — never on foreignness, never on age<0
  ADR-010  arming refuses to overwrite a live foreign marker

The single most load-bearing assertion in this file is
`test_gc_preserves_foreign_but_fresh`: after ADR-007, "foreign" means "another LIVE
session", so a GC that deleted whatever `active_marker` rejects would silently disarm a
peer.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from harness_maker import autopilot
from harness_maker.models import AtomicStage

DEFAULT_PIPELINE = [AtomicStage.RESEARCH, AtomicStage.SPEC, AtomicStage.PLAN]


def _iso(delta_hours: float = 0.0) -> str:
    return (datetime.now(UTC) + timedelta(hours=delta_hours)).isoformat()


def _read_raw(root: Path, session_id: str | None = None) -> dict[str, object]:
    raw: dict[str, object] = json.loads(
        autopilot.marker_path(root, session_id=session_id).read_text(encoding="utf-8")
    )
    return raw


def _write_raw(root: Path, payload: dict[str, object], session_id: str | None = None) -> None:
    # PLAN-multisession-marker-scoping ADR-001: the marker file is keyed by session. A
    # fixture that plants a PEER-owned marker must plant it at the path the caller under
    # test will actually read — post-ADR-001 two live sessions never meet on one file, so
    # the ownership guards are only reachable via a marker whose header disagrees with its
    # own filename (a hand-edit, or a half-finished format migration). Those must fail SAFE.
    p = autopilot.marker_path(root, session_id=session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")


def _marker_payload(root: Path, **over: object) -> dict[str, object]:
    from harness_maker.worktree import _current_session_uuid

    base: dict[str, object] = {
        "session_uuid": _current_session_uuid(root),
        "level": "auto_safe",
        "pipeline": [s.value for s in DEFAULT_PIPELINE],
        "created_at": _iso(),
    }
    base.update(over)
    return base


# --- ADR-007: one-directional session scoping ----------------------------------


def test_write_stamps_claude_session_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    assert _read_raw(tmp_path)["claude_session_id"] == "sess-A"


def test_write_omits_session_id_when_env_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    assert _read_raw(tmp_path)["claude_session_id"] is None


def test_matching_session_id_is_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    assert autopilot.active_marker(tmp_path) is not None


def test_mismatched_session_id_is_foreign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    monkeypatch.setenv("HM_SESSION_ID", "sess-B")
    assert autopilot.active_marker(tmp_path) is None


def test_env_id_does_not_inherit_fieldless_legacy_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-007 one-directional rule — the half the symmetric draft got wrong.

    A legacy (pre-upgrade) marker carries no `claude_session_id`. An id-BEARING session
    must NOT inherit it; `loop_marker`'s documented precedent honors the session-blind
    state "only when the caller has no id of its own".
    """
    _write_raw(tmp_path, _marker_payload(tmp_path))  # no claude_session_id key
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    assert autopilot.active_marker(tmp_path) is None


def test_idless_session_does_not_inherit_id_bearing_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mirror direction: marker has an id, environment does not → foreign.

    The positive control is load-bearing: today `extra="forbid"` rejects the unknown
    `claude_session_id` key outright, so the negative half alone would pass without the
    one-directional rule ever existing (A.5 false-RED finding). Asserting that the SAME
    marker IS accepted by its owner forces the field to be declared first.
    """
    # ADR-001: the negative half reads the degraded file, the positive control reads
    # sess-A's own file — two paths now, so the same payload is planted at both.
    payload = _marker_payload(tmp_path, claude_session_id="sess-A")
    _write_raw(tmp_path, payload, None)
    _write_raw(tmp_path, payload, "sess-A")

    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    assert autopilot.active_marker(tmp_path) is None

    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    assert autopilot.active_marker(tmp_path) is not None, "positive control: owner accepts"


def test_degraded_both_idless_falls_back_to_project_uuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cursor / Codex / SessionStart-hook failure: neither side has an id → today's rule."""
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    assert autopilot.active_marker(tmp_path) is not None


def test_ttl_still_applies_to_a_matching_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-007: 'the TTL check always applies' — even to a matching session id.

    Paired with a fresh positive control so the test cannot be satisfied by schema
    rejection (today's accidental pass) nor by an id-compare that short-circuits ahead
    of the freshness window (the regression ADR-007 warns against).
    """
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")

    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-A", created_at=_iso(-1)))
    assert autopilot.active_marker(tmp_path) is not None, "positive control: fresh + own id"

    _write_raw(
        tmp_path, _marker_payload(tmp_path, claude_session_id="sess-A", created_at=_iso(-19))
    )
    assert autopilot.active_marker(tmp_path) is None


# --- ADR-008: GC deletes on TTL staleness ONLY ---------------------------------


def test_gc_deletes_ttl_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    _write_raw(
        tmp_path, _marker_payload(tmp_path, claude_session_id="sess-A", created_at=_iso(-19))
    )
    assert autopilot.gc_stale_marker(tmp_path, session_id=None) is True
    assert not autopilot.marker_path(tmp_path, session_id=None).exists()


def test_gc_preserves_foreign_but_fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE load-bearing assertion (ADR-008): foreign == another LIVE session."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-PEER"), "sess-MINE")
    assert autopilot.active_marker(tmp_path) is None  # rejected...
    assert autopilot.gc_stale_marker(tmp_path, session_id=None) is False  # ...but NOT deleted
    assert autopilot.marker_path(tmp_path, session_id=None).exists()


def test_gc_preserves_future_dated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-008: age<0 is reject-but-preserve — clock skew must not disarm a peer."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-A", created_at=_iso(+5)))
    assert autopilot.active_marker(tmp_path) is None
    assert autopilot.gc_stale_marker(tmp_path, session_id=None) is False
    assert autopilot.marker_path(tmp_path, session_id=None).exists()


def test_gc_deletes_unparseable(tmp_path: Path) -> None:
    p = autopilot.marker_path(tmp_path, session_id=None)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    assert autopilot.gc_stale_marker(tmp_path, session_id=None) is True
    assert not p.exists()


def test_gc_absent_is_noop(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    assert autopilot.gc_stale_marker(tmp_path, session_id=None) is False


def test_gc_deletes_foreign_and_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-008 deletes on `age > TTL` — foreignness is not a criterion in EITHER direction.

    The over-correction is the real hazard: an implementation reading the ADR's headline
    as "never delete a foreign marker" passes every other GC test here, and a crashed
    peer's marker then becomes uncollectable forever — reinstating the very
    stale-file-suppresses-arming defect ADR-002 exists to remove.
    """
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    _write_raw(
        tmp_path,
        _marker_payload(tmp_path, claude_session_id="sess-PEER", created_at=_iso(-19)),
        "sess-MINE",
    )
    assert autopilot.gc_stale_marker(tmp_path, session_id=None) is True
    assert not autopilot.marker_path(tmp_path, session_id=None).exists()


def test_gc_preserves_a_replacement_written_after_the_judgement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-008 re-read-before-unlink: content changing mid-operation must abort the unlink.

    The replacement is itself STALE (a different peer's expired marker), which is what
    makes this a real discriminator rather than a read-ordinal accident:

      * a byte-comparison guard  → bytes differ → preserve  ✅
      * no guard at all          → unlinks whatever is there → file gone  ❌ caught
      * an accidental double-read (`active_marker()` then `load()` again, no byte
        compare) → the second read is ALSO stale → still unlinks → file gone  ❌ caught

    Keying the swap on staleness instead of on freshness is the whole point: a fresh
    replacement would let the double-read shape pass by luck.
    """
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    stale_own = _marker_payload(tmp_path, claude_session_id="sess-A", created_at=_iso(-19))
    stale_peer = _marker_payload(tmp_path, claude_session_id="sess-PEER", created_at=_iso(-20))
    _write_raw(tmp_path, stale_own)

    marker = autopilot.marker_path(tmp_path, session_id=None)
    original = {"read_text": Path.read_text, "read_bytes": Path.read_bytes}
    state = {"swapped": False, "reads": 0}

    def _make(name: str) -> Callable[..., Any]:  # local factory
        real = original[name]

        def _hooked(self: Path, *a: object, **kw: object) -> Any:
            out = real(self, *a, **kw)  # type: ignore[operator]
            if self == marker:
                state["reads"] += 1
                if not state["swapped"]:
                    state["swapped"] = True
                    _write_raw(tmp_path, stale_peer)  # writer replaces it mid-operation
            return out

        return _hooked

    # Patch BOTH primitives so the test is neutral to whichever the byte compare uses.
    with monkeypatch.context() as mp:
        mp.setattr(Path, "read_text", _make("read_text"))
        mp.setattr(Path, "read_bytes", _make("read_bytes"))
        result = autopilot.gc_stale_marker(tmp_path, session_id=None)

    assert result is False, "a marker whose bytes changed mid-operation must not be deleted"
    assert marker.exists()
    assert _read_raw(tmp_path)["claude_session_id"] == "sess-PEER"
    assert state["reads"] >= 2, "the guard must inspect the marker again before unlinking"


# --- ADR-010: arm ownership guard ----------------------------------------------


def test_write_refuses_to_overwrite_live_foreign_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-PEER"), "sess-MINE")
    before = autopilot.marker_path(tmp_path, session_id=None).read_bytes()
    with pytest.raises(autopilot.MarkerOwnedByAnotherSessionError):
        autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    assert autopilot.marker_path(tmp_path, session_id=None).read_bytes() == before


def test_write_force_overwrites_live_foreign_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-PEER"))
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE, force=True)
    assert _read_raw(tmp_path)["claude_session_id"] == "sess-MINE"


def test_write_overwrites_own_and_stale_markers_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    # Legacy level, normalized on write — see test_autonomy_level_matrix.
    autopilot.write(tmp_path, level="full", pipeline=DEFAULT_PIPELINE)  # type: ignore[arg-type]
    # The marker records the NORMALIZED level, so an older writer's `full` and a current
    # `auto_safe` are the same on disk — which is what makes the legacy marker loadable.
    assert _read_raw(tmp_path)["level"] == "auto_safe"

    _write_raw(
        tmp_path, _marker_payload(tmp_path, claude_session_id="sess-PEER", created_at=_iso(-19))
    )
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)  # stale → allowed
    assert _read_raw(tmp_path)["claude_session_id"] == "sess-A"


# --- ADR-003: task_slug persistence --------------------------------------------


def test_set_task_slug_persists_slug_and_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    assert autopilot.set_task_slug(tmp_path, slug="my-task", stage="research") is True
    raw = _read_raw(tmp_path)
    assert raw["task_slug"] == "my-task"
    assert raw["task_slug_stage"] == "research"
    assert autopilot.active_marker(tmp_path).task_slug == "my-task"  # type: ignore[union-attr]


def test_set_task_slug_refuses_when_marker_not_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R9 mitigation: never slug-write a marker this session does not own."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-PEER"), "sess-MINE")
    before = autopilot.marker_path(tmp_path, session_id=None).read_bytes()
    assert autopilot.set_task_slug(tmp_path, slug="my-task", stage="research") is False
    assert autopilot.marker_path(tmp_path, session_id=None).read_bytes() == before


def test_legacy_marker_without_new_keys_still_loads(tmp_path: Path) -> None:
    """Absent-case guard (CLAUDE.md): the three new fields are optional."""
    _write_raw(tmp_path, _marker_payload(tmp_path))
    m = autopilot.load(tmp_path, session_id=None)
    assert m is not None
    assert m.task_slug is None
    assert m.task_slug_stage is None
    assert m.claude_session_id is None


# --- ADR-002: `status` ----------------------------------------------------------


def _status(root: Path) -> dict[str, object]:
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = autopilot.main(["status", "--root", str(root)])
    assert rc == 0, "status must always exit 0"
    parsed: dict[str, object] = json.loads(buf.getvalue().strip())
    return parsed


def test_status_absent(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    out = _status(tmp_path)
    assert out["active"] is False
    assert out["reason"] == "absent"
    assert out["level"] is None
    assert out["pipeline"] is None
    assert out["task_slug"] is None


def test_status_armed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    out = _status(tmp_path)
    assert out["active"] is True
    assert out["reason"] == "armed"
    assert out["level"] == "auto_safe"
    assert out["session_scoped"] is True


def test_status_stale_reports_gc_and_deletes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    _write_raw(
        tmp_path, _marker_payload(tmp_path, claude_session_id="sess-A", created_at=_iso(-19))
    )
    out = _status(tmp_path)
    assert out["active"] is False
    assert out["reason"] == "stale (gc'd)"
    assert not autopilot.marker_path(tmp_path, session_id=None).exists()


def test_status_foreign_preserves_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The picker branches on this `reason` — ADR-010. `active:false` alone would arm."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-PEER"), "sess-MINE")
    out = _status(tmp_path)
    assert out["active"] is False
    assert out["reason"] == "foreign"
    assert autopilot.marker_path(tmp_path, session_id=None).exists()


def test_status_future_dated_preserves_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-A", created_at=_iso(+5)))
    out = _status(tmp_path)
    # `active` is half the exit criterion for case (d) — a marker reported as
    # future-dated but still armed would send the picker down the wrong branch.
    assert out["active"] is False
    assert out["reason"] == "future-dated"
    assert autopilot.marker_path(tmp_path, session_id=None).exists()


def test_status_survives_gc_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-002: an uncaught OSError would starve the picker of JSON — the exact
    failure mode this whole PLAN removes, re-entered through its own fix."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    _write_raw(
        tmp_path, _marker_payload(tmp_path, claude_session_id="sess-A", created_at=_iso(-19))
    )

    def _boom(self: Path, **kw: object) -> None:
        raise PermissionError(13, "read-only file system")

    monkeypatch.setattr(Path, "unlink", _boom)
    out = _status(tmp_path)
    assert out["active"] is False
    assert str(out["reason"]).startswith("gc-failed:")


def test_status_reports_degraded_session_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    out = _status(tmp_path)
    assert out["active"] is True
    assert out["session_scoped"] is False


def test_status_echoes_persisted_task_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    autopilot.set_task_slug(tmp_path, slug="my-task", stage="plan")
    assert _status(tmp_path)["task_slug"] == "my-task"


def test_on_against_live_foreign_marker_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-PEER"), "sess-MINE")
    before = autopilot.marker_path(tmp_path, session_id=None).read_bytes()
    rc = autopilot.main(["on", "--root", str(tmp_path)])
    assert rc != 0
    # The contract is "prints a diagnostic", not any particular wording — pinning an
    # invented string would break a green suite on a harmless reword.
    assert capsys.readouterr().err.strip() != ""
    assert autopilot.marker_path(tmp_path, session_id=None).read_bytes() == before


def test_on_force_flag_takes_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_raw(tmp_path, _marker_payload(tmp_path, claude_session_id="sess-PEER"))
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    assert autopilot.main(["on", "--root", str(tmp_path), "--force"]) == 0
    assert _read_raw(tmp_path)["claude_session_id"] == "sess-MINE"
