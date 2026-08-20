"""ADR-011 assertion 1 — the round-trip floor, and the proof it can fail.

The character floor is `measured * 0.80`. One deleted `!` line is ~0.5% of an atomic
command, so a character floor is structurally blind to the very thing this PLAN spends:
round-trips. This arm is therefore **exact equality, zero slack** — deliberately unlike
the character floor. A phase that changes a command's call count re-baselines the table
below **in its own commit**, naming the calls it removed.

A ratchet that cannot fail is worse than none, so the three mutations at the bottom are
not decoration: they are the evidence. The first draft of this phase aimed a single
mutation at the *ceiling*, which that mutation passes — and the shipped render already
`&&`-chains two commands onto one line, so chaining is not even an anomaly to detect by
shape. It has to be detected by count.
"""

from __future__ import annotations

import re

import pytest

from ._surface_baseline import CLAUDE_VARIANT, CODEX_VARIANT, count_round_trips, render_surface

# Measured 2026-07-29 against this repo's `.claude/harness.yaml` through the SAME
# generator the surface baseline uses. Phases 2–5 lowered `execute`, `wrapup` and their
# fused descendants; `research` ROSE because the fan-out's three `Task(` dispatches are
# counted individually by the ADR-011 rule even though they leave in one message — see
# the note in `test_the_fan_out_is_counted_as_three_though_it_costs_one_turn`.
_CLAUDE_ROUND_TRIPS: dict[str, int] = {
    # loop 12→10, plan 18→15, review 37→36, total 165→159 (2026-08-16,
    # PLAN-codex-lens-dispatch). **No mandated call was removed and none was added** — the
    # COUNTING RULE was corrected. `count_round_trips` used a bare `text.count("Task(")` for
    # both variants, which charged backticked PROSE as a round trip (a paragraph reading
    # "retry the `Task(...)` call" cost one) and named the CLAUDE tool for both arms. The
    # second half was harmless only while Codex output still carried `Task(` — and this task
    # is what stops it carrying it. Left alone, the rule would have scored `hm-review`'s
    # fourteen lens dispatches at ZERO from this commit on. Both arms now count their own
    # call-site form. The Claude drop is prose leaving the count plus `plan`'s multi-line
    # `Task(` collapsing into one macro call.
    # +1 on every review-bearing command (2026-07-30, PLAN-second-opinion-acceptance-gate):
    # Step 3.4 gained ONE mandated call, `hm codex_adapter stamp-ids`. It exists because the
    # step previously told an LLM to compute `sha256(...)[:16]` itself — which it cannot do, so
    # Claude-side finding ids were invented per round and the merge-by-`id` contract keyed on
    # values that changed every round. The call is the whole point of that fix; no call was
    # removed. `review` 7→8. (The four fused commands that also inherited it were deleted
    # with the fused axis — PLAN-harness-diet ADR-001.)
    # +1 on `execute`, `plan` and `review` (2026-08-05, PLAN-workflow-loop-efficiency P3):
    # each gained exactly ONE mandated call, and each is a ledger write, not a check:
    #   execute Phase A.5 → `hm stage_agent_ledger emit`   (test-reviewer verdict per attempt)
    #   plan    Step 4    → `hm stage_agent_ledger emit`   (validator verdict per pass)
    #   review  Step 3.4  → `hm stage_agent_ledger persist-payload` (ADR-006 part 2 corpus)
    # No call was removed. `execute` 14→15, `plan` 14→15, `review` 8→9, total 127→130.
    # These three calls are the entire reason stage 2 will have a denominator; the round-trip
    # cost is the price of that, and it is charged per stage invocation, not per round.
    #
    # configure 3→4, total 130→131 (PLAN-onboarding-interview-ux, 2026-08-06). ONE call added,
    # none removed: `hm cli detect-tools --json` in the new "Cross-model second opinion"
    # dimension. It is a check, not a ledger write, and it is conditional in spirit but not in
    # render — the dimension only asks after showing which CLIs are on PATH, and detection
    # cannot be cached (installing a CLI invalidates nothing `profile()` watches, ADR-001), so
    # there is no cheaper shape. `health` is unchanged at 7 even though it gained the same call:
    # that one renders under `{% if not config.second_opinion.models %}` and this fixture's
    # harness has models set, so it is absent from the measured body. Do not "fix" that
    # asymmetry by making health's call unconditional — the gate is the point.
    "configure": 4,
    # 15 → 17 (multi-lens-review-round, 2026-08-10). TWO calls added, none removed: Phase A.5
    # now dispatches one `test-reviewer` per lens — red-correctness, discrimination, coverage —
    # in a SINGLE message, and ADR-011's rule counts every `Task(` individually even though the
    # three leave in one turn. Identical over-count to the `research` fan-out, for the identical
    # reason — see `test_the_fan_out_is_counted_as_three_though_it_costs_one_turn`.
    # The ledger did NOT gain a call: ADR-007 emits one row per ROUND, after the merge, so the
    # three dispatches share one `emit`. Measured basis: a serially-retried single reviewer
    # surfaces one failure category per round (2 then 3 findings), three concurrent lenses
    # surfaced 9 and 12 with ZERO overlap between the two blocking lenses.
    # Attributed in work-docs/BASELINE-DELTA-multi-lens-review-round.md.
    # 17 → 18 (PLAN-ai-review-exit-criteria F1): Phase A.4 runs the test command once, before
    # the A.5 dispatch. It is the cheapest round-trip in this table and it removes reviewer
    # rounds — eleven findings across two tasks were decidable by exactly this call.
    # 18 → 19 (stuck-dispatch, 2026-08-17): ONE call added, none removed — Step 4's blocker path
    # now dispatches `stuck`. It fires only when A.5's budget is exhausted, Phase D is unfixable,
    # or an ADR conflicts, so the round-trip is paid on runs that were already stopping. That
    # off-happy-path claim is now true of the RENDERED TEXT and not only of the intent: the first
    # draft left `dispatch_intro()` and the fence outside the conditional, so a run that exited
    # Step 4 GREEN read an unqualified "Dispatch each item below" imperative and could have spent
    # the call on a stage that never blocked. Attributed in
    # work-docs/BASELINE-DELTA-stuck-dispatch.md.
    # 19 -> 17 (2026-08-17, PLAN-self-induced-regression-gate). Net -2: ADR-010 collapses Phase
    # A.5's three `test-reviewer` dispatches into ONE carrying all three lens questions.
    # It was briefly 18 — ADR-008 added a `verification_cache check` to Phase D (+1) — and
    # review withdrew that read: the producer half was already cut (`is_fresh` never compares
    # check sets, so a marker written after a TARGETED run would let the next verify/wrapup skip
    # the whole suite), which left a consumer that can never hit, because this stage changes
    # files before it reaches the read.
    "execute": 17,
    "health": 7,
    "help": 0,
    "loop": 10,
    "loop-p5-batch": 2,
    "make": 1,
    "metrics": 7,
    # 15 → 14 (PLAN-workflow-time-token-savings A5): the `stage_agent_ledger emit` call is
    # now behind the `instrumentation` axis, which defaults OFF for a fresh install. This
    # repo's own harness has it ON, so the call still renders here — what dropped is the
    # count measured from the DEFAULT fixture. No instruction was deleted.
    # 14 → 18 (2026-08-16, review-loop transfer to the plan stage). Four calls, none removed:
    #   +1  `hm plan_rounds plan` decides WHICH critiques earn a follow-up round. It replaces
    #       "one round per critical critique", which was the stage's only unbounded cost — the
    #       validator passes are capped at two and that cap holds.
    #   +1  `hm plan_rounds outcome` records `no-progress` vs `progress` at the terminal pass.
    #       A bare two-pass cap reports the same ending for both, hiding the one that means
    #       the revision step is not working on this document.
    #   +2  the two `hm review_churn pin` lines (the measure shares the post pin's line) that
    #       feed the stale rule. OPTIONAL: an unmeasured ratio runs every round, so a stage
    #       that skips them behaves exactly as it did before this change.
    "plan": 15,
    "research": 8,
    # 9 → 8 (same phase): `stage_agent_ledger persist-payload`, same axis.
    #
    # 8 → 16 (PLAN-ai-review-exit-criteria Phase 4). The largest single-stage round-trip rise
    # in this table, and all of it is the declared failure space becoming real: five `Task(`
    # lens dispatches in round 1 (+5), `hm freeze resolve-base` once at round 1 (+1), and
    # `hm lens_coverage check` (+2 — once after the round-1 dispatch, once in the auto-fix
    # loop after re-dispatching whatever the CLI's `missing` list named).
    #
    # The five are NOT compressible to one parameterised call. A single `Task(` with a
    # `<lens>` placeholder was considered and rejected for the same reason the Phase A.5
    # fan-out rejected it (see `execute` in the size table): the lenses run CONCURRENTLY in
    # one message, which is the property AC-002 asserts, and a loop over one template is a
    # serial reading. Merging them would also make `<lens>.json` unrenderable per lens, which
    # is what the coverage CLI reads.
    #
    # The two CLI calls replace a judgement, not a cheaper call: before this, nothing computed
    # which lenses had run — the executing model reported its own attendance. That is the
    # self-report hole AC-011 exists to close, so the round-trips buy the gate its input.
    # 16 → 19 (Phase 5): the confirmation pass adds `hm freeze commit` (+1), `hm freeze
    # read-base` (+1) and one more `hm lens_coverage check` over the pass's own results (+1).
    # `read-base` is a round-trip that exists to PREVENT a computation: re-resolving the base
    # here would silently use one that drifted with the commits landed during the review.
    # 19 → 20: the confirmation pass emits its own `stage_agent_ledger` row (F4). It is the
    # only cap in the harness with no recorded episodes, so its two-pass bound can currently
    # be defended only by assertion — the reviewer and validator caps both have rows, and
    # reading them settled questions no argument could (5-of-9 release vs 0-of-12, calling for
    # opposite responses). Behind the `instrumentation` axis, which defaults OFF.
    # 20 → 22 (round-2 review repairs): the auto-fix loop's coverage re-check became its own
    # rendered call (it now needs a repeatable `--round`), and `hm freeze reap` releases the
    # frozen refs at the terminal state — nothing else reaps them under the Side preset.
    # 22 → 39 (2026-08-16, PLAN-review-loop-empirics Phases 2–4). Seventeen calls, all
    # deliberate, none removable:
    #   +2  round 1 dispatches seven lenses instead of five. (It was nine before the
    #       2026-08-16 merge folded `complexity` into `design` and `naming` into `consistency`
    #       on measured redundancy — that merge is what took this row 39 -> 35.)
    #   +7  Step C2 now renders its OWN dispatch list instead of saying "exactly as round 1
    #       does". Under the old axis that back-reference was adequate because each lens had a
    #       self-describing agent; six of the nine now share `code-reviewer` and are told apart
    #       ONLY by their brief line, so a pass that never states the briefs cannot be run.
    #   +2  `hm review_consensus finalize` and the disposition ledger write — Step 4 stopped
    #       being prose (ADR-008), and prose has no executable surface to test. It was three
    #       chained verbs over one rewritten file until 2026-08-16; folding them into one
    #       stateless call took this row 35 -> 33 and removed the write-back defect class.
    #   +2  Phase 5's churn measurement: two endpoint pins (pre-fix, post-fix) and one
    #       `hm review_churn measure` per repair round. The measure shares a line with the
    #       post pin, so the round costs two counted calls, not three. They run only inside
    #       the auto-fix loop — a review that approves at round 1 pays none of them.
    # The ADR-011 rule counts each `Task(` individually even though all seven leave in one
    # message, so the dispatch half of this is a cost in the metric, not in turns.
    #   +2  Phase 6 + 7: `hm review_consensus plan` decides the repair round's re-review
    #       (gate-on render only), and one `hm review_churn oscillation` scan runs at the
    #       terminal state. The gate-off render pays neither and keeps the old dispatch.
    #   +1  ADR-003 of PLAN-self-induced-regression-gate (2026-08-17): Step 0's
    #       `hm review_run open`, which mints the run identity every `<run-id>` below stands
    #       for. `close` is prose on each terminal branch rather than a mandated call line, so
    #       it is not charged here. (An auto-fix-loop cache read was also added and then
    #       withdrawn in review — see the `execute` note above. It was inline prose either way,
    #       so this count never moved for it.)
    #   +1  The Telemetry Emit step's Claude arm gained the `!` auto-exec marker
    #       (2026-08-20). It is not a new call — the step always existed and always had to
    #       run — but it was the ONLY CLI line in this command rendered without `!`, so the
    #       metric never charged for a step the operator was expected to run by reading prose.
    #       That step is the one that writes `disposition_counts` and the four `churn_*` keys,
    #       i.e. the entire deliverable of PLAN-review-loop-ledger-fixes; a review round found
    #       it unmarked. The count rises because the command became honest, not longer.
    "review": 38,
    "spec": 6,
    "uninstall": 3,
    "verify": 13,
    "wrapup": 29,
}


