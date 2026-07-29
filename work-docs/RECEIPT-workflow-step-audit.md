---
type: receipt
task_slug: workflow-step-audit
status: partial
created: 2026-07-29
plan: "[[PLAN-workflow-step-audit]]"
baseline: "[[BASELINE-workflow-step-audit]]"
summary: "Phase 7 re-measurement: the mandated-call reduction is measured; the turn/wall-clock re-measurement is not yet possible"
---

# RECEIPT — Phase 7 re-measurement

## 0. The honest headline, first

**The pre-registered direction PR-1 cannot be evaluated, and not because it failed.**

PR-1 binds `hm:verify` main-loop turns per run to fall. Its subject is Phase 1, and
**Phase 1 was skipped** on the user's explicit instruction after the effort/payoff table
in this document's §4 showed it to be the most expensive phase in the PLAN and the least
consequential in wall-clock terms. `verify.md.j2` is byte-identical to its pre-change
form and its mandated call count is unchanged at 13.

A prediction whose subject was never touched is **not evaluable**. It is recorded here as
`n/a — subject unchanged`, not as pass, not as fail. Re-registering it against a
different subject after the fact would be exactly the reinterpretation the pre-registered
direction exists to prevent.

**The four quantities ADR-012 requires — main-loop turns, subagent turns, active
wall-clock, and carry, per stage — have no post-change values yet.** The changes landed
in this commit; no `/hm:` stage has run against them. A receipt reporting post-change
turns today would be reporting `n = 0`, and ADR-012's whole point is that `n` is stated.
§3 records what must be re-run and when.

What *is* measured, now, is the rendered surface. That is a real and complete
measurement, and it is the only one this receipt claims.

## 1. Measured — mandated round-trips and characters

Same generator as Phase 0 (`tests/structural/_surface_baseline.py`), same counting rule
(ADR-011: `^!` lines for the Claude variant, `Bash(` call sites for Codex, plus every
`Task(`), same config (this repo's `.claude/harness.yaml`).

| Variant | Round-trips before | after | Δ | Chars before | after | Δ |
|---|---:|---:|---:|---:|---:|---:|
| claude | 297 | 283 | **−14** | 830,393 | 820,815 | **−9,578 (−1.15%)** |
| codex | 102 | 100 | **−2** | 311,474 | 308,218 | **−3,256 (−1.05%)** |

Per command, where it moved:

| Command | Before | After | Δ | Cause |
|---|---:|---:|---:|---|
| `wrapup` | 32 | 29 | −3 | Steps 6→7.6 → `wrapup_land` |
| `execute` | 15 | 14 | −1 | Phase D select-then-one-call |
| `exec-rev-wrap-ver` (default) | 56 | 52 | −4 | both, fused |
| `exec-rev-wrap` | 46 | 42 | −4 | both, fused |
| `plan-exec-rev` | 28 | 27 | −1 | execute, fused |
| `exec-rev` | 17 | 16 | −1 | execute, fused |
| `hm-execute` (codex) | 14 | 13 | −1 | Phase D |
| `hm-wrapup` (codex) | 30 | 29 | −1 | partial — Codex renders the composite too |

For a single full pipeline run (`research → spec → plan → execute → review → verify →
wrapup`): **95 → 91 mandated calls, −4.2%.**

## 2. Three things the table above does not say, stated because they matter more

**(a) `spec` shows Δ 0 and that is an artefact of the counting rule, not of the change.**
Steps 4 and 4.5 were three fenced commands *without* `!` prefixes, so ADR-011's rule
never counted them. They are now one `spec_machine check --all` call. **Two real turns
were removed and the ratchet is blind to all three.** The rule is a consistent proxy, not
a semantic count — that was stated when it was fixed, and here is the case that shows it.

**(b) The `research` fan-out does not render in this repo at all.** `targets` is
`[claude-code, cursor, codex]`; Cursor reads the Claude command file (`.cursor/commands/`
is dead code, `render.py:585-597`), so shipping an `Explore` dispatch here would emit an
agent Cursor cannot resolve. The gate is therefore `cursor not in targets`, which is
narrower than ADR-010's "Claude target only" — a harness that lists Cursor gets **no
fan-out**. Since `research` is 12.1% of measured wall-clock and was the second-largest
lever in the plan, this is the single biggest gap between what was designed and what this
repo will actually experience. It is implemented, tested on both arms, and dormant here.

**(c) Where the fan-out does render, ADR-011's rule counts it as +3 and it costs +1.**
Three `Task(` dispatches sent in one message are one main-loop turn. Under a claude-only
render `research` reads 8 → 11 by the rule and 8 → 9 in reality. The rule was not amended
to suit the phase — that is what ADR-011 forbids — and
`test_roundtrip_budget.py::test_the_fan_out_is_counted_as_three_though_it_costs_one_turn`
pins the discrepancy so it cannot be quietly forgotten.

## 3. Not measured — the four ADR-012 quantities

| Quantity | Pre-change | Post-change | `n` post | Status |
|---|---|---|---|---|
| main-loop turns / run | §2 of BASELINE | — | 0 | pending runs |
| subagent turns / run | 12.5% of spend, §3 of BASELINE | — | 0 | pending runs |
| active wall-clock / run | §2 of BASELINE | — | 0 | pending runs |
| mean context / carry | 70.0% carry, 87.9% main-loop share | — | 0 | pending runs |

**How to close this.** Run the pipeline normally. After **at least 3 runs per stage**
(fewer must be labelled, per ADR-012), re-run the same instrument:

```
uv run python -m harness_maker.economics composition --root .
```

and re-derive the per-stage table with BASELINE §2's methodology (300 s idle-gap cap,
`<command-name>`-delimited segments). Append the result to this file — do not start a
second receipt, or the comparison loses its pre-change anchor.

