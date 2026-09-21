---
type: mutation
task_slug: dev-mode-removal
spec: "[[SPEC-dev-mode-removal]]"
tier: 1
threshold: 85
date: 2026-09-21
mutants: 19
killed: 18
equivalent: 1
score: 100
runner: targeted (hand-authored mutants)
---

# MUTATION — dev-mode-removal (tier 1)

## Why the mutants are hand-authored

`hm spec_mutation gate --tier 1` runs mutmut over the SPEC's `paths_to_mutate`, one of which is
`models.py` (~1500 lines of declarative pydantic fields). Without `--runner` mutmut runs the
WHOLE suite per mutant, which the CLI's own help says exceeds this repo's wall budget on the
first mutant; with a narrow runner the models.py mutants are uncovered by construction and would
report as survivors that no assertion could ever kill. `--sampled` is a recorded defect in this
repo (`[fail:tooling] sampled-flag-measures-nothing`: the flag appends `--use-coverage`, no
coverage file exists, mutmut dies, and the gate prints `T3 is informational` with `rc=0`).

So the run below is targeted at the LOGIC this change introduced, which is what the tier-1
threshold is protecting. It also covers `src/harness_maker/strictness.py`, which the SPEC's
`paths_to_mutate` does not name — an omission in the SPEC, since it is the new module. Covering
more than the contract demands is not a contract violation, so the approved SPEC is unchanged.

Every mutant was applied to the real source, run against the 14 test files listed below, and
reverted; the five `paths_to_mutate` files were `sha256sum -c`-verified unchanged afterwards
(`[fail:tooling] mutation-gate-timeout-leaves-source-mutated-on-disk`, a recurrence this repo
has already paid for once).

Runner: `pytest -x -q` over `test_strictness_reader_singleton`, `test_dev_mode_migration`,
`test_strictness_absent_case`, `test_dev_mode_retired`, `test_render_strictness_surface`,
`test_dev_mode_cli_flag_removed`, `test_spec_machine_waiver`, `test_spec_quality`,
`test_spec_quality_oracle`, `test_spec_gate`, `test_spec_need`,
`test_readiness_waiver_render_drift`, `test_retired_key_migration`, `test_interview`.

## Result

**18 killed / 18 non-equivalent = 100 %** (threshold 85). One equivalent, excluded from the
denominator with the reason below — the exclusion set did not exist before this run.

| # | Mutant | Verdict |
|---|---|---|
| M01 | `PRESET_DEFAULT` Production → `warn` | killed |
| M02 | `PRESET_DEFAULT` Side → `block` | killed |
| M03 | absent preset defaults to Production | killed **after strengthening** |
| M04 | malformed strictness falls through to the preset default | killed **after strengthening** |
| M05 | malformed strictness accepted verbatim | killed |
| M06 | unrecognised preset relaxes instead of failing closed | killed **after strengthening** |
| M07 | `explicit_strictness` calls every config explicit | killed |
| M08 | `write_strictness` ignores its argument | killed |
| M09 | translation table swapped (`spec-driven`→`warn`) | killed |
| M10 | migration never runs | killed |
| M11 | an explicit `spec.strictness` is overwritten by the legacy key | killed |
| M12 | an unknown legacy value relaxes instead of failing closed | killed |
| M13 | the migration advisory repeats on every load | killed |
| M14 | hook guard inverted (`!= "warn"`) | killed |
| M15 | hook drops its unreadable-config clause | **equivalent** |
| M16 | verify oracle relaxes at `block` | killed |
| M17 | verify oracle aligned to the general resolver | killed |
| M18 | quality gate normalises everything to `warn` | killed |
| M19 | quality gate blocks at `warn` | killed |

## The three survivors of the first run were real gaps, and were closed

The first run scored **15/18 = 83.3 %**, below the threshold. Per the gate's own rule the
assertions were strengthened rather than the threshold lowered:

- **M03 / M06** — nothing exercised a config whose `preset` is absent or unrecognised. Added
  `test_ac_003_a_config_with_no_preset_uses_the_model_default` (pins that `{}` resolves the way
  `HarnessConfig()` would, and asserts the model default it tracks) and
  `test_ac_003_an_unrecognised_preset_fails_closed` (block, and the refusal names the value).
- **M15** — nothing exercised `spec_gate` against an unreadable config. Added the `unreadable`
  case to `test_ac_006_hook_guard_reads_strictness`. The mutant still survives, which is the
  finding below.

## The one equivalent mutant, and what it says

`gates/spec_gate.py` guards with `if not cfg or resolve_strictness(cfg) != "block"`. Deleting
`not cfg or` changes no behaviour **today**: an unreadable config is loaded as `{}`, and `{}`
carries no preset, so the resolver returns the model default preset's value — Side → `warn` —
and the gate stands aside either way.

The clause is kept anyway, and this is recorded rather than deleted as dead code: it is the
explicit statement of the advisory fail-open, and its redundancy depends entirely on the model
default preset being `Side`. A future flip of that default would silently turn "your harness.yaml
does not parse" into "every test write is refused". The sibling test
`test_atomic_command_fallback_pins_block_strictness` exists because exactly that kind of default
is load-bearing elsewhere. Exclusion rule-id: `guard-redundant-only-under-current-default`.
