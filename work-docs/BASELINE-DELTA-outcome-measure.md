---
type: baseline-delta
task_slug: outcome-measure
created: 2026-09-17
summary: "Pre-change pin for AC-008 (plan/review/help/wrapup per arm + wrapup length), no inherited fold, and the Phase 5 retirement of this task's own wrapup growth"
---

# BASELINE-DELTA — outcome-measure

## 1. Pre-change pin (ADR-007) — captured before any source edit

Per-arm sha256 of the rendered `plan`, `review`, `help` and `wrapup` commands and the rendered
`wrapup` length, computed in this worktree at base `main` (commit 6ef0bcf9) with the recipe
`tests/structural/test_objective_gap_proposal_invariance._live_arms` uses (`_instruction_baseline.AXES`
+ `_render_atomic` for the `auto_safe@*` arms, `test_command_size_budget._render` for the
`ask@flag_*` arms), extended with `wrapup`. `tests/structural/test_outcome_measure_invariance.py`
parses the fenced block below: plan/review/help must stay byte-identical; wrapup may grow by at
most the PLAN's `surface_allowance.commands.wrapup` per arm (Phases 3–4) and is re-pinned at
Phase 5.

> **Re-pinned at Phase 5 (retirement):** the `wrapup` hashes and `wrapup_len` below are the final
> render (+601 per arm over the pre-change values 39 372 / 44 721 / 47 956 / 49 510, section 3).
> From here the invariant is the same for all four commands: byte-identical to this pin, with
> zero allowance. `plan`/`review`/`help` are the original pre-change values.

```json
{
 "arms": {
  "auto_safe@warn": {
   "plan": "7a7587853d74471463855637d31cd3884aa1503562fa635d3054b27124d02c92",
   "review": "8530386955e0a9cb25c83141c181d8b647271f67cadad7209716012edc81ef22",
   "help": "8b9d9aadf7b0ae5337cb12ca8e5343cc6efb3355b6f0196adc56f59a05a2af52",
   "wrapup": "1eca66e4e2c5ed6aa5041f1683907c48ed739db8cfc36c8236169304fe686d93"
  },
  "auto_safe@block": {
   "plan": "f67a2231c896bb8e5cdc36b62fb7b875bf01931128f3c3ea71afc9a52f232d0b",
   "review": "8d25ba69e1dfc332e117f2fb487dbae8af8237b7540c2fded27ea947c513f27e",
   "help": "8b9d9aadf7b0ae5337cb12ca8e5343cc6efb3355b6f0196adc56f59a05a2af52",
   "wrapup": "bcb05a2a66b1840ee514e26f312db973f56b1102c2347ccb6a89dd5b7cc62236"
  },
  "ask@flag_on": {
   "plan": "f3e3f2a4c451bcd6e24e70dff551e78e43c3318ed5d9701647341fd045dbb0af",
   "review": "4a2bb22c66535fd481e699ada2122c9f4a6b89e38bc5542868d60cc6822a542d",
   "help": "0d1b6929d1b1bd55262d811ce71dfcce01a5eb0d68503ff1b19532effda415f7",
   "wrapup": "34193626f00fb321714dec9c2e34f2b58299c6125668ae20d3083082d9e85561"
  },
  "ask@flag_off": {
   "plan": "08a7e9793074a33ae22f65b347134112f3cb926a718f47f010a44e2c8c553f2c",
   "review": "0bdf6e287a23db5c89fe19bf372bbdaaa344bc1304c0bdb8d1d1abd8ea87cf51",
   "help": "0d1b6929d1b1bd55262d811ce71dfcce01a5eb0d68503ff1b19532effda415f7",
   "wrapup": "56014ec6491330fbc30926fc579dd944a51c25bc7ebfb8532b79dd17e9972ac7"
  }
 },
 "wrapup_len": {
  "auto_safe@warn": 50111,
  "auto_safe@block": 48557,
  "ask@flag_on": 45322,
  "ask@flag_off": 39973
 },
 "harness_maker_version": "0.56.0"
}
```

## 2. No inherited fold

`main` (6ef0bcf9) was green on `test_surface_baseline.py`, `test_command_size_budget.py` and
`test_baseline_delta_attribution.py` when this task started: the previous task
(`objective-gap-proposal`) retired its own allowance in its Phase 6 and re-froze both baselines
before landing, so there is no expired allowance to fold here. Section 3 is the only movement
this task makes.

## 3. Measured delta of this task (Phase 3) and its retirement (Phase 5)

Moved set per arm against the section 1 pin, verified before any re-capture: `{wrapup}` in all
four arms (`ask@flag_off`, `ask@flag_on`, `auto_safe@block`, `auto_safe@warn`),
identically in `auto_safe` and `ask`. `plan`, `review` and `help` are byte-identical to the pin.

