---
type: spec
task_slug: world-model-name
status: approved
created: 2026-10-02
tier: 2
tags: [harness-maker, spec, python, jinja2, world-model, ux, skills, interview]
test_framework: pytest
interview_rounds: 3
intent: WORLD-INTENT-CLOSED-LOOP
research_doc: "[[RESEARCH-world-model-name]]"
summary: "Name the world model at onboarding (default Maker) and render a /<handle> router skill as the dev front door"
---

# SPEC — Named world model ("Maker") as the development front door

## 🎯 Intent

The world model (intent layer + project knowledge) and the seven `/hm:` stages are reachable only
through surfaces the operator must remember by name — two skills, ~20 `hm intent` verbs, seven
stage commands. The user wants to name the world model once, at onboarding (default `Maker`),
and then develop by talking to it: one addressable entry point that routes plain-language
requests to the machinery that already exists. This is the user's own `bibi` UX applied to the
project harness.

## 🌅 Outcomes

- During onboarding the operator names the world model right after choosing a locale; pressing
  Enter keeps `Maker`.
- Every rendered harness has a `/<handle>` skill (`/maker` by default; `$maker` on Codex) whose
  description and the always-loaded pointer carry the display name, so both `/maker …` and
  "Maker, …" reach it.
- Through that one entry point the operator can get a read-only briefing, start new work, resume
  the next stage, record a project fact, and work with intents/metrics — without knowing which
  skill or command owns the request.
- Names that cannot be a skill name ("비비", "메이커") still work: the display name stays as typed,
  and a separate ASCII handle is asked for.
- Existing harnesses pick this up on re-render with `Maker`/`maker`, and renaming leaves no
  stale entry point behind.

## 📋 In-Scope Scenarios

### S1: Fresh onboarding keeps the default
**Given** a project with no `.claude/harness.yaml`
**When** the operator runs the onboarding interview and presses Enter at the question asked right after locale
**Then** `harness.yaml` contains `world_model: {name: Maker, handle: maker}`
**And** `.claude/skills/maker/SKILL.md` is rendered with frontmatter `name: maker` and a description containing `Maker`
**And** when `codex` is a target, `.agents/skills/maker/SKILL.md` is rendered too

### S2: A name with no ASCII handle
**Given** the onboarding interview at the name question
**When** the operator enters `비비`
**Then** the interview asks once for a handle (default `maker`) because none can be derived
**And** `harness.yaml` stores `name: 비비` and the chosen handle, and the skill description contains `비비`

### S3: Old harness.yaml without the key
**Given** a `harness.yaml` written before this change (no `world_model` key)
**When** the harness is re-rendered
**Then** the output is byte-identical to a render whose yaml declares `world_model: {name: Maker, handle: maker}`

### S4: Rename
**Given** a rendered harness with handle `maker`
**When** the operator changes the name to `Atlas` (via `/hm:configure` or the Full reconfigure path) and re-renders
**Then** `.claude/skills/atlas/SKILL.md` exists
**And** a pristine `.claude/skills/maker/SKILL.md` is removed, while one the operator edited is kept

### S5: Invalid or colliding handle
**Given** the name/handle question (interactive, `--ci`, or configure)
**When** the handle is `intent-layer`, `hm-research`, `Maker!`, `-x`, `a--b`, or longer than 64 characters
**Then** it is rejected with a locale message naming the rule
**And** `harness.yaml` is not modified

### S6: Always-loaded pointer
**Given** any rendered harness
**When** the always-loaded files are rendered (the four CLAUDE.md variants, `AGENTS.md`, `.cursor/rules/harness.mdc`)
**Then** each contains a short "world model" pointer naming the display name and how to invoke the handle (`/<handle>` or `$<handle>` on Codex)
**And** the existing character-budget and AC-005 pointer-cap tests still pass

### S7: Routing through the front door
**Given** a rendered harness and the operator invokes `/<handle>` or addresses the display name
**When** the request is (a) empty, (b) "build/fix X", (c) "continue", (d) "remember X" or "X is wrong", (e) about a goal, metric or assumption, (f) "what next?"
**Then** (a) a read-only briefing of changed state — active task worktrees and their last stage, autopilot state, `hm intent status` — is shown and nothing is written;
(b) the router picks `/hm:research` (unfamiliar or vague) or `/hm:spec` (already concrete), states why in one line, and enters it;
(c) with exactly one active task it resumes that task's next stage, with two or more it asks one closed question listing slug + last stage;
(d) it follows `project-knowledge`; (e) it follows `intent-layer` with that skill's consent rule unchanged;
(f) it presents options and starts no stage
**And** every reply opens with the display name and uses the harness voice (direct, concerns first, no persona)

