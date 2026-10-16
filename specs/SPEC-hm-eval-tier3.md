---
type: spec
task_slug: hm-eval-tier3
status: draft
created: 2026-10-15
tags: [harness-maker, spec, eval, hidden-tests, multi-session, fairness]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[DESIGN-hm-eval-tier3]]"
parent_spec: "[[SPEC-hm-eval]]"
summary: "Tier 3 of the hm eval: nine tasks whose prompts do not hold the answer (ambiguous asks, hidden cross-file callers, multi-session state, one guard), a sequential multi-session runner, plain-only pilot, and a pre-registered decision rule"
---

# SPEC — hm-eval-tier3 (tasks plain fails, without telling plain the answer)

## 🎯 Intent

Plain solves 36/36 runs of tiers 1-2 at about a twentieth of hm's cost (bench `569e17ef29ab`).
Tier-2 prompts state every case their hidden tests check, so those tiers measure following
written instructions. Tier 3 asks whether hm buys anything when the prompt does **not** hold
the answer. If it does not, the DRI's plan applies: drop the quality claim and slim hm to state
and approval. Tier 3 therefore has to be fair to plain, and its decision rule is fixed here,
before anything is measured.

Design: `work-docs/DESIGN-hm-eval-tier3.md`, approved by the DRI on 2026-10-15 with one change:
B3's Arabic-Indic digit case is dropped, so B3's oracle covers ASCII inputs only.

## 🌅 Outcomes

- `INTEGRATION=1 uv run python scripts/bench_light_lane.py run --tier 3 --out DIR` runs the nine
  tier-3 tasks, the multi-session ones as sequential fresh `claude -p` processes on one work dir,
  and grades each run once, after its last session.
- `uv run python scripts/bench_light_lane.py check` also checks every tier-3 task: discrimination,
  the careless overlay, cited sentences and the prompt lint; it prints the tier-3 hash to sign.
- `report` adds a per-task block for tier 3 (solved/runs, cost and wall per arm, and the pilot
  drop rule) after the scorecard; tier-3 judge lines are labelled `uncalibrated`.
- Tiers 1-2 are byte-identical: the same task bytes, `bench_hash` (`569e17ef29ab`), `tier2_hash`
  (`1cf707c57e12`), `runner_hash` for the same settings, rows and published output.
- Two plain controls, `plain-careful` and `plain-continue`, run as their own arms.

## 📋 In-Scope Scenarios

### S1: Tier 3 holds nine tasks in four families, each with a real trap

**Given** `scripts/bench/tier3/tasks/<id>/` for t13-t21, each with a `tier` file (3), a `base`
file naming the shared overlay `scripts/bench/tier3/base/`, `hidden/`, `reference/`,
`careless/` and an optional `guards.txt`
**When** `check` runs
**Then** for every tier-3 task:
- the starting tree is the fixture, then the base overlay, then the task's `seed/` (if any);
  the grading tree adds every session overlay;
- the hidden tests fail on the grading tree, apart from the tests in `guards.txt`, which pass;
- the hidden and visible tests pass on the reference;
- the `careless/` overlay (the plausible-but-wrong solution) **fails** the hidden tests and
  **passes** the visible tests, so the trap is real and no visible test catches it;
- t21 (G1) carries a `guard` file and is exempt from the pilot drop.

| Id | Design | Family | Ask (sessions) | Hidden tests |
|---|---|---|---|---|
| t13 | A1 | (a) ambiguous ask | issue #21, ruled one hop away in D-6 | `hidden/test_t13_issue_21.py` |
| t14 | A2 | (a) | decimal amounts under D-3's whole-seconds rule | `hidden/test_t14_decimals.py` |
| t15 | A3 | (a) | a bare number, minutes per D-2 | `hidden/test_t15_bare_number.py` |
| t16 | B1 | (b) hidden caller | weeks, with the frozen `pack` index | `hidden/test_t16_weeks.py` |
| t17 | B2 | (b) | error positions, read back by `config.load` | `hidden/test_t17_error_position.py` |
| t18 | B3 | (b) | one-regex refactor, `strict.py` imports privates | `hidden/test_t18_one_regex.py` |
| t19 | C1 | (c) multi-session | a 30-day cap stated in S1, applied in S2 | `hidden/test_t19_remembered_cap.py` |
| t20 | C2 | (c) | a deferred step, teammate commit between S1 and S2 | `hidden/test_t20_deferred_locale.py` |
| t21 | G1 | guard | S2 supersedes S1's cap | `hidden/test_t21_lifted_cap.py` |

