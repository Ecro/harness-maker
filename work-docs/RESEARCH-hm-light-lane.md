---
type: research
task_slug: hm-light-lane
status: complete
created: 2026-10-14
tags: [harness-maker, research, bench, cost, execute, review, spec]
libs_fetched: []
sources: []
related_docs:
  - "[[SPEC-hm-light-lane]]"
summary: "Small single-session tasks: /hm: path costs x22 vs plain with no accuracy gain; both failures were A.5 self-blocks"
---

# RESEARCH — /hm: full pipeline vs plain run on small tasks (HR-004, 2026-10-14)

Condensed record of three headless A/B runs. Raw run directories lived in a session scratchpad
and are gone; these tables are the durable record. Model: claude-sonnet-5-5 (headless default,
not the operator's main model). Harness: harness-maker 0.62.0, Side preset, Claude Code only,
`autonomy.level: auto_full`, task prefixed with `/hm:spec ` so autopilot ran
execute → review → verify.

## Run 2 — `timeparse` fixture, 5 tasks, 3 runs per task per arm (30 runs)

Grading: 88 hidden tests the agent never sees (all pass against a reference implementation).

| Task | plain pass | hm pass | plain mean cost | hm mean cost | plain mean time | hm mean time |
|---|---|---|---|---|---|---|
| t1 `format_duration(max_units)` | 3/3 | 3/3 | $0.12 | $2.15 | 49s | 529s |
| t2 atomic `store.py` | 3/3 | **1/3** | $0.10 | $1.53 | 28s | 367s |
| t3 ISO-8601 duration parse | 3/3 | 3/3 | $0.09 | $2.29 | 23s | 488s |
| t4 CLI `--sum` + stdin `-` | 3/3 | 3/3 | $0.10 | $2.57 | 27s | 529s |
| t5 token-bucket RateLimiter | 3/3 | 3/3 | $0.11 | $2.50 | 40s | 576s |
| **Total** | **15/15** | **13/15** | $0.10 | $2.21 | 33s | 498s |

- Cost ratio hm / plain = **×22**, wall time ×15. The hm arm averaged 10 subagent dispatches per run
  (spec-validator, test-reviewer, review lenses, stuck).
- **Both hm failures were execute Phase A.5 self-blocks** at the 2-round cap: the SPEC and PLAN
  were written, tests authored, test-reviewer FAILed twice, Phase C never opened, `store.py` was
  never written. One was an internal contradiction the agent itself wrote (SPEC Outcomes vs Open
  Questions) surfaced as a "decision needed"; the other was a valid but non-decisive objection to
  a fault-injection seam. The plain arm passed the same task 3/3 on hidden tests.
- This is the first ground-truth arm for Phase A.5: on the two runs A.5 blocked, the arm without
  A.5 passed every hidden test.

## Run 3 — `tasklog` fixture (7 modules, written conventions, 2 planted violations), plain only

| Variant | pass | mean cost | mean time |
|---|---|---|---|
| README points at `docs/CONVENTIONS.md` | 15/15 | $0.13 | 44s |
| README pointer removed | 14/15 | $0.12 | 38s |

The hm arm (~$70) was not run: plain left almost no headroom. Across runs 2 and 3 plain passes
**44/45** single-session tasks.

## What this measures and what it does not

- Measured: on this model, the full /hm: pipeline on medium single-module tasks adds no hidden-test
  accuracy, costs ×22, and self-blocks 2/15 at A.5.
- Not measured: multi-file or multi-session work (state that outlives a context window), a human
  in the loop (headless "decision needed" ends the run; interactively it is one question), quality
  hidden tests cannot see, the operator's main model.
- Why every task ran the full pipeline: spec Step 0's only skip needs single file + no contract
  change + <1h reversible. Every bench task fails that, so all of them took spec-validator,
  A.4/A.5, the two-pass review fan-out plus confirmation pass, and verify.
- Weakness: n=3 per cell, 5 + 5 tasks, one model, ~300-line fixtures.
