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
validator_outcome: NOT_RUN
summary: "Extend the light-lane bench into a quality-first plain-vs-hm eval with run/report/publish, a tier-2 task set and docs/evals"
intent: HM-LIGHT-LANE
---

# PLAN — hm-eval

## 🎯 Executive Summary

Grow `scripts/bench_light_lane.py` from a cost ratio into an eval with three dimensions. Each run
records tokens, a solved/wrong/stalled outcome, deterministic quality deltas and one blind
LLM-rubric score. `report` prints a scorecard that leads with quality. `publish` writes
`docs/evals/RESULTS.md`, `docs/evals/history.jsonl` and the README block. Four tier-2 tasks give
quality room to differ. The intent metric is unchanged and computed on tier 1. Five phases, one PR.

## 📐 Architecture Decision Records

### ADR-001: Extend the existing script; no `scripts/eval.py`
**Decided by:** agent. `run`, `report`, `check` and `canary` already exist there. The approved
bench SPEC's 15 ACs, its test file and the runner/bench hashes are all keyed to that path. A new
entry would either duplicate the arm/grade/price code or import it across scripts (the tests load
the script with `importlib`, so a sibling import needs `sys.path` work). Adding `publish` and four
small sections (quality, judge, scorecard, publish) keeps one entry and every existing test. The
cost is file size: about 1,200 lines now, about 1,700 after. Split it at 2,000 lines. Code cannot
live under `scripts/bench/`, because that tree is hashed into `bench_hash`.

### ADR-002: Score quality inside the cell, at record time
**Decided by:** agent. The work dir, the private snapshot (pristine fixture, visible tests) and the
judge budget all exist only while the run is live. Scoring in `_record` (and in `_salvage` for
`runner_error`) needs no backfill command and keeps "one command runs it all". Old results get
`n/a` (SPEC S11), not a re-score. The trade-off: changing a quality check needs a new live run.
That is acceptable because the check config is folded into `runner_hash` anyway.

### ADR-003: The judge is one `claude -p` call per changed run
**Decided by:** agent. The judge is a single absolute-scoring call per run, not pairwise, so it has
no position bias and needs no pairing logic. The prompt goes on stdin (diffs can exceed argv
limits), with `--tools ""`, `--json-schema` (four 1–5 integers plus a ≤200-char note), the bench's
isolation flags, an empty temp cwd and a `--judge-budget-usd` cap (default 0.5). The diff is capped
at 60,000 characters, and `judge.diff_truncated` records when it was cut. The rubric text sits in
one constant whose hash enters `runner_hash`. The judge model defaults to `--model` (open question
in the SPEC).

### ADR-004: Tiers via a `tier` file; bug-fix seeds via a `seed/` overlay
**Decided by:** agent. A one-line `tier` file per task dir (absent means 1) is the smallest marker
and keeps t1–t5 byte-identical. `seed/` is applied in `prepare_work` and committed as `seed`, so
the agent starts from it. `check` applies it to pristine before grading, and the S3/S4 starting
tree is fixture plus seed. The templates are still built once per arm.

### ADR-005: Publish is a pure renderer over rows; goldens under `tests/unit/fixtures/hm_eval/`
**Decided by:** agent. `publish` reads rows only through `read_rows` + `ensure_consistent`, sorts by
(tier, task, arm, rep), formats floats with fixed places and writes atomically after rendering all
three outputs, so a refusal writes nothing. `history.jsonl` uses `json.dumps(sort_keys=True,
separators=(",", ":"))`. Dedupe goes by `results_digest`.

### ADR-006: The intent metric reads tier-1 rows only
**Decided by:** spec. `hm_cost_ratio_small`'s `how_measured` names the five small timeparse tasks
and a baseline of 22. Mixing tier 2 into it would change the metric without the DRI.
`summarize()` filters `tier == 1` (missing counts as 1) before its existing logic.

## 🧱 Phases

