---
type: review
task_slug: choice-cards
created: 2026-10-17
spec: "[[SPEC-choice-cards]]"
---

# REVIEW — choice-cards (round 1, code-reviewer; second opinion skipped: no codex CLI in this container)

## Findings

| id | severity | file:line | finding | disposition | resolution | authority |
|---|---|---|---|---|---|---|
| F1 | P2 | skills/world-model/SKILL.md.j2:35 | `{#- … -#}` glued the Maker rule to the previous paragraph | accepted | plain `{# #}`; AC-001 now asserts the rule opens a paragraph | — |
| F2 | P2 | stages/wrapup.md.j2 site j | a stash-pop/collision card could put a destructive option first as the recommendation | accepted | "and no recommendation" at site j | — |
| F3 | P3 | stages/execute.md.j2 site a | rewritten site a lost who runs approve and what `/hm:spec` does | accepted | worded like site b: approve runs …, `/hm:spec` stops | — |
| F4 | P3 | execute site c, wrapup site d | exit-5 asks named no options | accepted | "(approve / stop)" | — |
| F5 | P3 | stages/spec.md.j2 Step 0 | skip path still exempts without asking | rejected | the skip path is the trivial-change path, not an interview; recorded in SPEC Refinement Decisions | SPEC-choice-cards Refinement Decisions |
| F6 | P3 | skills/intent-layer/SKILL.md.j2:59 | its fallback says "ask in chat and wait", not a numbered list | rejected | intent-layer is out of scope (Non-Goals: already uses the tool); align later | SPEC-choice-cards Intent |
| F7 | P3 | skills/world-model site m | Codex may cap options per question | rejected | unverified; the numbered-list fallback covers it | SPEC-choice-cards Refinement Decisions |
| F8 | P3 | interview.py:657 | docstring still names Cursor AskQuestion | rejected | Python is out of scope (Constraints: templates and tests only) | SPEC-choice-cards Constraints |

Budget path, decided by the DRI on cards: the rule was shortened (AC-001 amended), execute trimmed its
intro sentence, and SPEC-hm-overhaul-p1 AC-004's wrapup budget moved 3,500 → 3,800 (re-approved,
20d524bc) because every candidate wrapup trim was kept-feature text its tests pin.

`hm check` gates: the pytest gate runs with `-x` and stops at one of the five known container-only
failures (`test_land_hold.py::…[unreadable]`, root ignores the chmod); the full `pytest -n auto` run
shows only those five.
