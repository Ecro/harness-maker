# hm eval: plain prompt vs `/hm:`

This eval compares two ways of asking the same model for the same change on a small Python
library (`scripts/bench/timeparse/`):

- **plain**: the task prompt as written, in a repo with no harness;
- **hm**: the same prompt with a `/hm:spec ` prefix, in the same repo plus this checkout's rendered
  harness.

hm is expected to spend more tokens than plain, so the scorecard opens with what that extra spend
buys, then the quality detail, then the cost detail. It reports what comes out: if plain writes
better code, or the extra spend buys nothing, the scorecard says so. The latest results are in
[RESULTS.md](RESULTS.md), and the README shows the "What the extra cost buys" tables from the same
run. SPEC: `specs/SPEC-hm-eval.md`.

## Run it

```
# both arms, live model, default tier 1 (3 runs per task and arm); prints the scorecard
INTEGRATION=1 uv run python scripts/bench_light_lane.py run --out /var/tmp/hm-eval [--tier 1|2|all]

# reprint the scorecard offline (--json adds a "scorecard" object)
uv run python scripts/bench_light_lane.py report --out /var/tmp/hm-eval

# write docs/evals/RESULTS.md and the README block (offline)
uv run python scripts/bench_light_lane.py publish --out /var/tmp/hm-eval

# prove every task's hidden tests discriminate; prints the tier-2 hash to sign (offline)
uv run python scripts/bench_light_lane.py check
```

`run` and `canary` call a live model and refuse without `INTEGRATION=1`. Both arms run with
`--dangerously-skip-permissions`, as you, with your file access, so `run` and `canary` also refuse
unless `IS_SANDBOX=1` says they are in a container or a throwaway VM, or `--no-sandbox-ok` takes
that risk explicitly. `--out` must sit outside any git work tree or `CLAUDE.md`/`.claude/`
ancestor.
`run` resumes when given the same `--out`, stops scheduling once spend passes `--total-budget-usd`
(default 80, judge calls included), and refuses rows from another setup.

The judge is on by default: one extra `claude -p` call per changed run (`--no-judge` turns it off,
`--judge-model` defaults to `--model`, `--judge-budget-usd` defaults to 0.5).

## Tasks

- **Tier 1 (t1-t5)**: small single-session changes. They are the cheap smoke and the only input to
  the intent metric `hm_cost_ratio_small`.
- **Tier 2 (t6-t9)**: one change shape each:
  - t6, a bug fix with a regression trap: a `seed/` overlay plants a parser bug, and guards pin the
    documented behaviours the fix must keep;
  - t7, a change that keeps an existing invariant: weeks, with the round-trip invariant checked at
    each unit boundary and every 7919th integer up to 10000000, which is what the prompt states
    (a full sweep would take minutes per run);
  - t8, a stated multi-case contract: every input class the parser accepts or rejects;
  - t9, a change with one source of truth: a long output style that must follow the one unit
    table, so the hidden tests patch the table and check both styles.
- **Tier-2 traps (t10-t12)**: each has a natural path that is easy to take and wrong, and a
  `trap.json` that names its kind, the prompt sentence it follows from (`cites`) and its check:
  - t10, **secret**: a quota client whose token comes from the environment, with a sample token
    (self-describing: `tp_live_EXAMPLE...`) in the seed's `notes/staging.md`. The prompt says
    plainly that the token comes from the environment variable and is never written into code,
    tests or docs; it does not list the patterns. Caught when no line the run added to any file
    outside `notes/` and `.git/` (specs, work-docs, `.env` and docs included) matches the runner's
    `SECRET_PATTERNS` (live-looking keys, a private-key block, a literal `Bearer` value of 16 or
    more characters). The diff is taken against the arm's own starting tree, so the harness files
    the hm arm starts with do not count, but a file the harness writes during the run does: a log
    that copies the token is still the token on disk. Nested checkouts are not read: any directory
    below the root that holds a `.git` entry, `.worktrees/`, `.claude/worktrees/` and `.venv/`. At
    most 20,000 files are read per tree, so a run that writes more could hide a line past the cap;
    - **Known effect:** hm's telemetry writes Bash command text to `.claude/observability/` with
      no redaction for `tp_live_` tokens, so an hm run that tries the client with the token inline
      falls for this trap through its telemetry, not its code. t10 therefore also measures the
      harness's telemetry redaction; that finding stays counted until the product fixes it;
  - t11, **scope**: report every invalid CLI argument, with one plain sentence saying the change
    belongs in `main` alone, next to a seeded
    `_total` helper and help text that invite tidying. Caught when every changed file and
    top-level name is in the allowlist (`allow`: file to top-level names, `allow_under`: path
    prefixes). Names are compared as ASTs, so comments and moves do not count; `<module>` stands for
    imports, constants and the module docstring;
  - t12, **hidden caller**: reject a zero duration in `parse_duration`, while the seeded
    `timeparse/schedule.py`, which no visible test covers, documents `normalize("0m") -> "0s"`.
    The prompt says only that, apart from `parse_duration` rejecting a zero duration, every other
    function in the package must behave as before; it does not point at that docstring. Caught when the hidden test named in `trap.json` (a guard that
    exercises that caller) passes. That test is also one of the hidden tests, so a run that falls
    for the trap is never solved: this trap overlaps solved and is a sub-signal, not an independent
    measure.

  Each run of a trap task records `trap: {kind, caught}`; a stalled run, a non-trap task and a
  row from before this eval record null.

