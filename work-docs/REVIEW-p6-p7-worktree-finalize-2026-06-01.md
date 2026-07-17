---
type: review
task_slug: p6-p7-worktree-finalize
status: APPROVED
created: 2026-06-01
reviewers_invoked: [code-reviewer, concurrency-reviewer]
consensus_method: cross-check
phase: P2
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: p6-p7-worktree-finalize
  computed_at: 2026-06-01T15:06:49Z
---

# REVIEW — p6-p7-worktree-finalize Phase 2 (merge-fence boundary widening)

Diff under review: staged P2 changes — `src/harness_maker/worktree.py` (fence wraps
`{stash, staged_before snapshot, merge}`; new `_snapshot_staged_paths`),
`tests/unit/test_worktree.py` (+4 P2 tests), `tests/unit/test_worktree_merge_fence.py`
(+T5 fence-gated-stash). P1 (commit `2eb6abe`) and the P3-drift/codex commits are
NOT under review here.

## 🎯 Round 1 Summary

- **Grade: A** (consensus-passed P0 = 0, P1 = 0). Threshold A met → no auto-fix loop.
- The restructure **honors the ADR-003 contract**: fence wraps exactly
  `{stash (2143), staged_before snapshot (2144), merge (2145)}`, snapshot strictly
  after the stash; handed_off / ref-write / cleanup / both pop paths pinned
  OUTSIDE the fence; `_capture_pending` worktree-side and outside; fence releases
  on every exit incl. the stash-failure path. Both reviewers independently
  verified the 5 finalize state-paths (capture-fail, stash-fail, merge-fail-after-stash,
  stage-only handoff, success-mode pop) route correctly into the rollback `finally`.
- **No fix applied.** Every finding is single-source (manual-only); the lone P1
  is ADR-overruled; the rest are pre-existing (`out_of_diff`) and out of P2's
  fence-widening scope (deferred per ADR-001's minimal-defense-core-change stance).

## 🔍 Drift Findings

**None.** Staged files are all within PLAN P2 scope (`worktree.py` `_cli_finalize`
fence + `test_worktree*.py`). Note: the PLAN testing-strategy named
`test_worktree_parallel_session.py` for P2's parallel-serialization assertion;
I placed it (deterministically, RED-on-pre-move) in `test_worktree_merge_fence.py`
instead — still in-scope (`test_worktree*.py`), and the Phase A.5 test-reviewer
approved the placement. Not a scope violation. `drift_verdict.result: clean`.

## ✅ Consensus Findings

**None.** The two reviewers' P2-cluster findings target different concerns (rollback
reset-guard, orphan stash, pop-race) at different lines — no surface+reasoning
consensus. The one same-line pair (CR3/CN1 at 2142) splits across severity tiers
(P3 vs P1) → not consensus candidates per Step 4a. Zero strong-consensus findings.

## ⚠️ Weak Consensus

**None** in the strict sense. But CR3 and CN1 **describe the same mechanism**
(the 300s `git stash push -u` is now inside the 60s-acquire fence) with divergent
severity — surfaced under Disagreements below.

## 📝 Manual-Only Findings

### P1 — CN1 (concurrency-reviewer) — fence timeout < critical-section hold — **ADR-OVERRULED, not fixed**
- **OBSERVE:** `_acquire_merge_fence(base, timeout=60.0)` (2142) now wraps `_stash_base_dirty`, whose own `git stash push -u` timeout is `_GIT_TIMEOUT_LONG=300`. A first finalize on a large untracked tree can legitimately hold the fence ~300s+; a second parallel finalize waits with a 60s acquire budget → `TimeoutError` → `wt_rc=1` → worktree preserved.
- **CONCLUDE (reviewer):** timeout-amplification regression — the second finalize spuriously fails on exactly the large-untracked-tree case.
- **Disposition — DEFERRED (ADR-003-accepted risk):** ADR-003 Consequences state verbatim: *"the 60s budget is retained, to be raised only if a real run trips TimeoutError."* The reviewer lacked this context. Raising the timeout (its suggested fix) contradicts the locked decision. Outcome is a *graceful degrade* (preserve + re-run), not data loss. **Recorded as a watch item:** if a real parallel-finalize-on-dirty-base run ever trips the 60s timeout, the 1-line fix is `timeout=_GIT_TIMEOUT_LONG + _GIT_TIMEOUT` (~360s). Until then, ADR-003 holds.

