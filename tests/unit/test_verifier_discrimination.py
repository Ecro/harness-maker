"""F3 — read verifier discrimination out of the ledger, and refuse to invent what is missing.

The assertions here are split deliberately. Some pin arithmetic; the rest pin **absences** —
that a quantity needing ground truth is not reported, and that "no evidence" never renders as a
reassuring zero. The absences are the point of the module: an approximate false-acceptance rate
would be indistinguishable from a real one at the call site, which is how a judge stops being
one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.verifier_discrimination import (
    agent_rounds,
    analyse,
    main,
    marginal_gain,
    read_rows,
    to_payload,
)


def _call(model: str, status: str, stage: str = "review") -> dict[str, Any]:
    return {"model": model, "status": status, "stage": stage, "finding_ref": "n/a"}


def _disposition(model: str, disposition: str, ref: str = "f1") -> dict[str, Any]:
    return {
        "model": model,
        "status": "invoked",
        "stage": "review",
        "finding_ref": ref,
        "disposition": disposition,
    }


def test_the_two_row_kinds_are_separated_by_finding_ref() -> None:
    """`finding_ref` is the ONLY discriminator, and mixing the kinds inflates the denominator.

    Both kinds carry `status: "invoked"`, so a reader that counts every row as an invocation
    sees one call per finding. CLAUDE.md records the consequence: an aggregate reported 10.3%
    where the truth was 20.7%.
    """
    rows = [
        _call("codex", "invoked"),
        _call("codex", "skipped"),
        _disposition("codex", "accepted", "f1"),
        _disposition("codex", "rejected", "f2"),
    ]
    stats = analyse(rows)["codex"]
    assert stats.calls == 2, "disposition rows were counted as invocations"
    assert stats.judged == 2
    assert stats.loss_rate == 0.5


def test_failed_is_inside_the_loss_numerator() -> None:
    """A `failed` payload means that model had no voice — identical to a skip downstream.

    Excluding it lets a healthy model dilute a broken one; measured 2026-08-06 at an aggregate
    of 20.7% masking a 2.4% / 37.8% split.
    """
    rows = [
        _call("m", "invoked"),
        _call("m", "skipped"),
        _call("m", "failed"),
        _call("m", "invoked"),
    ]
    assert analyse(rows)["m"].loss_rate == 0.5


def test_health_rows_are_excluded() -> None:
    """The smoke test runs in the base repo on a trivial prompt — structurally `invoked`-biased.

    Counting it makes every model look healthier than it is on the path that matters.
    """
    rows = [_call("m", "skipped"), _call("m", "invoked", stage="health")]
    stats = analyse(rows)["m"]
    assert stats.calls == 1
    assert stats.loss_rate == 1.0


def test_no_disputes_reports_none_not_zero() -> None:
    """The absence that matters most.

    With nothing judged there is no evidence about the verifier. Reporting `unresolved_rate:
    0.0` would read as "the verifier decided everything it saw" — the strongest possible claim,
    made from no data. Measured on the real ledger: antigravity has judged ZERO findings, so
    every discrimination figure for it must be null.
    """
    stats = analyse([_call("m", "invoked")])["m"]
    assert stats.judged == 0
    assert stats.unresolved_rate is None
    assert stats.refutation_rate is None


def test_unresolved_rate_is_the_verifier_abstention_share() -> None:
    """VRR-Stop's quantity: the share of disputes the verifier could not decide."""
    rows = [
        _disposition("m", "accepted", "a"),
        _disposition("m", "rejected", "b"),
        _disposition("m", "unresolved", "c"),
        _disposition("m", "duplicate", "d"),
    ]
    stats = analyse(rows)["m"]
    assert stats.judged == 4
    assert stats.unresolved_rate == 0.25
    assert stats.refutation_rate == 0.25


