"""Phase 2 — the ledger that makes "is delegation actually firing?" answerable.

The question four dead months could not answer needed a denominator as much as a
numerator, so this ledger records **every** invocation, not just the failures. It also
records two different events under one schema:

* `kind: "brief"` — the gate was evaluated (`ok` or `degraded`). Written by
  `wrapup_brief.main()`, which is Phase 3 because its `slug` comes from the `--slug` that
  phase adds.
* `kind: "dispatch"` — a subagent actually replied. Written by `wrapup_receipt.main()`,
  which the rendered stage reaches only after a reply exists.

Keeping them apart is the whole point: a derivable brief that is never dispatched is
exactly the state being detected, so a signal built on brief rows alone would reinstall
the blind spot one level up.

`dispatch_verdict` reads a **recency window**, never the whole file. The ledger is
append-only, so "has a dispatch ever succeeded" goes green on the first success and stays
green through every later regression — the same blind spot, one layer further in.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker import delegation_ledger as dl


def _base(tmp_path: Path) -> Path:
    (tmp_path / ".claude" / "observability").mkdir(parents=True)
    return tmp_path


def _rows(base: Path) -> list[dict[str, object]]:
    text = dl.ledger_path(base).read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def test_a_row_lands_under_the_base_observability_dir(tmp_path: Path) -> None:
    base = _base(tmp_path)
    dl.append(base, stage="wrapup", slug="s", kind="brief", status="ok")
    assert dl.ledger_path(base) == base / ".claude" / "observability" / "delegation.jsonl"
    assert len(_rows(base)) == 1


def test_appending_never_replaces(tmp_path: Path) -> None:
    """The denominator only exists if rows accumulate. A writer that rewrites in place
    reports "1 invocation" forever, which is indistinguishable from a dead harness."""
    base = _base(tmp_path)
    dl.append(base, stage="wrapup", slug="s", kind="brief", status="degraded", reason="a")
    dl.append(base, stage="wrapup", slug="s", kind="brief", status="degraded", reason="b")
    rows = _rows(base)
    assert len(rows) == 2
    assert [r["reason"] for r in rows] == ["a", "b"]


def test_a_row_carries_stage_slug_kind_status_and_reason(tmp_path: Path) -> None:
    base = _base(tmp_path)
    dl.append(base, stage="wrapup", slug="my-task", kind="brief", status="degraded", reason="why")
    row = _rows(base)[0]
    assert row["stage"] == "wrapup"
    assert row["slug"] == "my-task"
    assert row["kind"] == "brief"
    assert row["status"] == "degraded"
    # Equality, not truthiness: a row that records the event but loses the diagnosis
    # leaves the ledger able to prove degradation happened and unable to say why — the
    # state this defect was already in.
    assert row["reason"] == "why"


def test_reading_a_missing_ledger_is_empty_not_an_error(tmp_path: Path) -> None:
    """Every harness is in this state the day the signal ships."""
    assert dl.read_rows(_base(tmp_path)) == []


def test_a_corrupt_line_does_not_take_the_whole_ledger_down(tmp_path: Path) -> None:
    """Operational churn in a gitignored directory; a truncated line must not make the
    health signal unevaluable, which would read as "no invocations" — the failing arm."""
    base = _base(tmp_path)
    dl.append(base, stage="wrapup", slug="s", kind="brief", status="ok")
    with dl.ledger_path(base).open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    dl.append(base, stage="wrapup", slug="s", kind="dispatch", status="dispatched")
    assert len(dl.read_rows(base)) == 2


# ------------------------------------------------------------------------ CLI


def _record(base: Path, *args: str) -> int:
    return dl.main(["record", "--root", str(base), "--stage", "wrapup", "--slug", "s", *args])


def test_cli_writes_a_row_for_each_legal_kind_status_pair(tmp_path: Path) -> None:
    base = _base(tmp_path)
    assert _record(base, "--kind", "dispatch", "--status", "unavailable") == 0
    assert _record(base, "--kind", "brief", "--status", "ok") == 0
    kinds = [(r["kind"], r["status"]) for r in _rows(base)]
    assert kinds == [("dispatch", "unavailable"), ("brief", "ok")]


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        ("brief", "dispatched"),
        ("brief", "unavailable"),
        ("dispatch", "ok"),
        ("dispatch", "degraded"),
    ],
)
def test_cli_rejects_a_status_that_belongs_to_the_other_kind(
    tmp_path: Path, kind: str, status: str
) -> None:
    """A brief row carrying a dispatch status reads as `degrading`, and a dispatch row
    carrying a brief status falls through to `no-dispatch` — both are silent
    mis-verdicts. Rejecting at the writer names the bug instead."""
    base = _base(tmp_path)
    with pytest.raises(SystemExit) as exc:
        _record(base, "--kind", kind, "--status", status)
    assert exc.value.code == 2
    assert not dl.ledger_path(base).exists()


def test_cli_rejects_a_status_no_kind_accepts(tmp_path: Path) -> None:
    base = _base(tmp_path)
    with pytest.raises(SystemExit) as exc:
        _record(base, "--kind", "dispatch", "--status", "dispatchd")
    assert exc.value.code == 2


# --------------------------------------------------------------- dispatch_verdict


def _brief_ok(n: int, start: int = 0) -> list[dict[str, object]]:
    return [
        {
            "ts": f"2026-07-20T10:{start + i:02d}:00Z",
            "stage": "wrapup",
            "slug": "s",
            "kind": "brief",
            "status": "ok",
        }
        for i in range(n)
    ]


def _dispatch(status: str, minute: int) -> dict[str, object]:
    return {
        "ts": f"2026-07-20T10:{minute:02d}:00Z",
        "stage": "wrapup",
        "slug": "s",
        "kind": "dispatch",
        "status": status,
    }


def test_verdict_no_rows_when_the_ledger_is_empty() -> None:
    assert dl.dispatch_verdict([], stage="wrapup") == "no-rows"


def test_verdict_no_dispatch_when_briefs_exist_but_nothing_dispatched() -> None:
    assert dl.dispatch_verdict(_brief_ok(3), stage="wrapup") == "no-dispatch"


def test_verdict_ok_when_a_real_dispatch_is_in_the_window() -> None:
    rows = _brief_ok(3) + [_dispatch("dispatched", 5)]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "ok"


def test_verdict_unavailable_only_when_the_ide_cannot_dispatch() -> None:
    """Cursor and Codex self-skip the subagent entirely. Those harnesses must not sit
    permanently red on an action their user cannot satisfy."""
    rows = _brief_ok(3) + [_dispatch("unavailable", 5)]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "unavailable-only"


def test_verdict_ok_when_a_dispatch_failed_to_reconcile_but_did_happen() -> None:
    """`mismatch` and `unparseable` mean the subagent WAS dispatched — the reconciliation
    is a different problem, and conflating them would blame the user for the wrong thing."""
    rows = _brief_ok(3) + [_dispatch("mismatch", 5)]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "ok"


def test_verdict_goes_red_again_after_a_dispatch_stops_happening() -> None:
    """The recency window, and the reason it exists.

    A successful dispatch long ago followed by more than a window's worth of brief-ok
    rows with none since is a regression. A lifetime-existence rule reports `ok` here
    forever — which is this defect's blind spot rebuilt one layer further in, and is what
    a cross-model reviewer caught after three in-house review rounds had not.
    """
    rows = _brief_ok(1) + [_dispatch("dispatched", 1)] + _brief_ok(dl.WINDOW_BRIEFS + 2, start=20)
    assert dl.dispatch_verdict(rows, stage="wrapup") == "no-dispatch"


def test_a_dispatch_inside_the_window_still_reads_ok_with_older_briefs_present() -> None:
    """The negative control for the test above: the window must not be so tight that a
    healthy harness flickers red just because it has history."""
    rows = _brief_ok(30) + [_dispatch("dispatched", 59)]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "ok"


def _brief(status: str, minute: int) -> dict[str, object]:
    return {
        "ts": f"2026-07-20T10:{minute:02d}:00Z",
        "stage": "wrapup",
        "slug": "s",
        "kind": "brief",
        "status": status,
    }


def test_degrading_briefs_do_not_freeze_the_verdict_at_ok() -> None:
    """The blind spot this signal exists to remove, rebuilt one condition deeper.

    Anchoring the window on `ok` briefs alone means a brief that starts degrading appends
    no new anchor, so the floor stays pinned to the last healthy era — whose dispatch rows
    are still inside it — and the verdict reads `ok` forever. And the regression it hides
    is exactly the four-month one: a brief that cannot be derived makes Step 0.5 skip the
    dispatch entirely.
    """
    rows = [_brief("ok", 0), _dispatch("dispatched", 1)] + [
        _brief("degraded", 20 + i) for i in range(dl.WINDOW_BRIEFS + 2)
    ]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "brief-degrading"


def test_brief_degrading_is_distinct_from_no_dispatch() -> None:
    """Different halves of the seam, so they must not collapse into one verdict.

    `no-dispatch` means the brief was fine and the subagent was not dispatched;
    `brief-degrading` means the dispatch was never reachable. Same symptom in the ledger,
    opposite remedies — merging them sends the user to the wrong half.
    """
    assert dl.dispatch_verdict([_brief("ok", 0)], stage="wrapup") == "no-dispatch"
    assert dl.dispatch_verdict([_brief("degraded", 0)], stage="wrapup") == "brief-degrading"
    # One healthy brief in the window is enough to mean "should have dispatched".
    assert (
        dl.dispatch_verdict([_brief("degraded", 0), _brief("ok", 1)], stage="wrapup")
        == "no-dispatch"
    )


def test_the_window_is_sliced_in_timestamp_order_not_file_order() -> None:
    """The slice, specifically — an earlier version of this test could not see it.

    That version wrote exactly WINDOW_BRIEFS briefs already in chronological file order, so
    the slice was the whole list and file order equalled timestamp order: it passed against
    the very `briefs[-N:]` + string-compare shape it was named for. A test that agrees with
    both implementations distinguishes neither.

    Here there are MORE briefs than the window and they are appended newest-first, so the
    two orders disagree about which ten are recent. By file position the last ten are the
    OLD ones, putting the floor before the dispatch and yielding `ok`; by timestamp the
    recent ten are the new ones, the floor lands after the dispatch, and the correct answer
    is `no-dispatch`.
    """
    rows: list[dict[str, object]] = [_brief("ok", 40 + i) for i in range(dl.WINDOW_BRIEFS)]
    rows.append(_dispatch("dispatched", 20))
    rows += [_brief("ok", i) for i in range(dl.WINDOW_BRIEFS)]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "no-dispatch"


def test_a_dispatch_with_an_unreadable_timestamp_cannot_hold_the_signal_green() -> None:
    """Fail-closed in the dispatch position: a corrupt row is not evidence of a dispatch."""
    rows: list[dict[str, object]] = [_brief("ok", m) for m in range(30, 30 + dl.WINDOW_BRIEFS)]
    rows.append(
        {"ts": "not-a-timestamp", "stage": "wrapup", "kind": "dispatch", "status": "dispatched"}
    )
    assert dl.dispatch_verdict(rows, stage="wrapup") == "no-dispatch"


def test_a_brief_with_an_unreadable_timestamp_cannot_open_the_window() -> None:
    """The other position, where sorting-oldest was fail-OPEN rather than fail-closed.

    An epoch-sorted brief survives the slice whenever the ledger holds few enough briefs,
    lands at index 0, and becomes the floor — admitting every dispatch row in the file and
    restoring the lifetime-existence semantics this function exists to remove. One corrupt
    row was enough. The fix excludes undatable briefs from the window instead of relying on
    where they sort.
    """
    rows: list[dict[str, object]] = [
        {"ts": "not-a-timestamp", "stage": "wrapup", "kind": "brief", "status": "ok"},
        _brief("ok", 30),
        _brief("ok", 31),
        _dispatch("dispatched", 1),  # ancient, and must stay outside the window
    ]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "no-dispatch"


def test_only_undatable_briefs_reads_as_no_rows() -> None:
    """Nothing placeable in time means no usable invocation record — a failing arm."""
    rows: list[dict[str, object]] = [
        {"ts": "??", "stage": "wrapup", "kind": "brief", "status": "ok"},
        {"stage": "wrapup", "kind": "brief", "status": "ok"},
    ]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "no-rows"


def test_mixed_utc_spellings_compare_chronologically() -> None:
    """`Z` and `+00:00` are the same instant; a string comparison ranks them apart.

    The earlier version of this test compared `…T11:00:00+00:00` against a floor of
    `…T10:00:00Z` — those differ at the HOUR digit, so a string compare gets the right
    answer by accident and the test passed against the unfixed code. The lexicographic
    defect only fires when the datetime text is otherwise identical, which is what this
    version pins: same instant as the floor, spelled the other way. `'+' < 'Z'`, so the
    string comparison places it strictly before the floor and drops the dispatch.
    """
    rows: list[dict[str, object]] = [_brief("ok", m) for m in range(0, dl.WINDOW_BRIEFS)]
    rows.append(
        {
            "ts": "2026-07-20T10:00:00+00:00",  # identical instant to the floor brief
            "stage": "wrapup",
            "kind": "dispatch",
            "status": "dispatched",
        }
    )
    assert dl.dispatch_verdict(rows, stage="wrapup") == "ok"


def test_rows_from_another_stage_do_not_drive_this_stage_verdict() -> None:
    """The ledger is shared; `verify` is delegatable and its rendered line carries no
    `--slug`, so its briefs degrade structurally. Unfiltered, a handful of verify runs
    would flip a correctly-dispatching wrapup to `brief-degrading` — and a verify dispatch
    row would vouch for a wrapup that never dispatched."""
    verify_noise: list[dict[str, object]] = [
        {**_brief("degraded", 40 + i), "stage": "verify"} for i in range(dl.WINDOW_BRIEFS + 5)
    ]
    healthy = _brief_ok(3) + [_dispatch("dispatched", 5)]
    assert dl.dispatch_verdict(healthy + verify_noise, stage="wrapup") == "ok"

    # And the mirror: another stage's dispatch must not vouch for this one.
    foreign_dispatch = [{**_dispatch("dispatched", 5), "stage": "verify"}]
    assert dl.dispatch_verdict(_brief_ok(3) + foreign_dispatch, stage="wrapup") == "no-dispatch"


def test_an_unknown_dispatch_status_does_not_read_as_a_pass() -> None:
    """`unavailable-only` is a PASS, so only explicit self-skip evidence may reach it.

    A typo, a corrupt row, or a status some future writer adds must not be reclassified as
    "this IDE has no subagent tool" — that is fail-OPEN on unevaluable input, the very
    shape this signal exists to eliminate. Two Round-1 voters flagged it independently.
    """
    assert (
        dl.dispatch_verdict(_brief_ok(3) + [_dispatch("dispatchd", 5)], stage="wrapup")
        == "no-dispatch"
    )
    # A mix must not be rescued by the `unavailable` member either.
    rows = _brief_ok(3) + [_dispatch("unavailable", 5), _dispatch("???", 6)]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "no-dispatch"


def test_a_row_too_large_for_pipe_buf_is_shrunk_rather_than_dropped(tmp_path: Path) -> None:
    """Measured in BYTES, because the cap is bytes and this project's default locale is not.

    A character-count cap passes for ASCII and silently drops the row for Korean text at
    three bytes per character — the row would hit the helper's PIPE_BUF guard, raise, and
    be swallowed, moving the verdict toward its failing arm with no evidence at all.
    """
    base = _base(tmp_path)
    dl.append(base, stage="wrapup", slug="s", kind="brief", status="degraded", reason="한" * 8000)
    rows = _rows(base)
    assert len(rows) == 1
    assert rows[0]["reason"].endswith("…[truncated]")
    raw = dl.ledger_path(base).read_bytes()
    assert len(raw) <= 4096, f"row is {len(raw)} bytes — above PIPE_BUF, so no longer atomic"


def test_the_window_is_bounded_by_brief_rows_not_by_row_count() -> None:
    """Dispatch rows must not push brief rows out of the window — otherwise a burst of
    dispatch rows could make the signal forget the briefs it is measured against."""
    rows = _brief_ok(dl.WINDOW_BRIEFS) + [_dispatch("dispatched", 30)]
    assert dl.dispatch_verdict(rows, stage="wrapup") == "ok"
