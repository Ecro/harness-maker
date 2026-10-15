---
type: spec
task_slug: hm-eval
status: approved
created: 2026-10-14
tags: [harness-maker, spec, eval, code-quality, cost, hidden-tests, llm-judge]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
parent_spec: "[[SPEC-hm-light-lane-bench]]"
summary: "Turn the light-lane bench into an eval: plain vs /hm: on code quality first (hidden tests, lint/type deltas, a blind calibrated LLM rubric), cost second, published to docs/evals and the README"
---

# SPEC — hm-eval (plain prompt vs harness: code quality first, then cost)

## 🎯 Intent

The DRI wants one eval that shows, in numbers, how code written through the harness compares with
code written from a raw prompt, first on quality and then on what that quality costs. It has to be
easy to re-run after a harness change. Its results should live in `docs/`, and the README should
show the headline.

`scripts/bench_light_lane.py` (SPEC-hm-light-lane-bench) already runs both arms headlessly with the
same model and budget, grades hidden tests in isolation and prices every run. It measures one
thing, `hm_cost_ratio_small`, on five tasks that plain already solves 15/15. Both arms are at the
ceiling there, so those tasks cannot show a quality difference. This SPEC builds on that runner:
- a second task tier whose hidden tests are not saturated, with each test traceable to a sentence
  of its prompt;
- quality and token signals recorded per run;
- a blind, calibrated LLM rubric;
- a scorecard that leads with quality;
- a publish step that writes the scorecard into the docs.

The intent metric and its pre-registered verdict keep working, computed on tier 1 only.

The eval reports what comes out. If plain writes better code than `/hm:`, the docs say so.

The harness will spend more tokens than a raw prompt. The eval therefore has to show what that
extra spend buys, plainly enough that the DRI can decide whether the harness is worth using even at
several times the cost (amendment 2026-10-15). Every report surface leads with a "What the extra
cost buys" section (S16). Cost-reduction work such as the light lane is measured by the same
scorecard.

## 🌅 Outcomes

- `INTEGRATION=1 uv run python scripts/bench_light_lane.py run [--tier 1|2|all]` runs both arms,
  grades them, scores quality, and by default makes one blind judge call per changed run. It ends
  by printing the scorecard.
- `uv run python scripts/bench_light_lane.py report --out DIR` reprints the scorecard offline. Its
  sections, in order:
  1. **What the extra cost buys** (per tier, S16)
  2. **Quality** (plain vs hm per tier)
  3. **Efficiency** (the cost of that quality)
  4. The existing **intent-metric** block, whose last line is still
     `hm_cost_ratio_small=<ratio|n/a>`
- `uv run python scripts/bench_light_lane.py publish --out DIR` is offline. It writes
  `docs/evals/RESULTS.md` and rewrites the README block between `<!-- hm:eval:start -->` and
  `<!-- hm:eval:end -->`: the "What the extra cost buys" section per tier (S16) with n in each
  cell, and a link. The
  trend is the git history of `RESULTS.md`, which names `bench_hash`, `harness_sha`, `runner_hash`
  and the tool versions.
- `docs/evals/README.md` (hand-written) explains:
  - what is measured and how to run it;
  - how to read the scorecard;
  - how to read "What the extra cost buys", i.e. whether the extra cost is worth it, and that
    cost-reduction work (the light lane) is measured by the same scorecard;
  - the direction table and the lead rule;
  - the fairness rules and the tier-2 sign-off;
  - the improvement loop: change the harness, re-run, publish, then read `git log -p
    docs/evals/RESULTS.md`.
- Tier 2: four new tasks (t6–t9) on the same `timeparse` fixture.
  - Each covers one change shape: a bug fix with a regression trap, a change that keeps an existing
    invariant, a stated multi-case contract, and a change with one source of truth.
  - Each ships a reference that passes every hidden test, and a damaged copy of the reference for
    judge calibration.
  - `check` proves the hidden tests discriminate.
  - Tier 1 (t1–t5) stays the cheap smoke and cost tier.
- Tier 2 also holds three trap tasks (t10–t12, S17), one per kind: secret, scope and hidden
  caller. Each run of a trap task records whether the run avoided the trap, and every surface
  shows "traps caught" per arm (amendment 2026-10-15, traps).
- Nothing in the unit suite calls a model or the network.

## 📋 In-Scope Scenarios

### S1: Every task's hidden tests discriminate
**Given** the task directories under `scripts/bench/tasks/`, each with a `tier` file (absent means
1) and an optional `seed/` overlay
**When** `check` runs
**Then** for every task:
- the starting tree is the fixture plus the seed;
- the hidden tests fail on the starting tree and pass on the reference, apart from the tests listed
  in `guards.txt`;
