"""Phase 2 of PLAN-sessionid-env-propagation — autopilot's session-id channel.

The reader half of autopilot's ownership check reads `HM_SESSION_ID` from the process
environment, where it is never present, so `session_scoped` is permanently false and an
id-bearing marker is permanently `foreign`.

The dangerous part is the ASYMMETRY, and that is what most of this file pins. `_is_own` is
one-directional by design: ids are compared whenever EITHER side has one. So the moment the
writer stamps an id, every reader that still resolves id-less computes `env_id is None and
marker_id is not None` -> foreign -> `active_marker` None -> `evaluate_boundary` kill_switch.
Wiring the writer without the readers does not leave autopilot degraded; it turns it OFF.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import autopilot, autopilot_caps
from harness_maker.models import AtomicStage

_PIPELINE = [AtomicStage.PLAN, AtomicStage.EXECUTE, AtomicStage.REVIEW]
_SID = "session-aaa"


@pytest.fixture(autouse=True)
def _no_ambient_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real shape of a Bash subprocess: the variable is never exported."""
    monkeypatch.delenv("HM_SESSION_ID", raising=False)


def _arm(root: Path, *, claude_session_id: str | None) -> None:
    autopilot.write(
        root,
        level="auto_safe",
        pipeline=_PIPELINE,
        claude_session_id=claude_session_id,
    )


# ── the P0: an id-bearing marker read by an id-less caller ──────────────────


def test_id_bearing_marker_is_foreign_to_an_idless_reader(tmp_path: Path) -> None:
    """This is the failure mode, asserted directly rather than described in prose.

    It is ALREADY the live state for `autonomy.autopilot_persistent: true` harnesses,
    whose SessionStart hook stamps the id from its stdin payload.
    """
    _arm(tmp_path, claude_session_id=_SID)
    assert autopilot.active_marker(tmp_path) is None, (
        "an id-less reader must not silently adopt an id-bearing marker"
    )


def test_passing_the_id_restores_ownership(tmp_path: Path) -> None:
    """The fix. Same marker, same environment — only the argument differs."""
    _arm(tmp_path, claude_session_id=_SID)
    assert autopilot.active_marker(tmp_path, session_id=_SID) is not None


def test_evaluate_boundary_proceeds_only_with_the_id(tmp_path: Path) -> None:
    """The ownership proof on the path that actually drives auto-advance.

    `evaluate_boundary` is pure (no `touch`, no `_confirm_entry`, no `clear`), so it is
    the honest probe. The `autopilot_caps boundary` CLI is NOT: it mutates the ledger and
    clears the marker on the last stage.
    """
    _arm(tmp_path, claude_session_id=_SID)

    blind = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=None, time_cap_min=None)
    assert blind.proceed is False
    assert blind.halt_kind == "kill_switch"

    wired = autopilot_caps.evaluate_boundary(
        tmp_path, steps=0, step_cap=None, time_cap_min=None, session_id=_SID
    )
    assert wired.proceed is True
    assert wired.halt_kind is None


def test_a_genuinely_foreign_marker_still_halts(tmp_path: Path) -> None:
    """The guard must not become a rubber stamp: a DIFFERENT id is still foreign."""
    _arm(tmp_path, claude_session_id=_SID)
    decision = autopilot_caps.evaluate_boundary(
        tmp_path, steps=0, step_cap=None, time_cap_min=None, session_id="session-bbb"
    )
    assert decision.proceed is False
    assert decision.halt_kind == "kill_switch"


# ── status ──────────────────────────────────────────────────────────────────


def test_status_reports_session_scoped_only_when_wired(tmp_path: Path) -> None:
    _arm(tmp_path, claude_session_id=_SID)

    blind = autopilot.status(tmp_path)
    assert blind["session_scoped"] is False
    assert blind["active"] is False, "an id-less read of an id-bearing marker is not active"

    wired = autopilot.status(tmp_path, session_id=_SID)
    assert wired["active"] is True
    assert wired["reason"] == "armed"
    assert wired["session_scoped"] is True


def test_status_degraded_idless_reason_survives(tmp_path: Path) -> None:
    """The `degraded-idless` vs `foreign` split exists so the picker can give opposite
    advice. Passing no id must still reach it, not collapse into `foreign`."""
    _arm(tmp_path, claude_session_id=_SID)
    assert autopilot.status(tmp_path)["reason"] == "degraded-idless"


