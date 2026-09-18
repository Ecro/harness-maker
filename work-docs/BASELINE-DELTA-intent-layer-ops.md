---
type: baseline-delta
task_slug: intent-layer-ops
created: 2026-09-18
summary: "Pre-change pin for AC-006 (plan/review/help/wrapup per arm + wrapup length), no inherited fold, and the Phase 4 retirement of this task's wrapup growth"
---

# BASELINE-DELTA — intent-layer-ops

## 1. Pre-change pin (ADR-005) — captured before any source edit

Per-arm sha256 of the rendered `plan`, `review`, `help` and `wrapup` commands and the rendered
`wrapup` length, computed in this worktree at base `main` (commit 43c7ded0) with
`tests/structural/test_outcome_measure_invariance._live_arms` (`_instruction_baseline.AXES` +
`_render_atomic` for the `auto_safe@*` arms, `test_command_size_budget._render` for the
`ask@flag_*` arms). `tests/structural/test_intent_layer_ops_invariance.py` parses the fenced block
below: plan/review/help must stay byte-identical; wrapup may grow by at most the PLAN's
`surface_allowance.commands.wrapup` per arm (Phase 3) and is re-pinned at Phase 4.

> **Re-pinned at Phase 4 (retirement):** the `wrapup` hashes and `wrapup_len` below are the final
> render (+324 per arm over the pre-change values 50 111 / 48 557 / 45 322 / 39 973, section 3).
> From here all four commands are byte-identical to this pin with zero allowance. `plan`/`review`/`help`
> are the original pre-change values.

```json
{
 "arms": {
  "auto_safe@task-driven": {
   "help": "4983a54b81ac0de0489b07c281091e37dd9551cc3d38deffa56392b1c23e9e21",
   "plan": "f8a86fbb23fcd4ef739a26a4ce7155316f213a76ec687550cf4f7fe3cdb19524",
   "review": "66f5301260799c8339b25b2093edd5f503d40a8c7898ea5e648d2cc04225eb9e",
   "wrapup": "8d69b92a2cb3b88216c67017b0753fbd94f8ec891801f40dd9b21effcf8baa8b"
  },
  "auto_safe@spec-driven": {
   "help": "4983a54b81ac0de0489b07c281091e37dd9551cc3d38deffa56392b1c23e9e21",
   "plan": "bec83e17fcba482b2d46d15df70ad29caa3189f414264406ce76dfc6c1c6a5c2",
   "review": "3463592060b67803ffd4ec8b4e5e5208af9af5871cd78726fa233ecb6b30f8e5",
   "wrapup": "17935e049d397566210e2d15d9b360d04694c2d0d8c5c487b006f2cf0f62daef"
  },
  "ask@flag_on": {
   "help": "793c64f69bb8ce3170035c12599ea369c4558ccd5d5481f4141b4ec9e347e28c",
   "plan": "69da1e3c7309bf833ba2217a0a7b6bbd99d514de9199460aba0a6d7ac8b5af8d",
   "review": "1aaedd851167c589cd9ccf3218015f1a8104e1a8ec05967555c86d9791bb6f69",
   "wrapup": "2df2b3e66dbe68a7954c244751e8df06967b85bdc8fd2777dd454ab307de98f7"
  },
  "ask@flag_off": {
   "help": "793c64f69bb8ce3170035c12599ea369c4558ccd5d5481f4141b4ec9e347e28c",
   "plan": "81dc8c79079a62b8db32166407a2076c5219585899b6ccf6d3242e0a48cc0322",
   "review": "d0f28ab123c64513e9e4c18c8baf62935d133b5441900d3cd27f13e719de1c3d",
   "wrapup": "7cca43bea23c5ab3a1a05938ac55f4d889e5e11348938fdc6b45299fd84b97d8"
  }
 },
 "wrapup_len": {
  "auto_safe@task-driven": 50435,
  "auto_safe@spec-driven": 48881,
  "ask@flag_on": 45646,
  "ask@flag_off": 40297
 },
 "harness_maker_version": "0.57.1"
}
```

## 2. No inherited fold

