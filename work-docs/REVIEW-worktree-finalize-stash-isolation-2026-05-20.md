---
type: review
task_slug: worktree-finalize-stash-isolation
status: APPROVED
created: 2026-05-20
reviewers_invoked: [code-reviewer, concurrency-reviewer, security-reviewer, performance-reviewer]
consensus_method: cross-check
drift_verdict:
  result: scenario_miss
  scope_violations: []
  scenario_misses: [phase-4-failure-matrix]
  task_slug: worktree-finalize-stash-isolation
  computed_at: 2026-05-20T00:00:00Z
human_review_needed: true
final_grade: A
iterations_used: 2
max_iterations: 3
---

# REVIEW — worktree-finalize-stash-isolation (2026-05-20)

## 🎯 Round 1 Summary

| Metric | Value |
|--------|-------|
| Grade (initial) | D |
| Grade (post-autofix) | A |
| Consensus-passed findings (P0+P1) | 2 |
| Manual-only findings (P0+P1+P2) | 11 |
| Weak consensus | 0 |
| Iterations used | 2 / 3 |
| Status | **APPROVED** (with `human_review_needed=true`) |

**Why `human_review_needed=true` despite grade A:** Grade gate counts only consensus-passed (cross-reviewer corroborated) findings. Several genuine P0/P1 manual-only findings remain (most importantly the concurrency-reviewer's `stash@{N}` positional-ref staleness P0 and the security-reviewer's path-traversal P1). These require either follow-up work or explicit risk acceptance.

## 🔍 Drift Findings

- **scenario_miss: `phase-4-failure-matrix`** — PLAN-worktree-finalize-stash-isolation Phase 4 (full failure matrix: Class A/B pop conflicts, submodule abort end-to-end, cleanup-after-squash, multi-repo ref preservation, stale-ref skip end-to-end) was not implemented in this execute pass. Phase 1+2+3 covered (machine layer + handshake + template wiring). Phase 4 is the testing depth gap.

## ✅ Consensus Findings (auto-fixed)

### P0 — Non-atomic `.gitignore` write violates project atomic-write rule
- **File:** `src/harness_maker/worktree.py:741` (pre-fix) / `:746-749` (post-fix)
- **Sources:** code-reviewer (P0) + performance-reviewer (P1) → middle: **P0**.
- **Fix applied:** Replaced `gitignore.write_text(...)` (new-file branch) with `atomic_write(gitignore, ...)` from `harness_maker.io_utils`.
- **Reasoning:** `_ensure_gitignore_entry` is on the finalize hot path (called from `_write_loop_marker` AND new `_write_stash_ref_file`). A crash between file creation and content flush leaves `.gitignore` empty/truncated, allowing harness-managed files to subsequently appear as tracked drift. CLAUDE.md Python hard rule: `open(path, 'w')` forbidden outside tempfile-owned directories.

### P1 — `git stash list` substring match returns wrong ref on prefix collision
- **File:** `src/harness_maker/worktree.py:323`
- **Sources:** code-reviewer (P1) + concurrency-reviewer (P0) → middle: **P1**.
- **Fix applied:** Replaced `if message in line:` with exact message-field comparison (`parts = line.split(": ", 2); parts[2].strip() == message`).
- **Reasoning:** `_find_free_name` appends numeric suffixes on collision (`execute-1`, `execute-10`); message `hm-finalize-execute-1` is a substring of the stash line for `hm-finalize-execute-10`. Substring match returned the wrong `stash@{N}`, causing `pop` to drain the wrong stash — silently abandoning the real user WIP.

## ⚠️ Manual-Only Findings (NOT auto-fixed — require explicit human decision)

These are single-source (one reviewer flagged each) so the consensus filter classifies them as manual. Several are P0/P1; the user should triage them as follow-up work or risk-acceptance.

### P0 manual-only

