"""AC-002 at the call sites — a correct helper wired to nothing is the defect, not the fix.

Phase A.5's coverage and discrimination lenses raised the same thing from two directions:
`tests/unit/test_ledger_exclusions.py` asserts only on the helper, so an implementation that
filters perfectly in `ledger_exclusions.is_excluded` and never reaches
`verifier_discrimination`'s three `run_id in exclusions` sites passes every test in it. That
is not a hypothetical wrong implementation — it is a restatement of the shipped defect, in
which the second-opinion `report` path already called for exclusions and excluded nothing
because it keyed on a field those rows do not have.

So these tests drive the real seams: the `report` CLI over a second-opinion ledger, and
`agent_rounds` over a stage-agents ledger. Both are exercised through their public entry
points rather than through the helper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.verifier_discrimination import agent_rounds, main, marginal_gain


def _call_row(model: str, status: str, slug: str) -> str:
    """An INVOCATION row — `finding_ref: "n/a"` is what makes it one, per CLAUDE.md."""
    return json.dumps(
        {
            "ts": "2026-08-17T00:00:00Z",
            "slug": slug,
            "stage": "review",
            "model": model,
            "finding_ref": "n/a",
            "disposition": "unresolved",
            "status": status,
            "skip_reason": None,
            "oracle_result": None,
            "later_regression_link": None,
            "duration_s": 1.0,
        }
    )


def _agent_row(run_id: str, verdict: str, slug: str = "a") -> str:
    return json.dumps(
        {
            "agent": "test-reviewer",
            "stage": "execute",
            "slug": slug,
            "run_id": run_id,
            "pass_or_attempt": 1,
            "verdict": verdict,
            "terminal": True,
        }
    )


def _report(ledger: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    assert main(["report", "--ledger", str(ledger)]) == 0
    payload: dict[str, Any] = json.loads(capsys.readouterr().out)
    return payload


def test_excluded_slug_absent_from_second_opinion_aggregate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The SPEC-named test. Numerator AND denominator, not just the reported rate.

    The golden split is the machine SPEC's: three real rows, two excluded. Written so the
    two synthetic rows are `skipped` and every real row is `invoked` — that is the shape the
    live ledger actually had, and it is the shape in which the two readings diverge most: a
    filter that misses gives 2/5 = 40% loss, a filter that works gives 0/3 = 0%.
    """
    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        "\n".join(
            [
                _call_row("codex", "invoked", "review-loop-empirics"),
                _call_row("codex", "skipped", "s"),
                _call_row("codex", "invoked", "ai-review-exit-criteria"),
                _call_row("codex", "skipped", "s"),
                _call_row("codex", "invoked", "observed-harness-gaps"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps([{"key": "slug", "value": "s", "reason": "unit-suite synthetic"}]),
        encoding="utf-8",
    )
    before = ledger.read_bytes()

    codex = _report(ledger, capsys)["models"]["codex"]

    assert codex["calls"] == 3, "the excluded rows are still in the DENOMINATOR"
    assert codex["skipped"] == 0, "the excluded rows are still in the NUMERATOR"
    assert codex["loss_rate"] == 0.0
    assert ledger.read_bytes() == before, "reading the ledger must not rewrite it"


def test_an_unexcluded_synthetic_row_still_corrupts_the_rate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The counterexample, so the test above is a claim about the filter and not about the fixture.

    Same ledger, no exclusions file. If this reported 0.0 too, the assertion next door would
    be satisfied by an aggregate that ignores the rows for some unrelated reason.
    """
    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        "\n".join(
            [
                _call_row("codex", "invoked", "review-loop-empirics"),
                _call_row("codex", "skipped", "s"),
                _call_row("codex", "invoked", "ai-review-exit-criteria"),
                _call_row("codex", "skipped", "s"),
                _call_row("codex", "invoked", "observed-harness-gaps"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    codex = _report(ledger, capsys)["models"]["codex"]

    assert codex["calls"] == 5
    assert codex["loss_rate"] == pytest.approx(0.4)


def test_the_legacy_run_id_exclusion_still_reaches_the_stage_agents_ledger(
    tmp_path: Path,
) -> None:
    """Both ledgers, one helper — asserted at `agent_rounds`, not at the helper.

    `aiexit-exec-p2b` is this repository's real exclusion: a PASS emitted before the round it
    describes was dispatched. ADR-007 promotes the file's schema, and the one thing that
    promotion must not do is quietly stop honouring the entry that was already there.
    """
    (tmp_path / "stage-agents.jsonl").write_text(
        _agent_row("aiexit-exec-p2b", "PASS") + "\n" + _agent_row("wtts-exec-a1", "PASS") + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps({"aiexit-exec-p2b": "PASS emitted before its round was dispatched"}),
        encoding="utf-8",
    )

    episodes = agent_rounds(tmp_path)["agents"]["test-reviewer"]["episodes"]

    assert episodes == 1, "the legacy run-id exclusion stopped applying after the promotion"


def _review_row(slug: str, rnd: int, gain: int, run_id: str) -> str:
    return json.dumps({"slug": slug, "round": rnd, "consensus_passed_n": gain, "run_id": run_id})


def test_the_review_rounds_path_filters_through_the_same_helper(tmp_path: Path) -> None:
    """The helper's THIRD consumer — `marginal_gain`, the one no other test drives.

    `verifier_discrimination` has three `run_id in exclusions` sites. Two are covered above.
    This is the one a coverage lens found unexercised, and an unexercised consumer is exactly
    how a migration ships with one call site still on the private loader: nothing fails.

    The fixture is built so the excluded slug is the ONLY source of a round transition. If
    the filter reaches this path, there are no multi-round slugs and no transitions; if it
    does not, the excluded rows manufacture one.
    """
    (tmp_path / "review-2026-08-17.jsonl").write_text(
        "\n".join(
            [
                _review_row("s", 1, 0, "r-synthetic"),
                _review_row("s", 2, 3, "r-synthetic"),
                _review_row("real-task", 1, 2, "r-real"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps([{"key": "slug", "value": "s", "reason": "unit-suite synthetic"}]),
        encoding="utf-8",
    )

    out = marginal_gain(tmp_path)

    assert out["slugs_with_multiple_rounds"] == 0, (
        "the excluded slug still supplied a multi-round episode — the review-rounds path "
        "is not honouring a slug-keyed exclusion"
    )
    assert out["transitions"] == 0
    assert out["revivals"] == []


def test_the_review_rounds_path_sees_the_rows_when_nothing_is_excluded(tmp_path: Path) -> None:
    """Counterexample, so the assertion above is about the FILTER and not about the fixture."""
    (tmp_path / "review-2026-08-17.jsonl").write_text(
        "\n".join(
            [
                _review_row("s", 1, 0, "r-synthetic"),
                _review_row("s", 2, 3, "r-synthetic"),
                _review_row("real-task", 1, 2, "r-real"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out = marginal_gain(tmp_path)

    assert out["slugs_with_multiple_rounds"] == 1
    assert out["transitions"] == 1
    assert out["findings_a_first_zero_stop_would_miss"] == 3


def test_every_call_site_resolves_its_exclusions_through_the_shared_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Delegation, OBSERVED — the one assertion a private per-site loader cannot satisfy.

    Every other test here proves behaviour, and behaviour is exactly what a duplicate
    implementation of the same predicate inside `verifier_discrimination` reproduces. Two
    lenses named that hole from different directions: one said the `marginal_gain` test's
    name claims delegation its values cannot see, the other that the wrong implementation
    *currently on disk* — a private loader kept alongside the new helper — passes the whole
    set.

    Monkeypatching `ledger_exclusions.load` is the fix, because a call site that does not
    call it cannot observe the patch. The stub excludes a slug no file mentions, so a green
    result means the patched helper was consulted, not that a file happened to say so.
    """
    import harness_maker.ledger_exclusions as lx

    monkeypatch.setattr(
        lx, "load", lambda _dir: [lx.Exclusion(key="slug", value="s", reason="injected")]
    )

    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        _call_row("codex", "invoked", "real-task")
        + "\n"
        + _call_row("codex", "skipped", "s")
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "review-2026-08-17.jsonl").write_text(
        "\n".join([_review_row("s", 1, 0, "r"), _review_row("s", 2, 3, "r")]) + "\n",
        encoding="utf-8",
    )
    # slug="s" so the INJECTED entry is what excludes this row. An earlier draft left the
    # default "a" here, which made the assertion below unsatisfiable by any correct
    # implementation — all three lenses caught it independently, and one noted the trap:
    # today the `ImportError` fires first, so the contradiction would stay invisible until
    # the module exists, at which point the cheapest fix available to an implementer is to
    # weaken the assertion that is doing all the work.
    (tmp_path / "stage-agents.jsonl").write_text(
        _agent_row("r1", "PASS", slug="s") + "\n", encoding="utf-8"
    )

    assert _report(ledger, capsys)["models"]["codex"]["calls"] == 1, (
        "report path bypassed the helper"
    )
    assert marginal_gain(tmp_path)["slugs_with_multiple_rounds"] == 0, (
        "rounds path bypassed the helper"
    )
    assert agent_rounds(tmp_path)["agents"] == {}, "agents path bypassed the helper"


def test_every_call_site_delegates_the_predicate_not_only_the_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A call site can honour `load` and still re-filter privately — this refuses that.

    `is_excluded` is patched to a constant `False`, against a well-formed exclusions file
    that WOULD match. If a call site applies its own predicate instead of the helper's, the
    rows vanish and these assertions fail. Only a site that asks the helper — and accepts its
    answer — keeps them.
    """
    from harness_maker import ledger_exclusions as lx

    monkeypatch.setattr(lx, "is_excluded", lambda _row, _entries: False)

    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        _call_row("codex", "invoked", "real-task")
        + "\n"
        + _call_row("codex", "skipped", "s")
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "stage-agents.jsonl").write_text(
        _agent_row("r1", "PASS", slug="s") + "\n", encoding="utf-8"
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps([{"key": "slug", "value": "s", "reason": "would match, must not be applied"}]),
        encoding="utf-8",
    )

    (tmp_path / "review-2026-08-17.jsonl").write_text(
        "\n".join([_review_row("s", 1, 0, "r"), _review_row("s", 2, 3, "r")]) + "\n",
        encoding="utf-8",
    )

    assert _report(ledger, capsys)["models"]["codex"]["calls"] == 2, "report re-filtered privately"
    assert agent_rounds(tmp_path)["agents"] != {}, "agent_rounds re-filtered privately"
    # The third site. Its absence let `marginal_gain` keep a private predicate and pass the
    # whole set — the same "one call site still on the private loader" hole a coverage lens
    # found once already, surviving the rewrite one site over.
    assert marginal_gain(tmp_path)["slugs_with_multiple_rounds"] == 1, (
        "marginal_gain re-filtered privately"
    )


def test_a_real_row_whose_stage_collides_with_an_excluded_slug_is_still_counted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The cross-field negative, driven through a public seam rather than the helper.

    The helper-level test pins `key` semantics; every call-site fixture until now chose
    values that collide with exactly one field, so a key-blind matcher
    (`any(str(v) == entry.value for v in row.values())`) reproduced every asserted number. A
    lens traced all four and confirmed it. Here `stage` equals the excluded SLUG value, so a
    key-blind matcher drops a legitimate row and the count falls to 1.
    """
    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        _call_row("codex", "invoked", "review") + "\n" + _call_row("codex", "skipped", "s") + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps(
            [{"key": "slug", "value": "review", "reason": "collides with every row's stage"}]
        ),
        encoding="utf-8",
    )

    codex = _report(ledger, capsys)["models"]["codex"]

    assert codex["calls"] == 1, (
        "a slug-keyed entry matched rows on their STAGE — the filter is key-blind, and it "
        "will silently drop legitimate rows whose stage equals an excluded slug"
    )
    assert codex["skipped"] == 1