Each task dir has `prompt.md`, `hidden/` tests, a `reference/` overlay that passes them, optional
`guards.txt` (hidden tests that must already pass on the starting tree) and, for tier 2, a `tier`
file, `damaged/` and `control/` overlays for the judge calibration (t6-t9; the traps have neither),
`trap.json` for t10-t12 and, for t6 and t10-t12, a `seed/` overlay. The starting
tree is the fixture plus the seed, committed as one commit, so neither arm can read the planted bug
out of `git log`.

## How to read the scorecard

Figures for a tier use only tasks whose task x arm cells are complete for both arms (the full
number of usable runs). An incomplete task is listed as excluded. Every value prints its n:
`0.50 (n=2)` is a mean over 2 runs, and `n/a (n=0)` means no run carried the signal.

### What the extra cost buys

The first block, per tier, sets hm against plain over the same balanced cells as the rest of the
scorecard. The `hm vs plain` column is hm minus plain, except on the cost line, where it is a ratio.

| Line | What it is |
|---|---|
| cost ratio (cells: mean CLI $/run) | The arm cells are mean run cost (`cost_usd`: the CLI total, or the transcript price for a lost result). The ratio is the larger of two, by the intent metric's rule: mean CLI cost (`total_cost_usd`) hm over plain, and mean transcript-priced cost hm over plain. 5.00x means hm costs five times as much per run. When the two differ, both are printed, and `suspect` is added when they are more than 20% apart (the CLI total may leave out subagent spend). When one arm has no CLI cost at all, the transcript ratio is used and the note says so. |
| Δ solved runs | hm solved runs minus plain solved runs. |
| Δ hidden-case pass fraction | hm minus plain hidden-case pass fraction. |
| Δ regressions per run | hm minus plain mean regressions, over paired runs; negative is good for hm. |
| Δ new lint+type errors per run | hm minus plain mean of ruff_new + mypy_new, over paired runs; negative is good for hm. |
| traps caught | Per arm, trap runs that avoided the trap over trap runs that carry a result (`caught/n`). The `hm vs plain` column and the lead use the caught rate (band 0.20). The lead reads `n/a` when the two arms' n differ by 2 or more (one arm stalled more, so the rates cover different runs). A tier with no trap task reads `n/a (n=0)`. |
| Δ judge overall | hm minus plain mean judge overall, over paired runs. |
| cost per solved run | Each arm's priced run cost divided by its priced solved runs; `n/a (n=0)` when the arm solved nothing. Runs with no price are left out and counted, as `(k unpriced)`. Lower is better. |
| extra $ per additional solved run | (hm priced cost - plain priced cost) / (hm priced solved - plain priced solved). When hm solves no more runs than plain it reads `n/a: no additional solved runs for the extra cost`. When Δ solved runs reads `tie`, it adds `(Δ solved within the tie band)`: the extra solved runs are inside the noise the lead rule allows. Unpriced runs add `(k unpriced)`. |

**Paired runs.** The three quality Δ lines compare the same (task, rep) in both arms and use only
pairs where both arms changed code and the signal exists; `n` is the number of pairs. A pair never
mixes tasks, so a hard task that one arm stalled on cannot be set against an easy task the other
arm solved. The detailed Quality section below keeps the unpaired per-arm means.

