# hm eval results

<!-- Written by `uv run python scripts/bench_light_lane.py publish`; do not edit. -->

Plain prompt vs `/hm:` on the `timeparse` fixture. What each line means and how a lead is picked: [README.md](README.md).

| Setup | Value |
|---|---|
| bench_hash | `b38467bb5200` |
| harness_sha | `d48bdc0b6b49` |
| runner_hash | `6bc405d9e0df` |
| agent model | `claude-sonnet-5-5` |
| judge model | n/a (no judged runs) |
| rubric | `hm-eval-judge-v1` (no judged runs) |
| ruff | n/a (not recorded) |
| mypy | n/a (not recorded) |
| tiers | 1 |
| runs per cell | tier 1: 3 |
| runs started | 2026-10-14 to 2026-10-14 |

> Pre-eval seed: these rows predate the quality signals (no tier, tokens, outcome, quality or judge fields), so every quality line reads n/a (n=0).

## What the extra cost buys

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (cells: mean CLI $/run) | $0.058 (n=15) | $0.707 (n=15) | 13.79x (CLI 12.29x, transcript 13.79x) | plain |
| Δ solved runs | 15 (n=15) | 9 (n=15) | -6 | plain |
| Δ hidden-case pass fraction | 1.00 (n=15) | 0.64 (n=15) | -0.36 | plain |
| Δ regressions per run | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ new lint+type errors per run | n/a (n=0) | n/a (n=0) | n/a | n/a |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | n/a (n=0) | n/a (n=0) | n/a | n/a |
| cost per solved run | $0.058 (n=15) | $1.179 (n=9) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

## Quality

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | Lead |
|---|---|---|---|
| runs | 15 | 15 | — |
| hidden all-pass | 15 (n=15) | 9 (n=15) | plain |
| hidden-case pass fraction | 1.00 (n=15) | 0.64 (n=15) | plain |
| solved | 15 (n=15) | 9 (n=15) | plain |
| wrong | n/a (n=0) | n/a (n=0) | n/a |
| stalled | n/a (n=0) | n/a (n=0) | n/a |
| ruff_new mean | n/a (n=0) | n/a (n=0) | n/a |
| mypy_new mean | n/a (n=0) | n/a (n=0) | n/a |
| regressions mean | n/a (n=0) | n/a (n=0) | n/a |
| diff_lines mean | n/a (n=0) | n/a (n=0) | — |
| tests_touched rate | n/a (n=0) | n/a (n=0) | — |
| judge scope | n/a (n=0) | n/a (n=0) | n/a |
| judge clarity | n/a (n=0) | n/a (n=0) | n/a |
| judge maintainability | n/a (n=0) | n/a (n=0) | n/a |
| judge overall | n/a (n=0) | n/a (n=0) | n/a |

## Efficiency

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.058 (n=15) | $0.707 (n=15) | 12.29x | plain |
| input tokens | n/a (n=0) | n/a (n=0) | n/a | n/a |
| output tokens | n/a (n=0) | n/a (n=0) | n/a | n/a |
| cache_read tokens | n/a (n=0) | n/a (n=0) | n/a | n/a |
| cache_write tokens | n/a (n=0) | n/a (n=0) | n/a | n/a |
| turns | 3.6 (n=15) | 8.5 (n=15) | 2.35x | plain |
| wall s | 16 (n=15) | 159 (n=15) | 9.95x | plain |

Judge cost, kept out of the arm costs: $0.000 total over 0 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s).

## Intent metric (tier 1 only)

```text
bench hm-light-lane@b38467bb5200  harness d48bdc0b6b49  model claude-sonnet-5-5
task   plain pass  hm pass  plain $/run  hm $/run  plain s   hm s
t1         3/3      0/3           0.055     0.266       17     69
t2         3/3      1/3           0.055     0.652       14    183
t3         3/3      3/3           0.059     0.908       16    181
t4         3/3      2/3           0.049     0.661       13    132
t5         3/3      3/3           0.069     1.050       21    230
all       15/15     9/15          0.058     0.707       16    159
ratio (CLI cost): 12.29    ratio (transcript price): 13.79
pass rate: plain 15/15 (100%), hm 9/15 (60%)
verdict: missed — ratio 13.790 > target 5
record with:
  uv run hm intent metric record hm_cost_ratio_small --value 13.790 --evidence 'bench hm-light-lane@b38467bb5200 harness d48bdc0b6b49 model claude-sonnet-5-5: hm $0.707/run vs plain $0.058/run over 5 tasks x 3 runs (CLI-priced ratio 12.29, transcript-priced ratio 13.79); hidden-test pass plain 15/15, hm 9/15; verdict missed'
hm_cost_ratio_small=13.790
```
