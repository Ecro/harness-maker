---
type: plan
task_slug: hide-retired-cli
status: complete
created: 2026-11-10
spec: "[[SPEC-hide-retired-cli]]"
summary: Hide the retired autopilot/verify commands and --autonomy-persistent from help, add a retired notice, fix --autonomy-level help.
---

# PLAN — hide-retired-cli

- Phase 1 — scope: `cli.py` (`hidden=True` on `autopilot`, `verify` and `--autonomy-persistent`; one stderr notice in each command; `--autonomy-level` help); exit: `uv run pytest -q tests/unit/test_hide_retired_cli.py tests/unit/test_cli.py`; risk: a test pins the old help text; rollback: revert cli.py.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/inert_keys.py`
- `src/harness_maker/models.py`
- `src/harness_maker/templates/`

ADR-001: hide, do not delete; a caller keeps working and the keys stay under IRR-006. **Decided by:** agent