@pytest.fixture(scope="module")
def surface() -> dict[str, dict[str, str]]:
    return render_surface()


def test_the_table_covers_every_rendered_claude_command(surface: dict[str, dict[str, str]]) -> None:
    """A command absent from the table has no round-trip budget at all — the silent way
    this arm narrows. Asserted as set equality so neither direction can drift."""
    assert set(surface[CLAUDE_VARIANT]) == set(_CLAUDE_ROUND_TRIPS)


@pytest.mark.parametrize("name", sorted(_CLAUDE_ROUND_TRIPS))
def test_round_trips_match_exactly(surface: dict[str, dict[str, str]], name: str) -> None:
    actual = count_round_trips(surface[CLAUDE_VARIANT][name], CLAUDE_VARIANT)
    assert actual == _CLAUDE_ROUND_TRIPS[name], (
        f"{name}: {actual} mandated calls, table says {_CLAUDE_ROUND_TRIPS[name]}. "
        "If a phase changed this deliberately, re-baseline HERE in that phase's commit "
        "and name the calls it added or removed."
    )


def test_the_shipped_total_is_not_higher_than_the_table(
    surface: dict[str, dict[str, str]],
) -> None:
    """The aggregate the per-command arms cannot see: calls moved between commands."""
    total = sum(
        count_round_trips(body, CLAUDE_VARIANT) for body in surface[CLAUDE_VARIANT].values()
    )
    assert total == sum(_CLAUDE_ROUND_TRIPS.values())


