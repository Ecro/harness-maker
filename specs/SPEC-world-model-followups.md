---
type: spec
task_slug: world-model-followups
status: approved
created: 2026-10-02
tier: 2
tags: [harness-maker, spec, python, jinja2, world-model, cli, tokens, hardening]
test_framework: pytest
interview_rounds: 4
intent: WORLD-INTENT-CLOSED-LOOP
research_doc: "[[RESEARCH-world-model-name]]"
summary: "Deterministic artifact-based `hm world_model digest` for the Maker briefing, review leftovers, help listing"
---

# SPEC — Maker follow-ups: deterministic digest, review leftovers, help listing

## 🎯 Intent

SPEC-world-model-name shipped the `/<handle>` router with a prose briefing that composes four
shell commands and infers a task's next stage from the newest span row. That inference is
wrong: a span `end` row is written by the Claude Code **Stop hook at the end of every turn**
(`templates/settings/*.json.j2`; `worktree.py` "Claude-Code-only by construction"), never by
Codex or Cursor, so "ended" means "a turn ended", not "the stage finished". This task replaces
the prose with one deterministic, capped digest whose next stage comes from the task's
**artifacts**, fixes the review findings SPEC-world-model-name carried, and lists the router in
`/hm:help`.

## 🌅 Outcomes

- `hm world_model digest` prints one compact JSON object (≤ 1500 bytes) — active tasks with
  their next stage (artifact-derived), last-touched stage and session, autopilot state, intent
  items needing a decision, recent commits — and never fails the caller.
- The router briefs from that one command. Claude Code injects it with `!` (no tool round-trip);
  the same copy carries a one-line fallback to run it when nothing was injected — Cursor reads
  this copy natively and its `!` preprocessing is unverified. Codex runs it as one Bash line.
- "Continue" resumes the stage the artifacts say is next, on every runtime, and asks once before
  entering a task another session touched last.
- The review findings carried by SPEC-world-model-name are fixed or pinned by tests.
- `/hm:help` lists the router under the user's handle.

## 📋 In-Scope Scenarios

### S1: Digest is bounded and always succeeds
**Given** any project state — no git, no span ledger, a ledger with garbage, a torn last line or unrecognised/empty stage values, 0..N task worktrees with long slugs, long or non-ASCII commit subjects and intent ids
**When** `hm world_model digest [--root <dir>] [--session-id <id>]` runs
**Then** it exits 0 and prints exactly one JSON object of at most 1500 bytes
**And** a source that cannot be read is reported as `{"unavailable": "<reason>"}` for that part (or for the whole digest) instead of failing

### S2: Next stage comes from artifacts, not spans
**Given** a task worktree `hm/<slug>`
**When** the digest computes `next_stage`
**Then** it is the first stage whose completion signal is absent, in this order: spec (SPEC approval `approved` or `exempt`), execute (a `REVIEW-<slug>-*.md` exists), review (newest REVIEW `status: APPROVED`), verify (the verification marker matches the current tree), then `wrapup`
**And** research is optional: `research` is next only when the task has none of RESEARCH, SPEC, PLAN or REVIEW; with a RESEARCH doc and no approved SPEC, `spec` is next
**And** span rows never advance `next_stage` (a Claude Code turn-end `end` row and a Codex/Cursor task with no `end` rows give the same answer)

### S3: Last-touched stage and session
**Given** the base-root span ledger
**When** the digest reports a task
**Then** `last_stage` is the stage of the task's newest well-formed row (`null` when none or when the stage is empty/unrecognised) and `last_seen` its timestamp
**And** `other_session` is `true` when both `--session-id` and the row's session are present and differ, `false` when they are equal, and `null` when either is absent

### S4: Tasks are ordered and capped
**Given** seven active task worktrees
**When** the digest runs
**Then** `tasks` holds the five with the newest `last_seen` (tasks with no span last), and `more` is 2

### S5: Root resolves to the base
**Given** a project with a task worktree
**When** the digest runs with `--root` (or cwd) set to the base, a base subdirectory, or the task worktree
**Then** the output is identical — the ledger and artifacts are read from the git base root and each task's worktree

### S6: Router briefs from the digest and acts on it
**Given** a rendered harness
**When** the router skill is read
**Then** the Claude Code copy carries exactly one `!` digest injection plus a one-line fallback ("no digest output above → run it"), the Codex copy runs the digest as one Bash line, and neither contains any other briefing command
**And** Resume enters `next_stage`, asks once when `other_session` is `true`, reports a task whose `next_stage` is `wrapup` as ready to land, and keeps the 8-line reply cap, the Never-Read rule and the "what next → start no stage" / "record first" rows

### S7: Intent items match the intent layer
**Given** a project with `.claude/intent.yaml`
**When** the digest runs
**Then** its intent section carries the conflicts / fired revisits / needs-revalidation / stale-evidence items `hm intent status --json` reports, capped at 3 items plus counts

### S8: Interactive messages follow locale
**Given** the onboarding interview in locale `ko`
**When** the operator types an invalid name, or a reserved handle
**Then** each re-prompt is the `ko` catalog text naming the rule, and that text differs from the `en` text

### S9: Modular add cannot create a second router
**Given** a rendered harness
**When** `harness-maker make --add skill:world-model` runs
**Then** it exits non-zero with a message naming `/hm:configure`, and no `skills/world-model/` exists afterwards

### S10: Names round-trip and stay within budget
**Given** any name accepted by `name_error` (including emoji/astral characters) and any valid handle up to 64 characters
**When** the harness renders
**Then** harness.yaml and the router frontmatter parse back to the same name, U+FFFE/U+FFFF are rejected, and every always-loaded pointer section is ≤ 200 characters at name 40 / handle 64 while still containing the full name and the full `/<handle>` (or `$<handle>`) token

