---
type: spec
task_slug: ask-less
status: approved
created: 2026-11-10
tags: [harness-maker, spec, templates, ux, interview, intent-layer]
test_framework: pytest
interview_rounds: 0
summary: "hm asks the DRI only what the DRI owns (goal, scope, overall design, a main feature, a costly-to-undo decision, an approval, an intent decision); it decides everything else, including the intent link, oracles and plain intent records, and shows what it decided where the DRI approves."
---

# SPEC — ask-less (hm asks only what the DRI owns)

## Intent

The DRI, 2026-11-10 (thread "토큰 외 hm 개선점 구현"), verbatim: "너무 많이 물어보는 점이 있어.. 내가
대략적인 큰설계들은 알아야하고 큰결정사항, 주요기능 등에대해서는 알아야하지만, 너무 작은거, 그리고
인텐트 관련된것들 너무 자주 물어보는데 이부분 개선해야해". The same day the cost thread put about
ten cards in front of the DRI for one small SPEC.

The 0.65.3 templates ask in five places regardless of how small the choice is:

| # | where | what it asks today |
|---|---|---|
| 1 | `stages/_hm.md.j2` `choices()` (every stage, and Maker's copy) | "never choose for the user": every choice is a card |
| 2 | `stages/spec.md.j2` Step 0.5 | which intent the task serves, on every task once any intent exists |
| 3 | `stages/spec.md.j2` Step 2 | all six categories, `oracle_source` and `oracle_evidence` for every AC, closed questions unlimited |
| 4 | `stages/wrapup.md.j2` Step 5 | a multi-select of intent writes on every task with an intent in use |
| 5 | `skills/intent-layer/SKILL.md.j2` and its `references/workflow-feedback.md.j2` | a yes before every write, and a yes/no per proposed candidate |

CLAUDE.md's first goal already says who owns what: the human owns WHY, WHAT and trade-offs, the AI
takes HOW. The templates do not draw that line; this SPEC does.

## Outcomes

- **O1.** One rule, carried once by every stage and by Maker, names what the DRI decides and says
  the rest is decided by the agent and reported.
- **O2.** `/hm:spec` does not ask which intent a task serves; it picks one (or none) and says so.
- **O3.** The `/hm:spec` interview asks only DRI-owned slots, at most three questions a round. It
  settles constraints, the verification mapping and every oracle itself, and offers the approval
  as soon as nothing DRI-owned is open, round 1 included.
- **O4.** Every choice made for the DRI is listed in the SPEC's Refinement Decisions (what, why,
  cost to undo) and shown with the approval question.
- **O5.** `/hm:wrapup` writes plain intent records without asking, only for a SPEC the DRI
  approved, and prints each write at its close; anything that sets a verdict or closes an intent
  is asked.
- **O6.** The intent-layer skill and its workflow-feedback reference state the same split, and
  proposed candidates go on one multi-select question.

## In-Scope Scenarios

- **S1 (small, clear task).** Given a task whose goal, scope and features are plain from the ask,
  when `/hm:spec` runs, then the DRI sees the list of what was decided for them and one question,
  the approval, at every comprehension depth (the design brief comes with it unless depth is
  minimal).
- **S2 (one real choice).** Given a task with an open scope question, when the interview runs, then
  that question is asked and no question about oracles, the test framework or the verification
  mode is.
- **S3 (intent link).** Given one or more `active` or `proposed` intents, when `/hm:spec` reaches
  Step 0.5, then no question is asked, `intent: <id>` (or none) is written, and the pick is a line
  in Refinement Decisions.
- **S4 (wrapup, approved SPEC, intent in use).** Given a task whose approved SPEC names an intent,
  when `/hm:wrapup` reaches its intent step, then plain records are written without a question
  and each write is printed at the close.
- **S5 (verdict or close).** Given a wrapup where the agent wants to close the intent, resolve a
  claim, add a claim as `confirmed` or `wrong`, or supersede a claim, when it gets there, then it
  asks once and runs nothing without a yes.
- **S6 (no approval was shown).** Given a SPEC stamped `--exempt` (Step 0 skip, or `auto_full`),
  when `/hm:wrapup` reaches its intent step, then every intent write is asked, as today: nobody
  saw the intent link.
- **S7 (costly decision).** Given a choice that is costly to undo, in any stage, when it comes up,
  then it is asked, as today.
- **S8 (no question tool).** Given a host without the question tool, when a DRI-owned choice comes
  up, then it is a numbered list and the agent waits; agent-owned choices are still decided and
  reported.

