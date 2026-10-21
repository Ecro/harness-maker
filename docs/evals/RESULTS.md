# hm eval results

<!-- Written by `uv run python scripts/bench_light_lane.py publish`; do not edit. -->

Plain prompt vs `/hm:` on the `timeparse` fixture. What each line means and how a lead is picked: [README.md](README.md).

| Setup | Value |
|---|---|
| bench_hash | `569e17ef29ab` |
| harness_sha | `94a6d1f32935` |
| runner_hash | `36158f78b3de` |
| agent model | `claude-sonnet-5-5` |
| judge model | `claude-sonnet-5-5` |
| rubric | `hm-eval-judge-v1` |
| ruff | `ruff 0.15.12` |
| mypy | `mypy 1.20.2 (compiled: yes)` |
| tiers | 1 |
| runs per cell | tier 1: 3 |
| runs started | 2026-10-21 to 2026-10-21 |

## What the extra cost buys

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | hm vs plain | Lead |
|---|---|---|---|---|
| cost ratio (cells: mean CLI $/run) | $0.059 (n=15) | $0.652 (n=15) | 12.21x (CLI 11.04x, transcript 12.21x) | plain |
| wall time per run | 24s (n=15) | 5m 17s (n=15) | 13.13x | plain |
| Δ solved runs | 15 (n=15) | 15 (n=15) | +0 | tie |
| Δ hidden-case pass fraction | 1.00 (n=15) | 1.00 (n=15) | +0.00 | tie |
| Δ regressions per run | 0.00 (n=15) | 0.00 (n=15) | +0.00 | tie |
| Δ new lint+type errors per run | 0.27 (n=15) | 0.80 (n=15) | +0.53 | plain |
| traps caught | n/a (n=0) | n/a (n=0) | n/a | n/a |
| Δ judge overall | 4.22 (n=15) | 3.53 (n=15) | -0.69 (single-sample scores, judge noise ±0.67; tie band 0.25 over 15 pairs) | plain |
| cost per solved run | $0.059 (n=15) | $0.652 (n=15) |  | plain |
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
| ruff_new mean | 0.07 (n=15) | 0.73 (n=15) | plain |
| mypy_new mean | 0.20 (n=15) | 0.07 (n=15) | hm |
| regressions mean | 0.00 (n=15) | 0.00 (n=15) | tie |
| diff_lines mean | 47.27 (n=15) | 135.73 (n=15) | — |
| tests_touched rate | 0.13 (n=15) | 1.00 (n=15) | — |
| judge scope | 4.73 (n=15) | 3.53 (n=15) | plain |
| judge clarity | 3.93 (n=15) | 3.67 (n=15) | plain |
| judge maintainability | 4.00 (n=15) | 3.40 (n=15) | plain |
| judge overall | 4.22 (n=15) | 3.53 (n=15) | plain |

## Efficiency

### tier 1: 5 task(s) x 3 run(s) per arm (t1, t2, t3, t4, t5)

| Metric | plain | hm | hm/plain | Lead |
|---|---|---|---|---|
| cost $/run | $0.059 (n=15) | $0.652 (n=15) | 11.04x | plain |
| input tokens | 7 (n=15) | 72 (n=15) | 10.86x | plain |
| output tokens | 1874 (n=15) | 26883 (n=15) | 14.35x | plain |
| cache_read tokens | 53263 (n=15) | 1337944 (n=15) | 25.12x | plain |
| cache_write tokens | 8751 (n=15) | 69699 (n=15) | 7.96x | plain |
| turns | 3.7 (n=15) | 20.1 (n=15) | 5.39x | plain |
| wall s | 24 (n=15) | 317 (n=15) | 13.13x | plain |

Judge cost, kept out of the arm costs: $0.824 total over 30 call(s), 0 unpriced.

Run flags: plain: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 0 redaction(s) in 0 run(s); hm: 0 budget-capped, 0 leak-suspect, 0 judge-truncated, 187 redaction(s) in 15 run(s).

## Intent metric (tier 1 only)