### S2: Every hidden requirement has a findable source

**Given** a tier-3 hidden test
**When** `check` reads its docstring
**Then** the docstring quotes one sentence and ends with `Source: <home>`, where the home is a
file of the grading tree (a relative path), `prompt` (the task's prompt) or `session <n>` (that
session's prompt). The quote, whitespace-normalised, is in the home's text, and a miss is a
problem. The answer is always on disk or in a prompt, never only in the designer's head.

### S3: Tier-3 prompts carry no harness vocabulary

**Given** every session prompt of a tier-3 task
**When** `check` lints it
**Then** it is a problem when a prompt matches a `REDACTIONS` pattern, holds one of the whole
words `spec`, `plan`, `memory`, `remember`, `acceptance` or `non-goal` (any case), the phrase
`note this`, or `docs/` (the clarifying files live there). A prompt may carry what a real ticket
would: an issue number, a module name, "every other module keeps its behaviour".

### S4: The oracles are fixed from the unchanged starting trees

**Given** the tier-3 hidden tests, written and frozen before any arm runs
**Then** the differential oracles come from the start tree, not from a reference:
- t16's `_PACKED` goldens equal `pack()` of the start tree on every recorded value;
- t18's frozen `parse_duration` copy agrees with the start tree's function on the whole corpus;
- t13's compact oracle agrees with the start tree's `format_duration` over its sweep.

### S5: A multi-session task runs as sequential fresh sessions on one work dir

**Given** a task with `sessions/<n>/prompt.md` (and an optional `sessions/<n>/overlay/`)
**When** `run_cell` runs it
**Then**:
- each session is a new `claude -p` process in the same work dir with the same argv apart from
  its prompt; no main arm gets `--continue` or `--resume`; hm gets the `/hm:spec ` prefix on
  every session;
- before session n > 1 the runner copies that session's overlay in, `git add`s **only those
  paths** and commits them as `teammate` with `--only`, so the arm's own uncommitted work never
  enters the teammate commit; a path the arm had already written is overwritten and listed in
  `overlay_clobbered`;
- the run stops at the first session whose status is not `ok`; the row records
  `sessions: [{status, cost_usd, turns, wall_s}]` and `stopped_at` (null when all ran);
- cost (the CLI total, else the transcript price over every transcript under the work dir),
  turns and wall time are summed over the sessions; the leak check reads every session's output;
- grading runs once, after the last session that ran, against the fixture + base + seed + the
  overlays that were applied, so a teammate's file is never counted as the arm's change.

A task without `sessions/` is one session from `prompt.md`, unchanged.

### S6: Tier 3 has its own hash and gate, and rows never mix

**Given** the tier-3 files
**Then**:
- `tier3_hash` covers `scripts/bench/tier3/` (base and tasks), and nothing else;
- `bench_hash` and `tier2_hash` do not cover tier 3, so tiers 1-2 keep their values;
- each tier-3 row records `tier3_hash`, and rows of one results dir with two different
  `tier3_hash` values are refused like any other mix;
- `run --tier 3` with the `hm` arm exits 2 before any copy or spend unless
  `scripts/bench/tier3-signoff.json` names the current `tier3_hash` and a signer; a plain-only
  run (the pilot) needs no sign-off, and its rows carry the hash the DRI later signs;
- `--tier all` keeps meaning tiers 1-2, so tier 3 only runs when asked for.

### S7: Tiers 1-2 are unchanged

**Given** the tier 1-2 task dirs, fixture and committed results
**Then** `bench_hash()` is `569e17ef29ab`, `tier2_hash()` is `1cf707c57e12`, `runner_hash` gives
the values it gave before for the same settings, a tier 1-2 row carries no tier-3 field, and the
committed `RESULTS.md` and README block republish byte for byte.

### S8: Two plain controls run as their own arms

**Given** `--arms plain-careful` or `--arms plain-continue`
**Then**:
- both start from the plain template; `plain-careful` appends one fixed sentence to every
  session prompt: "Before changing code, read the documentation and every caller that the
  change could affect."; `plain-continue` adds `--continue` to every session after the first;
- their rows carry their own arm name, stay out of the plain-vs-hm scorecard, and appear in the
  tier-3 per-task block;
- neither decides the primary metric.

### S9: The tier-3 report lists each task and the pilot drop rule

**Given** tier-3 rows
**When** `report` runs
**Then** after the scorecard it prints, per tier-3 task and arm, solved/runs, mean cost and mean
wall, and for the plain arm the pilot rule: `drop` when plain solved 2 or more of 3 or more
runs, `keep` otherwise, `guard` for the exempt task. Tier-3 judge lines in the scorecard read
`(uncalibrated)`. A results dir without tier-3 rows prints exactly what it printed before.

### S10: Tier 3 is published beside the scorecard, never in it

**Given** plain pilot rows in `docs/evals/tier3/pilot/` and, optionally, hm diagnostic rows in
`docs/evals/tier3/diagnostic/`
**When** `publish` runs
**Then** `RESULTS.md` gains a tier-3 section after the unchanged tiers 1-2 render (the pilot per
task, the drop rule and its outcome, the hm runs labelled a diagnostic, the hand-written notes),
and the README block gains one to three tier-3 sentences after the unchanged tiers 1-2 text.
Every $ is named as the CLI cost, which excludes subagent spend, and an unpriced row is counted.
It refuses, writing nothing, when the pilot does not cover every tier-3 task (a task whose rows
were all dropped as unusable, a missing guard), holds an hm row or a task with fewer than 3
runs, or when any row has another tier, a mixed `tier3_hash` or `harness_sha`, an unknown arm
or no rep. Without a tier-3 dir it writes what it wrote before, byte for byte. The committed
rows' `tier3_hash` equals the DRI's sign-off and the checkout's `tier3_hash()`.

## ⚖️ Pre-registration (DESIGN §4, committed before the full run)

- **Cells:** plain, hm, plain-careful (all tasks), plain-continue (t19, t20, t21); 5 runs per
  cell. T = the discriminating tasks that survive the pilot (t13-t20, at most 8); t21 is the
  guard.
- **Primary metric:** Δ solved-run rate, hm minus plain, pooled over T × 5 runs per arm.
- **hm wins tier 3** only if all four hold: (1) Δ solved-run rate ≥ +0.25; (2) hm leads by at
  least 2 solved of 5 on at least ⌈T/2⌉ tasks and trails by 2 or more on none; (3) on t21, hm
  solves no fewer than plain − 1; (4) T ≥ 4. With fewer, the tier is **inconclusive**, which
  counts as "plain cannot be made to fail fairly", and the quality claim is dropped.
- **Secondary (reported, not deciding):** Δ hidden-case pass fraction, cost per solved run,
  extra $ per additional solved run, per-family Δ, judge lines labelled uncalibrated.
- **Attribution:** plain-careful within 0.15 of hm on a family means that gain is a one-line
  diligence instruction; plain-continue within 0.15 of hm on (c) means hm's state helps only
  when the conversation is lost.
- **Pilot (plain only, 3 runs, `--no-judge`):** a task is dropped when plain solves 2 or more of
  3; t21 is exempt. A plain failure that is not the trap's (a stall, a runner error, a hidden
  failure unrelated to the cited sentence) means drop, or fix under fairness rule 7. Tasks are
  only ever dropped, never edited because plain passed.

