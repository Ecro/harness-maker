"""P4a / ADR-005 — a delegation `mismatch` row arrives diagnosable.

Both `mismatch` rows in this repo's ledger carry `reason: null`, and the null is
**structural**: the two `delegation_ledger.append()` call sites in `wrapup_receipt` simply
never passed one. So no diagnosis exists for either occurrence — which is why ADR-005 had
to split the repair in two, with the *fix* (P4b) gated on a reproduction that cannot be
attempted until a diagnosis exists at all. P4a is the diagnosis.

This file deliberately does NOT test a fix for the `--worktree`/`doc_root` mismatch.
`wrapup_receipt.py:265-268` shows that path was already repaired once for the same symptom
("review M-05"), and a second preemptive repair with no reproduction is
`fix-introduced-defect-passes-all-gates` (count:4) — the class this whole PLAN exists to
close.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker import delegation_ledger
from harness_maker.wrapup_receipt import Mismatch, format_mismatch_reason, main

_RECEIPT = {
    "schema_version": 1,
    "stage": "wrapup",
    "result": "ok",
    "wiki_slugs": [],
    "failure_slugs": [],
    "promotion_candidates": 0,
    "promoted_slugs": [],
    "documents_updated": [],
}


def _rows(base: Path) -> list[dict[str, object]]:
    path = delegation_ledger.ledger_path(base)
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


# ── the formatter ─────────────────────────────────────────────────────────────


def test_the_reason_names_every_mismatch_kind() -> None:
    reason = format_mismatch_reason(
        (Mismatch(kind="doc-missing", detail="X"), Mismatch(kind="stage-mismatch", detail="Y")),
        correlator="r.json",
    )
    assert "doc-missing" in reason
    assert "stage-mismatch" in reason
    assert "n=2" in reason


def test_the_reason_carries_an_invocation_correlator() -> None:
    """`stage` and `slug` are already columns and neither identifies one invocation.

    Two mismatches on the same slug in one session are otherwise identical rows.
    """
    reason = format_mismatch_reason((Mismatch(kind="k", detail="d"),), correlator="receipt-7.json")
    assert "run=receipt-7.json" in reason


def test_the_kind_set_precedes_the_free_text_detail() -> None:
    """`_fit` truncates from the RIGHT, so the groupable part must come first.

    If a long `detail` preceded the kinds, the truncation that keeps the row writable would
    remove exactly the field an aggregation needs — leaving a row that survives but says
    nothing.
    """
    reason = format_mismatch_reason(
        (Mismatch(kind="doc-missing", detail="z" * 200),), correlator="r.json"
    )
    assert reason.index("kinds=") < reason.index("z" * 200)


def test_kinds_are_deduplicated_and_ordered_deterministically() -> None:
    """Two rows describing the same failure must be groupable as the same failure."""
    a = format_mismatch_reason(
        (Mismatch(kind="b", detail="1"), Mismatch(kind="a", detail="2")), correlator="c"
    )
    b = format_mismatch_reason(
        (Mismatch(kind="a", detail="2"), Mismatch(kind="b", detail="1")), correlator="c"
    )
    assert a.split(" | ")[0] == b.split(" | ")[0]
    assert "kinds=a,b" in a


# ── truncation: visible, never dropped ────────────────────────────────────────


def test_an_oversized_reason_is_truncated_visibly_not_dropped(tmp_path: Path) -> None:
    """P4a exit criterion, second half.

    The failure to avoid is a row that exceeds PIPE_BUF and is therefore never written —
    the diagnosis would be lost precisely on the largest, most interesting mismatch.
    """
    reason = format_mismatch_reason(
        (Mismatch(kind="huge", detail="q" * 20_000),), correlator="r.json"
    )
    delegation_ledger.append(
        tmp_path, stage="wrapup", slug="s", kind="dispatch", status="mismatch", reason=reason
    )
    (row,) = _rows(tmp_path)
    assert row["reason"] is not None, "the row was dropped instead of truncated"
    assert "truncated" in str(row["reason"]), "truncation is not visible in the row"
    assert "kinds=huge" in str(row["reason"]), "truncation ate the groupable prefix"
    line = json.dumps(row, ensure_ascii=False)
    assert len(line.encode("utf-8")) + 1 <= 4096


# ── end-to-end through the CLI ────────────────────────────────────────────────


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_a_real_mismatch_writes_a_row_with_a_non_null_reason(tmp_path: Path) -> None:
    """The regression this phase exists to prevent: `reason: null` on a mismatch row."""
    receipt = tmp_path / "receipt.json"
    _write(receipt, {**_RECEIPT, "stage": "verify"})  # expected wrapup → stage mismatch
    rc = main(
        ["--root", str(tmp_path), "--receipt-file", str(receipt), "--stage", "wrapup"],
    )
    assert rc == 1
    (row,) = _rows(tmp_path)
    assert row["status"] == "mismatch"
    assert row["reason"] is not None, "the structural null P4a exists to remove is still here"
    assert "kinds=" in str(row["reason"])
    assert "run=receipt.json" in str(row["reason"])


def test_a_clean_reconciliation_leaves_reason_null(tmp_path: Path) -> None:
    """Scope guard. `reason` is a diagnosis, not a description of success.

    Filling it on the happy path would make "has a reason" useless as a filter for the rows
    that need attention.
    """
    receipt = tmp_path / "receipt.json"
    _write(receipt, dict(_RECEIPT))
    main(["--root", str(tmp_path), "--receipt-file", str(receipt), "--stage", "wrapup"])
    rows = _rows(tmp_path)
    assert rows, "no row was written at all"
    assert rows[-1]["reason"] is None


@pytest.mark.parametrize(
    ("content", "expected_kind"),
    [
        ("this is prose, not a receipt", "receipt-unparseable"),
        ('{"schema_version": 99}', "receipt-unparseable"),
    ],
)
def test_unparseable_replies_are_diagnosable_too(
    tmp_path: Path, content: str, expected_kind: str
) -> None:
    """Beyond the letter of the exit criterion, and for the same reason.

    An `unparseable` row with no diagnosis cannot distinguish "the file was unreadable"
    from "the agent replied in prose" — and those have different remedies.
    """
    receipt = tmp_path / "receipt.json"
    receipt.write_text(content, encoding="utf-8")
    assert main(["--root", str(tmp_path), "--receipt-file", str(receipt), "--stage", "wrapup"]) == 2
    (row,) = _rows(tmp_path)
    assert row["status"] == "unparseable"
    assert expected_kind in str(row["reason"])


def test_a_missing_receipt_file_is_diagnosable(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert main(["--root", str(tmp_path), "--receipt-file", str(missing), "--stage", "wrapup"]) == 2
    (row,) = _rows(tmp_path)
    assert "receipt-unreadable" in str(row["reason"])
