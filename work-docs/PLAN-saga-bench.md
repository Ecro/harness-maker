---
type: plan
task_slug: saga-bench
status: complete
created: 2026-11-25
spec: "[[SPEC-saga-bench]]"
summary: New saga runner + fixture beside bench_light_lane, importing its helpers; offline tests with a fake claude.
---

# PLAN — saga-bench

- **Phase 1 — fixture.** scope: `scripts/bench/saga/` (repo, hidden/<session>, reference/<step>,
  hm/intent.yaml, saga.json, validator/). exit: `uv run python scripts/saga_bench.py check`
  prints `fixture ok`. risk: a trap that every arm passes or fails; the pilot drops or fixes it.
- **Phase 2 — runner.** scope: `scripts/saga_bench.py`, `tests/unit/test_saga_bench.py`. exit:
  `uv run pytest tests/unit/test_saga_bench.py -q`. risk: the owner simulator leaks facts;
  rules forbid volunteering and every reply is logged for audit. rollback: delete both files.
- **Phase 3 — live smoke.** One run per arm on S1 only, to catch runner bugs before the pilot.

## 🚧 Contract Boundaries

### Do not change

- scripts/bench_light_lane.py
- scripts/bench/timeparse/
- scripts/bench/tasks/
- scripts/bench/tier3/
- src/
- templates/

## Decisions

ADR-001: A separate script importing bench_light_lane's helpers, not a new mode in it.
**Decided by:** agent (keeps every existing hash and row shape unchanged)

ADR-002: Start the saga from the approved design; numbers of the decision rule are CLI
defaults fixed after the pilot. **Decided by:** user (design card "이 설계로 시작", 2026-11-25)
