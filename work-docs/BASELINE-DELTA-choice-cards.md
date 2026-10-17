---
type: baseline-delta
task_slug: choice-cards
created: 2026-10-17
owns: [surface_baseline]
summary: "SPEC-choice-cards' shipped-surface growth (the Choices rule and tool names at 13 sites), re-frozen from main after #40"
---

# Baseline delta — PLAN-choice-cards

The shipped surface **grew**: every stage command now carries the `**Choices.**` rule, and 13 choice
sites name the question tool. #40 held the growth as PLAN-choice-cards' `surface_allowance`; this
re-freezes `tests/structural/surface_baseline.json` from main at 03912b3c and sets the PLAN to
`complete`, so the allowance expires.

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`build_baseline()`), the install ref pinned.

| variant | command | before (chars, round trips) | after | cause |
|---|---|---|---|---|
| claude | `research` | 4 671, 0 | 4 879, 0 | Choices rule; site l names the tool |
| claude | `spec` | 7 380, 1 | 7 544, 1 | Choices rule; Step 5 exempts only at `auto_full` (IRR-001) |
| claude | `execute` | 8 397, 2 | 8 502, 2 | Choices rule and sites a-c, offset by dropping the intro sentence that restated the steps |
| claude | `wrapup` | 5 907, 2 | 6 201, 2 | Choices rule and sites d, e, j; its AC-004 budget moved to 3 800 (DRI card) |
| claude | `make` | 6 559, 1 | 6 606, 1 | sites f, g name `AskUserQuestion` |
| claude | `health` | 7 525, 5 | 7 449, 5 | Cursor `AskQuestion` dropped |
| claude | `uninstall` | 1 731, 3 | 1 691, 3 | same |
| codex | `hm-research` | 4 706, 0 | 4 936, 0 | same text as the Claude command |
| codex | `hm-spec` | 7 446, 1 | 7 629, 1 | same |
| codex | `hm-execute` | 8 363, 2 | 8 496, 2 | same |
| codex | `hm-wrapup` | 5 961, 2 | 6 283, 2 | same |

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 46 479 | 47 181 | +702: the surface **rose** by 1.5% |
| `aggregate_chars`.codex | 28 243 | 29 111 | +868: the surface **rose** by 3.1% |

`render_sha` and `payload_digest` moved mechanically with the re-freeze. Per ADR-010 the task
that moved the surface owns its attribution, and writing it next to the re-freeze is what keeps this
out of `ratchet-rebaselined-by-its-own-subject`. `_ATOMIC_RATCHET` re-measured: research 4554 → 4647,
wrapup 4568 → 4862.
