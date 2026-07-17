---
type: review
task_slug: codex-compat-fixes
status: APPROVED
created: 2026-05-22
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: codex-compat-fixes
  computed_at: 2026-05-22T00:00:00Z
---

# REVIEW — Codex compat fixes (SessionStart hook + profiles bootstrap)

## 🎯 Round 1 Summary

| Metric | Value |
|---|---|
| Grade | **A** |
| Threshold | A |
| Consensus-passed P0/P1 | 0 / 0 |
| Manual-only findings | 5 (all P2) |
| Auto-fix applied | 0 (no consensus-passed eligible) |
| Status | **APPROVED** |
| human_review_needed | false |

No P0/P1 consensus-passed defects. The two core fixes are correct:
- `systemMessage` correctly promoted to top-level payload (both Claude Code official + Codex strict schemas honored).
- `[profiles.*]` correctly excised from project-local config + bootstrapped to `~/.codex/config.toml` with idempotent lexical detection.

## 🔍 Drift Findings

N/A — bug-fix in-session; no PLAN/SPEC to drift against. `drift_verdict.result: clean`.

## ✅ Consensus Findings

None. No reviewer pair targeted the same file+line+severity tier.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

All 5 are real, all P2. None block A-grade — surfaced for human decision before commit.

### code-reviewer

**P2-1 — `codex_user_config.py:69` — Whitespace-variant TOML headers evade idempotency**
- OBSERVE: substring match `"[profiles.cheap]" not in existing`.
- INFER: TOML spec §4.5 allows whitespace inside brackets — `[ profiles.cheap ]` is semantically identical but bypasses the check.
- CONCLUDE: user config formatted by a TOML formatter that emits spaced headers gets duplicate blocks appended → Codex parse error.
- Suggestion: `re.search(r'\[\s*profiles\.cheap\s*\]', existing)`.

**P2-2 — `codex_user_config.py:75` — `~/.codex` is a file → opaque error, no test**
- OBSERVE: `path.parent.mkdir(parents=True, exist_ok=True)` raises `NotADirectoryError` if `~/.codex` exists as a plain file.
- INFER: caught at `cli.py:437` as `OSError` (graceful skip) but error message is `[Errno 20] Not a directory` — undiagnosable.
- CONCLUDE: graceful but bad UX; no test fixture exercises this path.

**P2-3 — `test_sessionstart_drift.py:131` — Drift-only test missing top-level negative guard**
- OBSERVE: only asserts `assert "systemMessage" not in payload["hookSpecificOutput"]`.
- INFER: production code at the new line 471 is gated on `hint is not None`, so drift-only currently never emits `systemMessage` anywhere. But a future refactor could accidentally set `payload["systemMessage"] = ""` unconditionally without breaking this test.
- CONCLUDE: weaker contract than the matching hint-path test (which has the negative guard at both levels).

**P2-4 — `codex_user_config.py:76` — `_HEADER` always prepended → duplicate on partial-install re-runs**
- OBSERVE: `body_parts = [_HEADER, *(block for _name, block in additions)]` always includes the header.
- INFER: second `make` run that installs only the missing block re-prepends the ADR-008 comment block.
- CONCLUDE: cosmetic; harmless to TOML parsers but confusing to a user reading the file.

### security-reviewer

**P2-5 — `io_utils.py:46` — `atomic_write` narrows existing file permissions to 0600**
- OBSERVE: `tempfile.NamedTemporaryFile(mode="w", dir=path.parent, ...)` — no explicit permissions; `mkstemp` defaults to 0600.
- INFER: `os.replace` transplants the tempfile's 0600 inode into the destination, discarding the prior file's mode bits. If `~/.codex/config.toml` was 0644, it becomes 0600 after our write.
- CONCLUDE: tighter is safer for a config file, but unexpectedly narrows perms on shared/scripted setups. Note: affects ALL files written by `atomic_write` repo-wide, not just this diff. Out of scope for the codex-compat bug-fix.

## 🤝 Disagreements

None — reviewers covered disjoint surfaces (code-reviewer focused on bootstrap correctness + test contracts; security-reviewer focused on file-mode + symlink/TOCTOU/encoding/secrets/injection — confirmed clean on all except mode).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 5 (manual-only) | — |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

## Telemetry

`pass1_n=5, verifier_kept_n=5 (skipped — small diff), pass2_kept_n=5, consensus_passed_n=0, manual_only_n=5, build_break_count=0, auto_fix_reverted_n=0, wall_time_ms≈200000, fallback=null`

## Recommendation to user

Grade-A pass means commit-ready. However, P2-1, P2-3, P2-4 are small, clearly-improvements, and trivial to apply:

- **P2-1** (regex idempotency) — 2-line change in `codex_user_config.py`; closes a real edge case.
- **P2-3** (top-level negative guard test) — 1-line test add.
- **P2-4** (`_HEADER` only on fresh file) — 2-line change.

**P2-2** (mkdir on file-path-not-dir) and **P2-5** (atomic_write mode preservation) are deferrable:
- P2-2 is an unusual user misconfiguration with graceful skip already in place.
- P2-5 affects an existing helper shared by many writers — out of scope for codex-compat.

Suggest applying P2-1, P2-3, P2-4 before commit; defer P2-2 + P2-5.
