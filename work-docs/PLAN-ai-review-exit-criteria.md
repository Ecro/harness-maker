---
type: plan
task_slug: ai-review-exit-criteria
status: complete
created: 2026-08-14
tags: [harness-maker, plan, jinja2, review-stage, lens-coverage, exit-criteria]
spec: "[[SPEC-ai-review-exit-criteria]]"
research_doc: "[[RESEARCH-ai-review-exit-criteria]]"
interview_rounds: 6
adrs: 14
validator_outcome: MAJOR_REVISION_TERMINAL
summary: "Declare a five-lens failure space, cover it on a frozen artifact, and let coverage block approval."
---

# PLAN — declared failure space, covered on a frozen artifact

> **The contract lives in `specs/SPEC-ai-review-exit-criteria.md`, not here.** This document
> holds *why* and *in what order*. Every rule is referenced by AC number and is not restated.
> That is a deliberate structural change, made after two adversarial validation rounds in
> which 8 of 13 and then 8 of 13 findings were this document and the SPEC stating one rule two
> ways — each repair propagated by hand, with no gate comparing them. `spec_machine
> cross_validate` gates the SPEC pair; nothing gates prose duplicated into a PLAN, so the
> duplication was removed instead of policed.

## 🎯 Executive Summary

**TL;DR.** `/hm:review` gains a declared five-lens failure space (AC-001, AC-002), a coverage
verdict computed by a called CLI (AC-011), an approval condition that no `grade_threshold`
can bypass (AC-003), and a confirmation pass over a faithfully frozen checkout diffed from
`review_base` (AC-004, AC-006, AC-007). `/hm:plan` gains a terminal whole-document
re-validation with a named outcome and named readers (AC-010).

**Why.** Two failures compose. Reviewer selection is reductive and unrecorded, so Grade A can
come from a round that never examined recovery or the tests' own oracles — two of five failure
classes have no reviewer in `/hm:review` at all. And the auto-fix loop re-reviews only touched
scopes, so the last round's fixes always exit unreviewed; those fixes introduce defects at
11/22, 7/7 and 3-of-4-rounds, every time behind a fully green four-gate run. Coverage without a
frozen artifact explores the wrong object; a frozen artifact without coverage explores the
right object at random.

**Cost.** Stated in the SPEC's Constraints table. In short: nothing extra unless the review
reaches the approval path; five dispatches if it approves on the first confirmation pass; ten
plus a repair round on the dirty path, which may still end `CHANGES_REQUESTED`.

**What this PLAN's own history is evidence of.** Six rounds. The first draft was refuted on
eight points by two independent models; the repairs for those eight produced eleven more; the
repairs for those produced thirteen more. No code existed at any point — there was nothing for
`ruff`, `mypy` or `pytest` to be green about, and the compounding rate matched the code-side
measurement anyway. The convergence only came from changing the mechanism (one contract
document) rather than patching the findings. That is the same remedy this repository's memory
records for the code-side version of the class.

## 📚 Prior Work

- `work-docs/RESEARCH-ai-review-exit-criteria.md` — the six-criterion mapping; this ships ④+⑤.
- `RESEARCH-review-round-inflation` / `PLAN-review-round-inflation` — the ~1:1 fix-to-defect
  rate, the rejection of raising `max_review_rounds`, and the measure-C counters left advisory.
- `PLAN-multi-lens-review-round` — the measured case for parallel lens breadth (1 lens → 2–3
  findings; 3 parallel → 9–12; zero overlap between blocking lenses) and the precedent that
  lenses can be prompt-only.
- `PLAN-second-opinion-acceptance-gate` — the frozen round-1 cross-model set and the vote-freeze
  contract AC-009 must not disturb.
- `[fail:test] fix-introduced-defect-passes-all-gates` (count:7) — the measurement that makes
  the confirmation pass worth its cost, including its planning-side half.
- `[wiki:gotcha] loop-body-skipping-review-stage` — Grade A over 5 unfixed P1s, and a model
  silently reinterpreting a costly mandatory step as optional. Why evidence is a receipt.
- CLAUDE.md 2026-06-08 (absent-case = feature black hole) — source of ADR-008.
- CLAUDE.md §Cross-model second opinion — "a prose recipe has no execution surface, so render
  tests can only grep its text; four silent-skip bugs shipped in that shape." Source of ADR-012.

## 🎙️ Interview Transcript

| # | Round | Topic | Question | Choice | → ADR |
|---|---|---|---|---|---|
| 1 | 1 | Scope | Which exit criteria ship? | One fix-loop re-entry on a dirty pass | ADR-007 |
| 2 | 1 | Surface | `/hm:review` only, or plan-validator too? | Both | ADR-010 |
| 3 | 2 | Lens coverage | Ship it this round? | Excluded — **reopened**, see #11 | — |
| 4 | 2 | Placement | Replace or follow the selective re-review? | Replace | ADR-005 |
| 5 | 2 | Accepted risk | Ship the register? | Excluded | ADR-011 |
| 6 | 3 | Evidence | Telemetry, REVIEW section, or both? | Telemetry (machine receipt) | ADR-008 |
| 7 | 3 | plan-validator | What shape? | Whole-PLAN re-validation after last revision | ADR-010 |
| 8 | 4 | Cost | I corrected my own claim — +1 full pass, not free. Proceed? | Accept | ADR-005 |
| 9 | 4 | Freeze | git ref, injected diff, or advisory? | git ref — **superseded**, see #14 | ADR-006 |
| 10 | 4 | Loop mode | Dirty second pass under `/hm:loop`? | Halt the iteration | ADR-008 |
| 11 | 5 | Reframe | "Systematically explore the failure space we defined as mattering" — that is ④, not ⑤. Reopen? | ④ becomes the body; ⑤ on top | ADR-001 |
| 12 | 5 | Lens set | Which failure space? | The five given lenses, fixed | ADR-001 |
| 13 | 5 | Gate strength | Does an unexercised lens block? | Blocks | ADR-003 |
| 14 | 5 | Realization | New agents or prompt-only briefs? | Prompt-only | ADR-002 |
| 15 | 5 | Leftovers | ux / performance — promote, keep, retire? | Keep optional, routed | ADR-009 |
| 16 | 6 | Convergence | Two validator passes, both MAJOR_REVISION, cap exhausted. Accept as risk, abort, narrow scope, or change the mechanism? | **Change the mechanism** — one contract document, rewrite | see the note under the title |

## 📐 Architecture Decision Records

> Each ADR records the decision's *rationale* and its *rejected alternatives*. The rule it
> decided is stated once, in the SPEC, under the AC named in the heading.

### ADR-001: The failure space is five fixed lenses (AC-001)
**Context:** A space must be declared and enumerable before "systematically explored" means
anything. `/hm:review` had no declaration.
**Why five, and these five:** they are failure-mode-shaped. The existing reviewer axes
(code / security / performance / ux / concurrency) are agent-shaped, and two of the five
classes — failure/recovery and tests/oracle — are absent from them. Those two are where the
measured defects lived.
**Rejected:** reuse the existing reviewer axes (declares systematic coverage of a space
missing the two classes that matter); per-project `harness.yaml` config (needs a default to
migrate from — this ships it).
**Source:** Interview #11, #12

### ADR-002: Lenses are dispatch-time briefs, not agent files (AC-002)
**Context:** Two lenses have no agent; the obvious move is to write two more.
**Why not:** `/hm:execute` Phase A.5 already dispatches three prompt-only lenses in parallel
and raised findings from 2–3 to 9–12, with zero overlap between the blocking lenses. A lens is
a brief, not an identity. Zero new `model` / `communication_variant` / routing-table surface.
**Accepted duplication:** `test-reviewer` continues to serve only Phase A.5; the tests/oracle
lens here is a brief, not that agent.
**Rejected:** add `failure-reviewer` and rewire `test-reviewer` (multiplies render surface and
forces a re-draw of the A.5 boundary for no measured gain); hybrid (two realization mechanisms
means two coverage-aggregation paths and two shapes of test).
**Source:** Interview #14

### ADR-003: Incomplete coverage blocks approval, beside the grade (AC-003)
**Context:** Recording coverage without acting on it leaves "No findings ≠ Reviewed"
unenforced — the shape of `human_review_needed`, persisted and, in loop mode, read by nothing.
**Why beside the grade, not inside it:** the first draft capped the grade "below A". Both
second-opinion models refuted it independently — `grade_threshold` may be `B` or `C`, and a cap
at B clears a B threshold. The mechanism would have been silently inert for every harness not
set to A.
**Rejected:** grade cap (inert at B/C); record-only (declares systematicity, enforces none);
mandatory subset (re-opens the "which concerns really count" judgement the declaration settles).
**Source:** Interview #13; codex `8dc3fb92`

### ADR-004: Mandatory lenses are exempt from conditional routing (AC-002)
**Context:** `routing: conditional` exists to drop reviewers; ADR-003 requires them present.
**Why:** the contradiction is at the source, not at the grade. Routing governs the two optional
reviewers and nothing else, and that must be visible where routing is read or configured, or
the next reader re-derives the conflict — so the docstring and `harness.yaml` comment are part
of **AC-002**, owned by Phase 1, rather than a requirement stated only here. An earlier draft
left them as a sentence in this ADR with no AC and no phase; that is the same ownerless-
requirement shape as the `open_items` field this PLAN dropped for the same reason.
**Rejected:** let routing drop lenses and accept the consequence — every conditional-routed
review would fail its coverage condition, making the setting equivalent to "never approve".
**Source:** derived from Interview #13, #15

