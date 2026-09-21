---
type: spec
task_slug: withdrawal-criterion-window
status: approved
created: 2026-09-20
tier: 3
tags: [harness-maker, spec, python, intent-layer, withdrawal, observability]
test_framework: pytest
research_doc: "[[RESEARCH-ai-native-sdlc-vs-intent-world]]"
summary: "Make the intent layer's withdrawal criterion fireable by judging a trailing quiet window, not a cumulative count"
---

> Vocabulary and storage layout are superseded by [[SPEC-intent-vocabulary-rename]];
> owners shape and advisory approval guidance by [[SPEC-intent-owners-role-map]].
> This historical SPEC and its machine companion retain their original ACs and test bindings
> as compatibility evidence. Unchanged behavioral guarantees still apply.


# SPEC: A withdrawal criterion that can still fire

## 🎯 Intent

The intent layer ships its own kill switch: `hm world gap --json` reports a `withdrawal`
block, and when `due` is true `/hm:wrapup` tells the operator the layer has stopped earning
its keep. The rule it evaluates is `wrapups >= 10 and objectives_observed == 0 and
revisit_candidates_now == 0`, and `objectives_observed` counts every objective that has
*ever* carried an `observed:` verdict. This repo closed `SOURCE-PLAN-STEPS` with
`observed: missed` on 2026-09-18, so that count is permanently 1 and `due` is permanently
false. The switch cannot fire again for the lifetime of the project.

Meanwhile the layer is measurably idle. All 16 measurement rows in
`.claude/world/outcomes.yaml` carry an `observed_at` of 2026-09-18 (latest
`21:55:14Z`); four wrapups have landed since with no measurement, no objective
transition and no fired revisit, and `LOOP-OPT-IN` has sat at `proposed` throughout.
The instrument reports green while describing exactly the state it exists to detect.

This SPEC replaces the cumulative rule with a trailing-window rule, registers the
replacement so the successor carries the same no-reinterpretation force as the rule it
retires, and leaves everything else about the layer alone.

## 🌅 Outcomes

- `hm world gap --json` reports how many wrapups have landed since the layer last did
  anything, instead of how many have landed since the file was first filled in.
- `due` becomes reachable from every state in which no revisit is currently a candidate:
  a long enough quiet stretch fires it, whatever the project's history contains.
- An event older than the window can no longer change the verdict. The specific defect —
  one 2026-09-18 measurement pinning `due` to false forever — has no analogue in the new
  rule.
- A project whose git history cannot date the fill still gets a verdict, provided the
  layer has recorded at least one signal.
- The operator reading `/hm:wrapup`'s notice is told which signal the count runs from.

## 📋 In-Scope Scenarios

### S1: A quiet stretch fires the criterion
**Given** a filled-in intent layer whose most recent signal is at some instant `T`
**And** no revisit condition currently evaluates to `candidate`
**When** 10 or more `hm:wrapup` start events are recorded after `T` with no new signal
**Then** `hm world gap --json` reports `withdrawal.due: true`
**And** `/hm:wrapup` prints the withdrawal notice exactly once

### S2: An old event cannot move the verdict
**Given** a withdrawal report computed over some history
**When** a signal whose instant is strictly earlier than `last_signal_at` is added to that
history
**Then** `last_signal_at`, `quiet_wrapups` and `due` are all unchanged

### S3: A layer that has never signalled still gets judged
**Given** a filled-in intent layer with no measurement row and no objective
**When** the withdrawal report is computed
**Then** `last_signal_at` is `null` and the count runs from `filled_at` instead
**And** `due` becomes true after 10 wrapups, as it did under the retired rule

### S4: A count that cannot be taken is absent, not zero
**Given** a repository with no `stage-spans.jsonl`, or none carrying an `hm:wrapup` event
**When** the withdrawal report is computed
**Then** `quiet_wrapups` is `null` and `reason` names the cause
**And** `due` is false — an uncountable history is never read as a quiet one

