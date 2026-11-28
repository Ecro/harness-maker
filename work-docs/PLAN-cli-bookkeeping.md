---
type: plan
task_slug: cli-bookkeeping
status: complete
created: 2026-11-27
spec: "[[SPEC-cli-bookkeeping]]"
summary: Add finalize, export-golden --write/--slug, mark-tested --slug default, a wrapup_land default manifest, switch the three stage templates to them, then measure tier 1.
---

# PLAN: cli-bookkeeping

- Phase 1: scope: `spec_machine.py` finalize, `export-golden --slug/--write`, `mark-tested --slug` with every testable AC by default (AC-001..AC-004); exit: `uv run pytest tests/unit/test_cli_bookkeeping.py -q`; risk: finalize stamping on a failing check; rollback: revert the spec_machine hunks.
- Phase 2: scope: `wrapup_land.py` default manifest (AC-005); exit: same test file; risk: a default that lands too little; rollback: revert.
- Phase 3: scope: `templates/stages/spec.md.j2`, `execute.md.j2`, `wrapup.md.j2`, rendered snapshots and budget pins (AC-006); exit: `uv run pytest tests -q -x -n auto`; risk: a snapshot or budget test pinned to the old text; rollback: revert templates.
- Phase 4: scope: tier-1 bench, plain + hm (branch) + hm (main), results recorded (AC-007); exit: `uv run pytest tests/integration/test_cli_bookkeeping_bench.py -q`; risk: noise near the bar; rollback: none (a miss is recorded).

## 🚧 Contract Boundaries

### Do not change
- src/harness_maker/check.py
- src/harness_maker/worktree.py
- src/harness_maker/review_effect.py

## ADRs
- ADR-001: `finalize` wraps `_run_check_all` by capturing its JSON line, so its verdict cannot drift from `check --all`. **Decided by:** agent
- ADR-002: `export-golden --write` replaces a block from its `# AC-NNN golden rows from` comment through the closing `]` of `AC_NNN_ROWS = [`, and appends missing blocks at the end of the file. **Decided by:** agent
- ADR-003: `--slug` resolves paths with `_named_spec_dir(root, slug, root)`, the reader `approval_state` already uses. **Decided by:** agent
- ADR-004: The bench compares hm on this branch with hm on main (124c4c8c) in the same window; plain runs once. **Decided by:** user (SPEC approval 2026-11-27)
- ADR-005: After the rebase onto main 593a6ac5 (#83, #84), the AC-006 char baseline and the hm-main bench arm use 593a6ac5, not 124c4c8c; the SPEC's hashed oracle text still names 124c4c8c. **Decided by:** agent
