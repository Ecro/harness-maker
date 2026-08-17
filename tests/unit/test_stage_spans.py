"""Phase 1 exit criteria for the stage-span ledger (PLAN-economics-attribution-and-carry).

Every assertion below names the wrong implementation it rejects — the project's
`[fail:test] assertion-invariant-over-named-dimension` class is a relation that
also holds in the broken world, so bounds and non-emptiness are not enough.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker.economics import (
    UNATTRIBUTED,
    AdjacencyBounds,
    TokenUsage,
    TurnRecord,
    aggregate,
    ratio_field_kinds,
)
from harness_maker.stage_spans import (
    SCHEMA_VERSION,
    UNKNOWN_STAGE,
    SpanEvent,
    attribute_turns,
    emit_event,
    ledger_path,
    read_events,
)

T0 = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


class _Turn:
    """Minimal stand-in for TurnRecord — attribute_turns must not require pricing."""

    def __init__(self, minute: float, session_id: str | None = "S1") -> None:
        self.ts = T0 + timedelta(minutes=minute)
        self.session_id = session_id


def _start(
    minute: float = 0.0, *, stage: str = "hm:wrapup", session_id: str | None = "S1"
) -> SpanEvent:
    return SpanEvent(
        schema_version=SCHEMA_VERSION,
        event="start",
        stage=stage,
        cwd="/repo",
        base_root="/repo",
        git_branch="hm/x",
        task_slug="x",
        ts=T0 + timedelta(minutes=minute),
        session_id=session_id,
    )


def _end(minute: float, *, stage: str = "hm:wrapup", session_id: str | None = "S1") -> SpanEvent:
    ev = _start(minute, stage=stage, session_id=session_id)
    return ev.model_copy(update={"event": "end"})


def _turns(n: int, *, step_min: float = 0.1, session_id: str | None = "S1") -> list[_Turn]:
    return [_Turn(0.05 + i * step_min, session_id) for i in range(n)]


# ── closure rules ────────────────────────────────────────────────────────────


def test_closes_on_explicit_end_and_excludes_later_turns() -> None:
    """Rejects an implementation that ignores `end` and runs to the next start/cap."""
    events = [_start(0.0), _end(1.0)]
    turns = [_Turn(0.5), _Turn(0.9), _Turn(1.5), _Turn(2.0)]
    res = attribute_turns(turns, events, max_turns=400, max_min=240.0)
    assert res.stages == ("hm:wrapup", "hm:wrapup", None, None)


def test_closes_on_next_start_and_reassigns_to_the_new_stage() -> None:
    """Rejects an implementation that leaves the first span open past the next start."""
    events = [_start(0.0, stage="hm:plan"), _start(1.0, stage="hm:execute")]
    turns = [_Turn(0.5), _Turn(1.5)]
    res = attribute_turns(turns, events, max_turns=400, max_min=240.0)
    assert res.stages == ("hm:plan", "hm:execute")


def test_closes_at_session_end_so_a_trailing_span_still_attributes() -> None:
    """Rejects an implementation that discards a span with no `end` record."""
    res = attribute_turns([_Turn(0.5), _Turn(9.0)], [_start(0.0)], max_turns=400, max_min=240.0)
    assert res.stages == ("hm:wrapup", "hm:wrapup")


# ── caps: pinned on BOTH sides, and each rejecting independently ─────────────


def test_turn_cap_attributes_the_nth_and_rejects_the_n_plus_first() -> None:
    """A one-sided pin passes for an off-by-one; both sides are pinned here."""
    res = attribute_turns(_turns(5), [_start(0.0)], max_turns=3, max_min=240.0)
    assert res.stages == ("hm:wrapup", "hm:wrapup", "hm:wrapup", None, None)
    assert res.capped_indices == (3, 4)
    assert res.capped_turn_count == 2


def test_duration_cap_rejects_independently_of_the_turn_cap() -> None:
    """Rejects an implementation that only ever applies the turn cap."""
    turns = [_Turn(1.0), _Turn(5.0), _Turn(31.0)]
    res = attribute_turns(turns, [_start(0.0)], max_turns=400, max_min=30.0)
    assert res.stages == ("hm:wrapup", "hm:wrapup", None)
    assert res.capped_indices == (2,)


def test_turn_cap_rejects_independently_of_the_duration_cap() -> None:
    """Mirror of the above — rejects an implementation that only applies the duration cap."""
    res = attribute_turns(_turns(4, step_min=0.01), [_start(0.0)], max_turns=2, max_min=10_000.0)
    assert res.stages == ("hm:wrapup", "hm:wrapup", None, None)


def test_duration_cap_boundary_accepts_at_the_limit_and_rejects_past_it() -> None:
    """Pins the boundary value, not merely that some turn was rejected."""
    turns = [_Turn(30.0), _Turn(30.001)]
    res = attribute_turns(turns, [_start(0.0)], max_turns=400, max_min=30.0)
    assert res.stages == ("hm:wrapup", None)


# ── terminal `capped` state ──────────────────────────────────────────────────


def test_a_late_end_record_cannot_extend_a_capped_span() -> None:
    """Rejects a read-time closure that re-evaluates a capped span against a later `end`."""
    events = [_start(0.0), _end(100.0)]
    res = attribute_turns(_turns(5), events, max_turns=2, max_min=240.0)
    assert res.stages == ("hm:wrapup", "hm:wrapup", None, None, None)


def test_a_later_start_cannot_reopen_a_capped_span() -> None:
    """The later start opens a NEW span; the capped one stays closed."""
    # 5 turns, not 6: `max_turns` applies PER SPAN, so a 6th turn would cap the
    # second span too and entangle that with the property under test.
    events = [_start(0.0, stage="hm:wrapup"), _start(0.35, stage="hm:verify")]
    res = attribute_turns(_turns(5), events, max_turns=2, max_min=240.0)
    assert res.stages == ("hm:wrapup", "hm:wrapup", None, "hm:verify", "hm:verify")
    assert res.capped_indices == (2,)


# ── absent cases ─────────────────────────────────────────────────────────────


def test_turns_before_the_first_start_are_never_backfilled() -> None:
    """Rejects an implementation that back-fills onto the nearest following stage."""
    res = attribute_turns([_Turn(0.5), _Turn(2.5)], [_start(2.0)], max_turns=400, max_min=240.0)
    assert res.stages == (None, "hm:wrapup")


def test_absent_session_id_degrades_the_join_and_is_counted() -> None:
    """Rejects an implementation that silently joins on base_root as if it were exact."""
    res = attribute_turns(
        [_Turn(0.5, session_id="S1"), _Turn(0.6, session_id="S2")],
        [_start(0.0, session_id=None)],
        max_turns=400,
        max_min=240.0,
    )
    assert res.stages == ("hm:wrapup", "hm:wrapup")
    assert res.ambiguous_session_join == 2


def test_a_turn_from_another_session_is_not_attributed_when_the_span_has_an_id() -> None:
    """Rejects an implementation that ignores session_id whenever it is present."""
    res = attribute_turns(
        [_Turn(0.5, session_id="S1"), _Turn(0.6, session_id="OTHER")],
        [_start(0.0, session_id="S1")],
        max_turns=400,
        max_min=240.0,
    )
    assert res.stages == ("hm:wrapup", None)
    assert res.ambiguous_session_join == 0


def test_an_emission_with_no_stage_degrades_to_the_sentinel_and_is_counted() -> None:
    """The real absent case: an un-re-rendered harness omits --stage, so the CLI
    writes an empty `stage`. Pinning the literal 'unknown' instead would freeze a
    second sentinel vocabulary alongside economics' own `(unattributed)`."""
    res = attribute_turns([_Turn(0.5)], [_start(0.0, stage="")], max_turns=400, max_min=240.0)
    assert res.stages == (UNKNOWN_STAGE,)
    assert res.unknown_stage_emissions == 1
    # Pin the constant at its use site. `stages == (UNKNOWN_STAGE,)` alone is invariant
    # over the constant's VALUE — it holds for `UNKNOWN_STAGE = None` and for
    # `= economics.UNATTRIBUTED`, which are exactly the two implementations ADR-008's
    # distinct sentinel exists to prevent (both merge an un-re-rendered harness's
    # emissions into the ordinary unattributed bucket).
    assert isinstance(UNKNOWN_STAGE, str)
    assert UNKNOWN_STAGE
    assert UNKNOWN_STAGE != UNATTRIBUTED


