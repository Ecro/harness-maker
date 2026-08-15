---
type: research
task_slug: review-loop-empirics
status: complete
created: 2026-08-15
tags: [harness-maker, research, review-loop, plan-validation, measurement]
mtime_warn_days: 7
libs_fetched: []
sources:
  - "https://claude.ai/code/artifact/fe83fa5c-5fe5-41b9-816b-1c1889bd75af"
  - "https://www.iso.org/obp/ui/en/#!iso:std:78176:en"
  - "https://arxiv.org/pdf/2007.12520"
  - "https://www.st.cs.uni-saarland.de/edu/recommendation-systems/papers/ICSE05Churn.pdf"
  - "https://www.scirp.org/journal/paperinformation?paperid=779"
related_docs:
  - "[[PLAN-ai-review-exit-criteria]]"
  - "[[PLAN-second-opinion-acceptance-gate]]"
  - "[[BASELINE-DELTA-multi-lens-review-round]]"
  - "[[BASELINE-DELTA-validator-pass-cap]]"
summary: "Close the lens-coverage gap and force per-finding dispositions first; instrument round churn second."
---

# RESEARCH — What the 200-run review experiment says about our review/plan validation

## 🎯 Recommended Direction

**Do the two prompt-surface changes first — add the maintainability lenses the fan-out data says
we are blind to, and force an explicit accept/reject disposition on *every* finding (not just
cross-model ones). Instrument per-round fix churn second, and only then touch exit policy.**