### S8: Re-render preserves the choice
**Given** a `harness.yaml` with any valid `world_model`
**When** it is loaded and re-rendered through the Update path
**Then** `world_model` in the written `harness.yaml` equals the original

### S9: Non-interactive setup
**Given** `/harness-maker:make --ci … world_model_name=Atlas` (optionally `world_model_handle=atlas`)
**When** the CLI runs
**Then** `harness.yaml` stores `name: Atlas, handle: atlas` and `.claude/skills/atlas/SKILL.md` is rendered

## Acceptance Criteria

### AC-001: onboarding asks the name right after locale and defaults to Maker
Covers S1. The Python interview and `commands/make.md` both ask it immediately after locale.

### AC-002: the router skill renders at the handle path with the display name
Covers S1, S2, S9. `.claude/skills/<handle>/SKILL.md` (and `.agents/skills/<handle>/SKILL.md` for codex) has `name: <handle>` and a description containing the display name.

### AC-003: derived handles always satisfy the skill name rule
Covers S2. Handle derivation returns either nothing (then the interview asks) or a valid name.

### AC-004: an absent world_model key renders identically to the explicit default
Covers S3.

### AC-005: renaming removes the pristine old router skill and keeps an edited one
Covers S4.

### AC-006: invalid or colliding handles are rejected without touching harness.yaml
Covers S5.

### AC-007: every always-loaded file names the world model and its handle within budget
Covers S6.

### AC-008: world_model survives load and re-render unchanged
Covers S8.

### AC-009: ci flags set the world model name and handle
Covers S9.

### AC-010: the router skill routes each request class to the existing surface
Covers S7. Judged against the rendered skill body plus a manual dogfood pass.

### AC-011: configure offers the world model name as a dimension
Covers S4. `/hm:configure` lists "World model name" and re-renders with the new value.

## 🚫 Non-Goals

- No new `hm` CLI verb (no `hm maker brief/next` aggregator) — the briefing is composed in the
  skill from existing read-only commands. A follow-up only if measured slow or inconsistent.
- No persona: no emoji prefix, no identity/SOUL file, no coaching or learning mode.
- No new state store or memory for Maker; it reads and routes only.
- No change to the gates, consent rules or behaviour of the stages, `intent-layer` or
  `project-knowledge` — Maker routes to them unchanged.