## Non-Goals

- No new `harness.yaml` key and no per-project switch for how much hm asks.
- No change to what counts as approval: `hm spec_machine approve`, the `--exempt` rule, the
  irreversible-decision lock at wrapup and execute's stops are untouched.
- No Python change: the intent CLI never required a confirmation flag, and the wrapup receipt is
  not extended; the rule lives in the stage and skill text.
- No change to the always-loaded CLAUDE.md / AGENTS.md pointers, apart from the Maker size cap
  line if the cap has to rise.
- `/hm:health` and `/hm:uninstall` confirmations stay: they approve a destructive step.
- Creating an intent keeps its deep interview: a new intent is a goal.
- The stale "wrapup Step 5.7" pointer in the intent-layer skill is not fixed here.
- No measurement gate on question counts; the live check below is reported, not enforced.

## Constraints

| Constraint | Value |
|---|---|
| Test framework | pytest (mandatory) |
| Where the rule lives | hm templates only (stages, Maker, intent-layer skill and its reference), as in SPEC-choice-cards |
| Size | apart from rule R itself, the change adds no text: total rendered surface grows by at most (renders carrying R) × (`len(R)` − `len(old rule)`); a budget or cap that R pushes over rises by the measured growth only |
| Maker cap | `_MAKER_CAP` in `tests/render/test_render_maker_front_door.py`, the template comment, `docs/reference/world-model.md` and the CLAUDE.md line "Maker SKILL.md ≤ 4,539 chars" move together by the measured growth |
| Approval wording | SPEC-hm-cost-p5's sentence stays with both labels, "Approve this SPEC and end interview" and "Approve after spec-validator"; only its opening "From round 2" is replaced by the condition in AC-003. Both labels are offered whenever the approval is |
| Order | implemented after SPEC-hm-cost-p5 is on main (both edit `spec.md.j2` Steps 2 and 4.6) and after the fold of SPEC-pipeline-env-fixes (one surface allowance at a time); AC-007's base is main's tip at that point, pinned as a constant |
| Runtimes | Claude Code (`AskUserQuestion`) and Codex (`request_user_input`) render the same rule; "the tool" below means what `hm.ask()` renders |
| SPEC-choice-cards | its AC-002, AC-003 and AC-004 stay (sites a–m keep their anchor and tool name; they are the questions "this command names"); its AC-001 rule text is superseded by R, so `test_ac_001_commands_carry_the_choice_rule`'s literal moves to R |
| Superseded pins | `tests/unit/test_overhaul_p1_kept.py:671-672` ("ask the DRI once (…, multi-select)", "run only the selected writes; no answer runs none"; SPEC-hm-overhaul-p1 kept-list) move to AC-005's literals. `tests/unit/test_render_intent_layer.py:156-157, 195-196` ("ask about each candidate in turn"; SPEC-objective-gap-proposal) move to AC-006's multi-select literal. `tests/unit/test_render_intent_layer.py:233` (`metric measure` deferred to "The rule for every write"; SPEC-outcome-measure) stays true: the write rule still governs it and now says it is unasked |
| Rubric | `rubrics/world_intent_authority_and_progress.yaml.j2` judges "unauthorized writes"; its wording is aligned with IRR-001 so a plain record under an approved SPEC is not one |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | Under a SPEC the DRI approved (not `--exempt`), these intent writes need no per-write yes: `question add --status open`, `question observe --relation confirms` or `contradicts`, `metric measure`, and `metric record` with an `--evidence-file` taken from this task's artifacts. Every other intent write still needs one: `question add --status confirmed` or `wrong`, `question observe --relation supersedes`, `question resolve`, `new`, `approve`, `activate`, `drop`, `reopen`, `close`; and every intent write under an exempt SPEC | security/permission boundary | The DRI asked for it on 2026-11-10 ("인텐트 관련된것들 너무 자주 물어보는데"). A plain record adds an observation and changes no verdict; the DRI saw the intent link when approving the SPEC. A verdict, a superseded claim or a lifecycle step changes what the project believes or is trying to do. Rendered harnesses in the field change behaviour on upgrade |

## Acceptance Criteria

Rule text R (Claude Code; Codex reads "`request_user_input` where available" for the tool):

> **Choices.** The DRI decides the goal, scope, overall design, a main feature, a costly-to-undo decision and every approval, plus any question this command names: ask with `AskUserQuestion`, recommendation first, except approvals and equal options; without the tool, a numbered list, then wait. Decide the rest yourself and report it.