# ── ADR-001's amendment: on THIS path, "" means id-less ─────────────────────


def test_empty_string_means_idless_on_the_autopilot_path(tmp_path: Path) -> None:
    """The 14 rendered call sites pass `--session-id "$HM_SESSION_ID"` unconditionally, so
    Cursor / Codex / a degraded session deliver `""`.

    The readiness tri-state deliberately distinguishes `None` from `""`; autopilot
    deliberately does NOT (`autopilot.py` already collapses them via `or`). Pinning the
    difference here stops a later refactor from "unifying" the two contracts.
    """
    _arm(tmp_path, claude_session_id=None)  # id-less marker, the manual-arm shape

    # An id-less marker + an id-less caller falls through to the project-uuid path.
    assert autopilot.active_marker(tmp_path, session_id="") is not None
    assert autopilot.status(tmp_path, session_id="")["active"] is True


def test_empty_string_cannot_own_an_id_bearing_marker(tmp_path: Path) -> None:
    """The other half: `""` collapses to id-less, so it must NOT match a stamped id.

    Kept in its own tmp root — `resolve_marker_root` walks UP, so a nested directory
    resolves to its parent's marker rather than getting one of its own.
    """
    _arm(tmp_path, claude_session_id=_SID)
    assert autopilot.active_marker(tmp_path, session_id="") is None


def test_idless_marker_is_still_owned_by_a_wired_caller(tmp_path: Path) -> None:
    """One-directional rule, the other way: a caller WITH an id must not adopt a
    fieldless legacy marker. `loop_marker` forbids exactly this direction."""
    _arm(tmp_path, claude_session_id=None)
    assert autopilot.active_marker(tmp_path, session_id=_SID) is None


# ── every INTERNAL marker reader, not just the ones the CLI names ────────────
#
# REVIEW round 1 P0. The first cut of this phase wired the three `active_marker`
# call sites that `autopilot_caps` owns and left `touch`, `set_task_slug` and
# `effective_level` resolving id-less inside `autopilot`. The pure-function probes
# above all stayed green, because none of them crosses into those helpers — so the
# defect reproduced the very asymmetry this file's own docstring calls fatal.
# Three independent reviewers plus the cross-model voter converged on it.


def test_touch_refreshes_the_heartbeat_only_when_wired(tmp_path: Path) -> None:
    """An id-less `touch` against a stamped marker is a silent no-op, which makes a live
    owner look abandoned to the takeover prompt — the signal it exists to feed."""
    _arm(tmp_path, claude_session_id=_SID)

    assert autopilot.touch(tmp_path, now="2026-01-01T00:00:00+00:00") is False
    assert autopilot.touch(tmp_path, now="2026-01-01T00:00:00+00:00", session_id=_SID) is True

    marker = autopilot.active_marker(tmp_path, session_id=_SID)
    assert marker is not None
    assert marker.last_seen == "2026-01-01T00:00:00+00:00"


def test_set_task_slug_persists_only_when_wired(tmp_path: Path) -> None:
    """A False here is not inert: `_resolve_task_slug` turns it into a `bad_slug` halt
    naming a slug that in fact passed validation."""
    _arm(tmp_path, claude_session_id=_SID)

    assert autopilot.set_task_slug(tmp_path, slug="my-task", stage="plan") is False
    assert autopilot.set_task_slug(tmp_path, slug="my-task", stage="plan", session_id=_SID) is True

    marker = autopilot.active_marker(tmp_path, session_id=_SID)
    assert marker is not None
    assert marker.task_slug == "my-task"


def test_effective_level_honours_the_marker_only_when_wired(tmp_path: Path) -> None:
    """An id-less resolve silently downgrades a `full`/`auto_safe` session to the
    committed yaml default — a precedence inversion with no diagnostic."""
    autopilot.write(tmp_path, level="full", pipeline=_PIPELINE, claude_session_id=_SID)  # type: ignore[arg-type]  # legacy level, normalized on write

    assert autopilot.effective_level(tmp_path, yaml_level="gated") == "gated"
    assert autopilot.effective_level(tmp_path, yaml_level="gated", session_id=_SID) == "auto_safe"