- No renaming of the existing `intent-layer` / `project-knowledge` skills.
- No opt-out switch in v1 — the router skill is always rendered.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo standard (CLAUDE.md) |
| Handle format | `^[a-z0-9]+(-[a-z0-9]+)*$`, 1–64 chars | Agent Skills spec `name` rule; must equal the directory |
| Reserved handles | every rendered skill name, every `hm-<stage>` Codex skill, any `hm-` prefix | Collision would shadow or overwrite a shipped skill |
| Config schema | `HarnessConfig` stays `strict=True, extra="forbid"`; new sub-model with defaults | Absent key must default (absent-case rule) |
| Always-loaded cost | pointer adds ≤ 200 chars per variant; CLAUDE.md char budgets unchanged | Every always-loaded byte is carried every turn |
| Language | Python only; display name may be any Unicode; persisted docs English | CLAUDE.md |
| Runtimes | Claude Code, Cursor (`.claude/skills/` native), Codex (`.agents/skills/`, `$handle`) | targets axis |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add `world_model: {name, handle}` to `harness.yaml` | schema/file format/storage layout | `extra="forbid"` means older plugin CLIs reject a yaml carrying it; once in users' files the shape is hard to change |
| IRR-002 | `/<handle>` / `$<handle>` invocation and `--ci world_model_name=` / `world_model_handle=` flags | public API/CLI contract | Operators and scripts will depend on the handle and flag names |
| IRR-003 | A rendered path (`skills/<handle>/`) is chosen by user input | schema/file format/storage layout | First user-determined render path; rename correctness depends on orphan sweep |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_ac001_interview_default_maker`, `test_ac002_router_skill_rendered` |
| S2 | unit | `test_ac003_handle_derivation_property`, `test_ac001_non_ascii_asks_handle` |
| S3 | unit | `test_ac004_absent_key_matches_explicit_default` |
| S4 | integration | `test_ac005_rename_sweeps_pristine_keeps_edited` |
| S5 | unit | `test_ac006_invalid_handle_rejected` (parametrized) |
| S6 | unit | `test_ac007_pointer_in_every_always_loaded_variant` + existing budget tests |
| S7 | manual + judgment | dogfood: `/maker`, `/maker 이어서`, `/maker 다음 뭐?`, `/maker 기억해 …` in this repo after re-render; judgment-reviewer against the `skill` rubric |
| S8 | unit | `test_ac008_world_model_roundtrip_property` |
| S9 | unit | `test_ac009_ci_flags_set_world_model` |

Test modules: `tests/unit/test_world_model.py`, `tests/render/test_render_world_model.py`.

## ❓ Open Questions

None blocking. Execute Step 0 decides as design ADRs:
- Module placement of handle derivation/validation (a small `world_model.py` is assumed by
  `paths_to_mutate`).
- Exact collision source of truth (derive the reserved set from the render blueprint, not a
  hand list).
- Whether the briefing reads task stage from `stage-spans.jsonl` or the worktree list alone when
  observability is absent (must degrade, not fail).

## 🔍 Refinement Decisions

- Round 1: intent `WORLD-INTENT-CLOSED-LOOP`; v1 = full front door; non-ASCII name → derive
  handle, ask only when derivation fails (default `maker`); harness voice, name on first line.
- Round 2: "build X" → LLM chooses research vs spec with a one-line reason, no confirm;
  "continue" → resume if one active task, closed question if several.
- Round 3: IRR-001..003 recorded; DRI approved the SPEC.
- Defaulted (stated in the design brief): all four interview surfaces (make slash, Python CLI,
  `--ci`, configure); no opt-out switch in v1; `pytest`.

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| RESEARCH/SPEC: "continue" resumes the next stage without the user re-stating the connection | WORLD-INTENT-CLOSED-LOOP / intent_world_closed_loop_cycles | recorded | metric record intent_world_closed_loop_cycles = 1 (operator: yes) | DRI | wrapup Step 5.7 answer | wrapup Step 5.7 decides |

## 🔎 Spec Validation

`spec-validator` single pass (advisory, codex second opinion skipped — usage limit):
**MAJOR_REVISION**, recorded after DRI approval. `/hm:execute` Step 0 must resolve each as an ADR
or AC refinement; none changes the approved scope.

| Sev | Finding | Required resolution at execute |
|---|---|---|
| critical | Reservation enforced only at prompts; a derived or hand-edited handle (`project-knowledge`, `hm-research`) can overwrite a shipped skill | Grammar + reservation become a `HarnessConfig` load-time invariant; derived handles pass the same check or fall back to ask/default; tighten AC-003 relation to `None or (grammar and not reserved)` |
| critical | AC-007 rows use only the default, so a hardcoded `/maker` passes and dangles after rename | Add non-default rows (Atlas/atlas, non-ASCII name); assert `/maker` absent when handle is `atlas`; every advertised handle resolves to a rendered skill |
| critical | AC-010 rubric `skill` measures none of S7's routes | Author a router rubric whose items are S7(a)-(f), incl. "(a) writes nothing" and "(f) starts no stage" |
| critical | `commands/make.md` slash path (question after locale, `--ci world_model_name=` parsing, dispatch forwarding) has no AC | Add rendered-text predicates on `commands/make.md` for §1 follow-up question, §0 parsing and every dispatch block |
| warning | AC-005 asserts deletion only; edited-kept and `.agents/` arms missing | Parametric rows {pristine→deleted, edited→kept} × {`.claude`, `.agents`} |
| warning | AC-011 checks the menu label, not the dispatch flag | Assert configure's dispatch forwards the world-model flags |
| warning | `hm cli make --world-model-name/--world-model-handle` flags are an unlisted contract | Fold the flag pair and omit/empty semantics into IRR-002 |
| warning | Display name unbounded (newline, quotes, length) but lands in frontmatter and a 200-char pointer | Name constraint (single line, max length) as an AC-006 row; `max_chars` on AC-007 |
| warning | `--ci world_model_name=비비` with no handle is undefined | Pick one outcome (default `maker` or non-zero exit) as an S9 row |
| warning | No AC bounds the router description's trigger (risk: fires on "make the test pass") | Description triggers on display name / handle only, not generic build/make/fix verbs |
| warning | Cursor `/<handle>` golden row unverified (RESEARCH OQ7) | Verify, or word the Cursor pointer with the display name only |
| suggestion | AC-003 `h` unbound | `(h := derive_handle(name)) is None or …` |
| suggestion | Partial key `{name: Atlas}` without handle undefined | Derive handle from name in the validator; state it |
