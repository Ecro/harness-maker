---
type: baseline-delta
task_slug: mission-context-loop
created: 2026-09-19
summary: "Pre-change pin (plan/review sha, wrapup/help length per arm), no inherited fold, and the Phase 5 retirement of this task's wrapup + help growth"
---

# BASELINE-DELTA — mission-context-loop

## 1. Pre-change pin (ADR-006) — captured before any source edit

Per-arm sha256 of the rendered `plan`, `review`, `help` and `wrapup` commands, plus the rendered
`wrapup` and `help` lengths. It was computed in this worktree at commit dfc9d37c (base `main`
555ca933) with the recipe of `tests/structural/test_outcome_measure_invariance._live_arms`:
`_instruction_baseline.AXES` + `_render_atomic` for the `auto_safe@*` arms, and
`test_command_size_budget._render` for the `ask@flag_*` arms.

`tests/structural/test_mission_context_loop_invariance.py` parses the fenced block below:
- `plan` and `review` must stay byte-identical;
- `wrapup` and `help` may grow by at most the PLAN's `surface_allowance.commands.{wrapup,help}`
  per arm while it is declared, and are re-pinned at Phase 5.

> **Re-pinned at Phase 5 (retirement):** the `wrapup` and `help` hashes and lengths below are
> the final render (after the review and verify fixes): wrapup +975 in every arm, help +159 (ask arms) / +102 (auto_safe arms) over
> the pre-change values (section 3). `plan` and `review` are the original pre-change values and
> did not move. From here all four commands are byte-identical to this pin, with zero allowance.

> **Re-pinned again at wrapup (rebase onto `e5eea25f`, observed-harness-gaps-salvage landed):**
> that task moved `plan`, `review` and `wrapup` (+1054 in every arm, the Steps 6 → 7.6
> proposal-backlog paragraph) on `main` first. Every hash and length below is the rebased final
> render. Relative to the landed golden, only `wrapup` and `help` moved, by exactly this task's
> section 3 deltas — the two tasks' wrapup edits are disjoint, so the deltas add.

```json
{
 "arms": {
  "ask@flag_off": {
   "help": "c11ca6d31b3d91905ece35c118854e8591ce676d541ef0f14fcddbd7d5bb362d",
   "plan": "81dc8c79079a62b8db32166407a2076c5219585899b6ccf6d3242e0a48cc0322",
   "review": "b5b33953cc7253db83d5409e7337ea3ef164282002667c479499c243750301b7",
   "wrapup": "17d132df404482e987e47489e44a9f047c777c269481550ad418490831bbfd13"
  },
  "ask@flag_on": {
   "help": "c11ca6d31b3d91905ece35c118854e8591ce676d541ef0f14fcddbd7d5bb362d",
   "plan": "69da1e3c7309bf833ba2217a0a7b6bbd99d514de9199460aba0a6d7ac8b5af8d",
   "review": "487f9494974bb2484c4a63f5214db68d3105b31e0f66cb825225b4cd7b054b91",
   "wrapup": "37ebf84119fee30eaea9420d4a8978ea19039e45dc9fa1b4c9ffcb921c2bc68f"
  },
  "auto_safe@block": {
   "help": "51af72e02aeeb566b28994279a1d771a69a71df892d8efe08b47d39954c256c9",
   "plan": "4df698bdecbb917cc5192f1e421b79cee7647351464a8adcb9ee510711746131",
   "review": "4a6bf81db83003f7a5b9362b9842ad01372c3d93bbd399dfd6df8ac28d83ac53",
   "wrapup": "934fdc25a5edd2d2dd0d4e6369e0940e919c40027be760da1fc8f61612af6e7c"
  },
  "auto_safe@warn": {
   "help": "51af72e02aeeb566b28994279a1d771a69a71df892d8efe08b47d39954c256c9",
   "plan": "e879ede63d1b4e4b83f971f826256d81d6b45791fb6fe50fe47e9d597fe17284",
   "review": "4497f48460432496f9234ce4632f2e179d4bfb0e757fcad9d17edae9c9c747c2",
   "wrapup": "4b8216c5426fed138b7a4b92c3511e8cfee42e0a41153da33fbdfb7f132c818d"
  }
 },
 "harness_maker_version": "0.57.1",
 "help_len": {
  "ask@flag_off": 2439,
  "ask@flag_on": 2439,
  "auto_safe@block": 2097,
  "auto_safe@warn": 2097
 },
 "wrapup_len": {
  "ask@flag_off": 43039,
  "ask@flag_on": 48388,
  "auto_safe@block": 51623,
  "auto_safe@warn": 53177
 }
}
```

## 2. Inherited fold

None. `tests/structural/test_surface_baseline.py` and `tests/structural/test_command_size_budget.py`
were green at the pin (32 passed): the previous task (`assumption-entry-and-evidence-locator`)
retired its allowance before landing.

## 3. This task's growth (Phase 4, declared with the edit)

Two commands moved, in both variants:
- **wrapup 5.1** gained the 5.1.0 fact-safe search-before-write blockquote, with one
  `hm memory_retrieve` call in each `is_codex` branch. Its slug bullet now names the reused
  non-fact slug.
