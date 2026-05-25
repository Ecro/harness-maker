---
type: review
task_slug: harness-artifact-leak
status: APPROVED
created: 2026-05-25
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: harness-artifact-leak
  computed_at: 2026-05-25T02:45:00+09:00
---

# REVIEW — harness-artifact-leak

## Round 1 Summary

Grade: A after auto-fix.

Review found one P1 race-safety issue in the first implementation pass:
`_scan_dangling_worktrees()` removed any owned `.worktrees/*` directory that
was not git-registered and not marker-referenced. That could delete a
half-created concurrent worktree directory before `git worktree add` had
finished writing registration/marker state.

Fix applied: dangling removal is now limited to owned directories with a
`.git` entry, and `test_prune_stale_keeps_half_created_dir_without_git_entry`
locks the race defense.

## Drift Findings

No drift. Changed files are within PLAN scope:

- `src/harness_maker/worktree.py`
- `src/harness_maker/render.py`
- `tests/unit/test_worktree_prune.py`
- `tests/unit/test_manifest_compaction.py`

## Consensus Findings

None remaining.

## Manual-Only Findings

None.

## Verification

- `uv run pytest tests/unit/test_worktree_prune.py tests/unit/test_manifest_compaction.py -q`
- `uv run pytest tests/unit/test_worktree.py tests/unit/test_worktree_multi.py tests/integration/test_worktree_parallel_session.py tests/unit/test_render.py -q`
- `uv run mypy --strict src/harness_maker/worktree.py src/harness_maker/render.py`
- `uv run ruff check src/harness_maker/worktree.py src/harness_maker/render.py tests/unit/test_worktree_prune.py tests/unit/test_manifest_compaction.py`
- `uv run ruff format --check src/harness_maker/worktree.py src/harness_maker/render.py tests/unit/test_worktree_prune.py tests/unit/test_manifest_compaction.py`
