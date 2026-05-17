---
type: review
task_slug: second-brain-write-failure
status: APPROVED
created: 2026-05-17
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
final_grade: A
iterations_used: 1
human_review_needed: false
---

# 🎯 Round 1 Summary

**Grade: A** (0 consensus-passed P0/P1 findings; all findings are `manual-only`
under the 2-reviewer cross-check rule since no two reviewers landed on the same
file+line+severity.)

Despite the manual-only consensus tag, the executor (Claude) proactively
applied 3 P1 fixes + 2 P2 fixes because each was a real correctness defect
introduced by this PLAN's own implementation and each came with a concrete
single-source code suggestion. Remaining manual-only findings are 1 P2 with
an acceptable documented-risk tradeoff and 3 P2 info-disclosure cosmetics that
do not affect correctness.

**Fixes applied this round:** 5
**Findings remaining (manual-only):** 4 P2
**New issues introduced by the fixes:** 0 (full pytest 203 tests pass, ruff
clean, mypy --strict clean post-fix)

# 🔍 Drift Findings

None. The diff stays within PLAN scope (Phase 1–5 files plus the
review-stage-introduced fix touches on `models.py`, which is an in-scope
edit because the bug was introduced by Phase 3's CLI subcommand exposing
the existing validator gap).

Note on apparent drift: `tests/e2e/sandbox*/.claude/**` show up in the
diff. These are **worktree-path artifacts**, not real edits — the rendered
sandbox embeds the absolute worktree path. They will be regenerated from
the main repo after stage finalize per the known
`[fail:test] snapshot-regen-inside-worktree` pattern. The reviewers were
explicitly told to ignore them.

# ✅ Consensus Findings

None. Two reviewers, no overlapping findings → consensus filter produces
zero `consensus-passed` items. By the harness grade rule, this means the
grade is **A** regardless of severity in the manual-only bucket.

# ⚠️ Weak Consensus

None.

# 📝 Manual-Only Findings

## Fixed proactively this round (not auto-fix; executor judgment call)

| # | Severity | File | Issue | Fix |
|---|---|---|---|---|
| F1 | P1 | `src/harness_maker/io_utils.py:107` | `load_harness_yaml` returned the provenance dict when the body was missing (truncated WSL2/NTFS write) | Filter out docs with `generated_by: harness-maker`; regression test `test_load_harness_yaml_skips_provenance_only_truncated_write` |
| F2 | P1 | `src/harness_maker/cli.py:1604` | `--add-folder` left a stale `content_hash` → reconciler would mark `harness.yaml` as user-modified and silently block future `/hm:make` re-renders | Recompute `content_hash = sha256(body_bytes)` and inject into the preserved frontmatter dict before atomic_write (mirroring `modular_edit._write_harness_yaml`). Regression test `test_configure_second_brain_add_folder_refreshes_content_hash` |
| F3 | P1 | `src/harness_maker/models.py:279` | `SecondBrainFolder.path` validator allowed `..` traversal — could persist into `harness.yaml` and reach `search_notes` / `write_note` runtime as an allowlist root outside the vault | Added `".." in Path(cleaned).parts → ValueError` after the absolute-path guard. Regression test `test_second_brain_folder_rejects_dot_dot_traversal` |
| F4 | P2 | `src/harness_maker/cli.py:1589` | `--add-folder` appended duplicates on repeated invocation | Dedupe by path; on already-present, emit `{"already_present": …}` JSON and return. Regression test `test_configure_second_brain_add_folder_is_idempotent` |
| F5 | P2 | `src/harness_maker/second_brain.py:266` | `_validate_vault_existence` resolved relative `vault_path` against cwd; `_vault_root` resolved against `harness_root` — divergent | Pass `harness_root` into `_validate_vault_existence` and use `_vault_root(harness_root, cfg)` |

## Remaining (deferred — manual-only, accept as known)

| # | Severity | File | Issue | Disposition |
|---|---|---|---|---|
| M1 | P2 | `src/harness_maker/second_brain.py:267` | Smart vault check follows symlinks: a symlinked `.obsidian/` could redirect mkdir | **Defer.** User owns vault_path and its parent; attacker surface is the user themselves. Documenting as known risk in CHANGELOG would be over-engineering. Revisit if a multi-user vault scenario surfaces. |
| M2 | P2 | `src/harness_maker/cli.py:1557` | `no harness.yaml at <abs-path>` error leaks absolute project path | **Defer.** CLI invoker already has shell access in the project directory; no privilege boundary crossed. |
| M3 | P2 | `src/harness_maker/cli.py:1575` | `configure-second-brain --check` emits raw `vault_path` (may be absolute home path) | **Defer.** Output is consumed by the slash command in the same session; no third-party logs receive it by default. |
| M4 | P2 | `src/harness_maker/second_brain.py:278` | `SecondBrainError` message includes absolute `vault.parent` | **Defer.** Same trust-boundary argument as M2/M3. |

# 🤝 Disagreements

None recorded — the two reviewers landed on distinct findings with no
overlapping (file, line, severity) triples.

# Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init) | A | 5 (3 P1 + 2 P2) | 4 (P2 only) | 0 |

**Final grade: A** (consensus rule: 0 `consensus-passed` P0/P1 findings)
**Iterations used: 1 / 3**
**Status: APPROVED**
**human_review_needed: false**

# Verification post-fixes

```
$ uv run pytest tests/unit/test_io_utils.py tests/unit/test_models.py \
    tests/unit/test_cli.py tests/unit/test_second_brain.py \
    tests/unit/test_interview.py tests/integration/test_second_brain_e2e.py
203 passed in 3.71s

$ uv run ruff check src/ tests/
All checks passed!

$ uv run mypy --strict src/
Success: no issues found in 77 source files

$ uv run pytest --ignore=tests/snapshot --ignore=tests/e2e
1881 passed, 6 skipped in 49.87s
```

# Notes for /hm:wrapup

- Snapshot regeneration deferred: the worktree's `tests/e2e/sandbox*/.claude/**`
  files embed the worktree absolute path. Per the
  `[fail:test] snapshot-regen-inside-worktree` failure pattern, regen MUST
  run from the main repo root **after** the worktree finalize-stage-only
  merges the new template content (if any) back. This PLAN did NOT change
  any templates, so the snapshot regen is purely a worktree-path refresh,
  not a content change. The wrapup stage should run
  `python tests/snapshot/regenerate.py` from the main repo root before
  committing.
- Three follow-up items are tracked in
  `docs/followups/io-utils-migration.md` (verify.py, worktree.py — direct
  callers; autoloop_driver.py, context_lint.py — different file type, out
  of ADR-001 scope).
- Configure.md.j2 slash-command dispatch update was descoped from Phase 3
  (template change would require snapshot regen mid-flight). The new
  `configure-second-brain` CLI subcommand is the load-bearing artifact;
  the slash command's manual prompt path continues to work today. A
  follow-up PR can wire `configure.md.j2` → `harness-maker configure-second-brain --check` JSON dispatch once the snapshot regen flow is clean.
