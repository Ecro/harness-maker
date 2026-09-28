---
type: evidence
task_slug: intent-feedback-continuity
intent: WORLD-INTENT-CLOSED-LOOP
spec: "[[SPEC-intent-feedback-continuity]]"
created: 2026-09-24
---

# Intent feedback continuity execution evidence

## AC-009 — Session-independent native behavior

The captured isolated Codex run is in
`tests/fixtures/intent_feedback_continuity_native_observed.json`; the reproducible
runner is `tests/fixtures/intent_trial_native_runner.py.txt`. Session A wrote a
`trial_feedback` observation to `work-docs/RESEARCH-a.md` and exited. Before a
separate session B, status showed candidate `a` and an empty cohort. B entered
the ordinary execute stage without a repair reminder, called the supported
`hm intent --root <base> trial reconcile ...` path, and left the cohort `[a]`
with outcome `pending`. The recorded trial document retained the source event
and contained no invented decision. Removing the owning workflow trigger in the
control run left the same source available but the cohort empty; its captured
commands contain no reconcile call. Both host renderings include the supported
status/reconcile guidance. The fixture contains the protocol hash, command traces,
source bytes, before/after status and control status; replay assertions live in
`tests/integration/test_intent_trial_native_evidence.py`.

`tests/fixtures/intent_feedback_continuity_native_edge_observed.json` and its
runner capture three more native runs. At closeout, the ordinary procedure
retained a terminal source event and left assessment pending. With policy
revoked, the actor made no reconcile call and the canonical trial bytes stayed
unchanged (`authority_required`). With a registered but unavailable worktree,
it likewise made no reconcile call and reported `source_incomplete` with the
missing source path. These are isolated workflow trials, not evidence that the
three real field tasks passed.

## AC-010 — Existing field-trial recovery

The live canonical record is
`/home/noel/harness-maker/work-docs/PLAN-world-intent-closed-loop-trial.md`.
Before the repair, the preserved activation was
`2026-09-22T02:45:59.012195Z`, policy was `legacy_collector`, candidate starts
were `docs-release-sync` at `2026-09-22T03:39:48.368348Z` and
`intent-feedback-continuity` at `2026-09-23T12:55:56.463716Z`, and the cohort
was empty. The status reason was `policy_revision_required`. The prior prose,
collector identity and zero-member history are retained in the typed record's
`collector_provenance` and `legacy_snapshot` as well as in the original body.
The pre-apply status and dry run are in
`work-docs/evidence/intent-feedback-continuity/live-pre-status.json` and
`live-pre-dry-run.json`.

The user approved the session-independent mechanical collection policy in the
SPEC interview and explicitly accepted the bounded historical population and
order in `conversation:call_uUHsEHSHPszjtqCpeZFrOmE0`. Two typed decisions
record those authorities with IDs
`intent-feedback-continuity-policy-approval` and
`intent-feedback-continuity-historical-source-review`. The first changed the
policy to `intent-feedback-continuity-v1` and left the cohort empty pending
source review. The second bound the reviewed source inventory and cutoff while
preserving the empty cohort before reconciliation. Decision payloads and each
public operation's readback are in this evidence directory.

Applying `reconcile` through the public API committed the two reviewed task
members. An independent `status` readback confirmed the same activation, the
ordered cohort `[docs-release-sync, intent-feedback-continuity]`, collection
`collecting`, outcome `pending`, and no assessments. The first apply exposed a
worktree-path attribution bug in member `source_refs`: the second task's worktree
directory name matched its slug and captured unrelated files. The exact-artifact
fix and regression tests were added, then a second idempotent reconcile repaired
the live member refs. `live-source-ref-repair.json` and `live-post-status.json`
record that correction. The final refs point only to each member's own task
artifacts. The original trial prose was preserved byte-for-byte as a body
substring; neither the original activation nor the prior policy and intervention
history was reset.

The current task PLAN then recorded a typed observation about this execute-stage
repair. Its changed artifact hash did not reopen the already reviewed two-task
cohort: a further public reconcile was byte-idempotent, kept recovery `complete`,
and independent status readback showed the observation while outcome remained
`pending`. `live-final-replay.json` and the updated `live-post-status.json`
capture that post-edit check. Exact-slug and later-artifact-edit regressions
cover both the source-reference repair and the no-new-candidate replay path.

The field trial remains open at **2/3 enrolled**, with no user success/failure
assessment and no intent closure. The third real task must be discovered from a
genuine later start, with a typed start acknowledgment or separately accepted
source coverage. A terminal task still needs its observation trace and explicit
user assessment. The source inventory is bound to the reviewed historical
snapshot; later task-document edits do not retroactively change the two
committed starts. They require a new attributable event for further enrollment.
Implementation completion and these isolated native runs do not establish
field-trial success.

## Verification

The authorized extra Phase A.5 test review passed S1–S4, after a 73-failure
measured RED gate on the absent production module. Ruff and strict mypy passed;
the full CI-selected pytest suite passed with seven loadfile workers. The source
reference defect was then covered by exact-slug, existing-member repair, and
later-document-edit regressions, all passing with strict mypy and Ruff. The machine SPEC has eight
mechanical AC test bindings, passes block-strict validation, and retains its
approved state. Native evidence checks passed five cases. No final judgment for
the real three-task trial was made, and this execute stage made no commit.
