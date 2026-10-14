---
type: spec
task_slug: hm-eval
status: draft
created: 2026-10-14
tags: [harness-maker, spec, eval, code-quality, cost, hidden-tests, llm-judge]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
parent_spec: "[[SPEC-hm-light-lane-bench]]"
summary: "Turn the light-lane bench into an eval: plain vs /hm: on code quality first (hidden tests, lint/type deltas, a blind LLM rubric), cost second, published to docs/evals and the README"
---

# SPEC — hm-eval (plain prompt vs harness: code quality first, then cost)

## 🎯 Intent

The DRI wants one eval that shows, in numbers, how code written through the harness compares with
code written from a raw prompt: first on quality, then on what that quality costs. The eval should
be easy to re-run after a harness change, its results should live in `docs/`, and the README should
show the headline.

`scripts/bench_light_lane.py` (SPEC-hm-light-lane-bench) already runs both arms headlessly with the
same model and budget, grades hidden tests in isolation and prices every run. It measures one
thing, `hm_cost_ratio_small`, on five tasks that plain already solves 15/15. On those tasks
quality cannot differ, because both arms reach the ceiling. This SPEC builds on that runner. It
adds a harder task tier with headroom, records quality and token signals per run, prints a
scorecard that leads with quality, and publishes the scorecard as docs. The intent metric and its
pre-registered verdict keep working, computed on tier 1 only.

The eval reports what comes out. If plain writes better code than `/hm:`, the docs say so.

## 🌅 Outcomes

- `INTEGRATION=1 uv run python scripts/bench_light_lane.py run [--tier 1|2|all]` runs both arms,
  grades them, scores quality and (by default) one blind LLM-judge call per run that changed code.
  It ends by printing the scorecard.
- `uv run python scripts/bench_light_lane.py report --out DIR` reprints the scorecard offline.
  Its sections, in order: **quality** (plain vs hm per tier), **efficiency** (the cost of that
  quality), and the existing **intent-metric** block, whose last line is still
  `hm_cost_ratio_small=<ratio|n/a>`.
- `uv run python scripts/bench_light_lane.py publish --out DIR` is offline. It writes
  `docs/evals/RESULTS.md`, appends one summary row to `docs/evals/history.jsonl` (once per distinct
  results set) and rewrites the README block between `<!-- hm:eval:start -->` and
  `<!-- hm:eval:end -->` with a small plain-vs-hm headline table and a link.
- `docs/evals/README.md` (hand-written) explains what is measured, how to run it, how to read the
  scorecard, the fairness rules, and the improvement loop: change the harness, re-run, publish,
  compare against `history.jsonl`.
- Tier 2: four new tasks on the same `timeparse` fixture (t6–t9). Each one gives a careful process
  room to beat a quick fix: a bug fix with a regression trap, a change that must keep an existing
  invariant, a general contract whose edge cases the hidden tests probe, and a maintainability
  change with one source of truth. Each ships a reference that passes every hidden test, and `check`
  proves that its hidden tests discriminate. Tier 1 (t1–t5) stays the cheap smoke and cost tier.
- Nothing in the unit suite calls a model or the network.

## 📋 In-Scope Scenarios

### S1: Tier-2 tasks have headroom and still discriminate
**Given** the task directories under `scripts/bench/tasks/`, each with a `tier` file (absent means 1)
**When** `check` runs
**Then** every task's hidden tests fail on the pristine fixture (after the task's optional `seed/`
overlay) and pass on its reference, apart from the tests listed in `guards.txt`. Guards are
regression traps: they must pass on pristine and on the reference. The fixture's own visible tests
pass on both. Tier 2 holds 3–5 tasks, each covering one of: regression-trap bug fix,
invariant-keeping change, edge cases from a general contract, maintainability

### S2: Tokens are recorded per kind
**Given** a finished run
**When** the runner records it
**Then** the row carries `tokens: {input, output, cache_read, cache_write}`. Each value is summed
over the run's own main and subagent transcript turns through `harness_maker.economics`
(`cache_write` = 5m + 1h writes). The row also records `tier`

