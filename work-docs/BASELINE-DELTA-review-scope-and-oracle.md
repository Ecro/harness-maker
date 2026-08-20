# BASELINE-DELTA — review scope follows causation, and the oracle follows the fix

**Date:** 2026-08-20 · **Owner:** the review-scope-and-oracle change (ADR-010's attribution document).

## What moved

| Key | Was | Now | Δ |
|---|---|---|---|
| `review` (claude) `chars` | 87 262 | **87 774** | +512 |
| `hm-review` (codex) `chars` | 82 573 | **83 085** | +512 |
| `execute` (claude) `chars` | 48 962 | **49 443** | +481 |
| `hm-execute` (codex) `chars` | 47 829 | **48 310** | +481 |
| `aggregate_chars.claude` | 429 872 | **430 865** | +993 |
| `aggregate_chars.codex` | 362 782 | **363 775** | +993 |
| `review` / `hm-review` `round_trips` | 38 / 33 | **38 / 33** | 0 |
| `execute` / `hm-execute` `round_trips` | 17 / 16 | **17 / 16** | 0 |
| `_ATOMIC_RATCHET["review"]` | 65 198 | **67 008** | +1 810 — only 512 of it is this change |
| `_ATOMIC_RATCHET["execute"]` | 47 718 | **48 199** | +481 |

`payload_digest` and `render_sha` moved too, mechanically: the digest hashes the measured surface
and the sha pins the commit frozen against. They are named here because the gate reading this
document treats an unmentioned changed key as an unexplained one.

**`render_sha` is `a5030534`, the parent of the commit carrying this change** — not the commit
itself, which cannot exist before the freeze. `assert_sha_is_durable` requires a base-reachable
SHA and `a5030534` is `main`'s tip at freeze time. The measured numbers come from the working
tree, which is what `test_round_trip_counts_match_the_live_render` compares against. The same
accepted artefact as the last two folds.

**Direction: LARGER**, +993 aggregate. No new round trips in either command.

## The review ratchet carries someone else's 1298

`_ATOMIC_RATCHET["review"]` read **65 198** while the flag-on fixture rendered **66 496**. The gate
never noticed: its ceiling is `measured * 1.02` = 66 501 — five characters of slack. The previous
fold recorded a figure taken before that task's last repair commit landed, exactly the half-done
fold the `execute` entry in that dict already describes.

Measured both ways rather than inferred: rendering the fixture with and without this change gives
66 496 → 67 008. **This change is +512.** The other +1298 is pre-existing unattributed drift being
written down for the first time. Rolling the two together would attribute another task's growth to
this one, which is the failure this document exists to prevent.

**`execute` was not tripping and is folded anyway** (+481, under the 2% slack). Leaving it there is
precisely how `review` accumulated 1298 characters nobody could attribute.

## The two rules, and why one implies the other

Both answer a single defect class, observed running this harness against a firmware experiment.
Three real defects were **triggered** inside the changed file and **caused** in files the diff
never touched — a ring-buffer time hole, front-swing key contamination, a 50 Hz sample-rate label.
All three sat in `sensor.c` / `power.c` while the change was in `swing_capture.c`.

**1. Diff scope becomes causation, not location (costs nothing here).** The reviewers' shared
`hard_rules` partial said: *do not flag pre-existing issues outside the changed lines unless the
change reveals them; if you do, mark `out_of_diff: true`*. Two problems. The clause reads as
location-first with a narrow exception, so a defect whose evidence is upstream is plausibly
suppressed — and the same agent body, twelve lines earlier, **instructs** the reviewer to *"walk
the runtime path the changed code triggers … Logic bugs hide where the patch doesn't touch."*
Reading there and not reporting there makes that walk pointless. The rewrite states the test as
reachability, says the **cause's** `file`/`line` goes in the finding because that is where the fix
goes, and suppresses only what the change is unrelated to.

`out_of_diff: true` is **removed rather than kept**. Nothing consumed it — no schema field, no
filter, no aggregation, in `src/`, `tests/` or any rendered harness. It was a marker the reviewers
were told to emit into a void.

This half is free against both ratchets: it lives in `agents/_partials/hard_rules.md.j2`, and
neither the atomic ceiling nor `surface_baseline.json` measures agent bodies. It is not free
everywhere — the five reviewer SHA pins in `test_agent_body_partials.py` moved, and so did eight
`synthesize` snapshots.

**2. The oracle follows the fix (+512 review, +481 execute).** This is the half that makes the
first one safe. Once findings point outside the diff, **fixes follow them there** — and
`targeted-test-selection` derives its targets from the **changed files** ("turning a set of changed
files into the tests that actually cover them", its own description). A fix that reaches a real
upstream symbol is then verified by a target that does not contain that symbol's module, and the
build breaks on a missing symbol rather than on anything wrong with the fix. Widening the reporting
rule without widening the oracle converts correct fixes into red builds by construction.

**The rule lives in the skill, not in a stage.** `targeted-test-selection` gains **§4.5**: a red
targeted run has three causes — production reaches the pinned state (fix the code) / it cannot
(name the caller-side fact; never edit the test) / the target is too narrow for the fix (widen and
re-run once) — and a build or link error is not a test failure and must not be logged as one. A
skill is loaded on demand and is measured by neither ratchet, so the rule itself costs nothing;
what the two commands pay for is a pointer and the parts that are genuinely theirs.

That placement was the second draft. The first put the whole rule inline in `review.md.j2` Step 5
and cost **+900**; moving it to the skill and keeping a pointer plus review's own two facts
(revert-either-way, and the per-cause log vocabulary) brought it to +512 **and** gave the same
rule to `/hm:execute` Phase D for one line there. Two sources of truth for one rule is what the
`consistency` lens is told to flag.

## `execute` had no counterpart to this question

`execute.md.j2` Phase D.5 asks what a repair **newly made reachable** — the right rule, kept. Its
inverse did not exist: `grep -in 'unreachable|test is wrong'` over that template returned **zero**.
So nothing asked whether a red light was about a reachable state in the first place. Phase D now
points at §4.5 for that, and names the D.5 relation so the two are not read as the same check.

## External confirmation of §4.5(c), and its limit

The oracle-widening rule was written from this repository's own reading. It has since been
observed independently, by an experiment that did not know the rule existed: a fix inserting
`power_sampling_active() && !power_resume_pending()` — a function that really is declared at
`power.h:44`, in a change that really did fix the 50 Hz mislabel — failed as
`undefined reference to 'power_sampling_active'` because the unit test linked only the module under
test. The same run recorded it as `n_failed = 0`: nothing ran, so an oracle reading failure counts
saw neither green nor red. That is the misclassification §4.5's build/link split exists to stop.

**Limit, stated because the observation is weaker than it looks:** it occurred once, at R1, and
propagated to later rounds — effectively **one independent observation**. It cannot support a claim
that the failure is common. The study reporting it also notes its adjudication was single-judge and
that its conclusions reversed seventeen times, always toward the less dramatic reading.

## What this does not fix

The reporting rule has no mechanical gate. Whether a reviewer actually reports an out-of-diff cause
is a judgment, and the only available evidence is a re-audit, not a counter. A text-presence test
would assert that the sentence exists, not that it is obeyed — the shape this repo has already
recorded as a defect elsewhere.

## Why only this document may move these numbers (ADR-010)

The ratchet's subject is the prompt surface and the failure mode is
`ratchet-rebaselined-by-its-own-subject`: the change that grows the surface also holds the pen, so
regenerating the baseline is always the cheapest way to green and erases the evidence in the same
stroke. This document is the price of the regeneration — and the 1298 above is what the evidence
looks like when the price is paid carelessly.
