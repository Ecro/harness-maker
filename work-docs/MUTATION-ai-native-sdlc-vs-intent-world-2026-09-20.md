---
type: mutation-report
slug: ai-native-sdlc-vs-intent-world
measured: 2026-09-20
tool: mutmut 2.5.1
verification_tier: 1
mutation_threshold: 85
score: 62.3
verdict: below-threshold
---

# Mutation measurement — ai-native-sdlc-vs-intent-world

The SPEC declared `mutation_threshold: 85` and `last_mutation_run: null`: the run during
`/hm:execute` produced 0 mutants and exited 1, so the number behind the threshold had never
been observed. This is the first real observation.

## Result

| | mutants | killed | survived | score |
|---|---|---|---|---|
| `src/harness_maker/spec_machine.py` | 1303 | 814 | 489 | 62.5% |
| `src/harness_maker/autopilot_caps.py` | 409 | 252 | 157 | 61.6% |
| total | 1712 | 1066 | 646 | **62.3%** |

Below the Tier-1 floor of 85. Wall time 5h52m, runner scoped to the 12 unit-test files that
cover the two modules (1109 tests, ~13 s per mutant, `-n 8`).

## Two tool faults found on the way, both of which produce a plausible wrong number

1. **`.mutmut-cache` is committed to the repository** (tracked since `bf65a1d1`, 0.18.0).
   mutmut 2.x runs every untested mutant in that cache, not only the ones for
   `--paths-to-mutate`: the first attempt reported `16/1712` while mutating `cache.py`.
   This is the most likely reason the execute-stage gate reported 0 mutants.
2. **mutmut counts only `rc == 1` as killed** (`tests_pass`: `return returncode != 1`).
   pytest exits `2` on a collection error, and pytest-xdist exits `2` when `-x` stops a run —
   so a mutant that breaks the module at import time, the loudest kind, is recorded as
   **survived**. Observed directly: mutating `ACType = Literal["mechanical", ...]` to
   `"XXmechanicalXX"` fails 8 tests at collection and mutmut called it survived. The run above
   used a wrapper that normalises any non-zero exit to 1; `harness_maker.spec_mutation` does
   not, so every score it has ever reported is deflated by its import-breaking mutants.

## Where the survivors are

`paths_to_mutate` names both modules whole, so most survivors are outside the surface the
threshold rationale names (the approval hash, the state table, the land decision, the spec
boundary): `_cmd_boundary` 94, `main` 58+10, module level 48+16, the waiver/judgment/oracle
CLI paths. 68 survivors fall inside the named surface, and these are real test gaps:

| Function | Survivors | What is unasserted |
|---|---|---|
| `compute_subject_hash` | 14 | the size/count caps (`>` vs `>=`), the unreadable-file and empty-subject raises |
| `approval_state_of` | 12 | mostly `detail=` text; `schema_version < 3 and items is None` (row 8) is real |
| `_spec_dir` | 11 | empty-after-strip, the `..` rejection, the `normpath` join |
| `_changed_spec_units` | 9 | the md-parent-in-configured-dirs condition |
| `_is_plain_slug` | 5 | the `"\\"` clause and the `(".", "..")` clause |
| `approve` | 5 | empty `git config user.name`, the pre-stamp `approval = None` |
| `_named_spec_dir`, `land_states`, `hold_lines`, `approval_state`, `_state_at` | 12 | the `or "-"` fallback, the pair-key construction, message text |

A message-text mutation that survives is not automatically a defect — asserting every string
is its own cost. The caps, the two boolean clauses and the `approve` error path are.

## What this does not say

The score is for the two whole modules, not for the change this task landed. Narrowing
`paths_to_mutate` would make the number mean what the rationale says it means — and doing that
edits an authored field, so it releases the approval and needs a fresh DRI stamp. That is the
approval gate working as designed, and it is a decision for the DRI, not a cleanup.