| command | chars (per arm) | round_trips |
|---|---|---|
| `wrapup` | +601 per arm (49 510 → 50 111 · 47 956 → 48 557 · 44 721 → 45 322 · 39 372 → 39 973) | +1 (the `outcome measure --all` call) |
| `hm-wrapup` | +611 (46 148 → 46 759, Codex arm) | +1 |

What moved: 5.7's heading now says **three questions**, and a third answer-gated block
`<!-- @hm:answer-gated:outcome-measure -->` sits after `objective-close`: it fires only when
`hm world gap --json` lists an outcome with `measure: true`, asks **"Measure outcomes now?"**
with each measurable outcome's `last` value and `observed_at` age, and on "yes" runs
`hm world outcome measure --all` once; otherwise it writes nothing (SPEC S7 / AC-007, PLAN
ADR-006). The skill's "measure first" step also changed, but skills are outside the command
surface. Declared as `surface_allowance{chars: 1300, commands.wrapup/hm-wrapup: 650,
round_trips.wrapup/hm-wrapup: 1}` in the same change as the call. Re-captures this delta
caused, each recorded at its source: `tests/structural/autopilot_gate_golden.json` (`wrapup` in
all four arms; `rebases` entry + docstring bullet in `test_autopilot_gate_render.py`),
`_CLAUDE_ROUND_TRIPS["wrapup"]` 28 → 29 in `test_roundtrip_budget.py`, the eight
`tests/snapshot/*.expected.yaml` (regenerated in this worktree), and the earlier prior-task
block-count pin in `test_render_intent_layer.test_ac_007_wrapup_supersedes_carries_claim`
(2 → 3 answer-gated blocks), and the wrapup body-line pins in
`test_render_wrapup_delegation.test_the_default_render_costs_existing_users_nothing`
(Side 702 → 709, Production 735 → 742: the block is 7 body lines).

### 3.1 Retirement (Phase 5, ADR-007) — attribution of every moved key

The allowance block is deleted from `PLAN-outcome-measure.md` and the own growth is folded into
both baselines from **this worktree's render** (the fold `surface_allowance.py` asks for at
completion). The aggregate moves the **wrong way** for a diet — the shipped surface is
**larger** (claude 432 759 → 433 360, +601; codex 367 788 → 368 399, +611) — and every byte
of it is this task's own wrapup 5.7 content (section 3). This is the subject folding its own
measured, allowance-declared growth at close-out, which ADR-010 of PLAN-workflow-step-audit
names as the legitimate re-freeze moment; it is not `ratchet-rebaselined-by-its-own-subject`,
because the growth was declared, measured against the section 1 pin, bounded by the allowance
and reviewed before the fold — the pattern that name warns about is a fold that replaces the
declaration.

| key | before → after | owner / reason |
|---|---|---|
| `wrapup` chars / round_trips | 47 956 / 28 → 48 557 / 29 (+601, +1) | outcome-measure wrapup 5.7: third answer-gated block `outcome-measure` ("Measure outcomes now?", one `hm world outcome measure --all` call) + "three questions" heading (SPEC S7 / AC-007, ADR-006) |
| `hm-wrapup` chars / round_trips | 46 148 / 26 → 46 759 / 27 (+611, +1) | same, Codex arm (`Bash("…")` form is 10 chars longer) |
| `aggregate_chars` | 432 759 / 367 788 → 433 360 / 368 399 | sum of the two rows above |
| `plan` / `hm-plan` chars and round_trips | unchanged by this task (52 973+1 215 … / 61 614 / 17 as landed) | **not this task's**: `test_baseline_delta_attribution` compares against the merge-base with `origin/main` (2fd69df7), and `objective-gap-proposal` (landed 6ef0bcf9, not yet pushed) moved these; they are attributed in `BASELINE-DELTA-objective-gap-proposal.md` §3.1 and listed here only so the whole branch delta has a row |
| `render_sha` | `6ef0bcf9` (unchanged base) | the freeze was taken in this worktree at base 6ef0bcf9; the landed squash commit will carry it forward |
| `payload_digest` | recomputed | mechanical — follows the surface map |
| `instruction_baseline.json` `commands.wrapup@spec-driven` / `commands.wrapup@task-driven` | 644 → 650 instructions: heading `5.7 … three questions` replaces `… two questions` (allowlisted in `test_instruction_preservation._ALLOWED_REMOVALS["outcome-measure"]`), plus the new `!… hm world outcome measure --all` executable in each arm | same outcome-measure line; the entry set stays 14 |

`_ATOMIC_RATCHET["wrapup"]` (44 654) is not moved: the atomic `ask@flag_off` render grew
39 372 → 39 973 and stays inside the ceiling. `_CLAUDE_ROUND_TRIPS["wrapup"]` moved 28 → 29 at
Phase 3 with the call (section 3). No peer PLAN with a live allowance was in flight on `main`
at the time.