```text
bench hm-light-lane@569e17ef29ab  harness 94a6d1f32935  model claude-sonnet-5-5
task   plain pass  hm pass  plain $/run  hm $/run  plain s   hm s
t1         3/3      3/3           0.055     0.517       21    235
t2         3/3      3/3           0.056     0.739       21    391
t3         3/3      3/3           0.058     0.532       24    301
t4         3/3      3/3           0.049     0.620       28    322
t5         3/3      3/3           0.077     0.854       27    333
all       15/15    15/15          0.059     0.652       24    317
ratio (CLI cost): 11.04    ratio (transcript price): 12.21
pass rate: plain 15/15 (100%), hm 15/15 (100%)
verdict: missed — ratio 12.205 > target 5
record with:
  uv run hm intent metric record hm_cost_ratio_small --value 12.205 --evidence 'bench hm-light-lane@569e17ef29ab harness 94a6d1f32935 model claude-sonnet-5-5: hm $0.652/run vs plain $0.059/run over 5 tasks x 3 runs (CLI-priced ratio 11.04, transcript-priced ratio 12.21); hidden-test pass plain 15/15, hm 15/15; verdict missed'
hm_cost_ratio_small=12.205
```

## Tier 3

Tasks whose prompt does not hold the answer: it sits in a file of the repo or in an earlier session. t21 is the guard. These rows sit outside the scorecard above.

| Setup | pilot | diagnostic |
|---|---|---|
| tier3_hash | `1f8767cb8b8c` | |
| harness_sha | `20341abe49d2-dirty-764de9af` | `441fe124cc0b-dirty-764de9af` |
| runner_hash | `7abf3fedaa7d` | `7abf3fedaa7d` |
| arms | plain | hm, plain-careful, plain-continue |
| runs started | 2026-10-15 to 2026-10-15 | 2026-10-16 to 2026-10-16 |

Each $ is the CLI cost per run, which excludes subagent spend, so an hm $ understates what the run spent.

### Plain pilot

Pre-registered drop rule: a task drops when plain solves 2 or more of 3 runs; the guard is exempt. Tier 3 needs at least 4 surviving tasks (T).

| Task | plain solved | hidden cases | $/run | wall/run | Pilot |
|---|---|---|---|---|---|
| t13 | 3/3 | 12/12 | $0.061 | 17s | drop |
| t14 | 3/3 | 15/15 | $0.075 | 21s | drop |
| t15 | 3/3 | 12/12 | $0.070 | 18s | drop |
| t16 | 3/3 | 15/15 | $0.096 | 28s | drop |
| t17 | 3/3 | 9/9 | $0.102 | 35s | drop |
| t18 | 2/3 | 11/12 | $0.110 | 57s | drop |
| t19 | 3/3 | 15/15 | $0.143 | 40s | drop |
| t20 | 0/3 | 12/18 | $0.130 | 37s | keep |
| t21 | 3/3 | 9/9 | $0.161 | 48s | guard |

Plain solved 23 of 27 pilot runs. **Outcome: T = 1 (t20), below the 4 surviving tasks the rule needs, so tier 3 is inconclusive.**

**The per-task code-quality claim is withdrawn under the pre-registered rule: an inconclusive tier 3 counts as "plain cannot be made to fail fairly", so this eval makes no claim that `/hm:` writes better code than a plain prompt on any task.**

### hm diagnostic on t20, t21 (diagnostic, not a verdict)

Asked by the DRI to see whether `/hm:` carries state across fresh headless sessions. It is not the pre-registered full run, too small to decide anything, and it changes no outcome above.

| Task | Arm | Solved | hidden cases | $/run | wall/run |
|---|---|---|---|---|---|
| t20 | hm | 2/3 | 17/18 | $3.015 | 17m 26s |
| t20 | plain-careful | 2/3 | 14/18 | $0.192 | 48s |
| t20 | plain-continue | 3/3 | 18/18 | $0.109 | 36s |
| t21 | hm | 1/2 | 4/6 | $3.406 | 15m 24s |
| t21 | plain-careful | 3/3 | 9/9 | $0.213 | 49s |
| t21 | plain-continue | 3/3 | 9/9 | $0.107 | 36s |

