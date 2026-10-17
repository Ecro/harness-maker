---
type: spec
task_slug: choice-cards
status: approved
created: 2026-10-17
tags: [harness-maker, spec, templates, ux, question-tool]
test_framework: pytest
interview_rounds: 1
lane: full
parent_spec: "[[SPEC-hm-overhaul-p1]]"
summary: "Every choice an hm command or Maker asks the user goes through the host's question tool (AskUserQuestion / request_user_input) as a closed-option card (recommendation first, except approvals and equal options); without the tool, the same options as a numbered list and wait. Thirteen prose-only choice sites are converted, stale Cursor `AskQuestion` mentions go, and /hm:spec exempts only at auto_full (IRR-001)."
---

# SPEC — choice-cards (every user choice in an hm render is a question-tool card)

## 🎯 Intent

The DRI (2026-10-17, thread "HM-LIGHT-LANE 기록과 구현") wants every choice the user has to make
offered as a choice card. On cards the DRI picked "hm templates only" for where the rule lives, and
"hm commands and skills only" (not the always-loaded CLAUDE.md/AGENTS.md). Today the interviews
(`/hm:spec`, `/hm:research`), the intent-layer skill, `/hm:health` and `/hm:uninstall` use the
question tool. The choice sites below, grepped from the 19c7ee89 render, ask in prose and name
no tool, so the model may print a question and a bullet list instead of a card:

| site | template | anchor (literal, survives the change) | today |
|---|---|---|---|
| a | stages/execute.md.j2 | `or a missing SPEC, stops` | "ask the DRI to approve with `hm spec_machine approve …`, or point at `/hm:spec`" |
| b | stages/execute.md.j2 | `then stop and ask the DRI` | irreversible choice found in Phase C |
| c | stages/execute.md.j2 | `approval is missing or invalid; ask the DRI` | exit 5 |
| d | stages/wrapup.md.j2 | `5: ask the DRI` | Step 1 exit 5 |
| e | stages/wrapup.md.j2 | ``On `land: hold`, show each `irreversible` decision`` | "ask once: approve runs …, keep stops" |
| f | commands/hm/make.md.j2 | ``**`decision_needed: true`** — ask`` | commit-or-not, options as equals |
| g | commands/hm/make.md.j2 | ``**`offer_stage: true`**`` | "Ask \"Stage the new harness files into a commit?\"" |
| h1 | skills/world-model/SKILL.md.j2 | `No task → say so, offer **Start**` | Resume 1 |
| h2 | skills/world-model/SKILL.md.j2 | `→ ask once first` | Resume 2, other session |
| j | stages/wrapup.md.j2 | ``Ask only on `[finalize] stash-pop conflict` `` | stash-pop / untracked-file collision |
| k | skills/world-model/SKILL.md.j2 | `Two or more → ONE closed question` | Resume 3 |
| l | stages/research.md.j2 | `Offer two ways on` | `/hm:spec` or dig deeper |
| m | skills/world-model/SKILL.md.j2 | `then 2–4 one-line options` | "what next?" |
| i | commands/hm/health.md.j2, uninstall.md.j2 | — | "Use `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code)"; Cursor was removed in 0.63.0 |

Codex exposes `request_user_input` only where its mode allows (the intent-layer skill already
says "only where allowed"), and the eval bench answers stages by resuming a headless session, so
a card-or-nothing rule would stall both. Without the tool, the same options go out as a numbered
list and the model waits.

That fallback meets `/hm:spec` Step 5, which today treats "no question tool" as "the DRI was not
asked" and may stamp `--exempt`. With the list, the DRI is asked, so the exempt branch narrows to
`auto_full`, and the DRI's own reply choosing "Approve" counts as approval (IRR-001, DRI card).

## 📐 Outcomes

- Each of the four stage commands (Claude `.claude/commands/hm/<stage>.md`, Codex
  `.agents/skills/hm-<stage>/SKILL.md`) carries one **Choices** rule naming that runtime's tool and
  the numbered-list fallback; Maker (both runtimes) carries the same rule.
- Every site in the table names the question tool right after its anchor; site i names no
  Cursor tool.
- `/hm:spec` Step 5 exempts only at `auto_full`.
- `/hm:make` site f keeps its options as equals (no recommendation); approval gates (a, b, c,
  d, e) carry no recommendation.

## 🎬 In-Scope Scenarios

### S1 — A stage reaches a DRI choice in Claude Code
- **Given** a Claude Code render and `/hm:execute` finds the approval missing
- **When** the model reaches the approval gate
- **Then** the stage text tells it to ask with `AskUserQuestion`, with no recommended option

### S2 — The same choice in Codex where the tool is unavailable
- **Given** a Codex render (a stage or Maker)
- **When** `request_user_input` is unavailable
- **Then** the text tells it to print the options numbered and wait, never choosing for the user

