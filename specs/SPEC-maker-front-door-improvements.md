---
type: spec
task_slug: maker-front-door-improvements
status: approved
created: 2026-10-03
tags: [harness-maker, spec, python, jinja2, front-door, intent-layer, autopilot, token-economy]
test_framework: pytest
interview_rounds: 2
intent: WORLD-INTENT-CLOSED-LOOP
research_doc: "[[RESEARCH-maker-front-door-improvements]]"
tier: 2
summary: "Maker becomes the only entrance and owns intents/knowledge; scope, load and retrieval fixes"
---

# SPEC — Maker as the only entrance and owner of the world model

## 🎯 Intent

0.61.0 unified the front door in name only: `intent-layer`, `project-knowledge`, an always-loaded
pointer and `/hm:help` still act as entrances, and the intent layer — the core of the world model —
is owned outside Maker. The operator's ask is also lost at the handoff (a research-only request runs
the whole autopilot pipeline), the injected briefing can abort Maker's load, Maker use is
unmeasurable, and the research stage's memory retrieval spends ~30 KB on mostly irrelevant entries.

## 🌅 Outcomes

- Intent and knowledge requests reach their procedures only through Maker (hard block on the skills);
  typing a skill name still runs it. An unnamed goal, fact or status request — even mid-stage — is
  routed by the always-loaded pointer to Maker's procedure, so the front door has no gap. For `/hm:*` stages the block is advisory (description
  gating), because Maker handoff, autopilot advance and `/hm:loop` invoke them model-side.
- Maker answers read-only "where are our goals?" from its briefing: active intents with metric
  progress. Intent or knowledge edits go through the procedure, consent rule unchanged.
- "Research this" ends at research even with autopilot armed; the operator's full pipeline is
  restored afterwards, and the route line names the end point.
- Maker always loads on Claude Code, even when the digest command cannot run.
- Every Maker load — typed, model-invoked or Codex — is countable from local observability.
- The operator can keep talking to Maker while a stage runs without breaking it: Maker answers as a
  short aside, records any decision, queues new work instead of starting it, and the stage resumes at
  the same step.
- Research-only tasks stop crowding the briefing.
- A decision made in conversation about an in-flight task is written to that task's most downstream
  artifact before the reply ends, and the briefing shows each task's latest artifact and time, so a
  resume after a pause or compaction does not silently proceed on a stale artifact.
- `hm memory_retrieve` output is bounded and lexical hits are never crowded out.

## 📋 In-Scope Scenarios

### S1: Unnamed intent request does not self-trigger
**Given** a rendered harness and no mention of Maker
**When** the operator says "change the goal"
**Then** neither `intent-layer` nor `project-knowledge` is model-invocable (`disable-model-invocation: true` on Claude Code/Cursor; `policy.allow_implicit_invocation: false` on Codex)
**And** typing `/intent-layer` (or `$intent-layer`) still runs it
**And** the always-loaded pointer routes the request to Maker's procedure instead

### S2: Named intent edit is handled by Maker through the procedure
**Given** the operator asks Maker to change a goal or record a project fact
**When** Maker routes it
**Then** Maker Reads the target runtime's procedure file before any `hm intent` / `hm memory_md` call and follows its consent rule unchanged
**And** a read-only goal question is answered from the briefing without reading the procedure

### S3: Briefing shows active intents
**Given** `.claude/intent.yaml` with active intents linked to metrics
**When** the digest runs
**Then** at least the first 3 active intents (all, when fewer) appear with `metric_id`, `last`, `target`, `gap` equal to `hm intent status --json`; an intent without metric data shows `—`
**And** the rendered digest stays ≤ 1,500 bytes, trimming `recent` first, then intents beyond 3, then tasks — never below 3 task rows

### S4: Research-only ask stops at research, then the pipeline is restored
**Given** this session's autopilot armed with the full pipeline
**When** the operator asks Maker to research X
**Then** Maker runs `hm autopilot narrow --until research` and names the end point in its route line
**And** the research boundary returns `proceed: false`, after which the marker's pipeline is restored to the pre-narrow value with level, `created_at` and session unchanged

### S5: Narrowing never widens autonomy
**Given** autopilot off, a foreign marker, an end stage already passed, or a pipeline already narrower than E
**When** `hm autopilot narrow --until E` runs
**Then** it arms nothing, changes no level/TTL/foreign marker, never extends the pipeline, and exits 0 with a reason; Maker only announces the end point

