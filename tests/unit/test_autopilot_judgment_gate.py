"""Phase B3 (ADR-009/010) — the judgment gate, keyed by SOURCE stage and fail-closed.

This is the PLAN's largest blast radius: it changes what happens at the end of every stage at
every level. Three things in it are easy to get backwards, and the matrix below exists because
drafts of this PLAN got two of them backwards on paper:

* **`clear` must proceed at every level, including `auto_safe`.** An earlier draft pinned
  `proceed: false` at `auto_safe` unconditionally and called that "the default is unchanged".
  It is the opposite: it would have stopped every plan and review stage of every existing
  autopilot session, which is the whole feature going dark.
* **Absent flag means pending.** A stage that forgets to pass `--judgment-gate` must stop, not
  sail through. Fail-open here is indistinguishable from a stage with no gate at all.
* **`judgment_gate` PRESERVES the marker.** `merge_gate` clears it, and copying that would end
  the autopilot session at the first plan stage — while starving `smoke_check` of the rows
  that make the gate's own frequency measurable.

The keying is on `--current` (the stage that just ran and owns the judgment), NOT on the next
stage: with a non-default pipeline the `(source, next)` pair changes while the judgment does
not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker import autopilot, autopilot_caps, autopilot_ledger
from harness_maker.models import AtomicStage

_PIPELINE = [
    AtomicStage.RESEARCH,
    AtomicStage.SPEC,
    AtomicStage.PLAN,
    AtomicStage.EXECUTE,
    AtomicStage.REVIEW,
    AtomicStage.VERIFY,
    AtomicStage.WRAPUP,
]
_LEVELS = ("gated", "auto_safe", "auto_full")
_JUDGMENT_STAGES = ("plan", "review")


def _arm(root: Path, *, level: str, pipeline: list[AtomicStage] | None = None) -> None:
    autopilot.write(root, level=level, pipeline=pipeline or list(_PIPELINE))  # type: ignore[arg-type]


def _boundary(
    root: Path, *, current: str, gate: str | None = None, capsys: pytest.CaptureFixture[str]
) -> dict[str, object]:
    argv = ["boundary", "--root", str(root), "--current", current]
    if gate is not None:
        argv += ["--judgment-gate", gate]
    autopilot_caps.main(argv)
    out = capsys.readouterr().out.strip().splitlines()[-1]
    result: dict[str, object] = json.loads(out)
    return result


# ── 1: the clean path is preserved at EVERY level ─────────────────────────────


@pytest.mark.parametrize("level", list(_LEVELS))
@pytest.mark.parametrize("current", list(_JUDGMENT_STAGES))
def test_clear_proceeds_at_every_level(
    tmp_path: Path, level: str, current: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _arm(tmp_path, level=level)
    assert _boundary(tmp_path, current=current, gate="clear", capsys=capsys)["proceed"] is True


# ── 2 + 3: pending stops by default, and absent IS pending ────────────────────


@pytest.mark.parametrize("level", ["gated", "auto_safe"])
@pytest.mark.parametrize("current", list(_JUDGMENT_STAGES))
@pytest.mark.parametrize("gate", ["pending", None])
def test_pending_and_absent_both_stop(
    tmp_path: Path, level: str, current: str, gate: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    _arm(tmp_path, level=level)
    res = _boundary(tmp_path, current=current, gate=gate, capsys=capsys)
    assert res["proceed"] is False
    assert res["halt_kind"] == "judgment_gate"


# ── 4: the differential — auto_full answers instead of stopping ───────────────


@pytest.mark.parametrize("current", list(_JUDGMENT_STAGES))
def test_auto_full_proceeds_through_a_pending_gate(
    tmp_path: Path, current: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _arm(tmp_path, level="auto_full")
    res = _boundary(tmp_path, current=current, gate="pending", capsys=capsys)
    assert res["proceed"] is True
    assert res["judgment_auto_answered"] is True


@pytest.mark.parametrize("current", list(_JUDGMENT_STAGES))
def test_the_two_levels_actually_differ(
    tmp_path: Path, current: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without this, both levels could return the same thing and every test above pass."""
    safe_root, full_root = tmp_path / "safe", tmp_path / "full"
    safe_root.mkdir()
    full_root.mkdir()
    _arm(safe_root, level="auto_safe")
    _arm(full_root, level="auto_full")
    safe = _boundary(safe_root, current=current, gate="pending", capsys=capsys)
    full = _boundary(full_root, current=current, gate="pending", capsys=capsys)
    assert safe != full


# ── 5: the land gate survives, probed with the call that reaches it ───────────


def test_the_merge_gate_still_fires_at_auto_full(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--current wrapup` is the WRONG probe — it hits the `nxt is None` branch instead."""
    _arm(tmp_path, level="auto_full")
    res = _boundary(tmp_path, current="verify", gate="clear", capsys=capsys)
    assert res["proceed"] is False
    assert res["halt_kind"] == "merge_gate"
    assert res["next_stage"] == "wrapup"


# ── 6: source-stage keying, not (source, next) ────────────────────────────────


def test_a_non_default_pipeline_still_gates_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _arm(
        tmp_path,
        level="auto_safe",
        pipeline=[AtomicStage.PLAN, AtomicStage.REVIEW, AtomicStage.VERIFY, AtomicStage.WRAPUP],
    )
    res = _boundary(tmp_path, current="plan", gate="pending", capsys=capsys)
    assert res["halt_kind"] == "judgment_gate"


def test_a_non_judgment_stage_is_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """execute owns no judgment, so an absent flag must not stop it."""
    _arm(tmp_path, level="auto_safe")
    assert _boundary(tmp_path, current="execute", capsys=capsys)["proceed"] is True


# ── 8: the ledger row, and the marker that must survive ───────────────────────


def test_judgment_gate_records_a_row_and_preserves_the_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _arm(tmp_path, level="auto_safe")
    _boundary(tmp_path, current="plan", gate="pending", capsys=capsys)
    assert autopilot.active_marker(tmp_path) is not None, (
        "the marker was cleared — copying merge_gate's behaviour ends the session at the "
        "first plan stage"
    )
    assert autopilot_ledger.count_events(tmp_path, "gate_blocked") >= 1