def test_a_named_stage_does_not_increment_the_unknown_counter() -> None:
    """Negative control — rejects an implementation that counts every emission."""
    res = attribute_turns([_Turn(0.5)], [_start(0.0)], max_turns=400, max_min=240.0)
    assert res.unknown_stage_emissions == 0


# ── conservation + positive controls ─────────────────────────────────────────


def test_the_cap_split_is_pinned_by_value_not_by_a_partition_relation() -> None:
    """A partition relation (disjoint ∪ complete) also holds when the cap NEVER
    fires — attributed=all, capped=∅ satisfies it, and so does an off-by-one.
    Only the concrete split rejects both."""
    turns = _turns(10)
    res = attribute_turns(turns, [_start(0.0)], max_turns=4, max_min=240.0)
    assert res.stages == ("hm:wrapup",) * 4 + (None,) * 6
    assert res.capped_indices == (4, 5, 6, 7, 8, 9)


def test_positive_control_an_implementation_attributing_nothing_fails() -> None:
    """Guards every cap test above: those pass trivially if nothing is ever attributed."""
    res = attribute_turns(_turns(3), [_start(0.0)], max_turns=400, max_min=240.0)
    assert res.stages.count("hm:wrapup") == 3


def test_positive_control_no_events_means_no_attribution_and_no_crash() -> None:
    """Guards against an implementation that raises unconditionally."""
    res = attribute_turns(_turns(3), [], max_turns=400, max_min=240.0)
    assert res.stages == (None, None, None)
    assert res.capped_indices == ()


