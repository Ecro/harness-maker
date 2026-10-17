---
type: plan
task_slug: maker-advance
status: complete
created: 2026-10-17
spec: "[[SPEC-maker-advance]]"
surface_allowance:
  chars: 120
  reason: "SPEC-maker-advance: spec and execute hand-offs add '; if the world model began this run, enter it now unless its Advance rule stops.' (+79 each), offset in spec by printing the approval-status state with the path and trimming its intro; execute nets +79, spec +2; /hm:help names Maker's Advance rule (+30); aggregate +111 per variant."
  delta_doc: BASELINE-DELTA-maker-advance.md
  commands:
    execute: 85
    hm-execute: 85
summary: "Maker's Advance rule chains spec -> execute -> wrapup in-session; stage hand-offs name the world model; the digest stops naming retired stages; a live Claude run checks land-once / land-never"
---

# PLAN — maker-advance

## Phases

1. Digest. scope: src/harness_maker/world_model_digest.py, specs/SPEC-world-model-followups.*, specs/SPEC-hm-light-lane-s3a.machine.yaml, tests/unit/test_world_model_digest.py, tests/unit/test_light_lane.py. exit: `uv run pytest -q tests/unit/test_world_model_digest.py tests/unit/test_light_lane.py`. risk: other approved SPECs pin the retired stages. rollback: revert.
2. Templates and docs. scope: skills/world-model/SKILL.md.j2, stages/spec.md.j2, stages/execute.md.j2, codex/AGENTS.md.j2, README.md, docs/ARCHITECTURE.md, docs/HOW-IT-WORKS*.md, docs/reference/world-model.md, CLAUDE.md. exit: `uv run pytest -q tests/render/test_maker_advance.py tests/render/test_render_maker_front_door.py tests/unit/test_overhaul_p1_surface.py`. risk: Maker 4,500 and spec 6,500 caps. rollback: revert.
3. Goldens and live run. scope: tests/snapshot/*.expected.yaml, src/harness_maker/test_dep_map.py, tests/integration/test_maker_advance_live.py. exit: `HM_MAKER_ADVANCE_LIVE=1 IS_SANDBOX=1 uv run pytest -q tests/integration/test_maker_advance_live.py`. risk: live-run cost and model variance. rollback: revert.

## 🚧 Contract Boundaries

### Do not change
- src/harness_maker/spec_machine.py
- src/harness_maker/worktree.py
- src/harness_maker/autopilot.py
- templates/agents/

## ADRs

ADR-001: Advance is prompt text in Maker only; stages keep naming the next command and never advance themselves. **Decided by:** user (card "Maker가 이어감", 2026-10-17)
ADR-002: An exempt SPEC chains to a local land with no human touch. **Decided by:** user (card "그대로 land", 2026-10-17)
ADR-003: The digest maps any REVIEW record to `wrapup`; `PIPELINE` keeps six names so `last_stage` still reads old span rows. **Decided by:** agent
