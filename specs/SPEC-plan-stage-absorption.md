---
type: spec
task_slug: plan-stage-absorption
status: approved
created: 2026-09-20
tags: [harness-maker, spec, python, jinja2, stage-removal, migration, pipeline]
tier: 1
test_framework: pytest
research_doc: "[[RESEARCH-ai-native-sdlc-vs-intent-world]]"
interview_rounds: 3
summary: "Delete /hm:plan as a stage; its DRI content stays in SPEC, its IC content moves to /hm:execute Step 0, and the PLAN document survives"
---

# SPEC — Plan stage absorption: the stage goes, the document stays

## 🎯 Intent

`/hm:plan` asks the DRI a second interview about work a SPEC has already scoped. Measured on
this repository across the 21 task slugs that carry both an interviewed SPEC and a PLAN, the two
stages cost **9.70 interview rounds per task** (SPEC 4.65 + PLAN 5.05); a merged single-stage
interview costs **6.55** — a 32 % reduction, and the estimate is robust because three different
absorption models (full-overlap lower bound, point estimate, no-overlap upper bound) all land
between 6.55 and 6.65. The reason is ownership, not effort: of 194 classified PLAN interview
entries, 52 % are DRI questions the SPEC interview **already asks** (`contract` 46 entries map
onto SPEC's five `irreversible_decisions` categories; `scope` 42 onto In-Scope Scenarios and
Non-Goals; `testing` 11 onto Verification Criteria and the oracle axis), and 21 % are IC
questions that should never have reached a human at all.

What disappears is the **stage, its interview and its auto-advance gate**. The PLAN *document*
does not: it is INV-class state, the artifact that survives a context window on a long task, and
`/hm:loop` depends on it. `/hm:execute` Step 0 becomes its author.

## 🌅 Outcomes

After this change:

- A DRI starting a task answers **one** interview, in `/hm:spec`, and never sees a second
  architectural interview before implementation begins.
- `/hm:execute` produces the PLAN document itself — phases, file list, order, risks, exit
  criteria — with no human gate between specification and implementation.
- Every existing consumer of the PLAN document (`execute`, `wrapup`, `review`, `verify`,
  `loop`) keeps reading the same artifact with the same frontmatter contract; none of them
  learns that the producer changed.
- An existing project whose `harness.yaml` names `plan` in `autonomy.pipeline` keeps loading,
  is migrated once, and is told once.
- SPEC quality still receives an independent LLM critique — relocated, conditional, and
  advisory rather than blocking.

## 📋 In-Scope Scenarios

### S1: The plan stage renders nowhere

**Given** a harness rendered for any combination of preset, `dev_mode` and `targets`
**When** the render completes
**Then** no `plan` stage command, skill or stage-trigger artifact exists for any target
**And** no stub or deprecation shim is rendered in its place

### S2: `/hm:execute` produces the SPEC-need fields, preserving what is already there

**Given** `/hm:execute` Step 0 is about to write `work-docs/PLAN-{slug}.md`
**When** the PLAN frontmatter already carries a `spec_need_verdict`
**Then** the existing value is preserved rather than overwritten
**And** when no value is present, Step 0 judges one and writes both
`spec_need_verdict` and `spec_need_target`
**And** after the write the field's presence is asserted, retried once, then surfaced and
stopped — never left absent

### S3: A legacy harness.yaml naming `plan` still loads

**Given** a `harness.yaml` written before this change, whose `autonomy.pipeline` contains `plan`
**When** it is loaded
**Then** `plan` is dropped from the pipeline and the load succeeds
**And** exactly one advisory is emitted for that migration
**And** a second load of the migrated file emits none

### S4: A loop iteration plans without the plan stage

**Given** `/hm:loop` is running an iteration against a master `work-docs/PLAN-{slug}.md`
**When** `/hm:execute` Step 0 runs inside that iteration
**Then** it writes `work-docs/PLAN-{slug}-iter{N}.md` carrying `derived_from`, `iter`, `phase`
and `loop_mode` in its frontmatter
**And** a decision that would require an ADR halts the iteration rather than being recorded
as a local per-iter decision

