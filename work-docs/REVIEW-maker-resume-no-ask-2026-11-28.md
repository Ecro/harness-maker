---
type: review
task_slug: maker-resume-no-ask
created: 2026-11-28
spec: "[[SPEC-maker-resume-no-ask]]"
summary: One reviewer round, no P0/P1; two false-positive paths of `interrupted` fixed with tests, the live-peer and trim cases accepted as recorded risks.
---

# REVIEW — maker-resume-no-ask

Round 1: one reviewer over the SPEC and `git diff origin/main`; it confirmed F1 and F2 with a
probe through the shipped `worktree span-end` hook. Render and digest tests green after fixes.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | world_model_digest.py `interrupted` | a start without a session id is never closed by an id-bearing Stop hook, so a finished task read as cut off | accepted | session-less start → not interrupted; `test_ac001_undecidable_reads_not_interrupted` |
| F2 | P2 | world_model_digest.py `interrupted` | one turn with spans on two tasks: the single `end` names only the last slug, the first stayed open | accepted | open only if its session wrote no later row on any task; `test_ac001_one_turn_two_tasks_both_closed` |
| F3 | P2 | SKILL.md.j2 Resume | a stage running now in another session also reads interrupted, and rule 3 prefers it | rejected (recorded) | no liveness signal exists; "not other_session" excludes every real resume. SPEC Refinement Decisions |
| F4 | P3 | world_model_digest.py render | "exactly one" judged on shown tasks; trimming can hide one | rejected (recorded) | needs > 5 tasks or > 1.5 KB; the cut-off task is newest and sorts first. Docs reworded to "never dropped from a shown task" |
| F5 | P3 | world_model_digest.py | Codex writes no `end`, so every Codex task carried `interrupted: true` | accepted | a ledger with no `end` → not interrupted |
| F6 | P3 | SKILL.md.j2 Resume | absent `latest_artifact` (trimmed) lost its rule | accepted | "absent or null" |
| F7 | P3 | SKILL.md.j2 Resume | "→ as 2" terse | rejected | 12 chars of headroom under the 4,689 cap; the rule numbering is local |
| F8 | P3 | CLAUDE.md, render docstring | invariant lists only `other_session` | accepted | both name `interrupted` |
| F9 | P3 | CHANGELOG, world-model.md | "resumes that one when several are open" and "end at every turn end" overstate | accepted | reworded |
