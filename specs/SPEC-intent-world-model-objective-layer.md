---
type: spec
task_slug: intent-world-model-objective-layer
status: draft
created: 2026-09-16
tags: [harness-maker, spec, python, intent, assumptions, objective, state-only]
tier: 1
test_framework: pytest
research_doc: "[[RESEARCH-cell-dev-future-and-intent-layer-fit]]"
summary: "State-only intent layer: intent.yaml + assumptions ledger + human-picked objective bound to an approval hash, read by hm status and the autopilot boundary; validity and revalidation are derived at read time, never stored; scope drift of the work itself is an LLM review judgment"
---

# SPEC — Intent / Assumptions / Objective layer (state-only slice)

> **Revision 6.1 (2026-09-16, during `/hm:plan`).** Prose corrections only, each traced to a
> plan-validator or codex plan-stage finding, none changing a decision: the CLI verbs take the
> `hm world <verb>` form (ADR-001 — `hm` dispatches `hm <module>`); AC-013's finalize clause is
> "byte-identical after the stash round trip" (deliverables are stash-preserved by design);
> `scope_drift` is severity **P2** (a manual-only P1 sets `human_review_needed`, which is a gate);
> AC-011's render predicate accepts the shipped `!uv run` / `Bash("uv run` forms; the gate event
> field is `display_ref` everywhere; wrapup staging is `hm wrapup_land` via
> `derive_deliverable_globs`, not a `git add` line; `/hm:plan`'s addition is `Step 0.5`.
>
> **Revision 6 (2026-09-16).** The codex review of revision 5 returned 13 findings (P1 2 · P2 11).
> The one real design hole was mine: "resolve the base root like `second_opinion_invoke`" would
> make the boundary read the **main** checkout's PLAN from inside a task worktree, find no link,
> and advance. This revision splits the roots — **versioned files (PLAN, intent, world) live in
> the current checkout; only operational markers and ledgers use the base root** — and adds the
> two-checkout fixture. It also adds the codex review surface to the AC-017 subject, states the
> skill promise as "available and listed" rather than "triggered", carves the explicit surface
> exception, types the assumption record, normalises timestamps to UTC on input, requires the
> per-objective loop in the plan prose, separates typed raw link values from display strings,
> and settles referential breakage as reported-not-transactional. This is the last SPEC revision
> before `/hm:plan`; what remains after the next review moves to Open Questions.
>
> **Revision 5 (2026-09-16).** The codex review of revision 4 returned 14 findings (P1 6 · P2 8)
> and the verdict "not yet". Three of the P1s were contradictions this document introduced in
> revision 4 (dropped immutability vs reopen; skeleton validity vs the non-empty `mission` rule;
> the stale-value gap stated two ways). This revision fixes those; makes the **PLAN link
> resolution part of the tested entrypoint** with present-but-invalid distinct from absent;
> narrows the Outcomes promise to the approval payload of non-terminal objectives; binds the
> scope-drift judgment to the **rendered lens text** so removing the lens invalidates the
> verdict; adds an explicit answer-gated branch contract to wrapup; pins required / nullable /
> referential rules for every record; removes `status: conflict` from the revisit grammar; adds
> a latest-value selection property; checks the import graph of all four entrypoints; and adds
> one **skill** (`intent-layer`) as the discoverable surface for the CLI verbs — the operator
> asks in prose, the skill runs the verb, nothing is written without an answer.
>
> **Revision 4 (2026-09-16).** Revision 3 withdrew the measurement bundle; the codex review of
> it returned 19 findings, of which two were promise/mechanism mismatches: the approval hash
> detects edits to the *objective record*, not growth of the *work*, and the task↔objective link
> that the gate depends on had no contract. This revision (a) **narrows the mechanical promise**
> to "changes to an approved objective record are detected" and adds a **`/hm:review` judgment
> lens** for work-vs-objective drift (decision A); (b) makes the task link a **single-source,
> absent-vs-dangling** contract; (c) makes approval validity and `needs_revalidation` **derived
> at read time, never stored**, which removes every terminal-state contradiction and every
> multi-file write; (d) adds an explicit `resolve` transition for `conflict`; (e) pins the
> revisit grammar, the two canonical hash payloads, the numeric value contract, gate precedence,
> and required-vs-optional fields; and (f) tightens every predicate the review named.

## 🎯 Intent

harness-maker stores **how to build** (`harness.yaml`, `CLAUDE.md`) and **what happened**
(`memory/`, `observability/`), but nothing stores **why the project exists**, **what it currently
assumes**, or **which piece of work the human actually chose and why**. The cost is measurable:
five fused workflow commands shipped at 58.5% of rendered command bytes with zero recorded
invocations, and nothing in the harness could have said that this contradicted any stated
outcome.

This SPEC adds three small pieces of durable state under `.claude/`, all human-written or
human-approved, all committed, none requiring an LLM to read:

1. **`intent.yaml`** — mission, outcomes with numeric targets, and optional vision,
   non-negotiables, non-scope, unknowns, owners.
2. **`world/assumptions.yaml`** — facts the project acts on, each `known | assumed | unknown |
   conflict`, with evidence, history and a `revisit_when` condition.
3. **`world/objectives/<id>.yaml`** — the objective the human picked: hypothesis, scope,
   non-scope, rejected alternatives, the outcome it serves, and an approval bound to a content
   hash with provenance.

Outcome *values* are recorded by a human with provenance in `world/outcomes.yaml`. Nothing is
measured automatically; nothing is scheduled; nothing computes a verdict. **What the Python
layer guarantees is narrow and mechanical**: a change to the **approval payload** (scope,
non-scope, hypothesis, outcome id, target) of a `proposed` or `active` objective is detected, a
task linked to an objective without a valid approval does not advance under autopilot, and a
contradiction never silently discards a side. Fields outside the payload (`depends_on`,
`rejected`, `revisit_when`) and terminal objectives are outside that guarantee by design. **Whether the work itself has
outgrown its objective is an LLM judgment**, made by `/hm:review` from the PLAN and the
objective record, and reported as a review finding.

