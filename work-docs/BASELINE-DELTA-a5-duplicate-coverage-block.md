# BASELINE-DELTA — a5-duplicate-coverage-block

**Status: MEASURED.** No declaration preceded it; the movement was discovered by the Phase 2
full-suite run and recorded after the fact, which is the weaker of the two shapes and is stated
as such rather than dressed up. **Revised once**, in review round 2: the first version was written
while `interview.comprehension.depth` had been applied to the base checkout only, so its figures
described a config the committed copy did not have. Cross-model review caught that; the numbers
below are the corrected ones.

**Owning phase: Phase 2 (re-render and reconcile snapshots and baselines).** Phase 1 supplies one
growth row; two configuration changes bundled into this task supply the rest, and they are
attributed separately below because they have nothing to do with each other and a single net
figure would hide all three.

The rule this document satisfies is `PLAN-surface-ratchet`'s **ADR-010** — a ratchet is never
rebaselined by its own subject. **This task is an unusual case for that rule**: the aggregate went
DOWN, so `surface_baseline.json` was regenerated without growth being laundered through it. The
record still belongs here, because the failure class the rule names
(`ratchet-rebaselined-by-its-own-subject`) is about the *record* disappearing, not the sign of the
movement — a net reduction that silently absorbs real increases is the same erasure, and there are
two real increases here.

**Current aggregate after this task: `claude` 435526, `codex` 370455.** The `aggregate_chars`,
`payload_digest` and `render_sha` keys all moved; the latter two are mechanical consequences of
regeneration and carry no independent meaning.

### Direction, stated out loud

**Four command surfaces got LARGER — `execute` by 379 on each arm, `spec` by 1032 on each — while
the aggregate got smaller.** Those are different facts and only the `execute` row is this SPEC's
doing. A reader scanning the aggregate would see a reduction and conclude the task cost nothing;
it cost +379 per execute surface plus +1032 per spec surface, and the reduction hiding it came
from a configuration toggle unrelated to either.

> **Note on the gate that required this section.** `test_the_document_states_the_direction_of_the_aggregate`
> accepts only the words "larger" or "wrong way", so it assumes every baseline movement is growth.
> This task's aggregate moved DOWN, and the sentence above is true as written rather than reworded
> to satisfy the check — four surfaces really are larger. A task whose surface shrank in every
> respect would have no honest way to pass that assertion; that is a limitation of the gate,
> recorded here rather than worked around silently.

## What moved, and which change moved it

| Key | Before | After | Δ | Cause |
|---|---|---|---|---|
| `claude` aggregate | 443831 | 435526 | **−8305** | net of the rows below |
| `codex` aggregate | 376706 | 370455 | **−6251** | same, codex surfaces |
| `execute` | 49443 | 49822 | **+379** | **Phase 1** — the four-site qualifier edit (+251), plus review round 2 bounding the unconditional "must PASS" (+128) |
| `hm-execute` (codex) | 48310 | 48689 | **+379** | **Phase 1** — same two edits, codex arm |
| `spec` | 31852 | 32884 | **+1032** | config — `comprehension.depth: deep` |
| `hm-spec` (codex) | 29124 | 30156 | **+1032** | config — same |
| `plan` | 69954 | 65710 | **−4244** | config — `antigravity` recipe (−5276) **plus** `depth: deep` (+1032) |
| `hm-plan` (codex) | 64164 | 60864 | **−3300** | config — same two, netted |
| `review` | 90525 | 85219 | **−5306** | config — `antigravity` recipe only (`review` has no comprehension block) |
| `hm-review` (codex) | 85843 | 81481 | **−4362** | config — same |
| `health` `chars` | 9772 | 9606 | **−166** | config — the per-model smoke block |
| `health` `round_trips` | 7 | 6 | **−1** | config — one fewer `second_opinion_invoke` smoke call |

**The SPEC's own growth is +379 per execute-bearing surface, and only that.** 251 of it is the
observable qualifier written into four sites (the coverage-lens table row, the `<brief>` routing
sentence, the dispatch string, and — in the agent body rather than the stage — the reviewer's Hard
Rule), plus the sentence stating the previously-implicit rule out loud: N tests under one scenario
ID asserting N different observables is not duplication. The remaining 128 came from review round
2, which bounded that sentence: as first written it said such tests "must PASS" unconditionally,
which targets the same `per_scenario.quality` field the banned-patterns rule forces to FAIL, so a
tautological test asserting a different observable was covered by two rules with opposite verdicts.
It now says they may not FAIL *for that reason* and are still judged against the banned patterns.
No other command was expected to move for SPEC reasons, and none did.

**Two configuration changes ride along, neither of them a phase of this PLAN.** Both were made on
user request in the same session: `second_opinion.models` dropped `antigravity`, so its per-model
recipe stops rendering in `plan` and `review` and `/hm:health` renders one fewer smoke call; and
`interview.comprehension.depth` moved to `deep`, which adds the per-question envelope and the
closing readback to `plan` and `spec`. See the Step 4 boundary report, which names
`.claude/harness.yaml` as out-of-scope drift rather than folding it in silently.

## Round trips

**`health: 7 → 6`, and nothing else.** The per-command table in `test_roundtrip_budget.py` was
re-baselined for that one row with the reason inline. `execute` stays at 17: the four-site edit is
prose inside existing blocks and adds no `!` line. `depth: deep` adds prose, not calls. Re-enabling
`antigravity` restores both the call and the row — this is a toggle, not a deletion.

## What a reader should check if this document looks wrong

The three causes are separable by construction: revert `second_opinion.models` alone and the
`review`/`health` rows return along with 5276 of `plan`'s; revert `comprehension.depth` alone and
the two `spec` rows and 1032 of `plan`'s return; revert the two template files alone and the two
`+379` rows return. If a future measurement finds a row that none of the three explains, this
attribution is incomplete and the row is the finding.
