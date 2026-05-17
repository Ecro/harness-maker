---
type: review
task_slug: io-utils-migration-followup
status: APPROVED
created: 2026-05-17
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
final_grade: A
iterations_used: 1
human_review_needed: false
---

# 🎯 Round 1 Summary

**Grade: A** (zero consensus-passed P0/P1 findings — the two reviewers landed
on disjoint file:line tuples, so all findings tag `manual-only` per the
2-reviewer cross-check rule.)

Two manual-only findings worth applying were addressed proactively (same
executor-judgment policy as the parent PR): one P1 test gap + one P2 latent
error-handling improvement. Two findings deferred: one P2 prose nit (would
trigger another snapshot regen cycle, cost > benefit), one P2 pre-existing
issue out of this commit's scope.

| Iteration | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 (init) | A | 2 (1 P1 + 1 P2) | 2 (P2 only) | 0 |

# 🔍 Drift Findings

None. All staged paths fall within the announced follow-up scope (verify.py +
worktree.py migration, configure.md.j2 dispatch wiring, tracker update, plus
the snapshot regen those template changes force).

# ✅ Consensus Findings

None — two reviewers, zero overlapping `(file, line, severity)` tuples.

# ⚠️ Weak Consensus

None.

# 📝 Manual-Only Findings

## Fixed proactively this round

| # | Severity | File | Issue | Fix |
|---|---|---|---|---|
| F1 | P1 (code) | `tests/unit/test_worktree_multi.py:end` | `_load_sibling_dirs` had no integration test against a provenance-frontmatter-prefixed `harness.yaml`. Existing test_cli_create_* tests used `yaml.dump` (bare single-doc), so the multi-document code path through the new `load_harness_yaml` helper was uncovered in the sibling-repo integration. | Added `test_cli_create_with_provenance_frontmatter_resolves_siblings` — writes a real renderer-shape `harness.yaml` (provenance block + body) and asserts both primary and sibling paths emit. |
| F2 | P2 (code) | `src/harness_maker/verify.py:36` | `except yaml.YAMLError` only caught structural-YAML errors; any other `OSError` (permission denied, NTFS lock on WSL2) would escape uncaught and crash `verify()`. The `hy.exists()` guard prevents `FileNotFoundError` but not the broader class. | Added `except OSError as e: errors.append(f"harness.yaml read error: {e}")` after the YAMLError handler. |

## Remaining (deferred)

| # | Severity | File | Issue | Disposition |
|---|---|---|---|---|
| M1 | P2 (code) | `src/harness_maker/templates/commands/hm/configure.md.j2:107` | Prose doesn't explicitly cover the `vault_path-set + project_id-blank` intermediate state (folder prompt is correctly suppressed but Claude has no instruction to re-surface prompt 2). | **Defer.** The natural prompt order (1 → 2 → 3) already handles this: prompt 2 (project_id) runs BEFORE the prompt 3 condition is evaluated, so a user who skips project_id explicitly chose to skip the folder. Editing the template would trigger another full snapshot regen cycle for a single-line wording change — cost > benefit. Revisit if a real user trips on this. |
| M2 | P2 (sec) | `src/harness_maker/worktree.py:484` | `with gitignore.open("a", ...)` violates the project's atomic-write policy (CLAUDE.md "Atomic file write"). | **Defer.** Pre-existing code; the security reviewer explicitly flagged it as `out_of_diff: true`. Out of this commit's scope. Worth a separate small refactor PR. Risk is low: gitignore entries are short fixed strings well under PIPE_BUF, and the failure mode (partial write) is bounded to the `.claude/.hm-loop-active` gitignore line — does not corrupt user `.gitignore` content. |

# 🤝 Disagreements

None.

# Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init) | A | 2 (1 P1 + 1 P2) | 2 (P2 only) | 0 |

**Final grade: A** (0 consensus-passed P0/P1)
**Iterations used: 1 / 3**
**Status: APPROVED**
**human_review_needed: false**

# Verification post-fixes

```
$ uv run pytest tests/unit/test_worktree_multi.py tests/unit/test_verify.py
25 passed in 2.72s

$ uv run pytest --ignore=tests/e2e
1885 passed, 6 skipped in 63.08s

$ uv run ruff check src/ tests/
All checks passed!

$ uv run mypy --strict src/
Success: no issues found in 77 source files
```

# Notes for wrapup

- Snapshot regen was performed from main repo root (not from inside the
  worktree) per the known `[fail:test] snapshot-regen-inside-worktree`
  pattern. All 8 `tests/snapshot/*.expected.yaml` files updated; the only
  changed content_hash is `commands/hm/configure.md` (mirrors the template
  edit), no incidental drift.
- New test (`test_cli_create_with_provenance_frontmatter_resolves_siblings`)
  is the regression net for the io_utils migration — future renderer
  changes that drop frontmatter or change its shape will fail here.
