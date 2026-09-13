---
type: research
task_slug: reviewer-lens-fanout-merge
status: complete
created: 2026-09-13
tags: [harness-maker, research, python, jinja2, review-stage, token-efficiency, lens-fanout]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: [[[PLAN-multi-lens-review-round]], [[PLAN-token-efficiency-autopilot-ux-speed]], [[RESEARCH-harness-diet]], [[PLAN-bench-study-adoption]], [[wiki:architecture nine-lens-axis-and-solo-lens-vote]]]
summary: "Merging the 4 core lenses into one dispatch is plausible but blind-untested; run the missing 1-call-N-category cell first"
---

# RESEARCH — merging the `/hm:review` core-lens fan-out into one dispatch

## 🎯 Recommended Direction

**Build the merge, but decide it with the one measurement nobody has taken: a single
`code-reviewer` call that enumerates all four core lens questions, run against the current
four-call fan-out on the same diff.** The token saving is real and large (three of seven
subagent dispatches disappear, and each one independently re-reads the diff and up to 400
lines of context per changed file). The yield risk is also real and is *not* covered by the
Phase A.5 precedent: the one measured single-call data point in `harness-bench` scored
**11.0 distinct findings against 30.0 for the six-category fan-out at the same task** — but
that single call used the *generic* base prompt, not an enumerated-category prompt. The
merged form is precisely the cell the study never ran. Running it costs one review; guessing
it costs the discovery axis that ADR-007 was written to protect.

Rationale in one line: this repository's own rule is that **lenses merge on measured
redundancy, not on taste** (`conditional_router.CORE_LENSES` docstring), and the redundancy
measured here for the core four is *low* — so the merge has to be justified on a different
axis (context-sharing, not question-overlap), and that axis has never been measured.

## 🔍 Refinement Decisions

**Discovery lens:** Technical architecture / implementation (primary), with the
Research / benchmark lens used on the local `harness-bench` study. The user-workflow
discovery lens does not apply — this is an internal cost/quality trade inside one stage
template, not a product-surface or roadmap question, so the discovery coverage guard's
"broad / trend / user-facing" trigger is not met. No external web or library search was run:
every load-bearing fact here is measurable inside the two local repositories, and the
external literature on multi-persona review does not measure this particular cell either.

## 🛠️ Approaches Found

### Approach A — Collapse the four core lenses into one `code-reviewer` dispatch

| Field | Content |
|---|---|
| **Approach** | One `Task(code-reviewer)` carrying all four lens questions verbatim, explicitly "accountable for all four". Per-finding `lens` stamp kept; the main loop still writes four result files. Mirrors Phase A.5 exactly. |
| **Assumption** | That the distinctive yield of the four lenses comes from the **lens question**, not from the **independent context** each agent runs in. |
| **Evidence** | *For:* Phase A.5 already made this move (`execute.md.j2:265-306`) and records ≈330k subagent tokens + ≈2 min per round saved. The four core lenses already share one agent (`LENS_DISPATCH`) and differ only by one brief sentence — the dispatches are indistinguishable in the rendered command except for that line. *Against:* the same A.5 note records the counter-evidence honestly — "all six blocking issues were solo finds … **the independent contexts, not the lens text, produced that spread**". |
| **Trade-off** | Buys ~3/4 of the core-lens subagent spend; pays with the only structural evidence that four distinct examinations happened. |
| **Compatibility** | **Better than expected.** (1) `review_consensus` is unaffected — one reviewer-lens voice already tags `consensus-passed` (ADR-007), so the merge cannot change any tag. (2) `lens_coverage.exercised_lenses` keys on *files*, not on dispatch count, and the main loop is already the file writer — four files from one return still satisfy it. (3) The 2-pass redaction gate keys on `config.reviewers.enabled | length > 1`, not on lens count, so redaction is not silently disabled. (4) `lens_dispatch()` is shared by round 1 and Step C2, so the confirmation pass follows automatically (SPEC AC-015 parity holds by construction). |
| **Risk** | **medium-high** — see Pitfall 1. The yield loss, if any, is invisible: a merged review that finds less looks exactly like a clean review. |