### S5: `spec-validator` critiques the SPEC without blocking it

**Given** a SPEC whose ACs declare or imply an irreversible decision
**When** `/hm:spec` reaches the validation point
**Then** `spec-validator` is dispatched exactly once, with no re-validation pass
**And** the SPEC's approval state is unchanged by the verdict it returns
**And** a SPEC that took the Step 0 skip path and declares no irreversible decision is not
dispatched at all

### S6: The removal is announced rather than discovered

**Given** a user upgrading to the release that removes the stage
**When** they read the CHANGELOG or run `/hm:help`
**Then** a BREAKING entry names the removal and where the content went
**And** `/hm:help` no longer lists `plan` among the stages

### S7: Every PLAN reader still reads the PLAN

**Given** the set of modules and templates that read PLAN frontmatter or PLAN sections
**When** that set is discovered rather than enumerated by hand
**Then** every member resolves the same required keys against a PLAN written by
`/hm:execute` Step 0 as against one written by the deleted stage

### S8: The measurement survives the change

**Given** a SPEC produced by the merged interview
**When** its frontmatter is read
**Then** it carries `interview_rounds` as an integer, continuing the series the 140 existing
PLAN frontmatters started

## 🚫 Non-Goals

- **`src/harness_maker/spec_machine.py`, `io_utils.py` and `world.py` are not touched.** A
  concurrent session owns them; `templates/` is this task's contract boundary and those three
  files are the other side of it.
- **`verify.md.j2` Check 6 is not changed.** Its absent-key `PASS (N-A)` path stays. See the
  accepted limitation under Constraints.
- **`/hm:loop` is not re-pointed at SPECs.** It keeps the PLAN-document axis; only the stage
  name list, the `--per-iter-stages` example and the per-iter PLAN producer move.
- **`/hm:verify` is not removed** — it is state scaffolding, not behaviour scaffolding
  (`PLAN-harness-diet` ADR-003).
- **The review apparatus is out of scope** (`PLAN-harness-diet` ADR-004): reviewer lenses,
  consensus, the auto-fix loop and the cross-model second opinion are untouched.
- **No Jira/Linear or external-ticket field** is introduced.
- **The `≤ 7 merged rounds` figure is not an acceptance criterion.** It is a post-ship outcome
  measure; see Constraints.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo-wide; `ruff` + `mypy --strict` gate alongside |
| Language | Python 3.12+, no Bash | CLAUDE.md fixed technical decision |
| Contract boundary | `src/harness_maker/templates/` is this task's; `spec_machine.py` / `io_utils.py` / `world.py` are the concurrent session's | A parallel session lands those three; a collision costs this side |
| Snapshot re-capture | `tests/structural/test_autopilot_gate_render.py` goldens are re-captured **with an appended entry naming the date, the task and what moved and why** | Re-capturing without a reason is the exact failure that file exists to prevent |
| Reader discovery | The PLAN-reader set is discovered by import-graph / AST traversal, never hand-listed | `new-marker-content-field-must-update-every-reader` (count:3): all three hand-made lists were wrong |
| Render coverage | Render assertions quantify over preset × `dev_mode` × `targets`, not one arm | A single-arm golden proves one combination and is silent about the rest |
| Migration shape | Enum removal and the one-shot pipeline drop ship **atomically** in one release | `PLAN-harness-diet` ADR-012; a schema removal ahead of its migration breaks every existing load |
| Announcement | CHANGELOG BREAKING + `/hm:help`, no stub command | `PLAN-harness-diet` ADR-009 shipped this exact form |
| Accepted limitation | On a path where `/hm:execute` never ran, `verify` Check 6 still auto-PASSes on the absent key | Deliberate (Round 2, Q5): if execute did not run, nothing was implemented, so the residual risk is small and the alternative widens the blast radius to Check 6 and `spec_need`'s CLI contract |
| Outcome measure, not AC | "Merged DRI rounds ≤ 7" is registered as an intent-layer outcome | Observation data is zero at ship time; as an AC it would hold the SPEC open across five later tasks and could trigger a land hold |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | The `/hm:plan` slash command is removed from all three targets with no stub | public API/CLI contract | It is a user-facing surface of a published plugin; restoring it costs a release and a second announcement |
| IRR-002 | `AtomicStage.PLAN` is removed from the enum and `plan` is dropped once from `autonomy.pipeline` at load | data migration | The migration rewrites user configuration in place; the original pipeline value is not recoverable afterwards |
| IRR-003 | The producer of `spec_need_verdict` / `spec_need_target` moves from `/hm:plan` to `/hm:execute` Step 0 | schema/file format/storage layout | `verify` Check 6 reads these fields and its absent-key path is a silent PASS, so two units implementing this differently kill the gate without any error |
| IRR-004 | A new public CLI verb `hm spec_need frontmatter-upsert` owns the presence-preserving PLAN frontmatter write | public API/CLI contract | Rendered stages call it by name, so its name and signature are a contract. AC-002's property oracle quantifies over arbitrary prior frontmatter states, which needs an execution surface a prose recipe cannot give — the shape that shipped four silent-skip bugs. Raised during `/hm:execute` (`source: execute`), accepted by the DRI, SPEC re-approved |