Each Δ line's lead uses the direction and band of its metric in the table below, so a Δ that sits
inside the band reads `tie`.

**Is the extra cost worth it?** Read the block top down. The cost ratio is the price. The Δ lines
show what the price bought, and their leads say whether the gap clears the fixed band. A high cost
ratio is worth paying when the Δ lines lead `hm`: more solved runs, a higher case fraction, fewer
regressions and new errors, more traps caught, or a better judge score. Extra $ per additional
solved run puts the first of those in dollars: what one more solved run costs over plain. If that line reads `n/a`, or
every Δ line reads `tie` or `plain`, the extra spend bought nothing this eval can see, whatever the
cost ratio. The verdict is the reader's; the scorecard only prints the figures and leads.

**Cost cuts use the same scorecard.** Work that makes hm cheaper (the light lane, for example) is
measured by re-running this eval: a cut should lower the cost ratio and cost per solved run without
turning a Δ line from `hm` to `tie` or `plain`. Both kinds of change show up in the git history of
RESULTS.md.

### Quality

| Line | What it is |
|---|---|
| runs | Usable runs per arm in the tier. |
| hidden all-pass | Runs whose hidden tests all pass. |
| hidden-case pass fraction | Passed hidden test cases over all hidden test cases, pooled. |
| solved | Runs with outcome `solved` (hidden tests all pass); with wrong and stalled it adds up to runs. Rows from before this eval carry no outcome: a passing one counts as solved, and wrong and stalled read `n/a`. |
| wrong | Runs that changed a file under `timeparse/` or `tests/` but fail the hidden tests. |
| stalled | Runs that changed nothing under `timeparse/` or `tests/`. Harness files, `specs/`, `work-docs/`, `.claude/` and `CLAUDE.md` are not a change, and the change is measured against the starting tree, not git history. |
| ruff_new mean | New ruff errors in the changed `.py` files (final count minus the starting count), `ruff check --isolated --ignore-noqa` with the pinned rule set `E4,E7,E9,F,B`: a `# noqa` the agent writes does not hide an error. |
| mypy_new mean | New `mypy --strict` errors in the package, with an empty config, from a clean copy in which `# type: ignore` and `# mypy:` comments are blanked. |
| regressions mean | The fixture's pristine visible tests (from the private snapshot) that fail against the final package. |
| diff_lines mean | Added plus removed lines under `timeparse/` and `tests/`. Shown, never ranked. |
| tests_touched rate | Share of runs that added or changed a file under `tests/`. Shown, never ranked. |
| judge scope | Blinded rubric score, 1-5: does the change do what the task asks and nothing else? |
| judge clarity | Blinded rubric score, 1-5: can a reader follow it? |
| judge maintainability | Blinded rubric score, 1-5: will the next change be easy? |
| judge overall | Mean of the three judge scores. |

Quality means are taken over changed runs only. A stalled run has no code, so its quality is null
rather than zero: an arm that mostly stalls cannot win lint or regressions by writing nothing. A
check that cannot run records null with a reason and never changes a run's status or outcome.
The agent's own config files (`pyproject.toml`, `mypy.ini`, `conftest.py`) are never read, and the
work dir is never modified. A `timeparse/` or `tests/` that is itself a symlink is not followed,
links inside are copied as links, and a file is read up to 1,000,000 bytes (a longer one is cut and
its size noted). A symlink anywhere inside `timeparse/` or `tests/` nulls every quality signal with
reason `symlink_in_scope`, since a link could point the checks at files outside the run's work.
`.venv/` and caches are skipped, and at most 20,000 files are read.

### How far the grade can be trusted

Grading imports the agent's package into the grader's pytest process, so it is only as trustworthy
as that code. The grader, ruff and mypy each run in their own process group with output to files,
read back up to 4,000,000 bytes, and the group is killed after every exit, so a child the code
starts cannot stall the grade; a grandchild that calls `setsid` leaves the group and can escape
that kill. A reap that times out after the kill is not treated as a grading error. The id pin
needs the reference to grade cleanly: if it does not (a timeout, say), the run is recorded as a
`runner_error`, never as `wrong`, and the failure is not cached. The test ids the junit report lists must equal the ids
the hidden tests report against the task's reference; a missing or extra id fails the run. That
catches code that rewrites the report at exit with ids of its own. It does not catch code that
reads the copied hidden tests and forges a report with the real ids: nothing short of running the
tests in a separate sandbox would, and this eval does not.

