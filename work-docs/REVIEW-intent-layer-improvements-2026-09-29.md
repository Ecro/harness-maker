---
type: review
task_slug: intent-layer-improvements
status: APPROVED
created: 2026-09-29
run_id: cda10095b67a
review_base: 2987be40d8bb79025e655a81593feccedbb517a2
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/structural/test_autopilot_gate_render.py
    - tests/structural/autopilot_gate_golden.json
    - tests/structural/test_roundtrip_budget.py
    - tests/unit/test_render_wrapup_delegation.py
    - tests/integration/test_intent_trial_native_evidence.py
    - tests/fixtures/workflow-feedback-trial-protocol.md.j2.txt
    - work-docs/BASELINE-DELTA-intent-layer-improvements.md
  scenario_misses: []
  task_slug: intent-layer-improvements
  computed_at: '2026-09-29T14:10:00Z'
---

# REVIEW — intent-layer-improvements (2026-09-29)

## 🎯 Round 1 Summary

Grade **A** (P0 0, P1 0 consensus-passed; P2 11, P3 3). Lens coverage: all seven lenses
exercised, `blocks_approval: false`. `human_review_needed: false` (no manual-only or
weak-consensus P0/P1). Pass 1 raised 21 findings (1 P1); Pass 2 kept 13 and regraded the P1
heredoc finding to P2 (consent-gated, safe alternative offered on the same line). Codex
(invoked, 4 findings) → PIDA: 3 accepted, 1 unresolved.

## 🔍 Drift Findings

`scope_violation` — seven files outside every PLAN phase's listed scope. Each is a guard that the
template/CLI change forced to move and each is attributed in-file: the autopilot golden
re-capture (dated entry + `rebases` row), the round-trip table 33 → 34 and wrapup line pins
850/852 → 840/842 (dated comments), the retired trial render test with its evidence hash rebound
to the preserved protocol fixture, and the BASELINE-DELTA document the `surface_allowance`
requires. Disposition: accepted as Phase 4 consequences; PLAN Phase 4 scope should list them.
No SPEC scenario lacks coverage; S7 (AC-006) is verified after task-land by design.

## ✅ Consensus Findings

| id | Sev | Lens | Where | Finding |
|---|---|---|---|---|
| 715e48918d404905 | P2 | security | wrapup.md.j2:592, SKILL.md.j2 | Fixed heredoc sentinel `HM_EOF`: a body line equal to it ends the heredoc and the rest runs as shell — reopens the class the file-only design closed |
| c4980242e8b95231 | P2 | security + codex | intent_trial.py:989 | Freeze authority check passes when decision id and `policy.authority` are both absent (`None == None`) |
| 01c2b8d1a52e0b95 | P2 | robustness | intent.py:480 | `-` reads stdin with no tty guard; a missing heredoc hangs |
| 11209d510dce0fdb | P2 | robustness | wrapup.md.j2:607 | Batch over 16 items (4 questions × 4 options) undefined; unseen rows would be marked `declined` |
| 02c8023901241a27 | P2 | functionality | wrapup.md.j2:608 | `failed` rows are skipped by Step 1 forever — "not in this wrapup" implies a retry that never comes |
| 547d728b8513765c | P2 | consistency | intent_cli.py:80 | `_CANONICAL_STATUS` duplicates `intent_vocabulary.QUESTION_STATES` |
| 0ddf871c51a9a0d2 | P2 | consistency | intent_trial.py:1024 | Freeze consulted at one branch only; marker-free/deleted branches stay protected by design but undocumented |
| 958a504b8e26f728 | P2 | tests | test_render_intent_layer_assume_add.py:67 | Nothing pins that each batch item shows its exact arguments (the consent) |
| 8f28f91f2558174b | P2 | tests | test_render_intent_feedback_batch.py:261 | Verdict clause `` `last` `` is also satisfied by the measure-all item |
| 88635b8d131ce908 | P2 | tests | test_render_intent_feedback_batch.py:353 | AC-007 regex/file set too narrow (`trial reconcile`, `record-decision`, `trial_feedback`, skill SKILL.md) |
| 47e2bea09c95b775 | P2 | intent drift | PLAN | WORLD-INTENT-CLOSED-LOOP scope 6: per-task evidence link for the verdict item unspecified |
| 8e4c3583f79971c0 | P3 | tests | test_render_intent_feedback_batch.py | Resume test filters empty regions (silent skip on heading rename) |
| 1fc38fcb466a4fcd | P3 | tests | test_intent_cli_inputs_resolve.py | No cases: non-UTF-8 stdin, empty stdin, explicit `--observed-at` preserved |
| 7ff1b0f9ea6c3a69 | P3 | tests | test_intent_trial_freeze.py | No case: HEAD user-disabled + uncommitted working-copy re-enable (expected active) |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Finding |
|---|---|---|---|
| cea50c76804b019a | P2 | codex (accepted) | A pending row that bears on a metric has no correct route: 5.7 sends every row to `question observe/add` |
| 3c22287da5aedbd7 | P3 | codex (accepted) | Default `observed_at` truncates to whole seconds, so it can precede the call start; the test hides it by truncating t0 |
| bf3d2ab6f9837692 | P2 | codex (unresolved) | Empty batch "go to the close question" skips the readback text Step 5 requires |

