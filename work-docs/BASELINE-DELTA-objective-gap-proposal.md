---
type: baseline-delta
task_slug: objective-gap-proposal
created: 2026-09-16
summary: "Pre-change pin for AC-007 (plan/review/help per arm + plan length), the inherited +67 fold that greens main, and the Phase 6 retirement of this task's own plan growth"
---

# BASELINE-DELTA — objective-gap-proposal

## 1. Pre-change pin (ADR-007) — captured before any source edit

Per-arm sha256 of the rendered `plan`, `review`, `help` commands and the rendered `plan` length,
computed in this worktree at base `main` (commit 2fd69df7) with the same recipe
`tests/structural/test_playbook_alignment_invariance._live_arms` uses (`_instruction_baseline.AXES`
+ `_render_atomic` for the `auto_safe@*` arms, `test_command_size_budget._render` for the
`ask@flag_*` arms). `tests/structural/test_objective_gap_proposal_invariance.py` parses the fenced
block below: review/help must stay byte-identical; plan may grow by at most the PLAN's
`surface_allowance.commands.plan` per arm (Phases 1–5) and is re-pinned at Phase 6.

> **Re-pinned at Phase 6 (retirement) and again after the review fix:** the `plan` hashes and
> `plan_len` below are the final render (+1 215 per arm over the pre-change values 52 973 /
> 54 377 / 65 221 / 55 900, section 3). From here the invariant is the same for all three commands: byte-identical
> to this pin, with zero allowance. `review`/`help` are the original pre-change values.

```json
{
 "arms": {
  "ask@flag_off": {
   "plan": "08a7e9793074a33ae22f65b347134112f3cb926a718f47f010a44e2c8c553f2c",
   "review": "0bdf6e287a23db5c89fe19bf372bbdaaa344bc1304c0bdb8d1d1abd8ea87cf51",
   "help": "0d1b6929d1b1bd55262d811ce71dfcce01a5eb0d68503ff1b19532effda415f7"
  },
  "ask@flag_on": {
   "plan": "f3e3f2a4c451bcd6e24e70dff551e78e43c3318ed5d9701647341fd045dbb0af",
   "review": "4a2bb22c66535fd481e699ada2122c9f4a6b89e38bc5542868d60cc6822a542d",
   "help": "0d1b6929d1b1bd55262d811ce71dfcce01a5eb0d68503ff1b19532effda415f7"
  },
  "auto_safe@spec-driven": {
   "plan": "f67a2231c896bb8e5cdc36b62fb7b875bf01931128f3c3ea71afc9a52f232d0b",
   "review": "8d25ba69e1dfc332e117f2fb487dbae8af8237b7540c2fded27ea947c513f27e",
   "help": "8b9d9aadf7b0ae5337cb12ca8e5343cc6efb3355b6f0196adc56f59a05a2af52"
  },
  "auto_safe@task-driven": {
   "plan": "7a7587853d74471463855637d31cd3884aa1503562fa635d3054b27124d02c92",
   "review": "8530386955e0a9cb25c83141c181d8b647271f67cadad7209716012edc81ef22",
   "help": "8b9d9aadf7b0ae5337cb12ca8e5343cc6efb3355b6f0196adc56f59a05a2af52"
  }
 },
 "plan_len": {
  "ask@flag_off": 54188,
  "ask@flag_on": 55592,
  "auto_safe@spec-driven": 66436,
  "auto_safe@task-driven": 57115
 },
 "harness_maker_version": "0.56.0"
}
```

## 2. Baselines re-frozen at main (2fd69df7) before this task's edit — the inherited fold (ADR-008)

`main` was red on `test_surface_baseline.py` and `test_aggregate_shipped_surface_does_not_grow`
when this task started: the previous task (`playbook-alignment`) landed, its wrapup set the PLAN
`status: complete`, its `surface_allowance` (`wrapup`/`hm-wrapup`: 67 chars) expired, and the
frozen figures still predated the +67. This is the documented fold `surface_allowance.py` asks
for at completion ("folded into the baseline once, with its BASELINE-DELTA attribution") and that
no stage performs — Phase 0 of this task performs it, from the **base checkout at main's render**
with `--out` into this worktree (base untouched):

| file | before | after |
|---|---|---|
| `surface_baseline.json` claude aggregate | 431 477 | 431 544 |
| `surface_baseline.json` codex aggregate | 366 499 | 366 566 |
| `wrapup` chars / round_trips | 47 889 / 28 | 47 956 / 28 |
| `hm-wrapup` chars / round_trips | 46 081 / 26 | 46 148 / 26 |
| `instruction_baseline.json` | 14 entries, 644 instructions (render 3edcca62) | 14 entries, 644 instructions (render 2fd69df7) |

### 2.1 Attribution of every moved key (ADR-010 of PLAN-workflow-step-audit — P7 owns the freeze)

The re-freeze moves the aggregate the **wrong way** for a diet: the shipped surface is
**larger** (claude 431 477 → 431 544, +67; codex 366 499 → 366 566, +67) and every byte of that
growth belongs to the landed `playbook-alignment` task (wrapup 5.7 `--claim` clause), whose
allowance was the attribution while it was in flight. Carrying that fold is the post-land routine,
not a `ratchet-rebaselined-by-its-own-subject` recurrence: the subject that grew has landed and no
longer edits these files; this task only carries the freeze so that main is green **before** it
adds anything of its own.

