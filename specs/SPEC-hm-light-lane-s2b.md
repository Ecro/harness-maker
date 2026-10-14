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

- When wrapup is delegated (`'wrapup' in delegation.stages`), the Claude Code wrapup command no
  longer carries Steps 1–5.6. They render in `.claude/hm/wrapup-steps.md`. Step 0.5 tells
  `stage-delegate` to read that file under the brief's `base_root`, and the degraded path tells the
  main loop to read it from the project root. Not delegated (the shipped default), the steps stay
  inline: there the main loop runs them anyway, so a Read would save no carry.
- The same holds for verify's six checks and advisory probes (`.claude/hm/verify-checks.md`). The
  `## Output` format stays in the command, because the main loop prints that report on the
  delegated-success path.
- `stage-delegate` may follow exactly those two files as instructions (IRR-002); every other file it
  reads stays data. If its file is missing or unreadable it returns no receipt, so the main loop takes
  the degraded path, which reads the same file and stops.
- The Claude Code review command keeps the Auto-Fix Loop and Confirmation Pass headings, the
  conditions that start them and the light-lane skip rule; their bodies render in
  `.claude/hm/review-autofix.md` and `.claude/hm/review-confirmation.md`.
- The Claude Code execute command keeps the Phase A.5 heading, the light-lane skip line and the
  `stage_agent_ledger` block it points at; the gate's procedure renders in
  `.claude/hm/execute-a5.md`.
- `/hm:loop`'s "substitute `<WT>` for every Read" rule names `.claude/hm/` as the exception.
- The `.claude/stages/*.md` copies follow their commands. Cursor has no dispatch tool, so a Cursor
  wrapup or verify on a delegated harness always takes the Read path.
- Every instruction of the four commands at `d2c0ab0` is in the new command or one of its
  reference files, and every moved section is byte-identical to its old text.
- Codex stage skills are unchanged.
- This repo's four rendered Claude commands shrink by at least 40,000 characters together.

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
from `<WT>`) and runs Steps 1–5.6 from it
**And** if the file is missing or unreadable it names the file, says to re-render with `/hm:make`,
and STOPs at once: no Step 5.7 intent record, no Step 6 commit

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

### S5a: A non-delegated stage keeps its body inline
**Given** `delegation.stages` is `[]`, `[wrapup]` or `[verify]`
**When** the harness is rendered for Claude Code
**Then** each non-delegated stage's command is byte-identical to its d2c0ab0 render

### S5b: The delegate follows only its allowlisted file
**Given** a delegated wrapup or verify
**When** `stage-delegate` is dispatched
**Then** its prompt names `<base_root>/.claude/hm/wrapup-steps.md` (or `verify-checks.md`) as the
one on-disk instruction source and keeps every other file as data
**And** when that file is missing or unreadable it returns no JSON, so the receipt check exits
`unparseable` and the degraded path stops

### S6: The loop reads reference files from the project root
**Given** `loop.enabled: true`
**When** `/hm:loop` dispatches review or verify inside `<WT>`
**Then** its Step 4 rule exempts `.claude/hm/` from the `<WT>` substitution, matching the pointers

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
- A saving on the full lane's confirmation pass: it runs on most full reviews, so there the move is
  neutral (the same text, read later, plus one Read). The saving is on the light lane and on reviews
  that stop before approving.