# ── ledger location + durability ─────────────────────────────────────────────


def _real_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A REAL git repo + linked worktree.

    A bare `mkdir` fixture cannot exercise ADR-010: `resolve_base_root` is entirely
    git-driven and returns cwd for a non-repo, so such a fixture can only be made
    green by hand-rolling a `.worktrees` path-scan — which is the very re-derivation
    ADR-010 forbids and the shipped `codex_ledger` bug it exists to prevent.
    """
    base = tmp_path / "repo"
    base.mkdir()

    def run(*a: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *a], cwd=base, check=True, capture_output=True, text=True, timeout=30
        )

    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    (base / "seed.txt").write_text("seed\n", encoding="utf-8")
    run("add", "seed.txt")
    run("commit", "-qm", "seed")
    wt = base / ".worktrees" / "slug"
    run("worktree", "add", "-q", "-b", "hm/slug", str(wt))
    return base, wt


def test_ledger_path_from_inside_a_worktree_resolves_to_the_base_repo(tmp_path: Path) -> None:
    """The shipped codex_ledger bug: a cwd-relative path is deleted by task-land."""
    base, wt = _real_worktree(tmp_path)
    assert ledger_path(wt) == base.resolve() / ".claude" / "observability" / "stage-spans.jsonl"


def test_emit_from_inside_a_worktree_appends_to_the_base_ledger(tmp_path: Path) -> None:
    """Producer/consumer round-trip — the read side must see what the write side wrote."""
    base, wt = _real_worktree(tmp_path)
    emit_event("start", stage="hm:wrapup", cwd=wt, session_id="S1", now=T0)
    path = base.resolve() / ".claude" / "observability" / "stage-spans.jsonl"
    assert path.is_file()
    events, diag = read_events(path)
    assert [e.event for e in events] == ["start"]
    assert events[0].stage == "hm:wrapup"
    assert events[0].base_root == str(base.resolve())
    assert diag.malformed_lines == 0


def test_emit_appends_rather_than_truncating(tmp_path: Path) -> None:
    """Rejects an implementation that opens the ledger for writing instead of appending."""
    base = tmp_path / "repo"
    base.mkdir()
    emit_event("start", stage="hm:plan", cwd=base, session_id="S1", now=T0)
    emit_event("end", stage="hm:plan", cwd=base, session_id="S1", now=T0)
    events, _ = read_events(ledger_path(base))
    assert [e.event for e in events] == ["start", "end"]


def test_a_malformed_trailing_line_is_skipped_and_counted(tmp_path: Path) -> None:
    """A killed process can leave a partial line; the reader must not crash on it."""
    base = tmp_path / "repo"
    path = ledger_path(base)
    path.parent.mkdir(parents=True)
    good = _start(0.0).model_dump(mode="json")
    path.write_text(json.dumps(good) + "\n" + '{"event": "sta', encoding="utf-8")
    events, diag = read_events(path)
    assert len(events) == 1
    assert diag.malformed_lines == 1


def test_read_events_on_a_missing_ledger_is_empty_not_an_error(tmp_path: Path) -> None:
    """Absent-case: a project that never ran an emitting stage must still report."""
    events, diag = read_events(ledger_path(tmp_path / "repo"))
    assert events == []
    assert diag.malformed_lines == 0


# ── config round-trip (checkpoint 6 — extra='forbid' regression) ─────────────


def test_span_cap_keys_survive_a_real_harness_yaml_dump_and_reload(tmp_path: Path) -> None:
    """A constructor echo is NOT this criterion: the key is dropped on the RELOAD
    path, so the test must go through the writer and `answers_from_harness_yaml`.
    Non-default values (123 / 45.0) so a default-fallback bug cannot masquerade
    as survival.
    """
    import yaml

    from harness_maker.interview import answers_from_harness_yaml
    from harness_maker.io_utils import load_harness_yaml

    payload = {
        "schema_version": 3,
        "preset": "Production",
        "targets": ["claude-code"],
        "economics": {"span_max_turns": 123, "span_max_min": 45.0},
    }
    path = tmp_path / "harness.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    reloaded = load_harness_yaml(path)
    assert reloaded["economics"]["span_max_turns"] == 123

    answers = answers_from_harness_yaml(path)
    assert answers is not None
    assert answers.economics.span_max_turns == 123
    assert answers.economics.span_max_min == pytest.approx(45.0)


# ── (d) source-axis conservation — ADR-009 ───────────────────────────────────


def _priced_turn(
    minute: float,
    *,
    skill: str | None = None,
    agent: str | None = None,
    sidechain: bool = False,
    session_id: str = "S1",
) -> TurnRecord:
    return TurnRecord(
        session_id=session_id,
        ts=T0 + timedelta(minutes=minute),
        model="claude-opus-4-7",
        usage=TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=1000),
        attribution_skill=skill,
        attribution_agent=agent,
        is_sidechain=sidechain,
    )


def test_every_priced_turn_carries_exactly_one_attribution_source() -> None:
    """ADR-009 conservation, source axis. Multiple buckets must be populated or the
    sum is trivially one bucket. `inferred` arrives in Phase 3 and is absent here.
    """
    turns = [
        _priced_turn(0.5, skill="hm:review"),  # direct
        _priced_turn(1.5),  # ledger (inside the span below)
        _priced_turn(1.6, agent="code-reviewer", sidechain=True),  # ledger, nested
        _priced_turn(9_000.0),  # none — far outside every span and bound
    ]
    spans = attribute_turns(turns, [_start(1.0), _end(2.0)], max_turns=400, max_min=240.0)
    report = aggregate(turns, spans=spans, bounds=AdjacencyBounds(enabled=False))

    assert sum(report.turns_by_attribution_source.values()) == report.turns == 4
    assert report.turns_by_attribution_source == {"direct": 1, "ledger": 2, "none": 1}
    assert sum(report.usd_by_attribution_source.values()) == pytest.approx(report.total_usd)


def test_direct_beats_ledger_when_a_turn_has_both_candidates() -> None:
    """The 'exactly one' half of (d). Without a turn carrying TWO candidate sources,
    an implementation applying ADR-001's ladder backwards passes every other test.
    The skill differs from the span's stage, so this is also the disagreement the
    ledger's health signal counts.
    """
    turns = [_priced_turn(1.5, skill="hm:review")]
    spans = attribute_turns(turns, [_start(1.0), _end(2.0)], max_turns=400, max_min=240.0)
    report = aggregate(turns, spans=spans, bounds=AdjacencyBounds(enabled=False))

    assert report.turns_by_attribution_source == {"direct": 1}
    assert report.ledger_ground_truth_disagreements == 1


def test_an_adjacency_sourced_turn_is_counted_once_and_does_not_break_the_sum() -> None:
    """`adjacency` is reachable in Phase 1 (Non-Goal 5 keeps estimate_attribution),
    and it is the arm where a double-count would leak into the per-source sum.
    """
    turns = [_priced_turn(0.0, skill="hm:plan"), _priced_turn(0.5)]
    spans = attribute_turns(turns, [], max_turns=400, max_min=240.0)
    report = aggregate(turns, spans=spans, bounds=AdjacencyBounds(enabled=True))

    assert report.turns_by_attribution_source == {"direct": 1, "adjacency": 1}
    assert sum(report.turns_by_attribution_source.values()) == report.turns == 2
    assert sum(report.usd_by_attribution_source.values()) == pytest.approx(report.total_usd)


def test_a_sidechain_turn_nests_into_the_enclosing_span_and_stays_on_by_agent() -> None:
    """ADR-009: nesting must not remove the turn from the `by_agent` cross-cut —
    rejects an implementation that "fixes" conservation by making by_agent a partition.
    """
    turns = [_priced_turn(1.5, agent="code-reviewer", sidechain=True)]
    spans = attribute_turns(turns, [_start(1.0), _end(2.0)], max_turns=400, max_min=240.0)
    report = aggregate(turns, spans=spans, bounds=AdjacencyBounds(enabled=False))

    assert "hm:wrapup" in report.by_stage
    assert report.by_stage["hm:wrapup"].turns == 1
    assert report.by_agent["code-reviewer"].turns == 1


def test_the_disagreement_count_is_computed_and_reported_not_just_stored() -> None:
    """The ledger's only health signal, gated as a COMPUTATION.

    The corpus form of this check ("< 1% over local transcripts") is deliberately NOT
    a gate: the 172-file corpus predates every span, so the intersection of turns
    carrying both is zero and 0-of-0 is vacuously under 1%. That measurement is a
    dated soak item; what must hold now is that the count is right when both signals
    are present, and zero when they agree.
    """
    agree = [_priced_turn(1.5, skill="hm:wrapup")]
    disagree = [_priced_turn(1.5, skill="hm:review")]
    events = [_start(1.0), _end(2.0)]  # span stage == hm:wrapup

    ok = aggregate(
        agree,
        spans=attribute_turns(agree, events, max_turns=400, max_min=240.0),
        bounds=AdjacencyBounds(enabled=False),
    )
    bad = aggregate(
        disagree,
        spans=attribute_turns(disagree, events, max_turns=400, max_min=240.0),
        bounds=AdjacencyBounds(enabled=False),
    )
    # Both arms asserted: a counter stuck at 0 and one that fires on every turn are
    # each rejected, which a single-arm assertion would not do.
    assert ok.ledger_ground_truth_disagreements == 0
    assert bad.ledger_ground_truth_disagreements == 1


def test_a_turn_with_no_ledger_span_never_counts_as_a_disagreement() -> None:
    """Rejects an implementation that treats "no span" as "a span that disagrees" —
    that would make the health signal scale with ledger COVERAGE rather than with
    ledger correctness, i.e. it would look worst exactly where no ledger exists."""
    turns = [_priced_turn(1.5, skill="hm:review")]
    res = aggregate(
        turns,
        spans=attribute_turns(turns, [], max_turns=400, max_min=240.0),
        bounds=AdjacencyBounds(enabled=False),
    )
    assert res.ledger_ground_truth_disagreements == 0
    assert res.turns_by_attribution_source == {"direct": 1}


def test_the_new_source_fields_introduce_no_cost_per_count_ratio() -> None:
    """ADR-002 of the prior economics work is enforced by this scan, not by prose."""
    for name, (num, den) in ratio_field_kinds().items():
        assert not (num == "cost" and den == "count"), name


def test_span_cap_defaults_match_the_measured_calibration() -> None:
    """ADR-003 locked 400/240 against the CDF; a silent default change is a defect."""
    from harness_maker.models import EconomicsConfig

    cfg = EconomicsConfig()
    assert cfg.span_max_turns == 400
    assert cfg.span_max_min == pytest.approx(240.0)


# --------------------------------------------------------- review round 2 (F-02)


def _ev(event: str, stage: str, ts_min: int, session: str | None) -> SpanEvent:
    from datetime import UTC, datetime, timedelta

    return SpanEvent(
        schema_version=SCHEMA_VERSION,
        event=event,  # type: ignore[arg-type]
        stage=stage,
        cwd="/repo",
        base_root="/repo",
        ts=datetime(2026, 7, 26, 9, 0, tzinfo=UTC) + timedelta(minutes=ts_min),
        session_id=session,
    )


class _T:
    def __init__(self, ts_min: int, session: str) -> None:
        from datetime import UTC, datetime, timedelta

        self.ts = datetime(2026, 7, 26, 9, 0, tzinfo=UTC) + timedelta(minutes=ts_min)
        self.session_id = session


def test_a_peer_sessions_start_does_not_close_your_span() -> None:
    """F-02. The ledger is SHARED. With one global `current`, session B's start closed
    A's span, A's session-scoped Stop hook then declined to write A's own `end`, and
    every later A turn fell out of the ledger entirely."""
    events = [
        _ev("start", "hm:plan", 0, "A"),
        _ev("start", "hm:execute", 1, "B"),
    ]
    turns = [_T(2, "A"), _T(3, "B")]

    result = attribute_turns(turns, events, max_turns=400, max_min=240.0)

    assert result.stages == ("hm:plan", "hm:execute")


def test_a_peer_sessions_end_does_not_close_your_span() -> None:
    """The other half: an `end` arriving from B must not terminate A's open span."""
    events = [
        _ev("start", "hm:plan", 0, "A"),
        _ev("start", "hm:execute", 1, "B"),
        _ev("end", "hm:execute", 2, "B"),
    ]
    turns = [_T(3, "A")]

    assert attribute_turns(turns, events, max_turns=400, max_min=240.0).stages == ("hm:plan",)