#### M-P0-1 — `stash@{N}` positional ref becomes stale across the finalize → post-commit-pop handoff
- **File:** `src/harness_maker/worktree.py:375` (in `_restore_base_dirty`); root cause in `_write_stash_ref_file` storing positional ref.
- **Source:** concurrency-reviewer.
- **Issue:** `_write_stash_ref_file` persists `stash@{N}` (resolved at push time). Between finalize and `post-commit-pop`, ANY concurrent `git stash push` (git GUI, sibling session, Cursor IDE) shifts the stack — `stash@{N}` now refers to a different entry. Pop drains the wrong stash; user WIP is leaked.
- **Recommended remediation:** Switch the stored ref from positional (`stash@{N}`) to the stash's commit SHA (resolved via `git rev-parse stash@{0}` immediately after push). `git stash pop <sha>` works since git 2.11.
- **Why not auto-fixed:** Single-source finding; the fix changes the on-disk ref-file format which is a structural design change beyond an in-place auto-edit.

### P1 manual-only

#### M-P1-1 — Path traversal on `session:` field in ref file → arbitrary file deletion
- **File:** `src/harness_maker/worktree.py:1020` (probe) + `:1043` (unlink) in `_cli_post_commit_pop`.
- **Source:** security-reviewer.
- **Issue:** `session = fields.get("session", "")` is used unsanitized in `(base / _LOOP_MARKER_DIR / session).is_file()` and `(claude_dir / session).unlink(missing_ok=True)`. An attacker who can write a `.hm-finalize-stash-*` file with `session: ../../.ssh/authorized_keys` causes deletion of arbitrary files reachable by traversal from `<base>/.claude/`.
- **Recommended remediation:** Before path operations, validate `session` matches `^\.hm-loop-[A-Za-z0-9_.-]+$`.
- **Why not auto-fixed:** Single-source; though the fix is mechanical, it changes the ref file's trust model — best to combine with M-P0-1's format change.

#### M-P1-2 — Sibling stash ref encodes sibling wt_name as session; primary marker is only loop marker on disk
- **File:** `src/harness_maker/worktree.py:440` (`_write_stash_ref_file` call site for sibling repos).
- **Source:** code-reviewer.
- **Issue:** `_write_loop_marker` creates ONE marker at `primary_base/.claude/.hm-loop-{primary_wt.name}`. Siblings get NO marker. `_write_stash_ref_file(sibling_base, sibling_wt.name, ...)` writes `session: .hm-loop-{sibling_wt_name}` — a name that has no matching marker. `post-commit-pop` invocations on sibling bases see `_session_marker_present == False` → classify as stale → never pop. Multi-repo dirty sibling base = silent data loss.
- **Recommended remediation:** Store the absolute marker path in the ref file (`session_marker_path: /abs/path/to/primary_base/.claude/.hm-loop-{primary_wt_name}`) and have `_cli_post_commit_pop` resolve against the absolute path.
- **Why not auto-fixed:** Compose with M-P0-1's format change.

#### M-P1-3 — `git stash push -u` 60s timeout leaves orphan partial stash on large trees
- **File:** `src/harness_maker/worktree.py:62` (`_GIT_TIMEOUT = 60`) applied at `:320` (`_stash_base_dirty`).
- **Source:** concurrency-reviewer.
- **Issue:** 60s default timeout is too tight for repos with hundreds of MB of untracked artifacts. `TimeoutExpired` → `RuntimeError` → no orphan cleanup path. Stack accumulates partial entries.
- **Recommended remediation:** Per-call timeout override, or detect and `git stash drop` matching messages on retry.

#### M-P1-4 — `_session_marker_present` non-atomic with subsequent pop (potential double-pop)
- **File:** `src/harness_maker/worktree.py:1020-1034`.
- **Source:** concurrency-reviewer.
- **Issue:** Marker can disappear (parent session crashes its `_clear_loop_marker`) between the `is_file()` check and the actual pop. If success-mode finalize and concurrent `post-commit-pop` race, the same stash could be popped twice.
- **Recommended remediation:** Use a stronger ownership token (e.g., a lockfile via `fcntl`) or re-verify marker presence + ref-file `created_at` mtime adjacency.

#### M-P1-5 — `sorted(glob(...))` snapshot in `post-commit-pop` silently skips refs written mid-iteration
- **File:** `src/harness_maker/worktree.py:1009`.
- **Source:** concurrency-reviewer.
- **Issue:** Refs created after the glob snapshot are not processed. Documented as by-design but undocumented in code.
- **Recommended remediation:** Add an explicit comment; optionally re-glob at loop end and warn.

