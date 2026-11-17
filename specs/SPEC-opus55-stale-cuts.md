---
type: spec
task_slug: opus55-stale-cuts
status: approved
created: 2026-11-17
tags: [harness-maker, spec, templates, cleanup, host-native, opus-5-5]
test_framework: pytest
interview_rounds: 1
summary: "Stop shipping the stale worktree-isolator skill, the dead session-snapshot hook and its hot tier, and the CLAUDE.md stub lines; nothing in the stage flow, gates or reviewers changes."
---

# SPEC — opus55-stale-cuts (stale and host-covered surface found by the Opus 5.5 review)

## 🎯 Intent

On 2026-11-17 the DRI asked what harness-maker can drop now that Claude Code runs Claude
Opus 5.5 by default. The research
(`/mnt/project-files/hm-opus55-research/RESEARCH-opus55-cuts.md`) found no source that supports
cutting the core (tests first, an independent reviewer, human approval, persistent state). It
found a small group of surface that is stale or that the host now covers, which can go without
any model measurement. The DRI chose "bench first, then clean up" on the decision card
(15:30Z) and wrote "나에게 묻지말고 너의추천대로 hm workflow 에 따라 wrapup and push to main까지
진행해" (15:31Z). This SPEC is that clean-up.

What is wrong on main `735db8fd` (0.65.5), each read from the templates:

1. Every rendered `CLAUDE.md` opens with "Phase 3 stub. Phase 6 fills in the locale × preset
   content." and carries `## Caching` (both presets), `## Memory` (Side), `## Reviewers` and
   `## Worktree` (Production), each one line that points at `harness.yaml` or at a build phase
   that never ran. They are loaded on every turn and tell the model nothing it can act on.
   (HR-016 in the proposals log.)
2. The `worktree-isolator` skill says to invoke it when "Any `/hm:` stage starts" and describes
   `python -m harness_maker.worktree create execute` with
   `.worktrees/execute-<uuid>-<timestamp>/` directories. The stages now run
   `hm worktree task-preflight <slug>` on `hm/<slug>`. It is typed-only
   (`disable-model-invocation: true` since HM-LIGHT-LANE lever 5), so it cannot self-trigger,
   but a user who types it gets the retired procedure.
3. The `flush_session` hook (Claude `PreCompact`, Codex `Stop`) snapshots
   `.claude-progress.json`, which nothing writes since autoloop was retired, and appends a
   `checkpoint:compaction` line that `/hm:execute`'s "Hot tier" reads. `/hm:execute` already
   resumes from the SPEC's `pending_test` flags, the PLAN and the REVIEW file, and the same
   paragraph tells the model to ignore the tier's other content.

## Outcomes

- A fresh render has 4 fewer files per preset (61 to 57 with targets `claude-code,codex`).
- `CLAUDE.md` keeps Workflow, Output Language, Context discipline, Project knowledge, World
  model and both user blocks, and loses the stub lines.
- No session-snapshot hook runs; `/hm:execute` no longer points at the session tier.
- A project rendered by 0.65.5 loses the skill files and the hook entries on its next `make`,
  unless the user edited them. Its session README stays on disk.

## In-Scope Scenarios

- **S1 (normal).** Given a new project, when `make` renders it for `claude-code,codex`, then
  `worktree-isolator`, its two Codex files and `memory/session/README.md` are absent and every other
  0.65.5 path is present.
- **S2 (normal).** Given the same render, when `CLAUDE.md` is read, then none of the stub lines
  is in it and the kept sections are.
- **S3 (normal).** Given the same render, when `.claude/settings.json` and `.codex/hooks.json`
  are read, then no command names `flush_session`, Claude's `PreCompact` still runs
  `worktree span-end`, and `/hm:execute` has no "Hot tier" paragraph.
- **S4 (edge, brownfield).** Given a pristine 0.65.5 render, when HEAD's `make` runs over it,
  then the three skill files are deleted and the shipped `flush_session` hook entries are
  removed, while a user's own hook in the same event stays. `memory/session/README.md` stays:
  memory files carry no content hash, so the sweep cannot prove a copy pristine.
- **S5 (edge, user edit).** Given a 0.65.5 render where the user changed one byte of the retired
  skill, when HEAD's `make` runs, then that file is kept.
- **S6 (failure).** Given a `settings.json` the user never re-rendered, when the host fires the
  old `python -m harness_maker.hooks.flush_session` command, then it exits 0 and writes nothing.
- **S7 (failure).** Given a `harness.yaml` that still lists `worktree-isolator`, when `make` runs,
  then it warns that the key is inert and renders nothing for it.

## 🚫 Non-Goals

