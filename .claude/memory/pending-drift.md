# Pending Drift

## [drift:onboarding-ux-2026-05] wrapup lint cleanup | 2026-05-12
`src/harness_maker/cli.py` was outside the onboarding PLAN phase scope, but wrapup's full `uv run ruff check src/ tests/` gate failed on a pre-existing E501 in the Second Brain override path. A formatting-only split was applied so the required gate could pass. No behavior change intended.