#### M-P1-6 — `git stash list` full scan O(N) over user stashes
- **File:** `src/harness_maker/worktree.py:321`.
- **Source:** performance-reviewer.
- **Issue:** Power users accumulate hundreds of stashes; the full list is iterated on every dirty-base finalize.
- **Recommended remediation:** Use `git rev-parse stash@{0}` immediately post-push + verify message with `--max-count=1`.

### P2 manual-only (omitted for brevity — recorded for follow-up)

- `_cli_post_commit_pop` marker deletion mid-loop (single-repo safe, fragile).
- `unknown`-class pop signal is inline literal, not a named constant alongside the other two signal constants.
- `git stash` push race: two parallel sessions can both check status and push concurrently — partial duplicate stash entries.
- Stash@{...} format guard missing on read side (defense in depth).
- Symlink on `.claude/` allows ref file write to unintended tree (threat model gap).
- Parallel sessions can duplicate-append `.gitignore` lines (cosmetic; git deduplicates).
- `pending.remove()` inside loop = O(N²) (N≤5 in practice).
- `_is_harness_artifact` filter could miss future patterns if new harness-managed files added without updating the prefix tuple.

## 🤝 Disagreements

| Surface | code-reviewer | concurrency-reviewer | Resolution |
|---------|---------------|----------------------|------------|
| Substring match on stash list (line 323) | P1 (wrong ref under name collision) | P0 (cross-session ownership inversion) | Middle → P1, auto-fixed. Both reasoning chains identify the same root cause (substring not safe); concurrency rates higher because it considers parallel sessions, code-reviewer because it considers sequential collision via `_find_free_name`. Fix is the same. |

## 📝 Auto-Fix Iteration Records

### Iteration 1 — Initial review (Grade: D)
- Consensus-passed P0: 1 (atomic write)
- Consensus-passed P1: 1 (substring match)
- Manual-only: 11
- Decision: enter auto-fix loop.

### Iteration 2 — After auto-fix (Grade: A)

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P0 | `.gitignore` atomic write violation | `worktree.py:746` | Applied |
| 2 | P1 | Substring match on stash list | `worktree.py:323` | Applied |

**Build verification after fixes:**
- `uv run ruff check src/harness_maker/worktree.py` — passed
- `uv run mypy --strict src/harness_maker/worktree.py` — passed
- `uv run pytest tests/unit/test_worktree*.py` — 83/83 passed
- No fix reverts triggered; no regressions introduced.

**Selective re-review:** Both fixes touched `worktree.py` only; re-running code-reviewer logic on the two changed regions confirms no new findings.

**Recomputed grade:** P0_count=0, P1_count=0 → **A**.

## ✅ Final Summary

| Iteration | Grade | Fixes Applied | Remaining (consensus) | New Issues |
|-----------|-------|---------------|----------------------|------------|
| 1 (init)  | D     | —             | 2                    | —          |
| 2         | A     | 2             | 0                    | 0          |

- **Final grade:** A
- **Iterations used:** 2 / 3
- **Status:** APPROVED
- **`human_review_needed`: true** — due to: (a) 1 manual-only P0 (positional stash ref staleness), (b) 6 manual-only P1 (including 1 security path-traversal), (c) Phase 4 (failure matrix tests) not yet implemented per drift gate.

## 🔭 Follow-up Recommendations

Order by risk × effort:

1. **Combine M-P0-1 + M-P1-1 + M-P1-2 into a single follow-up PLAN.** Switch ref-file format from positional `stash@{N}` to commit SHA, add session-name validation, store absolute marker path for siblings. One coordinated change to the ref file schema.
2. **Phase 4 test matrix.** Cover Class A/B pop conflicts, submodule abort, cleanup-after-squash, multi-repo ref preservation, stale-ref skip — most of these failure paths are currently unverified.
3. **M-P1-3 (60s timeout)** — easy fix, defensive.
4. **M-P1-4 (lockfile)** — investigate; may be unnecessary if M-P0-1 is fixed (SHA-based ref is immune to position drift).
5. **P2 cleanup pass** — apply the P2 list above as a single cleanup commit.