### ADR-005: The confirmation pass replaces the approval step, not a loop round (AC-004)
**Context:** The interview first recorded "replaces the last round's selective re-review".
Reading the loop showed that is not computable: the grade identifying the final round is
computed *from* that re-review.
**Why this shape:** the approval is granted by a pass that saw the whole final artifact, and a
review that fails its grade pays nothing extra.
**Rejected:** pre-emptively replace the terminal selective re-review (not computable); append
the pass after it (strictly more expensive for the same information — the confirmation pass
subsumes the touched scopes).
**Source:** Interview #4, #8

### ADR-006: Freeze is a faithful commit, checked out, diffed from `review_base` (AC-004)
**Context:** "Frozen diff" needs a referent, and reviewers hold `Read`.
**Three corrections, each from a refutation:**
1. A **bare ref is not a freeze** — naming a ref changes nothing about what `Read` opens. The
   first draft was the advisory option it had just rejected, wearing a ref's name. Hence a
   detached checkout.
2. The ref must name a commit built from the **current working state**. The fixes under review
   are uncommitted (commits happen at `/hm:wrapup`), so a ref naming `HEAD` freezes the
   artifact *without* the content the pass exists to examine.
3. The diff base must be **`review_base`**, not the freeze commit's parent chain from `HEAD`.
   With `-p HEAD`, "the diff of that ref" naturally reads as `HEAD..freeze` — only the last
   round's fixes — which would make the confirmation pass the scope-selective re-review ADR-005
   says it replaces. The second correction created this third defect.
**Why the frozen root is outside `.worktrees/` but named:** `.worktrees/` is governed by the
create-time guards and swept on the `execute-*` / `plan-*` / `phase-*` / `autoloop-*` prefixes,
which a freeze matches none of. But "not there" is not a location — leaving `<freeze-path>` a
free variable would make it untracked dirt the create-guard, the finalize dirt-filter and
wrapup's `git add` all see, and a second freeze's `git add -A` would ingest the first. Hence a
literal, gitignored, churn-prefixed path (AC-004).
**Residual, stated not hidden:** a reviewer can still open an absolute path outside the frozen
root. The brief gives only the frozen root and says why; nothing detects a violation. Closing
it would need a tool-level path restriction, which subagent frontmatter cannot express
(CLAUDE.md §보안/권한: `permissions:` is silently ignored; `tools:` is the only enforced
boundary and is not path-scoped).
**Rejected:** bare ref; ref naming `HEAD`; injected `git diff` text (same `Read` hole plus a
size ceiling); advisory instruction.
**Source:** Interview #9; codex `de3720d3`, antigravity `b7cc7543`, and two validator rounds

### ADR-007: One repair round, on a separate budget, order-independently defined (AC-006, AC-007)
**Context:** A dirty pass could re-enter the fix loop indefinitely — the "buy convergence with
rounds" pattern already rejected once.
**Why the budget is separate:** counting the repair round against `max_review_rounds` makes the
mechanism inert on exactly the reviews that used every round, which is where it matters most.
**Why the `auto_fix`-off rule is stated without reference to branch order:** an earlier draft
justified it by asserting that the shipped gate tests `grade ≥ grade_threshold` before the
auto-fix-disabled branch. That may be true today, but Phase 4 edits that gate and no test
pinned the ordering — so the justification was load-bearing and unguarded. The rule is now
unconditional (AC-007).
**Rejected:** iterate to convergence; count the repair round against the cap; skip the
confirmation pass when `auto_fix` is off (coverage is an approval condition independent of
fixing).
**Source:** Interview #1; codex `b26789ca`, antigravity `c8aaabab`, validator pass 2

### ADR-008: A dirty second pass inside `/hm:loop` fails the Gate 0 receipt (AC-008)
**Context:** `human_review_needed` is persisted in loop mode and read by nothing — an accepted
limitation this change must not reproduce.
**Why:** the loop is the least-supervised path, so it is where the protection is worth most;
and the existing Gate 0 retry/escalation machinery is the named reader, so no new loop surface
is added.
**Rejected:** inherit proceed-and-persist (reproduces the visibility regression); skip the
confirmation pass in loop mode.
**Source:** Interview #10, #6

### ADR-009: `ux-reviewer` and `performance-reviewer` stay optional and routed
**Context:** Both sit outside the declared space.
**Why keep:** retiring them is the only option here that reduces what the harness can find.
**Accepted cost:** the reviewer set is now two-tier, a distinction that must be visible
wherever reviewers are configured.
**Rejected:** promote to lenses 6–7 (neither fits "breaks production correctness", so making
them mandatory raises cost and dilutes the condition); retire.
**Source:** Interview #15

### ADR-010: plan-validator re-validates terminally, with a named outcome and readers (AC-010)
**Context:** `MAJOR_REVISION` re-runs the validator once; `NEEDS_REVISION` revises and
re-validates never. Five of six rounds of the planning-side measurement were revisions each
introducing the next round's P0, with no mechanical gate in existence.
**Why pass 2 is terminal:** "validate after the last revision" and a two-pass cap are jointly
satisfiable only if the last pass produces no further revision. The first draft left revision 2
permanently unvalidated.
**Why a distinct token:** `MAJOR_REVISION` already means "will be re-run after revision".
Letting it also mean "validated, unfixable within budget, proceed" is the shape ADR-008 exists
to prevent, reproduced on the plan side. Hence `MAJOR_REVISION_TERMINAL` with both readers
named (AC-010).
**Why no ledger field:** an earlier revision added an `open_items` count to the
`stage_agent_ledger` row, and no phase owned the schema change — a persisted field with no
implementer and no exit criterion, which is the absent-case class this PLAN cites. Dropped; the
frontmatter and `## 🔍 Plan Validation` carry it.
**Rejected:** raise the cap to three passes (moves the contradiction one pass along and reopens
round inflation on the planning side); revise after pass 2 without re-validating (the defect,
restated); fire only when the revision is a repair ("is this a repair" is another prompt
judgement, and that class is what silently does not fire).
**Source:** Interview #7; codex `e81d7180`, antigravity `bb8beea0`, validator passes 2 and 3

### ADR-011: The accepted-risk register is deferred
**Context:** The research's ⑥ — an `accepted` disposition with owner and rationale.
**Why not now:** it would record residual risk against an unmeasured coverage baseline, and its
authority question under autopilot `auto_full` is unresolved.
**Source:** Interview #5

### ADR-012: Coverage travels through a CLI seam written by the main loop (AC-011)
**Context:** Two findings land on the same seam. The coverage value was a free-text claim the
executing model wrote about its own behaviour; and a lens that failed in round 1 touched no
scopes, so the selective re-review never re-dispatched it — coverage stayed incomplete,
approval stayed blocked, and the review ran to `max_review_rounds` with no actionable finding.
**Why a CLI, not a helper function:** an earlier revision shipped `exercised_lenses()` and
`coverage_blocks_approval()` as Python with no transport — nothing called them. Phase 1's exit
criterion was a unit test of a function nobody invoked; Phase 3/4's were greps for sentences.
Every gate was satisfiable with zero runtime effect. CLAUDE.md records four silent-skip bugs
shipped in exactly that shape and records the cure as "reduce the recipe to one CLI line with
an execution surface".
**Why the main loop writes the result files:** the alternative — each lens subagent writing its
own — reopens the self-report hole (a lens that never looked can still write a file) and is
likely infeasible, since reviewer agents are read-only by tool set.
**Why rule 3 (the terminal blocker):** re-dispatch alone leaves the state absorbing at
`max_review_rounds: 1` and when the no-progress invariant fires on a repeatedly-failing lens.
The earlier draft claimed the class was closed when only the common case was.
**Residuals, stated not hidden — now with measurements attached:**
- The dispatch step is still prose. The seam raises forging coverage from writing a name in a
  list to writing fabricated result files — materially higher, not impossible.
- **AC-011 judges liveness, not validity** (the file-set check, nothing more). That is now
  written into the AC rather than left implicit, because *Building to the Test*
  (arXiv 2606.28430) measured what happens when a checked surface diverges from the requested
  one: with a hidden 222-test oracle in the loop, agents scored near-perfect from a demo
  carrying the tested behaviour while the requested library was left dead. The earlier
  "fail-closed by construction" wording is withdrawn as an overclaim.
- **The results path is known and stable, and mining it is observed behaviour.** *RuBench*
  (arXiv 2607.06411) found systematic oracle-hunting in one model family (8/69 and 13/75
  cells), including mining a prior round's artifacts from the run machine's disk — the exact
  move our `<round>` / pass-id keying forbids in prose and nothing enforces. Making the path
  unmineable is real design work and is **not** in this task; recorded as a follow-up.
**Rejected:** trust the self-reported list; treat a failed lens as exercised-with-no-findings
(converts a delivery failure into a clean bill of health).
**Source:** codex `fe5db612`, antigravity `d7daeb61`, validator passes 2 and 3

### ADR-013: The auto-fix loop's monotone lattice is an assumption, and this task records it as one
**Context:** The shipped Auto-Fix Loop uses a monotone lattice — `pending → resolved/stale`
only, never back to `pending`. That is not a neutral data structure: it encodes **"repair does
not damage what was already correct."**
**Decision:** Do not change the lattice in this task. **Do** record that it is an assumption,
name the evidence against it, and name the field that already collects the counter-evidence.
**Why now:** two independent measurements arrived after the lattice shipped.
- *OrchestraBench* (arXiv 2608.05263) injected failures into multi-agent pipelines and measured
  recovery per mode: tool faults **1.0**, ambiguous delegation **0.30**, three latent/semantic
  modes **0.0**. Its stated conclusion: *"Blind retry reproduced latent faults and increased
  time to detection, indicating that detection and attribution are necessary for containment."*
  (The authors scope this as controlled-chain mechanism probes, not domain-workload claims.)