Concrete surface cost, already known: `review` round trips go **39 → 33** (−3 in round 1,
−3 in Step C2; ADR-011's rule counts every `Task(` individually). Round trips are
**exact-match with no ratchet**, so `tests/structural/test_roundtrip_budget.py` and
`tests/structural/surface_baseline.json` must be re-frozen in the same commit, with a
`BASELINE-DELTA-*` attribution row per changed key.

### Approach B — Partial merge: four lenses into two dispatches

| Field | Content |
|---|---|
| **Approach** | `design` + `consistency` → one call ("is this the right shape, and do the names/docs tell the truth about it"); `functionality` + `robustness` → another ("does it do what the contract says, on every path including the bad ones"). |
| **Assumption** | That context-sharing degrades yield gradually rather than at a cliff, so half the collapse buys half the saving at less than half the risk. |
| **Evidence** | The 2026-08-16 axis merge already used exactly this shape of argument — `complexity` folded into `design` because "is this the right shape" and "is this more shape than the problem needs" are one question asked twice; `naming` folded into `consistency` because both read two places and compare. The pairing above is the same reasoning applied one level up. No measurement supports the specific pairing. |
| **Trade-off** | Half the token win; keeps two independent contexts, so a total failure of one call still leaves two lenses alive. |
| **Compatibility** | Identical to A on every contract (same four files, same tags, same gate). Round trips 39 → 35. |
| **Risk** | **medium** — same invisible-yield-loss class as A, at half the exposure, but with a pairing chosen on reasoning rather than data. |

### Approach C — Keep the fan-out; cut cost inside it

| Field | Content |
|---|---|
| **Approach** | Leave four dispatches, but stop each agent re-deriving the same context: hand all four a pre-built brief containing the redacted diff *and* the surrounding-context excerpts, so the per-lens read budget is spent on escalations only. |
| **Assumption** | That the dominant cost is the four independent repository reads, not the four completions. |
| **Evidence** | Circumstantial. The lens agents are `code-reviewer` (tools: Read/Grep/Glob) and the template gives them a 400-line-per-file context budget plus explicit permission to escalate outside the diff — so four agents perform four overlapping reads of the same files. Nothing measures how much of the spend that is, because **`stage-agents.jsonl` carries no per-lens review rows at all** (57 `test-reviewer`, 41 `plan-validator`, 9 `confirmation-pass`, 0 lens rows). |
| **Trade-off** | Keeps the discovery axis intact; the saving is bounded by whatever fraction of spend is redundant reading, which is currently unknown. |
| **Compatibility** | Total — no contract moves. |
| **Risk** | **low**, but possibly low-value: if most of the cost is completion rather than ingestion, this buys little. |

## ⚠️ Pitfalls

1. **The A.5 precedent transfers less than it looks.** A.5's fan-out was *serial* — the
   template says so outright: "one reviewer retried **serially** surfaces one category per
   round, which is why this was ever a fan-out". Its ≈2-minutes-per-round saving is a
   serialization saving. The review core lenses already dispatch **in one message,
   concurrently**, so wall-clock there is `max`, not `sum` — **merging them saves
   approximately zero latency, and may cost some**, since one agent must now do four
   examinations in sequence inside its own context. Only the token claim transfers. Do not
   let the "≈330k tokens and ≈2 minutes" number travel into this task's PLAN unqualified.

2. **The nearest measured point argues against the merge, and the exact cell is missing.**
   `harness-bench` §10 (`docs/review-convergence/FINDINGS.md:262-270`), tier-1, identical
   call budget:

   | condition | calls | distinct findings | raw findings | duplication |
   |---|---|---|---|---|
   | single structured | 1 | 11.0 | 11.6 | 1.0× |
   | same prompt, 6 calls | 6 | 19.7 | 69.3 | 3.6× |
   | six categories | 6 | **30.0** | 54.7 | 1.8× |

   Two corrections fall out of this table. **(a)** CLAUDE.md's reviewer-fan-out section
   paraphrases the +52% as fan-out recall; the study's contrast is
   `six categories` vs `same prompt, 6 calls` — i.e. it isolates the **category text at a
   fixed call count**, not fan-out versus a single call. **(b)** The single-call arm scored
   11.0 against 30.0, which is the closest thing to a measurement of the merge — but that
   arm ran the *generic base* prompt (METHODS §9: variants are script-derived from one base,
   exactly one axis changing), not an enumerated-four-category prompt. **The merged form is
   the untested cell**, sitting between 11.0 and 30.0 with nothing to locate it.
   The firmware task is the other caution: fan-out recall 43% vs 50% for a single review
   "because the categories overlapped heavily" — so the answer is task-dependent, and
   harness-maker is the Python-shaped case where the fan-out won.

3. **Merging turns `lens_coverage` from evidence into self-report.** Its docstring states
   the failure it exists to catch: "a dispatch that never happened — produces exactly an
   absent or empty file", and it is deliberately fail-closed on liveness. With four files
   written by the main loop from **one** return, the gate can still catch the merged
   dispatch dying wholesale, but it can no longer distinguish "the agent examined
   robustness and found nothing" from "the agent forgot robustness". That is a genuine
   weakening of a gate, and it must be named in the PLAN rather than discovered later.

4. **A lens with zero findings becomes contract-critical.** Today the rule is "a dispatch
   that returns nothing produces no file … that absence is the signal" — which conflates
   *dead agent* with *nothing to report*, harmlessly, because a live lens almost always
   returns something. Under a merge the main loop must write a file for a lens the merged
   agent had no findings for, or **every** clean review blocks on
   `blocks_approval: true`. The empty-file semantics have to be decided explicitly, and
   this is exactly the absent-case class recorded in the global learned corrections
   (2026-06-08, count:8).

5. **Do not implement the merge as a templated placeholder.** `PLAN-multi-lens-review-round`
   records this being tried and reverted: "A single `Task(` template with a `<lens>`
   placeholder rendered three dispatches conceptually while costing one `Task(` — cheaper on
   *both* budgets. It was reverted because … a literal example is what an executing model
   imitates, and **choosing the cheaper form *because* it was cheaper is exactly the move
   that produced two of the four P0s in the parent task**." The merge must render one
   literal dispatch with four literal questions, as A.5 does.

6. **Only the core four are mergeable.** `security` / `concurrency` / `tests` dispatch to
   three *different* agents (`security-reviewer`, `concurrency-reviewer`, `test-reviewer`),
   and measured 0% / 50% / 5% participation in multi-lens groups here. There is no merge
   available there, and Production dispatches all seven. The end state is 7 → 4 dispatches,
   not 7 → 1.

7. **Re-freezing the surface baseline has a precondition ADR-006 got wrong.** A whole-file
   re-freeze is only safe when **no peer PLAN holds a live `surface_allowance`** —
   `load_active_allowances` must return none. This was diagnosed the hard way on
   2026-09-12/13 (`BASELINE-DELTA-workflow-steps-vs-model-capability.md`, Phase 7). Also:
   `tests/structural/test_baseline_delta_attribution.py` wants each changed key's **parent
   segment backticked** (`` `review` ``), not the full dotted key.

## ❓ Open Questions

1. **Do we run the missing cell before deciding, or merge on the A.5 precedent alone?**
   The recommendation is to run it; the user may judge the token win large enough to accept
   an unmeasured yield risk, as A.5 did. If we run it: same diff, one arm = today's four
   core dispatches (a `review-payloads/*-round1-merged.json` already gives this for free on
   six past reviews), other arm = one merged dispatch. Accept threshold has to be set in
   advance — distinct finding groups at file:line, and separately the P0/P1 subset.
2. **Empty-lens file semantics** (Pitfall 4): does a merged run write `{"lens": "robustness",
   "findings": []}` — making "exercised" mean "was asked" rather than "delivered" — or does
   the gate change shape? This decision is binding on `lens_coverage` and must be an ADR.
3. **Four questions verbatim, or one synthesized brief?** A.5 kept all three lens sentences
   verbatim and added "You are ACCOUNTABLE for all three". The core lens briefs are much
   longer (the `consistency` one is four lines). Verbatim is the safer default and the one
   with precedent, but it makes a long dispatch line.
4. **Approach B's pairing** — if a partial merge is chosen, is the `design`+`consistency` /
   `functionality`+`robustness` split the right one? Nothing measures it; the alternative
   split (`design`+`functionality` / `robustness`+`consistency`) is equally arguable.
5. **Should per-lens `stage_agent_ledger` rows be added regardless of the outcome?**
   Today there are zero, which is why this document can report lens *yield* but not lens
   *cost*. Without them the merge's payoff cannot be confirmed after it ships, and a future
   reader is in the same position this one was.
6. **Is the merge reversible by config, or one-way?** `lens_dispatch()` currently derives
   the dispatch list from the preset alone. A `merged` / `fanout` switch would let the
   decision be revisited per project, at the cost of a second rendering arm to test.

## 📊 New measurement taken for this document

Six shipped round-1 reviews carry per-finding `lens` stamps
(`.claude/observability/review-payloads/*/`, post-2026-08-16 axis): `ai-work-boundaries`
(×2 runs), `review-loop-ledger-fixes`, `token-efficiency-autopilot-ux-speed`,
`workflow-steps-vs-model-capability` (×2 runs). 89 lens-stamped findings.

| lens | findings | in a multi-lens group | redundancy |
|---|---|---|---|
| `design` | 16 | 4 | 25% |
| `functionality` | 12 | 6 | 50% |
| `robustness` | 15 | 2 | 13% |
| `consistency` | 15 | 3 | 20% |
| `security` | 5 | 0 | 0% |
| `concurrency` | 4 | 2 | 50% |
| `tests` | 22 | 1 | 5% |

Grouping findings by `file:line`, **8 of 79 groups (10.1%) were raised by more than one
lens**; restricted to the core four, **7 of 51 (13.7%)**. Grouping by file only — a
deliberate upper bound that also merges genuinely different defects in one file — gives
**11 of 27 (40.7%)** for the core four. The true cross-lens overlap is inside that
13.7%–40.7% band.

By severity (file:line groups, all seven lenses): P0 2 groups / 1 solo (50%), P1 24 / 19
(79%), P2 44 / 42 (95%), P3 9 / 9 (100%). Severe findings are the ones most likely to be
corroborated, but n=2 at P0 supports no claim.

**Read this as "the four core lenses currently produce largely non-overlapping output",
not as "merging will lose 86% of the findings."** The measurement cannot distinguish the
lens question from the lens context — which is the whole open problem. Same caveat as the
2026-08-16 run it extends: one run per lens per review, and the source experiment measured
median Jaccard 0.36 between two runs of *one* reviewer, so a re-run redraws some groups.

## 📚 Sources

External literature: none fetched. Every load-bearing measurement is local.

- `~/harness-bench/docs/review-convergence/FINDINGS.md` §10 — the category-split table
  (single structured 11.0 / same prompt ×6 19.7 / six categories 30.0) and the firmware
  non-reproduction (43% vs 50%).
- `~/harness-bench/docs/review-convergence/METHODS.md` §9-10 — prompt variants derived by
  script with exactly one axis changing; blinded adjudication with an internal control.
- `src/harness_maker/conditional_router.py` — `CORE_LENSES` / `DOMAIN_LENSES` /
  `LENS_DISPATCH` / `lens_dispatch()` / `mandatory_lenses()`, and the 2026-08-16
  nine-lens redundancy run recorded in the module docstring.
- `src/harness_maker/lens_coverage.py` — `exercised_lenses` / `coverage_verdict` /
  `round_dir` and their fail-closed rationale.
- `src/harness_maker/templates/stages/review.md.j2` — Step 3 dispatch, the per-finding
  `lens` stamp rationale, the redaction gate condition, Step 4's tag table, Step C2.
- `src/harness_maker/templates/stages/execute.md.j2:265-306` — the Phase A.5 merged
  dispatch and its recorded cost/counter-evidence.
- `tests/structural/test_roundtrip_budget.py` — the `review: 39` entry and the
  count-every-`Task(` rule.
- `.claude/observability/review-payloads/`, `.claude/observability/stage-agents.jsonl`,
  `.claude/observability/review-2026-08-19.jsonl` — the measurement above and the absence
  of per-lens cost rows.

## 🔗 Related Internal Docs

- [[PLAN-multi-lens-review-round]] — the reverted single-`Task(`-placeholder compaction and
  why it was reverted; ADR-004 (round-trip re-baseline), ADR-005 (fan-out renders ungated).
- [[PLAN-token-efficiency-autopilot-ux-speed]] — ADR-003 retracting the
  `reviewers.enabled` fan-out lever (it is not an input to `lens_dispatch` at any point);
  ADR-008 deferring stage-level proportionality (Approach C there, distinct from this one).
- [[RESEARCH-harness-diet]] — "reduce reviewer fan-out" as a diet candidate.
- [[PLAN-bench-study-adoption]] — the route by which harness-bench findings enter this repo.
- [[BASELINE-DELTA-workflow-steps-vs-model-capability]] — the corrected precondition for a
  whole-file surface re-freeze.
- `[wiki:architecture] nine-lens-axis-and-solo-lens-vote` (2026-08-16) — ADR-007's solo-lens
  vote, the per-finding `lens` provenance, and why `lens` is metadata only.
