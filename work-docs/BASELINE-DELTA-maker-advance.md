---
type: baseline-delta
task_slug: maker-advance
created: 2026-10-17
owns: [surface_baseline]
summary: "SPEC-maker-advance's shipped-surface growth (stage hand-offs name the world model), held as a PLAN allowance until the fold"
---

# Baseline delta — PLAN-maker-advance

The shipped surface **grew** by 87 chars per variant: spec and execute now end "… is the user's
call; if the world model began this run, its Advance rule applies now.", and spec prints the
`approval-status` state with the SPEC path and trims its intro to stay inside its 6 500 AC-004
budget, and `/hm:help` says Maker can enter the next stage. PLAN-maker-advance holds this as `surface_allowance` until the fold re-freezes
`tests/structural/surface_baseline.json` from main.

| variant | command | before (chars) | after | cause |
|---|---|---|---|---|
| claude | `spec` | 7 544 | 7 546 | hand-off names the world model; Step 5 and intro trimmed |
| claude | `execute` | 8 502 | 8 581 | hand-off names the world model |
| claude | `help` | 1 834 | 1 864 | names Maker's Advance rule |
| codex | `hm-spec` | 7 629 | 7 631 | same text as the Claude command |
| codex | `hm-execute` | 8 496 | 8 575 | same |
| codex | `hm-help` | 1 767 | 1 797 | same |

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 47 674 | 47 785 | +111: the surface **rose** by 0.23% |
| `aggregate_chars`.codex | 29 111 | 29 222 | +111: the surface **rose** by 0.38% |

Per ADR-010 the task that moved the surface owns its attribution; the fold writes the re-measured
numbers here, which keeps it out of `ratchet-rebaselined-by-its-own-subject`.
