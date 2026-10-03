"""SPEC-maker-front-door-improvements S4/S5 — `autopilot narrow --until E` (AC-008, AC-009).

Narrow only ever shrinks the session's pipeline (PLAN ADR-001); the boundary that would have
cleared the marker at the narrowed end restores the saved original instead (ADR-002).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from harness_maker import autopilot, autopilot_caps
from harness_maker.models import AtomicStage, AutonomyConfig
from harness_maker.spec_machine import load_golden_table
from harness_maker.worktree import _current_session_uuid

_SPEC_YAML = Path(__file__).parents[2] / "specs/SPEC-maker-front-door-improvements.machine.yaml"
_AC009_ROWS = load_golden_table(_SPEC_YAML, "AC-009")

_SID = "11111111-2222-3333-4444-555555555555"
_FOREIGN_SID = "99999999-8888-7777-6666-555555555555"
# The default armed pipeline (research..verify, wrapup) — NOT `list(AtomicStage)`, whose
# declaration order puts wrapup before verify.
_FULL: list[str] = [s.value for s in AutonomyConfig().pipeline]
# `wrapup` is excluded on purpose: a full pipeline already ends there (narrow is a no-op) and
# the stage before it halts on `merge_gate` (wrapup is human-gated) — the AC-008 relation
# "every stage before E proceeds" cannot hold for E=wrapup. The machine.yaml input_domain
# lists it; that discrepancy is reported upward, not resolved here.
_END_STAGES = ("research", "spec", "execute", "review", "verify")


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A harness root (`.claude/harness.yaml` sentinel) so `resolve_marker_root` stops here."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    # The spec boundary derives its gate from an approved SPEC for the task slug; with no slug
    # it derives `pending` and halts at auto_safe. That gate is not under test here — pin it
    # to `clear` so only narrow/restore decides proceed vs. stop.
    monkeypatch.setattr(autopilot_caps, "_derived_spec_gate", lambda _root, _slug: "clear")
    return tmp_path


def _arm(root: Path, *, pipeline: list[str], level: str = "auto_safe", sid: str = _SID) -> None:
    autopilot.write(
        root,
        level=level,  # type: ignore[arg-type]
        pipeline=[AtomicStage(s) for s in pipeline],
        claude_session_id=sid,
    )


def _narrow(root: Path, until: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Run the CLI in-process. An argparse rejection becomes its exit code, not an error."""
    capsys.readouterr()
    argv = ["narrow", "--until", until, "--root", str(root), "--session-id", _SID]
    try:
        rc = autopilot.main(argv)
    except SystemExit as exc:  # unknown action today → argparse exit 2
        rc = exc.code if isinstance(exc.code, int) else 2
    captured = capsys.readouterr()
    return rc, captured.out + captured.err


