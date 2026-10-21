---
type: review
task_slug: hm-cost-p2
created: 2026-10-21
spec: "[[SPEC-hm-cost-p2]]"
plan: "[[PLAN-hm-cost-p2]]"
rounds: 3
reviewers: [code-reviewer, codex]
summary: Three rounds. Round 1 raised 12 code-reviewer and 2 Codex findings (one shared); 10 accepted and fixed, 3 rejected with authority. Round 2 found one P2 in a round-1 fix, fixed; round 3 found none.
---

# REVIEW — hm-cost-p2

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1 | P1 | src/harness_maker/check.py:1130 | `COMPACT_KEEP` dropped the payload of passing-but-warning sections: CVE `warning`/`added` without a lockfile, `--harness` `score`/`signals_failed`, security `out_of_scope`. Fix: keys added to the keep-set | accepted | SPEC AC-006 (`KEEP ⊇` the named set) and the critique fix "keeps warning keys of passing sections" |
| R2 | P1 | tests/unit/test_hm_cost_p2_check.py:63 | AC-002 drift assertions held without drift: every fixture AC was pending and had no runner, so `ac` already failed. Fix: `test_ac_002_drift_alone_fails_a_passing_section[check, red]`: the same project exits 0 with a matching JSON and 1 with a drifted one; dropping the `EXIT_FAILED` promotion fails both | accepted | SPEC AC-002 oracle |
| R3 / C2 | P2 | src/harness_maker/spec_machine.py:1006 | An int mapping key passes the JSON check, is written as a string and reports permanent drift; mixed keys crash `sort_keys` outside the `try`. Fix: export dumps with `sort_keys` and refuses a row that changes in a round trip (K=2: code-reviewer and Codex) | accepted | SPEC AC-001 "refuses non-JSON values" |
| R4 | P2 | src/harness_maker/spec_machine.py:1762 | `_check_approval` unguarded: a `UnicodeDecodeError`/`ValueError` yaml traced instead of printing the failure line. Fix: falls back to a `malformed` state | accepted | SPEC AC-005 |
| R5 | P2 | src/harness_maker/check.py:1105 | Absent JSON ignored an unexportable row and hinted at `export-golden`, which then fails. Fix: the hint names the AC and row; absent stays non-failing for SPECs whose tests use `load_golden_table` | accepted | SPEC AC-002 (absent is not a failure) |
| R6a | P2 | tests/unit/test_hm_cost_p2_templates.py:126 | AC-010 land check passed through the worktree sweep without the new glob. Fix: the land runs `--manifest-only` | accepted | SPEC AC-010 |
| R6b | P2 | tests/unit/test_hm_cost_p2_templates.py:122 | AC-008 "land accepts a short PLAN" cannot fail, since the land never parses PLAN content | rejected | SPEC AC-008 predicate `wrapup_land_accepts(short_plan_fixture)`: acceptance is the whole contract |
| R7 | P2 | tests/unit/test_hm_cost_p2_templates.py:80 | `_listed` filtered out an extra category without a slash. Fix: every quoted string on the categories line is compared | accepted | SPEC AC-004 |
| R8 | P2 | tests/unit/test_hm_cost_p2_spec_machine.py:46 | Key order and the refusal message were not pinned. Fix: byte comparison against `EXPECTED_TEXT`; stderr names the AC and row | accepted | SPEC AC-001 |
| R9 | P2 | tests/integration/test_hm_cost_p2_bar.py:64 | A tier-1 cell with zero usable runs was never flagged. Fix: every tier-1 task × arm cell is seeded from `bench.load_tasks()` / `bench.ARMS` | accepted | SPEC AC-009 |
| R10a | P2 | src/harness_maker/templates/stages/execute.md.j2:32 | Trim dropped the PLAN read-back. Fix: "Read it back:" restored | accepted | SPEC AC-008 `readback_rule_present` |
| R10b | P2 | src/harness_maker/templates/stages/execute.md.j2:46 | Golden-test line lost the "path relative to the test file" guidance | rejected | Bench evidence: 0 of 12 completed hm runs in the first re-run failed to locate the JSON; the surface allowance had 1 char left (PLAN ADR-006) |
| R11 | P2 | src/harness_maker/templates/stages/spec.md.j2:17 | Step 0 dropped "a code change gets one testable AC". Fix: restored | accepted | SPEC-hm-overhaul-p1 Step 0 rule kept by this SPEC's trims |
| R12 | design | src/harness_maker/spec_machine.py:1669 | `approval` in `check` omits `detail`/`irreversible` | rejected | SPEC AC-005 names `state`, `land`, `gate` |
| C1 | P1 | tests/integration/test_hm_cost_p2_bar.py:91 | AC-009 fixture and re-run rows missing. Fix: P4 was pending at review time | duplicate | PLAN P4 |
| N1 | P2 | src/harness_maker/check.py:1120 | With an unexportable row and a present JSON, `golden_drift.acs` named every AC in the file. Fix: only the unexportable entry is reported; pinned in `test_ac_002_absent_names_an_unexportable_row` (round 2) | accepted | SPEC AC-002 |

Round 3 (N1 fix only): no findings.

## Notes

- Execute trims made room for the ADR-008 property-AC fallback and the restored read-back; the surface ends at +262 claude / +280 codex, inside the approved 263/281 (BASELINE-DELTA-hm-cost-p2.md).
- The second tier-1 bench (on ac1ecd47) was stopped after one run ($0.06) because round-1 fixes changed `src/` and the templates; measuring code that would not land fails AC-009's tree-checked alias.
- Found while running: two tests render into a bare `mkdtemp()` and so write `/tmp/CLAUDE.md` (`tests/structural/test_hm_entrypoint.py:96`, `tests/unit/test_delegation_cli_boundary.py:270`); out of scope here.

## AC-009 re-measure

| run | harness | transcript ratio | CLI ratio | hidden pass plain / hm | verdict |
|---|---|---|---|---|---|
| baseline (2026-10-21, pre-change) | 473ac3f1c0b3 | 14.31 | 12.66 | 15/15 / 15/15 | — |
| first re-run | 60e5502a8641 | 11.14 | 10.13 | 15/15 / 12/15 | **missed** (pass rate; PLAN ADR-008) |
| re-run, counted | 94a6d1f32935 | **12.21** | 11.04 | 15/15 / 15/15 | **met** (≤ 12.5, hm pass ≥ plain) |

- Counted run: `/var/tmp/hm-eval-t1-p2c`, archive `~/hm-eval-archive/hm-eval-t1-p2c-2026-10-21.tgz`, `--jobs 4`; one `runner_error` row from the interrupted serial start is left out by `summarize` (UNUSABLE) and its cell was re-run. No budget-capped, leak-suspect or judge-truncated run.
- The margin is thin (12.21 against 12.5), and the ratio rose from the first re-run's 11.14 because the three stalled runs there cost less than finished ones.
- Not part of the bar, but worse than baseline: new lint+type errors per hm run 0.80 vs plain 0.27 (ruff 0.73); baseline hm was 0.47. Judge scores for hm stay below plain as in the baseline (scope 3.53 vs 4.73; baseline 3.60 vs 4.73).
- The rows replace `docs/evals/results.jsonl` (SPEC constraint), so the README block and `RESULTS.md` no longer carry the a2fe560a tier-2 rows.
