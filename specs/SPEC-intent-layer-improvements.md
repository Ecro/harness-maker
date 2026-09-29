---
type: spec
task_slug: intent-layer-improvements
status: approved
created: 2026-09-29
tier: 2
tags: [harness-maker, spec, python, jinja2, intent-layer, workflow-feedback, trial]
test_framework: pytest
interview_rounds: 4
intent: WORLD-INTENT-CLOSED-LOOP
research_doc: "[[RESEARCH-intent-layer-improvements]]"
summary: "Rewire wrapup 5.7, batch intent consent at wrapup, freeze the trial, cheaper writes, fix resolve"
---

# SPEC — intent layer: rewire, batch consent, freeze trial

## 🎯 Intent

Intent feedback currently needs the user to re-instruct it: the delegated wrapup path — taken by
every wrapup since 2026-09-16 — jumps from Step 0.5 straight to Step 6 and skips Step 5.7, the only
place intent state is updated (RESEARCH F1). Every stage also pays for an always-on feedback
directive that asks the model to read the skill, `intent status` and `trial status` (~10–12k tokens
per stage entry, F3); the real-task trial is deadlocked on a hash-pinned PLAN (F2); each write costs
6–7 tool calls plus a consent question (F5); and `question resolve` has no lifecycle — the inline
rewrite allows any transition while the engine's `observe --relation confirms` never changes status,
so an `open` question with confirming evidence has no defined way to settle (F7, `q_825d374c`).
This SPEC serves `WORLD-INTENT-CLOSED-LOOP`.

## 🌅 Outcomes

- Every wrapup — delegated or inline — reaches Step 5.7.
- Stages only *collect* intent-relevant observations as `pending` Feedback rows; reading intent state
  and asking for consent happen at wrapup: one batched record question, then (only when the PLAN is
  linked to an intent) one close question after readback.
- The deadlocked trial is frozen by a recorded user decision: it stops being "active", stops shaping
  the land path and stops appearing in stage prose; its data stays.
- `WORLD-INTENT-CLOSED-LOOP` is judged by a one-line user verdict item inside the record batch.
- A free-text value can be passed through stdin (quoted heredoc); `--observed-at` defaults to now.
- `question resolve` settles `open` questions and is the exit from `wrong`; `confirmed` is changed
  only through an observation first.

## 📋 In-Scope Scenarios

### S1: Delegated wrapup reaches 5.7
**Given** a rendered harness (Production/Side × claude-code/codex) whose wrapup renders Step 5.7
**When** `stage-delegate` returns a reconciled receipt for Steps 1–5.6, or the degraded inline path runs
**Then** the rendered wrapup names Step 5.7 as the next step on both paths
**And** no directive in the Step 0.5 region or the inline preamble sends the main loop to Step 6 past 5.7

### S2: Stages collect, wrapup decides
**Given** `.claude/intent.yaml` exists and a non-wrapup stage makes an observation bearing on an intent question or metric
**When** the stage reaches its feedback entry or close block
**Then** the block instructs appending a `pending` row to the `## Feedback` table of the task's most downstream existing artifact (PLAN, else SPEC, else RESEARCH), and never instructs reading `hm intent status`, the skill file, or any trial status
**And** when `.claude/intent.yaml` is absent the block is a no-op, and wrapup's own close block collects nothing (5.7 is the cutoff; later observations go to the final summary only)

### S3: One batched record question at wrapup
**Given** pending Feedback rows in the task's PLAN, SPEC or RESEARCH, and/or measurable metrics
**When** wrapup reaches Step 5.7
**Then** it reads `hm intent status --json` once and presents every proposed record write in one question — Claude Code: one multi-select; Codex: a numbered list answered by one reply (`numbers` or `none`)
**And** it runs only the selected writes, reads status back, marks unselected rows `declined`, marks a selected write that fails `failed` with its error and does not retry it; an empty batch asks nothing

### S4: Judgment metric verdict
**Given** the PLAN's intent is bound to a metric with `measure: false` (e.g. `intent_world_closed_loop_cycles`) and no verdict row for this task is already `recorded`
**When** Step 5.7 builds the record batch
**Then** the batch includes one item proposing a value derived from the metric's `how_measured` and `last`, phrased as a one-line verdict question; Other edits the value
**And** the value is recorded with `hm intent metric record` only if selected, and a resumed wrapup does not propose it again

### S5: Close after readback
**Given** the PLAN frontmatter links an intent
**When** the record batch has been applied and status read back
**Then** Step 5.7 asks one separate single-choice question: met / missed / no_data / keep open
**And** it never asks the close question before the record batch's readback

### S6: Frozen trial is inert
**Given** a trial PLAN whose latest `policy` decision is a user decision (`actor: user`, `authority: explicit_user_decision`) with `enabled: false`, present in both the working copy and `HEAD`
**When** `active_trials`, `protected_trial_paths` and the land fence run
**Then** the trial is not listed, its path is not protected, and the fence uses the normal timeout
**And** every other case stays active: `enabled: true`; a hand-edited `enabled: false` with no such decision; the decision only in the working copy; legacy body-only trials; unparseable frontmatter; unreadable or symlinked PLANs; deleted tracked PLANs; a marker-free working copy whose `HEAD` is a trial; git uncertainty

