"""Regression gates for the round-1/round-2 review fixes (PLAN-autopilot-advance-noop).

Each test here corresponds to a defect that shipped GREEN — the suite could not see it.
Deleting the behaviour under test must turn one of these red:

  * autoarm stamping the id it receives on stdin (round-1 P0: the marker was stamped
    id-less, so the arming session itself read it as foreign and autopilot was wedged for
    the full TTL with no in-band recovery);
  * autoarm NOT stealing a live peer's marker (round-2 P0: the first fix used `force=True`,
    which disabled the ownership guard for genuinely foreign markers too);
  * the `task_slug` allowlist holding on BOTH sinks — the marker and the boundary JSON the
    prompt turns into a `Skill(...)` argument;
  * `gc_stale_marker` collecting a schema-valid marker with a garbage `created_at`.
"""

from __future__ import annotations

import contextlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker import autopilot, autopilot_caps
from harness_maker.hooks import autopilot_autoarm
from harness_maker.models import AtomicStage

PIPELINE = [AtomicStage.RESEARCH, AtomicStage.SPEC, AtomicStage.PLAN]


def _harness(root: Path, *, persistent: bool = True, level: str = "auto_safe") -> None:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "harness.yaml").write_text(
        "autonomy:\n"
        f"  level: {level}\n"
        f"  autopilot_persistent: {'true' if persistent else 'false'}\n"
        "  pipeline: [research, spec, plan]\n",
        encoding="utf-8",
    )


def _raw(root: Path) -> dict[str, object]:
    return json.loads(autopilot.marker_path(root).read_text(encoding="utf-8"))


# --- round-1 P0: the hook must stamp the id it was handed -----------------------


def test_autoarm_stamps_the_supplied_session_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`HM_SESSION_ID` is deliberately ABSENT from the hook's own environment — its sibling
    `sessionid_envfile` publishes it to `$CLAUDE_ENV_FILE`, which reaches later Bash only."""
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _harness(tmp_path)
    assert autopilot_autoarm.arm_if_persistent(tmp_path, claude_session_id="sess-A") is True
    assert _raw(tmp_path)["claude_session_id"] == "sess-A"


def test_the_arming_session_owns_what_autoarm_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: the session whose id the hook stamped must then see it as ACTIVE.

    Before the fix this returned None — the marker was id-less, the session's Bash had an
    id, and the one-directional rule made them foreign to each other permanently.
    """
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _harness(tmp_path)
    autopilot_autoarm.arm_if_persistent(tmp_path, claude_session_id="sess-A")

    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    assert autopilot.active_marker(tmp_path) is not None


# --- round-2 P0: autoarm must not steal a live peer's marker --------------------


def test_autoarm_does_not_overwrite_a_live_peer_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two sessions opening in one project seconds apart is the documented normal mode.

    The first fix passed `force=True`, which skipped the ADR-010 guard entirely — so
    session B's SessionStart replaced session A's live marker and A's next boundary died
    at `kill_switch`.
    """
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _harness(tmp_path)
    autopilot_autoarm.arm_if_persistent(tmp_path, claude_session_id="sess-A")
    before = autopilot.marker_path(tmp_path).read_bytes()

    assert autopilot_autoarm.arm_if_persistent(tmp_path, claude_session_id="sess-B") is False
    assert autopilot.marker_path(tmp_path).read_bytes() == before

    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    assert autopilot.active_marker(tmp_path) is not None, "peer A must still be armed"


def test_autoarm_re_arms_its_own_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard must not block the SAME session re-arming — that is the feature."""
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _harness(tmp_path)
    autopilot_autoarm.arm_if_persistent(tmp_path, claude_session_id="sess-A")
    old = _raw(tmp_path)["created_at"]
    later = (datetime.now(UTC) + timedelta(seconds=5)).isoformat()
    assert (
        autopilot_autoarm.arm_if_persistent(tmp_path, claude_session_id="sess-A", now=later) is True
    )
    assert _raw(tmp_path)["created_at"] != old


