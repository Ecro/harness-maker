---
type: spec
task_slug: hm-light-lane-bench
status: draft
created: 2026-10-14
tags: [harness-maker, spec, bench, cost, hidden-tests]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 4 of HM-LIGHT-LANE: a repo bench runner (fixture, hidden tests, plain/hm arms) that prints hm_cost_ratio_small"
---

# SPEC — hm-light-lane-bench (stage 4, runner only)

## 🎯 Intent

Intent HM-LIGHT-LANE is judged by `hm_cost_ratio_small`: the mean cost of an `/hm:` run divided by
the mean cost of a plain run on small single-session tasks, with the counter-signal that the
`/hm:` arm's hidden-test pass rate must not fall below plain. The ×22 baseline came from a bench
whose fixture, hidden tests and runner lived in a session scratchpad and are gone
(`work-docs/RESEARCH-hm-light-lane.md`). The intent's own rule says that without a runner in the
repo the metric is `no_data`. This SPEC puts the runner in the repo. The measurement itself waits
for stages 2b and 3; this SPEC delivers the instrument, not the number.

## 🌅 Outcomes

- One command, `INTEGRATION=1 uv run python scripts/bench_light_lane.py run`, runs both arms over
  every task fixture headlessly. It prints per-task pass and cost, the ratio, both pass rates, the
  pre-registered verdict and a ready `hm intent metric record hm_cost_ratio_small …` command.
- `uv run python scripts/bench_light_lane.py report --out DIR` reprints that summary from the
  results file with no model call. `check` proves offline that the fixture can tell a fix from no
  fix.
- Five tasks on a reconstructed `timeparse` fixture (t1 `format_duration(max_units)`, t2 atomic
  `store.py`, t3 ISO-8601 durations, t4 CLI `--sum` and stdin `-`, t5 token-bucket rate limiter)
  ship with hidden tests and a reference solution each, mirroring the 2026-10-14 bench. Hidden
  test files: `scripts/bench/tasks/t1/hidden/test_t1_max_units.py`,
  `scripts/bench/tasks/t2/hidden/test_t2_store.py`, `scripts/bench/tasks/t3/hidden/test_t3_iso.py`,
  `scripts/bench/tasks/t4/hidden/test_t4_cli.py`, `scripts/bench/tasks/t5/hidden/test_t5_ratelimit.py`.
- Nothing in the unit suite calls a model or the network.

## 📋 In-Scope Scenarios

### S1: Live runs need an explicit opt-in
**Given** `INTEGRATION` is not `1` in the environment
**When** the operator runs `scripts/bench_light_lane.py run`
**Then** it exits 2 with a message naming `INTEGRATION=1`, before any copy, render or agent call

### S2: Hidden tests discriminate
**Given** a task's hidden tests and its reference overlay
**When** `check` grades a pristine fixture copy and a copy with the reference applied
**Then** the pristine copy fails at least one hidden test, the reference copy passes all of them,
and the fixture's own visible tests pass on both

### S3: The arms differ only by the harness and the `/hm:spec ` prefix
**Given** one task run in both arms
**When** the agent process starts
**Then** both work dirs are clean git repos holding the fixture, the hm work dir additionally holds
the harness rendered by this checkout (Side preset, Claude Code only, `autonomy.level: auto_full`),
the hm prompt is the plain prompt prefixed with `/hm:spec `, every other agent flag is the same,
and no hidden test or reference file exists in either work dir

### S4: Cost is read per run, subagents included
**Given** a finished run
**When** the runner records it
**Then** `cost_usd` is the CLI result's `total_cost_usd`, `transcript_cost_usd` prices every main
and subagent transcript turn of that run's work dir through `harness_maker.economics`, and a run
whose CLI result has no cost (timeout, crash) falls back to the transcript price with
`cost_source: transcript`

### S5: Grading is strict and isolated
**Given** a work dir after the agent ends
**When** the runner grades it
**Then** the hidden tests run outside the work dir with only `PYTHONPATH` pointing at it, a
collection error counts as a failure, a `conftest.py` the agent left in the work dir is not loaded,
and the run passes only when every hidden test passes

### S6: The report applies the pre-registered rule
**Given** a results file
**When** `report` runs
**Then** the ratio is mean hm cost per run over mean plain cost per run, setup failures are left
out, and the verdict is `met` (ratio ≤ 5 and hm pass rate ≥ plain), `missed` (ratio > 5, or hm pass
rate < plain) or `no_data` (an arm has no runs, or the task × arm grid is unbalanced)

### S7: The record command is ready to paste
**Given** a report with a ratio
**When** it is printed
**Then** it contains an `hm intent metric record hm_cost_ratio_small --value <ratio> --evidence …`
line that `hm intent`'s own parser accepts, whose evidence names the bench hash, the harness SHA,
the model, both mean costs and both pass counts, and the last printed line is
`hm_cost_ratio_small=<ratio>`

### S8: Interrupted runs resume, mixed results are refused
**Given** a results file from an interrupted run
**When** `run` is started again with the same `--out`
**Then** completed (task, arm, rep) cells are skipped and setup failures are retried
**And** `report` refuses (exit 2) a results file whose rows carry more than one bench hash or
harness SHA

