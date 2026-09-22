---
type: plan
task_slug: world-intent-closed-loop-trial
status: planning
created: 2026-09-22
intent: WORLD-INTENT-CLOSED-LOOP
spec: "[[SPEC-world-intent-closed-loop-trial]]"
---
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