**The secondary expectations from BASELINE §5 that remain live:**

- `hm:wrapup` main-loop turns per run: expected to fall. Mandated calls fell 32 → 29 and
  the git tail is 6 → 3, so this is the strongest remaining prediction.
- `hm:execute`: expected to fall, driven by the Phase C per-file rule far more than by
  the −1 mandated call. `execute` is 22.3% of wall-clock at 288 turns/run; almost none of
  those are mandated calls.
- `hm:research`: **not evaluable in this repo** — see §2(b).
- Carry ratio: direction still not predicted.

## 4. Why Phase 1 was skipped — recorded so the decision is auditable

Presented to the user mid-execution with these measurements:

| Phase | Mandated calls removed | Wall-clock share of its stage | Implementation cost |
|---|---:|---|---|
| 1 — verify | **6** (largest) | verify does not appear in the wall-clock table at all | five checks that do not exist in `cli.py` today + five golden fixtures |
| 2 — wrapup | 3 | 14.0% | new module + 10-case matrix, risk `high` |
| 3 — spec | 0 by the rule, 2 real | 0.9% of turns | one subcommand |
| 4 — execute | 1 | **22.3%** | already written and measured |
| 5 — research | 0 (+3 by the rule) | 12.1% | prose + render tests |

Phase 1 ranks first on the ratchet's own metric and last on the metric the PLAN exists to
improve. The user chose 4 → 5 → 3 → 2 and dropped 1. The PLAN's ordering note already
established that reordering 1–5 is sound: their `merge_hazards` sets are identical, so
the serial constraint is unaffected.

## 5. Outstanding

- **Phase 1** (verify two-call composite) — not started. PR-1 stays un-evaluated until it
  is, or until the PLAN retires the prediction explicitly.
- **Phase 2 criterion (j)** — one real `/hm:wrapup` on a throwaway task branch,
  producing the receipt's per-path dispositions, the commit's file list, and a clean base
  afterwards. Unit-tested end to end; the manual run has not happened.
- Three `manual-only` P1 findings from `REVIEW-workflow-step-audit-2026-07-29.md`, all in
  the Phase 4 classifier, which still has no consumer other than the execute template.
