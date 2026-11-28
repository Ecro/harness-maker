# SPEC-cli-bookkeeping (2026-11-27): bar missed

Tier 1, 3 runs per task, `claude-sonnet-5-5`, no judge. plain and hm-new from `6cc93900`
(this branch), hm-main from `593a6ac5`, two batches run at the same time. Rows:
`tests/fixtures/cli_bookkeeping/bench_tier1.jsonl` (`scripts/bench/cli_bookkeeping_rows.py`).

| arm | runs ok | mean cost | median cost | mean wall | median wall | hidden-test passes | hm Bash calls |
|---|---|---|---|---|---|---|---|
| plain | 15 | $0.060 | | 14.0 s | | 15/15 | 0 |
| hm-main | 15 | $0.425 | $0.402 | 135.1 s | 128 s | 14/15 | 11.0 |
| hm-new | 15 | $0.439 | $0.373 | 140.8 s | 125 s | 15/15 | 12.0 |

Bar (fixed in the SPEC before code): cost ≤ 0.93 × hm-main, wall ≤ 0.90 × hm-main, passes ≥
plain, hm Bash calls < hm-main. Only passes held: mean cost +3%, mean wall +4%, calls +1.
Bookkeeping subcommands did drop (`spec_machine` check/approve/approval-status/export/mark: 7.6
-> 5.9 per run), but the mean is set by review-and-fix loops: the two costliest hm-new runs
(t5, $0.761 and $0.636) ran two review rounds and 5-6 `hm check` calls. Medians favour hm-new
(-7% cost, -2% wall), but the pre-registered statistic is the mean. Cost ratio vs plain: hm-new
7.36x, hm-main 7.12x.
