# PLAN — saga-pilot-fixes

SPEC: `specs/SPEC-saga-pilot-fixes.md` (approved).

## Phase 1 — runner and scoring

- [x] RED: `test_pilot_ac_001..004` in `tests/unit/test_saga_bench.py` fail on main 53394592.
- [x] `Options.interrupt_delay_s` and the `run` CLI default 60 → 5 s; `build_parser()` split out of `main`.
- [x] `carried_facts(earlier)`; `run_sessions` passes it to every session (both of a parallel group);
      `sim_input` lists carried facts after the session's own; a carried delivery is recorded with
      `carried: True` and never counts toward must-deliver.
- [x] `score_traps`: `resume` also needs no own S4r fact delivered; `E1_no_recurrence` = FAILED
      marks in fewer than half of the later sessions (AC-007 golden updated: 1 of 5 → True).
- [x] `SATURATED`, `MARGIN = 0.2`, `MIN_TRAPS = 3`; `verdict` skips saturated traps; `report` marks them.
- [x] ruff, ruff format, mypy --strict, `tests/unit/test_saga_bench.py` green.