### S6: Digest command fails
**Given** the digest cannot run (missing cache path, missing executable, failure after partial output)
**When** Claude Code loads Maker
**Then** the injected line exits 0 with exactly one JSON object containing `unavailable`, Maker loads, and the fallback instruction is reachable
**And** when the digest succeeds the injected output is the digest JSON

### S7: Maker load is recorded
**Given** any Maker load (typed, model-invoked, Codex run-block)
**When** `hm world_model digest` runs
**Then** it appends one `{ts, event: "maker_load", session_id}` row to a jsonl under `.claude/observability/`, with no request text, and still exits 0 if the write fails

### S8: Research-only task is parked
**Given** a task whose only artifact is `RESEARCH-<slug>.md` with frontmatter `created` more than 7 days before today
**When** the digest runs
**Then** the task carries `parked: true` and sorts after every non-parked task; any SPEC/PLAN/REVIEW or a commit on `hm/<slug>` beyond the base unparks it

### S9: Memory retrieval is bounded and lexical-first
**Given** a corpus with many high-recurrence entries unrelated to the topic
**When** `hm memory_retrieve --k 6` runs
**Then** output ≤ 8,192 bytes; the first min(6, |eligible lexical hits|) entries are lexical hits; floor entries only fill the rest; each dated entry shows only its newest bullet; undated entries are kept

### S10: Unnamed request mid-stage keeps the front door
**Given** a stage (e.g. `/hm:spec`) is running and Maker was not named
**When** the operator states a goal change, a project fact or asks where things stand
**Then** the always-loaded pointer directs the model to Maker's procedure (Read) for that request, consent rule unchanged
**And** ordinary coding asks ("build/fix X") are not captured by it

### S11: Conversation decisions survive a pause
**Given** an in-flight task and a conversation that changes its scope or a decision after a stage stopped
**When** the reply ends
**Then** the change is written to the task's most downstream artifact (PLAN, else SPEC, else RESEARCH) before replying
**And** the next digest lists that task with `latest_artifact` = that file and its modification time

### S12: Talking to Maker mid-stage does not break the flow
**Given** a stage is running (e.g. `/hm:execute` Phase C)
**When** the operator addresses Maker or asks a status, goal, fact or new-work question
**Then** the reply is an aside opening `<Name> —`, at most 6 lines, with any decision recorded per S11
**And** a new-work ask is appended to the current task's most downstream artifact under `## Queued asks` and offered at the stage's STOP, never started mid-stage
**And** the aside ends with one line naming the stage and step being resumed, and the stage continues

## 🚫 Non-Goals

