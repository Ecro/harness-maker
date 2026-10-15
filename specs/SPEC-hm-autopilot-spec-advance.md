---
type: spec
task_slug: hm-autopilot-spec-advance
status: draft
created: 2026-10-14
tags: [harness-maker, spec, autopilot, jinja2, bugfix]
test_framework: pytest
tier: 1
interview_rounds: 0
lane: light
intent: HM-LIGHT-LANE
summary: "auto_full autopilot advances past an unapproved SPEC instead of stopping at it"
---

# SPEC — hm-autopilot-spec-advance

## 🎯 Intent

On a 2026-10-14 bench, headless `/hm:spec` runs at `autonomy.level: auto_full` stopped after the
SPEC in 6 of 15 runs. Each got `proceed: true, next_stage: execute, judgment_auto_answered: true`
from `hm autopilot_caps boundary --judgment-gate pending` and still ended with text like
"there is no approval to advance on, so I stopped here". No code was written.

The rendered spec stage contradicts the boundary. Step 5 says an unstamped SPEC means "autopilot
stops at this stage". That is false at `auto_full`, where the boundary answers the pending gate
without an approval and `/hm:wrapup`'s land hold asks again before landing. The boundary's
`judgment_directive` says "write NO approval" and never says the missing approval is no reason to
stop. This SPEC fixes the two sentences.

## 🌅 Outcomes

- Step 5 says a missing approval does not end the stage by itself: at any level other than
  `auto_full` the stage stops at this gate, at `auto_full` the boundary answers it and its
  `proceed: true` advances without an approval, and `/hm:wrapup` asks again before landing. It never says an approval is written.
- The sentence is the same at every level, so a `gated` render still differs from an armed one
  only inside the marked advance and picker blocks (the AC-005 contract of the autopilot gate).
- The auto_full `judgment_directive` keeps its text and adds that neither the auto-answer nor
  (for `spec`) the missing approval is a reason to stop: on `proceed: true`, invoke `next_stage`.
- The Claude Code command and the Codex stage skill carry the same Step 5 text.

## 📋 In-Scope Scenarios

### S1: auto_full Step 5 no longer claims autopilot stops
**Given** a harness rendered at `auto_full` for Claude Code and Codex
**When** the spec command and the `hm-spec` skill are read at Step 5
**Then** neither says "autopilot stops at this stage", and both say a missing approval does not
end the stage and that the boundary's `proceed: true` at `auto_full` advances without an approval

### S2: Step 5 is the same at every level
**Given** harnesses rendered at `gated`, `ask`, `auto_safe` and `auto_full`
**When** the spec command and skill are read at Step 5
**Then** all four render the same Step 5

### S3: the directive says to advance
**Given** an `auto_full` marker over the default pipeline
**When** `boundary --current spec --judgment-gate pending` runs
**Then** `proceed` is true and `judgment_directive` keeps "write NO approval" and adds that the
missing approval is not a reason to stop

## 🚫 Non-Goals

- Changing what the boundary decides at any level.
- Writing or implying a SPEC approval at any level.
- The plan and review stage text (the directive's new sentence covers them in passing).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Goldens | Snapshots, strictness references and the surface baseline re-captured with a dated note | Third-party move rule |
| Compatibility | Python 3.12; harnesses re-render through `/hm:make` | Text only |

## 🔒 Irreversible Decisions

(none)

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) | `tests/render/test_render_spec_autopilot_advance.py::test_auto_full_step5_says_the_stage_advances` |
| S2 | unit (render) | `tests/render/test_render_spec_autopilot_advance.py::test_step5_is_the_same_at_every_level` |
| S3 | unit | `tests/unit/test_autopilot_spec_advance_directive.py::test_directive_says_a_missing_approval_is_no_reason_to_stop` |

### AC-001: auto_full Step 5 says the stage advances without an approval
### AC-002: Step 5 is the same at every level
### AC-003: the spec directive says the missing approval is no reason to stop

## ❓ Open Questions

(none)

## 🔍 Refinement Decisions

- Interview not run: the DRI scoped the fix from the bench evidence on 2026-10-14.
- Lane `light`: two sentences in one template and one module, no irreversible decision.
- A first draft made the sentence conditional on `autopilot_enabled(config)` and kept the old
  sentence for `gated`. `test_autopilot_gate_render.py::test_ac_005_the_gated_delta_is_exactly_the_advance_blocks`
  refused it: level-dependent text outside the marked blocks. One sentence true at every level is
  simpler and keeps that contract.
