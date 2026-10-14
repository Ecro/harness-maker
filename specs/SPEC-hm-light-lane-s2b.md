---
type: spec
task_slug: hm-light-lane-s2b
status: draft
created: 2026-10-14
tags: [harness-maker, spec, jinja2, cost, context-carry, reference-files]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 2b of HM-LIGHT-LANE: move delegated, rare and full-lane-only stage bodies into on-demand reference files"
---

# SPEC — hm-light-lane-s2b (stage 2b, lever 2)

## 🎯 Intent

A stage command's text enters the main context when the stage starts and is carried, and re-read,
on every later call of the session. About 75% of a /hm: run's cost is that carry (RESEARCH-hm-light-lane).
Stage 2a removed text that cannot run. Stage 2b moves text that runs elsewhere or seldom: the
bodies `stage-delegate` runs for wrapup and verify, the review rounds that run only after a failed
grade gate, the confirmation pass, and execute's full-lane-only test-reviewer gate. The text is
kept word for word in `.claude/hm/` reference files (IRR-001 of SPEC-hm-light-lane-s2 reserved
the directory) and read only on the path that needs it.

## 🌅 Outcomes

- The Claude Code wrapup command no longer carries Steps 1–5.6. They render in
  `.claude/hm/wrapup-steps.md`. Step 0.5 tells `stage-delegate` to read that file from the brief's
  `base_root`, and the degraded path tells the main loop to read it there.
- The Claude Code verify command no longer carries the six checks, the advisory probes or the
  text-output format. They render in `.claude/hm/verify-checks.md`, read the same two ways.
- The Claude Code review command keeps the Auto-Fix Loop and Confirmation Pass headings, the
  conditions that start them and the light-lane skip rule; their bodies render in
  `.claude/hm/review-autofix.md` and `.claude/hm/review-confirmation.md`.
- The Claude Code execute command keeps the Phase A.5 heading, the light-lane skip line and its
  emit command; the gate's procedure renders in `.claude/hm/execute-a5.md`.
- Every instruction of the four commands at `d2c0ab0` is in the new command or one of its
  reference files, and every moved section is byte-identical to its old text.
- Codex stage skills are unchanged.
- This repo's four rendered Claude commands shrink by at least 45,000 characters together.

## 📋 In-Scope Scenarios

### S1: Wrapup delegation reads the steps from the reference file
**Given** a harness rendered for Claude Code
**When** wrapup reaches Step 0.5 and the dispatch tool is available
**Then** the dispatch instruction tells `stage-delegate` to Read `.claude/hm/wrapup-steps.md`
under the brief's `base_root` and perform Steps 1 through 5.6
**And** the command contains no Step 1–5.6 heading

### S2: A degraded wrapup reads the file or stops before committing
**Given** the brief degraded, the dispatch tool is unavailable, or the receipt is unusable
**When** the main loop reaches the inline-body pointer
**Then** it reads `.claude/hm/wrapup-steps.md` from the project root (above `.worktrees/`, never
`<WT>`) and runs Steps 1–5.6 from it
**And** if the file is missing or unreadable it names the file and STOPs before Step 6, so no
commit is made without those steps

### S3: Rare and full-lane-only paths are read only when taken
**Given** a review whose round 1 passes the grade gate on `lane: light` with no fix, or an execute
on `lane: light`
**When** the stage runs
**Then** it reads none of `review-autofix.md`, `review-confirmation.md` or `execute-a5.md`
**And** on a path that needs one (round 2+, a confirmation pass, A.5 on `lane: full`) the command
says to Read that file from the project root, and to STOP naming it when it is missing or unreadable

### S4: Nothing is lost in the move
**Given** the d2c0ab0 render and the new render of the same answers
**When** the instructions of each of the four commands are extracted with the existing
instruction-preservation extractor
**Then** each old instruction is in the new command or in one of that stage's reference files
**And** each moved section's text equals its d2c0ab0 text

### S5: Codex keeps its inline bodies
**Given** a render with the `codex` target
**When** the Codex stage skills for wrapup, verify, review and execute are rendered
**Then** they are byte-identical to the d2c0ab0 render

