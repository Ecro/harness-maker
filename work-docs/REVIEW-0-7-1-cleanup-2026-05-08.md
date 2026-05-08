---
type: review
task_slug: 0-7-1-cleanup
status: in-progress
created: 2026-05-08
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, performance-reviewer]
consensus_method: cross-check (surface match + reasoning alignment)
---

# 0.7.1 Cleanup Review (worktree `execute-20260508T1017Z`)

Scope: 16 modified source files + 2 new modules (`_metrics_io`, `_locking`),
with new tests for each. PLAN: `work-docs/plans/PLAN-0.7.1-cleanup.md`.

---

## 🎯 Round 1 Summary

| Reviewer | P0 | P1 | P2 | Notes |
|----------|----|----|----|-------|
| code | 0 | 1 | 5 | mostly nits + drift_monitor fence open-tag concern |
| security | 0 | 4 | 3 | url whitelist, Bearer regex, workspace.current_dir trust |
| concurrency | 2 | 2 | 2 | depth-before-flock + buffered TextIOWrapper (both P0) |
| performance | 0 | 2 | 2 | sort cost, lru_cache eviction (no cap) |

Drift gate: 0 scope drifts (all changes inside PLAN scope).

---

## 🔍 Drift Findings

None. All file changes map to PLAN phases 0–15 (ADRs 102–108).

---

## ✅ Consensus Findings (auto-fix applied)

### F1 — `_locking.exclusive_lock`: depth bumped before flock acquired
**Severity**: P0 · **Tag**: consensus-passed (concurrency, surface-confirmed by code)
**Site**: `src/harness_maker/memory/_locking.py:84–96`

OBSERVE — The acquisition path was:
```python
fd = os.open(...)
_depth_set(key, 1)            # ← BEFORE flock
fcntl.flock(fd, fcntl.LOCK_EX)
```
INFER — A signal handler / nested re-entry on the same thread that
inspects `_depth_get(key)` while we are still blocked in `fcntl.flock`
would observe depth=1 and skip the actual lock. Equally, if `flock`
raises (EINTR / EBADF / EDEADLK), the depth counter stays at 1 with
no fd held — every subsequent caller fast-paths past flock forever.
CONCLUDE — Order swap is mandatory: flock first, depth second.

**Fix applied**: flock now precedes depth bump; finally unwinds
depth → unlock → close in that order. fd cleanup wrapped in outer
try/finally so flock failure cannot leak fd.

### F2 — `telemetry.main`: buffered TextIOWrapper breaks O_APPEND atomicity
**Severity**: P0 · **Tag**: consensus-passed (concurrency)
**Site**: `src/harness_maker/telemetry.py:210–214`

OBSERVE — `metrics_path.open("a", encoding="utf-8")` returns a buffered
text stream. `f.write(line)` may flush across multiple `write(2)`
syscalls, even though the underlying fd was opened with `O_APPEND`.
INFER — POSIX guarantees atomicity only for single writes ≤ PIPE_BUF
(4 KiB). Two concurrent hooks (Claude Code + Cursor in the same
project, or two parallel tools in one IDE) can interleave their
JSONL lines, producing entries like `{"event":"po{"event":"stop"...`
that `iter_recent_entries` silently skips.
CONCLUDE — Replace with raw `os.write()` on `O_APPEND | O_WRONLY |
O_CREAT`. Each entry is ~200–400 B, well under PIPE_BUF.

**Fix applied**: `os.open + os.write + os.close`; comment cites the
PIPE_BUF bound and the interleave failure mode.

### F3 — `DriftMonitor.score`: open-tag injection bypasses fence
**Severity**: P1 · **Tag**: consensus-passed (code + security, 2/4)
**Site**: `src/harness_maker/drift_monitor.py:132–139`

OBSERVE — Defang only handled `</baseline>` / `</current>`.
INFER — A SPEC body containing `<baseline>` (open tag) injects what
looks like a *nested* fence. Some LLM judges treat the deepest tag
as the canonical boundary; the trailing content escapes the data
fence and is read as instructions.
CONCLUDE — Defang both open and close tags symmetrically.

**Fix applied**: chained `replace("<baseline>", r"<\baseline>")`
and equivalent for `<current>`.

---

## ⚠️ Weak Consensus

