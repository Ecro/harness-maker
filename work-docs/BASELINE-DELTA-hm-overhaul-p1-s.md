---
type: baseline-delta
task_slug: hm-overhaul-p1-s
created: 2026-10-16
owns: [surface_baseline]
summary: "PR-S's shipped-surface movement (seven stages collapsed to four), re-frozen in-branch"
---

# Baseline delta — PLAN-hm-overhaul-p1-s

The shipped surface **shrank**: the stage collapse removed three commands (`configure`, `review`,
`verify`) and two Codex skills (`hm-review`, `hm-verify`), and rewrote the four kept stages as
self-contained bodies. A shrink cannot be held as a `surface_allowance` (the allowance only
grants headroom; the frozen baseline's shape check still rejects the missing commands), so
unlike PR-C this PLAN re-froze `tests/structural/surface_baseline.json` in the branch.

**DRI item.** `assert_sha_is_durable` refuses a task-branch SHA, so `render_sha` records the
merge-base `a3c2a5a8` (verified an ancestor of `origin/main`; the local `main` lags). The
numbers are measured from this branch's tree, not from `a3c2a5a8`. After the squash lands,
re-freeze from main so `render_sha` names the commit the numbers came from.

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`build_baseline()`), the install ref pinned, so the version stamp is in no number below.

| variant | command | before (chars, round trips) | after | cause |
|---|---|---|---|---|
| claude | `research` | 17 292, 10 | 4 671, 0 | one self-contained stage body; the fan-out and `!` preamble lines are gone |
| claude | `spec` | 37 941, 10 | 7 380, 1 | the light/full split and the machine-SPEC fragment folded into one body |
| claude | `execute` | 39 587, 19 | 7 485, 2 | PLAN, A.5 and the review loop merged; review runs inside execute |
| claude | `wrapup` | 29 315, 20 | 5 827, 2 | Steps 1–8 compressed; `hm check` replaces the gate fan-out |
| claude | `health` | 8 636, 6 | 7 525, 5 | the autopilot auto-advance smoke check dropped; retired-command references repointed |
| claude | `help` | 2 103, 0 | 1 834, 0 | the stage table is four rows |
| claude | `metrics` | 15 447, 7 | 2 475, 0 | the stage-agent ledger readers are retired (AC-011) |
| claude | `configure` | 12 604, 4 | — | retired command (hand-edit `.claude/harness.yaml`) |
| claude | `review` | 56 833, 20 | — | retired; folded into `execute` |
| claude | `verify` | 12 651, 7 | — | retired; `hm check` in `wrapup` |
| codex | `hm-research` | 22 222, 8 | 4 706, 0 | same body as the Claude command |
| codex | `hm-spec` | 46 331, 11 | 7 446, 1 | same |
| codex | `hm-execute` | 64 792, 27 | 7 541, 2 | same |
| codex | `hm-wrapup` | 55 348, 32 | 5 921, 2 | same |
| codex | `hm-help` | 2 022, 0 | 1 767, 0 | same help edit |
| codex | `hm-review` | 80 213, 29 | — | retired |
| codex | `hm-verify` | 24 590, 11 | — | retired |

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 240 699 | 45 487 | −195 212: the surface **fell** by 81% |
| `aggregate_chars`.codex | 295 518 | 27 381 | −268 137: a 91% reduction |

`render_sha` and `payload_digest` moved mechanically with the re-freeze. Per ADR-010 the task
that moved the surface owns its attribution, and writing it in the commit that moved it is what
keeps this out of `ratchet-rebaselined-by-its-own-subject`.

## Review round 1 (2026-10-16): held as an allowance, not re-frozen

The review put back four rules the collapse had dropped and moved RED in front of the phases
(PLAN ADR-044..ADR-047). The surface grew, so the frozen baseline stays as committed and the
growth is held as this PLAN's `surface_allowance` until the DRI re-freezes from main.

| variant | command | frozen (chars, round trips) | now | cause |
|---|---|---|---|---|
| claude | `execute` | 7 485, 2 | 8 397, 2 | Phase A writes every AC test and RED runs once (ADR-044); the irreversible-decision stop and the test-edit rule (ADR-046); the background-gate rule (ADR-045) |
| claude | `wrapup` | 5 827, 2 | 5 875, 2 | the background-gate rule, answer-gated intent writes, the closing Understanding print; the rest compressed to stay at 3 497 of the 3 500 AC-004 budget |
| codex | `hm-execute` | 7 541, 2 | 8 363, 2 | same text; Codex gets the no-JSON rule without a background call |
| codex | `hm-wrapup` | 5 921, 2 | 5 929, 2 | same |

| key | frozen | now | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 45 487 | 46 447 | +960 (the allowance's `chars`) |
| `aggregate_chars`.codex | 27 381 | 28 211 | +830 |

The per-command allowance (`execute: 653`, `wrapup: 41`) is the measured overshoot of the
atomic ceilings in `test_command_size_budget.py` (8 072 vs 7 419 and 4 536 vs 4 495 on the
opt-in arm).
