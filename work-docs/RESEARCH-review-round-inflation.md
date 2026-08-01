---
type: research
task_slug: review-round-inflation
status: complete
created: 2026-08-01
tags: [harness-maker, research, review-stage, auto-fix-loop, convergence, prompt-engineering]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[REVIEW-autopilot-advance-noop-2026-07-31]]", "[[PLAN-second-opinion-acceptance-gate]]", "[[PLAN-audit-convergence-2026-05]]", "[[RESEARCH-review-grade-criteria]]"]
summary: "Round inflation is a fix-quality defect in the Auto-Fix Loop, not review sensitivity — harden the loop, do not raise the cap."
---

# RESEARCH — why `/hm:review` keeps reaching round 5–6

## 🎯 Recommended Direction

**Treat round inflation as a defect in the Auto-Fix Loop's *fix* step, not as a property of
review sensitivity.** The measured defect-per-fix rate on the reference case is ≈1:1, and
the loop is structurally incapable of catching a defect it just introduced: it applies
reviewer-suggested edits one finding at a time, verifies them with a test suite that by
construction contains no test for the class just discovered, and re-reviews only the scopes
it touched — so the last round's fixes always exit unreviewed.

Rationale: every round-count control the stage currently has (`max_review_rounds`, the grade
gate, the no-progress invariant) acts on the *symptom*. None of them acts on the rate at which
fixes create new defects. If that rate stays near 1, no cap produces a converged result — it
only produces an earlier stop with a larger unreviewed delta. The leverage is entirely in
Auto-Fix Loop steps 1–4 (`src/harness_maker/templates/stages/review.md.j2:516-545`).

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary) + **Risk** (secondary).
`--deep` was not set; the topic is a concrete internal-mechanism question with a reference
artifact on disk, so Phase 0/0.5 were skipped. The user-workflow discovery guard does not
apply — this is not a trend/roadmap/user-value topic. No external search was run: the claim
under test is about this repository's own stage templates, and every check below is
reproducible locally.

## 📊 The data (reference case)

`.worktrees/autopilot-advance-noop/work-docs/REVIEW-autopilot-advance-noop-2026-07-31.md:240-298`
— 6 rounds, ~30 findings, 3 budgeted rounds + 3 user-requested:

| Round | Grade | Fixes | New defects found *inside that round's own fix* |
|---|---|---|---|
| 1 | D | — | — |
| 2 | D | 8 | 1 × P0 (`force=True`) |
| 3 | A | 5 | 2 × P1 |
| 4 | A | 5 | 1 × P0/P1 — **the original reported bug, recreated** |
| 5 | A | 5 | 1 × P1 — **the original bug, recreated again** |
| 6 | A | 6 | 3 × P1/P2 inside rounds 4–5's fixes |

Two unbroken regression chains account for roughly half the findings:
`#2 → #7 → #15 → #21 → #25` (ownership rule) and `#17 → #20 → #26/#27` (slug path).
One subsystem produced 9 of 30. Detection is not the variable that changed across rounds.

Corroborating repo history: `[wiki:review] reproduction-outranks-consensus-count` records a
round-5 case where three concurring voices (including two cross-model voters) were all wrong
about a live P1, and a single-voice finding was right — i.e. later rounds are not producing
*better* findings, they are producing *more* findings about newer code.

## 🛠️ Approaches Found

### Approach 1 — Harden fix quality inside the Auto-Fix Loop (recommended)

| Field | Content |
|---|---|
| Approach | Batch-and-re-derive + failing-test-first + unreviewed-delta accounting, inside `review.md.j2` Auto-Fix Loop steps 1–5 |
| Assumption | The loop's edits, not its detection, drive round count; the stage template is the enforcement surface (per CLAUDE.md "LLM 활용 원칙", prompts carry judgment, Python carries rails) |
| Evidence | `review.md.j2:518-528` applies fixes per finding in priority order with no re-derivation step; `:530-536` verifies with the *existing* suite (`pytest -x`/`ruff`/`mypy`) and never requires a new test; `:538` re-reviews only touched scopes; `:565` returns to the gate immediately after applying — so the terminal round's edits are never reviewed. Contrast `execute.md.j2:187-296`, which for the same kind of edit requires Phase A (author tests) → A.5 (test-reviewer gate) → B (RED gate) → C (GREEN) → D (post-GREEN verification). The review loop applies untested edits that the execute stage would reject. |
| Trade-off | Each round costs more (one failing test per fix, one re-derivation pass); total rounds should drop more than per-round cost rises |
| Compatibility | Prose-only change to one template + telemetry field; no Python contract change required for the core of it |
| Risk | low |

