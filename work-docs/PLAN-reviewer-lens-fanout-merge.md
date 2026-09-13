---
type: plan
task_slug: reviewer-lens-fanout-merge
status: complete
created: 2026-09-13
tags: [harness-maker, plan, python, jinja2, review-pipeline, token-efficiency]
spec: "[[SPEC-reviewer-lens-fanout-merge]]"
research_doc: "[[RESEARCH-reviewer-lens-fanout-merge]]"
interview_rounds: 5
adrs: 7
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Merge /hm:review's four core lenses into one dispatch; lens_coverage gains a merged mode"
spec_need_verdict: change
spec_need_target: review-loop-empirics
---

# PLAN — merging the `/hm:review` core-lens fan-out

## 🎯 Executive Summary

**TL;DR.** `/hm:review` sends four of its seven lenses to the *same* `code-reviewer` agent,
differing only by one brief sentence, and each one independently re-reads the diff and its
surrounding context. Collapse those four into one dispatch carrying all four questions, and teach
`lens_coverage` that the resulting group file is evidence for all four. Production and Side both
go from seven dispatches per round to four.

**Why now.** Phase A.5 of `/hm:execute` made the identical move for its three test lenses and
recorded ≈330k subagent tokens per round saved — **the token claim only**: A.5's fan-out was
serial retries, while these four already dispatch concurrently, so its ≈2-minutes-per-round
latency saving does not transfer (ADR-001, R8). The four core lenses are structurally the same
situation — one agent, four briefs — and the user directed this change after the
token-efficiency work landed.

**Key decisions.**