def test_ground_truth_quantities_are_absent_not_approximated() -> None:
    """The banned output. An `accepted` disposition is NOT a confirmed true positive.

    If this module ever emits a `false_acceptance_rate`, a caller will compare it against the
    literature's numbers, and the comparison will be meaningless — the label means "the oracle
    did not contradict the claim", not "the finding was real".
    """
    payload = to_payload(analyse([_disposition("m", "accepted")]))
    flat = json.dumps(payload)
    assert "false_acceptance_rate" in payload["not_computable"]
    assert "true_positive_rate" not in flat
    assert "accuracy" not in flat
    model_keys = payload["models"]["m"]
    assert not any(k.startswith("false_") for k in model_keys), (
        f"a ground-truth quantity was reported per model: {sorted(model_keys)}"
    )


def test_an_empty_ledger_is_reported_as_absence_of_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing ledger must not exit 0 with an empty-but-healthy-looking report."""
    rc = main(["report", "--ledger", str(tmp_path / "nothing.jsonl")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "not a clean bill of health" in err


def test_a_torn_line_does_not_abort_the_whole_read(tmp_path: Path) -> None:
    """Concurrent sessions append to this file; one torn line must not suppress every number."""
    ledger = tmp_path / "l.jsonl"
    ledger.write_text(
        json.dumps(_call("m", "invoked"))
        + "\n{not json\n"
        + json.dumps(_call("m", "skipped"))
        + "\n",
        encoding="utf-8",
    )
    assert len(read_rows(ledger)) == 2


def test_the_cli_runs_through_its_shipped_spelling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`[fail:test] shipped-entry-point-not-exercised` (count:4) — exercise the entry, not just
    the functions under it."""
    ledger = tmp_path / "l.jsonl"
    ledger.write_text(json.dumps(_call("codex", "skipped")) + "\n", encoding="utf-8")
    assert main(["report", "--ledger", str(ledger)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["models"]["codex"]["loss_rate"] == 1.0


def test_the_cli_rejects_an_unknown_verb() -> None:
    assert main(["summarise"]) == 2


# ── F4: the marginal-gain input, including its counterexamples ────────────────


def _review_row(slug: str, rnd: int, gain: int) -> str:
    return json.dumps({"slug": slug, "round": rnd, "consensus_passed_n": gain})


def test_f4_a_zero_gain_round_followed_by_a_productive_one_is_reported(tmp_path: Path) -> None:
    """The only evidence that can REFUTE a first-zero stopping rule, so it must be surfaced.

    Measured on the real ledger: `second-opinion-invocation-and-slug-cap` produced 2 findings in
    round 1, **0 in round 2**, then 1 in round 3. A rule that stopped at the first non-positive
    round would have missed that finding. Reporting the trend without the counterexamples makes
    the rule look free, which is how a cap gets replaced by a worse cap.
    """
    (tmp_path / "review-2026-01-01.jsonl").write_text(
        "\n".join([_review_row("s", 1, 2), _review_row("s", 2, 0), _review_row("s", 3, 1)]),
        encoding="utf-8",
    )
    out = marginal_gain(tmp_path)
    assert out["revivals"] == [{"slug": "s", "zero_round": 2, "next_round": 3, "gain": 1}]
    assert out["findings_a_first_zero_stop_would_miss"] == 1


def test_f4_a_repeated_slug_round_takes_the_largest_gain(tmp_path: Path) -> None:
    """`/hm:review` re-invocations write a second row for the same slug+round.

    Taking the largest is the reading most FAVOURABLE to the stopping rule under test — if the
    rule still fails on that reading, the failure is not an artefact of the aggregation.
    """
    (tmp_path / "review-2026-01-01.jsonl").write_text(
        "\n".join([_review_row("s", 1, 0), _review_row("s", 1, 3), _review_row("s", 2, 1)]),
        encoding="utf-8",
    )
    out = marginal_gain(tmp_path)
    assert out["revivals"] == [], "a re-invocation row was read as a zero-gain round"
    assert out["decrease"] == 1


def test_f4_single_round_slugs_contribute_no_transitions(tmp_path: Path) -> None:
    """A slug that never had a second round says nothing about whether to stop after one."""
    (tmp_path / "review-2026-01-01.jsonl").write_text(_review_row("only", 1, 4), encoding="utf-8")
    out = marginal_gain(tmp_path)
    assert out["slugs_with_multiple_rounds"] == 0
    assert out["transitions"] == 0


def test_f4_does_not_claim_the_reviewer_caps_are_unmeasured(tmp_path: Path) -> None:
    """A false claim this file previously ASSERTED, so the correction has to be a test too.

    The first F4 draft reported `caps_with_no_telemetry_at_all: ["Phase A.5 reviewer rounds",
    "confirmation passes", "plan-validator passes"]`, in the module, in the PLAN, and here as a
    passing assertion. It was never checked. `stage-agents.jsonl` holds 17 `test-reviewer` rows
    and 25 `plan-validator` rows; both caps are instrumented and always were.

    Encoding an unverified claim as a gate is worse than writing it in prose — the gate then
    certifies it on every run. This test pins the absence of that claim.
    """
    out = marginal_gain(tmp_path)
    assert "caps_with_no_telemetry_at_all" not in out
    assert "emit nothing" not in out["note"]


def test_f4_no_data_exits_nonzero(tmp_path: Path) -> None:
    """An empty observability dir must not read as "the trend is fine"."""
    assert main(["rounds", "--observability-dir", str(tmp_path)]) == 1


# ── The reviewer/validator caps, read from stage-agents.jsonl ─────────────────


def _agent_row(agent: str, slug: str, run: str, attempt: int, verdict: str) -> str:
    return json.dumps(
        {
            "agent": agent,
            "slug": slug,
            "run_id": run,
            "pass_or_attempt": attempt,
            "verdict": verdict,
        }
    )


def test_a_cap_that_never_releases_is_reported_as_such(tmp_path: Path) -> None:
    """The measured `plan-validator` shape: 12 episodes, release_rate 0.0.

    Not one PLAN in the recorded history has reached a clean validator verdict, and the 3-pass
    episodes ended `MAJOR_REVISION` too. A `release_rate` of 0 says the verifier never accepts,
    which is a statement about the verifier or its rubric — raising the cap cannot fix it, and
    a single blended "pass rate" would have hidden it behind the reviewer gate's 56%.
    """
    (tmp_path / "stage-agents.jsonl").write_text(
        "\n".join(
            [
                _agent_row("plan-validator", "a", "r1", 1, "MAJOR_REVISION"),
                _agent_row("plan-validator", "a", "r1", 2, "MAJOR_REVISION"),
                _agent_row("plan-validator", "b", "r2", 1, "MAJOR_REVISION"),
            ]
        ),
        encoding="utf-8",
    )
    out = agent_rounds(tmp_path)["agents"]["plan-validator"]
    assert out["episodes"] == 2
    assert out["released"] == 0
    assert out["bound_by_the_cap"] == 2
    assert out["release_rate"] == 0.0


def test_an_episode_that_flips_to_clean_counts_as_released(tmp_path: Path) -> None:
    """The reviewer gate's useful case: a later pass reaching PASS is the cap paying for itself."""
    (tmp_path / "stage-agents.jsonl").write_text(
        "\n".join(
            [
                _agent_row("test-reviewer", "a", "r1", 1, "FAIL"),
                _agent_row("test-reviewer", "a", "r1", 2, "PASS"),
            ]
        ),
        encoding="utf-8",
    )
    out = agent_rounds(tmp_path)["agents"]["test-reviewer"]
    assert out["released"] == 1
    assert out["bound_by_the_cap"] == 0
    assert out["multi_pass_episodes"] == 1


def test_an_excluded_run_id_is_dropped_from_every_aggregate(tmp_path: Path) -> None:
    """These ledgers are append-only with NO retract verb, so one bad row is permanent.

    This repository has one: `aiexit-exec-p2b` is a `PASS` emitted BEFORE the round it claims to
    describe was dispatched. Without a reader-side exclusion it inflates the reviewer gate's
    release rate in every future aggregate, for good.
    """
    (tmp_path / "stage-agents.jsonl").write_text(
        "\n".join(
            [
                _agent_row("test-reviewer", "a", "good", 1, "FAIL"),
                _agent_row("test-reviewer", "a", "bad", 1, "PASS"),
            ]
        ),
        encoding="utf-8",
    )
    assert agent_rounds(tmp_path)["agents"]["test-reviewer"]["released"] == 1

    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps({"bad": "fabricated"}), encoding="utf-8"
    )
    out = agent_rounds(tmp_path)["agents"]["test-reviewer"]
    assert out["episodes"] == 1
    assert out["released"] == 0
    assert agent_rounds(tmp_path)["excluded_run_ids"] == {"bad": "fabricated"}


def test_a_malformed_exclusions_file_excludes_nothing_rather_than_everything(
    tmp_path: Path,
) -> None:
    """Fail-open here on purpose: a torn exclusions file must not silently empty the report."""
    (tmp_path / "stage-agents.jsonl").write_text(
        _agent_row("test-reviewer", "a", "r", 1, "PASS"), encoding="utf-8"
    )
    (tmp_path / ".ledger-exclusions.json").write_text("{not json", encoding="utf-8")
    assert agent_rounds(tmp_path)["agents"]["test-reviewer"]["episodes"] == 1


def test_agents_with_no_ledger_exits_nonzero(tmp_path: Path) -> None:
    assert main(["agents", "--observability-dir", str(tmp_path)]) == 1


def test_a_gate_that_never_releases_is_flagged_loudly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `plan-validator` shape, measured at 0 of 12, and its consequence.

    That verdict feeds `--judgment-gate blocked`, which **no autonomy level clears, auto_full
    included**, so the halt it drives is the default path on every task.

    The warning deliberately does NOT diagnose. A 0% release rate is equally consistent with an
    unreachable threshold and with an input population that genuinely fails every time, and the
    two call for opposite responses. Reading the 12 recorded episodes settled it here — the
    blocking findings were verified against source and held — but no aggregate could have.

    A number buried in a JSON payload nobody runs is not surfacing. This writes to stderr.
    """
    rows = [_agent_row("plan-validator", f"s{i}", f"r{i}", 1, "MAJOR_REVISION") for i in range(6)]
    (tmp_path / "stage-agents.jsonl").write_text("\n".join(rows), encoding="utf-8")

    assert main(["agents", "--observability-dir", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["degenerate_gates"] == ["plan-validator"]
    assert "zero-release gate" in captured.err
    assert "0 of 6 judged episodes" in captured.err, (
        "the count must be the JUDGED denominator; printing the total overstated N once "
        "never-dispatched episodes were excluded from the rate"
    )
    assert "TWO readings" in captured.err, (
        "the warning asserts a cause it cannot know; a 0% rate does not distinguish an "
        "unreachable threshold from a genuinely failing population"
    )


def test_a_small_sample_zero_is_not_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two failed episodes is noise, not a property of the gate.

    Flagging it would train the reader to ignore the warning, which costs more than the missed
    early signal.
    """
    (tmp_path / "stage-agents.jsonl").write_text(
        "\n".join([_agent_row("plan-validator", "a", "r1", 1, "MAJOR_REVISION")]),
        encoding="utf-8",
    )
    assert main(["agents", "--observability-dir", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["degenerate_gates"] == []
    assert "zero-release gate" not in captured.err


# ── Round-1 review findings ──────────────────────────────────────────────────


def test_the_episode_key_includes_stage(tmp_path: Path) -> None:
    """`run_id` is model-chosen and not globally unique — the sibling module says so.

    `stage_agent_ledger.check_run_coherence` records that keying on fewer than four fields
    "merged independent runs and produced fabricated reports". A three-field key here let one
    stage's pass-2 verdict overwrite another's at the same pass number.
    """
    rows = [
        _agent_row("plan-validator", "s", "shared", 1, "MAJOR_REVISION"),
        _agent_row("plan-validator", "s", "shared", 1, "PASS"),
    ]
    (tmp_path / "stage-agents.jsonl").write_text("\n".join(rows), encoding="utf-8")
    # Same agent+slug+run+pass but different stages → two episodes, not one overwrite.
    import json as _json

    rows2 = [
        _json.dumps({**_json.loads(rows[0]), "stage": "plan"}),
        _json.dumps({**_json.loads(rows[1]), "stage": "review"}),
    ]
    (tmp_path / "stage-agents.jsonl").write_text("\n".join(rows2), encoding="utf-8")
    out = agent_rounds(tmp_path)["agents"]["plan-validator"]
    assert out["episodes"] == 2, "two stages' rows were merged into one episode"


def test_a_conflicting_duplicate_row_is_surfaced_not_applied(tmp_path: Path) -> None:
    """These ledgers are append-only with no retract verb, so a duplicate is a CONFLICT.

    Letting the later row win would rewrite a recorded FAIL into a PASS and move historical
    release rates — accidentally, or by an appended row.
    """
    rows = [
        _agent_row("test-reviewer", "s", "r", 1, "FAIL"),
        _agent_row("test-reviewer", "s", "r", 1, "PASS"),
    ]
    (tmp_path / "stage-agents.jsonl").write_text("\n".join(rows), encoding="utf-8")
    out = agent_rounds(tmp_path)
    assert out["agents"]["test-reviewer"]["released"] == 0, "a later row rewrote a FAIL"
    assert out["conflicting_rows"], "the conflict was applied silently"
    assert out["conflicting_rows"][0]["kept"] == "FAIL"


def test_a_never_dispatched_episode_is_not_blamed_on_the_verifier(tmp_path: Path) -> None:
    """A launch failure says nothing about verifier strictness.

    Counted as `bound`, ≥5 of them would fire the zero-release warning over episodes that
    produced no findings at all — the mis-attribution the module's own docstring warns about.
    """
    rows = [
        _agent_row("plan-validator", f"s{i}", f"r{i}", 1, "dispatch-failed") for i in range(6)
    ] + [_agent_row("plan-validator", "real", "rr", 1, "APPROVED")]
    (tmp_path / "stage-agents.jsonl").write_text("\n".join(rows), encoding="utf-8")
    out = agent_rounds(tmp_path)
    stats = out["agents"]["plan-validator"]
    assert stats["never_dispatched"] == 6
    assert stats["bound_by_the_cap"] == 0
    assert stats["release_rate"] == 1.0, "sentinels were left in the denominator"
    assert out["degenerate_gates"] == []


def test_exclusions_apply_to_the_report_subcommand_too(tmp_path: Path) -> None:
    """The constant says these rows must not enter ANY aggregate; it was honoured in one."""
    ledger = tmp_path / "second-opinion.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps({**_call("codex", "skipped"), "run_id": "bad"}),
                json.dumps({**_call("codex", "invoked"), "run_id": "good"}),
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".ledger-exclusions.json").write_text(
        json.dumps({"bad": "fabricated"}), encoding="utf-8"
    )
    assert main(["report", "--ledger", str(ledger)]) == 0


def test_a_late_launch_failure_does_not_erase_the_episode(tmp_path: Path) -> None:
    """Round-2 P2. Classifying on `order[-1]` alone dropped a real episode from the denominator.

    `PASS` then `dispatch-failed` is producible in the auto-fix loop, and it read as "never
    dispatched" — silently deflating the sample the release rate is computed over. An episode
    is only never-dispatched when EVERY pass is a sentinel.
    """
    rows = [
        _agent_row("test-reviewer", "s", "r", 1, "PASS"),
        _agent_row("test-reviewer", "s", "r", 2, "dispatch-failed"),
    ]
    (tmp_path / "stage-agents.jsonl").write_text("\n".join(rows), encoding="utf-8")
    out = agent_rounds(tmp_path)["agents"]["test-reviewer"]
    assert out["never_dispatched"] == 0
    assert out["released"] == 1
    assert out["release_rate"] == 1.0


def test_a_malformed_exclusions_file_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Now that every subcommand loads it, a trailing comma re-admits the poisoned rows.

    Silently. That is the same shape as the skip-rate contamination this repository already
    records — a no-op that reads as a clean aggregate.
    """
    (tmp_path / "stage-agents.jsonl").write_text(
        _agent_row("test-reviewer", "a", "r", 1, "PASS"), encoding="utf-8"
    )
    (tmp_path / ".ledger-exclusions.json").write_text("{not json", encoding="utf-8")
    agent_rounds(tmp_path)
    assert "NO rows excluded" in capsys.readouterr().err
