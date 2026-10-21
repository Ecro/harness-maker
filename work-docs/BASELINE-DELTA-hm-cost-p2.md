---
type: baseline-delta
task_slug: hm-cost-p2
created: 2026-10-21
owns: [surface_baseline]
summary: "SPEC-hm-cost-p2's shipped-surface growth: execute's short-PLAN, edit-in-place and export-golden rules, wrapup's golden.json land flag"
---

# Baseline delta — PLAN-hm-cost-p2

The shipped surface **grew**. Execute gains the short-PLAN rule (AC-008), the edit-in-place rule
(AC-007), the `export-golden` parametric-test instruction that replaces the `load_golden_table` import
(AC-003) and the five irreversible categories written verbatim (AC-004); one `mark-tested` call now
takes every `--ac`. Wrapup adds `--optional specs/SPEC-<slug>.golden.json` (AC-010). Spec gains the
same edit-in-place and category lines but nets about zero after trims to Step 0, Step 2, Step 4 and
Step 5. Further cuts would have edited wording that other SPECs pin by test (execute's hot tier, the
Resume line, wrapup's REVIEW/RESEARCH flags), so the DRI chose to raise the budgets (2026-10-21).

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`measure_surface()`) against the frozen baseline at a188d25f.

| variant | command | before (chars, round trips) | after | cause |
|---|---|---|---|---|
| claude | `execute` | 8 581, 2 | 8 805, 2 | short PLAN, edit in place, export-golden, verbatim categories, stdlib property fallback (ADR-008) offset by trims |
| claude | `spec` | 7 546, 1 | 7 543, 1 | edit in place and categories, offset by trims |
| claude | `wrapup` | 6 201, 2 | 6 242, 2 | golden.json land flag |
| codex | `hm-execute` | 8 575, 2 | 8 808, 2 | same text as the Claude command |
| codex | `hm-spec` | 7 631, 1 | 7 637, 1 | same |
| codex | `hm-wrapup` | 6 283, 2 | 6 324, 2 | same |

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 47 785 | 48 047 | +262 |
| `aggregate_chars`.codex | 29 222 | 29 502 | +280 |

AC-004 stage budgets (`tests/unit/test_overhaul_p1_surface.py`): execute 7 000 → 7 250, wrapup
3 800 → 3 850. The growth is held as PLAN-hm-cost-p2's `surface_allowance` until the task lands;
the baseline is then re-frozen from main (the generator refuses a task-branch SHA) and
`_ATOMIC_RATCHET` re-measured, in a fold commit like #43.

Per ADR-010 the task that moved the surface owns its attribution, and writing it next to the
allowance and the later re-freeze is what keeps this out of `ratchet-rebaselined-by-its-own-subject`.
The surface **rose**: +0.55% claude, +0.96% codex, in a task whose purpose is to cut cost, because
the rules it adds remove whole round trips and rewrites that cost far more than the prose.