| Decision | ADR |
|---|---|
| Merge the four core lenses into one dispatch, **without** a measurement arm | [ADR-001](#adr-001) |
| No per-lens `stage_agent_ledger` instrumentation | [ADR-002](#adr-002) |
| `lens_coverage` gains a **merged mode** rather than the main loop fabricating four empty files | [ADR-003](#adr-003) |
| `exercised` expands the group into its member lenses; `core` never appears in it | [ADR-004](#adr-004) |
| Reversibility lives in a **grouping function**, not a `harness.yaml` knob | [ADR-005](#adr-005) |
| SPEC-need `change` verdict waived; two stale downstream SPEC sentences recorded as debt | [ADR-006](#adr-006) |
| The group identifier and the per-finding lens identifier are **different fields at different levels** | [ADR-007](#adr-007) |

**Estimated impact.** Three fewer subagent dispatches per review round, each of which today
ingests the diff plus up to 400 lines of context per changed file. Round-trip surface for
`review` drops 39 → 33. Two Python functions added, one template's two dispatch blocks rewritten,
two baseline artifacts re-frozen. No `harness.yaml` key, no schema migration, no user-facing
config change.

## 📚 Prior Work

- **[[RESEARCH-reviewer-lens-fanout-merge]]** — the contract compatibility survey and a new
  measurement over six shipped `review-payloads` rounds: 89 lens-stamped findings, 79 `file:line`
  groups, only 8 (10.1%) raised by more than one lens; core-four redundancy sits between 13.7%
  and 40.7% depending on the grouping key.
- **`execute.md.j2:265-306`** — the Phase A.5 merged dispatch. It is the direct precedent **and**
  the source of the counter-evidence: it records that on the round which produced it, all six
  blocking issues were solo finds, so "the independent contexts, not the lens text, produced that
  spread."
- **[[PLAN-multi-lens-review-round]]** — records a single-`Task(`-with-`<lens>`-placeholder
  compaction that was **tried and reverted**: "a literal example is what an executing model
  imitates, and choosing the cheaper form *because* it was cheaper is exactly the move that
  produced two of the four P0s in the parent task." This PLAN therefore renders literal
  dispatches with literal questions.
- **`[wiki:architecture] nine-lens-axis-and-solo-lens-vote` (2026-08-16)** — ADR-007's solo-lens
  vote, the per-finding `lens` provenance, and the rule that `lens` is metadata only and never an
  input to `codex_adapter.finding_id`.
- **[[PLAN-token-efficiency-autopilot-ux-speed]]** — ADR-003 retracted the `reviewers.enabled`
  fan-out lever (it is not an input to `lens_dispatch` at any point). ADR-005 of that PLAN and
  `BASELINE-DELTA-workflow-steps-vs-model-capability` carry the corrected precondition for a
  whole-file baseline re-freeze: **no peer PLAN may hold a live `surface_allowance`.**
- **`~/harness-bench/docs/review-convergence/FINDINGS.md` §10** — single structured call 11.0
  distinct findings, same prompt ×6 19.7, six categories ×6 30.0. The enumerated-categories-in-one-call
  cell this merge produces was never run.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Merge shape | Scope boundaries | Measure first, merge now, partial 4→2, or measure-only? | 4 | **Merge now (A.5 precedent)** | Inherited from `/hm:spec` Round 1. Yield comparison dropped from scope. | ADR-001 |
| 2 | Instrumentation | Observability | Add per-lens `stage_agent_ledger` rows? | 3 | **No** | Inherited from `/hm:spec` Round 1. Fixes the round-trip target at 33 rather than 37. | ADR-002 |
| 3 | Coverage satisfaction | Contract shape | Four fabricated files, a `lens_coverage` merged mode, or an agent-returned lens list? | 3 | **Merged mode in `lens_coverage`** | Inherited from `/hm:spec` Round 2. Accepts a Python change to make the gate say what it measures. | ADR-003, ADR-004 |
| 4 | Reversibility | Architecture | Grouping function, template hardcode, or `harness.yaml` knob? | 3 | **Grouping function** | Inherited from `/hm:spec` Round 2. No knob — an unevidenced choice is not put to consuming projects. | ADR-005 |
| 5 | SPEC-need gate | Scope boundaries | Two downstream SPECs carry lens-dispatch sentences this change contradicts. Author now, waive, or waive + schedule? | 3 | **Waive, record as debt in this PLAN** | `/hm:plan` Step 1.7. Both sentences were already stale before this work (core 6→4, mandatory 5→7) and neither prior change triggered a SPEC operation. Waiver is diff-hash-bound. | ADR-006 |
| 6 | Entry to decomposition | Implementation phasing | Proceed to phases, or lock a how-question first? | 4 | **Proceed to phase decomposition** | `/hm:plan` Step 3.0. The five defaults A1–A5 were shown before the question and accepted with it. | — |
| 7 | Unvalidated revision | Risk tolerance | The only validator pass returned MAJOR_REVISION and the revision answering it is unreviewed. Proceed to execute, re-validate once, or read the PLAN yourself? | 3 | **Proceed to execute (A)** | `/hm:plan` autopilot judgment gate, classified `pending` rather than `clear` because the literal `blocked` predicate keys on a *second* pass that the standing one-pass instruction skipped. Answered by the user, not auto-answered. The residual is that the revised document has no reader; it moves to `/hm:execute` Phase A.5 and `/hm:review`. | — |

**Defaults taken without asking** (shown in the design brief, none contested):
A1 no new CLI flag — merged mode is detected by file presence, so an un-re-rendered harness keeps
working; A2 the group file is `core.json` (`core` is not in `ALL_LENSES`, so no stem collision);
A3 the group vocabulary lives in `conditional_router`, already the single owner of lens
vocabulary; A4 the dispatch description names all four lenses rather than a single `core` label,
so a transcript reader can see what ran; A5 the baseline re-freeze waits on
`load_active_allowances` returning none.

## 📐 Architecture Decision Records

### ADR-001: Merge the four core lenses into one dispatch, without measuring the yield

**Status:** Accepted (2026-09-13, via /hm:spec interview Round 1, carried here)
**Context:** The four core lenses share one agent and differ by one sentence, so three of the
four context ingestions are redundant. Whether the *yield* is redundant is unknown: RESEARCH
measured 86.3% of core findings as line-exact solo-lens, and the nearest external data point
(`harness-bench` §10) scored a single generic call at 11.0 distinct findings against 30.0 for a
six-category fan-out — but the enumerated-categories-in-one-call arm was never run.
**Decision:** Merge now, following Phase A.5, with no paired measurement.
**Consequences:**
- ✅ Three subagent dispatches per round disappear immediately; the scope stays one unit.
- ⚠️ A yield loss, if any, is unobservable — a review that finds less looks like a clean review.
  This is stated in the SPEC Intent and here rather than discovered later.
- ⚠️ The A.5 precedent's *latency* claim does not transfer: A.5's fan-out was serial retries,
  while these four already dispatch concurrently in one message, so wall-clock gain is ≈0.
**Rejected alternatives:**
- Measure first, merge on the result — rejected as one unit becoming two stages.
- Partial merge 4→2 — rejected: half the saving, and the pairing would rest on reasoning rather
  than data.
- Measure only, defer the merge — rejected: zero token saving this unit.
**Source:** Interview #1

### ADR-002: No per-lens `stage_agent_ledger` instrumentation

**Status:** Accepted (2026-09-13, via /hm:spec interview Round 1, carried here)
**Context:** `stage-agents.jsonl` carries 57 `test-reviewer` rows, 41 `plan-validator` rows and 9
`confirmation-pass` rows — and **zero** review-lens rows. That is why RESEARCH could measure lens
*yield* from the shipped payloads but not lens *cost*.
**Decision:** Do not add per-lens rows in this unit.
**Consequences:**
- ✅ The round-trip budget moves in one direction only (39 → 33), which keeps the baseline
  re-freeze simple.
- ⚠️ Whether this merge paid off cannot be confirmed after it ships, and the next person asking
  the same question starts where this one did.
- ⚠️ `step_sensitivity`'s TUNE entries for the fan-out stay unmeasurable on the cost axis.
**Rejected alternatives:**
- One row per lens — rejected by the user; would have pushed the round-trip target to 37.
- One row per merged dispatch — rejected for the same reason at smaller scale.
**Source:** Interview #2

### ADR-003: `lens_coverage` gains a merged mode

**Status:** Accepted (2026-09-13, via /hm:spec interview Round 2, carried here)
**Context:** `exercised_lenses` builds its set from files that exist, parse, self-identify and
carry the right `run_id`. With one dispatch producing findings for four lenses, either the main
loop fabricates four per-lens files from one return, or the reader learns about group files.
**Decision:** Teach `lens_coverage` a group-file vocabulary: `core.json` carrying `lens: "core"`
contributes all four core lenses to the exercised set. Per-lens files keep working unchanged.
**Consequences:**
- ✅ The gate names what it actually measures instead of being fed four files that never
  independently existed.
- ✅ An un-re-rendered consuming harness writing four per-lens files stays approvable — both
  shapes resolve through the same code path, with no CLI flag to get wrong.
- ⚠️ A Python change to a fail-closed security-adjacent reader; AC-006 makes the fail-closed
  property explicit over the whole class of non-conforming files, not five enumerated cases.
- ⚠️ The gate's meaning weakens deliberately: `exercised` now answers "was this lens asked",
  not "did this lens deliver". It still catches the merged dispatch dying wholesale.
**Rejected alternatives:**
- Main loop writes four files with `findings: []` — rejected: it manufactures evidence of four
  deliveries that never happened, which is the exact failure `exercised_lenses` exists to catch.
- The merged agent returns its own "lenses I actually covered" list — rejected: an omission
  blocks a clean review, and a non-omission is identical to the first option.
**Source:** Interview #3

### ADR-004: `exercised` expands the group into its member lenses

**Status:** Accepted (2026-09-13, promoted from SPEC Open Question 1)
**Context:** With a group file, the verdict could report `core` or the four lenses it stands for.
`review_telemetry.lenses_exercised` is the downstream consumer and has shipped rows carrying the
individual names.
**Decision:** `exercised` contains `design`, `functionality`, `robustness`, `consistency` as
separate entries and never contains `core`. `ALL_LENSES` stays the output vocabulary; the group
name lives in a separate group vocabulary consumed only by `exercised_lenses`.
**Consequences:**
- ✅ `lenses_exercised` stays comparable with rows written before this change — the shipped
  2026-08-19 row is the golden for SPEC AC-005.
- ✅ `review_telemetry`'s lens enum needs no extension, so no parity test moves.
- ⚠️ A reader of the verdict cannot tell a merged run from a fan-out run. That is the intended
  trade: the verdict answers coverage, and the dispatch shape is the template's fact, not the
  gate's.
**Rejected alternatives:**
- Report `core` — rejected: breaks telemetry continuity and forces an enum extension whose
  missed reader is the failure mode.
**Source:** SPEC Open Question 1

### ADR-005: Reversibility is a grouping function, not a config knob

**Status:** Accepted (2026-09-13, via /hm:spec interview Round 2, carried here)
**Context:** Restoring the fan-out must be cheap, and the two dispatch blocks (round 1 and
Step C2) must not be able to drift — SPEC AC-015 of the nine-lens work makes a mismatch a
permanently unapprovable review.
**Decision:** Add `conditional_router.lens_dispatch_groups(preset)` and export it as a Jinja
global. Both dispatch blocks loop over it; neither contains a literal lens name, agent name or
brief. `lens_dispatch()` is untouched. No `harness.yaml` key.
**Consequences:**
- ✅ Restoring the fan-out is one function returning one group per lens.
- ✅ Round-1/Step-C2 parity is structural, not a convention — SPEC AC-002 and AC-008 assert it.
- ⚠️ Consuming projects get no lever for the dispatch shape. Deliberate: the merge rests on a
  precedent rather than on data for this stage, and an unevidenced choice is not handed to users
  as a setting. The retraction in `PLAN-token-efficiency-autopilot-ux-speed` ADR-003 is the
  cautionary case — a phantom lever is worse than none.
**Rejected alternatives:**
- Hardcode both blocks — rejected: two blocks that can drift, with an unapprovable review as the
  symptom.
- `reviewers.core_lens_dispatch: merged|fanout` — rejected: doubles the rendering arms, needs a
  schema migration and an interview round, for a choice nobody has evidence to make.
**Source:** Interview #4

### ADR-006: The SPEC-need `change` verdict is waived, with the debt recorded here

**Status:** Accepted (2026-09-13, via /hm:plan Step 1.7)
**Context:** Step 1.7 judged `change` against `SPEC-review-loop-empirics` AC-009 ("round-1
dispatch names the **six** core lenses on both presets", one brief per lens) and
`SPEC-ai-review-exit-criteria` ("all **five** mandatory lenses are dispatched as lens briefs, in
parallel"). Both sentences were **already wrong before this work**: the core set became four on
2026-08-16 and the Production mandatory set became seven, and neither of those changes triggered
a SPEC operation.
**Decision:** Waive, with a diff-hash-bound waiver receipt, and record the stale sentences plus
a third finding as explicit debt in this PLAN.
**Consequences:**
- ✅ This unit is not made to carry a backlog two earlier units created.
- ⚠️ A third layer of staleness accumulates on two SPECs. Recorded in the risk register (R4) so
  the next reader finds it stated rather than inferred.
- ⚠️ The waiver expires when the diff changes, so a later `/hm:plan` on this slug will re-ask.
**Third finding, recorded here because it has no other home:**
`SPEC-lens-and-review-fix-verification` AC-004 specifies an `unstamped` array over "findings
lacking a `lens` key matching the file's lens". That AC is `pending_test: true` and **was never
implemented** — `unstamped` appears nowhere in `src/`, and the test it names does not exist. Its
definition, taken literally, would mark every finding in a merged `core.json` as unstamped,
because those findings carry four different lens values and none of them is `core`. Nothing
breaks today. An implementer of that AC must scope "the file's lens" to the group's member
lenses.
**Rejected alternatives:**
- Author the SPEC changes now — rejected as disproportionate: it blocks the merge behind cleanup
  of two pre-existing errors.
**Source:** Interview #5

### ADR-007: The group identifier and the per-finding lens identifier are different fields

**Status:** Accepted (2026-09-13, from the cross-model second opinion at Step 4)
**Context:** `review.md.j2` Step 3 today says to add a `"lens"` key to the result file "**and
stamp the same `"lens"` value on every finding inside it**". `lens_coverage.exercised_lenses`
requires the file-level value to equal the filename stem, so a merged file must carry
`"lens": "core"`. Read literally, the instruction then stamps `core` on every finding — and the
paragraph directly beneath it explains that the per-finding stamp exists precisely so Step 4 can
tell one lens speaking once from one lens speaking several times. Following the sentence would
destroy the thing the sentence is for. For a singleton group the two values coincide, which is
why the collision was invisible until a group held more than one lens.
**Decision:** Two levels, two meanings. The **file-level** `"lens"` is the **group** identifier —
`core` for the merged file, the lens name for a singleton group — and is what `exercised_lenses`
matches against the stem. The **per-finding** `"lens"` is the **member lens that raised it**, one
of `design` / `functionality` / `robustness` / `consistency`, assigned by the merged agent and
preserved verbatim by the main loop. The rewritten instruction states both, explicitly.
**Consequences:**
- ✅ The solo-lens vote (ADR-007 of the *nine-lens* work, not this document) stays decidable
  from the data Step 4 actually sees.
- ✅ `codex_adapter.finding_id` is untouched; `lens` stays metadata at both levels, so the
  round-to-round merge key does not move.
- ⚠️ A new way for the main loop to get it wrong: a finding stamped `core` is attributable to no
  lens. The rewritten instruction names the four admissible values, but **nothing mechanically
  rejects a wrong one** — that stays a review-time catch (R9).
**Rejected alternatives:**
- Keep the sentence verbatim — rejected: it is the contradiction above.
- Make the file-level value a list of member lenses — rejected: `exercised_lenses` compares that
  value to the filename stem, and a list cannot equal a stem without changing the core comparison
  for every existing per-lens file too.
**Source:** Second opinion (codex), finding `da5d7ffa626388fd`

## 🏗️ Technical Design

**Current state.** `review.md.j2:2` binds `lenses = lens_dispatch(config.preset)` and two blocks
— Step 3 (round 1, line ~215) and Step C2 (line ~993) — loop over it emitting one
`dsp.dispatch(...)` per lens. `lens_dispatch()` returns seven `{lens, agent, brief}` dicts on
both presets (mandatory + routable). `template_globals.TEMPLATE_GLOBALS` exports
`lens_dispatch` / `mandatory_lenses` / `routable_lenses`. `lens_coverage.exercised_lenses` walks
`*.json` in the round directory and accepts a file only when its stem is in `ALL_LENSES`, its
`lens` field equals the stem, and its `run_id` matches.

**Affected components.**

| Component | Change |
|---|---|
| `src/harness_maker/conditional_router.py` | **add** `lens_dispatch_groups(preset)` and the group vocabulary constant. Nothing existing changes. |
| `src/harness_maker/template_globals.py` | **add** one entry to `TEMPLATE_GLOBALS`. |
| `src/harness_maker/lens_coverage.py` | **extend** `exercised_lenses` to accept a group file and expand it to its member lenses. `coverage_verdict` / `round_dir` unchanged in signature and in fail-closed behaviour. |
| `src/harness_maker/templates/stages/review.md.j2` | **rewrite** both dispatch blocks, the result-file path listings beside them, and Step 1's "told apart only by the lens line" sentence. |
| `tests/structural/test_roundtrip_budget.py` | `review` 39 → 33 with an attribution note. |
| `tests/structural/surface_baseline.json` | re-freeze `review` / `hm-review` `chars` + `round_trips` + aggregates + digest. |
| `tests/snapshot/*.expected.yaml` | **regenerate** — eight fixtures each pin `body_sha256` for `commands/hm/review.md` and `stages/review.md`; the active exclusion list is empty, so every edit to this template reddens `test_synthesize_snapshot.py`. |
| `tests/unit/test_render_lens_dispatch.py`, `tests/unit/test_render_confirmation_pass.py`, `tests/unit/test_render_lens_axis.py` | **migrate** — all three encode the one-result-file-per-lens contract. |
| `work-docs/BASELINE-DELTA-reviewer-lens-fanout-merge.md` | **new** — one attribution row per changed key. |

**Not affected:** `review_consensus.py`, `codex_adapter.py`, `models.py`, `interview.py`,
`review_telemetry`'s lens enum, `harness.yaml`, `synthesize.py`, `execute.md.j2`.

**Data flow.**

```
lens_dispatch_groups(preset)
   → [ {agent: code-reviewer,        lenses: [design, functionality, robustness, consistency],
        briefs: [...4 verbatim...],  file: "core"},
       {agent: security-reviewer,    lenses: [security],    briefs: [...], file: "security"},
       {agent: concurrency-reviewer, lenses: [concurrency], briefs: [...], file: "concurrency"},
       {agent: test-reviewer,        lenses: [tests],       briefs: [...], file: "tests"} ]
        │
        ├── review.md.j2 Step 3   → 4 dispatches, 4 result files (core.json + 3)
        └── review.md.j2 Step C2  → the same 4, same briefs

lens_coverage.exercised_lenses(round_dir, run_id)
   core.json      (lens == "core")   → {design, functionality, robustness, consistency}
   design.json    (lens == "design") → {design}          ← un-re-rendered harness
   anything else                     → ∅                 ← fail-closed, AC-006
```

**API changes.** One new public function in `conditional_router`, one new `TEMPLATE_GLOBALS`
key. `lens_coverage`'s CLI surface, flags and JSON shape are unchanged — merged mode is detected
from the files, not from an argument, which is what keeps an un-re-rendered harness working
(ADR-003).

**Design decisions.** Grouping lives in `conditional_router` because it already owns the lens
vocabulary and `lens_coverage` already imports from it (ADR-005, default A3). The group file is
`core.json`; `core` is not a member of `ALL_LENSES`, so the stem check cannot confuse a group
file with a lens file (default A2). The dispatch description names all four lenses rather than a
bare `core`, so a transcript or ledger reader can see what ran (default A4).

## 📝 Implementation Plan

### Phase 1 — `lens_dispatch_groups` and its Jinja global

**Status: GREEN (2026-09-13)** — `tests/unit/test_lens_dispatch_groups.py` 23/23; `ruff check`,
`ruff format --check` and `mypy --strict` clean on all three touched files. A.5 took two rounds
(round 1 FAIL on one blocking issue, round 2 PASS; ledger `rlfm-p1`). C.0 and D.5 skipped: pure
new-feature work — a constant and two functions added beside the existing ones, no defect repaired
and no existing behaviour changed, so there is no repair to declare and no newly-reachable window.

**Deviation from the written scope, for the better.** The PLAN had Phase 3 rebind
`{% set lenses = ... %}` to the group list, which is what made risk R14 (`{{ lenses | length }}`
silently rendering "4 lenses" against Step 1's seven) real. Phase 1 instead **adds** a `groups`
binding beside the untouched `lenses` one, so `lenses | length` stays 7 and the count sentences
become "N lenses as M dispatches". R14 is designed out rather than patched; Phase 3's scope-in
entry for the two count expressions stands, its exit-criterion assertion still applies.

**The `lens_coverage` seam is a constant, not a second function.** `LENS_GROUPS` maps the
result-file stem to the lenses it vouches for, `lenses_for_result_file(stem)` is its only reader,
and restoring the fan-out is `{lens: (lens,) for lens in ALL_LENSES}` — one dict literal. ADR-005's
"one function" is in practice one constant, which is stronger.

- **depends_on:** `[]`
- **parallel_group:** `serial-1`
- **merge_hazards:** none
- **Scope in:** `src/harness_maker/conditional_router.py`,
  `src/harness_maker/template_globals.py`, `tests/unit/test_lens_dispatch_groups.py`
- **Scope out:** `CORE_LENSES`, `DOMAIN_LENSES`, `ALL_LENSES`, `KNOWN_LENSES`,
  `MANDATORY_LENSES`, `lens_dispatch()`, `mandatory_lenses()`, `routable_lenses()`,
  `LENS_DISPATCH` — all unchanged.
- **Exit criterion:**
  `uv run pytest tests/unit/test_lens_dispatch_groups.py -q` green **and**
  `uv run mypy --strict src/harness_maker/conditional_router.py src/harness_maker/template_globals.py`
  clean **and** `uv run python -c "from harness_maker.conditional_router import lens_dispatch; assert len(lens_dispatch('Production')) == 7 and len(lens_dispatch('Side')) == 7"`
- **Risk:** low
- **Rollback point:** base HEAD (nothing consumes the new function yet)

### Phase 2 — `lens_coverage` merged mode

**Status: GREEN (2026-09-13)** — `tests/unit/test_lens_coverage_merged.py` 11/11 plus the
pre-existing `tests/unit/test_lens_coverage.py` with no regression; `ruff`, `ruff format` and
`mypy --strict` clean. Regression set `tests/unit` + `tests/structural`: **rc=0, 7111 passed,
13 skipped, 3 xfailed, zero F/E**. A.5 PASS in one round (ledger `rlfm-p2`). C.0 and D.5
skipped — new capability added to a reader, no defect repaired.

**The diff is smaller than the ADR implies.** `exercised_lenses` lost its `known = set(ALL_LENSES)`
line and its `found.add(stem)`, and gained `members = lenses_for_result_file(stem)` /
`found.update(members)`. Every existing check — parses, is a dict, `lens == stem`, `run_id`
matches — is untouched and now applies to a group file exactly as it did to a per-lens one. The
fail-closed property is therefore inherited rather than re-implemented, which is why AC-006's five
corruption classes passed before the change and still pass after it.

**A.5 corrected the A.4 justification, and the correction is recorded in the test file.** The
first draft claimed all seven pre-passing tests were vacuous for one reason;
`test_four_per_lens_files_still_cover_the_core_set` never writes `core.json` and pre-passes
through the existing per-lens path instead. It is kept — it is the only witness that an
implementation routing solely through `LENS_GROUPS` membership would fail — but the prose was
wrong and now says so.

- **depends_on:** `[1]` — imports the group vocabulary Phase 1 defines
- **parallel_group:** `parallel-b`
- **merge_hazards:** none on file ownership — `lens_coverage.py` is touched by no other phase.
  **But Phase 2 and Phase 3 must not land without each other**: a template writing `core.json`
  against the old reader leaves every core lens permanently `missing`, which is the unapprovable
  review AC-002's note is about. In this repo a task lands as one squash commit (`task-land`), so
  the hazard is latent rather than live — written down rather than relied upon.
- **Scope in:** `src/harness_maker/lens_coverage.py`, `tests/unit/test_lens_coverage_merged.py`
- **Scope out:** `coverage_verdict`'s signature and return keys, `round_dir`'s containment check,
  the CLI's flags, `mandatory_lenses`' role as the required set.
- **Exit criterion:** `uv run pytest tests/unit/test_lens_coverage_merged.py tests/unit/test_lens_coverage.py tests/unit/test_review_input_boundaries.py -q`
  green — covering SPEC AC-004 (`test_one_core_file_covers_the_four_core_lenses`), AC-005
  (`test_exercised_names_the_core_lenses_not_the_group`), AC-006
  (`test_merged_mode_is_fail_closed_on_every_bad_file`), and — **named, not left as prose** —
  AC-004's backward-compatibility clause as
  `test_lens_coverage_merged.py::test_four_per_lens_files_still_cover_the_core_set`.
  The SPEC's Verification Criteria row for AC-004 names only the merged test, so its third
  **And** had no witness; this PLAN supplies one without needing a SPEC change.
- **Risk:** medium — a fail-open here vouches for four lenses at once instead of one.
- **Rollback point:** end of Phase 1

### Phase 3 — the two dispatch blocks in `review.md.j2`

**Status: GREEN (2026-09-13), after four A.5 rounds and two user overrides.** Ledger `rlfm-p3`,
passes 1-4 (FAIL / FAIL / FAIL / PASS). `tests/render/test_render_review_lens_groups.py` 36/36;
the three migrated files 81/81; `tests/unit/test_synthesize_snapshot.py` 12/12 after regeneration.
Whole-repo `ruff check` clean, 690 files formatted, `mypy --strict` clean on 687 files. C.0 and
D.5 skipped — new capability, no defect repaired.

**Ten template edits**, all in `review.md.j2`: the `groups` binding beside the untouched `lenses`
one; Step 1's axis paragraph; Step 3's count sentence and the claim it replaces; both dispatch
blocks; both result-file listings; the ADR-007 two-level stamp instruction; Step C2's heading; and
the Auto-Fix Loop re-dispatch wording, where R13's decision is now written out (a `missing` member
lens re-dispatches its whole group and writes the group file). **A singleton group renders
byte-identically to the pre-merge form**, so the three domain dispatches have a zero diff and only
the core one changed.

**Snapshot regeneration behaved exactly as the newer memory predicts and the older `failures.md`
entry does not.** Eight files, two `body_sha256` each, sixteen lines — no other template moved. A
worktree path leaking through `_HARNESS_MAKER_PKG_ROOT`, which is what
`[fail:test] snapshot-regen-inside-worktree` (count:13) describes, would have changed every hash in
every file. `regenerate.py:105-124` pins that constant, `_compute_install_ref` and `HOME`. The
disappearing hashes match the two the plan-validator cited, confirming the right entries moved.

**A.5 cost four rounds; three of them were mine.** Round 1 found three template edits this PLAN
put in scope with no test authored. Rounds 2 and 3 were two attempts to make a regex adjudicate
whether a sentence about dispatch grouping is *true* — which CLAUDE.md's first principle forbids,
and which the reviewer broke from both sides: an evading wording (`"every lens receives its own
invocation"`) and an over-broad alternative that would false-RED a correct paragraph naming the
domain-lens exception. Round 4 passed only after the test was narrowed to what is mechanically
decidable and the truth question was filed as **R15**.

- **Round 1 FAIL** — `blocking_issues: []`, three `scenarios_missing`: Step C2's own
  `{{ lenses | length }}` count sentence, Step 1's axis paragraph, and the stale
  "one dispatch per lens" claim at `review.md.j2:208-210`. All three were template edits this
  PLAN put in scope and for which no test was authored. Three tests added.
- **Round 2 FAIL** — `scenarios_missing: []`, one blocking issue, category `tautology`, against
  a test authored in round 1: `test_step_3_no_longer_claims_one_dispatch_per_lens` is
  **negative-only**. It forbids two exact strings and requires no correct replacement in the
  same span, so a CODER who deletes the banned phrases and writes a differently-worded but
  equally false description of the grouping passes it. The paired positive assertion lives in
  `test_the_count_sentence_agrees_with_the_axis`, over a *different* sentence, so the two never
  constrain one span jointly. The reviewer's words: "a rewritten defect reads GREEN."

**The two rounds did not fail on the same defect** — round 1 was missing coverage, round 2 was a
flaw in the coverage added to answer it. The retry budget is nevertheless spent, and the stage
contract makes that a blocked phase rather than a third round.

**Round 3 granted by user override on 2026-09-13** (escalation Path A, `stuck` recommendation
accepted). The budget rule's trigger/justification mismatch is filed as a follow-up below.

> **Follow-up task, filed here rather than lost:** A.5's termination is coded as `rounds == 2`
> (`execute.md.j2:344`) while the sentence beside it justifies the cap as *"the defect list a
> lens-level rewrite already failed twice to fix"*. Those are different predicates and only the
> first is implemented, so the cap fires on a converging loop — which is what happened here.
> This repository already ships the correct predicate for the structurally identical problem:
> `/hm:review`'s Auto-Fix Loop terminates on a **monotone lattice plus one no-progress round,
> evaluated at round ≥ 2** (CLAUDE.md, PIDA section), explicitly because round 1 has no fix
> stage. Moving A.5 onto that predicate is a one-phase unit and is **not** in this task's scope.

**Round 3 repair** — `test_step_3_no_longer_claims_one_dispatch_per_lens` became
`test_step_3_describes_its_own_grouping_correctly`. Two changes, both answering the round-2
finding: the positive (`N lenses as M dispatches`) and the negative now share **one paragraph**
via a new `_paragraph()` extractor, because in the template the count expression and the false
claim are the same paragraph (`review.md.j2:208-210`); and the negative became a claim
**pattern** (`_PER_LENS_CALL`) rather than two literal strings, because deleting two strings and
rewording the same false claim was exactly the evasion the reviewer demonstrated.

> A correction to the round-2 finding, verified at source before acting on it: its `observe`
> said the positive assertion lived over "a different, independently-rendered sentence". That is
> true of the Step C2 instance only — `test_the_count_sentence_agrees_with_the_axis` is
> parametrized over both sections, so its Step-3 instance already read the same section. The
> real gap was narrower: same section, different paragraph. The finding stands; its stated
> mechanism was imprecise, and the fix is smaller than it implied.

**`[boundaries] comparison not performed — blocked exit`** for this phase. Phase 1 and Phase 2
edits exist on disk and are green; nothing in Phase 3's scope was touched.

- **depends_on:** `[1]`
- **parallel_group:** `parallel-b`
- **merge_hazards:** none against Phase 2 on file ownership, but **neither may land without the
  other** (see Phase 2). **Serial against Phase 4**, which re-freezes the baseline computed from
  this template's output.
- **Scope in — the template:** `src/harness_maker/templates/stages/review.md.j2`
  - Step 3's dispatch block and its result-file path listing; Step C2's dispatch block and its
    path listing; the `{% set lenses = ... %}` binding.
  - Step 1's "told apart only by the lens line in their brief" sentence (`:134` region).
  - **The two rendered count expressions** — `:208` `Dispatch the {{ lenses | length }} lenses`
    and `:973` `Step C2 — Dispatch all {{ lenses | length }} lenses`. Rebinding `lenses` to the
    group list silently turns both into "4 lenses" while Step 1 — which renders from the separate
    `lens_names = mandatory_lenses(config.preset)` binding — still enumerates seven. The command
    would contradict itself about the size of its own axis. Render them as *N lenses as M
    dispatches*, driven off `lens_names | length` and the group count.
  - **The result-file writing instruction** that today reads "stamp the same `lens` value on
    every finding inside it" — it must become the two-level contract of [ADR-007](#adr-007), or
    the merged file stamps `core` on every finding and destroys exactly the provenance the
    paragraph beneath it says the stamp exists for.
  - **The Auto-Fix Loop re-dispatch paragraph (`:758-760`) and the coverage-blocker paragraph
    (`:744-752`).** Under merged mode `missing` names *member lenses* while the dispatch unit is a
    *group*, so "re-dispatch the lenses the previous check named in `missing`" no longer says what
    to run or where to write it — re-run the group into `core.json`, or dispatch a single-lens
    `code-reviewer` into `design.json`? Both satisfy coverage, so the ambiguity is silent. Decide
    it in the rendered text: **a `missing` member lens re-dispatches its whole group and writes
    the group file.** This is the "reads fine, cannot be followed" class this phase's Risk line
    names.
- **Scope in — the tests.** The migration set was enumerated mechanically
  (`rg -n '\{lens\}\.json|lens \(\[a-z\]\+\)' tests/`), not by recall — naming only the first
  file found is what made the earlier revision incomplete:
  - `tests/unit/test_render_lens_axis.py` — `_dispatched`'s regex (`:59`) and
    `test_both_sites_write_a_result_file_per_lens` (`:181`).
  - `tests/unit/test_render_lens_dispatch.py` — `test_each_mandatory_lens_is_dispatched_not_merely_named`
    (`:207`), parametrized over the four core lenses against the round-1 block.
  - `tests/unit/test_render_confirmation_pass.py` — `test_the_pass_dispatches_every_mandatory_lens`
    (`:224`), the same assertion against Step C2.
  - `tests/snapshot/*.expected.yaml` — **eight** fixture files, each pinning `body_sha256` for
    `commands/hm/review.md` and `stages/review.md`. `tests/snapshot/EXCLUSIONS.md`'s active list
    is **empty**, so `review.md` is not exempt and `tests/unit/test_synthesize_snapshot.py` goes
    red on every edit to this template.
  - New: `tests/render/test_render_review_lens_groups.py`,
    `tests/render/test_render_review_lens_groups.py` (AC-008's no-literals assertion lives here
    as `test_no_lens_text_is_a_literal_in_the_template`; the separate structural file this PLAN
    originally named was never created, and `/hm:review`'s drift gate caught the dangling path).
- **Scope out:** the `<run-id>` minting prose; Step 4's tag table; Step 3.4–3.7 (cross-model
  PIDA); the 2-pass redaction gate, which keys on `reviewers.enabled | length`; the rationale
  paragraph *underneath* the stamp instruction, which stays verbatim — only the instruction
  itself moves; `tests/snapshot/EXCLUSIONS.md`, which stays empty (exempting `review.md` to dodge
  the regeneration would silence the fixture for every future change too).

  **Dispatch description format**, fixed here so the regex migration is deterministic: a
  singleton group keeps today's `description="lens <name>: {slug}"`; a multi-lens group renders
  `description="lenses <a>+<b>+<c>+<d>: {slug}"`. The migrated regex is
  `description="lens(?:es)? ([a-z+]+): \{slug\}"` with the capture split on `+`, so
  `_dispatched` still returns a set of lens names and `_expected_dispatch` needs no change.

  **Constraint on the accountability line.** `tests/unit/test_render_lens_dispatch.py:458`
  forbids `write\s+(your|the result|it to|to \S+/)` inside any `Task(` fence — the main loop owns
  result files, not the agent. AC-003's "accountability line naming all four lenses" must
  therefore be phrased without a write verb.
- **Exit criterion**, in order:
  1. `uv run python tests/snapshot/regenerate.py` **from this worktree** — the stored memory
     `project_snapshot_regen_in_worktree_is_correct` applies; running it from base regenerates
     hashes for templates this task never touched.
  2. `uv run pytest tests/render/test_render_review_lens_groups.py tests/unit/test_render_lens_axis.py tests/unit/test_render_lens_dispatch.py tests/unit/test_render_confirmation_pass.py tests/unit/test_render_dispatch_macro.py tests/structural/test_no_claude_tool_calls_in_codex_output.py tests/unit/test_synthesize_snapshot.py -q`
     green — covering SPEC AC-001 (exactly one `code-reviewer` dispatch, four total), AC-002
     (Step C2 groups equal round 1's, every preset × target arm), AC-003 (all four
     `LENS_DISPATCH` brief strings byte-identical, plus a write-verb-free accountability line),
     AC-008 (no literal lens text in either block), every migrated test above, and the
     regenerated snapshots.
  3. Two assertions the new render test carries that no SPEC AC does: the rewritten stamp
     instruction **names the four admissible per-finding values** (ADR-007 has no backing AC —
     without this it is a prose-inspection item while every other criterion has a test), and the
     round-1 block's stated lens count equals
     `len(mandatory_lenses(preset)) + len(routable_lenses(preset))`.
  4. **The counterfactual restoration test**: with the grouping global swapped for seven
     singleton groups, the render must produce seven dispatches, seven `<lens>.json` paths in
     both blocks and seven `lens <name>:` descriptions. Without it, a template that hard-codes
     "four groups" passes parity and no-literals while ADR-005's one-function-restores-it claim
     is false.
- **Risk:** medium — a rendered instruction that reads fine and cannot be followed is this
  repository's recurring defect class.
- **Rollback point:** end of Phase 1


### Phase 4 — re-freeze the two baseline artifacts together

**Status: GREEN (2026-09-13).** Peer-allowance gate asserted as a command first —
`load_active_allowances(Path("."))` returned `NONE`. Round-trip budget `review` 39 → 33, matching
the PLAN's prediction exactly. `surface_baseline.json` re-frozen at `9ea26255f3c4`:
`claude/review` 86 171 → 85 795 chars, `codex/hm-review` 82 433 → 82 191, both round-trip entries
39 → 33 and 34 → 28, plus `aggregate_chars`, `payload_digest` and `render_sha`.
`work-docs/BASELINE-DELTA-reviewer-lens-fanout-merge.md` carries a row per changed key;
`test_baseline_delta_attribution.py` 7/7.

**The codex arm grew before it shrank, and that is worth reading.** The counting rule charges a
dispatch differently per variant — claude renders `Task(subagent_type=, description=, prompt=)`,
codex renders `spawn_agent(agent_type=, message=)` with **no description** — so deleting three
dispatches saves less on codex while the added prose costs both arms alike. The first render put
codex **+106 chars** over the Phase 0 aggregate with a 0-char allowance. Taking a
`surface_allowance` would have contradicted this phase's own re-freeze precondition, so the prose
was trimmed instead. The trim also fixed a latent template bug: the stamp instruction enumerated
the core lens names through a `selectattr` chain over all seven lenses, using `loop.last` from
that outer loop to separate four names — the wrong loop. Iterating the merged group directly is
shorter and correct.

**Five unlisted migration targets surfaced during this phase and Phase 3**, none of them found by
the cross-model second opinion, the plan-validator, or the PLAN's own mechanical `rg` enumeration:
`tests/unit/test_render_lens_axis.py`, `tests/unit/test_render_lens_dispatch.py`,
`tests/unit/test_render_confirmation_pass.py` (these three WERE listed),
`tests/structural/test_no_claude_tool_calls_in_codex_output.py`'s positive control (counts
`spawn_agent(` occurrences — invisible to an `rg` for `{lens}.json`),
`tests/structural/test_instruction_preservation.py`'s removal allowlist, and
`tests/structural/autopilot_gate_golden.json`. **The enumeration in R10 was still incomplete after
two rounds of external review**; what actually found the rest was running the full structural
suite.

- **depends_on:** `[2, 3]`
- **parallel_group:** `serial-4`
- **merge_hazards:** **`tests/structural/surface_baseline.json` is shared with every other
  in-flight task in this repository.** A whole-file re-freeze absorbs any peer's unlanded surface
  growth. Before touching it, confirm `load_active_allowances` returns none — this precondition
  is what forced a revert on 2026-09-12. Also serial against Phase 3 by construction: the
  baseline is computed from Phase 3's render.
- **Scope in:** `tests/structural/test_roundtrip_budget.py` (the `review` entry, 39 → 33, with a
  note naming the merge), `tests/structural/surface_baseline.json`,
  `work-docs/BASELINE-DELTA-reviewer-lens-fanout-merge.md`
- **Scope out:** every other command's budget entry; the ratchet mechanism itself; the
  `surface_allowance` machinery.
- **Exit criterion**, in order:
  1. **The peer-allowance gate, as a command rather than a sentence** —
     `uv run python -c "from pathlib import Path; from harness_maker.surface_allowance import load_active_allowances; a = load_active_allowances(Path('.')); assert not a, a"`.
     A prose-only precondition on the highest-impact row in the register, with a revert
     precedent eight days old, is a choice and not a constraint; the function is trivially
     callable (`surface_allowance.py:107`).
  2. `uv run pytest tests/structural/ -q` green — including `test_roundtrip_budget.py`,
     `test_surface_allowance.py` and `test_baseline_delta_attribution.py`, the last of which
     requires each changed key's **parent segment backticked** (`` `review` ``, not the full
     dotted key).
- **Risk:** high — exact-match with no ratchet, on a file other sessions also write.
- **Rollback point:** end of Phase 3

## ✅ Execute outcome (2026-09-13)

All four phases GREEN. **No commit made** — HEAD is still the base tip `9ea26255`; wrapup owns it.

Four gates, exit codes recorded rather than inferred: `ruff check` clean, 690 files formatted,
`mypy --strict` clean on 689 source files, `pytest` **rc=0 — 7524 passed, 89 skipped, 3 xfailed,
zero F/E**.

**Boundary comparison: 30 changed paths, ZERO crossings.** The five path entries
(`review_consensus.py`, `codex_adapter.py`, `models.py`, `execute.md.j2`,
`tests/snapshot/EXCLUSIONS.md`) are absent from the changed set. The `conditional_router`
advisory was checked **mechanically, not by assertion** — an AST comparison of `CORE_LENSES`,
`DOMAIN_LENSES`, `ALL_LENSES`, `KNOWN_LENSES`, `MANDATORY_LENSES`, `LENS_DISPATCH`,
`lens_dispatch()`, `mandatory_lenses()` and `routable_lenses()` against `HEAD` shows every one
identical. That file changed; the boundary was its symbols, and this task only added beside them.

**Six unlisted migration targets, and what actually found them.** Three were named in the PLAN
(`test_render_lens_axis.py`, `test_render_lens_dispatch.py`, `test_render_confirmation_pass.py`).
Three were not: `test_no_claude_tool_calls_in_codex_output.py` (counts `spawn_agent(`
occurrences), `test_instruction_preservation.py` (compares heading SETS),
`test_render_dispatch_macro.py` (a frozen payload plus a `Your lens:` extractor), and
`autopilot_gate_golden.json` (a SHA-256 byte lock). **R10's `rg -n '\{lens\}\.json|lens
\(\[a-z\]\+\)' tests/` cannot match any of them** — each couples to the lens fan-out through
vocabulary that never mentions a lens. What found them was running the full structural suite.
R10's "was certain, now mitigated" label was therefore optimistic, and the honest generalization
is: **a mechanical enumeration is only as complete as the vocabulary it greps for; the full suite
is the enumeration.**

**A consistent repo pattern showed up three times:** frozen artifacts here ship with a
*registered-exception* escape hatch rather than a regenerate path. `test_instruction_preservation`
has `_ALLOWED_REMOVALS`; `test_render_dispatch_macro` has `_COLLAPSED_MULTILINE`, which already
held three entries from Phase A.5's identical three-lenses-into-one collapse — this task added
four for the same move one stage over. Each time the correct response was to register the change
with a reason, never to regenerate. `autopilot_gate_golden.json` was the one artifact with no such
hatch, which is why it needed a user decision (see Phase 3's status block and the re-capture list
now recorded in that test's docstring).

## 🚧 Contract Boundaries

### Do not change

- Advisory: inside `conditional_router`, the constants `CORE_LENSES`, `DOMAIN_LENSES`,
  `ALL_LENSES`, `KNOWN_LENSES`, `MANDATORY_LENSES` and the functions `lens_dispatch()`,
  `mandatory_lenses()`, `routable_lenses()` keep their current signatures and return values —
  `lens_coverage` derives the required set from them, and SPEC AC-008 asserts `lens_dispatch()`
  still returns one entry per lens.
- Advisory: `exercised` must keep naming the individual core lenses and must never contain
  `core`, so `review_telemetry`'s `lenses_exercised` stays comparable with rows written before
  this change (ADR-004).
- Advisory: `coverage_verdict`'s fail-closed property is absolute — a file that cannot be read,
  parsed, or attributed contributes nothing, and a group file vouching for four lenses makes a
  fail-open four times as costly (SPEC AC-006).
- `src/harness_maker/review_consensus.py` — the solo-lens vote and the tag table are out of
  scope; one lens still votes alone. (That rule is ADR-007 of the *nine-lens* work — a different
  document from this PLAN's [ADR-007](#adr-007), which is about finding stamps.)
- `src/harness_maker/codex_adapter.py` — `lens` must not become an input to `finding_id`; the
  round-to-round merge key stays unchanged.
- `src/harness_maker/models.py` — no `harness.yaml` schema change; this unit adds no config key
  (ADR-005).
- `src/harness_maker/templates/stages/execute.md.j2` — Phase A.5 is the precedent for this work,
  not a target of it.
- `tests/snapshot/EXCLUSIONS.md` — the active exclusion list stays empty. Exempting `review.md`
  would make `test_synthesize_snapshot.py` pass without regenerating, and would silence that
  fixture for every future change to the file as well.
- Advisory: no lens brief may contain a write verb matching
  `write\s+(your|the result|it to|to \S+/)` inside a `Task(` fence — the main loop owns result
  files, and `tests/unit/test_render_lens_dispatch.py:458` enforces it. The ADR-007
  accountability line must be phrased around it.

## 🧪 Testing Strategy

**Unit** (`tests/unit/`) — `test_lens_dispatch_groups.py` covers the grouping function on both
presets and asserts `lens_dispatch()` is unchanged beside it; `test_lens_coverage_merged.py`
covers SPEC AC-004/005/006 plus the backward-compatible per-lens-file case.

**Render** (`tests/render/`) — `test_render_review_lens_groups.py` renders `/hm:review` across
preset × target and asserts the dispatch count, the round-1 ↔ Step-C2 group equality, and the
byte-identical survival of the four briefs. The brief comparison reads `LENS_DISPATCH` directly,
so the render is checked against a different module rather than against a copy of itself. It also
carries the **counterfactual restoration test** — render with the grouping global replaced by
seven singleton groups, and assert the full fan-out comes back: dispatch count, descriptions, and
per-lens result paths. Parity plus no-literals cannot detect a block that silently depends on the
group count; only this test can.

**Migrated** (`tests/unit/test_render_lens_axis.py`) — it keeps asserting the axis, against the
new contract: `_dispatched` learns the `lens(?:es)?` description form and splits the capture on
`+`; the per-lens result-file assertion becomes a per-**group** assertion. `_expected_dispatch`
and `mandatory_lenses` are untouched, so the test still fails if a lens leaves the axis.

**Structural** (`tests/structural/`) — AC-008's no-literals assertion is
`test_render_review_lens_groups.py::test_no_lens_text_is_a_literal_in_the_template`, which asserts the
template carries no literal lens text in either block (SPEC AC-008);
`test_roundtrip_budget.py` / `test_surface_allowance.py` / `test_baseline_delta_attribution.py`
gate Phase 4.

**Manual** — none required. The live behaviour this changes (a review round actually running
four dispatches instead of seven) is observed the next time `/hm:review` runs on this repository,
and by design there is no oracle for its yield (ADR-001).

**Property emphasis.** Three of the eight ACs are `type: property` — Step-C2 parity, merged-mode
fail-closure, and the no-literals rule — because each must hold for *any* grouping the function
returns, including a restored fan-out. A test that hardcoded today's grouping would pass a wrong
implementation of the reversal.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | The merge loses real findings, invisibly. | medium | high | **Accepted, not mitigated** (ADR-001). Recorded in the SPEC Intent, this ADR, and CHANGELOG at wrapup. The nearest measured point (11.0 vs 30.0) is cited so a later reader can reopen it with the right number in hand. |
| R2 | A fail-open in merged mode vouches for four lenses at once. | low | high | SPEC AC-006 states fail-closure over the whole class of non-conforming files, not five enumerated cases, so a special-cased implementation fails a sixth. Phase 2's exit criterion runs it. |
| R3 | Round 1 and Step C2 drift, making every review permanently unapprovable. | low | high | Structural, not conventional: both blocks loop over one function, and AC-002 + AC-008 assert it from opposite directions (equality of output, absence of literals in source). |
| R4 | Two downstream SPECs carry lens-dispatch sentences that this change makes wronger. | certain | low | **Accepted** (ADR-006). `SPEC-review-loop-empirics` AC-009 and `SPEC-ai-review-exit-criteria`'s "five mandatory lenses … in parallel" were already stale from the 6→4 and 5→7 changes. Waiver is diff-hash-bound and will re-ask if the diff moves. |
| R5 | A future implementation of `SPEC-lens-and-review-fix-verification` AC-004 (`unstamped`) marks every merged finding unstamped. | low | medium | That AC is `pending_test: true` and unimplemented today. Recorded in ADR-006 with the required scoping ("the file's lens" means the group's member lenses). |
| R6 | The Phase 4 baseline re-freeze absorbs a peer session's unlanded surface growth. | medium | high | **Half mechanical, half judgement — stated as such.** Mechanical: Phase 4's exit criterion step 1 asserts `load_active_allowances(Path('.'))` is empty, so a live peer allowance fails the phase rather than being noticed in prose. Judgement: nothing detects a peer that will *start* an allowance between the assert and the commit. Corrected precondition from `BASELINE-DELTA-workflow-steps-vs-model-capability`, not ADR-006 of that PLAN. |
| R7 | The merged dispatch is implemented as a templated `<lens>` placeholder. | low | medium | Forbidden by the SPEC Constraints table with the revert precedent cited. AC-003's byte-identical brief check plus AC-008's no-literals check together force one literal dispatch carrying four literal questions. |
| R8 | Wall-clock gets *worse*, because one agent now does four examinations serially inside its own context. | medium | low | Stated in ADR-001 rather than mitigated. The claim this unit makes is about tokens, not latency; no latency exit criterion is asserted anywhere. |
| R9 | The merged agent stamps the group name on a finding instead of the member lens, silently ending the solo-lens vote. | medium | high | ADR-007 splits the two levels and the rewritten instruction names the four admissible per-finding values. **Residual, stated rather than claimed covered:** nothing mechanically rejects a `core`-stamped finding — it stays a review-time catch. |
| R10 | Shipped tests encoding the one-result-file-per-lens contract are left to fail, making full-suite green unreachable at Phase 3's exit. | was certain, now mitigated | high | The migration set is enumerated **mechanically** (`rg -n '\{lens\}\.json\|lens \(\[a-z\]\+\)' tests/`) rather than by recall: `test_render_lens_axis.py`, `test_render_lens_dispatch.py:207`, `test_render_confirmation_pass.py:224`. Phase 3's exit criterion runs all three. **Two rounds of external review were needed to close this** — codex found the first file, the plan-validator found the other two and called the first fix an incomplete inventory. |
| R12 | Eight `tests/snapshot/*.expected.yaml` fixtures pin `body_sha256` for the two rendered review files; nothing regenerates them. | was certain, now mitigated | high | `tests/snapshot/EXCLUSIONS.md`'s active list is empty, so `review.md` is not exempt. Phase 3's exit criterion step 1 runs `tests/snapshot/regenerate.py` **from the worktree** (stored memory `project_snapshot_regen_in_worktree_is_correct`), and step 2 runs `test_synthesize_snapshot.py`. Exempting `review.md` instead is explicitly out of scope — it would silence the fixture for every future change. |
| R13 | The Auto-Fix Loop's "re-dispatch the lenses named in `missing`" becomes ambiguous: `missing` names member lenses, the dispatch unit is a group, and both readings satisfy coverage. | was certain, now decided | medium | Phase 3 scope-in fixes the rendered wording: a `missing` member lens re-dispatches its **whole group** and writes the **group file**. Residual: no test asserts the resolved wording — it is prose in a rendered command, and the coverage CLI accepts either reading, so nothing mechanical can tell them apart. |
| R14 | `{{ lenses \| length }}` at `:208` and `:973` silently renders "4 lenses" while Step 1 enumerates seven, so the command contradicts itself about its own axis size. | was certain, now mitigated | medium | Both expressions are in Phase 3's scope-in with the decided rendering (*N lenses as M dispatches*), and exit-criterion step 3 asserts the stated lens count equals `len(mandatory_lenses(preset)) + len(routable_lenses(preset))`. |
| R15 | Newly-written Step 3 / Step 1 prose is false about the grouping in words no test forbids. | medium | medium | **Accepted residual, not mitigated.** Three A.5 rounds established that a regex cannot adjudicate this: a keyword catalogue is enumerable-around (the reviewer produced `"every lens receives its own invocation"`, evading six alternatives while asserting the banned claim) and simultaneously over-broad (`its own dispatch` is a *correct* statement about the three domain lenses). CLAUDE.md's first principle forbids the attempt. The tests now assert only what is mechanically decidable — the paragraph states the router-derived `N lenses as M dispatches`, and neither pre-merge string survives in that same paragraph. **Whether new prose is TRUE is a `/hm:review` question**, the same treatment R13 gives the auto-fix re-dispatch wording. |
| R11 | Both dispatch blocks silently depend on the group count, so ADR-005's one-function reversal is false while every test passes. | medium | medium | The counterfactual restoration test in Phase 3's exit criterion renders with seven singleton groups and asserts the fan-out returns in full. |

## ✅ Success Criteria

- [x] AC-001 — round 1 sends exactly one `code-reviewer` dispatch, four total, on both presets and both call forms
- [x] AC-002 — Step C2's groups equal round 1's, element for element, on every render arm
- [x] AC-003 — all four `LENS_DISPATCH` briefs appear byte-identically, plus an accountability line naming all four
- [x] AC-004 — one `core.json` plus three domain files yields `missing: []`; four per-lens files still do too
- [x] AC-005 — `exercised` names the four core lenses individually and never contains `core`
- [x] AC-006 — all five non-conforming `core.json` classes leave every core lens in `missing`, `blocks_approval: true`
- [x] AC-007 — `review` round trips are 33 in the budget table, in the live render, and in `surface_baseline.json`, with a BASELINE-DELTA attribution row per changed key
- [x] AC-008 — neither dispatch block contains a literal lens name, agent name or brief; `lens_dispatch()` still returns one entry per lens
- [x] **ADR-007 (no SPEC AC backs this — added after the SPEC was approved)** — the rendered
      instruction states both levels: file-level `lens` is the group id, per-finding `lens` is the
      member lens, with the four admissible values named
- [x] **Counterfactual restoration** — rendering with seven singleton groups reproduces the full
      fan-out (dispatches, descriptions, per-lens result paths)
- [x] `test_render_lens_axis.py`, `test_render_lens_dispatch.py` and `test_render_confirmation_pass.py` all migrated and green — not deleted, not xfailed
- [x] Eight `tests/snapshot/*.expected.yaml` regenerated **from the worktree**; `test_synthesize_snapshot.py` green; `EXCLUSIONS.md` still empty
- [x] AC-004's backward-compatibility clause has a named witness: `test_four_per_lens_files_still_cover_the_core_set`
- [x] Phase 4's peer-allowance assert ran and passed before the baseline was touched
- [x] `uv run ruff check`, `uv run ruff format --check`, `uv run mypy --strict src tests`, `uv run pytest` all green
- [x] CHANGELOG entry records the merge **and** the unmeasured-yield trade

## 🔍 Plan Validation

**Passes run: 1.** Pass 2 and the Step 4.5 terminal re-validation were **deliberately skipped** —
the user's standing instruction for this repository is that `plan-validator` runs once and the
PLAN is not re-validated after revision. The cost is explicit: **nothing has read the revised
document.** Every critique below was resolved by editing the PLAN, and those edits are themselves
unreviewed. The findings they answer move downstream to `/hm:execute` Phase A.5 and `/hm:review`.

**Cross-model second opinion — `codex`, `status: invoked`, 54 s.** Three findings, all
`accepted` by the validator's reconciliation, all verified at source before acceptance.

| id | sev | Finding | Resolution |
|---|---|---|---|
| `da5d7ffa626388fd` | P1 | The existing "stamp the same `lens` value on every finding" instruction stamps `core` on everything under merged mode, destroying the provenance the paragraph beneath it exists for. | **[ADR-007](#adr-007)** splits the file-level group id from the per-finding member lens; the instruction moved from Phase 3 scope-**out** to scope-**in**. Validator's residual — "a prose-inspection item with no named test" — is closed by Phase 3 exit-criterion step 3. |
| `d5f0299eadc95590` | P1 | Existing fan-out tests are not migrated, so full-suite green is unreachable. | First fix named **one** file; the validator called that an incomplete inventory and found two more. Migration set now enumerated mechanically by `rg`. **R10.** |
| `e421aa33284ae110` | P2 | No counterfactual test backs ADR-005's "change one function to restore it". | Seven-singleton-group restoration test in Phase 3 exit-criterion step 4, Testing Strategy, and **R11**. Validator: "fully resolved". |

**`plan-validator` pass 1 — `MAJOR_REVISION`.** Eight critiques; all resolved in the document.

| # | Sev | Section | Finding | Resolution |
|---|---|---|---|---|
| 1 | critical | Technical Design; Phase 3 | Eight `tests/snapshot/*.expected.yaml` pin `body_sha256` for both rendered review files and `EXCLUSIONS.md`'s active list is empty — nothing regenerated them. | Snapshot row added to Affected components; regeneration is Phase 3 exit-criterion **step 1**, from the worktree; `EXCLUSIONS.md` added to Contract Boundaries so exempting `review.md` is not the escape. **R12.** Verified at source before accepting. |
| 2 | critical | Phase 3; Testing Strategy; R10 | The migration set was one file by recall; `test_render_lens_dispatch.py:207` and `test_render_confirmation_pass.py:224` encode the same contract. | Set enumerated by `rg`, all three named with their line numbers, all three in the exit criterion. The adjacent write-verb guard at `test_render_lens_dispatch.py:458` is now a Contract Boundary. Verified at source. |
| 3 | warning | Phase 3 scope; Contract Boundaries | The Auto-Fix Loop re-dispatch (`:758-760`) and coverage-blocker (`:744-752`) paragraphs change meaning under merged mode and were in neither list. | Both in scope-in with the decision written out: a `missing` member lens re-dispatches its whole group and writes the group file. **R13**, with the residual stated — no test can tell the two readings apart. |
| 4 | warning | Phase 4; R6 | R6 was labelled mitigated by a precondition that had no command and no exit criterion, while every other accepted risk is honestly labelled "stated, not mitigated". | Promoted to a runnable assert as Phase 4 exit-criterion step 1; R6 relabelled to name which half is mechanical and which is judgement. |
| 5 | warning | Phase 3 scope | `{{ lenses \| length }}` at `:208` and `:973` would render "4 lenses" while Step 1 enumerates seven. | Both expressions in scope-in with the decided rendering; exit-criterion step 3 asserts the count against `mandatory_lenses + routable_lenses`. **R14.** |
| 6 | warning | SPEC AC-004; Phase 2 | AC-004's backward-compatibility clause had no named test anywhere. | Named in Phase 2's exit criterion and in Success Criteria as `test_four_per_lens_files_still_cover_the_core_set`. The SPEC's verification row stays under-specified by one test; the PLAN supplies the witness without a SPEC change. |
| 7 | suggestion | Phase 2/3 `parallel-b` | Safe on file ownership, but neither phase may land alone. | Joint-landing constraint written into both phases' `merge_hazards`. |
| 8 | suggestion | Executive Summary | The ≈330k figure was cited at the decision point without the qualification RESEARCH explicitly demanded there. | Qualified inline at the citation. |

**Checked and found sound by the validator** (recorded so silence is not read as a gap): `core`
cannot collide in either consumer — it is absent from `ALL_LENSES`, so `exercised_lenses`' stem
check cannot confuse a group file with a lens file, and absent from `KNOWN_LENSES`, so
`review_telemetry._lenses_are_known` would *reject* a row carrying it, which makes ADR-004
load-bearing rather than stylistic. The 39 → 33 arithmetic verifies: `count_round_trips` counts
`Task(subagent_type=`, the template has exactly two dispatch loops, and 7 → 4 in each is −6.
`step_sensitivity` keys on the ordinal `"Step C2"` only, so retitling that heading does not break
the registry gate. No deferred-decision phrasing appears in the draft.