- guards are regression traps: they must pass on the starting tree and on the reference;
- the fixture's own visible tests pass on both;
- tier 2 holds 3–5 non-trap tasks, each also shipping a `damaged/` overlay (see S13), plus one
  trap task per kind (S17), whose `trap.json` cites a prompt sentence verbatim and whose reference
  passes its own trap check.

### S2: Tokens are recorded per kind
**Given** a finished run
**When** the runner records it
**Then** the row carries `tokens: {input, output, cache_read, cache_write}`. Each is summed over the
run's own main and subagent transcript turns through `harness_maker.economics`, where `cache_write`
= 5m + 1h writes. The row also records `tier`.

### S3: A stall is distinguishable from a wrong fix
**Given** a graded run
**When** the runner classifies it
**Then** `outcome` is one of:
- `solved`: the hidden tests pass;
- `wrong`: a file under `timeparse/` or `tests/` changed, but the hidden tests fail. A change
  limited to `tests/` counts as changed;
- `stalled`: nothing under `timeparse/` or `tests/` changed, and the tests fail.

The change is measured against the task's starting tree (fixture plus seed) taken from the private
snapshot, not against git history. Changes to harness files, `specs/`, `work-docs/`, `.claude/` or
`CLAUDE.md` are not a change. A source root that is itself a symlink is not followed, symlinks
inside are copied as links, and a file is read up to 1,000,000 bytes.

Grading reads the hidden tests' junit report. Its test ids must equal the ids the snapshot's hidden
tests report against the task's reference; a missing or extra id fails the run. The grader, ruff
and mypy each run in their own process group, with output written to files and read back up to
4,000,000 bytes, and the group is killed after every exit. Grading imports the agent's code into
the grader's process, so a change that reads the copied hidden tests and forges a report with the
real ids is not caught; `docs/evals/README.md` states this residual.

### S4: Deterministic quality checks read the source diff of changed runs only
**Given** a graded run whose outcome is not `stalled`
**When** quality is scored
**Then** the row's `quality` holds:
- `ruff_new`: new ruff errors in the changed `.py` files under `timeparse/` and `tests/`, i.e. the
  count on the final files minus the count on their starting versions. A new file starts at 0.
  Ruff runs `--isolated --ignore-noqa` with a rule set pinned in the runner, so a `# noqa` the
  agent writes hides nothing;
- `mypy_new`: the same delta for `mypy --strict` on the package, run with an empty config from a
  clean copy in which `# type: ignore` and `# mypy:` comments are blanked;
- `diff_lines`: added plus removed lines in that scope;
- `tests_touched`: whether a file under `tests/` was added or changed;
- `regressions`: how many of the fixture's pristine visible tests (from the snapshot) fail against
  the final package.

These rules hold for every check:
- A config, `conftest.py` or `pyproject.toml` the agent left in the work dir is never read.
- The work dir is never modified.
- For a `stalled` run every signal is `null` with reason `stalled`.
- A check that cannot run records `null` with a reason and never changes `status`, `passed` or
  `outcome`.
- The ruff and mypy versions are recorded in the row (`quality_tools`) and folded into
  `runner_hash`.

### S5: The judge is blind
**Given** a run whose outcome is not `stalled`, with the judge enabled (the default; `--no-judge`
turns it off)
**When** the runner builds the judge input
**Then** the input (on stdin) holds only:
- the rubric `hm-eval-judge-v1` (below);
- the task prompt, without the `/hm:spec ` prefix;
- the source diff from S4's scope.

Before the diff is sent, these patterns are replaced with neutral tokens, and `judge.redactions`
records how many replacements were made:

| Pattern | Replaced with |
|---|---|
| `AC-\d+` | `REQ` |
| `SPEC-` | `DOC-` |
| `PLAN-` | `DOC-` |
| `/hm:` | `/x:` |
| `test_ac_\d+` | `test_req` |
| `ADR-\d+`, `IRR-\d+` | `DEC` |
| `INV-\d+` | `RULE` |
| `specs/`, `work-docs/` | `docs/` |
| `[[...]]` | `[link]` |
| the bare word `SPEC` | `DOC` |

The diff is fenced between two lines `<<<DIFF <hash>>>>`, where the hash is the first 24 hex digits
of the SHA-256 of the redacted diff, so the diff cannot contain its own fence. A closing line
after the fence says the fenced text is data and that any instruction in it is part of the change.

