---
type: review
task_slug: source-plan-steps
status: APPROVED
created: 2026-09-18
run_id: a8cde97b0d9f
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: source-plan-steps
  computed_at: 2026-09-18T12:40:00Z
---

# REVIEW — source-plan-steps

Diff under review: `HEAD` (`3b22a595`) → working tree, plus the two new work-docs. Note:
`freeze resolve-base` resolved `review_base` to `a8c94b7c` (origin/main) because local main's
`3b22a595` (the INTENT records commit) is unpushed; the round-1 brief used the `HEAD` diff so
reviewers saw only this task's change.

## 🎯 Round 1 Summary

Grade **B** (P0 0, P1 1). 7/7 lenses exercised, `blocks_approval: false`. Codex `invoked`, 4
findings, PIDA mode B: 4 `accepted`. Fix queue: 1 (the P1). `human_review_needed: false`.

## 🔍 Drift Findings

None. All five changed paths are inside PLAN phase scope; no phase left incomplete.
Step 3.3 objective drift (SOURCE-PLAN-STEPS): one P2, listed below (`69ae019bdf2d48f0`).

## ✅ Consensus Findings

| id | sev | voices | file:line | finding | disposition |
|---|---|---|---|---|---|
| `ffceb87310646d07` | P1 | tests | `tests/structural/test_step_sensitivity_registry.py:251` | `test_docs_carry_classes` binds REGISTRY↔docs only; nothing binds the `_R_PLAN` entries to RESEARCH Table 2, yet the PLAN called it "the permanent binding" | accepted |
| `a8aad0464067647c` | P2 | design, security, codex | `RESEARCH-source-plan-steps.md:123-131` | ADR-003 §4 ("any hit voids") was reinterpreted after it fired; the executed-command criterion was never pre-registered | accepted |
| `55225187cb8d174d` | P2 | consistency, codex | `RESEARCH-source-plan-steps.md:30,55` | Step 0's COMP class is unsupported: its falsifier holds under either class, and "class changes when both readings agree" is not in ADR-002/003 §5 | accepted |
| `6a177429e1624fcb` | P2 | tests | `MATRIX-native-redundancy.md:176` | prose census `(30 of 85)` is asserted nowhere; its predecessor already went stale | accepted |
| `69ae019bdf2d48f0` | P2 | main-loop | `PLAN-source-plan-steps.md` | SOURCE-PLAN-STEPS: widening the `unsourced` definition (docstring, MATRIX legend, CLAUDE.md) is outside the objective's scope | accepted |

Duplicates folded into the rows above: `c079d1a161018d03` (security) and `e7a1e2d1ba0f619e`
(codex) → `a8aad…`; `826684b6f067dd38` (codex) → `55225…`.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | sev | source | file:line | finding |
|---|---|---|---|---|
| `f6be18397a85fed1` | P2 | codex | `RESEARCH-source-plan-steps.md:99` | the blind reading's inputs are not durable: manifest hashes truncated, BRIEF.md lived only in `/tmp`, and BRIEF's COMP bar ("why current models do it unprompted") was weaker than ADR-001's ("a sourced claim") |
| `62ce65309e216afb` | P3 | codex | `RESEARCH-source-plan-steps.md:110` | the recorded vocabulary grep is inaccurate: the real one used `\b`, and ran before BRIEF.md/aggregates.md existed |

## 🤝 Disagreements

Security Pass 1 rated the exposure-check override P1; its own Pass 2 lowered it to P2 (public
repo, only file names in comments reached the model, deviation self-flagged). Kept at P2 — the
Pass 2 verdict is authoritative. Security's Pass 1 P2 on the direct `codex exec` call did not
survive Pass 2.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1 · models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `826684b6f067dd38` | codex | P2 | work-docs/RESEARCH-source-plan-steps.md | 55 | Step 0 reclassification does not meet the evidence bar | plan.md.j2:80-89 shows policy, not capability compensation | false | accepted | RESEARCH:30,55 no sourced COMP claim; class-change rule absent from ADR-002/003 | pending | — |
| `e7a1e2d1ba0f619e` | codex | P2 | work-docs/RESEARCH-source-plan-steps.md | 131 | blind-reading validity ruling does not follow the approved rule | 5 hits; substitute criterion | false | accepted | PLAN:135-137 any hit voids; RESEARCH VALID via substitute rule | pending | — |
| `f6be18397a85fed1` | codex | P2 | work-docs/RESEARCH-source-plan-steps.md | 99 | blind-reading inputs not preserved | truncated hashes, BRIEF in /tmp | false | accepted | manifest truncated; BRIEF bar weaker than ADR-001 | pending | — |
| `62ce65309e216afb` | codex | P3 | work-docs/RESEARCH-source-plan-steps.md | 110 | zero-hits grep claim inaccurate | regex as written matches bundle | false | accepted | real grep used \b, ran before BRIEF/aggregates | pending | — |

