---
type: spec
task_slug: hm-eval-wall-time
status: approved
created: 2026-10-15
tags: [harness-maker, spec, python, bench, eval]
test_framework: pytest
interview_rounds: 0
lane: light
intent: HM-LIGHT-LANE
summary: "The headline eval block shows mean wall time per run and the hm/plain time ratio"
---

# SPEC: the eval headline shows how long each arm takes

## 🎯 Intent
The DRI asked (2026-10-15) for elapsed time in the eval results. Every row already records
`wall_s`, but it appears only as `wall s` deep in the Efficiency section of RESULTS.md, and not
at all in the README block. Time is a cost a reader weighs next to dollars (eval 3: plain about
18 s per run, hm about 8 minutes), so it belongs in "What the extra cost buys".

## 🌅 Outcomes
- Each tier's "What the extra cost buys" block, in RESULTS.md and in the README block, has a
  `wall time per run` line right after the cost ratio: each arm's mean wall time per run, the
  hm/plain ratio, and the lead.

## 📋 In-Scope Scenarios

### S1: the headline shows wall time (AC-001)
**Given** rows whose `wall_s` is 10.0 for every plain run and 485.0 for every hm run
**When** the scorecard and the README block are rendered
**Then** the line reads plain `10s (n=6)`, hm `8m 05s (n=6)`, ratio `48.50x`, lead `plain`.

### S2: a missing time is not a zero (AC-002)
**Given** one arm whose rows carry no `wall_s`
**When** the line is rendered
**Then** that arm reads `n/a (n=0)`, the ratio `n/a` and the lead `n/a`.

## ✔️ Acceptance Criteria

### AC-001
The headline block shows mean wall time per run, the hm/plain ratio and the lead (S1).

### AC-002
An arm with no recorded wall time reads n/a, never zero (S2).

## 🚫 Non-Goals
- Changing what `wall_s` measures (the runner's monotonic clock around one `claude -p` run).
- The Efficiency section's `wall s` line, which stays as it is.
- Re-running the eval: RESULTS.md and the README are re-published from the eval-3 rows.

## ⚙️ Constraints
- pytest, in `tests/unit/test_bench_light_lane.py`.
- The lead uses DIRECTIONS["wall"] (lower, exact compare); no new direction.

## ✅ Verification
| Scenario | Mode | Oracle |
|---|---|---|
| S1 | unit | golden strings computed by hand from the fixture rows (AC-001) |
| S2 | unit | golden n/a strings (AC-002) |

## ❓ Open Questions
None.

## Refinement Decisions
- **Step 0 skip, lane light.** One file of logic (the bench publisher), no contract or format
  change (RESULTS.md is generated), reversible by reverting. Stamped exempt.
- **Minutes past 60 s.** `8m 05s` reads at a glance where `485` seconds does not.
