---
type: review
task_slug: how-it-works-docs
status: APPROVED
created: 2026-05-09
reviewers_invoked: [code-reviewer]
consensus_method: scope-exempt (single reviewer)
final_grade: A
iterations_used: 2
human_review_needed: false
---

# Review: how-it-works-docs

## 🎯 Round 1 Summary

**Grade: D** (P0=2, P1=2, P2=1)

Single new file `docs/HOW-IT-WORKS.md` (1,730 lines, Korean-language docs).
Conditional router: docs-only path → code-reviewer only (no auth/perf/UI/concurrency paths).
Single-reviewer context → scope-exempt bypass → all findings `consensus-passed`.

Fixes pending: 5 (2×P0, 2×P1, 1×P2).

## 🔍 Drift Findings

None — the file is the planned output per PLAN-how-it-works-docs.md Phase 2.

## ✅ Consensus Findings (Round 1, all consensus-passed)

### P0

| # | File | Line | Summary | Tag |
|---|------|------|---------|-----|
| 1 | docs/HOW-IT-WORKS.md | 588 | Grade table entirely wrong — all A/B/C/D/F boundaries mis-mapped | consensus-passed |
| 2 | docs/HOW-IT-WORKS.md | 596 | Field name `max_grade_threshold` wrong; default B wrong | consensus-passed |

**Finding #1 reasoning:**
- Observe: doc lines 588-592 show A=P0=0,P1≤2; B=P0=0,P1≤5; C=P0≤1,P1≤10; D=P0≤3; F=P0>3. Source (`review.md`) shows A=P0=0,P1=0; B=P0=0,P1=1-2; C=P0=0,P1≥3; D=P0=1-2; F=P0≥3.
- Infer: Every grade boundary is wrong. A user reading this table would believe 2 P1 findings earn grade A when the real system gives grade B.
- Conclude: P0 — users cannot predict review pass/fail from the document.

**Finding #2 reasoning:**
- Observe: doc uses `max_grade_threshold` with default B in 3 places (lines 596, 789, 1615). Actual field is `grade_threshold` with default A.
- Infer: Setting `max_grade_threshold: B` in harness.yaml silently uses an unknown key; system falls back to default A, creating a mismatch the user cannot debug.
- Conclude: P0 — wrong field name causes silent config failures.

### P1

| # | File | Line | Summary | Tag |
|---|------|------|---------|-----|
| 3 | docs/HOW-IT-WORKS.md | 1610 | Worktree scope shows [execute] only; Production default is [execute, plan] | consensus-passed |
| 4 | docs/HOW-IT-WORKS.md | 302 | PLAN language rule omitted — PLAN documents are always English on disk | consensus-passed |

### P2

| # | File | Line | Summary | Tag |
|---|------|------|---------|-----|
| 5 | docs/HOW-IT-WORKS.md | 789 | exec-rev-wrap: doc says wrapup skipped on grade miss; actually proceeds with flag | consensus-passed |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None.

## 🤝 Disagreements

None (single reviewer, no cross-reviewer divergence).

---

### Iteration 2 (Grade: D → A)

Fixes applied: 5

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P0 | Grade table replaced with correct values | docs/HOW-IT-WORKS.md:588 | Applied |
| 2 | P0 | `max_grade_threshold`→`grade_threshold`, default B→A (×3) | docs/HOW-IT-WORKS.md:596,791,1617 | Applied |
| 3 | P1 | Worktree scope comment updated with Production preset note | docs/HOW-IT-WORKS.md:1612 | Applied |
| 4 | P1 | PLAN language rule callout block added | docs/HOW-IT-WORKS.md:304 | Applied |
| 5 | P2 | exec-rev-wrap: `human_review_needed` flag behaviour corrected | docs/HOW-IT-WORKS.md:791 | Applied |

Remaining: 0 | New issues introduced: 0

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 5         | —   |
| 2         | A     | 5             | 0         | 0   |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false
