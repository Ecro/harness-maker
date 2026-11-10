---
type: plan
task_slug: ask-less
status: planning
created: 2026-11-10
spec: "[[SPEC-ask-less]]"
summary: One choice rule (R) in every stage and Maker; spec picks the intent and asks only DRI-owned slots; wrapup and the intent-layer skill write plain intent records unasked under an approved SPEC.
surface_allowance:
  chars: 800
  reason: "SPEC-ask-less: rule R replaces the old choice rule in every stage (+150 each), spec's interview rules (+34), and wrapup's split of intent writes into unasked records and asked decisions, one call per line with its `-file` flags (+334). SPEC-wrapup-gate's landed text (execute −4, wrapup −14) is netted into the measured numbers. Raised by the measured growth only (SPEC Constraints, Size)."
  delta_doc: BASELINE-DELTA-ask-less.md
  commands:
    execute: 146
    hm-execute: 146
    research: 150
    hm-research: 150
    spec: 184
    hm-spec: 181
    wrapup: 320
    hm-wrapup: 320
---

# PLAN — ask-less

- Phase 1 — scope: `stages/_hm.md.j2` `choices()` and Maker's copy carry rule R; exit: `uv run pytest -q tests/render/test_ask_less.py -k ac_001`; risk: a stage that relied on "never choose for the user" now decides a choice the DRI owns; rollback: revert the two templates.
- Phase 2 — scope: `stages/spec.md.j2` Steps 0.5, 2 and 3; exit: `uv run pytest -q tests/render/test_ask_less.py -k "ac_002 or ac_003 or ac_004 or ac_008"`; risk: an oracle or constraint the DRI should have seen is settled silently; rollback: revert `spec.md.j2`.
- Phase 3 — scope: `stages/wrapup.md.j2` intent block and Step 8, `skills/intent-layer/SKILL.md.j2`, `references/workflow-feedback.md.j2`, the rubric; exit: `uv run pytest -q tests/render/test_ask_less.py -k "ac_005 or ac_006 or ac_007"`; risk: an intent record written under an exempt SPEC; rollback: revert those templates.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/intent.py`
- `src/harness_maker/spec_machine.py`
- `src/harness_maker/check.py`

ADR-001: the size budget is paid by trimming duplicated prose in the spec stage and the intent-layer skill, not by dropping rules; the creation deep interview keeps every topic. **Decided by:** agent
ADR-002: the `open_ended_cap_by_locale` knob keeps rendering ("At most N open-ended follow-up(s) per turn") beside the new 3-questions-per-round limit, so the config key stays meaningful. **Decided by:** agent
ADR-003: superseded pins move to the SPEC's literals: test_choice_cards AC-001, test_overhaul_p1_kept (wrapup intent block, `metric` and `observe` forms), test_render_intent_layer (candidate multi-select). **Decided by:** agent