## 🚫 Non-Goals

- Deleting any instruction. This SPEC moves text; it removes none.
- The Codex stage skills (Codex has no dispatch tool and runs the bodies inline).
- Stage 3: running light execute and verify through `stage-delegate`, and carrying lens results as
  verdict + path.
- wrapup Step 5.7 and Steps 6 onward, which run in the main loop (ADR-004 of
  PLAN-wrapup-context-carry).
- Changes to `wrapup_brief`, `wrapup_receipt`, `delegation_ledger` or the receipt schema.
- Renumbering steps, checks or phases.
- Review Step 3.5 (second opinion) and Telemetry Emit, which run on every full review.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| One source per moved section | The command (Codex arm) and the reference file include the same partial | Two copies of the text would drift |
| Reference-file read | From the project root, never `<WT>`; missing or unreadable → STOP naming the file | Same rule as `.claude/hm/autopilot-advance.md` (SPEC-hm-light-lane-s2 S3) |
| Rendering | The five files render whenever the stage commands render, `gated` harnesses included | Unlike the auto-advance file, these back paths every harness can take |
| Generated-file frontmatter | Each file carries `generated_by`, `content_hash`, `source_template`, `harness_maker_version` | CLAUDE.md security rule for generated files |
| Size baseline | Re-frozen with a BASELINE-DELTA by this task (ADR-010) | `ratchet-rebaselined-by-its-own-subject` |
| Goldens | Snapshots and goldens re-captured with a dated note naming what moved | Third-party move rule |
| Compatibility | Python 3.12; existing harnesses re-render through `/hm:make` with no migration | Files are added, none renamed |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add five generated files under `.claude/hm/`: `wrapup-steps.md`, `verify-checks.md`, `review-autofix.md`, `review-confirmation.md` and `execute-a5.md` are the names the commands and `stage-delegate` read | schema/file format/storage layout | Renaming one later needs a retire step for the copies on disk and breaks a harness whose command and file came from different versions |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_wrapup_dispatch_names_the_steps_file` |
| S2 | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_pointers_read_from_root_and_fail_closed` |
| S3 | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_rare_paths_live_in_reference_files` |
| S4 | unit (render, differential) | `tests/render/test_render_light_lane_s2b.py::test_moved_text_is_preserved` |
| S5 | unit (render, differential) | `tests/render/test_render_light_lane_s2b.py::test_codex_stage_skills_unchanged` |
| Outcome (verify) | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_verify_dispatch_names_the_checks_file` |
| Outcome (files) | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_reference_files_render_with_generated_frontmatter` |
| Outcome (size) | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_the_four_commands_shrink` |

### AC-001: Wrapup Steps 1–5.6 render only in the reference file
### AC-002: Verify checks render only in the reference file
### AC-003: Review's auto-fix rounds and confirmation pass render only in reference files
### AC-004: Execute Phase A.5's procedure renders only in the reference file
### AC-005: Every pointer reads from the project root and fails closed
### AC-006: Nothing is lost and nothing is rewritten in the move
### AC-007: Codex stage skills are unchanged
### AC-008: The reference files render with generated-file frontmatter in every harness
### AC-009: The four Claude commands shrink by 45,000 characters

## ❓ Open Questions

(none: design decisions for `/hm:execute` Step 0 follow)

## 🔍 Refinement Decisions

- Interview not re-run: the scope is PLAN-hm-light-lane stage 2 (lever 2), approved with the five
  levers, and the DRI said on 2026-10-14 to run every stage on the recommended option.
- Lane `full`: about 15 files, and IRR-001 is a storage-layout decision.
- The wrapup inline body moves rather than goes: this repo has no `delegation.jsonl`, so the
  degraded rate cannot be checked, and PLAN-wrapup-context-carry measured 14 of 16 runs degraded
  before its fix. A Read on the degraded path keeps that path whole.
- Review Step 3.5 stays inline: when a model is configured it runs on every full review.
- Work stays on the session's designated branch instead of an `hm/<slug>` task worktree, as in
  stages 1 and 2a.
