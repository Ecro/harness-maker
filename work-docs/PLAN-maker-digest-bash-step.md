---
type: plan
task_slug: maker-digest-bash-step
status: complete
created: 2026-11-23
spec: "[[SPEC-maker-digest-bash-step]]"
summary: The Claude Maker's `!` digest injection becomes the same first-step bash block the Codex Maker uses; tests, the live boundary test and the docs follow.
---

# PLAN — maker-digest-bash-step

One phase: one template branch plus tests and docs.

- [x] Phase 1 — both targets render one bash block, placed before `## Pick the route`, introduced by "Run this first on every call, whatever the route". scope: `src/harness_maker/templates/skills/world-model/SKILL.md.j2`, `tests/render/test_render_maker_digest_bash_step.py` (new), `tests/render/test_render_maker_front_door.py` (`_injected_command` reads the block for both), `tests/render/test_render_world_model_followups.py` (AC-007 Claude shape), `tests/integration/test_boundary_maker_default_permissions.py` (untrusted arm), `CLAUDE.md`, `docs/reference/world-model.md`, `CHANGELOG.md`, `tests/snapshot/*.expected.yaml` (regenerated). exit: `uv run pytest tests/render/test_render_maker_digest_bash_step.py tests/render/test_render_maker_digest_session_id.py tests/render/test_render_maker_front_door.py tests/render/test_render_world_model_followups.py tests/render/test_ask_less.py tests/render/test_render_world_model.py tests/render/test_maker_advance.py tests/render/test_choice_cards.py tests/render/test_retired_text.py -q` (every test that reads the Maker render). risk: a model skipping the step on a Start route (then no `maker_load` row). rollback: restore the `{% if is_codex %}` branch.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/world_model.py
- src/harness_maker/world_model_digest.py
- src/harness_maker/hooks/sessionid_envfile.py

## Decisions

ADR-001: Drop the `!` injection rather than move Maker to a plugin skill (HR-023 option A, DRI card 2026-11-23). **Decided by:** DRI
ADR-002: Both targets share one block and introducing sentence. **Decided by:** agent
ADR-003: Keep the Claude `allowed-tools` grant; it still pre-approves the step where honoured. **Decided by:** agent
ADR-004: The untrusted live arm runs in default mode and accepts a run or a denial of the digest command with the substituted id. **Decided by:** agent
