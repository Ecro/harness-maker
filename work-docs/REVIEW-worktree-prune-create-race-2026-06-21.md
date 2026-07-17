---
type: review
task_slug: worktree-prune-create-race
status: APPROVED
created: 2026-06-21
reviewers_invoked: [code-reviewer, concurrency-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: worktree-prune-create-race
  computed_at: 2026-06-21T00:00:00Z
---

# REVIEW — Worktree prune-vs-create rmtree race

k-of-3: code-reviewer + concurrency-reviewer (Claude) + Codex (Production-mandatory).

## 🎯 Round 1 Summary

- **Grade: A** (consensus-passed P0=0, P1=0). Threshold A met. **No consensus-passed P0/P1.**
- All three reviewers found ZERO P0/P1 in their own scoring; the only P1s were single-source (Codex) and refuted by another reviewer → manual-only. 4 high-value P2 fixes applied + 3 regression tests added.

## 🔍 Drift Findings

`drift_verdict: clean`. Diff = `worktree.py` + `test_worktree_prune.py` + `test_worktree_prune_race.py` + `test_worktree_drain.py` (fixture) — exactly the PLAN's stated scope.

## ✅ Consensus Findings (consensus-passed) — graded

### P2 — `.hm-creating-*` reservation absent from gitignore + finalize dirt-filter [2/3: code-reviewer + concurrency]
`worktree.py:~1732/322`. OBSERVE: `_HARNESS_ARTIFACT_PREFIXES` and the gitignore set cover `.hm-loop-`/`.hm-finalize-stash-` but NOT `.hm-creating-`. INFER: a reservation leaked by a hard kill (the 300s window) is untracked dirt — committable AND stashed-as-user-dirt by a peer's finalize (`_is_harness_artifact` doesn't forgive it). CONCLUDE: hygiene gap inconsistent with the keep-base-clean invariant + the other two `.hm-*` markers.
**→ FIXED:** added `.claude/.hm-creating-` to `_HARNESS_ARTIFACT_PREFIXES` + `_ensure_gitignore_entry(base, ".claude/.hm-creating-*")` at create time.

### P2 — residual prune-vs-add race: narrowed, not closed [2/3: concurrency P2 + Codex P1; code-reviewer refuted "fully closed"]
`worktree.py:~2036`. OBSERVE: `prune_stale` gates `git worktree prune` on `_any_fresh_reservation` AND passes `--expire`. INFER: the reservation cannot protect peer-A once peer-B has already passed its `_any_fresh_reservation()==False` check (A reserves AFTER B observed its absence); only `--expire` saves a COMPLETE entry, and the half-written-`gitdir` instant is exposed. CONCLUDE: structurally unclosable without a lock (the design explicitly rejects locks) — narrowed, not closed.
**Severity resolution:** concurrency-reviewer (domain owner) = P2 (impact is a *recoverable create-retry*, NOT work loss; "acceptable, inherent, documented"); Codex = P1. Resolved to **P2** — the impact analysis (rare `git worktree add` RuntimeError → create retries; no data destroyed) places it below the work-loss bar.
**→ ACCEPTED + PINNED (not code-fixed):** a retry was considered and rejected (risk of masking unrelated `git worktree add` failures for a practically-closed P2 — the concurrent test passes 3/3 without it). The two belts (`_any_fresh_reservation` gate + `--expire`) are pinned by `test_expire_keeps_recent_prunable_admin_entry_but_reaps_aged` + `test_concurrent_create_is_never_reaped_mid_flight`, so a future refactor can't silently drop one. Documented accepted in the PLAN.

## ⚠️ Weak Consensus

