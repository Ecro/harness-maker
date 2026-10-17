---
type: plan
task_slug: choice-cards
status: complete
created: 2026-10-17
spec: "[[SPEC-choice-cards]]"
surface_allowance:
  chars: 900
  reason: "SPEC-choice-cards: the Choices rule (~175 chars) in four stages and Maker plus the tool names at 13 sites, offset by trimming execute's hot-tier note and wrapup's intent bullets; measured at Phase 3 after the DRI kept wrapup's text and raised its AC-004 budget to 3,800."
  delta_doc: BASELINE-DELTA-choice-cards.md
  commands:
    research: 50
    hm-research: 50
    wrapup: 250
    hm-wrapup: 250
summary: "One Choices macro for the four stages plus a Maker copy, tool names at the 13 sites, Cursor AskQuestion gone, spec Step 5 exempt narrowed"
---

# PLAN — choice-cards

## Phases

1. Stages. scope: stages/_hm.md.j2 (choices macro), research/spec/execute/wrapup.md.j2. exit: `uv run pytest -q tests/render/test_choice_cards.py -k "ac_001 or ac_004"`. risk: surface ratchet. rollback: revert.
2. Commands and Maker. scope: commands/hm/{make,health,uninstall}.md.j2, skills/world-model/SKILL.md.j2. exit: `uv run pytest -q tests/render/test_choice_cards.py tests/render/test_render_maker_front_door.py`. risk: Maker 4,500-char cap. rollback: revert.
3. Goldens. scope: tests/snapshot/*.expected.yaml, pinned shas that move. exit: `uv run pytest -q -n auto tests/structural tests/render tests/unit`. risk: re-capture from the wrong render. rollback: git checkout the fixtures.

## 🚧 Contract Boundaries

### Do not change
- src/harness_maker/*.py
- templates/agents/

## ADRs

ADR-001: The stage rule is a `_hm.md.j2` macro rendered right after the CLI line; Maker carries its own copy because it does not import `_hm`. **Decided by:** agent
ADR-002: Approval sites name the tool with no recommendation; `/hm:make` site f keeps its equals wording. **Decided by:** user (SPEC card 2026-10-17)
