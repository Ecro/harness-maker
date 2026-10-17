---
type: spec
task_slug: maker-advance
status: approved
created: 2026-10-17
tags: [harness-maker, spec, templates, maker, orchestration]
test_framework: pytest
interview_rounds: 2
lane: full
parent_spec: "[[SPEC-hm-overhaul-p1]]"
summary: "With autopilot removed, nothing chains the stages: spec and execute STOP with 'the user's call'. Maker gains an Advance rule: after a full-pipeline Start or a Resume it enters execute after spec and wrapup after execute in the same session, only when the stage reached its final print, and stops when a person is owed; never pushes; no marker or hook."
---

# SPEC — maker-advance (Maker chains spec → execute → wrapup)

## 🎯 Intent

The DRI (2026-10-17, thread "HM-LIGHT-LANE 기록과 구현") asked how stages advance now that autopilot is
gone, and on a card chose "Maker가 이어감": Maker runs spec → execute → wrapup in the same session,
stops at SPEC approval, irreversible decisions, land hold and `hm check` failure, never pushes, and
uses prompt text only (no marker file, no hook). Today `stages/spec.md.j2` and
`stages/execute.md.j2` end with "`/hm:<next> <slug>` is the user's call", Maker's Start table claims
"build X → the full pipeline" but only enters the first stage, and Resume says "the operator runs
wrapup".

## 📐 Outcomes

- Maker (both runtimes) carries an **Advance** section naming the two transitions, the stop
  conditions and "Never push". It advances only when a stage reached its final print; any earlier
  stop is owed to a person.
- spec and execute still name the next command and add "if the world model began this run, enter
  it now unless its Advance rule stops"; Codex `AGENTS.md` says the next stage is the user's or the world
  model's call. README, ARCHITECTURE, HOW-IT-WORKS and CLAUDE.md stop
  saying that only the user chains stages.
- Resume no longer reserves wrapup for the operator.
- The extra blank line before Maker's Choices rule (left by #40's review fix) is gone.
- `hm world_model digest` reports `next_stage: wrapup` once a REVIEW exists; it never names the
  retired `review` or `verify` stage, which a Resume after execute would try to enter.
- One live Claude Code run shows a resumed exempt task landing exactly once without a push, and an
  unapproved one landing nothing.

## 🎬 In-Scope Scenarios

### S1 — "build X" runs to a landed commit
- **Given** the operator asks Maker to build X and approves the SPEC
- **When** spec STOPs with the SPEC `approved`
- **Then** Maker enters execute; when `hm check` exits 0 and no finding is `unresolved`, it enters
  wrapup, which lands one squash commit locally and does not push

