---
type: plan
task_slug: existing-parametrize-all
status: planning
created: 2026-11-28
spec: "[[SPEC-existing-parametrize-all]]"
summary: One Phase A clause so every AC's cases join an existing parametrize of the same call.
surface_allowance:
  chars: 99
  reason: "every AC's cases join a test that already parametrizes the same call (execute Phase A)"
  delta_doc: BASELINE-DELTA-existing-parametrize-all.md
  commands:
    execute: 99
    hm-execute: 99
---

# PLAN — existing-parametrize-all

One phase is enough: one sentence and its pin.

- Phase 1: scope: `stages/execute.md.j2` Phase A, size pins; exit: `uv run pytest -q tests/unit/test_existing_parametrize_all.py tests/structural`; risk: size ratchets; rollback: revert the commit.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/check.py
- src/harness_maker/spec_machine.py

## Decisions

- ADR-001: The clause goes in the "Add each test to its module's existing test file" sentence, ahead of the per-type clauses, so it binds mechanical and property ACs too. The parametric clause keeps its pinned wording. **Decided by:** agent
- ADR-002: +99 chars re-pinned in `main_chars.json` and `_STAGE_BUDGET`, with a surface allowance until the fold. **Decided by:** agent
