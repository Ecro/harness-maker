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
| wall time per run | 18s (n=15) | 7m 59s (n=15) | 26.16x | plain |
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
| wall time per run | 13s (n=21) | 4m 26s (n=21) | 19.84x | plain |
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

## Tier 3

Tasks whose prompt does not hold the answer: it sits in a file of the repo or in an earlier session. t21 is the guard. These rows sit outside the scorecard above.

| Setup | pilot | diagnostic |
|---|---|---|
| tier3_hash | `1f8767cb8b8c` | |
| harness_sha | `20341abe49d2-dirty-764de9af` | `441fe124cc0b-dirty-764de9af` |
| runner_hash | `7abf3fedaa7d` | `7abf3fedaa7d` |
| arms | plain | hm, plain-careful, plain-continue |
| runs started | 2026-10-15 to 2026-10-15 | 2026-10-16 to 2026-10-16 |

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
| t20 | plain-continue | 3/3 | 18/18 | $0.179 | 36s |
| t21 | hm | 1/2 | 4/6 | $3.406 | 15m 24s |
| t21 | plain-careful | 3/3 | 9/9 | $0.213 | 49s |
| t21 | plain-continue | 3/3 | 9/9 | $0.179 | 36s |

| Run | Solved | hidden cases | Sessions (status, $, wall) | $ | wall |
|---|---|---|---|---|---|
| t20 hm 1 | yes | 6/6 | ok, $2.031, 25m 44s; ok, $1.483, 5m 12s | $3.514 | 30m 56s |
| t20 hm 2 | yes | 6/6 | ok, $1.192, 4m 54s; ok, $1.185, 4m 15s | $2.376 | 9m 09s |
| t20 hm 3 | wrong | 5/6 | ok, $1.865, 7m 27s; ok, $1.291, 4m 46s | $3.156 | 12m 13s |
| t20 plain-careful 1 | yes | 6/6 | ok, $0.089, 21s; ok, $0.118, 30s | $0.207 | 51s |
| t20 plain-careful 2 | wrong | 2/6 | ok, $0.095, 22s; ok, $0.070, 16s | $0.164 | 38s |
| t20 plain-careful 3 | yes | 6/6 | ok, $0.123, 30s; ok, $0.082, 25s | $0.205 | 54s |
| t20 plain-continue 1 | yes | 6/6 | ok, $0.076, 21s; ok, $0.113, 17s | $0.190 | 38s |
| t20 plain-continue 2 | yes | 6/6 | ok, $0.074, 21s; ok, $0.117, 19s | $0.191 | 40s |
| t20 plain-continue 3 | yes | 6/6 | ok, $0.061, 16s; ok, $0.096, 15s | $0.157 | 31s |
| t21 hm 1 | yes | 3/3 | ok, $2.038, 9m 16s; ok, $1.902, 8m 18s | $3.940 | 17m 34s |
| t21 hm 2 | wrong | 1/3 | ok, $1.713, 7m 31s; ok, $1.160, 5m 44s | $2.873 | 13m 15s |
| t21 plain-careful 1 | yes | 3/3 | ok, $0.104, 24s; ok, $0.103, 27s | $0.207 | 51s |
| t21 plain-careful 2 | yes | 3/3 | ok, $0.102, 23s; ok, $0.109, 24s | $0.210 | 47s |
| t21 plain-careful 3 | yes | 3/3 | ok, $0.104, 24s; ok, $0.119, 27s | $0.222 | 51s |
| t21 plain-continue 1 | yes | 3/3 | ok, $0.074, 20s; ok, $0.109, 16s | $0.183 | 36s |
| t21 plain-continue 2 | yes | 3/3 | ok, $0.070, 21s; ok, $0.103, 17s | $0.173 | 38s |
| t21 plain-continue 3 | yes | 3/3 | ok, $0.073, 20s; ok, $0.108, 16s | $0.180 | 36s |

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
transcript-priced total for the 17 diagnostic rows is about $22.2 against $18.1 by the CLI.

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
