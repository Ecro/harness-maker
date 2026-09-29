---
type: plan
task_slug: world-intent-closed-loop-trial
status: planning
created: 2026-09-22
intent: WORLD-INTENT-CLOSED-LOOP
spec: '[[SPEC-world-intent-closed-loop-trial]]'
trial:
  schema_version: 1
  activation: '2026-09-22T02:45:59.012195Z'
  policy:
    enabled: false
    revision: intent-layer-improvements-freeze-v1
    authority: world-intent-closed-loop-trial-freeze
  collector_provenance: codex-thread-01a0c683-3cde-7f40-9d06-e871e86c6da4
  decisions:
  - id: intent-feedback-continuity-policy-approval
    kind: policy
    actor: user
    decided_at: '2026-09-23T14:58:00.443103Z'
    evidence_refs:
    - conversation:spec-approval
    - specs/SPEC-intent-feedback-continuity.md
    - work-docs/PLAN-intent-feedback-continuity.md
    authority: explicit_user_decision
    payload:
      enabled: true
      revision: intent-feedback-continuity-v1
  - id: intent-feedback-continuity-historical-source-review
    kind: source_review
    actor: user
    decided_at: '2026-09-23T14:58:20.140099Z'
    evidence_refs:
    - conversation:call_uUHsEHSHPszjtqCpeZFrOmE0
    - .claude/observability/stage-spans.jsonl
    - work-docs/PLAN-docs-release-sync.md
    - work-docs/PLAN-intent-feedback-continuity.md
    authority: explicit_user_decision
    payload:
      inventory:
        base:ledger: b835e7c31ad279ea72486b82e0034b81878e7d63e41e93c0b5652c989c2ba8b7
        base:work-docs/RESEARCH-docs-release-sync.md: ce84d0d9cc37da655243beeba751d90b2ae7f56950307766cc12d223f6030057
        base:work-docs/PLAN-docs-release-sync.md: bf45661f1c3a062ed45336e354e823362f1bfac743ac0904363db1857b5d093f
        worktree:/home/noel/harness-maker/.worktrees/intent-feedback-continuity:work-docs/RESEARCH-docs-release-sync.md: ce84d0d9cc37da655243beeba751d90b2ae7f56950307766cc12d223f6030057
        worktree:/home/noel/harness-maker/.worktrees/intent-feedback-continuity:work-docs/PLAN-docs-release-sync.md: bf45661f1c3a062ed45336e354e823362f1bfac743ac0904363db1857b5d093f
        worktree:/home/noel/harness-maker/.worktrees/intent-feedback-continuity:work-docs/RESEARCH-intent-feedback-continuity.md: 360a835b6773c49f3e92243972e3f871b50959009a4140e01a1f587f5f4afab6
        worktree:/home/noel/harness-maker/.worktrees/intent-feedback-continuity:work-docs/PLAN-intent-feedback-continuity.md: 1cbf2ded92807392eb1fb780ac55c8afa8ec650064a51d1a2514d2731a99143f
      through: '2026-09-23T12:55:56.463716Z'
      disposition: accepted
      ordered_tasks:
      - docs-release-sync
      - intent-feedback-continuity
      excluded_tasks: []
  - id: world-intent-closed-loop-trial-freeze
    kind: policy
    actor: user
    decided_at: '2026-09-29T12:36:34Z'
    evidence_refs:
    - conversation:hm-spec-interview-round-1-trial-question
    - specs/SPEC-intent-layer-improvements.md
    - work-docs/RESEARCH-intent-layer-improvements.md
    authority: explicit_user_decision
    payload:
      enabled: false
      revision: intent-layer-improvements-freeze-v1
  members:
  - task: docs-release-sync
    start: '2026-09-22T03:39:48.368348Z'
    source_refs:
    - base:work-docs/RESEARCH-docs-release-sync.md
    - base:work-docs/PLAN-docs-release-sync.md
    - worktree:/home/noel/harness-maker/.worktrees/intent-feedback-continuity:work-docs/RESEARCH-docs-release-sync.md
    - worktree:/home/noel/harness-maker/.worktrees/intent-feedback-continuity:work-docs/PLAN-docs-release-sync.md
  - task: intent-feedback-continuity
    start: '2026-09-23T12:55:56.463716Z'
    source_refs:
    - worktree:/home/noel/harness-maker/.worktrees/intent-feedback-continuity:work-docs/RESEARCH-intent-feedback-continuity.md
    - worktree:/home/noel/harness-maker/.worktrees/intent-feedback-continuity:work-docs/PLAN-intent-feedback-continuity.md
  recovery:
    state: complete
    next_trigger: next_eligible_invocation
    authority: intent-feedback-continuity-policy-approval
  legacy_snapshot:
    activation: '2026-09-22T02:45:59.012195Z'
    members: []
    assessments: {}
    body_hash: 674dee56babcab41dda11b4f754ba6d88e7468d9170f5056fbdb56d98ab0d86d
  publication:
    base_blob: e6537294e82b26151718c112f53db36f57140620d54ab55308e873bcaca8a3df
    content_hash: 2e0c40750ca40bfcd2cf58cec1a18a0dbbdd2f1930775ab964a9f1f29376289b
    owner: intent_trial
