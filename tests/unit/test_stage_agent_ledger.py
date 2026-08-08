"""P3 exit criterion 1 — the `stage-agents.jsonl` writer, including the paths that fail.

`plan-validator` (34 dispatches) and Phase A.5 `test-reviewer` (42 dispatches) have zero
ledger rows today, so stage 2's decision on both rests on data that does not exist. The
rows this module writes ARE that data, which makes the failure paths as load-bearing as the
happy one: a launch failure that writes nothing is indistinguishable from a dispatch that
approved, and that is the shape that would let stage 2 delete a gate for the wrong reason.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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
    main,
    persist_payload,
    reconcile_counts,
    row_from_dict,
    sidechain_turn_groups,
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


@dataclass(frozen=True)
class _FakeTurn:
    """Only the two attributes `sidechain_turn_groups` reads — no transcript fixture needed."""

    scope: str
    ts: int


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
def test_a_sentinel_row_may_be_non_terminal_because_retries_exist(sentinel: str) -> None:
    """The inverse of what this test asserted until review.

    It required every sentinel to be terminal, reasoning that a dispatch producing no
    outcome cannot be a continuing attempt. But a launch failure is exactly what the plan
    stage tells the model to RETRY, so the mandated shape is `pass 1 failed` then `pass 2
    succeeds` — and forcing the first row terminal manufactured a two-terminal run that
    `check_run_coherence` then reported. The schema was creating the incoherence.
    """
    row = row_from_dict({**_BASE, "verdict": sentinel, "reason": "launch error", "terminal": False})
    assert row.terminal is False


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


def test_an_unfinished_run_is_surfaced_without_being_called_a_defect() -> None:
    """Superseded semantics, kept as the explicit record of the change.

    This asserted that a missing terminal row is a `problem`. It is not: an in-flight run
    legitimately has none, and with many concurrent sessions that made `coherence` exit 1
    almost always. It is now `incomplete` — printed, never silent, but not a defect.
    Silence would still be wrong; calling it a defect was just a different wrong.
    """
    (c,) = check_run_coherence([{**_BASE, "run_id": "r", "pass_or_attempt": 1, "terminal": False}])
    assert c.incomplete is True
    assert not any("no terminal row" in p for p in c.problems)
    assert c.ok


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


def test_the_mandated_retry_after_a_launch_failure_is_clean() -> None:
    """The shape `plan.md.j2` MANDATES, and the one the checker used to flag twice.

    `[pass 1 dispatch-failed (non-terminal), pass 2 real (terminal)]` — sentinels occupy an
    attempt number, so the sequence is (1, 2) and exactly one row ends the run. The earlier
    version excluded sentinels from `passes`, producing the gap `(2,)`, AND counted the
    schema-forced terminal, producing two — two false defects on the only dispatch shape the
    same commit's guidance tells the model to produce.
    """
    rows = [
        {
            **_BASE,
            "run_id": "retry",
            "pass_or_attempt": 1,
            "verdict": DISPATCH_FAILED,
            "reason": "launch error",
            "terminal": False,
        },
        {**_BASE, "run_id": "retry", "pass_or_attempt": 2, "verdict": "APPROVED", "terminal": True},
    ]
    (c,) = check_run_coherence(rows)
    assert c.passes == (1, 2)
    assert c.terminal_count == 1
    assert c.ok, c.problems


def test_runs_are_separated_by_stage_and_slug_not_run_id_alone() -> None:
    """`run_id` is model-chosen and globally unique only by convention.

    Grouping on `(agent, run_id)` merged independent runs that happened to reuse an id,
    fabricating "duplicate pass numbers" and "multiple terminal rows" — a checker inventing
    the defects it exists to find.
    """
    shared = {"agent": "plan-validator", "run_id": "same-id", "pass_or_attempt": 1}
    rows = [
        {**_BASE, **shared, "stage": "plan", "slug": "task-a", "terminal": True},
        {**_BASE, **shared, "stage": "plan", "slug": "task-b", "terminal": True},
    ]
    results = check_run_coherence(rows)
    assert len(results) == 2, "two independent runs were merged into one"
    assert all(c.ok for c in results), [c.problems for c in results]


@pytest.mark.parametrize(
    "bad_value",
    [None, "2x", [], {}, True],
)
def test_a_malformed_pass_number_is_reported_not_raised(bad_value: object) -> None:
    """Assert the problem is REPORTED, not merely that nothing raised.

    The first version asserted `results` was truthy — which holds for ANY non-empty input,
    because one `RunCoherence` is emitted per key regardless. It would have stayed green if
    the defensive coercion were deleted outright, so the newly-added guard had no coverage.
    `True` is in the list because `isinstance(True, int)` and an unguarded `int()` accepts it.
    """
    row = {
        "agent": "a",
        "stage": "s",
        "slug": "x",
        "run_id": "r",
        "terminal": True,
        "pass_or_attempt": bad_value,
    }
    (c,) = check_run_coherence([row])
    assert any("unreadable" in p for p in c.problems), c.problems


def test_a_missing_pass_number_is_reported_not_raised() -> None:
    """The key was subscripted, not `.get`, so its absence raised KeyError and voided the scan."""
    (c,) = check_run_coherence([{"agent": "a", "stage": "s", "slug": "x", "run_id": "r"}])
    assert any("unreadable" in p for p in c.problems), c.problems


def test_one_bad_row_does_not_hide_a_real_defect_in_another_run() -> None:
    """The actual consequence of raising: every OTHER run goes unreported.

    Rows come from a shared file that concurrent sessions append to, so a single torn line
    used to convert the checker from "reports problems" to "reports nothing".
    """
    rows = [
        {"agent": "a", "stage": "s", "slug": "x", "run_id": "bad", "pass_or_attempt": None},
        {**_BASE, "run_id": "real", "pass_or_attempt": 1, "terminal": True},
        {**_BASE, "run_id": "real", "pass_or_attempt": 2, "terminal": True},
    ]
    by_run = {c.run_id: c for c in check_run_coherence(rows)}
    assert any("terminal" in p for p in by_run["real"].problems), "the real defect was hidden"


def test_an_in_flight_run_is_not_a_defect() -> None:
    """A run with no terminal row yet is unfinished, not incoherent.

    This repo runs many sessions at once; failing on a peer's mid-run would make `coherence`
    exit 1 almost always, and a gate that always fires is a gate that gets ignored.
    """
    (c,) = check_run_coherence(
        [{**_BASE, "run_id": "live", "pass_or_attempt": 1, "terminal": False}]
    )
    assert c.incomplete is True
    assert c.ok, c.problems


def test_a_terminal_row_before_the_last_pass_is_reported() -> None:
    """A run that continues past its own recorded end is not coherent."""
    rows = [
        {**_BASE, "run_id": "t", "pass_or_attempt": 1, "terminal": True},
        {**_BASE, "run_id": "t", "pass_or_attempt": 2, "terminal": False},
    ]
    (c,) = check_run_coherence(rows)
    assert any("continues to" in p for p in c.problems), c.problems


def test_a_string_false_does_not_count_as_terminal() -> None:
    """`terminal` is compared to True, not tested for truthiness — "false" is truthy."""
    (c,) = check_run_coherence(
        [{**_BASE, "run_id": "s", "pass_or_attempt": 1, "terminal": "false"}]
    )
    assert c.terminal_count == 0


def test_a_sentinel_row_counts_as_an_attempt() -> None:
    """The reasoning here was backwards until review.

    It said counting a sentinel as a pass "would report a spurious gap on every run whose
    validator failed to launch". The opposite: a launch failure OCCUPIES attempt 1, so
    excluding it is what creates the gap — the retry lands at pass 2 and the sequence reads
    `(2,)`. Sentinels are attempts; only their outcome is missing.
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
    assert c.passes == (1, 2), "the sentinel was dropped from the sequence, creating a gap"
    assert c.terminal_count == 1
    assert c.ok, c.problems


