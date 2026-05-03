---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/autoloop-driver/SKILL.md.j2
provenance: official
name: autoloop-driver
description: Invokes the autoloop driver for unattended multi-iteration execution.
  Use when /hm:loop is called or when the orchestrator needs to delegate a goal to
  bounded-iteration autonomy with safety rails (time cap, iter cap, 3-failure halt,
  ping every 5 iters).
content_hash: 4605f90a75813ddb786478f49ff7c8b8bba2fab94d4274b2d102dad70af86e22
---

# autoloop-driver

The driver-invocation guide for `harness_maker.autoloop_driver.run(...)`.
Skill is loaded by the `/hm:loop` command and any orchestrator that wants
to hand off a goal to bounded-iteration autonomy.

## When to Invoke

- `/hm:loop "<goal>" [--time 8h] [--max-iter 30] [--workflow <name>] [--convergence "<expr>"] [--dry-run]`
- An autoloop-coder agent decides the current goal needs further iteration
- An orchestrator wants to retry a stalled phase under iteration discipline

## Driver Contract

```python
from harness_maker.autoloop_driver import run, AutoloopState

state: AutoloopState = run(
    goal="implement login. add logout. wire reset.",
    time_h=8.0,
    max_iter=30,
    workflow="dev",
    convergence=None,           # default: all features completed
    dry_run=False,
    executor=my_executor,       # callable (feature, iter_idx) -> bool
)
```

The `executor` callable is the per-iteration worker. In production it
delegates to the rendered fused workflow (`/hm:dev` etc.). In tests, mock
it. In `dry_run=True` mode, the driver skips the executor entirely.

## Safety Rails (always on)

1. **3 consecutive failures** → halt with `stop_reason="3 consecutive failures"`
2. **`max_iter` cap** → halt with `stop_reason="max_iter (N) reached"`
3. **`time_h` cap** → halt with `stop_reason="time_cap (Nh) reached"`
4. **Ping every 5 iterations** → INFO log line for observability
5. **Convergence check** before each iteration — early exit when satisfied

## Output

The returned `AutoloopState` contains:

- `iter` — number of iterations attempted
- `completed` — features successfully implemented
- `failed_streak` — consecutive failure counter (0 after a success)
- `converged` — True only when convergence check passes
- `stop_reason` — human-readable termination cause

The `/hm:loop` command renders a brief summary; `verify-before-completion`
gate runs immediately before the iteration is considered closed.

## Reference

- Module: `harness_maker.autoloop_driver`
- Agent: `autoloop-coder` (the implementation worker invoked per iteration)
- Gate: `verify-before-completion` (mandatory pre-close check)
