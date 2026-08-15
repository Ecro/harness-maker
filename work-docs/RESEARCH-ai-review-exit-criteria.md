---
type: research
task_slug: ai-review-exit-criteria
status: complete
created: 2026-08-14
tags: [harness-maker, research, review-stage, exit-criteria, risk-closure, lens-coverage]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[RESEARCH-review-round-inflation]]", "[[PLAN-review-round-inflation]]", "[[PLAN-multi-lens-review-round]]", "[[PLAN-second-opinion-acceptance-gate]]", "[[RESEARCH-review-grade-criteria]]"]
summary: "Exit is already risk-weighted; what is missing is a frozen artifact, declared lens coverage, and an accepted-risk record."
---

# RESEARCH — AI review exit criteria: Issue Exhaustion vs Risk Closure

## 🎯 Recommended Direction

**The proposed model's six exit criteria are not a redesign of `/hm:review` — three of
them already ship, and the three that do not each fail for a different structural
reason. Attack them in the order ⑤ → ④ → ⑥, and start with ⑤ (frozen diff), because
it is the only one that changes what "stop" *means*.**

Rationale: harness-maker's grade gate is already Risk Closure, not Issue Exhaustion —
only `consensus-passed` P0/P1 move the letter, and P2/P3 never do
(`review.md.j2:455-478`). "Minor 3개 남았는데 STOP" is the shipped behaviour, not an
aspiration. What the stage *cannot* currently do is evaluate criterion ⑤ at all: rounds
2..N review the **mutated** diff, so "two consecutive clean reviews of the same frozen
diff" has no referent. Every round's fixes change the artifact under review, and the
last round's fixes always exit unreviewed — which is exactly where the measured
1:1 fix-to-defect rate lives.

Binding trade-off: closing ⑤ properly costs one full multi-lens pass over the whole
final diff, and the prior work on this stage explicitly **rejected** buying convergence
with more rounds (`RESEARCH-review-round-inflation`). The proposal below is therefore
*not* "more rounds" — it is decoupling the fix loop from the exit evaluation, so the
exit decision is made once, over a frozen artifact, by reviewers who did not see the
fixes being applied.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary) + **Risk /
compliance** (secondary). `--deep` was not set — the topic is a concrete
internal-mechanism question with the mechanism on disk. The user-workflow discovery
guard does not apply: this is a maintainer-internal design question about this
repository's own stage template, not a trend/roadmap/user-value topic. No external
search was run; every claim below is a local file citation or a local measurement.

## 📐 Mapping the six proposed criteria onto what ships today

| # | Proposed criterion | Status in `/hm:review` | Where |
|---|---|---|---|
| ① | All Critical closed | **Ships.** Grade A requires `P0_count == 0` | `review.md.j2:470-478` |
| ② | Accepted Major closed | **Ships.** Grade A requires `P1_count == 0`; P2/P3 excluded from the letter | `review.md.j2:455-460` |
| ③ | Human holds semantic ownership of the critical path | **Absent.** Nearest proxies are the Step 2 drift gate (PLAN/SPEC vs actual diff) and `/hm:verify` | `review.md.j2:115-165` |
| ④ | All defined review lenses executed | **Absent as a criterion.** Reviewer selection is *reductive* path/LLM routing over 5 agents; nothing records which lenses ran | `conditional_router.py:106-137` |
| ⑤ | No new material issue over consecutive reviews of a **frozen** diff | **Structurally impossible today.** Only the cross-model set is frozen at round 1; Claude reviewers re-review the mutated diff, and re-review is *selective* (touched scopes only) | `review.md.j2:565`, CLAUDE.md §PIDA |
| ⑥ | Remaining issues are explicitly accepted risk | **Partial.** `unverified_severe` + `human_review_needed` surface residual severe findings, but there is no `accepted` disposition and in loop mode **the flag has no runtime reader** | `review.md.j2:482-515` |

Three additional facts that constrain any redesign:

1. **The stopping rules that do exist are exhaustion-shaped.** `max_review_rounds` is a
   budget cap and the no-progress invariant (step 7b) stops when a round produced no
   lifecycle transition. Neither says anything about risk; both stop the loop *earlier*
   with a *larger* unreviewed delta.
2. **Attribution already ships, and gates nothing.** The loop stamps `caused_by` per
   finding and telemetry carries `unreviewed_fix_count`, `regression_attributed_n`,
   `attribution_unknown_n` (`review_telemetry.py:75-84`). The proposal's "Issue C가
   원래 것이냐 Fix가 만든 것이냐" problem is *already measured* — it is deliberately
   not gated (`PLAN-review-round-inflation` ADR-003). The data to size any change is
   therefore already on disk.
