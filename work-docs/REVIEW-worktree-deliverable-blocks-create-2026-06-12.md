---
type: review
task_slug: worktree-deliverable-blocks-create
status: APPROVED
created: 2026-06-12
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
codex_status: skipped
codex_skip_reason: "permission gate denied codex exec in this environment"
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: worktree-deliverable-blocks-create
  computed_at: 2026-06-12T00:00:00Z
final_grade: A
human_review_needed: false
---

# REVIEW — worktree-deliverable-blocks-create (2026-06-12)

## 🎯 Round 1 Summary

- **Grade: A** (0 consensus-passed P0/P1). Threshold A met → **APPROVED**.
- Reviewers: `code-reviewer` (3 findings, max P2), `security-reviewer` (clean).
- **Codex third voter: SKIPPED** — the `codex exec` invocation was denied by this environment's permission gate (same as in the plan stage). Per the warn-and-proceed matrix (Production preset mandatory call), this is a loud notice, not a block; the verdict is Claude-derived (2 reviewers) and valid. Ledger row written to `.claude/observability/codex-second-opinion.jsonl`.
- **2 manual-only findings fixed by the orchestrator before wrapup** (not consensus-gated auto-fix — applied on judgment because they hit stated project invariants). 1 P3 left as accepted (cosmetic).

## 🔍 Drift Findings

`drift_verdict: clean`. All 5 changed files (`worktree.py`, `CLAUDE.md`, 3 test files) are within PLAN scope (Phase 1/2 = `worktree.py`+tests, Phase 3 = CLAUDE.md). No scope violations.

- **Incomplete-phase note (informational, not blocking):** PLAN Phase 3 also listed `templates/skills/worktree-isolator/SKILL.md.j2` + `templates/stages/execute.md.j2` dirty-base wording as in-scope; these were not changed. They are optional doc polish — the user-facing behavior is complete without them. No SPEC scenario depends on them, so drift stays `clean`. Tracked as a wrapup follow-up if desired.

## ✅ Consensus Findings

None. The two reviewers surfaced disjoint findings (code-reviewer: test/regex; security: clean), so no finding achieved cross-reviewer surface match. With Codex skipped, no third voice was available to form k-of-3 consensus. All findings below are `manual-only`.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| # | Sev | File | Finding | Disposition |
|---|-----|------|---------|-------------|
| 1 | P3 | `worktree.py:112` `_DELIVERABLE_RE` | `.+` matches `/`, so `work-docs/PLAN-experiments/notes.md` (nested user dir) was wrongly forgiven by the create-guard — an over-match gap in ADR-001's own "anchored, anti-over-match" invariant. | **FIXED** — `.+` → `[^/]+` (flat-file only). Added `test_is_deliverable_path_anti_over_match_nested_dir`. |
| 2 | P2 | `test_worktree_landed_marker.py` | The finalize-side `_write_landed_marker` call (the SOLE production producer of the marker) had no test; a regression there would silently revert the feature to the preserve-wall (the "absent-case = feature black hole" pattern the project's checklist warns about). | **FIXED** — added `test_finalize_writes_landed_marker_at_branch_tip` (real create→finalize→assert marker == branch tip). |
| 3 | P3 | `worktree.py:806` `_list_user_dirty_files` | `-uall` expands a large untracked non-deliverable user dir into N lines in the create-abort listing (was one collapsed `?? dir/` line). Cosmetic verbosity only; guard still fires correctly. | **ACCEPTED** (no fix) — correctness unchanged; the verbose listing is more informative, not wrong. |

**Security review:** `[]` — all 5 threat vectors refuted with evidence: (1) no command/option injection (all git via `_run` args-list, branch names prefix-filtered by `_list_owned_branches`, refs always `refs/hm-landed/v1/`-prefixed so never `-`-leading, `..` rejected by git's refname rules); (2) `--force` live-worktree skip + `git branch -D` checked-out refusal + recovery hint are defense-in-depth; (3) ADR-001 forgiveness is create-only — finalize still preserves a smuggled `PLAN-evil.md`, no data loss; (4) `-uall` is read-only, no posture change; (5) forging a "landed" marker requires `.git/refs` write access (attacker already owns the repo).

## 🤝 Disagreements

None — the reviewers did not disagree on any shared finding (they reviewed disjoint concerns).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 2 (manual, pre-wrapup) | 1 accepted P3 | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

Post-fix verification: `tests/unit/test_worktree_{deliverable_guard,landed_marker,churn_pollution}.py` (61 tests) GREEN; `ruff check` + `mypy --strict` clean. No `git commit` invoked (wrapup owns the commit).
