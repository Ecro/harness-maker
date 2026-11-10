---
type: spec
task_slug: hide-retired-cli
status: approved
created: 2026-11-10
tags: [harness-maker, spec, overhaul-phase-2, cli]
test_framework: pytest
interview_rounds: 0
summary: "Overhaul phase 2, slice 3: hide the retired `autopilot` and `verify` commands and the `--autonomy-persistent` flag from help, mark them retired in their own help, and correct the `--autonomy-level` help."
---

# SPEC — hide-retired-cli (overhaul phase 2, slice 3)

## Intent

0.64.0 retired `/hm:verify` (now `hm check`) and autopilot, but `harness-maker --help` still offers
`autopilot` and `verify`, and `make --help` still offers `--autonomy-persistent` (RESEARCH F7). A
user reading help is told to use features that no rendered command uses. This slice hides them and
marks them retired in their own `--help`. It does not delete them: a script that calls them keeps working, and the
`harness.yaml` keys behind them stay under SPEC-hm-overhaul-p1 IRR-006 (the schema keeps every key
and a re-render keeps its value), which only the DRI can reverse.

## Outcomes

- O1. `harness-maker --help` lists neither `autopilot` nor `verify`; `make --help` does not list
  `--autonomy-persistent`.
- O2. `harness-maker verify --help` and `autopilot --help` open with "Retired in 0.64.0" and what
  replaces it. Running them behaves exactly as before: no notice on any stream, because callers
  parse their output (a stderr notice broke `test_autopilot`'s JSON read of the mixed output).
- O3. `--autonomy-level` help lists the real values (`ask | gated | auto_safe | auto_full`) and says
  what the level still controls: only `auto_full` lets the spec stage stamp a SPEC, and execute and
  `hm check` proceed on an unstamped one, without asking.

## In-Scope Scenarios

- **S1 (normal).** Given `harness-maker --help`, When it prints, Then `autopilot` and `verify` are
  absent and `make`, `health` and `remove` are present.
- **S2 (edge).** Given `harness-maker verify --help` or `autopilot --help`, When it runs, Then it
  exits 0 (the command still exists).
- **S3 (normal).** Given `harness-maker autopilot --help`, When it prints, Then it says the command
  is retired.

## Non-Goals

- No `harness.yaml` key removal (IRR-006 of SPEC-hm-overhaul-p1 stays).
- No deletion of the `autopilot` or `verify` modules or commands.

## Constraints

| Constraint | Value | Source |
|---|---|---|
| Test framework | pytest (mandatory) | CLAUDE.md |
| Behaviour | each hidden command and flag behaves exactly as before, apart from the stderr notice | this SPEC |

## Irreversible Decisions

None. Hiding is a help-text change; the commands, flags and keys all keep working.

## Acceptance Criteria

### AC-001: retired commands and the persistence flag leave help, keep working, and say they are retired
`harness-maker --help` names neither `autopilot` nor `verify`; `harness-maker make --help` does not
name `--autonomy-persistent`; `harness-maker verify --help` and `autopilot --help` exit 0 and say
"Retired in 0.64.0"; the `--autonomy-level` help names `auto_full` and no longer says "Autopilot
auto-advance".

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1, S2, S3 | unit (CliRunner) | `tests/unit/test_hide_retired_cli.py` (AC-001) |

## Open Questions

None.

## Refinement Decisions

- Skipped the interview: one file, acceptance obvious, no contract change (the commands still run),
  reversible in minutes. The DRI also told this thread not to ask.
- The `harness.yaml` key diet planned for this slice is dropped: removing or no longer rendering
  `loop` and `autonomy.{pipeline,step_cap,time_cap_min,autopilot_persistent}` would reverse
  IRR-006, a DRI lock. Of these, `loop.enabled` and `autonomy.autopilot_persistent` already warn
  once per `make` (`inert_keys`).
