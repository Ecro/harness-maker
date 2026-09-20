---
type: mutation-report
slug: mutation-survivors-and-approval-p2s
measured: 2026-09-20
tool: mutmut 2.5.1
verification_tier: 3
mutation_threshold: null
score: 44.7
verdict: baseline-before-implementation
---

# Mutation baseline — `io_utils.py`, before this task's changes

Taken because the plan validator refused a tier-2 bar of 70 over a module nobody had measured.
This is the **pre-change** baseline: the shared `rmw_lock` helper does not exist yet.

## Result

| | mutants | killed | survived | score |
|---|---|---|---|---|
| `src/harness_maker/io_utils.py` | 85 | 38 | 47 | **44.7%** |

Runner: `python -m pytest -x -p no:cacheprovider tests/unit/test_io_utils.py`, wrapped in the
exit-code normaliser from `865e3ef5` (without it, a mutant that breaks the import reads as
survived). Wall time 259 s.

## What this changed about the plan

The first draft declared tier 2 (floor 70) over this module, on the argument that a tier-1 bar
over the 1938-line `spec_machine.py` (62.5%) would score the module rather than the change. At
44.7% the replacement has the same flaw, and worse: the survivors sit in `load_harness_yaml`,
`strip_retired_keys`, `atomic_append` and `denormalize_home_to_tilde` — helpers this task never
touches.

Two remedies were unavailable rather than merely unattractive:

- **Lowering `mutation_threshold`** does nothing. `spec_mutation.main` calls `gate(report, tier)`
  with no baseline, and `threshold_for(tier, None)` returns the **tier floor**. The SPEC's
  `mutation_threshold` field is documentation; the gate never reads it.
- **Narrowing `paths_to_mutate`** and **lowering the tier** are both hashed fields, so either
  releases the SPEC's DRI stamp.

The SPEC therefore moved to tier 3 — the run is taken and recorded, and gates nothing — and was
re-approved at `6983950a…`. The oracles that actually bind this change are the property criteria
AC-001, AC-002 and AC-004.

## The post-change measurement

| | mutants | killed | survived | timeout | suspicious | score |
|---|---|---|---|---|---|---|
| before (baseline) | 85 | 38 | 47 | 0 | 0 | 44.7% |
| after | 106 | 45 | 54 | 2 | 5 | 44.6% |

**The runner is not the same command**, and the two totals are therefore not comparable. The
baseline ran `tests/unit/test_io_utils.py` alone; the post-change run adds
`tests/unit/test_spec_approval.py`, because `rmw_lock`'s own tests (AC-004/AC-005) live there and
a one-module runner would leave every mutant in the new code alive by construction. The plan
validator flagged this confound in advance; the split below is what the phase rests on.

### The split — the only part that means anything

| function | killed | survived | timeout | suspicious | |
|---|---|---|---|---|---|
| `rmw_lock` | 7 | **3** | 2 | 3 | the code this task added |
| `append_atomic_line` | 0 | 21 | 0 | 0 | pre-existing |
| `strip_retired_keys` | 0 | 12 | 0 | 0 | pre-existing |
| `atomic_append` | 8 | 7 | 0 | 0 | pre-existing |
| module level | 3 | 8 | 0 | 0 | pre-existing |
| `atomic_write` / `load_harness_yaml` / `denormalize_home_to_tilde` | 28 | 2 | 0 | 0 | pre-existing |

`rmw_lock` started at 7 survivors and ends at 3. What closed them:

- **`fcntl.flock(fd, LOCK_EX | LOCK_NB)`** — survived. Every other lock test patches `fcntl`, so
  nothing in the suite had ever observed the real flags. Dropping `LOCK_NB` makes the second
  writer BLOCK rather than poll, turning the timeout contract into "wait forever".
  `test_a_held_lock_times_out_instead_of_blocking` runs two real processes against a real lock
  and bounds the wait.
- **Both `break` statements** — survived, now `timeout`: removing either makes the loop run
  forever, which the same test exposes.
- **`0o600`** — survived, now killed: a world-writable lock in a project directory lets any local
  account stall this repo's writers. Verified by re-running that single mutant after the
  assertion landed.

The three that remain are the deadline's `>=` (a difference of one 50 ms poll), the raise's
message text, and the sleep interval. Pinning message text was ruled out in the SPEC interview,
and the other two are timing constants with no observable behavioural difference.

### The score went DOWN while the coverage went UP

44.7% → 44.6%, and `killed` fell from 48 to 45 between two post-change runs. That is not noise
and it is not a regression: mutmut classifies a run that blocks or loops as `timeout` /
`suspicious` rather than `killed`, while the score's denominator still counts it. The mutants my
contention test newly catches are exactly the blocking kind, so catching them moved them out of
the numerator. **A mutation score is not monotone in test quality**, which is worth knowing before
anyone reads a falling number as a warning.

### What is deliberately left

51 of the 54 survivors are in helpers this task never touched — `append_atomic_line` (21) and
`strip_retired_keys` (12) have no killing tests at all. Closing those is its own task; doing it
here would mean writing ~22 tests for code outside this SPEC's subject, which is the reason
ADR-004 moved this SPEC to tier 3 in the first place.
