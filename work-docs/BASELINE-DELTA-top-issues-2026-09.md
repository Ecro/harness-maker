---
type: baseline-delta
task_slug: top-issues-2026-09
created: 2026-09-30
summary: "review +1 call (caused_by stamp); verify/wrapup −1 call each (one self-marking run verb); aggregate smaller"
---

# BASELINE-DELTA — top-issues-2026-09

This document covers the re-freeze of `tests/structural/surface_baseline.json` and of the
`review` / `verify` / `wrapup` entries in `tests/structural/test_roundtrip_budget.py`. Both
re-freezes land in the same change as the template edits that caused them.

Attribution follows **ADR-010**. Every key whose value moved has a row below naming the command
that owns it.

**Precondition.** No peer PLAN held a live `surface_allowance` when this re-freeze ran. This
task's own PLAN declares none: the aggregate went down, so it needed no headroom.

## Why this document exists, and who may write it

A re-freeze is a change measuring itself, which makes it a case of
**`ratchet-rebaselined-by-its-own-subject`**. The generator re-renders the templates this task
edited and records whatever it finds, so a green baseline after a re-freeze says nothing about
whether the edit was intended.

This document is what makes the re-freeze safe. It depends on two rules:

- The phase that moved a key re-freezes it, in the same commit.
- Every moved key has a row naming its owning command.

`test_every_changed_key_has_an_attribution_row` enforces the second rule against the actual
diff of the baseline.

## What moved

| File | Key | Before | After | Delta |
|---|---|---|---|---|
| `surface_baseline.json` | `surface.claude.review.chars` | 88 249 | 88 574 | **+325** |
| `surface_baseline.json` | `surface.claude.review.round_trips` | 34 | 35 | **+1** |
| `surface_baseline.json` | `surface.claude.verify.chars` | 27 781 | 27 427 | **−354** |
| `surface_baseline.json` | `surface.claude.verify.round_trips` | 14 | 13 | **−1** |
| `surface_baseline.json` | `surface.claude.wrapup.chars` | 56 497 | 56 288 | **−209** |
| `surface_baseline.json` | `surface.claude.wrapup.round_trips` | 34 | 33 | **−1** |
| `surface_baseline.json` | `surface.codex.hm-review.*` | chars 87 812, rt 30 | chars 88 140, rt 31 | +328 chars, +1 rt |
| `surface_baseline.json` | `surface.codex.hm-verify.*` | chars 27 505, rt 13 | chars 27 085, rt 12 | -420 chars, -1 rt |
| `surface_baseline.json` | `surface.codex.hm-wrapup.*` | chars 57 040, rt 34 | chars 56 765, rt 33 | -275 chars, -1 rt |
| `surface_baseline.json` | `aggregate_chars.claude` | 357 790 | 357 552 | **−238** |
| `surface_baseline.json` | `aggregate_chars.codex` | 312 039 | 311 672 | **−367** |
| `surface_baseline.json` | `payload_digest` | `21b81d38…` | `6b1204db…` | rewritten |
| `surface_baseline.json` | `render_sha` | `e5851a67…` | `3b718d91…` | re-pinned |
| `test_roundtrip_budget.py` | `review` / `verify` / `wrapup` | 34 / 14 / 34 | 35 / 13 / 33 | +1 / −1 / −1 |

The aggregate is **smaller**. The shipped surface fell by 238 characters (claude) and
367 characters (codex), even though `review` gained a call.

## Per-key attribution

- **`review` / `hm-review`.** Step 3.4 now runs `hm review_churn attribute` on the merged temp
  file before `persist-payload`. `caused_by` used to be "determined" in prose after the payload
  was already persisted, and 621 of 621 persisted findings carried none. The auto-fix step 1
  and the iteration-record example now read the stamp (`caused_by=fix-r1` instead of `#7`).
  Net effect: +1 round trip, and characters kept down by trimming the new prose.
- **`verify` / `hm-verify`.** Check 2's three steps were `verification_cache check`, then
  `verification_plan commands`, then a self-attested `mark-pass`. They are now one
  `verification_cache run`, which runs the CI gates and writes the marker itself. `mark-pass`
  survives only inside `<!-- @hm:verify-degraded -->`. Net −1 round trip, fewer characters.
- **`wrapup` / `hm-wrapup`.** Step 2 got the same change as `verify`.
- **`aggregate_chars`.** The sum of the three rows above in each variant. Nothing else moved:
  the autopilot golden re-capture showed only these three commands moving, in all four arms.
- **`payload_digest` and `render_sha`.** Both are mechanical. The generator rewrites the digest,
  and `render_sha` is the base commit it ran against.