def test_an_end_with_no_matching_start_in_its_session_is_dropped() -> None:
    """Closing a neighbour's span on a stray end is the same cross-session truncation
    this fix exists to prevent."""
    events = [_ev("start", "hm:plan", 0, "A"), _ev("end", "hm:review", 1, "C")]
    turns = [_T(2, "A")]

    assert attribute_turns(turns, events, max_turns=400, max_min=240.0).stages == ("hm:plan",)


def test_a_sessions_own_start_still_closes_its_previous_span() -> None:
    """Negative control: per-session chaining must not stop next-start closure WITHIN
    a session, which is ADR-003's primary closure rule."""
    events = [
        _ev("start", "hm:plan", 0, "A"),
        _ev("start", "hm:execute", 2, "A"),
    ]
    turns = [_T(1, "A"), _T(3, "A")]

    assert attribute_turns(turns, events, max_turns=400, max_min=240.0).stages == (
        "hm:plan",
        "hm:execute",
    )


def test_an_exact_session_match_outranks_a_session_less_span() -> None:
    """R2-06. `_match` accepts ANY turn inside a session-less span, so a single-pass
    scan let the unjoinable span win purely on list order — the outcome depended on
    which session emitted first, and a peer's turns were claimed outright."""
    events = [
        _ev("start", "hm:plan", 0, "A"),
        _ev("start", "hm:execute", 1, None),  # a session-less peer (WSL2 degraded)
    ]
    turns = [_T(2, "A")]

    result = attribute_turns(turns, events, max_turns=400, max_min=240.0)

    assert result.stages == ("hm:plan",)
    assert result.ambiguous_session_join == 0


def test_a_session_less_span_still_claims_a_turn_it_alone_covers() -> None:
    """Negative control: the exact-first pass must not disable the degraded fallback,
    which is the only attribution available when HM_SESSION_ID is empty everywhere."""
    events = [_ev("start", "hm:execute", 1, None)]
    turns = [_T(2, "A")]

    result = attribute_turns(turns, events, max_turns=400, max_min=240.0)

    assert result.stages == ("hm:execute",)
    assert result.ambiguous_session_join == 1