- SessionStart briefing injection (rejected again, 2026-10-03).
- Hard-flagging `/hm:*` stages.
- Merging intent-layer / project-knowledge bodies into Maker's SKILL.md (progressive disclosure instead).
- Changing intent consent rules, `hm intent` verbs, autopilot caps, levels or stage gates.
- Adding `skill` to the PostToolUse telemetry allowlist.
- Verifying `!` behaviour in Cursor; S6 is Claude Code only.
- Carried P2s from REVIEW-world-model-followups (whole span-ledger read, `index.lock` in `_verify_done`, vanishing worktree).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` (+ `hypothesis` for property ACs) | repo standard (CLAUDE.md) |
| Digest size | ≤ 1,500 bytes rendered (unchanged `MAX_BYTES`) | always-on Maker cost |
| World-model pointer | ≤ 400 chars per variant at NAME_MAX/HANDLE_MAX (was 200, SPEC-world-model-followups AC-013) | it now carries the routing and decision-capture rules every turn |
| Maker SKILL.md | ≤ 4,500 chars rendered, every target (0.61.0: 3,745) | router stays thin |
| memory_retrieve | ≤ 8,192 bytes; whole entries only; never cut mid-codepoint | observed 30 KB |
| Marker field | every `.hm-autopilot*` reader updated for the new field | CLAUDE.md multi-session invariant |
| Observability | local only; no request/args text | ADR-107 secret surface |
| Compatibility | Claude Code, Cursor ≥ 2.4, Codex | targets axis |
| Runtime | Python 3.12, `mypy --strict`, `ruff` | repo standard |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | `intent-layer` and `project-knowledge` render with `disable-model-invocation: true`; reachable only by typing or via Maker's Read | public API/CLI contract | changes how every rendered harness reaches these skills |
| IRR-002 | New rendered file `.agents/skills/<name>/agents/openai.yaml` with `policy.allow_implicit_invocation: false` | schema/file format/storage layout | new owned path; orphan sweep and ownership must track it |
| IRR-003 | `hm world_model digest` JSON gains `intents.active[]`, task `parked` and task `latest_artifact` | public API/CLI contract | consumed by rendered Maker templates |
| IRR-004 | `hm world_model digest` appends a `maker_load` row to a local observability jsonl | schema/file format/storage layout | digest stops being write-free; new persisted row shape |
| IRR-005 | Maker may narrow the session's autopilot pipeline (reverses PLAN-world-model-name ADR-008 "routes only") | security/permission boundary | the router now changes autonomy state |
| IRR-006 | `hm memory_retrieve`: floor fills only slots lexical hits leave empty; newest bullet per entry; 8,192-byte cap drops whole floor entries first | public API/CLI contract | every stage's retrieval output changes |
| IRR-007 | New CLI verb `hm autopilot narrow --until <stage>` | public API/CLI contract | new verb rendered templates call |
| IRR-008 | Autopilot marker gains a restore-pipeline field | schema/file format/storage layout | every marker reader must accept it |

## ✅ Verification Criteria

### AC-001: Intent and knowledge skills are not model-invocable
Rendered `intent-layer` and `project-knowledge` SKILL.md frontmatter carry `disable-model-invocation: true` for Claude Code/Cursor targets.

### AC-002: Codex implicit invocation is off for the same skills
With `codex` in targets, `.agents/skills/{intent-layer,project-knowledge}/agents/openai.yaml` contains `policy.allow_implicit_invocation: false`; removing `codex` from targets sweeps it.

### AC-003: Stage descriptions are entrance-gated
Every rendered `/hm:` stage description states it runs only when typed, routed by Maker, advanced by autopilot or driven by `/hm:loop`, contains no natural-language trigger phrase, and carries no `disable-model-invocation`.

### AC-004: Always-loaded pointers and help route to Maker
The project-knowledge pointer names the Maker invocation for natural-language intent/knowledge requests, and `/hm:help` rows for both skills contain `typed only`.

### AC-005: Maker reads intent and knowledge procedures on demand
For every target the rendered Maker instructs a Read of that runtime's procedure path before any edit verb, states the consent rule is unchanged, answers read-only goal questions from the briefing, and is ≤ 4,500 chars.

### AC-006: Briefing shows active intents within the byte cap
The digest lists at least min(3, active) intents with metric fields equal to `hm intent status --json`, shows `—` for missing metric data, keeps ≥ min(3, tasks) task rows, and renders ≤ 1,500 bytes.

### AC-007: Maker maps the ask to an end stage
The rendered Maker instructs narrowing to the ask's end stage, naming it in the route line and resolving ambiguity to the narrower end; the mapping is checked against a fixed phrasing table.

### AC-008: Narrow stops at the end stage and restores the pipeline
After `narrow --until E` on a full pipeline at an advancing level, every stage before E proceeds, E stops, and the marker's pipeline then equals the pre-narrow value with level, `created_at` and session unchanged.

### AC-009: Narrow never widens autonomy
`narrow` arms no unarmed session, leaves foreign markers, levels and `created_at` untouched, never extends a narrower pipeline, and exits 0.

### AC-010: Injected digest command never aborts Maker
The rendered injected command exits 0 with exactly one JSON object for success, missing cache, missing executable and partial-output failure; only failures contain `unavailable`.

### AC-011: Every digest run records one maker_load row
Each `hm world_model digest` run appends exactly one `maker_load` row without request text, and an unwritable observability dir still exits 0.

### AC-012: Stale research-only tasks are parked last
`parked` is true exactly when RESEARCH is the only artifact, frontmatter `created` is more than 7 days old and no commit exists beyond the base; parked tasks sort after all others; absent `created` is not parked.

### AC-013: Memory retrieval is bounded and lexical-first
`hm memory_retrieve` output is ≤ 8,192 bytes, its first min(k, eligible) entries are the independently computed lexical hits, floor entries fill only the remainder, dated entries show their max-date bullet, and undated entries are kept.

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S10 | unit (render) + manual | AC-014; manual: mid-`/hm:spec`, say "the goal changed" without Maker; confirm the intent procedure is read |
| S11 | unit (property) + unit (render) + manual | AC-015, AC-016; manual: stop after spec, change scope in chat, resume in a new session |
| S12 | unit (render) + manual | AC-017; manual: during `/hm:execute`, ask Maker for status and a new task; confirm aside, queue entry and resume line |
| S1 | unit (render) + manual | AC-001/002/003/004; manual: say "change the goal" without Maker in a fresh session, confirm no skill loads |
| S2 | unit (render) + manual | AC-005; manual: `/maker` goal edit reads intent-layer SKILL.md before `hm intent` |
| S3 | unit (property, differential) | AC-006 |
| S4 | unit (golden table) + unit (CLI property) + manual | AC-007, AC-008; manual: `maker야 X 리서치해줘` with autopilot armed |
| S5 | unit (CLI) | AC-009 |
| S6 | integration (subprocess) | AC-010 |
| S7 | unit | AC-011 |
| S8 | unit (property) | AC-012 |
| S9 | unit (property) | AC-013 |

### AC-014: Always-loaded pointer routes unnamed requests to Maker
Every pointer variant routes goal, metric, project-fact and status requests — named or not, mid-stage included — to Maker's procedure, excludes ordinary build/fix asks, and stays ≤ 400 chars at NAME_MAX/HANDLE_MAX.

### AC-015: Digest reports each task's latest artifact
Each listed task carries `latest_artifact` = the newest of its RESEARCH/SPEC/PLAN/REVIEW files by modification time, with that time, within the 1,500-byte cap.

### AC-016: Decision capture is instructed on every entrance
The pointer and the rendered Maker instruct writing an in-flight task's changed decision to its most downstream artifact before replying, and Maker's Resume states the latest artifact before entering a stage.

### AC-017: Mid-stage aside protocol is instructed
The pointer and the rendered Maker instruct, for a request arriving while a stage runs: an aside of at most 6 lines opening with the Maker name, decisions recorded per AC-016, new work appended under `## Queued asks` and never started mid-stage, and a closing resume line naming stage and step.