### S7: This repo's trial is frozen by the DRI's decision
**Given** `world-intent-closed-loop-trial` is active and the DRI decided "freeze" in this interview (2026-09-29)
**When** execute records that policy decision through `hm intent trial record-decision` and wrapup commits it
**Then** the trial is absent from `active_trials`
**And** no member, event or earlier decision is removed; if `record-decision` refuses (e.g. `source_conflict`), execute stops and reports rather than changing status precedence

### S8: stdin free text and default timestamp
**Given** a write verb taking `--<name>-file`
**When** the value is `-` and the text arrives on stdin
**Then** a scalar field stores the text with trailing newlines removed, and a list field stores its non-empty stripped lines — the same as a file with those bytes
**And** two `-` values in one invocation are refused with nothing written; omitting `--observed-at` on a call that writes an observation stamps an aware UTC time taken during the call

### S9: resolve lifecycle
**Given** a question with status `open`, `confirmed` or `wrong`
**When** `hm intent question resolve <id> --status <open|confirmed|wrong>` runs
**Then** it succeeds for open→confirmed, open→wrong, wrong→confirmed and wrong→open
**And** every other pair exits non-zero naming `observe --relation` and leaves `intent.yaml` byte-identical

### S10: Intent id derivation
**Given** spec Step 4.9 drafts an intent for slug `foo-bar`
**When** the rendered instruction is followed
**Then** the id is `FOO-BAR` (upper-cased slug, no `OBJ-` prefix), matching existing records

## 🚫 Non-Goals

