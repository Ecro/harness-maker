---
type: review
task_slug: saga-pilot-fixes
created: 2026-11-25
spec: "[[SPEC-saga-pilot-fixes]]"
summary: One reviewer round over SPEC and diff, no P1; 2 P2 and 3 P3 accepted and fixed, 1 P3 rejected after reading the code.
---

# REVIEW — saga-pilot-fixes

Round 1: one reviewer over the SPEC and the diff. RED: the 4 new tests failed on main 53394592
(`SATURATED`, `carried_facts`, `build_parser` missing; resume and E1 values wrong).

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | scripts/saga_bench.py score_traps | With the 5 s interrupt S4 rarely reaches a test run, so counting it in E1's denominator loosens "fewer than half" | accepted | cut-off sessions left out of E1; SPEC S4 and AC-003 updated |
| F2 | P2 | tests/unit/test_saga_bench.py test_pilot_ac_002 | The test sliced sessions itself, so the run_sessions wiring and the parallel group were untested; S4r only a subset check | accepted | `group_carried(saga, group)` used by run_sessions and tested on the real S3a ∥ S3b group and S4r with full lists |
| F3 | P3 | scripts/saga_bench.py group_carried | `--sessions` subsets carry facts of sessions that did not run | accepted | kept deliberately (the owner remembers), written in the docstring |
| F4 | P3 | scripts/saga_bench.py run_session | a carried C1 could become a later session's `c1` record | rejected | `c1` is set only when C1 is one of the session's own facts |
| F5 | P3 | scripts/saga_bench.py build_parser | CLI defaults repeat literals | accepted | `MARGIN`, `Options.interrupt_delay_s` |
| F6 | P3 | tests/unit/test_saga_bench.py test_pilot_ac_004 | no check that an active trap row lacks "saturated" | accepted | assertion added |
