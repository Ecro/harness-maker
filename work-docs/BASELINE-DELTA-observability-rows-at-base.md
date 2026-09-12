# BASELINE-DELTA — observability rows at base (2026-09-12)

Attribution for the `autopilot_gate_golden.json` re-base and the snapshot regeneration.
Every moved byte is one of the two template edits below; no autopilot advance or picker
block moved.

| command | arm | delta (chars) | edit |
|---|---|---|---|
| verify | ask@flag_off, ask@flag_on, auto_safe@spec-driven | -1484 | retire the hand-written `verify-<date>.jsonl` record |
| verify | auto_safe@task-driven | -1420 | same (5-check JSON example) |
| wrapup | every arm | +21 (+1 body line) | name the `invalid choice: 'rollup'` failure and skip visibly (paragraph compacted to stay inside the wrapup ratchet) |

Why the verify ledger goes rather than gains a CLI writer: nothing reads
`verify-*.jsonl` except the `hm cli verify` CI wrapper's own writer, and three projects
produced 3 rows in four months because the step was prose the model skipped. Stage
entry/exit already lands in `stage-spans.jsonl` and `auto-advance.jsonl`.

Non-template changes in the same unit (no rendered bytes): `review_telemetry emit` and
`spec_need record` now file at the base repo root; `/hm:health` gains
`observability_tracked_but_ignored`; `work-docs/BASELINE-ledger-rollup.md` regenerated
from the base ledger.