IRR-004 was raised during implementation, not in the interview — appending it invalidated the
approval stamp by design, and the DRI re-approved.

`plan-validator` → `spec-validator` renaming and the addition of `interview_rounds` to SPEC
frontmatter were considered and **dropped** from this list (Round 3): a name can be changed
back and an additive field can be removed, so neither justifies a land hold.

## ✅ Verification Criteria

| Scenario | Verification mode | Acceptance criterion |
|---|---|---|
| S1 | unit | AC-001 |
| S2 | unit | AC-002 |
| S3 | unit | AC-004 |
| S4 | unit | AC-005, AC-010 |
| S5 | unit | AC-007, AC-008 |
| S6 | unit | AC-006 |
| S7 | unit (structural) | AC-003 |
| S8 | unit | AC-009 |

### AC-001: the plan stage renders on no target in any arm

For every combination of preset, `dev_mode` and `targets` the renderer accepts, the rendered
artifact set contains no `plan` stage command, skill or stage-trigger file, and no stub.

### AC-002: execute writes the SPEC-need fields and preserves a pre-existing verdict

Writing the SPEC-need fields into PLAN frontmatter is presence-preserving and
presence-guaranteeing: an existing `spec_need_verdict` survives the write unchanged, an absent
one is filled, and the field is present afterwards in both cases.

Owned by `hm spec_need frontmatter-upsert` (IRR-004) and bound to
`tests/unit/test_spec_need_frontmatter_upsert.py`. The verb exists so this AC's property oracle
has an execution surface; `execute.md.j2` calls it rather than describing it.

### AC-003: every discovered PLAN reader resolves against an execute-written PLAN

The set of PLAN-frontmatter readers is obtained by traversing the import graph and template
set rather than from a list, and every discovered member resolves its required keys against a
PLAN produced by `/hm:execute` Step 0.

Bound to `tests/structural/test_plan_reader_baseline.py`. **Mechanism note (recorded during
implementation):** no Python module reads PLAN frontmatter — verified by grep over
`src/harness_maker/*.py`, where every `task_slug` hit belongs to the autopilot marker, not the
PLAN. The reader set is entirely Jinja templates, so the traversal is over the template corpus
rather than the Python import graph. The oracle's independence is unchanged — readers and the
key space are both *discovered*, never listed — but the SPEC's original wording named the wrong
corpus.

### AC-004: a legacy pipeline naming plan loads, migrates once, and says so once

Loading a `harness.yaml` whose `autonomy.pipeline` contains `plan` succeeds with `plan`
dropped and exactly one advisory; loading the migrated result emits none.