def test_the_codex_variant_is_counted_by_its_own_call_form(
    surface: dict[str, dict[str, str]],
) -> None:
    """`Bash(` not `^!` — a counter applying the Claude rule to Codex returns 0 and
    asserts nothing, which is how this arm would silently stop binding on that target."""
    execute = surface[CODEX_VARIANT]["hm-execute"]
    assert count_round_trips(execute, CODEX_VARIANT) > 0
    assert len(re.findall(r"^!", execute, re.M)) == 0


def test_the_fan_out_is_counted_as_three_though_it_costs_one_turn(
    surface: dict[str, dict[str, str]],
) -> None:
    """Stated as a test so the discrepancy cannot be quietly forgotten.

    ADR-011's rule adds every `Task(` to the call count. Three `Explore` dispatches sent
    in ONE message are one main-loop turn, so for the fan-out the rule OVER-counts. The
    rule is not being changed mid-flight — moving the goalposts to make a phase pass is
    exactly what ADR-011 forbids — but the Phase 7 receipt reports main-loop turns and
    subagent turns separately (ADR-012) precisely because this proxy conflates them.

    In THIS repo the fan-out does not render at all: `targets` includes `cursor`, and
    Cursor reads the Claude command file (`.cursor/commands/` is dead code), so shipping
    it here would emit a dispatch Cursor cannot resolve.
    """
    body = surface[CLAUDE_VARIANT]["research"]
    assert "Explore" not in body, "this repo includes cursor in targets — see the docstring"


