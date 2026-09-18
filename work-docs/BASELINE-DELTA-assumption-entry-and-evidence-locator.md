---
type: baseline-delta
task_slug: assumption-entry-and-evidence-locator
created: 2026-09-18
summary: "Pre-change pin for AC-012 (plan/review/help/wrapup per arm + wrapup length), no inherited fold, and the Phase 5 retirement of this task's own wrapup growth"
---

# BASELINE-DELTA — assumption-entry-and-evidence-locator

## 1. Pre-change pin (ADR-006) — captured before any source edit

Per-arm sha256 of the rendered `plan`, `review`, `help` and `wrapup` commands and the rendered
`wrapup` length, computed in this worktree at base `main` (commit 43c7ded0) with the recipe
`tests/structural/test_outcome_measure_invariance._live_arms` uses (`_instruction_baseline.AXES`
+ `_render_atomic` for the `auto_safe@*` arms, `test_command_size_budget._render` for the
`ask@flag_*` arms). `tests/structural/test_assumption_entry_invariance.py` parses the fenced block
below: plan/review/help must stay byte-identical; wrapup may grow by at most the PLAN's
`surface_allowance.commands.wrapup` per arm while it is declared, and is re-pinned at Phase 5.

> **Re-pinned at Phase 5 (retirement):** the `wrapup` hashes and `wrapup_len` below are the final
> render after rebasing onto `intent-layer-ops` (b48bcec4) and the post-review fix: +713 per arm
> over that base's values
> 40 297 / 45 646 / 48 881 / 50 435 (section 3). The section-1 pre-change values were taken at
> 43c7ded0; `intent-layer-ops` added +324 to wrapup in between (its own delta doc), and
> `plan`/`review`/`help` did not move.
> From here the invariant is the same for all four commands: byte-identical to this pin, with
> zero allowance. `plan`/`review`/`help` are the original pre-change values.

```json
{
 "arms": {
  "ask@flag_off": {
   "help": "793c64f69bb8ce3170035c12599ea369c4558ccd5d5481f4141b4ec9e347e28c",
   "plan": "81dc8c79079a62b8db32166407a2076c5219585899b6ccf6d3242e0a48cc0322",
   "review": "d0f28ab123c64513e9e4c18c8baf62935d133b5441900d3cd27f13e719de1c3d",
   "wrapup": "704edf6154505421dbe3d9c120b8e23ce64e9200113d193c5ffe48e3f0370e24"
  },
  "ask@flag_on": {
   "help": "793c64f69bb8ce3170035c12599ea369c4558ccd5d5481f4141b4ec9e347e28c",
   "plan": "69da1e3c7309bf833ba2217a0a7b6bbd99d514de9199460aba0a6d7ac8b5af8d",
   "review": "1aaedd851167c589cd9ccf3218015f1a8104e1a8ec05967555c86d9791bb6f69",
   "wrapup": "3cf04bb5e5ae46785d5cd5db2f1985ecb92684ac28ff5deee37a9d90648552ba"
  },
  "auto_safe@spec-driven": {
   "help": "4983a54b81ac0de0489b07c281091e37dd9551cc3d38deffa56392b1c23e9e21",
   "plan": "bec83e17fcba482b2d46d15df70ad29caa3189f414264406ce76dfc6c1c6a5c2",
   "review": "3463592060b67803ffd4ec8b4e5e5208af9af5871cd78726fa233ecb6b30f8e5",
   "wrapup": "fb5f5a25db8e0e82827b39164c64f1ee5f827c7175a04456867c5d717f8d205c"
  },
  "auto_safe@task-driven": {
   "help": "4983a54b81ac0de0489b07c281091e37dd9551cc3d38deffa56392b1c23e9e21",
   "plan": "f8a86fbb23fcd4ef739a26a4ce7155316f213a76ec687550cf4f7fe3cdb19524",
   "review": "66f5301260799c8339b25b2093edd5f503d40a8c7898ea5e648d2cc04225eb9e",
   "wrapup": "0a546efd9c1d915a2d1552d4fbb687eda0e5184c85d1a83001eacdcefc9e368c"
  }
 },
 "harness_maker_version": "0.57.1",
 "wrapup_len": {
  "ask@flag_off": 41010,
  "ask@flag_on": 46359,
  "auto_safe@spec-driven": 49594,
  "auto_safe@task-driven": 51148
 }
}
```

## 2. Inherited state

`tests/structural/test_surface_baseline.py`, `test_command_size_budget.py` and
`test_roundtrip_budget.py` ran green in this worktree before any edit (54 passed). No inherited
fold: the previous task retired its own allowance.