## 🤝 Disagreements

Security Pass 1 graded the heredoc finding P1; its own Pass 2 regraded to P2 with reasons. The
concurrency lens dropped all three of its Pass 1 findings in Pass 2 (safe-direction staleness,
or duplicates of robustness/security findings). Codex's `9ffa4f1da44b57f2` is the same defect as
security `c4980242e8b95231` and is folded into it as a cross-model voice.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1 · models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 9ffa4f1da44b57f2 | codex | P2 | src/harness_maker/intent_trial.py | 989 | Missing authority and decision IDs satisfy the freeze check | `policy.get("authority") == latest.get("id")` | false | accepted | None==None passes; corroborates c4980242 | pending | |
| cea50c76804b019a | codex | P2 | src/harness_maker/templates/stages/wrapup.md.j2 | 597 | Metric feedback has no correct route through the record batch | 5.7 step 2 routes pending rows to question writes only | false | accepted | S2 allows metric rows; 5.7 has no metric-row route | pending | |
| bf3d2ab6f9837692 | codex | P2 | src/harness_maker/templates/stages/wrapup.md.j2 | 605 | Empty batch skips the readback before the close question | step 3 vs step 5 | false | unresolved | textual conflict; empty batch writes nothing; no .j2 oracle | pending | |
| 3c22287da5aedbd7 | codex | P3 | src/harness_maker/intent_cli.py | 98 | Default timestamp drops fractional seconds | `strftime("%Y-%m-%dT%H:%M:%SZ")` | false | accepted | stamp can precede call start; test truncates t0 | pending | |

### Iteration 2 (Grade: A → A)

DRI chose to fix the accepted P2/P3 set and the codex manual-only items before the confirmation
pass (the gate had already cleared at round 1; P2/P3 would not have entered auto-fix).
Fixes applied: 17 · build: full suite 9663 passed, 0 failed · revert control: tty guard,
sub-second timestamp and the id check each turn a new test red when reverted.

| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| 1 | P2 | Remove heredoc/stdin guidance from rendered recipes; free text only via Write-tool files (CLI keeps `-`, IRR-004) | wrapup.md.j2, SKILL.md.j2 | Applied · caused_by=none |
| 2 | P2 | Freeze needs a non-empty string decision id matched by `policy.authority` | intent_trial.py | Applied · caused_by=none |
| 3 | P2 | tty guard on `-` stdin | intent.py | Applied · caused_by=none |
| 4 | P2 | Claude batch capped at 16 items; overflow stays `pending`; only shown rows become `declined` | wrapup.md.j2 | Applied · caused_by=none |
| 5 | P2 | `failed` rows re-offered once, labelled with the previous error | wrapup.md.j2 | Applied · caused_by=none |
| 6 | P2 | `_CANONICAL_STATUS` removed; uses `intent_vocabulary.QUESTION_STATES` | intent_cli.py | Applied · caused_by=none |
| 7 | P2 | Comment: freeze honoured only on the marker-present branch; others stay protected on purpose | intent_trial.py | Applied · caused_by=none |
| 8 | P2 | Test: exact arguments shown before the ask | test_render_intent_feedback_batch.py | Applied · caused_by=none |
| 9 | P2 | Test: verdict clause scoped to its item | test_render_intent_feedback_batch.py | Applied · caused_by=none |
| 10 | P2 | Test: AC-007 regex widened, skill SKILL.md scanned | test_render_intent_feedback_batch.py | Applied · caused_by=none |
| 11 | P2 | Verdict evidence names the task slug and its PLAN Feedback rows (intent drift) | wrapup.md.j2 | Applied · caused_by=none |
| 12 | P3 | Test: both resume regions must be non-empty | test_render_intent_feedback_batch.py | Applied · caused_by=none |
| 13 | P3 | Tests: non-UTF-8 / empty / terminal stdin refused; explicit `--observed-at` kept | test_intent_cli_inputs_resolve.py | Applied · caused_by=none |
| 14 | P3 | Tests: disable without ids; HEAD disabled + working copy re-enabled → active | test_intent_trial_freeze.py | Applied · caused_by=none |
| 15 | P2 | Metric-bearing pending rows routed to a `metric record` item (codex) | wrapup.md.j2 | Applied · caused_by=none |
| 16 | P3 | Default `observed_at` keeps microseconds; test no longer truncates t0 (codex) | intent_cli.py | Applied · caused_by=none |
| 17 | P2 | Empty batch: Step 1 read stated as the readback (codex, unresolved) | wrapup.md.j2 | Applied · caused_by=none |