`main` (43c7ded0) was green on `test_surface_baseline.py` and `test_command_size_budget.py`
(32 passed) when this task started, so there is no expired allowance to fold.

## 3. Measured delta of this task (Phase 3) and its retirement (Phase 4)

Moved set per arm against the section 1 pin, verified before any re-capture: `{wrapup}` in all
four arms (`ask@flag_off`, `ask@flag_on`, `auto_safe@spec-driven`, `auto_safe@task-driven`),
identically in `auto_safe` and `ask`. `plan`, `review` and `help` are byte-identical to the pin.

| command | chars (per arm) | round_trips |
|---|---|---|
| `wrapup` | +324 per arm (50 111 → 50 435 · 48 557 → 48 881 · 45 322 → 45 646 · 39 973 → 40 297) | 0 (no new call) |
| `hm-wrapup` | +324 (46 759 → 47 083, Codex arm) | 0 |

What moved: after the `outcome-measure` answer-gated block, 5.7 gained one sentence — when the
`hm world gap --json` output of that check reports `withdrawal.due: true`, print once
`[intent] withdrawal criterion met — …`; otherwise nothing (SPEC S5 / AC-005, PLAN ADR-005). It
reads output the step already obtains, so no round trip is added. Declared as
`surface_allowance{chars: 324, commands.wrapup/hm-wrapup: 324}` in the same change. Re-captures
this delta caused, each recorded at its source: `tests/structural/autopilot_gate_golden.json`
(`wrapup` in all four arms; `rebases` entry + docstring bullet in `test_autopilot_gate_render.py`).
The eight `tests/snapshot/*.expected.yaml` (regenerated in this worktree; only the two wrapup
entries' `body_sha256` moved in each) and the wrapup body-line pins in
`test_render_wrapup_delegation.test_the_default_render_costs_existing_users_nothing`
(Side 709 → 711, Production 742 → 744: the sentence and its blank line). The Phase D targeted
selection missed both — the full suite caught them (`[fail:process]
targeted-phase-d-subset-missed-the-snapshot-test`, recurring).

### 3.1 Retirement (Phase 4, ADR-005) — attribution of every moved key

The allowance block is deleted from `PLAN-intent-layer-ops.md` and the own growth is folded into
the baselines from **this worktree's render** (the fold `surface_allowance.py` asks for at
completion). The aggregate moves the **wrong way** for a diet — the shipped surface is
**larger** (claude 433 360 → 433 684, +324; codex 368 399 → 368 723, +324) — and every byte of it
is this task's own wrapup 5.7 sentence (section 3). This is the subject folding its own measured,
allowance-declared growth at close-out, which ADR-010 of PLAN-workflow-step-audit names as the
legitimate re-freeze moment; it is not `ratchet-rebaselined-by-its-own-subject`, because the
growth was declared, measured against the section 1 pin, bounded by the allowance and verified
before the fold.

| key | before → after | owner / reason |
|---|---|---|
| `wrapup` chars / round_trips | 48 557 / 29 → 48 881 / 29 (+324, +0) | intent-layer-ops wrapup 5.7: one sentence surfacing `withdrawal.due` (SPEC S5 / AC-005, ADR-005) |
| `hm-wrapup` chars / round_trips | 46 759 / 27 → 47 083 / 27 (+324, +0) | same, Codex arm |
| `aggregate_chars` | 433 360 / 368 399 → 433 684 / 368 723 | sum of the two rows above |
| `render_sha` | `6ef0bcf9` → `43c7ded0` | the freeze was taken in this worktree at base 43c7ded0 (main after source-plan-steps landed) |
| `payload_digest` | recomputed | mechanical — follows the surface map |
| `_ATOMIC_RATCHET["wrapup"]` | 44 654 → 45 646 | outside the 2 % band: the atomic `ask@flag_on` render is 45 322 + 324; re-based to the landed figure with an attribution comment in `test_command_size_budget.py` |

`instruction_baseline.json` does not move: the sentence adds no heading and no `!`-line. No peer
PLAN with a live allowance was in flight on `main` at the time.
