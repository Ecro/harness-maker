---
type: plan
task_slug: token-efficiency-autopilot-ux-speed
status: planning
created: 2026-09-08
tags: [harness-maker, plan, python, observability, parity, autopilot, token-economy]
spec: "[[SPEC-token-efficiency-autopilot-ux-speed]]"
research_doc: "[[RESEARCH-token-efficiency-autopilot-ux-speed]]"
interview_rounds: 2
adrs: 12
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Restore the evidence layer first, then close 15 prose/runtime parity gaps"
spec_need_verdict: add
spec_need_target: token-efficiency-autopilot-ux-speed
surface_allowance:
  chars: 1865
  round_trips:
    wrapup: 1
    hm-wrapup: 1
  reason: >-
    Four attributed growths and one shrink, itemised in the delta doc. Phase 1 (+47) names
    work-docs/BASELINE-ledger-rollup.md in wrapup_land's typed manifest, in both invocation
    branches of wrapup.md.j2 — the only mechanism that stages the roll-up when worktree.enabled is
    false, because the worktree-sweep records skipped-not-isolated when the worktree IS the base.
    Phase 4 (+1455) adds the stage-guarded backgrounding instruction to the shared second-opinion
    dispatch partial, which this repo renders because second_opinion.models is non-empty. Phase 5
    (-54) RETRACTS the reviewers.enabled bullet from review.md.j2 and corrects a disclosed default.
    The review fixes (+416) add the two instructions whose ABSENCE was the P1: wrapup.md.j2 gains
    the roll-up producer, because the manifest staged a path nothing wrote, and health.md.j2 passes
    --targets, because the applicability rule had no production caller. Every one of these is a
    command or an instruction the model executes, so each costs rendered characters.
    round_trips: the roll-up producer is one new call site per variant (claude wrapup, codex
    hm-wrapup). Declared rather than regenerating surface_baseline.json, which rewrites the frozen
    chars in the same file and would destroy the ratchet it sits next to.
  delta_doc: BASELINE-DELTA-token-efficiency-autopilot-ux-speed.md
---

# PLAN — evidence layer + prose/runtime parity

## 🎯 Executive Summary

**TL;DR** — Land the evidence layer (Phases 1–2), then close the fourteen shipped surfaces
that describe behaviour the runtime does not perform (Phases 3–6).

**What.** Two halves, sequenced. The **evidence half** makes harness-maker's
self-measurement produce readable, clone-surviving output and gives `/hm:health` the
vocabulary to distinguish *stopped correctly* from *never fired* from *cannot fire here*.
The **parity half** deletes or wires **fifteen** surfaces where shipped prose asserts
behaviour no code performs — fourteen found by research, the fifteenth by plan validation.

**Why.** All five observability ledgers held zero rows at measurement time, and
`.gitignore:73` discards them, so every optimization decision on the four axes the user named
would be made blind. The single largest un-taken token win (≈$390 of $697) has been
pre-registered and unrun for a month because nothing would record an arm. Meanwhile a guard
with zero producers ships 24,884 chars into harnesses that can never use it, and CLAUDE.md
recommends an escape hatch the code cannot honour.

