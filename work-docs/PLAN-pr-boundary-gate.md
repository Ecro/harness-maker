---
type: plan
task_slug: pr-boundary-gate
status: complete
created: 2026-11-22
spec: "[[SPEC-pr-boundary-gate]]"
summary: "One phase: CI boundary job, PR template DRI block, CLAUDE.md release text."
---

# PLAN — pr-boundary-gate

One phase is enough: three small text/config edits with no code path between them.

- Phase 1 — scope: `.github/workflows/ci.yml` (new `boundary` job), `.github/PULL_REQUEST_TEMPLATE.md`
  (DRI block on top), `CLAUDE.md` (릴리스 절차 paragraph); exit:
  `uv run pytest tests/unit/test_pr_boundary_gate.py -q`; risk: the CI job fails in GitHub for a
  reason the container hides (missing tool, shallow history); rollback: revert the commit.

## 🚧 Contract Boundaries

### Do not change

- `.github/workflows/release.yml`
- `.github/workflows/autotag.yml`
- `tests/integration/`

## Decisions

ADR-001: Blocking CI job, separate from quality-gate, no `needs`. **Decided by:** agent (SPEC Refinement Decisions)
ADR-002: Scope is plan items Q1 + U3 only. **Decided by:** user (thread message 2026-11-22 14:31Z, "다른것들은 반영안해?")
