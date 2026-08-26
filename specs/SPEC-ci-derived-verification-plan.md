---
type: spec
task_slug: ci-derived-verification-plan
status: approved
created: 2026-08-26
tier: 2
tags: [harness-maker, spec, python, verification, ci, stages, gates]
test_framework: pytest
summary: "Derive the stages' verification commands from the project's own CI instead of shipping example commands that silently narrow the local gate"
---

# SPEC — CI-derived verification plan

## 🎯 Intent

Every stage that tells the agent to "run the project's check suite" ships an **example**:
`mypy --strict src/`, `ruff check src/ tests/`, `pytest -q`. An example is a guess about
someone else's repository, and the dangerous direction of that guess is **narrowing** —
a local pass that goes green over a subset while CI fails on the rest. Narrowing is
invisible by construction: nothing in the local run mentions what it did not check.

The trigger is self-inflicted and measured. This harness's own stages prescribe
`mypy --strict src/` while its `ci.yml` runs `mypy --strict src tests`. Every type error
in `tests/` was therefore structurally unreachable from the local gate, and two consecutive
commits (`bd61ab57`, `12253460`) shipped red CI through it — the second built on the first
because the first's CI result was never read. Six errors, all in test code, all invisible
to a passing local verification.

The same shape sits in the neighbouring advice. `hm test_runners plan` already tells the
reader to "read the project's CI selection and mirror it", and names `-m "not advisory"`
for this harness — but `ci.yml`'s Pytest step carries no `-m` filter at all. Advice that is
prose drifts from the config it describes and nothing notices.

So the plan is **derived, not guessed**: read the project's CI, report what it actually
runs, and have the stages run that.

## 🌅 Outcomes

After this change:

1. `/hm:verify` and `/hm:wrapup` run the gate commands **the project's CI actually runs**,
   so a local pass and a CI pass can no longer disagree about which files were checked.
2. A project with no CI, unreadable CI, or CI containing no recognisable verification tool
   gets an **explicit degraded verdict with a reason**, and the stage falls back to its
   example commands *knowing* it is guessing — an empty result never reads as "clean".
3. A command CI runs that the harness cannot classify is **reported**, not dropped. So is a
   blocking CI command the stage deliberately does not run locally.
4. An **advisory** CI step (`continue-on-error: true`) never becomes a blocking local gate,
   so third-party drift is not reported as a failure of the user's change.

## 📋 In-Scope Scenarios

### S1: The derived type gate is not narrower than CI's

**Given** a repository whose CI runs `mypy --strict src tests`
**When** the verification plan is derived from that CI
**Then** the derived type command covers `tests` as well as `src`
**And** it is byte-identical to a command the CI job actually runs

### S2: An advisory CI step does not become a blocking local gate

**Given** a CI workflow with a step marked `continue-on-error: true`
**When** the plan is derived
**Then** that step's command is reported with `blocking: false`
**And** it is absent from the commands the stage is told to run

### S3: An unrunnable or absent CI degrades explicitly

**Given** a project with no `.github/workflows`, or with unparseable YAML, or whose gating
workflow contains no recognised verification tool
**When** the plan is derived
**Then** `degraded` is true and `reason` is a non-empty string naming the cause
**And** the command list is empty rather than partially populated

### S4: Nothing is dropped silently

**Given** a CI job containing setup commands alongside verification commands
**When** the plan is derived
**Then** each unrecognised command appears in `unclassified` with its command text, its
originating step, and a reason
**And** every blocking CI command not selected for local execution is listed separately

## 🚫 Non-Goals

- **CI systems other than GitHub Actions.** GitLab CI, CircleCI and Jenkins are out of
  scope. They degrade to the existing example commands, which is the status quo, not a
  regression.
- **Mirroring CI wholesale.** Running every blocking CI command locally imports CI's
  environment with it — this repo has a blocking job that `npm install -g`s an external CLI
  first, and running its tests on a machine without that CLI would report third-party
  absence as a failure of the user's change. The selection stays inside the tool kinds the
  stage would otherwise have guessed; the remainder is reported, not run.
