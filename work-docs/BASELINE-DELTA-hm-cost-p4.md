---
type: baseline-delta
task_slug: hm-cost-p4
created: 2026-11-10
owns: [surface_baseline]
summary: "SPEC-hm-cost-p4's shipped-surface growth: execute's test-naming and no-copy rules and conditional reads, spec's unchanged-behaviour rule"
---

# Baseline delta — PLAN-hm-cost-p4

The shipped surface **grew** by 228 chars per variant. Execute gains the shared parametrized-test rule
with `AC-NNN-<i>` ids, the no-copy / no-regenerate rule, and the "tests bind by these names" line
(AC-004), and its Step 1 read becomes conditional (AC-005); it loses the `test_ids` edit and
`validate` instruction and Step 0.3's "Read it back". Spec gains the behaviour-unchanged rule (AC-006).
The new wording was trimmed once; the rest is held as PLAN-hm-cost-p4's `surface_allowance` and the
AC-004 stage budgets rise (ADR-004, confirmed by the DRI on 2026-11-10).

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`measure_surface()`) against the frozen baseline.

| variant | command | before (chars, round trips) | after | cause |
|---|---|---|---|---|
| claude | `spec` | 7 858, 1 | 7 989, 1 | behaviour-unchanged AC rule before the execute hand-off line |
| claude | `execute` | 9 122, 2 | 9 219, 2 | test naming + no-copy rule, conditional Step 1 read, `test_ids` edit and `validate` dropped |
| codex | `hm-spec` | 7 952, 1 | 8 083, 1 | same text as the Claude command |
| codex | `hm-execute` | 9 125, 2 | 9 222, 2 | same |

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 48 737 | 48 965 | +228 |
| `aggregate_chars`.codex | 30 192 | 30 420 | +228 |

AC-004 stage budgets (`tests/unit/test_overhaul_p1_surface.py`): spec 6 850 → 6 950, execute 7 550 →
7 610. The growth is held as PLAN-hm-cost-p4's `surface_allowance` until the task lands; the baseline is
then re-frozen from main and `_ATOMIC_RATCHET` re-measured in a fold commit.

The prose grew in a task whose purpose is to cut cost: the rules replace a hand-edited `test_ids` step
that failed and retried in the diagnostic runs, and a same-session re-read of the PLAN and SPEC.
