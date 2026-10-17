---
type: review
task_slug: retired-text
created: 2026-10-17
spec: "[[SPEC-retired-text]]"
---

# REVIEW — retired-text (round 1, code-reviewer; second opinion skipped: no codex CLI in this container)

## Findings

| id | severity | file:line | finding | disposition | resolution | authority |
|---|---|---|---|---|---|---|
| F1 | P2 | templates/agents/consensus-arbiter_body.md.j2 | The new trigger says the arbiter runs on severity disagreements (as `/hm:execute` says), but its stale reachability note said execute never invokes it, and its Step 4a/Out of Scope say it never changes severity | accepted | reachability note rewritten; the trigger vs no-bridge tension predates this change and is a phase-2 note (below) | — |
| F2 | P2 | tests/integration/test_overhaul_p1_eval3_replay.py `digest_text` | `\s+` collapse over the whole frontmatter hid de-indented keys and blank lines | accepted | collapse only `\n +` (YAML's fold), manifest regenerated from the 36 originals | — |
| F3 | P2 | tests/integration/test_overhaul_p1_ship_bar.py | the missing-source branch was not exercised | accepted | `alias_problem({..., source: 0*40}) is None` | — |
| F4 | P3 | test_overhaul_p1_ship_bar.py `on_this_harness` | bare assert for a broken alias | accepted | `BadAliasError` | — |
| F5 | P3 | tests/render/test_retired_text.py AC-003(a) | a duplicated new group would pass | accepted | group count must equal the shipped count | — |
| F6 | P3 | replay `_maker_like` | synthetic frontmatter still carried the dropped grant | accepted | fixed | — |
| F7 | P3 | PLAN phase 2 / SPEC Constraints | goldens and BASELINE-DELTA named but untouched | rejected | `tests/fixtures/strictness_reference/` is a pre-change differential reference (its own docstring), so re-capturing it would void its oracle; the surface shrank (no growth to attribute), and the baseline is re-frozen from main after merge as with PR-S | test_render_strictness_surface.py docstring |
| F8 | P3 | scripts/regen_eval3_harness_manifest.py | non-atomic writes | accepted | `io_utils.atomic_write` | — |
| F9 | P3 | CLAUDE.md, READMEs | dropped `restore_pipeline` invariant; "each stage is your call" overstated | accepted | invariant line restored without the narrow grant; READMEs reworded | — |

Phase-2 note (F1 residual, for the DRI): the arbiter's trigger says it runs on severity disagreements, while its Step 4a/4c and Out of Scope say it never changes severity across tiers; `/hm:execute` says the arbiter "resolves conflicting severities". One of the two surfaces needs to change.

`hm check` gates: the pytest gate runs with `-x` and stops at `test_land_hold.py::...[unreadable]`, one of the five known container-only failures (root ignores the chmod); the full `pytest -n auto` run shows only those five.

Deviations reviewed and kept: `test_reasoning_chain_parity.py::test_arbiter_states_that_review_does_not_invoke_it` asserted the stale note, renamed to `test_arbiter_states_when_review_invokes_it` and pointed at the new wording; provenance stores `digest_sha256` per run (7 KB instead of 289 KB); `_NARROW` stays defined because AC-004 limits the front-door test to two edits; alias matches the rows' 12-hex-digit SHA by prefix.

Dogfood notes for phase 2 (0.64.0 run on this task): `task-preflight` run from inside the task worktree fails ("already used by worktree"), because the stage text passes `"$(pwd)"` as the base; execute.md's `hm spec_machine validate --yaml` does not parse (the CLI takes a positional path); the spec_gate hook blocks writing a test file until its node id is already in a SPEC's `test_ids`.
