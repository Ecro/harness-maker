---
type: plan
task_slug: hm-light-lane-s2b
status: planning
created: 2026-10-14
spec: "[[SPEC-hm-light-lane-s2b]]"
intent: HM-LIGHT-LANE
lane: full
tdd: true
---

# PLAN — hm-light-lane-s2b (stage 2b, lever 2)

## 🎯 Goal

Move the bodies that run in a subagent, after a failed gate, or only on the full lane out of the
Claude Code stage commands and into `.claude/hm/` reference files, word for word, so a light run
carries none of them (SPEC-hm-light-lane-s2b).

## 🧭 ADRs

### ADR-001: One partial per moved section, included by both arms
**Decided by:** agent. Each moved block becomes `templates/stages/_partials/<stage>_<block>.md.j2`.
The Codex arm of the stage template includes it inline; the Claude arm renders a pointer; the
reference template `templates/hm/<file>.md.j2` includes it with `is_codex = false`. One source
makes AC-006's byte equality hold by construction and AC-007's Codex identity follow from it.
**Rejected:** copying the text into the reference templates (drifts), and post-render splitting
in Python (hides the source of the text from the template reader).

### ADR-002: Reference files render whenever the stage commands render
**Decided by:** agent. `synthesize._reference_files` keeps the autopilot gate for
`autopilot-advance.md` only; the five new files have no gate, because every harness can take the
paths that read them.

### ADR-003: The pointer is the same three-part sentence everywhere
**Decided by:** agent. Read `<file>` from the project root (above `.worktrees/`), never from
`<WT>`; follow it; missing or unreadable → name the file and STOP (wrapup: before Step 6). One
partial `templates/stages/_partials/ref_pointer.md.j2` renders it, taking the file name and the
stop clause, so AC-005 tests one sentence shape.

### ADR-004: The delegate reads the file from `brief.base_root`
**Decided by:** agent. The dispatch instruction names `<brief.base_root>/.claude/hm/<file>`. The
delegate starts clean and has the brief, so the path needs no cwd reasoning. This also replaces
the old implicit "find the steps in the command file" read, which loaded the whole command.

### ADR-006: Wrapup and verify move only when delegated
**Decided by:** agent, from spec-validator pass 1. With `delegation.stages: []` (the shipped
default) the main loop runs those bodies itself, so a Read saves no carry and adds a STOP path.

### ADR-007: The delegate's one on-disk instruction source (IRR-002)
**Decided by:** agent. `stage-delegate_body.md.j2` names the two allowlisted files; a missing file
yields no JSON, which the existing reconciler maps to `unparseable` and the degraded path.

### ADR-005: Variables the moved text needs come from template globals or the reference context
**Decided by:** agent. Review's C2 heading uses `lenses` and `groups`; any such stage-local
`{% set %}` is either computed by a template global both renders call, or passed through
`_reference_files`' context. StrictUndefined fails a render that misses one.

## 📝 Implementation Plan

1. **Phase 1 — partials, pointers, reference files.** depends_on: none · scope:
   `templates/stages/{wrapup,verify,review,execute}.md.j2`, `templates/stages/_partials/*`,
   `templates/hm/{wrapup-steps,verify-checks,review-autofix,review-confirmation,execute-a5}.md.j2`,
   `synthesize.py` (`_reference_files`), `templates/agents/stage-delegate_body.md.j2`, `templates/commands/hm/loop.md.j2` (Step 4 exemption), `tests/unit/test_loop_opt_in.py` and `tests/render/test_render_light_lane_s2.py` (Supersedes row), `step_sensitivity.py` if its registry must name the
   reference-file headings, `tests/render/test_render_light_lane_s2b.py` (AC-001..009), the
   pre-edit goldens for AC-006/007 under `tests/fixtures/light_lane_s2b/`, re-captured snapshots and
   goldens, `tests/structural/surface_baseline.json` + `work-docs/BASELINE-DELTA-hm-light-lane-s2b.md`,
   instruction-preservation bookkeeping, `CHANGELOG.md` · exit: `uv run pytest tests -n auto` green
   except the 8 known environment failures; ruff, mypy --strict clean · risk: medium
   (instruction preservation, golden churn) · rollback: revert the PR.

## 🚧 Contract Boundaries

### Do not change
- `wrapup_brief`, `wrapup_receipt`, `delegation_ledger`, the receipt schema.
- The Codex stage skills' bytes (AC-007).
- wrapup Step 5.7 and Steps 6 onward.

## 🧪 Testing Strategy

Capture the d2c0ab0 renders (Claude commands, Codex skills, loop on and off) into fixtures before
editing a template, then write AC-001..009 against them (RED), then move the text (GREEN).

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| A moved section loses a line | AC-006 byte equality per heading + instruction subset |
| The delegate keeps reading the whole command | ADR-004 dispatch line names the file; test pins it |
| Stale reference file inside a worktree | read from the project root (ADR-003) |
| A variable missing in the reference render | StrictUndefined fails loud (ADR-005) |

## ✅ Success Criteria

- [ ] AC-001..009 pass.
- [ ] Surface baseline re-frozen lower with BASELINE-DELTA.