## 🚫 Non-Goals

- Running the hm arm or the full run. This SPEC delivers the instrument and the plain pilot.
- Calibrating the judge for tier 3; its lines stay `uncalibrated` and never decide.
- Folding tier 3 into the plain-vs-hm scorecard: the pilot is plain-only and the hm runs are a
  diagnostic, so neither forms a balanced cell (S10 publishes it beside the scorecard instead).
- The hm mechanism smoke (DESIGN §5, optional), and adding the cited sentences to the judge
  input; both are follow-ups.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard |
| Location | `scripts/bench/tier3/` for the base and tasks, one runner `scripts/bench_light_lane.py`, tests in `tests/unit/test_bench_tier3.py` | Keeps `bench_hash` and `tier2_hash` of tiers 1-2 unchanged |
| Live calls | as SPEC-hm-eval: `INTEGRATION=1`, `IS_SANDBOX=1` or `--no-sandbox-ok`; no unit test calls a model | CLAUDE.md test policy |
| Dependencies | stdlib plus existing dev dependencies | No new dependency |
| Fixture | the base adds `timeparse/{schedule,config,pack,strict}.py`, `docs/DECISIONS.md` (D-1 to D-10), 8 `docs/issues/*.md`, `docs/config.md`, `CHANGELOG.md` and a README layout; both arms get the same bytes | Plain reads a small package whole (t12), so the answers need somewhere real to live |
| Boundaries | No edit to tier 1-2 task dirs, the fixture, `src/harness_maker/`, templates or `CLAUDE.md` | Tiers 1-2 stay byte-identical |

