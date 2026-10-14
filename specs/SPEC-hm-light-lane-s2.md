---
type: spec
task_slug: hm-light-lane-s2
status: draft
created: 2026-10-14
tags: [harness-maker, spec, jinja2, cost, context-carry, autopilot, loop]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 2a of HM-LIGHT-LANE: drop unreachable loop branches, state auto-advance once, cut dead review steps"
---

# SPEC — hm-light-lane-s2 (stage 2a)

## 🎯 Intent

About 75% of a /hm: run's cost is stage text carried in the main context and re-read on every
call. The 2026-10-14 phase-pruning research
(`/mnt/project-files/harness-research/ab/2026-10-14-phase-pruning.md`) found that most removable
text is not a low-value check but a path that cannot run in the harness that renders it. The DRI
approved five cuts on decision cards the same day; this SPEC carries the four that remove text,
plus the stage-1 review's carried finding about the skills' typed-only flag.

## 🌅 Outcomes

- With `loop.enabled: false`, the six stage commands, their `.claude/stages/*.md` copies and the
  Codex stage skills carry no loop-only branch: no Gate 0 receipt, no execute Step 0.2 or Step 5,
  no verify Check 5, and no sentence mentioning Gate 0 (review's two loop-mode lines in its
  pseudo-code included). With `loop.enabled: true` they render those branches word for word, and
  the flag changes nothing else.
- The auto-advance procedure is written once, in `.claude/hm/autopilot-advance.md`. Each stage
  command keeps a short stub with the no-op conditions, the gate-before-boundary rule, its own
  gate predicate and its own executed lines, and reads the shared file from the project root only
  when autopilot is active. A missing or unreadable file stops the stage at its STOP banner. A
  `gated` harness renders neither.
- Review no longer carries Step 2.5 (silent-intent-miss hook), step 5c (complexity measure) or
  the `📏 Size & Complexity` report section; `/hm:health` drops the sub-check that read 2.5's
  output.
- Execute Phase C.0 and Phase D.5 are two or three lines each.
- `disable-model-invocation: true` on the seven typed-only skills comes from
  `synthesize._TYPED_ONLY_SKILLS`, the way commands get it from `_TYPED_ONLY_COMMANDS`.
- The rendered spec, execute, review and verify commands of this repo shrink by at least 20,000
  characters together.

## 📋 In-Scope Scenarios

### S1: A loop-off harness renders no loop branch
**Given** a harness with `loop.enabled: false`
**When** `/hm:make` renders it for Claude Code and Codex
**Then** no stage command, `.claude/stages/*.md` copy or Codex stage skill contains the Gate 0
receipt, execute Step 0.2, execute Step 5 or verify Check 5
**And** no remaining sentence mentions Gate 0

### S2: A loop-on harness keeps them
**Given** the same answers with `loop.enabled: true`
**When** both are rendered
**Then** the loop-on render has exactly the loop-only sections in the fixed inventory below, and
removing them yields the loop-off render

