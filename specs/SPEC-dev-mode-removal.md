---
type: spec
task_slug: dev-mode-removal
status: approved
created: 2026-09-20
tags: [harness-maker, spec, python, jinja2, config-migration, axis-removal]
tier: 1
test_framework: pytest
research_doc: "[[RESEARCH-ai-native-sdlc-vs-intent-world]]"
interview_rounds: 3
summary: "Remove the dev_mode axis; strictness becomes one preset-derived knob, and warn renders the SPEC machinery without blocking on it"
---

# SPEC — dev_mode removal: one strictness knob, not a second axis

## 🎯 Intent

`dev_mode` was introduced as an axis orthogonal to `preset`, with all four crosses allowed,
because it decided **which stages existed**: `task-driven` omitted the spec-gate hook, dropped
`/hm:verify`'s Check 6, skipped SPEC-need detection and turned the quality gate from block to
warn. That premise no longer holds. `SPEC-plan-stage-absorption` landed on 2026-09-20 and every
task now enters through a SPEC, so the axis no longer decides what exists — only how strictly
the SPEC gates fire. That is a preset-shaped default with an override, not an independent axis.

The cost of keeping it is not theoretical. The axis doubles every rendered artifact — eight
`preset × dev_mode` synthesize snapshots, `instruction_baseline.json` keys spelled
`<command>@<dev_mode>`, `step_sensitivity`'s `ARMS`, the render fixtures — and a template edit
in this repository already trips six gates before the axis multiplies them. Worse, the axis has
no single answer for its own absent case: `models.py:1172-1182` documents a **deliberate
three-way split** where bare construction resolves to `spec-driven`, the reverse mapper and the
advisory gates resolve to `task-driven`, and `spec_need`'s verify oracle gate is fail-closed
with an explicit instruction not to align it. Three readers, three answers, one key.

## 🌅 Outcomes

After this change an operator can:

- Pick a preset and get the matching strictness without a second question. Onboarding asks
  **one fewer** question than it does today, not one more.
- Run `/harness-maker:make --update` on an existing `task-driven` harness and keep both their
  **preset** and their **relaxed gates** — the two were independently chosen and stay
  independently honoured.
- Read one function to learn what strictness this project is in, and one function to learn what
  sets it, with a structural test that fails when a second of either appears.
- Work in `warn` and still *see* the SPEC checks — Check 6 runs, SPEC-need detection runs, the
  consensus finalizer gets its machine SPEC — without any of them stopping the work.

A maintainer gets four synthesize snapshot arms instead of eight, and every rendered artifact
becomes a function of `preset` alone.

## 📋 In-Scope Scenarios

### S1: A task-driven harness upgrades without being re-rendered
**Given** a `.claude/harness.yaml` carrying `dev_mode: task-driven` and `preset: Production`
**When** any entry point loads it through `io_utils.load_harness_yaml`
**Then** the loaded config carries `spec.strictness: warn`, the `dev_mode` key is gone from the
returned mapping, and `preset` is still `Production`
**And** exactly one advisory line names the translation, and a second load of the same file
produces the same result without a second advisory

### S2: A spec-driven Side harness keeps its strict gates
**Given** `preset: Side` with `dev_mode: spec-driven` — the cross whose strictness disagrees
with its preset default
**When** the config is loaded and re-rendered
**Then** `spec.strictness` is `block`, written explicitly rather than left to preset derivation
**And** the rendered harness still carries the spec-gate hook

### S3: A harness that never had the key
**Given** a `harness.yaml` with neither `dev_mode` nor `spec.strictness`
**When** every reader resolves strictness
**Then** each one returns the preset-derived value — `block` for Production, `warn` for Side
**And** `spec_need`'s verify oracle gate still enforces, because it is fail-closed by design and
is the single documented exception

### S4: A malformed strictness value
**Given** `spec.strictness: "Block"`, `spec.strictness: true`, or any value outside
`{block, warn}`
**When** the reader resolves it
**Then** the reader fails closed to `block` and says which value it refused, rather than falling
through to a preset default that the malformed value was trying to override

### S5: `warn` shows the SPEC checks and stops nothing
**Given** a harness rendered at `spec.strictness: warn`
**When** `/hm:verify`, `/hm:execute` and `/hm:review` render
**Then** Check 6, the SPEC-need detection block and the `review_consensus finalize --spec` flag
are all present in the rendered text
**And** no rendered instruction in any of them tells the reader to STOP, HALT or block on a
SPEC condition

