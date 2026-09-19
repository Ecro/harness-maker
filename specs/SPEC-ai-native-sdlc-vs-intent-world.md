---
type: spec
task_slug: ai-native-sdlc-vs-intent-world
status: approved
created: 2026-09-19
tags: [harness-maker, spec, python, jinja2, dri, spec-approval, autopilot, irreversible-decisions]
tier: 1
test_framework: pytest
research_doc: "[[RESEARCH-ai-native-sdlc-vs-intent-world]]"
summary: "DRI acceptance slice: hash-bound SPEC approval, autopilot stops at spec, irreversible-decision list, land hold at every land path"
---

# SPEC — DRI acceptance: SPEC approval, irreversible decisions, land hold

## 🎯 Intent

With implementation authored by agents, the human (DRI) contributes acceptance — the oracle
and the irreversible decisions — not authorship. Today nothing records that acceptance: a
SPEC becomes `approved` automatically when its Open Questions section is empty
(`spec.md.j2:342`), autopilot advances from spec with no human stop
(`autopilot_caps.py:60` gates only `plan` and `review`), and an irreversible decision an
agent makes during execute is never surfaced before the work lands. This is slice 1+2 of
[[RESEARCH-ai-native-sdlc-vs-intent-world]]'s ranked list, revised after the Codex
cross-model review (RESEARCH §"Codex cross-model review"), and the prerequisite for any later
removal of `/hm:plan`.

## 🌅 Outcomes

- A SPEC's acceptance is a recorded, content-bound fact: who, when, over which content.
  Changing any authored field afterwards invalidates it; tooling bookkeeping does not.
- Under `auto_safe`, autopilot cannot advance past an unaccepted SPEC, and it decides this
  from the SPEC itself, not from the stage's own claim. Under `auto_full` it proceeds — the
  user's explicit delegation — without creating a human stamp.
- Every new SPEC declares its irreversible decisions (possibly none) with stable ids. A
  decision discovered during execute is appended, which invalidates the approval.
- **No land path** — wrapup commit (worktree on or off), `task-land`, loop finalize — lands
  work whose SPEC is in a hold state. Wrapup offers the DRI the list and an on-the-spot
  approval first; no answer, no tool, or a loop context means the hold stands.
- Trivial SPECs, SPEC-less tasks and pre-feature SPECs add zero prompts.

## 📋 In-Scope Scenarios

### S1: Interview ends with approval
**Given** a `/hm:spec` interview whose final answer is "Approve this SPEC and end interview"
**When** the SPEC files are written and `spec_machine check` passes
**Then** machine.yaml carries `approval: {kind: human, content_hash, approved_by, approved_at}`
**And** `approved_by` is `git config user.name` read at the base repo root

### S2: Bookkeeping keeps the approval; authored edits break it
**Given** an approved SPEC
**When** tooling writes `test_ids`, `pending_test`, judgment verdict fields, quality score or mutation date
**Then** the state stays `approved`
**And** changing any other field — including `schema_version`, `rubric_id`, `judgment_subject_paths`, `preconditions`, an irreversible decision — makes it `invalid`

### S3: Autopilot stops at an unaccepted SPEC, whatever the stage claims
**Given** autopilot at `auto_safe` and a task SPEC whose state is not `approved`/`exempt`
**When** the spec boundary runs, even with `--judgment-gate clear`
**Then** it halts with `halt_kind: judgment_gate`, marker preserved
**And** at `auto_full` it proceeds, writes `gate_auto_answered`, and creates no `approval`

### S4: Execute discovers an irreversible decision
**Given** an approved SPEC and a decision in one of the five categories that the list lacks
**When** execute handles it
**Then** it appends `{id: IRR-<next>, decision, category, rationale, source: execute}` and the state becomes `invalid`
**And** interactively the DRI is asked to re-approve now; otherwise the land hold catches it

