---
type: plan
task_slug: hm-light-lane-bench
status: planning
created: 2026-10-14
tags: [harness-maker, plan, python, bench, cost]
spec: "[[SPEC-hm-light-lane-bench]]"
research_doc: "[[RESEARCH-hm-light-lane]]"
interview_rounds: 0
adrs: 15
validator_outcome: NOT_RUN
summary: "Stage 4 runner: one script, a reconstructed timeparse fixture with five hidden-test tasks, offline tests"
intent: HM-LIGHT-LANE
---

# PLAN — hm-light-lane-bench (stage 4, runner only)

## 🎯 Executive Summary

Put the bench that produced `hm_cost_ratio_small = 22` back in the repo as one script plus data,
so a single opt-in command can re-measure after stages 2b and 3. The measurement itself is out of
scope here.

## 📐 Architecture Decision Records

### ADR-001: One script under `scripts/`, data under `scripts/bench/`
**Decided by:** agent. `src/` ships in the wheel, and `tests/` is collected, so hidden
`test_*.py` files there would run (and fail on purpose) in CI. `scripts/` is linted but neither
shipped nor collected. One file (`scripts/bench_light_lane.py`) keeps the runner readable; unit
tests load it with `importlib`, as `test_measure_wiki_fact_window.py` already does.

