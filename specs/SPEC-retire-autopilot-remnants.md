---
type: spec
task_slug: retire-autopilot-remnants
status: approved
created: 2026-10-17
tags: [harness-maker, spec, readiness, autonomy, cleanup, overhaul]
test_framework: pytest
interview_rounds: 3
lane: full
parent_spec: "[[SPEC-hm-overhaul-p1]]"
summary: "/hm:health still fails autopilot_autoarm_registered on a key 0.64.0 made inert, the autonomy.pipeline default and preset fallback still name the folded review/verify stages, and this repo's hand-written CLAUDE.md lacks the output_language marker; retire the signal, make the pipeline the four rendered stages with a one-advisory load migration, and add the marker"
---

# SPEC — retire-autopilot-remnants

## Intent

A `/hm:make` on this repo (0.65.0) reported two health findings that a re-render cannot clear.

1. `autopilot_autoarm_registered` (readiness.py) reads `autonomy.autopilot_persistent` and fails
   when the `autopilot_autoarm` SessionStart hook is missing. SPEC-hm-overhaul-p1 made that key
   inert (Constraints, *Config*) and retired the hook (IRR-005), and the same `make` run warns that
   the key is inert. The signal is a permanent false alarm whose remedy ("re-render") does nothing.
2. `output_language_present` fails because this repo's CLAUDE.md is hand-written and never gets the
   rendered `output_language` partial.

While checking (1), the same `autonomy` block turned out to still list `review` and `verify` in
`pipeline`. They stopped being stages in 0.64.0 (review runs inside `/hm:execute`, verification is
`hm check` inside `/hm:wrapup`), but `AutonomyConfig`'s default and both preset fallbacks still
write them, so every new harness.yaml names two stages that do not exist.

Why now: the false findings recur on every `/hm:health` and train the operator to ignore it.

## Outcomes

- `/hm:health` on any harness emits no `autopilot_autoarm_registered` signal.
- A new harness.yaml writes `pipeline: [research, spec, execute, wrapup]`.
- An existing harness.yaml naming `review` / `verify` loads without them, logs one advisory, and
  the next re-render persists the shorter list; the load after that is silent. A pipeline that
  names only retired stages falls back to the four-stage default.
- `output_language_present` passes on this repo.

## In-Scope Scenarios

- **S1 (normal).** Given a harness with `autonomy.autopilot_persistent: true` and no autoarm hook,
  when readiness runs, then no signal named `autopilot_autoarm_registered` appears.
- **S2 (normal).** Given a fresh interview, when synthesize and render run, then the rendered
  `autonomy.pipeline` is `research, spec, execute, wrapup`, the same list the render produces
  stages for.
- **S3 (edge / migration).** Given a 0.62 harness.yaml whose pipeline names `plan`, `review` and/or
  `verify` anywhere among any order-preserving subsequence of the four stages, when it loads, then
  those names are dropped, the rest keep their order, every other `autonomy` field is unchanged and
  exactly one advisory is logged; loading the migrated result logs nothing. If nothing survives, the
  pipeline is the four-stage default.
- **S3b (migration persists).** Given that legacy harness.yaml, when the harness-yaml template
  renders from the loaded answers, then the written file names no retired stage and loading it
  logs no advisory.
- **S4 (failure guard).** Given this repo, when the hand-written CLAUDE.md loses the
  `<!-- @hm:output_language -->` marker, then a structural test fails.

## Non-Goals

- Removing `REVIEW` / `VERIFY` from `AtomicStage` or deleting the autopilot modules
  (SPEC-hm-overhaul-p1 leaves unreachable CLI to Phase 2).
- Warning about or rejecting folded names in the retired `hm autopilot on --pipeline` argument.
  Because `drop_retired_stages` is shared, that CLI now drops `review` / `verify` silently, and
  `--pipeline review,verify` arms zero stages. Auto-advance already ended (SPEC-hm-overhaul-p1
  IRR-005) and Phase 2 deletes the CLI, so this is accepted.
- Removing `autonomy.autopilot_persistent` from the schema or from this repo's harness.yaml; the
  `make`-time inert warning keeps covering it.
- Changing how readiness treats a hand-written CLAUDE.md in other projects.

## Constraints

| Constraint | Source |
|---|---|
| pytest; ruff check + format; mypy --strict | CLAUDE.md Tech decisions |
| A retired pipeline name is filtered only through `models.drop_retired_stages` | tests/structural/test_retired_stage_single_reader.py |
| No name may be both in `RETIRED_STAGES` and a live `AtomicStage` member, so the folded names live in a separate set | same test |
| Migration logs one advisory on the migrating load and none after | interview._parse_autonomy precedent (plan) |
| Retired autopilot library tests keep the 0.62 six-stage pipeline written out, not the default: tests/unit/test_autopilot_boundary.py, tests/unit/test_autopilot_narrow.py, tests/e2e/test_autopilot_chain_e2e.py, tests/unit/test_autopilot_unlimited_caps.py, tests/unit/test_autonomy_ask_resolution.py, tests/unit/test_autonomy_level_matrix.py | they test that library's mechanics |

