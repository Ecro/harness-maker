---
type: review
task_slug: health-plugin-bugs-2026-05
status: APPROVED
created: 2026-05-17
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
final_grade: A
iterations_used: 2
human_review_needed: false
---

# REVIEW — health-plugin-bugs-2026-05

## 🎯 Round 1 Summary

| Metric | Value |
|--------|------:|
| Grade | B |
| Reviewers invoked | code-reviewer · security-reviewer |
| Consensus method | cross-check (surface + reasoning alignment) |
| Consensus-passed findings | 1 |
| Manual-only findings | 5 |
| Drift findings | 0 |
| Auto-fix applied this round | 0 (auto-fix happens in Round 2) |

## 🔍 Drift Findings

None. The staged diff matches the PLAN's stated scope:
- Phase 1: `src/harness_maker/readiness.py` (rotation-aware `_dim_observability_setup`)
- Phase 2: `src/harness_maker/ai_readiness.py`, `cli.py`, `tests/unit/test_ai_readiness.py`, new `tests/integration/{conftest,test_health_dashboard_roundtrip}.py`
- Phase 3: 5 version files + `CHANGELOG.md` + `uv.lock`
- Mechanical regen: sandbox files in `tests/e2e/sandbox*/` + 4 fixture CLAUDE.md (auto-stamped by dogfood test)

## ✅ Consensus Findings (auto-fix eligible)

### P1 — Fixture date silently rots after 2027-05-15

- **File**: `tests/integration/conftest.py:14`
- **Tag**: `consensus-passed` (both code-reviewer + security-reviewer flagged the same site; differing severities resolved to P1 because the security-reviewer's reasoning chain proved the actual rot scenario rather than the lighter "missing comment" framing).
- **Issue**: `_FIXTURE_METRICS_DATE = "2026-05-15"` is a hardcoded ISO date. `_candidate_files(obs, days=365)` slices `dated[:days]` — a file-count cap, not a calendar window. Once the fixture date is no longer in the most-recent 365 dated shards observed by the rotation reader (which on the test runner means "after 2027-05-15"), the fixture file silently drops out of the returned list. The integration test then fails with `"Fixture floor not cleared"` pointing the developer at signal weights — the wrong remediation.
- **Fix applied (Round 2)**: Replace with `(datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")` so the fixture stays within the file-count cap regardless of when the test runs. Comment block updated to cite this REVIEW finding.
- **Verification**: `uv run pytest tests/integration/test_health_dashboard_roundtrip.py -v` → 2 passed. `ruff check tests/integration/` clean. `mypy --strict tests/integration/conftest.py` clean.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (not auto-fixed)

### P1 — `_metrics_io._candidate_files` docstring vs implementation mismatch
- **File**: `src/harness_maker/_metrics_io.py:21-22`
- **Reviewer**: code-reviewer only
- **Issue**: Docstring says "capped at `days` recent days" but implementation does `dated[:days]` — a list-slice by count, not a date comparison. Future callers reading the docstring with a small `days` value (e.g. 7) expecting a calendar-day window will get surprising behavior.
- **Why not auto-fixed**: This was the latent cause of Finding 1 above (consensus-passed). The fix is a one-line docstring correction in a file outside this PLAN's scope. **Recommended follow-up**: tighten the docstring in a separate small PR.

### P1 — `build_min_fixture` import coupling pattern
- **File**: `tests/integration/test_health_dashboard_roundtrip.py:30`
- **Reviewer**: code-reviewer only
- **Issue**: Direct import of `build_min_fixture` from `tests.integration.conftest` works but is an unusual pattern (conftest fixtures are normally injected via pytest's fixture mechanism, not imported as ordinary functions).
- **Why not auto-fixed**: Architectural decision worth a separate discussion. The current pattern is intentional — `build_min_fixture` is a function helper that returns a Path, not a pytest fixture that injects state. Moving to a separate `tests/integration/fixtures.py` module would work but is style preference, not correctness.

### P2 — `metrics_has_samples` suggestion ignores `has_telemetry` edge case
- **File**: `src/harness_maker/readiness.py:778-780`
- **Reviewer**: code-reviewer only
- **Issue**: When `has_telemetry=True` (files exist) but `has_samples=False` (files are empty), the suggestion text is still "Use Claude Code for ≥ 5 turns to accumulate telemetry" — which is correct but not maximally precise.
- **Why not auto-fixed**: Cosmetic UX improvement; the current text is never wrong. Recommended follow-up if a user reports the wrong remediation.

### P2 — `_candidate_files(days=365)` memory unbounded
- **File**: `src/harness_maker/readiness.py:765-768`
- **Reviewer**: security-reviewer only
- **Issue**: The for-loop reads each matched file via `_read_text(path).splitlines()` and sums line counts. With 365 dated files × very large file sizes, this could spike memory.
- **Why not auto-fixed**: Marginal regression from prior code (which read 1 file × unbounded size). The path is harness-controlled (`.claude/observability/`), not user input. Early-exit at threshold (≥ 5) is a trivial fix but unnecessary in practice (file sizes are small JSONL).

### P2 — Fixture `settings.json` uses `write_text` not `atomic_write`
- **File**: `tests/integration/conftest.py:51-57`
- **Reviewer**: security-reviewer only
- **Issue**: CLAUDE.md's atomic-write rule applies to files outside `tempfile`-owned directories; `tmp_path` (pytest fixture dir) is not a `tempfile.mkdtemp()` scope. Interrupted test write could leave a corrupted fixture file.
- **Why not auto-fixed**: Test-fixture context — corruption causes a dirty test run, not user data loss. The fixture is rebuilt every test invocation. Acceptable per pragmatic test-quality bar.

## 🤝 Disagreements

The fixture-date finding had a severity disagreement (code-reviewer P2 vs security-reviewer P1). Resolved to **P1** per Step 4c (severity resolution): when two reviewers differ by one tier and one of them has the substantively stronger reasoning chain (security-reviewer traced the actual rot path through `_candidate_files`), the deeper analysis prevails. Recorded here for transparency.

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 consensus, 5 manual | — |
| 2         | A     | 1             | 0 consensus, 5 manual | 0 |

**Final grade: A** — meets `harness.yaml.reviewers.grade_threshold = A`.
**Iterations used: 2 / 3**
**Status: APPROVED**
**human_review_needed: false**

The 5 manual-only findings remain documented above. None block this PLAN. Recommended follow-up items (separate small PRs):
- Fix the `_candidate_files` docstring (1 line in `_metrics_io.py`)
- Decide on the conftest-import pattern (style preference)
- Tighten the `metrics_has_samples` suggestion text (cosmetic)

## Telemetry

Emitted per-round to `.claude/observability/review-2026-05-17.jsonl` per ADR-006 14-field schema. Verifier (Pass 1.5) deferred per ADR-008 — no in-environment Anthropic API client available.
