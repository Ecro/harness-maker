---
type: baseline-delta
task_slug: hm-overhaul-p1-c
created: 2026-10-16
owns: [surface_allowance]
summary: "PR-C's shipped-surface movement (Cursor target removal), held as an allowance until it lands"
---

# Baseline delta — PLAN-hm-overhaul-p1-c

`surface_baseline.json` is **not** regenerated here. The baseline can only be re-frozen from a
main-reachable commit (`assert_sha_is_durable`), so this PLAN holds its growth as a
`surface_allowance` and the fold happens from main after PR-C lands.

Measured against the frozen baseline with the render version pinned (`pinned_install_ref`), so
the 0.63.0 version stamp is not part of any number below.

| variant | command | baseline | now | Δ chars | Δ round trips | cause |
|---|---|---|---|---|---|---|
| claude | research | 16 677 | 17 292 | **+615** | **+3** (7 → 10) | Phase 1's fan-out condition lost its `"cursor" not in config.targets` half. This repo's `.claude/harness.yaml` still lists cursor (dropped at parse), so the Claude command now takes the three-`Explore` fan-out branch instead of the plain "Run these in parallel" branch. That is the branch a claude-code-only harness always rendered. |
| claude | configure | 12 704 | 12 596 | −108 | 0 | Cursor removed from the targets line and the roots list. |
| claude | make | 6 647 | 6 559 | −88 | 0 | `.cursor` dropped from the roots loop. |
| claude | help | 2 183 | 2 103 | −80 | 0 | The Cursor targets row and note removed. |
| claude | health | 8 643 | 8 636 | −7 | 0 | `cursor` dropped from the `--targets` list. |
| codex | hm-help | 2 030 | 2 022 | −8 | 0 | Same help edit, Codex skill. |

| | baseline | now | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 240 359 | 240 691 | **+332** |
| `aggregate_chars.codex` | — | — | −8 |

The +332 is not new prose: it is the fan-out branch (+615) the research template already ships
for every non-Cursor harness, minus 283 chars of Cursor text removed. The allowance declares
exactly `chars: 332` and `round_trips: {research: 3}`.