### S5: Every land path holds
**Given** a task SPEC in a hold state (table in Constraints)
**When** wrapup reaches land, `wrapup_land` commits, `task-land` squashes (after its pending-edit capture), or the loop runs `finalize success`
**Then** wrapup first shows the list and asks approve-or-keep; approval re-stamps and lands
**And** with no answer, no question tool, or inside a loop, and at every Python land entry, the land is refused with a named hold reason and the task checkout is kept

### S6: Exempt, SPEC-less and legacy work add no prompts
**Given** a Step 0-skip SPEC stamped `kind: exempt`, a task with no SPEC files, or a v1/v2 SPEC without the new fields
**When** the spec boundary and the land checks run
**Then** exempt passes both while its hash matches and its list is empty
**And** SPEC-less and legacy pass the land checks with a one-line notice

## 🚫 Non-Goals

- Removing `/hm:plan`, removing `dev_mode`, a `spec-validator` critic — later slices.
- Vocabulary renames, `owners` role map, `intent/` folder, ticket intake, new withdrawal
  criterion, mutation-oracle repair.
- Proving the approver is human, cross-person gates, delegates (`approved_by` is an unverified
  `git config` string and the CLI can be called by an agent — same accepted limitation as
  objective approval; the stamp records the harness flow, it does not prove intent).
- `approval.provenance` counts, `added_at`, an ambiguity-score gate (Codex review: ceremony).
- Changing the SPEC `status` field's meaning; retroactively stamping existing SPECs.
- Hashing SPEC.md prose.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | repo standard; unit for CLI/gates/land entries, render tests for templates |
| Language / typing | Python 3.12, `mypy --strict`, `ruff` | CLAUDE.md technical decisions |
| Hash scope (deny-list) | canonical JSON of the whole machine.yaml — **including keys unknown to the model** — with default-valued fields omitted, **except** top-level `approval, spec_quality_score, spec_quality_score_at, last_mutation_run` and per-AC `test_ids, pending_test, judgment_verdict, judged_at, judgment_evidence, judgment_subject_hash` | every authored field is hashed, tooling-written fields are not; adding a defaulted field to the model in a later release does not change existing hashes (Codex + plan-validator) |
| Model round-trip | `approval` and `irreversible_decisions` are `SpecMachine` fields; unknown keys round-trip; `null` means absent and absent keys stay absent on write | `mark_tested`/`mark_judged` rewrite via `model_dump`; legacy files must not gain `approval: null` |
| Irreversible item | `{id: IRR-NNN (unique, never renumbered), decision, category, rationale, source: spec\|execute}` | stable references; `source` = where found, never whether a human approved |
| Categories | schema/file format/storage layout · public API/CLI contract · data migration · security/permission boundary · new external dependency; cost, scale and compliance are judgment **examples**, not categories | LLM judges; the BMAD admission questions (could independent units choose incompatibly? non-obvious? real trade-off?) are used only to **narrow** the list, never as a strict AND gate |
| Schema | `schema_version: 3` requires `irreversible_decisions`; v1 (omitted) / v2 valid without it | explicit absent-case |
| State table | see below | one function decides state for every consumer |
| Land decision | **hold** iff state ∈ {invalid, malformed} **or** (list non-empty and state ≠ approved); else ok | an approved-then-emptied list still holds (Codex) |
| SPEC location | an explicitly passed checkout wins; else `<base>/.worktrees/<slug>` when it exists; else the base. Land entries on a non-`hm/*` checkout (loop `execute-<uuid>`, worktree-off) evaluate **every** `specs/SPEC-*.machine.yaml` the branch changed since its merge-base (plus uncommitted), holding if any holds; a slug argument only adds to that set | the loop's slug is not the SPEC slug, and a leftover same-slug task worktree must not shadow the real checkout |
| CLI | `hm spec_machine approve [--exempt]` and `hm spec_machine approval-status`, registered in `command_registry` and exercised through the real `main()` | `approve` is registered as a `world` verb today; the guard runs before the parser |
| Autopilot | `spec` joins `_JUDGMENT_GATED_STAGES`; for `--current spec` the boundary derives the gate from the SPEC state and takes the more restrictive of (caller flag, derived); `malformed` → blocked | the caller's `clear` is not trusted |
| No answer | a missing question tool (Cursor/Codex fallback), no reply, or loop mode is never approval | hold stands |
| Targets | Claude Code, Cursor, Codex renders all carry the changed text | multi-target parity |
| Dogfood | the rendered harness pins the released plugin cache | memory `project_rendered_harness_pins_released_plugin` |
| Always-loaded context | no additions to CLAUDE.md / AGENTS.md | context budget |