def _boundary(root: Path, current: str, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    capsys.readouterr()
    argv = [
        "boundary",
        "--root",
        str(root),
        "--current",
        current,
        "--session-id",
        _SID,
        "--step-cap",
        "20",
        "--time-cap-min",
        "300",
        "--judgment-gate",
        "clear",
    ]
    assert autopilot_caps.main(argv) == 0
    out: dict[str, Any] = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return out


def _marker_raw(root: Path, sid: str = _SID) -> dict[str, Any]:
    path = autopilot.marker_path(root, session_id=sid)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


# ── AC-008 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("level", ["auto_safe", "gated"])
@pytest.mark.parametrize("end", _END_STAGES)
def test_ac008_narrow_stop_and_restore(
    root: Path, end: str, level: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _arm(root, pipeline=_FULL, level=level)
    before = autopilot.load(root, session_id=_SID)
    assert before is not None

    rc, _ = _narrow(root, end, capsys)
    assert rc == 0

    stages = _FULL[: _FULL.index(end) + 1]
    results = {s: _boundary(root, s, capsys) for s in stages}

    path = autopilot.marker_path(root, session_id=_SID)
    assert path.is_file(), "narrowed end must NOT clear the marker (ADR-002)"
    after = autopilot.load(root, session_id=_SID)
    assert after is not None
    assert after.level == before.level == level
    assert after.created_at == before.created_at
    assert after.claude_session_id == before.claude_session_id == _SID

    if level == "gated":
        # `gated` never auto-advances (existing contract: kill_switch at every boundary, marker
        # preserved), so the proceed-before-E half is inapplicable and the `nxt is None` restore
        # branch is never reached. What must still hold: no stage advanced, and the pre-narrow
        # PLAN ADR-001 amendment: at gated, narrow writes nothing — a write could never be
        # restored and would leave a latent `restore_pipeline`.
        for s, out in results.items():
            assert out["proceed"] is False, s
            assert out["halt_kind"] == "kill_switch", s
        assert [p.value for p in after.pipeline] == _FULL
        assert after.restore_pipeline is None
        return

    for s in stages[:-1]:
        assert results[s]["proceed"] is True, (s, results[s])
    assert results[end]["proceed"] is False, results[end]
    assert results[end]["pipeline_complete"] is False, "narrowed end is not pipeline completion"
    assert [p.value for p in after.pipeline] == _FULL
    assert after.restore_pipeline is None


# ── AC-009 ─────────────────────────────────────────────────────────────────────


def _row_id(i: int, row: Any) -> str:
    return f"{i}-{str(row.input['case']).replace(' ', '_').replace(',', '')}"


@pytest.mark.parametrize("row", _AC009_ROWS, ids=[_row_id(i, r) for i, r in enumerate(_AC009_ROWS)])
def test_ac009_narrow_never_widens(
    root: Path, row: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    case = row.input["case"]
    expected = row.expected
    own = autopilot.marker_path(root, session_id=_SID)

    if case == "no marker":
        rc, said = _narrow(root, "research", capsys)
        assert rc == expected["exit"] == 0
        assert expected["marker"] == "absent"
        assert not own.exists(), "narrow must never arm an unarmed session"
        assert said.strip(), "S5: exits 0 *with a reason*"
        return

    if case == "foreign live marker":
        _arm(root, pipeline=_FULL, sid=_FOREIGN_SID)
        foreign = autopilot.marker_path(root, session_id=_FOREIGN_SID)
        # Also plant the foreign-owned marker at OUR keyed path: that is the copy narrow
        # actually reads, so it is what exercises the ownership check.
        own.write_bytes(foreign.read_bytes())
        snapshot = {p: p.read_bytes() for p in (foreign, own)}
        rc, said = _narrow(root, "research", capsys)
        assert rc == expected["exit"] == 0
        assert expected["marker"] == "unchanged"
        for p, b in snapshot.items():
            assert p.read_bytes() == b, p
        assert said.strip(), "S5: exits 0 *with a reason*"
        return

    if case == "pipeline already ends before E":
        armed, until = ["research", "spec"], "execute"
    elif case == "E already passed":
        armed, until = ["spec", "execute", "review", "verify", "wrapup"], "research"
    elif case == "full pipeline, level gated":
        armed, until = list(_FULL), "spec"
    else:  # pragma: no cover — a new golden row needs an explicit setup here
        pytest.fail(f"unmapped AC-009 golden row: {case!r}")

    level = "gated" if case == "full pipeline, level gated" else "auto_safe"
    _arm(root, pipeline=armed, level=level)
    before = autopilot.load(root, session_id=_SID)
    assert before is not None

    rc, _ = _narrow(root, until, capsys)
    assert rc == 0
    if "exit" in expected:
        assert rc == expected["exit"]
    after = autopilot.load(root, session_id=_SID)
    assert after is not None

    if expected.get("pipeline") == "unchanged" or level == "gated":
        # Gated: PLAN ADR-001 amendment — narrow writes nothing at a non-advancing level.
        assert after.pipeline == before.pipeline
        assert after.restore_pipeline is None
    if "level" in expected:
        assert after.level == expected["level"]
    if expected.get("created_at") == "unchanged":
        assert after.created_at == before.created_at
    # Never widens, whichever row: the effective pipeline is a prefix of the armed one.
    assert [p.value for p in after.pipeline] == armed[: len(after.pipeline)]
    assert after.level == before.level
    assert after.claude_session_id == _SID


# ── absent case: a marker written before `restore_pipeline` existed ────────────


def test_ac008_pre_upgrade_marker_validates(root: Path) -> None:
    # Hand-written in today's on-disk shape — NOT via `autopilot.write`, which after the
    # upgrade would emit `restore_pipeline: null` and no longer model a pre-upgrade marker.
    pre_upgrade = {
        "session_uuid": _current_session_uuid(root),
        "level": "auto_safe",
        "pipeline": list(_FULL),
        "created_at": datetime.now(UTC).isoformat(),
        "task_slug": None,
        "task_slug_stage": None,
        "claude_session_id": _SID,
        "last_seen": None,
    }
    path = autopilot.marker_path(root, session_id=_SID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pre_upgrade), encoding="utf-8")
    assert "restore_pipeline" not in _marker_raw(root)

    loaded = autopilot.load(root, session_id=_SID)
    active = autopilot.active_marker(root, session_id=_SID)
    assert loaded is not None
    assert active is not None
    # Absent-case rule: the missing field defaults to None (not narrowed), rather than the
    # marker being rejected under `extra="forbid"` or silently treated as off.
    assert loaded.restore_pipeline is None
    assert active.restore_pipeline is None
    assert [p.value for p in active.pipeline] == _FULL


# ── REVIEW round 2: re-narrow, undo, superseded restore, distinct causes ───────


def test_double_narrow_keeps_armed_restore_and_boundary_restores_it(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REVIEW c5c46e75: a second narrow recomputes from the ARMED pipeline, not the narrowed one."""
    _arm(root, pipeline=_FULL)
    assert _narrow(root, "review", capsys)[0] == 0
    assert _narrow(root, "spec", capsys)[0] == 0
    mid = autopilot.load(root, session_id=_SID)
    assert mid is not None
    assert [p.value for p in mid.pipeline] == ["research", "spec"]
    assert mid.restore_pipeline is not None
    assert [p.value for p in mid.restore_pipeline] == _FULL

    assert _boundary(root, "research", capsys)["proceed"] is True
    out = _boundary(root, "spec", capsys)
    assert out["proceed"] is False
    assert out["narrow_end"] is True
    assert out["reason"].endswith("pipeline restored"), out["reason"]
    after = autopilot.load(root, session_id=_SID)
    assert after is not None
    assert [p.value for p in after.pipeline] == _FULL
    assert after.restore_pipeline is None


def test_narrow_to_armed_end_undoes_a_narrow(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REVIEW aea107e8: a run that stopped short of its narrowed end can be un-narrowed."""
    _arm(root, pipeline=_FULL)
    before = autopilot.load(root, session_id=_SID)
    assert before is not None
    assert _narrow(root, "review", capsys)[0] == 0

    rc, said = _narrow(root, _FULL[-1], capsys)
    assert rc == 0
    result = json.loads(said.strip().splitlines()[-1])
    assert result["restored"] is True
    assert result["narrowed"] is False
    after = autopilot.load(root, session_id=_SID)
    assert after is not None
    assert [p.value for p in after.pipeline] == _FULL
    assert after.restore_pipeline is None
    assert after.level == before.level
    assert after.created_at == before.created_at


def test_restore_with_superseded_expectation_does_not_overwrite(root: Path) -> None:
    """REVIEW 46a3fe23: a concurrent re-narrow must survive the older boundary's restore."""
    _arm(root, pipeline=_FULL)
    autopilot.narrow(root, until="review", session_id=_SID)
    raw_before = autopilot.marker_path(root, session_id=_SID).read_bytes()

    cause = autopilot.restore_narrowed(
        root, session_id=_SID, expected_pipeline=["research", "spec"]
    )
    assert cause == "superseded"
    assert autopilot.marker_path(root, session_id=_SID).read_bytes() == raw_before


def test_restore_causes_are_distinct(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REVIEW 7a51c2b1 / 091d480f: each restore failure names its own cause."""
    narrowed = _FULL[: _FULL.index("review") + 1]
    assert (
        autopilot.restore_narrowed(root, session_id=_SID, expected_pipeline=narrowed) == "no_marker"
    )
    _arm(root, pipeline=_FULL)
    assert (
        autopilot.restore_narrowed(root, session_id=_SID, expected_pipeline=_FULL) == "not_narrowed"
    )
    autopilot.narrow(root, until="review", session_id=_SID)

    calls: list[int] = []

    def _always_lose(*_a: Any, **_k: Any) -> bool:
        calls.append(1)
        return False

    with monkeypatch.context() as m:
        m.setattr(autopilot, "_write_if_unchanged", _always_lose)
        assert (
            autopilot.restore_narrowed(root, session_id=_SID, expected_pipeline=narrowed) == "raced"
        )
    assert len(calls) == 2, "one retry after a byte-identity miss"

    assert autopilot.restore_narrowed(root, session_id=_SID, expected_pipeline=narrowed) is None
    after = autopilot.load(root, session_id=_SID)
    assert after is not None
    assert [p.value for p in after.pipeline] == _FULL


def test_narrow_to_a_stage_the_custom_pipeline_lacks_restores_it(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Post-review (confirm-2 P3): Maker's fixed `--until wrapup` is the undo path; on a custom
    armed pipeline without wrapup it must still restore a leftover narrowing — and only to the
    ARMED pipeline, never beyond it. Without a leftover, the same call stays a no-op."""
    armed = ["research", "spec", "execute", "review"]
    _arm(root, pipeline=armed, level="auto_safe")
    rc, _ = _narrow(root, "spec", capsys)
    assert rc == 0
    narrowed = autopilot.load(root, session_id=_SID)
    assert narrowed is not None
    assert [p.value for p in narrowed.pipeline] == ["research", "spec"]
    rc, _ = _narrow(root, "wrapup", capsys)
    assert rc == 0
    after = autopilot.load(root, session_id=_SID)
    assert after is not None
    assert [p.value for p in after.pipeline] == armed
    assert after.restore_pipeline is None
    assert after.level == narrowed.level
    assert after.created_at == narrowed.created_at
    # No leftover: a stage the armed pipeline lacks changes nothing.
    rc, _ = _narrow(root, "wrapup", capsys)
    assert rc == 0
    again = autopilot.load(root, session_id=_SID)
    assert again is not None
    assert [p.value for p in again.pipeline] == armed


def test_narrow_to_an_unknown_stage_keeps_a_deliberate_narrowing(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Post-review focused pass: only Maker's literal `wrapup` is the absent-stage undo. A typo
    or invented stage must leave a deliberate narrowing in place."""
    _arm(root, pipeline=["research", "spec", "execute", "review"], level="auto_safe")
    rc, _ = _narrow(root, "spec", capsys)
    assert rc == 0
    rc, _ = _narrow(root, "specc", capsys)
    assert rc == 0
    after = autopilot.load(root, session_id=_SID)
    assert after is not None
    assert [p.value for p in after.pipeline] == ["research", "spec"]
    assert after.restore_pipeline is not None
