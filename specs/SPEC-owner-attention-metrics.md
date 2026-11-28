---
type: spec
task_slug: owner-attention-metrics
status: approved
created: 2026-11-28
tags: [eval, bench, saga]
test_framework: pytest
interview_rounds: 0
summary: Add owner-side numbers to the saga bench - attention per shipped change (what the owner read, replies, approvals), understanding (the existing quiz), and two guards (regressions that escaped to the end, pairwise maintainability) - so hm can be judged on the owner's time and understanding, not tokens.
---

# SPEC — owner-attention-metrics

## Intent

The user picked "owner-time metric, measure first" (HR-027, 2026-11-28) and said what matters
is the owner's attention and understanding, and that maintainability matters too. hm has been
measured on token ratio and hidden-test pass rate only. The saga bench already simulates an
owner across five sessions and already has an understanding quiz (main run: hm 0.77, plain
0.64, discipline 0.58), but it does not count what the owner had to read or decide, whether
earlier work broke later, or how maintainable the result is.

## Outcomes

- The saga report shows, per arm and per shipped change: characters the owner read (agent
  messages plus the SPEC an hm owner approved), owner replies, approvals; the quiz mean;
  escaped regressions per run; and pairwise maintainability tallies.
- Attention is computed from rows already written, so the 2026-11-25 main run gets a baseline
  without a rerun.

## Definitions

- **Shipped change**: a session that was not interrupted and whose own hidden tests all passed.
- **Read chars**: the length of every agent message in the session (the owner reads each one;
  the quiz answers from the same text) plus `doc_chars`.
- **doc_chars**: for an hm session whose SPEC is approved at its end, the length of
  `SPEC-<slug>.md` (the owner approves a document, not only a message). 0 for other arms.
- **Replies**: owner replies that were not empty, plus post-hoc corrections the runner sent
  (an owner who finds a defect after the work spent attention on it). The runner's own
  `/hm:execute` and `/hm:wrapup` prompts are not counted: Maker's Advance rule chains them
  without the owner.
- **Approvals**: simulator turns with `approved: true`.
- **Escaped regression**: a hidden test that passed when its own session was graded and fails
  on the final tree.

## In-Scope Scenarios

- **S1 (normal):** Given a session record with three agent messages, one owner reply, one
  approval and one post-hoc turn, `attention(record)` gives their chars, 2 replies, 1 approval.
- **S2 (normal):** Given an hm work tree whose SPEC is approved, `doc_chars` is the SPEC.md
  length; without approval or for a plain arm it is 0.
- **S3 (edge):** Given records where S1's hidden test passed at its session and fails on the
  final tree, `escaped_regressions` lists it; a test that failed at its own session is not a
  regression; an interrupted session's tests are skipped.
- **S4 (normal):** Given rows from the old schema (no `doc_chars`, no `escaped`), `owner_summary`
  still gives read chars, replies, approvals per shipped change and the quiz mean, with
  escaped shown as unknown.
- **S5 (normal):** Given ok rows of hm and plain at the same rep, `run_judge` asks twice with the
  order swapped and counts a pick only when both orders agree; the report prints the tallies.

## Non-Goals

- Choosing the intent metric's baseline (the user chose plain-discipline on a decision card,
  2026-11-28; recorded as `owner_read_ratio_saga` and goal OWNER-ATTENTION, baseline 2.50).
- Changing the fixture, sessions, owner rules, traps or verdict.
- Counting time in seconds: the bench has no human, so reading is counted in characters.

## Constraints

| Constraint | Source |
|---|---|
| Same owner rules and sheets for every arm | DESIGN-saga-bench §2.3 |
| Judge is position-swapped, Opus, a pick counts only when both orders agree | blog-cost pairwise judge |
| ruff, ruff format, mypy --strict clean; no new dependency | CLAUDE.md |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: attention per session from its turns

`attention(record)` returns `read_chars` (sum of message lengths + `doc_chars`, 0 when absent),
`replies` (non-empty `sim.reply` + `kind == "posthoc"` turns) and `approvals`
(`sim.approved` true). For the S1 record: read_chars 30 (10+10+10), replies 2, approvals 1.

### AC-002: an hm owner reads the SPEC it approves

`doc_chars(work, "hm", slug)` is the length of `specs/SPEC-<slug>.md` in the base or any
worktree when `spec_approved`; 0 when not approved, when slug is None, or for another arm.
`_finish` stores it on the record.

### AC-003: escaped regressions on the final tree

`escaped_regressions(records, work, hidden_root)` regrades each session's hidden dir once on
the final tree and returns `"<hidden>::<test>"` for each test that was `passed` in that
session's `hidden` and is not passed now. Interrupted sessions and sessions without `hidden`
are skipped. `run_saga` stores the list as `escaped` on the row.

### AC-004: owner summary works on old and new rows

`owner_summary(rows)` gives per arm: `runs`, `shipped` (mean per run), `read_per_ship`,
`replies_per_ship`, `approvals_per_ship` (totals over runs / shipped changes over runs),
`quiz` (mean of `quiz_mean`), `escaped` (mean of `len(escaped)` over rows that have it, None
when none do). `report` prints it as an "owner" table.

### AC-005: position-swapped maintainability judge

`run_judge(opts, model)` pairs the ok rows in `opts.out` of hm with each other arm at the same
rep, judges the scoped diff (fixture repo → final work tree) twice with the order swapped, and writes one
row per pair to `judge.jsonl` with each axis `A` (hm), `B`, `tie` or `split`. `judge_summary`
counts A and B wins per other arm and axis. The `judge` CLI command runs it and the `report`
command prints the summary when `judge.jsonl` exists.

## Verification

| Scenario | Mode | Check |
|---|---|---|
| S1–S5 | automated | `tests/unit/test_saga_bench.py::test_owner_ac_00*` |
| baseline | manual | `report --out` on the 2026-11-25 main-run rows prints the owner table |

## Open Questions

None.

## Refinement Decisions

- Skip check: one bench script, offline tests, reversible; spec-validator skipped (5 ACs).
- Attention is computed in the report from stored turns (agent choice): the old main run gets
  a baseline for free, and nothing new has to be stored except `doc_chars` and `escaped`.
- Maintainability is judged in the saga (final tree after five sessions) against every other
  arm at the same rep (agent choice); the tier bench's plain+tests arm does not exist here,
  and plain-discipline is the saga's control.
