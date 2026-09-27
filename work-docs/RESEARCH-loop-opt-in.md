---
type: research
task_slug: loop-opt-in
status: complete
created: 2026-09-27
tags: [harness-maker, research, python, jinja2, synthesize, conditional-render, migration]
mtime_warn_days: 7
intent: LOOP-OPT-IN
libs_fetched: []
sources: []
related_docs: ["[[intent/LOOP-OPT-IN]]", "[[wiki:architecture onboarding-disclosure-and-six-gates]]", "[[PLAN-world-intent-closed-loop-trial]]"]
summary: "New `loop.enabled` key gates loop + loop-p5-batch renders; absent key on existing harness = on"
---

# RESEARCH — loop-opt-in

## 🎯 Recommended Direction

**TL;DR:** Add a `loop.enabled: bool` key to `harness.yaml`. It gates the two
`/hm:loop*` command files (plus their Codex skill twins) and the few prose lines
that advertise `/hm:loop`. Existing harnesses keep the loop: an absent key there
migrates to `true`. New interviews default to `false`.

Rationale: the synthesize layer already has a config-gated file precedent
(`_schema_files(answers.second_opinion.enabled)`). The orphan sweep already
deletes a previously rendered, unmodified file once it drops out of the
blueprint (`reconcile._classify_orphan` → `ours-clean`). The mechanism is
therefore a list filter plus a migration default; no new machinery is needed.
The main impact is **internal maintainer value**: this repo's rendered surface
shrinks by 56,526 B, and `dead_rendered_bytes` drops from 21.7 to about 9.2
(computed with the metric's own formula on 2026-09-27). No user-facing
workflow changes for anyone who uses the loop.

## 🔍 Refinement Decisions

Discovery lens: Technical architecture / implementation + Risk (migration
preserving existing harnesses). The user-workflow lens is narrowed to this
repo's own usage evidence because the topic is a scoped internal change, not a
roadmap question.

## 🛠️ Approaches Found

### A. Opt-in key, legacy-absent = on (recommended)

| Field | Content |
|---|---|
| Approach | `loop.enabled` (default `false` for new interviews). An existing `harness.yaml` without the key resolves to `true` via a `schema_version` 5→6 migration in `interview.answers_from_harness_yaml` |
| Assumption | Some consumer harnesses may still use `/hm:loop`. We cannot see their usage, so silent removal is unsafe |
| Evidence | Precedent migrations: `codex_second_opinion → second_opinion.models` (schema 2→3), `feature_branch_workflow → worktree.enabled` (explicit bool preserved exactly, ADR-006). Global rule 2026-06-08 "absent-case = feature black hole" requires an explicit absent behaviour |
| Trade-off | One schema bump + migration branch + its tests. This repo must flip `loop.enabled: false` explicitly |
| Compatibility | Fits `_base_files(config_dump=…)` and `_codex_target_files(config_dump=…)`; both already receive the config |
| Risk | low–medium (the migration is the only part that touches user state) |

### B. Opt-out key, default on everywhere

| Field | Content |
|---|---|
| Approach | `loop.enabled` default `true`; absent = `true`; no schema bump. This repo sets `false` |
| Assumption | "Opt-in" in the intent title is not load-bearing; only this repo's metric matters |
| Evidence | The metric measures only this repo's base `.claude/commands/hm/` |
| Trade-off | Simplest (no migration). Every new install still ships 56 KB of loop prose it probably never calls, which contradicts the intent statement ("옵트인으로 바꾸고") and the vision line "각 프로젝트에는 필요한 구성만 렌더" |
| Compatibility | Same render gate as A |
| Risk | low |

### C. Gate the whole autoloop family (rejected: out of scope)

Gate the commands plus the `autoloop-driver` skill, the `autoloop-coder` agent
and the `loop_gate`/`sessionid_envfile` hooks. The intent's `out_of_scope`
excludes "다른 무호출 명령", and the hooks also serve task-worktree /
autopilot session scoping (`sessionid_envfile` feeds `HM_SESSION_ID` for every
stage). Record this as a possible follow-up only.

## ⚠️ Pitfalls

- **Dangling advertisement.** With the files gone, these lines would advertise a
  command that does not exist: `commands/hm/help.{en,ko}.md.j2:34,48`
  (table row + "Stages are chained by `/hm:loop` or by autopilot"),
  `claude-md/{Side,Production}.{en,ko}.md.j2` ("Stages chain via `/hm:loop` or
  autopilot"), and `cursor/rules/harness.mdc.j2:47`. The runtime-conditional
  prose in stages ("When dispatched by `/hm:loop` or by autopilot",
  `execute.md.j2` Step 5 "ephemeral `/hm:loop` worktrees ONLY") is harmless when
  the loop is off. It is guarded by runtime marker checks, and deleting it is out
  of scope ("loop 본문 삭제·축소").
- **Absent-case black hole** (global Learned Corrections 2026-06-08): a
  `loop.enabled` read without a defined absent behaviour would flip existing
  users off on their next `/hm:make --update`. The migration must be tested for
  the absent case, not only the present case.
- **Template edits trip six gates** ([wiki:architecture]
  onboarding-disclosure-and-six-gates): `tests/structural/surface_baseline.json`
  (aggregate ratchet), the BASELINE-DELTA attribution doc, the command-surface
  registry (`tests/fixtures/rendered_command_names.json`), the synthesize
  snapshots (`tests/snapshot/*.expected.yaml`), the round-trip budget, and the
  render fixtures. 18 test files reference the loop command paths directly
  (`grep -rl "commands/hm/loop\|loop-p5-batch.md" tests`). Size the phases by the
  gate set, not by the diff.
- **Metric moves only after release + re-render.** This repo's rendered harness
  runs the released plugin (memory: rendered-harness-pins-released-plugin; the
  base `wrapup.md` is 0.60.2 today). `dead_rendered_bytes` is measured in base
  `.claude/commands/hm/`. The intent therefore cannot be observed as met until a
  release ships and this repo is re-rendered with `loop.enabled: false`.
- **Orphan sweep keeps modified files.** A user-edited `loop.md` classifies as
  `ours-modified` and is kept with a warning. That is correct behaviour, but it
  means turning the loop off does not guarantee the file disappears.
- **The 9.2 projection is window-dependent.** The metric counts commands with
  zero turns in the transcript window. If `configure`/`health`/`make`/`help`/
  `uninstall` get invoked, they leave the dead set and the value changes. The
  loop's 56,526 B leave both numerator and denominator.

## ❓ Open Questions

1. **A or B**: does "opt-in" mean default-off for new installs (A), or is an
   opt-out flag that this repo flips enough (B)?
2. **Key placement/name**: `loop.enabled` (top-level block, room for future loop
   knobs) vs `commands.loop` vs `autoloop.enabled`?
3. **`/hm:configure` entry**: should the key be togglable there? Precedent:
   onboarding-disclosure made `/hm:configure` the no-hand-edit path for axes
   silently set at install.
4. **Interview**: ask about the loop during `/harness-maker:make` fresh install,
   or keep it silent-default-off with a line in the "Set for you" disclosure
   table?
5. **Codex twins**: gate `.agents/skills/hm-loop*/SKILL.md` with the same key
   (recommended for consistency; they are not counted by the metric).

## 📚 Sources

- Internal only; no external library or web source is needed for this change.

## 🔗 Related Internal Docs

- `intent/LOOP-OPT-IN.md`: approved and activated 2026-09-27; statement
  21.7 → ~9.2, target ≤10.
- `src/harness_maker/synthesize.py:689-690` (Claude render),
  `:784-792`, `:822-829` (Codex twins), `:1018` (`_schema_files` precedent).
- `src/harness_maker/reconcile.py:557` (`_classify_orphan`), `:684` (`sweep_orphans`).
- `src/harness_maker/interview.py:913` (schema_version read), `models.py:1253`
  (`schema_version: int = 5`).
- `src/harness_maker/readiness.py:1498` (`meta_cmds`, which tolerates absence).
- Usage evidence: base `.claude/observability/stage-spans.jsonl` has 0
  `hm:loop*` spans against 547 stage spans; the last `autoloop(` commit is
  2026-05-16 (13 in total).
- `[[PLAN-world-intent-closed-loop-trial]]`: an activated real-task trial whose
  collector is a Codex thread. This session is not the collector. Its evidence
  goes to this task's PLAN Feedback, and the collector update stays pending.
