---
type: baseline-delta
task_slug: loop-opt-out
created: 2026-09-29
owns: [surface_baseline.json, autopilot_gate_golden.json]
summary: "Turning /hm:loop off in this repo's harness.yaml shrank the rendered surface"
---

# Baseline delta — loop opt-out in this repo

This repo's `harness.yaml` now sets `loop.enabled: false`. That is the post-release follow-up
named in `specs/SPEC-loop-opt-in.md`. The shipped-surface baseline is rendered from that file,
so `loop` and `loop-p5-batch` left the render and `help` gained its one-line enable hint (AC-004).
No template changed.

Why the change: the operator does not use `/hm:loop` in this repo. The intent LOOP-OPT-IN
predicted that the opt-out would move `dead_rendered_bytes` from about 21.7 to about 9.2. The
measurement was 19.8 -> 7.3 (target 10), and the intent closed as met on 2026-09-29.

| key | before | after | delta |
|---|---:|---:|---:|
| `aggregate_chars.claude` | 414 198 | 358 106 | -56 092 |
| `aggregate_chars.codex` | 367 970 | 312 513 | -55 457 |
| claude `loop` chars / round trips | 51 336 / 10 | removed | -51 336 / -10 |
| claude `loop-p5-batch` chars / round trips | 4 794 / 2 | removed | -4 794 / -2 |
| claude `help` chars | 2 041 | 2 079 | +38 |
| codex `hm-loop` chars / round trips | 50 244 / 11 | removed | -50 244 / -11 |
| codex `hm-loop-p5-batch` chars / round trips | 5 251 / 0 | removed | -5 251 / 0 |
| codex `hm-help` chars | 1 927 | 1 965 | +38 |

The aggregate shrank, the right way for a surface ratchet, and the shrink is frozen in the same
commit as `test_a_large_shrink_means_the_baseline_went_stale` requires. The Claude round-trip
table in `tests/structural/test_roundtrip_budget.py` loses its `loop` (10) and `loop-p5-batch` (2)
rows, so the total goes 159 -> 147. The command floor in `test_surface_baseline.py` goes 14 -> 12.
`render_sha` and `payload_digest` move with any re-freeze.

**What is lost.** These dogfood gates no longer watch the size or round trips of the loop
templates, which still ship to projects that opt in. Unit and render tests that pass
`loop=True` still cover them, and the `ask@*` golden arms still hash them. Growth in
`loop.md.j2` will not trip the aggregate ratchet while this repo keeps loop off.

**Ownership (ADR-010).** This is not ratchet-rebaselined-by-its-own-subject. The ratchet guards
template growth, and this movement comes from a config choice on templates that were not edited.
The autopilot golden re-capture for the two `auto_safe@*` arms is recorded in
`tests/structural/test_autopilot_gate_render.py`. Setting `loop.enabled: true` restores every value
in the "before" column.
