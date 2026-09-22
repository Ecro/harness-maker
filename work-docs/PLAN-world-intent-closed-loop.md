---
type: plan
task_slug: world-intent-closed-loop
status: complete
created: 2026-09-22
tags: [harness-maker, plan, templates, intent, codex]
spec: "[[SPEC-world-intent-closed-loop]]"
interview_rounds: 0
adrs: 4
validator_outcome: NOT_RUN
summary: "Connect existing feedback procedures and enable gated Codex stage continuation"
intent: WORLD-INTENT-CLOSED-LOOP

---

## 🎯 Executive Summary

Implement the approved feedback contract using existing stage procedures and the
intent-layer skill. Add Codex-native same-conversation continuation after the
existing deterministic boundary authorizes it. The user explicitly added this
repair after research showed the host supports skills, Goals and Stop hooks.
No new hook, goal, public CLI, storage migration or background process is needed.
The separate [trial SPEC](../specs/SPEC-world-intent-closed-loop-trial.md) remains
open until three real tasks have source evidence and user assessment.

## 📚 Prior Work

- [Intent](../intent/WORLD-INTENT-CLOSED-LOOP.md) and
  [SPEC](../specs/SPEC-world-intent-closed-loop.md) define authority and outcomes.
- RESEARCH-mission-context-loop cautions against a parallel orchestration system.
- `assertion-invariant-over-named-dimension`: test owning blocks and hostile
  counterexamples, not whole-file keywords or a regenerated snapshot alone.
- `fix-introduced-defect-passes-all-gates`: explicitly cover pending/blocked,
  missing skill, and no-intent cases exposed by new continuation.
- Second Brain decision/preference/project searches returned no matching notes.
- Local CLI 0.155.1 has stable goals/hooks enabled. Official docs:
  https://learn.chatgpt.com/docs/build-skills and
  https://learn.chatgpt.com/docs/hooks#stop. Native capabilities do not override
  harness gates; current `stage_end_summary` excludes Codex at render time.


## Record navigation

