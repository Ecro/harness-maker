---
type: baseline-delta
task_slug: validator-pass-cap-telemetry
created: 2026-08-07
owns: [surface_baseline.json]
summary: "Baseline movement from the validator pass-cap / ledger-coherence fixes"
---

# Baseline delta — validator-pass-cap-telemetry

Baseline ownership follows **ADR-010**: one phase owns the ratchet, and a phase that
re-baselines the guard it tripped is `ratchet-rebaselined-by-its-own-subject` (count:2).
This document is this task's own attribution — it does not amend the previous task's.

Follow-up to `PLAN-workflow-loop-efficiency`, opened because the ledger that plan shipped
found three defects in its own first six rows.

## 1. Aggregate

| | Before | After | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 362 419 | 364 738 | **+2 319** |
| `aggregate_chars.codex` | 295 582 | 297 901 | **+2 319** |

> **Corrected four times.** The first version read `361 396` / `295 916` with deltas `+1 797` /
> `+440` — figures copied from the *previous* task's end state, two baseline generations
> stale. The second and third were each correct when written and went stale inside the same
> round, because each review round edited the templates again. The gate caught both. The
> lesson is ordering, not care: figures must be written AFTER the final regeneration, and
> any round that touches a template invalidates them again. It then explained the resulting asymmetry with a story about
> the guidance rendering into both `commands/hm/plan.md` and `stages/plan.md`. **The
> asymmetry did not exist**: the real delta is `+774` on both variants, so the explanation
> was explaining a copy error. An attribution document reporting the wrong movement, with a
> fabricated cause, is the precise failure this document exists to prevent — and the gate
> could not catch it, because it only checked the *After* figure.

**Direction: the shipped surface got LARGER, again.** +2 319 on both variants — `+774`
from the original commit and the rest from two review rounds' fixes (the shell-quoting
rules, the corrected terminal-scope invariant, and the `coherence` pointer), on top of the
+7 113 the parent PLAN added. Every change in this thread has moved the same way, because
detection and instrumentation are both prose. The running total is only repaid if stage 2
reads these ledgers and deletes something; until then the honest description of this work is
that it buys the ability to decide, and charges prompt size for it.

The added text is the F-C block — the pass cap, the one-terminal-row-per-run invariant, and
what to do when a pass exceeds the cap.

## 2. Attribution

| Key | Cause |
|---|---|
| `execute`, `hm-execute` (i.e. `surface.claude.execute`, `surface.codex.hm-execute`) | **F9 (review round)** — the Phase A.5 emit line had the same unquoted `--slug {slug}` / `--run-id <run-id>` sink as `plan`, so the fix had to close both. Quoting every model-substituted placeholder, plus the same single-quote-and-strip rule for the free-text `--reason`. |
| `plan`, `hm-plan` (i.e. `surface.claude.plan`, `surface.codex.hm-plan`) | **F-C** — the emit guidance now states the 2-pass cap, requires exactly one `--terminal` row per run, and requires a `--reason` on any over-cap pass. `--pass <1\|2>` became `--pass <N>`: the placeholder was encoding a rule that nothing enforced. |
| `render_sha`, `payload_digest` | mechanical |

### Movements a CONCURRENT task caused, swept in by this regeneration

| Keys | Cause |
|---|---|
| `research`, `review`, `spec`, `verify`, `wrapup` and their codex twins `hm-research`, `hm-review`, `hm-spec`, `hm-verify`, `hm-wrapup` | **Not this task.** `f53dd3a5` (a concurrent session, landed while this work was in flight) edited `src/harness_maker/templates/agents/_partials/step_manifest.md.j2` — a partial every stage includes — so all ten commands moved. That commit did not regenerate the baseline; this task's regeneration is what brings it in line. |

Attributed rather than absorbed, for the same reason as the `configure` row below: an
unexplained movement in an attribution document is the silent rebaseline `ADR-010` exists to
prevent, and "another task did it" is an explanation, not an excuse to stay silent. It is
also the second time in this one task that a regeneration swept in someone else's
un-regenerated change — which suggests the real gap is that landing a template edit does not
require regenerating, not that any individual author forgot.

### `_ATOMIC_RATCHET` (test source, not `surface_baseline.json`)

| Key | From | To | Cause |
|---|---|---|---|
| `plan` | 46 008 | 47 503 | The same F-C + review-round text as the `plan` row above. The ceiling is `measured × 1.02`, so raising it re-arms the guard at the new level rather than disabling it; the floor (`× 0.80`) rises with it, so a future phase that *deletes* this guidance will trip the floor and have to say so. |