| Run | Solved | hidden cases | Sessions (status, $, wall) | $ | wall |
|---|---|---|---|---|---|
| t20 hm 1 | yes | 6/6 | ok, $2.031, 25m 44s; ok, $1.483, 5m 12s | $3.514 | 30m 56s |
| t20 hm 2 | yes | 6/6 | ok, $1.192, 4m 54s; ok, $1.185, 4m 15s | $2.376 | 9m 09s |
| t20 hm 3 | wrong | 5/6 | ok, $1.865, 7m 27s; ok, $1.291, 4m 46s | $3.156 | 12m 13s |
| t20 plain-careful 1 | yes | 6/6 | ok, $0.089, 21s; ok, $0.118, 30s | $0.207 | 51s |
| t20 plain-careful 2 | wrong | 2/6 | ok, $0.095, 22s; ok, $0.070, 16s | $0.164 | 38s |
| t20 plain-careful 3 | yes | 6/6 | ok, $0.123, 30s; ok, $0.082, 25s | $0.205 | 54s |
| t20 plain-continue 1 | yes | 6/6 | ok, $0.076, 21s; ok, $0.037, 17s | $0.113 | 38s |
| t20 plain-continue 2 | yes | 6/6 | ok, $0.074, 21s; ok, $0.043, 19s | $0.117 | 40s |
| t20 plain-continue 3 | yes | 6/6 | ok, $0.061, 16s; ok, $0.035, 15s | $0.096 | 31s |
| t21 hm 1 | yes | 3/3 | ok, $2.038, 9m 16s; ok, $1.902, 8m 18s | $3.940 | 17m 34s |
| t21 hm 2 | wrong | 1/3 | ok, $1.713, 7m 31s; ok, $1.160, 5m 44s | $2.873 | 13m 15s |
| t21 plain-careful 1 | yes | 3/3 | ok, $0.104, 24s; ok, $0.103, 27s | $0.207 | 51s |
| t21 plain-careful 2 | yes | 3/3 | ok, $0.102, 23s; ok, $0.109, 24s | $0.210 | 47s |
| t21 plain-careful 3 | yes | 3/3 | ok, $0.104, 24s; ok, $0.119, 27s | $0.222 | 51s |
| t21 plain-continue 1 | yes | 3/3 | ok, $0.074, 20s; ok, $0.035, 16s | $0.109 | 36s |
| t21 plain-continue 2 | yes | 3/3 | ok, $0.070, 21s; ok, $0.034, 17s | $0.103 | 38s |
| t21 plain-continue 3 | yes | 3/3 | ok, $0.073, 20s; ok, $0.035, 16s | $0.108 | 36s |

### Notes

**What each hm run carried across the session boundary.** Read from the transcripts of both
sessions of every run. "Saved" is what session 1 left on disk, "used" is what session 2 read
before it changed code. No run wrote or read an intent entry or a world-model digest, and no
SessionStart context named the earlier work: session 2 found it by listing `specs/` and reading
the files.