def test_the_boundary_cli_proceeds_end_to_end_with_a_stamped_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate the pure-function probes explicitly declined to be.

    `test_evaluate_boundary_proceeds_only_with_the_id` calls the pure function directly and
    says so in its own docstring; that is exactly the seam the P0 slipped through — the CLI
    validated the marker with the id and then re-read it without. Driving `main()` covers the
    whole chain (marker check -> touch -> slug persist -> evaluate_boundary).

    `touch` needs an assertion of its own (round-2 P1 on this very test): its return value
    is discarded by the caller and its only effect is `last_seen` INSIDE the marker, so no
    JSON field moves when its `session_id=` is dropped. Stamping a known-old `last_seen`
    first makes the advance observable instead of a same-microsecond coin flip.
    """
    import json

    _arm(tmp_path, claude_session_id=_SID)
    stale = "2020-01-01T00:00:00+00:00"
    assert autopilot.touch(tmp_path, now=stale, session_id=_SID) is True
    rc = autopilot_caps.main(
        [
            "boundary",
            "--root",
            str(tmp_path),
            "--current",
            "plan",
            "--slug",
            "my-task",
            "--session-id",
            _SID,
            # B3 made the flag fail-closed and `plan` owns a judgment gate; this test is
            # about session-id wiring, so the gate is declared clear.
            "--judgment-gate",
            "clear",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is True, f"a stamped marker + the matching id must advance: {out}"
    assert out["halt_kind"] is None
    assert out["task_slug"] == "my-task"
    assert out["task_slug_source"] == "flag"

    after = autopilot.load(tmp_path, session_id=_SID)
    assert after is not None
    assert after.last_seen != stale, (
        "the boundary's heartbeat did not advance — `touch` resolved id-less, so a live "
        "owner keeps reporting growing idle to the takeover prompt"
    )


def test_the_gate_blocked_cli_records_with_a_stamped_marker(tmp_path: Path) -> None:
    """`main()`'s OTHER branch, which wires the id at two call sites of its own.

    Round-3 P1: the boundary branch got an end-to-end test and this one did not, and the two
    pre-existing `gate-blocked` tests cannot cover it — one arms an id-less marker (both sides
    id-less, so `_is_own` takes the project-uuid fallback) and the other sets `HM_SESSION_ID`,
    which supplies the same id whether or not the argument is forwarded. So this branch could
    be un-wired without a single test going red — the round-2 defect on the sibling branch.
    """
    from harness_maker import autopilot_ledger

    _arm(tmp_path, claude_session_id=_SID)
    stale = "2020-01-01T00:00:00+00:00"
    assert autopilot.touch(tmp_path, now=stale, session_id=_SID) is True

    rc = autopilot_caps.main(
        ["gate-blocked", "--root", str(tmp_path), "--stage", "plan", "--session-id", _SID]
    )
    assert rc == 0

    rows = autopilot_ledger.ledger_path(tmp_path).read_text(encoding="utf-8").splitlines()
    assert any('"gate_blocked"' in row for row in rows), (
        "no gate_blocked row was appended — `active_marker` resolved id-less and the branch "
        f"returned before the ledger write; rows={rows}"
    )

    after = autopilot.load(tmp_path, session_id=_SID)
    assert after is not None
    assert after.last_seen != stale, "the gate-blocked branch's heartbeat did not advance"


def test_the_typer_autopilot_surface_round_trips_the_session_id(tmp_path: Path) -> None:
    """The OTHER shipped entry point. `hm autopilot` (dot-form) and `harness-maker autopilot`
    (Typer) are one command with two spellings, and only the dot-form was wired — the exact
    "write grew a feature and one of its two callers was updated" precedent cli.py records
    a few lines below the option itself.
    """
    import json

    from typer.testing import CliRunner

    from harness_maker.cli import app

    runner = CliRunner()
    armed = runner.invoke(app, ["autopilot", "on", "--root", str(tmp_path), "--session-id", _SID])
    assert armed.exit_code == 0, armed.output

    wired = json.loads(
        runner.invoke(
            app, ["autopilot", "status", "--root", str(tmp_path), "--session-id", _SID]
        ).output
    )
    assert wired["active"] is True
    assert wired["session_scoped"] is True

    # And the marker it wrote really is id-stamped, not merely readable by its own writer.
    blind = json.loads(runner.invoke(app, ["autopilot", "status", "--root", str(tmp_path)]).output)
    assert blind["active"] is False
    assert blind["reason"] == "degraded-idless"