### S9: The output dir cannot inherit project context
**Given** an `--out` dir inside a git work tree or below a `CLAUDE.md`
**When** `run` starts
**Then** it exits 2, because Claude Code would load that context into both arms

## 🚫 Non-Goals

- Taking the measurement or recording the metric. That happens after stages 2b and 3 land.
- Reproducing the lost fixture byte for byte. The reconstruction keeps the five task shapes and
  their traps; both arms are re-measured on it, so the ratio does not depend on the old bytes.
- The `tasklog` fixture of run 3 (plain only, no hm arm) and Cursor/Codex arms (intent
  out-of-scope).
- Wiring a `measure:` block into `.claude/intent.yaml`: `hm intent metric measure --all` would then
  launch a ~$35 live bench.
- Parallel scheduling beyond a plain `--jobs N` thread pool.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Location | `scripts/bench_light_lane.py` and data under `scripts/bench/` | Dev-only tool; `src/` ships in the wheel and `tests/` is collected, so hidden `test_*.py` there would run in CI and fail on purpose |
| Live calls | `run` refuses without `INTEGRATION=1`; `check`, `report` and unit tests are offline | CLAUDE.md test policy |
| Dependencies | stdlib plus what harness-maker already depends on | PLAN constraint: no new runtime dependency |
| Pricing | `harness_maker.economics` is the only price table | One pricing authority in the repo |
| Model | `--model` defaults to `claude-sonnet-5-5`, the baseline's model | TUNE rule: no transfer across models without re-measure |
| Boundaries | No edit under `src/harness_maker/templates/`, `synthesize.py`, `step_sensitivity.py`, goldens or `CLAUDE.md` | Stages 2a/2b/3 edit those concurrently |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| (none) | — | — | A dev-only script and fixture; no shipped schema, CLI, migration, permission or dependency change |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name |
|---|---|---|
| S1 | unit (subprocess) | `tests/unit/test_bench_light_lane.py::test_run_refuses_without_integration` |
| S2 | unit (subprocess pytest) | `tests/unit/test_bench_light_lane.py::test_hidden_tests_discriminate`, `test_five_tasks_ship` |
| S3 | unit (fake agent) | `tests/unit/test_bench_light_lane.py::test_arms_differ_only_by_harness_and_prefix` |
| S4 | unit (fake transcripts) | `tests/unit/test_bench_light_lane.py::test_cost_comes_from_cli_and_transcripts`, `test_cli_result_is_parsed_from_the_last_result_line` |
| S5 | unit (subprocess pytest) | `tests/unit/test_bench_light_lane.py::test_grading_is_strict_and_isolated` |
| S6 | unit (golden table) | `tests/unit/test_bench_light_lane.py::test_report_verdict` |
| S7 | unit | `tests/unit/test_bench_light_lane.py::test_record_command_parses`, `test_no_ratio_prints_no_record_command` |
| Constraint (target) | unit | `tests/unit/test_bench_light_lane.py::test_target_matches_the_intent_metric` |
| S8 | unit | `test_resume_skips_completed_cells`, `test_report_refuses_mixed_results` |
| Outcome (one command) | e2e (subprocess, fake agent) | `tests/unit/test_bench_light_lane.py::test_offline_end_to_end_run`, `test_report_reprints_without_a_model` |
| S9 | unit | `tests/unit/test_bench_light_lane.py::test_out_dir_with_project_context_is_refused` |

### AC-001: Live runs refuse without INTEGRATION=1
### AC-002: Every task's hidden tests discriminate fix from no fix
### AC-003: The arms differ only by the harness and the prefix
### AC-004: Cost comes from the CLI result with a transcript cross-check
### AC-005: Grading is strict and isolated from the work dir
### AC-006: The report applies the pre-registered verdict rule
### AC-007: The printed record command parses
### AC-008: The verdict target matches the intent metric
### AC-009: Runs resume and mixed results are refused
### AC-010: One offline command runs both arms end to end
### AC-011: An output dir with project context is refused

## ❓ Open Questions

- Does `total_cost_usd` in `claude -p --output-format json` include subagent spend in the current
  CLI? The runner records the transcript price beside it and the report prints both ratios, so a
  gap shows up in the first live run instead of being assumed away.

## 🔍 Refinement Decisions

- Interview not run: scope is item 4 of `work-docs/PLAN-hm-light-lane.md` and the intent's
  `how_measured` (three runs per task and arm, headless, mean over mean, pass-rate counter-signal),
  both already approved by the DRI.
- Lane `full`: about twenty files (fixture, five tasks, runner, tests), over the light lane's five.
  The irreversible-decision list is empty.
- The fixture is reconstructed from the task table in the RESEARCH doc and the bench notes; the
  task wording now states each trap's required behaviour with an example so the hidden tests test
  the stated contract, not a guess.
- Mean over all runs per arm, failed runs included, as in the baseline ($1.53 for t2 counts the two
  A.5 self-blocks). Setup failures are the runner's fault and are excluded and retried.
- Work stays on the session's designated branch, as in stages 1 and 2a.
