---
type: baseline-delta
task_slug: maker-advance
created: 2026-10-17
owns: [surface_baseline]
summary: "SPEC-maker-advance's shipped-surface growth (stage hand-offs name the world model's Advance rule), re-frozen from main after #42"
---

# Baseline delta — PLAN-maker-advance

The shipped surface **grew**: spec and execute now end "… is the user's call; if the world model
began this run, enter it now unless its Advance rule stops.", and `/hm:help` says Maker can enter
the next stage. Spec offsets most of its line by printing the `approval-status` state with the SPEC
path and trimming its intro, to stay inside its 6 500 AC-004 budget. #42 held the growth as
PLAN-maker-advance's `surface_allowance`; this re-freezes `tests/structural/surface_baseline.json`
from main at a188d25f and sets the PLAN to `complete`, so the allowance expires.

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`build_baseline()`), the install ref pinned.

| variant | command | before (chars, round trips) | after | cause |
|---|---|---|---|---|
| claude | `spec` | 7 544, 1 | 7 546, 1 | hand-off names the Advance rule; Step 5 and intro trimmed |
| claude | `execute` | 8 502, 2 | 8 581, 2 | hand-off names the Advance rule |
| claude | `help` | 1 834, 0 | 1 864, 0 | names Maker's Advance rule |
| codex | `hm-spec` | 7 629, 1 | 7 631, 1 | same text as the Claude command |
| codex | `hm-execute` | 8 496, 2 | 8 575, 2 | same |
| codex | `hm-help` | 1 767, 0 | 1 797, 0 | same |

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 47 674 | 47 785 | +111: the surface **rose** by 0.23% |
| `aggregate_chars`.codex | 29 111 | 29 222 | +111: the surface **rose** by 0.38% |

`render_sha` and `payload_digest` moved mechanically with the re-freeze. Per ADR-010 the task
that moved the surface owns its attribution, and writing it next to the re-freeze is what keeps this
out of `ratchet-rebaselined-by-its-own-subject`. `_ATOMIC_RATCHET` re-measured: execute 8072 → 8256
(the ratchet fixture also carries #40's Choices growth, which that fold left unmeasured for execute).