### P2 — CR1 (code-reviewer) — success-mode merge-fail: stash-apply over un-reset dirty index — **`out_of_diff`, reachability ↑, recommended follow-up**
- **OBSERVE:** the rollback `finally` runs `git reset --hard HEAD` only `if not auto_commit`. In success mode (`auto_commit=True`), a `git merge --squash` conflict leaves partial conflict content staged with no commit; the reset is skipped and `_restore_base_dirty` (stash apply) runs over the dirty index.
- **CONCLUDE:** stash-apply over a conflicted index can fail/collide. The `finally` guard should key on `wt_rc != 0`, not `not auto_commit`.
- **Disposition:** the `finally` reset-guard **predates P2** (out_of_diff) and is in the rollback path, not the fence — out of P2's stated scope, and ADR-001 wants minimal defense-core change. **However, THIS diff increases its reachability:** pre-P2, a success-mode merge conflict propagated as an *uncaught* exception (function crashed); now it's caught → `wt_rc=1` → reaches this buggy rollback cleanly. Net behavior is better (graceful vs crash) but the latent reset-skip is now reliably hit. **Recommended near-term follow-up** (change `if not auto_commit:` → `if wt_rc != 0:` before the pop). Not folded into P2.

### P2 — CR2 (code-reviewer) — orphan stash if `_stash_base_dirty` raises post-`push` — **`out_of_diff` follow-up**
- If `git stash push` succeeds but the SHA-resolution scan finds no match, `_stash_base_dirty` raises **without dropping the pushed stash**; the caller's `stash_ref` stays `None` → the `finally` pops nothing → the user's base dirt is stranded in a leaked stash. Pre-existing in `_stash_base_dirty` (identical exposure in the old early-return path). Fix belongs in the helper (drop-on-no-match before raising). Not in P2 scope.

### P2 — CN2 (concurrency-reviewer) — base stash pop outside the fence races shared stash stack — **`out_of_diff`**
- Both pops (`_restore_base_dirty`: success-mode 2238 + rollback `finally` 2252) run OUTSIDE the fence on the shared base index/stash stack. Two parallel finalizes can collide on `<common-dir>/index.lock` → classified pop-failure + preserved worktree (NOT data loss; SHA-targeted apply/drop prevents wrong-entry destruction). **Pre-existing** — the diff only moved the *stash* into the fence; pops were always outside. Optional symmetry improvement: re-acquire the fence around the pops. Not a regression.

### P3 — CR3 (code-reviewer) — same as CN1, framed as accepted latency — see Disagreements.

## 🤝 Disagreements

**CR3 (P3) vs CN1 (P1) — the 300s-stash-inside-60s-fence mechanism.** Both reviewers
OBSERVE the identical fact (stash now inside the fence; fence acquire budget 60s).
They diverge on severity: code-reviewer calls it P3 (graceful degrade, "document,
no code change"); concurrency-reviewer calls it P1 (timeout-amplification regression,
"raise the timeout"). **Resolution:** ADR-003 already adjudicated this exact trade-off
and chose to keep 60s and accept the rare-case degrade — so the effective severity is
P3/accepted, and the P1 fix is overruled. Surfaced here (not silently averaged) because
it's the one substantive reviewer disagreement and the user may wish to revisit ADR-003's
"raise only if a real run trips" stance.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 0             | 1 ADR-deferred (CN1/CR3), 3 out-of-diff follow-ups (CR1, CR2, CN2) | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

> **Recommended follow-up (highest value, not blocking P2):** CR1 — change the
> rollback `finally` reset guard from `if not auto_commit:` to `if wt_rc != 0:` so a
> failed success-mode squash-merge resets the dirty index before the stash-apply.
> The diff raised this latent bug's reachability. Belongs in its own small change
> (touches the defense-core rollback; out of P2's fence scope).
> CR2 (orphan-stash-on-SHA-failure) and CN2 (unfenced-pop race) are lower-priority
> pre-existing follow-ups. CN1 stays an ADR-003 watch item.

## Codex second-opinion note

This is the first review since `codex_second_opinion.enabled: true`. code-reviewer
(allow-listed for codex) did NOT surface a `codex_status` in its output — consistent
with `codex login` not being completed → `warn-and-proceed` silent skip. The review
completed normally; the `CODEX_PERMISSION_PROBE.md` runtime confirmation remains TBD.