### Phase 1 — Rows gain tier, tokens, outcome and quality (AC-002, AC-003, AC-004)
- `transcript_cost` returns per-kind token sums too (`Spend.tokens`), from `TokenUsage`.
- `outcome_for(start_tree, work)`: difflib/tree compare of `timeparse/` against the snapshot
  fixture plus seed. `quality_for(...)`: a scoped diff of `timeparse/` + `tests/`, ruff
  `--isolated --select <PINNED>` and `mypy --strict --config-file <empty>`, each run on a clean
  copy of the start and final files (`sys.executable -m ruff/mypy`, with a timeout).
  `regressions` reuses `grade()` with the snapshot's visible tests.
- Tests: golden work dirs built from the fixture and reference overlays.

### Phase 2 — Blind judge (AC-005, AC-006)
- `judge_input(task, diff)` → stdin text; `judge_argv(opts)`; `run_judge` with the `_invoke`
  machinery (process group, timeout, STOP). `--no-judge`, `--judge-model`, `--judge-budget-usd`.
- `_spent` adds `judge.cost_usd`; `summarize` arm means stay on `cost_usd`.
- The fake claude grows a judge mode: it records stdin, argv and cwd and returns canned JSON or a
  failure.

### Phase 3 — Scorecard, lead rule, tier-1 metric (AC-007, AC-008, AC-009, AC-013)
- `scorecard(rows)` → dict per tier and arm; `lead(metric, plain, hm)` with a direction table and
  the 0.25 judge band; `SCORECARD_LABELS`.
- `render_report` prints the scorecard first, then the existing metric block unchanged. `--json`
  adds `scorecard`.
- Capture `PRE_EVAL_METRIC_BLOCK` from d48bdc0b on three 2026-10-14 rows *before* editing
  `summarize`.

### Phase 4 — Tier-2 tasks t6–t9 (AC-001, AC-014)
- t6: a bug fix with a regression trap. A `seed/` plants a reported parser bug; the obvious
  one-line fix breaks a documented behaviour pinned in `guards.txt`.
- t7: an invariant-keeping change. Extend the parser or formatter while
  `parse_duration(format_duration(n)) == n` keeps holding; hidden tests sweep a range.
- t8: edge cases from a general contract. The prompt states one validation rule; hidden tests probe
  whitespace, sign, overflow and non-ASCII digits without the prompt listing them.
- t9: maintainability. Add a long-form output style. Hidden tests patch the unit table and expect
  both styles to follow it (one source of truth).
- **Authoring rule (fairness):** prompt and reference first, then hidden tests from the prompt's
  contract only, then `check`. Neither arm runs before the tasks are committed. No task is edited
  after its first live result without a note in `docs/evals/README.md` (the `bench_hash` change is
  visible anyway). A task both arms always pass or always fail is reported, never dropped quietly.
- Update `test_five_tasks_ship` → `test_tasks_ship_in_two_tiers` and parametrize discrimination over
  the task dirs found.

### Phase 5 — Publish, docs, README (AC-010, AC-011, AC-012, AC-015)
- The `publish` subcommand, plus goldens in `tests/unit/fixtures/hm_eval/` (rows, RESULTS.md,
  history_row.json, README.before/after.md).
- `docs/evals/README.md`: what each metric means, the fairness rules, the lead rule, the commands,
  how to compare with `history.jsonl` (a one-line `jq`), and the improvement loop.
- Add the marker pair to `README.md` and seed it with `publish` on the 2026-10-14 tier-1 rows
  (quality `n/a`, labelled as a pre-eval run). Then run `tests/structural/test_documentation_contract.py`.

## ⚠️ Risks

- **Judge self-preference**: the same model family writes and judges. Mitigation: blind input,
  the model pinned in `runner_hash`, and the open question to the DRI.
- **n = 3 per cell is small.** The report prints n and a fixed tie band; it makes no significance
  claim.
- **Live cost** of `--tier all` with the judge is about $60–80 per grid, above the 40 default
  (open question).
- **The tier-2 headroom is a hypothesis.** If plain also solves t6–t9 every time, the eval says so
  and the tasks need a harder successor in a later SPEC, not a quiet re-tune.

## ✅ Done when

All 15 ACs have green tests, `ruff check`, `ruff format --check` and `mypy --strict` pass on the
script and tests, `check` passes for t1–t9, and `publish` on the seed rows reproduces the committed
`docs/evals/RESULTS.md` and README block byte for byte.