### S5: A signal rescues a repository git cannot date
**Given** a shallow clone, where the oldest visible commit is the clone boundary
**And** at least one measurement row or objective transition exists
**When** the withdrawal report is computed
**Then** `filled_at` is `null` with no effect on the verdict
**And** `quiet_wrapups` is an integer counted from `last_signal_at`, and `reason` is `ok`

### S6: The retired rule is recorded, not overwritten
**Given** `SPEC-intent-world-model-objective-layer.md`, where the cumulative rule was
originally registered as a Constraint
**When** this change lands
**Then** that Constraints row names this SPEC as its successor and states why the rule it
registered can no longer fire

## 🚫 Non-Goals

- **Objective link rate.** The share of landed tasks carrying an `objective:` link is the
  natural fourth signal, and it is deliberately excluded: the three readers of that link
  (`autopilot_caps.py`, `review.md.j2`, `wrapup.md.j2`) are being moved from PLAN to SPEC
  by a concurrent task on `hm/plan-stage-absorption`. A fourth reader written now would be
  written against a contract that is mid-move.
- **Automatic removal.** `due` stays a notice. Nothing in this change deletes the layer,
  disables a command, or alters a gate.
- **Re-tuning the threshold.** `WITHDRAWAL_WRAPUPS` stays 10. The number was
  pre-registered and is not re-litigated here.
- **An influence-weighted criterion.** Counting only decision-changing events (a closed
  objective, a fired revisit, a declined proposal) and discounting repeat measurements was
  considered and rejected for this task: it fires during legitimately quiet stretches where
  objectives are active and being worked.
- **Ticket intake, `external_ref`, tracker integration.** A separate roadmap item, folded
  into the plan-absorption task.
- **`status --json`.** Frozen by `SPEC-objective-gap-proposal`; the withdrawal block lives
  in `gap` only and stays there.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | The project's only test runner |
| Absent-case contract | A count that cannot be taken is `None` with a `reason`, never `0` | Inherited invariant of the withdrawal block (`[wiki:architecture] intent-layer-withdrawal-instrument`); a disguised zero reads as "quiet" and would retire a layer blind |
| Frozen payload | `hm world status --json` must stay byte-identical | `SPEC-objective-gap-proposal` froze it; both entry points share one `_status_payload` |
| LLM boundary | The withdrawal computation stays deterministic and offline | Inherited from `SPEC-intent-world-model-objective-layer`: `world`'s subcommand entrypoints import no LLM client |
| Threshold | `WITHDRAWAL_WRAPUPS = 10`, unchanged | Pre-registered; only the window it measures changes |
| Successor rule | Registered here and cross-linked from the original registration site | A pre-registered rule is not reinterpreted after it fires; replacing one before it fires is legitimate only if the replacement is registered with the same force |
| Concurrent-task boundary | Do not modify `autopilot_caps.py`, `models.py`, `presets.py`, `synthesize.py`, `step_sensitivity.py`, `command_registry.py`, `spec.md.j2`, `plan.md.j2`; add no new rendered `Step`/`Phase`/`Check` heading | All are in flight on `hm/plan-stage-absorption` (64 files); `step_sensitivity.py` must classify every rendered heading, so a new one written here lands in a registry that task owns |
| Derived artifact | `tests/structural/autopilot_gate_golden.json` is re-captured, not merged | Changing the wrapup notice moves its hashes across 4 arms; the concurrent task moves them too. Whichever lands second regenerates |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | The `withdrawal` block of `hm world gap --json` drops `objectives_observed` and `wrapups_since_fill` and gains `last_signal_at` and `quiet_wrapups` | public API/CLI contract | `gap --json` is a documented machine-readable output; a consumer outside this repo that reads the removed keys breaks, and no in-repo shim can reach it. Keeping the old names over new meanings was rejected — a name that makes a reader believe something false is the defect, not the fix |

The rule replacement itself is **not** an irreversible decision under the five categories:
it changes no schema, contract, stored data, permission boundary or dependency. It is
recorded as a Constraint and in Refinement Decisions instead of being forced into a
category it does not belong to.

