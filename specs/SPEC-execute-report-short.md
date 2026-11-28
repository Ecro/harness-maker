---
type: spec
task_slug: execute-report-short
status: approved
created: 2026-11-28
tags: [owner-attention, execute, bench]
test_framework: pytest
interview_rounds: 0
summary: End /hm:execute with a three-line report (hm check result, REVIEW path, what the DRI must decide) instead of a full summary, because the wrapup change card already carries what was verified and the changed assumptions; the owner reads less for the same understanding.
---

# SPEC — execute-report-short

## Intent

The saga bench (2026-11-28, SPEC-change-card v2) splits the owner's reading per shipped change:
task turn 2,245, replies 1,988, execute report 1,459, wrapup card 1,135 chars. Plain-discipline reads
task 2,678 + replies 1,934 and nothing else. So hm's excess over discipline is the two closing
messages, not the design brief. The execute report repeats what the land card says one step later:
the hm check result, AC tests, review findings and their dispositions, and changed assumptions.
The DRI said "진행해" to the next lever (2026-11-28 07:13Z).

## Outcomes

- The rendered `/hm:execute` (Claude and Codex) ends with a report of at most three lines: the
  `hm check` result, the REVIEW path, and the wrapup next step. It also lists every `unresolved` row,
  every P0/P1 `pre-existing` row and every stop reason, because those need the DRI before wrapup.
  It says to add no other summary, because the wrapup change card carries the rest.
- owner_read_ratio_saga drops below 1.48 while the quiz stays at or above 0.73 and no trap or
  escaped-regression count gets worse.

## In-Scope Scenarios

- S1 (normal): execute finishes clean. The closing message is about three lines: the gate passed,
  the REVIEW path, and "`/hm:wrapup <slug>` next". There is no phase or finding walkthrough.
- S2 (edge): one finding stays `unresolved`, or the review records a P0/P1 `pre-existing` row.
  Each one is listed by id and summary, because the DRI decides it before wrapup.
- S3 (failure): `hm check` fails, or a contract boundary is crossed. The stop and its reason are
  reported as today. Short means no summary; it never means hiding a failure.

## Non-Goals

- The design brief and interview rounds (the task turn is already shorter than discipline's).
- The wrapup card and its text after the card.
- The REVIEW file contents.
- Maker's Advance rule.

## Constraints

| constraint | source |
|---|---|
| Rendered execute stays within its stage budget (7,773 base; raised only by this change's measured growth) | tests/unit/test_overhaul_p1_surface.py |
| Every failure, stop, `unresolved` and P0/P1 `pre-existing` row is still reported | CLAUDE.md north star (owner understanding) |
| Bench needs IS_SANDBOX=1 and --out under /var/tmp | project memory |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: execute closes with a short report and no other summary

Rendered `commands/hm/execute.md` (Claude) and `.agents/skills/hm-execute/SKILL.md` (Codex), Production preset, have these properties:
- They no longer say "Print the phases done".
- They name the `hm check` result, the REVIEW path, `unresolved`, P0/P1 `pre-existing`, "at most three lines" and "no other summary".
- They name the wrapup change card as where the rest goes.

## Verification

| scenario | mode | AC |
|---|---|---|
| S1, S2, S3 (text) | unit | AC-001 |
| owner_read_ratio_saga < 1.48, quiz ≥ 0.73, traps not below v2, escaped 0 | manual (saga run, hm arm ×3 vs the 2026-11-28 discipline rows) | - |

## Open Questions

none

## Refinement Decisions

- **Three lines plus the must-decide rows; the "no other summary" wording follows the change card.**
  The bench showed the model ignores a list of items and writes about 1,400 chars. "Verbatim, no other summary" worked for the card. Undo cost: one template sentence.
- **Stacked on the change-card branch (PR #91).**
  This change relies on the land card to carry what the report drops, and the session pushes to one branch only. Undo cost: split the PR.
- **Skip the interview.** There is one template sentence, and the DRI already chose this lever. It is reversible within minutes. It is not a skip under Step 0, though, because it changes the user-facing message, so the SPEC is still shown for approval.