- **help** gained the `project-knowledge` skill row, with the Codex `@project-knowledge`
  mention note.

Measured against the frozen baseline from a fresh render:

| command | before → after | delta |
|---|---|---|
| claude `wrapup` | 49 594 → 50 569 | +975; round trips 30 → 31 (includes the review fixes below) |
| codex `hm-wrapup` | 47 806 → 48 786 | +980; round trips 28 → 29 |
| claude `help` | 1 995 → 2 097 | +102 |
| codex `hm-help` | 2 243 → 2 371 | +128 |

No other command moved.

**Review fix (2026-09-19, Codex P1 `19b3f7f1f0100b4f`):** wrapup 5.1.0 gained the exact-slug
Grep check (+187 per variant, zero new calls: the Grep tool is not a counted round trip). The
re-review then made that check state the base path — two levels above `<WT>` — for another +73
per variant (P1 `92cde7ba0790a79f`). `/hm:verify` then dropped the `<WT>` token from that
note (it leaked into the worktree-OFF render, caught by `test_worktree_surface_gating`), for −10
per variant. All three are folded into the same re-freeze below. The new `project-knowledge` skill, the six always-loaded pointers and
the wiki templates are NOT on the measured surface (`render_surface` covers
`.claude/commands/hm/*.md` and `.agents/skills/hm-*/SKILL.md` only). Their budgets are:
- SPEC AC-005's ≤300-character pointer cap: rendered en 259 / codex 224 / ko 182;
- context-lint's 300-line skill limit: the skill is 53 lines.

**Declared** in `PLAN-mission-context-loop.md` as `surface_allowance{chars: 858, commands{wrapup:
725, help: 159}, round_trips{wrapup: 1, hm-wrapup: 1}}` in the same change as the template edit.

**Moved with it:**
- `_CLAUDE_ROUND_TRIPS["wrapup"]` 30 → 31 (`test_roundtrip_budget.py`); 31 → 32 after the rebase;
- the `autopilot_gate_golden.json` re-capture (help and wrapup are the only moved commands in
  all four arms; `rebases` entry);
- `_ATOMIC_RATCHET["wrapup"]` 45646 → 47084 (`test_command_size_budget.py`, the 2 % band was
  crossed); 47413 → 48388 after the rebase;
- the wrapup body-line pins Side 713 → 729, Production 746 → 762
  (`test_render_wrapup_delegation.py`); 751 / 784 after the rebase (+22 theirs, +16 ours);
- the eight snapshot hashes;
- the new `project-knowledge` row in `work-docs/MATRIX-native-redundancy.md`.

### 3.1 Retirement (Phase 5, ADR-006) — attribution of every moved key

The allowance block is deleted from `PLAN-mission-context-loop.md`. The task's own growth is
folded into the baseline from **this worktree's render**, on base 555ca933: the task branch
carries only documentation commits, so `render_sha` records the base commit the diff renders
on. That is the same meaning as the previous freezes.

The aggregate moves **larger**:
- claude 434 397 → 435 474 (+1 077); rebased at wrapup: 436 655 → 437 732 (+1 077);
- codex 369 446 → 370 554 (+1 108); rebased at wrapup: 371 718 → 372 826 (+1 108).

Every byte of it is this task's own wrapup and help content (section 3). This is the subject
folding its own measured, allowance-declared growth at close-out (ADR-010 of
PLAN-workflow-step-audit names this as the legitimate re-freeze moment). It is not
`ratchet-rebaselined-by-its-own-subject`, because the growth was declared, measured against the
section 1 pin and bounded by the allowance before the fold.

| key | before → after | owner / reason |
|---|---|---|
| `wrapup` chars / round_trips | 49 594 / 30 → 50 569 / 31 (+975, +1); rebased 50 648 / 31 → 51 623 / 32 | mission-context-loop wrapup 5.1.0: fact-safe search-before-write, one `hm memory_retrieve` call (SPEC S6 / AC-006, ADR-007) |
| `hm-wrapup` chars / round_trips | 47 806 / 28 → 48 786 / 29 (+980, +1); rebased 48 867 / 29 → 49 847 / 30 | same, Codex arm (`Bash("…")` form) |
| `help` chars | 1 995 → 2 097 (+102) | mission-context-loop `/hm:help` `project-knowledge` row (ADR-006, validator C11) |
| `hm-help` chars | 2 243 → 2 371 (+128) | same, Codex arm with the `@project-knowledge` mention note |
| `aggregate_chars` | 434 397 / 369 446 → 435 474 / 370 554; rebased 436 655 / 371 718 → 437 732 / 372 826 | sum of the four rows above |
| `render_sha` | `b48bcec4` → `555ca933` → `e5eea25f` | the freeze was taken in this worktree at base 555ca933 (assumption-entry-and-evidence-locator landed), then re-taken at wrapup after rebasing onto e5eea25f (observed-harness-gaps-salvage landed) |
| `payload_digest` | recomputed | mechanical — follows the surface map |
