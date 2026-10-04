---
type: review
task_slug: intent-layer-diet
status: APPROVED
created: 2026-10-04
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 720b6f709be4
review_base: dcbc7678113f9d08c8a1026a7607eabe36ef1da7
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-layer-diet
  computed_at: 2026-10-04T02:00:00Z
---

# REVIEW — intent-layer-diet

## 🎯 Round 1 Summary

- **Grade: A** (P0 0, P1 0 consensus-passed; P2 5, P3 2 consensus-passed; 1 codex P2 `manual-only`).
- Coverage: all 7 lenses exercised, `blocks_approval: false`.
- `human_review_needed: false` (no `manual-only`/`weak-consensus` P0/P1).
- Pass 1 ran all four dispatches. Pass 2 re-ran `code-reviewer` (core) and `test-reviewer`.
  `security-reviewer` and `concurrency-reviewer` returned zero Pass 1 findings, so Pass 2 had
  nothing to validate and was not dispatched for them (deviation from the stage text,
  recorded here).
- `review_base` resolved to `dcbc7678`, the parent of the task base `94916873`, so confirmation
  spans also include that commit (`intent/WORLD-INTENT-CLOSED-LOOP.md` close, metrics rows),
  which is not part of this task.

## 🔍 Drift Findings

`clean`. Every changed source and test path is in a PLAN phase scope. The re-homed test in
`tests/unit/test_worktree_task_lifecycle.py` (added after round 1) restores coverage this task
removed. Task artifacts (`specs/`, `work-docs/`) are not code scope.

## ✅ Consensus Findings

| id | Sev | Lens | Location | Finding | Disposition |
|---|---|---|---|---|---|
| b2c76db280432503 | P2 | consistency | `worktree.py:4891` | Comment says the fence around `git worktree add` guards trial collection, which is deleted | accepted, fixed |
| 8e8ce3c1386fcbca | P2 | consistency | `stage_spans.py:119` | `emit_event` docstring names the deleted "trial source fence" and a required-evidence caller | accepted, fixed |
| 21d0cbd1b7d6b493 | P2 | design | `stage_spans.py:117` | `fence_timeout` parameter now has a single value on every path | accepted, **not applied**: conflicts with fa8eaa46 (which pins the value through that kwarg); the reviewer marked it optional |
| 32a572ca43d27305 | P2 | tests | deleted `test_intent_trial_concurrency.py:710` | The deleted trial suite held the only test of `_copy_and_exclude_secrets` fail-closed cleanup (non-trial) | accepted, fixed: re-homed as `test_worktree_task_lifecycle.py::test_copy_secrets_removes_unignored_copy_before_the_error`; mutation-checked (removing the `unlink` fails it) |
| fa8eaa468022aec2 | P2 | tests | `test_intent_layer_diet.py:161` | Span success test did not pin `fence_timeout == 5.0` | accepted, fixed |
| 60848a39643c7fc4 | P3 | tests | `test_intent_layer_diet.py:296` | AC-007 did not detect `status_report` mutating the copy it reads | accepted, fixed: `_status_of` digests the copy around the call |
| 70f532c2663c2b21 | P3 | tests | `test_intent_layer_diet.py:229` | `test_ac005_fresh_render_matches_pins` only hashes pins; name misleads | accepted, fixed: renamed `test_ac005_snapshot_pins_not_regenerated` |

These P2/P3 fixes were applied after round 1 graded A, outside the auto-fix loop (which only
selects P0/P1). They clean up leftovers this task created and are covered by the confirmation
pass, which reviews `review_base..freeze` over the whole change.

Dropped in Pass 2: core Pass 1 finding 4 (rubric templates still mention trial). The SPEC
Non-Goals keep the ten unrendered rubrics on purpose (rule-4 on four historical SPECs). Tests
Pass 1 finding 4 (weak negative in the lifecycle test) was dropped because the byte-compare
AC-006 test is the strong oracle.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Location | Finding |
|---|---|---|---|---|
| 1ba5cde4c42d657c | P2 | codex | `test_intent_layer_diet.py:296` | Same defect as 60848a39 (raised at P3 by the tests lens; different tier, so not a consensus pair). Fixed by the same edit |