def test_runs_are_grouped_by_agent_as_well_as_run_id() -> None:
    """`agent` is a discriminator, not decoration — two agents can share a run_id."""
    rows = [
        {**_BASE, "agent": "plan-validator", "run_id": "x", "terminal": True},
        {**_BASE, "agent": "test-reviewer", "stage": "execute", "run_id": "x", "terminal": True},
    ]
    assert len(check_run_coherence(rows)) == 2


# ── reconcile: is the ledger corroborated by the transcript? (PLAN A2) ────────


def test_reconcile_agrees_when_the_ledger_is_a_subset_of_observed_dispatches() -> None:
    """strange_chess's shipped shape: 37 recorded against 616 observed runs.

    The ledger records only `plan-validator` / `test-reviewer` / `code-reviewer`, never every
    subagent, so `ledger <= groups` is the EXPECTED relation — not evidence of loss. The
    39/45 pair an earlier draft cited here was retracted (see the wiki entry); the numbers
    below are illustrative of the SHAPE and are not claimed as an observation.
    """
    result = reconcile_counts(
        [{**_BASE, "verdict": "MAJOR_REVISION"} for _ in range(39)], subagent_turn_groups=45
    )

    assert result.ledger_dispatches == 39
    assert result.turn_groups == 45
    assert result.agrees is True
    assert result.reason is None