### S3 — A SPEC approved through the numbered list
- **Given** `/hm:spec` without a question tool and no irreversible decisions
- **When** the DRI does not answer the approve option
- **Then** the SPEC is left unstamped, not `--exempt` (exempt is only for `auto_full`)

### S4 — Re-rendering a pristine harness
- **Given** a project rendered by 0.64.0 with unedited stage files
- **When** `/hm:make` re-renders
- **Then** the stage files carry the rule; files the user edited are KEPT and reported, as today

## 🚫 Non-Goals

- The rendered CLAUDE.md / AGENTS.md (always loaded): the DRI chose "hm commands and skills only".
- Sub-agents (they have no question tool).
- Python CLI prompts and the interview's content, rounds or categories.
- This project's own Claude sessions (memory only, per the DRI's card).
- `autonomy.level: auto_full` steps that proceed unasked stay unasked.

## 🔒 Constraints

| constraint | value |
|---|---|
| test framework | pytest (`tests/render/`) |
| surface | SPEC-hm-overhaul-p1 AC-004 stage budgets hold; aggregate growth is a PLAN `surface_allowance`, folded after merge |
| Maker | SKILL.md ≤ 4,500 chars (`tests/render/test_render_maker_front_door.py` `_MAKER_CAP`) |
| runtimes | Claude Code and Codex renders, both presets |
| no Python change | templates and tests only |

## ⚠️ Irreversible Decisions

- IRR-001 (security/permission boundary): without a question tool, the DRI's own reply choosing
  "Approve" in a numbered list counts as SPEC approval, and `/hm:spec` Step 5's `--exempt` branch
  no longer opens on "no question tool" (only `auto_full`).

## ✅ Acceptance Criteria

### AC-001: Every stage command and Maker carries the Choices rule for its runtime
Both presets, both runtimes: each of the 4 stage renders and Maker contains exactly once

> **Choices.** Ask each choice with `AskUserQuestion`; recommendation first, except approvals and
> equal options. Without the tool: a numbered list, then wait; never choose for the user.

(Codex: "with `request_user_input` where available;" in place of "with `AskUserQuestion`;").
Amended 2026-10-17 (DRI card): the round-1 text was ~330 chars per stage and broke the AC-004 stage
budgets; batching stays in the spec interview's own text.
- oracle_source: golden. The text is fixed here from the DRI's request, before any template changed.

### AC-002: Each listed choice site names the question tool after its anchor
For every site a-m, in each runtime that renders the file, the anchor occurs, and the runtime's
tool name occurs within 200 characters after the anchor's end, with no blank line between them.
- oracle_source: golden. The site rows (template, literal anchor) are the Intent table, taken from
  the 19c7ee89 render before any template changed.

### AC-003: No render names Cursor's `AskQuestion`
No file under `.claude/` or `.agents/` in either preset contains `AskQuestion`.
- oracle_source: golden. Cursor was removed in 0.63.0 (SPEC-hm-overhaul-p1 IRR-001).

### AC-004: `/hm:spec` exempts only at `auto_full`
In both runtimes, the rendered spec stage contains "and the DRI was not asked (`auto_full`)." and
does not contain "or no question tool".
- oracle_source: golden. From IRR-001.

## 🧪 Verification

| AC | mode | test |
|---|---|---|
| AC-001 | unit (render) | `tests/render/test_choice_cards.py::test_ac_001_commands_carry_the_choice_rule` |
| AC-002 | unit (render) | `tests/render/test_choice_cards.py::test_ac_002_choice_sites_name_the_question_tool` |
| AC-003 | unit (render) | `tests/render/test_choice_cards.py::test_ac_003_no_render_names_cursor_askquestion` |
| AC-004 | unit (render) | `tests/render/test_choice_cards.py::test_ac_004_spec_exempts_only_at_auto_full` |

## ❓ Open Questions

None.

## 🔧 Refinement Decisions

- Lane `full`: about eight template files across two runtimes, plus IRR-001.
- The fallback is a numbered list, not a hard stop. Codex limits `request_user_input` by mode, and
  the bench answers by resuming headless sessions. This is a default; it was inferred, not asked.
- "Other" is not in the rule because Claude Code's tool adds its own. The spec interview keeps
  its explicit "Other — let me describe".
- Approvals and `/hm:make`'s equal options carry no recommendation (spec-validator round 1).
- The Codex wording is "where available" and does not claim Plan-mode-only, which is unverified
  (spec-validator round 1).
- One macro in `stages/_hm.md.j2` renders the rule in the stages. Maker gets its own copy because
  it does not import `_hm`.
- Step 0's skip path still stamps `--exempt` without asking at any autonomy level: it is the
  trivial-change path, not an interview, so AC-004 covers Step 5 only (code-reviewer F5).
