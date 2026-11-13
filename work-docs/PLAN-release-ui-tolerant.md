---
type: plan
task_slug: release-ui-tolerant
status: complete
created: 2026-11-13
spec: "[[SPEC-release-ui-tolerant]]"
summary: Make release.yml's github-release step update a Release published from the web UI; document the phone route.
---

# PLAN — release-ui-tolerant

- Phase 1 — scope: `.github/workflows/release.yml` (`github-release` step), `CLAUDE.md` release section, `docs/release-checklist.md`; exit: `uv run pytest -q tests/unit/test_release_ui_tolerant.py tests/unit/test_release_identity.py tests/unit/test_claude_md_relocation.py`; risk: a broken release step only shows at the next tag; rollback: revert the step.

## 🚧 Contract Boundaries

### Do not change

- `src/`
