---
type: plan
task_slug: p6-p7-worktree-finalize
status: complete
created: 2026-05-31
tags: [harness-maker, plan, worktree, defense-core, orphan-branch, merge-fence]
interview_rounds: 1
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "De-risked: fix orphan-branch leak + merge-fence boundary + safe polish; leave finalize/L3 intact"
---

# PLAN — Worktree finalize de-risked bug-fixes (supersedes parent P6/P7)

## 🎯 Executive Summary

**What:** Fix the two *confirmed* worktree bugs — the **orphan branch leak** and the **merge-fence boundary gap** — plus two genuinely-safe polish items, while **leaving the shipped 5-layer cross-session-contamination defense structurally intact**.

**Why:** This de-risks the parent `PLAN-latency-worktree-step-preview` P6/P7. That plan's ADR-001 (asymmetric finalize restructure) + ADR-002 (Layer-3 removal) **modify a shipped, tested 3rd-incident defense** (`[wiki:pattern] cross-session-worktree-defense-5-layer`: "all 5 layers must regress to re-open data loss"; `test_worktree_parallel_session.py` GREEN). Those changes target mostly-dormant code for a ~450-line reduction — too much incident-4 risk for too little gain. The actual bugs are separable and fixable without touching the finalize structure or removing a defense layer.

**Key decisions:** de-risk to confirmed-bugs-only (ADR-001, supersedes parent ADR-001/002); orphan-branch deletion at `worktree create` via a content-gate (ADR-002); merge-fence boundary widening that strengthens (not restructures) Layer-4 (ADR-003).

**Estimated impact:** orphan-branch leak closed (unbounded ref accumulation stopped); parallel-finalize stash race closed; ~no behavioral change to the common single-session path. Defense structure + Layer-3 untouched.

## 📚 Prior Work

- Parent `[[PLAN-latency-worktree-step-preview]]` — P6 execute attempt (reverted) surfaced that the orphan-branch fix can't go at finalize-cleanup; this PLAN consolidates the worktree work de-risked.
- `[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3) — the 3rd-incident bug class; its documented prevention is `git branch -D execute-*` **at create** (prune_stale), which this PLAN follows.
- `[wiki:pattern] cross-session-worktree-defense-5-layer` — the shipped defense; Layer-4 merge-fence (`_acquire_merge_fence`, `_flock_lock`), Layer-3 dirname-UUID, the scope-guard (`_verify_scope_subset` using `staged_before`).
- `[wiki:gotcha] orphan-stash-registration-drain-manual` — the ref-drain content-verified-consent pattern that ADR-002's content-gate mirrors.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | → ADR |
|---|---|---|---|---|---|---|
| 1 | 1 | Scope | Scope | full parent-ADR restructure vs de-risk to confirmed bugs | **De-risk: confirmed bugs only** (leave finalize structure + L3 intact) | ADR-001 |
| 2 | 1 | Orphan-branch location | Architecture | finalize-cleanup vs prune_stale-at-create vs both | **prune_stale-at-create, content-gated** | ADR-002 |

Validator pass (NEEDS_REVISION, 2 critical + 4 warnings) resolutions folded in — see `## 🔍 Plan Validation`.

## 📐 Architecture Decision Records