The experiment's two largest measured effects both land on surfaces we already own and can change
without new machinery. Category fan-out over the same call budget produced **+52 % unique issues
with 21 % fewer raw remarks** (claude), and the fan-out-exclusive findings concentrated in
`robustness · naming · style` — categories a general reviewer truncates under a "top 15 by
severity" instruction. Our mandatory lens set is `correctness · failure · concurrency · security ·
tests`; `failure ≈ robustness`, but we have **no naming/consistency lens and no complexity lens**,
which is where 11 of claude's 22 fan-out-exclusive groups (and 2 of 7 majors) lived. Separately,
making rejection *optional* produced a **0 % rejection rate**; making it mandatory produced
**20–26 %**. Our auto-fix loop drops findings silently (no `suggestion` → not selected, no record),
i.e. it is the 0 % arm. We already own the disposition machinery (`code-verifier` mode B, the
`accepted/rejected/duplicate/unresolved` enum, `codex_ledger` disposition rows) — it is just
scoped to second-opinion findings only.

Churn instrumentation is the follow-on because the exit-criterion changes it would justify
(stop on churn→0 rather than findings→0; force `confirm-2` when the terminal fix was large) need
a number we do not currently produce anywhere in the review path.

## 🔍 Refinement Decisions

Discovery lens: **technical architecture / implementation** (primary) + **risk** (secondary).
`--deep` was not set; the topic arrived with a primary source attached, so Phase 0/0.5 were
skipped. Warm-tier memory was read from the session-loaded `MEMORY.md` index — no entry covers
review-loop empirics, so `memory_retrieve` was not dispatched separately.

## 🛠️ Approaches Found

### Approach A — Coverage-first (lens set + brief wording)

| Field | Content |
|---|---|
| Approach | Add `maintainability` (naming/consistency) and `complexity/design` lenses to the Step 3 dispatch; add "the public contract is fixed and out of scope" to the design-facing brief |
| Assumption | Our 5-lens fan-out is already the good arm (arm B), so the remaining loss is *which* categories are absent, not the fan-out shape |
| Evidence | Artifact Exp-4: same 6 calls → 19.7 unique (repeat) vs 30.0 unique (category). Fan-out-exclusive by category: robustness 10, naming 8, style 3, design 1, functionality 0, complexity 0. `review.md.j2:180-190` shows our five lenses |
| Trade-off | Two more parallel dispatches per round (~40 % more reviewer cost); naming/style findings are P2/P3 so they add report volume without moving the grade |
| Compatibility | High — `lens_coverage` is keyed on a lens list; adding entries is mechanical. But making them **mandatory** makes `blocks_approval` harder to clear |
| Risk | medium (approval deadlock if the new lenses are mandatory and flaky) |

### Approach B — Disposition-first (every finding gets accepted/rejected + cited authority)

| Field | Content |
|---|---|
| Approach | Extend the PIDA disposition enum from cross-model findings to all findings; the fixer must cite an authority (SPEC AC id, or the code's own docstring) when it rejects |
| Assumption | Our auto-fix loop is the "rejection optional" arm and therefore accepts near-100 % of what reviewers say |
| Evidence | Artifact: optional → 0 rejections; mandatory → 25/97 (26 %) and 30/147 (20 %), with AC numbers quoted in the rationale. Contract-less fixers still rejected 26 %, substituting the docstring as authority. `review.md.j2:641-644` selects fixable findings and records nothing about the rest |
| Trade-off | Either an extra agent round-trip per round (which ADR-001 just *removed* for Pass 1.5, on measured cost grounds), or inline dispositions written by the main loop — cheaper but self-graded |
| Compatibility | High — enum, ledger rows, and `finding_id` join key all exist |
| Risk | low |

### Approach C — Instrumentation-first (per-round churn / size / complexity)

| Field | Content |
|---|---|
| Approach | Emit per-round `fix_churn_lines`, `loc_delta`, and (where tooling exists) cognitive complexity into the REVIEW iteration record and telemetry; use churn to gate re-review and to detect oscillation |
| Assumption | Exit policy should not change before we can see the quantity the policy would key on |
| Evidence | Artifact: new-finding rate at re-review correlates with fix churn r = 0.837 (n = 6) — re-review yield is driven by *how much new code exists*, not reviewer convergence. Compliance separated no arm (47 rounds all 19/19); size and complexity did. `/hm:metrics` measures post-merge blame-survival churn only, never per-round |
| Trade-off | New telemetry surface; cognitive-complexity tooling is language-specific and correlates r ≈ 0.81 with LOC in the artifact's own data, so it adds little beyond "which function is worst" |
| Compatibility | Medium — REVIEW iteration record and `stage_agent_ledger` are the natural carriers; no schema exists yet |
| Risk | medium (metric sprawl; language coverage) |

## Mapping — every prescription against what we ship today

| Artifact prescription | Our system | Verdict |
|---|---|---|
| Review-repeat ≠ review-fix loop; repeat buys coverage (44→71→83→94 %), the loop buys ~0 compliance | Round 1 = one dispatch per lens; rounds 2..3 = fix + **scope-selective** re-review. The new Confirmation Pass (edb87a59) re-runs **all five lenses over a frozen whole-review diff** | **Already largely right.** The confirmation pass *is* review-repeat over an immovable artifact. Its commit message ("risk closure over a frozen artifact, not issue exhaustion") states the artifact's thesis independently |
| Category fan-out > repetition at equal call budget | 5-lens fan-out, dispatched in one message | **Aligned in shape, incomplete in set** — no naming/consistency, no complexity/design lens |
| One review sees ~50 % of what that reviewer can see | One dispatch per lens per round; confirmation pass gives a second independent sample | Two samples ≈ 71 % by the artifact's curve. Acceptable, but not "covered" |
| Falling finding counts ≠ progress; stop on churn→0 | Grade A = zero consensus-passed P0/P1 — literally issue exhaustion. Termination is guaranteed by the monotonic `pending→resolved/stale` lattice and the one-non-progressing-round rule | **Structurally sound, semantically the warned-against metric.** The lattice proves the loop *ends*; it does not show the artifact *improved* |
| Re-review need ∝ fix churn, not round number | Step 6 re-spawns reviewers by **file scope**; `unreviewed_fix_count` is reported and "gates nothing" (skill §5) | **Gap.** A terminal round that rewrote half a file is treated identically to one that changed three lines |
| Force accept/reject on every finding | PIDA dispositions exist for **cross-model findings only** (Step 3.6/3.7). Claude findings without a `suggestion` are skipped with no record | **Gap — likely the single largest quality lever** |
| Loop flipping the same site twice ⇒ spec hole, fix the SPEC | Status oscillation is forbidden by the lattice; **code** oscillation (R3 removes, R4 restores) is undetected | **Gap.** No mechanism routes a contested site back to `/hm:spec` |
| Track compliance + size + complexity + churn together | Grade only, per round | **Gap** |
| Give reviewers repo access; boxing them to one file breaks external contracts | Read/Grep/Glob + 400-line budget that explicitly encourages escalation to callers in other files | **Aligned** |
| Fixer may run tests, must not edit them | Auto-fix step 5 runs targeted tests and reverts on failure; **no ban on editing test files** | **Gap, cheap to close** |
| Prefer two models once over one model many times | Each second-opinion model runs **exactly once** at round 1, then frozen | **Aligned** |
| Round cap matters more for claude (churn never dries) | `max_review_rounds: 3` | **Aligned** |
| "Public contract is fixed, out of scope" in the design brief | Not present in any lens brief | **Gap, one line** |
| Test as oracle, but verify what the test pins (unreachable-state tests) | No guidance; a repeatedly-broken test is treated as a regression | **Gap** — this is the mistake that inverted the artifact's Part 1 |

**Independent corroboration inside our own repo.** `plan.md.j2:588-594` records that across 12
`plan-validator` episodes **none reached a clean verdict**, and that one PLAN documents pass 2's
three criticals as *created by the pass-1 fixes*. That is the artifact's Exp-3 result (new findings
are a function of revision churn) measured on a different artifact type by a different mechanism.
Our response — a hard 2-pass cap with a **terminal** final pass whose findings are recorded and
never revised — is exactly the prescription "stop by budget, not by clean verdict". The plan side
is ahead of the review side here.

## ⚠️ Pitfalls

- **Treat the numbers as directions, not constants.** One 156-line Python module, one 359-line C
  module, two models, N=1 per cell in several places (the churn correlation is n=6). The author
  logs **eleven** reversals of his own conclusions, every one toward the less dramatic reading.
  Any threshold we hard-code from these figures is a guess wearing a citation.
- **Do not read "the loop buys nothing" as "delete the loop".** The same data shows the 5-round
  loop ended *simpler* than the one-shot big fix (cog 22 vs 29, worst function 6 vs 10) because a
  loop can remove what it added yesterday. The correct inference is "stop expecting compliance
  gains from repair rounds", not "stop repairing".
- **Mandatory new lenses can deadlock approval.** `lens_coverage` sets `blocks_approval: true` on
  any missing lens, and a missing lens is un-fixable by the auto-fix loop by design
  (`review.md.j2:596-604`). A flaky naming lens would make every review permanently
  unapprovable. Decide advisory-vs-mandatory before adding, not after.
- **Naming/style findings are P2/P3 and cannot move the grade** (`review.md.j2:521`). Adding those
  lenses without a routing decision buys report volume and zero gate signal.
- **Cognitive complexity is ~80 % LOC.** r = 0.807 in the artifact's own data, matching the
  published LOC↔cyclomatic correlation of 0.85–0.87. It earns its place only for "which function
  is worst", not as a headline number.
- **A silent reviewer is not a finished reviewer.** codex-bare went silent by round 3 having seen
  2 issues in 5 rounds. If we ever key an exit on "a voter stopped reporting", we would be reading
  under-coverage as convergence.
- **Do not re-add a per-round agent round-trip casually.** ADR-001 removed the Pass 1.5
  `code-verifier` dispatch because it dropped 1.9 % of findings for a full serialized round-trip
  on every round's critical path. A naive "PIDA for all findings" reintroduces exactly that shape.
- **The isolation lesson generalizes to us.** A CLI flag named `read-only` still let the reviewer
  read the project's own spec documents. Anything we assert about what a reviewer or second-opinion
  model *cannot* see needs a positive control, or it is an untested half-claim — the same failure
  class as our `.claude/hooks/hooks.json` assertion (2026-07-17).

## ❓ Open Questions

1. **Advisory or mandatory?** Do new lenses join the `lens_coverage` mandatory set (blocking
   approval) or land in a separate advisory section that never gates?
2. **Where do dispositions get produced?** Extending `code-verifier` mode B to all findings costs
   a serialized round-trip per round (the thing ADR-001 removed); having the main loop write them
   inline is cheap but self-graded. Which cost do we accept?
3. **What counts as "authority" for a rejection in our stack?** SPEC AC id is the clean answer, but
   `/hm:review` runs on task-driven work without a SPEC. Is the code's own docstring an acceptable
   fallback (the artifact's contract-less arm did exactly this at the same 26 % rate)?
4. **Churn unit and threshold.** Added+deleted lines per round, absolute or relative to touched-file
   LOC? What value forces `confirm-2` instead of stopping at a clean `confirm-1`?
5. **Oscillation detection storage.** Hunk hashes per round in REVIEW frontmatter, or an
   observability jsonl? And what does a detected oscillation *do* — a `P1` finding routed to
   `/hm:spec`, or a hard `CHANGES_REQUESTED`?
6. **Language coverage for complexity.** Is a Python-only metric acceptable in a harness that
   renders for arbitrary target projects, or do we ship LOC + churn only?
7. **Test-authority rule.** When the same test breaks across rounds, who decides whether it pins a
   reachable state — the fixer, a lens, or a human gate?
8. **Does `max_review_rounds: 3` still earn its keep** once dispositions and the confirmation pass
   are in place, given repair rounds are measured to buy no compliance?

## 📚 Sources

- Artifact "AI 코드 리뷰는 몇 번 돌려야 할까" (2026-08-15) —
  <https://claude.ai/code/artifact/fe83fa5c-5fe5-41b9-816b-1c1889bd75af>. Primary source; ~200 LLM
  calls, 4 experiments, bwrap-isolated with positive controls.
- ISO/IEC 25010 maintainability sub-characteristics — <https://www.iso.org/obp/ui/en/#!iso:std:78176:en>
- Campbell, *Cognitive Complexity* — comprehension-time correlation study, <https://arxiv.org/pdf/2007.12520>
- Nagappan & Ball, *Use of Relative Code Churn Measures to Predict System Defect Density*, ICSE'05 —
  <https://www.st.cs.uni-saarland.de/edu/recommendation-systems/papers/ICSE05Churn.pdf>
  (relative churn's defect prediction did **not** reproduce in the artifact's 8 arms)
- LOC ↔ cyclomatic-complexity correlation (0.85–0.87) —
  <https://www.scirp.org/journal/paperinformation?paperid=779>

## 🔗 Related Internal Docs

- `src/harness_maker/templates/stages/review.md.j2` — lens set (`:180-190`), read budget
  (`:265-280`), grade table (`:531-537`), auto-fix loop (`:606-680`), confirmation pass (`:682-811`)
- `src/harness_maker/templates/skills/second-opinion-gate/SKILL.md.j2` §5 — lifecycle, monotonic
  progress, exit reasons, frozen cross-model set
- `src/harness_maker/templates/stages/plan.md.j2` §4/4.5 — validator two-pass cap and the 12-episode
  measurement
- [[PLAN-ai-review-exit-criteria]] — the exit-criteria work the confirmation pass came from
- [[PLAN-second-opinion-acceptance-gate]] — the PIDA disposition machinery this research proposes
  to generalize
- [[BASELINE-DELTA-multi-lens-review-round]], [[BASELINE-DELTA-validator-pass-cap]] — prior
  measurements on the same two surfaces