def test_autoarm_replaces_a_stale_peer_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crashed peer's EXPIRED marker must not wedge a new session out."""
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _harness(tmp_path)
    autopilot_autoarm.arm_if_persistent(
        tmp_path,
        claude_session_id="sess-DEAD",
        now=(datetime.now(UTC) - timedelta(hours=19)).isoformat(),
    )
    assert autopilot_autoarm.arm_if_persistent(tmp_path, claude_session_id="sess-B") is True
    assert _raw(tmp_path)["claude_session_id"] == "sess-B"


def test_session_id_from_stdin_rejects_a_non_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": 17})))
    assert autopilot_autoarm._session_id_from_stdin() is None


def test_session_id_from_stdin_survives_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
    assert autopilot_autoarm._session_id_from_stdin() is None


# --- round-1 P1: the task_slug allowlist, on BOTH sinks -------------------------


@pytest.mark.parametrize(
    "bad",
    ["a b", "a;rm -rf /", "$(whoami)", "../escape", "-leading-dash", "", "x" * 129],
)
def test_set_task_slug_rejects_a_bad_slug_and_leaves_the_marker_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    """`model_copy(update=...)` does NOT run validators, so the persistence path needed an
    explicit re-validate — this pins it."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)
    before = autopilot.marker_path(tmp_path).read_bytes()
    assert autopilot.set_task_slug(tmp_path, slug=bad, stage="research") is False
    assert autopilot.marker_path(tmp_path).read_bytes() == before


def test_boundary_never_echoes_a_rejected_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second sink. The JSON's `task_slug` becomes the `Skill(hm:<next> <slug>)`
    argument, so echoing a value the marker refused hands it straight to the prompt."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = autopilot_caps.main(
            ["boundary", "--root", str(tmp_path), "--current", "research", "--slug", "a;evil"]
        )
    assert rc == 0
    out = json.loads(buf.getvalue().strip())
    # The security property: the rejected VALUE never reaches the JSON. (Its label is
    # `rejected`; `test_rejected_slug_with_no_persisted_fallback_reports_rejected` pins that.)
    assert out["task_slug"] != "a;evil"
    assert out["task_slug"] is None


def test_boundary_falls_back_to_the_validated_persisted_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)
    autopilot.set_task_slug(tmp_path, slug="good-slug", stage="research")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot_caps.main(
            ["boundary", "--root", str(tmp_path), "--current", "research", "--slug", "a b"]
        )
    out = json.loads(buf.getvalue().strip())
    # The chain keeps moving on a slug that IS validated — and the source says the flag was
    # refused rather than pretending none was passed.
    assert out["task_slug"] == "good-slug"
    assert out["task_slug_source"] == "rejected-fallback"


# --- round-1 P2: a schema-valid marker with a garbage created_at ----------------


def test_gc_collects_a_marker_with_an_unparseable_created_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`created_at` is a plain `str`, so "not-a-date" VALIDATES. `active_marker` rejects it,
    so leaving it on disk wedges the project: the picker sees a non-armed marker and,
    per ADR-010, will not arm over it."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    p = autopilot.marker_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    from harness_maker.worktree import _current_session_uuid

    p.write_text(
        json.dumps(
            {
                "session_uuid": _current_session_uuid(tmp_path),
                "level": "auto_safe",
                "pipeline": [s.value for s in PIPELINE],
                "created_at": "not-a-date",
                "claude_session_id": "sess-A",
            }
        ),
        encoding="utf-8",
    )
    assert autopilot.load(tmp_path) is not None, "it must actually validate"
    assert autopilot.active_marker(tmp_path) is None
    assert autopilot.gc_stale_marker(tmp_path) is True
    assert not p.exists()


# --- round-3: degraded-idless must not masquerade as a live peer ----------------


def test_status_distinguishes_degraded_idless_from_a_real_peer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WSL2: the SessionStart hook gets the id on stdin, but `$CLAUDE_ENV_FILE` fails so the
    session's own Bash has none. Labelling that `foreign` tells the picker a peer owns the
    user's OWN marker, and ADR-010's branch then refuses to arm — dark for the full TTL."""
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    _harness(tmp_path)
    autopilot_autoarm.arm_if_persistent(tmp_path, claude_session_id="sess-A")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot.main(["status", "--root", str(tmp_path)])
    out = json.loads(buf.getvalue().strip())
    assert out["active"] is False
    assert out["reason"] == "degraded-idless"

    # A session that DOES have an id, facing someone else's marker, is still plain foreign.
    monkeypatch.setenv("HM_SESSION_ID", "sess-B")
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        autopilot.main(["status", "--root", str(tmp_path)])
    assert json.loads(buf2.getvalue().strip())["reason"] == "foreign"


