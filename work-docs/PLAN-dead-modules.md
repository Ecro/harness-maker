---
type: plan
task_slug: dead-modules
status: complete
created: 2026-11-10
spec: "[[SPEC-dead-modules]]"
summary: Overhaul phase 2 slice 2 — delete the modules no shipped entry point reaches, unregister them from hm and command_registry, delete the tests that only test them, and keep a standing reachability check.
---

# PLAN — dead-modules

- Phase 1 — scope: `tests/structural/test_dead_modules.py` (RED); exit: `hm check --red --full --slug dead-modules` exit 0; risk: the reachability check is too loose and passes a dead module; rollback: delete the test.
- Phase 2 — scope: delete the AC-001 modules; drop them from `hm._DISPATCHABLE` and `command_registry`; delete tests that test only them, and remove only the dead-module functions from mixed test files; exit: `uv run pytest -q -n auto --dist loadfile`; risk: a shipped path imported a module the static scan missed (dynamic import by computed name); rollback: `git restore` the module.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/templates/stages/`
- `src/harness_maker/templates/commands/`
- `src/harness_maker/templates/skills/`
- `src/harness_maker/templates/agents/`
- `src/harness_maker/templates/settings/`
- `src/harness_maker/templates/codex/`
- `src/harness_maker/permission_syntax.py`
- `src/harness_maker/release_identity.py`
- `src/harness_maker/documentation_contract.py`
- `src/harness_maker/test_runners.py`
- `.github/workflows/`

ADR-001: reachability is a static closure from the console scripts, the shipped directories and `scripts/`, made a standing test (AC-003) so it cannot drift silently. A computed-name import would escape it; the full suite and `hm check` are the second net. **Decided by:** agent
ADR-002: look-alikes with an outside consumer or a test-only design stay, each with its reason in the SPEC (O2). **Decided by:** agent