- **This task's own history.** Across five Phase A.5 rounds and three plan-validator passes,
  roughly half of each round's findings were defects introduced by the previous round's repair,
  and none of them were tool faults — they were semantic: a scenario misattribution, a rule
  inert at `grade_threshold` B, a section slice three times too wide. Blind retry on exactly
  the class OrchestraBench measures at 0.0 recovery.
**Consequences:**
- ✅ The next reader inherits a labelled assumption instead of an unmarked invariant.
- ⚠️ `caused_by` — the attribution metadata the loop already stamps on every finding — still
  gates nothing (ADR-003 of `PLAN-review-round-inflation`, preserved as a non-goal here). We
  collect the evidence that would drive containment and do not use it. That is now a written
  gap rather than an accident.
- ⚠️ Under a repairer with a non-zero damage rate, a bounded round count makes the loop *stop*;
  it does not make it *converge*. Our caps are honest about stopping and silent about that.
**Rejected:** change the lattice now (out of scope, and the right change is attribution-gated
rather than lattice-shaped); leave it unmarked (the assumption reads as a proven invariant).
**Source:** arXiv 2608.05263; this task's A.5 and validator round history

### ADR-014: The Python verifiers are put under the mutation gate (AC-015)
**Context:** Every quality claim in this task rests on tests, and a passing test is evidence
about the gates' coverage rather than the code's correctness — count:7 in this repository.
**Decision:** Extend `paths_to_mutate` to every Python surface this SPEC ships a verifier on
(`lens_coverage`, `freeze`, `review_telemetry`, `conditional_router`) and make a zero-survivor
tier-1 run an acceptance criterion.
**Why:** the one procedure in this task that produced *strong* evidence was defect injection —
re-inserting `review_base` accepting `HEAD`, the freeze commit parented on `HEAD`, and a
fail-open unparseable result file, and confirming each test failed. All three bit; none of them
would have been visible from a passing run. *Building to the Test* (arXiv 2606.28430) uses the
same instrument — a no-op ablation to check each verdict — as its central method. Here it was
done by hand, once, and required by nothing.
**Consequences:**
- ✅ Reuses machinery that already ships (`hm spec_mutation gate --tier 1`); no new module.
- ✅ Threshold 70 over the surface that matters beats 85 over a surface chosen for being
  reachable.
- ⚠️ **Does not reach the rendered templates.** Mutation cannot mutate Jinja prose. The
  equivalent for render ACs is a RED gate that runs *before* the reviewer gate — recorded as a
  follow-up, since it changes `/hm:execute`, not this task's surface.
- ⚠️ A surviving mutant is closed by strengthening the assertion, never by lowering the
  threshold.
**Rejected:** leave mutation to the existing default set (it did not include the two new
modules, so the verifiers this task adds would have been the only unverified ones).
**Source:** arXiv 2606.28430; the Phase 1/3 injection results

## 🏗️ Technical Design

**Current state.** `review.md.j2` Step 3 dispatches the routed reviewer set; Grade Computation
(`:453-478`) counts only `consensus-passed` P0/P1; the Grade Gate (`:480-529`) approves on
`grade ≥ grade_threshold`; Auto-Fix Loop step 6 (`:565`) re-reviews only touched scopes.
`plan.md.j2:578` revises on `NEEDS_REVISION` without re-validating; `:579` re-runs once on
`MAJOR_REVISION` under a ledger-enforced 2-pass cap. `review_telemetry.py:75-84` already carries
a three-state `terminal` discriminator — the pattern AC-012's rules follow.

**Affected components.**

| Component | Change | ACs |
|---|---|---|
| `conditional_router.py` | `MANDATORY_LENSES`; `route_reviewers` narrowed to optional reviewers | AC-001, AC-002 |
| **new** `lens_coverage.py` + its CLI registration | the `check` entrypoint the template calls | AC-011, AC-003 |
| `review_telemetry.py` | three new fields + the AC-012 rules | AC-005, AC-012 |
| `worktree.py` | reap `refs/hm-freeze/v1/*` and `.claude/.hm-freeze/*`; add the freeze path to the churn prefixes and gitignore | AC-004 |
| `templates/stages/review.md.j2` | lens dispatch, result writing, coverage call, approval condition, confirmation pass, receipt branch | AC-002, AC-003, AC-004, AC-006, AC-007, AC-008, AC-009, AC-011, AC-013 |
| `templates/stages/plan.md.j2` | terminal whole-document re-validation | AC-010 |

## 📝 Implementation Plan

### Phase 1 — Lens constant, coverage CLI, approval condition
- `depends_on`: []
- `parallel_group`: `python-core`
- `merge_hazards`: `conditional_router.py`, new `lens_coverage.py`, **the CLI dispatch
  registration** — no other phase edits them
- Scope — in: `conditional_router.py` (including the `route_reviewers` docstring of AC-002),
  `src/harness_maker/lens_coverage.py`, the CLI registration that makes `hm lens_coverage`
  reachable, the `harness.yaml` reviewer-routing comment of AC-002,
  `tests/unit/test_lens_coverage.py`. Out: stage templates.
- `merge_hazards` (restated): `conditional_router.py`, `lens_coverage.py`, the CLI registration,
  the `harness.yaml` template — no other phase edits them
- Exit criterion: **end-to-end through `hm lens_coverage check`**, the entrypoint the template
  will call — a results directory that is missing, or contains an unparseable or unknown-lens
  file, yields `blocks_approval: true`; only five present-and-parsing files yield `false`. A
  test exercising the in-process helper alone does **not** satisfy this. Discharges AC-001 and
  AC-011's CLI half.
  **The `grade_threshold` A/B/C assertion does not belong here** — the CLI is threshold-blind
  by construction, so asserting threshold-independence through it would be vacuous decoration.
  AC-003's threshold-independence is discharged in Phase 4 by a render assertion over all three
  threshold renders. An earlier draft put it here, which made this phase's exit criterion
  unsatisfiable within its own scope and left the mechanism's headline claim with no test that
  could fail.
- Risk: low
- Rollback point: pre-phase HEAD

### Phase 2 — Telemetry fields
- `depends_on`: []
- `parallel_group`: `python-core`
- `merge_hazards`: `review_telemetry.py`
- Scope — in: `review_telemetry.py`, `tests/unit/test_review_telemetry_confirm.py`.
- Exit criterion: AC-005 and AC-012 hold, including the explicit all-lenses-failed row
  (`lenses_exercised: []`, `confirm_pass_ran: false`, `confirm_pass_new_severe_n: null`) and a
  pre-change row still parsing.
- Risk: low
- Rollback point: pre-phase HEAD

> **⛔ BLOCKED at Phase A.5 — retry budget exhausted (2 rounds), escalated to the user.**
> No implementation was written; the tests exist, the schema is unchanged.
>
> **Round 1 — FAIL, 3/3 lenses.** Five tautologies: every `pytest.raises(ValidationError)`
> was satisfied by the model's `extra="forbid"` guard rather than by the rule it named, so
> each would have read GREEN at the RED gate against a schema with none of the three fields.
> `per_scenario` S9 FAIL 3/3 — no test constructed S9's own row.
> Repairs: bound each rejection to its rule via a `_rejected_by_a_rule` helper that excludes
> `extra_forbidden`; added the mirror direction of rule 1; added S9's positive row; drove lens
> names from `MANDATORY_LENSES`; renamed the two S4 tests with a `test_s4_` prefix.
>
> **Round 2 — FAIL. red-correctness PASS, discrimination PASS, coverage FAIL.** One blocking
> issue, and it is a defect **round 1's own repair introduced** — the `test_s4_` prefix
> attributed `test_s4_dirty_confirmation_row_is_accepted` to S4, whose Then is "records ZERO
> new severe findings", while the test asserts `confirm_pass_new_severe_n == 2`. Category:
> scenario-id mismatch. S4 now carries two tests, one asserting the negation of its Then.
>
> **Do not delete that test.** It is the file's only positive-count acceptance; without it an
> implementation constraining `confirm_pass_new_severe_n` to the literal `0` passes
> everything here. The lens's own remedy is a rename only: drop the `test_s4_` prefix
> (`test_dirty_confirmation_row_carries_a_nonzero_count`) and leave both bodies unchanged.
>
> Escalated rather than repaired because the 2-round budget was spent. Resuming means
> applying that rename and re-entering Phase A.5 at round 1 with a fresh budget.
>
> **Resumed on user authorisation.** The rename was applied exactly as prescribed (bodies
> unchanged) and the test moved under a `rule 2 acceptance` header, since leaving it beneath
> the `S4` section comment would have reproduced the same misattribution in prose. A fresh
> A.5 budget was opened under run-id `aiexit-exec-p2c`.
>
> ### ⚠️ Ledger contamination — `aiexit-exec-p2b` is a spurious row, exclude it
>
> While resuming I emitted `stage_agent_ledger emit --run-id aiexit-exec-p2b --pass 1
> --verdict PASS --terminal` **before dispatching that round**. The intent was to check the
> CLI's argument handling; the effect was a recorded PASS for a gate round that never ran.
> `stage_agent_ledger` is append-only and its `emit` verb has no retract or void option
> (`--help`: only run-id / agent / stage / slug / pass / verdict / terminal / reason /
> duration-ms / barrier-index), so the row cannot be removed.
>
> **Any aggregation over `stage-agents.jsonl` must drop run-id `aiexit-exec-p2b`.** It
> reports a terminal PASS with no corresponding dispatch, which inflates the A.5 first-pass
> rate for this slug. The real rounds are: `aiexit-exec-p2` passes 1–2 (FAIL, FAIL+terminal)
> and `aiexit-exec-p2c` (this round).
>
> This is the failure this whole task is about, committed by the tooling's own operator: a
> green record that does not correspond to anything that happened, in a store that cannot be
> corrected. It is recorded here because the ledger cannot record it itself.

