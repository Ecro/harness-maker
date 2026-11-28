---
type: plan
task_slug: execute-report-short
status: complete
created: 2026-11-28
spec: "[[SPEC-execute-report-short]]"
summary: One template sentence in execute Step 6 swaps the closing summary for a three-line report plus must-decide rows.
---

# PLAN — execute-report-short

One phase is enough: the change is one sentence of `execute.md.j2` plus re-pinned snapshots.

- Phase 1: scope: `src/harness_maker/templates/stages/execute.md.j2` Step 6 closing sentence, snapshots; exit: `uv run pytest tests/unit/test_execute_report_short.py tests/unit/test_overhaul_p1_surface.py tests/snapshot -q`; risk: the model drops a must-decide row (S2) — the sentence names them; rollback: revert the sentence.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/change_card.py
- src/harness_maker/wrapup_land.py
- src/harness_maker/templates/stages/wrapup.md.j2

ADR-001: Close execute with at most three lines plus every `unresolved` / P0/P1 `pre-existing` row and stop reason, "no other summary", pointing at the wrapup change card. **Decided by:** user (approved SPEC 2026-11-28 07:17Z)
ADR-002: Stack on the change-card branch (PR #91). **Decided by:** agent