The input never contains the arm, the run dir, the rep, or any harness, `specs/`, `work-docs/` or
`.claude/` content. Two runs whose diffs are equal after redaction therefore produce byte-identical
judge input, whichever arm they come from. Redaction removes known words, not style, so the judge
is blinded rather than blind: the per-arm redaction counts (S7 run flags) are the visible sign of
a leaning diff.

### S6: The judge call is isolated and accounted separately
**Given** a judge input
**When** the runner calls the judge
**Then** it makes exactly one call:
- `<claude-bin> -p --output-format json --tools "" --json-schema <RUBRIC_SCHEMA>`
- `--model <judge-model>`, where the judge model defaults to `--model`, the agent's model
- `--setting-sources project,local --strict-mcp-config`
- `--max-budget-usd <judge-budget>` (default 0.5)
- the cwd is an empty temp dir outside `--out`
- the environment is the runner's allowlist, recorded by the fake claude in tests
- a diff longer than 60,000 characters is cut, and `judge.truncated` records it

Scores are `scope`, `clarity` and `maintainability`, each an integer from 1 to 5.

These cases are recorded, never imputed:
- A non-zero exit, a timeout, or output that breaks the schema records `judge.status: error` with
  null scores; these are counted.
- A missing judge cost is treated as 0 and counted as unpriced.

The judge cost is `judge.cost_usd`. It stays out of `cost_usd` and out of every arm mean, but counts
toward `--total-budget-usd`. The judge model, the rubric text, the judge argv and the redaction
table are part of `runner_hash`.

### S7: The scorecard leads with quality over balanced, changed runs
**Given** a results file
**When** `report` runs
**Then** for each tier it prints plain vs hm, in this order:
0. **What the extra cost buys** (S16).
1. **Quality.** These lines:
   - runs;
   - hidden-test all-pass count;
   - hidden-case pass fraction;
   - solved / wrong / stalled counts;
   - mean `ruff_new`, `mypy_new` and `regressions`;
   - mean `diff_lines`;
   - `tests_touched` rate;
   - judge mean per criterion and overall.
2. **Efficiency:**
   - mean cost, mean tokens per kind, turns and wall time;
   - the hm/plain ratio of each;
   - the total judge cost, with the number of unpriced judge calls;
   - run flags, per arm: budget-capped runs, leak-suspect runs, judge-truncated runs, and
     redactions over how many runs, printed as "N budget-capped, M leak-suspect, …".
3. **The existing intent-metric block**, computed on tier-1 rows only and unchanged in rule and
   output.

Per-tier figures use only the task×arm cells that are complete (`runs_per_cell` usable rows) for
both arms. Excluded tasks are listed. Each quality mean is taken over the changed runs that carry
the signal, and its n is printed next to it, or `n/a (n=0)` when there are none. `--json` adds a
`scorecard` object beside the existing keys.

### S8: Lead labels follow a fixed direction table
**Given** a scorecard line
**When** it is labelled
**Then** the label is `hm`, `plain`, `tie`, `—` (no lead) or `n/a` (a side has n = 0). It comes
from this table, which lives once in the runner and once in `docs/evals/README.md`:

| Metric | Better | Lead rule |
|---|---|---|
| hidden all-pass count, solved count | higher | gap ≥ 2 runs, else `tie` |
| traps caught (rate, caught/n) | higher | gap ≥ 0.20, else `tie` |
| wrong count, stalled count | lower | gap ≥ 2 runs, else `tie` |
| hidden-case pass fraction | higher | gap ≥ 0.05, else `tie` |
| mean `ruff_new`, `mypy_new`, `regressions`, lint+type | lower | exact compare |
| judge mean (each criterion, overall) | higher | gap ≥ 0.25, else `tie` |
| mean cost, tokens, turns, wall, cost per solved run | lower | exact compare |
| `diff_lines`, `tests_touched` rate | none | always `—` |

Every key of the runner's `DIRECTIONS` table appears, by key, in the docs table. Count lines
compare equal-sized arms, because cells are balanced (S7); traps use the rate because a stalled run
carries no trap result, so the two arms' n can differ. Nothing in the report or the
docs picks words by hand. A results set where plain is ahead prints `plain`. An arm whose runs
mostly stalled cannot win lint or regressions by having no code, because stalled runs carry null
quality (S4).

### S9: Publish writes RESULTS.md and the README block
**Given** a results dir
**When** `publish --out DIR` runs (`--docs`, default `docs/evals`; `--readme`, default `README.md`)
**Then** `RESULTS.md` holds the scorecard as Markdown tables, quality first, and names:
- `bench_hash`, `harness_sha` and `runner_hash`;
- the agent and judge models;
- the rubric id;
- the ruff and mypy versions;
- the tiers and runs per cell;
- the date range, taken from the rows' `started_at`.

