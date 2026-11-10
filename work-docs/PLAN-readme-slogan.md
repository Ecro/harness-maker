---
type: plan
task_slug: readme-slogan
status: complete
created: 2026-11-10
spec: "[[SPEC-readme-slogan]]"
summary: Add the pre-registered slogan and fix the stale not-shipped line in both READMEs.
---

# PLAN — readme-slogan

- Phase 1 — scope: `README.md`, `README.ko.md`; exit: `uv run pytest -q tests/structural/test_documentation_contract.py tests/unit/test_docs_render_pipeline.py tests/unit/test_docs_rewrite.py`; risk: a README pin; rollback: revert both files.

## 🚧 Contract Boundaries

### Do not change

- `src/`