### ADR-001: De-risk — fix confirmed bugs + safe polish only; leave the shipped defense intact
**Status:** Accepted (2026-05-31, via /hm:plan interview). **Supersedes** parent PLAN-latency-worktree-step-preview ADR-001 (asymmetric finalize restructure) + ADR-002 (Layer-3 removal).
**Context:** The parent ADRs restructure a shipped, tested 5-layer cross-session-contamination defense (3rd-incident closure) and remove Layer-3 — targeting mostly-dormant code.
**Decision:** This PLAN fixes ONLY the confirmed bugs (orphan-branch leak, merge-fence boundary) + two non-defense polish items. The finalize stash/deferred-pop structure and Layer-3 are left untouched.
**Consequences:**
- ✅ Lowest incident-4 risk — no defense layer removed, no finalize restructure.
- ⚠️ The ~450-line reduction the parent planned is forgone (the dormant deferred-pop apparatus stays).
- ⚠️ Layer-3's "wiring-gap #14" (wrapup doesn't set `HM_OWNED_SESSION_UUIDS` → L3 falls back to marker-exists) remains a separate follow-up, NOT addressed here.
- ⚠️ **Defense-adjacent polish dropped:** the WSL2 flock positive-exclusion probe (touches Layer-4's `_flock_lock` primary) and the `_stash_content_in_head` hot-path move (touches ADR-005 ref-drain timing) are NOT in scope — they contradict "leave the defense intact" and belong in a future deliberate Layer-4 hardening pass.
**Rejected alternatives:** full parent-ADR scope (incident-4 risk for dormant-code gain); middle/L3-only (still touches the defense unnecessarily).
**Source:** Interview #1.

### ADR-002: Orphan-branch deletion in prune_stale at create, content-gated
**Status:** Accepted (2026-05-31, via /hm:plan interview).
**Context:** `cleanup()`/`prune_stale()` never run `git branch -D`, so every finalized worktree leaks its `-b <name>` branch + WIP commit forever (grep-confirmed: no `git branch -D` in the module). The fix CANNOT go at finalize-cleanup: `cleanup(on_success=True)` is called by stage-only finalize too (worktree.py:2129), and execute's stage-only path leaves the work staged-not-committed with the `wip(execute)` commit on the branch as the documented stash-conflict recovery net — deleting it there breaks recovery (P6 finding).
**Decision:** In `prune_stale` (runs at every `worktree create`), delete branches matching the worktree prefixes (`execute-`/`plan-`/`phase-`/`autoloop-`) whose worktree dir is GONE (not in `_registered_worktree_paths`), **gated by a new `_branch_content_in_head(repo, branch)`** that mirrors `_stash_content_in_head` (path-keyed blob equality — NOT `git branch --merged`, because a squash-merged branch tip is not a HEAD ancestor). Delete iff content in HEAD; else preserve+warn (same policy as the existing stash-ref drain).
**Consequences:**
- ✅ Closes the orphan-branch leak using the memory-documented prevention; mirrors the existing ref-drain (consistent + content-verified).
- ✅ **Cross-session safe:** the in-HEAD requirement means an in-flight session's branch is NOT swept — stage-only work isn't in HEAD until that session's wrapup commits, so a concurrent `create`'s prune preserves it (resolves the scope-guard-branch-dependency race; the scope-guard at worktree.py:897 still has its branch).
- ✅ Current session's branch is never swept (its worktree dir is still registered).
- ⚠️ The gate is **path-keyed blob equality, biased toward preserve** — any mismatch (reformatted-at-commit blob, moved file) preserves+warns rather than deletes. Safe direction (never deletes unsaved work); cost is occasional stale-orphan retention until content fully matches.
**Rejected alternatives:** delete at finalize-cleanup (breaks stage-only WIP recovery net); delete in post-commit-pop only (misses non-wrapup sessions); `git branch --merged` (misses squash-merged branches).
**Source:** Interview #2; P6 finding.

### ADR-003: Merge-fence boundary widening (strengthen Layer-4, not restructure)
**Status:** Accepted (2026-05-31, via /hm:plan interview).
**Context:** `_stash_base_dirty` (worktree.py:1998) + the `staged_before` snapshot (2033) run OUTSIDE `_acquire_merge_fence`, which wraps only `merge()` (2041). Two parallel finalizes can `_stash_base_dirty` the same base concurrently — a real race the fence was meant to prevent.
**Decision:** Widen the fence to wrap **exactly** `{_stash_base_dirty call, staged_before snapshot, merge()}` — no more. Its **lower boundary is pinned**: `handed_off` computation, `_write_stash_ref_file`, `cleanup()`, and BOTH stash-pop paths (success-mode pop and the rollback `finally` pop) stay strictly OUTSIDE/after the fence. `stash_ref` and `staged_before` are assigned inside the `with` but read after it (Python `with` introduces no scope, so the outer reads at worktree.py:2007/2073/2122/2132 need no rebinding). This strengthens the shipped Layer-4 (closes the stash-race window); it does NOT restructure the finalize flow or enclose cleanup/ref-write/pop under the lock.
**Consequences:**
- ✅ Closes the parallel-finalize stash race.
- ⚠️ **Widened fence hold-time:** the critical section now includes `_stash_base_dirty` (a `git stash push -u` that can be slow on a large untracked tree), increasing hold time against the fixed 60s timeout. Accepted: correctness > speed for the rare dirty-base + parallel-finalize case; the 60s budget is retained, to be raised only if a real run trips TimeoutError. The fence is released on every exit path (context-manager `finally`), incl. the stash-failure `return 1`.
- ⚠️ **Load-bearing ordering invariant:** the `staged_before` snapshot MUST stay strictly AFTER `_stash_base_dirty` (it reads the post-stash index, which the scope-guard's `--allow-dirty-base` exemption depends on). A future refactor must not reorder them.
**Rejected alternatives:** move only the stash (leaves staged_before reading pre-stash state — breaks the scope-guard exemption); leave the gap (the confirmed race).
**Source:** Interview #1 (scope includes the fence bug); validator critical #1/#2.

## 🏗️ Technical Design

**Current state:** `worktree.py` (2433 lines). Orphan branches leak (no `git branch -D`); the merge fence has a boundary gap (stash outside). The 5-layer defense + Layer-3 are shipped and tested.

**Affected components:** `worktree.py` only — `prune_stale` + new `_branch_content_in_head` (P1); `_cli_finalize` fence block (P2); `_ensure_harness_gitignore` + the triple porcelain-parse sites (P3). Tests: `tests/unit/test_worktree*.py`, `tests/integration/test_worktree_parallel_session.py`.

**Design decisions:** all trace to ADR-001/002/003.

**Sequencing:** serial-worktree (P1 → P2 → P3) — all edit `worktree.py` (different functions; serial for clean per-phase commits). No template/snapshot involvement (pure Python). Runs WITH worktree isolation; finalize uses the pinned plugin-cache `0.28.2`, so edits to the repo's worktree.py don't affect this stage's own create/finalize (bootstrapping-safe).

## 📝 Implementation Plan

### Phase 1 — Orphan-branch leak fix (prune_stale, content-gated)
- **Status: DONE** (2026-05-31 — execute → review (grade A) → wrapup). All named exit criteria GREEN incl. the cross-session integration assertion (`test_create_time_prune_preserves_inflight_finalize_branch`). Review applied C1/C2/C3 (report-integrity + registration-based live-skip + S^3 parity note); N1 (fence-guard the sweep) DEFERRED to a future Layer-4 hardening pass per ADR-001 (out-of-scope).
- `depends_on`: `[]`
- `parallel_group`: `serial-worktree`
- `merge_hazards`: `worktree.py` `prune_stale` + the existing ref-drain block + `_scan_dangling_worktrees`/`_registered_worktree_paths`; **the scope-guard `_verify_scope_subset` (worktree.py:897) depends on `<wt_branch>` existence** — the content-gate prevents sweeping a live session's branch, but record the dependency; `tests/unit/test_worktree*.py`; `tests/integration/test_worktree_parallel_session.py`.
- Scope (in): add `_branch_content_in_head(repo, branch)` (mirror `_stash_content_in_head` — path-keyed blob equality); in `prune_stale`, sweep prefix-matched branches whose worktree dir is gone, gated by `_branch_content_in_head` (delete iff in HEAD; else preserve+warn). (out): finalize-cleanup branch deletion; `git branch --merged`.
- Exit (NAMED tests, not just "existing GREEN"):
  - `test_prune_sweeps_squash_merged_orphan_branch` — a branch with a `wip(execute)` commit that was squash-merged (tip NOT a HEAD ancestor, but all tip blobs ARE in HEAD), worktree dir gone → branch **swept**.
  - `test_prune_preserves_orphan_with_unmerged_content` — same setup but one tip blob differs from HEAD (e.g. reformatted) → branch **preserved + warned**.
  - `test_prune_does_not_sweep_live_worktree_branch` — current session's branch (worktree dir present) → untouched.
  - `INTEGRATION test_worktree_parallel_session.py` + a NEW concurrency case: session B's create-time prune runs while session A's stage-only finalize is mid-flight (A's work not yet in HEAD) → A's branch **survives** (content-gate).
- Risk: `medium`. Rollback: revert phase.

### Phase 2 — Merge-fence boundary widening
- **Status: DONE** (2026-06-01 — execute → review (grade A) → wrapup). Fence widened to wrap exactly `{stash, staged_before snapshot, merge}`; new `_snapshot_staged_paths`; `_capture` moved before the fence; handed_off computed after. All named exit tests GREEN + T5 fence-gated-stash (deterministic, in `test_worktree_merge_fence.py`). Review deferred CN1 (fence 60s timeout vs 300s stash) per ADR-003's accepted-risk clause; flagged CR1 (success-mode rollback reset-skip, `out_of_diff`, reachability ↑) as a recommended follow-up — NOT folded into P2.
- `depends_on`: `[1]`
- `parallel_group`: `serial-worktree`
- `merge_hazards`: `worktree.py` `_cli_finalize` fence block (`_stash_base_dirty`:1998, `staged_before`:2033, `_acquire_merge_fence`:2041) + `_verify_scope_subset` consumer (:2050); all worktree tests + `test_worktree_parallel_session.py`.
- Scope (in): widen the fence to wrap EXACTLY `_stash_base_dirty` + `staged_before` snapshot + `merge()`, preserving stash→snapshot order. **Lower boundary pinned (ADR-003): `handed_off`, `_write_stash_ref_file`, `cleanup()`, and both pop paths stay OUTSIDE.** (out): any change to the scope-guard, the deferred-pop handoff logic, cleanup, or the fence timeout value.
- Exit:
  - `test_finalize_scope_guard_contamination_unchanged` — on the `--allow-dirty-base` fixture, `_verify_scope_subset`'s contamination set is **identical** before/after the move (the load-bearing invariant — proves the move didn't shift scope-guard semantics).
  - `test_finalize_releases_fence_on_stash_failure` — `_stash_base_dirty` raising inside the fence → function returns 1 AND a subsequent fence acquisition succeeds (no leaked lock).
  - `test_finalize_stage_only_deferred_pop_handoff_unchanged` — stage-only with a dirty base still writes `.hm-finalize-stash-*` + sets `handed_off=True` + the `finally` does NOT pop, after the move (pins that the deferred-pop handoff stayed OUTSIDE the fence — do NOT rely on "existing GREEN" for this).
  - NEW parallel-finalize case: two concurrent finalizes on the same dirty base → the stashes are **serialized** (the race the move closes — proves the fix works, not just doesn't-break).
  - Existing finalize tests (stage-only/success/fail) + `test_worktree_parallel_session.py` GREEN.
- Risk: `medium`. Rollback: revert to Phase 1 state.

### Phase 3 — Safe (non-defense) polish
- **Status: DONE** (2026-06-01 — execute → review (grade A, zero findings) → wrapup). Extracted `_porcelain_path` (3 divergent parse sites unified, fail-safe direction confirmed by review) + batched `git check-ignore --stdin` in `_ensure_harness_gitignore` (N→1 subprocess). Dropped items (flock probe, hot-path move) stayed dropped per ADR-001. Closes PLAN-p6-p7-worktree-finalize (P1+P2+P3 all done).
- `depends_on`: `[2]`
- `parallel_group`: `serial-worktree`
- `merge_hazards`: `worktree.py` `_ensure_harness_gitignore` (check-ignore) + the three porcelain-parse sites (433/686/725); worktree tests.
- Scope (in): batch `git check-ignore` via `--stdin` in `_ensure_harness_gitignore` (one call vs ×12 on first create); collapse the triple-duplicated porcelain-path parsing (433/686/725) into one `_porcelain_path(line)` helper. (out): **the WSL2 flock probe and the `_stash_content_in_head` hot-path move are DROPPED — defense-adjacent (Layer-4 primary / ref-drain timing), deferred to a future deliberate Layer-4 pass per ADR-001.**
- Exit: `test_ensure_gitignore_batches_check_ignore` (asserts a single batched call, not per-pattern); `test_porcelain_path_helper` (the 3 call sites produce identical parsing); full worktree suite + `test_worktree_parallel_session.py` GREEN.
- Risk: `low`. Rollback: revert to Phase 2 state.

## 🧪 Testing Strategy

- **Unit:** the named P1 content-gate tests; P2 scope-guard-invariant + fence-release tests; P3 batch + porcelain-helper tests.
- **Integration (`INTEGRATION=1`):** `test_worktree_parallel_session.py` must stay GREEN AND gain a NEW assertion per defense-touching phase (P1 cross-session prune-vs-finalize; P2 parallel-finalize stash serialization) — "existing GREEN" alone cannot catch net-new-behavior defects.
- Determinism: real-git-in-tmp_path (existing `repo` fixture pattern), no mocks for git.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Orphan-branch gate deletes unsaved work | high→low | path-keyed blob equality biased-to-preserve; named tests for squash-merged-swept + reformatted-preserved; cross-session in-flight branch preserved (not in HEAD) |
| Fence widening shifts scope-guard semantics | high→low | exit asserts contamination set unchanged on dirty-base fixture; ordering invariant (snapshot after stash) in ADR-003 |
| Fence widening trips 60s timeout under parallel finalize | medium | accepted hold-time increase documented; timeout retained, raise only if a real run trips |
| Touching defense core (Layer-4) regresses the 5-layer defense | medium | parallel-session integration test GREEN + new concurrency assertions; defense-adjacent polish (flock/hot-path) dropped |

## ✅ Success Criteria

- [x] No orphan `execute-*`/etc. branch survives once its content is in HEAD and its worktree is gone (P1).
- [x] In-flight / unmerged-content branches are preserved+warned, never deleted (P1).
- [x] Parallel-finalize stash race closed; scope-guard contamination set unchanged; fence released on all exits (P2).
- [x] check-ignore batched; porcelain parse single-sourced (P3).
- [x] `test_worktree_parallel_session.py` GREEN + new concurrency assertions pass.
- [x] Finalize structure + Layer-3 untouched (no asymmetric restructure, no L3 removal).

## 🔍 Plan Validation

**Validator:** pass 1 NEEDS_REVISION (2 critical + 4 warnings + 1 suggestion) → all resolved → **re-validated once** → NEEDS_REVISION (1 new warning, 0 critical: ADR-003 fence lower-boundary unpinned + deferred-pop handoff not explicitly tested) → resolved (fence span pinned to exactly stash+snapshot+merge; `handed_off`/ref-write/cleanup/pops stay outside; added `test_finalize_stage_only_deferred_pop_handoff_unchanged`). Both original criticals confirmed resolved by the re-run. **Final: NEEDS_REVISION_RESOLVED.**

| Finding | Sev | Resolution |
|---|---|---|
| P2 splits `staged_before` from scope-guard consumer; structural-only exit | critical | Exit now asserts contamination set UNCHANGED on dirty-base fixture; ADR-003 records the stash-then-snapshot ordering invariant |
| P2 widens fence over slow stash vs 60s budget; stash-failure now holds lock | critical | ADR-003 Consequences document the hold-time increase + retained 60s; P2 exit tests fence-release-on-stash-failure |
| P1↔scope-guard cross-session branch-existence window | warning | Resolved by the content-gate (in-flight work not in HEAD → branch preserved); recorded in ADR-002 + P1 merge_hazards + a new parallel assertion |
| P1 content-gate edge cases (squash-merged-wip, reformatted blob) | warning | Named P1 tests added; ADR-002 states path-keyed-blob-equality biased-to-preserve |
| P3 buries flock-probe (Layer-4 primary) + hot-path (ref-drain) as low-risk | warning | **Dropped both** — defense-adjacent, deferred per ADR-001; P3 keeps only non-defense polish |
| Exit criteria lean on "existing test GREEN" only | warning | Each defense-touching phase gains a NEW concurrency assertion |
| ADR-002/003 missing Consequences | suggestion | Consequences added to both |
| (re-run) ADR-003 fence lower-boundary unpinned; deferred-pop handoff not explicitly tested | warning | Fence span pinned to exactly stash+snapshot+merge; `handed_off`/ref-write/cleanup/pops stay outside; `test_finalize_stage_only_deferred_pop_handoff_unchanged` added |

### Non-Goals
- Asymmetric finalize restructure; Layer-3 removal (parent ADR-001/002 — superseded by ADR-001).
- Layer-3 wiring-gap #14 (`HM_OWNED_SESSION_UUIDS` in wrapup).
- WSL2 flock positive-exclusion probe; `_stash_content_in_head` hot-path move (defense-adjacent — future Layer-4 pass).
- The 60s fence timeout value (retained; revisit only on a real trip).
