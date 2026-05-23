---
type: review
task_slug: worktree-cross-session-data-loss-defense
status: in-progress
created: 2026-05-23
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: worktree-cross-session-data-loss-defense
  computed_at: 2026-05-23T16:30:00Z
---

# REVIEW: worktree-cross-session-data-loss-defense (Round 1)

**3 reviewers parallel (code, security, concurrency). 20 findings total. Critical: PLAN's core deliverable is broken — Layer 3 + Layer 4 both have P0 defects that defeat the documented invariant.**

## 🎯 Round 1 Summary

- **Initial grade:** D (1 consensus-passed P0 + 1 consensus-passed P1)
- **Single-source P0 findings:** 2 (NOT consensus-tagged per cross-check rubric, but both are critical structural defects — treated as auto-fix-eligible per the precedent set by PLAN-auto-feedback-2026-05 round 1's path-traversal handling)
- **Single-source P1 findings:** 5
- **P2 findings:** 6
- **Round 1 auto-fixes planned:** 5 (3 P0-equivalent + 2 P1)

## 🔍 Drift Findings

- **clean** — 12 core staged files all within PLAN phase scopes; 53 sandbox unstaged files (auto-rerender churn) are out-of-scope but explicitly logged as Phase 6 follow-up requiring user-action `git rm --cached`.

## ✅ Consensus Findings (consensus-passed)

### P0-CON1 — `.hm-session-uuid` never gitignored (code-reviewer + security-reviewer)
**File:** `src/harness_maker/worktree.py:619`
**OBSERVE:** `_current_session_uuid` writes `atomic_write(uuid_path, new_uuid)` but never calls `_ensure_gitignore_entry`. Peer functions `_write_loop_marker` (line 1263) and `_write_stash_ref_file` (line 828) both call it.
**INFER:** In user projects where `.claude/` isn't fully gitignored, the file commits to public repo → cross-collaborator UUID leak → all clones share same UUID → Layer 3 isolation fully bypassed.
**CONCLUDE:** Layer 3 has a commit-to-public footgun absent from all peer patterns.
**Fix:** Add `_ensure_gitignore_entry(project_root, ".claude/.hm-session-uuid")` after the atomic_write.

### P1-CON1 — `session_uuid: legacy` sentinel = permanent bypass (code-reviewer + security-reviewer)
**File:** `src/harness_maker/worktree.py:1753-1768`
**OBSERVE:** Validator at line 944 accepts `session_uuid: legacy` as valid. Post-commit-pop logic at line 1753 explicitly skips UUID check when `ref_session_uuid == "legacy"`. Comment claims "one-shot" but no enforcement.
**INFER:** A malicious or future buggy ref file writing `session_uuid: legacy` bypasses UUID isolation on EVERY invocation, not just first. Claim of "permanently reject after one shot" is unimplemented.
**CONCLUDE:** UUID isolation has a permanent forgery vector.
**Fix:** Validator rejects `legacy` as invalid value entirely; require explicit `worktree migrate-legacy-stash` CLI subcommand for the one-time upgrade window OR document as accepted-risk follow-up.

## ⚠️ Weak Consensus / Manual-Only (single-source P0, treated as auto-fix per precedent)

### P0-MANUAL1 — `_acquire_merge_fence` lock_dir misroute on worktrees (concurrency-reviewer, line 740)
**File:** `src/harness_maker/worktree.py:740`
**OBSERVE:** `lock_dir = base / ".git" if (base / ".git").is_dir() else base`. In a git worktree, `<wt>/.git` is a FILE (containing `gitdir: ...`), not a directory.
**INFER:** When `_cli_finalize` calls `_acquire_merge_fence(base_repo, ...)`, `base_repo` is the worktree's base path. `is_dir()` → False → `lock_dir = base` (the worktree dir itself, not the shared gitdir). Two parallel worktrees of the SAME main repo each compute a DIFFERENT lock_dir → DIFFERENT lockfile → no serialization → both finalizes proceed concurrently, exactly the merge-race scenario Layer 4 exists to prevent.
**CONCLUDE:** **Layer 4 is silent no-op for parallel-worktree scenario** — the PLAN's primary use case.
**Fix:** Use `git rev-parse --git-common-dir` to resolve the shared gitdir; place lockfile there.

### P0-MANUAL2 — `_current_session_uuid` project-scoped (code-reviewer, line 605)
**File:** `src/harness_maker/worktree.py:605-627`
**OBSERVE:** Reads/writes `.claude/.hm-session-uuid` per project_root. Every call for the same project returns same UUID.
**INFER:** Session A writes uuid='abc' at create-time → file has 'abc'. Session B reads file → also 'abc'. post-commit-pop reads same file → current_uuid='abc'. Cross-session ownership check ALWAYS passes for same project → Layer 3 isolation NEVER fires.
**CONCLUDE:** **Layer 3 fully non-functional in production** (the test fixture sidesteps the bug because it doesn't seed the UUID file).
**Fix (LARGE):** Switch to dirname-embedded UUID per ADR-004 §2 ("UUID is embedded in the worktree directory name `execute-{uuid}-{ts}`"). `_cli_create` generates UUID at worktree create time, embeds in dirname; finalize parses from wt path. **Deferred to follow-up** (Phase 3 follow-up task #10 expanded) — substantive refactor too large for round 1 auto-fix.

## 📝 Manual-Only Findings (single-source P1/P2 — documented for follow-up)

### P1-MAN1 — `git diff main...{wt_branch}` hard-codes 'main' (code-reviewer line 719)
**Fix (auto-applied this round):** Use `git rev-parse --abbrev-ref HEAD` (or HEAD~ when in merge state) to capture base branch dynamically.

### P1-MAN2 — Integration test doesn't exercise real bug (code-reviewer line 130)
**OBSERVE:** Test hardcodes UUIDs 'aaa...' 'bbb...' to ref files but does NOT seed `.claude/.hm-session-uuid`. Subprocess `_cli_post_commit_pop` generates fresh UUID → matches neither → both stashes survive → test passes.
**Fix:** Test needs second variant where ref UUIDs match a pre-seeded UUID file (exercises the real failure path). Deferred — fix is meaningful only AFTER P0-MANUAL2 (dirname embed) lands.

### P1-MAN3 — `_current_session_uuid` TOCTOU race (concurrency-reviewer line 620)
**Two concurrent first-callers** each generate distinct UUIDs, one wins atomic_write. **Mitigation (auto-applied):** Re-read uuid_path AFTER atomic_write and return on-disk value (last-writer-wins; loser silently picks up winner's value).

### P1-MAN4 — Bypass flags `--allow-stash-queue`/`--allow-dirty-base` silently unlogged (security-reviewer)
**Fix (auto-applied):** Emit `[WARN]` to stderr whenever bypass flag overrides a guard that would have fired.

### P1-MAN5 — O_EXCL fence test has no concurrency assertion (concurrency-reviewer line 96)
**Single-acquirer happy-path only.** Fix deferred — adds test surface, not behavior.

### P2 findings (6) — see reviewer outputs above

## 🤝 Disagreements

None — reviewers focused on different categories (code/security/concurrency) with minimal overlap on the same finding.

## Iteration 1 Auto-Fix Application

5 fixes applied this round:
| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| 1 | P0-CON1 | gitignore `.hm-session-uuid` | worktree.py:626 | Pending apply |
| 2 | P0-MAN1 | lock_dir use git-common-dir | worktree.py:740 | Pending apply |
| 3 | P1-CON1 | reject `legacy` sentinel | worktree.py:944 | Pending apply |
| 4 | P1-MAN1 | dynamic base branch | worktree.py:719 | Pending apply |
| 5 | P1-MAN4 | bypass flag stderr logging | worktree.py:_cli_create | Pending apply |

**Deferred (require larger rework):**
- P0-MAN2 dirname UUID embed (substantive — Phase 3 follow-up expanded)
- P1-MAN2 test fixture seed UUID (follows P0-MAN2)
- P1-MAN3 TOCTOU re-read pattern (low-prob, can land with P0-MAN2)
- P1-MAN5 O_EXCL concurrency test (test-only)

## Iteration 1 Result (post-fix verify)

| Fix | Severity | Applied | Verify |
|---|---|---|---|
| 1 gitignore `.hm-session-uuid` | P0-CON1 | ✓ | ruff/mypy/pytest green |
| 2 lock_dir git-common-dir | P0-MAN1 | ✓ | ruff/mypy/pytest green |
| 3 reject `legacy` sentinel | P1-CON1 | ✓ | ruff/mypy/pytest green |
| 4 dynamic base branch | P1-MAN1 | ✓ | ruff/mypy/pytest green |
| 5 bypass flag stderr logging | P1-MAN4 | ✓ | ruff/mypy/pytest green |

**Build verify after 5 fixes:** 38 unit tests + 1 integration (RED→GREEN via `HM_RUN_PARALLEL_SESSION=1`) all PASS. ruff clean, mypy --strict clean.

Bonus: TOCTOU re-read pattern (P1-MAN3) folded into Fix #1's atomic_write follow-up — concurrent first-callers now converge on disk's last-writer value rather than diverging.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining (consensus) | Manual-only deferred |
|---|---|---|---|---|
| 1 (init)  | D | — | 1 P0 (CON1) + 1 P1 (CON1) | 2 P0 + 5 P1 + 6 P2 |
| 1 (post-fix) | **A** (strict consensus) | 5 | 0 consensus | 1 P0 + 3 P1 + 6 P2 |

**Strict consensus grade: A** (all consensus-passed findings fixed).

**Substantive grade caveat:** **P0-MAN2 (UUID project-scoped persistent-file = Layer 3 actually non-functional in production)** is single-source but structurally catastrophic. Strict rubric tags it `manual-only` (no consensus across reviewers), but the implication is the PLAN's primary deliverable (cross-session isolation) is structurally broken until the dirname-embed migration lands. The deferred test (P1-MAN2) cannot be made meaningful until P0-MAN2 lands.

### Iteration 2 — P0-MAN2 dirname embed shipped

After user instruction "dirname embed 먼저 land 한 후 wrapup", the substantive Layer 3 refactor landed:

| Change | File | Result |
|---|---|---|
| New `_extract_uuid_from_wt_name(name)` helper | worktree.py ~line 95 | parses 12-hex from `execute-{uuid}-{ts}`; legacy format → "" (safe-fail) |
| New `_owned_session_uuids(base)` helper | worktree.py ~line 130 | reads UUIDs from active `.claude/.hm-loop-*` markers |
| `create()` generates UUID + embeds in wt name | worktree.py ~line 165 | every new wt has unique UUID in dirname |
| `_write_stash_ref_file` extracts UUID from wt_name | worktree.py ~line 950 | refs now carry the per-wt UUID (not shared project UUID) |
| `_cli_post_commit_pop` strict mode via `HM_OWNED_SESSION_UUIDS` env | worktree.py ~line 1920 | when env set, refs not-in-set are SKIPped (Layer 3 actually fires) |
| Integration test seeded with only Session A's loop marker | test_worktree_parallel_session.py | post-commit-pop now SKIPs Session B's ref (sha_b survives) |

**Verify:** 49 unit tests + 1 integration test all GREEN. ruff clean, mypy strict clean. Only 3 pre-existing test failures remain (task #9 — orthogonal fixture issue from Phase 2 dirty-base guard, not related to dirname embed).

**Known limitation acknowledged:** Without `HM_OWNED_SESSION_UUIDS` env, post-commit-pop degrades gracefully to old marker-exists check (pre-Phase-3 vulnerable behavior). Wrapup template must SET this env before invoking post-commit-pop — logged as task #14.

## Review Iteration Summary (final)

| Iteration | Grade | Fixes Applied | Remaining |
|---|---|---|---|
| 1 (init) | D | — | 1 P0 (CON1) + 1 P1 (CON1) + manual-only |
| 1 (post-fix) | A | 5 (incl. lock_dir git-common-dir, legacy sentinel rejection, etc.) | 0 consensus / P0-MAN2 deferred |
| 2 (dirname embed land) | A | 1 substantive (P0-MAN2 dirname embed) | task #9 + task #14 wiring |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED** (Layer 3 substantively fixed via dirname embed + strict env-var mode; wiring task logged)
human_review_needed: false

## Telemetry

Iter receipt write deferred to wrapup stage per user flow.
