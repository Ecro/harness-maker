---
type: review
task_slug: review-base-and-superseded-gaps
status: APPROVED
created: 2026-10-05
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 50a27677b0ca
review_base: 62564cef5ac37213eb70b9a0728bcf2be2cf61f9
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: review-base-and-superseded-gaps
  computed_at: 2026-10-04T15:05:00Z
---

# REVIEW: review-base-and-superseded-gaps

## 🎯 Round 1 Summary

- **Grade A**: P0 0, P1 0, P2 2 consensus-passed, P3 1. One more P2 came from codex and is manual-only.
- **Coverage:** all 7 lenses exercised; `blocks_approval: false`.
- **review_base:** the released 0.62.0 plugin stored `HEAD~1` (f2c017b9) on this zero-commit task branch. That is the bug this task fixes, reproduced live. This task's source resolved `HEAD` (62564cef), and the ref was corrected with `git update-ref` before any lens ran.
- **Process:** Pass 1 and Pass 2 were collapsed into one dispatch. There is no commit, PR title or description to redact, so the redacted and full contexts are identical.

## 🔍 Drift Findings

The result is `clean`. All 10 changed paths are inside the PLAN phase scope. No `Do not change` entry was crossed: `src/harness_maker/templates/` and `src/harness_maker/command_registry.py` are untouched.

## ✅ Consensus Findings

| id | Sev | Lens | Finding | Disposition |
|---|---|---|---|---|
| 07fb750cfd781154 | P2 | functionality | `_default_base_branch` truncated a slash base (`release/1.0` became `1.0`), so the base branch looked like a task branch | accepted, fixed in iteration 2 |
| bac5677451d25b42 | P2 | design | Task-branch classification compares against a guessed base name. An unconfigured `master` repo with a stray `main` ref would classify `master` as a task branch | accepted, carried (currently masked: no `main` ref means every merge-base candidate fails) |
| c7c823c855629ece | P3 | tests | No test used a base branch other than `main`, so a literal `"main"` comparison passed | accepted, fixed in iteration 2 |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Finding | Status |
|---|---|---|---|---|
| 200c0ebbc3821179 | P2 | codex | A tag named like the base branch makes `symbolic-ref --short` return `heads/main`, so `main` is misclassified as a task branch | PIDA accepted (reproduced). Fixed in iteration 2 |

## 🤝 Disagreements

None.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 200c0ebbc3821179 | codex | P2 | src/harness_maker/freeze.py | 83 | same-named tag makes `--short` return `heads/main` | `symbolic-ref --short` with tag `main` | false | accepted | scratch repo: `--short` = `heads/main`; `resolve_review_base` returned HEAD 310aee64, expected HEAD~1 7dbe8abc | resolved | — |

### Iteration 2 (Grade: A → A)

This round sits outside the standard selection rule. P2/P3 are not normally auto-fixed at grade A. Two of these were verified correctness defects in code this task had just written: one reproduced, one traced. Each fix was two or three lines. The DRI delegated this call because the run was non-interactive. confirm-1 then reviewed the whole span, these fixes included.

Fixes applied: 3

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P2 | Read the full `symbolic-ref HEAD` and strip it with `_branch_name`, instead of using `--short` (200c0ebb) | src/harness_maker/freeze.py | Applied · caused_by=none |
| 2 | P2 | `_default_base_branch` strips the `refs/remotes/origin/` prefix instead of using `rsplit` (07fb750c) | src/harness_maker/freeze.py | Applied · caused_by=none |
| 3 | P3 | Added `test_a_tag_named_like_the_base_branch_does_not_make_it_a_task_branch` and `test_a_non_main_base_branch_is_honoured[develop\|release/1.0]` (c7c823c8, 200c0ebb, 07fb750c) | tests/unit/test_freeze_commit.py | Applied · caused_by=none |

- **Mutants killed:** `--short` restored, `rsplit` restored, literal `"main"` comparison.
- **Remaining:** 1 (bac56774, P2, carried). New issues introduced: 0.
- **Churn:** 0.055 (max: tests/unit/test_freeze_commit.py, measured 2, excluded 0). Rereview skipped: churn 0.055 < 0.30.

## ✔️ Confirmation pass (confirm-1)

- **Span:** freeze `926ca9c6`, diffed against `62564cef`.
- **Lenses:** all 7 exercised; `blocks_approval: false`.
- **Result:** zero new consensus-passed P0/P1, so APPROVED.
- **New finding:** one P2 robustness finding from core. When the configured `worktree.base_branch` differs from the branch being reviewed, that branch is classified as a task branch (name-only classification). This is the same class as bac56774 and is carried with it.
- **Clean lenses:** security, concurrency and tests.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 4         | —   |
| 2         | A     | 3             | 1         | 0   |
| confirm-1 | A     | —             | 2         | 1 (P2) |

- **Final grade:** A
- **Iterations used:** 2 / 3
- **Exit reason:** converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/freeze.py | 384 → 387 | 37 → 37 | 3 → 3 | measured |
| tests/unit/test_freeze_commit.py | 395 → 418 | 57 → 60 | 1 → 1 | measured |

The table covers iteration 2 only.

## Final status

Status: APPROVED
human_review_needed: false
Counters: unreviewed 3 · prior-fix 0 · unattributed 0

### Carried follow-ups

- **bac56774 + confirm-1 P2:** task-branch classification is name-based (`current != base`). Two narrow configurations still collapse the scope:
  - an unconfigured `master` repo that also has a `main` ref;
  - a configured `worktree.base_branch` that is not the branch under review.
  - Options: add an `hm/` prefix or task-marker signal, or state the name-based rule in the SPEC.
- **Live dogfood note:** until the next release, the 0.62.0 plugin still stores `HEAD~1` on a zero-commit task branch. Check `refs/hm-freeze/v1/<slug>-base` against `git merge-base HEAD main` at round 1.
