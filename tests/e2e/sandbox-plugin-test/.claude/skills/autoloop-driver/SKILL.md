---
generated_by: harness-maker
harness_maker_version: 0.4.8
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/autoloop-driver/SKILL.md.j2
provenance: official
name: autoloop-driver
description: Orchestration guide for /hm:loop. Covers two modes (feature and improve),
  coverage-driven adaptive interview rationale, LoopContext schema (work-docs/loop-context/),
  improve-mode loop body invariants, and safety rails. The /hm:loop command file owns
  the per-step procedure; this skill explains WHY and the invariants Claude must hold.
content_hash: ea4baec8c2fc849c60e628fd6460c5a068b778ef57bb46fab366c5df7adc0f6e
---

# autoloop-driver

`/hm:loop` is **prompt-driven and LLM-maximised**. Claude plays the role of
the autoloop driver. No Python module is imported at runtime.

## Two Modes

**`feature` mode (default)**: implement discrete features one per iteration.
Executor = configured fused workflow. Convergence = named predicate.

**`improve` mode**: continuous quality improvement — review → fix → test →
review — until LLM judges stopping criteria met. No feature list.

Mode detection order: explicit `--mode` flag → spec `mode` field → keyword
scan of goal (`improve`, `refactor`, `quality`, `clean`, `cleanup`,
`optimize`, `코드 품질`, `리팩토링`, `개선`, `code review`) → default `feature`.

## Coverage-Driven Adaptive Interview

**Invariant**: zero ambiguity before the first iteration. The interview is
not a fixed script — it is a coverage problem solved by LLM judgment.

Five required dimensions (every loop, every mode):

| Dimension | Actionable = |
|-----------|-------------|
| **purpose** | Caller identity + data flow clear |
| **invariants** | Specific interfaces/protocols named |
| **priority** | Explicit 1-2-3 ranking with tiebreaker |
| **test_reliability** | Coverage % or scenario count + known gaps |
| **stopping_criteria** | Measurable bar (issue counts, test results) |

**Extraction first**: Claude reads all source material and extracts answers
with LLM comprehension before asking anything. Only missing or ambiguous
dimensions trigger `AskUserQuestion`.

**Ambiguity judgment**: after each answer, Claude evaluates actionability
via LLM — not regex. A future Claude reading only the context file must
be able to make correct decisions without asking again. If not, generate
a targeted follow-up. No question cap.

## Context Persistence

`work-docs/loop-context/<slug>.yaml` — survives across multiple loop runs.
Merge on re-run: keep unchanged answers, update new ones, append notes.

`.claude/loop-specs/<slug>.yaml` — generated per run, references context
via `context_ref`.

## Improve Mode — Invariants

Each iteration: read target → review (classify critical/high/medium/low)
→ evaluate stopping_criteria (LLM) → fix if not converged → run tests
→ re-review. The stopping_criteria judgment decides convergence, not a
rule-based predicate.

Hard invariants:
- Never make changes that would cause context invariants to be violated
- Evaluate stopping_criteria **before** fixing (converge early when met)
- Detect test command from project structure (Makefile, pyproject.toml…)

## Safety Rails (always on, never skip)

1. `iter >= max_iter` → halt
2. `elapsed >= time_h × 3600` → halt
3. `failed_streak >= 3` → halt
4. *(feature mode only)* Same feature retried ≥ 3 times → halt and report
   blocker. Not applicable in improve mode (no feature list).
5. Ping every 5 iterations
6. Convergence check **before** each iteration body

## LLM-Maximised Design Principle

Every judgment benefiting from language understanding is delegated to Claude:
ambiguity detection, follow-up question generation, answer extraction from
source documents, stopping criteria evaluation, issue classification.
Python types enforce schema and enable unit tests — they contain no
business logic.

## Dev-time Python API (NOT for runtime use)

`harness_maker.autoloop_driver`: `LoopMode`, `ImprovementContext`,
`LoopContext`, `Feature`, `LoopSpec`, `AutoloopState`, `detect_mode`,
`parse_goal`, `parse_loop_spec`, `parse_loop_context`, `is_loop_consumable`,
`run`. Exists for harness-maker unit tests only. `/hm:loop` must not import.

## Reference

- Command: `commands/hm/loop.md` (full per-step procedure)
- Agent: `autoloop-coder` (per-iteration implementation worker)
- Context: `work-docs/loop-context/<slug>.yaml`
- Spec: `.claude/loop-specs/<slug>.yaml`

<!-- @hm:user:extensions -->
<!-- Project-specific autoloop rules. Preserved across upgrades. -->
<!-- @hm:/user:extensions -->