# ── the three mutations ADR-011 requires this arm to fail under ────────────────


def _mutate_chain_two_calls(text: str) -> str:
    """`&&`-chain two real calls onto one line — the shape a ceiling cannot see."""
    lines = text.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.startswith("!")]
    assert len(idx) >= 2, "fixture has too few calls to chain"
    a, b = idx[0], idx[1]
    lines[a] = lines[a] + " && " + lines[b].lstrip("!")
    del lines[b]
    return "\n".join(lines)


def _mutate_delete_one_call(text: str) -> str:
    lines = text.splitlines()
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("!"))
    del lines[idx]
    return "\n".join(lines)


def test_chaining_two_calls_onto_one_line_fails_the_floor(
    surface: dict[str, dict[str, str]],
) -> None:
    body = surface[CLAUDE_VARIANT]["wrapup"]
    mutated = count_round_trips(_mutate_chain_two_calls(body), CLAUDE_VARIANT)
    assert mutated != _CLAUDE_ROUND_TRIPS["wrapup"]


def test_deleting_one_call_fails_the_floor(surface: dict[str, dict[str, str]]) -> None:
    body = surface[CLAUDE_VARIANT]["verify"]
    mutated = count_round_trips(_mutate_delete_one_call(body), CLAUDE_VARIANT)
    assert mutated != _CLAUDE_ROUND_TRIPS["verify"]


def test_moving_a_call_between_commands_fails_the_total(
    surface: dict[str, dict[str, str]],
) -> None:
    """Per-command equality already catches this; the total is the arm that catches it
    when someone re-baselines one command and forgets the other."""
    bodies = dict(surface[CLAUDE_VARIANT])
    bodies["verify"] = _mutate_delete_one_call(bodies["verify"])
    total = sum(count_round_trips(b, CLAUDE_VARIANT) for b in bodies.values())
    assert total != sum(_CLAUDE_ROUND_TRIPS.values())