def test_reconcile_flags_subagents_that_ran_while_the_ledger_recorded_nothing() -> None:
    """spoton's shipped shape: zero ledger rows against a live corpus (1036 runs).

    This is the only disagreement the reconciler surfaces on its own — every other
    `ledger < groups` case is expected. **The flag is not a defect claim:** spoton's zero has
    a recorded, benign cause (its harness re-rendered after its last gated stage ran, so the
    emit did not exist yet), and the disagreement will persist until that project next runs
    one. That is why the CLI exits 2 rather than 1 and must never gate.

    The literal below is illustrative of the SHAPE, not an observation — 57 was the retracted
    hand-rolled figure; the shipped run count is 1036. Only `dispatches == 0` drives this branch.
    """
    result = reconcile_counts([], subagent_turn_groups=57)

    assert result.ledger_dispatches == 0
    assert result.agrees is False
    assert result.reason is not None
    assert "57" in result.reason


def test_reconcile_flags_recording_more_dispatches_than_were_observed() -> None:
    """Recording more than ran is impossible on a healthy corpus — loss or fabrication."""
    result = reconcile_counts([dict(_BASE) for _ in range(5)], subagent_turn_groups=2)

    # Assert the structural fields, not only the message: "2" matches inside "12", "25" and
    # any timestamp, so a substring check alone carries weight it cannot bear.
    assert result.ledger_dispatches == 5
    assert result.turn_groups == 2
    assert result.agrees is False
    assert result.reason is not None


def test_reconcile_excludes_dispatch_sentinels_from_the_dispatch_count() -> None:
    """A dispatch that never ran cannot have left a turn-group, so counting it inverts the test.

    With sentinels counted, a run of launch failures would read as "ledger > observed" and be
    reported as loss — the opposite of what those rows mean.
    """
    rows = [
        dict(_BASE),
        {**_BASE, "verdict": DISPATCH_FAILED, "reason": "launch error"},
        {**_BASE, "verdict": DISPATCH_SKIPPED, "reason": "gate off"},
    ]

    result = reconcile_counts(rows, subagent_turn_groups=1)

    assert result.ledger_dispatches == 1
    assert result.agrees is True


def test_reconcile_agrees_on_an_empty_corpus() -> None:
    """No ledger rows AND no subagent turns is a project that has not run a gated stage."""
    assert reconcile_counts([], subagent_turn_groups=0).agrees is True