### S3: A stall is distinguishable from a wrong fix
**Given** a graded run
**When** the runner classifies it
**Then** `outcome` is `solved` (hidden tests pass), `wrong` (the code under `timeparse/` changed but
the hidden tests fail) or `stalled` (nothing under `timeparse/` changed and the tests fail). The
change is measured against the task's starting tree (fixture plus seed), not against git history.
Changes to harness files, `specs/`, `work-docs/`, `.claude/` or `CLAUDE.md` do not count as a change

### S4: Deterministic quality checks read the source diff only
**Given** a graded run whose work dir survives
**When** quality is scored
**Then** the row's `quality` holds:
- `ruff_new` and `mypy_new`: new errors in the changed `.py` files under `timeparse/` and `tests/`,
  i.e. the error count on the final files minus the count on their starting versions (a new file
  starts at 0). Ruff runs `--isolated` with a rule set pinned in the runner. mypy runs `--strict`
  on the package with an empty config, from a clean copy. A config, `conftest.py` or `pyproject.toml`
  the agent left in the work dir is never read
- `diff_lines`: added plus removed lines in that scope
- `tests_touched`: whether a file under `tests/` was added or changed
- `regressions`: the number of the fixture's pristine visible tests (from the private snapshot)
  that fail against the final package

The work dir is never modified. A check that cannot run records `null` with a reason and never
changes `status`, `passed` or `outcome`

### S5: The judge is blind, isolated and accounted separately
**Given** a run whose outcome is not `stalled` and the judge enabled (the default; `--no-judge`
turns it off)
**When** the runner judges it
**Then** it makes one `claude -p` call. The prompt goes on stdin and holds the fixed rubric, the
task prompt *without* the `/hm:spec ` prefix, and the source diff from S4's scope only. It never
contains the arm, the run dir, the rep, or any harness, `specs/`, `work-docs/` or `.claude/`
content, so two runs with the same diff produce byte-identical judge input whichever arm they come
from. The call uses `--claude-bin`, `--tools ""`, `--json-schema` for the rubric, `--model
<judge-model>`, `--setting-sources project,local --strict-mcp-config`, a per-call budget cap and an
empty temp cwd outside `--out`. Scores are four criteria, each 1–5: `scope`, `clarity`,
`maintainability`, `tests`. A non-zero exit, a timeout or output that breaks the schema records
`judge.status: error` with null scores, which are counted and never imputed. The judge's cost is
`judge.cost_usd`: it stays out of `cost_usd` and every arm mean, but counts toward
`--total-budget-usd`. The judge model, rubric text and judge argv are part of `runner_hash`

### S6: The scorecard leads with quality and keeps the intent metric
**Given** a results file
**When** `report` runs
**Then** it prints, per tier, plain vs hm, in this order:
1. Quality: runs, hidden-test all-pass rate, hidden-case pass fraction, outcome counts (solved /
   wrong / stalled), mean `ruff_new`, `mypy_new`, `regressions`, `diff_lines`, `tests_touched`
   rate, and judge means per criterion and overall, with the number of judged runs
2. Efficiency: mean cost, mean tokens per kind, turns and wall time, the hm/plain ratio of each,
   and the total judge cost
3. The existing intent-metric block, computed on **tier-1 rows only**, unchanged in rule and output

Quality means skip runs where the signal is null and show `n/a (k)` when every run lacks it.
`--json` adds a `scorecard` object beside the existing keys

### S7: Lead labels follow a fixed rule and plain can win
**Given** a scorecard
**When** each quality and efficiency line is labelled
**Then** the label is `hm`, `plain` or `tie`, set by a direction-aware rule written once in the
runner and in `docs/evals/README.md`. Pass rates, case fractions and outcome counts compare exactly.
Judge means need a gap of at least 0.25 to win. Every count error and every cost or token line
compares exactly, with lower winning. Each table carries an `n = runs per arm` caveat line. Nothing
in the report or the docs picks words by hand. A results set where plain is ahead prints `plain`