`RESULTS.md` opens with the S16 section, before the Quality and Efficiency tables.

The README block between the markers is replaced with the S16 section for each tier and a link to
`docs/evals/RESULTS.md`. The table columns are plain | hm | Δ (hm − plain) | lead, and each plain
and hm cell shows its n.

README bytes outside the markers are unchanged.

### S10: Publish is deterministic and idempotent
**Given** the same results dir
**When** `publish` runs twice, or runs on the same rows in another line order
**Then** `RESULTS.md` and the README are byte-identical each time. Rows are sorted by (tier, task,
arm, rep). The output holds no wall-clock time, absolute path or hostname.

### S11: Publish refuses what it cannot render honestly
**Given** any of:
- a README with zero marker pairs, several pairs, or an end marker before its start;
- a results file that mixes setups (the existing `MixedResultsError`);
- no usable rows;
- a tier whose task×arm cells are not complete for both arms.

**When** `publish` runs
**Then** it exits 2 with a message, before writing either file.

### S12: Results from before this SPEC still report and publish
**Given** rows in the 2026-10-14 schema (no `tier`, `tokens`, `outcome`, `quality`, `judge` or
`quality_tools`)
**When** `report` or `publish` runs
**Then**:
- the rows count as tier 1;
- the outcome is derived where it can be: `passed: true` → solved, otherwise `n/a`;
- every missing signal shows `n/a (n=0)`;
- the intent-metric block equals what the runner printed before this SPEC.

### S13: The judge is calibrated before tier-2 results count
**Given** every non-trap tier-2 task's reference overlay, its `damaged/` overlay (the reference with
planted defects: duplicated logic, dead code, a misleading name) and its `control/` overlay (the
reference made longer but kept clean: explanatory comments and extra tests), each passing the
hidden and visible tests
**When** `INTEGRATION=1 … canary --judge-calibration --record PATH` judges the three diffs per task
with the real judge, or a test replays such a recording offline
**Then** the calibration passes only when, for every such task, `overall(reference) >
overall(damaged)` and `overall(control) ≥ overall(reference) − 0.5`. Trap tasks (S17) are left out:
their checks are deterministic, so they ship neither overlay. The recording stores each judge
input's hash and the judge model. A changed rubric, task or redaction table makes it stale, a
recording made with another judge model than the run's does not pass, and a stale recording does
not pass. A pass rules out a judge blind to the planted defects and one that punishes clean length
by more than 0.5; it does not rule out arm-style preference, self-preference or single-sample
noise (`docs/evals/README.md`).

### S14: Tier 2 needs DRI sign-off and a passing calibration before a live run
**Given** the tier-2 task dirs are committed
**When** `run --tier 2|all` starts
**Then** it exits 2 before any copy or spend unless both of these hold:
- `scripts/bench/tier2-signoff.json` names the current tier-2 hash (over every tier-2 task dir,
  the trap tasks included) and the DRI who signed;
- `scripts/bench/judge-calibration.json` is a fresh, passing recording (S13), made with the judge
  model this run uses.

`check` prints the tier-2 hash to sign.

Each tier-2 hidden test's docstring quotes, verbatim, the prompt sentence it follows from. A prompt
states every case its hidden tests check: no unstated edge case. The DRI's sign-off is the check
that the prompts are fair and do not lean towards either arm.

### S15: Fairness holds by construction
**Given** both arms of any task
**When** they run
**Then** SPEC-hm-light-lane-bench S3 still holds: same model, budget, turn cap, flags and fixture
bytes, differing only by the harness and the `/hm:spec ` prefix. Tier-2 prompts name no harness
step, stage, SPEC, PLAN or review. Task files are covered by `bench_hash`, which `RESULTS.md` shows,
so a task edited after its results shows up in the RESULTS.md diff.