A "step" below is the text from its `## Step …` heading to the next `## ` heading. "The tool" is
the `hm.ask()` render for the runtime.

### AC-001: Every stage and Maker carries rule R once, and the old rule is gone
Both presets, both runtimes: each of the four stage renders and Maker contains R exactly once, and
no render under `.claude/` or `.agents/` contains "never choose for the user".
- oracle_source: golden. R is written here from the DRI's 2026-11-10 message and CLAUDE.md's first goal, before any template changes.

### AC-002: `/hm:spec` Step 0.5 picks the intent without asking
In both runtimes Step 0.5 does not contain the tool, and contains "pick the one this task plainly
serves, else none, without asking" and "Step 3 writes `intent: <id>` and lists the pick under
Refinement Decisions".
- oracle_source: golden (S3).

### AC-003: The interview asks only DRI-owned slots
In both runtimes Step 2 contains: "Ask only what the DRI owns: categories 1–4 and each
irreversible decision"; "at most 3 questions per round"; "Settle categories 5–6 and every oracle
yourself"; "Once nothing the DRI owns is open (round 1 included), one question per round offers";
"Approve this SPEC and end interview"; and "Approve after spec-validator". It does not contain
"Ask for `oracle_source`", "closed ones are unlimited" or "From round 2". The stage contains
"Approve this SPEC and end interview" at least twice.
- oracle_source: golden (S1, S2), plus the tool-count differential of AC-008.

### AC-004: Choices made for the DRI are written down and shown at approval
Step 3 contains "Refinement Decisions lists each choice you made for the DRI: what, why and the
cost to undo". Step 2 contains "Show your Refinement Decisions with the approval question", with no condition on
comprehension depth.
- oracle_source: golden (O4, S1).

### AC-005: `/hm:wrapup` writes plain records unasked, under an approved SPEC only
In both runtimes the wrapup stage's intent block (from "An intent in use" to the next `## `
heading) contains: "Under an approved SPEC (not `--exempt`), write without asking"; the four
record forms `question add … --status open`, `question observe … --relation <confirms|contradicts>`,
`metric measure` and "`metric record` with an `--evidence-file` from this task"; and "Anything
else, and every write under an exempt SPEC: ask once with" followed by the tool. The block names
the tool exactly once. Step 8 contains "then each intent write of Step 5". The stage no longer
contains "ask the DRI once (".
- oracle_source: golden (S4, S5, S6, IRR-001).

### AC-006: The intent-layer skill and its reference separate records from decisions
In both runtimes the skill's write rule contains the four record forms of IRR-001 as written
without asking under an approved SPEC, and the asked forms (`question add --status confirmed|wrong`,
`question observe --relation supersedes`, `question resolve`, `new`, `approve`, `activate`,
`drop`, `reopen`, `close`) with "showing the exact arguments"; "on any other answer or no answer —
write nothing" still follows the asked forms. Candidates: the skill contains "ask about all
candidates in one multi-select question" and "an unticked candidate is declined; no answer writes
nothing and records no decline", and keeps "answer every candidate before the first write".
Neither the skill nor `references/workflow-feedback.md` contains "Ask before writes", "Mutation
verbs write only after consent", "Workflow writes are consented once" or "ask about each
candidate in turn".
- oracle_source: golden (IRR-001, O6).

### AC-007: Apart from R, nothing gets longer
Against the render of the pinned base commit, for each runtime and preset: the summed size of the
four stage renders, Maker, the intent-layer skill and its workflow-feedback reference grows by at
most 5 × (`len(R)` − `len(old rule)`).
- oracle_source: differential. The base is rendered from a pinned SHA through `tests/_overhaul_p1_ref.py`'s `ref_root`, not from numbers typed into the test.

### AC-008: The number of places that name the question tool goes down
Against the same base, counting occurrences of the tool per render: the spec stage has exactly
one fewer; the wrapup stage has the same number; the research and execute stages and Maker have
the same number; the intent-layer skill has no more than before.
- oracle_source: differential. A count cannot be satisfied by rewording, and it is taken from the base render, not from this SPEC's literals.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1, S2 | render (unit) | test_ac_003, test_ac_004, test_ac_008 |
| S3 | render (unit) | test_ac_002, test_ac_008 |
| S4, S5, S6 | render (unit) | test_ac_005, test_ac_006 |
| S7, S8 | render (unit) | test_ac_001, and SPEC-choice-cards' `test_ac_002_choice_sites_name_the_question_tool` staying green |
| size | render (differential) | test_ac_007 |
| does the model follow it | manual, reported in the PR | one tier-1 bench cell on the hm arm before and after; count question-tool calls in the spec and wrapup turns |