---
## Trial

Activated at: 2026-09-22T02:45:59.012195Z
Collection: collecting
Outcome: pending
Enrolled: 2/3

| Order | Task | Start | Terminal | User assessment |
|---|---|---|---|---|
| 1 | docs-release-sync | 2026-09-22T03:39:48.368348Z | False | pending |
| 2 | intent-feedback-continuity | 2026-09-23T12:55:56.463716Z | False | pending |

<details><summary>Preserved trial history</summary>

<!-- intent-trial:history:start -->
# Real-task feedback continuity trial

## Trial

Repository: /home/noel/harness-maker
Activation: 2026-09-22T02:45:59.012195Z
Applied revision: c4423410a8cc287ff76d39cdf4a5ed217290e9e9
Collector: codex-thread-01a0c683-3cde-7f40-9d06-e871e86c6da4
Collection: collecting
Outcome: pending
Enrolled: 0/3

Authority: the user approved this repository's next three real task slugs,
retaining current record locations and separating implementation completion from
real-use assessment. The implementation is applied before this activation.
This administrative setup is not an enrolled task.

Only the named collector writes this authoritative base-root PLAN. Other task
agents keep source events in their own PLAN Feedback and report pending handoff.
They must not allocate a slot or merge a stale worktree copy. Ownership transfer
requires the former collector's explicit stop acknowledgment before the named
successor writes; no transfer is currently authorized.

| Order | Task slug / PLAN | Start / terminal times | Observation → update → decision evidence | Conversation evidence | User assessment |
|---|---|---|---|---|---|

No qualifying task has been enrolled. On each entry/resume and terminal exit,
reconcile the base .claude/observability/stage-spans.jsonl first-start interval
with task PLAN evidence. Enroll the next three distinct genuine starts strictly
after activation in start order. Arrival or completion order cannot select the
cohort. Incomplete or ambiguous preceding intervals remain pending.

Resume/rerun of a slug is one task. Keep failures, aborts and missing evidence.
Exclude world-intent-closed-loop (already started), this administrative setup,
and synthetic fixtures. Do not create work to fill the cohort. Preserve the
same three rows; no reset or replacement without a new user decision.

Collection stays collecting until all three enrolled tasks are terminal.
Outcome precedence: confirmed continuity failure → failed; otherwise a terminal
row lacking evidence → insufficient_evidence; otherwise incomplete enrollment
or assessment → pending; only three successful user assessments → passed.
New evidence can resolve insufficiency, never erase a confirmed failure.

The user owns each final assessment. A reminder to reconnect feedback is a
continuity failure. Ordinary approval questions and justified termination may
pass, including an aborted underlying task. No relevant observation or missing
trace cannot prove a successful cycle.

## Records

- [Trial SPEC](../specs/SPEC-world-intent-closed-loop-trial.md)
- [Implementation PLAN](PLAN-world-intent-closed-loop.md)
- [Implementation REVIEW](REVIEW-world-intent-closed-loop.md)
- [Intent](../intent/WORLD-INTENT-CLOSED-LOOP.md)
- [Metric definitions](../.claude/intent.yaml)
- [Measurement history](../.claude/intent/metrics.yaml)

## Feedback

Implementation completion does not establish intent attainment. The intent
remains active; the real-use metric is unmeasured. No trial verdict, measurement,
intent closure or user assessment is fabricated by activation.

## Activation verification

Local harness regenerated from the applied revision before activation. Generated
Codex execute includes native same-conversation advance; both hosts contain the
lazy workflow-feedback reference. Codex ledger smoke reports applicable=true,
degraded=false, entry_count=362. Implementation find-unjudged remains clear.
The post-update health scan reported two unrelated historical stale judgments
(SPEC-intent-world-model-objective-layer AC-017 and SPEC-workflow-loop-efficiency
AC-010); they are not re-certified by this implementation acceptance.
<!-- intent-trial:history:end -->
</details>