| Run | Session 1 saved | Session 2 found and used | t20 trap / t21 guard | Holds and stalls |
|---|---|---|---|---|
| t20 hm 1 | SPEC (full lane), PLAN, REVIEW, code and tests. The SPEC's Non-Goals hold the whole deferred step: `lang` defaults to `en`, joiner `", "` for `en` and `" "` for `ko`, an unknown `lang` raises before formatting | Read that SPEC first, wrote a step-2 SPEC from it | Avoided: Korean joiner and `lang` both right | Session 1 sat idle for about 18 minutes after its verify report, waiting on its own 20-minute `ScheduleWakeup` fallback, which then fired a no-op review. That is most of the run's 31-minute wall |
| t20 hm 2 | SPEC (light lane), PLAN, REVIEW. The hand-off is one line, "`", "` vs `" "` joiner", which does not say which language gets which | Read the SPEC and chose `en` `", "`, `ko` `" "` from the order of that line | Avoided, on an ambiguous note | none |
| t20 hm 3 | SPEC (full lane), PLAN, REVIEW. The SPEC says step 2 exists and lists open questions, but drops the joiner rule and the unknown-`lang` ordering | Read the SPEC and its machine file, chose `", "` for every language, and filed the Korean joiner as an open question for the DRI | **Hit**: `"1시간, 30분"` where the rule says `"1시간 30분"` (`test_korean_uses_its_own_joiner`) | The open question waited for an answer that a headless run cannot give |
| t21 hm 1 | SPEC (full lane), PLAN, REVIEW, a new `D-11` in `docs/DECISIONS.md`, and a project fact in `.claude/memory/wiki.md` (through Maker) stating the 30-day cap | Grepped `D-11` and the wiki fact, superseded `D-11` with `D-12`, retired the fact, lifted the cap | Guard kept (`parse_duration` unchanged); solved | none |
| t21 hm 2 | SPEC (full lane), PLAN, REVIEW for the capped `parse_iso_duration` | Read that SPEC and wrote a step-2 SPEC that lifts the cap | Guard kept, but the run is not solved: `parse_clock` was never written and the cap stayed | **Decided by a hold.** The test-reviewer gate (A.5) failed twice, execute stopped as blocked and asked the operator to pick a path. Nobody answers in `-p`, so the session ended with only tests on disk |
| t21 hm 3 | not run | | | The runner stopped scheduling when recorded spend passed the run's $15 cap |

**Approval holds.** Four of the five runs wrote full-lane SPECs that autopilot could not get
approved headless ("no approval stamped, so the land hold covers IRR-..."). The bench grades the
work tree and nothing has to land, so the land hold changed no grade. The hold that changed a
grade was t21 hm 2's blocked test-review gate. No session hit the runner's 1800-second timeout.

**Controls on the same two tasks.** `plain-continue` (the second session resumes the first
conversation) solved t20 3/3 and t21 3/3 at under a fifteenth of hm's cost per run, so on these
tasks hm's saved state did not beat simply keeping the conversation. `plain-careful` solved t20 2/3
with no saved state at all: its second session wrote `" "` for Korean, which is the natural
Korean convention, so t20's joiner can be guessed as well as remembered. Its one failure never
added `lang`. In the pilot, plain failed t20 the same two ways: `", "` for Korean twice, no `lang`
once.

**Cost.** Each hm row's cost is the CLI total, which leaves out subagent spend; the
transcript-priced total for the 17 diagnostic rows is about $22.2 against $17.7 by the CLI.

**Correction (plain-continue cost).** The first publish of these rows put `plain-continue` at
$0.179/run on each task; the right figures are $0.109 (t20) and $0.107 (t21). A resumed
session's `total_cost_usd` is the running total of the whole conversation, not that session's
own spend, and the runner added the two sessions' totals, so session 1 was counted twice. The
six rows were recomputed exactly from their recorded per-session totals: the run's cost is the
last running total, and each session's own cost is the difference from the one before (the
DRI path's rule), with the raw total kept as `cli_total_usd`. No row was estimated. The CLI
total for the 17 rows fell from $18.1 to $17.7. The hm and `plain-careful` rows start a fresh
process per session, so their summed totals were right and are unchanged.

**Fairness notes.**

- The plain pilot ran before the DRI signed the tier-3 hash; the rows record the hash that was
  later signed (`1f8767cb8b8c`), so the piloted bytes are the signed bytes.
- `docs/DECISIONS.md` in the shared base (D-1 to D-10) helped plain: the answer to several tasks
  is a decision record, and a plain session reads that small file whole. It is part of why plain
  solved t13-t19 and the tasks dropped.
- t18's oracle is strict: one hidden test parses `timeparse/parse.py` and fails while the old
  token loop (`finditer`) is still called. Plain's one t18 failure is exactly that, a structure
  miss with unchanged behaviour, and t18 dropped either way (2 of 3).
- The pilot and the diagnostic ran from a checkout with one untracked session file, so both
  record a `-dirty-764de9af` harness sha; the diagnostic's base commit is the rebased branch.
