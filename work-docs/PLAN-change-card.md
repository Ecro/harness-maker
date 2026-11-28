---
type: plan
task_slug: change-card
status: complete
created: 2026-11-28
spec: "[[SPEC-change-card]]"
summary: One phase - change_card module (spec + land cards, locale labels), wrapup_land receipt key, spec/wrapup template sentences, saga bench messages-only accounting.
---

# PLAN — change-card

One phase: the module, its two callers and the bench accounting are small and tested together.

- Phase 1 — card + wiring. scope: `src/harness_maker/change_card.py` (new, labels for en/ko inside it), `hm.py` (dispatchable), `wrapup_land.py` (receipt key), `templates/stages/spec.md.j2` + `wrapup.md.j2`, `scripts/saga_bench.py`, `.claude/intent.yaml` metric text. exit: `uv run pytest tests/unit/test_change_card.py tests/unit/test_saga_bench.py tests/unit/test_wrapup_land.py tests/unit/test_overhaul_p1_surface.py tests/unit/test_overhaul_p1_kept.py tests/render/test_ask_less.py -q`. risk: stage char budgets; Codex skill copies carry the same body. rollback: revert the commit.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/check.py`
- `src/harness_maker/spec_machine.py`
- `src/harness_maker/worktree.py`

## Decisions

ADR-001: The land card is built inside `wrapup_land`, before `task-land` removes the worktree that holds the `hm check` verdict record. **Decided by:** agent
ADR-002: The card reads the verdict record, machine.yaml, SPEC.md and REVIEW from disk; it never re-runs a gate. **Decided by:** agent
ADR-003: Saga read chars count agent messages only; the SPEC is reference. **Decided by:** user (card 2026-11-28 05:34Z)
ADR-004: Card labels follow `harness.yaml` locale. **Decided by:** user (thread 2026-11-28 05:32Z)
