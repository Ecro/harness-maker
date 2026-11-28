# PLAN — owner-attention-metrics

SPEC: `specs/SPEC-owner-attention-metrics.md` (approved).

## Phase 1 — owner numbers in the saga bench

- [x] RED: `test_owner_ac_001..005` in `tests/unit/test_saga_bench.py` fail on main 16731486
      (`attention`, `doc_chars`, `escaped_regressions`, `owner_summary`, `run_judge` missing).
- [x] `attention(record)` from stored turns; `shipped(record)`; `doc_chars(work, arm, slug)`
      stored by `_finish` with `hidden_dir`.
- [x] `escaped_regressions` regrades each session's hidden dir once on the final tree;
      `run_saga` stores `escaped`.
- [x] `owner_summary` + "owner (per shipped change)" table in `report`.
- [x] `run_judge` / `judge_summary` / `judge` CLI: position-swapped, Opus default, pick only on
      agreement; `report` prints `judge.jsonl` when present.
- [x] Baseline: `report` on the 2026-11-25 main-run rows prints the owner table.

## ADR

- ADR-001 (agent): attention is derived in the report from stored turns, so old rows count.
- ADR-002 (agent): maintainability is judged on the saga's final tree, hm vs every other arm at
  the same rep; the saga has no plain+tests arm.