## ✅ Verification Criteria

| Scenario | Verification mode | Covering ACs |
|---|---|---|
| S1 | unit + property | AC-002, AC-007 |
| S2 | property | AC-001 |
| S3 | unit | AC-003, AC-006 |
| S4 | unit + parametric | AC-004, AC-006 |
| S5 | unit | AC-005 |
| S6 | unit | AC-009 |

### AC-001: An event older than the window cannot change the verdict

The withdrawal report depends only on signals at or after `last_signal_at`. Adding a
signal strictly earlier than the current maximum leaves `last_signal_at`, `quiet_wrapups`
and `due` unchanged. This is the property the retired rule violated: `objectives_observed`
counted an objective closed at any date in history.

### AC-002: The due state is reachable from every non-vetoed state

For any world whose `revisit_candidates_now` is `0`, appending `WITHDRAWAL_WRAPUPS` wrapup
start events after the last signal — adding no new signal — makes `due` true. The retired
rule was absorbing: once any objective carried `observed`, no extension of the history
could make `due` true again.

### AC-003: `last_signal_at` is the maximum over the four timestamp sources

Measurement rows' `observed_at`, and each objective's `created_at`, `approval.approved_at`
and `closed_at`. A stored timestamp that is not an aware ISO instant is skipped, exactly as
the existing evidence readers skip one, and does not fail the report.

### AC-004: An uncountable value is absent with a reason, never zero

Whenever `quiet_wrapups` is `None`, `reason` is not `ok` and `due` is false. The report
never returns `0` for a count it could not take.

### AC-005: A recorded signal makes the verdict independent of git

When `last_signal_at` is present, the count runs from it and `filled_at` is informational.
A repository where `filled_at` cannot be resolved still reports an integer `quiet_wrapups`
and `reason: ok`.

### AC-006: The reason enum is unchanged and each value has one cause

`not_filled_in`, `no_git`, `fill_uncommitted`, `no_stage_spans`, `no_wrapup_spans`, `ok`.
The replacement introduces no new failure mode and retires none.

### AC-007: The wrapup notice names the signal the count runs from

The rendered `/hm:wrapup` withdrawal line quotes `quiet_wrapups` and `last_signal_at`, and
no longer asserts "no observed objective" — a claim the new rule does not evaluate.

### AC-008: The withdrawal block's key set is exactly the six declared keys

`filled_at`, `last_signal_at`, `quiet_wrapups`, `revisit_candidates_now`, `due`, `reason`.
This is IRR-001's observable: a removed key that survives, or a new one that does not
arrive, is the contract change not happening.

### AC-009: Both registration sites carry the succession

This SPEC registers the successor rule, and the Constraints row in
`SPEC-intent-world-model-objective-layer.md` that registered the retired rule names this
SPEC and states that the rule it registered can no longer fire.

## ❓ Open Questions

None. The three Round-1 ambiguities (window shape, payload keys, registration site) and
the two Round-2 ambiguities (threshold, irreversible list) are resolved above.

## 🔍 Refinement Decisions

- **Round 1** — Window shape: a single "wrapups since the last signal" counter, with
  `filled_at` as the fallback when no signal has ever been recorded. Rejected: a
  trailing-10-wrapup set, which needs its own rule for repositories with fewer than 10
  wrapups. Payload: replace the deciding keys and remove `objectives_observed` outright
  rather than leave a key that is read but decides nothing. Registration: both this SPEC
  and the original site.
- **Round 2** — Threshold stays 10; changing the number while changing the rule would make
  the successor untraceable to what it replaced. Irreversible list is IRR-001 alone; the
  rule replacement does not fit any of the five categories and is recorded as prose rather
  than widening the category filter.
- **Pre-interview** — Strictness was fixed before the interview as the *activity* window
  (any of measurement, transition or current revisit candidate keeps the layer alive)
  rather than an influence window. The objective link-rate signal was excluded on
  concurrency grounds, not on merit.
