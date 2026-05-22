---
generated_by: harness-maker
harness_maker_version: 0.22.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/autoloop-driver/SKILL.md.j2
provenance: official
name: autoloop-driver
description: Orchestration guide for /hm:loop. Covers two modes (feature and improve),
  coverage-driven adaptive interview rationale, LoopContext schema (work-docs/loop-context/),
  loop intensity + exit criteria checklist (4-gate convergence), improve-mode loop
  body invariants, and safety rails. The /hm:loop command file owns the per-step procedure;
  this skill explains WHY and the invariants Claude must hold.
content_hash: 135e175ca2833377f3a6741f76aff2cdae22d82e0c953268eb5821666cc5dccf
---

# autoloop-driver

`/hm:loop` is **prompt-driven and LLM-maximised**. Claude plays the role of
the autoloop driver. No Python module is imported at runtime.

## Two Modes

- **`feature`** (default): one discrete feature per iteration. Executor = configured fused workflow; convergence = named predicate.
- **`improve`**: continuous quality loop (review → fix → test → re-review) until LLM judges stopping criteria met. No feature list.

Mode detection order: explicit `--mode` flag → spec `mode` field → keyword
scan of goal (`improve`, `refactor`, `quality`, `clean`, `cleanup`,
`optimize`, `코드 품질`, `리팩토링`, `개선`, `code review`) → default `feature`.

## Coverage-Driven Adaptive Interview

**Invariant**: zero ambiguity before iter 1. The interview is a coverage
problem over 5 dimensions, solved by LLM judgment — not a fixed script.
Claude extracts answers from source material first; only missing/ambiguous
dimensions trigger the structured question tool (`AskQuestion` in Cursor,
`AskUserQuestion` in Claude Code, `request_user_input` in Codex).
Actionability is LLM-judged, not regex. No question cap. Step 4-G fires
**before** 4-B so the quality bar is set first; 4-B post-hook proposes
measurable `stopping_criteria` items as additional `ExitCriterion`.

| Dimension | Actionable = |
|-----------|-------------|
| **purpose** | Caller identity + data flow clear |
| **invariants** | Specific interfaces/protocols named |
| **priority** | Explicit 1-2-3 ranking with tiebreaker |
| **test_reliability** | Coverage % or scenario count + known gaps |
| **stopping_criteria** | Measurable bar (issue counts, test results) |

## Context Persistence

`work-docs/loop-context/<slug>.yaml` survives across runs (merge: keep
unchanged answers, update new, append notes). `.claude/loop-specs/<slug>.yaml`
is generated per run and references context via `context_ref`.

## Loop Intensity + Exit Criteria

`loop_intensity` (set in step 4-G) defines the strictness tier:

| Tier | Included criteria |
|------|-------------------|
| `quick` | tests pass, lint clean |
| `standard` | + mypy clean (warning-only `required:false`), review grade ≥ B |
| `thorough` | + mypy clean (required), review grade = A, all AC verified |
| `maximum` | + security scan, no regressions |

`exit_criteria_checklist: list[ExitCriterion]` — each item has `label`,
`cmd` (shell or `""`), `required` flag. Checked by the 4-gate system.

## 4-Gate Convergence

Four independent gates replace single-LLM stopping judgment. All pass for 2
consecutive iters (`convergence_streak >= 2`) → converged.

- **Gate 1 — Mechanical**: run `ExitCriterion.cmd`; `required:false` failures = warning.
- **Gate 2 — LLM individual**: evaluate each criterion's `label` against `<WT>`. Deadlock detector at 3 "Ambiguous" → question tool.
- **Gate 3 — Regression**: baseline = exit-code + failing test names. No prior baseline → pass; skip on iter 1.
- **Gate 4 — Streak**: single reset site. All 3 pass → increment; any fail → 0.

## Improve Mode — Invariants

Each iter: read target → review (classify critical/high/medium/low) →
4-gate check → fix if not converged → tests → re-review. Convergence check
runs **before** fixing (converge early when criteria already met).

- Never change anything that violates context invariants
- Convergence requires 4-gate ALL-pass × 2 iters, not a single LLM verdict
- Detect test command from project structure (Makefile, pyproject.toml…)

## Safety Rails (always on)

1. `iter >= max_iter` → halt
2. `elapsed >= time_h × 3600` → halt
3. `failed_streak >= N` → halt (default N=5, `--failed-streak-cap`)
4. *(feature mode only)* same feature retried ≥ 3 times → halt + blocker report
5. Ping every 5 iterations
6. Convergence check **before** each iteration body

## Non-stopping Discipline

Iteration boundaries are checkpoints, not stop signs. Unless a safety rail
fires or the 4-gate streak ≥ 2, the loop continues without prompting the
user. See `commands/hm/loop.md` for the canonical procedure.

<!-- @hm:user:extensions -->
<!-- Project-specific autoloop rules. Preserved across upgrades. -->
<!-- @hm:/user:extensions -->