def test_turn_groups_counts_contiguous_sidechain_runs_not_turns() -> None:
    """The denominator has to be DERIVED, and the derivation is where a fabricated number hides.

    A dispatch is one contiguous run of sidechain turns, so the two candidate keys must be
    told apart: adjacent sidechain turns are ONE dispatch, and two runs separated by a
    main-chain turn are TWO. Grouping by `(session_id, stage)` instead — which is how the
    first draft's figures were computed, by hand, in a shell one-liner — silently merges every
    dispatch of one agent in one session into a single group.
    """
    scopes = ["main", "subagent", "subagent", "main", "subagent", "main"]
    turns = [_FakeTurn(scope=s, ts=i) for i, s in enumerate(scopes)]

    assert sidechain_turn_groups(turns) == 2


def test_turn_groups_is_zero_without_sidechain_turns() -> None:
    assert sidechain_turn_groups([_FakeTurn(scope="main", ts=i) for i in range(3)]) == 0


def test_turn_groups_orders_by_timestamp_before_grouping() -> None:
    """Transcript order is not guaranteed; two runs must not merge because input was shuffled."""
    turns = [
        _FakeTurn(scope="subagent", ts=0),
        _FakeTurn(scope="subagent", ts=4),
        _FakeTurn(scope="main", ts=2),
    ]

    assert sidechain_turn_groups(turns) == 2


def test_turn_groups_merges_concurrent_dispatches_into_one_run() -> None:
    """The undercount is pinned, not discovered later: N parallel subagents read as ONE run.

    Reviewers are dispatched as a batch in a single message and the main loop emits no turn
    until the batch returns, so their sidechain turns are contiguous in timestamp order. This
    is the direction the docstring's "NOT a dispatch count" warning is about, and `code-reviewer`
    — one of the three agents the ledger records — is dispatched exactly this way.
    """
    turns = [_FakeTurn(scope="subagent", ts=i) for i in range(6)]

    assert sidechain_turn_groups(turns) == 1


# ── the reconcile CLI branch itself (round-3 review: it shipped untested) ─────


def _fake_ingestion(scopes: list[str]) -> object:
    class _Diag:
        dirs_scanned = 1

    class _Ing:
        turns = [_FakeTurn(scope=s, ts=i) for i, s in enumerate(scopes)]
        diagnostics = _Diag()

    return _Ing()


def test_reconcile_cli_rejects_a_nonexistent_root(capsys: pytest.CaptureFixture[str]) -> None:
    """A typo'd root must not print a confident `agrees=yes` — that is the silent-zero shape."""
    assert main(["reconcile", "--root", "/definitely/not/here"]) == 1
    assert "no such directory" in capsys.readouterr().err


def test_reconcile_cli_exits_2_for_a_disagreement_not_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`1` is reserved for tool failure, so an operator can tell the two apart.

    spoton's disagreement is expected and permanent; conflating it with a broken command is
    what makes a diagnostic un-runnable in an `&&` chain.
    """
    monkeypatch.setattr(
        "harness_maker.economics_source.load_turns",
        lambda *a, **k: _fake_ingestion(["main", "subagent"]),
    )
    monkeypatch.setattr("harness_maker.stage_agent_ledger.resolve_base_root", lambda p: tmp_path)

    assert main(["reconcile", "--root", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert "agrees=NO" in out
    assert "dirs_scanned=1" in out


def test_reconcile_cli_counts_and_reports_torn_ledger_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dropped row lowers `dispatches`, which can only move the verdict toward agreement.

    Silence there flatters the answer, so the count must reach stdout — the `coherence` branch
    already learned this and its comment records it as "the first version's bug".
    """
    ledger = ledger_path(tmp_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps({**_BASE, "ts": "2026-08-08T00:00:00Z"}) + "\n{ torn\n[1,2]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "harness_maker.economics_source.load_turns",
        lambda *a, **k: _fake_ingestion(["subagent", "main", "subagent"]),
    )
    monkeypatch.setattr("harness_maker.stage_agent_ledger.resolve_base_root", lambda p: tmp_path)

    assert main(["reconcile", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "malformed_rows=2" in out
    assert "2 malformed ledger line(s) excluded" in out