### Phase 3 — Freeze plumbing and reaping
- `depends_on`: []
- `parallel_group`: `python-core`
- `merge_hazards`: new `freeze.py`, and `worktree.py` for the reaping/churn-prefix entries —
  no other phase edits them
- Scope — in: **new** `src/harness_maker/freeze.py` (the `review_base` resolver and its store,
  the freeze-commit construction), `worktree.py` (`refs/hm-freeze/v1/*` and
  `.claude/.hm-freeze/*` reaping, the churn-prefix and gitignore entries),
  `tests/unit/test_freeze_commit.py`. Out: templates.
  > **Deviation from the pre-implementation scope, recorded rather than silent.** This phase
  > was scoped to `worktree.py` alone. The construction went into a new `freeze.py` instead:
  > `worktree.py` is ~5k lines and is the module the 5-layer contamination defense lives in,
  > which this phase's own risk row names. A new module keeps the freeze logic testable without
  > importing that surface. The reaping still belongs in `worktree.py` because that is where
  > the sweep lives.
- Exit criterion: AC-004's construction half holds — including the `review_base` fallback
  cases (on the base branch, and on a branch with no own commits) and the `git status`
  invisibility obligation, both of which are now stated in AC-004 rather than only here — plus
  a stale freeze ref and root being reaped. **This phase exists because an earlier draft named
  the reaping as a risk mitigation and gave it no phase.**
- Risk: medium — touches the module the 5-layer defense lives in
- Rollback point: pre-phase HEAD

### Phase 4 — `review.md.j2`: declared space, coverage, approval condition
- `depends_on`: [1, 2, 3]
- `parallel_group`: `serial-review-template`
- `merge_hazards`: `review.md.j2` — shared with Phase 5; serial
- Scope — in: `review.md.j2` (Step 3 lens dispatch, main-loop result writing, the
  `hm lens_coverage check` call, `review_base` resolution, the Grade Gate's coverage condition,
  the re-dispatch obligation and the AC-013 blocker, the Telemetry Emit field list),
  `tests/unit/test_render_lens_dispatch.py`. Out: the confirmation pass.
- Exit criterion: AC-002, AC-013 and the render halves of AC-003 and AC-011 hold — including
  **AC-003's threshold-independence, asserted over all three `grade_threshold` renders**, and
  the emission half of AC-005 (the rendered stage actually writes the three telemetry fields;
  the schema tests of Phase 2 construct rows directly and cannot see this). A
  `routing: conditional` render still drops only optional reviewers.
- Risk: medium — the largest prose edit; the grade table is load-bearing
- Rollback point: Phase 3