def test_write_refuses_to_clobber_a_future_dated_peer_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`gc_stale_marker` refuses to delete a `future` marker because it may be a peer's LIVE
    one; a `write` guard that only covered `fresh` let the same marker be overwritten
    instead — the same peer-disarm through the other door."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-PEER")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(
        tmp_path,
        level="auto_safe",
        pipeline=PIPELINE,
        now=(datetime.now(UTC) + timedelta(hours=5)).isoformat(),
    )
    before = autopilot.marker_path(tmp_path).read_bytes()
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    with pytest.raises(autopilot.MarkerOwnedByAnotherSessionError):
        autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)
    assert autopilot.marker_path(tmp_path).read_bytes() == before


def test_task_slug_rejects_a_trailing_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`re.match` + `$` accepts "ok\\n" — and this value reaches a shell command line."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)
    assert autopilot.set_task_slug(tmp_path, slug="ok\n", stage="research") is False


def test_rejected_slug_is_reported_distinctly_from_a_benign_inherit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The prompt reads the JSON, not stderr. Reporting the fall-through as plain
    "persisted" makes a refused slug indistinguishable from "no flag was passed"."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)
    autopilot.set_task_slug(tmp_path, slug="task-one", stage="research")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot_caps.main(
            ["boundary", "--root", str(tmp_path), "--current", "research", "--slug", "bad slug"]
        )
    out = json.loads(buf.getvalue().strip())
    assert out["task_slug"] == "task-one"
    assert out["task_slug_source"] == "rejected-fallback"


def test_rejected_slug_with_no_persisted_fallback_reports_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot_caps.main(
            ["boundary", "--root", str(tmp_path), "--current", "research", "--slug", "bad slug"]
        )
    out = json.loads(buf.getvalue().strip())
    assert out["task_slug"] is None
    assert out["task_slug_source"] == "rejected"


# --- round-4: an abandoned marker must not wedge the project for the full TTL ----


def test_heartbeat_is_refreshed_by_the_owner_and_surfaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`idle_minutes` is the FACT the picker puts to the user. Ownership alone cannot tell a
    live peer from a marker abandoned mid-pipeline — nothing clears the marker at session
    end, so a session that armed and closed used to lock the project out for 18h."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(
        tmp_path,
        level="auto_safe",
        pipeline=PIPELINE,
        now=(datetime.now(UTC) - timedelta(hours=3)).isoformat(),
    )
    marker = autopilot.load(tmp_path)
    assert marker is not None
    assert autopilot.idle_minutes(marker) > 170  # falls back to created_at

    assert autopilot.touch(tmp_path) is True
    refreshed = autopilot.load(tmp_path)
    assert refreshed is not None
    assert autopilot.idle_minutes(refreshed) < 1


def test_a_peer_cannot_refresh_someone_elses_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise a peer could keep a dead marker looking live forever."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)
    before = autopilot.marker_path(tmp_path).read_bytes()
    monkeypatch.setenv("HM_SESSION_ID", "sess-B")
    assert autopilot.touch(tmp_path) is False
    assert autopilot.marker_path(tmp_path).read_bytes() == before


def test_status_reports_idle_minutes_for_a_foreign_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-PEER")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(
        tmp_path,
        level="auto_safe",
        pipeline=PIPELINE,
        now=(datetime.now(UTC) - timedelta(hours=2)).isoformat(),
    )
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot.main(["status", "--root", str(tmp_path)])
    out = json.loads(buf.getvalue().strip())
    assert out["reason"] == "foreign"
    assert out["idle_minutes"] > 110