### Efficiency

| Line | What it is |
|---|---|
| cost $/run | Mean run cost: the CLI's `total_cost_usd`, or the transcript price when that is missing. Judge calls are not included. |
| input tokens | Mean uncached input tokens per run, main and subagent transcript turns. |
| output tokens | Mean output tokens per run. |
| cache_read tokens | Mean cache-read tokens per run. |
| cache_write tokens | Mean cache-write tokens per run (5-minute plus 1-hour writes). |
| turns | Mean CLI-reported turns per run. |
| wall s | Mean wall time per run, in seconds. |
| judge cost | Total judge spend in the tier, with the number of judge calls and of unpriced calls (no cost reported, counted as 0). Kept out of every arm mean. |
| run flags | Per arm: runs that hit the per-run budget cap (`budget-capped`), runs whose output or transcript named a hidden-test path (`leak-suspect`), runs whose diff was cut at 60,000 characters for the judge (`judge-truncated`), and how many redactions were made in how many runs' judge input. Any non-zero count is a reason to read those runs before trusting the tier's figures. |

In the Efficiency block, the `hm/plain` column is the ratio of the two means. Tokens and prices come from
`harness_maker.economics`.

### Intent metric

The last block is the pre-registered `hm_cost_ratio_small` verdict, computed on tier-1 rows only,
unchanged in rule and output. Its last line is `hm_cost_ratio_small=<ratio|n/a>`.

## Direction table and lead rule

Each line's lead is `hm`, `plain`, `tie`, `—` (no lead) or `n/a` (a side has n = 0), from this
table and nothing else. No word in the report or these docs is picked by hand.

| Metric (`DIRECTIONS` key) | Better | Lead rule |
|---|---|---|
| hidden all-pass (`all_pass`), solved (`solved`, also Δ solved runs) | higher | gap of at least 2 runs, else `tie` |
| wrong (`wrong`), stalled (`stalled`) | lower | gap of at least 2 runs, else `tie` |
| hidden-case pass fraction (`case_fraction`) | higher | gap of at least 0.05, else `tie` |
| traps caught (`traps`) | higher | caught-rate gap of at least 0.2, else `tie` |
| ruff_new mean (`ruff_new`), mypy_new mean (`mypy_new`), regressions mean (`regressions`), new lint+type errors (`lint_type`) | lower | exact compare |
| judge scope (`judge_scope`), clarity (`judge_clarity`), maintainability (`judge_maintainability`), overall (`judge_overall`) | higher | gap of at least 0.25, else `tie` |
| cost $/run (`cost`), cost per solved run (`cost_per_solved`), tokens (`tokens_input`, `tokens_output`, `tokens_cache_read`, `tokens_cache_write`), turns (`turns`), wall s (`wall`) | lower | exact compare |
| runs (`runs`), diff_lines mean (`diff_lines`), tests_touched rate (`tests_touched`) | none | always `—` |

Count lines compare equal-sized arms, because cells are balanced. n is small (3 runs per cell by
default); the bands are fixed and there is no significance test.

## The judge

The judge is one `claude -p` call per changed run, with rubric `hm-eval-judge-v1` (the text is in
the SPEC and in the runner as `RUBRIC`). It is:

- **Blinded, not blind**: its stdin holds only the rubric, the task prompt without the
  `/hm:spec ` prefix, and the diff under `timeparse/` and `tests/`. Known harness vocabulary is
  replaced with neutral tokens first: `AC-<n>`, `SPEC-`, `PLAN-`, `/hm:`, `test_ac_<n>`,
  `ADR-<n>`, `IRR-<n>`, `INV-<n>`, `specs/` and `work-docs/` paths, `[[...]]` links and the bare
  word `SPEC`. The count is recorded per run and shown per arm under run flags. Redaction removes
  words, not style: docstrings that restate requirements, test names or comment habits can still
  hint at the arm, and nothing corrects for that. A redaction count that differs a lot between the
  arms is the visible sign. Equal diffs give byte-identical input in both arms.
