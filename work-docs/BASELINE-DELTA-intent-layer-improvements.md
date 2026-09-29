# BASELINE-DELTA — intent-layer-improvements

SPEC: `specs/SPEC-intent-layer-improvements.md` (approved 2026-09-29).

## 1. Aggregate characters

Net **decrease** on both variants. The shared feedback-entry/close partials became collect-only
(one `pending` Feedback row; no skill/status/trial reads), wrapup's close block became a one-line
5.7 cutoff, and Step 5.7's three answer-gated questions became one record batch plus a close
question. `surface_allowance.chars` is the minimum the schema accepts (1); no character headroom
is spent.

## 2. Moved commands

`research`, `spec`, `execute`, `review`, `verify`, `wrapup` (Claude) and their `hm-*` Codex
skills — the six stages that include the feedback partials. No command added or removed.

## 3. Round trips

`wrapup` / `hm-wrapup`: **33 → 34**. Before: Step 5.7 mandated `question observe`,
`question add`, `metric measure --all`, `close`. After: the same four plus
`metric record` for the verdict item on a linked intent's `measure: false` metric (SPEC S4,
AC-004). Declared as `surface_allowance.round_trips` in the PLAN; `test_roundtrip_budget.py`'s
table updated in the same change.

## 4. Re-freeze

The allowance expires when the PLAN is `complete`. After task-land, regenerate
`tests/structural/surface_baseline.json` at the landed main SHA (`uv run python
tests/structural/_surface_baseline.py`) so main does not go red by the declared delta.