### P2/P3 — `_has_fresh_reservation` hidden mutation in a boolean predicate [concurrency P2 (TOCTOU) + code-reviewer P3 (smell)]
`worktree.py:~1770`. OBSERVE: the predicate `unlink()`d an aged reservation. INFER (concurrency): stat→unlink can delete a fresh reservation a name-colliding peer just rewrote (name reuse = negligible uuid+timestamp collision). CONCLUDE: real-but-low-probability TOCTOU + a maintainability smell.
**→ FIXED:** `_has_fresh_reservation` is now a PURE predicate; reaping moved to an explicit `_reap_aged_reservations(base)` step in `prune_stale` (only reaps `< cutoff` entries — never a live create's).

## 📝 Manual-Only Findings (single-source — NOT auto-applied)

- **P2 (Codex) `worktree.py:~1691` — dead-stash markers immortal.** A marker preserved by a DEAD stash ref (object gone OR content-in-HEAD) deadlocks: marker kept ⇒ ref-drain skips it ⇒ marker kept forever. *Single-source but a real correctness bug* — **FIXED** (`_marker_has_pending_stash` now gates on the same liveness test as the stash-ref drain: `_stash_object_exists AND NOT _stash_content_in_head`). Regression test `test_orphan_marker_with_DEAD_stash_is_still_pruned`.
- **P1 (Codex) `worktree.py:~330` — sibling worktree unprotected.** `create()` writes the reservation only for the PRIMARY base; a concurrent drain/create IN A SIBLING REPO could prune/scan the sibling's in-flight `.worktrees/<name>-<slug>` with no reservation. code-reviewer REFUTED ("no sibling prune runs at create") — but a sibling-repo create / `drain` does run `prune_stale` on the sibling base. *Manual-only (1 refuted) → does not lower the grade.* **DEFERRED follow-up:** the PLAN scoped to the primary leaf; extending the reservation to each sibling base is a multi-repo follow-up (lower frequency).
- **P3 `worktree.py:~1799` — `.git`-less partial dirs leak forever** (Codex + code-reviewer + concurrency, all P3). Accepted ADR-001 operator-path limitation (`prune-branches --force`).
- **P3 `worktree.py:~1799` — `.git` check uses weak `.exists()`** (code-reviewer). Preserve-direction (a planted `.git` only PREVENTS reaping) → not a security regression; noted.
- **P3 `worktree.py:~69` — 300s mtime/clock-skew/>300s-create** (concurrency). Single-host CLI → no cross-host skew; only a >300s checkout re-exposes the dir. Low risk, conscious bound.

## 🤝 Disagreements

- **residual race @2036:** concurrency P2 ("acceptable, inherent") vs Codex P1 ("concerning") vs code-reviewer ("fully closed, not a finding"). Resolved: it IS a real residual (2/3) but P2 by impact (recoverable retry, not work loss); accepted + test-pinned.
- **sibling unprotected @330:** Codex P1 ("real gap") vs code-reviewer ("not a finding"). Resolved manual-only; deferred follow-up (Codex's drain/sibling-create path defeats code-reviewer's "no sibling prune" premise).

## Auto-Fix Loop

### Iteration 2 (Grade: A → A; fixes are correctness/hygiene improvements on an already-passing diff)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P2 (Codex, correctness) | dead-stash marker immortality → liveness gate | `_marker_has_pending_stash` | Applied |
| 2 | P2 (concurrency) | predicate-mutation TOCTOU → pure predicate + explicit reaper | `_has_fresh_reservation`/`_reap_aged_reservations` | Applied |
| 3 | P2 (consensus) | `.hm-creating-` gitignore + dirt-filter | `_HARNESS_ARTIFACT_PREFIXES` + create-time ensure | Applied |
| 4 | P2 (consensus) | residual race | — | Accepted + test-pinned (retry rejected: risk > benefit) |

Regression tests added: `test_orphan_marker_with_DEAD_stash_is_still_pruned`, `test_prune_stale_reaps_aged_leaked_reservation`, `test_prune_stale_keeps_fresh_reservation`.
Verify: `ruff` + `mypy --strict` clean; full worktree prune/race/drain suite GREEN.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 0 consensus P0/P1 | — |
| 2         | A     | 3 (+1 accepted) | 0 | 0 |

Final grade: A (no consensus-passed P0/P1; 3 P2 correctness/hygiene fixes + 1 accepted residual applied as hardening)
Iterations used: 2 / 3
Status: APPROVED
human_review_needed: false

## ⚠️ Carry-forward for follow-up (not blocking)
- **Multi-repo sibling reservation gap** (Codex P1, manual-only): extend the pre-create reservation to each sibling base. Lower-frequency; the PLAN scoped to the primary leaf.
