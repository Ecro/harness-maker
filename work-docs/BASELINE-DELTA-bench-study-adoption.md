# BASELINE-DELTA — bench-study-adoption

**Status: MEASURED.** It opened as a declaration — an authorization to grow while the work was
in flight — and the figures below are now the measured ones, which is what the fold uses. The
original prediction is kept beside the measurement rather than overwritten by it; the size of
the gap is the useful part.

**Owning phase: Phase 4 (the repo-access canary), with Phases 2 and 3 contributing.** The rule
this document exists to satisfy is `PLAN-surface-ratchet`'s **ADR-010** — a ratchet is never
rebaselined by its own subject, so growth is folded through an attribution document naming what
grew and why, never by regenerating `surface_baseline.json`. The failure class it names is
`ratchet-rebaselined-by-its-own-subject`: regenerating the baseline rewrites the frozen `chars`
in the same file, so the change that grew the surface also erases the record of what it grew
from — the ratchet stops being one, as a side effect of an edit that looks like bookkeeping.

Terminal plan-validation named the absence of this document as one of three live criticals:
`_ATOMIC_RATCHET["review"] = 67008` carries `measured * 1.02` ≈ 1340 characters of built-in
slack, and this PLAN's own estimate is ~1.2k of prose plus ~240 from appending
`--diff-files <path> --rev <sha>` to six literal command lines. Phases 2–4 would therefore have
blocked mid-flight on a red `test_atomic_commands_within_budget`, whose only escapes are bumping
the per-command ratchet (which this PLAN's Contract Boundaries forbid — a ratchet is never
rebaselined by its own subject) or improvising.

## What is being funded

| Phase | Command | What it adds | Declared |
|---|---|---|---|
| 2 | `review` | Auto-Fix Step 4 pointer to the skill's read-before-fix rule; one `authority` row in the Step 4e table; the `oracle-blocked` exclusion in Step 3's fixable-finding filter | ~700 |
| 3 | `review` | The `hm review_churn complexity` invocation and the `## 📏 Size & Complexity` report section, both Production-gated | ~600 |
| 4 | `review` | `repo_probe` transcription in Step 3, and `--diff-files <path> --rev <sha>` on six literal command lines across three logical sites (each rendered twice behind the `is_codex` fence) | ~900 |

`execute` is **not** expected to move. If it does, that is a finding, not a rounding error.

The rule body for Phase 2 goes into the `targeted-test-selection` skill, not the stage — skills
are not measured by either ratchet, and this is the same structure that on 2026-08-20 cut a
comparable change's stage cost from +900 to +512 characters while extending its reach.

## Round trips

**One per variant: `review: 1`, `hm-review: 1`.** The paragraph this replaces predicted none and
named its own exception — *"in particular if Phase 3's measurement needs its own `!` line rather
than riding the existing `review_churn pin` block"*. That is what happened, and the prediction is
recorded rather than quietly overwritten.

Step 5c could have been chained onto 5b's `pin && measure | tee` line at a cost of zero round
trips. It was **rejected** on those terms: 5b's churn measurement decides whether the round
re-reviews, and a record-only telemetry failure must not be able to take it down. Paying one
mandated call to keep the two independent is the trade, made deliberately.

Both variants are declared because the block renders on both branches of the `is_codex` fence.
Phase 4's `--diff-files`/`--rev` remain argument additions to invocations that already exist.

**Correction, worth keeping:** an intermediate check reported "round trips did not increase" after
running `test_command_size_budget` and `test_documented_commands_exist`. Neither counts round
trips. The counters are `test_roundtrip_budget.py` (a hand table, re-baselined in this phase's
commit with attribution) and `test_surface_baseline.py` (funded by the `round_trips` key above).
Running the wrong green tests is not evidence.

## Measured: 3817, against a declared 2600

**The estimate was 2.6x low.** The table above predicted ~2200 and the declaration carried 2600
with a deliberate margin; `test_aggregate_shipped_surface_does_not_grow` measured
**claude 430865 → 434675 (+3810)** and **codex 363775 → 367592 (+3817)**. The declaration is one number shared by both variants, so it is the larger: **3817**. The seven-character gap is the `is_codex` branches of the same blocks rendering slightly longer — a real difference, not rounding, and the reason a single-variant measurement would have under-funded this by exactly enough to fail.

Two causes, both worth keeping:

1. **The estimate predated the live review.** Round 1 of `/hm:review` found seven defects, and
   two of the repairs are prose in `review.md.j2` — chiefly the confirmation pass's
   re-derivation note, which exists because `probe_flags` is template-scope and all three sites
   were embedding round 1's stale diff list. A declaration written before a review cannot fund
   that review's repairs.

2. **The per-block estimates were short.** This is the larger half and has no interesting
   explanation: each landed block is simply longer than guessed. Recorded because "the estimate
   was low" is the useful fact, and dressing it as a surprise would not be.

The per-command ratchet passed throughout — `_ATOMIC_RATCHET["review"]`'s own 2% slack plus the
allowance covered it — so this was an aggregate-only overrun. Both are funded at 3817 now.

**What was NOT done:** prose was not trimmed to fit the old number. Every block added since the
estimate exists because a reviewer or the plan validator named its absence as a defect, and
cutting one to protect a declaration would trade a real finding for a tidy figure. The rule this
repo applies — cut before raising — is about prose that stopped earning its place; none of this
has.
