---
type: plan
task_slug: retire-autopilot-remnants
status: complete
created: 2026-10-17
spec: "[[SPEC-retire-autopilot-remnants]]"
summary: "Retire the autoarm readiness signal, make autonomy.pipeline the four rendered stages with a one-advisory load migration (all-retired falls back to the default), and give this repo's CLAUDE.md the output_language marker"
---

# PLAN — retire-autopilot-remnants

The implementation was drafted before the SPEC (see SPEC Refinement Decisions) and moved unchanged
into this worktree. Phase A writes the AC tests against it; Phase C closes the gaps those tests
expose. The known gap is the all-retired fallback (the SPEC's round 3).

## Phases

1. **readiness** — scope: remove `autopilot_autoarm_registered` from `readiness._dim_guardrails` and its tests (AC-001) · exit: `uv run pytest tests/unit/test_readiness_hooks_from_settings.py` · risk: low; weight-0 display-only signal · rollback: restore the block from HEAD
2. **pipeline** — scope: `models.FOLDED_STAGES` in `drop_retired_stages`, a four-stage `AutonomyConfig` default, the preset harness-yaml fallbacks, the `_parse_autonomy` advisory and the all-retired fallback, pins in the retired autopilot tests, snapshots (AC-002, AC-003, AC-005) · exit: `uv run pytest tests/unit/test_atomic_stage_plan_retirement.py tests/unit/test_autonomy_config.py tests/unit/test_synthesize_snapshot.py tests/structural/test_retired_stage_single_reader.py` · risk: medium; IRR-001 rewrites user harness.yaml on re-render · rollback: revert models/interview/templates, regenerate snapshots
3. **locale marker** — scope: the `## Output Language` section in this repo's CLAUDE.md, plus a structural test (AC-004) · exit: `uv run pytest tests/structural/test_repo_output_language.py` · risk: low · rollback: delete the section and the test

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/autopilot.py` behaviour (comment edits only; the retired CLI's silent drop is a SPEC Non-Goal)
- `src/harness_maker/hooks/autopilot_autoarm.py`
- `src/harness_maker/inert_keys.py` (the `autopilot_persistent` make-time warning stays)
- `src/harness_maker/render.py` (`_HARNESS_RETIRED_HOOK_INVOCATIONS` is append-only)
- The `AtomicStage` enum members

## ADRs

ADR-001: The folded names go in a separate `FOLDED_STAGES` set filtered by `drop_retired_stages`, not in `RETIRED_STAGES`, because the structural test forbids a name that is both retired and a live enum member, and the enum keeps `REVIEW`/`VERIFY` for the retired autopilot CLI. **Decided by:** agent

ADR-002: When the migrated pipeline is empty, `_parse_autonomy` uses `AutonomyConfig().pipeline`. **Decided by:** user (SPEC round 3)

ADR-003: The retired autopilot library tests write the 0.62 six-stage pipeline out in full instead of reading the default, so they keep testing that library's mechanics. **Decided by:** agent

ADR-004: Fix the readiness check rather than delete `autopilot_persistent` from this repo's harness.yaml, because other harnesses carry the key too. **Decided by:** user (2026-10-17 conversation)