| Follow from this PLAN | Authoritative record or result |
|---|---|
| Governing acceptance criteria | [Implementation SPEC](../specs/SPEC-world-intent-closed-loop.md) |
| Scope and lifecycle | [WORLD-INTENT-CLOSED-LOOP](../intent/WORLD-INTENT-CLOSED-LOOP.md) |
| Relevant metric/claims | [Shared definitions and questions](../.claude/intent.yaml): look up metric ID `intent_world_closed_loop_cycles` |
| Measurement evidence | [Shared measurement history](../.claude/intent/metrics.yaml): look up the same metric ID; no observation is recorded yet |
| Actual execution evidence | [EVIDENCE](EVIDENCE-world-intent-closed-loop.md), including both failed and corrected experiments |
| Result | [REVIEW](REVIEW-world-intent-closed-loop.md) and [verification receipt](RECEIPT-world-intent-closed-loop-verification.md) |
| Recorded decision | [Feedback](#feedback) and [completion disposition](#completion-disposition) |
| Authorized next work | [Real-task trial SPEC](../specs/SPEC-world-intent-closed-loop-trial.md); activate its PLAN after local application, then observe real starts |

These links identify the authoritative stores; this PLAN does not own a copied
current-state metric or question record. The absent metric observation remains
unmeasured. Trial evidence and the user's assessments are still pending.

## 📐 Architecture Decision Records

### ADR-001: Reuse the intent skill and existing durable records
Put the feedback procedure in an intent-layer reference (preserving the existing
120-line skill budget), with short stage entry/observation
and close-out pointers. Use PLAN Feedback for dispositions; do not duplicate
shared state. A SPEC-stage observation stays in the conversation/SPEC until the
execute PLAN exists. This implements SPEC IRR-001 without a new schema parser.

### ADR-002: Native Codex dispatch after the existing boundary
Keep Python boundary/approval/cap semantics intact. A Codex terminal partial calls
the same CLI, classifies judgment gates, and reads/executes the next local skill
in the same conversation on proceed=true. Preserve Claude's Skill dispatch.
Resolve skills from the current task root, base root, then the session catalog;
missing skills produce an honest handoff. Never launch nested codex exec for
ordinary stage continuation. The active loop retains its own stage ordering.

### ADR-003: Trial is a later, separately assessed task
The trial PLAN owns activation revision/time and start-ordered enrollment; no
trial is started during implementation. Existing intent consent gates remain.
Explicit user approvals in the session are reusable; no absent answer is consent.
Separate collection and outcome status with failure precedence and no reset.

### ADR-004: Test prose contracts and observed workflow behavior separately
Render tests cover integration, branch selection, gate/slug forwarding and
protocol discoverability. Existing real boundary tests cover authority. Independent
workflow evaluation uses authored scenarios/counterexamples and records evidence
in this PLAN; it does not claim three real task outcomes. Snapshot updates carry
only actual render changes. The diagnostic target predicate is covered by real-ledger transition tests
and target-membership mutation controls. Task-specific rubrics resolve from the
template directory through spec_machine; no global registration is required.

## 🏗️ Technical Design

Data flow: stage entry/resume or material observation → existing intent status →
affected IDs/evidence → consent-aware write/readback or pending disposition →
PLAN Feedback → boundary authorization → next host-specific stage invocation.
Close-out evaluates measurements before deciding intent closure and records a
termination or authorized continuation. Replay consults previous dispositions.

Supporting diagnostic: autopilot_ledger.smoke_check must recognize Codex alongside
Claude, preserving Cursor-only inapplicability. Update its existing golden table in
SPEC-token-efficiency-autopilot-ux-speed and its regression tests; the earlier
capability assumption is intentionally superseded by AC-007.

Affected templates: step_manifest, stage_end_summary, a Codex continuation partial,
intent-layer skill with its lazy-loaded reference, wrapup and execute PLAN-writing instructions.
Synthesize registers the reference for both hosts; stage/skill inventories,
state format and boundary engine stay unchanged. Documentation provides a record
map and a reusable Trial table in the skill instead of new machine state.

## 📝 Implementation Plan

### Phase 1 — Feedback and Codex continuation contracts
- status: complete
- depends_on: []
- parallel_group: workflow
- merge_hazards: shared stage partials, generated snapshots; implementation is serial
- scope in: the templates listed above; AC rubrics; focused render/behavior fixtures;
  existing tests that explicitly pin Codex exclusion; snapshot and attributed golden
  updates; this PLAN, SPECs and authorized intent lifecycle update.
- scope out: boundary engine semantics, public CLI, hooks, Goal creation, migrations.
- exit criterion: `uv run pytest tests/unit/test_world_intent_feedback.py tests/unit/test_codex_autopilot_continuation.py tests/unit/test_autopilot_template_render.py tests/unit/test_render_autopilot_picker_runtimes.py tests/unit/test_codex_stage_procedures.py tests/render/test_judgment_gate_surface.py tests/unit/test_autopilot_caps_entry_and_slug.py tests/e2e/test_autopilot_chain_e2e.py -q`
- risk: medium — rendered instructions are executable workflow behavior
- rollback: restore only this task's edited templates/tests; retain accepted SPECs
  and intent history. No commits during execute.

### Phase 2 — Integration evidence and regression validation
- status: complete
- depends_on: [1]
- parallel_group: validation
- merge_hazards: no edits during full suite; snapshots serialized after implementation
- scope in: scenario evidence, rubric review, snapshot regeneration, lint/type and
  full suite, measured surface deltas, PLAN progress.
- scope out: actual three-task trial, release, merge or push.
- exit criterion: `uv run ruff check . && uv run mypy src && uv run pytest -n 7 --dist loadfile -m 'not advisory' --ignore=tests/e2e/test_plugin_live.py -q`
- risk: medium — render size and historical golden checks require attribution
- rollback: revert only an attributable regression; do not relax gates or rewrite
  unrelated failing tests.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/autopilot_caps.py` — approval, caps, gate and merge semantics
- `src/harness_maker/world.py` — canonical state and lifecycle enforcement
- `src/harness_maker/intent.py` — metric definitions and schema
- `src/harness_maker/hooks/` — no new background continuation mechanism
- Advisory: preserve declined consent and terminal intent records; reuse explicit authorization
- Advisory: no real-use success or trial activation from synthetic evidence

## 🧪 Testing Strategy

pytest render tests against actual synthesized Codex/Claude output; false-RED
screen before test-reviewer; RED then GREEN; existing boundary E2E controls.
Independent rubric evaluation checks fixture-derived workflow decisions and
negative controls. The future trial remains unmeasured. Full suite once after
targeted tests; rerun failing files only while repairing regressions.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| Arming confused with authorization | Require boundary JSON before next-skill dispatch |
| Continued work bypasses consent | Existing write rules and pending/blocked controls |
| Skill missing inside worktree | Explicit base/catalog lookup and honest handoff |
| Prompt checks pass without behavior | Independent source-evidence review and counterexamples |
| Trial blocks first implementation | Separate trial SPEC and no synthetic attainment |
| Context grows | Shared skill, short pointers, bounded attributed allowance |

## ✅ Success Criteria

- [x] AC-001 evidence and trigger contract verified.
- [x] AC-002 authority and continuation verified.
- [x] AC-003 missing/conflicting/deferred evidence handled.
- [x] AC-004 completion and replay preserve scope.
- [x] AC-005 records navigable without migration.
- [x] AC-006 trial collection protocol verified; actual trial remains pending.
- [x] AC-007 Codex dispatch and halt branches verified.
- [x] Targeted, lint, type and full suite pass; boundaries compared.

## Feedback

| Observation / source | Affected record | Update status | Decision / owner / authority | Next action |
|---|---|---|---|---|
| User reported autopilot did not advance; official docs and stage_end_summary exclusion confirmed | WORLD-INTENT-CLOSED-LOOP, implementation SPEC AC-007 | User approved scope addition; both SPECs stamped, intent approved and active via CLI | Agent implements explicit user request under existing gates | Phase 1, no extra Goal or hook |

## Execution evidence

Historical pre-waiver checkpoint: implementation and targeted verification were complete, but the full-suite exit was blocked by external Claude quota. The resumption and final verification sections supersede this checkpoint. Real-use outcome remains not started.

Phase 1 test-reviewer: initial keyword assertions rejected; rewritten to exact
condition/action obligations and PLAN integration. Round 2 PASS. RED 29 failed /
0 passed; GREEN 29 passed. Repair invariant: no Codex action before boundary
permission; non-goals are all Contract Boundaries above.


### Final verification and source evidence

- Initial full suite ran with 7 workers. All code/render failures were repaired
  and their files were included in the follow-up run: **1166 passed, 19 skipped,
  2 xfailed**. This does not relabel the initial full suite as green.
- Final boundary/feedback matrix after the canonical slug spelling fix:
  **76 passed**. Ruff passes; mypy passes on 158 source files. `git diff --check` passes.
- Diagnostic predicate mutation sampling in isolated processes killed 4/4 mutants:
  Claude-only, Codex-only, every-target, and absent-target-default removal.
  No production source was modified by the mutation experiment.
- A.5 repair review PASS; 9 expected RED cases became GREEN after lazy reference
  loading, active-trial wiring, generic opt-in wording, and explicit missing-slug STOP.
- Independent D.5 recheck confirms all three reported gaps resolved.
- [Native execution evidence](EVIDENCE-world-intent-closed-loop.md) preserves real
  boundary authorization, next-skill execution, step-cap halt, authorized metric
  write followed by status readback, declined-write byte preservation, and replay
  without another measurement/task. These are fixtures, never real trial enrollment.
- SPEC approval remains valid. Intent status reports WORLD-INTENT-CLOSED-LOOP
  active with valid approval. The real-use metric remains unmeasured.

### D.5 newly reachable windows

Codex now reaches next-stage dispatch: missing/invalid slug and missing skill must
stop, while uppercase valid slugs remain accepted. The owning tests are
`test_s7_missing_or_invalid_slug_stops_before_skill_dispatch`,
`test_s7_boundary_precedes_codex_skill_execution`, and
`test_s7_halt_and_judgment_controls_survive`, with real boundary and native traces.
An active trial can now encounter a task without intent state, a resumed slug, or
an abort: `test_s6_trial_hooks_run_without_intent_and_keep_operator_choice_local`
and `test_s6_trial_includes_failed_rows_and_concurrent_completion` cover the
rendered integration and policy. Absent activation explicitly skips enrollment.
The small health predicate now reaches Codex-only and mixed Codex/Cursor harnesses;
`test_codex_supported_smoke_transitions_from_empty_to_recorded` and the retained
unknown-target/Cursor/Claude controls cover that window.

### External verification blocker (Phase D escalation)

The four tests in `tests/e2e/test_plugin_live.py` invoke the real Claude service.
All failed with return code 1 and the service response:
`You've hit your weekly limit · resets 10am (Asia/Seoul)`.
This is service unavailability, not evidence of a product failure or a passed
check. The message contains no reset date; no precise recovery time is asserted.
The independent stuck assessment recommends preserving the gate and rerunning
that failed file when quota is available. An already-authorized equivalent
execution environment is another possible route, but no account or billing
change is made here. No permission to waive the check is inferred.

Reproduce after recovery:
`uv run pytest -o addopts='' tests/e2e/test_plugin_live.py -q --tb=short`

Phase 2 and execute remain blocked. No review/verify/land success, commit, merge,
base harness update, trial activation or intent attainment is claimed. Remaining
work is the external live check, formal judgment/review and subsequent workflow
stages, followed by application and the separately approved three-real-task trial.

### Feedback disposition

The user's connection request led to the previously absent Codex dispatch path,
then to native positive/negative evidence and the state/readback fixtures above.
Authorized code work is implemented. The full-suite quality gate remains
unresolved because Claude quota is unavailable; the next dependent stage must
not start. Preserve this PLAN and resume the existing task after that specific
external condition changes, without creating a duplicate task or asking again
for the same implementation authorization.


Final snapshot and surface-budget confirmation: **19 passed** after the final
canonical slug spelling and blocked PLAN status. This includes the actual
`tests/unit/test_synthesize_snapshot.py` snapshot consumer.

[boundaries] comparison not performed — blocked exit. The work remains in
`.worktrees/world-intent-closed-loop` on `hm/world-intent-closed-loop`; no
worktree finalization, commit or merge was performed. The active autopilot marker
was retained and an execute `gate_blocked` event was emitted. Resuming after
external verification does not require re-authorizing the same code changes.


## Resumption — explicit user verification exception (2026-09-22)

The user explicitly approved proceeding without Claude live-environment tests
for this task. This supersedes the external blocker above, not its historical
result. Exclude only `tests/e2e/test_plugin_live.py` (four service-backed tests)
from this task's acceptance run; do not change global pytest configuration or
claim those tests passed. The remaining full-suite results, repaired-file reruns,
Codex native traces, lint and type evidence satisfy execute's revised exit.
Proceed with review, remaining verification, landing and local harness application.
The real-task trial still requires subsequent genuine tasks and user assessment.

Execute resumed boundary comparison: 41 changed paths, 0 protected boundary crossings.
```text
intent/WORLD-INTENT-CLOSED-LOOP.md
specs/SPEC-token-efficiency-autopilot-ux-speed.machine.yaml
specs/SPEC-world-intent-closed-loop-trial.machine.yaml
specs/SPEC-world-intent-closed-loop-trial.md
specs/SPEC-world-intent-closed-loop.machine.yaml
specs/SPEC-world-intent-closed-loop.md
src/harness_maker/autopilot_ledger.py
src/harness_maker/synthesize.py
src/harness_maker/templates/agents/_partials/codex_autopilot_advance.md.j2
src/harness_maker/templates/agents/_partials/stage_end_summary.md.j2
src/harness_maker/templates/agents/_partials/step_manifest.md.j2
src/harness_maker/templates/rubrics/world_intent_authority_and_progress.yaml.j2
src/harness_maker/templates/rubrics/world_intent_codex_continuation.yaml.j2
src/harness_maker/templates/rubrics/world_intent_completion_and_replay.yaml.j2
src/harness_maker/templates/rubrics/world_intent_discoverability.yaml.j2
src/harness_maker/templates/rubrics/world_intent_evidence_before_decision.yaml.j2
src/harness_maker/templates/rubrics/world_intent_real_task_trial.yaml.j2
src/harness_maker/templates/rubrics/world_intent_trial_protocol.yaml.j2
src/harness_maker/templates/rubrics/world_intent_uncertainty_disposition.yaml.j2
src/harness_maker/templates/skills/intent-layer/SKILL.md.j2
src/harness_maker/templates/skills/intent-layer/references/workflow-feedback.md.j2
src/harness_maker/templates/stages/execute.md.j2
src/harness_maker/templates/stages/wrapup.md.j2
tests/render/test_render_sessionid_wiring.py
tests/snapshot/prod-firmware.expected.yaml
tests/snapshot/prod-tauri-app.expected.yaml
tests/snapshot/side-python-cli.expected.yaml
tests/snapshot/side-tauri-app.expected.yaml
tests/structural/autopilot_gate_golden.json
tests/structural/test_autopilot_gate_render.py
tests/unit/test_autopilot_ledger_health.py
tests/unit/test_autopilot_template_render.py
tests/unit/test_codex_autopilot_continuation.py
tests/unit/test_health_evidence_surface.py
tests/unit/test_render_autopilot_picker_runtimes.py
tests/unit/test_render_intent_layer.py
tests/unit/test_render_wrapup_delegation.py
tests/unit/test_world_intent_feedback.py
work-docs/BASELINE-DELTA-world-intent-closed-loop.md
work-docs/EVIDENCE-world-intent-closed-loop.md
work-docs/PLAN-world-intent-closed-loop.md
```


## Review repairs (round 2)

The initial review found three P1 issues and one P2 evidence gap. Repairs:
1. Persist auto-answered judgment directives before inspecting `proceed:false`.
   The real boundary tests cover review→wrapup and a pipeline ending at review.
2. Use a single explicitly named collector for the authoritative base-root trial
   PLAN. Task agents retain local source events and never merge stale cohort copies.
   Reconcile shared first-start spans before slot assignment; incomplete clocks stay
   pending. Transfer requires the prior collector's acknowledged stop.
3. Add independent native protocol fixtures for cohort ordering/resume/abort,
   out-of-order completion, missing evidence, confirmed failure, denied reset,
   noncollector writes, and incomplete sources; add uncertainty/terminal controls.
4. Expand judgment subject paths to include the actual included partials and
   reference/evidence files. This changes verification binding only, not any AC or
   irreversible decision. Re-stamp the original user approval for these unchanged
   requirements; the explicit continuation approval also covers their repair.

The two trial findings share a state model: collector ownership, canonical root,
first-start source completeness, cohort identity, terminality, evidence, and final
user assessment. The consolidated protocol edit covers all dimensions without a
new CLI, storage schema, daemon, or task. Repair attribution: original review
findings, caused_by=none; no finding was introduced by a prior repair round.


## Final verification and review repair evidence

The unrestricted non-Claude suite completed: 9134 passed, 100 skipped, 3 xfailed,
8 failures. Four atomic command budgets still depended on the now-removed PLAN
allowance; their distinct pinned fixture was re-measured before/after and
re-frozen with full attribution. One remaining inventory assertion counted a
reference document as a skill; both inventory tests now count SKILL.md only.
Three failures were ambient /tmp/.claude test-marker interference during the
parallel suite (root resolution and two clean-chain assertions); the directory
disappeared with test cleanup. A preservation attempt found it already absent
and changed nothing. The three tests pass after the concurrent suite finishes.

The repaired-file run covers every failed file plus both inventory checks and
native evidence assertions. All original failures and successful follow-ups
remain in /tmp/world-final-suite-2.log and
/tmp/world-final-repaired-files-green.log. No Python engine gate was changed.

Round 3 resolved the remaining AC-001 gap with explicit-dependency isolated
native pairs. The observation pair was corrected to ongoing work after entry
and before closeout; the initial duplicate-entry context remains in the capture.
Independent code-reviewer re-review returned no findings. Captured evidence is
included in judgment subject hashes so changing it invalidates a prior verdict.

Managed documentation is updated for Codex dispatch and feedback/record links.
No protected implementation boundary was crossed. The real trial is separate;
none of these synthetic fixtures is an enrolled task.

Final failed-file follow-up: 78 passed in 24.64 seconds; ruff check/format and
strict mypy src+tests passed (778 source files). No general verification cache
marker is published for a task with the explicit Claude-live exception.

Confirmation caught the newly ignored EVIDENCE file missing from its temporary
index. A task-specific .gitignore exception makes the durable evidence visible
to fresh checkouts and frozen review; all original experiment results remain.


## Completion disposition

Implementation is complete and review is APPROVED, grade A after full frozen
confirmation. Verification covers the full non-Claude suite and successful
reruns of every failed file (78 passed), plus lint, formatting and strict typing.
The only intentionally excluded tests are the four explicitly waived Claude
live cases. No universal cached pass is exported for this exception.

Verification checks: matching clean REVIEW drift verdict; regression evidence
above; structural PASS with prior/current null because the generated dashboard
contains no populated score; no security findings file or unresolved high finding;
no unmerged paths or whitespace conflicts; SPEC-need N-A because this PLAN has
no spec_need_verdict, with both approved SPEC artifacts present. Independent
judgment binding is the final wrapup gate; its results are stored in machine SPEC.

The intent remains active and its real-use metric remains unmeasured. The
separate trial will be activated only after local application, with zero initial
rows. The next three genuine task starts, including failures and aborts, must be
retained; the user owns their final continuity assessments.