### S8: Publish writes the docs and the README block
**Given** a results dir
**When** `publish --out DIR` runs (it accepts `--docs`, default `docs/evals`, and `--readme`,
default `README.md`)
**Then** `RESULTS.md` holds the scorecard as Markdown tables, quality first. It names
`bench_hash`, `harness_sha`, `runner_hash`, model, judge model, tiers, runs per cell, and the date
range taken from the rows' `started_at`. `history.jsonl` gains one row (schema in IRR-001). The
README block between the markers is replaced with a headline table (tier-2 pass rate, judge
overall, new lint+type errors, regressions, tier-1 cost per run and ratio; columns plain | hm |
lead) and a link to `docs/evals/RESULTS.md`. README bytes outside the markers are unchanged

### S9: Publish is deterministic and idempotent
**Given** the same results dir
**When** `publish` runs twice, or on the same rows in another line order
**Then** `RESULTS.md` and the README are byte-identical each time, and `history.jsonl` holds
exactly one row for that results set (keyed by `results_digest`, a hash of the usable rows
serialised with sorted keys and sorted by (tier, task, arm, rep)). The output holds no wall-clock
time, absolute path or hostname

### S10: Publish refuses what it cannot render honestly
**Given** a README with zero or several marker pairs, a results file that mixes setups (the
existing `MixedResultsError`) or no usable rows
**When** `publish` runs
**Then** it exits 2 with a message, before writing any of the three files

### S11: Results from before this SPEC still report and publish
**Given** rows in the 2026-10-14 schema (no `tier`, `tokens`, `outcome`, `quality` or `judge`)
**When** `report` or `publish` runs
**Then** the rows count as tier 1, the outcome is derived from `passed` where it can be
(`passed: true` → solved, otherwise `n/a`), every missing signal shows `n/a`, and the intent-metric
block equals the runner's output before this SPEC

### S12: Fairness holds by construction
**Given** both arms of any task
**When** they run
**Then** the existing S3 isolation of SPEC-hm-light-lane-bench still holds (same model, budget,
turn cap, flags and fixture bytes; the only differences are the harness and the `/hm:spec `
prefix). Tier-2 prompts state the contract only and name no harness step, stage, SPEC, PLAN or
review. Task files are covered by `bench_hash`, which `RESULTS.md` and `history.jsonl` show, so
editing a task after its results splits the history visibly instead of silently

## 🚫 Non-Goals

- Taking the live measurement. The DRI runs it; this SPEC delivers the instrument, the docs
  skeleton and a seed `RESULTS.md` published from the 2026-10-14 tier-1 rows (quality `n/a`).
- Fixing the hm arm's stall after `/hm:spec` (bench 2026-10-14: 6/15). The eval has to show it,
  as `outcome: stalled`.
- Statistical tests or confidence intervals. n is printed and the tie band is fixed; anything more
  waits for data that warrants it.
- Pairwise (A/B) judging, judge ensembles, or re-judging old work dirs (a `score` backfill). Each
  run is judged alone, once.