- Changing the shipped `delegation.stages` default.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| One source per moved section | The command (Codex arm) and the reference file include the same partial | Two copies of the text would drift |
| Reference-file read | From the project root, never `<WT>`; missing or unreadable → STOP naming the file | Same rule as `.claude/hm/autopilot-advance.md` (SPEC-hm-light-lane-s2 S3) |
| Rendering | The five files render whenever the stage commands render, `gated` harnesses included | Unlike the auto-advance file, these back paths every harness can take |
| Generated-file frontmatter | Each file carries `generated_by`, `content_hash`, `source_template`, `harness_maker_version` | CLAUDE.md security rule for generated files |
| Supersedes | SPEC-loop-opt-in AC-009's allowed body diffs widen by exactly `.claude/hm/verify-checks.md` and `.claude/hm/review-confirmation.md`; SPEC-hm-light-lane-s2's loop inventory (AC-001/002) spans command plus reference files | Check 5 and the confirmation pass's Gate 0 line move into those files; the bound stays enumerated |
| Size baseline | Re-frozen with a BASELINE-DELTA by this task (ADR-010) | `ratchet-rebaselined-by-its-own-subject` |
| Goldens | Snapshots and goldens re-captured with a dated note naming what moved | Third-party move rule |
| Compatibility | Python 3.12; existing harnesses re-render through `/hm:make` with no migration | Files are added, none renamed |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add five generated files under `.claude/hm/`: `wrapup-steps.md`, `verify-checks.md`, `review-autofix.md`, `review-confirmation.md` and `execute-a5.md` are the names the commands and `stage-delegate` read | schema/file format/storage layout | Renaming one later needs a retire step for the copies on disk and breaks a harness whose command and file came from different versions |
| IRR-002 | `stage-delegate` follows `<base_root>/.claude/hm/wrapup-steps.md` and `verify-checks.md` as instructions; every other file stays data | security/permission boundary | Its prompt said nothing read from disk could extend its instructions. Anyone who can write the base checkout's `.claude/hm/` can now direct the delegate, the same reach they already have over the command files |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_wrapup_dispatch_names_the_steps_file` |
| S2 | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_pointers_read_from_root_and_fail_closed` |
| S3 | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_rare_paths_live_in_reference_files` |
| S4 | unit (render, differential) | `tests/render/test_render_light_lane_s2b.py::test_moved_text_is_preserved` |
| S5 | unit (render, differential) | `tests/render/test_render_light_lane_s2b.py::test_codex_stage_skills_unchanged` |
| S5a | unit (render, differential) | `tests/render/test_render_light_lane_s2b.py::test_undelegated_stages_stay_inline` |
| S5b | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_delegate_trusts_only_its_file` |
| S6 | unit (render) | `tests/render/test_render_light_lane_s2b.py::test_loop_reads_reference_files_from_root` |
| Supersedes row | unit (differential) | `tests/unit/test_loop_opt_in.py::test_ac009_disable_removes_only_loop_files`, `tests/render/test_render_light_lane_s2.py::test_loop_on_adds_exactly_the_loop_branches` |
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
### AC-009: The four Claude commands shrink by 40,000 characters
### AC-010: A non-delegated stage keeps its body inline
### AC-011: The delegate follows only its allowlisted file and fails without it
### AC-012: The loop exempts reference files from the worktree substitution
### AC-013: The loop flag's allowed diffs stay enumerated

## ❓ Open Questions

(none: design decisions for `/hm:execute` Step 0 follow)

## 🔍 Refinement Decisions

- Interview not re-run: the scope is PLAN-hm-light-lane stage 2 (lever 2), approved with the five
  levers, and the DRI said on 2026-10-14 to run every stage on the recommended option.
- Lane `full`: about 20 files; IRR-001 is a storage-layout decision and IRR-002 a security boundary.
- spec-validator pass 1: MAJOR_REVISION (3 critical, 5 warning, 3 suggestion); codex skipped (CLI
  not installed). Folded in: delegation-off stays inline (S5a), the delegate trust rule as IRR-002
  (S5b), the positive "never from `<WT>`" check, the Supersedes row, the loop exemption (S6), an
  immediate wrapup stop before 5.7, the ledger block kept in execute, verify's Output kept, the
  full-lane confirmation trade-off in Non-Goals, a `/hm:make` recovery hint, Cursor in the fixture.
  The size floor drops to 40,000 because Output and the ledger block stay.
- The wrapup inline body moves rather than goes: this repo has no `delegation.jsonl`, so the
  degraded rate cannot be checked, and PLAN-wrapup-context-carry measured 14 of 16 runs degraded
  before its fix. A Read on the degraded path keeps that path whole.
- Review Step 3.5 stays inline: when a model is configured it runs on every full review.
- Work stays on the session's designated branch instead of an `hm/<slug>` task worktree, as in
  stages 1 and 2a.