## 🔒 Irreversible Decisions

None. `tier3-signoff.json` mirrors `tier2-signoff.json`, and the row fields are additive in a
dev-only file whose readers tolerate their absence.

## ✅ Verification Criteria

| Scenario | Verification mode | Test name |
|---|---|---|
| S1 | unit (subprocess pytest) | `tests/unit/test_bench_tier3.py::test_tier3_tasks_discriminate`, `test_tier3_ships_nine_tasks_in_four_families`, `test_a_careless_overlay_that_passes_is_a_problem` |
| S2 | unit | `test_every_tier3_hidden_test_cites_a_findable_sentence`, `test_a_quote_missing_from_its_home_is_a_problem` |
| S3 | unit (parametrized) | `test_tier3_prompts_carry_no_harness_word`, `test_the_prompt_lint_rejects_each_listed_word` |
| S4 | unit (differential) | `test_goldens_match_the_unchanged_start_tree` |
| S5 | unit (fake claude) | `test_sessions_run_in_order_as_fresh_processes_in_one_work_dir`, `test_the_teammate_commit_holds_only_the_overlay_paths`, `test_an_overlay_the_arm_already_wrote_is_recorded_as_clobbered`, `test_a_failed_session_stops_the_run_and_grades_once` |
| S6 | unit | `test_tier3_hash_covers_tier3_files_only`, `test_a_tier3_run_with_the_hm_arm_needs_the_signoff`, `test_tier3_rows_record_their_hash_and_never_mix` |
| S7 | unit (pinned values, committed rows) | `test_tier_one_and_two_hashes_are_unchanged`, `test_a_tier_two_row_has_no_tier3_fields`, `tests/unit/test_bench_light_lane.py::test_the_committed_results_and_readme_block_are_published_from_the_committed_rows` |
| S8 | unit (fake claude, golden rows) | `test_the_careful_variant_appends_one_sentence`, `test_the_continue_variant_continues_after_the_first_session`, `test_control_rows_stay_out_of_the_main_scorecard` |
| S9 | unit (golden rows) | `test_the_tier3_report_lists_each_task_and_the_pilot_drop`, `test_tier3_judge_lines_are_labelled_uncalibrated` |
| S10 | unit (golden rows, committed rows) | `test_tier3_publishes_the_pilot_rule_and_withdraws_the_claim`, `test_four_kept_tasks_make_tier3_measurable_and_keep_the_claim_open`, `test_tier3_publish_refuses_rows_it_cannot_report_honestly`, `test_without_tier3_rows_publish_writes_what_it_wrote_before` |
| S10 (cost, hash) | unit (golden rows, committed rows) | `test_tier3_costs_say_they_are_cli_totals_without_subagent_spend`, `test_tier3_costs_omit_the_unpriced_note_when_every_row_is_priced`, `test_the_committed_tier3_rows_carry_the_signed_tier3_hash`, `test_the_committed_tier3_rows_publish_the_committed_section` |