- No change to the worktree lifecycle (`task-preflight`, `task-refresh`, `task-land`), the
  worktree gate, or `worktree.enabled`.
- No change to stage steps, `hm check`, the RED gate, the reviewer, spec-validator, the review
  round cap, the intent layer or Maker.
- `agent-quality-rubric`, `ai-readiness-rubric` and `context-linter` stay. The research listed
  them as a cut on the grounds that their descriptions load into every session; the render
  shows they are typed-only already, so they carry no context cost. The rubric files under
  `.claude/rubrics/` stay too: `/hm:health` reads them.
- The reviewers' reasoning field stays. The research listed it as a cut; reading
  `code-verifier` shows its mode A verifies each step of that chain, so it is an evidence
  format with a consumer, not thinking scaffolding.
- `memory_md append-session` and existing `.claude/memory/session/<date>.md` files stay.
- The Context discipline block stays until it is re-measured on Opus 5.5.
- No version bump and no release.

## Constraints

| Constraint | Value |
|---|---|
| Test framework | pytest (mandatory) |
| Retirement path | the existing ones only: `synthesize.RETIRED_SKILLS`, the orphan sweep, `render._HARNESS_RETIRED_HOOK_INVOCATIONS` |
| Kept user copies | a retired hook's `python -m` entry point stays as an exit-0 stub, as 0.64.0 did |
| Surface budgets | may only shrink |
| Docs | README (en, ko), HOW-IT-WORKS (en, ko) and ARCHITECTURE describe what renders now |

## Irreversible Decisions

| id | decision | category | rationale | source |
|---|---|---|---|---|
| IRR-001 | The `worktree-isolator` skill, `memory/session/README.md` and the `flush_session` hook wiring stop shipping; a re-render deletes pristine copies of the skill and removes the shipped hook entries (an existing session README is left in place); `python -m harness_maker.hooks.flush_session` becomes an exit-0 stub. | public API/CLI contract | A user who typed the skill name or relied on the session checkpoint loses it on upgrade. The skill describes a retired procedure, and the checkpoint carried no state since autoloop was retired. | spec |

## Acceptance Criteria

### AC-001: CLAUDE.md has no stub lines and keeps its live sections

For each preset (Side, Production) and locale (en, ko), the rendered `CLAUDE.md` contains none
of `Phase 3 stub`, `Phase 6`, `Phase 9`, nor the stub headings of its locale (en: `## Caching`,
`## Reviewers`, `## Worktree`, `## Memory`; ko: `## 캐싱`, `## 리뷰어`, `## 자동 루프 / 워크트리`,
`## 메모리`). It contains its locale's two live headings (en: `## Workflow`,
`## Output Language`; ko: `## 워크플로우`, `## 출력 언어`) and, in both locales,
`## Context discipline`, `## Project knowledge`, `## World model`,
`<!-- @hm:user:project-rules -->` and `<!-- @hm:user:extensions -->`.

### AC-002: A fresh render is the 0.65.5 path set minus the four retired paths

For each preset, rendered with `--targets claude-code,codex --locale en`, the set of files
equals the 0.65.5 set recorded in `tests/fixtures/opus55_stale_cuts/render_paths_0655.json`
minus exactly: `.claude/skills/worktree-isolator/SKILL.md`,
`.agents/skills/worktree-isolator/SKILL.md`,
`.agents/skills/worktree-isolator/agents/openai.yaml` and
`.claude/memory/session/README.md`.

### AC-003: worktree-isolator is a retired name

`worktree-isolator` is in `synthesize.RETIRED_SKILLS`, in neither `synthesize._ALL_SKILLS` nor
`interview._ALL_SKILLS`, has no template directory, and a `harness.yaml` whose `skills.enabled`
names it produces the inert-key warning. The three rubric skills are still in both lists.

### AC-004: No session-snapshot hook and no hot tier in a fresh render

For each preset: no command in `.claude/settings.json` or `.codex/hooks.json` contains
`flush_session`; Claude's `PreCompact` groups (`auto`, `manual`) each still run
`worktree span-end`; `.codex/hooks.json` has no empty event list; the rendered `/hm:execute`
(Claude command and Codex stage skill) contains neither `Hot tier` nor `memory/session`, and
still contains `hm memory_retrieve`.

### AC-005: A re-render over 0.65.5 retires pristine copies and keeps the user's own

