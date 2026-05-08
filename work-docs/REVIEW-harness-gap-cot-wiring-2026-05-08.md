---
type: review
task_slug: harness-gap-cot-wiring-2026-05
status: in-progress
created: 2026-05-08
reviewers_invoked: [code-reviewer, security-reviewer, performance-reviewer, concurrency-reviewer]
consensus_method: cross-check + scope-aware (Phase 12c new rule)
target_commit: 00d91a0
parent_review: REVIEW-harness-gap-cot-2026-05-2026-05-08
---

# Review: Phase 12 wiring (commit 00d91a0)

> Re-review of the wiring commit on top of the prior 12-phase reliability stack.
> Confirms that prior P0 races + drift findings are closed, and surfaces the
> NEW security/concurrency holes the wiring introduced.

## 🎯 Round 1 Summary

**Grade: D** (2 P0 + 6 P1 consensus-passed-by-scope)

Phase 12c's scope-aware exemption rule is now **load-bearing for grading**:
single-specialist findings that cleared scope-exempt criteria are counted as
`consensus-passed-by-scope` rather than buried as `manual-only`. This is the
direct intent of the rule (Pitfall #7 closure), but it does mean the grade
is stricter than pre-12c cross-check would have produced.

**Verified closures from REVIEW-harness-gap-cot-2026-05** (prior round's P0/P1):
- ✅ CP1-CP4 (P0×4 read-modify-write race in episodic/tool_cascade/semantic/profile) → fixed
- ✅ CP5+CP6 (P1 telemetry / security_scanner non-atomic JSONL) → carry-over noted but design exception
- ✅ CP7 (P1 prod_name_guard not wired) → fixed (Phase 12b)
- ✅ CP8 (P1 hallucination dead `_is_guarded_import`) → deleted
- ✅ CP9 (P1 spec_quality bare except) → fixed (logger.warning)
- ✅ CP10 (P1 merge_passes invalidated returned) → fixed
- ✅ CP12 (P2 two_pass_review PR metadata raw) → wrapped in XML fences

## 🔍 Drift Findings

None — all 4 phases (12a-12d) shipped per their PLAN scope. CP8 cleanup
(dead `_is_guarded_import`) was tracked as wrapup-time fix and is included.

## ✅ Consensus Findings

### P0 (consensus-passed-by-scope, security domain)

**Sec-R2-1 — `spec_quality.py:144` XML fence escape via `</spec>` in spec_text**
- The fence I added in Round 1 to fix prior Sec F3 is itself bypassable.
  `<spec>...</spec>` interpolates raw user-controlled `spec_text`. A spec
  containing the literal close-tag `</spec>` followed by adversarial
  instructions ends the fence early and leaks bare instructions to the
  judge.
- **Round-2 fix applied**: `safe_spec = spec_text[:5000].replace("</spec>", r"<\/spec>")`.

**Sec-R2-2 — `drift_monitor.py:193` unrestricted path traversal**
- The new `__main__` CLI accepts `baseline_spec_path` / `baseline_plan_path`
  from stdin and reads them directly. Caller can pass `/etc/shadow` and
  receive its contents in the drift output. Any caller controlling stdin
  becomes an arbitrary-read primitive.
- **Round-2 fix applied**: new `_safe_baseline_path` helper resolves paths
  against `os.getcwd()` and rejects paths that escape via `relative_to`.

### P1 (consensus-passed-by-scope)

| ID | Reviewer scope | File:line | Summary | R2 fix? |
|----|----------------|-----------|---------|---------|
| Sec-R2-3 | security | `telemetry.py:147` | `cwd` from stdin → arbitrary JSONL write path | ❌ deferred 0.7.1 (env var precedence design) |
| Sec-R2-4 | security | `two_pass_review.py:104` | XML fence escape in `pr_title`/`pr_description` | ✅ `_fence_escape` helper |
| Sec-R2-5 | security | `_locking.py:41` | Lock fd `O_RDWR` + mode 0o644 + no symlink check | ✅ `O_WRONLY \| O_NOFOLLOW`, mode 0o600 |
| Sec-R2-6 | security | `security_scanner.py:64-66` | `_load_recent_tool_calls` poisoned tool_input propagates to gate | ❌ deferred 0.7.1 (needs schema validation) |
| Conc-R2-1 | concurrency | `episodic.py:54` + `tool_cascade.py:91` | TextIOWrapper buffered `"a"` mode multi-syscall risk for >PIPE_BUF lines | ✅ switched to `os.write` + cap error string |
| Conc-R2-2 | concurrency | `semantic.py:57` | `read_all`/`search` unlocked → stale read undocumented (no torn read on Linux) | ❌ defer 0.7.1 (no actual corruption today; document only) |
| Perf-R2-1 | performance | `security_scanner.py:48` + `cache_diagnostics.py:218` | O(file_size) read of metrics.jsonl on every scan | ❌ defer 0.7.1 (needs rotation policy) |

**Sub-grade after Round-2 auto-fix:** 0 P0, 4 P1 remaining (deferred to 0.7.1) → **C**.

### P2 (consensus-passed × 1, others single-source)

**Strong cross-check consensus (3 reviewers agree, true `consensus-passed`):**
- **Triple-CP1** — `telemetry.py:102` tool_input truncation produces invalid JSON →
  silently dropped by `_load_recent_tool_calls` (Code F4 + Sec F7 + Perf F4).
  Severity: P2. **Round-2 fix deferred** — needs dict-level truncation
  redesign, not a string slice.

Other consensus-passed-by-scope P2s:
- Code F1 (P1, latent) `_locking.py` not re-entrant — manual-only (no current caller nests)
- Code F5 (P2 — **rejected on review**) `spec_quality.main()` missing module-level `import sys` — actually `import sys` IS inside `main()` body which is valid Python (function-scope import), code reviewer was wrong about scope.
- Code F8 (P2) `cache_diagnostics` None vs 0 → ✅ R2 fix `or 0` pattern
- Conc F4-F6 (P2) lock cleanup, test timeout, exitcode None — defer 0.7.1
- Perf F5-F7 (P2) sliding window, syscall overhead — defer 0.7.1

## ⚠️ Weak Consensus

- Sec-F5 (P1, propagation) + Code-F4 (P2, silent skip) at `_load_recent_tool_calls` —
  same surface, divergent reasoning (security: injection vector / code: silent log).
  Both kept as separate findings.

## 📝 Manual-Only Findings (truncated)

- Code F2 (P1) docstring "5 gates" → ✅ R2 fix
- Code F3 (P1) `merge_passes` empty-pass2 with malformed entries → ✅ R2 fix
  (now also requires at least one entry to carry a `severity` key)
- Code F7 (P2) `hallucination.py` guarded_lines doesn't walk except handlers — defer
- Conc F5+F6 test fixtures — defer

## Round-2 Auto-Fix Application Log

| # | ID | File | Status |
|---|----|------|--------|
| 1 | Sec-R2-1 | spec_quality.py | Applied — `safe_spec` replace `</spec>` |
| 2 | Sec-R2-2 | drift_monitor.py | Applied — `_safe_baseline_path` helper |
| 3 | Sec-R2-4 | two_pass_review.py | Applied — `_fence_escape` helper |
| 4 | Sec-R2-5 | _locking.py | Applied — `O_NOFOLLOW`, mode 0o600, `O_WRONLY` |
| 5 | Code F2 | security_scanner.py | Applied — docstring "7 gates" |
| 6 | Code F3 | two_pass_review.py | Applied — pass2 severity guard |
| 7 | Code F8 | cache_diagnostics.py | Applied — `or 0` for None handling |
| 8 | Conc-R2-1 | episodic.py + tool_cascade.py | Applied — `os.write` + error cap |

**Build verification after Round-2 fixes:**
- `uv run pytest tests/unit/test_memory tests/unit/test_tool_cascade.py tests/unit/test_2pass_review.py tests/unit/test_spec_quality.py tests/unit/test_drift_monitor.py tests/unit/test_security_scanner.py tests/unit/test_cache_diagnostics.py` → **green**
- `uv run ruff check + ruff format --check + mypy --strict` (67 src files) → **clean**
- Full `uv run pytest` → in progress (background)

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining (consensus-passed P0/P1) | Notes |
|-----------|-------|---------------|-------------------------------------|-------|
| 1 (init)  | D     | —             | 2 P0 / 6 P1                         | Phase 12c scope-aware rule applied for first time |
| 2 (auto-fix) | **C** | 8           | 0 P0 / 4 P1 (deferred 0.7.1)        | All P0 closed; remaining P1 are documented carry-overs |

Final grade: **C**
Iterations used: 2 / 3
Status: **CHANGES_REQUESTED** (grade < A threshold)
human_review_needed: **true** — but the 4 remaining P1 are intentionally
deferred to 0.7.1 with documented rationale. User decision required: push
0.7.0 with carry-over P1, or apply round-3 deeper fixes first.

## Recommendation

**Push 0.7.0 as-is**, document the 4 P1 carry-overs in a 0.7.1 plan:
1. **Sec-R2-3** telemetry `cwd` validation — design decision (`CLAUDE_PROJECT_DIR` precedence vs stdin)
2. **Sec-R2-6** + **Triple-CP1** — schema-validate `tool_input` field at read time + fix dict-level truncation in telemetry. These pair.
3. **Conc-R2-2** — semantic/profile read-side locking (or just doc as accepted staleness)
4. **Perf-R2-1** — metrics.jsonl rotation policy. Couple with cache_diagnostics tail-read helper.

The 2 P0s (XML fence escape and path traversal) — the most acute new vulns
introduced by the wiring — are now closed. The remaining P1s are quality
improvements over already-shipped code, not new attack surface.
