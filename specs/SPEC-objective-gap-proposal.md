---
type: spec
task_slug: objective-gap-proposal
status: approved
created: 2026-09-16
tags: [harness-maker, spec, python, jinja2, intent-layer, objectives, outcomes, llm-judgment]
tier: 1
test_framework: pytest
research_doc: "[[RESEARCH-objective-gap-proposal]]"
summary: "Read-only `hm world gap` table + on-demand LLM objective candidates (skill + plan Step 0.5); writes only via `objective new`, approve stays human"
---

> Vocabulary and storage layout are superseded by [[SPEC-intent-vocabulary-rename]];
> owners shape and advisory approval guidance by [[SPEC-intent-owners-role-map]].
> This historical SPEC and its machine companion retain their original ACs and test bindings
> as compatibility evidence. Unchanged behavioral guarantees still apply.


# SPEC — Objective gap & proposal: from a written mission to a proposed objective

## 🎯 Intent

The intent layer records *why* work happens, but it starts from an empty file: once `mission`
and `outcomes` are written there is nothing that looks at the gap between the outcomes' targets
and what has been recorded, and nothing that turns that gap into an objective the operator can
approve. The first intent RESEARCH evaluated a derived "`hm next`" view and rejected it for
re-proposing rejected work and for unstable rankings; the user withdrew that lock-in on
2026-09-16 for an **on-demand, read-only, never-gating** form. This SPEC adds the deterministic
gap table as a verb, lets the LLM propose candidates only when asked, and keeps every write on
the existing answer-gated `objective new` path with `approve` in human hands.

## 🌅 Outcomes

- The operator can run `hm world gap --json` and see, per outcome, whether it is
  `never_measured`, `stale_definition` or `measured` (with the existing `gap` verdict), every
  objective in every state with its `observed` verdict and `rejected[]`, assumption conflicts,
  `unknowns` and fired revisits — without any file being written.
- The operator can ask "what should we do next / where are the gaps" and the `intent-layer`
  skill answers with at most three objective candidates, each carrying evidence and an
  `overlaps-with` line, and writes an `INTENT-<ID>.md` in state `proposed` only for the
  candidates the operator says yes to.
- Answering "none" in `/hm:plan` Step 0.5 offers, once, to draft an objective for the task.
- Declined candidates from the same turn are pre-filled into the accepted record's `rejected[]`,
  and each accepted proposal leaves one `objective_proposed` ledger event so adoption is
  measurable.
- Nothing about the gate, review Step 3.3 or wrapup 5.7 changes; a `proposed` objective linked
  from a PLAN still halts autopilot with `not_active` until a human approves and activates it.

## 📋 In-Scope Scenarios

### S1: the gap table names why an outcome cannot be judged
**Given** `intent.yaml` has outcomes `a` (never recorded), `b` (recorded under an older
`how_measured`) and `c` (recorded under the current definition, below target)
**When** the operator runs `hm world gap --json`
**Then** the payload lists `a` with `reason: never_measured`, `b` with `reason: stale_definition`
and `c` with `reason: measured` and `gap: below_target`, and every outcome row carries
`how_measured` so a "measure first" line can print the command
**And** no file under the checkout changes
**And** on an invalid `intent.yaml` the payload is `status_report`'s invalid early-return
(`state: invalid`, `error`, `errors`) verbatim — one shape for both readers.

### S2: the gap table carries the rejection history
**Given** objectives `OBJ-1` (`closed`, `observed: missed`, `rejected: [x]`), `OBJ-2`
(`active`, `rejected: [y]`) and `OBJ-3` (`dropped`)
**When** the operator runs `hm world gap --json`
**Then** all three appear under `objectives` with their `state`, `observed`, `title` and
`rejected[]`, so a proposer can name what it overlaps with
**And** `hm world status --json` is unchanged (it still omits closed and dropped records).

### S3: a proposal is written only on yes and leaves a trace
**Given** the skill proposed candidates P1, P2, P3 and the operator answered yes to P2 only
**When** the skill runs `hm world objective new OBJ-9 … --from-proposal --candidates 3 --declined "P1 title" --declined "P3 title"`
**Then** `work-docs/INTENT-OBJ-9.md` exists in state `proposed` with `rejected: ["P1 title", "P3 title"]`
**And** exactly one `objective_proposed` event `{objective: OBJ-9, candidates: 3, accepted: 1}` is appended to the autopilot ledger
**And** the skill collected every candidate's answer before the first write, so a decline that arrives after the yes (P3) is in the list; with two accepted candidates each record carries the same complete declined list and one event each
**And** a call with none of the three proposal flags writes the record and no event, while `--candidates` or `--declined` without `--from-proposal` is refused before any write.

