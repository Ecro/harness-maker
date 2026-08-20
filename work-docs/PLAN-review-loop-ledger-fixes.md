---
type: plan
task_slug: review-loop-ledger-fixes
status: planning
created: 2026-08-19
tags: [harness-maker, plan, review-stage, telemetry, auto-fix-loop]
summary: "Give the disposition gate a measurement surface; stop diagnosing over-specified tests as regressions; take P2 out of the fixer's queue."
surface_allowance:
  chars: 2572
  reason: "MEASURED after the reduction, not before. round_trips 37/33 unchanged — every rule lands in a step that already runs. The number moved four times and each move is attributable: 2516 first draft -> 1861 after cutting all three blocks to the facts that change a reader decision -> 1975 when finalize gained the counts and the record list gained copy-it-never-tally-it -> 1908 after a rationale cut -> 1914 when a confirm-1 repair fixed two self-contradicting prose spots -> 2096 now. The last move is the ONLY one that is a net addition rather than a repair, and it is the price of Option A: deleting round_record.py (228 lines) means the producers tee their payload and emit takes --measured, which costs +182 prompt characters across four template arms. That trade removed five P1 findings and six P2s, all of them in the store machinery and none in the feature. A second review of the reduction then found a P0 and six P1s and the repairs took it to 2572: `set -o pipefail` on two producer pipelines (four template arms), an absolute-path rule for the tee'd payload paths, the `!` auto-exec marker the emit step never had, and moving `--spec` back in front of the pipe. round_trips 37 -> 38 for the `!`, re-baselined in test_roundtrip_budget.py with its reason. The per-command atomic ceiling needs 1294 of it; the rest is aggregate."
  delta_doc: BASELINE-DELTA-review-loop-ledger-fixes.md
  round_trips:
    review: 1
  commands:
    review: 1294
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
   a prompt optional. The producers `tee` their own payload; `emit --measured <path>` reads the
   numbers out of it and strips them from the model's row.

## 📐 Scope

**In:** `review_telemetry.py` (one nullable field, one validator, `MEASURED_KEYS`, and the
`--measured` reader), `review_consensus.py` (one pure counter on `finalize`'s payload +
`--slug`/`--round` stamping), `review_churn.py` (the same stamping on `measure`),
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
- **A harness change cannot be verified through its own rendered stage.** The rendered command
  runs `uv run --with $HOME/harness-maker`, which resolves to the BASE checkout — so a stage
  running inside `.worktrees/<slug>/` executes `main`'s Python, not the branch under review.
  Measured: this change's own terminal `emit` wrote a row with no `disposition_counts` key,
  because the code that produces it is not on `main` yet. Pre-existing, out of this diff's scope,
  and the single largest obstacle to ever measuring a harness change end to end.
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

## 🔻 What Option A removed, and why the shape changed twice

The first implementation carried the numbers in a shared scratch store keyed by (slug, round).
A store has to answer three questions a file path does not — which root it lives under, how two
writers coordinate, how two runs stay apart — and each answer was added only after a review round
found the previous one broken:

| Round | Finding | Answer added |
|---|---|---|
| 1 | **P0** producers wrote inside `<WT>`, `emit` read the base | base-root anchoring |
| confirm-1 | **P1 ×2** that anchoring made two worktrees share one file: lost update, chimera row | `flock`, `RUN_KEY` |
| confirm-2 | **P1 ×5** in the lock and the stamp: TOCTOU, no timeout, no oracle, two doc claims | — |

Three consecutive rounds produced severe findings **only** in the machinery guarding the feature,
never in the feature. Per 제1목표 the device was reduced rather than repaired again: `round_record.py`
(228 lines) is deleted, and with it all five surviving P1s and six P2s — not fixed, but left
without a subject. The P0's own recurrence path goes too, since absolute temp paths are
cwd-independent by construction.

**The honest cost:** the prompt surface grew +182 characters (1914 → 2096). Python shrank by 228
lines; the prose explaining `tee` and `--measured` is larger than the prose describing the store.

**The one hazard passing paths introduces is a stale file**, and unlike the store's three
questions it is decidable: the producers stamp `slug`/`round` onto their payload and `emit`
refuses a file whose stamp disagrees with the row. An unstamped payload is accepted, so nothing
that predates the stamp regresses.

## ✅ Exit criteria

- `tests/unit/test_review_telemetry_disposition.py` passes, including the arm asserting the enum
  is imported rather than restated.
- A row with `disposition_counts` absent still validates (pre-change rows stay readable).
- `round_trips` for `review` / `hm-review` unchanged at 37 / 33.
- A telemetry row whose model-supplied JSON omits every measured key still carries the producers'
  numbers (`test_a_row_that_omits_everything_still_gets_the_numbers` — the 0/69 case, reproduced).
- A producer payload stamped with a different slug or round is refused, not merged.
- Nothing imports `round_record`; no shared mutable store remains on this path.
- Full `pytest` green with the declared allowance and **without** regenerating
  `surface_baseline.json`.
