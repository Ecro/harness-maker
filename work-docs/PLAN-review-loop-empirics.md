---
type: plan
task_slug: review-loop-empirics
status: planning
created: 2026-08-15
tags: [harness-maker, plan, review-loop, lens-coverage, churn, disposition]
spec: "[[SPEC-review-loop-empirics]]"
research_doc: "[[RESEARCH-review-loop-empirics]]"
interview_rounds: 22
adrs: 9
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Adopt the six-category axis, give each lens a vote, gate re-review on churn."
---

# PLAN — Review loop: coverage diversity in, budget-exhausting repeat rounds out

## 🎯 Executive Summary

**What.** Seven phases. The discovery axis is replaced wholesale by the six categories the source
experiment used, with the three domain lenses kept alongside (P2); each reviewer lens gains a full
vote so the fan-out yield is not discarded (P3); dispositions become mandatory with an
AC-cited-rejection escape (P4); churn is measured (P5), then gates the repair round behind a flag
(P6); oscillation is reported to a human (P7). A pilot (P0) measures the new axis against the old
one, and the changes that need no measurement ship unblocked (P1).

**Why.** Rounds 2..N re-run the same work and stop on issue exhaustion. Measurement
([[RESEARCH-review-loop-empirics]]) says category-distinct calls beat identical ones at equal budget
(+52 % unique, −21 % raw), repair-round yield tracks fix churn (r = 0.837, n = 6), and 40 rounds of
review→fix produced zero compliance improvement.

**The decision that makes the rest coherent.** The fan-out gain consists *by definition* of findings
only one lens raised. Under cross-lens K=2 those become `manual-only` — ungraded and unfixable — so
adopting the axis without ADR-007 would pay the full cost and discard the entire yield. That
interaction was not raised by either second-opinion model nor by the validator; it surfaced when the
user compared this PLAN against the source recipe directly.

**Key decisions.** ADR-001 (six-category axis; domain lenses mandatory on Production, conditionally
routed on Side; both dispatch sites share the set) · ADR-007 (a single reviewer lens votes alone;
K=2 retained for same-lens repeats and for cross-model voters) · ADR-002 (dispositions from the
round-record writer; only an AC-cited rejection clears the grade) · ADR-003 (oscillation as a
`manual-only` `spec_gap`) · ADR-004 (churn gating flagged, default `true`; no new exit reason) ·
ADR-005 (one structured reviewer on repair rounds; `confirm-1` is the compensating sweep) ·
ADR-006 (test-edit ban carves out test-targeted findings).

**Estimated impact — this change costs more, and is defended on coverage, not cost.** An earlier
draft claimed a net saving; that claim was **retracted** after validation (T-08). Repair rounds do
not fan out today — `review.md.j2:661` re-spawns only reviewers whose scope a fix touched, typically
one or two — so the repair-round saving is roughly 0–1 dispatch and is **negative above the
threshold**, where the gate forces one dispatch the scope filter might have skipped. Against that,
Production gains a fixed **+4 at round 1 and +4 at the confirmation pass**, and nine lenses produce
more findings, hence more repair rounds. The justification is the measured coverage gain (+52 %
unique issues at equal budget) and the elimination of *identical* repeat work — not a smaller bill.
Phase 0 measures today's dispatches-per-review so the real delta is known rather than argued.

## 📚 Prior Work

- [[RESEARCH-review-loop-empirics]] — the source measurement and its eleven recorded reversals.
- [[PLAN-ai-review-exit-criteria]] — the confirmation pass (`edb87a59`). Reading it killed this
  PLAN's original forced-`confirm-2` rule: `confirm-1` already diffs `review_base..freeze`.
- [[PLAN-second-opinion-acceptance-gate]] — the PIDA enum, `finding_id`, ledger disposition rows and
  the `finding_ref` discriminator this PLAN generalizes.
- `plan.md.j2:588-594` — 12 `plan-validator` episodes on this repo, none clean, one recording that
  pass 2's criticals were **created by pass 1's fixes**. Reproduced here: nine of the validator's
  criticals were defects in this draft's own new decisions.
- ADR-001 of the two-pass work — removed the Pass 1.5 `code-verifier` dispatch on measured cost.
  Constrains ADR-002.
- CLAUDE.md — K=2 is pinned for cross-model voters (`conditional_router.scope_aware_consensus`) and
  records that codex once caught a P0 two Claude reviewers missed; absent-case rule 2026-06-08;
  `permissions.deny_dangerous` as the opt-out-reported-as-`not_applicable` precedent.

## 🎙️ Interview Transcript

