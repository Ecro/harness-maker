---
type: plan
task_slug: retired-wiring
status: complete
created: 2026-11-10
spec: "[[SPEC-retired-wiring]]"
summary: Overhaul phase 2 slice 1 — drop the loop_gate Stop hook from renders (retired through the existing retirement set), stop the ~/.codex profile write, delete six dead partials, drop the progress-file pointer.
---

# PLAN — retired-wiring

- Phase 1 — scope: settings/Side.json.j2, settings/Production.json.j2 and codex/hooks.json.j2 drop the `loop_gate` Stop command; `render._HARNESS_RETIRED_HOOK_INVOCATIONS` gains it; exit: `uv run pytest -q tests/unit/test_retired_wiring.py -k ac_001 tests/unit/test_render_settings_hooks.py`; risk: a re-render drops a user's own Stop hook; rollback: revert the three templates and the set entry.
- Phase 2 — scope: `cli.make` no longer calls `bootstrap_user_codex_profiles`; codex/config.toml.j2 loses the profiles comment; exit: `uv run pytest -q tests/unit/test_retired_wiring.py -k ac_002`; risk: a user relied on `codex -p cheap`; their existing profiles are kept; rollback: revert cli.py.
- Phase 3 — scope: delete the six partials and their pinned tests; execute.md.j2 drops `.claude-progress.json`; exit: `uv run pytest -q tests/unit/test_retired_wiring.py -k "ac_003 or ac_004"`; risk: a test-only renderer still includes a partial; rollback: restore the files.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/templates/hooks/hooks.json.j2`
- `src/harness_maker/hooks/loop_gate.py`
- `src/harness_maker/codex_user_config.py`

ADR-001: modules stay importable in this slice; only rendered wiring and dead templates go. A kept user copy of the old hook keeps working, and module deletion needs per-module reachability evidence. **Decided by:** agent
ADR-002: the loop_gate command is retired through `_HARNESS_RETIRED_HOOK_INVOCATIONS`, the one curated retirement path, instead of a new pruning rule. **Decided by:** agent
