# hm eval results

<!-- Written by `uv run python scripts/bench_light_lane.py publish`; do not edit. -->

Plain prompt vs `/hm:` on the `timeparse` fixture. What each line means and how a lead is picked: [README.md](README.md).

| Setup | Value |
|---|---|
| bench_hash | `e65288c988d1` |
| harness_sha | `d25e6bb5261f-dirty-e7b80b46` |
| runner_hash | `ae77b902f31b` |
| agent model | `claude-sonnet-5-5` |
| judge model | `claude-sonnet-5-5` |
| rubric | `hm-eval-judge-v1` |
| ruff | `ruff 0.15.12` |
| mypy | `mypy 1.20.2 (compiled: yes)` |
| tiers | 1, 2 |
| runs per cell | tier 1: 3, tier 2: 3 |
| runs started | 2026-10-15 to 2026-10-15 |

## What the extra cost buys

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (cells: mean CLI $/run) | $0.057 (n=15) | $1.371 (n=15) | 26.63x (CLI 24.13x, transcript 26.63x) | plain |
| Δ solved runs | 15 (n=15) | 13 (n=15) | -2 | plain |
| Δ hidden-case pass fraction | 1.00 (n=15) | 0.85 (n=15) | -0.15 | plain |
| Δ regressions per run | 0.00 (n=13) | 0.00 (n=13) | +0.00 | tie |
| Δ new lint+type errors per run | 0.31 (n=13) | 0.15 (n=13) | -0.15 | hm |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | 4.36 (n=13) | 3.82 (n=13) | -0.54 (single-sample scores, judge noise ±0.67; tie band 0.25 over 13 pairs) | plain |
| cost per solved run | $0.057 (n=15) | $1.582 (n=13) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (cells: mean CLI $/run) | $0.052 (n=21) | $0.914 (n=21) | 20.06x (CLI 17.66x, transcript 20.06x) | plain |
| Δ solved runs | 21 (n=21) | 17 (n=21) | -4 | plain |
| Δ hidden-case pass fraction | 1.00 (n=21) | 0.92 (n=21) | -0.08 | plain |
| Δ regressions per run | 0.00 (n=17) | 0.00 (n=17) | +0.00 | tie |
| Δ new lint+type errors per run | 0.12 (n=17) | 0.06 (n=17) | -0.06 | hm |
| traps caught | 9/9 | 6/6 | +0.00 | n/a |
| Δ judge overall | 4.51 (n=17) | 4.37 (n=17) | -0.14 (single-sample scores, judge noise ±0.67; tie band 0.25 over 17 pairs) | tie |
| cost per solved run | $0.052 (n=21) | $1.129 (n=17) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

## Quality

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 15 | 15 | — |
| hidden all-pass | 15 (n=15) | 13 (n=15) | plain |
| hidden-case pass fraction | 1.00 (n=15) | 0.85 (n=15) | plain |
| solved | 15 (n=15) | 13 (n=15) | plain |
| wrong | 0 (n=15) | 0 (n=15) | tie |
| stalled | 0 (n=15) | 2 (n=15) | plain |
| ruff_new mean | 0.00 (n=15) | 0.08 (n=13) | plain |
| mypy_new mean | 0.27 (n=15) | 0.08 (n=13) | hm |
| regressions mean | 0.00 (n=15) | 0.00 (n=13) | tie |
| diff_lines mean | 38.60 (n=15) | 154.46 (n=13) | — |
| tests_touched rate | 0.00 (n=15) | 1.00 (n=13) | — |
| judge scope | 4.87 (n=15) | 3.92 (n=13) | plain |
| judge clarity | 4.13 (n=15) | 3.77 (n=13) | plain |
| judge maintainability | 4.00 (n=15) | 3.77 (n=13) | tie |
| judge overall | 4.33 (n=15) | 3.82 (n=13) | plain |

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 21 | 21 | — |
| hidden all-pass | 21 (n=21) | 17 (n=21) | plain |
| hidden-case pass fraction | 1.00 (n=21) | 0.92 (n=21) | plain |
| solved | 21 (n=21) | 17 (n=21) | plain |
| wrong | 0 (n=21) | 0 (n=21) | tie |
| stalled | 0 (n=21) | 4 (n=21) | plain |
| ruff_new mean | 0.00 (n=21) | 0.00 (n=17) | tie |
| mypy_new mean | 0.14 (n=21) | 0.06 (n=17) | hm |
| regressions mean | 0.00 (n=21) | 0.00 (n=17) | tie |
| diff_lines mean | 23.76 (n=21) | 68.18 (n=17) | — |
| tests_touched rate | 0.38 (n=21) | 1.00 (n=17) | — |
| judge scope | 4.81 (n=21) | 4.41 (n=17) | plain |
| judge clarity | 4.33 (n=21) | 4.53 (n=17) | tie |
| judge maintainability | 4.52 (n=21) | 4.18 (n=17) | plain |
| judge overall | 4.56 (n=21) | 4.37 (n=17) | tie |

