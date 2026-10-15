# hm_eval golden fixtures (SPEC-hm-eval)

- `rows.jsonl` — 18 hand-written result rows: tier 1 task `t1` and tier 2 tasks `t6`, `t7`,
  3 reps per arm. `scorecard.txt` is the report over these rows **without** `t7 hm #3`, so `t7`
  is incomplete and excluded from every tier-2 figure. Publish uses all 18 (balanced).
- `scorecard.txt` — expected `report` output. Worked by hand before it was compared:
  - tier 2 (t6 only) case fraction: plain (10 + 6 + 10) / 30 = 0.87, hm (10 + 10 + 0) / 30 = 0.67,
    gap 0.20 >= 0.05, lead plain.
  - hm `t6 #3` stalled: its quality is null, so hm ruff_new is (0 + 2) / 2 = 1.00 (n=2), mypy_new
    (0 + 1) / 2 = 0.50, regressions 0 / 2; plain ruff_new (0 + 1 + 0) / 3 = 0.33, mypy_new over 2
    runs (rep 3 null: the check could not run), regressions 1 / 3 = 0.33.
  - judge: plain rep 2 is an error, so plain is (4 + 3) / 2 = 3.50 (n=2); hm (5 + 4) / 2 = 4.50
    scope and clarity, (5 + 5) / 2 = 5.00 maintainability, (5 + 13/3) / 2 = 4.67 overall.
  - judge cost: plain 0.02 + 0.02 + unpriced, hm 0.03 + 0.03 (the stall made no call) = $0.100 over
    5 calls, 1 unpriced.
  - tier 2 tokens and turns: hm cache_read (40000 + 40000 + 8000) / 3 = 29333, ratio 2.93; turns
    (20 + 24 + 8) / 3 = 17.3, ratio 2.89.
  - The intent block is tier 1 only: plain $0.100, hm $0.400, ratio 4.000, met.
  - What the extra cost buys, tier 2 (t6 only): cost $0.200 vs $0.700, 3.50x (CLI and transcript
    agree); solved 2 vs 2 (+0, tie); Δ case -0.20 (plain). The quality Δ lines use (task, rep)
    pairs where both arms carry the signal; hm rep 3 stalled, so: Δ regressions over reps 1-2,
    plain (0 + 1) / 2 = 0.50, hm 0.00, -0.50 (hm); Δ lint+type over reps 1-2 (plain rep 3 has no
    mypy), plain 0.50, hm (0 + 3) / 2 = 1.50, +1.00 (plain); Δ judge over rep 1 only (plain rep 2
    is a judge error), 4.00 vs 5.00, +1.00 (hm); cost per solved plain 0.60 / 2 = $0.300, hm
    2.10 / 2 = $1.050; Δ solved = 0, so extra $ per additional solved run is n/a.
- `RESULTS.md`, `README.before.md`, `README.after.md` — `publish` over all 18 rows. What the extra
  cost buys, by hand:
  - tier 1: $0.100 vs $0.400, 4.00x; 3 vs 3 solved; Δ judge (4 + 4 + 5) / 3 - 4 = +0.33 (hm); cost
    per solved $0.100 vs $0.400; extra $ n/a (Δ solved 0).
  - tier 2 (t6, t7): cost 1.05 / 6 = $0.175 vs 3.90 / 6 = $0.650, 3.71x; solved 5 vs 4 (-1, gap 1,
    tie); paired Δ regressions over t6 r1-r2 and t7 r1-r3, plain 1 / 5 = 0.20 vs 0 / 5 (hm);
    paired Δ lint+type over the same five pairs, plain 1 / 5 = 0.20 vs hm 4 / 5 = 0.80 (plain);
    paired Δ judge over t6 r1 and t7 r1-r3, plain (4 + 11) / 4 = 3.75 vs hm
    (5 + 14/3 + 3 + 4) / 4 = 4.17, +0.42 (hm); cost per solved 1.05 / 5 = $0.210 vs
    3.90 / 4 = $0.975; extra $ n/a (Δ solved -1).
- AC-018's four extra-$ cases are built in the test from `_rows` (2 tasks x 3 runs per arm): hm
  solves more ($1.800 extra / 3 more solved = $0.600), plain solves at least as many (n/a), hm
  solves none (n/a), plain solves none ($1.800 / 6 = $0.300).
- `pre_eval_rows.jsonl` — the 2026-10-14 tier-1 rows (schema before SPEC-hm-eval), copied
  unchanged. `pre_eval_metric_block.txt` is what the runner at d48bdc0b printed for them.
- Trap figures (AC-019) are built in the test from `_rows` with the `_TRAP_ROWS` table, not from
  `rows.jsonl`, whose tiers hold no trap task: there every tier's "traps caught" line reads
  `n/a (n=0)` with lead `n/a`. By hand: plain caught t10 1 of 2, t11 0 of 2, t12 1 of 1 (rep 2
  stalled, null) = 2/5 = 0.40; hm 2 + 1 + 2 = 5/6 = 0.83; the lead is on the rate, gap 0.43 >= 0.20,
  hm. Flipping plain's two t11 runs to caught gives 4/5 = 0.80 vs 0.83, gap 0.03, tie.
- The whole-file goldens (`scorecard.txt`, `RESULTS.md`, `README.after.md`) are runner output,
  regenerated after a reviewed change; the figures above are the hand check that each regeneration
  is compared against. Their prose is the runner's, not a separate oracle.