def test_an_implausibly_future_dated_marker_becomes_collectable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real clock skew is bounded. Beyond one TTL of it, a foreign marker was neither
    GC-able (GC preserves `future`) nor overwritable (the guard protects non-`stale`)."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-PEER")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(
        tmp_path,
        level="auto_safe",
        pipeline=PIPELINE,
        now=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
    )
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    assert autopilot.gc_stale_marker(tmp_path) is True
    assert not autopilot.marker_path(tmp_path).exists()


def test_modest_clock_skew_is_still_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bound must not undo the protection it was carved out of."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-PEER")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(
        tmp_path,
        level="auto_safe",
        pipeline=PIPELINE,
        now=(datetime.now(UTC) + timedelta(hours=2)).isoformat(),
    )
    monkeypatch.setenv("HM_SESSION_ID", "sess-MINE")
    assert autopilot.gc_stale_marker(tmp_path) is False
    assert autopilot.marker_path(tmp_path).exists()


def test_a_rejected_slug_halts_instead_of_authorizing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Authorizing while the prompt is told not to run strands a pending authorization that
    a later retry's entry would then be paired against."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot_caps.main(
            ["boundary", "--root", str(tmp_path), "--current", "research", "--slug", "bad slug"]
        )
    out = json.loads(buf.getvalue().strip())
    assert out["proceed"] is False
    assert out["halt_kind"] == "bad_slug"
    from harness_maker import autopilot_ledger

    assert autopilot_ledger.count_events(tmp_path, "advance_authorized") == 0


def test_pairing_follows_append_order_not_timestamps(tmp_path: Path) -> None:
    """The ledger is O_APPEND, so file order IS write order. Reconstructing order from `ts`
    made the pairing hostage to a clock rollback."""
    from harness_maker import autopilot_ledger

    base = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)
    autopilot_ledger.append_event(
        tmp_path, event="advance_authorized", fields={"to": "spec"}, now=base.isoformat()
    )
    # An entry whose ts LOOKS older than the authorization (clock rollback) still confirms
    # it, because it was appended after.
    autopilot_ledger.append_event(
        tmp_path,
        event="advance_entered",
        fields={"to": "spec", "elapsed_s": 0.0},
        now=(base - timedelta(hours=1)).isoformat(),
    )
    assert autopilot_ledger.find_unconfirmed_authorization(tmp_path, to="spec", since=None) is None


# --- round-5 ---------------------------------------------------------------------