### S6: `block` renders the spec-gate hook and `warn` does not
**Given** the same project rendered at each strictness
**When** the settings and hook artifacts are compared
**Then** the `spec_gate` PreToolUse entry is present at `block` and absent at `warn`
**And** at `block` the hook's own runtime guard agrees with the render — it activates on
`spec.strictness == "block"`, never on a key that no longer exists

### S7: Nothing still reads the retired axis
**Given** the landed change
**When** `src/` and `src/harness_maker/templates/` are scanned
**Then** there are zero references to `dev_mode`, `DevMode`, `spec-driven` or `task-driven`
outside the one migration site that translates them and the tests that pin it
**And** the synthesize snapshot set has four arms, one per preset × project profile, not eight

### S8: The removal is announced and the reversal is recorded
**Given** `dev_mode` was a user-locked decision — memory `project_dev_mode_axis` records
"preset 과 직교, 4 cross 다 허용" as a standing choice
**When** the change lands
**Then** the CHANGELOG carries a BREAKING entry naming `dev_mode` and the migration
**And** a PLAN ADR states the reversal and its reason rather than letting the axis vanish
silently

### S9: Onboarding gets shorter, not longer
**Given** a fresh `/harness-maker:make` interview
**When** the config axes are asked
**Then** no question asks about strictness or development methodology
**And** `/hm:configure` offers `spec.strictness` as an editable entry

## 🚫 Non-Goals

- **Vocabulary renames and the `owners` role map** — that is the next roadmap item and carries
  its own hazard (`world.py:212` hashes the literal key `outcome_id`, so a rename invalidates
  every approval stamp). Nothing in this SPEC touches `intent.yaml`, `intent.py` or `world.py`.
- **A separate "light SPEC" axis.** `/hm:spec` Step 0's skip heuristic already produces a
  minimal SPEC for trivial work in either strictness; a second knob would duplicate it.
- **Changing what a preset means.** `Production` and `Side` keep their current depth; this
  change only makes strictness derive from them by default.
- **A deprecation window for `--dev-mode`.** The flag is removed outright in all four entry
  points (`spec_machine` check + waiver, `harness-maker make`, `codex_setup`).
- **Re-litigating the SPEC-first pipeline.** That `every task enters through a SPEC` is
  inherited from `SPEC-plan-stage-absorption`, not decided here.
- **Removing `/hm:spec`'s quality gate or changing its thresholds.** Only the block-vs-warn
  branch changes owner.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | The repository's only framework; `-m "not advisory"` mirrors CI |