Drift: PLAN Phase 4 scope now lists the seven guard files (accepted, documented).
Guards moved again by these edits: autopilot golden (only `wrapup`, dated entry), wrapup line pins
840/842 → 841/843, snapshots regenerated in the worktree (no path leaks).
Remaining: 0 | New issues introduced: 0 (not re-reviewed — see below)
Churn: 0.217 (max: tests/unit/test_intent_cli_inputs_resolve.py, measured 16, excluded 0)
rereview: skipped — churn 0.22 < 0.30 (all 17 fixes unreviewed until the confirmation pass)

## Confirmation pass — confirm-1 (frozen 07a2c8d6, span 2987be40..07a2c8d6)

All seven lenses exercised (`blocks_approval: false`). New consensus-passed severe findings: **1**
(`729352e51140b286`, P1 functionality — the 5.7 verdict item's "skip when already `recorded`" rule
keyed on a row no step wrote, so a resumed wrapup could record the metric twice). Also new: 7 P2,
4 P3. Outcome: dirty → one repair round (budgeted separately; does not increment
`iteration_count`), then confirm-2.

### Repair round after confirm-1

| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| 1 | P1 | Shown items without a row (stale question, verdict) get a PLAN Feedback row carrying their mark; that is the verdict row the skip rule reads | wrapup.md.j2 | Applied · caused_by=none |
| 2 | P2 | A re-offered row that fails again becomes `declined` with the error (bounds "once") | wrapup.md.j2 | Applied · caused_by=#5 (iteration 2) |
| 3 | P2 | Skill: the reference is applied at wrapup Step 5.7; 5.7 names the reference | SKILL.md.j2, wrapup.md.j2 | Applied · caused_by=none |
| 4 | P2 | Feedback-entry names the intent-layer Feedback columns and says to add the table if missing | step_manifest.md.j2 | Applied · caused_by=none |
| 5 | P2 | Missing stdin (`None` / no `.buffer`) → parser error, not AttributeError | intent.py | Applied · caused_by=#3 (iteration 2) |
| 6 | P3 | Batch items show an excerpt of the text they record beside the arguments | wrapup.md.j2 | Applied · caused_by=none |
| 7 | P2 | `_committed_user_disabled` fail-closed on undecodable HEAD — `_split` raises only ValueError (incl. UnicodeDecodeError, wrapped YAML errors); pinned by a test | test_intent_trial_freeze.py | Applied (test only) · caused_by=none |
| 8 | P3 | Tests: re-freeze after thaw is inactive; explicit `--observed-at` kept on all three write paths; trial-duty negative controls; verdict-row clause | tests | Applied · caused_by=none |
| 9 | P2 | Resolve from engine `assumed` | — | Rejected · authority AC-010 — canonical `intent.yaml` stores only open/confirmed/wrong and writes require the canonical layout, so `assumed` is unreachable at resolve time (a fixture forcing it is refused by the loader) |
| 10 | P2 | Non-tty stdin that never closes still blocks | — | Accepted, not fixed: the rendered recipes no longer pass `-` at all (agents use files); a timeout on a scripted caller's own pipe is out of scope |

Revert control: `test_missing_stdin_is_refused` fails against the pre-repair `intent.py`.

## Confirmation pass — confirm-2 (frozen e2a187fd, span 2987be40..e2a187fd)

Full suite before freeze: 9669 passed, 0 failed. All seven lenses exercised (`blocks_approval:
false`; the tests lens was re-dispatched once after a session interruption). New consensus-passed
P0/P1: **0** → APPROVED. No fixes applied in this pass. Carried P3 (accepted, not fixed):

| id-source | Sev | Finding | Carry |
|---|---|---|---|
| core/design | P3 | `_RESOLVABLE` keeps an `assumed` key that is unreachable at write time | follow-up: drop or annotate as defensive |
| core/consistency | P3 | SKILL `question add` synopsis still pairs `--observed-at` with `--text-file` | follow-up: `[--text-file [--observed-at] …]` |
| security | P3 | `_user_disabled` is looser than `_validate_decision` (no `decided_at`/`evidence_refs`/`revision` check) | follow-up: also require `_validate_decision(latest)` |
| tests | P3 | `assumed` resolve source unexercised | Rejected · AC-010 (same as confirm-1 repair row 9) |

## 🔁 Oscillation

None (`review_churn oscillation --rounds 2,3` returned no rows).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 17        | —   |
| 2         | A     | 17            | 0         | 0 (not re-reviewed; churn 0.22 < 0.30) |
| confirm-1 | B (1 new P1) | —      | 12        | 12  |
| repair    | A     | 8 applied, 1 rejected, 1 accepted-unfixed | 0 | — |
| confirm-2 | A     | —             | 3 P3 carried | 4 (P3) |

Final grade: A
Iterations used: 2 / 3 (+ one confirm-1 repair round, budgeted separately)
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/intent.py | 629 → 631 (round 2) | 118 → 119 | 5 → 5 | measured |
| src/harness_maker/intent_cli.py | 257 → 255 (round 2) | 57 → 57 | 10 → 10 | measured |

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 0 · prior-fix 2 · unattributed 0