- **Executing the commands from Python.** The module reports; the stage runs. A helper that
  shells out to the project's whole test suite is a different and much larger safety surface.
- **Correcting `test_runners`' stale `-m "not advisory"` note.** Real and confirmed above,
  but it is a separate module with its own consumers.
- **The `ci.yml` inconsistency it points at** — the measurement comment cites
  `-m "not advisory"` while the shipped Pytest step has no filter. Recorded here so the
  observation is not lost; changing CI's own selection is not this SPEC's business.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo-wide; `harness.yaml.toolchains[python].commands.test`. |
| Language | Python 3.12+, no Bash | CLAUDE.md "Runtime / Tooling". |
| No shell-out | Parsing only | The module reads YAML. It must never execute a command it found in CI — that would run arbitrary shell out of a config file. |
| Never raises | Degraded result instead | A missing or malformed CI is a legitimate state with a legitimate fallback; an exception would turn it into a stage failure. |
| YAML 1.1 `on:` | Must handle the boolean key | `safe_load` yields `True`, not `"on"`. Reading `"on"` makes every workflow non-gating and the plan silently empty. |
| Surface budget | Net-neutral or negative | `test_command_size_budget` ratchets the per-turn-injected command surface; the template edit replaces example blocks with one call. |

## ✅ Verification Criteria

| Scenario | AC | Verification mode | Test name / manual step |
|---|---|---|---|
| S1 | AC-001 | unit (differential vs real `ci.yml`) | `test_primary_commands_match_this_repos_actual_quality_gate`, `test_derived_type_gate_covers_tests_dir_like_ci_does` |
| S2 | AC-002 | unit | `test_continue_on_error_step_is_non_blocking`, `test_job_level_continue_on_error_applies_to_its_steps` |
| S3 | AC-003 | unit | `test_no_workflows_directory_is_degraded_with_a_reason`, `test_malformed_yaml_names_the_file_and_degrades`, `test_gating_workflow_with_no_recognised_tool_is_degraded` |
| S4 | AC-004 | unit | `test_unrecognised_commands_are_reported_with_a_reason`, `test_environment_heavy_ci_jobs_are_reported_not_run` |

All four are exercised by `tests/unit/test_verification_plan.py`.

### AC-001: The derived gate is not narrower than CI's

For each verification tool the project's commit-gating CI runs, the derived plan contains a
command byte-identical to one that CI job runs, and no tool CI gates on is omitted.

The anchor test is a **differential against this repository's own `ci.yml`**, reading the
job's steps rather than restating them. A hand-written fixture shaped like what the author
assumes CI looks like is exactly what let the original divergence ship: the assumption and
the reality were never compared.

### AC-002: An advisory step is reported as non-blocking

A step or job carrying `continue-on-error: true` yields `blocking: false`, and its command
is excluded from the commands the stage runs.

### AC-003: Absent, unreadable, or gate-less CI degrades with a reason

Each of the three cases yields `degraded: true`, a non-empty `reason`, and an empty command
list. An unparseable workflow's reason names the file.

### AC-004: Nothing is dropped in silence

Every command in a gating workflow's `run:` step that is not classified as a gate appears in
`unclassified` with its text, step name, and reason. Every blocking CI command outside the
selection appears in the additional list.

## ❓ Open Questions

None.

## 🔍 Refinement Decisions

- **Scope** — chosen over two cheaper alternatives: point-fixing the five templates' example
  commands (still a guess for consuming projects, closes nothing), and detecting the
  divergence advisorily (visible, but a human still has to act on every occurrence).
- **One command per tool kind, not every blocking CI command** — see Non-Goals. The
  remainder is reported rather than hidden, so the narrowing this SPEC fixes is not
  reintroduced in a new place.
- **`ruff check` and `ruff format --check` are different kinds** — they share a binary, so
  keying on the head token alone collapses them and the format gate disappears behind the
  lint one. That is the same narrowing in miniature.
