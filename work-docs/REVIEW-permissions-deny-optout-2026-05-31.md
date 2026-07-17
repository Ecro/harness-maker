---
type: review
task_slug: permissions-deny-optout
status: APPROVED
created: 2026-05-31
reviewers_invoked: [security-reviewer, code-reviewer]
consensus_method: cross-check
scope: commit 21a6066 (permissions deny-list opt-out) — standalone unit, no PLAN
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: permissions-deny-optout
  computed_at: 2026-05-31T00:00:00Z
---

# REVIEW — permissions deny-list opt-out (commit 21a6066)

Reviewed AFTER commit (the change was committed directly without a prior review; this review was explicitly requested for the security-sensitive loosening). Findings fixed-forward in a follow-up commit.

## 🎯 Round 1 Summary

A security-default loosening: main-session `settings.json permissions.deny` empty by default, opt-in via `harness.yaml permissions.deny_dangerous: true`. Two reviewers on disjoint lenses.

- **security-reviewer: clean.** Verified the loosening is correctly scoped — the diff touches only models.py / readiness.py / 2 settings templates / test; **no agent sandbox weakened** (all 5 reviewers + executor retain their deny-lists). No inversion bug (default False = empty deny). JSON valid in both branches. The executor still independently denies curl|sh + /etc + ~/.ssh writes, so worktree-bounded autoloop writes stay guarded. No injection surface (plain bool).
- **code-reviewer: 2×P1** (verified, both real).

## 🔍 Drift Findings

None (standalone unit, no PLAN to drift against).

## ✅ Consensus Findings

None — the two reviewers ran disjoint lenses (security-posture vs round-trip correctness), so no surface-match pairs.

## 📝 Manual-Only Findings (single-source; orchestrator-verified + FIXED)

### P1 — `permissions.deny_dangerous` did not round-trip → feature dead end-to-end → **FIXED**
- **OBSERVE:** `synthesize()` rebuilds `HarnessConfig` from `InterviewAnswers` with an explicit kwarg list that **omitted `permissions`** (synthesize.py:675); `InterviewAnswers` had no `permissions` field; `answers_from_harness_yaml` never read `data["permissions"]`. **Verified** against the code.
- **CONCLUDE:** `config.permissions.deny_dangerous` was always False at render time, so `deny_dangerous: true` in harness.yaml rendered `deny: []` anyway — the opt-in was inert through the real `/hm:make --update` path. Violates the reconcile.py:153-155 round-trip contract (CLAUDE.md checklist #6).
- **Fix:** added `permissions: PermissionsConfig` to `InterviewAnswers`; `answers_from_harness_yaml` now reads `data["permissions"]` into the `update` dict; synthesize passes `permissions=answers.permissions`. The harness.yaml flag was already preserved on disk (`_preserve_yaml_user_keys`), so readiness stayed correct — only the settings.json render was dead; now fixed.

### P1 — tests bypassed the broken round-trip → **FIXED**
- **OBSERVE:** the original tests built `HarnessConfig(permissions=...)` directly, skipping `answers_from_harness_yaml → synthesize`, so the dead round-trip was invisible to the suite.
- **Fix:** added `test_deny_dangerous_round_trips_through_synthesize` — writes harness.yaml with `deny_dangerous: true`, runs the real load→synthesize path, asserts `answers.permissions.deny_dangerous` AND `bp.config.permissions.deny_dangerous` are True. This is RED on the pre-fix code, GREEN after.

## 🤝 Disagreements

None — complementary lenses (security-reviewer confirmed the loosening was *safe*; code-reviewer caught that it was *non-functional*).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A (consensus-passed=0) but feature non-functional | — | 2 P1 (manual-only) | — |
| 2 (fix)   | A | round-trip threaded through InterviewAnswers + answers_from_harness_yaml + synthesize; round-trip test added | 0 | 0 |

Final grade: **A** (after fix the feature genuinely works end-to-end)
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false

**Note:** this was the value of reviewing a directly-committed change — the security-reviewer confirmed the loosening was safe, but the feature was silently dead until the code-reviewer's round-trip catch. Lesson reinforced: a setting written to harness.yaml that the render path can't read back is a recurring bug class (CLAUDE.md checklist #6).