## 🤝 Disagreements

The `status_report` mutation gap: codex P2 vs tests lens P3. Kept independent (tiers are not
bridged).

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1ba5cde4c42d657c | codex | P2 | tests/unit/test_intent_layer_diet.py | 296 | AC-007 does not detect file changes in the root status_report reads | `_status_of()` runs on `tmp/fixture`, but the preservation check hashes only `FIXTURES/fixture` | false | accepted | status_report runs on the tmp copy (60-63) but line 296 hashes only `FIXTURES/<f>` | resolved | — |

## ✔️ Confirmation Pass

- **confirm-1** froze `dede1729` and reviewed `dcbc7678..dede1729`. All 7 lenses ran
  (`blocks_approval: false`). New consensus-passed P0/P1: **0**, so the outcome is
  **APPROVED**. No confirm-2 was run.
- New findings, all P2/P3. P2/P3 cannot move the grade.

| Sev | Lens | Location | Finding | Disposition |
|---|---|---|---|---|
| P2 | consistency | `docs/HOW-IT-WORKS.md:1528` | Doc said the adoption event "remains" `objective_proposed`, but no writer exists | accepted, fixed after approval |
| P2 | tests | `worktree.py` `task_refresh` fence | The deleted trial suite held the only test that refresh waits on the merge fence | accepted, fixed after approval: re-homed as `test_worktree_task_lifecycle.py::test_task_refresh_waits_for_the_merge_fence` |
| P2 | tests | `worktree.py:4893` registration fence | The deleted trial suite held the only test that `git worktree add` waits on the merge fence | accepted, fixed after approval: re-homed as `test_task_create_registration_waits_for_the_merge_fence`. The original's single "not yet registered" check raced `git worktree add` and **survived a fence-removal mutant**. It now observes a 1 s window and kills that mutant |
| P3 | design | `world.py` `new_objective` | `candidates` is now validated only, never stored | accepted, carried (public flag contract kept) |
| P3 | consistency | `tests/fixtures/intent_trial_native_*runner.py.txt` | Orphan captured runner scripts import the deleted modules | accepted, carried (historical fixtures, not executed) |

## 🧹 Post-approval edits (NOT re-reviewed)

Applied after confirm-1 approved, so no lens saw them:
- two re-homed fence tests, adapted to the target file's `_repo`/`_git` helpers, one strengthened as above;
- one sentence in `docs/HOW-IT-WORKS.md`.
- No source change. Verified: `tests/unit/test_worktree_task_lifecycle.py` 35 passed; ruff and
  format clean; the registration test fails against a fence-removal mutant; `worktree.py` was
  restored and diff-checked after each mutation.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 8 (all P2/P3) | — |
| confirm-1 | A     | 0 (observation) | 5 new P2/P3 | 5 |

Final grade: A
Iterations used: 1 / 3
Exit reason: converged
Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 3 · prior-fix 0 · unattributed 0

Telemetry correction: the terminal `review-2026-10-04.jsonl` row records
`unreviewed_fix_count: 7`. That is wrong. The 7 pre-confirmation fixes were covered by
confirm-1; the unreviewed count is the 3 post-approval edits above. The ledger is append-only,
so the row stands with this correction.

## 📏 Size & Complexity

No repair round ran, so there are no 5c measurements. Size: `src/` 8 files, +20 / −1,681
(including the deleted `intent_trial.py`, 1,472 lines).

Verify-stage follow-up (also not re-reviewed): `/hm:verify` Check 2 failed on
`mypy --strict src tests`, because execute had type-checked only `src`. Two typing-only edits in
`tests/unit/test_intent_layer_diet.py` fixed it: an unused `type: ignore` was removed and the
`_status_of` result was annotated. The CI gates then passed (ruff, format, mypy, full pytest).