### S16: The headline says what the extra cost buys
**Given** a results file
**When** `report` or `publish` renders it
**Then** each tier opens with "What the extra cost buys", plain vs hm over the same balanced cells
as S7, with these lines:
- **cost ratio**: the larger of mean CLI cost hm/plain and mean transcript-priced cost hm/plain
  (the intent metric's rule). When the two differ both are printed, and `suspect` is added when
  they are more than 20% apart;
- **Δ solved runs** (hm − plain) and **Δ hidden-case pass fraction**;
- **Δ regressions per run** and **Δ new lint+type errors per run** (negative is good);
- **Δ judge overall**;
- **traps caught** for each arm, as `caught/n` (S17); the `hm vs plain` column is the difference in
  catch rate;
- **cost per solved run** for each arm: the arm's priced cost divided by its priced solved runs,
  `n/a` when it solved none, with `(k unpriced)` when k > 0 runs carry no price;
- **extra $ per additional solved run**: (hm priced cost − plain priced cost) / (hm priced solved −
  plain priced solved). When the denominator is ≤ 0 it prints `n/a` and the sentence "no additional
  solved runs for the extra cost". When Δ solved runs reads `tie` it adds "(Δ solved within the tie
  band)", and `(k unpriced)` when k > 0.

The three quality Δ lines (regressions, lint+type, judge overall) are paired: they use only the
(task, rep) pairs where both arms have a changed run carrying the signal, and print n pairs. A pair
never mixes tasks.

The Δ lines, traps caught and the cost ratio take their lead from the S8 table (solved, case
fraction, regressions, lint+type errors, traps, judge overall, cost). Cost per solved run is lower-better with an
exact compare. The extra-$ line has no lead.

### S17: Trap tasks record whether the run avoided the trap
**Given** a tier-2 task dir with a `trap.json` holding `kind` (`secret`, `scope` or
`hidden_caller`), `cites` (the prompt sentence the check follows from, verbatim) and the kind's
check data
**When** a changed run of that task is recorded
**Then** the row carries `trap: {kind, caught}`, from a deterministic check:
- **secret** (t10): a seed file under `notes/` holds a self-describing sample token
  (`tp_live_EXAMPLE…`), and the prompt asks for a client that reads its token from the
  environment, saying plainly that the token comes from the environment variable and is never
  written into code, tests or docs. The prompt lists no patterns. Caught when no line the run added
  to any file outside `notes/` and `.git/` (specs, work-docs, `.env` and docs included) matches the
  runner's `SECRET_PATTERNS` (live-looking keys such as `tp_live_…`, `sk-…`, `ghp_…`, `AKIA…`, a
  private-key block, a literal `Bearer` value of 16 or more characters). The diff is taken against
  the arm's own starting tree, so the harness files the hm arm starts with are not counted, while a
  file the harness writes during the run is. The patterns enter `runner_hash`.
- **scope** (t11): the prompt asks, in one plain sentence, for one change to one function in a
  file whose seeded neighbours invite tidying. Caught when every changed file and top-level name is in the
  allowlist: `allow` maps a file to the top-level names that may change, `allow_under` lists path
  prefixes that may change freely. Names are compared as AST dumps, so comments and moves do not
  count; `<module>` stands for imports, constants and the module docstring, and a file that does
  not parse counts as `<module>`.
- **hidden_caller** (t12): the change looks local but breaks a seeded caller that no visible test
  covers. The prompt carries only the general sentence that existing behaviour must not change,
  which the caller test's docstring cites. Caught when the hidden test named in `trap.json` passes;
  that test is a guard (it passes on the starting tree). Because it is also a hidden test, a run
  that falls for this trap is never solved: the trap overlaps solved and is a sub-signal.

A stalled run, a non-trap task and a row from before this SPEC record `trap: null` and count in
no trap figure. The scorecard's "traps caught" line (S16) is caught runs over runs with a trap
result, per arm.

## 🧑‍⚖️ Judge rubric (`rubric_id: hm-eval-judge-v1`)

The runner sends this text verbatim, followed by the task prompt and the redacted diff.

