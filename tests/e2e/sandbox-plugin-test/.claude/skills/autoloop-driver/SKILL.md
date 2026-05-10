---
generated_by: harness-maker
harness_maker_version: 0.8.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/autoloop-driver/SKILL.md.j2
provenance: official
name: autoloop-driver
description: Orchestration guide for /hm:loop. Covers two modes (feature and improve),
  coverage-driven adaptive interview rationale, LoopContext schema (work-docs/loop-context/),
  loop intensity + exit criteria checklist (4-gate convergence), improve-mode loop
  body invariants, and safety rails. The /hm:loop command file owns the per-step procedure;
  this skill explains WHY and the invariants Claude must hold.
content_hash: 7d764912ddee54367d06139aeb1072a86775b9db06505a8940a3941bdf54f179
---

# autoloop-driver

`/hm:loop` is **prompt-driven and LLM-maximised**. Claude plays the role of
the autoloop driver. No Python module is imported at runtime.


## When to invoke vs skip

**Invoke when:**
- `/hm:loop "<goal>"` starts and the orchestrator needs the WHY behind feature/improve mode + per-loop worktree invariants.
- A loop iteration boundary needs to confirm the LoopContext schema rules.

**Skip when:**
- A single non-loop stage runs (`/hm:execute`, `/hm:review`, etc.) — autoloop-driver is loop-scope.
- The loop is interrupted mid-iteration (resume logic lives in the command file, not this skill).
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

**Interview order** — step 4-G fires **before** 4-B (missing dimensions):
4-G locks in `loop_intensity` and `exit_criteria_checklist` first, so the
quality bar is known before the rest of the context is collected.
After 4-B finalises `stopping_criteria`, the 4-B post-hook re-scans for
measurable conditions and proposes them as additional `ExitCriterion` items.

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

## Loop Intensity + Exit Criteria

`loop_intensity` (set in step 4-G) defines the strictness tier:

| Tier | Included criteria |
|------|-------------------|
| `quick` | tests pass, lint clean |
| `standard` | + mypy clean (warning-only `required:false`), review grade ≥ B |
| `thorough` | + mypy clean (required), review grade = A, all AC verified |
| `maximum` | + security scan, no regressions |

`exit_criteria_checklist: list[ExitCriterion]` — each item has `label`,
`cmd` (shell command or `""`), and `required` flag. All items in the list
are checked at convergence time via the 4-gate system.

## 4-Gate Convergence

Replace single-LLM stopping judgment with four independent gates. All must
pass for 2 consecutive iters (`convergence_streak >= 2`):

- **Gate 1 — Mechanical**: run `ExitCriterion.cmd` items; exit 0 = pass.
  Skip items where `cmd=""`. `required: false` failures = warning only.
- **Gate 2 — LLM individual**: evaluate each criterion's `label` independently
  against current `<WT>` state. Deadlock detector: `criterion_ambiguity_counts[label]`
  increments on "Ambiguous"; at 3 → `AskUserQuestion` (continue/accept/remove).
  Persist counts to `runtime.criterion_ambiguity_counts` after each iter.
- **Gate 3 — Regression**: baseline = exit-code + set of failing test names,
  stored as `runtime.last_test_result`. No prior baseline → Gate 3 passes
  unconditionally (post-compaction safe). Skip on iter 1.
- **Gate 4 — Streak**: `convergence_streak` is the **single reset site**.
  Gates 1+2+3 pass → `convergence_streak += 1` (persisted to
  `runtime.convergence_streak`); any gate fails → `convergence_streak = 0`.
  Converged when streak ≥ 2.

## Improve Mode — Invariants

Each iteration: read target → review (classify critical/high/medium/low)
→ run 4-gate convergence check → fix if not converged → run tests
→ re-review. The convergence check runs **before** fixing (converge early
when criteria are already met).

Hard invariants:
- Never make changes that would cause context invariants to be violated
- Convergence requires 4-gate ALL-pass for 2 consecutive iters, not a
  single LLM judgment that "stopping criteria are met"
- Detect test command from project structure (Makefile, pyproject.toml…)

## Safety Rails (always on, never skip)

1. `iter >= max_iter` → halt
2. `elapsed >= time_h × 3600` → halt
3. `failed_streak >= N` → halt (default N=5, configurable via `--failed-streak-cap`)
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

`harness_maker.autoloop_driver`: `LoopMode`, `LoopIntensity`, `ExitCriterion`,
`ImprovementContext`, `LoopContext`, `Feature`, `LoopSpec`, `AutoloopState`,
`detect_mode`, `parse_goal`, `parse_loop_spec`, `parse_loop_context`,
`is_loop_consumable`, `run`. Exists for harness-maker unit tests only.
`/hm:loop` must not import.

## Reference

- Command: `commands/hm/loop.md` (full per-step procedure)
- Agent: `autoloop-coder` (per-iteration implementation worker)
- Context: `work-docs/loop-context/<slug>.yaml`
- Spec: `.claude/loop-specs/<slug>.yaml`

<!-- @hm:user:extensions -->
<!-- Project-specific autoloop rules. Preserved across upgrades. -->
<!-- @hm:/user:extensions -->
