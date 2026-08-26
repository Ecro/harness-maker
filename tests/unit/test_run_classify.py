"""Phase 3: retroactive run classification — boundaries, verdict cache, safe defaults.

The invariant every test here defends is ADR-005's: an unresolved boundary NEVER
becomes a continuation. A wrong continuation verdict is invisible (spend silently
lands on a stage that did not incur it); an unattributed run is visible. So the
failure this file must make impossible is the *convenient* one.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from harness_maker import run_classify as rc
from harness_maker.economics import (
    AdjacencyBounds,
    TokenUsage,
    TurnRecord,
    aggregate,
)

T0 = datetime(2026, 7, 26, 9, 0, tzinfo=UTC)


def _usage() -> TokenUsage:
    return TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=1000)


# A sentinel, not `None`: `None` is a MEANINGFUL uuid value (a pre-uuid transcript
# line), so it cannot double as "caller did not specify".
_AUTO_UUID = "\x00auto"


def _turn(
    i: int,
    *,
    skill: str | None = None,
    session: str = "s1",
    uuid: str | None = _AUTO_UUID,
    preceded_by_user: bool = True,
) -> TurnRecord:
    return TurnRecord(
        session_id=session,
        ts=T0 + timedelta(minutes=i),
        model="claude-opus-4-7",
        usage=_usage(),
        attribution_skill=skill,
        uuid=f"u{i}" if uuid == _AUTO_UUID else uuid,
        preceded_by_user=preceded_by_user,
    )


def _verdict(uuid: str, verdict: str, *, version: int = rc.CLASSIFIER_VERSION) -> rc.VerdictRecord:
    return rc.VerdictRecord(
        schema_version=rc.SCHEMA_VERSION,
        boundary_uuid=uuid,
        classifier_version=version,
        verdict=verdict,  # type: ignore[arg-type]
        reason="test",
        ts=T0,
    )


def _index(*records: rc.VerdictRecord) -> dict[tuple[str, int], rc.VerdictRecord]:
    return {(r.boundary_uuid, r.classifier_version): r for r in records}


# ------------------------------------------------------------------ boundary detection


def test_one_boundary_per_contiguous_unattributed_run() -> None:
    turns = [
        _turn(0, skill="hm:plan"),
        _turn(1),
        _turn(2),
        _turn(3, skill="hm:execute"),
        _turn(4),
    ]
    bounds = rc.find_boundaries(turns)

    assert [(b.index, b.end_index, b.preceding_stage) for b in bounds] == [
        (1, 2, "hm:plan"),
        (4, 4, "hm:execute"),
    ]
    assert [b.uuid for b in bounds] == ["u1", "u4"]


def test_a_run_that_opens_the_session_has_no_preceding_stage() -> None:
    """Nothing to continue. A `continuation` verdict here is unsatisfiable, which is
    a different fact from "the classifier said new" and must not be conflated."""
    bounds = rc.find_boundaries([_turn(0), _turn(1), _turn(2, skill="hm:review")])
    assert len(bounds) == 1
    assert bounds[0].preceding_stage is None
    assert (bounds[0].index, bounds[0].end_index) == (0, 1)


def test_a_run_never_continues_a_stage_from_a_different_session() -> None:
    """Turns are sorted by ts across ALL sessions, so the turn physically preceding
    an unattributed one is routinely a peer session's. Inheriting across that seam
    would attribute one session's spend to another's stage."""
    turns = [_turn(0, skill="hm:plan", session="s1"), _turn(1, session="s2")]
    bounds = rc.find_boundaries(turns)
    assert len(bounds) == 1
    assert bounds[0].preceding_stage is None
    assert bounds[0].session_id == "s2"


def test_a_session_change_inside_an_unattributed_stretch_splits_the_run() -> None:
    turns = [
        _turn(0, skill="hm:plan", session="s1"),
        _turn(1, session="s1"),
        _turn(2, session="s2"),
    ]
    bounds = rc.find_boundaries(turns)
    assert [(b.index, b.end_index, b.session_id) for b in bounds] == [
        (1, 1, "s1"),
        (2, 2, "s2"),
    ]


def test_a_ledger_attributed_turn_neither_opens_a_run_nor_inflates_the_boundary_count() -> None:
    """The forward ledger outranks inference (ADR-001), so a span-covered stretch is
    not work for the classifier. Counting it anyway would inflate
    `classification_cache_misses` forever with boundaries nobody should ever judge —
    the instrument reporting a growing backlog that is already resolved.
    """
    turns = [_turn(0, skill="hm:plan"), _turn(1), _turn(2), _turn(3)]
    ledger = (None, "hm:execute", "hm:execute", None)

    bounds = rc.find_boundaries(turns, already_attributed=ledger)

    assert [(b.index, b.end_index, b.preceding_stage) for b in bounds] == [(3, 3, "hm:execute")]


def test_a_fully_attributed_stream_has_no_boundaries() -> None:
    assert rc.find_boundaries([_turn(0, skill="hm:plan"), _turn(1, skill="hm:plan")]) == []


def test_the_boundary_carries_whether_a_user_message_opened_the_run() -> None:
    """ADR-005 names the no-user-message boundary as an explicit absent case; the
    classifier can only honour it if the payload says which kind it is."""
    turns = [
        _turn(0, skill="hm:plan"),
        _turn(1, preceded_by_user=False),
        _turn(2, skill="hm:execute"),
        _turn(3, preceded_by_user=True),
    ]
    bounds = rc.find_boundaries(turns)
    assert [b.has_user_message for b in bounds] == [False, True]


# ------------------------------------------------------------------ safe defaults


def test_a_cache_miss_leaves_the_run_unattributed_and_is_counted() -> None:
    turns = [_turn(0, skill="hm:plan"), _turn(1), _turn(2)]
    result = rc.attribute_runs(turns, rc.find_boundaries(turns), {})

    assert result.stages == (None, None, None)
    assert result.cache_misses == 1
    assert result.unknown == 0
    assert result.continuations == 0
    assert result.boundaries == 1


def test_an_unknown_verdict_leaves_the_run_unattributed_and_is_counted() -> None:
    turns = [_turn(0, skill="hm:plan"), _turn(1)]
    result = rc.attribute_runs(turns, rc.find_boundaries(turns), _index(_verdict("u1", "unknown")))

    assert result.stages == (None, None)
    assert result.unknown == 1
    assert result.cache_misses == 0


def test_a_boundary_with_no_user_message_is_not_auto_continued() -> None:
    """The tempting bug: "no user message separates these turns, so obviously the
    stage continued". It is exactly the invisible-error direction ADR-005 forbids —
    a post-compaction tail or a tool-result boundary looks identical to a
    continuation from the transcript alone. Without a verdict it stays unattributed.
    """
    turns = [_turn(0, skill="hm:plan"), _turn(1, preceded_by_user=False), _turn(2)]
    result = rc.attribute_runs(turns, rc.find_boundaries(turns), {})

    assert result.stages == (None, None, None)
    assert result.cache_misses == 1


def test_a_recorded_continuation_on_a_no_user_message_boundary_is_honoured() -> None:
    """The positive twin of the test above, and the one that stops the *other*
    over-correction: `if not boundary.has_user_message: return unknown` before ever
    consulting the cache. That ships green against every negative test here while
    permanently excluding the post-compaction / tool-result / task-notification
    population — the largest runs in the measured corpus — from attribution, with
    `classification_unknown` climbing and nothing able to distinguish "the classifier
    said unknown" from "the code refused to ask". ADR-005 says these boundaries are
    "classified from surrounding turns, ELSE unknown"; the else-branch is the fallback,
    not the rule.
    """
    turns = [_turn(0, skill="hm:plan"), _turn(1, preceded_by_user=False), _turn(2)]
    result = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u1", "continuation"))
    )

    assert result.stages == (None, "hm:plan", "hm:plan")
    assert result.continuations == 1
    assert result.unknown == 0
    assert result.cache_misses == 0


def test_an_unparseable_cached_line_does_not_poison_its_intact_neighbour(
    tmp_path: Path,
) -> None:
    """A truncated or hand-edited cache line must degrade to unattributed. Counting
    it as parsed-and-continuation is the failure mode that has no observable symptom.
    """
    path = tmp_path / "verdicts.jsonl"
    rc.write_verdict(path, _verdict("u1", "continuation"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"boundary_uuid": "u1", "verdict": "contin\n')  # truncated

    verdicts, diag = rc.read_verdicts(path)
    assert diag.malformed_lines == 1
    assert diag.total_lines == 2

    # The intact record still resolves — a malformed neighbour must not poison it.
    turns = [_turn(0, skill="hm:plan"), _turn(1)]
    result = rc.attribute_runs(turns, rc.find_boundaries(turns), verdicts)
    assert result.stages == (None, "hm:plan")


def test_a_wholly_unparseable_cache_yields_no_verdicts_and_the_run_stays_unattributed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "verdicts.jsonl"
    path.write_text(
        '{"boundary_uuid": "u1", "verdict": "conti\nnot json at all\n', encoding="utf-8"
    )

    verdicts, diag = rc.read_verdicts(path)
    assert verdicts == {}
    assert diag.malformed_lines == 2

    turns = [_turn(0, skill="hm:plan"), _turn(1)]
    result = rc.attribute_runs(turns, rc.find_boundaries(turns), verdicts)
    assert result.stages == (None, None)
    assert result.cache_misses == 1


def test_a_continuation_verdict_with_nothing_to_continue_is_rejected() -> None:
    """The run opens the session: there is no preceding stage. Honouring the verdict
    would require inventing a stage name."""
    turns = [_turn(0), _turn(1), _turn(2, skill="hm:review")]
    result = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u0", "continuation"))
    )

    assert result.stages == (None, None, None)
    assert result.unknown == 1
    assert result.continuations == 0


def test_a_verdict_recorded_under_a_different_classifier_version_does_not_resolve() -> None:
    """Changing the prompt must invalidate prior judgments rather than silently
    reusing them under new semantics."""
    turns = [_turn(0, skill="hm:plan"), _turn(1)]
    stale = _index(_verdict("u1", "continuation", version=rc.CLASSIFIER_VERSION - 1))

    result = rc.attribute_runs(turns, rc.find_boundaries(turns), stale)
    assert result.stages == (None, None)
    assert result.cache_misses == 1


def test_a_boundary_turn_with_no_uuid_cannot_be_cached_and_stays_unattributed() -> None:
    """Older transcript lines may lack `uuid`. The key would be unformable, so the
    run must fall through to unattributed rather than key on something unstable."""
    turns = [_turn(0, skill="hm:plan"), _turn(1, uuid=None)]
    bounds = rc.find_boundaries(turns)
    assert bounds[0].uuid is None

    result = rc.attribute_runs(turns, bounds, _index(_verdict("u1", "continuation")))
    assert result.stages == (None, None)
    assert result.cache_misses == 1


# ------------------------------------------------------------------ positive control


def test_a_continuation_verdict_attributes_every_turn_in_the_run() -> None:
    """Positive control: an implementation that attributes nothing fails here, so the
    safe-default tests above cannot be passed by a no-op."""
    turns = [_turn(0, skill="hm:plan"), _turn(1), _turn(2), _turn(3)]
    result = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u1", "continuation"))
    )

    assert result.stages == (None, "hm:plan", "hm:plan", "hm:plan")
    assert result.continuations == 1
    assert result.cache_misses == 0
    assert result.unknown == 0


def test_a_new_verdict_is_resolved_but_attributes_nothing() -> None:
    """`new` is a real answer, not a failure — it must NOT inflate the miss/unknown
    counters, or the reported instrument health degrades every time the classifier
    correctly says "this is a different task"."""
    turns = [_turn(0, skill="hm:plan"), _turn(1)]
    result = rc.attribute_runs(turns, rc.find_boundaries(turns), _index(_verdict("u1", "new")))

    assert result.stages == (None, None)
    assert result.cache_misses == 0
    assert result.unknown == 0
    assert result.continuations == 0


def test_only_the_runs_own_turns_are_touched() -> None:
    turns = [
        _turn(0, skill="hm:plan"),
        _turn(1),
        _turn(2, skill="hm:execute"),
        _turn(3),
    ]
    result = rc.attribute_runs(
        turns,
        rc.find_boundaries(turns),
        _index(_verdict("u1", "continuation"), _verdict("u3", "new")),
    )

    assert result.stages == (None, "hm:plan", None, None)


# ------------------------------------------------------------------ cache round-trip


def test_write_then_read_round_trips_the_record(tmp_path: Path) -> None:
    path = tmp_path / "verdicts.jsonl"
    rc.write_verdict(path, _verdict("u1", "continuation"))

    verdicts, diag = rc.read_verdicts(path)
    assert diag.malformed_lines == 0
    rec = verdicts[("u1", rc.CLASSIFIER_VERSION)]
    assert rec.verdict == "continuation"
    assert rec.reason == "test"
    assert rec.ts == T0


def test_a_later_record_supersedes_an_earlier_one_for_the_same_key(tmp_path: Path) -> None:
    """The cache is append-only, so re-classification appends rather than rewrites."""
    path = tmp_path / "verdicts.jsonl"
    rc.write_verdict(path, _verdict("u1", "continuation"))
    rc.write_verdict(path, _verdict("u1", "new"))

    verdicts, _ = rc.read_verdicts(path)
    assert verdicts[("u1", rc.CLASSIFIER_VERSION)].verdict == "new"


def test_an_absent_cache_reads_as_empty_rather_than_raising(tmp_path: Path) -> None:
    verdicts, diag = rc.read_verdicts(tmp_path / "nope.jsonl")
    assert verdicts == {}
    assert diag.total_lines == 0


def test_the_cache_resolves_to_the_base_repo_from_inside_a_worktree(tmp_path: Path) -> None:
    """Same seam as the span ledger: a cwd-relative path inside `.worktrees/<slug>/`
    is gitignored churn that `task-land` deletes, so the verdicts built up over a
    task would vanish exactly when the task completes."""

    def _git(args: list[str], cwd: Path) -> None:
        subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=60
        )

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    wt = repo / ".worktrees" / "slug"
    _git(["worktree", "add", "-b", "hm/slug", str(wt)], repo)

    assert rc.verdict_cache_path(wt) == repo.resolve() / ".claude/observability/run-verdicts.jsonl"


# ------------------------------------------------------------------ aggregate wiring


def _priced(skill: str | None, i: int) -> TurnRecord:
    return _turn(i, skill=skill)


def test_inferred_turns_are_labelled_inferred_and_land_on_the_inherited_stage() -> None:
    turns = [_priced("hm:plan", 0), _priced(None, 1), _priced(None, 2)]
    inferred = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u1", "continuation"))
    )

    report = aggregate(turns, bounds=AdjacencyBounds(enabled=False), inferred=inferred)

    assert report.turns_by_attribution_source == {"direct": 1, "inferred": 2}
    assert set(report.by_stage) == {"hm:plan"}
    assert report.by_stage["hm:plan"].turns == 3


def test_the_source_axis_still_partitions_the_turns_with_inference_active() -> None:
    turns = [_priced("hm:plan", 0), _priced(None, 1), _priced(None, 2), _priced(None, 3)]
    inferred = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u1", "continuation"))
    )
    report = aggregate(turns, bounds=AdjacencyBounds(enabled=False), inferred=inferred)

    # The VALUE, not just the sum: with adjacency off, an implementation that ignores
    # `inferred` entirely still conserves (`{direct: 1, none: 3}`), so conservation
    # alone is invariant over the dimension this test is named for.
    assert report.turns_by_attribution_source == {"direct": 1, "inferred": 3}
    assert sum(report.turns_by_attribution_source.values()) == report.turns == 4
    assert report.usd_by_attribution_source
    assert sum(report.usd_by_attribution_source.values()) == pytest.approx(report.total_usd)


def test_a_direct_attribution_outranks_an_inferred_one() -> None:
    """Precedence is `direct > ledger > inferred > adjacency`. Ground truth must win,
    or a classifier bug can overwrite the 44% of turns we actually know."""
    turns = [_priced("hm:plan", 0), _priced("hm:review", 1)]
    # Force a stale inference onto an already-attributed turn.
    forced = rc.ClassificationAttribution(stages=("hm:plan", "hm:plan"), boundaries=0)

    report = aggregate(turns, bounds=AdjacencyBounds(enabled=False), inferred=forced)

    assert report.turns_by_attribution_source == {"direct": 2}
    assert set(report.by_stage) == {"hm:plan", "hm:review"}


def test_a_ledger_attribution_outranks_an_inferred_one() -> None:
    from harness_maker.stage_spans import SpanAttribution

    turns = [_priced(None, 0)]
    spans = SpanAttribution(stages=("hm:verify",))
    forced = rc.ClassificationAttribution(stages=("hm:plan",), boundaries=0)

    report = aggregate(turns, bounds=AdjacencyBounds(enabled=False), spans=spans, inferred=forced)

    assert report.turns_by_attribution_source == {"ledger": 1}
    assert set(report.by_stage) == {"hm:verify"}


def test_an_inferred_attribution_outranks_the_adjacency_estimate() -> None:
    """Adjacency is the last fallback by construction — it resolves to the
    `(unattributed)` bucket, so letting it win would discard a real stage name."""
    turns = [_priced("hm:plan", 0), _priced(None, 1)]
    inferred = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u1", "continuation"))
    )

    report = aggregate(
        turns,
        bounds=AdjacencyBounds(enabled=True, max_gap_min=60.0, max_turns=20),
        inferred=inferred,
    )

    assert report.turns_by_attribution_source == {"direct": 1, "inferred": 1}


def test_the_classification_counters_reach_the_report() -> None:
    turns = [_priced("hm:plan", 0), _priced(None, 1), _priced("hm:review", 2), _priced(None, 3)]
    inferred = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u1", "unknown"))
    )

    report = aggregate(turns, bounds=AdjacencyBounds(enabled=False), inferred=inferred)

    assert report.classification_boundaries == 2
    assert report.classification_unknown == 1
    assert report.classification_cache_misses == 1


def test_no_classification_input_leaves_the_counters_at_zero_and_changes_nothing() -> None:
    """The absent case: a fresh clone with no verdict cache must report the same
    numbers it did before Phase 3 existed, not silently gain an `inferred` bucket."""
    turns = [_priced("hm:plan", 0), _priced(None, 1)]

    report = aggregate(turns, bounds=AdjacencyBounds(enabled=False))

    assert "inferred" not in report.turns_by_attribution_source
    assert report.classification_boundaries == 0
    assert report.classification_cache_misses == 0
    assert report.classification_unknown == 0


# ------------------------------------------------------------------ CLI surface


def test_the_boundaries_command_emits_the_payload_the_classifier_needs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The prose layer in `/hm:metrics` cannot classify what it cannot see: it needs
    the uuid to key on, the stage it would inherit, and the no-user-message flag."""
    rc.main(["boundaries", "--root", str(tmp_path), "--transcript-root", str(tmp_path / "none")])
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "ok"
    assert payload["classifier_version"] == rc.CLASSIFIER_VERSION
    assert payload["boundaries"] == []