### S4: unmeasured outcomes are proposed with a label, never silently
**Given** every outcome is `never_measured`
**When** the operator asks the skill what to do next
**Then** the rendered skill instructs: propose, but every candidate for such an outcome carries
`evidence: none — hypothesis only` and the answer opens with the `how_measured` commands under
a "measure first" line
**And** the instruction to ask per candidate, run `objective new` once per yes, and never call
`approve` is present in both the Claude and Codex renders.

### S5: plan offers a draft after "none" — and on a cold start
**Given** `/hm:plan` Step 0.5 asked "Which objective does this task serve?" and the operator chose `none`,
**or** the intent is filled in but no `active`/`proposed` objective exists yet (the pick is skipped)
**When** the rendered plan command is read
**Then** it asks once "Draft an objective for this task?" and on yes records consent only;
after the interview, in a new `Step 4.9` placed before Step 5, it derives `objective new`
arguments (id, title, hypothesis, scope, outcome) from the interview and RESEARCH, shows them,
runs once with `--from-proposal --candidates 1`, and Step 5 writes `objective: <id>`
**And** if the verb refuses (id exists, outcome unknown) it prints the refusal and continues
without an `objective:` link — never retries with a mutated id
**And** on no it writes nothing and continues exactly as before.

### S6: a proposed link still halts autopilot
**Given** a PLAN whose `objective:` names a record in state `proposed`
**When** `autopilot_caps boundary` evaluates the objective gate
**Then** the decision is a halt with ledger reason `not_active`, not `approval_invalid`.

### S7: only the plan command moves, by a declared amount
**Given** the rendered command set after this change
**When** the plan/review/help byte pins and the wrapup ratchet are compared to the pre-change pin
**Then** review and help are byte-identical, wrapup is unchanged, and plan grew by no more than
the PLAN's `surface_allowance.commands.plan`.

### S8: the allowance is retired before the task lands
**Given** every phase is done and the plan growth has been measured
**When** the PLAN's `surface_allowance` block is deleted and the shipped-surface baselines are
re-frozen from the worktree with an attribution row per moved key
**Then** `pytest tests/structural` is green with no in-flight allowance, and main is green after
the land — including the +67 chars the previous task (playbook-alignment) left unfolded, which
this task folds first.

## 🚫 Non-Goals

- No rendered `/hm:intent` / `/hm:next` slash command (RESEARCH Approach C).
- No persisted candidate list; a declined candidate lives only in the accepted record's `rejected[]`.
- No ranking or scoring of candidates; no automatic `approve` / `activate`; no change to the
  gate's precedence (advance → halt only), review Step 3.3 or wrapup 5.7.
- No per-stage mission-alignment check; no LLM judgment anywhere the operator did not invoke it.
- No `evaluating` state, no change to the withdrawal criterion, no measurement automation
  (`how_measured` stays a string the human runs).
