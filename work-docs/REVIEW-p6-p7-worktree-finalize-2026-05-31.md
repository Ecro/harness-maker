---
type: review
task_slug: p6-p7-worktree-finalize
status: APPROVED
created: 2026-05-31
reviewers_invoked: [code-reviewer, concurrency-reviewer]
consensus_method: cross-check
phase: P1
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: p6-p7-worktree-finalize
  computed_at: 2026-05-31T14:10:32Z
---

# REVIEW — p6-p7-worktree-finalize Phase 1 (orphan-branch leak fix)

Diff under review: staged P1 changes — `src/harness_maker/worktree.py` (+orphan-branch
sweep in `prune_stale`) and `tests/unit/test_worktree.py` (+3 tests). The P3-count-drift
fix was a separate committed change (`6ea501c`) and is NOT part of this review.

## 🎯 Round 1 Summary

- **Grade: A** (consensus-passed P0 = 0, P1 = 0). Threshold A met → no auto-fix loop fired.
- **No P0/P1 from either reviewer.** The concurrency reviewer explicitly **confirmed
  ADR-002's cross-session-safety claim** and found no data-loss path; the safety-critical
  preserve-bias of `_branch_content_in_head` is sound across every traced edge case
  (empty diff, path-deleted-on-branch, diverged HEAD, multiple merge-bases, detached/current
  branch — all fail toward preserve or toward a refused delete).
- **3 fixes applied during review** (C1, C2, C3 — all safe, non-defense-touching, ADR-aligned).
- **1 finding deferred** (N1 — its primary fix touches Layer-4, which ADR-001 forbids).
- **1 finding rejected with rationale** (N2 — empty orphan branch has nothing to preserve).

## 🔍 Drift Findings

**None.** The staged diff (`worktree.py`, `test_worktree.py`) is exactly within PLAN P1
scope (orphan-branch fix + its tests). No scope drift, no incomplete phase. No SPEC →
no scenario-miss analysis. `drift_verdict.result: clean`.

## ✅ Consensus Findings

**None.** The two P2 clusters from the two reviewers sit in the same sweep block
(lines ~1509–1521) but their CONCLUDE clauses diverge entirely — report-integrity (C1)
vs contract-wording (C2) vs fence-race (N1). Per the consensus filter (Step 4b), surface
proximity with divergent reasoning = distinct defects, not the same issue. Every finding
is therefore single-source → manual-only. Zero strong-consensus findings.

## ⚠️ Weak Consensus

**None.**

## 📝 Manual-Only Findings

All findings below are single-source. Per policy they are not auto-applied by the grade
loop; as stage orchestrator I applied the safe, ADR-aligned subset and recorded the rest.

### P2 — C1 (code-reviewer) — false-removal report — **APPLIED**
- **OBSERVE:** `removed_branches.append(branch)` ran *before* a `contextlib.suppress(RuntimeError)`-wrapped `git branch -D`.
- **INFER:** if the delete silently fails (branch still checked out in a registration the dir-check missed), the report claims a removal that did not happen.
- **CONCLUDE:** forensics-integrity defect in defense-core code; not data loss (branch survives), but the PruneReport lies.
- **Fix applied:** append to `removed_branches` only after a confirmed delete; a failed `git branch -D` now routes to `preserved_branches` + `warnings` with the error. `dry_run` appends unconditionally (no delete attempted).

### P2 — C2 (code-reviewer) — live-skip diverged from ADR-002 — **APPLIED**
- **OBSERVE:** live-skip used `dir.exists()`; ADR-002 specifies `_registered_worktree_paths` (matching `_scan_dangling_worktrees`).
- **INFER:** `git worktree prune` does not always reap a dir-missing registration (locks / grace window), so a registered-but-dir-gone worktree's branch was not skipped.
- **CONCLUDE:** contract-wording drift; preserve-bias still held, but the implementation did not honor its own ADR.
- **Fix applied:** compute `registered = _registered_worktree_paths(base)` once; skip when `wt_dir in registered or wt_dir.exists()` (registration primary, dir as belt-and-suspenders). Strictly more preserve-biased; all 3 P1 tests stay GREEN.

### P3 — C3 (code-reviewer) — S^3 parity comment — **APPLIED**
- Branches have no untracked-tree (`S^3`) analogue (untracked work is captured into the `wip(execute)` commit before cleanup), so the omission vs `_stash_content_in_head` is correct. Added a docstring note so a future maintainer does not "fix" the non-bug.

### P3 — C4 (code-reviewer) — single merge-base — **NO FIX (documented safe)**
- `git merge-base branch HEAD` returns one base when several exist; diffing against it lists a *superset* of changed paths → stricter → more-preserve. Detached/current-branch only makes `git branch -D` refuse. Every corner biases toward preserve. No action.

### P2 — N1 (concurrency-reviewer) — unfenced sweep vs Layer-5 scope-guard re-run — **DEFERRED (ADR-001)**
- **OBSERVE:** the sweep takes no lock; `_verify_scope_subset` hard-depends on `wt_branch` existing.
- **INFER:** narrow window — a finalize that failed partway is *re-run*, work landed in HEAD between, and a concurrent `create`→`prune_stale` sweeps the now-in-HEAD branch → the re-run's scope-guard merge-base call raises, falls through to an unguarded `git diff main...wt_branch` that also raises and is swallowed at the `_cli_finalize` level.
- **CONCLUDE:** Layer-5 scope-guard silently degrades to a no-op for that one re-run turn. Not data loss (reviewer concurs).
- **Disposition — DEFERRED:** the reviewer's primary fix wraps the sweep in `_acquire_merge_fence` — the **Layer-4 fence primary**. ADR-001 **explicitly scopes defense-layer-touching changes OUT** ("the WSL2 flock probe touches Layer-4's `_flock_lock` primary … NOT in scope … belong in a future deliberate Layer-4 hardening pass"). The lighter "skip a branch with a live `.hm-finalize-stash-*` ref / loop marker" variant is also defense-adjacent and narrow. Both belong in the deliberate Layer-4 hardening pass, not this de-risked PLAN. **Recorded as a follow-up; not blocking (grade A, narrow non-data-loss window).**

### P3 — N2 (concurrency-reviewer) — empty-diff returns True — **REJECTED (rationale)**
- The reviewer suggested returning False on an empty changed-set (biased-to-preserve). **Rejected:** an orphan branch with zero commits past its merge-base has *no work to preserve* — deleting it is correct and is precisely the leak the sweep exists to clean. Returning False would re-introduce the leak for empty branches. The real protection against sweeping a *live, freshly-created* branch is the registration/dir live-skip (strengthened by C2), not the content predicate. `git worktree add -b` is atomic, so there is no window where the branch exists with its dir/registration absent.

## 🤝 Disagreements

**None.** The two reviewers surfaced complementary, non-conflicting issues (report integrity,
contract wording, fence interaction). No severity or reasoning conflict to resolve.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 3 (C1,C2,C3)  | 1 deferred (N1), 1 rejected (N2), 1 no-fix (C4) | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

> **Deferred follow-up (not blocking):** N1 — fence/marker-guard the orphan-branch sweep
> against a concurrent finalize re-run. Belongs in the deliberate Layer-4 hardening pass
> (per ADR-001's explicit out-of-scope decision), tracked for a future PLAN.

## Verification after applied fixes

- `uv run pytest tests/unit/test_worktree.py` → 42 passed (incl. the 3 P1 tests).
- `uv run ruff check src/harness_maker/worktree.py` → clean.
- `uv run mypy --strict src/harness_maker/worktree.py` → clean.
- Fixes re-staged; working tree has no unstaged changes.
