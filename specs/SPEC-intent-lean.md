---
type: spec
task_slug: intent-lean
status: approved
created: 2026-11-28
tags: [harness-maker, spec, intent, cli, templates, simplification]
test_framework: pytest
interview_rounds: 1
summary: "Cut the intent layer to what changes outcomes: goals + metrics + measurement history across sessions. Ask the DRI only to create a goal, change a target, or close a goal; drop the approval/activation state machine, the never-fired revisit/revalidation/withdrawal/locator engine, the legacy `hm world` CLI, the proposal path and spec Step 0.5."
---

# SPEC — intent-lean

## Intent

The DRI finds the intent layer cumbersome, asking often, with no clear effect (2026-11-28), and
added the rule "hm keeps only what the model does not and will not do" (SPEC-intent-model-progress-rule).
The analysis (`/mnt/project-files/hm-intent-review/REPORT-intent-layer-2026-11-28.md`, main 593a6ac5)
found that only one part changes outcomes: **goals, metrics and their measurement history kept
across sessions** (the 8x cost bar, the UNDERSTANDING-HANDOFF verdict). The rest is unread
(`IntentFile.rules` has no caller; the SPEC `intent:` tag is read only by the retired autopilot's
objective gate), never fired (`q_intent_layer_unfired_paths`: revisit, revalidation, conflict,
objective halt), or dead (a skill pointer to a wrapup Step 5.7 that no longer exists). The
questions come from the skill's own rules: a 12-topic multi-round creation interview, a consent
ask for 10 verbs, and an approval hash over the target that forces a re-approval on every target
change. The DRI chose "cut the structure too" on 2026-11-28.

Token cost is about 1% per task (FEATURE-COST-2026-11-28); the gain is DRI attention and code
maintenance, not tokens.

## Outcomes

- O1. The DRI is asked about intent only to **create a goal** (one round: a drafted goal, metric and
  target to confirm, at most 3 questions), to **change a metric target**, or to **close a goal**
  (met / missed / no_data). Every other intent write runs without asking and prints one line.
- O2. A goal record has two states, `open` and `closed`. No approval stamp, no activation.
- O3. Gone: the never-fired engine (revisit, revalidation, withdrawal, conflicts, evidence-locator
  staleness), the legacy `hm world` CLI, the vocabulary translation layer outside `migrate`, the
  autopilot objective gate, the skill's proposal path, spec Step 0.5 and the SPEC `intent:` field,
  the wrapup consent ask for records, and the workflow-feedback reference.
- O4. `hm intent status --json`, `hm intent show` and the Maker digest report goals, metrics,
  measurement gaps and open questions only, with one state mapping.
- O5. Stale project data fixed: the Cursor rule, and HM-LIGHT-LANE closed as met (6.984 ≤ 8).
  **The DRI's approval of this SPEC is the close confirmation for HM-LIGHT-LANE.**

## In-Scope Scenarios

- **S1 (normal, create).** Given the DRI says "record a goal: keep the tier-1 cost ratio at or under
  8x", When Maker routes to the intent skill, Then it drafts id, title, statement, metric and target
  from the conversation, asks once (one round, ≤ 3 questions, only for what the conversation did not
  state, plus the confirmation), shows the rest under "decided for you", adds the metric to
  `.claude/intent.yaml` `metrics` first if none fits (validated by `hm intent status`), and runs
  `hm intent new`, which writes `intent/<ID>.md` with `state: open`.
- **S2 (normal, record).** Given an open goal and a task whose wrapup measured its metric, When wrapup
  Step 5 runs, Then it runs `hm intent metric measure` / `metric record` and `question add|observe`
  without asking and prints `intent: <verb> <id> — <what>` once per write.
- **S3 (normal, close).** Given an open goal whose metric gap turns `at_or_better` in this wrapup,
  or a task the SPEC says finishes the goal, When wrapup Step 5 runs, Then it asks once whether to
  close it (met / missed / no_data / keep open) and runs `hm intent close` only on a close answer.
- **S4 (normal, target change).** Given the DRI asks to change a target, When the skill runs, Then
  it confirms the new value once, edits `metrics[].target`, runs `hm intent status` to validate,
  and runs `metric measure <id>` when the metric has `measure`; otherwise it says the gap is
  unevaluable until the next record (rows carry a definition hash that includes the target;
  unchanged).
