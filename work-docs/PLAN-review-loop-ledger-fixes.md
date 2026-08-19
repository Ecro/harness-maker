---
type: plan
task_slug: review-loop-ledger-fixes
status: planning
created: 2026-08-19
tags: [harness-maker, plan, review-stage, telemetry, auto-fix-loop]
summary: "Give the disposition gate a measurement surface; stop diagnosing over-specified tests as regressions; take P2 out of the fixer's queue."
surface_allowance:
  chars: 1909
  reason: "MEASURED after the trim, not before. Three rules added to steps that already run — hence round_trips 37/33 unchanged. The first draft measured 2516/variant; compressing all three blocks to the facts that change a reader's decision brought it to 1861, and that cut preceded this number, per the repo rule that prose is cut before a ceiling is raised. It then rose to 1975 when Step 4e's counts were moved onto finalize's payload and the record list gained 'copy it, never tally it yourself' — a rule that exists because 'counts' beside it is severity — and a further ~67 of rationale was cut back to land at 1908. A fourth change (the round record) then replaced the model's transcription instructions with producer flags — NET +1 after its own trim, because the prose it deletes nearly pays for the flags it adds. Split: ~500 disposition_counts on the telemetry record list, ~690 the reachability question before the revert diagnosis, ~720 the P2 selection change and its rationale. The per-command atomic ceiling needs 631 of it; the rest is aggregate. Attribution in BASELINE-DELTA-review-loop-ledger-fixes.md."
  delta_doc: BASELINE-DELTA-review-loop-ledger-fixes.md
  commands:
    review: 631
---

# PLAN — three fixes the re-audit left standing

> Context: `RESEARCH-review-loop-empirics.md` (2026-08-15) mapped the 230-run experiment against
> this harness and most of it landed. Re-auditing on 2026-08-19 against the source's grown Parts
> 5–6 left three items, and **retired five hypotheses of my own** — recorded here because the
> retractions cost more to rediscover than the fixes did to write.

## 🎯 Executive Summary

Three independent changes to `/hm:review`, none of which adds a round trip:

1. **`disposition_counts` on the telemetry row.** ADR-002's gate has no measurement surface —
   `finalize` writes nothing and reviewer-lens dispositions are not ledgered — so the rejection
   rate the gate exists to move is unreadable from disk.
2. **Ask whether a failing test's state is reachable before calling the revert a regression.**
   Revert either way; the answer changes the record.
3. **P2 leaves the auto-fix queue** (restored at grade D/F). P2/P3 cannot move the grade, so
   fixing them is churn against a gate that cannot read them.
4. **Measured fields stop passing through the model.** Found while checking whether item 1 would
   actually populate: it would not have. Every nullable measured field on the telemetry row is
   0/69 on this repo's own ledger while all nine required fields are 69/69 — a schema optional is
   a prompt optional. Producers now write a per-round record and `emit` reads it.

## 📐 Scope

**In:** `review_telemetry.py` (one nullable field, one validator, producer-sourced measures),
`review_consensus.py` (one pure counter on `finalize`'s payload + `--slug`/`--round`),
`review_churn.py` (`--slug`/`--round` on `measure`), `round_record.py` (new),
`stages/review.md.j2`, `PRIVACY.md`, two unit test modules.

**Out:** any new persisted artifact; the `review-payloads/` store; the disposition enum itself;
the per-finding record; the test-editing ban; `max_review_rounds`; every existing key on
`finalize`'s payload — `disposition_counts` is added beside them, and `counts` keeps meaning
severity.

## What the re-audit retired

Recorded so the next pass does not re-derive them.

| Hypothesis | Why it fell |
|---|---|
| plan-validator needs repo access | It already greps. Its highest-yield finding class is "the PLAN cites a symbol that does not exist" — five episodes, each naming the real `file:line`. |
| Its `Out of Scope: code-level review` line cuts it off from the code | That excludes reviewing code *quality*, not checking whether the PLAN's factual claims hold. The agent reads the distinction correctly. |
| "12 episodes, none clean" evidences missing grounding | `BASELINE-DELTA-plan-validator-transfer.md` uses that number for the opposite claim — that a small revision is not evidence a revision is safe. |
| Reviewer rejection rate is 2.1% | Measured against `review-payloads/`, which snapshots at **Step 3.4**, before Step 4d/4e assign tag and disposition. Wrong denominator; the store is a pre-consensus replay corpus by design. |
| Document-only voters produce the false positives | `codex` is document-only too and ran 33/34 accepted. The `antigravity` 0/8 was a token-quota exhaustion window, not a quality signal. |

**One of those retractions is load-bearing for a live gate.** The ledger's
`(skipped + failed) / total` cannot separate a degraded model from an exhausted quota — both land
in `failed`. Not fixed here; noted so the rate is not read as quality.

## 🔭 Still open, not scoped here

- The `plan-validator` verdict field is a constant: 35 passes, 16 slugs, **zero** APPROVED. The
  findings inside those verdicts are real, so the letter — not the critique — is what carries no
  information. Transferring the review churn gate is already refused by
  `BASELINE-DELTA-plan-validator-transfer.md`; a different mechanism is needed.
- Per-reviewer payloads do not exist (only the merged one). Until they do, this harness cannot
  measure its own reviewer false-positive rate, which is what a local replication of the source
  experiment's repo-access result would need.
- Size trend: `FileChurn.post_loc` is computed and discarded into a ratio denominator.
- `lenses_exercised` and `confirm_pass_ran` are still prose-populated and still 0/69. They have no
  producer command to hang a `--slug`/`--round` on, so they are the next candidates rather than a
  drop-in extension of item 4.
- A signal registry — for each measured field: emitter, **population rate**, direction, threshold
  and its derivation, confounds. Gated by a test the way `PRIVACY.md` is, or it goes stale like
  every hand-maintained table this project has kept. Deliberately AFTER item 4: a registry whose
  first column reads 0/69 documents intent for numbers that do not exist, which is how
  `DEFAULT_CHURN_RATIO` came to be called a recalibration.
- The grade gate rests entirely on reviewer-declared severity, whose self-assessment measured
  ~50% accurate in the source. No prescription yet.

## ✅ Exit criteria

- `tests/unit/test_review_telemetry_disposition.py` passes, including the arm asserting the enum
  is imported rather than restated.
- A row with `disposition_counts` absent still validates (pre-change rows stay readable).
- `round_trips` for `review` / `hm-review` unchanged at 37 / 33.
- A telemetry row whose model-supplied JSON omits every measured key still carries the producers'
  numbers (`test_a_row_that_omits_everything_still_gets_the_numbers` — the 0/69 case, reproduced).
- Full `pytest` green with the declared allowance and **without** regenerating
  `surface_baseline.json`.