Not covered by `test_baseline_delta_attribution` — that gate reads `surface_baseline.json`
only, and this table lives in test source. Recorded here anyway: an unattributed ratchet
raise is the thing ADR-010 exists to prevent, and "the gate did not ask" is not a reason to
stay silent.

### One movement this task did NOT cause

`surface.claude.configure.round_trips` went **3 → 4** with `chars` unchanged at 10 746.
Nothing here touches `configure`. Identical text with a different call count means the
committed baseline was **already stale** for that command — an earlier task changed it and
did not regenerate — and this task's regeneration swept the correction in.

The first version of this document asserted "No round-trip count changed", which was false
and would have left an unexplained movement attributed to nobody. That is exactly the silent
rebaseline `ADR-010` and `ratchet-rebaselined-by-its-own-subject` (count:2) describe, so it
is named here rather than absorbed. The rows this task did cause (`plan`, `hm-plan`) held
their round-trip counts: the F-C block adds rules to follow, not calls to make.

## 3. What the first six ledger rows found

The instrumentation's first real use surfaced three defects, one of them in the
pre-registration itself.

**F-A — the pre-registered aggregation was blind to the event that happened.** The validator
rule read `pass_or_attempt == 2`. Run `msms-20260807-1` had a **third** pass — three genuine
dispatches 15.1 and 4.9 minutes apart, not a mislabeled row — and the equality dropped it.
Since passes 1 and 2 had already agreed, pass 3 was the only place the verdict could have
disagreed: the metric was structurally blind to its own most informative case.

Amended to `>= 2`, **with the amendment recorded next to the rule** rather than left to a
diff. The justification is correctness alone: the equality discarded real observations, so it did
not measure the question it was registered to answer. **A "conservative direction" argument
originally stood here and was false** — the admitted row was already known to agree, so
0/2 → 0/3 *strengthens* the deletion case rather than raising its bar. Widening only raises
the bar when the added rows are numerator-eligible in expectation, which inspection had
already excluded. The protection is the disclosure, not a directional defence.

**F-B — two `terminal` rows in one run, undetectable by design.** `StageAgentRow`'s
validator sees one row; every defect of this kind is a relationship *between* rows, so it
cannot be closed at the schema. `check_run_coherence()` closes it where rows are read, and
flags the real run on sight. It also catches duplicate and non-contiguous pass numbers, a terminal
row that is not the last, and unreadable rows.

**Sentinels COUNT as attempts, and the first version had this exactly backwards.** It
excluded them, reasoning that counting a failed dispatch as a pass "would put a false gap on
every run whose validator did not launch". The opposite is true: a launch failure occupies
attempt 1, so *excluding* it is what leaves the retry sitting at `(2,)` — a gap. Worse, the
schema was simultaneously forcing every sentinel to `terminal=True`, so the retry shape the
guidance mandates recorded two terminal rows. The checker was reporting incoherence the
schema manufactured. Both halves are inverted now, and a missing terminal row is reported as
`incomplete` rather than as a defect — an in-flight run legitimately has none, and with many
concurrent sessions a gate that fires almost always is a gate that gets ignored.

**F-C — the cap existed only as a placeholder.** `--pass <1|2>` encoded it and nothing
enforced it. The guidance now states it, and requires an over-cap pass to be **recorded with
a reason** rather than dropped: without the reason the ledger cannot separate "the operator
asked for another pass" from "the stage overran its own limit", and those have opposite
remedies. An unrecorded pass is worse still — a serial barrier the latency figures charge to
nobody.

## 4. The gate caught its own scoping bug

`test_baseline_delta_attribution.py` pinned `BASELINE-DELTA-P7.md`, a **per-task** artifact.
This task moved the baseline and the gate demanded the new figure appear in the *previous*
task's document — a wrong instruction of exactly the kind people comply with. It now scans
every `work-docs/BASELINE-DELTA-*.md`, so each task writes its own and a stale one cannot
satisfy it by accident (the aggregate is an exact figure that moves with every change).

Worth noting what worked: this was found by the gate firing on the first subsequent task,
not by review. The failure it was strengthened to catch one day earlier — asserting a
hardcoded figure *appears* rather than *matches* — is the same family, and both were caught
because the check reads the baseline instead of trusting the prose.
