# Example project

Text before the block, with a table:

| Axis | Note |
|---|---|
| one | first |
| two | second |

<!-- hm-doc-contract:pipeline:start -->
> A different marker pair that publish must leave alone.
<!-- hm-doc-contract:pipeline:end -->

## How it compares

<!-- other:start -->
<!-- hm:eval:start -->
**Measured: plain prompt vs `/hm:`** at harness `hs0001`, same model and budget; n is the number of runs behind each figure. Leads follow the fixed bands in [docs/evals/README.md](docs/evals/README.md); the full scorecard is [docs/evals/RESULTS.md](docs/evals/RESULTS.md).

**What the extra cost buys, tier 1: 1 task(s) x 3 run(s) per arm (t1)**

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (hm/plain) | $0.100 (n=3) | $0.400 (n=3) | 4.00x | plain |
| Δ solved runs | 3 (n=3) | 3 (n=3) | +0 | tie |
| Δ hidden-case pass fraction | 1.00 (n=3) | 1.00 (n=3) | +0.00 | tie |
| Δ regressions per run | 0.00 (n=3) | 0.00 (n=3) | +0.00 | tie |
| Δ new lint+type errors per run | 0.00 (n=3) | 0.00 (n=3) | +0.00 | tie |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | 4.00 (n=3) | 4.33 (n=3) | +0.33 | hm |
| cost per solved run | $0.100 (n=3) | $0.400 (n=3) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |

**What the extra cost buys, tier 2: 2 task(s) x 3 run(s) per arm (t6, t7)**

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (hm/plain) | $0.175 (n=6) | $0.650 (n=6) | 3.71x | plain |
| Δ solved runs | 5 (n=6) | 4 (n=6) | -1 | tie |
| Δ hidden-case pass fraction | 0.93 (n=6) | 0.78 (n=6) | -0.15 | plain |
| Δ regressions per run | 0.17 (n=6) | 0.00 (n=5) | -0.17 | hm |
| Δ new lint+type errors per run | 0.20 (n=5) | 0.80 (n=5) | +0.60 | plain |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | 3.60 (n=5) | 4.20 (n=5) | +0.60 | hm |
| cost per solved run | $0.210 (n=5) | $0.975 (n=4) |  | plain |
| extra $ per additional solved run | | | n/a: no additional solved runs for the extra cost | — |
<!-- hm:eval:end -->
<!-- other:end -->

Text after the block.
