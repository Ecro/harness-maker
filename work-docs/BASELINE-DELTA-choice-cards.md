---
type: baseline-delta
task_slug: choice-cards
created: 2026-10-17
---

# BASELINE-DELTA — choice-cards

| where | change | chars |
|---|---|---|
| research, spec, execute, wrapup (each runtime) | `**Choices.**` rule from `stages/_hm.md.j2` `choices()` | about +175 each |
| execute, wrapup, research, make | the question tool named at sites a-g, j, l | about +25 each |
| execute | intro sentence that restated the steps dropped; site a shortened; `validate` call fixed to the positional path | about -150 |
| health, uninstall | Cursor `AskQuestion` dropped | about -30 each |

Net: claude +648 (46,479 → 47,127), codex +814 (28,243 → 29,057); wrapup keeps its kept-feature text and its AC-004 budget
moved to 3,800 (DRI card 2026-10-17). Folded into
`tests/structural/surface_baseline.json` after merge.