## 3. This task's growth (Phase 4, declared with the edit)

Wrapup 5.7's assumption block (both `is_codex` branches) gained: the four-option cap with at most
two ids read from `hm world gap --json`'s `assumptions`, stale ones first and labelled
"(cited code changed)"; the "new — record an assumption" option with ONE `hm world assume add`
call; and `[--locator <path:A-B>]` on the existing observe line. Measured against the frozen
baseline from a fresh render: claude `wrapup` 48 557 → 49 105 (+548, round trips 29 → 30), codex
`hm-wrapup` 46 759 → 47 314 (+555, round trips 27 → 28); no other command moved. After rebasing
onto `intent-layer-ops` (b48bcec4, which added +324 / +324 to the same two commands with zero
calls) the same delta reads claude 48 881 → 49 429 and codex 47 083 → 47 638. The post-review
fix (the "new" branch shows the exact `add` arguments and asks once more — codex dbc13952) adds
+165 / +168 on the same line (no new line, no new call): final claude 48 881 → 49 594 (+713),
codex 47 083 → 47 806 (+723). The
`intent-layer` skill (+2 verb forms, +2 prose lines) is not on the measured surface.

Declared in `PLAN-assumption-entry-and-evidence-locator.md` as `surface_allowance{chars: 555,
commands{wrapup: 548, hm-wrapup: 555}, round_trips{wrapup: 1, hm-wrapup: 1}}` in the same change
as the template edit. Moved with it: `_CLAUDE_ROUND_TRIPS["wrapup"]` 29 → 30
(`test_roundtrip_budget.py`), the wrapup body-line pins (Side 709 → 711, Production 742 → 744,
`test_render_wrapup_delegation.py`), the `autopilot_gate_golden.json` re-capture (wrapup the only
moved command in all four arms; `rebases` entry), an `_ALLOWED_REMOVALS` entry for the pre-change
observe line (`test_instruction_preservation.py`), and the eight snapshot hashes (wrapup command,
wrapup stage, intent-layer skill).

### 3.1 Retirement (Phase 5, ADR-006) — attribution of every moved key

The allowance block is deleted from `PLAN-assumption-entry-and-evidence-locator.md` and the own
growth is folded into both baselines from **this worktree's render** at base b48bcec4 (after
rebasing onto `intent-layer-ops`, including the post-review fix). The aggregate moves **larger** —
claude 433 684 → 434 397 (+713), codex 368 723 → 369 446 (+723) —
and every byte of it is this task's own wrapup 5.7 content (section 3). This is the subject
folding its own measured, allowance-declared growth at close-out (ADR-010 of
PLAN-workflow-step-audit names this as the legitimate re-freeze moment); it is not
`ratchet-rebaselined-by-its-own-subject`, because the growth was declared, measured against the
section 1 pin and bounded by the allowance before the fold.

| key | before → after | owner / reason |
|---|---|---|
| `wrapup` chars / round_trips | 48 881 / 29 → 49 594 / 30 (+713, +1) | assumption-entry-and-evidence-locator wrapup 5.7: "new — record an assumption" + one `hm world assume add` call, four-option cap from `gap`, `--locator` on observe (SPEC S8 / AC-010, ADR-005) |
| `hm-wrapup` chars / round_trips | 47 083 / 27 → 47 806 / 28 (+723, +1) | same, Codex arm (`Bash("…")` form) |
| `aggregate_chars` | 433 684 / 368 723 → 434 397 / 369 446 | sum of the two rows above |
| `render_sha` | `b48bcec4` (intent-layer-ops) → `b48bcec4` | the freeze was taken in this worktree at base b48bcec4 |
| `payload_digest` | recomputed | mechanical — follows the surface map |
| `instruction_baseline.json` `commands.wrapup@spec-driven` / `commands.wrapup@task-driven` | 650 → 652 instructions: the observe executable with `[--locator <path:A-B>]` replaces the pre-change one (allowlisted in `test_instruction_preservation._ALLOWED_REMOVALS["assumption-entry-and-evidence-locator"]`), plus the new `!… hm world assume add` executable in each arm | same assumption-entry-and-evidence-locator 5.7 edit |

`_ATOMIC_RATCHET["wrapup"]` (45 646, re-based by `intent-layer-ops`) is **not moved**: the
`ask@flag_on` render it measures grew 45 646 → 46 359 (+713), inside its 2 % ceiling (46 558).
(Before the rebase this task had moved it 44 654 → 45 870, because at that base outcome-measure's
un-rebased +601 left no room; `intent-layer-ops` re-based it first, so that edit was dropped in
the rebase. An earlier draft of this section also misread the `ask@flag_off` figure.)