**State table** (evaluated in order; first match wins)

| # | Condition | State | Spec gate | Land |
|---|---|---|---|---|
| 1 | no SPEC.md and no machine.yaml for the slug | `no_spec` | pending | ok + notice |
| 2 | SPEC.md present, machine.yaml absent or unparsable | `malformed` | blocked | hold |
| 3 | `schema_version ≥ 3` and `irreversible_decisions` absent, or `approval` present but not a valid block | `malformed` | blocked | hold |
| 4 | `approval` present, hash ≠ current | `invalid` | pending | hold |
| 5 | `approval.kind: exempt`, hash matches, list non-empty | `invalid` | pending | hold |
| 6 | `approval.kind: exempt`, hash matches, list empty | `exempt` | clear | ok |
| 7 | `approval.kind: human`, hash matches | `approved` | clear | ok |
| 8 | no `approval`, `schema_version < 3`, no list | `legacy` | pending | ok + notice |
| 9 | no `approval`, otherwise | `missing` | pending | hold iff list non-empty |

## 🔒 Irreversible Decisions

(Dogfooding the section this SPEC introduces.)

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | machine.yaml gains `approval` and `irreversible_decisions`; `schema_version: 3` | file format | every future SPEC and reader depends on the shape |
| IRR-002 | CLI verbs `hm spec_machine approve` / `approval-status` | public CLI contract | rendered stages in user harnesses call them by name |
| IRR-003 | `spec` becomes a judgment-gated autopilot stage whose gate is derived from the SPEC | public contract (autopilot) | changes when every armed pipeline stops |
| IRR-004 | land entries (`wrapup_land`, `task-land`, loop `finalize`) refuse on hold | public CLI contract | changes the exit behaviour of three existing commands |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (real CLI `main()`) | `test_ac_001_approve_records_stamp`, `test_ac_001_empty_user_name_refuses`, `test_ac_001_verbs_are_registered` |
| S2 | unit (property) | `test_ac_002_valid_iff_only_denylisted_fields_changed`, `test_ac_002_round_trip_keeps_new_fields` |
| S3 | unit (parametric) | `test_ac_003_spec_boundary_table` |
| S4 | unit + render | AC-002 append case + `test_ac_007_execute_renders_escalation_rule` |
| S5 | unit (parametric) + render | `test_ac_005_state_table`, `test_ac_006_land_entries_refuse_on_hold`, `test_ac_007_wrapup_asks_before_land` |
| S6 | unit | AC-005 rows 1, 6, 8 |

Test files: `tests/unit/test_spec_approval.py` (AC-001/002/004/005),
`tests/unit/test_autopilot_spec_gate.py` (AC-003), `tests/unit/test_land_hold.py` (AC-006),
`tests/render/test_spec_acceptance_render.py` (AC-007),
`tests/structural/test_ai_native_sdlc_invariance.py` (plan/review pins, surface bounds).

### AC-001: approve records a content-bound stamp at the base-root identity
`hm spec_machine approve --yaml <path>`, run through the real `main()`, writes
`approval: {kind: human, content_hash, approved_by, approved_at}`; `--exempt` writes
`kind: exempt` with the same hash and no identity requirement. With an empty base-root user
name the human form exits non-zero and the file is byte-identical. Both verbs are registered
so the command-registry guard routes them to `spec_machine`.

