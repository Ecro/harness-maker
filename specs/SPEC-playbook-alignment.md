---
type: spec
task_slug: playbook-alignment
status: approved
created: 2026-09-16
tags: [harness-maker, spec, python, intent-layer, playbook, deliverables, world-state]
tier: 1
test_framework: pytest
research_doc: "[[RESEARCH-playbook-alignment]]"
summary: "INTENT-<ID>.md is the objective record: frontmatter = machine fields + hash payload, body = Playbook sections; plus three P2 fixes"
---

> Vocabulary and storage layout are superseded by [[SPEC-intent-vocabulary-rename]];
> owners shape and advisory approval guidance by [[SPEC-intent-owners-role-map]].
> This historical SPEC and its machine companion retain their original ACs and test bindings
> as compatibility evidence. Unchanged behavioral guarantees still apply.


# SPEC — Playbook alignment: the objective record becomes `work-docs/INTENT-<ID>.md`

## 🎯 Intent

Anthropic's AI-Native SDLC Playbook (2026-08-21) makes a human-written `intent.md` the first
committed artifact of the chain `intent → spec → plan → diff → review`. harness-maker already has
the machine half of that artifact — the objective record under `.claude/world/objectives/<ID>.yaml`
with its approval hash, states, `scope`/`non_scope`/`hypothesis` — but no human-readable half and no
place in the `work-docs/` chain a reader follows. This task moves the record to
`work-docs/INTENT-<ID>.md`, where the YAML frontmatter *is* the record `world.py` validates and hashes
and the markdown body carries the Playbook's five sections. One file, one source of truth. Three
small defects the last review left at P2 ride along because they live in the same files.

## 🌅 Outcomes

- An operator creates an objective with `hm world objective new OBJ-9 …` and gets a
  `work-docs/INTENT-OBJ-9.md` they can read, edit in prose, and commit like any other deliverable.
- `hm world status / show / revisit`, `/hm:plan` Step 0.5, `/hm:review` Step 3.3 and the autopilot
  `objective_gate` read the same record through the same verbs, with **no rendered-template wording
  change** for those three steps.
- Editing prose never invalidates an approval; editing a hashed frontmatter field always does.
- Every writer (`approve`, `activate`, `drop`, `reopen`, `close`) rewrites only the frontmatter; the
  body is byte-identical after any write.
- `INTENT` is a first-class deliverable prefix: committable, swept by `wrapup_land`, forgiven by the
  create-guard, all derived from `DELIVERABLE_PREFIXES`.
- The `supersedes` branch of wrapup 5.7 no longer fails by construction; `schema_version: "1.0"`
  loads exactly when it validates; a malformed outcome value row is reported, never a crash.

## 📋 In-Scope Scenarios

### S1: The frontmatter of INTENT-<ID>.md loads under the on-disk objective rules
**Given** `work-docs/INTENT-OBJ-1.md` whose frontmatter carries the objective fields and whose body is
arbitrary markdown
**When** `load_world(root)` runs from the checkout root
**Then** `world.objectives["OBJ-1"]` equals the frontmatter mapping, `id` must equal the stem after
`INTENT-`, and every rule of `_validate_objective_raw` applies unchanged
**And** a file whose frontmatter breaks a rule lands in `world.broken["OBJ-1"]` with the same error
list the rule set produces for that mapping, never in `world.objectives`
**And** a file with no frontmatter, or frontmatter that is not a mapping, is `broken` with field `file`

### S2: Every writer preserves the body byte for byte
**Given** an INTENT file with any body (CRLF, trailing whitespace, code fences, non-ASCII, empty)
**When** any of `approve`, `activate`, `drop`, `reopen`, `close`, `edit_objective` rewrites the record
**Then** the bytes after the closing frontmatter fence are identical to the bytes before
**And** the frontmatter keys are emitted in the declared order (`_OBJECTIVE_REQUIRED` then optionals)
so a repeated write of an unchanged record produces an identical file

### S3: The approval hash covers frontmatter fields only
**Given** an approved, `active` INTENT record
**When** the body prose is edited by hand
**Then** `derive(...).approval_valid` still reads `true`
**And** when any hashed frontmatter field (`hypothesis`, `scope`, `non_scope`, `outcome_id`) or the
outcome's `target` in `intent.yaml` is edited, it reads `false`, and verification writes nothing

### S4: INTENT is a deliverable derived from the single source
**Given** `DELIVERABLE_PREFIXES` contains `INTENT` and `DELIVERABLE_STATE_PATHS` no longer lists
`.claude/world/objectives/`
**When** the structural single-source test, `_is_deliverable_path`, the `.gitignore` negation and
`derive_deliverable_globs` are evaluated
**Then** `work-docs/INTENT-OBJ-7.md` classifies as `deliverable`, is not ignored, and appears in the
wrapup staging globs when such a file exists, while `.claude/world/objectives/x.yaml` no longer does
**And** `.claude/intent.yaml`, `assumptions.yaml`, `outcomes.yaml` keep their state-path status

