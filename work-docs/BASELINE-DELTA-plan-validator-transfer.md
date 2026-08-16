# BASELINE-DELTA — the review loop's mechanisms, transferred to the plan stage

**Date:** 2026-08-16 · **Owner:** the plan-validator follow-up-round transfer (no PLAN document;
this is the attribution document ADR-010 requires).

## What moved

| Key | Was | Now | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 411 452 | **415 621** | +4 169 |
| `aggregate_chars.codex` | 339 400 | **343 593** | +4 193 |
| `plan` (claude) `chars` | 56 451 | **58 885** | +2 434 |
| `plan` (claude) `round_trips` | 14 | **18** | +4 |
| `hm-plan` (codex) `chars` | 49 790 | **52 252** | +2 462 |
| `hm-plan` (codex) `round_trips` | 13 | **17** | +4 |
| `review` (claude) `chars` | 81 190 | **82 086** | +896 |
| `hm-review` (codex) `chars` | 75 128 | **76 020** | +892 |
| `verify` (claude) `chars` | 21 323 | **22 036** | +713 |
| `hm-verify` (codex) `chars` | 18 713 | **19 426** | +713 |
| `wrapup` (claude) `chars` | 47 242 | **47 368** | +126 |
| `hm-wrapup` (codex) `chars` | 44 569 | **44 695** | +126 |

### The three groups of rows

**`plan`** is the transfer described above.

**`verify` and `wrapup`** are the cross-runtime test-execution recipe, and they add **no
round-trips**. `wrapup` gets it folded into an existing comment line rather than as a new
paragraph, because `test_the_default_render_costs_existing_users_nothing` budgets that command
in LINES and a three-line block broke it — the gate is right and the guidance fits on the line
that already tells the reader to pick a toolchain. `verify` owns the full version. Both say: ask
`hm test_runners plan` for THIS project's runner instead of pasting a parallel flag. The flag
is not portable advice. `cargo`, `go`, `vitest`, `jest` and `flutter` are **already parallel**,
where a worker flag caps or nests rather than accelerates; `pytest` is the one common runner
that is serial by default. The recipe also carries a worker count capped at about half the
visible cores — oversubscription makes a suite slower, and a runner whose workers each shell
out to `git` is running roughly twice the processes the core count suggests.

**`review`** is a separate fix that landed in the same commit. It adds **no round-trips**: three commands that took model-authored JSON through
`echo '<json>' | …` now take `--file <path>`. One apostrophe in a diff line used to end the
quoting and hand the rest of that line to the shell, and `churn_max_path` had just made a
FILENAME OUT OF THE DIFF part of that JSON. The characters are the two sentences saying why,
at each call site. Nothing else moved;
`payload_digest` and `render_sha` move mechanically with any render change and carry no
attribution of their own.

## Direction

**The shipped surface is LARGER.** This change removes interview rounds, not characters, and it
pays for that with prose. The cost it targets is the only unbounded one in the stage: the
validator passes are capped at two and that cap holds, while "run follow-up rounds for each
critical critique" has no bound at all. With five criticals where answering the first rewrites
half the PLAN, the stage used to spend five rounds; it now spends one.

Whether that trade pays is **not decidable from this document**, for the same reason it was not
decidable for the review loop: the mechanism that would measure it is the thing being shipped.

## Why the churn half is INVERTED, and why that is the whole point

In `/hm:review` a **low** churn ratio skips the re-review. Copying that shape here would read
"small edit → skip re-validation", which is precisely what this stage's own recorded measurement
refutes: twelve `plan-validator` episodes, **none ever reached a clean verdict**, and one PLAN
records outright that pass 2's three criticals were *created by the pass-1 fixes*. A small
revision is not evidence that a revision is safe.

What transfers is the other direction. Once a revision has rewritten **more than half** the PLAN,
the critiques still sitting in the queue were raised against a document that no longer exists.
They go `stale` and buy no round — and nothing is lost, because Step 4.5's terminal pass is
mandatory and re-derives whichever of them still hold.

The threshold is 0.50, not the review gate's 0.20, and the difference is deliberate: there the
ratio decides whether to *look* at a repair, here it decides whether to *drop* a question the
validator already asked. The bar to discard is the higher one.

## What did NOT transfer

The **lens axis**. `plan-validator` is a single agent, not a fan-out; there is nothing to
diversify and no coverage gate to compute.

## Why only this document may move these numbers (ADR-010)

The ratchet's subject is the prompt surface, and the failure mode is
`ratchet-rebaselined-by-its-own-subject`: the task that grows the surface is also the task
holding the pen, so "regenerate the baseline" is always the cheapest way to go green and it
erases the evidence in the same stroke. This row is the price of the regeneration.
