# Pending Drift

## [drift:onboarding-ux-2026-05] wrapup lint cleanup | 2026-05-12
`src/harness_maker/cli.py` was outside the onboarding PLAN phase scope, but wrapup's full `uv run ruff check src/ tests/` gate failed on a pre-existing E501 in the Second Brain override path. A formatting-only split was applied so the required gate could pass. No behavior change intended.

## [drift:second-brain-write-failure] models.py validator hardened during review | 2026-05-17
PLAN-second-brain-write-failure phases 1-5 did not list `src/harness_maker/models.py`. The review stage's security-reviewer found a P1 path-traversal: `SecondBrainFolder.path` validator rejected absolute paths and `~` but allowed `..` segments — exploitable via the new `configure-second-brain --add-folder` CLI surface introduced in Phase 3. Fix added `if ".." in Path(cleaned).parts: raise` after the absolute-path guard. New test `test_second_brain_folder_rejects_dot_dot_traversal` in `tests/unit/test_models.py`. Scope expansion is justified — the PLAN's ADR-003 CLI subcommand exposed the pre-existing validator gap — but the edit is outside the literal PLAN scope, so the next /hm:plan round should consider whether validator hardening belongs in its own follow-up PLAN or stays bundled with the ADR-003 deliverable retroactively. No behavior break for prior callers (folder paths without `..` continue to validate).
