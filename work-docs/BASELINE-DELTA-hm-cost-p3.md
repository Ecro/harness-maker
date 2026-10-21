---
type: baseline-delta
task_slug: hm-cost-p3
created: 2026-10-21
owns: [surface_baseline]
summary: "SPEC-hm-cost-p3's shipped-surface growth: spec's defaults rule, execute's batching rule and post-REVIEW check, wrapup's --reuse call"
---

# Baseline delta — PLAN-hm-cost-p3

The shipped surface **grew**. Spec gains the rule that settles spec-validator critiques as defaults
under Refinement Decisions and limits Open Questions to what the DRI owns (AC-001). Execute gains the
`&&` batching rule with its exclusions (AC-004) and an unconditional `hm check` after the REVIEW doc
(AC-003), and drops the per-round `hm check` rerun. Wrapup's gate becomes `hm check --reuse` (AC-003).
The new wording was trimmed once; the rest is held as PLAN-hm-cost-p3's `surface_allowance` and the
AC-004 stage budgets rise (ADR-007, agent-decided under the DRI's autopilot instruction).

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`measure_surface()`) against the frozen baseline at 022d6f2a.

| variant | command | before (chars, round trips) | after | cause |
|---|---|---|---|---|
| claude | `spec` | 7 543, 1 | 7 858, 1 | defaults rule in Step 4.6 (DRI-owned critiques excluded, critical ones surfaced before a stamp), Open Questions limit in Step 3 |
| claude | `execute` | 8 805, 2 | 9 122, 2 | batching rule (stops at the first failure), post-REVIEW `hm check` acted on as at Bind, per-round rerun dropped |
| claude | `wrapup` | 6 242, 2 | 6 300, 2 | `--reuse` on the Step 1 gate |
| codex | `hm-spec` | 7 637, 1 | 7 952, 1 | same text as the Claude command |
| codex | `hm-execute` | 8 808, 2 | 9 125, 2 | same |
| codex | `hm-wrapup` | 6 324, 2 | 6 382, 2 | same |

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 48 047 | 48 737 | +690 |
| `aggregate_chars`.codex | 29 502 | 30 192 | +690 |

AC-004 stage budgets (`tests/unit/test_overhaul_p1_surface.py`): spec 6 500 → 6 850, execute 7 250 →
7 550, wrapup 3 850 → 3 900. The growth is held as PLAN-hm-cost-p3's `surface_allowance` until the
task lands; the baseline is then re-frozen from main and `_ATOMIC_RATCHET` re-measured in a fold commit.

Per ADR-010 the task that moved the surface owns its attribution, and writing it next to the
allowance and the later re-freeze is what keeps this out of `ratchet-rebaselined-by-its-own-subject`.
The surface **rose** (+1.4% claude, +2.3% codex) in a task whose purpose is to cut cost: the rules
added remove a gate rerun and the approval-turn rewrite, which cost far more per run than the prose.

## Folded into the baseline from main

After the squash (277405a9) the allowance expired with the PLAN, so the growth was folded on main:
`tests/structural/surface_baseline.json` re-frozen by the generator at 277405a9e6c5 (claude 48 737,
codex 30 192, the after column above; `render_sha` and `payload_digest` moved mechanically with the
re-freeze), and `_ATOMIC_RATCHET` execute 8 480 → 8 797, spec 7 033 → 7 400, wrapup 4 862 → 4 961 (the
measured atomic renders). The AC-005 rows' harness SHA cdf28dce is not reachable from main after the
squash, so both `tests/fixtures/hm_cost_p3/harness_shas.json` and
`tests/fixtures/overhaul_p1/harness_sha_aliases.json` gained a squash alias, checked by tree hash
(`src` and `scripts` are identical in cdf28dce and 277405a9).
