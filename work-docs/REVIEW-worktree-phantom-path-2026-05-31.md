---
type: review
task_slug: worktree-phantom-path
status: in-progress
created: 2026-05-31
reviewers_invoked: [code-reviewer, concurrency-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: worktree-phantom-path
  computed_at: 2026-05-31T00:00:00Z
  note: "No PLAN baseline — user opted for direct fix, skipping /hm:plan. Drift gate N/A."
---

# REVIEW — worktree phantom-path / cascade-cancel fix

Diff under review (uncommitted working tree):
- `src/harness_maker/iter_receipts.py` — `_require_existing_root` guard
- `src/harness_maker/worktree.py` — `worktree verify` CLI subcommand
- `src/harness_maker/templates/commands/hm/loop.md.j2` — Step 5 verify gate + no-batch rule
- `src/harness_maker/templates/stages/execute.md.j2` — Step 0 verify gate
- 8 regenerated snapshot fixtures (hash-only churn)

## 🎯 Round 1 Summary

Initial grade: **B** (1 consensus-passed P1). Three reviewers, single contextual pass
(Pass-1 redaction a no-op — uncommitted diff has no PR metadata to anchor on).
Security review found **no P0/P1** (subprocess is `shell=False` args-list; `repr()`
escaping on the error path).

## 🔍 Drift Findings

None. No PLAN baseline (direct fix). `drift_verdict: clean`.

## ✅ Consensus Findings

| Tag | Severity | Finding | Sources |
|-----|----------|---------|---------|
| consensus-passed [2/3] | P1 | No test coverage for `_require_existing_root` + `worktree verify` | code-reviewer, concurrency-reviewer |

## ⚠️ Weak Consensus

None (no surface-matched pairs with diverging reasoning).

## 📝 Manual-Only Findings (single-source — verified correct by orchestrator)

| # | Severity | Finding | Source | Disposition |
|---|----------|---------|--------|-------------|
| M1 | P1 | `verify` falsely accepts the **main repo root** (`git rev-parse --show-toplevel` returns main toplevel) | code-reviewer | **Fixed** (linked-worktree check: git-dir ≠ git-common-dir) |
| M2 | P1 | Prose overpromises uuid/timestamp drift detection the code never implements | code-reviewer | **Fixed** (prose reframed: structural check, name is a human heuristic) |
| M3 | P1 | Anti-batch warning sits 250 lines from the per-iter marker/dispatch sites | concurrency-reviewer | **Fixed** (reminder added at Step 3.5) |
| M4 | P1 | Multi-repo: only primary `<WT>` verified, siblings unverified | concurrency-reviewer | **Fixed** (prose: verify every printed line) |
| M5 | P1 | `_require_existing_root` only checks `is_dir()`, weaker than `verify` | concurrency-reviewer | **Documented** (SCOPE note: cheap existence backstop; verify is authoritative) |
| M6 | P2 | Prose-only serialization is unenforceable; suggest a PreToolUse gate | concurrency-reviewer | **Deferred** (new feature — noted below) |
| M7 | P2 | `verify` re-prints `resolve()`'d path; could differ from create-printed under symlinks | concurrency-reviewer | **Deferred** (low risk; prose says driver keeps create-path) |
| M8 | P2 | Concurrent-`/hm:execute` finalize-stash race untouched/unreferenced | concurrency-reviewer | **Deferred** (orthogonal; owned by 5-layer worktree defense) |
| M9 | P3 | `git` runs with attacker-influenced cwd → reads that dir's config chain | security-reviewer | **Deferred** (rev-parse runs no hooks; internal gate fed by own `create`) |
| M10 | P3 | Resolved toplevel not asserted under `.worktrees/` base | security-reviewer | **Deferred** (defense-in-depth; equality check already defeats fabrication) |

> Cross-cutting signal: M1 (code) and M5 (guard) are the **same weakness class** —
> verification accepting existing-but-invalid paths — surfaced independently by two
> reviewers on different files. Strict surface-match keeps them separate, but the
> convergence raised confidence enough to fix M1 in this round.

## 🤝 Disagreements

None on severity.

### Iteration 2 (Grade: B → A)
Fixes applied: 6 (1 consensus-passed + 5 orchestrator-verified manual)

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Add tests for verify + root guard (consensus-passed) | tests/unit/test_worktree_verify.py, test_iter_receipts.py | Applied |
| 2 | P1 | Reject main repo root (linked-worktree check) | worktree.py:_cli_verify | Applied |
| 3 | P1 | Reframe prose to match actual structural check | loop.md.j2, execute.md.j2 | Applied |
| 4 | P1 | Per-iter anti-batch reminder at Step 3.5 | loop.md.j2 | Applied |
| 5 | P1 | Verify every line in multi-repo mode | loop.md.j2 | Applied |
| 6 | P1 | Document guard-vs-verify scope boundary | iter_receipts.py | Applied |

Remaining (deferred, non-grade-affecting): M6, M7, M8 (P2), M9, M10 (P3).
New issues introduced: 0 (ruff + mypy clean; new tests green).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 consensus + 9 manual | — |
| 2         | A     | 6             | 5 deferred (P2/P3) | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: APPROVED
human_review_needed: false

Verification: `uv run ruff check` ✓, `uv run mypy --strict` ✓, targeted tests ✓, full suite — see terminal. No `git commit` invoked (wrapup owns the commit).
