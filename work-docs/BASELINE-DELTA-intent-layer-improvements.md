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

## 4. Re-freeze (done 2026-09-29 at the landed main commit e5851a67)

The PLAN went `complete`, the `surface_allowance` expired, and `test_surface_baseline.py` failed
1/15 (round trips) as predicted. `surface_baseline.json` was regenerated at e5851a67 and the
allowance block was retired from the PLAN in the same commit. Aggregate after re-freeze:
**claude 357 790, codex 312 039** — the aggregate shrank (a reduction, the right way for a surface
ratchet).

| key | before | after | delta | why |
|---|---:|---:|---:|---|
| `aggregate_chars.claude` | 358 106 | 357 790 | -316 | sum of the rows below |
| `aggregate_chars.codex` | 312 513 | 312 039 | -474 | sum of the rows below |
| claude `execute` chars | 64 259 | 64 027 | -232 | collect-only feedback-entry/close partials |
| claude `research` chars | 24 711 | 24 479 | -232 | same partials |
| claude `review` chars | 88 481 | 88 249 | -232 | same partials |
| claude `spec` chars | 49 400 | 49 233 | -167 | same partials; Step 4.9 bare-id derivation |
| claude `verify` chars | 28 013 | 27 781 | -232 | same partials |
| claude `wrapup` chars / round trips | 55 718 / 33 | 56 497 / 34 | +779 / +1 | Step 5.7 record batch + close question, Step 0.5 resumes at 5.7, 5.7 cutoff close block; +1 `metric record` call |
| codex `hm-execute` chars | 65 519 | 65 287 | -232 | same partials |
| codex `hm-research` chars | 24 656 | 24 424 | -232 | same partials |
| codex `hm-review` chars | 88 044 | 87 812 | -232 | same partials |
| codex `hm-spec` chars | 48 173 | 48 006 | -167 | same partials; Step 4.9 |
| codex `hm-verify` chars | 27 737 | 27 505 | -232 | same partials |
| codex `hm-wrapup` chars / round trips | 56 419 / 33 | 57 040 / 34 | +621 / +1 | as for `wrapup` (Codex numbered-list form) |

`render_sha` and `payload_digest` move with any re-freeze.

**Ownership (ADR-010).** This is not ratchet-rebaselined-by-its-own-subject: the re-freeze follows
a landed, reviewed change whose growth was declared in advance as `surface_allowance`
(round trips only; characters fell), and the only growing commands are `wrapup` / `hm-wrapup`,
whose +1 round trip is the verdict item SPEC-intent-layer-improvements AC-004 requires.