### AC-001: Every tier-3 task discriminates, and its careless overlay fails hidden but passes visible
### AC-002: Every tier-3 hidden test quotes a sentence found in its named home
### AC-003: Tier-3 prompts carry no harness vocabulary and no clarifying path
### AC-004: The differential oracles equal the unchanged start tree
### AC-005: A multi-session run is sequential fresh sessions on one work dir, graded once
### AC-006: Tier 3 has its own hash and sign-off gate, and rows never mix
### AC-007: Tiers 1-2 keep their hashes, rows and published output
### AC-008: The two plain controls run as their own arms, outside the main scorecard
### AC-009: The tier-3 report lists each task, the pilot drop rule and uncalibrated judge lines
### AC-010: Tier 3 publishes beside the scorecard, refuses rows it cannot report honestly, and ties to the signed hash

## ❓ Open Questions

- Whether hm's S1 in `-p` leaves anything (a SPEC, a memory entry) that names the decision of
  t19/t20. The optional mechanism smoke (DESIGN §5) answers it before the full run.
- B3 (t18) without the unicode quirk: its trap is the private-name cleanup alone. If plain keeps
  `_TOKEN`/`_rank`, t18 drops in the pilot, which is a legitimate result.

## 🔍 Refinement Decisions

- Interview not run: scope is the approved DESIGN plus the DRI default of 2026-10-15 (no
  Arabic-Indic digits; the corpus is ASCII, and its whitespace is `string.whitespace`).
- **Location deviation from DESIGN §2 and §3:** the base sits at `scripts/bench/tier3/base/`
  and the tasks at `scripts/bench/tier3/tasks/`, outside `bench_hash`, so tiers 1-2 keep their
  hashes (the coordinator's "byte-identical" instruction). `tier3_hash` covers tier 3, and each
  tier-3 row records it.
- **Gate timing:** DESIGN rule 4 has the DRI sign before the pilot. The coordinator asked for
  the plain pilot now, without stamping any approval, so the gate binds runs that include the hm
  arm; the pilot rows record `tier3_hash`, which lets the DRI check the signed bytes are the
  piloted bytes.
- **t15:** the fixture's visible test lists `"10"` as invalid, so any solution edits that
  visible test; the reference and careless overlays both do. A t15 run therefore shows one
  pristine-test regression in either arm; it is shown, never ranked.
- **t13:** the careless overlay (hours-only output) also updates the visible `test_format.py`
  case it changes, as a run that follows the thread's proposal would.
- **t17:** the hidden tests check only the config message the docs show for a malformed
  duration; how the other config messages change is not tested, because the ask changes every
  message format and no fix can keep them all.
- **t18:** the corpus compares outcomes (the value, or `ValueError`), not message text; the
  config message for a malformed duration is checked as "nothing else in the package may
  break".
- **t20:** `locale.unit_name(unit, count, lang)` returns the count with the name
  (`"2 hours"`, `"2시간"`), and S1 says `lang` defaults to `en`.
- **t21:** its S2 restates the clock format, since a fresh session has no "as above".
- Controls are built as arms (`plain-careful`, `plain-continue`) rather than a `variant` field
  on plain rows, so no plain-only reader can count them as plain by accident.
- **Publishing tier 3 (2026-10-16):** the Non-Goal "Publishing tier 3 into `RESULTS.md`" is
  dropped. The DRI chose by decision card on 2026-10-16 ("publish + hm diagnostic") to publish
  the inconclusive pilot with an hm diagnostic on t20 and t21. S10 and AC-010 cover it: beside
  the scorecard, never in it, with the refusals, the no-tier-3 byte identity, the CLI-cost
  caveat and the tie to the signed `tier3_hash`. The status returns to `draft` for re-approval.
