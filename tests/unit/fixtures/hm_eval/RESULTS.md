# hm eval results

<!-- Written by `uv run python scripts/bench_light_lane.py publish`; do not edit. -->

Plain prompt vs `/hm:` on the `timeparse` fixture. What each line means and how a lead is picked: [README.md](README.md).

| Setup | Value |
|---|---|
| bench_hash | `bh0001` |
| harness_sha | `hs0001` |
| runner_hash | `rh0001` |
| agent model | `model-a` |
| judge model | `model-a` |
| rubric | `hm-eval-judge-v1` |
| ruff | `ruff 0.15.12` |
| mypy | `mypy 1.20.2 (compiled: yes)` |
| tiers | 1, 2 |
| runs per cell | tier 1: 3, tier 2: 3 |
| runs started | 2026-10-15 to 2026-10-16 |

## What the extra cost buys

### tier 1: 1 task(s) x 3 run(s) per arm (t1)

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (cells: mean CLI $/run) | $0.100 (n=3) | $0.400 (n=3) | 4.00x | plain |
| Δ solved runs | 3 (n=3) | 3 (n=3) | +0 | tie |
| Δ hidden-case pass fraction | 1.00 (n=3) | 1.00 (n=3) | +0.00 | tie |
| Δ regressions per run | 0.00 (n=3) | 0.00 (n=3) | +0.00 | tie |
| Δ new lint+type errors per run | 0.00 (n=3) | 0.00 (n=3) | +0.00 | tie |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | 4.00 (n=3) | 4.33 (n=3) | +0.33 | hm |
| cost per solved run | $0.100 (n=3) | $0.400 (n=3) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

### tier 2: 2 task(s) x 3 run(s) per arm (t6, t7)

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (cells: mean CLI $/run) | $0.175 (n=6) | $0.650 (n=6) | 3.71x | plain |
| Δ solved runs | 5 (n=6) | 4 (n=6) | -1 | tie |
| Δ hidden-case pass fraction | 0.93 (n=6) | 0.78 (n=6) | -0.15 | plain |
| Δ regressions per run | 0.20 (n=5) | 0.00 (n=5) | -0.20 | hm |
| Δ new lint+type errors per run | 0.20 (n=5) | 0.80 (n=5) | +0.60 | plain |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | 3.75 (n=4) | 4.17 (n=4) | +0.42 | hm |
| cost per solved run | $0.210 (n=5) | $0.975 (n=4) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

## Quality

### tier 1: 1 task(s) x 3 run(s) per arm (t1)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 3 | 3 | — |
| hidden all-pass | 3 (n=3) | 3 (n=3) | tie |
| hidden-case pass fraction | 1.00 (n=3) | 1.00 (n=3) | tie |
| solved | 3 (n=3) | 3 (n=3) | tie |
| wrong | 0 (n=3) | 0 (n=3) | tie |
| stalled | 0 (n=3) | 0 (n=3) | tie |
| ruff_new mean | 0.00 (n=3) | 0.00 (n=3) | tie |
| mypy_new mean | 0.00 (n=3) | 0.00 (n=3) | tie |
| regressions mean | 0.00 (n=3) | 0.00 (n=3) | tie |
| diff_lines mean | 10.00 (n=3) | 20.00 (n=3) | — |
| tests_touched rate | 0.00 (n=3) | 1.00 (n=3) | — |
| judge scope | 4.00 (n=3) | 4.00 (n=3) | tie |
| judge clarity | 4.00 (n=3) | 5.00 (n=3) | hm |
| judge maintainability | 4.00 (n=3) | 4.00 (n=3) | tie |
| judge overall | 4.00 (n=3) | 4.33 (n=3) | hm |

### tier 2: 2 task(s) x 3 run(s) per arm (t6, t7)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 6 | 6 | — |
| hidden all-pass | 5 (n=6) | 4 (n=6) | tie |
| hidden-case pass fraction | 0.93 (n=6) | 0.78 (n=6) | plain |
| solved | 5 (n=6) | 4 (n=6) | tie |
| wrong | 1 (n=6) | 1 (n=6) | tie |
| stalled | 0 (n=6) | 1 (n=6) | tie |
| ruff_new mean | 0.17 (n=6) | 0.60 (n=5) | plain |
| mypy_new mean | 0.00 (n=5) | 0.20 (n=5) | plain |
| regressions mean | 0.17 (n=6) | 0.00 (n=5) | hm |
| diff_lines mean | 30.00 (n=6) | 52.00 (n=5) | — |
| tests_touched rate | 0.17 (n=6) | 1.00 (n=5) | — |
| judge scope | 3.80 (n=5) | 4.20 (n=5) | hm |
| judge clarity | 3.20 (n=5) | 4.00 (n=5) | hm |
| judge maintainability | 3.80 (n=5) | 4.40 (n=5) | hm |
| judge overall | 3.60 (n=5) | 4.20 (n=5) | hm |

## Efficiency

### tier 1: 1 task(s) x 3 run(s) per arm (t1)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.100 (n=3) | $0.400 (n=3) | 4.00x | plain |
| input tokens | 1000 (n=3) | 4000 (n=3) | 4.00x | plain |
| output tokens | 100 (n=3) | 400 (n=3) | 4.00x | plain |
| cache_read tokens | 5000 (n=3) | 20000 (n=3) | 4.00x | plain |
| cache_write tokens | 500 (n=3) | 2000 (n=3) | 4.00x | plain |
| turns | 4.0 (n=3) | 12.0 (n=3) | 3.00x | plain |
| wall s | 20 (n=3) | 80 (n=3) | 4.00x | plain |

Judge cost, kept out of the arm costs: $0.150 total over 6 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s).

### tier 2: 2 task(s) x 3 run(s) per arm (t6, t7)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.175 (n=6) | $0.650 (n=6) | 3.71x | plain |
| input tokens | 1750 (n=6) | 6000 (n=6) | 3.43x | plain |
| output tokens | 175 (n=6) | 600 (n=6) | 3.43x | plain |
| cache_read tokens | 8750 (n=6) | 29667 (n=6) | 3.39x | plain |
| cache_write tokens | 875 (n=6) | 2967 (n=6) | 3.39x | plain |
| turns | 5.5 (n=6) | 16.2 (n=6) | 2.94x | plain |
| wall s | 35 (n=6) | 130 (n=6) | 3.71x | plain |

Judge cost, kept out of the arm costs: $0.250 total over 11 call(s), 1 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s).

## Intent metric (tier 1 only)

```text
bench hm-light-lane@bh0001  harness hs0001  model model-a
task   plain pass  hm pass  plain $/run  hm $/run  plain s   hm s
t1         3/3      3/3           0.100     0.400       20     80
all        3/3      3/3           0.100     0.400       20     80
ratio (CLI cost): 4.0    ratio (transcript price): 4.0
pass rate: plain 3/3 (100%), hm 3/3 (100%)
verdict: met — ratio 4.000 <= target 5 and hm pass rate >= plain
record with:
  uv run hm intent metric record hm_cost_ratio_small --value 4.000 --evidence 'bench hm-light-lane@bh0001 harness hs0001 model model-a: hm $0.400/run vs plain $0.100/run over 1 tasks x 3 runs (CLI-priced ratio 4.0, transcript-priced ratio 4.0); hidden-test pass plain 3/3, hm 3/3; verdict met'
hm_cost_ratio_small=4.000
```
