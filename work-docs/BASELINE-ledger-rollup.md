# Ledger roll-up

## Per model

| model | calls | invoked | skipped | failed | loss_rate |
|---|---|---|---|---|---|
| antigravity | 101 | 49 | 25 | 27 | 0.5148514851485149 |
| codex | 114 | 110 | 4 | 0 | 0.03508771929824561 |

## Per stage

| stage | calls |
|---|---|
| plan | 83 |
| review | 132 |

Invocation rows counted: 215.

## Exclusions applied

Rows dropped: 150.

- `run_id=aiexit-exec-p2b` — PASS emitted BEFORE the A.5 round it claims to describe was dispatched (2026-08-14, PLAN-ai-review-exit-criteria). These ledgers are append-only with no retract verb, so the row is permanent; this file is the only way to keep it out of aggregates.
- `slug=s` — Synthetic rows written by tests/unit/test_second_opinion_invoke.py before the 2026-08-17 conftest redirect, across roughly 140 pytest runs. They are the bulk of the codex loss rate and none of them describe a real call.
- `slug=hm-ledger-canary` — Canary rows from the Phase 1 RED runs of tests/unit/test_ledger_isolation.py, whose first assertion certified a live leak as safe.
- `slug=hm-ledger-canary-invoke` — Same, from the direct-invoke canary in the same file.

## Dangling authorizations

- authorized to `execute` with no confirming entry
- authorized to `execute` with no confirming entry
- authorized to `execute` with no confirming entry
- authorized to `execute` with no confirming entry
- authorized to `execute` with no confirming entry
- authorized to `execute` with no confirming entry
- authorized to `review` with no confirming entry
- authorized to `review` with no confirming entry
- authorized to `review` with no confirming entry
- authorized to `review` with no confirming entry
- authorized to `spec` with no confirming entry
- authorized to `spec` with no confirming entry
- authorized to `spec` with no confirming entry
