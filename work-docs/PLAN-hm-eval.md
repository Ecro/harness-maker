---
type: plan
task_slug: hm-eval
status: planning
created: 2026-10-14
tags: [harness-maker, plan, eval, code-quality, cost]
spec: "[[SPEC-hm-eval]]"
research_doc: "[[RESEARCH-hm-light-lane]]"
interview_rounds: 0
adrs: 6
validator_outcome: MAJOR_REVISION_FOLDED
summary: "Extend the light-lane bench into a quality-first plain-vs-hm eval with run/report/publish, a signed-off tier-2 task set, a calibrated blind judge and docs/evals"
intent: HM-LIGHT-LANE
---

# PLAN — hm-eval

## 🎯 Executive Summary

Grow `scripts/bench_light_lane.py` from a cost ratio into an eval with three dimensions. Each run
records:
- tokens;
- an outcome: solved, wrong or stalled;
- deterministic quality deltas (changed runs only);
- one blind, calibrated LLM-rubric score.

`report` prints a scorecard that leads with quality, computed over balanced cells. `publish`
writes `docs/evals/RESULTS.md` and the README block. Its git history is the trend. Four tier-2
tasks are gated by DRI sign-off and a judge calibration. The intent metric is unchanged and
computed on tier 1. Five phases, one PR. The hm stall after `/hm:spec` is out of scope (PR #21).

## 📐 Architecture Decision Records

### ADR-001: Extend the existing script; no `scripts/eval.py`
**Decided by:** agent.
- `run`, `report`, `check` and `canary` already live in this script. The approved bench SPEC's
  15 ACs, its test file and the runner/bench hashes are all keyed to its path.
- A separate entry would either duplicate the arm, grade and price code, or import it across
  scripts. The tests load the script with `importlib`, so a sibling import needs `sys.path` work.
- So `publish` and four sections (quality, judge, scorecard, publish) go into this file. One entry
  and every existing test stay as they are.
- The cost is file size: about 1,200 lines now, about 1,750 after. Split it at 2,000.
- Code cannot live under `scripts/bench/`, because `bench_hash` covers that tree.

### ADR-002: Score quality inside the cell, at record time
**Decided by:** agent.
- The work dir, the private snapshot (start tree, visible tests) and the judge budget exist only
  while the run is live.
- Scoring in `_record` (and in `_salvage` for `runner_error`) therefore needs no backfill command.
- Old results get `n/a`; they are not re-scored.
- The ruff and mypy versions are read once per run (`--version`) and folded into `runner_hash`, so
  a tool upgrade starts a new series instead of shifting the old one.

### ADR-003: The judge is one blind, schema-bound `claude -p` call per changed run
**Decided by:** spec. This follows the validator findings.
- **Scoring:** absolute, not pairwise, so there is no position bias and no pairing logic.
- **Input:** goes on stdin and holds the rubric `hm-eval-judge-v1` (verbatim from the SPEC, one
  constant), the task prompt, and the redacted source diff. The diff is capped at 60,000 characters
  (`judge.diff_truncated`).
- **Redaction:** a five-row pattern table (SPEC S5), with replacements counted in
  `judge.redactions`.
- **Call flags:** `--tools ""`, `--json-schema` (three 1–5 integers plus a note of at most 200
  characters), the bench's isolation flags, an empty temp cwd, and
  `--judge-budget-usd` (default 0.5).
- **Model:** the judge model is `--model`.
- **Hashing:** the rubric, the redaction table, the judge argv and the model enter `runner_hash`.

### ADR-004: Task data — `tier`, `seed/`, `damaged/`, sign-off and calibration files
**Decided by:** agent. One mechanism per need, all of it under `scripts/bench/`:
- **`tier`:** a one-line file per task dir; absent means 1, so t1–t5 stay byte-identical.
- **`seed/`:** applied in `prepare_work` and committed as `seed`. The S3/S4 start tree is fixture
  plus seed, and `check` grades that start tree.
- **`damaged/`:** the reference with planted defects. It is used only by the calibration and never
  copied into a work dir.
- **`tier2-signoff.json`:** holds `{tier2_hash, signed_by, signed_at}`. `tier2_hash` hashes the
  tier-2 task dirs only, so the file is not inside its own hash.
- **`judge-calibration.json`:** a live `canary --judge-calibration --record` writes it. Per task it
  holds the judge input hashes and scores for the reference and the damaged copy.
- **The gate:** `run --tier 2|all` checks both files before any copy or spend.

### ADR-005: Publish is a pure renderer over balanced rows
**Decided by:** agent.
- `publish` reads rows only through `read_rows` and `ensure_consistent`, then refuses unbalanced
  tiers.
- It sorts rows by (tier, task, arm, rep) and formats floats with fixed places.
- It renders `RESULTS.md` and the README block first, then writes both atomically, so a refusal
  writes nothing.
- There is no `history.jsonl`. The trend is `git log -p docs/evals/RESULTS.md`, whose header names
  `bench_hash`, `harness_sha`, `runner_hash` and the tool versions.
- Goldens live under `tests/unit/fixtures/hm_eval/`.

### ADR-006: The intent metric reads tier-1 rows only
**Decided by:** spec. `hm_cost_ratio_small`'s `how_measured` names the five small timeparse tasks
and a baseline of 22. `summarize()` filters to `tier == 1` (a missing tier counts as 1) before its
existing logic.

## 🧱 Phases

### Phase 1 — Rows gain tier, tokens, outcome, quality (AC-002, AC-003, AC-004)
- `transcript_cost` also returns per-kind token sums from `TokenUsage`.
- `outcome_for(start, work)` compares `timeparse/` and `tests/` between the start tree and the
  work dir; a tests-only change counts as changed.
- `quality_for(...)` returns null with reason `stalled` for a stalled run. Otherwise:
  - it builds the scoped diff;
  - it runs ruff (`--isolated --select <PINNED>`) and `mypy --strict --config-file <empty>` on
    clean copies of the start and final files (via `sys.executable -m`, with a timeout);
  - `regressions` reuses `grade()` with the snapshot's visible tests.
- Tests use golden work dirs built from the fixture, seed and reference overlays.

### Phase 2 — Blind judge (AC-005, AC-006)
- New functions: `redact(diff)`, `judge_input(task, diff)`, `judge_argv(opts)`.
- `run_judge` reuses the `_invoke` machinery: process group, timeout, STOP.
- New flags: `--no-judge`, `--judge-model`, `--judge-budget-usd`.
- `_spent` adds `judge.cost_usd or 0`. Arm means in `summarize` stay on `cost_usd`.
- The fake claude gets a judge mode: it records stdin, argv and cwd, and returns canned JSON, a
  failure, or a result with no cost.

### Phase 3 — Scorecard, direction table, tier-1 metric (AC-007, AC-008, AC-009, AC-013)
- Capture `PRE_EVAL_METRIC_BLOCK` from d48bdc0b on a balanced set of 2026-10-14 rows *before*
  editing `summarize`.
- `scorecard(rows)`:
  - balances cells per tier;
  - takes quality means over changed runs that carry the signal, and records their n.
- `DIRECTIONS` holds the SPEC S8 table. `lead(metric, plain, hm)` applies it: 2-run gap for counts,
  0.05 for the case fraction, 0.25 for judge means, exact compare elsewhere, `—` for `diff_lines`
  and `tests_touched`.
- `SCORECARD_LABELS` lists the labels the scorecard prints.
- `render_report` prints the scorecard, then the unchanged metric block. `--json` adds a
  `scorecard` object.

### Phase 4 — Tier-2 tasks t6–t9, sign-off, calibration (AC-001, AC-014, AC-016, AC-017)
The four task shapes, one each:
- **t6, regression-trap bug fix:** a `seed/` plants a reported parser bug. The prompt states the
  bug and the documented behaviours that must keep working, and `guards.txt` pins those
  behaviours.
- **t7, invariant-keeping change:** extend the parser or formatter. The prompt states the
  round-trip invariant and the input range it holds over, and the hidden tests sweep that range.
- **t8, stated multi-case contract:** the prompt lists every input class it accepts or rejects
  (whitespace, sign, overflow, non-ASCII digits). The hidden tests check exactly those classes.
- **t9, one source of truth:** add a long-form output style. The prompt states that both styles
  must follow the one unit table. The hidden tests patch the table and check both styles.

Authoring order, and the fairness rules that come with it:
1. Write the prompt.
2. Write the reference.
3. Write the hidden tests. Each test's docstring quotes the prompt sentence it follows from, and no
   test checks a case the prompt does not state.
4. Write `damaged/` (duplicated logic, dead code, a misleading name; each defect named in a
   comment).
5. Run `check`, then commit.
6. Hand the tier-2 hash to the DRI for sign-off. Neither arm runs before the sign-off file lands.
   Wording that presumes a winner is not allowed in prompts, tests or docs.
7. Once tier-2 results exist, a task edit changes `bench_hash` and therefore shows in the RESULTS.md
   diff. A task that both arms always pass or always fail is reported, never dropped quietly.

Test updates:
- `test_five_tasks_ship` becomes `test_tasks_ship_in_two_tiers`.
- Discrimination is parametrized over the task dirs found, not a hard-coded list.
- Add the citation, sign-off and calibration tests (fake judge, plus the recording when present).

### Phase 5 — Publish, docs, README (AC-010, AC-011, AC-012, AC-015)
- Add the `publish` subcommand and the goldens (rows, RESULTS.md, README.before/after.md).
- Write `docs/evals/README.md`:
  - what each metric means and the direction table;
  - the rubric id, the fairness rules and the tier-2 gate;
  - the commands;
  - the improvement loop: change the harness, re-run, publish, `git log -p docs/evals/RESULTS.md`.
- Add the marker pair to `README.md`. Seed it, and `docs/evals/RESULTS.md`, with `publish` on a
  balanced copy of the 2026-10-14 tier-1 rows (quality `n/a`, labelled as a pre-eval run).
- Run `tests/structural/test_documentation_contract.py`.
- Raise the `--total-budget-usd` default to 80.

## ⚠️ Risks

- **Judge bias:** the same model family writes and judges. Mitigations: blind and redacted input, a
  rubric that refuses to reward length, a calibration gate, and judge overall shown next to
  `diff_lines` in RESULTS.md.
- **Small samples:** n = 3 per cell. The report prints n everywhere, uses fixed tie bands, and makes
  no significance claim.
- **Live cost:** `--tier all` with the judge runs about $60–80, plus about $1 for calibration.
- **Tier-2 results are unknown in advance.** The tasks may separate the arms in either direction,
  or not at all. Whatever comes out is published. A successor task set needs its own SPEC.

## ✅ Done when

- All 17 ACs have green tests (AC-016's recording check skips until the DRI records a calibration).
- `ruff check`, `ruff format --check` and `mypy --strict` pass on the script and the tests.
- `check` passes for t1–t9.
- `publish` on the seed rows reproduces the committed `docs/evals/RESULTS.md` and README block byte
  for byte.
