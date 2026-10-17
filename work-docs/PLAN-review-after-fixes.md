---
type: plan
task_slug: review-after-fixes
status: complete
created: 2026-10-17
spec: "[[SPEC-review-after-fixes]]"
summary: "execute writes one cumulative REVIEW after its fix loop, and an execute re-entered after Bind skips Phase A and RED"
---

# PLAN — review-after-fixes

## Phases

1. Template. scope: src/harness_maker/templates/stages/execute.md.j2, tests/render/test_review_after_fixes.py. exit: `uv run pytest -q tests/render/test_review_after_fixes.py tests/unit/test_overhaul_p1_surface.py tests/unit/test_overhaul_p1_kept.py tests/unit/test_overhaul_p1_cut_ledger.py tests/integration/test_stage_template_memory_loader.py`. risk: execute's 7,000-char AC-004 budget and kept-feature lines. rollback: revert.
2. Goldens. scope: tests/snapshot/*.expected.yaml, CHANGELOG.md, docs/reference/world-model.md. The surface nets 0 chars per variant (trims offset the additions), so no allowance or baseline delta. exit: `uv run pytest -q tests/structural/`. risk: none beyond the ratchet. rollback: revert.

## 🚧 Contract Boundaries

### Do not change
- src/harness_maker/world_model_digest.py
- src/harness_maker/check.py
- src/harness_maker/review_effect.py
- src/harness_maker/templates/skills/world-model/SKILL.md.j2

## ADRs

ADR-001: The REVIEW's existence is execute's completion record; no new field or marker. **Decided by:** agent (default, recorded in the SPEC; DRI card "지금 고침", 2026-10-17)
ADR-002: No `hm check` after the REVIEW is written; wrapup's check gates it. **Decided by:** agent (spec-validator round 1)
ADR-003: The resume clause is appended to the kept hot-tier line, not a new step. **Decided by:** agent