- A second fixture, other languages, Cursor/Codex arms.
- Changing the intent metric, its target or its verdict rule.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard |
| Location | `scripts/bench_light_lane.py` (one entry), task data under `scripts/bench/tasks/`, docs under `docs/evals/` | Smallest change. The approved bench SPEC, its 15 ACs and their test ids keep their paths (PLAN ADR-001) |
| Live calls | `run` and `canary` refuse without `INTEGRATION=1`. `report`, `publish` and `check` are offline. Unit tests keep the autouse failing `claude` stub, and the judge goes through `--claude-bin` like the agent | CLAUDE.md test policy |
| Dependencies | stdlib plus existing dev dependencies (ruff and mypy are already dev deps) | No new dependency |
| Pricing and tokens | `harness_maker.economics` only | One pricing authority |
| Judging quality | An LLM rubric judges quality. Rule-based checks are limited to compiler-grade facts (lint/type error counts, line counts, test pass/fail) | CLAUDE.md LLM-judgment principle |
| Writes | `publish` writes atomically (temp + rename) and only the three named files | Implementation patterns |
| Boundaries | No edit under `src/harness_maker/templates/`, goldens, `step_sensitivity.py` or `CLAUDE.md` | Other HM-LIGHT-LANE stages edit those |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | `docs/evals/history.jsonl` row schema: one JSON object per line, sorted keys, `schema: 1`; keys `bench`, `bench_hash`, `harness_sha`, `runner_hash`, `model`, `judge_model`, `results_digest`, `date_first`, `date_last`, `runs_per_cell`, `tiers`, `metric` (`ratio`, `verdict`), and per tier and arm `runs`, `passed`, `case_pass`, `outcomes`, `mean_cost_usd`, `mean_tokens`, `mean_turns`, `mean_wall_s`, `quality` (`ruff_new`, `mypy_new`, `regressions`, `diff_lines`, `tests_touched_rate`, `judge`) plus `judge_cost_usd`. Additive only: readers ignore unknown keys, a breaking change bumps `schema` | schema/file format/storage layout | The trend history is append-only and committed; every later row and reader depends on the shape |
| IRR-002 | README marker contract: exactly one `<!-- hm:eval:start -->` / `<!-- hm:eval:end -->` pair in `README.md`. The content between them is owned by `publish`; bytes outside are never touched | public API/CLI contract | Once in the README, hand edits around it and every later publish rely on it. The name sits beside the `hm-doc-contract:*` markers without colliding with them |

The judge rubric and prompt are not irreversible: they are covered by `runner_hash`, so changing
them starts a new comparable series rather than corrupting the old one. The added `results.jsonl`
row fields are additive in a dev-only file whose readers tolerate their absence (S11).

## ✅ Verification Criteria

| Scenario | Verification mode | Test name |
|---|---|---|
| S1 | unit (subprocess pytest) | `tests/unit/test_bench_light_lane.py::test_hidden_tests_discriminate` (parametrized over every task dir), `test_tasks_ship_in_two_tiers` |
| S2 | unit (fake transcripts) | `test_tokens_are_summed_per_kind_over_main_and_subagent_turns` |
| S3 | unit (golden work dirs) | `test_outcome_tells_a_stall_from_a_wrong_fix` |
| S4 | unit (golden work dirs) | `test_quality_checks_count_new_errors_on_the_source_diff_only` |
| S5 | unit (fake claude) | `test_judge_input_is_blind_to_the_arm`, `test_judge_argv_is_isolated_and_schema_bound`, `test_judge_failure_is_recorded_not_imputed`, `test_judge_cost_stays_out_of_the_arm_cost`, `test_no_judge_and_stalled_runs_make_no_judge_call` |
| S6 | unit (golden rows) | `test_scorecard_leads_with_quality_and_keeps_the_metric_line`, `test_intent_metric_ignores_tier_two_rows` |
| S7 | unit (golden rows) | `test_lead_labels_follow_the_fixed_rule_and_plain_can_win` |
| S8 | unit (golden rows → golden files) | `test_publish_writes_results_history_and_readme_block` |
| S9 | unit (property) | `test_publish_is_idempotent_and_order_independent` |
| S10 | unit | `test_publish_refuses_bad_markers_mixed_or_empty_results` |
| S11 | unit (2026-10-14 rows) | `test_pre_eval_rows_report_and_publish_with_na` |
| S12 | unit | `test_arms_differ_only_by_harness_and_prefix` (existing), `test_tier_two_prompts_name_no_harness_step` |
| Outcome (docs) | unit | `test_docs_readme_explains_every_scorecard_metric` |

