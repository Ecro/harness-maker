---
type: plan
task_slug: hm-light-lane-s2
status: planning
created: 2026-10-14
tags: [harness-maker, plan, python, jinja2, cost, context-carry]
spec: "[[SPEC-hm-light-lane-s2]]"
research_doc: "[[RESEARCH-hm-light-lane]]"
interview_rounds: 0
adrs: 5
validator_outcome: NOT_RUN
spec_need_verdict: spec-required
summary: "Stage 2a of HM-LIGHT-LANE: loop-gated branches, auto-advance once, dead review steps out"
intent: HM-LIGHT-LANE
---

# PLAN — hm-light-lane-s2

## 🎯 Executive Summary

Removes stage text that cannot run in the harness that renders it, per the DRI's 2026-10-14
decision cards. One phase, one PR. Master plan: `PLAN-hm-light-lane.md` stage 2 (split into 2a
here and 2b for lever 2).

## 📐 Architecture Decision Records

### ADR-001: The shared auto-advance procedure is a rendered file
**Decided by:** agent (SPEC IRR-001, pending DRI approval on the card). `.claude/hm/autopilot-advance.md`,
rendered only when `autonomy.level != gated`, from `templates/hm/autopilot-advance.md.j2`. The
stage stub keeps the NO-OP condition, the stage's gate predicate and its executed lines; the file
carries the classification ladder, slug rule, JSON reading list and precedence clause verbatim.

### ADR-002: One reader for the loop flag
**Decided by:** agent. A Jinja global `loop_enabled(config)` holds the dict rule;
`synthesize._loop_enabled` delegates to it for non-`None` dumps, so a stage body cannot drop
Gate 0 while the loop driver renders.

### ADR-003: Loop gating covers sentences that instruct a Gate 0 receipt
**Decided by:** agent. Beyond the named sections, review's "emit the Gate 0 receipt" line and any
other sentence that instructs the receipt render only with the loop on. Plain "Loop mode:
proceed" mentions stay (SPEC Non-Goals).

### ADR-004: Health's silent-intent-miss sub-check goes with review Step 2.5
**Decided by:** agent. Its only input was 2.5's audit file; the Python module stays.

### ADR-005: Registry follows the render
**Decided by:** agent. `step_sensitivity` drops review Step 2.5; loop-gated headings carry
`renders_when="loop.enabled"`.

## 📝 Implementation Plan

1. **Phase 1 — tests, then templates.** depends_on: none · scope: stage templates (execute,
   review, verify, research, spec, wrapup), `stage_end_summary.md.j2`, new
   `templates/hm/autopilot-advance.md.j2`, `health.md.j2`, seven skill templates, `synthesize.py`,
   `template_globals.py`, `step_sensitivity.py`, tests and goldens · exit: `uv run pytest tests -n
   auto` green except the 7 pre-existing environment failures · risk: medium (autopilot wording)
   · rollback: revert the PR.

## 🧪 Testing Strategy

`tests/render/test_render_light_lane_s2.py` per SPEC AC-001…AC-010; update
`test_autopilot_advance_render_gate.py` to read the shared template; SPEC-loop-opt-in AC-009 test
widened to the stage files; goldens re-captured with dated entries.
