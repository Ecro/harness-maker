---
type: spec
task_slug: existing-parametrize-all
status: approved
created: 2026-11-28
tags: [execute, maintainability]
test_framework: pytest
interview_rounds: 1
summary: Any AC test's cases go into a test that already parametrizes the same call, not only golden rows.
---

# SPEC — existing-parametrize-all

## Intent

After SPEC-test-shape-rules (#94), 4 of the 7 remaining maintainability losses to plain + tests stayed losses when re-judged. In t7-1, the decisive evidence on both orders was a new `test_week_out_of_order_or_repeated` that copies the existing `test_invalid` body instead of adding two cases to its list. The counterfactual (cases moved into `test_invalid`'s list, nothing else changed) made that evidence disappear. A second cause, unrelated to this one, kept the pair at B. Execute's "paste into an existing parametrize" rule covers only a parametric AC's golden rows. A mechanical AC's raising cases have no such rule. (`/mnt/project-files/hm-blog-cost/CAUSES-maintainability-2026-11-28.md`, "The last 7 losses".) The DRI chose this one confirmed cause and no other.

## Outcomes

- A test written by `/hm:execute` for any AC adds its cases to a test in the file that already parametrizes the same call, rather than creating a parallel test.

## In-Scope Scenarios

- S1 (normal): Given `test_invalid` parametrizes `parse_duration` raising cases, when a mechanical AC adds raising cases, then they go into that list.
- S2 (render): Given the rendered `/hm:execute` (Claude and Codex), then it states the rule for every AC test and keeps every SPEC-test-shape-rules and SPEC-behaviour-named-tests phrase.

## Non-Goals

- One-row golden tables (weak evidence: 5 of 39, one loss) and a finalize gate for them.
- The model's own code and test style (t5-2, t9-2), and combining boundary and sweep checks into one test (t7-1's second cause).

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| stage size | execute within every size ratchet; any growth re-pinned with the reason |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: execute puts every AC's cases into an existing parametrize of the same call
The rendered `/hm:execute` (Claude and Codex) says that cases for a call that a test there already parametrizes go into its list, one per line, not a new test. It says this before the AC-type clauses, so it covers mechanical ACs too. It keeps the SPEC-test-shape-rules and SPEC-behaviour-named-tests execute phrases.
- oracle_source: golden. Phrase fixed here before the template change.

## Verification

| scenario | mode | AC |
|---|---|---|
| S1 | manual | bench t7 ×3 + evidence judge |
| S2 | unit | AC-001 |

## Open Questions

none

## Refinement Decisions

- **Text only** (agent-decided): the cause is the missing rule, and the template change is the smallest fix. Undo: one clause.
- **One per line** (agent-decided, after the t7 ×3 bench): t7-3 put its cases into the existing list but left all eight on one 140-character line. The judge's only decisive evidence on both orders was that line (A → B). With only that line wrapped, the pair went to tie (`cf-epa-t7-3-wrap.json`). Hence ", one per line" (+14 chars). Undo: those words.