### S2 — A person is owed
- **Given** the same run
- **When** a stage stopped before its final print (spec Step 4, execute's PLAN check, a `Do not
  change` crossing, a declined irreversible decision, a land hold), an ask is unanswered, spec's
  printed status is not `approved`, the last `hm check` was not 0, a finding is `unresolved`, or
  `## Queued asks` has entries
- **Then** Maker stops and reports instead of entering the next stage

### S3 — Resume continues the pipeline
- **Given** a task whose `next_stage` is execute or wrapup
- **When** the operator asks Maker to continue
- **Then** Maker enters it and advances as in S1

### S4 — A stage typed directly
- **Given** the operator typed `/hm:spec` without Maker
- **When** spec STOPs
- **Then** the stage still names the next command, and nothing in the stage text advances on its
  own

## 🚫 Non-Goals

- Re-creating autopilot: no marker file, hook, expiry or `hm autopilot` call.
- research → spec: research ends on a choice card (`/hm:spec` or dig deeper), which stays the DRI's.
- Cross-session chaining: Advance applies within the session that ran Start or Resume.
- Push or PR creation.
- A live Codex run: no Codex CLI in the build container; Codex is covered by the render ACs only.

## 🔒 Constraints

| constraint | value |
|---|---|
| test framework | pytest (`tests/render/`) |
| Maker | SKILL.md ≤ 4,500 chars (`_MAKER_CAP`) |
| stages | SPEC-hm-overhaul-p1 AC-004 budgets hold (spec 6,500, execute 7,000) |
| Python | only `world_model_digest.next_stage`; everything else is templates, docs and tests |
| live run | opt-in (`HM_MAKER_ADVANCE_LIVE=1`), `claude` CLI, `--max-budget-usd 5` per run |

## ⚠️ Irreversible Decisions

- IRR-001 (security/permission boundary): Maker enters `/hm:wrapup`, which squash-lands the task on
  the base branch, without the operator typing it. An `exempt` SPEC (Step 0 skip path or
  `auto_full`) therefore lands with no human touch; an approved SPEC whose irreversible decisions the
  DRI approved lands without a further stop. Land hold, unapproved irreversible decisions and push
  stay gated on the DRI. (DRI card 2026-10-17, recommended option "그대로 land".)
- IRR-002 (public API/CLI contract): `hm world_model digest`'s `next_stage` values shrink from six
  stages to the four 0.64.0 ships (research, spec, execute, wrapup); SPEC-world-model-followups
  IRR-001 and its AC-003 golden rows, and SPEC-hm-light-lane-s3a AC-012's
  golden rows, are amended to match.

## ✅ Acceptance Criteria

### AC-001: Maker carries the Advance rule
Both presets and runtimes, Maker contains exactly once

> ## Advance
>
> After a full-pipeline Start or Resume, when a stage reaches its final STOP, enter the next,
> same `<slug>`: `<execute>` after spec, `<wrapup>` after execute. Stop and report if it
> stopped earlier, an ask is unanswered, spec's status is not `approved`, the last `hm check` was
> not 0, a finding is `unresolved`, or `## Queued asks` has entries. Never push.

with `<execute>`/`<wrapup>` = `/hm:execute`/`/hm:wrapup` (Claude) or `$hm-execute`/`$hm-wrapup` (Codex).
- oracle_source: golden — the transitions, "never push" and "stops when a person is owed" come from
  the DRI's card ("Maker가 이어감"); the stop list is the enumeration of every early stop in
  `stages/spec.md.j2` and `stages/execute.md.j2` at e2743fd7 (spec-validator round 1).

### AC-002: Resume no longer reserves wrapup for the operator
Maker contains "`next_stage: wrapup` → ready to land." and not "the operator runs wrapup".
- oracle_source: golden — from the DRI's card (Maker runs wrapup).

### AC-003: hand-offs name the next command and the world model
Both runtimes: spec contains "`<execute> <slug>` is the user's call; if the world model began this
run, enter it now unless its Advance rule stops."; execute contains the same with `<wrapup>`; Codex `AGENTS.md` contains "the next one
is the user's call, or the world model's under its Advance rule." Neither stage contains
"`<next> <slug>` is the user's call." (the old sentence ending).
- oracle_source: golden — S4: the stage keeps naming the next command and never advances itself.

### AC-004: Maker's Choices rule follows exactly one blank line
Maker contains "\n\n**Choices.**" and not "\n\n\n**Choices.**".
- oracle_source: golden — markdown paragraph break; #40 review F1 intended one.

### AC-005: a live resumed task lands once, an unapproved one not at all
Opt-in live run (`HM_MAKER_ADVANCE_LIVE=1`). A scratch git project with a bare `origin`, rendered
with the Claude target, holds a seeded task `add-fn` (SPEC + machine.yaml, one AC: `add(a, b)`
returns `a + b`). `claude -p` is asked to have Maker continue `add-fn`.
- stamped `exempt` → the base branch gains exactly 1 commit and `origin`'s refs are unchanged;
- unstamped → the base branch gains 0 commits and `origin`'s refs are unchanged.
- oracle_source: golden — commit counts and remote refs read with `git`, independent of the
  transcript and of the template text.

### AC-006: the digest names only live stages
For every artifact set in SPEC-world-model-followups AC-003's golden table, and for an approved SPEC
with a REVIEW of each status (`in-progress`, `CHANGES_REQUESTED`, `APPROVED`) with or without the
verification marker, `next_stage` is one of `research`, `spec`, `execute`, `wrapup`; with a REVIEW
present it is `wrapup`.
- oracle_source: golden — the stage set is SPEC-hm-overhaul-p1's (four stages since 0.64.0), not
  the digest code.

## 🧪 Verification

| AC | mode | test |
|---|---|---|
| AC-001 | unit (render) | `tests/render/test_maker_advance.py::test_ac_001_maker_carries_the_advance_rule` |
| AC-002 | unit (render) | `tests/render/test_maker_advance.py::test_ac_002_resume_does_not_reserve_wrapup` |
| AC-003 | unit (render) | `tests/render/test_maker_advance.py::test_ac_003_hand_offs_name_next_command_and_world_model` |
| AC-004 | unit (render) | `tests/render/test_maker_advance.py::test_ac_004_choices_rule_single_blank_line` |
| AC-006 | unit | `tests/unit/test_world_model_digest.py::test_ac006_digest_names_only_live_stages` |
| AC-005 | integration (live, opt-in) | `tests/integration/test_maker_advance_live.py::test_ac_005_resumed_task_lands_once_unapproved_never` |

## ❓ Open Questions

None.

## 🔧 Refinement Decisions

- research → spec is excluded because research ends on a DRI choice card (default; inferred).
- Resume advances too, so "continue" after a session break reaches wrapup (default; the card named
  "same session", and a Resume is a new Start in that session).
- Maker's "Then the stage's own gates and STOP rules decide." line is replaced by Advance, which
  keeps the same meaning for the stops and adds the transitions.
- Round 2 (spec-validator, 9 critiques): Advance fires only on a stage's final print, and the stop
  list is enumerated instead of "an open question"; Maker reads spec's printed status, and execute
  Step 0 re-gates the approval stamp, so a status/stamp mismatch stops there; non-empty Queued asks
  stop the chain; hand-offs keep the next command and say "the world model" because stage
  templates have no world-model name in context; AGENTS.md and the four docs are in scope;
  `test_stage_invocation_syntax.py` keeps passing because "is the user's call" stays in the line;
  the live run (AC-005) answers the text-only-oracle critique for Claude Code.
- Live runs (AC-005) during execute: with the hand-off "or the world model's under its Advance
  rule" the model ended its turn at execute's STOP after a clean `hm check`, so the hand-off now
  tells it the rule applies at that point; the next run entered wrapup on its own. A later run
  still stopped once with "wrapup is your call", so the line now says to enter the next stage
  unless the rule stops. Live runs also showed Resume re-asking the other-session question when
  `other_session` is null, so the fixture seeds a span row from the resuming session. The live
  fixture renders with `--worktree` (the flag-off wrapup commits in place and never lands) and
  gives the scratch task a `.venv` with pytest, since `hm check` reads `<root>/.venv`.
- spec Step 5 prints the `approval-status` state with the SPEC path (the pointer moved there,
  validator round 1 critique 3), and its intro drops "and `/hm:execute` decides how to build" to
  stay inside the 6,500 budget.
- The AC-001 wording was compressed to fit Maker's 4,500-char cap (same stops, same transitions);
  spec's budget is handled as above.
- Found while seeding AC-005: the digest still derived `review`/`verify` (retired in 0.64.0), so a
  Resume after execute would enter a stage that no longer exists. Fixed here as AC-006 / IRR-002
  because S3 depends on it.
- The exempt zero-touch land went to the DRI as a card; work proceeds on the recommended option.