def test_a_torn_exclusions_file_is_loud_and_non_fatal_at_the_report_seam(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Conjunct 3's malformed clause, asserted where the aggregate actually runs.

    The helper-level malformed test is about a function the shipped aggregates might never
    call. Here the torn file reaches `report`, and all three properties are pinned together:
    the command still succeeds, the rows are reported UNFILTERED (fail-open, so a torn file
    cannot silently empty the aggregate), and the shout reaches stderr.
    """
    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        "\n".join(
            [
                _call_row("codex", "invoked", "review-loop-empirics"),
                _call_row("codex", "skipped", "s"),
                _call_row("codex", "invoked", "ai-review-exit-criteria"),
                _call_row("codex", "skipped", "s"),
                _call_row("codex", "invoked", "observed-harness-gaps"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text("{not json", encoding="utf-8")

    assert main(["report", "--ledger", str(ledger)]) == 0
    captured = capsys.readouterr()
    codex = json.loads(captured.out)["models"]["codex"]

    assert codex["calls"] == 5, "a torn exclusions file must not silently empty the aggregate"
    assert codex["loss_rate"] == pytest.approx(0.4)
    assert "NO rows excluded" in captured.err


def test_a_slug_exclusion_also_reaches_the_stage_agents_ledger(tmp_path: Path) -> None:
    """The new key must work on the old ledger too, or 'one helper' is a name, not a fact."""
    (tmp_path / "stage-agents.jsonl").write_text(
        _agent_row("r1", "PASS") + "\n" + _agent_row("r2", "PASS") + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps([{"key": "slug", "value": "a", "reason": "cross-ledger slug entry"}]),
        encoding="utf-8",
    )

    assert agent_rounds(tmp_path)["agents"] == {}


def test_the_report_payload_publishes_what_it_suppressed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The suppression record itself — unpinned until now, so reverting it stayed green.

    `report` began filtering this ledger for the first time with ADR-007 (the previous filter
    keyed on `run_id`, which these rows do not carry, so it was a guaranteed no-op). A filter
    whose output does not say what it removed is the same silent bias the mechanism exists to
    end, one function away — which is exactly why the field must be asserted rather than
    merely added.
    """
    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        "\n".join(
            [
                _call_row("codex", "invoked", "real-task"),
                _call_row("codex", "skipped", "s"),
                _call_row("codex", "skipped", "s"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps([{"key": "slug", "value": "s", "reason": "unit-suite synthetic"}]),
        encoding="utf-8",
    )

    payload = _report(ledger, capsys)

    assert payload["exclusions"]["rows_dropped"] == 2
    assert payload["exclusions"]["applied"] == [
        {"key": "slug", "value": "s", "reason": "unit-suite synthetic"}
    ]


def test_an_unfiltered_report_says_so_rather_than_omitting_the_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Counterexample, so the assertion above is about the filter and not the field's presence."""
    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(_call_row("codex", "invoked", "real-task") + "\n", encoding="utf-8")

    payload = _report(ledger, capsys)

    assert payload["exclusions"] == {"applied": [], "rows_dropped": 0}


def test_an_exclusion_set_that_empties_the_ledger_blames_the_exclusions_not_the_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An intact, full ledger emptied by an over-broad predicate is a CONFIGURATION problem.

    The pre-existing message — "no rows … this is not a clean bill of health; it is an
    absence of evidence" — pointed the operator at a file that is fine, which is a
    multi-hour misdirection for a one-line fix.
    """
    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        _call_row("codex", "invoked", "a") + "\n" + _call_row("codex", "skipped", "b") + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps([{"key": "stage", "value": "review", "reason": "far too broad"}]),
        encoding="utf-8",
    )

    assert main(["report", "--ledger", str(ledger)]) == 1
    err = capsys.readouterr().err
    assert "all 2 row(s)" in err
    assert "exclusion set is too broad" in err
    assert "absence of evidence" not in err


def test_agent_rounds_publishes_a_lossless_exclusion_record(tmp_path: Path) -> None:
    """`excluded_run_ids` collapses same-value entries; the sibling list must not.

    A slug entry and a stage entry sharing a value are precisely the pair the key semantics
    exist to distinguish, and the compatible field renders them as one line under a name that
    says run ids.
    """
    (tmp_path / "stage-agents.jsonl").write_text(_agent_row("r1", "PASS") + "\n", encoding="utf-8")
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps(
            [
                {"key": "slug", "value": "review", "reason": "as a slug"},
                {"key": "stage", "value": "review", "reason": "as a stage"},
            ]
        ),
        encoding="utf-8",
    )

    out = agent_rounds(tmp_path)

    assert out["excluded_run_ids"] == {"review": "as a stage"}, "the lossy field, unchanged"
    assert out["exclusions"] == [
        {"key": "slug", "value": "review", "reason": "as a slug"},
        {"key": "stage", "value": "review", "reason": "as a stage"},
    ], "the lossless record lost an entry — the audit trail under-reports what was suppressed"