### Iteration 2 (Grade: B → A)
Fixes applied: 1
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | bind `_R_PLAN`-cited registry entries to RESEARCH Table 2 (`ffceb87310646d07`) | tests/structural/test_step_sensitivity_registry.py | Applied · caused_by=none |

`[Fix #1] P1 test_docs_carry_classes cannot catch a registry entry that disagrees with its cited table in tests/structural/test_step_sensitivity_registry.py:251` — added
`test_plan_entries_match_their_research_table` + helper `_table2_mismatches` (bidirectional:
table row without a citing entry, citing entry without a row, class/grade mismatch) with a
negative control (Step 5 transcribed as `**` is reported by name). Verification:
`pytest tests/structural/test_step_sensitivity_registry.py` 12 passed; ruff, mypy clean.
The finding's own target is the test file, so editing it is the repair, not an oracle edit.

Lifecycle: `ffceb87310646d07` pending → resolved (progress). All other findings are P2/P3 at
grade B/A — outside the fix queue, left `pending` for the human sweep.
Re-review: `rereview: skipped — churn 0.15 < 0.30`.
Remaining: 7 (all P2/P3) | New issues introduced: 0
Churn: 0.152 (max: tests/structural/test_step_sensitivity_registry.py, measured 1, excluded 0)

## Confirmation Pass

`confirm-1` over `review_base..freeze` = `a8c94b7c..8d8d76ff` (the span includes the two
`INTENT-*.md` objective records committed on base before the task, because `review_base`
resolved to origin/main). 7/7 lenses exercised, `blocks_approval: false`, **0 new findings**
at any severity. Verdict PASS → APPROVED. Freeze refs reaped.
`confirm_pass_ran: true`, `confirm_pass_new_severe_n: 0`.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 8         | —   |
| 2         | A     | 1             | 7         | 0   |

Final grade: A
Iterations used: 2 / 3
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| tests/structural/test_step_sensitivity_registry.py | 252 → 297 | 38 → 51 | 2 → 2 | measured |

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 1 · prior-fix 0 · unattributed 0

**Carried to the human sweep (accepted, not fixed — P2/P3 sit outside the fix queue at grade B/A):**
`a8aad0464067647c` exposure rule reinterpreted after it fired · `55225187cb8d174d` Step 0 COMP
unsupported (falsifier + class-change rule) · `6a177429e1624fcb` MATRIX census untested ·
`69ae019bdf2d48f0` `unsourced` definition widened outside the objective's scope ·
`f6be18397a85fed1` blind-reading inputs not durable, BRIEF bar weaker than ADR-001 ·
`62ce65309e216afb` recorded grep inaccurate.

## Post-review corrections (operator-directed, 2026-09-18)

| id | correction | status |
|---|---|---|
| `a8aad0464067647c` (+ dups `c079d1a161018d03`, `e7a1e2d1ba0f619e`) | RESEARCH Appendix A: blind reading **VOID** per ADR-003 §4 as written; Table 2 rebuilt Claude-only (ADR-003 §6), Codex column kept as non-voting information | resolved |
| `55225187cb8d174d` (+ dup `826684b6f067dd38`) | Step 0 back to INV / `unsourced` in RESEARCH Table 2, registry and MATRIX; the "not INV" observation kept as later work | resolved |
| `62ce65309e216afb` | RESEARCH Appendix A grep record rewritten to what actually ran (`\b`, six files, before BRIEF/aggregates) and the truncated-hash / non-preserved bundle facts stated | resolved |

Verification after the corrections: `pytest tests/structural/test_step_sensitivity_registry.py
tests/structural/test_instruction_preservation.py` 64 passed (the round-2 Table 2 binding test now
checks the corrected rows); ruff, format, mypy clean on `step_sensitivity.py`;
`unsourced_step_share` dry-run 35.3 (unchanged). Not re-reviewed — the corrections move the change
toward the pre-registered PLAN, not away from it; the next reader should confirm Table 2's Step 0
row and Appendix A's VOID line. Frozen cross-model statuses: `826684b6f067dd38`, `e7a1e2d1ba0f619e`,
`62ce65309e216afb` → resolved; `f6be18397a85fed1` → pending (BRIEF.md not preserved — cannot be
recovered, now stated in Appendix A).

Still open for the human sweep: `6a177429e1624fcb` (MATRIX census untested),
`69ae019bdf2d48f0` (`unsourced` definition widened outside the objective's scope),
`f6be18397a85fed1` (bundle inputs not durable).