## ❓ Open Questions

None. Execute Step 0 records as ADRs: the observability file name for `maker_load`, the restore-field name, and how `narrow` restores (on the boundary stop vs. on the next stage entry) within S4/AC-008.

## 🔎 Spec Validation

spec-validator pass 1 (2026-10-03): `MAJOR_REVISION` — 4 critical (AC-007 circular oracle, autonomy semantics, AC-006 vacuous cap, AC-011 lexical-count oracle), 9 warnings, scope-boundary clean. Codex second opinion: invoked, 11 findings, 10 accepted, 1 partially refuted (stage-universe circularity). All accepted findings folded into this revision: AC-007 split into mapping (AC-007), stop+restore (AC-008) and no-widening (AC-009); AC-006/013 oracles made independent; AC-010 success/partial cases; usage measured at digest (AC-011); parked age source fixed; Codex key pinned from the Codex docs.

## 🔍 Refinement Decisions

- Round 0 (RESEARCH validation): narrow autopilot in Maker; no SessionStart briefing; keep worktree + `parked`; include memory_retrieve.
- Round 0b: Maker is the only entrance unless the operator types a skill name; Maker owns intents and knowledge with on-demand procedure loading.
- Round 1: intent = WORLD-INTENT-CLOSED-LOOP; stages description-gated; Codex parity via `agents/openai.yaml`; memory_retrieve = byte cap + floor fills empty slots + newest bullet.
- Round 2: new verb `hm autopilot narrow --until` that only shrinks and restores the pre-narrow pipeline; usage measured by a `maker_load` row from the digest; DRI approved.
- Round 3 (during execute Step 0, 2026-10-03): resume/front-door gaps — unnamed mid-stage requests route via the pointer to Maker's procedure (S1 amended, S10); conversation decisions are written to the task artifact and the digest shows `latest_artifact` (S11); pointer cap raised to 400; narrow always recomputes from the saved original pipeline. Mid-stage aside protocol added (S12): answer as an aside, queue new work in the task artifact, resume the stage at the same step. DRI re-approved.

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| RESEARCH §Recommended Direction 3; commit 7aeb2f47 "unknown: whether operators adopt /maker" (2026-10-03) | intent_world_closed_loop_cycles | declined | Maker use is unmeasurable today; AC-011 makes it countable | agent | pending decision | wrapup Step 5.7 |
| interview 2026-10-03: operator states intent management is the core of the world model | WORLD-INTENT-CLOSED-LOOP | recorded + readback | Maker briefing previously hid active intents; AC-005/006 move ownership to Maker | agent | pending decision | wrapup Step 5.7 |
