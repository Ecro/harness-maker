---
type: review
task_slug: price-table-current-models
created: 2026-11-16
spec: "[[SPEC-price-table-current-models]]"
plan: "[[PLAN-price-table-current-models]]"
rounds: 2
reviewers: [code-reviewer]
summary: "Two code-reviewer rounds: 14 findings (2 major, 6 minor, 6 nit), then 4 (2 minor, 2 nit). Fifteen accepted and fixed, two rejected with an authority, one left to the DRI as information; nothing unresolved."
---

# REVIEW — price-table-current-models

Two code-reviewer rounds on the uncommitted diff. The reviewer priced about 80 id shapes (123 in
round 2, including `cache_diagnostics`) through HEAD's table and the working copy, rebuilt the 30
recorded rows from `git show HEAD`, and recomputed the golden dollars and the corrected ratios by
hand. Verified without defect: every golden row; the 30 rows differ from HEAD only in
`transcript_cost_usd`, `transcript_cost_usd_table_v3` and `price_table_version`; CLI and transcript
ratios are both 6.98425; the 179-row claim (178 within 0.2%, 79 with subagent turns); p2 11.04, p3
10.267, p4 9.437 and 6.996; tier-3 diagnostic $22.18 at table 3, $17.71 repriced, $17.72 by the
CLI; tier 2 9.362 and 7.611 from the project file. The approval stamps of the five older SPECs whose
prose was edited still validate. No `Do not change` path is touched. The cross-model second opinion
was requested once and skipped (`CLI not installed: codex`). The round-2 fixes (H1, H3, H4) follow
the reviewer's stated fix and were not sent for a third round.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | major | tests/unit/test_bench_scripted_dri.py:39 | The new row field made an existing test red: only one of two pinned key sets was widened. Fix: both pins carry the two new keys and still pin the exact set | accepted | SPEC-hm-eval-scripted-dri AC-007 |
| F2 | major | src/harness_maker/economics.py (`resolve_model_family`) | The new `fable-5-2` key is a substring of `claude-fable-5-20260401`, so a dated Fable 5 turn moved to the 5.2 card ($0.935 to $0.742 on the test turn) with no trace. Fix: `model_key_end`, a key ending in a digit does not match right before another digit; shared with `cache_diagnostics`. AC-003 gained dated Fable 5 rows | accepted | SPEC S4, AC-003 |
| F3 | minor | specs/SPEC-hm-cost-p5.md | "hm's transcript total was about 8% too high" was the ratio's inflation, not the dollars'. Fix: 19% for hm, 10% for plain | accepted | recomputed from the rows |
| F4 | minor | src/harness_maker/step_sensitivity.py:163 | The tier-2 figures (9.36x, 7.61x) cannot be reproduced from the repository. Fix: the SPEC names their source, a project file outside the repository; round 2 confirmed the figures from that file | accepted | SPEC Refinement Decisions |
| F5 | minor | scripts/bench_light_lane.py (`transcript_cost`) | The bench, where the wrong number was recorded, dropped the new trace. Fix: `Spend` and the row carry `family_priced_turns` and the run warns | accepted | SPEC S3 |
| F6 | minor | scripts/bench_light_lane.py (`MIXED_FIELDS`) | `price_table_version` is written but not enforced, so an `--out` resumed under a new table mixes two | rejected | SPEC Non-Goals: the row records the fact; refusing a resume or changing the pre-registered verdict rule is the DRI's decision |
| F7 | minor | .claude/intent/metrics.yaml | The latest `hm_cost_ratio_small` record is still 7.563. Fix: recorded at wrapup, now named in the PLAN scope | accepted | wrapup Step 5 |
| F8 | minor | specs/SPEC-price-table-current-models.golden.json | Golden gaps: prose named `claude-haiku-5-6` but no row tested it; AC-003 covered 6 of 13 rows; no long-prompt row on a dated or `[1m]` id; a dotted version was not marked. Fix: rows added, `_NEXT_VERSION` accepts a dot, a non-AC test covers the long-prompt card through `fallback_model` | accepted | SPEC AC-002..004 |
| F9 | nit | src/harness_maker/economics.py | Two comments still said the flag means a bare family row only. Fix: reworded | accepted | style |
| F10 | nit | docs/evals/README.md:160 | "means the price table is wrong" claimed more than the data shows. Fix: "suggests" | accepted | style |
| F11 | nit | SPEC Intent; CHANGELOG.md | "Fit as well as the rest" and "equals the CLI total" were ahead of the data. Fix: the residuals are stated; "within 0.5%" | accepted | recomputed from the rows |
| F12 | nit | specs/SPEC-hm-cost-p4.md | The quoted 7.674 does not reproduce (the rows give 7.669). Fix: both figures stated | accepted | history rows |
| F13 | nit | specs/SPEC-hm-cost-p5.md | The Intent's old figures were not covered by the correction note. Fix: covered | accepted | style |
| F14 | nit | docs/evals/results.jsonl | The repriced rows placed the new keys before `transcript_turns`; `_record` writes after it. Fix: same order | accepted | style |
| H1 | minor | src/harness_maker/economics.py (`model_key_end`) | The digit guard also applied to bare family keys, so a free-text `price_model: sonnet4.5` stopped resolving and fell to the opus rate. Fix: the guard applies only to a key that ends in a digit; test `test_a_key_ending_in_a_digit_does_not_match_before_a_digit` | accepted | SPEC S4 |
| H2 | minor | work-docs/PLAN-price-table-current-models.md (ADR-006) | The matching rule that an older ADR-002 kept unchanged was narrowed on an agent decision, and the re-approval is stamped by the agent | accepted | Reported to the DRI in the PR notes and the thread reply; no code change. After H1 the rule changes the result only for ids where a digit-ending key is directly followed by a digit |
| H3 | nit | tests/unit/test_price_table_current_models.py | The bench test asserts on `Spend`, not on a row, and the warning called the price "unreliable" although an old model on its family row triggers it too. Fix: the warning asks to check the rates. The row-level assertion is not added | rejected | The two key-set pins prove the key is in the row and the `Spend` test proves the count; the single assignment between them does not justify a `run_cell` fixture |
| H4 | nit | specs/SPEC-hm-cost-p5.md | The correction gave tier 1's 9.44x for a figure the Intent states for both tiers. Fix: tier 2's 9.36x added | accepted | project file rows |

Found by the full test run rather than the reviewer: nothing further (the only red test was F1).

The approval stamp on this SPEC reads `approved_by: Claude`: the agent stamped it on the DRI's card
choice ("둘 다 고치기") and the standing instruction of 2026-11-10, and re-stamped it after the
golden rows grew in review. The SPEC's Refinement Decisions say so.