| Config schema | `schema_version` 4 → 5 | Records when a file was written; the migration itself keys on **key presence**, so a file left at 4 still migrates (`PLAN-harness-diet` ADR-012) |
| Migration site | `io_utils.load_harness_yaml` | A migration in the renderer reaches only users who re-render; one in the loader reaches users who merely load |
| Readers / writers | Exactly one each | `[wiki:architecture] single-reader-single-writer-config-axis` — a second reader does not crash, it disagrees, and `/hm:health` then reports a mode the execution path does not take |
| Backward compatibility | `--dev-mode` removed outright | Rendered commands pin a version-specific plugin path (`…/harness-maker/0.58.0`), so a harness rendered before the change keeps calling the CLI that still has the flag |
| Preset preservation | `preset` is never rewritten by the migration | A `Production` + `task-driven` user must not be silently demoted to `Side` |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | `harness.yaml` schema 4 → 5: `dev_mode` is translated into `spec.strictness` and the key is dropped at load | schema/file format/storage layout | The user's configuration file is rewritten in place on the next `--update`; once the key is gone the original choice cannot be recovered from the file, so the translation must be right the first time |
| IRR-002 | `--dev-mode` is removed from all four CLI entry points with no alias | public API/CLI contract | A published flag; any external caller or older rendered harness that passes it gets an argparse error rather than a warning |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_ac_002_migration_maps_every_cross` |
| S2 | unit | `test_ac_002_migration_maps_every_cross` |
| S3 | unit | `test_ac_003_absent_key_resolves_from_preset` |
| S4 | unit | `test_ac_003_malformed_strictness_fails_closed` |
| S5 | unit | `test_ac_006_warn_renders_the_checks_and_blocks_nothing` |
| S6 | unit | `test_ac_006_block_renders_the_spec_gate_hook` |
| S7 | unit | `test_ac_004_no_dev_mode_reference_survives` / `test_ac_005_snapshot_arms_halve` |
| S8 | unit | `test_ac_008_removal_is_announced` |
| S9 | unit | `test_ac_009_onboarding_asks_no_strictness_question` |

### AC-001: strictness has exactly one reader and one writer

A single resolver owns "what strictness is this project in" and a single function owns setting
it; every other call site delegates. Readers are **discovered** by AST traversal of the modules
that import the config loader, never by a hand-maintained list — every hand list of readers in
this repository has been wrong (`[fail:design] new-marker-content-field-must-update-every-reader`,
count:3).

### AC-002: the migration maps every cross and never moves the preset

Six inputs — the four `preset × dev_mode` crosses, an absent key, and a malformed value — map to
a pinned `(preset, strictness)` pair. `preset` is identical to its input in all six rows.
Re-loading an already-migrated file is a fixed point and emits no second advisory.

### AC-003: an absent key resolves from the preset, with one named exception

With no `spec.strictness` and no `dev_mode`, every discovered reader returns the preset-derived
value. `spec_need`'s verify oracle gate is the single exception and stays fail-closed; the
exception is named in code and pinned by the test, so it cannot be "aligned away" by a later
reader that reads the general rule and not the comment.

### AC-004: no reference to the retired axis survives

`dev_mode`, `DevMode` and the two enum values appear nowhere in `src/` or the template tree
except at the one migration site and in the tests that pin it. The absence is quantified over
the whole tree, not sampled.

### AC-005: the render matrix loses its second axis

The synthesize snapshot set has four arms, not eight, and `instruction_baseline.json` carries no
key spelled `<command>@<dev_mode>`. Rendering the same project twice with only strictness
differing produces artifacts that differ **only** in the places S5 and S6 name.

### AC-006: warn renders the SPEC machinery and blocks nothing; block renders the hook

At `warn`, Check 6, the SPEC-need detection block and the `finalize --spec` flag are present and
carry no stop instruction. At `block` they are present and do stop. The `spec_gate` hook entry
is rendered at `block` only, and its runtime guard tests `spec.strictness`, not the removed key.
The reference for "what must not block" is the pre-change render at `dev_mode: task-driven`.

### AC-007: the CLI flag is gone from every entry point

`--dev-mode` is absent from `spec_machine` check, `spec_machine` waiver, `harness-maker make`
and `codex_setup`; passing it produces an argument error rather than being silently ignored.

### AC-008: the removal is announced and the reversal is recorded

The CHANGELOG carries a BREAKING entry naming `dev_mode` and the translation, and the PLAN
carries an ADR stating that this reverses the previously locked "four crosses all allowed"
decision, with the reason.

### AC-009: onboarding asks no strictness question

The rendered interview asks nothing about strictness or development methodology, and the
question count for a fresh install is strictly lower than before the change. `/hm:configure`
lists `spec.strictness` as an editable entry.

## ❓ Open Questions

None. All three interview rounds closed.

## 🔍 Refinement Decisions

- **Round 1** — Locked the knob shape (`spec.strictness: block | warn`, preset-derived default
  with a user override), the retirement mechanism (translate-then-strip in the loader,
  `schema_version` 4 → 5, migration keyed on key presence), and the meaning of `warn` (renders
  everything, blocks nothing; the spec-gate hook, whose only function is to block, therefore
  does not render at `warn` — a derived consequence, not a per-gate exception).
- **Round 2** — Locked the absent case (preset-derived for every reader, with `spec_need`'s
  verify oracle gate kept fail-closed as the single named exception) and the removal of
  `--dev-mode` with no deprecation alias. The DRI chose immediate removal over the recommended
  alias; the author's stated compatibility concern was then **withdrawn as overstated** —
  rendered commands pin a version-specific plugin path, so a harness rendered before the change
  keeps invoking the CLI that still carries the flag.
- **Round 3** — Locked no onboarding question (preset derives it, `/hm:configure` edits it) and
  the two irreversible decisions. AC-009 was added in this round to carry the onboarding answer;
  the AC skeleton shown to the DRI listed eight, and the ninth is a direct consequence of an
  answer given in the same round rather than new scope.
