---
type: spec
task_slug: retired-wiring
status: approved
created: 2026-11-10
tags: [harness-maker, spec, overhaul-phase-2, hooks, templates]
test_framework: pytest
interview_rounds: 0
summary: "Overhaul phase 2, slice 1: stop shipping the retired loop's Stop hook, stop writing Codex profiles into the user's home config, delete six partials nothing includes, and drop the dead progress-file pointer."
---

# SPEC — retired-wiring (overhaul phase 2, slice 1)

## Intent

Overhaul phase 1 (0.64.0) retired `/hm:loop` and autopilot. RESEARCH-hm-non-token-improvements F7
found that their wiring is still shipped:

- Every render adds a `Stop` hook, `hooks.loop_gate --mode stop-hook`. It guards a loop and an
  autopilot that no rendered command can start, and it costs about 0.28 s at every turn end.
- `make` with the codex target writes `[profiles.cheap]` and `[profiles.deep]` into
  `~/.codex/config.toml`. These are per-loop profiles, written outside the project, and the
  README does not mention them.
- Six template partials are included by nothing.
- Execute's session-context step points at `.claude-progress.json`, which nothing writes (HR-015).

The DRI asked on 2026-11-10 for phase 2 to proceed on the recommended option. This slice removes
the wiring that a user can feel (a hook per turn, a write to their home directory) and the dead
text. Deleting unreachable modules and the `harness.yaml` key diet come in later slices.

## Outcomes

- O1. A fresh render ships no `loop_gate` hook. A re-render over an existing settings file
  removes the harness-shipped `loop_gate` Stop command and keeps every user hook.
- O2. `make` never writes to `~/.codex/config.toml`. Profiles a user already has are left alone.
- O3. The six unreferenced partials are gone. Execute no longer names `.claude-progress.json`.

## In-Scope Scenarios

- **S1 (normal).** Given a fresh `make` (Side or Production, claude-code and codex), When it
  renders, Then neither `.claude/settings.json` nor `.codex/hooks.json` contains `loop_gate`, and
  the Claude `Stop` event still runs `worktree span-end`.
- **S2 (edge, upgrade).** Given a settings file rendered by 0.65 (Stop group: `loop_gate` plus
  `span-end`) and a user's own Stop hook, When `make` re-renders, Then the `loop_gate` command is
  gone, `span-end` is present once, and the user's hook is kept.
- **S3 (normal).** Given `make --targets claude-code,codex` with `HOME` pointing at an empty
  directory, When it runs, Then `$HOME/.codex/config.toml` does not exist afterwards.
- **S4 (failure guard).** Given the partials directory, When the render runs, Then no template
  includes a deleted partial (a missing include would fail the render).

## Non-Goals

- No deletion of Python modules: `hooks/loop_gate.py`, `loop_marker.py`, the autopilot modules and
  `codex_user_config.py` stay as importable modules. A kept user copy of the old hook still runs,
  and later slices delete code with their own evidence.
- No `harness.yaml` key removal and no CLI command removal (`autopilot`, `verify`).
- `templates/hooks/hooks.json.j2` is unchanged. It renders the stale 0.51 file only so that
  `cli._retire_stale_hooks_json` can recognise a pristine copy.
- Existing `[profiles.*]` entries in a user's `~/.codex/config.toml` are not removed.

## Constraints

| Constraint | Value | Source |
|---|---|---|
| Test framework | pytest (mandatory) | CLAUDE.md |
| Hook retirement | through `_HARNESS_RETIRED_HOOK_INVOCATIONS` only (append-only) | render.py, PLAN-hook-inventory-efficiency-audit ADR-001 |
| User hooks | a user's own hook in any event survives a re-render | pre-change checklist (1) |
| Surface | the rendered command surface may only shrink | tests/structural/test_command_size_budget.py |

## Irreversible Decisions

None. Every removal is in rendered output or in this repository's templates. A user's kept copy of
the old Stop hook goes through the existing retirement path.

## Acceptance Criteria

### AC-001: no render ships the loop_gate hook, and a re-render retires it
A fresh render (Side and Production, claude-code and codex) contains no `loop_gate` in
`.claude/settings.json` or `.codex/hooks.json`. `"<HM>:harness_maker.hooks.loop_gate --mode stop-hook"`
is in `render._HARNESS_RETIRED_HOOK_INVOCATIONS`. Re-rendering over a 0.65 settings file that
holds the old Stop group and a user Stop hook leaves `worktree span-end` exactly once, no
`loop_gate`, and the user hook.

### AC-002: make writes nothing to the user's Codex config
`make --targets claude-code,codex` with an empty `HOME` leaves `$HOME/.codex/config.toml` absent.
The rendered `.codex/config.toml` no longer mentions `profiles`.

### AC-003: the six unreferenced partials are deleted
`agents/_partials/step_manifest.md.j2`, `stage_end_summary.md.j2`, `gate0_receipt.md.j2`,
`comprehension_block.md.j2`, `worktree_preflight.md.j2` and `codex_autopilot_advance.md.j2` do not
exist under `templates/`, and no template names them.

### AC-004: execute no longer points at `.claude-progress.json`
No rendered stage contains `.claude-progress.json`.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1, S2 | unit | `tests/unit/test_retired_wiring.py` (AC-001) |
| S3 | integration | `tests/unit/test_retired_wiring.py` (AC-002, CLI with a temp `HOME`) |
| S4 | unit | `tests/unit/test_retired_wiring.py` (AC-003, AC-004) |

## Open Questions

None.

## Refinement Decisions

- The interview was skipped. The DRI told this thread not to ask and to follow the recommended
  option. There is no irreversible decision, so the SPEC is stamped `--exempt`.
- The Python modules stay in this slice. Deleting them needs per-module reachability evidence
  (RESEARCH F7 says its "unreachable" list is static), which is the next slice's job.
- Profiles already present in a user's home config are kept, because removing them would be a
  second write outside the project.
- Tests that pin the removed partials or the Stop hook move with this SPEC; the REVIEW lists each.