### S5: Readers, gate and templates are unchanged in wording
**Given** the rendered `plan`, `review` and `help` commands and the 77-cell autopilot boundary baseline
**When** the task lands
**Then** those rendered bytes equal the golden and the boundary matrix equals the baseline for every
cell; only `wrapup` moves, by the attributed 5.7 change of S7
**And** the gate's `_plan_link` still reads `objective: <ID>` and halts with the same four reasons

### S6: `hm world objective new` writes a loadable skeleton
**Given** a valid `intent.yaml` with outcome `dead_rendered_bytes`
**When** `hm world objective new OBJ-9 --title T --hypothesis H --scope a --scope b --outcome dead_rendered_bytes`
runs
**Then** `work-docs/INTENT-OBJ-9.md` exists with state `proposed`, `approval: null`, `created_at` UTC Z,
`schema_version: 1`, and a body carrying the five headings `## Problem`, `## Proposed outcome`,
`## Affected users and systems`, `## Constraints`, `## Open questions`
**And** `load_world` loads it unbroken; a second `new OBJ-9` is refused without touching the file; an id
not matching `[A-Z0-9-]+` is refused naming the rule

### S7: Wrapup 5.7 can record a `supersedes` observation
**Given** the rendered wrapup 5.7 assumption block
**When** the operator's answer names relation `supersedes`
**Then** the rendered instruction carries `--claim "<new claim>"` for that relation and the
answer-gated markers, the "Otherwise: write nothing" branch and the observe verb form are unchanged

### S8: schema_version "1.0" loads exactly when it validates
**Given** `intent.yaml` with `schema_version: "1.0"` (string, same major)
**When** `validate_intent` returns no error
**Then** `load_intent` returns an `Intent` with `schema_version == 1`, and for `"2.0"` both refuse with
the same message

### S9: A malformed outcome value row is reported, not raised
**Given** `outcomes.yaml` with one valid row and one row lacking `value`
**When** `load_world` and `status_report` run
**Then** the bad row is absent from `world.values`, `world.errors` names `outcomes.yaml:values[1].value`,
`last_value` returns the valid row and `status_report` returns a payload carrying the error

### S10: A file left at the old path is diagnosed, not loaded
**Given** a file under `.claude/world/objectives/`
**When** `load_world` runs
**Then** it is not loaded as an objective and `world.errors` carries one entry naming the path and
`work-docs/INTENT-<stem>.md` as the destination

## 🚫 Non-Goals

