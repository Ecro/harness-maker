---
type: plan
task_slug: wrapup-gate
status: complete
created: 2026-11-10
spec: "[[SPEC-wrapup-gate]]"
summary: hm check gains --require-review (wrapup) and a contract section that path-matches the PLAN's Do not change list; execute and wrapup text hand both checks to hm check.
---

# PLAN — wrapup-gate

- Phase 1 — scope: `check.py` `review_section` (`needs_review`, `require`), `contract_section`, `_reprint`, `--require-review`, `_UNKEYED_OPTIONS`; exit: `uv run pytest -q tests/unit/test_wrapup_gate.py -k "ac_001 or ac_002 or ac_003"`; risk: an existing PLAN's bare-path bullet now fails a task that edits it; rollback: revert `check.py`.
- Phase 2 — scope: `templates/stages/execute.md.j2` Step 0 and Step 4, `wrapup.md.j2` gate line; exit: `uv run pytest -q tests/unit/test_wrapup_gate.py -k ac_004`; risk: surface growth past the baseline; rollback: revert the two templates.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/check_reuse.py`
- `src/harness_maker/spec_machine.py`
- `src/harness_maker/wrapup_land.py`

ADR-001: the review requirement is a wrapup-only flag, not stage sensing; execute's own gate runs before its review. **Decided by:** agent
ADR-002: `require_review` stays out of the verdict key, and an identical reprint recomputes the review section; keying on it would cost wrapup the reuse of execute's pass. **Decided by:** agent
ADR-003: a qualified `Do not change` bullet is advisory and only a user-decided `allows:` counts (spec-validator critiques 1 and 2). **Decided by:** agent
