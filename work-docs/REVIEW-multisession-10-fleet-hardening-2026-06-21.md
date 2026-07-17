---
type: review
task_slug: multisession-10-fleet-hardening
status: APPROVED
created: 2026-06-21
reviewers_invoked: [code-reviewer, concurrency-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multisession-10-fleet-hardening
  computed_at: 2026-06-21T00:00:00Z
---

# REVIEW — Multi-session 10-fleet worktree hardening

k-of-3 consensus: 2 Claude reviewers (code, concurrency) + Codex third voter (Production-mandatory).

## 🎯 Round 1 Summary

- **Grade: B** (P0=0, consensus-passed P1=2). Threshold A → auto-fix loop entered.
- 2 consensus-passed P1 (both fixed in round 2). Several P2/P3 weak/manual-only (do not lower grade).

## 🔍 Drift Findings

`drift_verdict: clean`. Diff = `worktree.py`, `readiness.py`, `conftest.py`, 4 new test files, 2 updated tests — all within the PLAN's Technical-Design "Affected Components".
- **Note (not a violation):** the PLAN listed `cli.py` for flag parsing, but the CLI handlers (`_cli_task_*`) live in `worktree.py`; flags were wired there. `worktree_preflight.md.j2` was NOT edited (the auto-refresh/hard-fail outcomes surface via stderr warnings already — optional polish deferred). `conftest.py` autouse `_isolate_session_env` was added (test-determinism necessity for Fix 4, within Phase 1's testing scope).

## ✅ Consensus Findings (consensus-passed)

### P1 — `_unlink_if_unchanged` successor-removal TOCTOU [2/3: concurrency + Codex]
`worktree.py:~1096` (round-1 line). OBSERVE: the reaper re-read the body then `unlink()`ed BY PATHNAME. INFER: if a peer reaper removed the dead-holder lock and a live successor recreated it between the equality check and the unlink, this process unlinked the *successor's live* lock. CONCLUDE: re-opens the exact O_EXCL mutual-exclusion failure the hardening closes. (code-reviewer dissented "clean" — the re-read shrinks but does not close the unlink-by-name window; 2/3 with aligned reasoning → consensus-passed.)
**→ FIXED (round 2):** atomic `os.replace`-to-quarantine reap; the reaper only ever unlinks its private quarantine name.

### P1 — unfenced registry fallback re-opens silent same-slug share [2/3: concurrency + Codex]
`worktree.py:3396` (round-1 line). OBSERVE: `_registry_mutate` falls back to an UNFENCED read-modify-write on lock failure; `claim_task_branch` relies on it. INFER: when the registry lock is wedged (SIGKILL'd O_EXCL holder on WSL2/NTFS), two concurrent claims both read no foreign row, both write, both skip `git worktree add` (`wt.is_dir()` true) → both return the same worktree. CONCLUDE: the ADR-001 atomic-claim guarantee silently degrades to check-then-act under contention — the precise silent share the fenced critical section exists to eliminate.
**→ FIXED (round 2):** `_registry_mutate(strict=True)` re-raises on lock failure; `claim_task_branch` fails closed (SharedSlugError) when `not allow_shared`.

## ⚠️ Weak Consensus

### P2 — O_EXCL body-not-written wedges the fence [weak: concurrency @1078 (SIGKILL window) + Codex @1133 (write failure)]
Two facets of one defect: a lock whose body never got written (SIGKILL in the create→write window, OR `os.write` ENOSPC/short-write) is unparseable → only reapable via the 720s age path → wedges the fence for minutes. Codex's actionable cut: treat a failed/partial body-write as acquisition failure.
**→ FIXED (round 2):** `_excl_lock` verifies the full payload was written; on short/failed write it closes the fd, unlinks its own fresh lock, and keeps polling. (The pure SIGKILL-in-window case remains the documented age-gated path — unavoidable without an atomic body write, ADR-003.)

## 📝 Manual-Only Findings (single-source — NOT auto-applied)

- **P2 (code-reviewer) `worktree.py:~3799`** — preflight auto-refresh rewrites a shared branch under an `--allow-shared-slug` peer (ADR-002's single-owner rationale is waived on the allow_shared path). *Recommendation:* skip auto-refresh when `allow_shared`. Deferred — `--allow-shared-slug` is an explicit opt-in into shared semantics; low real-world incidence. Tracked for follow-up.
- **P2 (code-reviewer) `worktree.py:~3728`** — `task_create` rollback (`release_session`) can drop a legitimately-pre-existing row on a transient `git worktree add` failure during a crash-recovery re-entry (row pre-existed + dir manually removed + transient git failure). *Recommendation:* only roll back a freshly-created claim. Deferred — narrow (manual dir removal + transient failure); the next preflight self-heals the row. Tracked for follow-up.
- **P2 (concurrency) `worktree.py:~1068`** — `_reap_if_stale` parses the nonce but never uses it for the staleness/pid decision; pid-reuse safety comes from never age-reaping a live pid (over-preservation), not the nonce. *Recommendation:* clarify the docstring. Cosmetic.
- **P3 (code-reviewer) `worktree.py:~4316`** — `--allow-drift-land` detected via `in args` can be falsely triggered by a `--message "--allow-drift-land"` value. Extreme argv edge.
- **P3 (code-reviewer) `worktree.py:~4283`** — `--allow-shared-slug` matches exactly; `=`/typo forms are a silent no-op (fails safe toward blocking).

## 🤝 Disagreements

- **`_unlink_if_unchanged` TOCTOU:** concurrency-reviewer + Codex → P1 (real race); code-reviewer → "clean". Resolved 2/3 in favor of the race (the re-read does not close the unlink-by-name window). Fixed regardless.

## Auto-Fix Loop

### Iteration 2 (Grade: B → A)
Fixes applied: 3 (the 2 consensus-passed P1s + the weak-consensus body-write P2).

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | atomic-rename reap (close successor-removal race) | worktree.py `_reap_stale_file` | Applied |
| 2 | P1 | strict registry mutate → claim fails closed | worktree.py `_registry_mutate`/`claim_task_branch` | Applied |
| 3 | P2 | body-write failure = acquisition failure | worktree.py `_excl_lock` | Applied |

Regression tests added: `test_wedged_lock_claim_fails_closed`, `test_wedged_lock_allow_shared_proceeds_unfenced`, `test_excl_lock_body_write_failure_is_acquisition_failure`. Existing `test_reap_abandoned_when_body_changed` now exercises the rename-based restore path.

Verify: `ruff check` + `mypy --strict` clean; worktree concurrency suite GREEN.

Remaining: 0 consensus-passed P0/P1 | New issues introduced: 0 (P0/P1/P2).

### Selective re-review (concurrency-reviewer on the 3 fixes)
Verdict: **all three fixes SOUND.** Fix 2 (body-write cleanup) and Fix 3 (strict claim) are race-free as written. Fix 1 (rename reap) closes the primary 2-party unlink-by-pathname race; a **P3 residual** remains (a 4-party sub-millisecond restore-window interleaving) that is *strictly narrower than the original bug and self-healing* — explicitly "not a regression". Two P3 robustness notes:
- P3 `_reap_stale_file` restore window — accepted residual (documented in the function docstring); chasing the 4-party race risks more than it fixes.
- P3 `quarantine.unlink()` non-FNF OSError propagation — **FIXED** (broadened to `suppress(OSError)`; cleanup of our own quarantine never escapes the fence).
No new P0/P1/P2.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 2 P1      | —   |
| 2         | A     | 3 (+1 P3)     | 0 P1      | 0   |

Final grade: A (selective re-review confirmed all 3 fixes sound; only self-healing P3 residuals remain)
Iterations used: 2 / 3
Status: APPROVED
human_review_needed: false

## ⚠️ Post-review follow-up (found during `/hm:health` verification) — P1-equivalent, FIXED

The automated k-of-3 review reasoned about code logic and missed a **runtime-environment** defect: **Fix 4 never actually fired.** An env probe in a real Claude Code session showed `CLAUDE_ENV_FILE` is **UNSET** in the slash-command Bash subprocess (Claude Code exposes it only to HOOKS, not to the command env). Since `_dim_guardrails` gated the live probe on `CLAUDE_ENV_FILE`, `in_session` was always False → `sessionid_envfile_live` was **permanently N-A** → the signal was silent-dead, i.e. the exact silent-degradation it exists to catch.

**Fix:** re-gate on `CLAUDECODE` (env probe confirmed it IS exported to command Bash, alongside `CLAUDE_CODE_SESSION_ID`). `conftest._isolate_session_env` now also pins `CLAUDECODE` out (else pytest-under-Claude leaks it). Fix-4 tests updated to set `CLAUDECODE`.

**End-to-end proof (this session, CLAUDECODE set):** `sessionid_envfile_live emitted: True`, `passed: False`, `hard_gate: True`, `guardrails score: 0` — the signal now fires and hard-gates as designed (it correctly flags that the harness-maker *source* repo has no rendered SessionStart hook). `ruff` + `mypy --strict` clean; readiness suite GREEN.

**Lesson:** the layered review caught code-logic races but a single env probe caught a dead-on-arrival feature. Runtime-env assumptions need a live probe, not just code review.
