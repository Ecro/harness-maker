---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/loop.md.j2
provenance: official
content_hash: a0f9931faa984dc7a1fabc1906810f33dc036c7a7560c15639103a613e94fd00
---
# /hm:loop

> Run the autoloop driver for unattended, multi-iteration execution.

## Usage

```
/hm:loop <goal> [--time 8h] [--max-iter 30] [--workflow dev] [--convergence "<criterion>"] [--dry-run]
```

## Arguments

`$ARGUMENTS` is parsed positionally + by flag:

- `<goal>` — required. Free-form target description; the driver splits it
  into a feature list on `.`, `,`, `;`, newline, or `·`.
- `--time <Nh>` — max wall-clock duration (default 8h). When elapsed exceeds
  this, the loop halts with `converged=False` and `stop_reason=time_cap`.
- `--max-iter <N>` — max iterations (default 30). Halts with
  `stop_reason=max_iter` when reached.
- `--workflow <name>` — which fused workflow command the iteration body
  invokes (default `dev`). Opaque to the driver — passed through for logging.
- `--convergence "<expr>"` — optional Python expression evaluated against
  `{completed, features, iter}` (with safe builtins: `len`, `all`, `any`).
  Default: all features completed.
- `--dry-run` — simulate without invoking the executor; single iteration
  marks all features completed, no disk writes.

## Behavior

The command invokes `harness_maker.autoloop_driver.run(...)` with the parsed
arguments. The driver:

1. Parses `<goal>` into a feature list via `parse_goal`.
2. Iterates: pick next un-completed feature → invoke executor (the configured
   workflow) → on success, mark completed; on failure, increment failed_streak.
3. Safety rails: 3 consecutive failures stop the loop; every 5 iterations
   logs a ping; `time_h` and `max_iter` caps are checked before each iteration.
4. Convergence: by default, all parsed features must be in `completed`.
   Custom expression overrides this default.

Returns an `AutoloopState` with `iter`, `completed`, `failed_streak`,
`converged`, and `stop_reason`.

## Reference

- Skill: `autoloop-driver` (driver invocation guide)
- Agent: `autoloop-coder` (per-iteration implementation worker)
- Module: `harness_maker.autoloop_driver`
