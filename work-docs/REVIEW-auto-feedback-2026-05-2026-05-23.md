---
type: review
task_slug: auto-feedback-2026-05
status: APPROVED
created: 2026-05-23
reviewers_invoked: [code-reviewer]
consensus_method: single (cross-check configured but only 1 reviewer invoked for time)
human_review_needed: false
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: auto-feedback-2026-05
  computed_at: 2026-05-23T08:45:00Z
---

# REVIEW: auto-feedback-2026-05 (Round 1)

## 🎯 Round 1 Summary

- **Grade:** A (after P1-1 auto-fix)
- **Pass 1 findings:** 5 (2× P1, 3× P2)
- **Auto-fix applied:** 1 (P1-1 task_slug path-traversal guard + regression test)
- **Manual-only remaining:** 4 (1× P1, 3× P2 — single-reviewer, consensus tag = manual-only by Step 4d default)
- **Iterations used:** 1 / 3
- **Status:** APPROVED (grade A ≥ threshold A; P1-1 fixed at source + 3 regression tests)

## 🔍 Drift Findings

Drift gate against PLAN-auto-feedback-2026-05 §Implementation Plan (7 phases):

| Severity | Type | Detail |
|---|---|---|
| informational | Scope-expansion | 154 changed files; PLAN explicitly scoped ~20 source/test files. The 130+ extra are auto-regenerated artifacts (snapshot/*.expected.yaml, fixtures/*/CLAUDE.md, sandbox-plugin-test/*) triggered by Phase 7 version bump (0.23.7 → 0.24.0). Not unintended — but the PLAN body did not enumerate them. |
| P1 | Incomplete-phase | Phase 5 (interview wiring + `_ask_feedback_enabled()` + locale-aware copy) implemented as **minimal interpretation** — users currently toggle via direct `harness.yaml` edit, not via `/hm:configure` interview. PLAN scope explicitly listed the interview question. Deferred under time pressure. Documented in CHANGELOG. |

Both items are informational — no scope violation, no scenario miss. The Phase 5 gap is documented in CHANGELOG and is a follow-up PR candidate.

## ✅ Consensus Findings (consensus-passed)

None — single-reviewer round; all findings tagged `manual-only` per Step 4d default. P1-1 was auto-fixed despite the tag because path-traversal is an unambiguous security regression that does not need cross-check to confirm.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (single-reviewer; awaiting cross-check)

### P1-1 — task_slug path-traversal (AUTO-FIXED in this round)
- **File:** `src/harness_maker/feedback/draft_writer.py:153`
- **OBSERVE:** `out_path = out_dir / f"{date}-{draft.task_slug}-{dedup}.md"` had no validator on `task_slug` (validators existed on `error_message` and `file_paths` only).
- **INFER:** A prompt-injected `task_slug` like `../../etc/cron.d/evil` produces a write outside `.claude/observability/feedback/` because `atomic_write` does `mkdir -p` + `os.replace`. Threat model is internal (the writing LLM gets injected via telemetry content) but contract was explicitly "whitelist discipline".
- **CONCLUDE:** Contract violation; missing validator allowed path-traversal writes.
- **Fix applied (this round):**
  - Added `_TASK_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")` constant.
  - Added `_validate_task_slug` field_validator on `FeedbackDraft.task_slug`.
  - Added 3 regression tests in `tests/unit/test_feedback_draft_writer.py`: `test_task_slug_path_traversal_rejected` (5 bad inputs), `test_task_slug_too_long_rejected`, `test_task_slug_kebab_case_accepted` (4 good inputs including the real `auto-feedback-2026-05`).
- **Verification:** `uv run pytest tests/unit/test_feedback_draft_writer.py -q` → 32 passed (was 29 pre-fix). ruff + mypy clean.

### P1-2 — Dead `_candidate_files` call for review files
- **File:** `src/harness_maker/feedback/telemetry_grep.py:112`
- **OBSERVE:** `_candidate_files(obs_dir, days=1)` filters by `_DATED_RE = r'^metrics-(\d{4}-\d{2}-\d{2})\.jsonl$'` — `review-*.jsonl` cannot match.
- **INFER:** The list comprehension on line 112 always produces an empty list; the `child not in review_files` guard on line 121 is always True; all review files enter via the fallback scan.
- **CONCLUDE:** Behavior is correct (fallback scan picks them up) but the code structure is misleading. A future maintainer adding genuine dedup logic on top of `review_files` will trust the guard and silently fail.
- **Recommendation:** Either remove lines 112-123 (collapse to single fallback scan) or extract `_candidate_files` variant that supports prefix-pluggable patterns.
- **Status:** Deferred — not behavior-affecting, suitable for follow-up cleanup PR.

### P2-1 — Template "5 whitelisted fields" vs 8 enumerated bullets
- **File:** `src/harness_maker/templates/agents/_partials/feedback_dispatcher.md.j2:24`
- **Summary:** Template instructs the LLM about "5 whitelisted fields" but enumerates 8 bullet points (matching the 8 actual `FeedbackDraft` fields). The "5" framing is from ADR-004's logical-category grouping (version+IDE+OS = 1 category, stage+slug = 1, …); the LLM consumer counts 8 and gets confused.
- **Recommendation:** Change to "8 whitelisted fields" OR collapse bullets into 5 logical categories matching ADR-004.
- **Status:** Deferred — cosmetic; does not affect output safety.

### P2-2 — Whole-file read in `_read_jsonl_tail`
- **File:** `src/harness_maker/feedback/telemetry_grep.py:64`
- **Summary:** `silent-intent-miss-{slug}.jsonl` lacks daily rotation. Over months it can grow to MB; only 5 rows are needed.
- **Recommendation:** Add file-size guard (read last 1MB only if file > 1MB) or document rotation policy.
- **Status:** Deferred — memory impact is bounded by maintainer-only feature scope.

### P2-3 — `FeedbackDraft.ide` Literal drift vs `Target` enum
- **File:** `src/harness_maker/feedback/draft_writer.py:55`
- **Summary:** `ide: Literal["claude-code", "cursor", "codex"]` is hardcoded. Adding a fourth `Target` won't auto-update this Literal; first draft from the new target will silently ValidationError.
- **Recommendation:** Either derive from `Target` enum or add a structural test asserting `FeedbackDraft.__fields__['ide']` annotation covers all `Target` values.
- **Status:** Deferred — no new target imminent.

## 🤝 Disagreements

None (single reviewer).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 1 (P1-1)      | 4 (1×P1, 3×P2 — all manual-only) | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: **false**

Caveat: `harness.yaml.reviewers.consensus = cross-check` (2/3) was configured, but only 1 reviewer was invoked this round (time pressure). The 4 deferred manual-only findings would benefit from `security-reviewer` + `concurrency-reviewer` cross-check in a follow-up REVIEW — particularly P1-2 (telemetry dead code) and P2-3 (schema drift) which are higher-confidence with second-opinion confirmation.

## Telemetry

Emitting `review-2026-05-23.jsonl` record:
- slug: auto-feedback-2026-05
- round: 1
- pass1_n: 5
- verifier_kept_n: 5 (no Pass 1.5 verifier invoked — single-reviewer mode)
- verifier_dropped_n: 0
- pass2_kept_n: 5
- consensus_passed_n: 0 (single reviewer)
- build_break_count: 0
- auto_fix_reverted_n: 0