Concrete sub-changes, in expected-effect order:

1. **Batch-and-re-derive before editing.** Group a round's findings by subsystem; where ≥2
   findings touch one state model, re-derive the model's full table once and emit a single
   edit, instead of patching each reported cell. This is the largest term — 9 of 30 findings
   in the reference case came from one table patched cell-by-cell.
2. **Failing-test-first per applied fix.** Mirror execute's RED gate: a fix is `resolved`
   only if a test that fails before it and passes after it exists. Today `resolved` requires
   "verification passed" (`review.md.j2:511`) where verification is the pre-existing suite —
   green is guaranteed for a defect class no test covers, so the state transition is
   uninformative.
3. **Account for the unreviewed delta.** The loop can exit right after an apply step. Either
   require a final review-only round with no fixes, or record `unreviewed_fix_count` in the
   Review Iteration Summary so an `A` is not read as "settled". The reference REVIEW wrote
   this in prose (`:262`) — it should be a machine field.
4. **Design-escape branch.** The gate's only outcomes are "fix more" or "stop"
   (`review.md.j2:476-505`). Add: when the defect-per-fix rate stays ≥ ~0.5 across two
   consecutive rounds, stop the loop and surface *revert + re-plan* as the recommended
   action. In the reference case that trigger fires at round 4 — exactly where the REVIEW's
   own retrospective (`:293-298`) says the correct call was to revert two ADRs and re-plan.
5. **Executed-surface gate rule.** Findings whose subject spans the Python contract ↔ prompt
   prose boundary must be gated on the executed surface (the `!` line, the JSON key), not a
   whole-file substring match. This is already a documented recurring class in CLAUDE.md
   checkpoint #2 ("전처리 문제는 파일을 읽어서는 절대 안 잡힌다") with existing prior art —
   `tests/structural/test_no_positional_params_in_commands.py` — but the review loop does not
   require it, and finding #26 in the reference case is exactly this shape.
6. **No prose compaction after logic freeze.** Compaction is an unreviewed edit pass; in the
   reference case it inverted a negation and buried an exception. Order: settle wording, then
   compact, then re-read — never compact as the last act of a round.

### Approach 2 — Tune the round budget / gate strictness

| Field | Content |
|---|---|
| Approach | Raise `max_review_rounds`, or tighten the grade table so `A` is harder to reach |
| Assumption | The loop converges given enough rounds |
| Evidence | Contradicted by the data: rounds 4–6 were already past budget and each still found a defect in the previous round's fix; grade was `A` from round 3 onward while the ownership chain was still live |
| Trade-off | Cost scales linearly with rounds; convergence does not follow |
| Compatibility | Trivial (`models.py:1176`, `harness.yaml:95`) |
| Risk | medium — it hides the rate problem behind a bigger number |

Rejected as a primary measure. Note it is not purely inert: the grade table
(`review.md.j2:450-456`) counts only `consensus-passed` P0/P1, which is why an `A` coexisted
with a live regression chain. That is a *reporting* defect worth fixing alongside Approach 1,
not a round-count lever.

### Approach 3 — Route cross-layer findings out of auto-fix entirely

| Field | Content |
|---|---|
| Approach | Make findings that span prompt ↔ Python, or that touch a declared state model, ineligible for auto-fix; collect them into a follow-up PLAN instead |
| Assumption | Some defect classes are design decisions, and an in-loop patch is always the wrong instrument for them |
| Evidence | Both regression chains in the reference case are of exactly this kind; the REVIEW's own strategic read (`:293-298`) reaches the same conclusion independently |
| Trade-off | Slower to close a review; more PLAN churn; loses the loop's demonstrated value on local defects (`[fail:design] stash-list-substring-match` was caught and correctly auto-fixed in one round) |
| Compatibility | Needs a finding-classification step the stage does not have today |
| Risk | medium |

Best treated as a *narrowed* version of Approach 1's item 4, not a separate direction.

## ⚠️ Pitfalls

