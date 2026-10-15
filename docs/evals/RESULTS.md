# hm eval results

<!-- Written by `uv run python scripts/bench_light_lane.py publish`; do not edit. -->

Plain prompt vs `/hm:` on the `timeparse` fixture. What each line means and how a lead is picked: [README.md](README.md).

| Setup | Value |
|---|---|
| bench_hash | `e65288c988d1` |
| harness_sha | `0289e72412ce-dirty-e7b80b46` |
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
| cost ratio (cells: mean CLI $/run) | $0.062 (n=15) | $1.401 (n=15) | 26.25x (CLI 22.63x, transcript 26.25x) | plain |
| Δ solved runs | 15 (n=15) | 12 (n=15) | -3 | plain |
| Δ hidden-case pass fraction | 1.00 (n=15) | 0.77 (n=15) | -0.23 | plain |
| Δ regressions per run | 0.00 (n=12) | 0.00 (n=12) | +0.00 | tie |
| Δ new lint+type errors per run | 0.42 (n=12) | 0.08 (n=12) | -0.33 | hm |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | 4.25 (n=12) | 4.06 (n=12) | -0.19 (single-sample scores, judge noise ±0.67; tie band 0.25 over 12 pairs) | tie |
| cost per solved run | $0.062 (n=15) | $1.751 (n=12) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (cells: mean CLI $/run) | $0.051 (n=21) | $0.910 (n=21) | 20.60x (CLI 17.99x, transcript 20.60x) | plain |
| Δ solved runs | 21 (n=21) | 15 (n=21) | -6 | plain |
| Δ hidden-case pass fraction | 1.00 (n=21) | 0.82 (n=21) | -0.18 | plain |
| Δ regressions per run | 0.00 (n=15) | 0.00 (n=15) | +0.00 | tie |
| Δ new lint+type errors per run | 0.20 (n=15) | 0.27 (n=15) | +0.07 | plain |
| traps caught | 9/9 | 7/7 | +0.00 | n/a |
| Δ judge overall | 4.62 (n=15) | 4.22 (n=15) | -0.40 (single-sample scores, judge noise ±0.67; tie band 0.25 over 15 pairs) | plain |
| cost per solved run | $0.051 (n=21) | $1.274 (n=15) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

## Quality

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 15 | 15 | — |
| hidden all-pass | 15 (n=15) | 12 (n=15) | plain |
| hidden-case pass fraction | 1.00 (n=15) | 0.77 (n=15) | plain |
| solved | 15 (n=15) | 12 (n=15) | plain |
| wrong | 0 (n=15) | 0 (n=15) | tie |
| stalled | 0 (n=15) | 3 (n=15) | plain |
| ruff_new mean | 0.07 (n=15) | 0.08 (n=12) | plain |
| mypy_new mean | 0.27 (n=15) | 0.00 (n=12) | hm |
| regressions mean | 0.00 (n=15) | 0.00 (n=12) | tie |
| diff_lines mean | 42.33 (n=15) | 148.50 (n=12) | — |
| tests_touched rate | 0.07 (n=15) | 1.00 (n=12) | — |
| judge scope | 4.80 (n=15) | 4.08 (n=12) | plain |
| judge clarity | 3.93 (n=15) | 4.08 (n=12) | tie |
| judge maintainability | 4.07 (n=15) | 4.00 (n=12) | tie |
| judge overall | 4.27 (n=15) | 4.06 (n=12) | tie |

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 21 | 21 | — |
| hidden all-pass | 21 (n=21) | 15 (n=21) | plain |
| hidden-case pass fraction | 1.00 (n=21) | 0.82 (n=21) | plain |
| solved | 21 (n=21) | 15 (n=21) | plain |
| wrong | 0 (n=21) | 0 (n=21) | tie |
| stalled | 0 (n=21) | 6 (n=21) | plain |
| ruff_new mean | 0.00 (n=21) | 0.13 (n=15) | plain |
| mypy_new mean | 0.14 (n=21) | 0.13 (n=15) | hm |
| regressions mean | 0.00 (n=21) | 0.00 (n=15) | tie |
| diff_lines mean | 23.43 (n=21) | 64.53 (n=15) | — |
| tests_touched rate | 0.33 (n=21) | 1.00 (n=15) | — |
| judge scope | 4.86 (n=21) | 4.33 (n=15) | plain |
| judge clarity | 4.48 (n=21) | 4.33 (n=15) | tie |
| judge maintainability | 4.38 (n=21) | 4.00 (n=15) | plain |
| judge overall | 4.57 (n=21) | 4.22 (n=15) | plain |

## Efficiency

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.062 (n=15) | $1.401 (n=15) | 22.63x | plain |
| input tokens | 8 (n=15) | 113 (n=15) | 14.62x | plain |
| output tokens | 2016 (n=15) | 41935 (n=15) | 20.80x | plain |
| cache_read tokens | 62671 (n=15) | 3892864 (n=15) | 62.12x | plain |
| cache_write tokens | 8857 (n=15) | 167005 (n=15) | 18.85x | plain |
| turns | 4.1 (n=15) | 6.3 (n=15) | 1.56x | plain |
| wall s | 17 (n=15) | 435 (n=15) | 26.00x | plain |

Judge cost, kept out of the arm costs: $0.689 total over 27 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 48 redaction(s) in 10 run(s).

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.051 (n=21) | $0.910 (n=21) | 17.99x | plain |
| input tokens | 7 (n=21) | 80 (n=21) | 12.19x | plain |
| output tokens | 1254 (n=21) | 24227 (n=21) | 19.31x | plain |
| cache_read tokens | 52023 (n=21) | 2400139 (n=21) | 46.14x | plain |
| cache_write tokens | 8198 (n=21) | 116303 (n=21) | 14.19x | plain |
| turns | 3.9 (n=21) | 10.1 (n=21) | 2.59x | plain |
| wall s | 12 (n=21) | 202 (n=21) | 17.18x | plain |

Judge cost, kept out of the arm costs: $0.813 total over 36 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 28 redaction(s) in 7 run(s).

## Intent metric (tier 1 only)

```text
bench hm-light-lane@e65288c988d1  harness 0289e72412ce-dirty-e7b80b46  model claude-sonnet-5-5
task   plain pass  hm pass  plain $/run  hm $/run  plain s   hm s
t1         3/3      2/3           0.057     0.855       16    233
t2         3/3      3/3           0.055     2.674       13    868
t3         3/3      3/3           0.064     1.174       16    604
t4         3/3      3/3           0.056     1.516       14    293
t5         3/3      1/3           0.078     0.784       25    176
all       15/15    12/15          0.062     1.401       17    435
ratio (CLI cost): 22.63    ratio (transcript price): 26.25
pass rate: plain 15/15 (100%), hm 12/15 (80%)
verdict: missed — ratio 26.254 > target 5
record with:
  uv run hm intent metric record hm_cost_ratio_small --value 26.254 --evidence 'bench hm-light-lane@e65288c988d1 harness 0289e72412ce-dirty-e7b80b46 model claude-sonnet-5-5: hm $1.401/run vs plain $0.062/run over 5 tasks x 3 runs (CLI-priced ratio 22.63, transcript-priced ratio 26.25); hidden-test pass plain 15/15, hm 12/15; verdict missed'
hm_cost_ratio_small=26.254
```