Inventory (lead line of each section, fixed before the edit): every stage's Gate 0 receipt
heading; execute `#### Step 0.2 — Loop mode`, `### Step 5 — Worktree finalize` and its Quality
Bar line about the `execute-<uuid>` worktree; verify `### Check 5 — Worktree merge cleanliness`;
review's `• Loop mode: proceed` bullet in the grade gate and `→ Loop mode: emit the Gate 0
receipt` line in the confirmation pass.

### S3: Autopilot reads the shared procedure once
**Given** a non-`gated` harness rendered for Claude Code
**When** a stage reaches its auto-advance check with autopilot active
**Then** the stage stub names its gate predicate and runs the same `autopilot_caps` lines as
before, and points at `.claude/hm/autopilot-advance.md` for the shared procedure
**And** the stub says to read the file from the project root (above `.worktrees/` when inside
one), never from `<WT>`, and to print the STOP banner and run nothing below when it is missing or
unreadable
**And** with autopilot inactive the stub is a no-op that reads nothing: the no-op conditions are
in the stub itself

### S4: A gated harness carries no autopilot text
**Given** `autonomy.level: gated`
**When** it is rendered
**Then** no stage command has an auto-advance stub and `.claude/hm/autopilot-advance.md` is not
rendered

### S5: Dead review telemetry is gone
**Given** a Production or Side render
**When** review and health are read
**Then** neither mentions `record_intent_miss`, `silent_intent_miss_rate`,
`review_churn complexity` or `Size & Complexity`

### S6: The no-answers render keeps Gate 0 beside the loop driver
**Given** the legacy render path with no config (`config_dump=None`), which renders the loop
commands
**When** the stage bodies are rendered on that path, for Claude Code and Codex
**Then** they carry the Gate 0 receipt, and for a real dump they carry it exactly when
`_loop_enabled` is true

## 🚫 Non-Goals

- Lever 2 for review and execute (moving full-lane-only and rare paths into reference files).
  That is stage 2b, which reuses the `.claude/hm/` directory this SPEC introduces.
- The Codex auto-advance block (`codex_autopilot_advance.md.j2`) and Cursor, which has no
  `Skill` tool and treats the block as a no-op.
- Deleting Python modules: `observability.intent_miss` and `review_churn complexity` stay
  importable and callable; only their prompt callers go.
- spec Step 4.6's trigger (the DRI kept spec-validator on every lane), wrapup Steps 2 and 3,
  research Phase 0/0.75/4.
- Renumbering steps or checks. Check 6 stays Check 6 when Check 5 does not render.
- Inline one-line loop mentions that do not instruct a Gate 0 receipt ("When dispatched by
  `/hm:loop` or by autopilot", "Loop mode: proceed").
- Any change to `autopilot_caps`, `iter_receipts` or the loop driver.
- Accepted loop residue: verify's "The 6 Checks" count and its `[5/6]` sample report line, and the
  stage-start loop-marker probe in the step manifest (it also suppresses the banner and serves
  autopilot). Execute's "a phase that exited GREEN skips to Step 4.5" is reworded to not name the
  Gate 0 heading.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Loop flag | One reader: the loop-on decision for stage bodies uses the same rule as `synthesize._loop_enabled` | A stage body without Gate 0 next to a rendered loop driver would make Gate 0 see every stage missing on every iteration |
| Autopilot semantics | `autopilot_caps` lines, judgment-gate flags and caps are unchanged per stage | The DRI asked to keep each stage's own gate check |
| Goldens | `autopilot_gate_golden.json` and synth snapshots are re-captured with a dated docstring entry naming what moved | Third-party move rule in `test_autopilot_gate_render.py` |
| Supersedes | SPEC-loop-opt-in AC-009's allowed body diffs widen by exactly the six stage commands, the six `.claude/stages/*.md` and the six Codex stage skills (AC-012) | Its Non-Goals deferred in-body loop prose; this SPEC is that follow-up and keeps a bound |
| Shared-file read | From the project root, never `<WT>`; fail closed to the STOP banner | `.claude/` may be untracked, or stale on an old task branch |
| AC-005 allowlist | Exactly the six wrapped NO-OP lead lines of the old block and the two Step 1 predicate lead lines (spec, verify), listed in the test | Fixed here so a dropped line cannot be excused after the fact |
| Size baseline | Measured under `_surface_baseline.pinned_install_ref` on this repo's `.claude/harness.yaml` at e9b6198; an edit to that file needs a re-measure | Install-path length and config both move the byte count |
| Compatibility | Python 3.12, existing harnesses re-render through `/hm:make` with no migration | A new generated file is added; nothing is renamed |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add the generated file `.claude/hm/autopilot-advance.md` and reserve `.claude/hm/` for harness-maker's on-demand reference files | schema/file format/storage layout | Every rendered harness gains the path; stage 2b adds siblings, and moving the directory later needs a retire step for files already on disk |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) | `tests/render/test_render_light_lane_s2.py::test_loop_off_renders_no_loop_branch` |
| S2 | unit (render, differential) | `tests/render/test_render_light_lane_s2.py::test_loop_on_adds_exactly_the_loop_branches` |
| S3 | unit (render) | `test_stub_points_at_the_shared_procedure`, `test_executed_autopilot_lines_are_unchanged`, `test_shared_procedure_keeps_every_instruction` |
| S4 | unit (render) | `tests/render/test_render_light_lane_s2.py::test_gated_renders_no_autopilot_text` |
| S5 | unit (render) | `tests/render/test_render_light_lane_s2.py::test_dead_review_telemetry_is_gone` |
| Outcome (C.0/D.5) | unit (render) | `tests/render/test_render_light_lane_s2.py::test_repair_phases_are_three_lines_or_fewer` |
| Outcome (skills) | unit (render, differential) | `tests/render/test_render_light_lane_s2.py::test_typed_only_skill_flag_comes_from_the_list` |
| Outcome (size) | unit (render) | `tests/render/test_render_light_lane_s2.py::test_the_four_stage_bodies_shrink` |
| S6 | unit | `tests/render/test_render_light_lane_s2.py::test_no_answers_path_keeps_gate0_beside_the_driver` |
| Supersedes row | unit (differential) | `tests/unit/test_loop_opt_in.py::test_ac009_disable_removes_only_loop_files` |

### AC-001: Loop-off renders carry no loop branch
### AC-002: Loop-on renders add exactly the loop branches
### AC-003: Each stage stub points at the shared auto-advance procedure
### AC-004: The executed autopilot lines are unchanged
### AC-005: The shared procedure keeps every instruction of the old block
### AC-006: A gated harness renders no autopilot text
### AC-007: Dead review telemetry is gone
### AC-008: Repair phases C.0 and D.5 are three lines or fewer
### AC-009: The typed-only skill flag comes from the list
### AC-010: The four stage bodies shrink by 20,000 characters
### AC-011: The no-answers render keeps Gate 0 beside the loop driver
### AC-012: The loop flag's allowed body diffs stay enumerated

## ❓ Open Questions

(none: design decisions for `/hm:execute` Step 0 follow)

## 🔍 Refinement Decisions

- Interview not re-run: scope was settled by the DRI's decision cards on 2026-10-14
  (loop-only branches and auto-advance "2단계에 포함", Step 2.5/5c "제거", C.0/D.5 "축소",
  spec-validator "유지") and by "승인할게 계속 진행해".
- Lane `full`: about 25 files, and IRR-001 is a storage-layout decision.
- Stage 2 is split: this SPEC (2a) carries the cuts; lever 2 for review and execute is 2b, so
  each review stays readable.
- The shared procedure goes in a rendered file, not in the `autopilot_caps` JSON: the gate
  classification must happen before the CLI call, and a file keeps the text verbatim.
- spec-validator pass 1: MAJOR_REVISION (2 critical, 6 warning, 2 suggestion); codex skipped (CLI
  not installed). All ten folded in before approval: fixed loop inventory (AC-002), project-root
  read and fail-closed (S3, AC-003), fixed allowlist, stricter AC-006, the None path (S6,
  AC-011), an enumerated loop-opt-in diff set (AC-012), residue classified in Non-Goals.
- Work stays on the session's designated branch instead of an `hm/<slug>` task worktree, as in
  stage 1.