3. **The measurement says the problem is real and large.** `[fail:test]
   fix-introduced-defect-passes-all-gates` (count:7): 11/22 findings were defects
   introduced by the previous round's own fixes; a later phase measured **7/7**; a third
   task had 3 of 4 rounds each certify a fix the next round overturned — every time on a
   fully green `ruff` + `ruff format` + `mypy --strict` + `pytest` run, and once with a
   7/7 mutation score. **A green gate after a fix is evidence about the gates' coverage,
   not about the fix.**

## 🛠️ Approaches Found

### Approach A — Frozen-diff confirmation pass (criterion ⑤)

| Field | Content |
|---|---|
| Approach | After the auto-fix loop reaches `grade ≥ threshold`, freeze the resulting diff and run **one** full multi-lens review over the entire frozen diff — not the selective touched-scope re-review of step 6. Exit only when that pass yields 0 new `consensus-passed` P0/P1. |
| Assumption | That the residual risk concentrates in the last round's fixes, which today exit unreviewed by construction. |
| Evidence | `RESEARCH-review-round-inflation` states the loop "re-reviews only the scopes it touched — so the last round's fixes always exit unreviewed"; `unreviewed_fix_count` was added to count exactly this. The count:7 memory entry supplies the rate. |
| Trade-off | One extra full review dispatch per `/hm:review`. This is a real cost on the common case where the loop converges in 2 rounds. It is *not* a round-count increase — the fix loop's cap is unchanged; the added pass never applies fixes. |
| Compatibility | Reuses the existing Step 3/4 machinery. Needs a decision on whether it replaces or follows the final selective re-review. Cross-model voters are already frozen at round 1, so their votes must be re-read, not re-invoked. |
| Risk | medium — cost is certain, benefit is inferred from an n-small set of measured tasks. |

### Approach B — Declared lens coverage (criterion ④)

| Field | Content |
|---|---|
| Approach | Make a round declare which lenses it exercised, and treat an unexercised mandatory lens as a gate condition rather than an invisible omission. |
| Assumption | That reviewer breadth, not reviewer depth, is the dominant recall variable. |
| Evidence | `PLAN-multi-lens-review-round` measured it directly: 1 lens → 2 and 3 findings; **3 parallel lenses → 9 and 12**; a 4-voice review → 36. In the 3-lens rounds the two blocking lenses had **zero overlap**, and the lens that returned PASS on its own rubric surfaced two defects belonging to another lens. That work applied the finding to `/hm:execute` Phase A.5, **not** to `/hm:review`. |
| Trade-off | The current reviewer set does not match the proposed lens set. Shipped scopes are `code/design/correctness`, `security`, `performance`, `ux`, `concurrency` (`conditional_router.py:23-29`). The proposal's **Pass 2 (failure / recovery / persistence)** and **Pass 5 (tests / oracle / mutation)** have no reviewer in `/hm:review` — `test-reviewer` exists but only runs in `/hm:execute` Phase A.5. Adding lenses adds dispatches. |
| Compatibility | `routing: conditional` currently *removes* reviewers by path substring; a coverage criterion inverts that intent and would need the two reconciled. |
| Risk | medium — the lens taxonomy itself is a design decision, not a lookup. |

### Approach C — Accepted-risk register (criteria ⑥ + ③)

| Field | Content |
|---|---|
| Approach | Add an explicit `accepted` disposition with a required rationale and owner, and end the REVIEW report with a residual-risk register instead of a list of open findings. |
| Assumption | That the difference between "AI didn't find anything" and "we know what remains and chose to accept it" is worth a persisted field. |
| Evidence | The disposition vocabulary already exists for the cross-model gate — `accepted`/`rejected`/`duplicate`/`unresolved` (CLAUDE.md §PIDA) — but is scoped to second-opinion findings and means "accepted as a *finding*", not "accepted as a *risk*". The gap is a vocabulary collision as much as a missing feature. |
| Trade-off | Cheapest of the three to build, and the one that does least on its own. Without ④/⑤ the register records residual risk from an unmeasured coverage baseline. |
| Compatibility | Must state a **loop-mode reader**. `human_review_needed` already degrades exactly this way: ADR-003 accepts that in loop mode "the flag has no runtime reader" (`review.md.j2:511-515`). A second criterion with the same shape reproduces the failure. |
| Risk | low to build, medium to trust. |

**Recommended (informational — `/hm:plan` decides):** A, then B, then C. A is the only
one that changes the semantics of stopping; B raises recall the most per the one
measurement that exists; C is bookkeeping that becomes meaningful only after the other two.

## ⚠️ Pitfalls

1. **Do not buy convergence with rounds.** `RESEARCH-review-round-inflation` rejected
   raising `max_review_rounds` on the grounds that no cap changes the rate at which fixes
   create defects — a higher cap "only produces an earlier stop with a larger unreviewed
   delta." Any "2 clean passes" rule implemented over the *mutated* diff is that mistake
   wearing new clothes: it would certify "the last two rounds' fixes were small", not
   risk closure.