**Every** reader that turns a raw pipeline into `AtomicStage` filters retired names first —
discovered by AST walk, not listed. Bound to `tests/unit/test_atomic_stage_plan_retirement.py`
and `tests/structural/test_retired_stage_single_reader.py`. Found during implementation:
`hooks/autopilot_autoarm.py` parses the pipeline itself and swallows a bad one as a **silent
no-op by design**, so the migration in `interview._parse_autonomy` alone would have stopped
autopilot arming for every existing user with no diagnostic.

Bound to `tests/unit/test_atomic_stage_plan_retirement.py`.

### AC-005: the per-iter PLAN keeps its frontmatter contract under a new producer

A per-iter PLAN written by `/hm:execute` Step 0 in loop mode carries `derived_from`, `iter`,
`phase` and `loop_mode`.

### AC-006: the removal is announced and leaves no stub

The CHANGELOG carries a BREAKING entry naming the `/hm:plan` removal, the rendered `/hm:help`
does not list `plan`, and no `plan` command file is rendered.

### AC-007: spec-validator is single-pass, conditional, and cannot move approval

`spec-validator` is dispatched at most once per `/hm:spec` run, is not dispatched for a SPEC
that took the Step 0 skip path and declares no irreversible decision, and the SPEC's approval
state is invariant under its verdict.

Bound to `tests/render/test_spec_validator_dispatch.py`.

### AC-008: every spec-validator dispatch is recorded

Each `spec-validator` dispatch emits exactly one `stage-agents.jsonl` row carrying its
verdict, so its discrimination is measurable from the first run.

### AC-009: the merged interview records its round count on the SPEC

A SPEC written by `/hm:spec` carries an integer `interview_rounds` in its frontmatter.

### AC-010: the PLAN document keeps its required per-phase fields

Every phase in a PLAN written by `/hm:execute` Step 0 carries `depends_on`,
`parallel_group`, `merge_hazards`, scope, exit criterion, risk and rollback point.

## ❓ Open Questions

None. Every question raised across the three interview rounds was resolved; the two deliberate
residuals (the Check 6 absent-key path, and the round-count figure being an outcome rather
than an AC) are recorded as accepted limitations under Constraints, not as open questions.

## 🔍 Refinement Decisions

- **Round 1** — Locked the removal shape (hard removal, no stub, CHANGELOG BREAKING +
  `/hm:help`, per `PLAN-harness-diet` ADR-009); named `/hm:execute` Step 0 as the new producer
  of `spec_need_verdict` / `spec_need_target` with a pre-existence check; relocated
  `plan-validator` to SPEC as a conditional `spec-validator` rather than removing it; kept
  `/hm:loop` on the PLAN-document axis.
- **Round 2** — Scoped the absent-case fix to the producer side only: `/hm:execute` checks for
  a pre-existing value before writing and asserts presence after, while `verify` Check 6 keeps
  its `PASS (N-A)` path, accepting that an execute-less path is ungated. Assigned the per-iter
  PLAN to `/hm:execute` Step 0 with its frontmatter contract unchanged. Made `spec-validator`
  never-block, because 0 APPROVED in 54 plan-validator runs leaves its discrimination unproven
  and an unproven gate should not hold a release. Chose enum removal plus a one-shot silent
  drop in `answers_from_harness_yaml` over a deprecated-but-present enum member.
  Corrected a brief premise in the process: `/hm:loop` iterates a loop-spec YAML, not a master
  PLAN — the master-PLAN iteration is the deleted stage's own loop-mode branch, so loop's
  migration surface is three sites, not the nine PLAN references in `loop.md.j2`.
- **Round 3** — Held `irreversible_decisions` to the three entries that are genuinely
  irreversible, dropping the agent rename and the additive frontmatter field so that a land
  hold keeps its meaning. Scoped `spec-validator` fully into this task — agent, trigger
  condition and measurement record — on the grounds that deleting `plan-validator` while
  leaving its replacement unbuilt would ship an absorption with no critique at all. Registered
  the measured round reduction as an intent-layer outcome rather than an AC, since observation
  data is zero at ship time.