### S11: Router body and help reflect the chosen name
**Given** name `Atlas`, handle `atlas`
**When** the harness renders (with codex)
**Then** the router body opens with `# Atlas` and the `Atlas —` voice rule, the Codex copy uses `$atlas`, and `/hm:help` lists `/atlas` (Claude) / `$atlas` (Codex)

## Acceptance Criteria

### AC-001: digest output never exceeds 1500 bytes
### AC-002: digest always exits 0 with one valid JSON object
### AC-003: next stage is derived from artifacts
### AC-004: last stage and other-session flag
### AC-005: tasks are newest-first and capped at five
### AC-006: digest reads the base ledger from any root
### AC-007: router briefs from a single digest with a fallback
### AC-008: router resume acts on the digest fields
### AC-009: digest intent items match hm intent status
### AC-010: interactive name and handle errors follow locale
### AC-011: modular add of the world-model skill is refused
### AC-012: accepted names round-trip and noncharacters are rejected
### AC-013: pointer stays within 200 characters with full tokens
### AC-014: router body carries the display name and the Codex token
### AC-015: help lists the router under its handle

## 🚫 Non-Goals

- v1.1: "why did we decide X" query route, failures-since-last-session, stage STOP-text hints (next task).
- Persona, a persisted digest/state file, SessionStart injection (rejected in RESEARCH).
- Changing the `world_model` schema, `/<handle>` invocation or `--world-model-*` flags (SPEC-world-model-name IRR-001/002).
- Changing any stage template to emit a completion signal; liveness detection beyond the span session id.
- Verifying Cursor's `!` preprocessing (the fallback line covers it).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` (+ Hypothesis for property ACs) | Repo standard |
| Digest size | ≤ 1500 bytes, compact JSON (`ensure_ascii=False`), per-field truncation | RESEARCH addendum tier (b) budget; survives skill compaction re-attach |
| Digest failure | exit 0 always; `unavailable` on unreadable sources | The router must never stall on its own briefing |
| Digest cost | No full read of `wiki.md` / `failures.md`; span ledger streamed once; read-only (no writes, no markers) | Measured sizes 456 KB / 377 KB / 193 KB |
| Verify signal | read-only verification-marker check for the task worktree's current tree | Never re-runs gates |
| Session id | optional; absent → `other_session: null` | `HM_SESSION_ID` is a shell var and may be absent in `!` subshells |
| Language | Python only; mypy --strict | CLAUDE.md |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | `hm world_model digest` with flags `--root`, `--session-id`, the exit-0 contract, and JSON keys `tasks[].{slug,next_stage,last_stage,last_seen,other_session}`, `more`, `autopilot`, `intents`, `recent`, `unavailable`; `next_stage` values = the six pipeline stages. Lives under `world_model` (the router's input) rather than `hm world` (the intent layer's read path) | public API/CLI contract | Rendered router skills and user scripts depend on the command, flags and keys |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (property) | `test_ac001_digest_size_bound`, `test_ac002_digest_never_fails` |
| S2 | unit (parametric) | `test_ac003_next_stage_from_artifacts` |
| S3 | unit (parametric) | `test_ac004_last_stage_and_session` |
| S4 | unit | `test_ac005_newest_first_capped` |
| S5 | integration (git worktree) | `test_ac006_root_resolves_to_base` |
| S6 | unit (render) | `test_ac007_router_single_digest`, `test_ac008_router_resume_fields` |
| S7 | unit (differential) | `test_ac009_intents_match_status` |
| S8 | unit | `test_ac010_interactive_messages_follow_locale` |
| S9 | integration (CLI) | `test_ac011_modular_add_refused` |
| S10 | unit (property) + render | `test_ac012_names_round_trip`, `test_ac013_pointer_cap_full_tokens` |
| S11 | render | `test_ac014_router_body_name`, `test_ac015_help_lists_router` |

Test modules: `tests/unit/test_world_model_digest.py`, `tests/render/test_render_world_model_followups.py`.

## ❓ Open Questions

None blocking. Execute decides as ADRs: module placement of the digest (keep `paths_to_mutate`
in step with it); in-process vs subprocess reads of autopilot / intent / approval / marker state;
the P3 cleanups without ACs (dispatch selector in the make.md test, sweep docstring scope,
flag-OFF note in the router) as regression tests.

## 🔍 Refinement Decisions

- Round 1: intent `WORLD-INTENT-CLOSED-LOOP`; scope A (review leftovers) + B (digest CLI) + D (help); C (v1.1) deferred; command `hm world_model digest`.
- Round 2: other-session open spans flagged, router asks before them; Claude Code briefs via `!` injection; IRR-001 recorded.
- Round 3: DRI approved AC-001..012 (first draft).
- Round 4 (after spec-validator MAJOR_REVISION): span `end` is a turn end, so the next stage is artifact-derived (DRI: artifacts); all warnings/suggestions folded in (mixed session cases, non-ASCII size domain, Cursor fallback, resume-field AC, stronger AC-010/011/013, base-root AC, carried 0248ff45 remainder + a62626dd, IRR flags + `hm world` naming note, ordering, unrecognised stages); re-approval requested.

## 🔎 Spec Validation

`spec-validator` single pass on the first draft: MAJOR_REVISION (1 critical, 9 warnings, 4
suggestions; codex skipped — usage limit). Every item was folded into this revision (Round 4);
none remains open.

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| SPEC S2/S6: artifact-derived resume removes a re-instruction point ("which stage was I in?") on every runtime | WORLD-INTENT-CLOSED-LOOP / intent_world_closed_loop_cycles | pending | — | — | — | wrapup Step 5.7 decides |