def test_heartbeat_survives_the_slug_write_on_the_same_boundary_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_cmd_boundary` calls `touch` and then `set_task_slug` — both read-modify-write the
    same file. The only load-bearing interaction of the heartbeat had no gate: a future
    de-duplication that reused the pre-touch snapshot would silently drop `last_seen`,
    making a LIVE session report a growing idle and re-opening the abandoned-marker wedge.
    """
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(
        tmp_path,
        level="auto_safe",
        pipeline=PIPELINE,
        now=(datetime.now(UTC) - timedelta(hours=3)).isoformat(),
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot_caps.main(
            ["boundary", "--root", str(tmp_path), "--current", "research", "--slug", "good-slug"]
        )
    after = autopilot.load(tmp_path)
    assert after is not None
    assert after.task_slug == "good-slug"
    idle = autopilot.idle_minutes(after)
    assert idle is not None
    assert idle < 1, "the heartbeat was dropped by the slug write"


def test_touch_refuses_when_the_marker_changed_underneath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deliberate `--force` takeover landing mid-touch must not be reverted."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)

    real = autopilot.active_marker
    calls = {"n": 0}

    def _takeover_after_first_read(root, **kw):  # noqa: ANN001, ANN202
        out = real(root, **kw)
        calls["n"] += 1
        if calls["n"] == 1:
            monkeypatch.setenv("HM_SESSION_ID", "sess-B")
            autopilot.write(tmp_path, level="full", pipeline=PIPELINE, force=True)
            monkeypatch.setenv("HM_SESSION_ID", "sess-A")
        return out

    monkeypatch.setattr(autopilot, "active_marker", _takeover_after_first_read)
    autopilot.touch(tmp_path)
    monkeypatch.setattr(autopilot, "active_marker", real)

    raw = _raw(tmp_path)
    assert raw["claude_session_id"] == "sess-B", "the takeover must stand"
    assert raw["level"] == "full"


def test_idle_minutes_is_unknown_not_zero_for_a_future_stamp(tmp_path: Path) -> None:
    """Clamping to 0.0 reported "active right now" for a clock-skewed marker — and the
    picker puts that number to the user as the fact that decides a takeover."""
    from harness_maker.worktree import _current_session_uuid

    p = autopilot.marker_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "session_uuid": _current_session_uuid(tmp_path),
                "level": "auto_safe",
                "pipeline": [s.value for s in PIPELINE],
                "created_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    marker = autopilot.load(tmp_path)
    assert marker is not None
    assert autopilot.idle_minutes(marker) is None


def test_a_repeated_authorization_does_not_bank_a_second_confirmable_slot(
    tmp_path: Path,
) -> None:
    """A re-run boundary (corrected --slug, retried stage) issues a second authorization.
    Banking both would let one real entry be followed by a spare slot that a later entry
    consumes, so the step cap would count work that never happened."""
    from harness_maker import autopilot_ledger

    base = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)
    for i in range(3):
        autopilot_ledger.append_event(
            tmp_path,
            event="advance_authorized",
            fields={"to": "spec"},
            now=(base + timedelta(minutes=i)).isoformat(),
        )
    autopilot_ledger.append_event(
        tmp_path,
        event="advance_entered",
        fields={"to": "spec", "elapsed_s": 1.0},
        now=(base + timedelta(minutes=5)).isoformat(),
    )
    assert autopilot_ledger.find_unconfirmed_authorization(tmp_path, to="spec", since=None) is None


# --- round-6 ---------------------------------------------------------------------


def test_same_owner_writes_do_not_clobber_each_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`created_at` was the change detector, but NEITHER writer mutates it — `touch`
    changes `last_seen`, `set_task_slug` changes `task_slug` — so every same-owner
    collision passed the guard and the later writer reverted the other's field. Co-owners
    are a real population: `_is_own` falls back to the project-scoped `session_uuid`
    whenever neither side has a session id (Cursor, Codex, WSL2 env-file failure).
    """
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)
    assert autopilot.set_task_slug(tmp_path, slug="task-one", stage="research") is True

    # Simulate the interleave: capture a PRE-slug snapshot, then try to write it back.
    stale = autopilot.load(tmp_path)
    assert stale is not None
    stale_bytes = autopilot.marker_path(tmp_path).read_bytes()
    autopilot.touch(tmp_path)  # a co-owner's heartbeat lands
    # The pre-touch snapshot must no longer be writable.
    assert (
        autopilot._write_if_unchanged(
            tmp_path, before=stale_bytes, updated=stale.model_copy(update={"task_slug": None})
        )
        is False
    )
    after = autopilot.load(tmp_path)
    assert after is not None
    assert after.task_slug == "task-one", "the slug was reverted by a stale snapshot"


def test_unknown_stage_does_not_stamp_the_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--current bogus --slug s` used to write `task_slug_stage: "bogus"` and THEN report
    "marker preserved" — a contract the slug write had already broken."""
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=PIPELINE)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        autopilot_caps.main(
            ["boundary", "--root", str(tmp_path), "--current", "bogus", "--slug", "my-task"]
        )
    assert json.loads(buf.getvalue().strip())["halt_kind"] == "unknown_stage"
    after = autopilot.load(tmp_path)
    assert after is not None
    # The heartbeat DOES refresh — a typo'd `--current` is still proof the session is
    # alive, and `touch` runs before any stage validation. What must not happen is the
    # slug write attributing itself to a stage that is not in the pipeline.
    assert after.task_slug is None
    assert after.task_slug_stage is None


def test_bad_slug_is_in_the_declared_halt_vocabulary() -> None:
    """`out` is `dict[str, object]`, so mypy could not see the JSON contract diverge from
    the Literal the module declares."""
    from typing import get_args

    assert "bad_slug" in get_args(autopilot_caps.HaltKind)
