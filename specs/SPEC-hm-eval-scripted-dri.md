---
type: spec
task_slug: hm-eval-scripted-dri
status: approved
created: 2026-10-16
tags: [harness-maker, spec, eval, bench, fairness, multi-turn]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
parent_spec: "[[SPEC-hm-eval]]"
summary: "The bench plays the DRI for the hm arm: one resumed session gets /hm:spec <task>, one fixed approval, /hm:execute <slug> and /hm:wrapup <slug>, summed into one row; plain is unchanged and both arms are re-run"
---

# SPEC — hm-eval-scripted-dri (the bench plays the DRI, in order)

## 🎯 Intent

The bench runs the hm arm as one headless call, `/hm:spec <task>` (`HM_PREFIX`). With the old
harness, `auto_full` autopilot carried that one call through every stage. The overhaul (PR-S,
branch `hm-overhaul-p1-s`) removes autopilot and keeps human SPEC approval, so the spec stage
writes the SPEC and stops. A test run of the new harness stalled 6 of 6 hm runs on tiers 1-2
(`/var/tmp/hm-eval-p1/`). In `runs/t1-hm-1-388dea/agent.stdout` the run takes 2 turns, leaves
a `draft` SPEC and ends with "If you approve the SPEC as written, I'll stamp it ... After that,
`/hm:execute format-duration-max-units` is yours to run." PR-S's ship bar (SPEC-hm-overhaul-p1
AC-010: tier-1 cost ratio ≤ 8x, hm hidden-test pass rate ≥ plain on tiers 1-2) needs a re-run
that uses hm the way a person uses the overhauled harness.

The DRI decided by card on 2026-10-16 ("순서대로 명령"): in one resumed session, the bench sends
the stage commands in order, as a person would. That is `/hm:spec <task>`, then an approval once
the SPEC is shown, then `/hm:execute <slug>`, then `/hm:wrapup <slug>`.

## 🌅 Outcomes

- An hm cell of a tier-1 or tier-2 task is one resumed CLI session. The bench sends a fixed turn
  script and records one row with the turns summed. The row also records each turn, the slug it
  found and why it stopped early, if it did.
- The bench sends nothing but the fixed strings below, the task prompt and a slug read from a file
  name the run wrote. It never composes a reply from the agent's text.
- The plain arm, tier 3, `bench_hash` and `tier2_hash` are unchanged. `runner_hash` changes for
  every run, so rows recorded before this change can never mix with new ones, and both arms are
  re-run into a fresh `--out`.
- `docs/evals/README.md`'s description of the hm arm names the turn script instead of only the
  `/hm:spec ` prefix.

## 📋 In-Scope Scenarios

### S1: The hm arm sends the stage commands in order, in one session (AC-001)

**Given** an hm cell of a task with one session (tiers 1-2)
**When** `run_cell` runs it
**Then** it sends these turns, in this order, stopping early only as S2 and S5 say:

