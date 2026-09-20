---
type: mutation
task_slug: withdrawal-criterion-window
date: 2026-09-20
spec: "[[SPEC-withdrawal-criterion-window]]"
verification_tier: 3
subject: src/harness_maker/world.py
method: targeted (not mutmut whole-file — see "Why not mutmut")
mutants: 19
killed: 17
survived: 2
score: 89
summary: "89% on 19 targeted mutants of the lines this task authored; both survivors classified equivalent"
---

# Mutation measurement — withdrawal-criterion-window

## Result

| | |
|---|---|
| Mutants evaluated | 19 |
| Killed | 17 |
| Survived | 2 |
| Score | **89%** |
| Runner | `pytest tests/unit/test_world_withdrawal.py -p no:randomly -x` |
| Tier | 3 — informational, no gate (`mutation_threshold: null`) |

Source integrity was pinned by sha256 before and verified after every run; `world.py` is
byte-identical to its pre-run state.

## Why not mutmut

The SPEC's `paths_to_mutate` is `src/harness_maker/world.py`, which is **1911 lines**, of which
this task authored about eighty (lines 881–1045). Two things make a whole-file mutmut run
measure the wrong thing here:

1. **`hm spec_mutation gate --sampled` does not sample.** Its CLI help says "200-mutant sampled
   mode", but the flag appends `--use-coverage` (`spec_mutation.py:266`), which narrows by an
   existing coverage file. This repository has none, so mutmut exited immediately, produced no
   output, and the gate printed `T3 is informational (no gate)` with **`rc=0`** — a silent
   non-measurement that reads exactly like a pass. Filed for REVIEW.
2. **Without `--sampled` the run is capped at 600 s** (`min(wall_budget_min * 60, 600)`, with no
   flag on `gate` to raise it). mutmut walks the file in order at roughly 5 s per mutant, so the
   cap is exhausted around line 120 — it never reaches the changed region at all. The score
   would be a measurement of code this task did not touch.

So the mutants below are **authored against the changed lines**: each is a plausibly-wrong
implementation of something this task wrote. The harness is
`scratchpad/targeted_mutation.py` — it restores from a pristine copy before every mutant and
again in a `finally`, which matters (see "Incident" below).

## Mutants

| Mutant | Verdict |
|---|---|
| `quiet_wrapups >= WITHDRAWAL_WRAPUPS` → `>` | killed |
| `quiet_wrapups >= WITHDRAWAL_WRAPUPS` → `<=` | killed |
| `and candidates == 0` → `!= 0` (revisit veto inverted) | killed |
| `return quiet_wrapups is not None and` → `is None` (absent-case inverted) | killed |
| `best_ts is None or ts > best_ts` → `>=` (ties win) | **survived — equivalent** |
| `best_ts is None or ts > best_ts` → `<` (max becomes min) | killed |
| `or` → `and` in the max guard | killed |
| `if ts is not None` → `is None` (unparseable accepted) | killed |
| `return best` → `return None` | killed |
| drop the `approved_at` source | killed |
| drop the `closed_at` source | killed *(survived before the fix below)* |
| drop the `created_at` source | killed *(survived before the fix below)* |
| drop the `observed_at` source | killed |
| `if isinstance(approval, dict)` → `not isinstance` | killed |
| `if instant is None or instant <= now` → `<` | **survived — equivalent** |
| `if instant is None or instant <= now` → `>=` (clamp inverted) | killed |
| `_clamped(since, now)` → `since` (clamp removed) | killed |
| `since = signal or filled` → `filled or signal` | killed |
| `now = now or datetime.now(UTC)` → `datetime.now(UTC)` | killed |

## The two survivors, classified

**`max -> ties win` (`>` → `>=`) — equivalent for every consumer.** The two branches differ
only when two sources carry the *same instant*; `last_signal_at` returns the stored string, so
the returned spelling could differ (`…T00:00:00Z` vs `…T00:00:00+00:00`) while the instant does
not. `_count_wrapups` parses the string back to an instant, so `quiet_wrapups`, `due` and
`reason` are identical either way. Pinning a tie-break would specify an arbitrary choice; that
is over-specification, not coverage. **Accepted.**

**`clamp boundary <= -> <` — equivalent.** They differ only when `instant == now` exactly. At
that point `_clamped` returns either `since` or `now.strftime(...)`, two spellings of the same
instant, and `_count_wrapups` compares instants. No consumer can observe the difference.
**Accepted.**

## The two survivors that were real, and were fixed

The first run scored **77% (18 mutants, 4 survived)**. Two of those four were a genuine hole:
dropping the `created_at` source, or the `closed_at` source, **survived**.

The cause is this repository's most recurrent test defect,
`[fail:test] assertion-invariant-over-named-dimension` (count 16). AC-003 says `last_signal_at`
is "the maximum over the four timestamp sources", and the test was a single fixture in which
`approved_at` was the winner — so three of the four named sources were never bound, and a
reader that ignored them entirely passed. The name claimed a dimension the assertion did not
touch.

Fixed by parametrising the test over `winner ∈ (observed_at, created_at, approved_at,
closed_at)`: each source carries the maximum in turn while the other three stay behind it. Both
mutants now die. The second run is the 89% above.

**This is the value the measurement bought.** The four green gates — 9032-test suite, ruff,
mypy, and the renamed-only-control discrimination screen — all passed while that hole was open.
The screen in particular says "every `discriminates` test fails against the control", and the
single-winner AC-003 test did fail against it, because the control returns `last_signal_at:
None` unconditionally. Failing against *that* control says nothing about whether the test binds
all four sources.

## Incident: mutmut left the source mutated

While diagnosing (1) above, a direct `mutmut run` was cut off by its wall-clock timeout
(`rc=143`, SIGTERM). mutmut did not restore, and `world.py` was left carrying a live mutant:

```
-OBJECTIVE_STATES: tuple[str, ...] = ("proposed", "active", "closed", "dropped")
+OBJECTIVE_STATES: tuple[str, ...] = ("proposed", "active", "XXclosedXX", "dropped")
```

This is `[fail:tooling] mutation-gate-timeout-leaves-source-mutated-on-disk`, reproduced. It was
caught **only** because a sha256 of `world.py` was pinned before the run — and it mattered more
than usual here, because this task's changes to that file were uncommitted, so `git checkout`
would have destroyed them rather than restoring anything. The recovery was a one-line revert
plus a hash re-verification.

**Pin the subject's hash before any mutation run, and verify it after.** The tool's own cleanup
is not a guarantee, and on an uncommitted working tree git is not a fallback.
