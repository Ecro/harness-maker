---
type: review
task_slug: multisession-worktree-concurrency
status: APPROVED
created: 2026-06-21
scope: task-land wrapup wiring (Phase-4 gap) + task_land cross-session contamination fix
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: k-of-3
grade: A
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multisession-worktree-concurrency
  computed_at: 2026-06-21
codex_status: invoked
---

# REVIEW — task-land wrapup wiring + task_land contamination fix

Two review rounds (wiring, then the contamination fix it surfaced). The Codex
heterogeneous voter caught **two real P1s both Claude reviewers missed** — the same
pattern that has repeatedly earned its keep this feature.

## What shipped
1. **wrapup Step 7.7** (`templates/stages/wrapup.md.j2`, flag-on + `hm/*`-branch only):
   wraps `task-land <slug> <base>` to squash the task branch onto base HEAD + teardown
   (the Phase-4 wiring gap). Loop's `execute-<uuid>` worktree skips it (loop-close
   finalize owns that land) → no double-land. Byte-neutral flag-off (proven: only the
   intended gate0_pass prose + content_hash differ).
2. **task_land contamination fix** (`worktree.py`): squash now commits ONLY
   `_squash_path_set` (`git commit -- *touched`), not the whole index.

## P1 findings — all FIXED
- **Codex P1 (round 1, empirically confirmed)** — `git merge --squash` + `git commit`
  (no pathspec) committed the WHOLE index, sweeping a concurrent session's pre-staged
  `.claude/`/`work-docs/` base churn (excluded by the dirty-base guard, so no abort)
  into the task's squash commit (count:3 contamination class). **Fix**: scoped commit
  to `touched`. Regression: `test_task_land_does_not_sweep_concurrent_staged_base_churn`.
- **Codex P1 (round 2)** — `_squash_path_set` used `git diff --name-only` WITHOUT
  `--no-renames`; under a user's `diff.renames=true` a rename reports only the
  destination path → the scoped commit would miss the staged deletion of the old path
  (renamed-away file lingers in HEAD + staged-deletion leak). **Fix**: `--no-renames`
  (rename = two entries). Regression: `test_task_land_records_rename_under_diff_renames_config`.

## P2 findings — FIXED
- **code P2** — empty `touched` (merge-base failure / unrelated histories, where the
  `already` gate and `_squash_path_set` fail independently) would let `merge --squash`
  stage content then skip the commit → orphan staging. **Fix**: detect empty `touched`
  BEFORE merging → abort rc1 (preserve branch+worktree; never reset the base index a
  concurrent session may have staged into).
- **code P2** — regression test now also asserts the concurrent file stays STAGED.
- **security/Codex P2** — Step 7.7 said "onto `main`"; `task_land` squashes onto base
  HEAD (branch-agnostic). **Fixed** wording (wrapup + gate0_pass).
- **Codex P2** — teardown deletes `<WT>`; Step 7.7 outcome now instructs an explicit
  `cd <BASE>` for later steps.
- **code P2 (round 1)** — render tests tightened to pin the exact `worktree task-land
  <SLUG> <BASE>` invocation + heading (not an incidental `task-*` match).

## 🟢 Cleared (multi-reviewer)
- No double-land (namespace split `hm/*` vs `execute-*`; finalize never lands).
- Teardown ordering benign (Gate-0 receipt no-ops after teardown; loop uses
  `execute-<uuid>` so Step 7.7 skips → `<WT>` intact for the loop's receipt).
- rc1 preserves branch+worktree; Step 7.7 STOPs (no push) on rc1.
- `touched` computed AFTER `_capture_pending_in_worktree` → captured work included.
- Dogfooding unaffected (this repo's harness flag is absent → falsy → legacy render).

## 🟡 Acknowledged follow-up (not blocking; P2, pre-existing)
- **execute Step 5 finalize prose** renders unchanged flag-on, still says "merge back
  + cleanup worktree"; the no-teardown behavior rests on the `_cli_finalize` runtime
  guard. Prose-vs-runtime divergence (latent footgun if the guard regresses) —
  recommend a flag-on clarifying note in a follow-up (separate template, avoids
  widening this commit's snapshot churn).
- The other deferred data-loss item (stage-only landed-marker spec-conflict, from the
  Phase-7 review) remains for its dedicated plan.

## Verdict
**APPROVED (grade A).** All P0/P1 fixed + regression-tested; data-loss-core squash is
now index-scoped + rename-safe. Byte-neutral flag-off; full deterministic suite +
mypy/ruff green.