## Efficiency

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.057 (n=15) | $1.371 (n=15) | 24.13x | plain |
| input tokens | 7 (n=15) | 102 (n=15) | 15.55x | plain |
| output tokens | 1786 (n=15) | 39858 (n=15) | 22.32x | plain |
| cache_read tokens | 51213 (n=15) | 3435362 (n=15) | 67.08x | plain |
| cache_write tokens | 8462 (n=15) | 157740 (n=15) | 18.64x | plain |
| turns | 3.5 (n=15) | 8.9 (n=14) | 2.51x | plain |
| wall s | 16 (n=15) | 385 (n=15) | 23.96x | plain |

Judge cost, kept out of the arm costs: $0.725 total over 28 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 68 redaction(s) in 10 run(s).

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.052 (n=21) | $0.914 (n=21) | 17.66x | plain |
| input tokens | 7 (n=21) | 79 (n=21) | 11.53x | plain |
| output tokens | 1296 (n=21) | 24711 (n=21) | 19.06x | plain |
| cache_read tokens | 54675 (n=21) | 2342439 (n=21) | 42.84x | plain |
| cache_write tokens | 8331 (n=21) | 116383 (n=21) | 13.97x | plain |
| turns | 4.2 (n=21) | 8.4 (n=21) | 1.98x | plain |
| wall s | 13 (n=21) | 316 (n=21) | 24.74x | plain |

Judge cost, kept out of the arm costs: $0.869 total over 38 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 28 redaction(s) in 8 run(s).

## Intent metric (tier 1 only)

```text
bench hm-light-lane@e65288c988d1  harness d25e6bb5261f-dirty-e7b80b46  model claude-sonnet-5-5
task   plain pass  hm pass  plain $/run  hm $/run  plain s   hm s
t1         3/3      3/3           0.054     0.962       16    223
t2         3/3      3/3           0.056     2.925       14    955
t3         3/3      3/3           0.050     1.133       14    280
t4         3/3      3/3           0.054     1.220       14    298
t5         3/3      1/3           0.071     0.616       22    170
all       15/15    13/15          0.057     1.371       16    385
ratio (CLI cost): 24.13    ratio (transcript price): 26.63
pass rate: plain 15/15 (100%), hm 13/15 (87%)
verdict: missed — ratio 26.625 > target 5
record with:
  uv run hm intent metric record hm_cost_ratio_small --value 26.625 --evidence 'bench hm-light-lane@e65288c988d1 harness d25e6bb5261f-dirty-e7b80b46 model claude-sonnet-5-5: hm $1.371/run vs plain $0.057/run over 5 tasks x 3 runs (CLI-priced ratio 24.13, transcript-priced ratio 26.63); hidden-test pass plain 15/15, hm 13/15; verdict missed'
hm_cost_ratio_small=26.625
```
