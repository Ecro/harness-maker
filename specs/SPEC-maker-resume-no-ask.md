---
type: spec
task_slug: maker-resume-no-ask
status: approved
created: 2026-11-28
tags: [maker, world-model, resume, digest]
test_framework: pytest
interview_rounds: 0
summary: A resume ask is the owner's consent, so Maker enters the cut-off task without asking first and never looks for its files in the base checkout.
---

# SPEC — maker-resume-no-ask

## Intent

The hm vs oh-my-claudecode bench (2026-11-28,
`/mnt/project-files/hm-omc-bench/RESULTS-omc-vs-hm-2026-11-28.md`, saga S4r turns in
`data/saga-results.jsonl`) scored hm 0/5 on resume, against plain 5/5 and OMC 3/5. Maker found
the cut-off task `tz-setting` in 5 of 5 runs, so routing (SPEC-maker-resume-route) works. It then
lost the trap two ways:

- **It asked first, every time.** The Resume rule says `other_session` true or absent → "ask once
  first". A fresh session always has a new session id, so the cut-off session is always "another
  session" and the question fires on every cross-session resume. The owner's reply then has to
  say what was unfinished (4 of 5 replies restated it). In rep 3 two tasks were open (`tz-setting`
  cut off, `remind-list-color` un-landed), and the closed question asked the owner to pick.
- **It looked in the wrong place.** In 2 of 5 runs Maker said the PLAN and SPEC "aren't on disk":
  it checked the base `work-docs/` and `specs/`, but the files sat in `.worktrees/tz-setting/`. The
  Briefing line "else or on failure use `work-docs/`, `specs/`" reads as "look in the base".

The DRI asked for the fix ("고쳐", 2026-11-28). The rule it follows: hm should not spend the
owner's attention on a question whose answer the ask already gave.

## Outcomes

- An explicit resume ask enters the task's `next_stage` without a confirmation question, even when
  another session touched the task last.
- With two or more tasks on Claude Code, the one whose stage was cut off is resumed without a
  question when it is the only one.
- Maker never reports a task's artifacts missing because it looked in the base checkout.

## In-Scope Scenarios

- **S1 (normal):** Given a Maker render (Claude/Codex × en/ko), the Resume section says the ask is
  consent and never to ask first even if `other_session` is true; the "ask once first" rule is gone.
- **S2 (normal):** Given a Maker render, Resume says the stage opens the worktree (check no files),
  and the Briefing says a task's files are in `.worktrees/<slug>/`, not the base. Maker stays
  ≤ 4,689 chars.
- **S3 (normal):** Given a task whose newest span row is a `start` with no `end` after it (the Stop
  hook never ran), the digest reports `interrupted: true` for that task only. A task whose newest
  row is an `end`, or with no rows, has no `interrupted` key.
- **S4 (normal):** Given a Claude Maker render, Resume with two or more tasks resumes the single
  `interrupted: true` one; the Codex render keeps the closed question (Codex writes no span `end`,
  so every Codex task would read as cut off).
- **S5 (live, manual):** Given the saga S4r state, a fresh session with the bare resume prompt enters
  `/hm:execute tz-setting` in its first turn.

## Non-Goals

- Detecting whether the other session is still alive. The session registry's pid is the `hm` CLI's
  own pid, so it is dead right after the call; fixing that liveness is separate work.
- Changing Briefing's use of `other_session`, its never-dropped status, or the digest's other keys.
- Changing the stage preflight's same-task warning.

## Constraints

| Constraint | Source |
|---|---|
| Maker SKILL.md ≤ 4,689 chars on every target | CLAUDE.md "World model (Maker)" |
| Digest ≤ 1,500 bytes, always exit 0; `other_session` never dropped | CLAUDE.md "World model (Maker)" |
| Adding a digest key is additive to IRR-001 of SPEC-world-model-followups (no key renamed or removed) | specs/SPEC-world-model-followups.md |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the digest marks a cut-off stage

`interrupted` is `true` exactly when the task's newest span row (ts, then file order) is a `start`
with a session id, its session wrote no later row (on any task), and the ledger holds at least one
`end`; otherwise the key is absent. Rows come from the real `emit_event` start and the shipped
`worktree span-end` Stop hook. Golden table over the task's history:

| history | interrupted |
|---|---|
| none | absent |
| start | true |
| start, end | absent |
| start, end, start | true |
| start, end, start, end | absent |

| start, start on another task, one Stop `end` (same session) | absent for both |
| start without a session id, then a Stop `end` with one | absent |
| starts only, no `end` in the ledger (Codex) | absent |

A peer task's ended span never sets it, and a peer session's later row never clears it.

### AC-002: Resume enters without asking and checks no files

On every Maker arm, Resume contains `The ask is consent: never ask first, even if
`other_session` is true.` and `the stage opens the worktree, check no files`; the file has no
`ask once first`; Briefing contains `A task's files are in `.worktrees/<slug>/`, not the base`; the
file stays ≤ 4,689 chars.

### AC-003: the cut-off rule is Claude-only

Resume contains `Exactly one `interrupted: true` → as 2 instead.` on the Claude arms and not on
the Codex arms.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S3 | unit | `tests/unit/test_maker_digest.py::test_ac001_interrupted_from_open_span`, `::test_ac001_undecidable_reads_not_interrupted`, `::test_ac001_one_turn_two_tasks_both_closed` |
| S1, S2 | render | `tests/render/test_render_maker_front_door.py::test_resume_no_ask_ac002_enters_without_asking` |
| S4 | render | `tests/render/test_render_maker_front_door.py::test_resume_no_ask_ac003_interrupted_claude_only` |
| S5 | live, manual | a replay of the saga S4r state; recorded in the REVIEW |

## Open Questions

none

## Refinement Decisions

- **Drop the question, do not detect liveness:** a live/dead signal for the other session would be
  the precise fix, but no reliable one exists (the registry pid is the CLI's own). The owner typed
  "continue", which is the consent; a real collision is rare and the owner can stop the stage.
- **`interrupted` from the span ledger:** the Stop hook already writes `end` at every turn end, so
  an open `start` is a free, exact "cut off mid-turn" signal. Emitted only when true (about 19
  bytes a task) and never dropped by the trimmer, so its absence always means "not cut off".
- **A live peer reads as cut off too (REVIEW F3, accepted risk):** a stage running right now in
  another session also has an open `start`, so with several tasks Resume can pick it. There is no
  liveness signal to tell them apart (see Non-Goals); "not `other_session`" would exclude every
  real resume, since the cut-off session is always another one. Concurrent sessions on one repo
  are rare for a solo owner, and the stage's own preflight still warns on a same-task session.
- **Trimmed tasks (REVIEW F4, accepted):** "exactly one" is judged on the shown tasks. Hiding an
  interrupted task needs more than 5 tasks or a payload over 1,500 bytes, and an interrupted task
  is normally the newest, so it sorts first and survives the cut.
- **Worktree path in prose, not in the digest:** the path is always `.worktrees/<slug>/`, so one
  Briefing line costs nothing per task, where a digest field would cost bytes on every task.
- **Approval:** the DRI's "고쳐" on the reported defect. Small fix, no irreversible decision.