- No mirror: the YAML objective file is retired, not kept beside the markdown (RESEARCH Approach A).
- No `intent/` folder and no dedicated intent repo; `work-docs/INTENT-` is the placement.
- No incident → intent loop (Playbook Stage 6); no LLM gap detection (previous PLAN ADR-003).
- No enforcement of the five body headings; the body is the human's.
- No converter for `.claude/world/objectives/*.yaml` (zero files exist); S10 diagnoses only.
- No rename of the PLAN link key (`objective:` stays); no change to the gate's reason enum.
- No change to `assumptions.yaml`, `outcomes.yaml` or `intent.yaml` formats.
- `edit_objective` stays as is (no CLI verb); the TOCTOU windows accepted by the previous SPEC stay accepted.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` (+ `hypothesis` for the two property ACs) | repo standard; property ACs need a generator |
| Record location | `work-docs/INTENT-<ID>.md`; `id` = stem after `INTENT-`, `[A-Z0-9-]+` | one source of truth; the deliverable regex already accepts any flat stem |
| Frontmatter parser | reuse `second_brain.parse_frontmatter(text) -> (dict, body)`; no fifth parser | four exist already; the last review flagged duplicate rule sets twice |
| Writer | one shared `_dump_intent(path, record, body)`: `yaml.safe_dump(sort_keys=False)` in declared key order, body appended verbatim, `atomic_write` | S2 byte preservation and diff-stable git history |
| Hash payload | unchanged: `{hypothesis, non_scope, outcome_id, scope, target}` from frontmatter | prose edits must not invalidate approvals |
| Two roots | INTENT files are versioned → checkout root; `approved_by` and gate events → base root | previous SPEC row; carry into every new function |
| Rendered surface | `plan`, `review`, `help` byte-identical; `wrapup` moves only by the 5.7 `--claim` line, declared via `surface_allowance` after a `BASELINE-DELTA-playbook-alignment.md` | the four frozen numbers |
| Deliverable single source | add `INTENT` to `DELIVERABLE_PREFIXES` and mirror `!work-docs/INTENT-*.md`; remove the `objectives/` entry from `DELIVERABLE_STATE_PATHS` | structural test enforces |
| Previous SPEC | `SPEC-intent-world-model-objective-layer` rows "Storage root", "Path ownership", "Objective record — required" are superseded by this SPEC; its fixtures move to `INTENT-OBJ-7.md` | AC-017's judgment subject moves; re-judge is that SPEC's business, not a blocker here |
| Security | Step 3.3's `[A-Z0-9-]+` check stays; `new` refuses ids outside it before touching the filesystem | id becomes a file name |
| Compatibility | plugin ≥ 0.57 render; no harness.yaml schema change | — |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (differential) | `test_ac_001_intent_frontmatter_loads_under_the_disk_rules` |
| S2 | unit (property, Hypothesis) | `test_ac_002_every_writer_preserves_the_body_bytes` |
| S3 | unit (property, Hypothesis) | `test_ac_003_prose_edits_keep_approval_hashed_edits_break_it` |
| S4 | structural (golden) | `test_ac_004_intent_is_a_deliverable_and_objectives_dir_is_not_a_state_path` |
| S5 | structural (golden) | `test_ac_005_plan_review_help_bytes_and_boundary_baseline_unchanged` |
| S6 | unit (differential) | `test_ac_006_objective_new_writes_a_loadable_skeleton` |
| S7 | render (golden) | `test_ac_007_wrapup_supersedes_carries_claim` |
| S8 | unit (golden) | `test_ac_008_schema_version_string_loads_when_it_validates` |
| S9 | unit (golden) | `test_ac_009_malformed_value_row_is_reported_not_raised` |
| S10 | unit (golden) | `test_ac_010_legacy_objective_path_is_diagnosed` |

### AC-001: the INTENT frontmatter loads under the on-disk objective rules
For a well-formed file the loaded record equals the frontmatter mapping; for a malformed one
`world.broken[id]` equals the error list `_validate_objective_raw` returns for that mapping and path.

### AC-002: every writer preserves the body bytes
For every writer and every body, the bytes after the closing fence are identical before and after.

### AC-003: prose edits keep approval valid and hashed edits break it
Editing the body leaves `approval_valid` true; editing any hashed field or the outcome target reads false.

### AC-004: INTENT is a deliverable and the objectives dir is not a state path
`INTENT` in `DELIVERABLE_PREFIXES`, `_is_deliverable_path("work-docs/INTENT-OBJ-7.md")`, the gitignore
negation present, `derive_deliverable_globs` lists the shape, and no `objectives/` state path remains.

### AC-005: plan, review, help bytes and the boundary baseline are unchanged
The golden's non-gated arms move only for `wrapup`; the 77-cell boundary baseline is equal cell for cell.

### AC-006: objective new writes a loadable skeleton
`new` produces a `proposed`, unapproved record with the five headings; duplicate and bad ids are refused.

### AC-007: wrapup supersedes carries claim
The rendered 5.7 block names `--claim` for `supersedes` and keeps the answer-gated markers.

### AC-008: schema_version string loads when it validates
`load_intent` and `validate_intent` share one major parser: `"1.0"` loads, `"2.0"` refuses in both.

### AC-009: malformed value row is reported not raised
The bad row is excluded from `world.values`, named in `world.errors`, and `status_report` returns.

### AC-010: legacy objective path is diagnosed
A file under `.claude/world/objectives/` is not loaded and one error names it and the INTENT destination.

### Test files (spec gate)

| Test file | ACs |
|---|---|
| `tests/unit/test_frontmatter_split.py` | AC-001 (fence statuses), AC-002 (byte-exact body) |
| `tests/unit/test_intent_doc_record.py` | AC-001, AC-002, AC-003, AC-010 |
| `tests/unit/test_intent_doc_new.py` | AC-006 |
| `tests/structural/test_deliverable_single_source.py` | AC-004 |
| `tests/structural/test_playbook_alignment_invariance.py` | AC-005 |
| `tests/unit/test_render_intent_layer.py` | AC-007 (wrapup 5.7 block) |
| `tests/unit/test_intent_validate.py` | AC-008 |
| `tests/unit/test_world_outcomes.py` | AC-009 |
| `tests/integration/test_intent_layer_lifecycle.py` | lifecycle via `objective new` (Phase 5) |

## ❓ Open Questions

None — resolved in the interview (see Refinement Decisions).

## 🔍 Refinement Decisions

- Round 1: **B** (INTENT-<ID>.md is the record) over mirror (A) and YAML prose fields (C); ids stay
  `[A-Z0-9-]+` with `INTENT-<ID>.md`; `hm world objective new` writes the skeleton; the three P2
  leftovers are bundled (S7–S9).
- Round 2: PLAN link key stays `objective:`; body headings advisory (written by `new`, not
  validated); no converter for the old path, diagnosis only (S10); oracles as declared per AC
  (differential for S1/S6, property for S2/S3, golden elsewhere).