- No new agent; the main loop with the skill is the proposer.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | repo standard; render tests + world fixtures already exist |
| Determinism | `gap` is LLM-free and pure over the checkout | same contract as `status`; the CLI must be safe to run at any time |
| Ledger | `objective_proposed` joins `autopilot_ledger.EVENTS` (ADR-009 allowlist) | `append_event` rejects unknown events; the golden/enum tests must move together |
| Surface | plan may grow only by a declared `surface_allowance.commands.plan`; review/help pinned | AC-005 of playbook-alignment fails (not skips) at the same version |
| Writes | every file write goes through `new_objective`; `gap` writes nothing | one writer per file (intent layer invariant) |
| Compatibility | `status --json` payload unchanged | consumers (plan Step 0.5, wrapup 5.7, tests) read it |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_ac_001_gap_reports_measurement_reason_per_outcome` |
| S1 | property | `test_ac_002_gap_writes_nothing` |
| S2 | unit | `test_ac_001_gap_lists_every_objective_state_with_rejected` |
| S3 | unit | `test_ac_003_from_proposal_prefills_rejected_and_emits_one_event` |
| S4 | unit (render) | `test_ac_004_skill_renders_gap_situation_and_candidate_rules` |
| S5 | unit (render) | `test_ac_005_plan_offers_draft_after_none` |
| S6 | unit | `test_ac_006_proposed_link_halts_with_not_active` |
| S7 | structural | `test_ac_007_review_help_pinned_and_plan_within_allowance` |
| S8 | structural | `test_ac_008_allowance_retired_and_structural_suite_green` |

### Acceptance criteria

### AC-001: gap report carries measurement reason and every objective state
`world.gap_report(root)` returns each outcome with `reason ∈ {never_measured, stale_definition, measured}`, the existing `gap` verdict and `how_measured`, and every loadable objective with `state`, `title`, `observed`, `rejected`; its outcome subset equals `status_report(root)["outcomes"]` on the shared keys; on an invalid world it returns `status_report`'s invalid payload verbatim.

### AC-002: gap writes nothing
For every loadable world, running `hm world gap --json` leaves the checkout's file tree byte-identical.

### AC-003: from-proposal prefills rejected and emits one event
`objective new … --from-proposal --candidates N --declined T…` writes a `proposed` record whose `rejected` equals the declined titles in order and appends exactly one `objective_proposed` event with `{objective, candidates, accepted: 1}` to the ledger directory the caller names (tests pin a tmp directory); a call without any proposal flag writes the record and no event; `--candidates`/`--declined` without `--from-proposal` is refused before any write; a failed append after the record write is reported on stderr and exits 0 (the record stands, no retry).

### AC-004: skill renders the gap situation and candidate rules
Both renders of the `intent-layer` skill contain the `gap --json` verb, the "at most three" cap, the `overlaps-with` field, the `evidence: none — hypothesis only` label, the "measure first" line, the per-candidate ask rule, the sentence "answer every candidate before the first write" and the sentence that the proposer never runs `approve`.

### AC-005: plan offers a draft after none
Both renders of the plan command contain, after the Step 0.5 "none" branch and on the filled-in zero-objective branch (which skips the pick), the question "Draft an objective for this task?" (consent only), a `Step 4.9` heading placed after Step 4 and before Step 5 that holds the `objective new … --from-proposal --candidates 1` call, the refusal line ("print the refusal and continue without a link"), and the "write nothing" line on no; the call site index is greater than the Step 4.9 heading index, which is greater than the consent question index.

### AC-006: proposed link halts with not_active
A PLAN linking a `proposed` objective makes the objective gate halt with ledger `reason == "not_active"`.

### AC-007: review, help pinned and plan within allowance
Review and help command hashes equal the pre-change pin for every arm; plan's growth per arm is ≤ the PLAN's `surface_allowance.commands.plan`.

### AC-008: the allowance is retired and the structural suite is green without it
The PLAN frontmatter carries no `surface_allowance` key, the shipped-surface baselines and the attribution document agree with the rendered surface, and `pytest tests/structural` passes from the worktree with zero in-flight allowances.

### Test files (spec gate)

| Test file | ACs |
|---|---|
| `tests/unit/test_world_gap.py` | AC-001, AC-002 |
| `tests/unit/test_intent_doc_new.py` | AC-003 |
| `tests/unit/test_render_intent_layer.py` | AC-004, AC-005 |
| `tests/unit/test_autopilot_caps_objective_gate.py` | AC-006 |
| `tests/structural/test_objective_gap_proposal_invariance.py` | AC-007, AC-008 |

## ❓ Open Questions

None — every slot was settled in the interview (see Refinement Decisions). Items for
`/hm:plan` ADRs: the exact `gap_report` payload shape, the `surface_allowance.commands.plan`
amount and where the pre-change pin is stored, and whether `--declined` accepts titles only
(recommended) or full candidate JSON.

## 🔍 Refinement Decisions

- Round 1 — **Unmeasured outcomes: propose with the `evidence: none — hypothesis only` label**
  (user chose this over the recommended refuse-and-measure-first; the "measure first" line with
  `how_measured` commands stays as the opening of the answer). **LLM step lives in both** the
  skill and plan Step 0.5. **Adoption measured** by one `objective_proposed` ledger event written
  by `objective new --from-proposal`. **Declined candidates** pre-fill the accepted record's
  `rejected[]`; nothing else persists.
- Defaults taken without asking: candidate cap 3; `gap` payload = outcomes + objectives (all
  states) + conflicts + unknowns + fired_revisits; `status --json` untouched; `pytest`.
- Round 2 (plan-validator follow-up, 2026-09-16) — **flags are proposal-only**: `--candidates`/
  `--declined` without `--from-proposal` are refused (S3 last clause reworded). **Consent at Step
  0.5, creation at Step 4.9** after the interview (S5/AC-005 now assert ordering). **Collect every
  candidate answer before the first write** (S3/AC-004). **Invalid world mirrors `status`**
  (S1/AC-001). **Allowance retirement is in scope** (S8/AC-008) — the previous task's expired
  +67 is folded first, this task's growth at close-out.