- Merging `hm world` into `hm intent` or deleting the `hm world` CLI (F4).
- Deleting `intent_trial.py` or its tests; re-enabling or resetting the trial; reordering trial status reason precedence.
- Metric/question hygiene: retiring `change_failure_rate`, expiring dormant questions, assigning `unsourced_step_share` (F6).
- Review Step 3.3 changes; the open P1 `3e276d78` (trial `status()` outside the fence).
- Editing any intent record (`intent/*.md`) or `intent.yaml` metric definitions.
- The operator-initiated write path in the skill ("record X" asked directly) keeps its per-write consent.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` (+ `ruff check`, `ruff format`, `mypy --strict`) | repo standard (CLAUDE.md) |
| Language | Python only | CLAUDE.md technical decisions |
| Target parity | Claude Code and Codex renders, including `.agents/skills/hm-*/SKILL.md`, satisfy S1–S5, S10 in their own form | both render the shared partials |
| Absent case | no `.claude/intent.yaml` → feedback blocks no-op, 5.7 prints `[intent] not in use` | absent-case black hole rule |
| Snapshots | regenerate in the task worktree | `project_snapshot_regen_in_worktree_is_correct` |
| Pinned evidence | `tests/fixtures/workflow-feedback-legacy.md.txt` untouched | hash-pinned protocol capture |
| Test quality | render/prose assertions are scoped to their owning block and each has a deletion control that fails when the owning line is removed | `[fail:test] assertion-invariant-over-named-dimension` (count 22) |
| Shell safety | stdin input documented only with a quoted heredoc delimiter | shell-quote breakout risk (REVIEW-intent-file-inputs) |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | `hm intent question resolve` accepts only open→confirmed/wrong and wrong→confirmed/open; all other pairs (including any target `open` from `open` and any source `confirmed`) are refused | public API/CLI contract | invocations that succeed today (e.g. confirmed→wrong) start failing |
| IRR-002 | a trial is inactive only when its latest user `policy` decision has `enabled: false` in both working copy and `HEAD`; every other case stays active and protected | schema/file format/storage layout | changes the meaning of a stored field that the land path reads |
| IRR-003 | workflow-feedback consent moves from per-write at any stage to one batched record question plus one close question at wrapup 5.7 | security/permission boundary | the unit of human approval for intent writes changes in every rendered harness |
| IRR-004 | `-` on any `--*-file` flag reads stdin; `--observed-at` becomes optional (default now) | public API/CLI contract | once consumers rely on the additive inputs, removing them breaks callers |

## ✅ Verification Criteria

| Scenario | AC | Verification mode | Test name / manual step |
|---|---|---|---|
| S1 | AC-001 | unit (render) | `test_wrapup_delegated_path_resumes_at_5_7` |
| S2 | AC-002 | unit (render) | `test_feedback_blocks_collect_only` |
| S3 | AC-003 | unit (render) + manual | `test_wrapup_5_7_record_batch`; manual: one wrapup on this repo shows one record question |
| S4 | AC-004 | unit (render) | `test_wrapup_5_7_judgment_verdict_item` |
| S5 | AC-012 | unit (render) | `test_wrapup_5_7_close_after_readback` |
| S6 | AC-005 | unit | `test_frozen_trial_is_inactive` |
| S7 | AC-006 | integration (live repo) | `hm intent --root . trial status world-intent-closed-loop-trial --json` + `active_trials` check |
| S2 | AC-007 | unit (render) | `test_no_trial_duty_in_rendered_prose` |
| S8 | AC-008 | unit | `test_stdin_matches_file_semantics` |
| S8 | AC-009 | unit | `test_observed_at_defaults_to_now` |
| S9 | AC-010 | unit | `test_resolve_lifecycle` |
| S10 | AC-011 | unit (render) | `test_spec_intent_id_derivation` |

### AC-001: Delegated and inline wrapup paths resume at Step 5.7
Every rendered wrapup (Production/Side × claude-code/codex) that renders Step 5.7 names 5.7 as the
next step on both the delegated-success and the degraded inline path; no directive in those regions
sends the main loop to Step 6 past 5.7.

### AC-002: Stage feedback blocks only collect pending rows
In every rendered stage command and Codex stage skill, the feedback-entry and feedback-close blocks
are conditional on `.claude/intent.yaml`, instruct appending `pending` Feedback rows to the most
downstream existing task artifact, and contain none of `intent status`, `SKILL.md`, `trial`; wrapup's
close block states that 5.7 is the collection cutoff.

### AC-003: Step 5.7 asks one batched record question
Rendered Step 5.7 contains exactly one record answer-gated block that reads Feedback rows from the
task's PLAN, SPEC and RESEARCH, reads status once, asks one question in the target's form
(multi-select / numbered list with one reply), runs only selected writes, marks unselected
`declined` and failed `failed`, and asks nothing for an empty batch.

### AC-004: Judgment metric verdict item in the batch
Inside the record block, rendered Step 5.7 adds one verdict item for a linked intent's
`measure: false` metric, recorded via `hm intent metric record` only when selected, and not proposed
when a verdict row for the task is already `recorded`.

### AC-005: Trial inactive only on a recorded user disable
`active_trials` omits a trial exactly when its latest user `policy` decision has `enabled: false` in
both working copy and `HEAD`; every enumerated fail-closed case stays active.

### AC-006: Repository trial frozen by recorded decision
`world-intent-closed-loop-trial` carries the DRI's `policy` decision with `enabled: false`, is absent
from `active_trials`, and keeps all prior members, events and decisions.

### AC-007: No trial duty in rendered prose
No rendered stage command, Codex stage skill or rendered intent-layer reference instructs a
Real-task trial duty.

### AC-008: Stdin value matches file semantics
For every `--*-file` flag, `-` with stdin stores `x.rstrip('\n')` for scalars and the non-empty
stripped lines of `x` for lists; two `-` values in one call are refused with nothing written.

### AC-009: Omitted observed-at defaults to now
On a call that writes an observation, omitting `--observed-at` stores a timezone-aware UTC instant
between the call's start and end.

### AC-010: Resolve lifecycle open and wrong exits
`question resolve` succeeds exactly for open→confirmed, open→wrong, wrong→confirmed, wrong→open;
every other pair exits non-zero and leaves `intent.yaml` byte-identical.

### AC-011: Spec draft intent id is the upper-cased slug
Rendered spec Step 4.9 derives the id as the upper-cased slug, shows `foo-bar` → `FOO-BAR`, and has
no `OBJ-` prefix.

### AC-012: Close question follows the record readback
When the PLAN links an intent, rendered Step 5.7 asks one single-choice close question
(met / missed / no_data / keep open) placed after the record block's status readback.

## ❓ Open Questions

(none — all resolved in interview; implementation choices go to `/hm:execute` Step 0 ADRs)

## 🔎 Spec Validation

Step 4.6 ran (irreversible decisions non-empty). Codex (`invoked`, 4 P1 + 4 P2) and
`spec-validator` (`MAJOR_REVISION`, 3 critical, 5 warning, 3 suggestion) were reconciled into this
revision: resolve lifecycle corrected (validator critical 1 — the earlier "open only" rule would have
made `wrong` terminal), freeze bound to a recorded user decision with every fail-closed case
enumerated (critical 2–3, codex P1 ×2), AC-006 no longer expects `authority_required` because
`source_incomplete` precedes it, stdin expected values stated per kind (codex P1), Codex batch form
defined (codex P1), close split out after readback, empty/failed/resumed batch semantics, 5.7
collection cutoff and sources, positive AC-011, Codex skills in AC-002/007, AC-009 scoped to
observation writes.

## 🔍 Refinement Decisions

- Round 1: intent = WORLD-INTENT-CLOSED-LOOP; scope = F1+F3+F5+F7; trial = freeze; consent = batched at wrapup.
- Round 2 (design): batching makes stages collect-only; freeze needs code because `active_trials` ignores `policy.enabled` (`intent_trial.py:966`).
- Round 3: trial replaced by a one-line verdict item; collect-only stage prose confirmed; resolve "open only" (superseded in Round 4).
- Round 4: resolve from open or wrong (corrected premise: `observe --relation confirms` never changes status, `world.resolve` is the only exit from `wrong`); record batch + separate close question; Codex numbered list with one reply; DRI approved the revised SPEC.