| key | before → after | owner / reason |
|---|---|---|
| `wrapup` chars | 47 889 → 47 956 (+67) | playbook-alignment wrapup 5.7: `--claim "<new claim>"` for the `supersedes` relation (its SPEC AC-007) |
| `hm-wrapup` chars | 46 081 → 46 148 (+67) | same, Codex arm |
| `aggregate_chars` | 431 477 / 366 499 → 431 544 / 366 566 | sum of the two rows above |
| `render_sha` | `3edcca62` → `2fd69df7d203` | the main commit the freeze was taken at |
| `payload_digest` | recomputed | mechanical — follows the surface map |
| `instruction_baseline.json` `commands.wrapup@spec-driven` / `commands.wrapup@task-driven` | 5.7 observe executable without `--claim` → with `[--claim …]` | same playbook-alignment line; the entry set stays 14 / 644 |

No peer PLAN with a live allowance was in flight on `main` at the time; this task's own
allowance (section 3) was declared in its PLAN before this freeze but covers `plan`/`hm-plan`
only, which section 2 does not touch.

## 3. Measured delta of this task (Phase 4) and its retirement (Phase 6)

Moved set per arm against the section 1 pin, verified before any re-capture: `{plan}` in all
four arms (`ask@flag_off`, `ask@flag_on`, `auto_safe@spec-driven`, `auto_safe@task-driven`),
identically in `auto_safe` and `ask`. `review` and `help` are byte-identical to the pin.

| command | chars (per arm) | round_trips |
|---|---|---|
| `plan` | +1 049 per arm (52 973 → 54 022 · 54 377 → 55 426 · 65 221 → 66 270 · 55 900 → 56 949) | +1 (the Step 4.9 call) |
| `hm-plan` | +1 049 | +1 |

What moved: Step 0.5 gained the one-line "Draft an objective for this task?" consent question
after "none", and a new `### Step 4.9 — Objective draft (consented at Step 0.5)` holds the
`objective new … --from-proposal --candidates 1` call after the interview, the refusal line and
the `proposed`/`not_active` note (SPEC S5 / AC-005, PLAN ADR-009).

**Allowance re-declared per ADR-005's over-budget branch.** The PLAN first declared
`surface_allowance.commands.plan/hm-plan: 700`; the first render measured +1 654, the prose was
compacted (Step 4.9 halved, the consent bullet to one line, the Step 5 comment trimmed) to
+1 049, and the remaining excess is real content — the id-derivation rule, the refusal branch
and the orphan story the plan-validator's C5/C9 required. The declaration is now `1100` with
`round_trips.plan/hm-plan: 1`. Re-captures that this delta caused, each recorded at its source:
`tests/structural/autopilot_gate_golden.json` (`plan` in all four arms; `rebases` entry +
docstring bullet in `test_autopilot_gate_render.py`), and the `plan` hashes in
`BASELINE-DELTA-playbook-alignment.md` §1 (note added there; its `review`/`help`/fixture pin is
untouched).

### 3.1 Retirement (Phase 6, ADR-008) — attribution of every moved key

The allowance block is deleted from `PLAN-objective-gap-proposal.md` and the own growth is
folded into both baselines from **this worktree's render** (the fold `surface_allowance.py`
asks for at completion). The aggregate moves the **wrong way** for a diet — the shipped surface
is **larger** (claude 431 544 → 432 759, +1 215; codex 366 566 → 367 788, +1 222) — and every
byte of it is this task's own Step 0.5/4.9 content (section 3: +1 049 at Phase 4, +166 from the
post-review fix of finding 0a2499c3 — the consent question now also fires on the filled-in,
zero-objective branch, re-folded the same way before wrapup). This is the subject folding its
own measured, allowance-declared growth at close-out, which ADR-010 of PLAN-workflow-step-audit
names as the legitimate re-freeze moment; it is not `ratchet-rebaselined-by-its-own-subject`,
because the growth was declared, measured against the section 1 pin, bounded by the re-declared
allowance and reviewed before the fold — the pattern that name warns about is a fold that
replaces the declaration.

| key | before → after | owner / reason |
|---|---|---|
| `plan` chars / round_trips | 65 221 / 28 → 66 436 / 29 | Phase 4: Step 0.5 consent question + Step 4.9 (`objective new … --from-proposal` call) |
| `hm-plan` chars / round_trips | 60 392 / 16 → 61 614 / 17 | same, Codex arm (+1 222: the `Bash("…")` call form is 7 chars longer) |
| `aggregate_chars` | 431 544 / 366 566 → 432 759 / 367 788 | sum of the two rows above |
| `render_sha` | `2fd69df7d203` (unchanged — the freeze is taken in the worktree at the same base commit) | — |
| `payload_digest` | recomputed | mechanical — follows the surface map |
| `instruction_baseline.json` | 14 entries, 644 → 648 instructions | Phase 4: the Step 4.9 call executable and the consent question, in both dev-mode arms |

`_ATOMIC_RATCHET['plan']` in `test_command_size_budget.py` is not moved: the rendered plan stays
inside its 2 % band. `review`, `help`, `wrapup` and the 77-cell boundary fixture are unchanged
(section 1 pin; AC-007). With the block deleted, `pytest tests/structural` runs with **zero**
in-flight allowances (AC-008) — the state main will be in after the land.