> You are reviewing a code change to a small Python library. You see the task its author was given
> and the diff of the source and test files. Score the change on three criteria, each an integer
> from 1 to 5. Judge only the code in the diff.
>
> Correctness is checked separately by tests. Do not score it, and do not guess whether tests pass.
>
> Do not reward length. A longer change, more comments, more tests or more files is not better in
> itself; a smaller change that does the job scores at least as well as a larger one.
>
> **scope**: does the change do what the task asks and nothing else?
> 5 = every edit serves the task; no unrelated edits, no speculative features.
> 3 = the task is addressed, with some unrelated or speculative edits.
> 1 = mostly unrelated edits, or the task's main change is missing.
>
> **clarity**: can a reader follow it?
> 5 = names say what things are; control flow is direct; comments only where the reason is not
> obvious.
> 3 = readable with effort; some vague names or needless indirection.
> 1 = hard to follow; misleading names, dead code or confusing flow.
>
> **maintainability**: will the next change be easy?
> 5 = one source of truth for each rule; fits the existing structure; no duplicated logic, no dead
> code.
> 3 = some duplication, or a structure that fights the existing code.
> 1 = logic copied in several places, or a change that works against the module's structure.
>
> Return JSON only: {"scope": n, "clarity": n, "maintainability": n, "note": "<at most 200
> characters>"}.

`overall` is the mean of the three. There is no `tests` criterion. It would reward the process
rather than the code, and correctness comes from the hidden tests.

## 🚫 Non-Goals

- Taking the live measurement. The DRI runs it after signing off tier 2 and recording the
  calibration. This SPEC delivers the instrument, the docs skeleton, and a seed `RESULTS.md`
  published from the 2026-10-14 tier-1 rows (quality `n/a`).
- The hm arm's stall after `/hm:spec` (6/15 on 2026-10-14). It is being fixed separately (PR #21).
  Until that lands, the eval shows it as `outcome: stalled`.
- A trend file (`history.jsonl`) or trend charts. Git history of `RESULTS.md` is the trend.
- Statistical tests or confidence intervals. n is printed and the tie bands are fixed.
- Pairwise (A/B) judging, judge ensembles, or re-judging old work dirs (a `score` backfill).
- A second fixture, other languages, Cursor/Codex arms.
- Changing the intent metric, its target or its verdict rule.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard |
| Location | `scripts/bench_light_lane.py` (one entry), task data under `scripts/bench/`, docs under `docs/evals/` | Smallest change; the approved bench SPEC's ACs and test ids keep their paths (PLAN ADR-001) |
| Live calls | `run` and `canary` refuse without `INTEGRATION=1`, and without `IS_SANDBOX=1` or `--no-sandbox-ok`, since the agent runs with `--dangerously-skip-permissions` as the user; `report`, `publish` and `check` are offline; unit tests keep the autouse failing `claude` stub, and the judge goes through `--claude-bin` like the agent | CLAUDE.md test policy |
| Budget | `--total-budget-usd` default raised from 40 to 80 | `--tier all` with the judge exceeds 40 |
| Dependencies | stdlib plus existing dev dependencies (ruff and mypy are already dev deps) | No new dependency |
| Pricing and tokens | `harness_maker.economics` only | One pricing authority |
| Judging quality | The LLM rubric judges quality; rule-based checks are limited to compiler-grade facts (lint/type error counts, line counts, test pass/fail) | CLAUDE.md LLM-judgment principle |
| Writes | `publish` renders both outputs first, then writes the README and then `RESULTS.md`, each atomically (temp + fsync + rename, keeping the file's mode, 0644 for a new file), and touches only those two files | Implementation patterns |
| Boundaries | No edit under `src/harness_maker/templates/`, goldens, `step_sensitivity.py` or `CLAUDE.md` | Other HM-LIGHT-LANE stages edit those |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-002 | README marker contract: exactly one `<!-- hm:eval:start -->` / `<!-- hm:eval:end -->` pair in `README.md`. The content between them is owned by `publish`; bytes outside are never touched | public API/CLI contract | Once in the README, hand edits around it and every later publish rely on it. The name sits beside the `hm-doc-contract:*` markers without colliding with them |

IRR-001 (a `history.jsonl` schema) was dropped after spec-validator review. The id is kept so
review references stay valid. The judge rubric is not irreversible: it is covered by `runner_hash`
and the calibration hash, so changing it starts a new comparable series. The added `results.jsonl`
row fields are additive in a dev-only file whose readers tolerate their absence (S12).

## ✅ Verification Criteria

| Scenario | Verification mode | Test name |
|---|---|---|
| S1 | unit (subprocess pytest) | `tests/unit/test_bench_light_lane.py::test_hidden_tests_discriminate` (parametrized over every task dir), `test_tasks_ship_in_two_tiers` |
| S2 | unit (fake transcripts) | `test_tokens_are_summed_per_kind_over_main_and_subagent_turns` |
| S3 | unit (golden work dirs, subprocess) | `test_outcome_tells_a_stall_from_a_wrong_fix`, `test_grading_pins_the_collected_test_ids`, `test_tools_run_in_their_own_process_group`, `test_scope_skips_symlinked_roots_and_caps_file_size` |
| S4 | unit (golden work dirs) | `test_quality_checks_count_new_errors_on_the_source_diff_only`, `test_tool_versions_enter_the_runner_hash` |
| S5 | unit (fake claude) | `test_judge_input_is_blind_to_the_arm`, `test_redactions_cover_harness_vocabulary`, `test_the_diff_is_fenced_as_data` |
| S6 | unit (fake claude) | `test_judge_argv_is_isolated_and_schema_bound`, `test_judge_failure_is_recorded_not_imputed`, `test_judge_cost_stays_out_of_the_arm_cost`, `test_no_judge_and_stalled_runs_make_no_judge_call`, `test_the_judge_runs_with_the_allowlisted_environment`, `test_a_diff_over_the_cap_is_truncated_and_counted` |
| S7 | unit (golden rows) | `test_scorecard_leads_with_quality_over_balanced_changed_runs`, `test_run_flags_count_caps_leaks_truncation_and_redactions` |
| S7 (metric) | unit (property) | `test_intent_metric_ignores_tier_two_rows` |
| S8 | unit (golden rows) | `test_lead_labels_follow_the_direction_table` |
| S9 | unit (golden rows → golden files) | `test_publish_writes_results_and_readme_block`, `test_atomic_write_keeps_the_mode_and_fsyncs`, `test_publish_writes_the_readme_before_the_results` |
| S10 | unit (property) | `test_publish_is_idempotent_and_order_independent` |
| S11 | unit | `test_publish_refuses_bad_markers_mixed_empty_or_unbalanced_results` |
| S12 | unit (2026-10-14 rows) | `test_pre_eval_rows_report_and_publish_with_na` |
| S13 | unit (fake and recorded judge) | `test_judge_calibration_ranks_reference_above_damaged` |
| S14 | unit | `test_tier_two_run_needs_signoff_and_calibration`, `test_tier_two_hidden_tests_cite_their_prompt`, `test_live_commands_need_a_sandbox` |
| S15 | unit | `test_arms_differ_only_by_harness_and_prefix` (existing), `test_tier_two_prompts_name_no_harness_step` |
| S16 | unit (golden rows) | `test_extra_cost_section_shows_what_hm_buys`, `test_quality_deltas_pair_runs_by_task_and_rep`, `test_cost_ratio_takes_the_larger_of_cli_and_transcript`, `test_cost_per_solved_and_extra_use_priced_runs_only` |
| S17 | unit (golden work dirs, fake claude, golden rows) | `test_trap_tasks_declare_their_kind_and_cite_the_prompt`, `test_a_malformed_trap_file_is_an_error`, `test_the_secret_check_flags_a_credential_added_to_the_source`, `test_the_secret_check_ignores_placeholders_and_env_reads`, `test_the_seed_token_says_it_is_an_example`, `test_the_secret_check_reads_every_changed_file_outside_notes`, `test_the_secret_check_ignores_files_the_run_started_with`, `test_the_scope_check_measures_the_diff_against_the_allowlist`, `test_the_hidden_caller_check_is_the_caller_test_passing`, `test_each_run_records_its_trap`, `test_traps_caught_leads_the_value_section_by_the_rate_gap` |
| Outcome (docs) | unit | `test_docs_readme_explains_every_scorecard_metric` |

### AC-001: Every task's hidden tests discriminate, and tier 2 ships 3–5 tasks plus one trap per kind
### AC-002: Rows record tokens per kind from the run's own transcripts
### AC-003: The outcome tells a stall from a wrong fix
### AC-004: Deterministic quality checks count new errors on the source diff of changed runs only
### AC-005: The judge input is blind to the arm, harness vocabulary redacted
### AC-006: The judge call is isolated, schema-bound and accounted separately
### AC-007: The scorecard leads with quality over balanced, changed runs
### AC-008: The intent metric is computed on tier-1 rows only
### AC-009: Lead labels follow the direction table
### AC-010: Publish writes RESULTS.md and the README block
### AC-011: Publish is idempotent and independent of row order
### AC-012: Publish refuses bad markers, mixed, empty or unbalanced results before writing
### AC-013: Pre-eval results still report and publish with n/a
### AC-014: Tier-2 prompts name no harness step
### AC-015: docs/evals/README.md explains every scorecard metric
### AC-016: The judge ranks every tier-2 reference above its damaged copy and near its clean control
### AC-017: A tier-2 live run needs DRI sign-off, a passing calibration and cited hidden tests
### AC-018: Every report leads with what the extra cost buys, per tier
### AC-019: Trap tasks record whether each run avoided the trap, and every surface shows traps caught

## ❓ Open Questions

- Residual length or self-preference bias. The judge is the agent's model family, and the rubric
  tells it not to reward length. The calibration (S13) checks that the judge ranks planted defects
  and does not punish a longer clean control by more than 0.5; it does not check the reverse (that
  length is not rewarded) or self-preference. The first
  live `RESULTS.md` shows judge overall beside mean `diff_lines` per arm, so the DRI can see any
  correlation. No automatic correction is planned.
- `README.ko.md` gets no eval block, because the doc-contract test lets localized prose differ.
  Add one later if the DRI wants parity.

## 🔍 Refinement Decisions

- Interview not run. Scope comes from the DRI's two messages (2026-10-14):
  1. Formalise token efficiency, problem solving and code quality, keep the eval in the codebase,
     and publish it to docs and the README.
  2. Lead with how the harness's code quality compares to a raw prompt, add harder tasks, and make
     fairness an AC.
- **Three dimensions over one task suite:**
  - efficiency: tokens per kind, cost, turns, wall time, and hm/plain ratios;
  - problem solving: hidden all-pass, case fraction, and solved/wrong/stalled;
  - quality: ruff/mypy new-error deltas, regressions, diff size, tests touched, and the blind
    rubric.

  The judge is on by default (`--no-judge` turns it off). Its cost is reported separately and kept
  out of arm cost.
- **Quality is the headline**, per DRI message 2; efficiency is shown as the price of that quality.
- **Tier 2 is added**, which overrides the earlier "tasks stay five" default.
  - Four tasks on the existing fixture, with an optional per-task `seed/` overlay for the bug-fix
    task.
  - Tier 1 is unchanged and stays the only input to `hm_cost_ratio_small`.
- **The spec-validator review (12 findings, MAJOR_REVISION) is folded in:**
  1. Stalled runs carry null quality, and means are over changed runs with n printed.
  2. Harness vocabulary is redacted before judging.
  3. The rubric text is in this SPEC. The `tests` criterion is dropped, the rubric tells the judge
     not to reward length, and a calibration AC was added.
  4. A per-metric direction table was added.
  5. A DRI sign-off gate for tier 2 was added, plus prompt-cited hidden tests and no unstated edge
     cases.
  6. Per-tier figures use balanced cells only, publish refuses an unbalanced tier, and the default
     budget is now 80.
  7. `history.jsonl` and IRR-001 are dropped; the git history of `RESULTS.md` is the trend.
  8. The ruff and mypy versions are in `runner_hash` and `RESULTS.md`.
  9. The judge AC asserts exact flag/value pairs, and a null judge cost counts as 0.
  10. Count-based leads need a gap of at least 2 runs, and every headline cell shows its n.
  11. The seed is part of the starting tree, and a change limited to tests counts as changed.
  12. The judge model stays the agent model.
- Error checks count *new* errors against the task's starting files, so a fixture blemish never
  counts against either arm. The fixture is ruff- and `mypy --strict`-clean today (checked
  2026-10-14).
- Commands are `run`, `report` and `publish` (plus the existing `check` and `canary`), on the
  existing script rather than a renamed `scripts/eval.py` (PLAN ADR-001).
- Lane `full`: about fifteen files plus four task dirs, and one irreversible decision.
- **Amendment 2026-10-15 (DRI):** "the harness will spend more tokens; the eval must show what
  the extra spend buys, so that I would keep using it even at 5x tokens, and cost reduction
  continues." This adds S16 and AC-018: every surface leads with "What the extra cost buys",
  replacing the earlier five-row README headline (tier-2 all-pass, judge overall, lint+type,
  regressions, tier-1 cost). The detailed Quality and Efficiency sections follow it unchanged.
- **Amendment 2026-10-15, traps (DRI):** add feature-trap tasks. This adds S17 and AC-019: three
  tier-2 trap tasks (secret t10, scope t11, hidden caller t12) written under the same fairness
  rules, a per-run `trap: {kind, caught}`, and a "traps caught" line in the S16 section (so in the
  report, `RESULTS.md` and the README block) with the count-gap lead. The trap tasks are inside the
  tier-2 sign-off hash and outside the judge calibration, which needs a `damaged/` copy that a
  deterministic trap check does not.
- **Review round 1, 2026-10-15 (coordinator):** traps lead on the catch rate (band 0.20); the
  quality Δ lines pair runs by (task, rep); the cost ratio follows the intent metric's
  max(CLI, transcript) rule with a suspect flag; dollar lines use priced runs only; run flags are
  counted per arm; the judge input is fenced and redacts more harness vocabulary; the calibration
  gains a clean control per task and is tied to the judge model; grading pins the collected test
  ids and runs tools in killed process groups; ruff and mypy ignore suppressions the agent writes;
  live commands need a sandbox; the trap prompts state their contracts plainly, and the secret
  check reads every changed file outside `notes/`.