- **S5 (edge, legacy data).** Given records in state `proposed`, `active`, `closed` or `dropped`
  carrying `approval`, `revisit_when`, `depends_on` or `rejected`, and questions carrying `locator`,
  When `hm intent status --json` runs, Then `state` is `ok`, proposed/active are `open`,
  closed/dropped are `closed` (dropped reports `observed: no_data` when it has none), closed and
  dropped record files stay byte-identical, and a later question write keeps every other entry's
  keys, locators included.
- **S6 (edge, legacy layout).** Given an unmigrated project (`.claude/world/` files or
  `work-docs/INTENT-*.md`), When `hm intent status --json` runs, Then it returns `state: invalid`
  with an error naming `hm intent migrate`; `migrate` behaves as on main 593a6ac5 and accepts an
  existing `state: open` record.
- **S7 (failure, removed verb).** Given `hm intent approve|activate|drop|reopen X`, When it runs,
  Then it exits 2 with a message naming the replacement, never redirects to `spec_machine`, and
  writes nothing.

## Non-Goals

- No change to metric measurement semantics: `measure.cmd`, `select`, `cwd`, the gap rule, the
  `definition_hash` formula and the `metrics.yaml` row format stay.
- No removal or rewording of existing metrics, purpose, vision or open questions beyond O5.
- No autopilot removal beyond its objective gate (the residue is another thread's cleanup).
- No deletion of the `world_intent_*`, `intent_feedback_continuity` and `objective_scope_drift`
  rubric templates: 11 ACs of 4 historical SPECs resolve `rubric_id` against them. They are not
  rendered, so they cost no tokens.
- No change to project-knowledge, memory or the SPEC interview.

## Constraints

| Constraint | Value | Source |
|---|---|---|
| Test framework | pytest (mandatory) | CLAUDE.md |
| Maker | only entrance; intent-layer typed-only; digest ≤ 1,500 bytes, exit 0, `other_session` never dropped; Maker SKILL.md ≤ 4,689 chars | CLAUDE.md World model |
| User state | entries the user wrote are never dropped or rewritten unasked; closed/dropped records never change | pre-change checklist (1) |
| Python only, render deterministic | — | intent.yaml rules |
| Step sensitivity | removing spec Step 0.5 removes its REGISTRY entry | test_step_sensitivity_registry |

## Irreversible Decisions

| ID | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | `hm intent` keeps `status`, `show`, `new` (`--title-file --statement-file --metric`, optional `--scope-file --out-of-scope-file`), `close` (`--observed --note-file`), `metric measure` / `metric record`, `question add|observe|resolve` (without `--locator`), `migrate`. Removed: verbs `approve`, `activate`, `drop`, `reopen`; flags `--from-proposal`, `--candidates`, `--declined-file`, `--locator`; the `hm world` module. `status --json` top-level keys become `state, purpose, metrics, intents, open_questions, open`; status on an unmigrated layout returns `invalid` naming `migrate` | public API/CLI contract | Rendered skills, wrapup and user scripts call these; the removed parts only fed the approval state machine, the proposal path or the never-fired staleness check |
| IRR-002 | Goal record `state` written as `open` or `closed`; read: proposed/active → open, closed/dropped → closed; `approval`, `revisit_when`, `depends_on`, `rejected` are not written on new records; existing entries and records keep every key they have | schema/file format/storage layout | Removes the approval hash that forced re-approval; old data stays readable and intact |
| IRR-003 | `hm world_model digest` `intents` becomes `{"open": [{id, metric_id, last, target, gap}]}`; `open` takes the old `intents` slot in the trim order | public API/CLI contract | The rendered Maker skill briefs from it |

## Acceptance Criteria

### AC-001: the intent skill asks only at the three moments
The rendered intent-layer SKILL.md (Claude and Codex) names the ask tool exactly once, in a rule
that lists exactly creating a goal, changing a target and closing a goal; states "one round" and
"at most 3 questions" for creation; mentions none of `approve`, `activate`, `drop`, `reopen`,
`revisit`, `--from-proposal`, `workflow-feedback`; and is at most 4,000 characters.

### AC-002: removed verbs exit 2 with a replacement and write nothing
`hm intent approve|activate|drop|reopen X` each exit 2; output names the replacement (`close` for
drop, "no step needed" for the others), never contains `spec_machine`; the project tree is unchanged.

### AC-003: one state mapping on every read surface; nothing the user wrote is lost
proposed → open, active → open, closed → closed, dropped → closed (`observed: no_data` when
absent), in both `status --json` and `show`. After `new`, `metric record` and `question observe` on
one project, closed and dropped record bytes are unchanged and every other `open_questions` entry
parses equal to before (locators included).

### AC-004: status JSON shape
Top-level keys exactly `{state, purpose, metrics, intents, open_questions, open}`; each `intents`
value has keys `{state, title, metric_id, observed}`; each `metrics` value has keys `{last, target,
gap, observed_at, reason, how_measured, higher_is_better, measure}`; `open` is the list of open ids.

### AC-005: new then close round-trip
`hm intent new` writes `state: open` with no `approval` key; `close --observed met --note-file f`
writes `state: closed`, `observed: met` and the note; a second `close` exits non-zero.

### AC-006: gap rule unchanged
Rows computed from the unchanged `world.gap` / `definition_hash` at spec time (main 593a6ac5).

### AC-007: digest intents block is lean and capped
With one open goal `intents` is `{"open": [{id, metric_id, last, target, gap}]}`; with 12 open goals
and 5 task worktrees the digest is ≤ 1,500 bytes, keeps `other_session` on each task, and is not
`unavailable`.

### AC-008: stages and Maker carry the lean surface
A fresh Side and Production render (Claude + Codex): spec stage has no `Step 0.5 — Intent` and no
`intent` in the frontmatter list; wrapup Step 5 names `metric measure`, `metric record`,
`question add`, `question observe`, the `intent: <verb> <id>` line, and exactly one ask, for
`close`; no `references/workflow-feedback.md`; the Maker SKILL.md names `intents.open`, not
`intents.active`, and is ≤ 4,689 characters.

### AC-009: the engine modules are gone
`harness_maker.world` and `harness_maker.intent_vocabulary` are not importable (the legacy reader
`migrate` needs lives inside `intent_migrate`), `hm world` is not a registered module, and
`autopilot_caps` has no objective gate.

### AC-010: project data fixed
`.claude/intent.yaml` `rules` contains no "Cursor", and `intent/HM-LIGHT-LANE.md` is `closed` with
`observed: met`.

### AC-011: legacy layout path
On an unmigrated fixture, `status --json` is `invalid` with an error containing `hm intent migrate`;
`hm intent migrate` on the fixtures of `tests/unit/test_intent_vocabulary.py` produces the results
those tests assert today (assertions unchanged), and succeeds on a canonical project holding a
`state: open` record.

## Verification

| Scenario | Mode | AC |
|---|---|---|
| S1 | render + unit | AC-001, AC-005 |
| S2 | render | AC-008 |
| S3 | render + unit | AC-008, AC-005 |
| S4 | render + unit | AC-001, AC-006 |
| S5 | unit | AC-003, AC-004 |
| S6 | unit | AC-011 |
| S7 | unit | AC-002 |
| — | unit | AC-007, AC-009, AC-010 |

## Open Questions

None.

## Refinement Decisions

- **Questions** (agent): kept as a list (`claim`, `status`, `evidence[]`); `--locator` is no longer
  accepted and `stale_evidence` is no longer reported (it never fired), but existing locators stay
  in the file. Cost to undo: one phase.
- **Target change** (agent): no new verb; ask, edit `metrics[].target`, validate with `status`,
  re-measure where possible. The hash keeps the target, so old rows go stale on a target change;
  this is the existing rule, kept (Non-Goals).
- **New metric** (agent): no `metric add` verb; the skill adds the entry in the same confirmation and
  `status` validates it.
- **`drop`** (agent): replaced by `close --observed no_data`.
- **Proposal path** (agent): removed; "what next" is answered from `status` by the model, which does
  that unprompted.
- **Module layout** (agent): `intent.py` keeps the project file and measurement; `intent_cli.py`
  holds records, status and the CLI; `world.py` and `intent_vocabulary.py` are deleted;
  `intent_migrate.py` carries its own legacy reader.
- **Removed verbs stay registered** for `intent` in `command_registry` as stubs, so the misroute
  guard never sends `hm intent approve` to `spec_machine approve`.
- **Tests** (agent): tests whose subject is removed are deleted with it; kept-behaviour tests move to
  the new imports with assertions unchanged.
- **HM-LIGHT-LANE** (agent proposal, DRI confirms by approving this SPEC): close as met —
  `hm_cost_ratio_small` 6.984 ≤ 8 with hidden tests ≥ plain (PR #66).
- **Stale metrics** (agent): not touched here; 6 of 9 were last measured 2026-10-04. Follow-up.
- **spec-validator** ran once (MAJOR_REVISION, 4 critical / 10 warning / 1 suggestion); every finding
  was folded in above (dropped state, verb redirect, stale-hash row, digest IRR, target/metric/close
  moments, cap test, legacy layout, locator preservation, flag list, rubric deletion withdrawn).
- **No release** in this PR; CHANGELOG [Unreleased] only.
