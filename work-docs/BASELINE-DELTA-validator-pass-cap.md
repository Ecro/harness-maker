---
type: baseline-delta
task_slug: validator-pass-cap-telemetry
created: 2026-08-07
owns: [surface_baseline.json]
summary: "Baseline movement from the validator pass-cap / ledger-coherence fixes"
---

# Baseline delta — validator-pass-cap-telemetry

Follow-up to `PLAN-workflow-loop-efficiency`, opened because the ledger that plan shipped
found three defects in its own first six rows.

## 1. Aggregate

| | Before | After | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 361 396 | 363 193 | **+1 797** |
| `aggregate_chars.codex` | 295 916 | 296 356 | +440 |

Smaller than it looks: the claude figure includes the same guidance rendered into both
`commands/hm/plan.md` and `stages/plan.md`. The added text is the F-C block — the pass cap,
the one-terminal-row-per-run invariant, and what to do when a pass exceeds the cap.

## 2. Attribution

| Key | Cause |
|---|---|
| `surface.claude.plan`, `surface.codex.hm-plan` | **F-C** — the emit guidance now states the 2-pass cap, requires exactly one `--terminal` row per run, and requires a `--reason` on any over-cap pass. `--pass <1\|2>` became `--pass <N>`: the placeholder was encoding a rule that nothing enforced. |
| `render_sha`, `payload_digest` | mechanical |

No round-trip count changed: nothing was added that the model must *call*, only rules it
must follow.

## 3. What the first six ledger rows found

The instrumentation's first real use surfaced three defects, one of them in the
pre-registration itself.

**F-A — the pre-registered aggregation was blind to the event that happened.** The validator
rule read `pass_or_attempt == 2`. Run `msms-20260807-1` had a **third** pass — three genuine
dispatches 15.1 and 4.9 minutes apart, not a mislabeled row — and the equality dropped it.
Since passes 1 and 2 had already agreed, pass 3 was the only place the verdict could have
disagreed: the metric was structurally blind to its own most informative case.

Amended to `>= 2`, **with the amendment recorded next to the rule** rather than left to a
diff. Two things make it auditable: the direction is conservative (a larger denominator
makes "the later pass never changes the verdict" *harder* to show, raising the bar for the
deletion this metric feeds), and the disclosure states it was made after seeing the pass-3
row, with the figures unchanged in conclusion (0/2 old rule, 0/3 new).

**F-B — two `terminal` rows in one run, undetectable by design.** `StageAgentRow`'s
validator sees one row; every defect of this kind is a relationship *between* rows, so it
cannot be closed at the schema. `check_run_coherence()` closes it where rows are read, and
flags the real run on sight. It also catches missing terminals, duplicate and non-contiguous
pass numbers, and excludes sentinel rows from the sequence — counting a failed dispatch as a
pass would put a false gap on every run whose validator did not launch.

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
