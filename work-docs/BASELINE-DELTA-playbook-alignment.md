---
type: baseline-delta
task_slug: playbook-alignment
created: 2026-09-16
summary: "Pre-change pin for AC-005 (plan/review/help per arm + boundary fixture) and the wrapup surface numbers the 5.7 line will move"
---

# BASELINE-DELTA — playbook-alignment

## 1. Pre-change pin (ADR-010) — captured before any source edit

Per-arm sha256 of the rendered `plan`, `review`, `help` commands, copied from
`tests/structural/autopilot_gate_golden.json` at base `main` (commit 3edcca62), plus the sha256 of
the 77-cell boundary fixture `tests/fixtures/autopilot_caps_baseline.json`. `golden_wrapup_sha` is
the pre-change `wrapup` hash per arm, kept so Phase 4's verify-before-recapture can name the moved
set. `tests/structural/test_playbook_alignment_invariance.py` parses the fenced block below.

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
 "boundary_baseline_sha256": "efba6d171c056ddb75ff156ac82aa9fd8164ea1657f0e50717f3b92dfa0c6594",
 "golden_wrapup_sha": {
  "ask@flag_off": "cab8bd7f2bc9e529c4c593a0a76ddbc4bd792d5ca34bbdd7a613fbaef954b353",
  "ask@flag_on": "1348f8b9d087803596ff3175df8db5681300d5a251c24c8de693f43e232405f6",
  "auto_safe@spec-driven": "ba49690a7f78296b8f55b4852bfb4de74a921c21aefefaff2c3f4107be62f584",
  "auto_safe@task-driven": "56566955888ea04a52f462a1a617d5ccd8028ead477af1dccc20a1f2954c1404"
 },
 "harness_maker_version": "0.56.0"
}
```

> **Re-pinned 2026-09-16 by `objective-gap-proposal` (its PLAN ADR-005, Phase 4):** the `plan` hashes in the fence above were re-taken after that task's Step 0.5/4.9 edit (+1 049 chars per arm, attributed in `BASELINE-DELTA-objective-gap-proposal.md` §3). `review`, `help` and the boundary fixture are the original pin — this document still proves playbook-alignment left them alone.

Recompute: `uv run python -c "import json,hashlib,pathlib; …"` over the golden's `arms` and the
fixture bytes — Phase 0's exit criterion.

## 2. Baselines re-frozen at main (3edcca62) before this task's edit

`main` was already red on `test_surface_baseline.py` when this task started: the previous task
(`intent-world-model-objective-layer`) landed, its PLAN went `status: complete`, its
`surface_allowance` expired, and the frozen figures still predated it (claude 427 369 vs live
431 477; `plan`/`review`/`wrapup` round trips +2/+1/+2). Per the repo's post-land routine
(commit 9ea26255, "re-freeze both baselines, peer allowance now expired") both freezers were run
**from the base checkout at main's render** with `--out` into this worktree — base untouched:

| file | before | after |
|---|---|---|
| `surface_baseline.json` claude aggregate | 427 369 | 431 477 |
| `surface_baseline.json` codex aggregate | 362 326 | 366 499 |
| `wrapup` chars / round_trips | 46 531 / 26 | 47 889 / 28 |
| `hm-wrapup` chars / round_trips | 44 703 / 24 | 46 081 / 26 |
| `instruction_baseline.json` | 14 entries | 14 entries, 644 instructions |

### 2.1 Attribution of every moved key (ADR-010 of PLAN-workflow-step-audit — P7 owns the freeze)

The re-freeze moves the aggregate in the **wrong way** for a diet: the shipped surface is
**larger** (claude 427 369 → 431 477, +4 108; codex 362 326 → 366 499, +4 173) and every byte of
that growth belongs to the landed `intent-world-model-objective-layer` task, whose allowance was
the attribution while it was in flight. Re-freezing is the documented post-land routine, not a
`ratchet-rebaselined-by-its-own-subject` recurrence: the subject that grew (that task) has landed
and no longer edits these files; this task only carries the freeze.

| key | before → after | owner / reason |
|---|---|---|
| `plan` chars / round_trips | 63 813 / 26 → 65 221 / 28 | intent layer Step 0.5 (objective context: status load + revisit loop) |
| `hm-plan` chars / round_trips | 58 967 / 14 → 60 392 / 16 | same, Codex arm |
| `review` chars / round_trips | 85 923 / 33 → 87 153 / 34 | intent layer Step 3.3 (objective drift, one `objective show` call) + the review-fix id charset sentence |
| `hm-review` chars / round_trips | 82 319 / 28 → 83 556 / 29 | same, Codex arm |
| `wrapup` chars / round_trips | 46 531 / 26 → 47 889 / 28 | intent layer 5.7 (two answer-gated questions) |
| `hm-wrapup` chars / round_trips | 44 703 / 24 → 46 081 / 26 | same, Codex arm |
| `help` chars | 1 883 → 1 995 | intent layer: the `intent-layer` skill row |
| `hm-help` chars | 2 110 → 2 243 | same, Codex arm |
| `aggregate_chars` | 427 369 / 362 326 → 431 477 / 366 499 | sum of the rows above |
| `render_sha` | previous freeze → `3edcca62d640` | the main commit the freeze was taken at |
| `payload_digest` | recomputed | mechanical — follows the surface map |

The "after" figures are those in `tests/structural/surface_baseline.json` at this commit. `instruction_baseline.json` was re-frozen from the same render (14 entries,
644 instructions).

No peer PLAN with a live allowance was in flight on `main` at the time (the only in-flight
PLAN is this one, which declared its allowance after this freeze — section 3).

## 3. Measured delta of this task (Phase 4, after the freeze above)

Moved set per arm against the pre-change golden, verified before re-capture: `{wrapup}` in all
four arms (`ask@flag_off`, `ask@flag_on`, `auto_safe@spec-driven`, `auto_safe@task-driven`).

| command | chars | round_trips |
|---|---|---|
| `wrapup` | 47 889 → 47 956 (+67) | 28 → 28 |
| `hm-wrapup` | 46 081 → 46 148 (+67) | 26 → 26 |

Declared in `PLAN-playbook-alignment.md` frontmatter as `surface_allowance: {chars: 67,
commands: {wrapup: 67, hm-wrapup: 67}}`, no `round_trips` (the clause sits on the existing call
line). `plan`, `review`, `help` and the 77-cell boundary fixture are unchanged (section 1 pin).