> **⛔ BLOCKED at Phase A.5 — 2-round budget spent, escalated.** No template edit was made;
> `review.md.j2` is unchanged. `tests/unit/test_render_lens_dispatch.py` holds 29 RED tests.
>
> **Round 1 — FAIL 3/3, 11 merged blocking issues.** The headline: a bare `lens in
> review_body` was GREEN before implementation, because the template already ships `failure`
> in its Quality Bar prose and renders `correctness`/`tests` under the mechanical-checks
> branch for other configs. Also unsound: `'below A' not in review_body`, which admits "caps
> the grade at B" and rejects the *correct* sentence for an A-threshold harness. One lens
> claimed `ux-reviewer`/`performance-reviewer` were pre-existing; **verified directly — they
> occur zero times** in the template and zero times in the rendered sandbox, so that lens was
> wrong and the other was right that asserting their literal names would push the coder to
> hard-code optional reviewer names into a preset that may not enable them.
>
> **Round 2 — FAIL 3/3.** The rewrite (section slicing, `<lens>.json` anchors, A/B/C
> thresholds, eleven new clause tests) fixed the round-1 defects and introduced others:
> - `_section` was **narrowed in name only** — the dispatch block's stop token is a level-2
>   heading, so the slice spans 287 lines (Step 3 → Grade Computation) and already contains
>   `calls in parallel` (:257) and `Round 1` (:337, :436). The parallelism test is GREEN today.
> - AC-003(a) is observed by `'grade_threshold' in gate`, but that identifier is already in
>   the shipped gate (`IF grade ≥ grade_threshold:` :499). An implementation that wrote the
>   coverage conjunct and demoted the grade to advisory prose passes.
> - `test_route_reviewers_never_drops_a_mandatory_lens` **drives a wrong implementation**: it
>   passes `MANDATORY_LENSES` as `preset_reviewers` and requires them returned, whose cheapest
>   satisfaction is `selected |= set(MANDATORY_LENSES)` — injecting five non-agent ids into the
>   list the dispatcher Task-spawns. That contradicts this repo's own
>   `conditional_router.py:27-29` ("failure-mode-shaped, not agent-shaped … deliberately NOT
>   the same set") and ADR-002. **This test would fail the correct implementation.**
>
> ### What the round answered about prose-executed artifacts
>
> The open question going in was whether the remaining defects were an infinite regress —
> every fix being "quote more of the SPEC sentence, slice tighter" — which would mean the
> SPEC's "no gate satisfiable with zero runtime effect" standard is unreachable for render ACs
> by construction. **It is not a regress.** For nearly every sentence-quoting assertion a
> strictly better structural anchor exists, and the reviewers named them:
>
> | assertion quoting the SPEC | structural anchor available instead |
> |---|---|
> | `'sole producer'` | the Grade Gate slice consumes the CLI's own JSON key `blocks_approval` |
> | `'main loop writes'` | the `<lens>.json` write instruction is in the dispatch block **and** the lens-brief slice contains no Write instruction |
> | `'distinct'` in the blocker | the blocker phrase is **absent** from the findings-section slice and present under its own heading |
> | `'names the unexercised lens'` | the gate consumes the CLI's `missing` key |
> | `'never reused'` | subsumed by the per-round path assertion, or anchored to the `confirm-1`/`confirm-2` pass-id form |
> | `'regardless of the P0/P1 counts'` | slice the `APPROVED` branch and require both conjuncts *in that slice* |
>
> The handles a rendered command does offer are: **the CLI's output key names, section
> boundaries, and presence/absence across sections.** Weak anchors here were a choice, not a
> limit. What remains genuinely unanchorable is whether the executing model obeys the prose —
> ADR-012's stated residual, unchanged.

### Phase 5 — `review.md.j2`: confirmation pass
- `depends_on`: [4]
- `parallel_group`: `serial-review-template`
- `merge_hazards`: `review.md.j2` — shared with Phase 4
- Scope — in: the same template's Grade Gate, Auto-Fix Loop and Gate 0 receipt sections,
  `tests/unit/test_render_confirmation_pass.py`. Out: `plan.md.j2`.
- Exit criterion: AC-004 (render half), AC-006, AC-007, AC-008 and AC-009 hold, including the
  unconditional `auto_fix`-off branch of AC-007.
- Risk: medium — a new terminal branch in an already-branchy gate
- Rollback point: Phase 4

### Phase 6 — `plan.md.j2`: terminal re-validation
- `depends_on`: []
- `parallel_group`: `plan-template`
- `merge_hazards`: `plan.md.j2`
- Scope — in: `plan.md.j2` Step 4 resolution block,
  `tests/unit/test_render_plan_revalidation.py`. Out: the ledger schema (ADR-010).
- Exit criterion: AC-010 holds; the two-pass cap text is unchanged.
- Risk: low
- Rollback point: pre-phase HEAD

### Phase 7 — Snapshot regeneration and full suite
- `depends_on`: [1, 2, 3, 4, 5, 6]
- `parallel_group`: `serial-close`
- `merge_hazards`: snapshot baselines — after every template edit has landed
- Scope — in: snapshot baselines, `tests/`. Out: source.
- Exit criterion: `ruff check`, `ruff format --check`, `mypy --strict src` and full `pytest`
  green; snapshots regenerated **inside this worktree**; **and AC-015 — `hm spec_mutation gate
  --yaml specs/SPEC-ai-review-exit-criteria.machine.yaml --tier 1` reports zero surviving
  mutants** over the four `paths_to_mutate`. A survivor is closed by strengthening the
  assertion, never by lowering the threshold. If mutmut is absent the gate prints a skip
  notice and passes — that is non-gating by design, and a skip is **not** evidence.
- Risk: low
- Rollback point: Phase 6

## 🧪 Testing Strategy

Verification **modes** are fixed per AC in the SPEC's Verification Criteria table; this section
states only the standard each mode must meet.

- **Where an executable surface exists, the test must drive it** — an entrypoint (AC-011), a
  git object (AC-004), or a schema (AC-005, AC-012). A unit test of a function the template
  does not call, and a grep for a sentence, both pass while the mechanism is inert.
  **This is a preference with a large exception, stated here rather than buried:** eight of the
  behaviours in the SPEC's verification table are prose branches in a rendered command, and a
  render assertion is the only mode available for them. The standard binds where a surface
  exists; where none does, the residual is the one ADR-012 states — the dispatch step is prose,
  and no test in this repo closes that.
- **Expected strings come from the SPEC**, never from the template under test.
- **AC-009 has exactly one mode** — the render assertion named in the SPEC. A ledger-row
  comparison is optional and `INTEGRATION`-guarded, and is not a release condition.
- **Not covered by any test** — whether a lens brief actually elicits the findings its lens
  names. No mechanical test reaches it; the A.5 measurement is the only evidence and it is
  about a different stage. Stated as a risk, not papered over.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The two brief-only lenses under-perform a real agent | medium | high — the condition would certify nominal coverage | Briefs carry an explicit failure-mode checklist; ADR-002 is revisitable if those lenses return empty far more often than the agent-backed three |
| A dispatch failure blocks approval | medium | medium | Intended (ADR-003); AC-011's re-dispatch and AC-013's named blocker keep it from being absorbing or mute |
| Freeze refs / roots accumulate | high | low | Phase 3 owns the reaping — it is a phase, not a sentence |
| The confirmation pass re-invokes the second-opinion CLIs | low | high — double-bills the models and breaks the vote freeze | AC-009's render assertion over the confirmation-pass block |
| Phases 4 and 5 conflict in `review.md.j2` | high if parallelised | medium | Declared `serial-review-template`; 5 depends on 4 |
| This PLAN's own review compounds like the ones it cites | **observed, not hypothetical** | medium | The change ships the mechanism that detects it; the first `/hm:review` after Phase 7 is the natural self-test |

## ✅ Success Criteria

Every criterion is an AC in the SPEC. This table maps each to the phase that discharges it;
where two phases share one, both must land before the AC is closed.

| AC | Phase(s) |
|---|---|
| AC-001 | 1 |
| AC-002 | 1, 4 |
| AC-003 | 1 (computation), 4 (gate consumes it, report names the lens, threshold-independence) |
| AC-004 | 3 (construction, `review_base` fallback, `git status` invisibility), 5 (render) |
| AC-005 | 2 (schema), 4 (emission) |
| AC-006 | 5 |
| AC-007 | 5 |
| AC-008 | 5 |
| AC-009 | 5 |
| AC-010 | 6 |
| AC-011 | 1 (CLI), 4 (template calls it, re-dispatch) |
| AC-012 | 2 |
| AC-013 | 4 |
| AC-014 | 5 |
| AC-015 | 7 (the tier-1 mutation gate runs over the full `paths_to_mutate` once every phase has landed) |
| four-gate green + snapshots | 7 |

## 🚦 Implementation Status

| Phase | Status |
|---|---|
| 1 — lens constant, coverage CLI, approval condition | **landed** (`conditional_router.MANDATORY_LENSES` / `OPTIONAL_REVIEWERS`, `lens_coverage.py`, `hm` dispatch entry, 11 tests) |
| 2 — telemetry fields | **landed** — `lenses_exercised` / `confirm_pass_ran` / `confirm_pass_new_severe_n` + a `_lenses_are_known` field validator and a `_confirmation_record_is_readable` model validator carrying AC-012's three rules; 12 tests |
| 3 — freeze plumbing | **partially landed** — `freeze.py` (resolver, store, freeze commit) + 8 tests; the `worktree.py` reaping and churn-prefix entries are not done |
| 4 — review template (lens/coverage/approval) | **BLOCKED at A.5**, 2-round budget spent, escalated — see below |
| 5–7 | not started |

**The round-4 defects are now expressed as tests that fail when the defect is present.**
Verified by re-introducing each defect and observing the failure — not by observing a green run:

| Defect re-introduced | Caught by |
|---|---|
| `review_base` accepts the merge-base even when it equals `HEAD` (the naive definition) | 3 tests, incl. the base-branch and no-own-commits configurations |
| freeze commit parented on `HEAD` instead of `review_base` | `test_freeze_commit_is_parented_on_review_base_not_head` — the reviewed diff loses the committed earlier phase |
| an unparseable result file counted as exercised (fail-open coverage) | `test_unparseable_file_is_not_exercised` |

That mutation check is the point of these two phases: a green suite is evidence about the
gates' coverage, not about the code's correctness, and this repository's memory records seven
instances of exactly that confusion. The remaining ACs are still adjudicated only by prose.

**Phase 2's A.5 gate is the same lesson, arriving from the other direction.** Round 1 found
that all five negative tests were satisfied by the model's `extra="forbid"` guard rather than
by the rule each named — they would have read GREEN at a RED gate against a schema with none
of the three fields. The repair bound each rejection to its rule; the RED run then failed
12/12 with `row was rejected by the extra-key guard, not by a rule`, which is the assertion
refusing the false-RED it used to accept. Round 2 then FAILED on a defect **that repair
introduced** (a `test_s4_` prefix attributing a `count == 2` case to the scenario whose Then
is zero), the budget expired, and the gate escalated rather than letting the operator judge
the remaining defect trivial. Three rounds of three lenses; every round found something; none
of it would have been visible from a green suite.

**Phase D.5 — newly-reachable window.** Phase 2 is new-feature work, not a repair, so the
trigger does not strictly fire; run anyway, per "when in doubt". The window this opens is on
the *emitters*: every existing caller writes rows without the three fields, which rule 3
keeps valid — the absent case is the default path and is covered by
`test_legacy_row_without_any_new_field_still_parses`. The one genuinely new coupling is
`review_telemetry` now importing `conditional_router` for `MANDATORY_LENSES`; that module
pulls `llm_judge`, which is `Protocol`-based and imports no SDK at module level, and the
emit hot path's cold start measures 0.25 s. No fixture gap identified.

## 🚧 Phase 4 A.5 gate bypass — five rounds, non-converging, seven findings open

**This is a disclosed override, not a pass.** `/hm:execute` Phase A.5 was dispatched five times
on `tests/unit/test_render_lens_dispatch.py` (three lenses each round, merged per the stage's
own rules). Every round returned FAIL. The user elected to proceed to Phase C with the findings
recorded rather than spend a sixth round.

**The measurement that matters.** Blocking findings per round, after dedupe: 5 → 6 → 7. It is
not converging. And rounds 3, 4 and 5 each found that the *previous round's repair* had
relocated its defect rather than closed it — usually by attaching a docstring asserting the new
anchor was strong. Three such claims were refuted by measurement (`lens in body` goes red for a
dropped dispatch; slicing a `###` section to the next `##` narrows it; a backticked `missing`
proves CLI consumption). The compounding is real and it is this task's own subject matter.

**Why bypass is defensible here rather than in general.** The artifact under test is Jinja
prose. A render-grep can observe that a token is present in a bounded slice; it cannot observe
that the executing model obeys the instruction, and the ACs are largely about obedience. With
no implementation on disk, every discrimination finding is of the form "a wrong template could
say X" — the reviewer must *invent* the wrong template, and the space of inventable wrong
templates does not shrink as the test tightens. Once `review.md.j2` is written, the same lenses
judge an artifact that exists, and the question changes from "could a template evade this" to
"does this one." That is the round where the findings become decidable.

**A process defect of my own, recorded because it consumed reviewer budget.** The round-5 briefs
stated `24 failed, 3 passed` as a MEASURED RED-gate state and asked all three lenses to identify
"the third GREEN". The true state was **25 failed / 2 passed** of 27 collected; there was no
third GREEN. The count was inferred from a truncated progress line and labelled as measured. The
red-correctness lens refuted it statically from the progress string. Nothing in the test file was
wrong; a fabricated measurement was.

### The seven open findings (re-adjudicate against the implementation, not against invention)

| # | Test | Defect |
|---|---|---|
| 1 | ~~`test_budget_exhaustion_...`~~ **CLOSED in Phase C** | `_gate_arm` took the FIRST `CHANGES_REQUESTED`, which is the `auto_fix disabled` arm (AC-007), not the budget arm (AC-013). **Both lenses.** It surfaced immediately as a **false-RED against the correct implementation** — the budget arm *was* guarded. Replaced by `_gate_conditions`, which returns **every** matching arm; the caller then chooses `all(...)` for APPROVED and `any(...)` for CHANGES_REQUESTED. Ordering no longer matters, and the `j == -1` fallback that produced the `ELSE`-shaped false-GREEN is gone with it. |
| 2 | ~~`test_approval_requires_both_conjuncts_...`~~ **CLOSED in Phase C** | `_gate_arm` returned the arm's body as well as its condition (the outcome token sits inside the body), so a gate that merely *printed* the coverage verdict passed. `_gate_conditions` keeps only the `IF` header up to the `:` that closes it — a wrapped condition survives, body lines cannot leak in — and strips trailing `#` comments, not only whole-line ones. |
| 3 | `test_the_lens_agents_are_not_told_to_write_their_own_result` | Forbids only a literal `.json` inside a `Task(` fence. A prose brief outside any fence, or a path without the extension, evades. |
| 4 | `test_route_reviewers_...` | `len(kept_optional) < 2` is satisfied by dropping one optional reviewer; no call exercises the `/perf/` rule, so `performance-reviewer` routing is unasserted in both directions. |
| 5 | `test_the_coverage_call_carries_its_full_flag_set` | `_section` takes the first occurrence of the literal anywhere in the document — a Configuration paragraph documenting the full invocation satisfies it while the real call omits `--round`. |
| 6 | `test_the_result_path_is_per_slug_and_per_round` | Two unrelated whole-document substrings; nothing requires them to be the same path or to sit at the write instruction. |
| 7 | ~~`test_the_harness_yaml_routing_block_carries_the_rule`~~ **CLOSED before Phase C** | Demanded a `routing:` config key that **no AC requires** and no template renders. A SPEC-faithful implementation would have stayed RED, and its message named a non-AC-002 defect. Assertion dropped; the surviving one now requires the comment to name a lens id from `MANDATORY_LENSES`, so an unrelated use of "mandatory" cannot satisfy it. |

**Status: all seven closed.** Findings 1, 2 and 7 closed in Phase C; 3–6 closed afterwards
against the real implementation, which is what the bypass rationale predicted would make them
decidable. Each repair and what it cost:

| # | Repair | What it took |
|---|---|---|
| 3 | lens brief must not carry a write directive | The results root and `.json` are now forbidden inside any `Task(` fence, plus a **directive** regex. The first attempt forbade the substring `write` and went red on `partial-write` — the failure lens's own topic name. An over-broad *negative* is a false-RED against a correct template: the same defect as an over-broad positive, pointing the other way. |
| 4 | router: both optional rules driven | `len(kept) < 2` was satisfied by dropping ONE, so "keep ux always, strip performance always" passed. Now `kept == []` on a no-match diff, plus a `/perf/` call and a `.tsx` call each asserting the *other* optional reviewer is absent. |
| 5 | every CLI invocation carries the full flag set | Was the first occurrence anywhere in the document. Now every **invocation line** (`!uv run` / `Bash("`) is checked — the first version of this repair also caught the blocker paragraph's prose mention of the CLI and had to learn the difference between a call and a reference. |
| 6 | one concatenated path literal | Two independent whole-document substrings passed a template whose write instruction omitted the round segment while a rationale sentence quoted it. |

**What the bypass actually bought, measured.** Of the three findings that Phase C resolved, two
(#1, #2) were only *decidable* once `review.md.j2` existed — #1 in particular presented as a
false-RED against a correct implementation, which no amount of pre-implementation reasoning
would have shown. That is evidence for the bypass rationale above. It is not evidence that
findings 3–6 are wrong; they were simply never about this implementation.

## 🔬 AC-015 is unmet, and the reason is not what the SPEC guessed

The SPEC records the mutation gate as reporting `score 0% < threshold 85%` and calls that "the
correct state" for a task with no mutation run recorded. **That reading was wrong.** Diagnosed
this session:

1. mutmut 2.x refuses to run without a `.coverage` file — `FileNotFoundError: No .coverage file
   found. You must generate a coverage file to use this feature.` The 0% was never a measurement;
   it was a crashed subprocess whose traceback the wrapper swallowed into `raw_output` and
   reported as a score.
2. Generating valid coverage (`uv run --with coverage python -m coverage run
   --source=src/harness_maker -m pytest <the four test files>`, 68 passed, 86 KB `.coverage`)
   removes that error — and the gate **still** reports `score 0%`.

So there is a second failure below the first, in how `spec_mutation` invokes mutmut's test
runner (the likely candidate: the runner shells out to bare `pytest`, which cannot import
`harness_maker` outside `uv run` — the exact `ModuleNotFoundError` seen when coverage was first
attempted the same way). **Not fixed here**: that is the shared mutation harness, used by every
SPEC in the repo, and changing it blind at the end of this task risks a silent change to every
other tier-1 gate.

**What this means for AC-015.** The AC stands and is honestly unmet. What must NOT be inherited
is the SPEC's framing that a `0%`/`rc=1` gate is evidence of "no run recorded" — on this repo,
today, a green mutation gate is unreachable for any SPEC until the runner is fixed, and a red one
carries no information about the tests. **A skip is not evidence, and neither is this failure.**
Follow-up **F5** below.

## 📌 Recorded follow-ups — deliberately NOT in this task

Each is named so the next reader inherits it rather than rediscovering it. None is started.

### F1 — Run the RED gate BEFORE the reviewer gate in `/hm:execute` — **DONE 2026-08-15**
**The cheapest finding of this task, and it belongs to another stage.** Six Phase A.5 findings
here were "this test passes before the implementation exists" — five tautologies in Phase 2
(satisfied by the model's `extra="forbid"` guard) and the parallelism test in Phase 4
(satisfied by prose the template already ships at `:257`, `:337`, `:436`). Every one is
**mechanically decidable**: run the tests against the unmodified subject and any that pass are
false-REDs. The stage orders Phase A → A.5 → B, so those six cost six reviewer dispatches
instead of one pytest run. Reordering B before A.5 — or adding a pre-A.5 false-RED check —
catches them for free and leaves the reviewers to judge what only judgment can decide
(discrimination, coverage holes). **Not done here because it changes `/hm:execute`, not this
task's surface.**

### F2 — Make the lens-results path unmineable — **CLOSED 2026-08-15 (invocation hole fixed; mining DROPPED)**
*RuBench* observed an agent mining a prior round's artifacts from disk. Our defence is the
`<round>` / pass-id keying plus the sentence "written once and never reused". Content
addressing, or a per-run directory the lens brief never learns, would make it structural. Real
design work; see ADR-012's residuals.

### F3 — Measure verifier discrimination from the ledgers we already write — **DONE 2026-08-15**
*VRR-Stop* (arXiv 2607.17641) finds stopping reliability is governed by verifier discrimination
and the decision margin, not by the absolute size of estimation error. We compute neither. The
labels already exist: second-opinion PIDA dispositions (`accepted`/`rejected`) are judge-error
labels, and `review-telemetry.jsonl` / `stage-agents.jsonl` carry per-round outcomes.
Estimating false acceptance / false rejection needs no new data collection, only a reader.

### F4 — Replace fixed round caps with a marginal-gain sign test — **NOT DONE, and the measurement says why**
Our caps (≤2 confirmation passes, 1 repair round, 2-round A.5, 2-pass validator) are the
fixed-N baseline *VRR-Stop* measures itself against (+60.6pp true validity at 0.72 average
repair rounds, on a GSM8K stress setting). Its method needs only *sign identifiability*, not
accurate parameter recovery — possibly within reach even for a weak judge. Depends on F3.
Note what our k-of-N consensus (K=2) already is: an estimation-free margin rule, i.e. a crude
`VRR-Guard`. That part we got right by accident.

## 🔍 Plan Validation

**Outcome: `MAJOR_REVISION_TERMINAL`** — the 2-pass validator cap was exhausted with a second
`MAJOR_REVISION`, and the user chose to change the mechanism rather than accept the findings as
risk or abort (Interview #16).

**What was done with the 13 pass-2 findings.** Eight were the SPEC and this PLAN stating one
rule two ways; they are structurally removed by making the SPEC the sole contract holder rather
than being individually patched. The remaining five were substantive and are closed in the
revision: the diff base is now `review_base` (AC-004); the frozen root has a literal gitignored
path (AC-004); reaping has an owning phase (Phase 3); the result-file writer is named as the
main loop (AC-011); the `open_items` ledger field was dropped rather than left ownerless
(ADR-010). The `auto_fix`-off rule was additionally restated order-independently (AC-007), and
S5's missing carve-out — the pass-2 finding that C1 had *moved* the contradiction rather than
removing it — is now S5a.

**A third pass was run, out of cap, at the user's request — and refuted the rewrite's own
claim.** It returned `MAJOR_REVISION` with 11 findings, `rewrite_introduced_new_defects: true`
and `duplication_actually_removed: **false**`. The single-document restructure reduced the
duplication but did not eliminate it: ADR-004 still imposed a `harness.yaml` comment with no AC
and no owning phase, and Phase 3's exit criterion still carried an obligation (`git status`
invisibility) that no AC held. Both are now folded into AC-002 and AC-004.

**Four rounds: 8 → 11 → 13 → 11.** Changing the mechanism did not stop the compounding. What it
did change is what the findings are *about*: rounds 1–3 were dominated by the two documents
disagreeing; round 4 was dominated by genuine underspecification that had been present since
round 1 and only became visible once the propagation noise was gone — chiefly that **"new
finding" was never defined** although S4/S5/S6 and a telemetry field all key on it. Removing the
self-inflicted defects did not reduce the count; it changed the population.

**The four design gaps round 4 found are closed** (`review_base` degenerating to `HEAD` on the
two most ordinary configurations; no store for a value that must survive N rounds; `--round`
undefined for a confirmation pass, which could have counted a failed lens as exercised from a
stale directory and produced a *silent false approval by the coverage mechanism itself*; and
the zero-new-severe-with-incomplete-coverage state matching no outcome branch). Phase 1's
exit criterion, which was unsatisfiable within its own scope, was split.

**These closures are unverified, deliberately.** No fifth pass was run: four rounds of the same
lens reading the same prose showed no convergence, and the round-inflation research this PLAN
cites is explicit that buying convergence with rounds is the wrong move. More fundamentally, a
document has no oracle — every judge so far has been another model reading prose. Whether
`review_base` degenerates, and whether a reused results directory yields a false approval, are
questions **code can answer and prose cannot**. Phases 1 and 3 are pure Python and both
questions are expressible there as tests that fail today. That is the next step, and it is the
first point in this task where the adjudicator is not a model.

### F5 — The tier-1 mutation gate cannot pass for any SPEC in this repo — **FIXED 2026-08-15**

**Priority: above everything else in this list.** Diagnosed in the section above. Two stacked
faults: mutmut 2.x requires a `.coverage` file that nothing in the repo generates before the
gate, and after supplying a valid one the gate still scores 0%, which points at how
`spec_mutation` invokes mutmut's test runner.

Why it outranks F1–F4: `mutation_threshold` appears in every `*.machine.yaml` in this repo and
reads as an enforced quality floor. It is currently a **dead gate that fails closed** — the worst
of both, because it costs a red run on every SPEC while proving nothing about any of them. Every
`verification_tier: 2` SPEC has been shipping with this hole.

Concrete first step: `uv run python -m harness_maker.spec_mutation gate --yaml <any machine.yaml>
--tier 1` after generating coverage, then read `MutationReport.raw_output` rather than the score
— the wrapper swallows the runner's traceback into that field, which is how a crash has been
reading as a measurement.

**Also check whether the wrapper should fail LOUD instead of scoring 0** on a crashed runner. It
already has that shape for two cases (`mutmut not installed`, `mutmut 3.x unsupported` — both
skip non-gating with a named reason). A third branch for "the runner did not execute" would have
surfaced this the first time it happened rather than after two SPECs wrote rationale around a
number that measured nothing.


#### F5 outcome — four faults, and one the fix itself created

Fixed in `spec_mutation`; full write-up in that module's `mutation_runner_faults` docstring.

| # | Fault | Evidence |
|---|---|---|
| 1 | `_COUNTERS_RE` scanned for the words `killed:`/`survived:`; mutmut 2.x emits an **emoji-only** progress line | A healthy 55-mutant run parsed as all-zeros |
| 2 | No `--runner`, so mutmut ran the **whole suite per mutant** (~6 min vs a 600 s cap) | The first mutant always exhausted the budget |
| 3 | `score` returns 0.0 for an empty denominator, so a **non-run and a total wipeout print the same string** | Every SPEC's gate read `score 0% < threshold 85%` |
| 4 | **Created by fixing #1.** With the parser working, a *truncated* run parses to a real-looking number and was reported as the score for the whole path set | The 46% first produced by the repaired gate was a prefix, not a result |

Fault 3 is the one to remember. It is not a parsing bug — it is a **judge that cannot tell "no
observation" from "a bad observation"**, and it therefore reported the second whenever it meant
the first, for the lifetime of the gate. Two SPECs (this one included) wrote rationale around
that number. This is the same failure this task's whole subject is about, found in the
instrument the task chose as its strongest verifier.

Fault 4 is worth as much: **the repair introduced a new instance of the class it repaired.**
Caught only by re-reading the timeout branch after landing the parser fix, not by any test.

**First real measurements.** `lens_coverage.py` alone: 55 mutants, 42 killed, 13 survived —
**76%**, below the 85% floor. The four-file set does not complete inside the wall budget, so
AC-015 still has no whole-set number; the gate now says so instead of inventing one.

#### Working-tree corruption — an unrelated hazard this uncovered

An interrupted mutmut run **leaves a mutated source file on disk**. Measured: a killed run left
`if __name__ != "__main__":` in `review_telemetry.py`, which makes *importing* the module call
`sys.exit()`. It was invisible to `uv run pytest` in the runs that preceded it and would have
been committed. All four `paths_to_mutate` files were audited against `git diff` (and by reading,
for the two untracked ones); that one line was the only artifact.

`spec_mutation`'s CLI now prints a loud stderr warning naming the paths whenever a run does not
complete. It deliberately does **not** auto-revert — those files are the user's working tree.

**Standing advice: after any interrupted `mutmut run`, `git diff` the `paths_to_mutate` before
committing.**


## 📊 F1–F4 outcomes (2026-08-15)

### F1 — `Phase A.4 — false-RED screen`, before the dispatch
`execute.md.j2` gains a numbered phase between A and A.5: run the tests, record **`N failed, M
passed` as read from the summary line**, and for each passing test either fix it or justify it
in the module docstring by naming the wrong implementation it would catch and its RED positive
sibling. The justified list travels into the A.5 brief so the lenses adjudicate the
justification instead of rediscovering the test.

Two design points that are not obvious and are load-bearing:

- **It is not "all tests must fail".** Two tests in this task's own Phase 4 file are negative
  invariants, vacuously true until the construct they forbid exists. A screen that forbids them
  teaches the author to delete the invariant — the cure being worse than the disease.
- **"Do not infer the counts."** The round-5 brief in this task said `24 failed, 3 passed` when
  the truth was 25/2, because the number came from eyeballing a progress string. All three
  lenses were then sent to find a third passing test that did not exist.

Gated by `tests/render/test_render_false_red_screen.py`. Its own first run failed on a weak
anchor (`body.find("Phase A.5")` landed on the Communication Protocol sentence at the top of the
document, so the ordering assertion compared two prose mentions) — the fifth appearance of that
class in this task, caught here by the test rather than by a reviewer.

### F2 — the demonstrated hole was invocation reuse, not mining
The recorded proposal was content addressing or a directory the brief never learns. **Not built
as recorded**, for a reason worth keeping: its benefit rests on a claim about what a subagent's
Glob can reach that I cannot verify here, and shipping an unverifiable security argument is the
move this whole task is about.

What *was* found is a concrete, reproducible defect in what Phase 4 shipped. The results
directory is keyed by slug and round, so **re-running `/hm:review` on the same slug lands in the
same directory**. Measured: five files from invocation 1, then an invocation 2 in which only one
lens returns → `blocks_approval: false`, four dead lenses reported as exercised. That is exactly
the silent false approval `round_dir`'s own docstring claims the keying prevents; the keying
separates a pass from a round, not one invocation from the next.

Closed with a per-invocation `run_id`, minted once per `/hm:review`, stamped into every result
file and required by `hm lens_coverage check --run-id`. A file with an absent or foreign
`run_id` is not evidence about this invocation — **fail-closed on the absent case**, which is
where it will most often be wrong (`[fail:design]` absent-case, count:8).

**Mining: dropped, by decision (2026-08-15).** The demonstrated hole is closed. The mining threat
itself remains a hypothesis carried over from RuBench's observation in a *different* harness, and
acting on it would mean shipping a relocation whose benefit rests on an unverified claim about
what a reviewer subagent's Glob can reach. Removed from the follow-up list rather than left
open indefinitely; re-open it if a probe ever shows the reach.

### F3 — `hm verifier_discrimination report`
A reader over `second-opinion.jsonl`, no new telemetry. What it computes, and what it refuses to:

- `loss_rate` = `(skipped + failed) / calls`, per model, **call rows only** (`finding_ref ==
  "n/a"`), excluding `stage: "health"`.
- `unresolved_rate` — the share of disputed findings the verifier could not decide. VRR-Stop's
  governing quantity, never before surfaced here.
- `false_acceptance_rate` — **deliberately absent.** An `accepted` disposition means the oracle
  did not contradict the claim, not that the finding was real. Approximating it would produce a
  number indistinguishable from the real thing at the call site.

**First measurement, and it is not comfortable:**

| model | calls | loss_rate | judged | unresolved | refuted |
|---|---:|---:|---:|---:|---:|
| codex | 142 | **52.1%** | 11 | 9.1% | 18.2% |
| antigravity | 78 | **43.6%** | **0** | n/a | n/a |

Two things follow immediately. **The `k-of-2` consensus assumes two voters, and roughly half of
all second-opinion invocations produce no voice at all** — so cross-model corroboration is
frequently unavailable at the moment the gate needs it. And **antigravity has never had a single
finding reach the PIDA gate**, so every claim about its contribution rests on zero adjudicated
evidence.

### F4 — not done, and the data is the reason
`hm verifier_discrimination rounds` builds the input a sign test needs. Measured over the whole
review history:

- 15 slugs with ≥2 rounds, **16 transitions**: 2 increase, 6 flat, 8 decrease.
- **1 counterexample**: `second-opinion-invocation-and-slug-cap` went 2 → **0** → 1. A rule that
  stopped at the first non-positive round would have missed that finding.

A sign test needs the sign *identifiable*. With 16 transitions, one counterexample moves the
estimated miss rate across most of its plausible range, so it is not — and no cap is changed on
this evidence. The alternative, changing the caps anyway and writing a rationale around a
16-sample trend, is precisely the failure F5 found in the mutation gate.

#### Correction — "those caps emit nothing" was false, and unchecked

The paragraph that stood here claimed Phase A.5, confirmation passes and plan-validator passes
emitted no telemetry, and called that absence the next piece of work. **It was wrong.**
`execute.md.j2:340` has rendered a `stage_agent_ledger emit` for the A.5 gate all along, and
`stage-agents.jsonl` holds **17 `test-reviewer` rows and 25 `plan-validator` rows**.

The claim was written into the PLAN, into `verifier_discrimination`'s output payload, and into a
**passing test** — which is the worst of the three, because a gate then re-certifies the falsehood
on every run. It cost one grep to check and I did not run it. This is the fourth instance in this
task of the class the task is about, and the first one I put into a test.

Only one third of it was true: **confirmation passes** emit nothing, because Phase 5 is not built
yet. Instrument it when it lands.

#### F4's real answer for these two caps — `hm verifier_discrimination agents`

Each `(agent, slug, run_id)` is one gate episode. `released` = the last pass reached a clean
verdict; `bound_by_the_cap` = it did not, so the cap stopped the loop rather than the loop
converging.

| agent | episodes | multi-pass | released | bound | release rate |
|---|---:|---:|---:|---:|---:|
| `plan-validator` | 12 | 10 | **0** | 12 | **0.0%** |
| `test-reviewer` (A.5) | 9 | 6 | 5 | 4 | 55.6% |

**No PLAN in the recorded history has ever passed plan-validation.** Every episode ended
`MAJOR_REVISION` or `NEEDS_REVISION`, including all three 3-pass runs. A cap that never releases
is not a budget, it is a formality — and the response is *not* to raise it. A verifier that has
never once accepted is telling you about the verifier or its rubric, not about the PLANs. Note
that this task's own PLAN sits in that column: `MAJOR_REVISION_TERMINAL` after three passes.

The A.5 gate behaves differently — 5 of 9 episodes released, 2 of 6 multi-pass ones flipped to
PASS by round 2 — so its 2-round cap does real work, and its 4 bound episodes are candidates for
the sign test once there are more of them.

**A reader over an append-only ledger needs an exclusion mechanism.** There is no retract verb,
so the fabricated `aiexit-exec-p2b` row (a `PASS` emitted before its round was dispatched, ADR
disclosure above) would inflate the reviewer gate's release rate in every future aggregate,
permanently. `.claude/observability/.ledger-exclusions.json` maps run id → reason and is read by
every subcommand; this repository's copy carries that one entry. Malformed file excludes nothing
rather than everything — a torn file must not silently empty the report.


## ✅ Phase 3 remainder — freeze-ref reaping

`freeze.py` writes `refs/hm-freeze/v1/<slug>-base` once per review and a freeze commit per
confirmation pass. **Nothing deleted them.** Each ref keeps an entire frozen working tree
reachable in the object store, so the leak is bytes, not just entries.

`prune_stale` now reaps a freeze ref whose slug has no live `hm/<slug>` branch and no live
worktree — that task landed, and the commit is unreachable from any branch.

**Deliberately conservative, and this is the load-bearing part.** A slug with a live branch is
left alone even when the review looks finished, because a confirmation pass reads `<slug>-base`
rounds after it was written (AC-004). Reaping mid-review makes the pass silently re-resolve
against a drifting HEAD. Over-reaping produces a *wrong review*; under-reaping produces a few
stale refs. The asymmetry decides the default.

Slug attribution matches against the live set rather than splitting on hyphens: a split would
read `multi-word-slug-base` as slug `multi` and reap a live task's base. Gated by
`tests/unit/test_freeze_ref_reaping.py` (6 cases, including that one and a dry-run check).


## 🚨 `plan-validator` has never once released — and its verdict drives a hard halt

Measured: **0 of 12 episodes** reached `APPROVED`. Ten were multi-pass; all three 3-pass runs
also ended `MAJOR_REVISION`. This task's own PLAN is in that column.

**The rubric explains it** (`plan-validator_body.md.j2:79-81`):

- `APPROVED` → **zero critical AND zero warning**
- `NEEDS_REVISION` → zero critical, ≥1 warning
- `MAJOR_REVISION` → ≥1 critical

`APPROVED` therefore demands a document an LLM critic finds *nothing* wrong with, at any
severity, with no cap on what may be called critical. A critic asked to critique will produce at
least one finding essentially always, so the clean verdict is not a high bar — it is unreachable.

**Why it matters operationally.** `plan.md.j2:716`: a second-pass `MAJOR_REVISION` with the A/B
question unanswered sets `--judgment-gate blocked`, and **no autonomy level clears it, auto_full
included**. So the halt this gate drives is the **default path on every task**.

### The 12 episodes, read — and the earlier reading was wrong

I first wrote that a gate firing on 100% of inputs "carries no information about which input was
risky" and that the clean verdict was "unreachable". **The recorded critiques refute that.**

Every PLAN's `## 🔍 Plan Validation` section records what happened to the blocking findings, and
the authors verified them against source before acting:

| PLAN | Recorded outcome of the criticals |
|---|---|
| `workflow-time-token-savings` | "Every critical from all three rounds was verified against source before being acted on, and **every one was accurate**." |
| `second-opinion-oracle-polyglot` | "Every critical was fact-checked against the source before revising; **all four held**." |
| `onboarding-interview-ux` | "Both critical findings were verified against the repo before acceptance, and **both held**." |
| `antigravity-second-opinion-timeout` | Each critical annotated "Verified by `rg`" / "Verified (`0` references)" / "Verified by file read". |
| `multi-lens-review-round` | The validator "confirmed 10 by reading code and judged 2". |
| `opus5-selfreview-vs-harness-gates` | Pass-1 criticals verified at named source lines; pass 2's three were **created by the pass-1 fixes**. |

Refutations do occur in these records — but they are of **cross-model (codex) findings**, not of
the validator's own criticals (`plan-interview-comprehension`: two codex claims refuted, the
validator's own confirmed at pass 2).

**So the `critical` labels were warranted.** The 0% release rate is a true statement about the
PLAN drafts, not about the rubric. `APPROVED` requiring zero criticals is correct *if criticals
are real*, and here they were.

What is actually broken is something else, and this task has measured it everywhere: **the loop
does not converge, because each revision introduces new criticals.** `opus5` states it outright —
pass 2's three criticals were produced by pass 1's fixes. More passes therefore cannot reach
`APPROVED`; the 2-pass cap is not what is blocking release.

And the halt fires correctly. A human is being asked to accept **real, source-verified critical
defects** as risk. That is expensive on every task and it is also the right question.

### Decision: change nothing here

Not the rubric, not the cap, not the halt. The number that looked like a mis-calibrated verifier
turned out to be a well-calibrated one pointed at a population that genuinely fails, and the
correct response to those two cases is opposite. The `hm verifier_discrimination agents` warning
was rewritten to say exactly that rather than to diagnose: a `[zero-release gate]` line now
states that the ledger **cannot** distinguish the two readings and sends the reader to the
episodes' recorded critiques.

**The one thing worth remembering** is that no aggregate could have settled this. `release_rate:
0.0` was compatible with both stories, and only reading twelve prose records decided between
them. A metric that cannot separate "the judge is broken" from "the work is bad" will be read as
whichever the reader already believed.


## ✅ Phase 5 — the confirmation pass (2026-08-15)

Criterion ⑤ shipped. `## Confirmation Pass` runs **only on the APPROVED path**, freezes the
working tree into `refs/hm-freeze/v1/<slug>-<pass-id>` via a temporary index, reads `review_base`
from its round-1 store, and dispatches all five lenses over `review_base..<freeze commit>`.

Three things are worth carrying forward:

- **`read-base` fails loudly instead of re-resolving.** It is a round-trip whose purpose is to
  *prevent* a computation. A pass that recomputes the base gets one that drifted with the commits
  landed during the review, and the drift is invisible in the diff the pass then reviews.
- **The six-arm outcome block does not compress.** S4a exists because an earlier draft collapsed
  two arms and produced a state matching **no** branch (zero-new-severe with incomplete
  coverage). Merging arms to save bytes is how that hole was made.
- **A defect I introduced, caught by an existing gate.** The cross-model re-read paragraph
  rendered unconditionally, so a harness with `second_opinion.models: []` got prose about a
  frozen voter set it never had. `test_review_pida_and_freeze` caught it; the paragraph is now
  Jinja-gated. Worth noting the shape: the new feature's own 22 tests were all green, and the
  thing that failed was a *pre-existing* test guarding an axis the new work did not think about.

Following F1's own rule, the tests were run **before** anything was reviewed: 22 tests, 0 passing
against the unmodified template — every one an ERROR on the absent `## Confirmation Pass`
section, so there was no false-RED to justify.

`hm freeze` gained `commit` and `read-base`, both exercised through the CLI entry point rather
than through their functions (`[fail:test] shipped-entry-point-not-exercised`, count:4), and the
freeze test asserts the frozen span contains an **uncommitted** fix — the state the gate is about
to approve, since wrapup owns commits.


## ✅ Phase 6 — terminal whole-document re-validation (2026-08-15)

AC-010 shipped as `plan.md.j2` Step 4.5, **zero new round-trips** — it re-aims the second pass
the two-pass cap already allows, from "the sections you revised" at "the whole document".

The instruction carries its own measurement, and that is deliberate. 12 recorded episodes, none
clean, blocking findings source-verified, one PLAN recording that pass 2's criticals were created
by pass 1's fixes. Those numbers are the argument both *for* re-reading the whole document (a
revision's damage is cross-section) and *against* raising the cap (three-pass episodes also ended
`MAJOR_REVISION`). Stripped of them the step reads as bureaucracy, and this repository records
what happens to a costly mandatory step presented without justification
(`[wiki:gotcha] loop-body-skipping-review-stage`).

`MAJOR_REVISION_TERMINAL` is a new **frontmatter** value; the ledger keeps its three verdicts.

## 🔓 A shipped gate that had frozen two templates permanently

Phase 6 was blocked by `comprehension_zero_cost_golden.json`, another task's **deliberately
immutable** oracle. It digests the **whole** `plan` and `spec` documents at `depth: minimal` and
compares against a frozen pre-change SHA, with a tamper test that correctly forbids regeneration.

The claim it was built for — AC-003, "a third-party opt-out install pays zero for the
comprehension partial" — is strictly weaker than what it asserted. Digesting whole documents also
froze every unrelated line in them, so **any** later edit to `plan.md.j2` or `spec.md.j2` failed
it, with only two exits: abandon the edit, or launder the oracle. AC-010 was the first stage edit
to arrive after that work landed, and it hit the wall immediately.

**Narrowed, not regenerated** (user decision). The zero-cost claim now lives where the bytes are
produced: `test_the_partial_emits_the_empty_string_at_minimal` renders the partial standalone at
`minimal`, for both stages and all four blocks, and requires `""`. That is a **same-commit
oracle** — no snapshot, catches the stray-newline hazard directly rather than as a side effect of
hashing a whole file, and stays true however the enclosing documents evolve. The marker-absence
assertion on the full render is kept. The golden file, its `source_sha` provenance and its tamper
test are **untouched**; the whole-document comparison skips with a stated reason once every
tracked document has moved.

**The generalisable point.** An oracle that over-asserts is not conservatively safe. This one
bought a stronger guarantee than its AC needed and paid for it by making two shipped templates
unmodifiable — a cost invisible at the moment it was written, and payable only by whoever arrives
next. "Pin the narrowest thing that would actually catch the defect" is the rule; here the
narrowest thing was three lines away, at the partial itself.