2. **Consensus count is not evidence.** `[wiki:review] reproduction-outranks-consensus-count`
   records a round-5 case where three concurring voices, including two cross-model voters,
   were all wrong about a live P1 and a single-voice finding was right. A lens-coverage
   criterion must not silently become a vote-count criterion.
3. **Grade A is not "reviewed".** `[wiki:gotcha] loop-body-skipping-review-stage` records a
   cumulative review that returned Grade A while holding 5 real P1s, because the strict
   cross-reviewer surface-match rubric tagged them all `manual-only` and manual-only
   findings do not lower the letter. The proposal's "No Findings ≠ Reviewed" has a
   sharper local form: **Grade A ≠ zero severe findings.** `unverified_severe` was added
   for precisely this and is the field any new criterion must compose with.
4. **Green gates prove coverage, not correctness** — count:7 above. A confirmation pass
   that only re-runs the mechanical gates would add cost and no information.
5. **Absent-case black hole.** CLAUDE.md's 2026-06-08 learned correction: any gate that
   activates on an optional field must define its absent-case. A new exit criterion with
   no loop-mode reader is a silent no-op on exactly the path that runs unattended.
6. **Prompt-level criteria are not enforcement.** All six proposed criteria would live in
   a `.j2` stage template, i.e. in prose the model is asked to honour. The stage's own
   history shows a model reinterpreting an expensive mandatory step as optional under
   context pressure (pitfall 3's entry: review silently skipped for 6 iterations). A
   criterion that costs a dispatch needs a machine receipt, not a paragraph.

## ❓ Open Questions

1. **Does the confirmation pass replace or follow the last selective re-review?** Replacing
   keeps dispatch count flat but loses the targeted check on the last fixes; following
   adds one full pass per review.
2. **Which lens taxonomy?** Adopt the proposed five
   (correctness / failure-recovery / concurrency-resource / security / test-oracle), or
   extend the shipped five (which include `ux` and `performance` and lack failure-recovery
   and test-oracle)? These are not the same axis — one is failure-mode-shaped, the other
   agent-shaped.
3. **Is lens coverage a gate or a recorded property?** A gate cannot coexist unchanged with
   `routing: conditional`, whose purpose is to *drop* reviewers.
4. **Re-type severity, or add a `risk_class` field beside it?** P0 currently mixes
   "data loss" with "build/CI breakage" — the latter is deterministically detectable and
   does not belong in a residual-risk class. But P0..P3 is a wire format across
   append-only telemetry and ledger rows; re-specifying its meaning silently re-labels
   history.
5. **Who is the acceptance authority under autopilot `auto_full`?** Today that level
   *clears* `human_review_needed` and records the passed-over ids — an accepted-risk
   register with no human in the loop is an auto-signed waiver.
6. **Scope: `/hm:review` only, or also `/hm:execute` Phase A.5 and `/hm:verify`?** The
   multi-lens evidence was gathered at A.5, and `/hm:verify` is the stage that already
   claims the "pre-completion stop sign" role.

## 📚 Sources

No external sources. All evidence is local and re-checkable:

- `src/harness_maker/templates/stages/review.md.j2` — grade computation (455-478), grade
  gate + `unverified_severe` (480-529), auto-fix loop (531-584).
- `src/harness_maker/templates/agents/_partials/rubric.md.j2` — the P0..P3 severity rubric.
- `src/harness_maker/conditional_router.py` — `REVIEWER_SCOPES` (23-29),
  `scope_aware_consensus` (41-), `route_reviewers` (106-137).
- `src/harness_maker/review_telemetry.py:75-84` — the measure-C counters.
- `work-docs/RESEARCH-review-round-inflation.md`, `work-docs/PLAN-review-round-inflation.md`.
- `work-docs/PLAN-multi-lens-review-round.md` — the lens-breadth measurements.
- `CLAUDE.md` §Cross-model second opinion — PIDA disposition enum, frozen round-1 set.

## 🔗 Related Internal Docs

- [[RESEARCH-review-round-inflation]] — why rounds inflate; rejects the round-cap answer.
- [[PLAN-review-round-inflation]] — `caused_by` attribution + the measure-C counters.
- [[PLAN-multi-lens-review-round]] — 1 lens vs 3 lenses, measured.
- [[PLAN-second-opinion-acceptance-gate]] — finding `id` stamping, PIDA dispositions, vote freeze.
- [[RESEARCH-review-grade-criteria]] — prior work on the grade gate itself.
- `[fail:test] fix-introduced-defect-passes-all-gates` — the fix-defect rate, count:7.
- `[wiki:gotcha] loop-body-skipping-review-stage` — Grade A over 5 unfixed P1s; skipped-review precedent.
- `[wiki:review] reproduction-outranks-consensus-count` — three concurring voices, all wrong.