**Key decisions.** Evidence before parity ([ADR-001](#adr-001-the-evidence-half-lands-before-the-parity-half));
durability via an overwritten roll-up on a committed deliverable path
([ADR-002](#adr-002-ledger-durability-is-an-overwritten-roll-up-under-work-docs), [ADR-010](#adr-010-the-roll-up-covers-the-four-ledgers-and-excludes-stage-span-durations));
on the `reviewers.enabled` mismatch the **prose retracts and the code stands**
([ADR-003](#adr-003-on-reviewersenabled-the-prose-retracts-and-the-code-stands));
on the `context_lint` mismatch the **code moves and the prose stands**
([ADR-004](#adr-004-on-context_lint-the-code-moves-and-the-prose-stands)) — the two
mismatches resolve in opposite directions, and the asymmetry is the point;
the doc-truth property starts where the evidence is
([ADR-005](#adr-005-the-doc-truth-property-starts-at-the-rendered-disclosure-table));
the dead guard is deleted and the advance block gains the level gate
([ADR-006](#adr-006-delete-the-dead-guard-and-gate-the-advance-block-on-level));
the concurrency claim becomes true rather than being downgraded
([ADR-007](#adr-007-wire-run_in_background-rather-than-downgrade-the-claim), [ADR-009](#adr-009-the-live-dispatch-runs-under-integration1-not-the-pr-gate));
proportionality is deferred ([ADR-008](#adr-008-defer-approach-c-proportionality));
and the per-command ratchet is re-derived **once**, as a recorded measurement-subject change
([ADR-011](#adr-011-the-ratchet-is-re-derived-because-its-measurement-subject-changed)).

**Estimated impact.** 24,884 chars recovered for every `gated` harness; up to 300 s per
review taken off the critical path; the `EXPERIMENT-session-length-ab` arms become
recordable, which is the gate on a measured ≈$390. **No token or wall-clock saving is
claimed by this unit** — see [Success Criteria](#-success-criteria).

## 📚 Prior Work

- **`work-docs/RESEARCH-token-efficiency-autopilot-ux-speed.md`** — the measured baseline
  and the rejection list. Read its `⚠️ Pitfalls` before proposing any saving: twelve
  directions are prior-rejected with recorded reasons, and three of them (compressing
  CLAUDE.md, making `second_opinion` opt-in, shrinking the lens set) are the ones a fresh
  reader reaches for first.
- **`PLAN-harness-diet`** ADR-001/002 — the −530,222 char (−45.2%) fused-command deletion.
  The one large surface win, already taken. ADR-004 defers the review cost centre ($658,
  22.4%) to a PLAN that does not exist.
- **`PLAN-token-economy-step-pruning`** ADR-001 names round-trips as the correct lever, then
  compacted prose instead and delivered ~0. ADR-016/017 record the estimate collapse
  (8.2% → 12.0% → 4.7% → net zero) and the withdrawn "documentation-only" trim that removed
  runtime-behavioural instructions.
- **`PLAN-render-observability-audit`** ADR-004 relocated CLAUDE.md's two largest blocks to
  `docs/` (624 → 392 lines). `:234-236` and `:500` R6 **accept** the line-vs-token
  divergence, and `SPEC-workflow-loop-efficiency` bounds the CLAUDE.md upside at ~4% of
  total spend.
- **`RESEARCH-context-carry-economics-2026-07-28`** — the $697 / $390 figures, and the
  measurement that delegation does not fix carry ("reduces what is added; cannot reduce what
  is already there").
- **`[wiki:convention] wrong-transparency-table-worse-than-none`** — the remedy pattern this
  PLAN generalizes in ADR-005: bind a documented claim to the object that produces the
  value, and ask "would this still pass if the disclosed value were inverted?".
- **`[wiki:architecture] narrative-output-needs-explicit-envelope`** — one real dispatch is
  the only evidence for an output-shape or behaviour contract; fixture-shaped output proves
  the validator, never the producer. This is why ADR-007's proof is a live run.
- **`[wiki:architecture] one-rule-one-normative-site-others-defer`** — the deletion test for
  duplicated normative prose, and the record of what five review rounds cost when a rule was
  written in four places.
- **`[wiki:architecture] autonomy-levels-live-in-two-places-and-a-test-finds-the-third`** —
  `ask` is the fresh-render default and absent/malformed pins to `gated`, which is why
  ADR-006's level gate matters to real installs and not only to a hypothetical.
- **Adjacent defect, deliberately OUT of scope.** `hm memory_retrieve` returned
  `(no entries matched)` for this task's topic while the two most relevant wiki entries
  (`wrong-transparency-table-worse-than-none`,
  `one-rule-one-normative-site-others-defer`) exist and were located by direct grep. That is
  a reader reporting absence where the thing is present — structurally the same shape as
  AC-004, and the same family as
  `[wiki:gotcha] memory-retrieve-silent-empty-on-missing-close-marker`. **It is excluded on a
  narrower ground than "the scope is closed"** — the scope *was* widened one round later, for
  the `review.md:139` contradiction, so a blanket closure would be a reason this document
  itself refutes. The distinction that holds: AC-015 closes the *other half of a contract this
  unit is already changing* (ADR-003 retracts the CLAUDE.md half, so leaving the rendered half
  would make that ADR partly false), whereas the retrieval prefilter is an unrelated
  component with no edge to anything here. Recorded so the silence is not later read as
  "nobody noticed", and so the *reason* is auditable rather than a count.

## 🎙️ Interview Transcript

SPEC-stage rounds are recorded in `SPEC-…#🔍 Refinement Decisions` and are not re-litigated
here (Case B inheritance: the six SPEC categories were locked, only the five open questions
were opened).

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Phase ordering | Implementation phasing | Does the evidence half or the parity half land first? | D-first / self-provable-parity-first / split into two PLANs | **D-first** | Accepts that the largest immediate recovery (24,884 chars) moves to Phase 3 | ADR-001 |
| 2 | AC-007 document range | Scope boundaries | Which document set does the inversion property range over? | rendered `make.md` table then extend / all doc sets at once / no property, four goldens | **`make.md` table, toggleable extension** | Starts where a truth-regression is already recorded; bounds R5 | ADR-005 |
| 3 | `context_lint` mismatch | Contract shape | CLAUDE.md says the renderer warns; there is no production caller. Which side moves? | wire it / retract the doc / wire + switch unit to chars | **wire it** | Warn, never block, so an existing harness is not broken; unit stays lines (the char switch is prior-bounded at ~4%) | ADR-004 |
| 4 | Roll-up shape | Observability | Overwritten snapshot, append-only, or per-window files? | single overwritten snapshot / append-only / per-window | **single overwritten snapshot** | Follows the `observability/dashboard.md` precedent; git preserves history, the file stays readable | ADR-002 |
| 5 | Ratchet collision | Risk tolerance | `second_opinion` in the ratchet render exceeds review's 1,403-char slack ~7.5×, but the Contract Boundary forbids raising a ceiling | ADR + re-baseline + carve-out / drop AC-013's second half / a separate models-on ceiling table | **ADR + re-baseline + carve-out** | The aggregate arm cannot attribute growth to a command, so abandoning the per-command ceiling makes review's ~10.6 kB permanently unattributable; a second ceiling table would violate one-rule-one-normative-site | ADR-011 |
| 6 | Fifteenth parity gap | Scope boundaries | `review.md:139` instructs the model to start from `reviewers.enabled` while the same file's generated dispatch table ignores it — fold in or defer? | fold into Phase 5 (14→15) / accept as risk / separate unit | **fold into Phase 5** | It is the other half of the contract ADR-003 addresses, in the largest rendered command; retracting only the CLAUDE.md half would make ADR-003 itself partly false | ADR-003 |

**Round 2 origin.** Rows 5–6 were opened by plan validation, not by the ambiguity list —
the validator returned `MAJOR_REVISION` with fifteen findings, and these two were the only
ones presenting a genuine A/B/C choice. The other thirteen were factual or mechanism errors
with a single sound resolution and were applied as revisions; a round whose answer is
predetermined has zero expected information gain, and the record of what was corrected is in
`## 🔍 Plan Validation` rather than as thirteen manufactured questions.

**Round 1 exit gate.** Three further candidates were generated and none passed the 5-term
inequality: the AC-007 toggle mechanism (EIG below ε — a module-level list plus a documented
extension procedure is derivable), warn-vs-block for the wired linter (common-ground:
CLAUDE.md already specifies warn; confidence 0.9), and whether wrapup stages the roll-up
(common-ground: `work-docs/` is already in the deliverable commit, and AC-001's
clone-readback catches a miss; confidence 0.85). Interview closed at one round.

## 📐 Architecture Decision Records

### ADR-001: The evidence half lands before the parity half
**Status:** Accepted (2026-09-08, via /hm:plan interview)
**Context:** The parity work is mostly self-provable from render diffs and document
inversion, but AC-006's oracle is a recorded live run, and the ledgers that would record it
hold zero rows.
**Decision:** Phases 1–2 deliver the evidence layer; Phases 3–6 deliver parity. Phase 3's
`depends_on: [2]` is a **decisional** dependency, not a technical one.
**Consequences:**
- ✅ Every later phase can be measured, and AC-006 has a recording surface when it runs.
- ⚠️ The largest immediate recovery (24,884 chars) is deferred to Phase 3.
- ⚠️ A future reader may relax Phase 3–6's `depends_on` once the ordering rationale is spent; the phases say so explicitly so the constraint is not mistaken for a technical one.
**Rejected alternatives:**
- Self-provable parity first — rejected because the phases that ran before the evidence layer arrived would not record their own effect, which is the exact condition this unit exists to end.
- Two separate PLANs — rejected because it reverses the SPEC's locked D+A scope and would require re-deciding the SPEC.
**Source:** Interview #1

### ADR-002: Ledger durability is an overwritten roll-up under `work-docs/`
**Status:** Accepted (2026-09-08, via /hm:plan interview)
**Context:** `.gitignore:73` excludes `.claude/observability/*`, so measurements are
per-machine and vanish on a fresh clone, while the narrative (`work-docs/`, `.claude/memory/`)
is committed.
**Decision:** The raw ledgers stay gitignored. A roll-up aggregate is written as a **single
file, fully overwritten on each generation**, at the named path
**`work-docs/BASELINE-ledger-rollup.md`**, and that path is added to `wrapup_land`'s typed
manifest as an `--optional` entry.
**Consequences:**
- ✅ **Blast radius zero, but for a narrower reason than "work-docs/ is staged".** `work-docs/` is **not** blanket-staged: `.gitignore:104` is `work-docs/*` followed by an explicit negation allowlist (fourteen negation lines, of which the twelve `!work-docs/<X>-*.md` entries are the ones bound to the prefix set), and `worktree.py:170-194` declares `DELIVERABLE_PREFIXES` as one definition with three consumers (the gitignore negations, `_is_deliverable_path` in the create-guard, and `wrapup.md.j2`'s staging flags) that `tests/structural/test_deliverable_single_source.py` asserts are equal. `BASELINE-` is **already** in that set, so choosing it moves no consumer. A new prefix would have meant editing all three — the very defense this ADR claims to avoid touching.
- ✅ The `--optional` manifest entry is what makes the guarantee hold at `worktree.enabled: false`. The `worktree-sweep` row that would otherwise catch an unnamed file records `skipped-not-isolated` when `--worktree` IS `--base`, so without the manifest entry a Side harness writes the roll-up and never commits it.
- ✅ One file, always the current picture; git holds the history.
- ⚠️ A regenerated deliverable adds diff noise to the wrapup commit; the snapshot form keeps that to one file rather than a growing log interleaved with human documents.
- ⚠️ `_is_harness_artifact` (the finalize dirt-filter, `worktree.py:653`) deliberately does not forgive deliverables, so a machine-regenerated roll-up is stash-preserved user dirt on every finalize. Accepted: preservation is the safe direction.
- ⚠️ Inherited limitation: neither dirt-filter covers a non-default `work_docs.dir` (`worktree.py:122-126`, `:164-166`), so the staging guarantee is scoped to the default directory.
**Rejected alternatives:**
- Committing the raw ledgers / un-ignoring `.claude/observability/` — rejected because that directory is listed in `worktree._HARNESS_CHURN_DIRS` (`worktree.py:109-117`), which both the finalize dirt-filter and the create-guard read; a committed path beneath it perturbs the dirt classification the defense depends on. (The symbol is `_HARNESS_CHURN_DIRS`. `_HARNESS_CHURN_PREFIXES` appears in CLAUDE.md and **does not exist in the source** — the siblings are `_HARNESS_CHURN_FILES`, `_HARNESS_CHURN_GLOBS` and `_HARNESS_ARTIFACT_PREFIXES`. This repo has paid for a phantom citation before: CLAUDE.md's own correction note records that following a cited-but-absent template path "would have created a new inert file rather than erroring".)
- Append-only — rejected because a growing machine log inside the deliverable directory lands a diff line in every wrapup commit.
- Per-window files — rejected because `work-docs/` is already 407 documents and a reader would have to decide which file is current.
**Source:** Interview #4

### ADR-003: On `reviewers.enabled`, the prose retracts and the code stands
**Status:** Accepted (2026-09-08, via /hm:spec interview, carried here)
**Context:** CLAUDE.md offers shrinking `reviewers.enabled` as the user's lever against
language-conditional fan-out cost. `lens_dispatch(preset)` takes no such argument, so the
list is not an input to the dispatch table and narrowing it has no effect on what the model
is told to invoke.

> **Premise corrected 2026-09-08 (Phase 5, A.5 round 1).** This paragraph used to add "and the
> rendered review dispatches `test-reviewer` and `concurrency-reviewer` although neither is in
> `enabled`". That was **false**: `interview.py:127-137`'s `_PROD_ENABLED_REVIEWERS` contains
> both, and `interview.py:978` preserves a non-empty user list, so on every harness a producer
> can emit, the dispatched set is a **strict subset** of `enabled`. The empty `enabled` behind
> the original claim came from constructing `InterviewAnswers` directly in a measurement script.
> The decision below is unaffected — the lever is still false, for the stated reason — but the
> test that binds it had to change shape, because a synthetic `[]` also suppresses the
> `{% if enabled | length > 1 %}` two-pass section and would have made the verdict independent
> of the fix.
**Decision:** Retract the recommendation. `conditional_router.py` is unchanged. The
surrounding "reviewer fan-out is language-conditional" section is **kept** — only the
false-lever sentence is removed, with a pointer to the deferred Approach C. The **fifteenth
gap is folded in**: the rendered `review.md`'s instruction to start from `reviewers.enabled`
is reconciled in Phase 5 (AC-015), because retracting only the CLAUDE.md half would leave
this ADR itself partly false.

**The replacement wording must state the shipped semantics, which are the opposite of
"asset-activation only".** `synthesize.py:3-5`: *every preset installs the FULL skill + agent
inventory*, and `reviewers.enabled` / `skills.enabled` govern **default activation**. So
`enabled` **is** the activation list and `installed` governs nothing — verified on disk, where
`test-reviewer.md` and `judgment-reviewer.md` exist while appearing in neither list. `enabled`
also still gates rendered output (`review.md.j2:279` branches on its length). The accurate
retraction is therefore: *`reviewers.enabled` is the default-activation list; it is **not** an
input to the lens fan-out, which `lens_dispatch(preset)` composes from the preset alone.*
**Consequences:**
- ✅ The documented lever and the code stop disagreeing, without touching lens coverage.
- ⚠️ Users are left with no lever for fan-out cost until Approach C ships. Stated in the retraction itself rather than left silent.
- ✅ The harness-bench record (+52% on Python, no gain on C firmware) survives, so the silence is not later read as an unexamined hole.
**Rejected alternatives:**
- Give `lens_dispatch` an `enabled` argument — rejected on **orthogonality**, which is the reason that actually holds: `LENS_DISPATCH` (`conditional_router.py:104-138`) binds each of the seven lenses to a hard-coded agent name, and `lens_dispatch` (`:141-160`) composes `mandatory_lenses(preset) + routable_lenses(preset)`; `reviewers.enabled` is not an input at any point, which is exactly why `test-reviewer` and `concurrency-reviewer` are dispatched. Making it an input would mean redefining what a lens *is*, and the data that would justify a narrowing rule is this unit's output. **The earlier draft of this ADR rejected it via `lens_coverage.blocks_approval` instead, and that reason does not hold** — `blocks_approval` is about mandatory **lenses**, while the retracted recommendation is about **reviewers**, and `harness.yaml:78-81` separates the two ("Routing narrows the OPTIONAL reviewers … only"). Narrowing `enabled` cannot drop a mandatory lens.
- Document the gap and change neither side — rejected because a standing false recommendation is the `wrong-transparency-table-worse-than-none` failure mode by definition.
**Source:** SPEC interview, Round 1

### ADR-004: On `context_lint`, the code moves and the prose stands
**Status:** Accepted (2026-09-08, via /hm:plan interview)
**Context:** CLAUDE.md states the renderer warns on over-threshold assets. `context_lint.lint()`
has no production caller — it is invoked only by the `context-linter` skill's own snippet and
by tests.
**Decision:** Wire a production caller on the render path so the renderer actually warns.
**Warn only, never block.** The measurement unit stays lines.
**Consequences:**
- ✅ A documented, already-relied-upon behaviour becomes real.
- ⚠️ Re-rendering an existing harness may surface a warning that was never seen before; `render-must-not-degrade-live-harness` applies, and warn-not-block is what keeps that from being a break.
- ⚠️ The line-based unit remains blind to character density (CLAUDE.md passes 392/500 lines at 60,921 chars). Left as-is deliberately: the divergence is prior-accepted and the upside is bounded at ~4% of total spend.
**Rejected alternatives:**
- Retract the doc line to "advisory via the skill" — rejected because the warn is useful and users already read it as real; retracting removes the only thing enforcing the documented thresholds.
- Wire it and switch the unit to characters — rejected as scope widening against a prior-bounded ~4% ceiling; recorded in RESEARCH as a meter defect worth a separate unit.
**Source:** Interview #3

> The opposite resolutions of ADR-003 and ADR-004 are deliberate. A prose/runtime mismatch
> is not a defect in a fixed direction: the side that moves is whichever one is **wrong**.
> `reviewers.enabled` is **orthogonal** to the lens fan-out by construction — it is not an
> input to `lens_dispatch` at any point — so a document offering it as the fan-out lever was
> wrong about the mechanism, and no code change makes the offer true without redefining what
> a lens is. The renderer plainly should warn and a caller is a line of wiring, so there the
> code was wrong. **ADR-012 is deliberately excluded from this argument.** Its mismatch is not
> the same shape: ADR-003 and ADR-004 are both *shipped* prose contradicting runtime
> (CLAUDE.md, the renderer), while ADR-012's wrong claim lives in an internal RESEARCH audit
> that ships to nobody. There the runtime was right, the audit was wrong, and the resolution is
> an ordinary correction of an internal document — not a third direction of this asymmetry.
> Generalising the argument onto it would weaken the one paragraph whose job is to explain why
> two *identical-looking* defects resolve oppositely.

### ADR-005: The doc-truth property starts at the rendered disclosure table
**Status:** Accepted (2026-09-08, via /hm:plan interview)
**Context:** AC-007 requires that inverting a disclosed default in its producing object makes
the guarding assertion fail. Ranging over every document at once risks false positives on
prose that merely mentions a config name (risk R5); ranging too narrowly reproduces the gap.
**Decision:** The property ranges over the rendered `make.md` disclosure table first, with an
explicit, extensible list of additional document sets.
**Consequences:**
- ✅ Starts where a truth regression is already recorded — that table graded D in round 1 of the onboarding work because its gate asserted presence, not truth.
- ✅ Extension is a one-line list change, so later coverage does not need a new mechanism.
- ⚠️ CLAUDE.md, README and `docs/` are not covered by the property on day one; their four known false claims are closed by concrete goldens (AC-008, AC-009, AC-011) in the same phase.
**Rejected alternatives:**
- All document sets at once — rejected on R5: a broad predicate produces false positives a human must then classify, in the same phase that is already changing four documents.
- Four goldens and no property — rejected because it leaves nothing preventing a fifth false claim, and presence-asserting greps are exactly what passed on inverted content before.
**Source:** Interview #2

### ADR-006: Delete the dead guard and gate the advance block on level
**Status:** Accepted (2026-09-08, via /hm:spec interview, carried here)
**Context:** `autopilot_advance_enabled` has zero producers — its only reference is the
consumer at `stage_end_summary.md.j2:24` with `| default(true)`, and its sole producer
`workflow_fuse.py` no longer exists. The advance block is not gated on `autonomy.level`, so a
`gated` harness ships 24,884 chars that can only ever emit `kill_switch`.
**Decision:** Delete the dead name and gate the advance block on `autonomy.level != "gated"`.
The picker block is untouched.
**Consequences:**
- ✅ A `gated` harness stops paying for surface it cannot use. `ask` is the fresh-render default and absent/malformed pins to `gated`, so this reaches real installs.
- ✅ The `auto_safe` render — this repo's own — is unchanged, so no rendered behaviour moves for users who are actually on autopilot.
- ⚠️ This is a removal, and the character floor (`measured × 0.80`) cannot see a single deleted instruction. Every removal is recorded in `_ALLOWED_REMOVALS` keyed `<command>@<dev_mode>`.
**Rejected alternatives:**
- Delete only the dead flag — rejected because it leaves the 24,884 chars shipping into gated harnesses.
- Retire the picker block too — rejected because the picker is already correctly gated on `level != "gated"` and therefore does not render in a gated harness; there is nothing to retire.
**Source:** SPEC interview, Round 1

### ADR-007: Wire `run_in_background` rather than downgrade the claim
**Status:** Accepted (2026-09-08, via /hm:spec interview, carried here)
**Context:** ADR-011 of the review work hoisted the second-opinion call to run concurrently
with Pass 1, explicitly to stop it being "a fourth serial barrier for no reason".
`run_in_background` occurs **zero** times in templates and rendered commands, so the
foreground Bash blocks up to `CODEX_TIMEOUT_S=300`.
**Decision:** Wire real backgrounding at the dispatch site in the review template. The
existing hoist prose stands.
**Consequences:**
- ✅ Up to 300 s per review leaves the critical path, and the claim already in the harness becomes true.
- ⚠️ The proof is a live run, which is non-deterministic and costs a real cross-model call (R2).
- ✅ `second_opinion_invoke.py` is untouched — the change is at the dispatch site, so the invoker keeps sole ownership of CLI construction.
**Rejected alternatives:**
- Downgrade ADR-011's claim to ordering-only — rejected because the saving is real and available; the claim is not the problem, the missing mechanism is.
**Source:** SPEC interview, Round 1

### ADR-008: Defer Approach C (proportionality)
**Status:** Accepted (2026-09-08, via /hm:spec interview, carried here)
**Context:** An auto-triaged light path by diff size is the strongest user-facing wall-clock
win found (measured spread 12 min / 90 min / 5.5 h across comparable spec-driven tools, and
the one criticism no shipped tool has answered).
**Decision:** Out of scope. Scope is D + A — fourteen parity gaps at the time this ADR was
written, fifteen after interview round 6 folded in the `review.md:139` contradiction. The
deferral of Approach C is what this ADR locks; the gap *count* is not part of that lock and is
recorded here only so a later reader is not misled by a stale number.
**Consequences:**
- ✅ This unit stays provable; a triage rule would need data it does not yet have.
- ⚠️ The highest user-noticed win is postponed.
- ✅ The data that would justify a triage rule is this unit's own output, so the deferral is ordered rather than indefinite.
**Rejected alternatives:**
- Design C now — rejected because an unjustified triage rule collides with `lens_coverage.blocks_approval`, and under-scoping silently converts a quality gate into a skipped one.
**Source:** SPEC interview, Round 1

### ADR-009: The live dispatch runs under `INTEGRATION=1`, not the PR gate
**Status:** Accepted (2026-09-08, defaulted with reason — 5-term gate, common-ground)
**Context:** AC-006's oracle is one real `/hm:review` dispatch. CLAUDE.md's test policy
confines real external calls to `INTEGRATION=1`; `release.yml` already carries a post-tag
`boundary-advisory` job.
**Decision:** The live dispatch is an `INTEGRATION=1` fixture. `boundary-advisory` is named as
the place a post-tag advisory run can go without new PR-gate policy.
**Consequences:**
- ✅ No new CI policy, and no cross-model call in the PR gate.
- ⚠️ The AC is proven on demand rather than continuously; a regression can therefore ship. The render-grep precondition stays as the cheap continuous half, explicitly not as the proof.
**Rejected alternatives:**
- Put the live dispatch in the PR gate — rejected as a policy change beyond this unit, and a per-PR cross-model call has a recurring cost the unit does not need to incur to prove the AC once.
**Source:** Step E 5-term gate (skipped as common-ground; recorded because the default is a decision)

### ADR-010: The roll-up covers the four ledgers and excludes stage-span durations
**Status:** Accepted (2026-09-08, defaulted with reason — 5-term gate, common-ground)
**Context:** `stage-spans.jsonl` records `start`/`end` events with no duration field, so
durations must be derived by pairing. `economics.py:501` forbids summing wall-clock scopes,
and one such ratio has already been retracted.
**Decision:** The roll-up aggregates `auto-advance`, `stage-agents`, `second-opinion` and
`delegation`. Stage-span durations are excluded. **The roll-up composes the shipped readers
(`verifier_discrimination`, `ledger_exclusions`) rather than re-deriving the formula**, and
`tests/unit/test_ledger_exclusions_call_sites.py` is extended to name the new entry point in
the same commit.
**Additional consequence:** ✅ this is what keeps the roll-up from becoming a *third*
aggregator over a ledger whose hand-aggregation was already wrong by 30×. That test drives its
covered entry points **by name**, and states its own reason — "a correct helper wired to
nothing is the defect, not the fix" — so a new aggregator in `autopilot_ledger.py` could omit
`is_excluded` entirely with every existing test green. CLAUDE.md is directive here as well:
use the shipped reader, do not hand-calculate.
**Consequences:**
- ✅ The roll-up cannot be read as a summable wall-clock total, so the retracted-ratio mistake has no surface here.
- ⚠️ Wall-clock remains measured only by the existing stage-median path, at n=1–9 with `spec` absent entirely.
**Rejected alternatives:**
- Include paired-span durations — rejected because the moment durations appear beside counts in one document, summing them is the obvious next step and it is forbidden.
**Source:** Step E 5-term gate (skipped as common-ground; recorded because the default is a decision)

### ADR-011: The ratchet is re-derived because its measurement subject changed
**Status:** Accepted (2026-09-08, via /hm:plan interview round 2)
**Context:** AC-013 requires the per-command ratchet's render to carry `second_opinion`.
`test_command_size_budget._render()` builds a models-off config, and `_ATOMIC_RATCHET["review"]
= 70153` has `int(70153 × 1.02) − 70153 = 1,403` chars of slack while the addition is ~10.6 kB
— about 7.5× over. `plan` has 1,106 chars of slack and gains the same shared partial. Yet the
Contract Boundary forbids raising a ceiling to pass a phase.
**Decision:** Re-derive the `review` and `plan` constants **once**, recorded explicitly as a
**measurement-subject change** rather than as growth, with the derivation written into the
phase and a named carve-off in the Contract Boundary. The prohibition otherwise stands.
**Consequences:**
- ✅ Review's ~10.6 kB of second-opinion surface becomes attributable to a command. The aggregate arm can see total growth but cannot say *which* command grew, which is the entire purpose of a per-command ceiling.
- ⚠️ This is a deliberate, single instance of `[fail:design] ratchet-rebaselined-by-its-own-subject` (count:2). It is bounded by being written down: the new constants and their derivation are in the phase, so a later reader can tell this re-baseline from an undocumented one.
- ⚠️ Between the re-derivation and the wiring the gate is red; the two must land in one commit.

**The derivation, as landed (2026-09-08, Phase 6).** ADR-011's carve-out is conditioned on this
being written down, so it lives here and not only in a code comment:

| Command | Was | Now | Δ | Basis |
|---|---|---|---|---|
| `plan` | 55,322 | 62,703 | **+7,381** | models-on minus models-off, same answers |
| `review` | 70,153 | 80,586 | **+10,433** | same |

Measured through `test_command_size_budget._render`, which applies `pin_install_ref` — that matters:
an unpinned ad-hoc render gave +7,454 / +11,607, because the `uv run --with <path>` strings differ in
length per command, and those wrong figures reached a code comment before A.5 round 1 caught the two
records disagreeing. The other **five** atomic commands are byte-identical across the two
configurations, which is what makes "only `review` and `plan`" a measurement rather than an
assumption, and `test_ac_013_the_models_delta_is_produced_by_configuration` asserts it so the claim
fails rather than rots when the partial reaches a third stage. `_RATCHET_MODELS = ["codex"]` is one
model, so the `≥2 models` concurrency block and the antigravity transport remain outside every
per-command band — a recorded scope limit, not a claim of coverage.

**Rejected alternatives:**
- Drop AC-013's second half — rejected because the aggregate arm cannot attribute growth to a command, so review's ~10.6 kB would be permanently invisible to any per-command ceiling; RESEARCH A-11 identified that as the defect.
- A separate models-on ceiling table — rejected because two tables measuring the same artifact is `[wiki:architecture] one-rule-one-normative-site-others-defer` by construction, and the next reader would not know which to move.
**Source:** Interview #5

### ADR-012: The "gate measures the shipped file" claim is retracted, not implemented
**Status:** Accepted (2026-09-08, forced by plan validation)
**Context:** AC-013 originally also required the gate's baseline to equal the on-disk shipped
surface, citing a measured 435,437-vs-442,446 gap. `.gitignore:26` excludes `.claude/*`, so
there is no shipped render in a fresh worktree and only a stale one in base;
`_surface_baseline.py:5-9` records measuring it as a **deliberately rejected** design —
"measuring it would have frozen a baseline against whatever happened to be lying around".
**Decision:** Retract the claim. The gate's re-render is correct; the 442,446 figure is
untracked local output of whenever `/harness-maker:make` last ran. Neither the gate nor the
prose moves.
**Consequences:**
- ✅ The gate stays runnable in CI and in every worktree, which binding it to an absent artifact would have prevented.
- ✅ RESEARCH finding A-10 is corrected in place rather than left standing as a defect that is not one — the same discipline this unit applies to everything else.
- ⚠️ There is genuinely no check that the render a user has on disk matches what the gate measures. That is inherent to gitignoring rendered output and is out of scope.
**Rejected alternatives:**
- Make the shipped render CI-checkable (commit it, or generate it in CI) — rejected because committing `.claude/*` reverses a standing design decision, and generating it in CI is what the gate already does; the "gap" dissolves once the artifact is understood.
**Source:** Plan validation, critique 3 (no user round — the alternative dissolves on inspection)

## 🏗️ Technical Design

**Current state.** Five ledger writers exist (`autopilot_ledger`, `stage_agent_ledger`,
`codex_ledger`, `delegation_ledger`, `stage_spans`) and all four JSONL targets are absent on
disk; `stage-spans.jsonl` holds one `start` with no `end`.
`find_unconfirmed_authorization` (`autopilot_ledger.py:235-272`) has exactly one caller and
`elapsed_s` has no consumer. `smoke_check` (`autopilot_ledger.py:319-340`) reads only
`yaml_level` with zero `targets` references. `context_lint.lint()` has no production caller.
`stage_end_summary.md.j2:24` gates on a name with no producer.

**Affected components.**

| Component | Change | ADR |
|---|---|---|
| `src/harness_maker/autopilot_ledger.py` | roll-up aggregate; dangling-authorization report; target-aware smoke | 002, 010 |
| `src/harness_maker/readiness.py` | absence-as-absence for every ledger reader; unreachable-vault standing condition; the two new autopilot signals | 002 |
| `src/harness_maker/context_lint.py` + render path | production caller, warn-only | 004 |
| `templates/agents/_partials/stage_end_summary.md.j2` | level gate; dead name deleted | 006 |
| `templates/agents/_partials/second_opinion_dispatch.md.j2` + the two model partials | `run_in_background`, guarded on `second_opinion_stage == "review"`. **Shared** — included by `review.md.j2:452` and `plan.md.j2:556` | 007 |
| `templates/stages/wrapup.md.j2` | the roll-up's `--optional` entry in `wrapup_land`'s manifest | 002 |
| `CLAUDE.md`, `README.md`, `docs/HOW-IT-WORKS.md`, audit message, `harness.yaml` template, `review.md.j2:139` | claim/reality reconciliation | 003, 005 |
| `tests/structural/test_command_size_budget.py` | the ratchet render carries `second_opinion`; the `review`/`plan` constants are re-derived. **Not** a shipped-file binding — retracted | 011, 012 |

**Data flow (evidence half).** Ledger writers append JSONL under
`.claude/observability/` (unchanged, still gitignored) → the roll-up reader aggregates
per-model / per-stage / per-arm, applying `.ledger-exclusions.json` and excluding
`stage: "health"` rows → one overwritten snapshot under `work_docs.dir` → wrapup's existing
deliverable commit carries it → readable in a fresh clone.

**Aggregation contract (load-bearing).** Per-model, `(skipped + failed) / total`, over
**invocation rows only**. Three rules, each closing a recorded mis-measurement:

1. **`finding_ref` is the discriminator.** `second-opinion.jsonl` holds two row kinds —
   `finding_ref == "n/a"` is one row per *invocation*, `finding_ref != "n/a"` is one row per
   *finding disposition* — and **both carry `status: "invoked"`**, so `finding_ref` is the only
   thing separating them. Aggregating without it counts one invocation per finding and silently
   inflates the denominator. `codex_ledger.disposition_rows` / `disposition_counts` exist
   precisely to split them.
2. **`failed` is not dropped.** A `failed` row means the CLI ran but produced a payload the
   consumer cannot use, so that model's voice is as absent as a skip. An earlier
   `skipped/total` reported 10.3% where the truth was 20.7%, with one model's entire loss
   sitting in `failed` rows.
3. **Models are not merged**, because a healthy model dilutes a broken one — the same
   measurement showed 20.7% aggregate against 2.4% / 37.8% per model.

Plus `stage: "health"` rows excluded (the smoke runs in base with a trivial prompt and is
structurally `invoked`-biased) and `.ledger-exclusions.json` applied — omitting the exclusions
file is what produced 61.3% against the shipped reader's 2.15%, a 30× error, three times.

**API changes.** New `autopilot_ledger` subcommands (roll-up generation; dangling-authorization
report). `smoke_check` gains a `targets` input. No existing signature is removed.

**Design decisions.** Sequencing per ADR-001. Durability per ADR-002/010. The two
mismatch directions per ADR-003/004. Property scope per ADR-005. Render gating per ADR-006.
Backgrounding per ADR-007/009.

## 📝 Implementation Plan

### Phase 1 — Roll-up producer and dangling-authorization reader
- **depends_on:** `[]`
- **parallel_group:** `serial-evidence-core`
- **merge_hazards:** `src/harness_maker/autopilot_ledger.py` — both ACs edit it; `tests/unit/test_ledger_exclusions_call_sites.py`, whose named-entry-point list gains the roll-up in this phase's commit; `templates/stages/wrapup.md.j2`, whose `wrapup_land` manifest gains the `--optional` entry; **`tests/structural/instruction_baseline.json` + `test_instruction_preservation.py` + `_ALLOWED_REMOVALS`** — the manifest edit rewrites a frozen executable line, so the old spelling reads as a removal for **both** `wrapup@spec-driven` and `wrapup@task-driven` (the `_PHASE_2_SESSIONID` precedent needed fourteen entries for this same "nothing is cut, one flag longer" shape; the Contract Boundaries advisory's "Phase 3 adds no entry" is **not** a statement about this phase); **`tests/structural/surface_baseline.json`** — `test_aggregate_shipped_surface_does_not_grow` is **zero-tolerance**, not a 2% band.
- **Scope in:** `src/harness_maker/autopilot_ledger.py` (roll-up composing `verifier_discrimination` / `ledger_exclusions`, not re-deriving — ADR-010); the dangling-authorization report; `work-docs/BASELINE-ledger-rollup.md`; the `--optional` manifest entry in `wrapup.md.j2`; the call-sites test extension; the `_ALLOWED_REMOVALS` entries for both `wrapup@` arms; **the surface allowance, created in this order** — (1) write `work-docs/BASELINE-DELTA-token-efficiency-autopilot-ux-speed.md`, (2) *then* add the `surface_allowance:` frontmatter block to this PLAN pointing at it. **The order is mandatory:** `surface_allowance._parse` raises `AllowanceError` when the `delta_doc` does not already exist, so adding the block first makes the gate red by itself. Re-freezing `surface_baseline.json` instead is the destructive act the allowance exists to remove; new unit tests.
- **Scope out:** `readiness.py`, every other template, `.gitignore`, `DELIVERABLE_PREFIXES` (the `BASELINE-` prefix is already in the set — ADR-002).
- **Exit criterion:** three clauses, all mechanical.
  1. `uv run pytest -q` green on the new roll-up and dangling tests, with the AC-001 fixture containing all four discriminating row kinds (two models, a `failed` row, a **disposition row**, an excluded row).
  2. After this phase's commit: `git ls-tree -r HEAD --name-only` contains `work-docs/BASELINE-ledger-rollup.md`, **and** `git check-ignore -v --no-index work-docs/BASELINE-ledger-rollup.md` prints nothing. *A fresh clone cannot substitute for this* — `git clone` transfers commits and never index state, the task branch is never pushed, and wrapup's land runs after Phase 6, so at Phase 1 exit there is no clone that could contain the file. `--no-index` is required because `check-ignore` answers "not ignored" for an already-tracked path.
  3. The path appears in `wrapup_land`'s manifest in `wrapup.md.j2`.
- **Risk:** medium
- **Rollback point:** base of `hm/token-efficiency-autopilot-ux-speed`.
- Delivers AC-001, AC-002.
- **Status: DONE (Phase D green, verified over the complete change set)** — A.5 exited on a **named-form application, not a third round**.

##### Step 4 — stage exit record (Phase 1 only; phases 2–6 not started)

**Boundary comparison performed — no crossing.** 17 changed paths; none equals or sits under a
`Do not change` entry (`conditional_router.py`, `_partials/step_manifest.md.j2`,
`second_opinion_invoke.py`, `.gitignore` are all untouched). `git log -1` is still the base commit
`5d211f61` — **no commit was made from this stage**, as the stage requires.

**Two edits outside Phase 1's declared scope, flagged rather than hidden:**

| Path(s) | Why it was needed |
|---|---|
| `src/harness_maker/command_registry.py` | `MODULES["autopilot_ledger"]` declares the allowed subparsers and **refuses an undeclared one**, so the `rollup` subcommand — itself required, because a writer is what makes AC-001's committed-path conjunct reachable — cannot exist without moving this file too. Bound by `test_the_rollup_subcommand_is_registered`. |
| `tests/snapshot/*.expected.yaml` (8 files) | Mechanically forced by the in-scope `wrapup.md.j2` edit. Two `body_sha256` values per file (`commands/hm/wrapup.md`, `stages/wrapup.md`); no `file_count` and no other entry moved. |

**Verification, stated by scope rather than as one claim:** Phase 1's two test files 26/26;
`ruff check` + `ruff format` + `mypy --strict` clean on all four changed sources;
`tests/structural` + `tests/snapshot` + `tests/render` green after the snapshot regeneration;
the whole suite (minus the auth-gated live e2e) green immediately before the call-sites seam was
added, and the `tests/unit` chunk — which contains every file the remaining delta could reach —
green after it; `hm spec_machine check --all` green with **rule 3 actually active**. The first
attempt at a single post-everything full run was **killed for low memory**, not failed, which is
why the record is a set of scopes instead of one number.

**Not done, and not claimed:** phases 2–6. `_ALLOWED_REMOVALS` entries were in Phase 1's scope and
turned out **unnecessary** — `test_instruction_preservation` does not read a lengthened line as a
removal, so the prediction that made them scope did not hold. The 2-round budget stands; the user picked Path C from the `stuck` escalation, so the two surviving blocking issues were closed with the forms below and no A.5 re-dispatch was made. The blocker note is kept verbatim underneath, because a resolved blocker whose record is deleted is indistinguishable from one that never happened.

#### How the two surviving A.5 issues were closed (Path C)

| Issue | Form applied |
|---|---|
| `"6" in body` binds nothing | **Per-axis differential**, not the reviewer's line-scoped token match. `test_ac_001_the_document_is_a_function_of_every_aggregate_axis` renders the fixture result and two perturbed results — one moving only the per-model counts, one moving only the per-stage split, **both holding the total at 6** — and requires the document's numeric-token multiset to move under each. A render printing only the total passes neither; a render omitting an axis fails that axis's arm. Nothing about layout is pinned. Deviation from the reviewer's named form is recorded in SPEC AC-001 with its reason (that form pins a layout on a function that did not exist yet). |
| `count(--optional …) == 2` | **The reviewer's form verbatim**: collect the lines containing `hm wrapup_land --worktree`, assert the collection is non-empty, assert **every** member carries the needle. Verified sound against the file first — exactly two such lines (`:598` codex, `:602` non-codex) and no prose line. |
| *(third instance, surfaced by `stuck`, not by A.5)* | `"absence of evidence" in body` was a wording pin — red for a non-defect if an implementer wrote "no evidence recorded". Replaced by `render_rollup(empty) != render_rollup(populated)`, which is the property AC-004 actually names and constrains no wording. |

**Settled by execution, not argument** (the `stuck` note's own next-action): the manifest test was
run alone before Phase C and was **RED on the needle itself** — not on an import error — then GREEN
once both branches carried the entry. One correction to that note: it called the test "runnable
today", but it dereferences `ROLLUP_RELPATH`, so the constant had to land first for the RED to be
about the manifest rather than an `AttributeError`.

#### Two defects this phase found in its own work

1. **The fixture's exclusions file was inert.** `_EXCLUSIONS` was written as a `dict`, which
   `ledger_exclusions.load` reads as the LEGACY map — matching nothing. That is verbatim the failure
   its own docstring names: *"a file that looks configured and is inert"*. Caught by the count arm
   (`calls == 5` read 6), not by inspection.
2. **`rollup()`'s default `observability_dir` ignored `project_root`** — a bare relative
   `Path(".claude/observability")`, so any caller not standing in the root read the wrong directory.
   **Every one of the 11 tests passed**, lint and `mypy --strict` were clean, and it was found by
   running the CLI once for real. This is the absent-case class CLAUDE.md records at **count:8**;
   Phase D.5's window and its covering test are below.

#### Phase D.5 — newly-reachable window

1. **Window:** `rollup(project_root)` with `observability_dir` **absent**, from any CWD. Before the
   fix that path read the CWD; every caller trusting the default — including the new CLI — was
   outside the reachable set.
2. **Test entering it, same change:** `tests/unit/test_autopilot_ledger_rollup.py::test_the_default_observability_dir_resolves_against_project_root`.
   It passes `tmp_path` only, with the fixture under `tmp_path/.claude/observability`; pytest's CWD
   is the repo root, so before the fix it read the repo's own ledger and reported different numbers.
3. **Absent-case:** the repair activates *on* the absent optional argument, and that is exactly what
   the test exercises.

#### Also delivered, beyond the AC text — and why it is not scope creep

`write_rollup()` plus a `rollup` subcommand on `autopilot_ledger`, registered in
`command_registry.MODULES` (the registry refuses an undeclared subparser, so both sites had to move
together). Without a writer, `rollup` + `render_rollup` would be **a correct helper wired to
nothing** — the defect AC-014 exists to name — and AC-001's committed-path conjunct could never
become true. Bound by `test_the_writer_puts_the_rendered_body_at_the_named_path` and
`test_the_rollup_subcommand_is_registered`.

`Rollup` carries **no timestamp**, deliberately. A `BASELINE-` deliverable invites one, and `stuck`
predicted precisely that ("any 2026 timestamp contains `6`"); with a timestamp, two renders taken
microseconds apart differ for a reason unrelated to the aggregate and the differential passes
vacuously. git already records when the file changed, which is the provenance ADR-002 relies on.

#### Gates, and what the carried criticals actually did

- `ruff check` + `ruff format` + `mypy --strict`: clean on all three changed sources.
- **Aggregate surface gate fired exactly as pass-2 validation predicted** — zero-tolerance, not a 2% band: `claude: shipped surface grew 47 chars (435437 → 435484)`. Closed by declaring `surface_allowance` in this PLAN's frontmatter, in the mandatory order: `BASELINE-DELTA-token-efficiency-autopilot-ux-speed.md` **first**, then the block pointing at it (`surface_allowance._parse` raises on a missing `delta_doc`). `surface_baseline.json` was **not** re-frozen — that is the destructive act the allowance exists to remove.
- **`instruction_baseline` did NOT fire.** Pass-2 validation predicted the manifest edit would read as a removal on both `wrapup@` arms and require `_ALLOWED_REMOVALS` entries. Empirically it did not — the edit lengthens a line rather than removing one. One of the three carried criticals did not materialise, and saying so is the point of recording predictions.
- **The targeted selection missed a red test.** `hm test_dep_map` selected `tests/snapshot` but not `tests/unit/test_synthesize_snapshot.py`, so the targeted run was green while the full suite was red on 8 combos. That is `[fail:test] enumeration-tests-not-updated-with-new-rendered-artifact` and "scoped verification hides regressions" — the reason the full suite runs once at phase exit.
- Snapshots regenerated per the recorded convention (`[wiki:gotcha] snapshot-regen-must-render-each-fixture-in-process-isolation`): **not** via `regenerate.py`, which renders all combos in one process and produces unstable hashes, but by converging each combo in its **own** pytest process. Two sha changes per snapshot (`commands/hm/wrapup.md`, `stages/wrapup.md`), grouping by preset+mode — `wrapup.md` does not vary by fixture, which is the internal consistency check that the new hashes are right.
- **`tests/e2e/test_plugin_live.py` fails on `403 Authorization header is missing`** — it shells out to the real `claude` CLI, which this environment cannot authenticate. Per the targeted-test-selection skill's three-way rule this is "production cannot reach the pinned state", the caller-side fact being the missing auth; the test was **not** edited.

> **🚧 BLOCKED at Phase A.5 — retry budget exhausted (2026-09-08).**
> Phase C was never entered; A.5 gates the implementation. `tests/unit/test_autopilot_ledger_rollup.py`
> exists and is RED for the right reason (7 failed / 0 passed, every failure an `AttributeError`
> on a symbol Phase C would write). **Nothing was implemented and nothing was committed.**
>
> **Round 1** — FAIL, 3 blocking issues: the counting test pinned 1 of the 3 aggregate axes AC-001
> named; the render test asserted labels under a comment claiming numbers; the AC-002 pair was
> logically one observable, and because its fixture put the only unconfirmed authorization LAST,
> a reader that never reads `advance_entered` passed both.
>
> **Round 2** — FAIL, but with real progress: S9 → PASS, the counting arm cleared, and three
> round-1 items explicitly cleared (the exact-dict `by_stage` assertion is the wanted
> discrimination over a closed `stage` domain; the misaggregation test is not a duplicate; the
> per-arm deferral is stated soundly). Two blocking issues survive, **both introduced by the
> round-1 repairs**: `"6" in body` is a one-character substring that any 2026 date in the
> document satisfies, and `count("--optional …") == 2` is satisfied by any distribution summing
> to two — including one codex-branch hit plus one prose mention, leaving the non-codex branch
> (the one this repo actually renders) unstaged. The reviewer named a concrete accepted form for
> each.
>
> **The class, stated plainly:** both surviving defects are *an assertion weaker than the comment
> above it claims*, and both are mine. Round 1 flagged that class in two tests; the repairs
> reproduced it in the repaired test and in a newly authored one. What is exhausted is the
> **budget**, not the diagnosis.
>
> **`[boundaries] comparison performed on the blocked exit — no crossing.`** The stage's blocked
> path says to record `comparison not performed`, on the reasoning that edits exist on disk so
> silence would read as clean. The comparison *was* performed, so recording it as not-performed
> would be a false statement of exactly the class this unit exists to remove. Changed-path set,
> 5 entries, all untracked: `specs/SPEC-…{md,machine.yaml}`, `work-docs/{PLAN,RESEARCH}-…md`,
> `tests/unit/test_autopilot_ledger_rollup.py`. **Zero source files touched.** None equals or
> sits under a `Do not change` entry (`conditional_router.py`, `_partials/step_manifest.md.j2`,
> `second_opinion_invoke.py`, `.gitignore` are all untouched). `git log -1` is still the base
> commit `5d211f61` — no commit was made from this stage.

**Also recorded during this attempt** (not blockers):
- The `spec-gate` PreToolUse hook refused the test file twice until a `specs/SPEC-*.md` **markdown** body referenced its node ids — `test_ids` in `.machine.yaml` alone does not satisfy it. Working as designed; noted because it is natural to try the yaml first.
- **`verifier_discrimination.to_payload` already publishes `exclusions.applied` (key/value/reason) and `rows_dropped`.** That dissolves the carried risk `rollup-durability-omits-the-exclusions-list-it-depends-on` **by composition alone** — ADR-010's "compose the shipped reader, do not re-derive" closes a provenance hole nobody chose it for. No scope was added.
- AC-001's third conjunct having no pytest node is confirmed a **legitimate** split, not a coverage hole: a node asserting HEAD containment would be red for a reason no Phase C code can fix, because the commit happens at wrapup.
- SPEC AC-001 and scenario S8 were corrected during this attempt: the **per-arm axis is now an explicit deferral**, because no ledger carries an `arm` field and recording one needs the `EXPERIMENT-session-length-ab` unit that interview round 4 separated out. The SPEC had named an axis it could not test.

### Phase 2 — Health surface: target-awareness, absence, unreachable vault
- **depends_on:** `[1]`
- **parallel_group:** `serial-evidence-surface`
- **merge_hazards:** `src/harness_maker/readiness.py` — three signals land in one module; `autopilot_ledger.smoke_check` is edited here after Phase 1 restructured the module.
- **Scope in:** `readiness.py`; `smoke_check`'s `targets` input; parametrized target-set tests; the empty-vs-healthy reader property.
- **Scope out:** templates, documents, the size gate.
- **Exit criterion:** named test nodes only — no clause discharged by reading CLI prose.
  1. `uv run pytest -q tests/unit/test_smoke_target_awareness.py` — the five-row target-set table.
  2. `uv run pytest -q tests/unit/test_health_second_brain_vault.py` — the unreachable-vault condition asserted **by name**, not by "health reports it".
  3. `uv run pytest -q tests/structural/test_ledger_reader_absence_property.py` — the absence property over a reader set **derived from the import graph**, not from a hand list. The set has no membership definition otherwise, so a reader added in Phase 1 (the roll-up itself) would silently fall outside it. This repo already uses that pattern for exactly the "the hand list was wrong three times" problem (`tests/structural/test_autopilot_marker_api_session_key.py`).
- **Risk:** medium — a wrong `targets` read would mask a genuine Claude-Code degradation (risk R4).
- **Rollback point:** Phase 1.
- Delivers AC-003, AC-004, AC-012.
- **Status: DONE (Phase D green).** A.5 ran both rounds, both FAIL, and the phase exited on an application of the reviewer's named forms — the same route Phase 1 took, under the user's standing "do not stop midway" instruction. 17/17 in the phase's own file; `ruff`/`ruff format`/`mypy --strict` clean on all four changed sources; `tests/structural` green; and the 83 test files that reference `readiness` / `autopilot_ledger` / `verifier_discrimination` / `smoke_check` / `second_brain` green (`pytest_exit=0`). The whole `tests/unit` directory was attempted twice and **killed for low memory both times**, which is why the record names a grep-derived set instead of one number.

##### What the gate caught in Phase 2 — six defects, all mine, three of them in the repairs

| Round | Finding |
|---|---|
| 1 | The AC-003 verdict collapse short-circuits on `degraded`, so `applicable` was never read on the two degraded rows — `applicable = (entry_count > 0)` passed the entire golden table. |
| 1 | The enumeration control keyed on the parameter name `observability_dir`, so it was structurally blind to the family's reference reader: the `report` verb inside `main(argv)`, keyed on `--ledger`. That verb emits the exact sentence AC-004's own `oracle_evidence` quotes. |
| 1 | The property ranged over 2 of ≥3 readers, omitting the one the SPEC holds up as the reference. |
| 2 | The `report` arm added to fix that read `.err` for empty and `.out` for healthy — an inequality no implementation can fail, **and** it discarded exactly the two streams where AC-004's failures appear (a zeros payload on the empty run's stdout; an absence notice on the healthy run's stderr). |
| 2 | `_CLI_VERBS` reconciled prose in the promoting direction only. A verdict verb mislabelled `passthrough` satisfied the key check and was never examined — the demoting direction is the one that silently shrinks the property, and it is where the cheapest-green incentive points. |
| 2 | `targets` **omitted** — the production call path — was unpinned. An implementation returning `applicable=False` there satisfied all seven AC-003 tests, the golden table, and every pre-existing `smoke_check` test, while dropping the one real degradation signal for any harness whose yaml has no `targets` key. |

**A SPEC defect the review exposed, and the reviewer then adjudicated.** AC-004's `preconditions`
said *"the reader exits 0 in both cases (absence is not an error)"* — which put the family's
reference reader outside its own property's domain, because `report` writes the absence sentence to
stderr and returns 1. I judged the precondition wrong rather than the reader and corrected it in
place. Round 2 confirmed that call and strengthened the reasoning: exit-1-on-empty is this module's
own established vocabulary (`return 0 if payload["agents"] else 1`), and reverting "would have
laundered round 1's two-reader domain into the SPEC as a justified exclusion".

**A coincidence that was standing in for a classification.** `rollup` the CLI verb and `rollup` the
function share a name, so a flat lookup had been classifying the verb by accident — and a rename of
either would have silently un-classified the other. CLI verbs now carry a typed `(kind, target)`
classification reconciled against `_VERDICT_READERS` in both directions.

**One pre-existing surface lock widened, deliberately.**
`test_autopilot_ledger_health.py::test_smoke_cli_emits_json` asserts
`set(out) == {...}  # full surface locked`. AC-003 adds `applicable`, so the lock grew by one key —
claimed in the SPEC rather than quietly edited, because the lock's whole purpose is to make adding a
field a conscious act.

**Phase D.5.** Phase 2 is new-feature work, so the trigger does not fire; run anyway, one window
was found. `Path("")` is `.`, a directory that always exists, so an *empty* `vault_path` would have
read as reachable and the condition would never fire. The guard is `Path(v).is_dir() if v else
False` — chosen over `bool(v) and …` because that form both narrows for `mypy --strict` and rejects
`""` — and `test_ac_012_an_empty_vault_path_is_unreachable_not_the_cwd` enters that window. Absent
case: `second_brain` absent or `enabled: false` reads as an opt-out (`passed`, `not_applicable`),
never as a failure.

**Two edits outside the declared scope, flagged:** `src/harness_maker/verifier_discrimination.py`
(the `ABSENCE_NOTICE` constant plus its use — required because the round-2 named form binds the
test to a producer constant instead of a re-typed phrase, and the two producers punctuate
differently so the constant must be the shared substring with no trailing punctuation) and
`tests/unit/test_autopilot_ledger_health.py` (the surface lock above).

### Phase 3 — Level-gate the advance block and delete the dead guard
- **depends_on:** `[2]` — **decisional, not technical** (ADR-001). This phase is self-provable from a render diff and could run first; it is sequenced here so its effect is recorded.
- **parallel_group:** `serial-parity-render`
- **merge_hazards:** `templates/agents/_partials/stage_end_summary.md.j2`; **`tests/unit/test_autopilot_template_render.py:98-101`** — `test_codex_exclusion_is_structural` asserts the **exact literal** Jinja condition string, `autopilot_advance_enabled` included, so deleting the name from that condition turns it red. This phase's own "the name emits nothing" grep was over *rendered* output; the surviving reference is a test over the *template*. `_render_partial`'s now-dead `advance_enabled` kwarg needs the same disposition, and `test_autopilot_block_behaviorally_absent_for_codex` survives untouched because `HarnessConfig().autonomy.level` is `"ask"`. Also `tests/structural/_instruction_baseline.py` **`AXES`** and its regenerated snapshot. **`_ATOMIC_RATCHET`: resolved to `none`** — `test_command_size_budget._render` sets no `autonomy`, so it takes `AutonomyConfig.level` = `"ask"` (`models.py:926`), a non-gated arm, and the block still renders. (The in-file comment claiming the class default is `auto_safe` is **stale**.) A hazard left as an unresolved conditional is a deferred decision, and this one is answerable from two lines.
- **Scope in:** `stage_end_summary.md.j2` — an **in-place replacement of the condition on line 24**, no added tag lines and no `{%-`/`-%}` change; deletion of the dead name; **`tests/unit/test_autopilot_template_render.py`'s literal assertion and `_render_partial`'s `advance_enabled` kwarg**, updated in the same commit as the template edit; an `autonomy.level` arm added to `_instruction_baseline.AXES` with the snapshot regenerated (**see the carried risk in `## 🔍 Plan Validation` — this is a second axis and a key-grammar migration, not a list append**).
- **Scope out:** `step_manifest.md.j2` (the picker is untouched — ADR-006), `autopilot_caps.py`, `autopilot.py`, `_ALLOWED_REMOVALS` (see below — there is nothing to list).
- **Exit criterion:**
  1. A `gated` render contains **zero** `autopilot_caps boundary` invocations across all commands.
  2. **SHA-256 byte identity against a pre-change golden for every non-gated arm** — `ask` (the ratchet fixture) and `auto_safe` (both baselines, which render this repo's own `harness.yaml`). This is the mechanism the repo already uses for zero-cost proofs, and it is the only clause that also discharges the picker's 18,067 chars staying untouched.
  3. `_instruction_baseline`'s new `autonomy.level` arm is green, and `test_instruction_preservation.py` passes **with no `_ALLOWED_REMOVALS` entry added**.
- **Why no `_ALLOWED_REMOVALS` entry, and why `AXES` must grow:** every committed guard renders a non-gated arm (`_instruction_baseline._render_atomic` and `_surface_baseline.render_surface` both render this repo's `auto_safe` `harness.yaml`; the ratchet fixture is `ask`). So the advance block's headings and both `!` lines **survive in every baseline**, meaning there is nothing to list — and the allowlist's staleness check ("an entry naming something still present means the allowlist drifted") would **fail** on any entry this phase added. The deeper consequence: **no committed guard renders a `gated` harness at all**, so the new level gate could swallow more than the advance block with every gate green. `_instruction_baseline.py:28-32` states the governing rule — a phase editing a block gated on an uncovered axis must extend `AXES` first — and this is exactly such a phase.
- **Why the old "byte-identical except for the deleted name" wording was void:** `autopilot_advance_enabled` appears only inside the Jinja condition, so it **emits nothing** — grepping it across the rendered commands returns 0 (the 7 hits are `autopilot_caps boundary`). An exception that cannot exist licenses any diff the executor labels as such. And the render env is `trim_blocks=False, lstrip_blocks=False` (`render.py:61-68`), so a restructure into nested `{% if %}` tags adds output newlines that nothing catches: the ratchet's 2% band absorbs a few chars, `instruction_baseline` compares stripped heading and `!`-line **sets**, and the aggregate has headroom. `[wiki:convention] jinja-comment-whitespace-moves-renders` is the recorded hazard.
- **Risk:** medium — the level gate is invisible to every existing guard until `AXES` grows (risk R1, rewritten).
- **Rollback point:** Phase 2.
- Delivers AC-005.
- **Status: DONE (Phase D green).** A.5 **PASSED on round 2** — the first PASS of the unit. `structural` + `snapshot` + `render` + the autopilot template test + the synthesize snapshots all green, `pytest_exit=0`; `mypy --strict` clean.

##### The AXES migration was avoided, as the carried risk allowed

`_instruction_baseline.AXES` is untouched. The gated arm is guarded by
`tests/structural/test_autopilot_gate_render.py`, which the carried risk named as the alternative
("or find a different guard for the gated arm"). `test_dev_mode_axes_is_still_the_only_instruction_baseline_axis`
records *why* this file exists and fails if `AXES` ever stops being a `DevMode` tuple — a comment
would rot; that notices.

##### Snapshots did not move, and that is the design working

The condition was replaced **in place** on one line, so for every non-gated arm both the old and
new conditions are truthy and the condition text itself never emits. Result: byte-identical output
for `auto_safe` and `ask`, so `surface_baseline`, `instruction_baseline` and all eight
`test_synthesize_snapshot` combos stayed green with no regeneration. A nested `{% if %}` restructure
would have added an output newline to the *armed* arm (`keep_trailing_newline=True, trim_blocks=False,
lstrip_blocks=False`), which the byte golden catches and the delta test does not — the two are
complementary by construction, and A.5 verified that arithmetic rather than assuming it.

##### What the gate caught, and one thing my own measurement nearly hid

| Round | Finding |
|---|---|
| 1 | **The delta test would have failed a CORRECT implementation.** `autonomy.level` gates the PICKER too (`step_manifest.md.j2:33`, included into every command), so `gated = armed − advance − picker` while the test expected `armed − advance`. Phase C doing the chartered work stayed red; the only available green was deleting the picker's level gate, which ADR-006 and SPEC Open Question 4 forbid. The sibling picker test in the same file already asserted that asymmetry, so **the file contradicted itself**. |
| 1 | The dead-name scan walked `src/` only, justified as "where a producer would have to live" — refuted by a counterexample already in the repo: `tests/unit/test_autopilot_template_render.py` declared an `advance_enabled` kwarg and wrote `ctx[...]` from it, and **nothing passes that kwarg**, so its survival was silent. |

Three more surfaced during Phase C, each from running something rather than reading it:

- **`__pycache__` echoes.** The widened scan flagged four `.pyc` files — compiled copies of the very sources being scanned, which also linger after the sources are fixed. Skipped, with the reasoning in the code.
- **The comparison was unsatisfiable by construction.** Rendered files carry a `content_hash` computed *from* the body, so it necessarily differs between two arms whose bodies differ. Comparing it added nothing once the bodies were compared. Normalised.
- **`autonomy.level` gates THREE regions, not two.** `health.md` has an unmarked "Autopilot auto-advance smoke check" section gated on the same axis, predating this change. A whole-command comparison charged this phase for correct pre-existing behaviour, so the delta assertion is scoped — **derived, not hand-listed** — to the commands that carry an advance block, since the conjunct asks what the *advance* gate removed. A.5's own analysis had assumed two.

##### Mutation receipts: seven gates, seven demonstrated killers

`tests/structural/test_new_gates_file_a_mutation_receipt.py` refuses a new structural gate with no
receipt naming the line that kills it. Filed for all seven, each established by **actually
performing the mutation** and reading which tests died:

| Mutation | Gates it kills |
|---|---|
| `stage_end_summary.md.j2:24` — level gate neutralised, or the old dead name restored | the boundary-count gate, the delta gate, and (on the name variant) the dead-name scan |
| `stage_end_summary.md.j2:79` — the boundary `!` line deleted | the armed-control gate, the byte golden |
| `step_manifest.md.j2:33` — picker gate neutralised | the picker gate, the delta gate |
| `_instruction_baseline.py:75` — `AXES` members no longer `DevMode` | the AXES-invariant gate, the byte golden |

**My first measurement of this was wrong and would have recorded a false clean bill.** Deleting the
`{% if %}` line unbalances its `{% endif %}`, so pytest reports `ERROR`, and my collector only read
`FAILED` — the run said "deleting the level gate kills nothing". The corrected mutations preserve
Jinja balance (drop the condition, keep the tags), and then the two headline gates die as they
should. All template files were restored byte-for-byte and re-verified green afterwards.

### Phase 4 — Background the cross-model dispatch
- **depends_on:** `[2]` — the live run must be recordable.
- **parallel_group:** `serial-parity-concurrency`
- **merge_hazards:** **not `none`.** The dispatch lives in the **shared** partial `templates/agents/_partials/second_opinion_dispatch.md.j2`, which `review.md.j2:452` **and** `plan.md.j2:556` both include; the model-invoked recipes are in `second_opinion_codex.md.j2` and `second_opinion_antigravity.md.j2`. So this phase moves **`plan.md` as well as `review.md`** in `instruction_baseline.json` and `surface_baseline.json` — both are hazards, because this repo's `harness.yaml` is models-on (`second_opinion.models: ["codex"]`) and those two baselines render it. **`_ATOMIC_RATCHET` is NOT a hazard of this phase**: the shared partial renders byte-zero while `models` is empty, and the ratchet fixture stays models-off until Phase 6 sets it — so this phase moves those constants by zero. Ownership of `_ATOMIC_RATCHET["review"]`/`["plan"]` is Phase 6's, exactly once, per ADR-011; `depends_on: [4, 5]` on Phase 6 is what makes that single derivation land against the final render.
- **Scope in:** `agents/_partials/second_opinion_dispatch.md.j2` and the two model partials; a **`second_opinion_stage == "review"` guard** on the backgrounding; the `INTEGRATION=1` live fixture; **this phase's rows in the surface allowance Phase 1 created** — the added prose moves `surface_baseline.json` (zero-tolerance) and `instruction_baseline.json` for **both** `review` and `plan`, and if it spells a literal `Bash(` it also moves the codex `round_trips`, which `test_round_trip_counts_match_the_live_render` compares exactly.
- **Scope out:** `second_opinion_invoke.py` (the invoker keeps sole ownership of CLI construction — ADR-007), `CODEX_TIMEOUT_S`, the agy timeout stack, `review.md.j2` and `plan.md.j2` themselves (the edit belongs in the shared partial — duplicating it into review only would violate `one-rule-one-normative-site-others-defer`, which this PLAN's Prior Work cites).
- **The plan-stage join is why the guard is not optional.** CLAUDE.md's contract for `/hm:plan` requires the main loop to run each model and **inject** the adapted findings into `plan-validator`'s prompt *before* dispatch. A backgrounded call there has nothing to inject unless the template adds an explicit wait — and Phase 4's exit criterion is a *review* run, which cannot observe the plan stage at all. Gating on the stage is the smaller change; adding a plan-stage join would need its own AC.
- **Exit criterion:** `INTEGRATION=1 uv run pytest` on the live fixture shows the second-opinion span starting before the Pass 1 fan-out completes; the render-grep precondition passes; and a render of `plan.md` shows the dispatch **not** backgrounded. A green grep with a red dispatch is the expected failure mode and does not satisfy this phase.
- **Risk:** high — non-deterministic, real cross-model call (risk R2).
- **Rollback point:** Phase 3.
- Delivers AC-006.
- **Status: MECHANISM LANDED, ORACLE UNVERIFIED — by explicit user decision.** Wiring green (`structural` + `snapshot` + `render` + the phase's own tests, `pytest_exit=0`); AC-006 is **not** called green.

##### The oracle cannot be produced here, and that is recorded rather than worked around

`command -v codex` and `command -v agy` both return nothing, and Phase 1's live invoker call returned
`status: "skipped", reason: "CLI not installed: codex"`. AC-006's oracle is one real cross-model
dispatch and its own text disqualifies a render-grep as proof. The user was offered wire-and-record /
defer Phases 4+6 / install a CLI first, and chose **wire-and-record**: leaving the concurrency claim
unwired keeps a *false* claim in the harness (ADR-007 rejected downgrading it to ordering-only),
while calling a render-grep proof would commit the defect this unit removes.
`test_ac_006_a_live_review_overlaps_the_fan_out` is `skipif`'d on CLI absence and **fails loudly if a
CLI is present**, so the gap closes automatically in an environment that has one. Honest summary:
**the 300 s is off the critical path in the render, and nobody has watched it happen.**

##### Phase C before Phase A — my process error, and how it was repaired

I edited the template before writing the tests, so all three preconditions passed on first run.
"Passes because I implemented first" proves nothing, so each was put through a real mutation: removing
the review block kills the review test; removing the plan refusal kills the plan test; **dropping the
stage guards kills both** — which is the shared-partial hazard demonstrated rather than asserted.

A fourth test had **no constructible killer**. `test_ac_006_no_model_enabled_renders_neither_instruction`
asserted the instruction does not leak with `models: []`, and byte-zero turned out to be enforced
twice — `review.md.j2` wraps the include in `{%- if config.second_opinion and config.second_opinion.models %}`
*and* the partial re-checks `{%- if _models %}` — so hoisting the block above the inner gate, and then
removing both layers, still produced no leak. Rather than ship an assertion I had proven nothing
about, it was rewritten as a **structural** claim (the blocks must sit after the partial's models
gate), which hoisting does kill.

##### Three guards caught things I would not have

- **`test_render_review_read_budget`'s `_VALIDATOR_DISPATCH` counts a backticked `` `plan-validator` `` as a dispatch witness.** My prose said "into `plan-validator`'s prompt" and added a phantom witness — my paragraph was **impersonating a dispatch site**. Fixed by unbackticking, not by widening the golden.
- **The aggregate surface gate** fired at +1,684. 182 of those chars were a note about a *test convention* — information for template authors that the model reading the command cannot act on. It moved into a Jinja comment (renders to nothing) and the figure returned to **+1,503**. "Explain it in the prose" is the default instinct and it is billed per harness, per invocation.
- **Phase 3's byte golden** went red, correctly: Phase 4 legitimately moves the non-gated arms. Re-based **with a `rebases` row** naming the phase, the reason and the delta doc — and the note now says a re-base with no such row is the failure the file exists to catch. Phase 3's neutrality was verified against the pre-Phase-3 capture first, so that fact is not lost by the re-base.

`surface_allowance.chars` is now **1503** — the *total* against the frozen baseline (47 from Phase 1 +
1,456 from Phase 4), not the latest increment, because the gate compares the live figure against
baseline + allowance and a per-phase number would fail on the earlier growth.

### Phase 5 — Doc-truth property and the four concrete false claims
- **depends_on:** `[2]`
- **parallel_group:** `serial-parity-docs`
- **merge_hazards:** `CLAUDE.md` — shared with Phase 6, which edits its Context Lint section while this phase edits the reviewer-fan-out section. The two phases must stay serial.
- **Scope in:** the inversion property over the rendered `make.md` disclosure table plus its extension list; `README.md`'s worktree sentence; the personalization-audit message; `docs/HOW-IT-WORKS.md`'s fusion section and its TOC entry; CLAUDE.md's reviewer-fan-out retraction, worded to the shipped semantics per ADR-003; **and the fifteenth gap — the rendered `review.md`'s "Start from `harness.yaml.reviewers.enabled`" instruction (`review.md.j2:139`), reconciled against the dispatch table the same file generates without it.**
- **Scope out:** `conditional_router.py` (ADR-003 keeps the code as-is), CLAUDE.md's Context Lint section (Phase 6), `review.md.j2:279`'s length branch (that one genuinely reads `enabled` and is not part of the contradiction).
- **Exit criterion:**
  1. Inverting the disclosed default in `AutonomyConfig()` makes the table's assertion fail, **verified by actually performing the revert** — a presence-asserting grep passes on inverted content, which is how this table graded D once already.
  2. The worktree claim holds on both `worktree.enabled` arms, evaluated against `worktree_enabled(base)`.
  3. The advisory cites the threshold whose branch fired, across all three states (count-over, days-over, both).
  4. `grep "Fusion Commands" docs/HOW-IT-WORKS.md` is empty — **both** the TOC entry at `:22` and the section at `:938`, since deleting only the body leaves a link to nothing.
  5. AC-015: the rendered `review.md` no longer instructs from `reviewers.enabled` while its generated dispatch table composes without it.
- **Risk:** medium — an over-broad property fails on prose that merely names a config (risk R5).
- **Rollback point:** Phase 4.
- Delivers AC-007, AC-008, AC-009, AC-011, AC-015.
- **Status: DONE** (2026-09-08). Phase D green: 63 tests across the three touched test files,
  `tests/structural` + `tests/snapshot` clean, 0 failures across every unit/integration test that
  references a changed file, repo-wide `ruff check` + `ruff format --check` + `mypy --strict` clean,
  and all three spec gates (`validate` / `cross-validate` / `find-unbound`) OK. **The rendered
  surface SHRANK 54 chars** (436,940 → 436,886); the allowance is tightened from 1,503 to the
  measured 1,449 and the golden carries a `rebases` row for it.

**A.5 round 1 returned FAIL with three blocking findings, and one of them refuted a premise this
unit was built on.** All three were independently verified before folding:

1. **The AC-015 premise was false.** RESEARCH and this PLAN's ADR-003 said "the rendered review
   dispatches `test-reviewer` and `concurrency-reviewer` although neither is in `enabled`".
   `interview.py:127-137`'s `_PROD_ENABLED_REVIEWERS` contains **both**, and `interview.py:978`
   preserves a non-empty user list — so on every harness a producer can emit, the dispatched set is
   a **strict subset** of `enabled`. The `[]` behind the claim came from constructing
   `InterviewAnswers` directly in a measurement script, a value no producer emits, and it
   additionally suppresses `review.md.j2:279`'s `{% if enabled | length > 1 %}` section, which would
   have made the test's verdict independent of the fix. The **decision** survives (the lever is
   still false — `lens_dispatch(preset)` never reads the list), but the test now renders a
   *reachable narrowed* harness (`["code-reviewer", "security-reviewer"]`) and carries a vacuity
   guard that fails loudly if the mechanism ever starts honouring `enabled`.
2. **AC-009's wiring guard was a decoration.** I asserted `"compose_audit_advisory" in
   inspect.getsource(_personalization_hint)` and justified skipping execution by claiming three
   fixtures were unavailable. `tests/unit/test_sessionstart_drift.py` already builds all three. The
   grep is satisfied by a comment, by a dead branch, and by a call whose return value is discarded —
   so the shipped banner could still print `threshold 30` on a days-only trip. Replaced by a
   parametrized arm that drives the real SessionStart hook and reads `additionalContext`.
3. **AC-011 was a second, narrower source of truth.**
   `tests/structural/test_no_fused_workflow_axis.py::test_no_repo_doc_advertises_a_fused_workflow`
   already owns this invariant across `README{,.ko}.md` and all of `docs/`; its `_PROSE_BAN` was
   case-sensitive and singular-only, so `## 4. Fusion Commands`, the anchor `#4-fusion-commands` and
   a `4 fusion` count row all escaped it — the third round of the same recurrence, each round fixing
   the spelling it had just been shown. The ban is now **bare and case-insensitive in both
   languages** plus `workflow_fuse`, and AC-011 **defers** to it.

**Defects found by the widened gate that no AC had named** — the reason B3 was worth taking:

| Where | What |
|---|---|
| `docs/CONTRIBUTING.md:18` | a directory tree still drawing `workflow_fuse.py`, a **deleted module** |
| `docs/ARCHITECTURE.md:179` | a true "it is gone" sentence missing its `@hm:axis-removed` marker |
| `docs/HOW-IT-WORKS.md:69` + `.ko.md:70` | `12` sub-agents — the measured count is **15**, on both presets |
| `docs/HOW-IT-WORKS.ko.md:70` | the same false `14 commands (… 4 fusion …)` row as the English file |
| `commands/make.md:355` + `:563` | offered a level named `full`; the `AutonomyLevel` literal has no such member (`auto_full`) |
| `src/harness_maker/models.py:880` | the class docstring claimed the `level` default is `auto_safe`; the field says `ask`, and has since 2026-08-09 |

**Three of my own mistakes, recorded because each is a class:**

- I put the `@hm:axis-removed` marker on its **own line** above the offending sentence. The gate is
  **per-line**, so it stayed red. Marker conventions are line-scoped unless proven otherwise.
- I read the rendered `harness.yaml` with `yaml.safe_load`, which raises `ComposerError`: it is
  **two** documents (provenance frontmatter + body). The production reader
  `io_utils.load_harness_yaml` exists and is now what the test calls — the singleton rule applies to
  tests too.
- Repo-wide `ruff format --check` surfaced an unformatted line in **Phase 2's** test file. Phase 2's
  Phase D had only checked the files it edited. Phase D now runs the repo-wide gates.

**§4 was given a real subject rather than deleted.** `docs/HOW-IT-WORKS.md` has 48 internal anchor
links and a `## 7a.` heading, so renumbering was rejected as breakage risk and a numbering gap was
rejected as reading like an error. `## 4. Fusion Commands` — whose body said no fusion command
exists — became `## 4. Chaining the Stages`, which is what the section was pretending to be about:
a two-row table contrasting autopilot with `/hm:loop`, and the fact that a fresh harness renders
`autonomy.level: ask` so neither runs until the user picks. The Korean file got the same section, so
the two languages stay structurally identical (the A.5 reviewer flagged deleting one while
marker-exempting the other). That serves the user's third axis directly — the removed surface was
dead, the added surface answers "how do these seven commands connect", which nothing documented.

### Phase 6 — Config and gate hygiene
- **depends_on:** `[4, 5]` — **`4` is load-bearing, not stylistic.** Phase 4 edits the shared second-opinion partial, which renders byte-zero while `models` is empty and therefore contributes nothing to the ratchet fixture *until this phase sets `second_opinion`*. If Phase 6 ran first it would derive the constants against a render lacking Phase 4's prose, and Phase 4 would then have to fit the fresh 2% band by luck or re-derive a second time — the second re-baseline ADR-011's carve-out forbids. Ordering 6 after 4 makes the single re-derivation land against the final render.
- **parallel_group:** `serial-parity-hygiene`
- **merge_hazards:** `CLAUDE.md` (shared with Phase 5 — serial); `tests/structural/surface_baseline.json` and `test_command_size_budget.py`, which Phase 3 may also have moved.
- **Scope in:** the **resolves-to-a-real-asset** invariant over the rendered `harness.yaml` (deleting the `relevance-filter` and `research-crawler` entries); `_render()` carrying `second_opinion` **together with** the re-derived `_ATOMIC_RATCHET` constants for `review` and `plan` and their written derivation (ADR-011), in one commit; `context_lint`'s production caller on the render path; the wired-or-gated property over the unwired component set; CLAUDE.md's Context Lint section.
- **Scope out:** `context_lint.THRESHOLDS`' unit (stays lines — ADR-004); the shipped-file half of the old AC-013 (**retracted** — ADR-012); every ratchet ceiling other than `review` and `plan`, which the ADR-011 carve-out names.
- **Exit criterion:**
  1. Every name in `skills.enabled` resolves to a `templates/skills/<name>/` directory and every name in `reviewers.enabled` resolves to a rendered `.claude/agents/<name>.md`. **Not** a containment check against `installed`: `synthesize.py:3-5` installs the full inventory unconditionally, so `installed` is descriptive, the reviewer half is already green with zero work, and the invariant would be satisfiable by *adding* a phantom to `installed` — where it still resolves to nothing.
  2. `_render()` carries `second_opinion`, the models-on `review` and `plan` renders sit inside their re-derived ceilings, and the derivation is recorded in this phase's commit message and in ADR-011.
  3. A re-render of this repo emits the linter warning path without failing.
  4. Each of the three unwired components has a production caller or an intent gate.
- **Not in the exit criterion, by ADR-012:** any comparison of the gate's baseline against an on-disk render. `.gitignore:26` excludes `.claude/*`, so that artifact is absent in a fresh worktree and stale in base — the clause would have made the gate red or erroring everywhere it runs.
- **Risk:** medium — wiring the linter can surface a first-time warning on an existing harness (`render-must-not-degrade-live-harness`); warn-not-block is what keeps that from being a break.
- **Rollback point:** Phase 5.
- Delivers AC-010, AC-013, AC-014.
- **Status: DONE** (2026-09-08). Phase D: `tests/unit` 6,347 passed / 4 skipped / 1 xfail with
  **zero** F or E (the summary line was lost to the documented OOM at teardown — the run reached
  100% and an `-x` run would have stopped at the first failure); `tests/structural` +
  `tests/snapshot` + `tests/unit/test_synthesize_snapshot.py` clean; repo-wide `ruff check`,
  `ruff format --check` and `mypy --strict src/` clean; all three spec gates OK, with every AC now
  `pending_test: false` and bound.

**⚠️ A correction to Phases 1, 4 and 5: their "Phase D green" was incomplete.** Phase 6's run
surfaced 8 failures in `tests/unit/test_synthesize_snapshot.py`, and the diff showed
`stages/wrapup.md` among the changed hashes — **Phase 1's** edit. That file has been red since
Phase 1: my per-phase subsets were built with `grep` over changed-file names, `tests/snapshot`
(a different directory) passed, and this file matched none of my patterns. It is the same trap the
task's own notes already recorded once (`hm test_dep_map` misses it too), and I repeated it three
times. Regenerated by running each of the 8 combos **through pytest's own fixtures**, one process
per combo — my first attempt reimplemented the test body in a standalone script and produced a
third set of hashes, because the `tests/unit/conftest.py` autouse fixtures are part of the
measurement. Confined diff: 10 paths per combo (7 atomic commands from `step_manifest.md.j2`,
`stages/review.md`, `stages/wrapup.md`, `harness.yaml`), no `file_count` or `path` movement.

**A.5 round 1 returned FAIL with three blocking findings.** I also ran Phase C **before** dispatching
the gate — my process error, the same one as Phase 4 — so the reviewer adjudicated an implementation
already in the tree, and one of its findings had already been repaired between dispatch and report.

1. **The `context_lint` wiring had no emission test** — the finding that mattered most, and plan
   validation had **pre-named** it. My call-site arm (even after I tightened it to two-hop
   reachability) stays green when the return value is discarded, when `logger.warning` becomes
   `logger.debug`, or when an early `return` guards the helper. I measured all three: each keeps the
   old arm green and each turns the new
   `test_ac_014_the_linter_emits_on_an_over_threshold_asset` red. Phase 6's exit criterion 3 was
   otherwise decided by nothing but a hand observation.
2. **AC-010's reviewer half could go vacuously green.** `.get(...) or []` turns a renamed key or an
   emptied preset list into "nothing unresolved". Fixed by refusing an empty list before the
   subtraction and by adding the reviewer-side phantom the first version lacked — the SPEC says that
   is precisely the half "a containment check would report green with zero work".
3. **The ratchet derivation was recorded three times in three different values**, and the
   attribution doc *denied the change happened*. The `_RATCHET_MODELS` docstring carried
   +11,607/+7,454 (an ad-hoc render that skipped `pin_install_ref`, whose `uv run --with <path>`
   strings differ in length per command); the per-entry comments carried the correct +10,433/+7,381;
   `BASELINE-DELTA` said "`_ATOMIC_RATCHET` is untouched"; and ADR-011 carried no numbers at all
   even though its carve-out is *conditioned* on the derivation being written down. All four sites
   now agree, and ADR-011 holds the table.

**My own gate reproduced the defect it was built to catch.** The first version of
`test_ac_014_context_lint_has_a_production_caller` passed if any AST `Call` was named `lint`. I
mutated the implementation to check it and **it did not go red**: the only such call lives *inside*
`_warn_context_lint`, so deleting the line that invokes that helper left the gate green — a call
inside a function nobody calls, which is verbatim AC-014's subject. Recorded rather than quietly
repaired. The repair is two-hop (callee must be `context_lint.lint`; its enclosing function must
itself be invoked in `src/`), and it is still not full reachability — a chain of three uncalled
helpers would pass — which is why finding 1's emission arm is the load-bearing one.

**And my mutation *measurement* was wrong again, the same way as Phase 3.** Deleting only the
invocation line left `if not dry_run:` with no body → `IndentationError` → pytest reported a
**collection error**, and my collector grepped for `^FAILED|^ERROR` while pytest prints `E   `. The
run said "the mutation kills nothing". Re-measured with balance-preserving deletions and the
**pytest exit code** instead of a grep: all four AC-014 receipts are exit-1 kills, filed via
`hm mutation_receipt record`, and every mutated file was restored byte-for-byte.

**AC-010 was already green, which is the third stale premise from the same RESEARCH pass.** The two
"live phantoms" (`relevance-filter`, `research-crawler`) were removed in 0.22.3 and survive only in
comments; I had read a comment as a config value. The AC is kept as a regression guard with the
killer demonstrated on both halves. What the measurement *did* find is a real defect the SPEC never
named: `test-reviewer` was enabled on Production and absent from `_ALL_REVIEWERS`, so the rendered
`installed` list under-reported what ships — and `security-auditor` is a **fourth** unwired agent,
found by the discovery arm rather than transcribed from the SPEC, which is the whole reason that arm
discovers instead of listing.

Advisories taken: a `["wrapup"]` arm on the delegation gate (a **shipped** cross-stage key-collision
class, per `models.py`'s own record of ADR-011 rejecting `wrapup.delegate`); exact counts instead of
`>= 10`/`>= 5` floors, which passed a 15→10 render regression; the containment check extended to the
rendered artifact and not just the producer constants; the machine SPEC's AC-010 note corrected,
since a machine half contradicting the prose half is exactly this unit's thesis. Dropped: the
`len(reason.split()) >= 20` word-count floor — it decided nothing. Recorded scope limit:
`_RATCHET_MODELS = ["codex"]` is one model, so the `≥2 models` concurrency block and the antigravity
transport are still outside every per-command band.

## 🔎 Review round 1 (2026-09-08)

Full record in `work-docs/REVIEW-token-efficiency-autopilot-ux-speed-round1.md`. Two reviewers over
the Python source, independently: **0 P0, 5 P1, 6 P2 — all fixed.** Consensus of both on one finding
(the `readiness.py` vault resolver); every other finding verified against the code before folding,
and one turned out to have been repaired between dispatch and report, which is recorded as such
rather than claimed as a catch.

**The finding worth carrying forward:** *four of the six new capabilities in this diff did not work
on the production path* — the roll-up writer had no rendered caller, `smoke_check`'s applicability
parameter had no production caller, the context linter dropped the entire Codex half of the render,
and the vault signal used a resolver that disagreed with the code it reports on. Every one is **the
defect class this unit exists to remove**, and three of them are in the phases whose subject is that
class. Writing the mechanism is not the hard part; proving something calls it is.

That is the third time in this unit the same shape appeared in my own work — the A.5 gates caught it
twice in tests (a source-grep wiring guard; a `lint` call inside a function nothing invoked) and the
code review caught it four times in production. The instrument that found it each time was **running
the thing**, not reading it: the roll-up defect surfaced from one CLI invocation, `--targets` from
two, `AGENTS.md` coverage from a threshold-lowered render.

Two findings were left **unfixed on purpose**, both outside this unit's diff and both recorded rather
than absorbed: a pre-existing prompt-injection path where `sessionstart_drift` interpolates
`harness_maker_version` from `harness.yaml` raw into an imperative session-start banner, and a
maintainer's Windows username shipped in a tracked file in a public repo. Neither is widened here.

Cost of the fixes: +416 rendered chars and one round trip per variant, because two P1 fixes could
only be made by ADDING a rendered instruction — the absence *was* the defect. Declared in the
`surface_allowance` above and itemised in the delta doc; `surface_baseline.json` was not re-frozen.
**Four** normative sites had to move together (`_ATOMIC_RATCHET`, `surface_baseline.json`'s
`round_trips`, `test_roundtrip_budget.py`'s table, `test_render_wrapup_delegation.py`'s line-count
pin) — each now says so in place, since rediscovering that list costs a red suite every time.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/conditional_router.py` — ADR-003 resolves the `reviewers.enabled` mismatch on the prose side; the dispatch table and `lens_dispatch`'s signature stay as they are.
- `src/harness_maker/templates/agents/_partials/step_manifest.md.j2` — the picker block is already correctly level-gated; ADR-006 touches only the advance block.
- `src/harness_maker/second_opinion_invoke.py` — the invoker owns CLI construction; ADR-007 wires backgrounding at the dispatch site.
- `.gitignore` — the raw ledgers stay ignored; ADR-002 puts durability in the roll-up.
- Advisory: no ceiling in `_ATOMIC_RATCHET` may be raised to pass a phase — **with exactly one carve-out, ADR-011**: the `review` and `plan` constants are re-derived in Phase 6 because that phase changes what they measure (the render gains `second_opinion`), and the derivation is recorded. No other ceiling moves, and this carve-out does not license a second one.
- Advisory: a removal from a rendered command is listed in `_ALLOWED_REMOVALS` in the commit that removes it — but note Phase 3 removes **nothing from any covered arm** and therefore adds no entry; it extends `_instruction_baseline.AXES` instead.
- Advisory: the seven mandatory review lenses, `reviewers.max_review_rounds`, `reviewers.grade_threshold` and `second_opinion.models` semantics are outside this unit.
- Advisory: `context_lint.THRESHOLDS` stays line-based (ADR-004); the character-unit question is a separate unit.

## 🧪 Testing Strategy

**Unit (`pytest`, mock-first).** Roll-up aggregation against a hand-authored fixture carrying
all four discriminating row kinds (two models, a `failed` row, a **disposition row**, an
excluded row). Dangling-authorization detection against a fixture with one authorized and no
entered row. The five-row target-set table. The empty-vs-healthy reader property.
**Resolution of every `enabled` name against the actual inventory — explicitly NOT an
`enabled ⊆ installed` containment check**, which `synthesize.py:3-5` makes vacuous
(the full inventory is installed unconditionally, so `installed` is descriptive and the check
is satisfiable by adding a phantom to it). Render diffs across the `autonomy.level` arms. The
inversion property, verified by actually reverting the producing object and watching the
assertion fail.

**Integration (`INTEGRATION=1`).** One live `/hm:review` dispatch proving the second-opinion
span starts before the Pass 1 fan-out completes (ADR-009). **No fresh-clone fixture** — the
task branch is never pushed and wrapup's land runs after Phase 6, so a clone that contains the
roll-up cannot exist at Phase 1 exit; the committing proof is `git ls-tree` at HEAD plus
`git check-ignore --no-index`, per Phase 1 clause 2.

**Structural.** The `_ATOMIC_RATCHET` ceilings and floors, with `review` and `plan` re-derived
per ADR-011. `_instruction_baseline`'s arms. **No shipped-file binding** — retracted by
ADR-012, because `.claude/*` is gitignored and the artifact is absent in a fresh worktree.

**Manual.** Re-render this repo's harness and confirm the linter warning path fires without
blocking, and that the `auto_safe` render is otherwise unchanged.

**Mutation.** Tier 2, threshold 70, over `autopilot_ledger.py`, `readiness.py`,
`context_lint.py` — the aggregation arithmetic is where a wrong bucket key survives a
shape-only assertion.

## ⚠️ Risks & Mitigation

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **No committed guard renders a `gated` harness**, so Phase 3's level gate is invisible to every existing check and could swallow more than the advance block with all gates green. The character floor (`measured × 0.80`) is irrelevant here — the block is not removed from any covered arm. | high | Extend `_instruction_baseline.AXES` with an `autonomy.level` arm and regenerate the snapshot **in the same phase**, per `_instruction_baseline.py:28-32`. Prove the non-gated arms by SHA-256 against a pre-change golden. Add **no** `_ALLOWED_REMOVALS` entry — an entry naming something still present fails the allowlist's own staleness check. |
| R10 | Phase 6's ratchet re-derivation is a deliberate instance of `[fail:design] ratchet-rebaselined-by-its-own-subject` (count:2). | medium | Bounded by ADR-011: exactly two constants, one commit, derivation written down, and a named carve-out rather than a silent raise. Between re-derivation and wiring the gate is red, so they must land together. |
| R11 | Phase 4 edits a partial shared by `review` and `plan`, so it can silently background the plan-stage call whose findings must be injected into `plan-validator` before dispatch — and Phase 4's own exit criterion (a review run) cannot see it. | high | Guard the backgrounding on `second_opinion_stage == "review"`, and make "a render of `plan.md` shows the dispatch not backgrounded" an explicit exit clause. |
| R2 | AC-006 needs a live, non-deterministic cross-model call. | high | `INTEGRATION=1` fixture (ADR-009). The render-grep is kept as a cheap precondition and explicitly not as proof — a green grep with a red dispatch is the anticipated failure. |
| R3 | The roll-up is a new committed artifact; if wrapup does not stage it the measurements still vanish. | medium | Phase 1 clause 2: `git ls-tree -r HEAD --name-only` contains it and `git check-ignore -v --no-index` prints nothing. **Not a clone read** — `git clone` transfers commits, never index state, and the task branch is never pushed. Plus clause 3: the path is named in `wrapup_land`'s manifest, which is what makes it land when `worktree.enabled: false` and the `worktree-sweep` records `skipped-not-isolated`. |
| R4 | Target-aware smoke could mask a real Claude-Code degradation. | medium | The not-applicable branch fires only when `claude-code` is absent from `targets`; a harness containing it keeps today's behaviour exactly, asserted by the five-row table. |
| R5 | The inversion property could fail on prose that merely names a config. | medium | Scoped to disclosed defaults — claims of the form "the default is X" — and to one document set on day one (ADR-005). A false positive here is loud, not silent. |
| R6 | Retracting the `reviewers.enabled` recommendation leaves users no fan-out lever. | medium | Accepted and stated inside the retraction, pointing at deferred Approach C (ADR-003, ADR-008). |
| R7 | Wiring the linter surfaces a first-time warning on existing harnesses. | low | Warn, never block (ADR-004). `render-must-not-degrade-live-harness` is satisfied because no render output changes and nothing fails. |
| R8 | Phases 5 and 6 both edit `CLAUDE.md`. | low | Declared as a merge hazard on both; `depends_on: [5]` forces serial. |
| R9 | This unit could be read as promising a token or wall-clock saving. | medium | Success Criteria states no measured saving is claimed; the enabling work and the saving are deliberately separate units. |

## ✅ Success Criteria

Mirrors `SPEC-token-efficiency-autopilot-ux-speed`'s fifteen acceptance criteria.

- [ ] AC-001 — the roll-up carries hand-checkable counts and survives a clone
- [ ] AC-002 — a dangling authorization is reported
- [ ] AC-003 — the smoke check is not-applicable when the runtime cannot advance
- [ ] AC-004 — absence of evidence is never reported as health
- [ ] AC-005 — a gated harness renders no auto-advance surface
- [ ] AC-006 — the cross-model call is in flight before the fan-out completes
- [ ] AC-007 — no disclosed default survives inversion of its producing object
- [ ] AC-008 — README's worktree claim holds on both arms
- [ ] AC-009 — the advisory names the threshold that fired
- [ ] AC-010 — every enabled name resolves to a real asset
- [ ] AC-011 — no shipped section survives whose body refutes its heading
- [ ] AC-012 — an unreachable vault is a standing health condition
- [ ] AC-013 — the per-command ratchet sees second-opinion surface
- [ ] AC-014 — every unwired component is wired or gated as intentional
- [ ] AC-015 — no rendered command instructs from a list its own dispatch ignores

**Not a success criterion, deliberately.** No measured token or wall-clock reduction. This
unit removes dead surface and restores the instrument; a saving claim requires a
pre-change measurement and a per-section classification table (ADR-017's reopening
conditions), and the prior estimate history in this area collapsed from 8.2% to net zero.

## 🔍 Plan Validation

Two passes, the cap. `plan-validator` (opus), cross-model second opinion **skipped**
(`codex`: `CLI not installed`) — both verdicts are Claude-only, and that is valid on its own.

| | Verdict | Findings | Disposition |
|---|---|---|---|
| Pass 1 | `MAJOR_REVISION` | 11 critical · 3 high · 1 medium | **15 resolved, 0 unresolved.** Two needed a user decision (interview rows 5–6); thirteen were factual or mechanism errors with a single sound resolution and were revised directly. |
| Pass 2 (terminal) | `MAJOR_REVISION` | 6 critical · 6 high · 6 medium · 4 low | **9 resolved in revision, 13 carried** (below). |

**Why the loop ended: `progress`, not `no-progress`** (`hm plan_rounds outcome`:
`resolved_n: 15`, `unresolved_n: 0`, `new_n: 22`). The two-pass cap stopped a loop that was
still moving — every pass-1 finding was answered, and pass 2's findings are new rather than
repeats. Reporting "the cap fired" without that distinction would hide which of the two
happened, and they have opposite remedies.

**Four of pass 1's fifteen came back as `new`** — the revision introduced a different defect
in that area (Phase 1's exit criterion, AC-013's retraction, AC-010's referent, and the
phantom symbol each left a stale assertion somewhere else). That is this repo's recorded
pattern, not a surprise: revisions are where new criticals come from, which is why the terminal
pass reads the whole document and not the diff.

### Carried into `/hm:execute` as known risks

Recorded, not revised — the terminal pass's findings are the input to implementation, and
`/hm:execute` proceeds rather than halting on them. **Three turn a committed gate red inside a
phase whose declared scope does not contain the fix.**

> **The user chose to apply those three remedies before proceeding** (no third validation
> pass, which the stage forbids). The first three rows below are therefore **already folded
> into Phase 1's and Phase 3's `merge_hazards` and scope-in**; they stay listed here so the
> reasoning is auditable and so a later reader can see *why* those files are in scope. The
> remaining ten rows are genuinely carried.
>
> One remedy carries an ordering constraint worth repeating: the `surface_allowance:`
> frontmatter block must be added **after** its `delta_doc` exists, because
> `surface_allowance._parse` raises `AllowanceError` on a missing doc — adding the block first
> makes the gate red by itself.

| Severity | Finding | What execute must do |
|---|---|---|
| critical | `tests/unit/test_autopilot_template_render.py:98-101` asserts the **exact literal** Jinja condition containing `autopilot_advance_enabled`. Phase 3 deletes that name from that condition. The phase's own grep was over *rendered* output; the surviving reference is in a test over the *template*. | Add that test file to Phase 3's `merge_hazards` and scope-in, and give `_render_partial`'s dead `advance_enabled` kwarg the same disposition. |
| critical | `test_aggregate_shipped_surface_does_not_grow` is **zero-tolerance** (not a 2% band) over `surface_baseline.json`, and `test_round_trip_counts_match_the_live_render` compares exactly. Phase 1 edits `wrapup.md.j2` (both variants) and Phase 4 edits the shared second-opinion partial, which **does** render in those baselines because this repo is models-on. The only sanctioned escape is a `surface_allowance:` frontmatter block plus a **pre-existing** `BASELINE-DELTA-…` doc; this PLAN has neither, and ADR-011's carve-out is scoped to `_ATOMIC_RATCHET` alone. | Add the `surface_allowance` block and its delta doc to Phase 1's scope **before** the first surface-moving edit. Re-freezing `surface_baseline.json` is the destructive act the allowance exists to remove. |
| critical | Phase 1's `--optional` manifest entry rewrites a line whose exact text `instruction_baseline.json` freezes, so the old spelling reads as a removal for **both** `wrapup@` dev_mode arms. The `_PHASE_2_SESSIONID` precedent needed fourteen `_ALLOWED_REMOVALS` entries for this same "nothing is cut, one flag longer" shape. | Add `instruction_baseline.json`, `test_instruction_preservation.py` and `_ALLOWED_REMOVALS` to Phase 1's hazards and scope. Note the Contract Boundaries advisory says only that *Phase 3* adds no entry — it is not a statement about Phase 1. |
| high | `_instruction_baseline.AXES` is `tuple[DevMode, ...]` and `entry_key` is `command@dev_mode.value`, so an `autonomy.level` member fails `mypy --strict` and has no `.value`. The honest form is a **second axis and a new key grammar** — `_SCHEMA_VERSION` 2→3, a doubled baseline (14→28 keys), and a collision with the `<command>@<dev_mode>` grammar this PLAN's own Contract Boundary pins. | Re-scope Phase 3 as a schema migration, or find a different guard for the gated arm. Exit clause 3 is not reachable as written. |
| high | Phase 3's R1 mitigation regenerates the gated snapshot **after** the edit, so the new arm's frozen set records any over-swallowing instead of flagging it — `ratchet-rebaselined-by-its-own-subject` applied to the instruction baseline. Clause 1 counts only `autopilot_caps boundary`; clause 2's SHA identity covers only the non-gated arms. | Carry AC-005's middle conjunct ("the difference between the arms accounts for the advance blocks") into the phase as a gated-vs-`auto_safe` differential against a **pre-change** gated render. |
| high | Phase 6 clause 1 resolves reviewers against a rendered `.claude/agents/` — an untracked artifact, the same thing ADR-012 retracts, one bullet above the ADR-012 note. Also: this repo's `harness.yaml` has no `reviewers.enabled` key and the model default is empty, so the reviewer half may be vacuous on the only renderable config. | Use an in-process render of `harness.yaml`, or resolve reviewers against `templates/agents/` as the skills half resolves against `templates/skills/`. |
| high | `.ledger-exclusions.json` is under the gitignored observability path, so it does **not** survive the clone the roll-up is designed to survive. The committed roll-up then carries numbers whose provenance cannot be checked — the `wrong-transparency-table-worse-than-none` shape, in the artifact this unit adds. | Have the roll-up record the exclusions it applied (names or digest), or state the gap as an accepted limitation as ADR-002 does for `work_docs.dir`. |
| medium | Phase 2 clause 3 requires an import-graph-derived reader set but names no **edge**; the obvious candidate ("imports `ledger_exclusions`") is circular against the exact failure ADR-010 cites — a reader that forgot the import is the one the derivation would not discover. | Name the edge and show it catches an omitting reader, or admit an enumerated set with a positive control that fails when a reader is added. |
| medium | `templates/skills/conditional-router/SKILL.md.j2:38` ships the same false `reviewers.enabled` lever as `review.md.j2:139`, and AC-015's wording ("rendered **command**") excludes a skill by construction. | Record it in Phase 5's scope-out with its reason — the discipline this PLAN already uses for the `memory_retrieve` gap — or fold it in. |
| medium | Phase 1 clause 2 opens "after this phase's commit" while the documented commit point is `/hm:wrapup`; and `git check-ignore` **exits 1** when nothing matches, so "prints nothing" is a pass that a `set -e` chain reads as failure. | State the commit point, and judge clause 2's second half on stdout rather than exit status. |
| medium | ADR-012 asserts RESEARCH finding A-10 "is corrected in place", but no phase's scope-in names `work-docs/RESEARCH-token-efficiency-autopilot-ux-speed.md`. | Add the RESEARCH correction to Phase 5's scope, or drop the claim from ADR-012. |
| medium | Phase 6 clause 3 presumes some asset crosses a `context_lint` threshold; ADR-004 records the opposite for the largest candidate. If nothing crosses, the clause is discharged by observing **silence** — the presence-passes-on-inverted-content shape ADR-005 exists to stop, reappearing as an exit criterion. | Make it a positive observation over a constructed over-threshold asset, keeping the this-repo re-render as the no-fail half. |
| low | Phase 5 clause 5 restates AC-015 rather than naming a check. | Use a literal: the `- Start from \`harness.yaml.reviewers.enabled\`.` bullet is absent from the render while `:279`'s length branch survives. |

### Clean on inspection (stated so the silence is not read as unexamined)

`adrs: 12` matches the twelve `### ADR-` headings. All eight `## 🚧 Contract Boundaries`
bullets conform to the three admitted forms. No `Accept?` / `OK?` / `Verify?` / `Should we?`
phrasing. Every phase carries `depends_on`, `parallel_group`, `merge_hazards`, scope in/out, an
exit criterion, a risk and a rollback point. The phase→AC mapping covers AC-001…AC-015 exactly
once each, with no orphan and no double claim, and agrees with both the Success Criteria list
and the SPEC's Verification Criteria table.