### ADR-002: Ratio from the CLI's `total_cost_usd`; transcript price as cross-check and fallback
**Decided by:** agent. The baseline bench read `claude -p --output-format json` (its notes report
the same fields: cost, turns, cache-create tokens), so the same source keeps the new number
comparable to 22. The runner also prices the run's own transcripts, subagents included, through
`harness_maker.economics` (the repo's only price table) and prints both ratios. A run with no CLI
result (timeout) takes the transcript price. Whether `total_cost_usd` includes subagents in the
current CLI is an open question the first live run answers by itself.

### ADR-003: Grade outside the work dir
**Decided by:** agent. Only `work/timeparse` is copied into a fresh temp dir (outside `--out`,
removed after) next to a copy of the hidden tests, and pytest runs there with its own `-c
pytest.ini`, `--rootdir`, `python -s`, `PYTHONNOUSERSITE=1` and a minimal environment. A
`conftest.py`, pytest config, `pytest.py` or `sitecustomize.py` the agent left in the work dir can
then neither shadow pytest nor skip or rewrite the hidden tests, and nothing graded sits where a
later run can read it. Pass means every hidden test passed; a collection error, a skip or a
timeout is a failure.

### ADR-004: Reconstruct the five timeparse tasks, with the trap stated in the task
**Decided by:** agent. The original fixture is gone. The five task shapes and traps are kept
(carry in rounding, atomic replace with validation first, strict ISO grammar, report every bad
input, exact token refill at 0.1 s steps). Each prompt states the required behaviour with an
example, so a hidden test checks the stated contract and not a guess. `check` proves offline that
every task's hidden tests fail on the fixture and pass on its reference.

### ADR-005: Model defaults to the baseline's `claude-sonnet-5-5`
**Decided by:** agent (source: `.claude/intent.yaml` rule "TUNE values are not moved to a new
model without re-measure"). The operator can pass `--model`; the model is stamped into every row
and the evidence string.

### ADR-006: Results are an append-only JSONL with resume; mixing is refused
**Decided by:** agent. A full bench is ~30 headless runs and ~$35; a crash must not repeat paid
cells. Rows carry a bench hash (fixture + tasks) and the harness SHA, and `report` refuses a file
that mixes either, because a ratio across two harness versions means nothing.

### ADR-007: The output dir must not sit under a git tree or a `CLAUDE.md`
**Decided by:** agent. Claude Code reads `CLAUDE.md` from every ancestor of the launch dir, so a
bench run inside this repo would load harness-maker's own CLAUDE.md into both arms. The default
`--out` is a fresh system temp dir.

### ADR-008: Verdict on the unrounded, more conservative ratio; `suspect` on disagreement
**Decided by:** agent (review round 1). It is open whether `total_cost_usd` includes subagent
spend, so the verdict judges the larger of the CLI and transcript ratios and returns `suspect`
when they differ by more than 20%. Ratios are compared unrounded (5.004 is above 5); the rounded
value is only printed and recorded. Means use `math.fsum` and the target check allows 1e-9.

### ADR-009: Unknown cost is unknown, not $0
**Decided by:** agent. A run with no CLI cost and an empty transcript gets `cost_usd: null` and
`cost_source: unknown`. It stays in the pass rate but leaves the cost mean and is counted in the
report, because recording $0 would deflate the arm's mean and could turn a miss into a pass.

### ADR-010: The agent gets project-only settings, an allowlisted environment and a spend cap
**Decided by:** agent. `--setting-sources project,local --strict-mcp-config` keep `~/.claude`
settings, plugins, MCP servers and memory out of both arms (flags verified in `claude --help`;
`--bare` is not used because it skips the hooks the hm arm needs). The environment is an
allowlist (auth, proxy, CA, locale, `PATH`/`HOME`; `--pass-env` adds names). `--max-budget-usd`
(default 5) caps one run and `--total-budget-usd` (default 40) stops new cells. None of this is a
sandbox: the module docstring and `--help` say to run live in a container. `--jobs` defaults to 1.

### ADR-011: Hidden tests are graded from a private snapshot; leaks are flagged, not prevented
**Decided by:** agent. `scripts/bench/` is copied to a 0700 temp dir at run start and its hash
verified against the checkout; grading and the hash stamped into rows use the copy, so an agent
cannot alter what later cells are graded with. It can still read the checkout path, so agent
output and transcripts are scanned for it and a hit sets `leak_suspect` on the row and a count in
the report.

### ADR-012: Stop signals kill the agents; one crashing cell costs one cell
**Decided by:** agent. Agents run in their own session (so a timeout kills their children), which
also means Ctrl-C never reaches them. The runner keeps a registry of live process groups, turns
SIGTERM into `KeyboardInterrupt`, and on any abort sets a stop flag, cancels queued futures
(`shutdown(wait=False, cancel_futures=True)`), kills every group and exits 130. Reaping after a
kill is time-bounded. An exception in a cell becomes a `runner_error` row (retried on resume).

### ADR-013: Resume checks the same fingerprint `report` does, plus the runner settings
**Decided by:** agent. Rows carry `runner_hash` (prefix, agent argv, harness render argv,
timeout) beside bench hash, harness SHA and model, and `run` applies the mixed-rows check to the
existing file before any spend. The harness SHA is HEAD plus a hash of `git diff HEAD`, so two
different dirty trees differ. Rows are appended with one `os.write` on an `O_APPEND` fd, a torn
line is skipped with a warning, and a `flock` on `--out/.run.lock` refuses a second runner.

### ADR-014: Render each arm's template once per run
**Decided by:** agent. The fixture repo (and, for hm, the rendered harness) is built once into
`--out/.templates/<arm>` and copied per cell. Render output holds no absolute path (checked), the
cost is one render instead of one per hm cell, and a render failure stops the run before any
model spend.

### ADR-015: Hidden tests must fail on pristine unless marked as guards
**Decided by:** agent. `check` prints per-test pristine outcomes and fails when a hidden test
passes on the pristine fixture and is not listed in the task's `guards.txt`, or a listed guard
does not pass there. t1's parse-back tolerance is half the last kept unit (the old
`max(seconds, 1)` accepted any rounding), and t5's default-clock test uses a 1/1h rate so a slow
machine cannot flake it. Tests whose module cannot import on pristine (t2, t3, t5) show one
collection error; that still proves the module is missing, not each test.

## 📝 Implementation Plan

1. **Phase 1 — fixture and tasks.** scope: `scripts/bench/timeparse/`, `scripts/bench/tasks/t1..t5/`
   (prompt.md, hidden/, reference/) · exit: `check` green.
2. **Phase 2 — runner.** scope: `scripts/bench_light_lane.py` (`run`, `report`, `check`) · exit: unit
   tests green.
3. **Phase 3 — tests.** scope: `tests/unit/test_bench_light_lane.py` · written first, red before
   phase 2.

depends_on: stage 1 (merged) · merge_hazards: none (no shared files with stages 2a/2b/3) · risk:
low · rollback: revert.

## 🧪 Testing Strategy

Offline only: a fake `claude` executable (a Python script the tests write) applies the task's
reference overlay, writes a transcript into a temp transcript root and prints a CLI-shaped result.
The hm arm renders a real harness from this checkout (about two seconds).

## Later measurement (not this PR)

```
INTEGRATION=1 uv run python scripts/bench_light_lane.py run --runs 3
```

Then paste the printed `uv run hm intent metric record hm_cost_ratio_small --value … --evidence …`.

## ✅ Success Criteria

- [ ] AC-001 … AC-011 of SPEC-hm-light-lane-bench pass.
- [ ] No file touched under `src/harness_maker/templates/`, `synthesize.py`, `step_sensitivity.py`,
  goldens or `CLAUDE.md`.
