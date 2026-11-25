# PLAN — maker-resume-route

SPEC: `specs/SPEC-maker-resume-route.md` (approved).

## Phase 1 — route resume asks to Maker

- [x] Reproduce: saga S4r transcripts (main run + pilot) show 0/7 Maker loads; replaying the
      interrupted state on the 0.66.1 render gives 0/3 Maker loads and 2/3 "no unfinished work".
      `hm world_model digest` on that state lists `tz-setting` with `next_stage: execute`.
- [x] RED: `_ROUTING_GROUPS["resume"]` and the new `_DESCRIPTION_ROUTE` fail on main 8ae7248e
      (11 render cases).
- [x] `world_model_pointer.md.j2`: en/Codex "goal, metric, fact, status, resume asks, unnamed or
      mid-stage" (398 chars at max name/handle); ko "목표·지표·사실·현황·재개 요청".
- [x] `world-model/SKILL.md.j2` description: "...a goal, metric, fact, status or resume request".
- [x] Docs that list the routed asks: README(.ko), ARCHITECTURE, reference/world-model.
- [x] Live replay on the new render: 5/5 Maker loads, 5/5 name `tz-setting` (next stage execute).
