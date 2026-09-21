---
type: spec
task_slug: observed-harness-gaps-salvage
status: approved
created: 2026-09-19
tier: 2
tags: [harness-maker, spec, python, memory-retrieval, escalation, telemetry, salvage]
test_framework: pytest
research_doc: "[[RESEARCH-observed-harness-gaps-salvage]]"
summary: "Salvage observed-harness-gaps onto main; backlog warning moves to the wrapup main loop"
---

> Vocabulary and storage layout are superseded by [[SPEC-intent-vocabulary-rename]];
> owners shape and advisory approval guidance by [[SPEC-intent-owners-role-map]].
> This historical SPEC and its machine companion retain their original ACs and test bindings
> as compatibility evidence. Unchanged behavioral guarantees still apply.


# SPEC — Observed harness-maker gaps, salvaged onto main (memory loop + contract mismatches)

> **Provenance.** This SPEC is derived from `SPEC-observed-harness-gaps` (2026-08-14, in the
> abandoned `.worktrees/observed-harness-gaps/`), which reached `executed` but was never reviewed
> or landed. Re-verified against main `555ca933` on 2026-09-19
> ([[RESEARCH-observed-harness-gaps-salvage]]): every defect is still present. Changes from the
> source SPEC: **S2 / AC-003 are rewritten** (the warning's placement), **S8 / AC-012 are new**
> (the oldest-date field), and the counts below are refreshed. Everything else carries over.

## 🎯 Intent

An external session audited harness-maker and reported seven defects. Verification against
source confirmed five, narrowed two, and refuted one. Three of the confirmed five — the
unread proposal backlog, the recall miss at prevention time, and the body-less warm tier in
`execute` — are not independent bugs but **three severed links in one loop**: knowledge is
recorded, recurrence is detected, a recommendation is written, and nothing ever reads any of
it back at the moment it would prevent the recurrence. The measured cost, re-counted
2026-09-19: **27** unread proposals, the oldest from 2026-05-17 (was 16 when the source SPEC was
written), and a retrieval run whose failure-shaped topic ("repair round broke something new while
the suite stayed green") returned `(no entries matched)` although
`fix-introduced-defect-passes-all-gates` (count:13) paraphrases it.

The remaining two in scope (`wall_time_ms`, `--barrier-index`) are the same defect class as
each other: a rendered template states a field contract its Python entry point does not
honour. `wall_time_ms` additionally **blocks the review telemetry stream outright**, which is
why it is bundled here rather than deferred — without it there is no data with which to
measure how often the review-consensus gap (finding 5, out of scope) actually fires.

## 🌅 Outcomes

Observable end-state that does not exist today:

- A maintainer can run one command and see the open proposal backlog, and `/hm:wrapup` says
  so unprompted once the backlog reaches five, naming the open count **and the oldest open
  proposal's date**. The line is produced by wrapup's **main loop**, not the delegated
  Steps 1–5.6, so it actually reaches the person running wrapup.
- A stage that retrieves memory receives the highest-recurrence failure entries **even when
  they share no vocabulary with the topic**, so a `count:13` entry can no longer be silently
  dropped before the reranking turn ever sees it.
- `/hm:execute` — the stage that writes code, and therefore the stage at which a failure
  instance is actually created — receives failure entry **bodies**, not a slug list.
- `hm review_telemetry emit` accepts a record that omits `wall_time_ms`, so the first emit of
  a review round succeeds and the review telemetry stream starts producing rows.
- `hm stage_agent_ledger emit --barrier-index` is documented as an integer everywhere it is
  rendered, so the plan stage's first emit is not rejected on a type error.

## 📋 In-Scope Scenarios

### S1: The proposal backlog gets a reader
**Given** `.claude/memory/pending-proposals.md` contains proposals, some resolved and some not
**When** the maintainer runs `hm proposals list --open`
**Then** every unresolved proposal is listed, one per row, and the command exits 0
**And** `--triaged` lists exactly the complement — the resolved ones — with no proposal
appearing in both and none missing from both.

### S2: wrapup surfaces a backlog it can no longer ignore — from the main loop
**Given** the open-proposal count is 5 or more
**When** `/hm:wrapup` reaches its main-loop `Steps 6 → 7.6` section (the part that is **not**
delegated to `stage-delegate`)
**Then** the main loop runs the proposals CLI itself and prints one prominent line naming the
open count and the oldest open proposal's date
**And** below 5 it prints no such line
**And** when the CLI is missing, exits non-zero, or prints a non-integer count, it prints ONE line
naming the failure and continues — never halts, never treats an error string as a count.

> **Why the placement is part of the contract.** Steps 1–5.6 run inside `stage-delegate`, whose
> prose is not relayed; `WrapupReceipt` carries no warning field. A warning printed there is
> write-only — the exact defect this task exists to remove. The source SPEC's "runs its
> escalation step" placed it there.

### S3: A high-recurrence failure survives zero lexical overlap
**Given** a memory corpus containing a `count:13` failure entry whose heading and body share
no normalized token with the topic
**When** a stage runs `hm memory_retrieve --topic "<unrelated topic>" --k 6`
**Then** that entry appears in the emitted `<memory_candidates>` fence
**And** it is labelled as a high-recurrence inclusion so the reranking turn can distinguish it
from a lexical hit.

### S4: The floor costs the lexical result nothing
**Given** any corpus, topic and `k`
**When** retrieval runs with the count floor enabled and again with it disabled
**Then** every entry the floor-disabled run returned is still present in the floor-enabled run
— the floor is additive to `k`, never a carve-out of it.

### S5: execute receives bodies, not slugs
**Given** the rendered `/hm:execute` command
**When** its Session Context Loading section is read
**Then** it invokes `hm memory_retrieve`, as the research / spec / plan / wrapup stages already do
**And** it no longer instructs a `failures.md` head-skim plus `rg -F "[fail:"` slug scan.

### S6: The first telemetry emit of a round succeeds
**Given** a review round that has not measured wall time
**When** a record omitting `wall_time_ms` is piped to `hm review_telemetry emit`
**Then** the record validates and one line is appended to today's JSONL
**And** a record that *does* carry an integer `wall_time_ms` still validates unchanged.

### S7: The ledger's segment argument is documented as an integer
**Given** the rendered `/hm:plan` stage
**When** its `stage_agent_ledger emit` example is read
**Then** the `--barrier-index` placeholder states that the value is an integer, matching the
`type=int` the CLI enforces and the guidance `/hm:execute` already carries.

### S8: the oldest open proposal's date is machine-reported
**Given** a backlog whose open proposals carry a trailing `(YYYY-MM-DD)` in their heading
**When** the proposals CLI is asked for the backlog summary
**Then** it reports the earliest date among **open** proposals only (resolved batches never count)
**And** it reports no date — not an error — when the file is absent or no open proposal is dated.

## 🚫 Non-Goals

- **Finding 4 (pytest-only SPEC binding).** Confirmed, but it needs a new `harness.yaml`
  key, a schema version bump and an `answers_from_harness_yaml` migration. Separate project.
- **Finding 5 (cross-tier consensus).** Confirmed, but the fix is a new counter feeding
  `human_review_needed`, not a change here — and its frequency cannot be measured until S6
  unblocks the telemetry stream. Sequenced after this work, not merged into it.
- **Finding 6 (execute Step 5).** **Refuted.** `~/strange_chess`, the project where it was
  observed, renders `harness_maker_version: 0.51.1` and its `.claude/commands/hm/execute.md:529`
  already reads "Worktree finalize (ephemeral `/hm:loop` worktrees ONLY)" with the `hm/*` SKIP
  branch. No defect remains. No work item.
- **The task-kind second query** (finding 2's second half). Deliberately excluded: measure
  whether the count floor alone closes the recall gap before adding a second retrieval pass.
  Recorded as an Open Question for a later cycle.
- Embeddings, TF-IDF or any non-lexical ranking. Bound by `PLAN-memory-retrieve-lexical-recall`
  ADR-001.
- Bridging severity tiers in `consensus-arbiter`. Explicitly forbidden by that agent's own
  contract; not revisited.
- Retroactively rewriting the 27 existing proposals, or auto-resolving any of them. Triage is
  separate work; this task only makes the backlog visible.
- **The default `memory_retrieve --byte-cap` starvation.** Measured 2026-09-19: at the default
  10240, `--k 6 --pre-k 30` emits **3** entries (40960 → 9; 200000 → 30). A budget decision that
  changes every stage's context at once; recorded as a pending proposal instead (user decision,
  2026-09-19).
- **Disposal of `.worktrees/observed-harness-gaps` / `hm/observed-harness-gaps`.** Another
  session's state; decided by the user at wrapup, never by this task's code.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | CLAUDE.md locked technical decision — Python only, no Bash |
| Language / runtime | Python 3.12+, `uv` | CLAUDE.md locked technical decision |
| Ranking method | Lexical + deterministic only | `PLAN-memory-retrieve-lexical-recall` ADR-001 rejects embeddings and defers TF-IDF; a count floor and a fence label are both deterministic and honour it |
| Floor / `k` relation | Additive to `k`, never carved out | RESEARCH pitfall 1 — a carve-out trades a recall miss for a precision loss, which is not a net win |
| `wall_time_ms` resolution | Schema becomes optional | The same doc paragraph forbids interpolating it (determinism leakage) and requires it; the schema is the side that must yield |
| Back-compat | Existing valid telemetry rows stay valid | Optionality must be a superset, not a replacement — prior rows are already on disk |
| Absent-case | Every new field/flag states its behaviour when absent | CLAUDE.md, `count:8` most-recurring failure class |
| File writes | `atomic_write` (tempfile + `os.replace`) | CLAUDE.md implementation pattern; plain `open(path,"w")` is banned |
| Proposal file format | Read-only consumer | The consumer must not rewrite `pending-proposals.md`; wrapup remains its sole writer |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name |
|---|---|---|
| S1 | unit | `test_proposals_list_open_lists_unresolved` |
| S1 | unit | `test_proposals_open_triaged_partition` |
| S2 | unit (render-grep) | `test_wrapup_renders_backlog_warning_threshold` |
| S2 | unit (render-grep) | `test_wrapup_backlog_check_runs_in_the_main_loop` |
| S3 | unit | `test_count_floor_admits_zero_overlap_entry` |
| S3 | unit | `test_count_floor_entries_are_labelled` |
| S4 | unit (property) | `test_count_floor_is_additive_to_k` |
| S5 | unit (render-grep) | `test_execute_warm_tier_uses_memory_retrieve` |
| S6 | unit | `test_emit_accepts_record_without_wall_time_ms` |
| S6 | unit (property) | `test_previously_valid_records_still_validate` |
| S6 | unit (render-grep) | `test_review_doc_matches_wall_time_optionality` |
| S7 | unit (render-grep) | `test_plan_barrier_index_documented_as_int` |
| S8 | unit (parametric) | `test_ac_012_oldest_open_date` |

**Test files** (the modules the rows above live in):
`tests/unit/test_proposals.py`, `tests/unit/test_proposals_real_backlog.py`,
`tests/unit/test_render_wrapup_backlog_warning.py`, `tests/integration/test_wrapup_backlog_degrade.py`,
`tests/unit/test_memory_retrieve_count_floor.py`, `tests/integration/test_memory_retrieve_cli.py`,
`tests/unit/test_render_execute_warm_tier.py`, `tests/unit/test_review_telemetry_optional_wall_time.py`,
`tests/unit/test_render_telemetry_contract_docs.py`.

### AC-001: proposals list --open lists every unresolved proposal
Running the CLI against a fixture backlog yields exactly the unresolved proposals, one row
each, exit 0. Oracle: a hand-authored fixture whose open/resolved split is fixed in the
fixture file itself, not derived from the parser under test.

### AC-002: --open and --triaged partition the backlog exactly
For any backlog file, the open set and the triaged set are disjoint and their union is the
full set of proposal headings. Holds regardless of how the parser is written.

### AC-003: wrapup warns from the main loop when open proposals reach five
The rendered wrapup command instructs a single prominent warning gated on an open count of 5
or more, states the below-threshold behaviour (no warning) and the one-line degrade behaviour
explicitly, and places the proposals CLI call inside the `### Steps 6 → 7.6` section (after that heading,
before the next `### Step` heading) — main-loop steps that render on both worktree arms, never
inside the delegated Steps 1–5.6 body nor in 5.7, which the delegated path's "skip straight to
Step 6" can bypass.

### AC-004: the count floor admits a zero-overlap high-recurrence entry
A corpus entry carrying the highest `count:` and sharing no normalized token with the topic
is present in the emitted fence, where today `top_candidates` drops it before rerank.

### AC-005: floor entries are labelled in the fence
Every entry admitted by the floor rather than by lexical score carries a distinguishing label
in the `<memory_candidates>` fence, so the reranking turn can discard it cheaply.

### AC-006: the count floor is additive to k and never displaces a lexical hit
The floor-disabled result set is a subset of the floor-enabled result set for every corpus,
topic and k. This is an invariant of the composition, independent of the ranking internals.

### AC-007: execute warm tier invokes memory_retrieve
The rendered `/hm:execute` Session Context Loading section calls `hm memory_retrieve` and no
longer instructs the `failures.md` head-skim plus `rg -F "[fail:"` slug scan.

### AC-008: emit accepts a record omitting wall_time_ms
A record with no `wall_time_ms` key validates and appends exactly one line to today's JSONL.

### AC-009: previously valid telemetry records remain valid
Any record that validated under the required-field schema still validates under the optional
one. Optionality is a superset — no existing row becomes unreadable.

### AC-010: the review stage doc matches the wall_time_ms optionality
The rendered review command's telemetry paragraph no longer claims `wall_time_ms` defaults to
0 while the schema rejects its absence; doc and schema state the same contract.

### AC-011: plan documents --barrier-index as an integer
The rendered `/hm:plan` `stage_agent_ledger emit` example states that the barrier-index value
is an integer, matching `type=int` and the guidance `/hm:execute` already carries.

### AC-012: the proposals CLI reports the oldest open proposal's date
For a fixed set of hand-authored backlogs, the reported oldest date is the minimum trailing date
among open proposals, ignores resolved batches and file order, and is null for an absent file or
an all-undated open set.

## ❓ Open Questions

None blocking. Deferred by explicit decision, for a later cycle:

1. **Does the count floor alone close the recall gap?** The task-kind second query was scoped
   out to measure the floor's effect in isolation first. If a follow-up audit still shows
   `[fail:*]` misses at prevention time, revisit — and decide then whether topic expansion
   belongs in the CLI (deterministic, testable, but re-introduces a lexical rule) or the stage
   template (uses LLM judgment per CLAUDE.md, but untestable beyond render-grep).
2. **Default N for the count floor.** Resolved as a flagged tunable with a default rather
   than a specification constant; `/hm:plan` picks the number.
3. **Whether the class of defect behind 7a/7b warrants a standing structural gate** — a check
   that a rendered template's stated field contract matches its Python entry point. Two
   instances found in one audit; a third would make it a `count:3` escalation.

## 🔍 Refinement Decisions

- **Salvage round (2026-09-19):** carried S1, S3–S7 and AC-001/002/004–011 over unchanged.
  Warning placement → **main-loop CLI call** (rejected: a new `WrapupReceipt` field, which
  reconciliation cannot verify; both). Byte-cap starvation → **out of scope, filed as a
  proposal**. Warning content → **count + oldest open date** (a line that fires on every wrapup
  must carry information that changes). Test framework, Non-goals and oracles inherited.

### Source SPEC rounds (2026-08-14)

- **Round 1 (Intent + Outcomes):** scope cut to findings 1 + 2 + 3 + 7a + 7b. Findings 4 and 5
  split off as separate work. Finding 6 investigated live in `~/strange_chess` and **refuted**
  — that project renders 0.51.1 and already carries the `hm/*` SKIP branch. Test framework
  `pytest` taken as common-ground from CLAUDE.md, not asked.
- **Round 2 (Outcomes + Constraints):** proposals consumer = **both** a CLI subcommand and a
  wrapup warning. Count floor = **additive to `k`, labelled in the fence**. Task-kind second
  query = **out of scope**. `wall_time_ms` = **schema becomes optional**. Inferred and stated
  for override: `execute` warm tier **replaces** the skim rather than running both.
- **§2.5 inequality gate:** three candidates generated, one asked (5/5). C1 (floor default N)
  failed EIG — a flagged tunable does not change SPEC content. C2 (open/resolved parse rule)
  failed common-ground — the existing file's `## Proposal:` / `## RESOLVED …` split determines
  it at inference confidence ≥ 0.95.
- **Round 3 (Verification):** the wrapup warning counts **total unresolved proposals ≥ 5** —
  not proposal age, and not the count of undetected recurrences. With 16 open today it fires
  on the next wrapup, which is the intended effect.