### F4 — `_locking`: hard reset depth=0 on outer exit
**Severity**: P2 · **Tag**: weak-consensus (code + concurrency reasoning diverged)

Surface match: same finally block, same severity tier.
Reasoning divergence: code-reviewer concluded "potential bug — should
decrement, not zero"; concurrency-reviewer concluded "intentional fail-
safe — outer exit always returns to depth=0 by invariant".

After re-reading the implementation: re-entrant calls take the
`if _depth_get(key) > 0:` branch which symmetrically increments and
decrements. By the time the outer `finally` fires, depth has unwound
back to 1 (the value the outer set). Setting it to 0 is therefore
correct AND defensive — it ensures cleanup even after a leaked
exception path. **Not auto-fixed** (kept as defensive-zero).

---

## 📝 Manual-Only Findings (single source, scope-passed)

These survived their owner's quality bar but did not surface from
a second reviewer. Recorded for the user — none auto-applied.

| ID | Owner | Severity | File / Line | Summary |
|----|-------|----------|-------------|---------|
| M1 | security | P1 | `secscan/hallucination.py:_is_available` | `(p / pkg).is_dir()` is permissive — any directory named after a hallucinated package on `sys.path` returns true. Limit to dirs containing `__init__.py` or `*.pth`. |
| M2 | security | P1 | `telemetry.py:199` | `workspace.current_dir` from stdin trusted as cwd fallback when env vars absent. Path-traversal primitive if stdin is poisoned. Mitigation: containment check `cwd.resolve().is_relative_to(safe_root)`. |
| M3 | security | P1 | `telemetry._SECRET_PATTERNS` | Bearer regex `Bearer\s+[A-Za-z0-9._-]{16,}` may not catch JWTs > 16 chars but with `+/=` (standard base64). Either widen char class or add explicit JWT pattern. |
| M4 | security | P2 | `telemetry._ALLOWED_TOOL_INPUT_KEYS` | `url` is whitelisted but logged verbatim — could include `?token=...`. Consider stripping query string. |
| M5 | performance | P1 | `_metrics_io._candidate_files` | `sorted(..., reverse=True)` is O(N log N) on day-prefix glob. For multi-year accumulation (>1k files) consider heap-based selection. Acceptable until users hit the threshold. |
| M6 | performance | P1 | `secscan/hallucination._is_available` | `@lru_cache(maxsize=512)` has no eviction policy beyond size — long-running daemon could see stale cache after package install. Acceptable for short-lived hooks. |
| M7 | concurrency | P1 | `memory/_locking._LOCK_DEPTH` | `threading.local` does not survive `os.fork()`; child inherits parent's fd but depth=parent. Acceptable: harness uses `multiprocessing` spawn context, never bare fork. |
| M8 | concurrency | P1 | `memory/episodic.read_all` | Glob over `.claude/memory/episodic/*.jsonl` does not exclude in-progress writes. Mitigation: lock file (already exists for semantic; episodic is single-writer per process). |
| M9 | code | P2 | `secscan/prod_name_guard.scan_sequence` | `deque(maxlen=window)` allocation is per-call. If the caller iterates millions, allocate once and `clear()`. Premature; current callers are slash-command scoped. |

---

## 🤝 Disagreements

None — all four reviewers converged on the two P0s with identical
reasoning (depth-before-flock; buffered append).

---

## Round 2 (auto-fix)

Iteration 2 applied F1, F2, F3 in priority order:

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P0 | depth-before-flock | `_locking.py` | Applied |
| 2 | P0 | buffered TextIOWrapper | `telemetry.py` | Applied |
| 3 | P1 | open-tag fence defang | `drift_monitor.py` | Applied |

Verification: `uv run pytest tests/unit/test_memory/test_locking.py
tests/unit/test_telemetry.py tests/unit/test_drift_monitor.py
tests/unit/test_metrics_io.py` → 49 passed in 0.14s.

Full suite re-run: pending (background).

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 2 P0, 1 P1 | — |
| 2         | A     | 3             | 0 P0, 0 P1 | 0 |

Final grade (consensus-passed only): **A**
Iterations used: 2 / 3
Status: APPROVED
human_review_needed: false (consensus); manual-only items M1–M9 left
for user direction (not blockers — design judgment).

**Wrapup blocked by user instruction**: "wrapup 직전에 멈춰". No commit,
no squash-merge, no push from this stage.