### AC-001: Tier-2 tasks ship and their hidden tests discriminate
### AC-002: Rows record tokens per kind from the run's own transcripts
### AC-003: The outcome tells a stall from a wrong fix
### AC-004: Deterministic quality checks count new errors on the source diff only
### AC-005: The judge input is blind to the arm
### AC-006: The judge call is isolated, schema-bound and accounted separately
### AC-007: The scorecard leads with quality and keeps the intent-metric line
### AC-008: The intent metric is computed on tier-1 rows only
### AC-009: Lead labels follow a fixed rule and report plain when plain is ahead
### AC-010: Publish writes RESULTS.md, one history row and the README block
### AC-011: Publish is idempotent and independent of row order
### AC-012: Publish refuses bad markers, mixed or empty results before writing
### AC-013: Pre-eval results still report and publish with n/a
### AC-014: Tier-2 prompts name no harness step
### AC-015: docs/evals/README.md explains every scorecard metric

## ❓ Open Questions

- Judge model. The default is the agent model (`claude-sonnet-5-5`), so one model family does both
  writing and judging. A stronger fixed judge (an Opus model) would reduce self-preference but
  cost more per run. Either way it is pinned in `runner_hash`; the DRI picks.
- `--total-budget-usd` default: 40 fits tier 1 only (2026-10-14: $11.48). `--tier all` with the
  judge on likely needs about $60–80. Proposed: raise the default to 80 and keep `--tier 1` for
  cost-only re-runs.
- Should `RESULTS.md` also carry a trend table from `history.jsonl`? That makes it a function of
  two inputs instead of one. Proposed: no; `docs/evals/README.md` shows a one-line `jq` for the
  trend.
- `README.ko.md` gets no eval block (the doc-contract test lets localized prose differ). Add one
  later if the DRI wants parity.

## 🔍 Refinement Decisions

- Interview not run. Scope comes from the DRI's two messages (2026-10-14): (1) formalise token
  efficiency, problem solving and code quality, keep it in the codebase, publish it to docs and the
  README; (2) lead with how the harness's code quality compares to a raw prompt, add harder tasks
  with headroom, make fairness an AC.
- Three dimensions over one task suite: efficiency (tokens per kind, cost, turns, wall, hm/plain
  ratios), problem solving (hidden all-pass, case fraction, solved/wrong/stalled), and quality
  (ruff/mypy new-error deltas, regressions, diff size, tests touched, blind LLM rubric). The judge
  is on by default and `--no-judge` turns it off. Judge cost is reported separately and excluded
  from arm cost.
- Quality is the headline (DRI message 2); efficiency is shown as the price of that quality.
- Tier 2 added (DRI message 2 overrides the earlier "tasks stay five" default): four tasks on the
  existing fixture, so no new fixture. An optional per-task `seed/` overlay allows the bug-fix
  task. Tier 1 is unchanged and stays the only input to `hm_cost_ratio_small`, whose
  `how_measured` names the five small tasks.
- Error checks count *new* errors against the task's starting files, so a fixture blemish never
  counts against either arm. The fixture is ruff- and `mypy --strict`-clean today (checked
  2026-10-14).
- The judge sees only `timeparse/` and `tests/` diffs. The hm arm's SPEC/PLAN files would reveal
  the arm, and the user asked to judge code, not process.
- Stalled runs are not judged: an empty diff has nothing to judge, and the call would cost money
  to produce an uninformative score.
- Commands: `run`, `report`, `publish` (plus the existing `check`, `canary`) on the existing
  script, not a renamed `scripts/eval.py` (PLAN ADR-001).
- `publish` output is a pure function of the results dir (plus the README bytes outside the
  markers and the prior `history.jsonl`, which it only appends to), so tests can golden it.
- Lead labels use a fixed, documented rule (tie band 0.25 on 1–5 judge means), so the docs can show
  plain ahead without anyone choosing words.
- Lane `full`: about fifteen files plus four task dirs, and two irreversible decisions.
