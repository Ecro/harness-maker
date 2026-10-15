# hm eval results

<!-- Written by `uv run python scripts/bench_light_lane.py publish`; do not edit. -->

Plain prompt vs `/hm:` on the `timeparse` fixture. What each line means and how a lead is picked: [README.md](README.md).

| Setup | Value |
|---|---|
| bench_hash | `569e17ef29ab` |
| harness_sha | `6b7c30d9e175` |
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
| cost ratio (cells: mean CLI $/run) | $0.061 (n=15) | $1.396 (n=15) | 26.42x (CLI 22.79x, transcript 26.42x) | plain |
| Δ solved runs | 15 (n=15) | 15 (n=15) | +0 | tie |
| Δ hidden-case pass fraction | 1.00 (n=15) | 1.00 (n=15) | +0.00 | tie |
| Δ regressions per run | 0.00 (n=15) | 0.00 (n=15) | +0.00 | tie |
| Δ new lint+type errors per run | 0.27 (n=15) | 0.07 (n=15) | -0.20 | hm |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | 4.27 (n=15) | 3.87 (n=15) | -0.40 (single-sample scores, judge noise ±0.67; tie band 0.25 over 15 pairs) | plain |
| cost per solved run | $0.061 (n=15) | $1.396 (n=15) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (cells: mean CLI $/run) | $0.051 (n=21) | $1.011 (n=21) | 22.68x (CLI 19.76x, transcript 22.68x) | plain |
| Δ solved runs | 21 (n=21) | 19 (n=21) | -2 | plain |
| Δ hidden-case pass fraction | 1.00 (n=21) | 0.96 (n=21) | -0.04 | tie |
| Δ regressions per run | 0.00 (n=20) | 0.00 (n=20) | +0.00 | tie |
| Δ new lint+type errors per run | 0.20 (n=20) | 0.15 (n=20) | -0.05 | hm |
| traps caught | 9/9 | 8/8 | +0.00 | tie |
| Δ judge overall | 4.58 (n=20) | 4.50 (n=20) | -0.08 (single-sample scores, judge noise ±0.67; tie band 0.25 over 20 pairs) | tie |
| cost per solved run | $0.051 (n=21) | $1.117 (n=19) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

## Quality

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 15 | 15 | — |
| hidden all-pass | 15 (n=15) | 15 (n=15) | tie |
| hidden-case pass fraction | 1.00 (n=15) | 1.00 (n=15) | tie |
| solved | 15 (n=15) | 15 (n=15) | tie |
| wrong | 0 (n=15) | 0 (n=15) | tie |
| stalled | 0 (n=15) | 0 (n=15) | tie |
| ruff_new mean | 0.00 (n=15) | 0.00 (n=15) | tie |
| mypy_new mean | 0.27 (n=15) | 0.07 (n=15) | hm |
| regressions mean | 0.00 (n=15) | 0.00 (n=15) | tie |
| diff_lines mean | 46.20 (n=15) | 170.93 (n=15) | — |
| tests_touched rate | 0.13 (n=15) | 1.00 (n=15) | — |
| judge scope | 4.73 (n=15) | 4.00 (n=15) | plain |
| judge clarity | 4.07 (n=15) | 3.80 (n=15) | plain |
| judge maintainability | 4.00 (n=15) | 3.80 (n=15) | tie |
| judge overall | 4.27 (n=15) | 3.87 (n=15) | plain |

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 21 | 21 | — |
| hidden all-pass | 21 (n=21) | 19 (n=21) | plain |
| hidden-case pass fraction | 1.00 (n=21) | 0.96 (n=21) | tie |
| solved | 21 (n=21) | 19 (n=21) | plain |
| wrong | 0 (n=21) | 1 (n=21) | tie |
| stalled | 0 (n=21) | 1 (n=21) | tie |
| ruff_new mean | 0.05 (n=21) | 0.10 (n=20) | plain |
| mypy_new mean | 0.14 (n=21) | 0.05 (n=20) | hm |
| regressions mean | 0.00 (n=21) | 0.00 (n=20) | tie |
| diff_lines mean | 24.33 (n=21) | 65.95 (n=20) | — |
| tests_touched rate | 0.43 (n=21) | 1.00 (n=20) | — |
| judge scope | 4.81 (n=21) | 4.60 (n=20) | tie |
| judge clarity | 4.43 (n=21) | 4.70 (n=20) | hm |
| judge maintainability | 4.48 (n=21) | 4.20 (n=20) | plain |
| judge overall | 4.57 (n=21) | 4.50 (n=20) | tie |

## Efficiency

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.061 (n=15) | $1.396 (n=15) | 22.79x | plain |
| input tokens | 7 (n=15) | 118 (n=15) | 15.80x | plain |
| output tokens | 2020 (n=15) | 42647 (n=15) | 21.11x | plain |
| cache_read tokens | 60440 (n=15) | 3819665 (n=15) | 63.20x | plain |
| cache_write tokens | 8747 (n=15) | 166924 (n=15) | 19.08x | plain |
| turns | 3.9 (n=15) | 8.7 (n=15) | 2.22x | plain |
| wall s | 18 (n=15) | 479 (n=15) | 26.16x | plain |

Judge cost, kept out of the arm costs: $0.821 total over 30 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 98 redaction(s) in 13 run(s).

### tier 2: 7 task(s) x 3 run(s) per arm (t10, t11, t12, t6, t7, t8, t9)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.051 (n=21) | $1.011 (n=21) | 19.76x | plain |
| input tokens | 7 (n=21) | 94 (n=21) | 13.87x | plain |
| output tokens | 1250 (n=21) | 27958 (n=21) | 22.37x | plain |
| cache_read tokens | 53845 (n=21) | 2713646 (n=21) | 50.40x | plain |
| cache_write tokens | 8317 (n=21) | 125333 (n=21) | 15.07x | plain |
| turns | 4.2 (n=21) | 9.2 (n=21) | 2.20x | plain |
| wall s | 13 (n=21) | 266 (n=21) | 19.84x | plain |

Judge cost, kept out of the arm costs: $0.948 total over 41 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 34 redaction(s) in 10 run(s).

## Intent metric (tier 1 only)

```text
bench hm-light-lane@569e17ef29ab  harness 6b7c30d9e175  model claude-sonnet-5-5
task   plain pass  hm pass  plain $/run  hm $/run  plain s   hm s
t1         3/3      3/3           0.057     1.270       16    648
t2         3/3      3/3           0.057     2.415       17    625
t3         3/3      3/3           0.054     0.863       15    225
t4         3/3      3/3           0.051     1.135       14    560
t5         3/3      3/3           0.088     1.296       29    337
all       15/15    15/15          0.061     1.396       18    479
ratio (CLI cost): 22.79    ratio (transcript price): 26.42
pass rate: plain 15/15 (100%), hm 15/15 (100%)
verdict: missed — ratio 26.418 > target 5
record with:
  uv run hm intent metric record hm_cost_ratio_small --value 26.418 --evidence 'bench hm-light-lane@569e17ef29ab harness 6b7c30d9e175 model claude-sonnet-5-5: hm $1.396/run vs plain $0.061/run over 5 tasks x 3 runs (CLI-priced ratio 22.79, transcript-priced ratio 26.42); hidden-test pass plain 15/15, hm 15/15; verdict missed'
hm_cost_ratio_small=26.418
```