| # | Topic | Category | Choice | Note | → ADR |
|---|---|---|---|---|---|
| 1 | Scope | Scope boundaries | All four change families | Goal recorded as Intent | — |
| 2 | Lens mandatory-ness | Architecture | Mandatory, audit-informed; low-importance at P2 | — | ADR-001 |
| 3 | Rejection authority | Contract shape | AC id preferred, docstring fallback | AC-only returns us to the 0 %-rejection arm | ADR-002 |
| 4 | Round shape | Architecture | Round 1 fans out once; repair rounds re-review narrowly; churn skip | User-authored | ADR-005 |
| 5 | Threshold source | Contract shape | harness.yaml configurable, relative-ratio default | — | ADR-004 |
| 6 | Oscillation outcome | Failure handling | P1 `spec_gap` | Fix the contract, not the code | ADR-003 |
| 7 | Preset split | Architecture | Production full mandatory, Side reduced | — | ADR-001 |
| 8 | Coverage recovery | Risk tolerance | The confirmation pass | — | ADR-005 |
| 9 | Default threshold | Contract shape | 20 % of touched-file LOC | — | ADR-004 |
| 10 | Disposition producer | Architecture | Main-loop inline | Avoids re-adding the round-trip ADR-001 removed | ADR-002 |
| 11 | Oscillation storage | Observability | observability jsonl | Shares the churn write path | ADR-003 |
| 12 | Audit method | Testing depth | Pilot run on this repo's diffs | Becomes Phase 0 | ADR-001 |
| 13 | Rollout | Risk tolerance | churn gating flagged; lens changes unflagged | Rationale corrected at #17 | ADR-004 |
| 14 | Exit | — | End interview | — | — |
| 15 | K=2 conflict | Architecture | (superseded by #18) | Raised by `plan-validator` | ADR-005 |
| 16 | Rejection effect | Risk tolerance | `rejected` does not silently clear the grade | — | ADR-002 |
| 17 | Exit reason | Failure handling | Ratio on `no-progress`; no new exit reason | Avoids reordering a pinned invariant | ADR-004 |
| 18 | Consensus scope | Architecture | **Single reviewer lens votes alone** | User caught that cross-lens K=2 discards the entire fan-out yield — neither model nor the validator saw it | ADR-007 |
| 19 | False-positive escape | Risk tolerance | **Only an AC-cited rejection clears the grade** | Replaces the suppression K=2 used to provide | ADR-002 |
| 20 | Discovery axis | Architecture | **Adopt the six categories verbatim**; domain lenses mandatory on Production, conditionally routed on Side only | User decision; concern about losing security/concurrency/tests was raised and answered by keeping them | ADR-001 |
| 21 | Terminal-verdict gate | Risk tolerance | **Fix T-05, T-06, T-08; accept the other thirteen as risk; no third validation pass** | The terminal verdict was MAJOR_REVISION; the three fixed are the ones that would make `/hm:execute` build something other than this PLAN | ADR-008 |
| 22 | Surface ratchet conflict | Risk tolerance | **Re-freeze `surface_baseline.json`, superseding the prior line's no-refreeze rule** | Surfaced by the suite during Phase 1, not predicted. Third occurrence of a count:2 failure class — deliberate, attributed in BASELINE-DELTA | ADR-009 |

**Assumptions recorded in place of questions the gate declined to ask:**

- **Agent mapping** — six of the nine lenses (`design`, `functionality`, `complexity`, `robustness`,
  `naming`, `consistency`) dispatch to `code-reviewer` with the lens named in the brief; `security`,
  `concurrency` and `tests` keep their dedicated agents. This is how the template already handles the
  two agentless lenses today.
- **`performance-reviewer` / `ux-reviewer`** — outside the six-category axis; they stay as
  conditionally-routed extras, unchanged.
- **Phase order** — P0 informs but does not gate; P1 is independent of it; P5 precedes P6 and P7.

**Corrections applied without an interview round** — defects, not choices, each traced to a source
line by `plan-validator`: forced `confirm-2` removed; confirmation-pass lens parity added;
disposition producer moved to the round-record writer; `no-contract` authority fallback added; churn
endpoints, degenerate files and max-across-files aggregation specified; test-edit ban carve-out
added; oscillation reduced to a report with a defined site key; phase exit criteria pinned to the
SPEC's test names; gate-off N-A branch specified.

## 📐 Architecture Decision Records

### ADR-001: The discovery axis is the six review categories; domain lenses ride alongside, mandatory on Production and conditionally routed on Side
**Status:** Accepted (2026-08-15, via /hm:plan interview)
**Context:** Our five lenses (`correctness`, `failure`, `concurrency`, `security`, `tests`) are an
incidental set. The source experiment's structured arm used the textbook code-review order —
`design`, `functionality`, `complexity`, `robustness`, `naming`, `consistency` — and its measured
fan-out gain concentrated in `robustness`, `naming` and `style`. Its target had no auth and no
threads, so it needed no security or concurrency lens; harness-maker renders for firmware and BLE
repositories that do. `review.md.j2` also names the mandatory set in **two** places — round 1 and
the confirmation pass's Step C2 — and only one was in the original scope.
**Decision:** The six categories become the universal core. `security`, `concurrency` and `tests` are
**mandatory on Production** and selected by the conditional router on **Side only**. Round 1 and the
confirmation pass read the same set. `performance-reviewer` / `ux-reviewer` remain conditional
extras.
**Consequences:**
- ✅ The axis that produced the measured gain is adopted verbatim rather than approximated.
- ✅ Domain safety is preserved where it matters; the cost adjustment lands on the preset axis.
- ✅ Lens parity means the confirmation pass cannot become a permanent `blocks_approval: true`.
- ⚠️ Production round 1 and the confirmation pass go from 5 to 9 dispatches. The saving has to come
  from the repair rounds (ADR-004/005); P0 measures whether it does (risk R6).
- ⚠️ Nine mandatory lenses are nine terminal, unrepairable failure conditions (R1).
**Rejected alternatives:**
- Pure six-category replacement — retires `security`, `concurrency` and `tests`, which exist because
  this harness renders for firmware and auth-bearing repositories.
- Keep the old five and append the missing categories — approximates an axis that was measured as a
  whole, and leaves `design`/`consistency` unowned.
**Source:** Interview #2, #7, #12, #20; validator critical C-02

### ADR-007: A single reviewer lens carries a full vote; K=2 is retained for same-lens repeats and for cross-model voters
**Status:** Accepted (2026-08-15, via /hm:plan interview)
**Context:** The measured fan-out gain consists, by construction, of findings that exactly one
category raised — `robustness` 10, `naming` 8, `style` 3 in the source data, 7 of 22 at major
severity. Our Step 4 requires K=2 agreeing voices; a finding with one voice is tagged `manual-only`,
which `review.md.j2:521` excludes from the grade and `:643` excludes from fix selection. Adopting the
axis while keeping cross-lens consensus would therefore spend nine dispatches and discard their
entire distinctive output. Distinct lenses examine distinct axes: expecting the `security` lens to
second a `naming` finding is a category error, not a quality bar.
**Decision:** A finding raised by exactly one **reviewer lens** is treated as consensus-passed — it
counts toward the grade and is auto-fix eligible. K=2 is retained where corroboration is meaningful:
repeated instances of the same lens, and cross-model voters, who review the same diff on the same
axis rather than a distinct one.
**Consequences:**
- ✅ The fan-out yield is actually captured instead of being logged and dropped.
- ✅ ADR-005 can revert to **one** reviewer per repair round — the user's original choice — because a
  single voice now votes. Validator critical C-01 is resolved by this rather than by a second dispatch.
- ⚠️ **False-positive suppression is gone.** K=2 was the mechanism making grade A reachable at all;
  the source data shows reviewers produce 6–12 findings on verified-correct code with zero-finding
  rounds never observed. ADR-002's AC-cited rejection is the replacement, and R10 records the
  exposure.
- ⚠️ Cross-model findings still need a second voice, so a genuine cross-model-only catch stays
  `manual-only`. Accepted: those findings carry no `suggestion`, so a solo vote would block grade A
  with no repair path.
**Rejected alternatives:**
- Keep cross-lens K=2 — pays for the axis and discards its yield; this is the status quo the change
  exists to leave.
- Extend the solo vote to cross-model voters — unfixable findings blocking the grade.
- Lower `grade_threshold` from A to B instead — lets two genuine P1s through as well as two false
  positives, with no way to tell them apart.
**Source:** Interview #18

### ADR-002: Dispositions are produced inline by the round-record writer, and only an AC-cited rejection clears the grade
**Status:** Accepted (2026-08-15, via /hm:plan interview)
**Context:** Every finding must carry a disposition. Extending `code-verifier` mode B is the obvious
move and is the shape ADR-001 of the two-pass work deleted on measured cost. The first draft also
put the producer inside the *fix-selection* step, which sees only fix-eligible findings. And after
ADR-007 removed cross-lens consensus, the disposition is now the **only** false-positive control in
the system, so its interaction with the grade decides whether the loop can terminate at all.
**Decision:** The **round-record writer** assigns the disposition, seeing every finding on every path
including rounds with no fix step. Authority is required only on `rejected`: a SPEC AC id, else a
docstring citation, else the finding is recorded `unresolved` with authority `no-contract`. A
disposition is **not** a lifecycle transition. A rejection **excludes the finding from the grade only
when it cites a SPEC acceptance-criterion id**; a docstring-cited rejection still counts and sets
`human_review_needed`.
**Consequences:**
- ✅ Zero added latency per round; no reversal of a measured decision.
- ✅ Self-grading cannot launder a P0 into an `A` — that requires citing an independent contract.
- ✅ A genuine false positive has an escape hatch, which ADR-007 makes necessary.
- ✅ The termination proof is unaffected: the two enums stay orthogonal.
- ⚠️ On a task-driven harness with no SPEC there are **no AC ids**, so no rejection can clear the
  grade and every false positive lands on `human_review_needed`. This is the acknowledged cost of
  ADR-007 in the SPEC-less case (R10).
- ⚠️ Two producers write the enum (round-record writer, `code-verifier` for cross-model). One schema
  and one validator, shared, or the rejection rate silently splits.
**Rejected alternatives:**
- Extend `code-verifier` mode B to all findings — the measured cost of the round-trip.
- Let every rejection clear the grade — turns self-grading into grade laundering.
- Keep rejections fully counted — leaves ADR-007 with no false-positive escape at all.
**Source:** Interview #3, #10, #16, #19; validator criticals C-03, C-05, C-16

### ADR-003: Oscillation is reported as a `manual-only` `spec_gap`; state in an observability jsonl; nothing is suspended
**Status:** Accepted (2026-08-15, via /hm:plan interview)
**Context:** Detecting that round 4 restored round 3's removal needs per-round hunk identity;
`finding_id` cannot carry it because it hashes location. The first draft also suspended auto-fix at
the site — for which no cross-round store exists — and emitted an ordinary P1, which under ADR-007
would now be unfixable *and* fully graded, making `A` unreachable.
**Decision:** Append per-round hunk records to `.claude/observability/review-oscillation-{slug}.jsonl`
keyed by (file path, normalized hunk content hash, nearest enclosing symbol). On restoration, emit a
P1 `spec_gap` **tagged `manual-only`**, which sets `human_review_needed` without entering fix
selection or the grade. Nothing is suspended.
**Consequences:**
- ✅ Shares the churn write path; already inside the gitignored harness-churn set; survives `/compact`.
- ✅ Cannot deadlock the loop — the one place `manual-only` is still deliberately used after ADR-007,
  because this finding has no code fix by construction.
- ⚠️ The loop may keep oscillating within the review; the operator is told, not protected.
**Rejected alternatives:**
- REVIEW frontmatter — grows the document and forces a per-round rewrite.
- Suspend auto-fix at the site — requires a store that does not exist.
**Source:** Interview #6, #11; validator criticals C-09, C-19

### ADR-004: Churn gating ships behind `reviewers.rereview_churn_gate` (default `true`); lens changes unflagged; no new exit reason
**Status:** Accepted (2026-08-15, via /hm:plan interview)
**Context:** Re-rendering propagates everything at once. The first draft justified leaving lenses
unflagged with "added lenses only add coverage", **which is false** — a mandatory lens is a new
unrepairable approval blocker, a larger blast radius than the gate it chose to flag. The draft also
added a `churn-converged` exit reason that is unreachable: zero churn implies zero counted lifecycle
transitions, so the pinned `no-progress` rule fires first.
**Decision:** `reviewers.rereview_churn_gate` (bool, default `true`) and
`reviewers.rereview_churn_ratio` (float, default `0.20`). Absent key → default; malformed →
load-time error. Lens changes carry **no** flag — not because they are harmless, but because ADR-005
makes `confirm-1` the compensating control for the narrowed repair round, and a compensating control
that is independently switchable is not a control. The unflagged blast radius is accepted as R8. No
new exit reason: the ratio is attached to `no-progress`.
**Consequences:**
- ✅ A user whose reviews get worse has a one-line revert for the gate.
- ✅ Default `true` means measurement accrues rather than waiting for opt-in.
- ✅ The pinned exit-reason ordering is untouched.
- ⚠️ The axis change has no revert short of pinning an old plugin version (R8).
- ⚠️ `0.20` ships with zero local observations behind it (R3, R9).
- ⚠️ `readiness` must report the off state as `not_applicable`, per `permissions.deny_dangerous`.
**Rejected alternatives:**
- Both flagged, default off — nobody opts in, so no data accrues.
- Keep `churn-converged` with an explicit precedence rule — reorders a pinned invariant for a value
  whose information is fully carried by an annotation.
**Source:** Interview #5, #9, #13, #17; validator criticals C-04, C-13

### ADR-005: Repair rounds dispatch one structured reviewer; `confirm-1` is the compensating sweep and no `confirm-2` is forced
**Status:** Accepted (2026-08-15, via /hm:plan interview)
**Context:** A repair round's re-review is mostly a *first* review of newly written code whose yield
scales with churn, so a full fan-out per repair round is waste. An intermediate draft raised this to
two reviewers because K=2 made a single dispatch structurally inert (validator C-01) — ADR-007
removes that constraint. The draft also forced `confirm-2` after a clean `confirm-1`, which
re-reviews a byte-identical frozen tree.
**Decision:** Above threshold, dispatch exactly **one** structured reviewer over the changed hunks.
Below threshold, none. Full mandatory-lens coverage is re-established once by the confirmation pass
over `review_base..freeze` — which already includes the terminal round's fixes, so **no `confirm-2`
is forced**.
**Consequences:**
- ✅ Repair rounds become **predictable**: exactly one dispatch above threshold, zero below. This is
  not a large saving — the scope filter already selected one or two, and above threshold the gate
  can *force* a dispatch the filter would have skipped (T-08). The gain is that the round no longer
  re-reviews scopes nothing touched, and that the skip is recorded with its ratio.
- ✅ That single reviewer's findings can now be graded and fixed (ADR-007).
- ✅ No identical-repeat pass, which would have contradicted this PLAN's own evidence base.
- ⚠️ Between round 1 and the confirmation pass there is no full-lens sample; `confirm-1` is the
  compensator and ADR-004 keeps it unswitchable.
- ⚠️ One dispatch means one point of failure for the round; a dead dispatch yields a silent
  no-sample round, distinguishable only by the absence of a result file.
**Rejected alternatives:**
- Two reviewers — needed only under cross-lens K=2, which ADR-007 removes.
- Force `confirm-2` on large terminal churn — an identical review of an identical tree.
**Source:** Interview #4, #8, #15, #18; validator criticals C-01, C-07

### ADR-006: The test-edit ban carves out findings whose own target is a test
**Status:** Accepted (2026-08-15, via /hm:plan interview)
**Context:** The source recipe forbids the fixer from editing tests, to stop it making a failing
oracle pass. But `tests` is a mandatory lens on Production, so it raises findings repairable only by
writing a test. An unqualified ban leaves those permanently `pending` — one non-progressing round,
terminal `no-progress`, an unapprovable review on a finding class the harness itself mandates.
**Decision:** The ban is on editing a test to resolve a finding whose target is **not** that test. A
finding whose own target is the test file may be fixed.
**Consequences:**
- ✅ The mandatory `tests` lens stays repairable.
- ✅ The oracle-weakening case the ban exists for is still covered.
- ⚠️ Prompt-level and unenforced; a fixer can mislabel a target. SPEC Non-Goals says so.
**Rejected alternatives:**
- Unqualified ban — guarantees unapprovable reviews.
- Route all test-lens findings to `human_review_needed` — silently downgrades a mandatory lens.
**Source:** Validator critical C-06

### ADR-008: Consensus tagging, grade computation and the re-review decision move into a Python module the stage calls; findings carry per-finding lens provenance
**Status:** Accepted (2026-08-15, after terminal validation — interview #21)
**Context:** Two terminal-pass criticals are the same defect seen from opposite ends. **T-06:** six of
the nine lenses dispatch to `code-reviewer` with the lens named only in the brief; findings carry
`reviewer`/`source`, and the `"lens"` key is written on the **result file**, not per finding. So
ADR-007's rule — solo *lens* votes, same-lens repeats keep K=2 — is undecidable from the data Step 4
sees, because six lenses collapse to one voter name. **T-05:** `review.md.j2:478` states verbatim
that Step 4 runs as prose; `compute_grade` and `rereview_dispatches` do not exist, and the one Python
consensus function (`conditional_router.scope_aware_consensus`) sits on a path that same line
declares unwired. So the ACs encoding ADR-007 have no executable surface, and a green test proves
nothing an operator would see.
**Decision:** Introduce `src/harness_maker/review_consensus.py` owning three pure functions —
`tag_finding(voices) -> tag`, `compute_grade(findings) -> letter`, and
`rereview_plan(churn_ratio, threshold) -> list[Dispatch]` — invoked by the rendered stage through
`hm review_consensus …`, the same shape as `lens_coverage` and `two_pass_review`. The main loop
stamps `lens: <name>` **on every finding** when it writes each lens's result file. `lens` is
metadata and is **not** an input to `codex_adapter.finding_id`, so the round-to-round merge key is
unchanged.
**Consequences:**
- ✅ ADR-007's rule becomes decidable and testable; the ACs name functions that exist.
- ✅ The judgment/mechanism boundary stays where CLAUDE.md puts it: the LLM still decides *whether a
  finding is real*; Python only counts voices and applies the tag table.
- ✅ `paths_to_mutate` gains a module the change actually implements, so the mutation score measures
  this work.
- ⚠️ Step 4's prose must be rewritten to call the CLI rather than describe the arithmetic, and
  `review.md.j2:478`'s "runs as prose" statement retired. That is a larger template edit than the
  original Phase 3 scoped.
- ⚠️ `conditional_router.scope_aware_consensus` now has a live sibling. It stays on its unwired path;
  the new module does not import it, and no phase revives it.
**Rejected alternatives:**
- Keep Step 4 as prose and assert the ACs by render-grep — grep proves the instruction is present,
  never that the tag is correct; after ADR-007 removed cross-lens consensus this is the only
  false-positive control, so it cannot be the untested one.
- Reuse `scope_aware_consensus` — it implements a different single-reviewer exemption keyed on
  `file:line:severity`, has no cross-model concept, and lives on a path the stage does not execute.
- Put `lens` into `finding_id` — changes the merge key and breaks the round-2 voter merge
  (`second-opinion-gate` §1).
**Source:** Interview #21; validator terminal criticals T-05, T-06

### ADR-009: This PLAN supersedes the prior line's no-refreeze rule for the shipped-surface ratchet
**Status:** Accepted (2026-08-15, interview #22 — during Phase 1)
**Context:** `tests/structural/surface_baseline.json` is a **one-directional** ratchet frozen by
PLAN-workflow-step-audit (ADR-010/011) for a line of work whose purpose was to *shrink* the render.
`test_plan_net_surface.py` states in its own docstring that re-freezing is forbidden and names the
failure class — `[fail:test] ratchet-rebaselined-by-its-own-subject`, **count:2** in this repo.
Phase 1's two clauses cost +732 chars after compression from 1 123, and the carve-out half is not
removable (ADR-006). So Phase 1 could not land without either re-freezing or dropping a clause.
**Decision:** Re-freeze, and record the supersede rather than let it read as an oversight.
`work-docs/BASELINE-DELTA-review-loop-empirics.md` carries the attribution the repo's own gates
demand: what moved, the direction (**larger**), the owning phase, and the failure class re-entered.
The escape route named in R11 — moving stage prose into a skill the stage always loads — is
**rejected as metric-gaming**: it lowers the measured number without lowering what the model reads.
**Consequences:**
- ✅ The re-freeze is attributed, per-change, and visible in CI; a future reader finds the
  discontinuity documented rather than inferring it from a number that moved.
- ⚠️ **Third occurrence of a count:2 failure class**, deliberate this time. The distinction from
  the two prior instances is procedural, not technical.
- ⚠️ `surface_baseline.json` is no longer a stable origin for cross-PLAN comparison.
- ⚠️ **This does not scale.** Phases 2–7 add far more than 732 chars. If each re-freezes, the
  ratchet stops being a ratchet — which is R11's still-open decision, now due before Phase 2.
**Rejected alternatives:**
- Cut existing prose to fund it — attempted first and it went wrong: the read-budget block that
  looked like verbatim duplication is **per-dispatch-site and test-enforced**
  (`test_the_agent_body_precedence_is_stated_at_every_site`). Restored. That near-miss is the
  argument against "just trim something else" as a default.
- Drop the two clauses — leaves the mandatory-`tests`-lens deadlock (ADR-006) unfixed.
- Move the prose into a loaded skill — metric-gaming, as above.
**Source:** Interview #22; discovered by the full suite during Phase 1, not predicted by the PLAN

## 🏗️ Technical Design

**Current state.** `review.md.j2` Step 3 dispatches five lenses; Step C2 dispatches the same five over
the frozen diff; `lens_coverage.py` computes `exercised`/`missing`/`blocks_approval`; Step 4 applies a
K=2 consensus filter; the auto-fix loop selects fixable findings (P0–P2, `consensus-passed`, concrete
suggestion), applies, verifies, re-spawns reviewers by file scope, recomputes the grade;
`second-opinion-gate` §5 owns the lifecycle lattice and the four exit reasons.

**Affected components.**

| Component | Change |
|---|---|
| `templates/stages/review.md.j2` | nine-lens round-1 dispatch, **Step C2 dispatch**, per-lens briefs for the six categories, Step 4 consensus scoping, two brief clauses, disposition recording, churn gate, one-reviewer repair round, oscillation step |
| `templates/skills/second-opinion-gate/SKILL.md.j2` §5 | churn ratio on `no-progress`; disposition declared orthogonal to the lifecycle |
| `lens_coverage.py` | preset-aware mandatory set, shared by both dispatch sites |
| `conditional_router` | Side-only routing of the three domain lenses; consensus scoping (lens vs cross-model) |
| `models.py` | `ReviewersConfig.lenses`, `.rereview_churn_gate`, `.rereview_churn_ratio` |
| `presets.py` | per-preset lens defaults |
| `codex_ledger.py` | disposition rows from the round-record writer |
| new `review_consensus.py` | **`tag_finding` / `compute_grade` / `rereview_plan`** — the executable surface Step 4 and the repair round call (ADR-008) |
| new `review_churn.py` | churn measurement, threshold resolution, oscillation detection |
| `readiness.py` | `not_applicable` when the gate is off |

**Data flow (per repair round).**

```
fixes applied ──> review_churn.measure(pre_ref, post_ref, touched_files)   ratio = MAX over files
                        ├─ ratio <  threshold ──> skip, record ratio ──────────────┐
                        └─ ratio >= threshold ─> ONE structured reviewer ──────────┤
                                                                                   │
   consensus scoping: 1 lens voice = passed | 1 cross-model voice = manual-only ───┤
   round-record writer assigns a disposition to EVERY finding ─────────────────────┤
   grade: rejections counted UNLESS an AC id was cited ────────────────────────────┤
   hunk records ──> review-oscillation-{slug}.jsonl ──> restoration? ──> manual-only P1 spec_gap
                                                                                   v
                                              grade + no-progress+ratio + iteration record
```

**API changes.** Two new optional `reviewers` keys; one new observability file; one new finding
category (`spec_gap`); a new `authority` field on dispositions. No existing key or exit reason
changes meaning. The consensus rule changes meaning for reviewer lenses — that is the point of
ADR-007 and it is not backward compatible with a harness that expected `manual-only` demotion.

## 📝 Implementation Plan

> **State at 2026-08-15 wrapup: Phases 0 and 1 are DONE and committed. Phases 2–7 have not
> started.** The PLAN frontmatter deliberately still reads `status: planning` — wrapup's Step 4
> asks for `status: complete`, and writing that over six unimplemented phases would mislead both a
> future reader and a resuming `/hm:execute`. The Success Criteria checkboxes are left unticked
> for the same reason: most are not met yet.
>
> **Two decisions are still open and gate Phase 2** — R11 (a single justified surface allowance
> for the whole PLAN vs. cutting existing prose to fund it) and, informed by Phase 0's audit,
> whether to prune `correctness`, which had zero exclusive yield across all three pilot diffs.

> `parallel_group` values prefixed `serial-` run in **listed phase order**; the label marks shared
> file ownership, not concurrency.

### Phase 0 — Axis pilot — **Status: DONE**
- **depends_on:** `[]` · **parallel_group:** `parallel-audit` · **merge_hazards:** none
- **Result:** `work-docs/AUDIT-lens-axis-2026-08.md`. 33 dispatches over 3 real diffs. **~52 finding-groups (~16 major) that the shipped five lenses did not produce.** Arm comparison: 74 raw findings from 27 dispatches (9-lens) vs 27 from 15 (5-lens) — +174 % findings for +80 % dispatches. Every one of the six new lenses earned exclusive yield.
- **Two results that change the PLAN:** (1) **`correctness` is a prune candidate — zero exclusive groups across all three diffs**, subsumed by `functionality`; pruning it makes the axis 5 → **8** lenses, not 9, recovering one dispatch. (2) The dispatch floor for an approved review rises **11–12 → 19** (~+65 %), which quantifies T-08's retraction: the repair-round saving cannot offset +8 at round 1 and +8 at the confirmation pass.
- **Unexpected support for ADR-007:** on `b83551df`, four lenses reported the same line and each named a *different* defect. Today's Step 4 demotes that to `manual-only`. T-01 is now observed, not hypothetical.
- **Scope.** In: `work-docs/AUDIT-lens-axis-2026-08.md`. Out: every shipped file.
- **Method.** Three real diffs from this repository. The nine-lens configuration does not exist yet
  (Phase 2 builds it), so the pilot **hand-dispatches the nine briefs** — that is not the shipped
  configuration and the caveat is recorded in the audit (T-10). Run the current five-lens
  configuration over the same diffs; cluster; record per lens the groups no other lens produced, with
  severities. **Also record today's baseline dispatch count per review** — round 1, each repair round
  and the confirmation pass — so the cost delta the Executive Summary declines to assert (T-08) is
  measured rather than argued.
- **Exit criterion.** The audit document exists and records per-lens exclusive-group counts with
  severities and dispatch counts over ≥3 named diffs, plus any zero-yield lens as a prune candidate
  (AC-018). **It informs a future prune; it does not gate this change** — the axis is a user decision.
- **Risk:** low · **Rollback:** none needed.

### Phase 1 — Brief clauses, test-edit carve-out, and config plumbing — **Status: DONE**
- **depends_on:** `[]` · **parallel_group:** `serial-review-tpl` · **merge_hazards:** `review.md.j2`
- **Landed.** `src/harness_maker/review_churn.py` (`resolve_churn_threshold`, `churn_gate_enabled`,
  `ChurnConfigError` — absent key → documented default, malformed → load-time error);
  `models.py` `InterviewAnswers.rereview_churn_{gate,ratio}`; `synthesize.py` carries them into the
  rendered `reviewers` block; both preset `harness.yaml.j2` render them with the revert hint;
  `interview.answers_from_harness_yaml` reads them back (checkpoint 6 — otherwise a user's
  `gate: false` is silently restored on re-render). `review.md.j2` gained the global
  contract-fixed brief rule and the test-edit ban **with ADR-006's carve-out**.
  Tests: `tests/unit/test_review_churn_config.py` (AC-012, table-driven from `golden_table`),
  `tests/unit/test_render_review_briefs.py` (AC-017). Snapshots regenerated in the worktree —
  only `commands/hm/review.md` and `harness.yaml` hashes moved, which is exactly the touched set.
- **Deviation from the original scope.** The contract-fixed clause was written as a **global brief
  rule**, not a `design`-lens brief, because the `design` lens does not exist until Phase 2 and
  Phase 1 is deliberately independent of the lens set. `presets.py` lens defaults moved to Phase 2
  with the rest of the lens list, for the same reason.
- **Scope.** In: `design`-lens brief clause + auto-fix ban with ADR-006's carve-out; `models.py` new
  `reviewers` keys; `presets.py` lens defaults. Out: the dispatch list.
- **Exit criterion.** `pytest tests/ -k "test_render_briefs_and_test_edit_carve_out or test_churn_threshold_absent_and_explicit_and_invalid"` passes (AC-017, AC-012).
- **Risk:** low — independent of Phase 0 by design.
- **Rollback:** pre-change.

### Phase 2 — The nine-lens axis on both dispatch sites
- **depends_on:** `[1]` · **parallel_group:** `serial-review-tpl` · **merge_hazards:** `review.md.j2`, `lens_coverage.py`, `conditional_router`
- **Scope.** In: round-1 dispatch list with per-lens briefs, **Step C2 dispatch list and result
  paths**, `lens_coverage.py` preset-aware set, Side-only conditional routing of the three domain
  lenses. Out: consensus scoping, dispositions, churn.
- **Exit criterion.** `pytest tests/ -k "test_round1_lens_set_matches_preset or test_side_mandatory_is_subset_of_production or test_confirmation_pass_uses_same_mandatory_set or test_missing_new_mandatory_lens_blocks_approval or test_p2_only_findings_grade_a"` passes (AC-001 to AC-003, AC-005, AC-015); snapshots regenerated **in the worktree**.
- **Risk:** high — nine mandatory lenses at two sites; a flaky one blocks every Production approval.
- **Rollback:** Phase 1.

### Phase 3 — Lens provenance, the consensus module, and per-lens sovereignty
- **depends_on:** `[2]` · **parallel_group:** `serial-review-tpl` · **merge_hazards:** `review.md.j2` Step 3 + Step 4, `conditional_router`
- **Scope (ADR-008).** In: (a) stamp `lens: <name>` on **every finding** as each lens's result file
  is written — metadata only, never an input to `finding_id`; (b) new
  `src/harness_maker/review_consensus.py` with `tag_finding` / `compute_grade` / `rereview_plan` plus
  its `hm review_consensus` entry point; (c) rewrite Step 4's prose to call it and retire
  `review.md.j2:478`'s "Step 4 runs as prose"; (d) the tag rule itself — a single reviewer-lens voice
  is `consensus-passed`, same-lens repeats and cross-model voices keep K=2. Out: dispositions, churn.
- **Exit criterion.** `pytest tests/ -k "test_single_lens_votes_crossmodel_keeps_k2 or test_finding_carries_lens_provenance or test_finding_id_unchanged_by_lens_field"` passes over the full AC-004 golden table including the mixed cross-model + lens row, and asserts `finding_id` is byte-identical with and without the `lens` field.
- **Risk:** high — removes the system's false-positive filter; **must land in the same release as
  Phases 2 and 4** (T-04, T-05, T-06).
- **Rollback:** Phase 2.

### Phase 4 — Dispositions, authority, and the grade rule
- **depends_on:** `[3]` · **parallel_group:** `serial-review-tpl` · **merge_hazards:** `review.md.j2`, `codex_ledger.py`, `second-opinion-gate` §5
- **Scope.** In: round-record-writer disposition assignment, one shared schema + validator, the
  authority rules including `no-contract`, the AC-cited grade exclusion, ledger rows, and the §5 note
  that a disposition is not a lifecycle transition. Out: churn.
- **Exit criterion.** `pytest tests/ -k "test_every_finding_has_disposition or test_rejection_requires_authority or test_only_ac_cited_rejection_clears_grade or test_dispositions_ledgered"` passes (AC-006 to AC-009), including an `auto_fix`-disabled run and a round with no fix step.
- **Risk:** high — this is the only false-positive control after Phase 3.
- **Rollback:** Phase 3 (and Phase 3 must not ship without this).

### Phase 5 — Churn measurement (record only)
- **depends_on:** `[1]` · **parallel_group:** `serial-review-tpl` · **merge_hazards:** `review.md.j2` iteration record (shared with Phase 4)
- **Scope.** In: `review_churn.py` — pinned pre/post endpoints, per-file ratio, **max across files**,
  created/deleted/binary/renamed handling — plus iteration-record and telemetry fields. Out: any gate.
- **Exit criterion.** `pytest tests/ -k "test_churn_ratio_endpoints_and_degenerate_files"` passes over the full AC-013 golden table; a live `/hm:review` round writes a non-null ratio.
- **Risk:** low — recording only.
- **Rollback:** Phase 4.

### Phase 6 — Churn gate, one-reviewer repair round, ratio on `no-progress`
- **depends_on:** `[4, 5]` · **parallel_group:** `serial-review-tpl` · **merge_hazards:** `review.md.j2`, `second-opinion-gate` §5 (shared with Phase 4)
- **Scope.** In: `rereview_churn_gate`, the skip/dispatch branch, the single-reviewer dispatch, the
  ratio on `no-progress`, `readiness.py` `not_applicable`. Out: oscillation.
- **Exit criterion.** `pytest tests/ -k "test_below_threshold_churn_skips_rereview or test_above_threshold_dispatches_one_structured_reviewer or test_no_progress_records_churn_ratio or test_health_reports_gate_off_as_not_applicable"` passes (AC-010, AC-011, AC-014, AC-019); **with the gate off, a repair round dispatches the same scope-selected reviewer set as before Phase 6**, verified by a snapshot diff limited to the gated block.
- **Risk:** high — the only phase that removes a review that happens today.
- **Rollback:** Phase 5, or `rereview_churn_gate: false`.

### Phase 7 — Oscillation report
- **depends_on:** `[4, 5]` · **parallel_group:** `serial-review-tpl` · **merge_hazards:** `review.md.j2`, `review_churn.py` (shared with Phase 5)
- **Scope.** In: hunk records keyed by (path, normalized content hash, enclosing symbol), restoration
  detection, `manual-only` P1 `spec_gap`, `review-oscillation-{slug}.jsonl`. Out: suspension.
- **Exit criterion.** `pytest tests/ -k "test_oscillating_hunk_emits_manual_only_spec_gap"` passes (AC-016) against a fixture reproducing the R3-removes / R4-restores sequence, asserting both the category and the `manual-only` tag.
- **Risk:** medium — a false positive raises a spurious human-review flag; it cannot block the grade.
- **Rollback:** Phase 6.

## 🧪 Testing Strategy

- **Unit** — one test per AC, named exactly as the SPEC's Verification Criteria table specifies; the
  phase exit criteria select those names, so a green phase proves the claimed ACs ran.
- **Parametric** — AC-004, AC-007, AC-008, AC-010, AC-012, AC-013 are table-driven from their
  `golden_table` rows, boundary and degenerate rows included.
- **Property** — AC-002 (Side ⊆ Production), AC-006 (findings ↔ dispositions), AC-015 (round-1 set ==
  pass set) are invariants over generated inputs.
- **Render/snapshot** — Phases 2 and 6 regenerate snapshots **inside the worktree**.
- **Integration** — one live `/hm:review` after Phase 6 on a real diff: nine lenses at round 1, a
  small fix skipping the re-review with the ratio printed, a large one dispatching one reviewer.
- **Mutation** — `paths_to_mutate` per the machine SPEC, threshold 70.
- **Not tested** — the brief clauses are prompt-level; the tests assert their presence in the
  rendered artifact (SPEC Non-Goals).

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | A mandatory lens fails to return and blocks approval at round 1 or the confirmation pass — now nine chances instead of five | medium | high | The coverage-blocker path names the lens as terminal rather than feeding it to the auto-fix loop; Phase 2 lands both sites together; P0 names zero-yield lenses as prune candidates |
| R2 | Churn gating skips a re-review that would have caught a real defect | medium | high | Flagged (ADR-004) with a one-line revert; `confirm-1`'s full-lens sweep over `review_base..freeze` covers every skipped round's fixes |
| R3 | The 20 % threshold is wrong for this codebase | high | medium | Configurable from day one; Phase 5 records the ratio for every round |
| R4 | Two producers of the disposition enum drift, splitting the rejection rate | medium | medium | One schema, one validator, shared (Phase 4 exit criterion) |
| R5 | Oscillation false positive raises a spurious `human_review_needed` | medium | low | Detection needs restoration of a prior round's exact normalized hunk content; `manual-only`, so it cannot block the grade |
| R6 | Round 1 + confirmation pass rise 5 → 9 dispatches and the repair-round saving does not cover it | **certain** | medium | **Measured by Phase 0, not predicted: the approved-review floor goes 11–12 → 19 dispatches (~+65 %) and the saving does NOT cover it.** The remedy is now concrete: prune `correctness` (0 exclusive groups) for 5 → 8, and re-measure `concurrency` on a worktree/session diff before deciding on it. Phase 5's per-round records track the rest |
| R7 | The source measurement is one case study whose author reversed himself eleven times | certain | medium | No number is hard-coded without a local default and a config escape; P0 re-measures the axis on our own diffs |
| R8 | The axis change is unflagged, so a regressed harness has no revert short of pinning an old plugin version — **and, with the cost claim retracted (T-08), it buys no offsetting saving** | medium | **high** | **Accepted** (ADR-004), re-weighted from medium after terminal validation. Unflagged because `confirm-1` is ADR-005's compensating control and must not be switchable. The remaining controls are Phase 0's exclusive-yield numbers, which name prune candidates, and R6's trigger below |
| R9 | The gate ships default-on with zero local calibration rounds behind the threshold | high | medium | **Accepted**. Phase 5 precedes Phase 6 but nothing gates on N recorded rounds; the mitigation is the config escape, not the phase order |
| R11 | **The prompt-surface ratchet blocks this PLAN.** `tests/structural/test_command_size_budget.py` caps the rendered `review` command at 48,605 chars with a floor to stop the ceiling being met by gutting. Phase 1's two short clauses alone overshot it by 170 chars and grew the aggregate shipped surface by 1,123. Phases 2–7 add nine lens briefs, consensus scoping, disposition rules, the churn gate and oscillation prose — far more | **certain** | high | Discovered during Phase 1, not predicted: this is a **fourth cost dimension** nobody counted (T-08 counted dispatches; this counts context). Phase 1 paid for itself by compressing its own additions. Later phases cannot — raising the `review` ceiling will be a deliberate, justified ratchet change with the pre-change size recorded, or the prose must move out of the stage into a skill the stage loads. **Decide which before Phase 2**, because discovering it at Phase 6 means rewriting five phases of prose |
| R10 | **ADR-007 removes false-positive suppression, so reviews stop reaching grade A.** The source data shows 6–12 findings on verified-correct code and never a zero-finding round | high | high | ADR-002's AC-cited rejection is the replacement. **On a task-driven harness with no SPEC there are no AC ids**, so nothing can clear a false-positive P0/P1 and every such review lands on `human_review_needed`. Phase 4 must ship with Phase 3, never after. The measurable signal is the rejection rate and the `human_review_needed` rate in the ledger — if they climb, the remedy is a `no-contract`-cleared rejection or a `grade_threshold` change, both config-level |

## ✅ Success Criteria

- [ ] AC-001 … AC-019 each covered by a passing test named as the SPEC specifies.
- [ ] `hm spec_machine check --all` stays `ok: true` once `test_ids` are filled and `pending_test`
      flips to `false`.
- [ ] `AUDIT-lens-axis-2026-08.md` records per-lens exclusive yield, severities, dispatch counts and
      prune candidates over ≥3 named diffs.
- [ ] **Phases 2, 3 and 4 ship in one release.** No release contains the nine-lens axis without
      per-lens sovereignty, and none contains sovereignty without dispositions (T-04, T-05, T-06).
- [ ] `review_consensus.py` exists, is invoked by the rendered Step 4 and repair round, and appears
      in `paths_to_mutate`; `finding_id` is byte-identical with and without the `lens` field.
- [ ] `AUDIT-lens-axis-2026-08.md` records today's baseline dispatches per review alongside the
      per-lens yield, so the cost delta is measured (T-08).
- [ ] With `rereview_churn_gate: false`, a repair round dispatches the same scope-selected reviewer
      set as before Phase 6 (behavioural, not byte-identity — Phases 1–5 change the render
      unconditionally).
- [ ] `exit_reason` remains the **four**-value set; the churn ratio appears as an annotation.
- [ ] Round 1 and the confirmation pass render the same mandatory lens set.
- [ ] `hm stage_agent_ledger coherence` exits 0.
- [ ] Snapshots regenerated in the worktree; `ruff check`, `ruff format --check`, `mypy --strict`
      and the full `pytest` suite pass.

## 🔍 Plan Validation

**Pass 1 — MAJOR_REVISION** (9 critical, 9 warning, 1 suggestion). All nine criticals addressed:
C-01 (single reviewer inert under K=2) → resolved by ADR-007 rather than by a second dispatch;
C-02 (confirmation pass lens list unowned) → ADR-001 + Phase 2 scope; C-03 (disposition ↔ lifecycle
mapping, grade laundering) → ADR-002; C-04 (`churn-converged` unreachable) → ADR-004, exit reason
dropped; C-05 (producer cannot see every finding) → ADR-002 round-record writer; C-06 (`tests` lens
vs edit ban) → ADR-006; C-07 (forced `confirm-2` reviews an unchanged tree) → ADR-005, rule removed;
C-08 (churn measurement underspecified) → AC-013 golden table, pinned endpoints, max-across-files;
C-09 (hunk identity and suspension) → ADR-003 site key, suspension descoped. Warnings addressed:
phase DAG corrected, `-k` selectors pinned to SPEC test names, brief clauses raised to ADR-006 and
decoupled into Phase 1, ADR-004 rationale corrected, R3's false control replaced by R9, exit-reason
parity, `no-contract` authority, byte-identity criterion restated, `spec_gap` tag specified,
`/hm:health` N-A given AC-019.

**Cross-model second opinion (pass 1).** `codex` — `invoked`, 13 findings (11 accepted, 1 rejected,
1 unresolved). `antigravity` — `invoked`, 9 findings (4 accepted, 2 rejected, 3 duplicate).

**What none of the three found.** The interaction between cross-lens K=2 and the fan-out yield
(ADR-007) — the defect that would have made the whole axis change a pure cost. Two second-opinion
models and one validator read the draft; the user found it by comparing the PLAN against the source
recipe's own diagram. Recorded here because it is the same lesson the source experiment reports:
the reviewer that stops talking has not necessarily seen everything.

**Pass 2 — TERMINAL. MAJOR_REVISION: 9 critical, 6 warning, 1 suggestion.** Recorded verbatim below
and **not revised** — the 2-pass cap is deliberate (every recorded three-pass episode on this repo
also ended `MAJOR_REVISION`, so a further pass buys findings, not release). Six of the nine are
defects *created by the pass-1 fixes and by interview rounds 18–20*, which is the pattern this
repo's ledger already records.

| # | Severity | Target | Finding |
|---|---|---|---|
| T-01 | critical | ADR-007 vs `review.md.j2:448-455`, `:471-473` | ADR-007 promotes a **solo** lens voice but leaves Step 4b's other outcomes intact: two lenses whose reasoning diverges become `weak-consensus`, and a surface match with reasoning missing on one side becomes `manual-only`. **A finding raised by one lens now outranks the same finding raised by two.** AC-004's table encodes the new rows without saying what Step 4b does. The lattice is non-monotonic in corroboration |
| T-02 | critical | ADR-002 + R10 + AC-007/AC-008 | On a task-driven harness there is no SPEC, so **no rejection can clear a P0/P1**. `no-contract` forces `unresolved`, which at P0/P1 is `manual-only` → `unverified_severe` → `human_review_needed` even at grade A, and the finding stays `pending` → `no-progress` next round. R10's stated remedies do not exist: AC-007 makes `rejected` + `no-contract` **invalid**, and lowering `grade_threshold` cannot clear a P0. No AC covers the absent-SPEC case — the exact absent-case class CLAUDE.md's 2026-06-08 correction names |
| T-03 | critical | ADR-002 Decision + AC-008 | The AC id is produced by the same main loop being graded, and validation checks only its **shape**. Nothing resolves it against `SPEC-<slug>.machine.yaml`. ADR-002's claim that laundering "requires citing an independent contract" is false as specified — citing is a free-text act by the grader |
| T-04 | critical | Phase 2 `depends_on [1]`; Success Criteria pins only 3+4 | Phase 2 ships nine lenses while cross-lens K=2 still holds. Every discarded fan-out P0/P1 is `manual-only` → `unverified_severe` → `human_review_needed` on **every** Production review at that commit. Phases auto-commit and releases cut from main, so the Phase-2-only state is releasable and strictly worse than the status quo on both cost and approvability |
| T-05 | critical | Phase 3 exit criterion; AC-004/005/010/011 predicates; `paths_to_mutate` | **There is no executable surface.** `review.md.j2:478` states verbatim that Step 4 runs as prose; `compute_grade` and `rereview_dispatches` do not exist in `src/harness_maker`; the one Python consensus function (`conditional_router.scope_aware_consensus:62`) is on the path `:478` declares **unwired** and implements a different single-reviewer exemption with no cross-model concept. `paths_to_mutate` names four modules, none of which implement these ACs. A green Phase 3 would change nothing an operator sees |
| T-06 | critical | ADR-007 vs the agent-mapping assumption | Six of nine lenses dispatch to `code-reviewer` with the lens named **only in the brief**. Findings carry `reviewer`/`source`, not `lens`; the `"lens"` key is written on the **result file**, not per finding; `finding_id` hashes `[source, file, line, message]`. So "one lens" vs "a same-lens repeat" vs "two distinct lenses" is **undecidable from the data Step 4 sees** — six lenses collapse to the voter name `code-reviewer`. No phase adds per-finding lens provenance |
| T-07 | critical | AC-013 golden table + S12 | No ratio formula is stated and the rows are inconsistent with the one they imply: `small.py` 30 added / 30 deleted / 30 LOC gives 2.0, but the expected max is 1.0 — an unstated clamp. The all-files-deleted case (empty denominator set) is undefined, as is whether `deleted` belongs in the numerator. Two conforming implementations can disagree by 2× exactly at the 0.20 boundary |
| T-08 | critical | Executive Summary "Estimated impact" + ADR-005 | **Repair rounds do not fan out to nine today** — `review.md.j2:661` re-spawns only reviewers whose scope a fix touched, typically one or two. The saving is ~0–1 dispatch per repair round and is often **negative** (above threshold the gate forces one where the scope filter would have selected zero), against a fixed +8 at round 1 and +8 at the confirmation pass. Nine lenses also produce more findings, hence more repair rounds. The cost claim is the sole justification for accepting an unflagged, un-revertible 80 % dispatch increase |
| T-09 | critical | Affected-components table | Three load-bearing statements of the **old** consensus contract sit outside every listed edit surface: `review.md.j2:11` (Purpose — "single-source findings are recorded as `manual-only`, never auto-applied"), `:473` (tag table), `:546-547` (unverified-severe rationale), plus `second-opinion-gate` §3:138. The stage is read top to bottom by an LLM, and line 11 comes first |
| T-10 | warning | Phase 0 Method | The pilot runs "the nine-lens configuration", which is what Phase 2 builds. Either P0 hand-dispatches nine briefs (say so — its yield then does not transfer) or it silently depends on Phase 2, inverting the stated ordering |
| T-11 | warning | Phase 6 exit vs Success Criteria 5 | "Snapshot diff limited to the gated block" and "behavioural, not byte-identity" cannot both be the acceptance test; a snapshot over a region Phase 6 edits is not empty |
| T-12 | warning | ADR-003 "Cannot deadlock the loop" | True of the letter grade, false of the gate: any `manual-only` P0/P1 sets `unverified_severe` (`:543-548`), which at `:839` becomes STOP-for-human / `--judgment-gate pending` even at APPROVED. The oscillation finding halts the pipeline every time it fires; R5's "low" impact rests on the same wrong premise |
| T-13 | warning | Phase 7 scope / API changes | Nothing owns the finding-schema surface that defines legal categories, so `spec_gap` is a category emitted but never validated |
| T-14 | warning | R1, R6 | R1's mitigation restates the risk; R6's remedy ("a prune") has no owner, trigger threshold or phase |
| T-15 | warning | CLAUDE.md | It documents "k-of-N consensus, K=2 고정" and the `manual-only` semantics. ADR-007 changes both for reviewer lenses and no phase updates it — the documented-vs-shipped drift class this repo has paid for repeatedly |
| T-16 | suggestion | This section | Pass-1 dispositions are asserted without evidence links; a per-item file/section table would make re-validation checkable |

**Assessment (author's, not the validator's).** T-05, T-06 and T-08 are not editorial. T-06 says
ADR-007's rule cannot be evaluated from the data the stage sees; T-05 says the ACs that encode it
have no executable surface at all; T-08 says the cost premise in the Executive Summary is
contradicted by the file this PLAN cites for current behaviour. Any of the three is enough to make
`/hm:execute` produce something other than what this PLAN describes.

### Gate resolution (interview #21)

The user was presented the terminal verdict and chose to **fix T-05, T-06 and T-08 and proceed**,
accepting the remaining thirteen as risk. No third validation pass was run. What changed:

| Finding | Disposition | Where the fix landed |
|---|---|---|
| T-05 no executable surface | **fixed** | ADR-008; Phase 3 scope (b)(c); `review_consensus.py` in Affected components; `paths_to_mutate`; AC-004/005/010/011 predicates rebound |
| T-06 lens provenance undecidable | **fixed** | ADR-008; Phase 3 scope (a); new `test_finding_carries_lens_provenance` and `test_finding_id_unchanged_by_lens_field` |
| T-08 cost claim contradicted | **fixed** | Executive Summary "Estimated impact" retracted and rewritten; ADR-005 consequence corrected; Phase 0 gains a baseline dispatch count; R8 re-weighted to **high** |
| T-10 Phase 0 method | **fixed in passing** | Phase 0 now states the pilot hand-dispatches and records the caveat |
| T-01 non-monotonic lattice · T-02 SPEC-less deadlock · T-03 forgeable AC citation · T-04 Phase 2 releasable alone · T-07 churn formula under-determined · T-09 three old-contract statements · T-11 Phase 6 criterion conflict · T-12 oscillation halts the pipeline · T-13 `spec_gap` unvalidated · T-14 R1/R6 discharge outside the PLAN · T-15 CLAUDE.md not updated · T-16 no disposition links | **accepted as risk** | Recorded above; `/hm:execute` inherits them. T-01, T-02 and T-04 are the ones most likely to surface first — T-04 in particular means **Phases 2, 3 and 4 must ship in one release**, which the Success Criteria now pins |
