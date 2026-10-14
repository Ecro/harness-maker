---
type: plan
task_slug: hm-light-lane-bench
status: planning
created: 2026-10-14
tags: [harness-maker, plan, python, bench, cost]
spec: "[[SPEC-hm-light-lane-bench]]"
research_doc: "[[RESEARCH-hm-light-lane]]"
interview_rounds: 0
adrs: 7
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
**Decided by:** agent. Hidden tests are copied to `<run>/hidden/` after the agent exits and run
with `PYTHONPATH=<work>`, their own `-c pytest.ini` and `--rootdir`. A `conftest.py` or pytest
config the agent left behind can then not skip or rewrite the hidden tests. Pass means every
hidden test passed; a collection error is a failure.

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
INTEGRATION=1 uv run python scripts/bench_light_lane.py run --runs 3 --jobs 3
```

Then paste the printed `uv run hm intent metric record hm_cost_ratio_small --value … --evidence …`.

## ✅ Success Criteria

- [ ] AC-001 … AC-011 of SPEC-hm-light-lane-bench pass.
- [ ] No file touched under `src/harness_maker/templates/`, `synthesize.py`, `step_sensitivity.py`,
  goldens or `CLAUDE.md`.
