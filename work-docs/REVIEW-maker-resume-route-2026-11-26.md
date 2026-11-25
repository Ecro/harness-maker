---
type: review
task_slug: maker-resume-route
created: 2026-11-26
spec: "[[SPEC-maker-resume-route]]"
summary: One reviewer round, no P1; the docs finding accepted, the mid-stage resume guard rejected (budget and Resume is idempotent), two notes need no change.
---

# REVIEW — maker-resume-route

Round 1: one reviewer over the SPEC and the diff; render tests green.

Live evidence (Sonnet 5.5, `claude -p`, bare saga resume prompt, interrupted `tz-setting` in
`.worktrees/`): 0.66.1 render 0/3 Maker loads, 1/3 found the task; new render 5/5 Maker loads,
5/5 named `tz-setting` with next stage execute ($0.05 per run). Maker asked before entering in
each run because `other_session` is true, as its Resume rule requires.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | world_model_pointer.md.j2:16 | "resume … mid-stage" may route a same-session resume (after Esc) to Maker, whose Resume re-enters the stage | rejected | Resume enters the task's `next_stage`, which is the running stage; stages are built to be re-entered (an interrupted execute resumes to execute). A guard line costs 46 chars over the 4,689 Maker cap. Revisit if a live mid-stage case misroutes |
| F2 | P3 | world_model_pointer.md.j2:16 | "unnamed or mid-stage" vs "named or not, mid-stage too" | duplicate | named asks are admitted by the description's "addresses … by name"; no scope change |
| F3 | P3 | world_model_pointer.md.j2:16 | ko wording | duplicate | reads naturally, routes 재개 |
| F4 | P3 | docs | README(.ko), ARCHITECTURE, reference/world-model and the template comment list only goal/metric/fact/status | accepted | resume added to each |
