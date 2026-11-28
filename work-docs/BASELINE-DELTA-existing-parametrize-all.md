---
type: baseline-delta
task_slug: existing-parametrize-all
created: 2026-11-28
owns: [surface_baseline]
summary: "SPEC-existing-parametrize-all's shipped-surface growth: one clause in /hm:execute Phase A"
---

# Baseline delta — PLAN-existing-parametrize-all

The shipped surface **grew** by 99 chars in `execute` (claude) and `hm-execute` (codex): ". Cases for a call a test there already parametrizes go into its list, one per line, not a new test.". t7-1's counterfactual confirmed the cause. A mechanical AC's raising cases became a new test that copied `test_invalid`, because the paste rule covered only golden rows. The clause is the rule itself, so it cannot be paid for elsewhere without cutting another rule.

Measured with `tests/fixtures/cli_bookkeeping/main_chars.json` renders against the frozen baseline (964fbf730cbd).

| variant | command | delta (chars) | cause |
|---|---|---|---|
| claude | `execute` | +99 | every AC's cases join an existing parametrize |
| codex | `hm-execute` | +99 | same text |

Per ADR-010 the task that moved the surface owns its attribution. Writing it next to the
allowance and the later re-freeze keeps this out of `ratchet-rebaselined-by-its-own-subject`.
