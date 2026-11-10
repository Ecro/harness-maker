---
type: plan
task_slug: docs-rewrite
status: complete
created: 2026-11-10
spec: "[[SPEC-docs-rewrite]]"
summary: Rewrite HOW-IT-WORKS en/ko for the four-stage workflow and drop stale deleted-module lines from the other living docs.
---

# PLAN — docs-rewrite

- Phase 1 — scope: `docs/HOW-IT-WORKS.md`, `docs/HOW-IT-WORKS.ko.md` (full rewrite), `docs/ARCHITECTURE.md` (M17, flow 2, version-drift module), `docs/CONTRIBUTING.md` (layout), `README.md` / `README.ko.md` (digest list, example yaml), `docs/reference/autoloop-pattern.md`, `docs/reference/block-merge-spec.md`; exit: `uv run pytest -q tests/unit/test_docs_rewrite.py tests/structural tests/unit/test_doc_truth.py tests/unit/test_docs_render_pipeline.py tests/unit/test_release_identity.py tests/unit/test_claude_md_relocation.py`; risk: a doc pin on removed text; rollback: revert the doc files.

## 🚧 Contract Boundaries

### Do not change

- `src/`
- `docs/reference/multi-session-worktree.md`
- `docs/reference/reviewer-fanout.md`
- `TECH_SPEC.md`

ADR-001: rewrite instead of editing; the history lives in CHANGELOG and ARCHITECTURE. **Decided by:** agent
ADR-002: dated snapshot docs stay verbatim (they are pinned as the recorded why). **Decided by:** agent