- **Reading the grade as convergence.** `A` means "no consensus-passed P0/P1 that anyone has
  looked for yet". Round 3 of the reference case graded `A` with three more regressions ahead
  of it. Source: `REVIEW-autopilot-advance-noop-2026-07-31.md:262`.
- **Assuming more voices means better findings.** `[wiki:review]
  reproduction-outranks-consensus-count`: three concurring voices (2 cross-model) were refuted
  by running the mechanism they named; a single-source finding was correct. A reproduction
  outranks a count in both directions. Adding voters raises recall, not fix quality — and
  fix quality is what is binding here.
- **Re-invoking second-opinion models each round.** Already fixed (`c962e57e`,
  `review.md.j2:539-545`): re-invoking injects a fresh stochastic voter every round, so
  `Remaining`/`New` never drain and the loop exits on the cap. This was one inflation
  mechanism; the remaining inflation is Claude-side fix quality, and the same failure shape
  (nondeterministic voter churn) is worth checking for in the re-spawned reviewers, which are
  merged by `id` but re-run on modified files.
- **Verifying a fix with the suite that already passed.** `pytest -x` green after a fix is
  evidence only about the classes already covered. `[fail:design]
  gitignore-write-text-non-atomic` and `stash-list-substring-match` were both caught by
  *review*, not by the suite — the suite was green throughout.
- **Compaction after the logic settles.** Two of the reference case's findings were created
  by a size-ratchet compression pass, not by the logic edit it summarized.

## ❓ Open Questions

1. **Where does the state-table obligation belong** — a required PLAN section for any change
   declaring a multi-dimensional state model, a SPEC property-AC, or an Auto-Fix Loop step
   that re-derives on demand? (The user's prior note `project_spec_tetrad_oracle_pbt` puts
   property/oracle elicitation in `/hm:spec`; this may be the same seam.)
2. **What is the cost of failing-test-first per fix**, measured? Rounds get more expensive;
   the claim is that total cost drops. Needs one instrumented run before committing.
3. **How is defect-per-fix measured automatically?** Telemetry today emits
   `build_break_count` and `auto_fix_reverted_n` (`review.md.j2:615`) but nothing that says
   "this round's finding is a defect in round N−1's fix". The `id` stamp from Step 3.4 plus a
   `caused_by` field would make the rate computable — and the escape branch (item 4) needs it.
4. **Does the escape branch belong in `/hm:review` or in the `stuck` agent?** Review has no
   escalation path today; `stuck` exists and is read-only.
5. **Should `unverified_severe` / `human_review_needed` also fire on a nonzero unreviewed
   delta?** Currently a terminal round's untouched fixes are invisible to both flags.

## 📚 Sources

No external sources. Every claim above is reproducible from this repository:

- `src/harness_maker/templates/stages/review.md.j2` — Grade Computation (:433-458), Grade Gate (:460-505), Auto-Fix Loop (:507-565), telemetry fields (:595-618)
- `src/harness_maker/templates/stages/execute.md.j2` — TDD machine Phases A/A.5/B/C/D (:183-344), used as the contrast case
- `src/harness_maker/models.py:1176`, `.claude/harness.yaml:95` — `max_review_rounds: 3`
- `.worktrees/autopilot-advance-noop/work-docs/REVIEW-autopilot-advance-noop-2026-07-31.md:240-298` — the 6-round reference case and its own retrospective
- `git show c962e57e` — the already-landed fix for cross-model voter churn
- `tests/structural/test_no_positional_params_in_commands.py` — prior art for executed-surface gating
- `CLAUDE.md` checkpoint #2 — the documented "preprocessing defects are invisible to file-content tests" rule

## 🔗 Related Internal Docs

- [[REVIEW-autopilot-advance-noop-2026-07-31]] — the reference case (§"Why every round finds more")
- [[PLAN-second-opinion-acceptance-gate]] — round-state contract, `id` stamping, vote freeze
- [[PLAN-audit-convergence-2026-05]] — convergence scoring for a different subject (config drift); no overlap in mechanism
- [[RESEARCH-review-grade-criteria]] — origin of the grade table this research proposes to re-read, not replace
- `[wiki:review] reproduction-outranks-consensus-count` — a reproduction outranks a count
- `[fail:design] stash-list-substring-match`, `[fail:design] gitignore-write-text-non-atomic` — cases where the auto-fix loop worked correctly on local defects