| # | kind | prompt sent (exact) |
|---|---|---|
| 1 | `spec` | `/hm:spec ` + the task prompt (today's `prompt_for(task, "hm")`, unchanged) |
| 1b | `reply` | only as S2 says: `REPLY_TURN` |
| 2 | `approve` | `APPROVE_TURN` |
| 3 | `execute` | `/hm:execute <slug>` |
| 4 | `wrapup` | `/hm:wrapup <slug>` |

with these pinned constants:

- `APPROVE_TURN` = `I approve this SPEC as written. For each open question, take the option you
  recommend and record it in the SPEC. Stamp the approval, then stop.`
- `REPLY_TURN` = `I have nothing to add. For each open question, take the option you recommend,
  then write the SPEC.`

Each string is a single line (the wrap above is only for layout), with one space after every
sentence. Turn 1's argv is today's hm argv, byte for byte. Every later turn's argv is turn 1's
argv with the `-p` value replaced by that turn's prompt and `--resume <id>` appended. `<id>` is the
`session_id` that turn 1's CLI result reported. Every turn passes the same `--max-turns`,
`--model`, `--max-budget-usd` and `--setting-sources`, and each runs as its own `_invoke` with
the per-turn timeout `opts.timeout_s`.

### S2: A question instead of a SPEC gets one fixed reply, then the run stops (AC-002)

**Given** turn 1 ended with status `ok` and the run created no SPEC (S3 finds no slug)
**When** the runner decides the next turn
**Then** it sends `REPLY_TURN` once, as a resumed turn of kind `reply`. If S3 then finds a slug,
the script goes on at `approve`. If it still finds none, the run stops with `dri_stop: "no_spec"`
and sends nothing more, and S6 grades the tree. A run gets at most one `reply` turn, and only at
this point. A question asked at a later turn gets no answer, and the next scripted turn follows.

### S3: The slug is the newest SPEC the run created (AC-003)

**Given** the work dir after a spec-stage turn (`spec`, `reply` or `approve`)
**When** the runner looks for the slug
**Then** it reads the files directly under `work/specs/` whose name matches
`SPEC-([a-z0-9][a-z0-9-]*)\.md`. It ignores any whose path also exists in the arm's template
(`opts.templates[template_key(task, arm)]`), so only a file this run created counts. The slug is
the captured group of the file with the largest `(st_mtime_ns, name)`. Anything else gives no
slug: `.machine.yaml` files, other names, subdirectories, a missing `specs/`. The slug sent to
`/hm:execute` and `/hm:wrapup` is the one found after the `approve` turn. If that search finds
none, the run stops with `dri_stop: "no_spec"`. The row records the slug as `dri_slug`, or null.

### S4: Turns are summed into one run row (AC-004)

**Given** the turns that ran, each with its CLI result
**When** the row is recorded
**Then**:
- each turn's CLI `total_cost_usd` is read as the session's running total. A turn's own cost is
  its total minus the previous turn's (turn 1: its total). `cli_cost_usd` is the last turn's
  total, which equals the sum of the turns' own costs;
- when any turn's result has no cost, or a total falls below the previous one, `cli_cost_usd` is
  null. `pick_cost` then takes the transcript price (`cost_source: "transcript"`), and the row
  records `cli_cost_shape: "not_cumulative"` for a falling total;
- `num_turns` is the sum of the turns' `num_turns` (null when any is missing), and `wall_s` is
  the sum of each turn's own wall time;
- `tokens`, `transcript_cost_usd`, `transcript_turns` and `subagent_turns` stay the transcript
  price over every transcript under the work dir, which covers every turn of the session;
- `dri_turns` lists each turn that ran, in order:
  `{kind, status, cost_usd (own), cli_total_usd, turns, subtype, wall_s}`.

### S5: Per-run limits and failures still stop the run (AC-005)

**Given** a run in progress
**Then**:
- a turn whose `_status` is not `ok` (`timeout`, `agent_error`) stops the run, and the row's
  `status` is that turn's. On every early stop (this one, S2, S3 and the ones below), `stopped_at`
  is the 1-based position of the last turn sent. It is null when the `wrapup` turn ran with status
  `ok`. `dri_stop` is null unless one of S2, S3 or the stops below applied;
- before each turn after the first, the runner stops if the run's spend so far is at least
  `opts.max_budget_usd`, or if any turn's cost is unknown. The spend so far is the last reported
  total. If any total fell (S4), it is the sum of the reported totals, the larger reading, so the
  cap is never under-counted. Totals of 2.0 then 4.0 under a cap of 5.0 are a spend of 4.0, so the
  next turn is sent. It records `dri_stop: "budget"`, and
  for a total at the cap it records `subtype: "error_max_budget_usd"`, so `summarize` marks the
  verdict `suspect` as it does for a capped run today;
- a turn 1 result without `session_id`, or a later turn that reports a different one, stops the
  run with `dri_stop: "session_lost"`. Resuming an unknown conversation is not the DRI's sequence;
- `STOP` set between turns gives an `interrupted` row, as today. An exception after a turn ran
  gives a `runner_error` row with `_salvage`'s cost evidence, as today;
- `--total-budget-usd` stays a scheduling cap, checked before each cell. One cell's spend stays
  bounded by the per-run cap across its turns.

### S6: The run is graded once, on the final work tree (AC-006)

**Given** the last turn that ran (or the stop of S2, S3 or S5)
**When** the row is recorded
**Then** `grade`, `outcome_for`, `quality_for`, `trap_for` and the judge run once, unchanged, on
the work dir root against the task's start tree. The outcome rules stay as they are:
`solved`/`wrong`/`stalled` from the hidden tests and the `timeparse/`+`tests/` scope. A run
stopped at `no_spec` with no code change is `stalled`. Code left uncommitted because `/hm:wrapup`
did not commit is still graded, since the outcome compares files, not git history. Each turn's
stdout and stderr are kept as `agent-<n>.stdout`/`agent-<n>.stderr` (n = position among the turns
sent), beside the last turn's `agent.stdout`. The leak check reads every turn's output.

### S7: The plain arm and tier 3 are unchanged (AC-007)

**Given** a plain cell of any task, or any cell of a tier-3 task
**When** it runs
**Then** it runs exactly as today, apart from the run's `runner_hash` value (S8). Plain is one call with today's argv, and a tier-3 task runs one
fresh call per session with the `/hm:spec ` prefix for hm. Its row has today's keys and no
`dri_*`, `stopped_at` or `cli_cost_shape` field. A plain tier-1/2 row's key set equals
`_TIER_TWO_ROW_KEYS`.

### S8: The turn script is part of `runner_hash`, so old and new rows never mix (AC-008)

**Given** the runner settings
**Then** `runner_hash` covers the script: `APPROVE_TURN`, `REPLY_TURN`, the turn order with the
`/hm:execute ` and `/hm:wrapup ` prefixes, the one-reply cap, `--resume`, the SPEC name pattern
and the tiers it applies to. Changing any of them changes `runner_hash`. Rows recorded before this
change carry another `runner_hash` (and, from PR-S, another `harness_sha`), so `ensure_consistent`
refuses a results dir that mixes them through `MIXED_FIELDS`, unchanged. The re-run therefore uses
a fresh `--out` and runs plain as well as hm.

### S9: Nothing but fixed strings reaches the agent (AC-009)

**Given** every scripted fake-CLI run of S1-S5 (each stop path, the reply path, a full sequence)
**When** the prompts the runner sent are collected
**Then** each is one of `HM_PREFIX + task.prompt`, `REPLY_TURN`, `APPROVE_TURN`,
`"/hm:execute " + slug` or `"/hm:wrapup " + slug`, where slug is a file name the run itself
wrote that matches S3's pattern. The agent's result text never shows up in a prompt.

## 🚫 Non-Goals

- **Tier 3.** Tier 3 stays published as inconclusive from its committed rows (the plain pilot
  plus the hm diagnostic on t20/t21), and AC-010 reads tiers 1-2 only. Scripting the DRI through
  multi-session tasks needs its own decision: whether each session gets its own spec→wrapup chain,
  and how the turns interleave with fresh sessions and teammate commits. Until a follow-up SPEC
  makes that decision, a tier-3 hm run keeps today's path, which stalls under PR-S, so it is not
  run.
- Changing the plain arm, the plain controls, the task files, the fixture, the outcome rules, the
  judge or the published scorecard's layout.
- Answering questions at the `execute` or `wrapup` turns, or any turn written from the agent's
  text.
- A flag to choose the old single-call hm path. Under PR-S that path measures a stall.
- Fixing the tier-3 diagnostic's `plain-continue` cost. Its `cli_cost_usd` sums running totals
  (see Refinement Decisions). That is a separate fix to a published section.
- Running the re-run and publishing its rows, which is PR-S's job.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest`, new file `tests/unit/test_bench_scripted_dri.py` | Project standard; the tier-3 suite's in-process scripted fake (`_fake(tmp_path, steps)`) is the pattern |
| Live calls | none in unit tests; the fake CLI emits `session_id`, `total_cost_usd`, `num_turns` and writes files on cue | CLAUDE.md test policy: mock first |
| Location | `scripts/bench_light_lane.py` only (`run_cell`, `_record`, `runner_hash`), plus `docs/evals/README.md` | `bench_hash` and `tier2_hash` cover task files, not the runner, so they stay put |
| Pinned hashes moved on purpose | `tests/unit/test_bench_tier3.py::test_tier_one_and_two_hashes_are_unchanged` gets new `runner_hash` values; its `bench_hash`, `tier2_hash`, report and scorecard pins stay | The turn script is a new runner setting (S8); SPEC-hm-eval-tier3 AC-007's "same settings" no longer holds for `runner_hash` alone |
| Existing argv test | `test_arms_differ_only_by_harness_and_prefix` compares turn 1 of the hm cell with the plain call | SPEC-hm-eval S15 is amended: arms differ by the harness, the prefix on turn 1 and the fixed later turns |
| Dependencies | stdlib only | No new dependency |
| Before the re-run | one live two-turn `--resume` smoke under `INTEGRATION=1` (`tests/integration/test_boundary_bench_resume.py`). It checks that the session id is kept, the reported total does not fall, and the total stays within `SUSPECT_GAP` of the transcript price | S4's running-total reading and S5's cap rest on CLI behaviour that is observed but not documented |
| Sequencing | this change lands on main, then PR-S rebases onto it, and the re-run runs from the PR-S branch | AC-010 reads rows whose `harness_sha` is reachable from PR-S's HEAD |

## 🔒 Irreversible Decisions

None. The new row fields (`dri_turns`, `dri_slug`, `dri_stop`, `stopped_at`, `cli_cost_shape`)
are additive in a dev-only results file whose readers tolerate their absence. The turn strings
sit in `runner_hash`, so changing them later means a fresh `--out` and a re-run, never a silent
mix. The CLI of `scripts/bench_light_lane.py` gains no flag.

## ✔️ Acceptance Criteria

### AC-001: The hm arm sends spec, approval, execute and wrapup in order in one resumed session
### AC-002: A run with no SPEC after turn 1 gets one fixed reply, then stops as no_spec
### AC-003: The slug is the newest matching SPEC the run created, else none
### AC-004: Turn costs, turns and wall time are summed into one row from the running CLI total
### AC-005: A failed turn, the run budget or a lost session stops the run with its reason
### AC-006: The run is graded once on the final work tree, and every turn's output is kept and leak-checked
### AC-007: The plain arm and tier-3 cells run exactly as before
### AC-008: runner_hash covers the turn script, so rows from before are refused
### AC-009: Every prompt the bench sends is a fixed string, the task prompt or the discovered slug

## ✅ Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit (scripted fake CLI) | `test_hm_cell_sends_spec_approve_execute_wrapup_in_one_resumed_session`, `test_later_turns_differ_from_turn_one_only_by_prompt_and_resume` |
| S2 | unit (scripted fake CLI) | `test_no_spec_after_turn_one_gets_one_fixed_reply`, `test_no_spec_after_the_reply_stops_as_no_spec` |
| S3 | unit (golden work dirs) | `test_slug_is_the_newest_spec_the_run_created`, `test_template_specs_and_other_names_give_no_slug` |
| S4 | unit (golden CLI results) | `test_turn_costs_are_differences_of_the_running_cli_total`, `test_a_falling_or_missing_total_falls_back_to_the_transcript_price`, `test_turns_and_wall_time_are_summed` |
| S5 | unit (scripted fake CLI) | `test_a_failed_turn_stops_the_run_with_its_status`, `test_the_run_budget_stops_the_next_turn`, `test_a_lost_session_id_stops_the_run` |
| S6 | unit (scripted fake CLI) | `test_the_run_is_graded_once_after_its_last_turn`, `test_every_turn_output_is_kept_and_leak_checked` |
| S7 | unit (fake CLI) | `test_the_plain_arm_runs_one_unchanged_call`, `test_tier3_cells_keep_one_call_per_session` |
| S8 | unit | `test_runner_hash_covers_the_turn_script`, `test_rows_from_before_the_turn_script_are_refused` |
| S9 | unit (property over every fake run) | `test_every_sent_prompt_is_fixed_or_the_task_or_the_slug` |
| re-run precondition | integration, `INTEGRATION=1`, advisory | `tests/integration/test_boundary_bench_resume.py::test_resume_keeps_the_session_and_a_running_total` |

## ❓ Open Questions

None. The calls the DRI may want to override are marked *(DRI may override)* below.

## 🔍 Refinement Decisions

- **Interview not run.** The DRI fixed the sequence on 2026-10-16. The coordinator asked for the
  remaining details to be decided and pinned here.
- **The approval turn is always sent** *(DRI may override)*, even when the agent already stamped
  the SPEC `--exempt`, as t11-hm-1 and t11-hm-2 did in the test run. The script stays the same for
  every run, and the bench never reads approval state, which would couple it to `spec_machine`'s
  format. A person also says "approved" after reading a SPEC. The extra short turn is real hm cost
  and is counted.
- **Approval wording.** It accepts the SPEC, settles open questions with the agent's own
  recommended option (spec stage's interview contract: the DRI picks, the agent recommends), asks
  for the stamp the agent itself offered in t1-hm-1, and says "then stop". Without "then stop", an
  agent that reads "approved" as "go" would build inside the approval turn, and `/hm:execute`
  would then arrive at finished work, which is not the DRI's sequence. It names no file or command
  beyond what the agent's own message offered.
- **One reply, then stalled.** A spec stage that asks questions in `-p` instead of writing a SPEC
  gets one fixed "use your recommendation" reply. A second miss is a stall of the harness, not of
  the script. More replies would let the bench drive the interview, and the bench cannot answer
  anything without making something up. The check is "did a SPEC file appear", not a reading of
  the agent's text, so it involves no LLM or regex judgment of prose.
- **Slug from the file name.** The spec stage writes `specs/SPEC-<slug>.md` (PR-S
  `stages/spec.md.j2` Step 3), and the test run's work dirs hold exactly those (`worktree.enabled:
  false` in the bench's rendered `harness.yaml`, so no task worktree moves them). The newest
  created file wins, because a stage that rewrites its SPEC under a new name means the later one.
  The name pattern keeps the slug a plain token before it goes into a prompt.
- **Resume, not continue.** The runner resumes turn 1's `session_id` explicitly. `--continue`
  picks the most recent conversation in the cwd, which is right only by accident. Resuming keeps
  the session id (the CLI forks only with `--fork-session`), so a changed id means something
  other than the DRI's conversation is being continued, and the run stops.
- **Cost is a running total.** In `docs/evals/tier3/diagnostic/results.jsonl` (rows written by
  `--continue` sessions), the t20 `plain-continue` sessions report 0.0763 (5 turns) and then
  0.1134 (3 turns). Their sum, 0.1897, is 1.48x the transcript price of 0.1285. Fresh-session
  pilot rows read about 0.91x (t19: 0.1369 against 0.1505). Read as a running total, the session
  costs 0.1134, which is 0.88x the transcript price, in line with fresh sessions. So a resumed
  turn's own cost is a difference of totals. `num_turns` drops from 5 to 3 there, so turns are per
  call and are summed. A falling total disproves the reading for that row, and the row then falls
  back to the transcript price instead of guessing. `summarize`'s `SUSPECT_GAP` check still flags
  a systematic disagreement, and the integration smoke checks the reading before the re-run.
- **Same cap on every turn.** Every turn passes the same `--max-budget-usd`. If the CLI applies
  it to the restored running total, which the same evidence suggests, it caps the whole session. A
  smaller "remaining" cap on each turn would then stop runs early. The runner's own check before
  each turn bounds the run to at most twice the cap even if the CLI caps per call.
- **Timeout per turn.** `opts.timeout_s` (default 1800 s) applies to each turn. A run's wall time
  is bounded by the number of turns times that value, and `wall_s` reports what was spent.
- **Outcome rules unchanged.** One rule for both arms, applied to the final tree. A special case
  that marks `no_spec` runs `stalled` regardless of the tree would let the turn logic, not the
  graded files, decide an outcome. In practice a `no_spec` run changed no code and is `stalled`.
- **Plain is unchanged but re-run.** The DRI kept plain as one call: a person using plain Claude
  types the task and nothing else. `runner_hash` is one value per run for both arms, so old plain
  rows cannot sit beside new hm rows, and the scorecard compares arms recorded under the same
  runner.
- **Fairness.** The later turns carry no task information. They are the same fixed strings for
  every task, and the slug is the agent's own file name, so SPEC-hm-eval S15 still holds in
  substance: the arms differ by the harness and by how a person drives it.