## Open Questions

None.

## Refinement Decisions

The DRI's standing instruction for this thread (2026-11-10 13:26Z, verbatim: "나에게 묻지말고
이제부터는 모두 너의 추천대로 wrapup 후 push to. Main까지 진행해") replaces the interview: every
choice below is the recommended option, taken without a card, and the approval stamp is set under
that instruction; the design was reported to the DRI in the thread before any template changed. The spec-validator pass
(MAJOR_REVISION, 13 critiques, 2 critical) is folded in; both critical critiques changed the
design rather than being waved through.

- **Default — the line between "ask" and "decide" follows CLAUDE.md's first goal** (human: WHY,
  WHAT, trade-offs; AI: HOW) and the DRI's own words (big design, big decisions, main features).
  R names six things so the model has a list, not a judgement call. Cost to undo: one sentence.
- **Validator C1 (critical), accepted — R covers the overall design and any costly-to-undo
  decision,** not only irreversible ones. A small trade-off that is cheap to undo is the agent's
  and is reported; one that is costly to undo is the DRI's. Step 3's "Open Questions holds only
  what you cannot decide (a WHY, WHAT or trade-off the DRI owns)" stays and agrees with that.
- **Validator C2 (critical), accepted — a "record" is defined by its arguments, not its verb:**
  `question add --status confirmed|wrong` and `observe --relation supersedes` set a verdict and
  are asked.
- **Validator C3, accepted — unasked records need a SPEC the DRI approved.** On the Step 0 skip
  path and at `auto_full` nobody saw the intent link, so every intent write is asked there. An
  unasked `metric record` must carry evidence from this task.
- **Validator C4, C7, accepted — the reference file, the skill's description and the three pinned
  tests are in scope** (Constraints: Superseded pins, Rubric).
- **Validator C5, decided — an oracle critique from spec-validator is fixed by the agent and
  listed as a default;** it goes to Open Questions only when no independent oracle exists, which
  is then a trade-off for the DRI. An irreversible-decision critique is still never a default.
  Step 4.6's sentence changes accordingly; its pin `tests/unit/test_hm_cost_p3_templates.py:38`
  (SPEC-hm-cost-p3) now reads "an irreversible-decision critique is never a default", and its
  Step 3 pin (line 41) "Open Questions holds only what the DRI must decide";
  `tests/unit/test_schema_migration.py:143` pins "at most 3 questions per round" in place of the
  removed "(closed ones are unlimited)"; `tests/unit/test_hm_cost_p5_templates.py:76` (SPEC-hm-cost-p5
  AC-003, "does not grow") allows the measured +34 chars of the spec stage.
- **Validator C6, accepted — both approval labels are pinned,** so a round-1 approval can still be
  "Approve after spec-validator".
- **Validator C8, accepted — every helper is a literal in the AC text,** and AC-008 adds a count
  that rewording cannot satisfy.
- **Validator C9, accepted — unasked writes are printed in Step 8,** the step that prints the
  close, not only mentioned in the intent block.
- **Validator C10, C11, accepted — the base SHA is pinned; the Maker cap and its three mentions
  move by measured growth.**
- **Validator C12, accepted — R ends the DRI's list with "plus any question this command names",**
  so the kept question sites (research's next step, Maker's Start, Resume and "what next?") are
  not auto-picked.
- **Validator C13, accepted — the decided list is shown at approval at every depth.**
- **Default — this narrows "the full interview" the DRI listed as a non-negotiable on
  2026-10-15.** The interview keeps its six categories and its approval; it stops asking the DRI
  for categories 5–6 and for oracles, which the agent can settle from the repository.
- **Default — no `harness.yaml` knob.** A second mode is the complexity the first goal argues
  against; if asking less turns out wrong, the rule is one sentence to change back.
- **Default — the cap is three questions a round,** the upper end of what the intent skill already
  uses ("one to three"). The per-locale open-ended cap stays inside that.
- **Default — intent link: none for this SPEC.** It serves neither HM-LIGHT-LANE (cost) nor
  UNDERSTANDING-HANDOFF (wrapup summary).
- **Default — the live check is reported, not gated:** the bench's hidden tests cannot see
  questions, and one cell is not a measurement.
- **Default — implementation waits for SPEC-hm-cost-p5 and the SPEC-pipeline-env-fixes fold;** the
  cost thread confirmed its Step 2 edit changes only the approval sentence.