## Irreversible Decisions

| ID | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | A re-render rewrites a user's `autonomy.pipeline` without `review` / `verify` (one advisory on the migrating load) | data migration | Once a user's harness.yaml is re-rendered the names are gone; restoring the filter does not bring them back. Impact is nil today because only the retired autopilot reads `pipeline`. Approved by the DRI in round 1. |

## Acceptance Criteria

### AC-001: readiness emits no autopilot_autoarm_registered signal

For a project with a settings.json lacking the `autopilot_autoarm` hook, no readiness signal has
id `autopilot_autoarm_registered`, and the set of failing signal ids is the same whether
`autonomy.autopilot_persistent` is `true` or `false` (so a renamed copy of the check also fails).

### AC-002: the default pipeline is the four rendered stages

`[s.value for s in AutonomyConfig().pipeline] == synthesize._ATOMIC_STAGES`, and the Side and
Production harness-yaml fallbacks are both discovered (the discovered keys equal `PRESET_FILES`,
so an unmatched template cannot pass vacuously) and both encode the same list.

### AC-003: a legacy pipeline drops plan/review/verify once

Property over legacy pipelines: take any order-preserving subsequence of the four stages (empty
included), insert any non-empty multiset-free subset of `plan` / `review` / `verify` at any
positions, and load through `interview._parse_autonomy` with arbitrary valid level and caps. The
result's pipeline equals the input with the retired names removed (computed in the test without
`drop_retired_stages`), or the four-stage default when that is empty; every other `autonomy` field
equals the input's; one advisory is logged; a second load of the result logs none.

### AC-005: the migration persists through a render

Rendering the harness-yaml template (Side and Production) from answers loaded off a legacy
harness.yaml writes a `pipeline` with no `plan` / `review` / `verify`, and loading the written file
logs no retirement advisory.

### AC-004: this repo's CLAUDE.md (and AGENTS.md when present) carries the locale marker

Running readiness on the repo root yields `output_language_present` passed, and the committed
CLAUDE.md contains the marker. AGENTS.md is gitignored, so it is checked only where it exists.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit | AC-001 test in tests/unit/test_readiness_hooks_from_settings.py |
| S2 | unit | AC-002 test in tests/unit/test_autonomy_config.py |
| S3 | unit (property, hypothesis) | AC-003 test in tests/unit/test_atomic_stage_plan_retirement.py |
| S3b | unit (render round-trip) | AC-005 test in tests/unit/test_atomic_stage_plan_retirement.py |
| S4 | structural | AC-004 test in tests/structural/test_repo_output_language.py |

## Open Questions

## Refinement Decisions

- Intent: none. No active or proposed intent's metric moves with this change.
- The implementation was drafted before this SPEC, in the base checkout and through shell writes
  that bypassed the PreToolUse spec gate. That was not deliberate. It was moved unchanged into
  this task worktree, and `/hm:execute` binds its tests to these ACs.
- Fix the readiness check, not this repo's harness.yaml: deleting the key here would leave every
  other harness carrying it with the same false alarm.
- Round 3 (after spec-validator, all resolved, none left open):
  - The AC-003 oracle was too weak (critical): every input mapped to the default, so a migration that
    overwrote a custom pipeline or reset caps would pass. Fixed by drawing subsequences, comparing
    every autonomy field, and computing the expected list independently.
  - The all-retired case falls back to the four-stage default (DRI, round 3).
  - Silent drop in the retired autopilot CLI is accepted as a Non-Goal (DRI, round 3).
  - Outcome 3 had no AC, so AC-005 adds a render-then-reload test.
  - AC-002 could pass vacuously, so it now requires both presets to be discovered.
  - AC-001 now compares the failing-signal sets; AC-004 now asserts the readiness signal itself.
  - Rejected: "documentation_contract switched canonical source". `SourceContract.pipeline` was
    already `_ATOMIC_STAGES` at HEAD; only its comment changed.
- Execute found that tests/unit/test_overhaul_p1_surface.py's "no auto-advance" row matched
  `autopilot` inside the rendered `uv run --with <install path>` prefix, and this task's worktree
  path contains the slug. The row now strips the install ref (the file's own `_INSTALL_REF`)
  before it searches, so a checkout path cannot trip it. tests/render/test_retired_text.py's
  AC-001 had the same defect and now removes the checkout path (`HEAD_SRC.parent`) first.
- CLAUDE.md gets the rendered directive text verbatim (copied from AGENTS.md), so the two root
  files say the same thing.