### AC-002: approval is valid iff only deny-listed fields changed
For any SPEC, after changing exactly one field, the state is unchanged if the field is on the
deny-list and `invalid` otherwise; a `mark-tested` / `mark-judged` round-trip keeps
`approval` and `irreversible_decisions` intact.

### AC-003: spec boundary follows the approval state, not the caller's claim
For `--current spec`, the boundary outcome for (level × state × caller flag) matches the
table in machine.yaml; a caller `clear` never clears a non-approved state; `malformed` blocks
at every level; `auto_full` proceeds on `pending` without writing an `approval`.

### AC-004: schema v3 requires a well-formed irreversible-decision list
`validate` rejects a v3 file without `irreversible_decisions`, with a duplicate or
ill-formed id, an unknown category, or an unknown `source`; it accepts v1/v2 without the key.

### AC-005: approval-status follows the state table
`hm spec_machine approval-status` returns `{state, land, irreversible, notice?}` exactly as
the nine-row state table in this SPEC for each row's fixture, including an approved SPEC whose
list was later emptied (`invalid`, hold) and a v3 file stripped by an older writer
(`malformed`, hold).

### AC-006: every land entry refuses on hold
With a task SPEC in a hold state, `wrapup_land` aborts before staging, `worktree task-land`
aborts after its pending-edit capture and before squashing, and `worktree finalize` in the
success path aborts — each with a non-zero exit, a `hold:` reason naming the state and ids, and
the task checkout intact; with state ok each proceeds unchanged. `finalize` checks every
worktree before merging any, finds the SPECs from the branch diff (no slug needed), and still
lands a SPEC-less loop.

### AC-007: stage renders carry the acceptance flow
Rendered `spec`, `execute`, `wrapup` and `loop` commands (all targets) contain: the final
option "Approve this SPEC and end interview" and the Step 0 `--exempt` stamp; the execute
escalation rule with the five categories, the narrowing questions and the examples; the
wrapup approve-or-keep question before land with "no answer / no tool = hold"; the loop's
halt on a hold refusal.

## ❓ Open Questions

(none — plan owns module layout, template wording and the surface-budget allowance)

## 🔍 Refinement Decisions

- Round 1: scope = slice 1+2; `auto_full` proceeds without a stamp; approval = the interview's
  final answer; Step 0 skip SPECs exempt, recorded.
- Round 2: execute escalation = append to the list → approval invalid; wrapup asks approve-now
  or keep worktree; LLM judges irreversibility against five categories; legacy SPECs pass
  with a notice.
- Round 3: oracle table accepted; `status` unchanged, approval separate.
- Revision 1 (after surveys + Codex review, re-approved by the user 2026-09-19): hash by
  deny-list; invalid approval holds regardless of the list; exemption is a hash-bound stamp;
  nine-row state table incl. malformed / old-writer / v1-v2 / no-spec; CLI registered and
  tested through `main()`; the spec boundary derives the gate from the SPEC; no answer = hold;
  land hold enforced in the templates **and** at the three Python land entries; list items
  get `IRR-NNN` ids and `source`; admission questions narrow only; cost/scale/compliance are
  examples; `provenance`/`added_at`/score gate dropped; "the stamp is not proof of a human"
  recorded as an accepted limitation.
- Revision 2 (after plan-validator + Codex plan review, re-approved by the user 2026-09-19):
  land entries derive the SPEC set from the branch diff (loop slug ≠ SPEC slug); explicit
  checkout wins; hash with defaults omitted and unknown keys kept; `null` = absent, absent
  stays absent on write; `finalize` checks all worktrees before any merge; this SPEC's
  machine.yaml migrated to `schema_version: 3` with IRR-001..004 (`source: spec`).
- The machine stamp cannot be written until `approve` ships; at wrapup, after the last
  `mark-tested`/`mark-judged` write, stamp from the worktree source and confirm `approved`.
