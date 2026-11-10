---
type: spec
task_slug: dead-modules
status: approved
created: 2026-11-10
tags: [harness-maker, spec, overhaul-phase-2, deletion]
test_framework: pytest
interview_rounds: 0
summary: "Overhaul phase 2, slice 2: delete the harness_maker modules that no shipped entry point reaches (about 7k LOC) and the tests that only test them."
---

# SPEC — dead-modules (overhaul phase 2, slice 2)

## Intent

RESEARCH-hm-non-token-improvements F7 found about 30 modules that only tests import. Slice 1
(SPEC-retired-wiring) removed the rendered wiring of the retired loop. This slice deletes the code
that no shipped entry point reaches, so the source a maintainer reads is the source that runs.
The DRI asked on 2026-11-10 for phase 2 to proceed on the recommended option.

Reachability was measured, not assumed. The roots are the `harness-maker` and `hm` console scripts
(`cli`, `hm`, `__main__`), every `harness_maker.<module>` or `hm <module>` string in
`src/harness_maker/templates/`, the plugin bundle (`hooks/`, `skills/`, `commands/`, `agents/`,
both plugin manifests) and `scripts/`. The closure follows every `import` (top-level and lazy) and
every `harness_maker.<module>` string constant in reached modules. The `hm` allowlist and
`command_registry` are not roots: they list names, they do not call them.

## Outcomes

- O1. The modules in AC-001 are gone, and nothing in `src/` imports or registers them.
- O2. Modules that look unreachable but have a reason to stay are kept, and the reason is written
  here: `permission_syntax` (the independent oracle that the allow/deny prune tests check
  `render` against), `release_identity` and `documentation_contract` (`release.yml` runs them),
  `test_runners` (CI runs it), `step_sensitivity` and `surface_allowance` (structural checks that
  are test-only by design, CLAUDE.md "Step sensitivity classes"), and package `__init__` files.
- O3. Tests that test only a deleted module are deleted with it. A test file that also tests live
  code keeps its live tests.

## In-Scope Scenarios

- **S1 (normal).** Given the deleted list, When `src/harness_maker` is listed, Then none of them
  exists, and neither `hm._DISPATCHABLE` nor `command_registry` names them.
- **S2 (failure guard).** Given the live entry points, When the full suite and `hm check` run,
  Then they pass: no shipped path imported a deleted module.
- **S3 (edge).** Given a kept module from O2, When the suite runs, Then its tests still run.

## Non-Goals

- No deletion of a reachable module, even a large one (`spec_need`, autopilot modules).
- No CLI command removal (`harness-maker autopilot`, `verify`) and no `harness.yaml` key removal.
  They change a public CLI and a file format, and come in a later slice.
- No change to what `make` renders. The deleted `foreign-configs` templates were rendered only
  by `foreign_config`, which no shipped path calls.
- Fixture files under `tests/fixtures/` that quote old renders are data and stay.

## Constraints

| Constraint | Value | Source |
|---|---|---|
| Test framework | pytest (mandatory) | CLAUDE.md |
| Evidence | each deleted module is outside the static closure of the shipped roots | RESEARCH F7 pitfall |
| Rendered surface | unchanged (snapshots must not move) | this SPEC |

## Irreversible Decisions

None. Everything deleted is internal to this repository, reachable by no shipped path, and
restorable from git.

## Acceptance Criteria

### AC-001: the unreachable modules are deleted and unregistered
None of these exists under `src/harness_maker/`: `codex_user_config`, `common_ground`, `eig`,
`foreign_config`, `high_diff`, `inequality_gate`, `lens_coverage`, `mutation_receipt`,
`plan_rounds`, `plan_verify`, `provenance`, `review_consensus`, `review_run`, `review_telemetry`,
`test_dep_map`, `tool_cascade`, the `spec_inventory` package, and
`observability/{coverage_classifier,intent_miss,spec_drift}`. No module in `src/` imports one,
and neither `hm._DISPATCHABLE` nor `command_registry` names one. `templates/foreign-configs/`,
which only `foreign_config` rendered, is gone too.

### AC-002: the kept look-alikes stay
`permission_syntax`, `release_identity`, `documentation_contract`, `test_runners`,
`step_sensitivity` and `surface_allowance` still exist and import.

### AC-003: the shipped roots reach no deleted module
The static closure of the shipped roots (as defined under Intent) contains no AC-001 module and
contains every remaining module except the AC-002 set and package `__init__` files.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit | `tests/structural/test_dead_modules.py` (AC-001) |
| S3 | unit | `tests/structural/test_dead_modules.py` (AC-002) |
| S2 | structural + suite | `tests/structural/test_dead_modules.py` (AC-003), then the full suite |

## Open Questions

None.

## Refinement Decisions

- The interview was skipped. The DRI told this thread not to ask and to follow the recommended
  option. There is no irreversible decision, so the SPEC is stamped `--exempt`.
- AC-003 makes the reachability argument a standing check, so a later module that nothing
  reaches fails CI instead of waiting for the next audit. A module that must stay test-only joins
  the AC-002 set with its reason.
- Retired CLI commands and `harness.yaml` keys are a separate slice, because each changes a
  public contract and needs its own deprecation path.