Starting from a tree rendered by the 0.65.5 source (`735db8fd`): after HEAD's `make`, the
file set (leaving out the re-render's own backup and orphan log) equals a fresh HEAD render's
plus `.claude/memory/session/README.md`, and no hook command names `flush_session`,
while a user hook added to `PreCompact` (Claude) and `Stop` (Codex) before the re-render is
still there. A user command appended inside a shipped `flush_session` group survives as well,
and the `flush_session` entry beside it is removed. With no user hook added, neither hook file
is left with an event that has no hook group, and the hook commands equal a fresh HEAD
render's. With one byte appended to `.claude/skills/worktree-isolator/SKILL.md` before the
re-render, that file is kept. With one byte appended to the Codex copy
(`.agents/skills/worktree-isolator/SKILL.md`) instead, that file and its
`agents/openai.yaml` (which holds `allow_implicit_invocation: false`) are both kept.

### AC-006: The old hook command is a harmless stub

`python -m harness_maker.hooks.flush_session`, run with a PreCompact payload on stdin in a
project that has a `.claude-progress.json`, exits 0, prints nothing to stdout, and leaves the
project tree byte-identical. `<HM>:harness_maker.hooks.flush_session` is in
`render._HARNESS_RETIRED_HOOK_INVOCATIONS`.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S2 | unit (render) | `test_ac_001_*` |
| S1 | integration (`make`) | `test_ac_002_*` |
| S7 | unit | `test_ac_003_*` |
| S3 | integration (`make`) | `test_ac_004_*` |
| S4, S5 | integration (0.65.5 ref render, then HEAD) | `test_ac_005_*` |
| S6 | unit (subprocess) | `test_ac_006_*` |

## Open Questions

None.

## Refinement Decisions

Chosen for the DRI under the 15:31Z instruction; each is cheap to undo (restore a template and a
list entry) unless noted.

- **Scope narrowed from the research's five items to three.** Two research claims did not
  survive reading the render. The reasoning-template cut (A5) is dropped: `code-verifier`
  consumes that chain. The self-audit cut (A4) is dropped: the three skills are typed-only, so
  the stated cost (descriptions in every session) does not exist, and the host overlap holds on
  Claude Code only.
- **`flush_session` becomes a stub, not a deleted module.** A `settings.json` that was never
  re-rendered still calls it; deleting the module would print an error on every compaction.
  Follows 0.64.0's handling of `telemetry` and `autopilot_autoarm`. Undo cost: none.
- **An existing session README is not deleted.** Found at GREEN: the orphan sweep keeps every
  `memory/` file because they carry no content hash. Deleting it would need a new retirement
  rule for a user-data directory, for a file that harms nothing. New renders do not create it.
- **Older SPECs' ACs retired with `spec_machine retire --by opus55-stale-cuts`.** Found while
  updating pinned tests: `SPEC-flush-session` AC-001, `SPEC-retired-text` AC-003 (the hook's
  status message on re-render) and the skeleton ACs of `SPEC-tpl-SKILL-md` (the
  worktree-isolator template) and `SPEC-tpl-session-readme-md` describe behaviour this SPEC
  removes. `SPEC-retired-text` AC-001 and AC-002 stay live; their tests drop the rows that
  name the retired skill and hook.
- **`SPEC-hm-overhaul-p1` is amended by IRR-001, not retired.** Its AC-009 ("kept behaviour is
  unchanged from db19f023") stays live for everything else; the clause "execute.md at HEAD
  contains the db19f023 hot-tier sentences naming checkpoint:compaction" and `flush_session` in
  its differential domain no longer hold, and its test `test_ac009_compaction_checkpoint_resume`
  is deleted. Its AC-004 hook tables and kept-skill list lose `flush_session` and
  `worktree-isolator`. That SPEC classed the execute hot tier INV ("state that survives the
  context window"); the state that survives is the SPEC's `pending_test` flags, the PLAN and
  the REVIEW file, all on disk, and the checkpoint added only a timestamp line beside them.
- **Two fixes from review (REVIEW F-001, F-002).** The orphan sweep keeps a Codex skill's
  `agents/openai.yaml` while the `SKILL.md` beside it is kept, so an edited copy of the retired
  skill cannot become self-triggering. The hook merge drops an event whose every entry was a
  retired harness hook, so a pristine Codex project is not left with `"Stop": []`.
- **`memory_md append-session` stays.** It is a documented CLI verb with no caller in the
  render; removing it is a separate contract change.
- **spec-validator skipped.** 6 live ACs is under `VALIDATOR_SKIP_MAX_ACS` (8), the default.
- **No intent picked.** No active intent measures rendered surface; `HM-LIGHT-LANE`'s metric is
  cost ratio and this change is not sized to move it.
- **Oracles.** AC-002 and AC-005 use the 0.65.5 render as a differential reference (path list
  recorded before any template changed; `735db8fd` source extracted by the test). AC-001,
  AC-003, AC-004 and AC-006 are golden strings typed from the templates at `735db8fd`.
