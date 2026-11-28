---
type: plan
task_slug: bench-omc-arm
status: complete
created: 2026-11-28
spec: "[[SPEC-bench-omc-arm]]"
summary: One phase - an `omc` arm (OMC execute mode via --plugin-dir, own HOME) in bench_light_lane and saga_bench, plus report lines.
---

# PLAN — bench-omc-arm

One phase: both runners share `bench_light_lane`'s helpers, so the arm, its setup check,
argv, env and report land together and are tested together.

- **Phase 1 — omc arm in both runners.** scope: `scripts/bench_light_lane.py`,
  `scripts/saga_bench.py`, `tests/unit/test_bench_omc_arm.py`. exit: `uv run pytest
  tests/unit/test_bench_omc_arm.py tests/unit/test_bench_light_lane.py
  tests/unit/test_saga_bench.py tests/unit/test_bench_tier3.py -q`. risk: an existing arm's
  argv/env/hash moves and earlier rows stop resuming. rollback: revert the commit.

## 🚧 Contract Boundaries

### Do not change

- `scripts/bench/`
- `docs/evals/`
- `tests/unit/fixtures/hm_eval/`

## ADRs

- ADR-001: the OMC loader is OMC-specific (`OMC_PREFIX`, plugin name check), not a generic
  external-plugin arm. **Decided by:** user (scope card 2026-11-28 named OMC only).
- ADR-002: omc gets its own HOME (per cell; per saga run) and keeps CLAUDE_CONFIG_DIR;
  plain/hm keep the operator HOME. **Decided by:** agent
- ADR-003: shared helpers (`OMC_PREFIX`, `omc_setup`, `omc_argv`, `omc_env`) live in
  bench_light_lane; saga_bench imports them, as it does every other agent helper.
  **Decided by:** agent
- ADR-004: `tests/unit/test_bench_tier3.py`'s ALL_ARMS pin gains `omc` (the arm list is what
  this task changes) plus a check that omc rows leave the plain-vs-hm scorecard unchanged.
  **Decided by:** agent
