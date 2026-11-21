---
type: spec
task_slug: review-measurement-fixes
status: approved
created: 2026-11-21
tags: [review, measurement, execute, cleanup]
test_framework: pytest
interview_rounds: 2
summary: Make review_effect read the severities REVIEW tables actually carry, add three one-line execute rules (gate retry cap, pre-existing disposition, flaky tests), and retire the dead two_pass_review module.
---

# SPEC — review-measurement-fixes

## Intent

Triggered by the Claude Code team's verification post (2026-11-16): a reviewer is only tunable if its results are measured, a failing check loop should hand off to the human after three rounds, a pre-existing bug is tagged rather than fixed in scope, and flaky tests are fixed or deleted, never retried. Measured against this repo: `review_effect` counts every `major`/`minor`/`nit` severity as `unrecognized` (114 of 413 REVIEW rows across 19 docs; the 2026-11-19 land recorded `unrecognized: 13, severe_accepted: 0`), because execute Step 6 never names the severity vocabulary. The other three rules are absent from the rendered stages. `two_pass_review` (500 lines, `manual-dispatch`) is called by no rendered stage — the purpose statement says devices that do not earn their keep are removed.

## Outcomes

- `review_effect` maps the word severities to the P scale, so historical REVIEW tables count.
- Rendered `/hm:execute` names the P0–P3 severity scale for the REVIEW table, caps a failing `hm check` at three runs before handing to the DRI, keeps `pre-existing` findings out of the fix loop, and states the flaky-test rule.
- `hm check` accepts a `pre-existing` disposition; the reviewer prompt can mark a finding pre-existing.
- `harness_maker.two_pass_review` and `hm two_pass_review` no longer exist.

## In-Scope Scenarios

- **S1 (normal)** Given a REVIEW table with `major` and `minor` severities, When `wrapup_land` records the review, Then the counts land under P1 and P2 and `unrecognized` is 0.
- **S2 (edge)** Given a REVIEW row with severity `—` or `design`, When parsed, Then it is still `unrecognized` (no guessing beyond the fixed map).
- **S3 (normal)** Given a reviewer finding the diff did not introduce, When execute writes the REVIEW, Then its disposition is `pre-existing`, it is not fixed in the loop, and `hm check` passes it.
- **S4 (failure)** Given `hm check` exits 1 three times in a row at Bind, When the third fails, Then execute stops retrying and hands what it names to the DRI.

## Non-Goals

- Second-opinion ledger repair: the near-empty ledger is a fresh clone (2026-11-19 22:36, gitignored history lost) plus an uninstalled `codex` CLI on this machine, not a code defect (DRI, round 1).
- A `/hm:health` warning for a missing second-opinion CLI.
- Re-tagging historical REVIEW documents.
- Changing `max_review_rounds`, the step-sensitivity registry, or any heading text.
- Diff-triggered checklists, commit observe/enforce gates, E2E smoke steps.

## Constraints

| Constraint | Value |
|---|---|
| Test framework | pytest |
| Language | Python 3.12+, `mypy --strict`, `ruff` |
| Rendered headings | unchanged (step-sensitivity registry test must stay green) |
| Prompt size | execute.md stays within the skill/agent line budgets |
| Snapshots | rendered-template snapshots regenerate deliberately, not by hand |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | Add `pre-existing` to the REVIEW-table disposition vocabulary accepted by `hm check` | schema/file format/storage layout | Additive; older REVIEW docs still parse. DRI chose it over `rejected`+authority so rejection counts stay honest (round 1). |
| IRR-002 | Remove `hm two_pass_review` (`redact`, `merge`) and `harness_maker.two_pass_review` | public API/CLI contract | No rendered stage or skill invokes it; DRI approved removal (round 1). |

## Acceptance Criteria

### AC-001: review_effect normalises word severities to the P scale

`parse_review` maps `critical`/`blocker` → P0, `major` → P1, `minor` → P2, `nit` → P3 (case-insensitive, decoration stripped); P0–P3 behave as before; anything else stays `unrecognized`.

### AC-002: Rendered execute names the P0–P3 severity scale

### AC-003: Rendered execute caps a failing hm check at three runs

### AC-004: Rendered execute keeps pre-existing findings out of the fix loop

### AC-005: Rendered execute states the flaky-test rule

### AC-006: hm check accepts the pre-existing disposition

Review-table gating is unchanged for every other disposition; `pre-existing` passes without an authority.

### AC-007: Code reviewer can mark a finding pre-existing

### AC-008: two_pass_review is gone

## Verification

All AC tests live in `tests/unit/test_ac_review_measurement_fixes.py`.

| Scenario | Mode | Test |
|---|---|---|
| S1, S2 | unit | `test_ac_001_*` |
| S3 | unit | `test_ac_004_*`, `test_ac_006_*`, `test_ac_007_*` |
| S4 | unit (rendered text) | `test_ac_003_*` |
| — | unit | `test_ac_002_*`, `test_ac_005_*`, `test_ac_008_*` |

## Open Questions

none

## Refinement Decisions

- **Intent link:** none — HM-LIGHT-LANE (the only proposed intent) is about cost lanes; this task does not plainly serve it. Undo: minutes.
- **Retry cap is a literal 3**, not `max_review_rounds`: different loop (deterministic gate vs review), and reusing the knob would couple them. Undo: one line.
- **Severity map** follows code-reviewer's scale (P0 breaks AC/data/security, P1 real bug, P2 maintainability) and `review_effect`'s P3 slot: `major` is a real bug (P1), `minor` maintainability (P2), `nit` P3. `critical`/`blocker` → P0. No fuzzy matching. Undo: one dict.
- **Flaky deletion record** goes into a PLAN ADR (`Decided by: agent`), which wrapup already surfaces in the Understanding block — no new mechanism. Undo: one line.
- **Pre-existing needs no authority** (unlike `rejected`): the claim is accepted as real, only its origin differs. Undo: one condition.
- **Second-opinion skill's `two_pass_review` mention** is deleted with the module (it only said "this is not the control").