def _seed_store(tmp_path: Path) -> Path:
    """One session: an attributed turn, then two unattributed ones opened by a user.

    Built through the encoded-project-dir contract the loader actually uses, so this
    exercises the same discovery + cwd filter the real command does.

    **Timestamps are relative to now, not literals — do not pin them back.** They were
    `2026-07-26T09:0X:00Z`, which passed when written and began failing silently 31 days
    later: `_cmd_boundaries` falls back to `EconomicsConfig.window_days` (30) when
    `--days` is absent and `--root` has no harness.yaml, so `load_turns` dropped all
    three turns as `outside_window` and every assertion about a derived boundary saw an
    empty list. Nothing about the code changed — the fixture aged out of the window.
    `run_classify`'s `boundaries` command has no `--now` (economics does), so anchoring
    the data to the clock is the isolation available here; CLAUDE.md's pre-change
    checkpoint 7 asks for exactly that for any test whose subject reads the clock.
    The relative SHAPE is what the assertions depend on — t0 at +1m, the user turn at
    +1m30s between t0 and t1, t1 at +2m, t2 at +3m — and it is preserved exactly.
    """
    from harness_maker.economics_source import encode_project_dir

    root = tmp_path / "store"
    directory = root / encode_project_dir(tmp_path.resolve())
    directory.mkdir(parents=True)

    # One day old: comfortably inside any window a caller might configure, and far
    # enough from `now` that a slow suite cannot drift a turn into the future.
    base = (datetime.now(UTC) - timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )

    def _stamp(**delta: int) -> str:
        return (base + timedelta(**delta)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _assistant(uuid: str, minute: int, skill: str | None) -> dict[str, object]:
        line: dict[str, object] = {
            "type": "assistant",
            "uuid": uuid,
            "sessionId": "sess-A",
            "timestamp": _stamp(minutes=minute),
            "cwd": str(tmp_path.resolve()),
            "message": {
                "model": "claude-opus-4-7",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "content": [{"type": "text", "text": "x"}],
            },
        }
        if skill is not None:
            line["attributionSkill"] = skill
        return line

    user = {
        "type": "user",
        "sessionId": "sess-A",
        "timestamp": _stamp(minutes=1, seconds=30),
        "cwd": str(tmp_path.resolve()),
        "message": {"role": "user", "content": "actually, also check the parser"},
    }
    lines: list[dict[str, Any]] = [
        _assistant("t0", 1, "hm:plan"),
        user,
        _assistant("t1", 2, None),
        _assistant("t2", 3, None),
    ]
    (directory / "a.jsonl").write_text(
        "".join(json.dumps(entry) + "\n" for entry in lines), encoding="utf-8"
    )
    return root


def test_the_boundaries_command_emits_the_fields_a_verdict_can_be_keyed_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The populated case — the empty-store test above cannot see any of this.

    `boundaries` is the ONLY seam between Python and the `/hm:metrics` prose
    classifier. If it emits rows without a `uuid`, the classifier has nothing to pass
    to `record --boundary-uuid`; without `preceding_stage` it cannot say what would be
    continued; without `has_user_message` it cannot honour ADR-005's no-user-message
    branch. Every one of those failures leaves `find_boundaries`' unit tests green.
    """
    store = _seed_store(tmp_path)
    rc.main(["boundaries", "--root", str(tmp_path), "--transcript-root", str(store)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["total_boundaries"] == 1
    assert payload["pending"] == 1
    (row,) = payload["boundaries"]
    assert row["uuid"] == "t1"
    assert row["preceding_stage"] == "hm:plan"
    assert row["has_user_message"] is True
    assert row["turns"] == 2
    assert row["session_id"] == "sess-A"


def test_the_boundaries_command_stops_listing_a_boundary_once_it_has_a_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bounded cost is the point of the cache (ADR-005: ~144 judgments, not 10,249).
    A command that re-lists resolved boundaries makes every run pay full price again.
    """
    store = _seed_store(tmp_path)
    rc.main(
        [
            "record",
            "--root",
            str(tmp_path),
            "--boundary-uuid",
            "t1",
            "--verdict",
            "continuation",
        ]
    )
    capsys.readouterr()

    rc.main(["boundaries", "--root", str(tmp_path), "--transcript-root", str(store)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["total_boundaries"] == 1
    assert payload["pending"] == 0
    assert payload["boundaries"] == []


def test_the_report_command_reads_the_verdict_cache_and_labels_the_recovered_turns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Phase-3 exit criterion, end to end through the shipped CLI.

    `aggregate()` gained `inferred` in Phase 1's join work, but nothing constructed it
    on the CLI path — the same gap the span ledger had (`_collect` never passed
    `spans` either). Every unit test above passes while `economics report` reports a
    world where the classifier does not exist.
    """
    store = _seed_store(tmp_path)
    rc.main(
        ["record", "--root", str(tmp_path), "--boundary-uuid", "t1", "--verdict", "continuation"]
    )
    capsys.readouterr()

    from harness_maker import economics

    economics.main(["report", "--root", str(tmp_path), "--transcript-root", str(store)])
    report = json.loads(capsys.readouterr().out)["report"]

    assert report["turns_by_attribution_source"] == {"direct": 1, "inferred": 2}
    assert report["by_stage"]["hm:plan"]["turns"] == 3
    assert sum(report["usd_by_attribution_source"].values()) == pytest.approx(report["total_usd"])
    assert report["classification_boundaries"] == 1
    assert report["classification_cache_misses"] == 0


def test_the_report_command_without_a_verdict_falls_back_instead_of_inferring(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The absent case, and the negative control for the test above: with no cache the
    same corpus must NOT produce an `inferred` bucket, and the boundary must show up
    as an uncounted-judgment backlog rather than disappearing."""
    store = _seed_store(tmp_path)
    from harness_maker import economics

    economics.main(["report", "--root", str(tmp_path), "--transcript-root", str(store)])
    report = json.loads(capsys.readouterr().out)["report"]

    assert "inferred" not in report["turns_by_attribution_source"]
    assert report["classification_boundaries"] == 1
    assert report["classification_cache_misses"] == 1


def test_a_cached_line_carrying_a_verdict_outside_the_enum_is_dropped(tmp_path: Path) -> None:
    """Valid JSON, invalid verdict — the write-side `choices` guard cannot catch a
    hand-edited or foreign-tool line. It must be dropped, not coerced."""
    path = tmp_path / "verdicts.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": rc.SCHEMA_VERSION,
                "boundary_uuid": "u1",
                "classifier_version": rc.CLASSIFIER_VERSION,
                "verdict": "maybe",
                "reason": "",
                "ts": "2026-07-26T09:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    verdicts, diag = rc.read_verdicts(path)
    assert verdicts == {}
    assert diag.malformed_lines == 1


def test_the_record_command_persists_a_verdict_that_read_back_resolves(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    rc.main(
        [
            "record",
            "--root",
            str(tmp_path),
            "--boundary-uuid",
            "u1",
            "--verdict",
            "continuation",
            "--reason",
            "same task, user asked to keep going",
        ]
    )

    verdicts, _ = rc.read_verdicts(rc.verdict_cache_path(tmp_path))
    rec = verdicts[("u1", rc.CLASSIFIER_VERSION)]
    assert rec.verdict == "continuation"
    assert "keep going" in rec.reason


def test_the_record_command_rejects_a_verdict_outside_the_enum(tmp_path: Path) -> None:
    """`--verdict maybe` must fail loudly rather than persist a value that
    `read_verdicts` will later discard as malformed — a silent write-then-drop."""
    with pytest.raises(SystemExit):
        rc.main(["record", "--root", str(tmp_path), "--boundary-uuid", "u1", "--verdict", "maybe"])


# ------------------------------------------------- review round 2 (F-01, M-07, M-09)


def test_the_boundaries_command_resolves_a_relative_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-01, the shipped form. `/hm:metrics` renders `--root .`, and an unresolved
    `Path(".")` encodes to the project-dir name `"-"`, which matches nothing — so the
    command returned 0 boundaries while `economics report` saw 392 on the same corpus.

    Every other CLI test here passes an ABSOLUTE `str(tmp_path)`, which is precisely
    why none of them saw it. This one chdirs and passes a literal `.`.
    """
    store = _seed_store(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc.main(["boundaries", "--root", ".", "--transcript-root", str(store)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["total_boundaries"] == 1
    assert payload["boundaries"][0]["uuid"] == "t1"


def test_the_preceding_stage_is_found_past_an_interleaved_peer_session() -> None:
    """M-07. Turns are sorted by ts across ALL sessions, so under concurrency the
    physically-preceding turn is routinely a peer's. Stopping at `i - 1` reported
    "nothing to continue" and silently disabled inference for interleaved sessions —
    the failure is under-attribution, which is safe but invisible."""
    turns = [
        _turn(0, skill="hm:plan", session="s1"),
        _turn(1, skill="hm:review", session="s2"),  # a peer's turn in between
        _turn(2, session="s1"),
    ]
    bounds = rc.find_boundaries(turns)

    assert [(b.index, b.session_id, b.preceding_stage) for b in bounds] == [
        (2, "s1", "hm:plan"),
    ]


def test_a_peer_session_stage_is_still_never_inherited() -> None:
    """Negative control for the scan-back fix: it must skip peer turns, not accept the
    nearest attributed one regardless of session."""
    turns = [_turn(0, skill="hm:plan", session="s2"), _turn(1, session="s1")]

    assert rc.find_boundaries(turns)[0].preceding_stage is None


def test_a_continuation_is_capped_by_turn_count() -> None:
    """M-09. Both sibling attribution paths cap explicitly under a comment saying every
    bound must be able to REJECT; an unbounded inheritance let one verdict move an
    entire overnight stretch onto the preceding stage."""
    turns = [_turn(0, skill="hm:plan"), _turn(1), _turn(2), _turn(3)]
    result = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u1", "continuation")), max_turns=2
    )

    assert result.stages == (None, "hm:plan", "hm:plan", None)


def test_a_continuation_is_capped_by_elapsed_time() -> None:
    """The duration cap rejects independently of the turn cap — `_turn(i)` is one
    minute apart, so a 2-minute bound cuts the third turn."""
    turns = [_turn(0, skill="hm:plan"), _turn(1), _turn(2), _turn(3)]
    result = rc.attribute_runs(
        turns, rc.find_boundaries(turns), _index(_verdict("u1", "continuation")), max_min=1.0
    )

    assert result.stages == (None, "hm:plan", "hm:plan", None)


def test_a_capped_continuation_still_counts_as_one_continuation() -> None:
    assert (
        rc.attribute_runs(
            [_turn(0, skill="hm:plan"), _turn(1), _turn(2)],
            rc.find_boundaries([_turn(0, skill="hm:plan"), _turn(1), _turn(2)]),
            _index(_verdict("u1", "continuation")),
            max_turns=1,
        ).continuations
        == 1
    )


def test_a_capped_turn_is_not_resurrected_by_inference_or_adjacency() -> None:
    """F-03. `attribute_turns` leaves a capped turn's stage `None`, which is
    indistinguishable from "no span claimed it" — so `inferred`/`adjacency` picked it
    up and it was reported as BOTH capped and attributed, contradicting ADR-003's
    terminal cap."""
    from harness_maker.stage_spans import SpanAttribution

    turns = [_priced(None, 0), _priced(None, 1)]
    spans = SpanAttribution(stages=(None, None), capped_indices=(0, 1))
    forced = rc.ClassificationAttribution(stages=("hm:plan", "hm:plan"), boundaries=1)

    report = aggregate(
        turns,
        bounds=AdjacencyBounds(enabled=True, max_gap_min=60.0, max_turns=20),
        spans=spans,
        inferred=forced,
    )

    assert report.turns_by_attribution_source == {"none": 2}
    assert report.capped_turns == 2


def test_a_capped_turn_keeps_its_own_ground_truth() -> None:
    """Negative control: the cap suppresses GUESSES, not the turn's own
    `attributionSkill` — that is measured, not inferred."""
    from harness_maker.stage_spans import SpanAttribution

    turns = [_priced("hm:review", 0)]
    report = aggregate(
        turns,
        bounds=AdjacencyBounds(enabled=False),
        spans=SpanAttribution(stages=(None,), capped_indices=(0,)),
    )

    assert report.turns_by_attribution_source == {"direct": 1}
    assert report.capped_turns == 1


def test_a_mismatched_attribution_length_raises_a_described_error() -> None:
    """M-14. An IndexError from deep inside the loop said nothing about what was
    wrong."""
    from harness_maker.stage_spans import SpanAttribution

    with pytest.raises(ValueError, match="spans.stages has 1 entries for 2 turns"):
        aggregate([_priced(None, 0), _priced(None, 1)], spans=SpanAttribution(stages=(None,)))


# ------------------------------------------------- review round 3 (R2-01, R2-02, R2-04)


def test_a_capped_predecessor_names_no_stage() -> None:
    """R2-01, a defect introduced BY the F-03 fix. The first version marked capped
    indices with the literal `"(capped)"` inside `already_attributed`, and the back-scan
    reads that same sequence — so `preceding_stage` became `"(capped)"`, the prose layer
    was asked whether the run continues "the stage named `(capped)`", and a
    `continuation` verdict bucketed real spend under a stage that does not exist."""
    turns = [_turn(0, skill="hm:plan"), _turn(1), _turn(2)]

    bounds = rc.find_boundaries(turns, capped={1})

    assert [(b.index, b.preceding_stage) for b in bounds] == [(2, None)]


def test_a_capped_turn_does_not_open_a_run() -> None:
    turns = [_turn(0, skill="hm:plan"), _turn(1)]

    assert rc.find_boundaries(turns, capped={1}) == []


def test_both_entry_points_derive_the_same_boundaries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R2-02, guarded by actually CALLING both entry points.

    The first version of this test called `boundary_inputs` and `find_boundaries`
    directly and asserted a property of the HELPER — while the defect it is named for
    is divergence BETWEEN `_cmd_boundaries` and `economics._collect`. Inlining the old
    independent derivation back into either caller left it green. In a task whose
    recurring failure is "two entry points, one of them wrong", a guard that touches
    neither entry point is the same mistake one level up.
    """
    store = _seed_store(tmp_path)

    rc.main(["boundaries", "--root", str(tmp_path), "--transcript-root", str(store)])
    cli_uuids = [b["uuid"] for b in json.loads(capsys.readouterr().out)["boundaries"]]

    from harness_maker import economics

    economics.main(["report", "--root", str(tmp_path), "--transcript-root", str(store)])
    report = json.loads(capsys.readouterr().out)["report"]

    # The report counts the boundaries it derived; the CLI lists the ones it derived.
    # If the two derivations diverge, a verdict recorded against a CLI-listed uuid is
    # looked up under a key the report never asks for — paid for, then discarded.
    assert cli_uuids == ["t1"]
    assert report["classification_boundaries"] == len(cli_uuids)
    assert report["classification_cache_misses"] == len(cli_uuids)


def test_recording_a_verdict_the_cli_listed_is_seen_by_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The end-to-end shape R2-02 actually broke: list → record → report.

    Divergence is only observable when a verdict recorded against a CLI-listed uuid
    fails to resolve in the report. Asserting the counts match is necessary; asserting
    the judgment SURVIVES the round trip is what proves the keys are the same ones.
    """
    store = _seed_store(tmp_path)

    rc.main(["boundaries", "--root", str(tmp_path), "--transcript-root", str(store)])
    (row,) = json.loads(capsys.readouterr().out)["boundaries"]

    rc.main(
        [
            "record",
            "--root",
            str(tmp_path),
            "--boundary-uuid",
            row["uuid"],
            "--verdict",
            "continuation",
        ]
    )
    capsys.readouterr()

    from harness_maker import economics

    economics.main(["report", "--root", str(tmp_path), "--transcript-root", str(store)])
    report = json.loads(capsys.readouterr().out)["report"]

    assert report["classification_cache_misses"] == 0, (
        "the report did not find the verdict the boundaries CLI told the operator to "
        "record — the two entry points are keying on different boundaries"
    )
    assert report["turns_by_attribution_source"].get("inferred") == 2


def test_a_run_split_by_a_peer_turn_still_finds_its_own_preceding_stage() -> None:
    """R2-04. The first M-07 fix broke at the FIRST same-session predecessor
    "attributed or not" — but under interleaving that predecessor is usually another
    fragment of the same unattributed stretch, so every fragment after the first got
    `preceding_stage=None`, was still listed as pending, and cost an LLM judgment that
    could never be applied."""
    turns = [
        _turn(0, skill="hm:plan", session="s1"),
        _turn(1, session="s1"),
        _turn(2, session="s2"),  # a peer turn splits the s1 stretch
        _turn(3, session="s1"),
    ]

    bounds = rc.find_boundaries(turns)

    assert [(b.index, b.session_id, b.preceding_stage) for b in bounds] == [
        (1, "s1", "hm:plan"),
        (2, "s2", None),
        (3, "s1", "hm:plan"),
    ]