## 🌅 Outcomes

A maintainer returning after days away runs one LLM-free command and sees the mission, each
outcome's last recorded value against its target with the date it was recorded, the active
objective and whether its approval still holds, open unknowns, facts in conflict, and any revisit
condition that has fired. When `/hm:plan` proposes work, it can say whether a prior decision
already rejected it and whether the condition that would justify reopening is met. A `proposed`
or `active` objective whose approval payload is edited afterwards reads as unapproved
everywhere, and the autopilot boundary halts on it. The operator does not have to remember a
verb: the `intent-layer` skill is available on every target and listed in `/hm:help`, its
description names the situations ("record that we found X", "close the objective", "where are
we"), and when the model selects it the skill runs the matching CLI verb and asks before every
write. Whether the model selects it on a given phrasing is model behaviour and is **not**
promised by this SPEC; `hm world status` remains callable directly as the deterministic fallback. When `/hm:review` sees a PLAN whose scope has drifted from the objective it
claims to serve, it says so as a finding. When a human closes an objective they record what they
observed, not what the machine inferred.

## 📋 In-Scope Scenarios

### S1: The intent skeleton is created once and never overwritten
**Given** a project with no `.claude/intent.yaml`
**When** `/harness-maker:make` runs
**Then** a commented skeleton is written with every recognised field present, typed as its empty value (`mission: ""`, `vision: ""`, every list `[]`) and `schema_version` filled
**And** `hm world status` on that skeleton reports `not_filled_in` — the state where `mission` is empty **and** `outcomes` is empty — rather than failing
**And** a file with an empty `mission` but a non-empty `outcomes` is a validation error naming `mission`, not a skeleton
**And** a second `make --update` on a hand-filled file leaves every byte unchanged
**And** no field is ever filled in by an LLM at make time

### S2: An observation is filed against an assumption by relation, and a contradiction loses neither side
**Given** an assumption recorded `known` with evidence E1
**When** an observation E2 is filed with relation `contradicts`
**Then** the assumption's status becomes `conflict`, both E1 and E2 survive a save-and-reload with their text, time and relation intact, and the claim is unchanged
**And** an observation filed with relation `supersedes` replaces the claim, appends the prior claim to history, and leaves the status unchanged
**And** an observation filed with relation `confirms` appends evidence and leaves claim and status unchanged
**And** only `assumptions.yaml` is written — no objective file changes

### S3: A conflict is resolved by an explicit human transition
**Given** an assumption in `conflict`
**When** the human runs `resolve` with a target status in `{known, assumed, unknown}` and a claim
**Then** the status and claim are set, the prior claim is appended to history, and all evidence is retained
**And** `resolve` to any other status, or on an assumption not in `conflict`, is refused

### S4: `needs_revalidation` is derived, never stored
**Given** an assumption in `conflict`
**When** any reader (status, plan, boundary check) computes it
**Then** every `proposed` or `active` objective naming that assumption in `depends_on` reads `needs_revalidation: true`, and every `closed` or `dropped` objective reads `false`
**And** the flag appears in no file, and it blocks nothing

### S5: An outcome value without provenance, or of the wrong shape, is refused
**Given** an outcome declared in `intent.yaml`
**When** a value is recorded with `observed_at` missing, not ISO-8601, or naive (no timezone) — any timezone-aware form is accepted and stored normalised to UTC `Z` — or `evidence` missing or empty, or `value` non-numeric, or an unknown `outcome_id`
**Then** each case is refused with an error naming that specific field
**And** the outcomes file's bytes are unchanged
**And** a complete record stores the `definition_hash` of the outcome's current definition

### S6: A change to an approved objective record is detected, and validity is derived
**Given** an `active` objective whose `approval.content_hash` covers scope, non-scope, hypothesis, outcome id and the outcome's target at approval time
**When** any of those inputs is edited afterwards
**Then** every reader computes `approval_valid: false`; the objective's stored `state` is untouched and verification writes nothing
**And** editing `depends_on`, `rejected`, `revisit_when`, or the outcome's `how_measured` leaves it valid
**And** a `closed` or `dropped` objective is never re-verified — its approval is a historical record
**And** re-approving writes a new approval block over the current inputs

### S7: The task link is single-source, read by the entrypoint; absent, invalid and dangling differ
**Given** a task slug whose `work-docs/PLAN-<slug>.md` frontmatter may carry `objective:`
**When** the autopilot boundary entrypoint runs for that slug
**Then** it reads the link from that file **in the current checkout** (the task worktree when run there) — no caller passes an objective in, and the main checkout's PLAN is never consulted from a worktree
**And** when the task worktree carries a PLAN with a link and the main checkout carries none, or a different one, the worktree's link is the one used
**And** with the key absent, or the PLAN file absent, the result equals the pre-change baseline for every stage and input
**And** with the key present and the id resolving to an `active` objective with a valid approval, the result equals the baseline
**And** with the key present but null, empty, non-string, or the frontmatter unparseable, the check halts with `objective_gate` and reason `link_invalid` — present-but-invalid is never treated as absent
**And** with a well-formed id that is missing on disk, not `active`, or with an invalid approval, it halts with reason `missing`, `not_active` or `approval_invalid`
**And** every halt above applies **only where the baseline would have advanced** — every existing halt keeps precedence — and records a gate-blocked event carrying `reason`, a typed `raw_link` (the YAML value as parsed when it is a JSON-representable scalar, list or map; otherwise the object `{"yaml_type": <tag name, e.g. "date">, "repr": <str()>}`; or `null` with `parse_error: true` when the frontmatter did not parse) and a `display_ref` string (the id, or `repr()` of the raw value, or `"<unparseable frontmatter>"`) that also appears in the halt message — the event must always serialise as JSON

### S8: Closing an objective records what the human observed
**Given** an `active` objective
**When** the human closes it
**Then** `observed ∈ {met, missed, no_data}`, a non-empty `note` and `closed_at` are persisted, and any later edit of the record is refused
**And** a close missing either field, or with any other `observed`, is refused by field name and writes nothing
**And** `/hm:wrapup` asks the operator whether to file an assumption observation and whether to close the task's objective, performs each write only on an affirmative answer, and carries an explicit "otherwise write nothing" branch for each

### S9: A prior decision advises but never blocks
**Given** an objective record with `rejected[]` and a `revisit_when` in the grammar of the Constraints table
**When** `/hm:plan` runs
**Then** it loads the intent and assumptions before Step 1, and for each objective whose `rejected[]` the LLM judges to match the proposed work, invokes the revisit check and displays the record, the condition and the last recorded value
**And** the check is invoked once per matching objective with that objective's id — the prose is an explicit loop over the matches, not a single call — and prints the record's title, the condition, and the last recorded value it was evaluated against
**And** the check returns `candidate`, `not_met`, or `unevaluable` — the last whenever the referenced outcome has no value, its last value has a stale definition, the referenced assumption is in `conflict`, or the reference does not resolve — and never blocks in any of the three

### S10: `/hm:review` judges work-vs-objective drift
**Given** a PLAN linked to an objective
**When** `/hm:review` runs
**Then** it reads the objective's scope, non-scope and hypothesis and the PLAN's scope, and emits a `scope_drift` finding at **severity P2** when the PLAN adds work outside the objective's scope (whether or not it is named in non-scope), adds work inside non-scope, or omits the subject of the hypothesis — citing the objective id and, for an addition, the offending PLAN item, or, for an omission, the objective requirement and where in the PLAN it is missing
**And** the finding enters the normal review flow with an id — it is a finding, not a gate; P2 is what keeps it out of `unverified_severe`, since a voice-less P1 would set `human_review_needed` and stop the stage
**And** the judgment of this lens is bound to the rendered review surface **of every target** — `.claude/commands/hm/review.md` and, for codex, `.agents/skills/hm-review/SKILL.md` — so changing or removing the lens on either invalidates the recorded verdict
**And** re-judgment after any edit to those files, including edits unrelated to this lens, is an **accepted cost**: four fixture pairs per target per re-judgment

### S13: The verbs are discoverable without remembering them
**Given** a rendered harness for any target
**When** the operator says in prose that they observed something, want to close or approve an objective, record an outcome value, or asks where the project stands
**Then** the `intent-layer` skill is available, its description names those situations, its body lists the four verbs **with their full argument forms**, and it instructs the model to run `hm world status` freely but to ask before any write, to run the write exactly once with the arguments the operator confirmed, and to write nothing on a non-affirmative or absent answer
**And** whether the model selects the skill for a given phrasing is not promised; `hm world status` is the deterministic fallback
**And** the skill renders under `.claude/skills/` and, for the codex target, `.agents/skills/`, and `/hm:help` lists it
**And** no new slash command is rendered

### S11: All new paths are shared knowledge — committed, never swept
**Given** a rendered harness with the new layer and a clean consuming project holding two objective files
**When** `git check-ignore -v` runs against each new path, then `make --update`, then `worktree finalize`, then the rendered `/hm:wrapup` staging step
**Then** `intent.yaml`, `world/assumptions.yaml`, `world/outcomes.yaml` and each `world/objectives/<id>.yaml` are not ignored, classify as `deliverable`, survive `make --update` byte-for-byte, are **byte-identical after the finalize stash round trip** (deliverables are stash-preserved by design, like PLAN and SPEC), and are present in the git index after `hm wrapup_land` runs

### S12: `hm world status` has a fixed, LLM-free, read-only contract
**Given** a populated intent, assumptions, outcomes and objective set
**When** the `hm world status` CLI entrypoint runs
**Then** its stdout carries mission; per-outcome last value, target, observed-at, gap direction and whether the value predates the current definition; each active objective with `approval_valid` and `needs_revalidation`; open unknowns; assumptions in `conflict`; and every `revisit_when` that evaluates `candidate`
**And** the entrypoint's import graph reaches no LLM client, no file changes, and exit code is 0

## 🚫 Non-Goals

- **Automated measurement of any kind.** No `measure_cmd`, no cadence, no budget, no scheduler,
  no ledger. Reconsidered only when one real project has a metric worth polling.
- **Verdicts, horizons, `released_at`, an `evaluating` state.** The human writes `observed:`.
- **Mechanical detection of work drift.** The hash detects edits to the objective *record*;
  drift of PLAN or execution scope away from an unchanged record is the `/hm:review` judgment
  in S10, and it is a finding, not a gate (decision A, revision 4).
- **Candidate objective generation** (`/hm:objective`). `/hm:plan` may draft an objective
  record for the human to edit; no rendered command.
- Jira / Linear / Teams / Confluence sync, org hierarchy, multi-Cell aggregation, a World-Model
  server, an AI-manager UI, a vector store, a knowledge graph, a second memory system.
- Migrating existing PLANs into assumptions. Cell-mode behaviour (`owners:` has no runtime
  effect). A lock on the active-objective cap. Forgery-proof approval.
- Fact identity beyond a human-chosen id, validity intervals, automatic supersession or
  automatic conflict resolution. Relations are asserted by the caller; resolution is a human
  transition.
- Non-numeric outcomes, units, aggregation, baselines, minimum samples. v1 compares one number
  to one number in one declared direction.
- Any addition to the always-loaded surface (`CLAUDE.md`, SessionStart hook output), **with one
  named exception**: the `intent-layer` skill's index line (name + description), which is the
  price of discoverability and is bounded by the Skill-contract row.
- Cross-file transactional writes. Every mutation touches exactly one file; derived state is
  what makes that sufficient. Referential integrity across files is **validated on read and
  reported**, never enforced on write (see the Referential-breakage row).
- A guarantee that the model selects the `intent-layer` skill for a given phrasing.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | CLAUDE.md fixed toolchain |
| Language | Python 3.12+, `mypy --strict`, `ruff` | CLAUDE.md fixed toolchain |
| File writes | atomic write; `intent.yaml` is **write-if-absent only**; every mutation writes exactly one file | `implementation-patterns.md`; derived state removes the need for multi-file updates |
| Intent fields — required | `schema_version`, `mission` (non-empty string), `outcomes` (list, may be empty) | the minimum `hm world status` can render |
| Intent fields — optional | `vision`, `non_negotiables[]`, `non_scope[]`, `unknowns[]`, `owners[]`; all present-and-empty in the skeleton; absent on read is treated as empty | enumerated so AC-001/002 have a reference that predates the validator |
| Outcome item | `id` (unique, `[a-z0-9_]+`), `description`, `target` (JSON number), `higher_is_better` (bool), `how_measured` (string); all required | numeric-only is the v1 comparison contract |
| Assumption record | required: `id` (unique, `[a-z0-9_]+`), `claim` (non-empty string), `status ∈ {known, assumed, unknown, conflict}`; optional with defaults: `evidence[]` default `[]` (each entry requires `text` non-empty string, `observed_at` timestamp, `relation ∈ {confirms, supersedes, contradicts}`), `history[]` default `[]` of strings, `revisit_when` default null (grammar below); any other type, a null required field, or an unknown key is a validation error naming the field | five user-facing fields; the research found no practitioner evidence for anything richer |
| `resolve` transition | `conflict → {known, assumed, unknown}` with a new claim; any other source status refused; evidence retained; prior claim appended to history | the only path out of `conflict`; nothing infers it |
| Objective record — required | `id` (equals the file stem, `[A-Z0-9-]+`), `title`, `hypothesis`, `scope[]` (non-empty), `outcome_id` (must exist in `intent.outcomes` at read time — see Referential breakage), `state ∈ {proposed, active, closed, dropped}`, `created_at`, `schema_version` | `needs_revalidation` and `approval_valid` are **not** fields **Superseded by SPEC-playbook-alignment (2026-09-16): the record is `work-docs/INTENT-<ID>.md` — frontmatter = these fields, `id` = the stem after `INTENT-`.** |
| Objective record — optional / nullable | `non_scope[]` and `rejected[]` default `[]`; `depends_on[]` default `[]`, every entry must be an existing assumption id (a dangling entry is a validation error, never read as "not in conflict"); `approval` null until approved; `revisit_when` null; `observed`, `note`, `closed_at` null until `closed` and required non-null once `closed` | absent-case defined per field |
| File envelopes | `assumptions.yaml` = `{schema_version, assumptions: []}` with unique ids; `outcomes.yaml` = `{schema_version, values: []}`; each objective file is one record | the loader validates the envelope before any record |
| Skeleton validity | validation always checks types and unknown keys; the non-empty `mission` rule is waived **only** in the `not_filled_in` state (`mission` empty **and** `outcomes` empty); empty `mission` with non-empty `outcomes` is an error naming `mission` | a strict loader must accept the file it just generated, and a half-filled file must not hide as a skeleton |
| Derived at read time | `approval_valid` = state ∈ {proposed, active} ∧ approval present ∧ recomputed hash == `content_hash`; `needs_revalidation` = state ∈ {proposed, active} ∧ any `depends_on` assumption in `conflict`; terminal objectives read `approval_valid: n/a`, `needs_revalidation: false` | derived state cannot contradict immutability and needs no cross-file write |
| Approval hash payload | canonical JSON of `{"hypothesis": str, "non_scope": [str], "outcome_id": str, "scope": [str], "target": number}` — `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8, SHA-256 hex; `target` is the outcome's target at approval time, also stored as `approved_target` | typed keyed payload; no concatenation ambiguity; `outcome_id` closes the relink hole; terminal records keep `approved_target` as the definition they were judged under |
| Approval provenance | `approved_by` = `git config user.name` at the base root; empty → approval **refused** with a message; `approved_at` ISO-8601 UTC | a hash alone cannot say who agreed |
| Definition hash payload | canonical JSON (same rules) of `{"higher_is_better": bool, "how_measured": str, "target": number}` | flipping direction is a definition change |
| Outcome value record | `outcome_id` (must exist), `value` (JSON number), `observed_at` (ISO-8601 **timezone-aware** timestamp; a naive timestamp is refused; stored normalised to UTC `Z` form), `evidence` (non-empty string), `definition_hash` | provenance is what makes "observation, not causation" honest; normalising on input is what makes `observed_at` comparable |
| Gap | last value = the record with the greatest `observed_at`, ties broken by file order (last appended wins); gap ∈ `{at_or_better, above_target, below_target}` sign-aware by `higher_is_better`; a last value whose `definition_hash` ≠ current is reported `stale_definition: true` and its gap is `unevaluable` | one number, one direction, one flag |
| `revisit_when` grammar | exactly one of `{outcome: <id>, op: <"<" \| "<=" \| ">" \| ">=" \| "==">, value: number}` or `{assumption: <id>, status: <known \| assumed \| unknown>}`; `conflict` is not a valid target status | the smallest grammar that an LLM-free reader can evaluate; a conflicted assumption is always `unevaluable`, so allowing it as a target would be a condition that can never fire |
| Revisit result | `candidate` when the condition holds; `not_met` when it does not; `unevaluable` when the outcome has no value, the last value has a stale definition, the assumption is in `conflict`, or the reference does not resolve; never blocking | honest about unknowns |
| Task ↔ objective link | **sole source**: `work-docs/PLAN-<slug>.md` frontmatter `objective: <id>`, read by the boundary entrypoint from the slug; `task-preflight` takes no objective option; key absent or PLAN absent → no objective; key present → must be a non-empty string resolving on disk; null / empty / non-string / unparseable frontmatter → `link_invalid` | absent-case defined explicitly; present-but-invalid is never absent |
| Gate precedence | the objective check runs **after** every existing check; it can only turn an `advance` into `objective_gate`; halt_kind enum gains exactly one value; the gate-blocked event carries `display_ref`, `raw_link`, `parse_error` and `reason ∈ {link_invalid, missing, not_active, approval_invalid}`; the check keys on the **resolved** slug (marker-persisted when `--slug` is absent) | existing halts keep byte-identical precedence |
| Storage root | `.claude/intent.yaml`, `.claude/world/{assumptions,outcomes}.yaml`, `.claude/world/objectives/<id>.yaml` | churn machinery is keyed to `.claude/` and `work-docs/` **Superseded by SPEC-playbook-alignment (2026-09-16): the record is `work-docs/INTENT-<ID>.md` — frontmatter = these fields, `id` = the stem after `INTENT-`.** |
| Path ownership | all four patterns → `deliverable` via `_is_deliverable_path`, matching real `objectives/<id>.yaml` files; not in the churn prefix tuple; nothing gitignored | an unregistered live file classifies as `user` and finalize stashes it **Superseded by SPEC-playbook-alignment (2026-09-16): the record is `work-docs/INTENT-<ID>.md` — frontmatter = these fields, `id` = the stem after `INTENT-`.** |
| Wrapup staging | `hm wrapup_land` stages the four paths through `derive_deliverable_globs`, which reads the same `DELIVERABLE_STATE_PATHS` constant as `_DELIVERABLE_RE`; no prose change | wrapup staging is a typed manifest, not a `git add` line; one symbol adds a state path |
| Wrapup questions | the two writes (assumption observation, objective close) sit inside blocks opened by `<!-- @hm:answer-gated:assumption -->` / `<!-- @hm:answer-gated:objective-close -->` and closed by `<!-- /@hm:answer-gated -->`; inside each block, in order: an `AskUserQuestion`, a line beginning `If the answer is "yes":` followed by the write command, and a line beginning `Otherwise: write nothing` | same marker discipline as `@hm:drop-policy:user-confirmed`; the branch is part of the contract, not only the order |
| Root resolution — two roots | **Versioned files** (`work-docs/PLAN-*.md`, `.claude/intent.yaml`, `.claude/world/**`) are read and written in the **current checkout root** (`git rev-parse --show-toplevel` of the cwd — the task worktree when run there, main otherwise); **operational files** (gate-blocked events, markers, any ledger) use the **base root** resolved like `second_opinion_invoke`. Neither uses bare `Path.cwd()` | the earlier single rule would have made the boundary read main's PLAN from a worktree and advance with no link; the ledger rule stays because `codex_ledger`'s worktree rows were lost at `task-land` |
| Concurrency | last-writer-wins per file, atomic; **accepted loss**: two humans saving the same file within the same second lose one save; no cross-file **write** invariant exists because derived state replaced stored flags | human-paced deliverable files |
| Referential breakage | removing an outcome from `intent.yaml` or an assumption from `assumptions.yaml` is a legal edit; a reader that then meets a dangling `outcome_id`, `depends_on` entry or value record reports a validation error naming the reference; the boundary treats a linked objective that fails to load as `link_invalid`; `hm world status` lists the broken references and exits 0 | integrity is checked on read, never enforced on write |
| Active-objective cap | `max_active_objectives` default 1; breach warns and proceeds on the same call | interview lock-in R4 |
| Rendered surface | zero new slash commands; `hm world status`, `hm world assume`, `hm world outcome`, `hm world objective` are the CLI verbs (one dispatchable module `world`); `/hm:plan`, `/hm:wrapup`, `/hm:review` gain ≤ 25 lines each and `/hm:help` gains ≤ 3 lines, **per variant**; **one new skill** `intent-layer` (SKILL.md ≤ 120 lines) rendered to `.claude/skills/` and `.agents/skills/` | frozen baseline 427,369 + 362,326; the PLAN `surface_allowance` names all **four** commands in both variants; the skill body loads only when selected; its index line is the always-on cost the Non-Goals exception admits |
| Skill contract | `description` ≤ 200 chars naming the trigger situations (observed something, close / approve / drop an objective, record an outcome value, where are we); body lists the four verbs **with their full argument forms** and the answer-gated rule: run `hm world status` freely; before any write, ask with `AskUserQuestion` (or the target's equivalent) showing the exact arguments; on an affirmative answer run the write **once** with those arguments; on any other answer or no answer write nothing; no LLM-authored intent content. Selection by the model is not promised | discoverability without a rendered command: the operator does not remember verbs, the model does |
| Scope-drift lens | `/hm:review` reads `objective: <id>` from the PLAN in a main-loop step before Step 3.4; emits `scope_drift` findings judged by the `objective_scope_drift` rubric; severity **P2**; no gate; the judgment subject includes the rendered review surface of **every target** (`.claude/commands/hm/review.md`, `.agents/skills/hm-review/SKILL.md`) so a changed or removed lens on any target invalidates the verdict; re-judgment on unrelated edits to those files is an accepted cost | decision A: LLM judgment, Python stores |
| LLM boundary | the `world` module's four subcommand entrypoints must not import an LLM client | deterministic, free read path |
| Data versioning | `schema_version` required in every new file; missing → refused; major ≠ the build's known major (older **or** newer) → refused naming file and both versions | long-lived, hand-edited data |
| Withdrawal criterion | **Superseded 2026-09-20 by [[SPEC-withdrawal-criterion-window]].** The rule registered here — "after 10 wrapups with no `observed:` on any objective and no `candidate` revisit, remove the layer", measured by `hm world gap --json` → `withdrawal` since 2026-09-18 ([[SPEC-intent-layer-ops]]; was a skeleton comment only) — **can no longer fire**: `objectives_observed` is cumulative, so one objective ever closed with `observed:` pins `due` to false for the project's remaining life, and this repository crossed that line on 2026-09-18. The successor counts wrapups since the layer last did anything and carries the same no-reinterpretation force. This row is the record of what was registered, not of current behaviour | the 58.5% instrument, applied from day one; a kill switch that cannot fire is not one |

## ✅ Verification Criteria

| Scenario | Verification mode | Covering ACs |
|---|---|---|
| S1 | unit + property | AC-001, AC-002, AC-003 |
| S2 | unit | AC-004, AC-005 |
| S3 | unit | AC-006 |
| S4 | unit | AC-004 |
| S5 | property | AC-007 |
| S6 | property | AC-009 |
| S7 | differential | AC-012 |
| S8 | unit + render-grep | AC-015 |
| S9 | unit + render-grep | AC-011 |
| S10 | judgment | AC-017 |
| S11 | integration | AC-013 |
| S12 | unit | AC-014 |
| S13 | render-grep | AC-019 |
| (cross-cutting) | property + unit | AC-008 transitions · AC-010 cap · AC-016 schema_version · AC-018 latest value |

Test files bound to this SPEC (recorded here so the spec gate can attribute each file; the
`.machine.yaml` `test_ids` carry the node-level binding after `/hm:wrapup`):

| File | Covers |
|---|---|
| `tests/unit/test_baseline_fixtures_load.py` | PLAN P0 differential fixtures (oracles for AC-012, AC-019) |
| `tests/unit/test_intent_validate.py` | AC-001 intent half |
| `tests/unit/test_intent_skeleton.py` | AC-002 |
| `tests/unit/test_intent_update_invariance.py` | AC-003 |
| `tests/unit/test_world_assumptions.py` | AC-001 assumptions half, AC-004, AC-005, AC-006 |
| `tests/unit/test_world_outcomes.py` | AC-007, AC-018 |
| `tests/unit/test_world_objectives.py` | AC-001 objective half, AC-008, AC-009, AC-010, AC-015 (close half) |
| `tests/unit/test_world_status_and_revisit.py` | AC-011 (CLI half), AC-014 |
| `tests/unit/test_world_schema_version.py` | AC-016 |
| `tests/unit/test_autopilot_caps_objective_gate.py` | AC-012 |
| `tests/integration/test_intent_layer_lifecycle.py` | AC-013 |
| `tests/unit/test_render_intent_layer.py` | AC-011 render half, AC-015 render half, AC-019 |
| `tests/fixtures/objective_scope_drift/` | AC-017 judgment inputs |

### AC-001: an invalid file is refused with the offending field named
For intent: an unknown top-level key, a missing required key, a duplicate outcome id, a
non-numeric target, a missing outcome sub-field, an empty `mission` beside a non-empty
`outcomes`. For objectives: id ≠ file stem, empty `scope`, unknown `outcome_id`, a dangling
`depends_on` entry, `closed` with null `observed`. For assumptions: a duplicate id, a bad
envelope. Each fails naming that field; optional keys absent → valid.

### AC-002: make creates the typed skeleton and the strict loader accepts it as not_filled_in
Key set equals required ∪ optional; `mission` and `vision` are `""`, every list is `[]`,
`schema_version` is filled; the same loader that enforces AC-001 loads it without error and
reports `not_filled_in`; the file contains no LLM-generated text.

### AC-003: make --update never rewrites a hand-filled intent
Byte-identical after a second run, for arbitrary content including malformed YAML.

### AC-004: a contradicts observation yields conflict, retains every evidence tuple, and dependants derive the flag
After reload: status `conflict`; the evidence list equals `[E1, E2]` as full `(text,
observed_at, relation)` tuples; claim unchanged; the dependent active objective derives
`needs_revalidation: true`, the dependent closed one `false`; every objective file's bytes are
unchanged.

### AC-005: supersedes and confirms never produce conflict and lose no evidence
After reload: for `supersedes`, claim equals the new claim, history equals prior history plus
the old claim, evidence equals prior evidence plus the new tuple, status unchanged; for
`confirms`, claim and history unchanged, evidence equals prior plus the new tuple, status
unchanged.

### AC-006: resolve is the only exit from conflict
`resolve` to `known|assumed|unknown` sets status and claim, appends the prior claim to
history, retains all evidence, and the derived flag on dependants reads `false` afterwards;
`resolve` to `conflict`, or on a non-conflict assumption, is refused and writes nothing.

### AC-007: every malformed or unprovenanced outcome value is refused by name, and a good one carries the definition hash
Each of `observed_at` missing / non-ISO, `evidence` missing / empty, `value` non-numeric,
`outcome_id` unknown is refused naming that field with the file's bytes unchanged; a complete
record stores `definition_hash` equal to the hash the test computes from the fixture's
definition using the Constraints payload.

### AC-008: only legal objective transitions are accepted
`proposed→active` (requires `approval_valid`), `active→closed`, `proposed|active→dropped`,
`dropped→proposed` (the **reopen** transition, which clears the approval block). Every other
pair over the four states is refused. Every field edit of a `closed` record is refused; on a
`dropped` record every field edit is refused and reopen is the only accepted operation.

### AC-009: approval validity is derived from the canonical hash with provenance, and verification writes nothing
For every single edit to a hashed input, `approval_valid` reads `false`; for every edit to a
non-hashed field it reads `true`; the stored `state` and the file bytes are unchanged after
verification either way; `content_hash` equals the hash the test computes from the Constraints
payload; `approved_by` equals the fixture repo's `git config user.name`; approval with an empty
name is refused; a terminal objective reads `approval_valid: n/a` after the same edit.

### AC-010: exceeding max_active_objectives warns on the same call that activates
One call's result carries `activated: true` and a warning naming count and cap, and the
reloaded objective is `active`.

### AC-011: the revisit check has three non-blocking results, four unevaluable causes, prints its inputs, and is invoked per objective by /hm:plan
`candidate`, `not_met`, `unevaluable` each with `blocked: false`; `unevaluable` for each of: no
value, stale definition, assumption in `conflict`, unresolved reference; the CLI output for a
fixture objective carries its title, its condition and the last value used; the rendered
`/hm:plan` contains, before `## Step 1`, a mandated-call load (same call forms) of `intent.yaml` and
`assumptions.yaml`, an instruction to match the proposed work against each objective's
`rejected[]`, an explicit loop line (`For each matching objective:`) and, inside it, a
mandated-call invocation `hm world objective revisit <objective-id>` in the shipped call form for that target (`!uv run …` on Claude, `Bash("uv run …` on Codex; a bare `uv run` line is inert on both).

### AC-012: the boundary entrypoint reads the link from the current checkout, existing gates are byte-identical, and objective_gate only replaces advance
The entrypoint is invoked with a slug on fixture projects whose PLAN frontmatter is one of:
key absent, PLAN file absent, valid id (approved-active), null, empty string, non-string
(a number **and** a bare YAML date, which is not JSON-representable), unparseable frontmatter,
missing id, not-active id, approval-invalid id. Over every stage ×
every baseline input: the first three equal the captured pre-change baseline exactly; the rest
equal the baseline wherever it halts, and where it advances yield `objective_gate` with the
matching reason (`link_invalid` for the four malformed shapes), the `display_ref` in the
message, and a gate-blocked event carrying `reason`, typed `raw_link` and `display_ref`.
Additionally, on a fixture with a **task worktree whose PLAN links an unapproved objective
while the main checkout's PLAN has no link**, running from the worktree halts and running from
main advances. No test passes an objective object in.

### AC-013: the new paths survive the whole lifecycle as deliverables, including real objective files
With two real `objectives/<id>.yaml` files and the three fixed paths untracked on a clean
project: none ignored; `_path_owner` returns `deliverable` for each; byte-identical after `make
--update`; absent from any finalize stash; and present in the git index after the rendered
wrapup staging line is executed.

### AC-014: hm status prints the fixture's values on stdout, reaches no LLM, writes nothing
The CLI entrypoint's stdout, parsed, carries every S12 field with the fixture's values (mission
text; for the lower-is-better outcome recorded under a stale definition: last value, target,
observed-at, `gap: unevaluable`, `stale_definition: true`; for the higher-is-better outcome:
`gap: below_target`; `OBJ-1` with `approval_valid: false` and `needs_revalidation: true`; the
unknowns list; `log_location` in conflicts; `OBJ-3` in fired revisits); on the skeleton it
prints `not_filled_in`; the import graphs of **all four** verb entrypoints reach no LLM client;
no file under `.claude/` changes; exit 0.

### AC-015: close persists three fields, is immutable, and wrapup's two writes are answer-gated with an explicit no-branch
A good close persists `observed`, `note`, `closed_at` and state `closed`; a close missing either
field or with an invalid `observed` is refused by name and leaves the bytes unchanged; a second
close is refused; the rendered `/hm:wrapup` contains both `@hm:answer-gated` blocks, each holding
in order an `AskUserQuestion`, an `If the answer is "yes":` line followed by the write command
(`hm world assume` / `hm world objective close`), and an `Otherwise: write nothing` line, all before the block's closing marker.

### AC-016: a missing or foreign-major schema_version is refused naming the file and both versions
For each of the four file kinds: missing version, older major, newer major → refused; the error
names the path, the found version and the known version.

### AC-017: /hm:review emits scope_drift findings that cite the objective and the evidence, judged against the rendered lens
Judged by the `objective_scope_drift` rubric on output the judgment-reviewer produces **at
judgment time** by running the currently rendered review lens **of each target** over four
fixture (PLAN, objective) input pairs — in scope; adds work outside scope that non-scope does
not name; adds work inside non-scope; omits the hypothesis's subject. The subject is the fixture
inputs **plus `.claude/commands/hm/review.md` plus `.agents/skills/hm-review/SKILL.md`**, so a
changed or removed lens on either target invalidates the verdict.

### AC-018: the latest value is selected by observed_at, not by append order, and staleness follows the definition
For any sequence of value records for one outcome in any append order, with `observed_at`
supplied as any timezone-aware ISO-8601 form (`Z`, `+00:00`, non-zero offsets, fractional
seconds) that the recorder normalises to UTC: the reported last value is the one with the
greatest normalised instant, ties resolved to the later index; a later-appended
record with an earlier `observed_at` never becomes last; `stale_definition` is true iff the
selected record's `definition_hash` differs from the current definition's, including when only
`higher_is_better` changed.

### AC-019: the intent-layer skill renders on every target with the trigger description and the answer-gated rule
The rendered `SKILL.md` exists under `.claude/skills/intent-layer/` for every target and under
`.agents/skills/intent-layer/` when `codex` is a target; its frontmatter `description` contains
each trigger situation and is ≤ 200 chars; its body contains each verb's full argument form
(`hm world assume observe <id> --relation <confirms|supersedes|contradicts> --text --observed-at`,
`hm world assume resolve <id> --status --claim`, `hm world outcome record <id> --value --observed-at
--evidence`, `hm world objective <approve|activate|drop|reopen> <id>`, `hm world objective close <id>
--observed <met|missed|no_data> --note`), and in order: an `AskUserQuestion` mention, the
phrase `showing the exact arguments`, the word `affirmative`, `run the write once`, and
`on any other answer or no answer` followed by `write nothing`;
`/hm:help` lists it; no file under `.claude/commands/hm/` is added.

## ❓ Open Questions

1. **Objective record vs Second Brain `decision` note.** Whether wrapup Step 5.6 promotes a
   closed objective to a `decision` note or leaves it in place is a PLAN ADR.
2. **Which always-on bytes pay for the gate prose.** Three commands grow by ≤ 25 lines each; the
   `CLAUDE.md`-as-table-of-contents rewrite is a separate task.
3. **Two-root test design** (codex rev-6 #4, deferred to PLAN as test design). AC-012's
   two-checkout fixture pins only the PLAN link. A PLAN test-design ADR should extend it so the
   same objective id is approval-valid on main and approval-invalid in the worktree (payload or
   target edited there), asserting the worktree halts with `approval_invalid` and the event
   lands in the base root only — which is what distinguishes "PLAN from current checkout" from
   "everything from current checkout".
4. **Resolver structure and CLI option spelling** are PLAN ADRs (codex rev-6 verdict).

## 🔍 Refinement Decisions

- **Revision 6.1 corrections** (plan stage; plan-validator P-02/03/04/06/07/10/11 and codex
  plan cx-2/3/5/7): verb strings → `hm world …` (AC-011 argv, AC-015 `cmd`, AC-019 forms,
  Rendered-surface and LLM-boundary rows); AC-013 finalize clause → round-trip byte identity;
  `scope_drift` → P2 (S10, lens row, rubric `finding_not_gate`); AC-011 render predicate →
  shipped call forms; gate event → `display_ref`; wrapup staging → `derive_deliverable_globs`;
  plan addition → `Step 0.5`. Decisions are recorded in PLAN ADR-001/004/007/012.
- **Revision 6 review closure** (codex rev-6, 5 × P2): #1 → S5 timestamp wording matches the
  value-record row; #2 → AC-019 adds the `close` argument form and the ordered branch phrases;
  #3 → S7 defines the JSON encoding of non-JSON YAML link values and AC-012 adds the date
  fixture; #4 → Open Question 3; #5 verdict → the three named items are closed above, the rest
  are Open Questions 3–4. **SPEC revisions end here; `/hm:plan` follows.**
- **R11 — revision 6, two roots.** Versioned files resolve to the current checkout; operational
  files to the base root. Closes codex rev-5 #1, which would otherwise have let every task
  worktree bypass the gate.
- **Revision 6 traceability** (codex rev-5 finding → disposition): #1 → Root-resolution row /
  S7 / AC-012 two-checkout fixture; #2 → Outcomes and S13 restated as "available and listed",
  Non-Goals entry; #3 → Skill-contract row / AC-019 argument forms and literal phrases; #4 →
  Non-Goals exception + `/hm:help` in the allowance; #5 → AC-017 subject adds the codex review
  skill; #6 → re-judgment cost accepted in S10 and the lens row; #7 → Assumption-record row
  typed; #8 → value record accepts timezone-aware input normalised to UTC, AC-018 domain
  restated; #9 → AC-011 explicit loop line; #10 → rubric `no_drift_no_finding` action reworded;
  #11 → typed `raw_link` + `display_ref` in S7 / AC-012; #12 → Referential-breakage row,
  Concurrency row says "write invariant".
- **R10 — revision 5, discoverability.** The four verbs get one **skill**, not a slash command.
  A command costs ~19 K rendered chars across both variants and is only found if its name is
  remembered; a skill is found by the model from a prose request, its body loads only when
  triggered, and it dual-renders to `.agents/skills/` for codex. The rule that nothing is written
  without an affirmative answer lives in the skill body and in the wrapup blocks — the same
  contract in both places.
- **Revision 5 traceability** (codex rev-4 finding → disposition): #1 → S7 / link row / AC-012
  entrypoint form; #2 → Intent + Outcomes narrowed to the approval payload of non-terminal
  objectives; #3 → AC-017 subject includes the rendered `review.md`, output generated at
  judgment time; #4 → wrapup-questions row / AC-015 explicit branch; #5 → AC-008 reopen carved
  out of dropped immutability; #6 → skeleton-validity row / S1 / AC-002 same loader; #7 → AC-014
  prose now says `unevaluable` for the stale value; #8 → required / nullable / envelope rows /
  AC-001 extended; #9 → grammar row drops `conflict`; #10 → AC-018; #11 → AC-011 per-objective
  invocation and printed inputs; #12 → S10 four fixtures and omission evidence, rubric updated;
  #13 → AC-014 all four entrypoints.
- **R1–R6** stand as recorded in revision 3.
- **R7 — revision 4, decision A.** The mechanical guarantee is narrowed to the objective record;
  work drift is an `/hm:review` judgment lens (S10, AC-017, rubric `objective_scope_drift`).
  Rationale: binding PLAN scope into the hash would force re-approval on every PLAN edit and
  contradict S7's "approved scope does not re-ask"; CLAUDE.md's rule is LLM judgment over
  rule-matching, with Python owning storage, hashing and gating.
- **R8 — derived state.** `approval_valid` and `needs_revalidation` are computed by readers and
  never written. Closes codex rev-3 #3, #4, #5, #11 in one move: no terminal-state
  contradiction, no cross-file write, no question of who persists `active→proposed` (nobody —
  the transition no longer exists).
- **R9 — link contract.** PLAN frontmatter is the sole source; absent ≠ dangling; dangling,
  not-active and invalid all halt only where the baseline would advance. Closes #1 and #10.
- **Revision 4 traceability** (codex rev-3 finding → disposition): #1 → R9 / AC-012; #2 → R7 /
  S10 / AC-017; #3 #4 #5 #11 → R8 / AC-004 / AC-008 / AC-009; #6 → S3 / AC-006; #7 → grammar
  row / AC-011; #8 → the two payload rows / AC-007 / AC-009; #9 → value and gap rows; #10 →
  precedence row / AC-012; #12 → AC-010; #13 → AC-004 / AC-005 full tuples; #14 → AC-014 stdout
  + entrypoint graph; #15 → AC-011 three results + non-comment invocation; #16 → AC-015
  persisted fields + answer-gated markers; #17 → provenance row / AC-007 / AC-009; #18 → AC-013
  real files + index; #19 → required/optional rows / AC-001 / AC-016.
