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
# `gated` is deliberately NOT here. An earlier version of this file parametrized it as a
# level that proceeds on a clear gate, which encoded the P0 codex found: `gated` means
# "never auto-advance", and `boundary` was not checking it at all. The dedicated test below
# pins the fail-closed behaviour instead.
_ADVANCING_LEVELS = ("auto_safe", "auto_full")
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


@pytest.mark.parametrize("level", list(_ADVANCING_LEVELS))
@pytest.mark.parametrize("current", list(_JUDGMENT_STAGES))
def test_clear_proceeds_at_every_level(
    tmp_path: Path, level: str, current: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _arm(tmp_path, level=level)
    assert _boundary(tmp_path, current=current, gate="clear", capsys=capsys)["proceed"] is True


# ── 2 + 3: an explicit `pending` stops below auto_full; ABSENT stops everywhere ──
# (This heading used to read 'absent IS pending'. That was true for one round and it was
#  the round-2 P0. Left uncorrected it would be the same retraction-survives-verbatim
#  pattern this file's sibling entries record.)


@pytest.mark.parametrize("level", ["auto_safe"])
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


# ── the level that must never advance at all ──────────────────────────────────


@pytest.mark.parametrize("gate", ["clear", "pending", None])
def test_a_gated_marker_never_advances(
    tmp_path: Path, gate: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    """`gated` means never auto-advance, and nothing used to enforce it.

    Every other branch reads `marker.level` only to decide HOW to advance, so a gated marker
    sailed straight through with `proceed: true`. It was unreachable while the picker
    rendered only for non-gated harnesses; B4 made it reachable by offering `gated` as a pick
    and instructing "arm with the PICKED level" — i.e. on the default `ask` path. Found by
    the codex voter and reproduced before this test was written.
    """
    _arm(tmp_path, level="gated")
    res = _boundary(tmp_path, current="research", gate=gate, capsys=capsys)
    assert res["proceed"] is False
    assert res["halt_kind"] == "kill_switch"
    # The stop is RECORDED: without a row, a session that was offered autopilot and declined
    # is indistinguishable on the ledger from one whose marker simply expired.
    assert autopilot_ledger.count_events(tmp_path, "gate_blocked") == 1
    # NOT cleared: arming gated is how a session records "asked, declined". Clearing it would
    # make the picker re-offer at every stage.
    assert autopilot.active_marker(tmp_path) is not None


# ── the threshold half: `blocked` is un-clearable at EVERY level ──────────────


@pytest.mark.parametrize("level", list(_ADVANCING_LEVELS))
@pytest.mark.parametrize("current", list(_JUDGMENT_STAGES))
def test_blocked_halts_even_at_auto_full(
    tmp_path: Path, level: str, current: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-010's hard half, in code rather than in prose.

    Before the third flag value existed, a CHANGES_REQUESTED review and an APPROVED review
    with `human_review_needed` both reached `boundary` as `pending`, so `auto_full` cleared
    both — advancing past a failed grade, which ADR-010 lists as a Non-Goal. The separation
    lived only in a template sentence, which is the enforcement Interview #5 rejected.
    """
    _arm(tmp_path, level=level)
    res = _boundary(tmp_path, current=current, gate="blocked", capsys=capsys)
    assert res["proceed"] is False
    assert res["halt_kind"] == "judgment_gate"
    assert res["judgment_auto_answered"] is False
    # The stop must be RECORDED, not merely returned: `smoke_check` reads these rows, and a
    # halt that writes nothing is indistinguishable from a session that never ran.
    assert autopilot_ledger.count_events(tmp_path, "gate_blocked") >= 1


def test_the_auto_answer_leaves_a_row_of_its_own(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Otherwise an auto_full pass over a human decision is byte-identical to an auto_safe
    advance on the ledger, and the directive telling the model to record it is the only
    trace — which is exactly what the code's own comment calls an unauditable skip."""
    _arm(tmp_path, level="auto_full")
    _boundary(tmp_path, current="plan", gate="pending", capsys=capsys)
    assert autopilot_ledger.count_events(tmp_path, "gate_auto_answered") == 1


@pytest.mark.parametrize("level", list(_ADVANCING_LEVELS))
@pytest.mark.parametrize("current", list(_JUDGMENT_STAGES))
def test_an_omitted_verdict_halts_even_at_auto_full(
    tmp_path: Path, level: str, current: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """ABSENT is not `pending`, and the first attempt at this fix conflated them.

    `pending` is the caller SAYING a judgment is unresolved — a claim `auto_full` is licensed
    to answer. Absence is the caller saying nothing: a forgotten flag, or a harness rendered
    before the flag existed. Defaulting absence to `pending` reopened the round-1 P0 at
    exactly the level where it is dangerous, and both round-2 reviewers found it independently.
    """
    _arm(tmp_path, level=level)
    res = _boundary(tmp_path, current=current, gate=None, capsys=capsys)
    assert res["proceed"] is False
    assert res["halt_kind"] == "judgment_gate"
    reason = str(res["reason"])
    # The diagnostic must lead with the LIKELY cause. It first blamed a stale render, which is
    # false on a freshly rendered harness — and prescribed `--update`, which reproduces a
    # byte-identical file. Two reviewers filed that independently: a remedy that provably
    # cannot work is worse than no remedy.
    assert "--judgment-gate clear|pending|blocked" in reason, reason
    assert reason.index("omitted") < reason.index("stale render"), (
        "the forgotten append is the likely cause on a current render; the stale render is "
        "the fallback, and leading with it sends the user to a no-op remedy"
    )


def test_blocked_is_honoured_outside_the_judgment_stages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`blocked` is an assertion that a threshold failed; scoping it to plan/review made it a
    silent no-op on the other six stages."""
    _arm(tmp_path, level="auto_full")
    res = _boundary(tmp_path, current="execute", gate="blocked", capsys=capsys)
    assert res["proceed"] is False
    assert res["halt_kind"] == "judgment_gate"


def test_the_advanced_field_is_true_when_the_chain_moves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The positive half of the `advanced` field.

    Without it the ONLY assertion on this field is its False case, so replacing the predicate
    with the literal `False` passes the whole suite — an inversion or collapse would be
    invisible, which is the exact defect class every prior round of this layer shipped. The
    field's stated purpose ("both questions stay answerable") would then be silently false for
    every advancing run.
    """
    _arm(tmp_path, level="auto_full")
    res = _boundary(tmp_path, current="plan", gate="pending", capsys=capsys)
    assert res["proceed"] is True
    raw = autopilot_ledger.ledger_path(tmp_path).read_text(encoding="utf-8")
    answered = [
        json.loads(line)
        for line in raw.splitlines()
        if line.strip() and json.loads(line).get("event") == "gate_auto_answered"
    ]
    assert len(answered) == 1, answered
    assert answered[0]["advanced"] is True


def test_the_auto_answer_row_lands_even_when_the_chain_then_stops(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The row answers "was a human judgment cleared?", not "did the chain advance?".

    Two reviewers proposed opposite placements. Round 2: writing it inside the auto-answer
    branch also fires on runs that then stop at the land gate. Round 3: suppressing it there
    makes such a run byte-identical on the ledger to a `clear`-gate `auto_safe` run — the
    exact indistinguishability the row exists to remove. Round 3 wins, and the outcome
    becomes a field so both questions stay answerable.

    The default pipeline never reaches this shape; a customised one does.
    """
    _arm(
        tmp_path,
        level="auto_full",
        pipeline=[AtomicStage.PLAN, AtomicStage.REVIEW, AtomicStage.WRAPUP],
    )
    res = _boundary(tmp_path, current="review", gate="pending", capsys=capsys)
    assert res["halt_kind"] == "merge_gate", res
    assert res["judgment_auto_answered"] is True
    raw = autopilot_ledger.ledger_path(tmp_path).read_text(encoding="utf-8")
    answered = [
        json.loads(line)
        for line in raw.splitlines()
        if line.strip() and json.loads(line).get("event") == "gate_auto_answered"
    ]
    assert len(answered) == 1, answered
    assert answered[0]["advanced"] is False


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