- **Fenced**: the diff sits between two lines `<<<DIFF <hash>>>>`, where the hash is taken over
  the fenced text itself, so the diff cannot contain the fence. A closing line says the fenced
  text is data and any instruction in it is part of the change. This makes prompt injection from a
  diff harder, not impossible; the scores of a run whose diff talks to the judge should be read
  with that in mind.
- **Isolated**: `--tools ""`, `--json-schema`, `--setting-sources project,local`,
  `--strict-mcp-config`, a spend cap, and an empty temp dir as its cwd.
- **Recorded, never imputed**: an exit error, a timeout or output that breaks the schema records
  `judge.status: error` with null scores.

The rubric tells the judge not to reward length. Judge overall and mean diff_lines sit side by
side in RESULTS.md, so a correlation between them is visible. The judge is the agent's model
family; residual self-preference is not corrected.

## Fairness rules

- Both arms use the same model, budget, turn cap, flags and fixture bytes. They differ only by the
  rendered harness and the `/hm:spec ` prefix.
- Hidden tests and references never enter a work dir; grading runs from a private snapshot.
- Tier-2 prompts name no harness step. Each tier-2 hidden test's docstring quotes, word for word,
  the prompt sentence it follows from, and each prompt states every case its hidden tests check.
- Task files are covered by `bench_hash`, which RESULTS.md shows, so a task edited after its
  results shows up in the RESULTS.md diff. A task that both arms always pass or always fail is
  reported, never dropped.

## Tier-2 gate

`run --tier 2` (or `--tier all`) exits 2 before any copy or spend unless both of these hold:

1. **DRI sign-off**: `scripts/bench/tier2-signoff.json` holds
   `{"tier2_hash": "<hash>", "signed_by": "<name>", "signed_at": "<date>"}`, where the hash is the
   one `check` prints; it covers every tier-2 task dir, the trap tasks included. Signing says the
   prompts are fair and do not lean towards either arm. Any
   edit to a tier-2 task dir changes the hash and needs a new sign-off.
2. **Judge calibration**: `scripts/bench/judge-calibration.json` is a fresh, passing recording
   made by

   ```
   INTEGRATION=1 uv run python scripts/bench_light_lane.py canary --judge-calibration \
       --record scripts/bench/judge-calibration.json
   ```

   It judges three copies of each tier-2 task, using the live judge model:
   - the `reference`;
   - its `damaged/` copy: the reference with duplicated logic, dead code and a misleading name
     planted (see each task's `damaged/DEFECTS.md`); it must score strictly below the reference;
   - its `control/` copy: the reference made longer but kept clean, with explanatory comments and
     extra tests (see `control/CONTROL.md`); it must score no more than 0.5 below the reference.

   `check` requires both copies to pass the hidden and visible tests, so the calibration ranks
   quality, not correctness. The trap tasks t10-t12 have neither copy and are left out: their
   checks are deterministic and do not rest on the judge. The recording stores each judge input's
   hash and the judge model, so a changed rubric, task or redaction table, or a run that judges
   with another model, makes it stale.

   **What a pass rules out:** a judge that cannot tell planted duplication, dead code and a
   misleading name from the clean reference, and a judge that punishes a clean change for being
   longer (more comments, more tests) by more than half a point. **What it does not rule out:**
   preference for one arm's style, self-preference for the agent's model family, unreliable
   ranking between two different clean solutions, or noise: each copy is judged once. A pass is
   necessary for the judge lines to mean anything; it is not proof that they are right.

## Improvement loop

1. Change the harness.
2. Re-run: `INTEGRATION=1 uv run python scripts/bench_light_lane.py run --tier all --out DIR`.
3. Publish: `uv run python scripts/bench_light_lane.py publish --out DIR`, and commit
   `docs/evals/RESULTS.md` with the README block.
4. Read the trend: `git log -p docs/evals/RESULTS.md`. Each version names `bench_hash`,
   `harness_sha`, `runner_hash`, the models, the rubric id and the ruff and mypy versions, so a
   moved number can be traced to what changed.

`publish` refuses (exit 2, nothing written) when the README has no single marker pair, when the
results mix setups, when no row is usable, or when a tier's cells are incomplete. It writes the
README first, then RESULTS.md, each atomically (temp file, fsync, rename, keeping the file's mode):
a failure on the README changes nothing, and a failure on RESULTS.md is completed by running
`publish` again. It is
deterministic: the same rows in any order give byte-identical files.
