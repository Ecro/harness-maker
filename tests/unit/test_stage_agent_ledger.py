"""P3 exit criterion 1 — the `stage-agents.jsonl` writer, including the paths that fail.

`plan-validator` (34 dispatches) and Phase A.5 `test-reviewer` (42 dispatches) have zero
ledger rows today, so stage 2's decision on both rests on data that does not exist. The
rows this module writes ARE that data, which makes the failure paths as load-bearing as the
happy one: a launch failure that writes nothing is indistinguishable from a dispatch that
approved, and that is the shape that would let stage 2 delete a gate for the wrong reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker.stage_agent_ledger import (
    DISPATCH_FAILED,
    DISPATCH_SKIPPED,
    LEDGER_FILENAME,
    StageAgentRow,
    check_run_coherence,
    emit,
    ledger_path,
    persist_payload,
    row_from_dict,
)

_BASE = {
    "run_id": "plan-workflow-loop-efficiency-1",
    "agent": "plan-validator",
    "stage": "plan",
    "slug": "workflow-loop-efficiency",
    "pass_or_attempt": 1,
    "verdict": "APPROVED",
    "terminal": True,
}


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


# ── the two aggregations' inputs ──────────────────────────────────────────────


def test_a_two_pass_validator_writes_two_rows_sharing_a_run_id(tmp_path: Path) -> None:
    """The pre-registered aggregation compares pass 2 against pass 1 of the SAME run_id.

    Two rows with different run_ids cannot be paired, so the whole "does the second pass
    change the verdict" question would be unanswerable while the file still looked full.
    """
    emit(
        row_from_dict({**_BASE, "verdict": "MAJOR_REVISION", "terminal": False}), base_root=tmp_path
    )
    emit(row_from_dict({**_BASE, "pass_or_attempt": 2, "verdict": "APPROVED"}), base_root=tmp_path)

    rows = _rows(ledger_path(tmp_path))
    assert len(rows) == 2
    assert {r["run_id"] for r in rows} == {_BASE["run_id"]}, "the passes are not pairable"
    assert [r["pass_or_attempt"] for r in rows] == [1, 2]
    assert [r["terminal"] for r in rows] == [False, True]


def test_a_retried_phase_a5_writes_one_row_per_attempt(tmp_path: Path) -> None:
    """P(FAIL) over Phase A.5 rows needs the FAILing attempts, not just the final PASS."""
    a5 = {**_BASE, "agent": "test-reviewer", "stage": "execute", "run_id": "exec-1"}
    emit(row_from_dict({**a5, "verdict": "FAIL", "terminal": False}), base_root=tmp_path)
    emit(row_from_dict({**a5, "pass_or_attempt": 2, "verdict": "PASS"}), base_root=tmp_path)

    rows = _rows(ledger_path(tmp_path))
    assert [r["verdict"] for r in rows] == ["FAIL", "PASS"]


def test_both_agents_coexist_and_stay_separable(tmp_path: Path) -> None:
    """One file, two row kinds — the `second-opinion.jsonl` conflation must not recur.

    There, two kinds shared `status: "invoked"` and a discriminator had to be found after
    the fact. Here `agent` and `stage` are fields from the first row.
    """
    emit(row_from_dict(dict(_BASE)), base_root=tmp_path)
    emit(
        row_from_dict({**_BASE, "agent": "test-reviewer", "stage": "execute", "verdict": "PASS"}),
        base_root=tmp_path,
    )
    rows = _rows(ledger_path(tmp_path))
    assert {r["agent"] for r in rows} == {"plan-validator", "test-reviewer"}
    assert len([r for r in rows if r["agent"] == "plan-validator"]) == 1


# ── the failure paths ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("sentinel", [DISPATCH_SKIPPED, DISPATCH_FAILED])
def test_a_launch_failure_is_a_row(tmp_path: Path, sentinel: str) -> None:
    emit(
        row_from_dict({**_BASE, "verdict": sentinel, "reason": "model unavailable"}),
        base_root=tmp_path,
    )
    (row,) = _rows(ledger_path(tmp_path))
    assert row["verdict"] == sentinel
    assert row["reason"] == "model unavailable"


@pytest.mark.parametrize("sentinel", [DISPATCH_SKIPPED, DISPATCH_FAILED])
def test_a_sentinel_row_without_a_reason_is_rejected(sentinel: str) -> None:
    """`delegation_ledger`'s two mismatch rows both carry a structural `reason: null`.

    No diagnosis exists for either, which is why P4a had to be created. Rejecting the
    undiagnosable row at the schema is what stops this ledger from needing its own P4a.
    """
    with pytest.raises(ValidationError):
        row_from_dict({**_BASE, "verdict": sentinel})


@pytest.mark.parametrize("sentinel", [DISPATCH_SKIPPED, DISPATCH_FAILED])
def test_a_sentinel_row_cannot_be_non_terminal(sentinel: str) -> None:
    """A dispatch that produced no outcome cannot be "attempt 1 of a continuing sequence"."""
    with pytest.raises(ValidationError):
        row_from_dict({**_BASE, "verdict": sentinel, "reason": "x", "terminal": False})


def test_the_sentinels_cannot_collide_with_an_agent_verdict() -> None:
    """`test-reviewer` emits `FAIL`; a sentinel spelled `failed` differs only by case.

    P(FAIL) would then silently count launch failures as test-quality failures — inflating
    exactly the ratio that decides whether the A.5 gate survives.
    """
    for sentinel in (DISPATCH_SKIPPED, DISPATCH_FAILED):
        assert sentinel.lower() not in {"fail", "failed", "pass", "skip", "skipped"}
        assert "-" in sentinel


# ── nullability, mirroring P1's ADR-002 ───────────────────────────────────────


def test_unmeasured_duration_is_null_not_zero(tmp_path: Path) -> None:
    """`0` reads as "measured, instantly". These rows are append-only."""
    emit(row_from_dict(dict(_BASE)), base_root=tmp_path)
    emit(row_from_dict({**_BASE, "duration_ms": 0, "barrier_index": 0}), base_root=tmp_path)
    absent, measured = _rows(ledger_path(tmp_path))
    assert absent["duration_ms"] is None
    assert absent["barrier_index"] is None
    assert measured["duration_ms"] == 0
    assert measured["barrier_index"] == 0


def test_negative_counters_are_rejected() -> None:
    with pytest.raises(ValidationError):
        row_from_dict({**_BASE, "duration_ms": -1})


# ── placement + atomicity ─────────────────────────────────────────────────────


def test_rows_land_under_the_given_base_root(tmp_path: Path) -> None:
    """P3 exit 4. `codex_ledger.main()` used `Path.cwd()` and lost every worktree row."""
    path = emit(row_from_dict(dict(_BASE)), base_root=tmp_path)
    assert path == tmp_path / ".claude" / "observability" / LEDGER_FILENAME
    assert path.is_file()


def test_an_oversized_reason_is_refused_at_the_schema(tmp_path: Path) -> None:
    """`max_length` bounds the FIELD. It does not bound the encoded row — see below."""
    with pytest.raises(ValidationError):
        row_from_dict({**_BASE, "reason": "x" * 5000})


def test_a_schema_valid_multibyte_row_is_truncated_rather_than_lost(tmp_path: Path) -> None:
    """The property `max_length` does NOT give you, and the comment once claimed it did.

    The per-field limits sum to ~1052 characters; `ensure_ascii=False` means 4 bytes per
    character is reachable, so a fully schema-valid row can encode past PIPE_BUF. This
    project's default locale is non-ASCII, so it is a real row. Before the `_fit` shrink it
    raised `ValueError` at write time from a code path that caught only `ValidationError` —
    losing exactly the row the ledger exists to capture.
    """
    # Every string field at its max_length, filled with 4-byte characters. Measured, not
    # assumed: this encodes to 4401 bytes — 305 past the PIPE_BUF ceiling.
    wide = "\U0001f600"
    row = row_from_dict(
        {
            **_BASE,
            "ts": wide * 64,
            "run_id": wide * 128,
            "agent": wide * 64,
            "stage": wide * 32,
            "slug": wide * 200,
            "verdict": wide * 64,
            "reason": wide * 500,
        }
    )
    path = emit(row, base_root=tmp_path)
    (written,) = _rows(path)
    assert "truncated" in str(written["reason"]), "the row was not visibly truncated"
    assert len(json.dumps(written, ensure_ascii=False).encode("utf-8")) + 1 <= 4096
    # Truncation eats `reason` from the right and nothing else — the other fields survive
    # intact, so an aggregation can still group the row it was written to preserve.
    assert written["agent"] == wide * 64
    assert written["verdict"] == wide * 64


def test_the_row_schema_matches_the_pre_registered_field_set() -> None:
    """ADR-004 names the schema. A field added without updating the ADR is drift."""
    assert set(StageAgentRow.model_fields) == {
        "ts",
        "run_id",
        "agent",
        "stage",
        "slug",
        "pass_or_attempt",
        "verdict",
        "terminal",
        "reason",
        "duration_ms",
        "barrier_index",
    }


# ── payload persistence (ADR-006 part 2) ──────────────────────────────────────


def test_a_payload_is_persisted_verbatim(tmp_path: Path) -> None:
    """Verbatim on purpose: a schema guessed from today's reviewers would reject tomorrow's."""
    src = tmp_path / "findings.json"
    src.write_text('[{"severity": "P0", "file": "a.py", "summary": "x"}]', encoding="utf-8")
    dest = persist_payload(
        src, base_root=tmp_path, slug="s", run_id="r1", round_n=1, reviewer="code-reviewer"
    )
    assert dest.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")
    assert dest.parent == tmp_path / ".claude" / "observability" / "review-payloads" / "s"


def test_payloads_from_different_reviewers_and_rounds_do_not_overwrite(tmp_path: Path) -> None:
    """One file per (run, round, reviewer) — a replay corpus of one row is not a corpus."""
    src = tmp_path / "f.json"
    src.write_text("[]", encoding="utf-8")
    made = {
        persist_payload(src, base_root=tmp_path, slug="s", run_id="r1", round_n=n, reviewer=who)
        for n in (1, 2)
        for who in ("code-reviewer", "security-reviewer")
    }
    assert len(made) == 4


def test_a_payload_larger_than_pipe_buf_is_accepted(tmp_path: Path) -> None:
    """Payloads routinely exceed 4096 bytes — that is why this is not the JSONL path."""
    src = tmp_path / "big.json"
    src.write_text("[" + ",".join('{"s":"P2"}' for _ in range(2000)) + "]", encoding="utf-8")
    assert len(src.read_text(encoding="utf-8")) > 4096
    dest = persist_payload(src, base_root=tmp_path, slug="s", run_id="r", round_n=1, reviewer="c")
    assert dest.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")


def test_a_reviewer_name_cannot_escape_the_payload_directory(tmp_path: Path) -> None:
    """The reviewer name reaches a filename; a traversal there would write outside the store."""
    src = tmp_path / "f.json"
    src.write_text("[]", encoding="utf-8")
    dest = persist_payload(
        src, base_root=tmp_path, slug="s", run_id="r", round_n=1, reviewer="../../etc/passwd"
    )
    store = (tmp_path / ".claude" / "observability" / "review-payloads").resolve()
    assert dest.resolve().is_relative_to(store)


# ── AC-003 / AC-004 bindings ──────────────────────────────────────────────────
#
# Both predicates are `<ledger rows> == <dispatch count>`. The dispatch count CANNOT come
# from the ledger — that is R3, the self-referential predicate that yields a zero-row
# denominator (0 == 0 holds against a completely unwired harness). Here the count is the
# number of dispatches the test itself performs, so the property under test is the real one:
# one row per dispatch, no loss and no duplication, across the multi-pass and retry paths
# that are exactly where a per-dispatch writer goes wrong.
#
# The *wiring* half — that the rendered stages actually call this — is asserted separately
# and from an independent source in `tests/structural/test_stage_agent_ledger_wiring.py`.


def _dispatch_and_record(base: Path, *, agent: str, stage: str, verdicts: list[str]) -> int:
    """Simulate N dispatches, recording each. Returns N — the independent count."""
    for i, verdict in enumerate(verdicts, start=1):
        emit(
            row_from_dict(
                {
                    **_BASE,
                    "agent": agent,
                    "stage": stage,
                    "run_id": f"{stage}-run",
                    "pass_or_attempt": i,
                    "verdict": verdict,
                    "terminal": i == len(verdicts),
                }
            ),
            base_root=base,
        )
    return len(verdicts)


def validator_ledger_rows(base: Path) -> int:
    return len([r for r in _rows(ledger_path(base)) if r["agent"] == "plan-validator"])


def phase_a5_ledger_rows(base: Path) -> int:
    return len([r for r in _rows(ledger_path(base)) if r["agent"] == "test-reviewer"])


def test_ac_003_validator_ledger_row_per_pass(tmp_path: Path) -> None:
    """AC-003 — including the two-pass MAJOR_REVISION path, which is the whole question."""
    count = _dispatch_and_record(
        tmp_path, agent="plan-validator", stage="plan", verdicts=["MAJOR_REVISION", "APPROVED"]
    )
    assert validator_ledger_rows(tmp_path) == count


def test_ac_004_phase_a5_ledger_row_per_attempt(tmp_path: Path) -> None:
    """AC-004 — including the retry path, where P(FAIL) is actually decided."""
    count = _dispatch_and_record(
        tmp_path, agent="test-reviewer", stage="execute", verdicts=["FAIL", "FAIL", "PASS"]
    )
    assert phase_a5_ledger_rows(tmp_path) == count


# ── F-B: cross-row coherence ──────────────────────────────────────────────────
#
# Every defect here is a relationship BETWEEN rows, which `StageAgentRow`'s validator
# structurally cannot see — it is handed one row. Closing this at the schema is impossible,
# so it is closed where rows are read back, and these tests pin that it discriminates.


def test_a_run_with_two_terminal_rows_is_reported(tmp_path: Path) -> None:
    """The real defect: `msms-20260807-1` shipped passes 1/2/3 with terminal on 2 AND 3.

    Any aggregation keyed on "the row that ended the run" then picks one arbitrarily and
    reports a figure nobody can reproduce.
    """
    rows = [
        {**_BASE, "run_id": "r", "pass_or_attempt": 1, "terminal": False},
        {**_BASE, "run_id": "r", "pass_or_attempt": 2, "terminal": True},
        {**_BASE, "run_id": "r", "pass_or_attempt": 3, "terminal": True},
    ]
    (c,) = check_run_coherence(rows)
    assert not c.ok
    assert c.terminal_count == 2
    assert any("terminal" in p for p in c.problems)
    assert c.passes == (1, 2, 3)


def test_a_well_formed_run_is_clean() -> None:
    """The discriminating half — a checker that flags everything gates nothing."""
    rows = [
        {**_BASE, "run_id": "r", "pass_or_attempt": 1, "terminal": False},
        {**_BASE, "run_id": "r", "pass_or_attempt": 2, "terminal": True},
    ]
    (c,) = check_run_coherence(rows)
    assert c.ok, c.problems


def test_a_run_with_no_terminal_row_is_reported() -> None:
    """An unfinished run is not a finished one; silence must not read as completion."""
    (c,) = check_run_coherence([{**_BASE, "run_id": "r", "pass_or_attempt": 1, "terminal": False}])
    assert any("no terminal row" in p for p in c.problems)


def test_gaps_and_duplicates_in_the_pass_sequence_are_reported() -> None:
    gap = check_run_coherence(
        [
            {**_BASE, "run_id": "g", "pass_or_attempt": 1, "terminal": False},
            {**_BASE, "run_id": "g", "pass_or_attempt": 3, "terminal": True},
        ]
    )[0]
    assert any("not 1..N" in p for p in gap.problems)

    dup = check_run_coherence(
        [
            {**_BASE, "run_id": "d", "pass_or_attempt": 1, "terminal": False},
            {**_BASE, "run_id": "d", "pass_or_attempt": 1, "terminal": True},
        ]
    )[0]
    assert any("duplicate" in p for p in dup.problems)


def test_a_sentinel_row_does_not_break_the_pass_sequence() -> None:
    """A dispatch that never ran has no place in the sequence, but it does end the run.

    Counting it as a pass would report a spurious gap on every run whose validator failed
    to launch — turning the coherence check into noise exactly when it matters.
    """
    rows = [
        {**_BASE, "run_id": "s", "pass_or_attempt": 1, "terminal": False},
        {
            **_BASE,
            "run_id": "s",
            "pass_or_attempt": 2,
            "verdict": DISPATCH_FAILED,
            "reason": "launch error",
            "terminal": True,
        },
    ]
    (c,) = check_run_coherence(rows)
    assert c.passes == (1,)
    assert c.terminal_count == 1
    assert c.ok, c.problems


def test_runs_are_grouped_by_agent_as_well_as_run_id() -> None:
    """`agent` is a discriminator, not decoration — two agents can share a run_id."""
    rows = [
        {**_BASE, "agent": "plan-validator", "run_id": "x", "terminal": True},
        {**_BASE, "agent": "test-reviewer", "stage": "execute", "run_id": "x", "terminal": True},
    ]
    assert len(check_run_coherence(rows)) == 2
