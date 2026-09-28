---
type: spec
task_slug: intent-feedback-continuity
status: approved
created: 2026-09-23
tags: [harness-maker, spec, python, intent, continuity, concurrency]
test_framework: pytest
tier: 2
interview_rounds: 2
intent: WORLD-INTENT-CLOSED-LOOP
research_doc: "[[RESEARCH-intent-feedback-continuity]]"
summary: "Recover trial collection across sessions while preserving evidence, cohort and human judgment."
---

# Session-independent intent feedback collection

## 🎯 Intent

The active real-task trial reports zero enrolled tasks although docs-release-sync has execution, observation and decision evidence. Its named-collector rule prevents subsequent sessions from reconciling that evidence without the previous session's acknowledgment. This feature makes collection resumable from repository evidence while preserving the user's authority over final judgments and intent closure.

The user selected reusable minimal collection under WORLD-INTENT-CLOSED-LOOP, automatic mechanical enrollment/update under approved trial rules, and recovery of the existing trial without erasing intervention history. Implementation completion does not demonstrate success of that intent or its three-task field trial.

## 🌅 Outcomes

- A user can distinguish no observed work, evidence awaiting reconciliation, evidence gaps, and a complete trace awaiting user assessment.
- On the next eligible stage entry/resume or closeout, any session can reconcile the same active trial without contacting a prior collector or asking again for an already authorized mechanical update.
- Replays, concurrent sessions and a killed writer do not duplicate enrollment, lose committed decisions or leave a permanently owned trial.
- Existing activation, eligible start chronology, recorded failures, user judgments and intervention history survive recovery. Missing data never becomes a successful outcome.
- A repository without an activated trial incurs no trial record, trial write or trial-specific user question.

Progress is bounded by invocation, not elapsed time: absent an eligible invocation, no background progress is promised. A blocked write or uncertain source produces an explicit reason; it does not stop independent authorized task work.

## 📋 In-Scope Scenarios

### S1: Discover and resume collection from a different session

**Given** an activated trial with approved mechanical-collection authority, durable task evidence, and no unresolved source or storage conflict.
**When** a different session enters/resumes a workflow stage or closes out work.
**Then** it discovers and reconciles eligible evidence during that invocation, without a previous collector's acknowledgment or a user reminder.
**And** a read-only query reports candidates separately from committed membership, trace evidence and user assessment; lack of an execution PLAN does not hide a research/spec task.

### S2: Preserve cohort and judgments through retries, concurrency and process loss

**Given** a trial and two sessions processing overlapping task evidence.
**When** processing is replayed, sessions write concurrently, or one writer is killed before or after its commit.
**Then** the next invocation observes either the prior valid state or the complete committed update and can continue without the failed session.
**And** committed membership and user assessments are retained, duplicate operations have no additional effect, and conflicting operations report a conflict without overwriting committed state.

### S3: Expose incomplete evidence and respect judgment authority

**Given** missing/contradictory start evidence, stale worktree records, a terminal task with missing trace, or absent user assessment.
**When** status is queried or reconciliation runs.
**Then** it reports the specific pending/conflict reason and the affected source/task, never treating missing evidence as zero work or success.
**And** no automatic action changes the final user assessment, intent approval, intent lifecycle, project metrics, trial activation, trial scope or cohort reset policy.

### S4: Recover the existing trial without rewriting its history

**Given** the existing world-intent-closed-loop-trial activation and its old named-collector policy.
**When** the user-approved collection-policy revision is applied and recovery runs.
**Then** a reviewable preview identifies the prior policy, retained activation, known candidates, pending evidence and intervention history before the authorized apply.
**And** replaying recovery does not reset the trial, replace existing members, assert user judgments or present repair-assisted work as proof of uninterrupted continuity.

## 🚫 Non-Goals

- New intents, automatic success/failure assessment, intent closure or independent new work.
- A scheduler, daemon, collector heartbeat/lease, distributed coordination service, external dependency or new general-purpose event store.
- Replacing ordinary workflow/autopilot authority, task worktree isolation or merge gates.
- Guaranteeing complete historical telemetry from best-effort logs; fabricating unavailable conversation traces.
- Requiring three future real tasks to finish before this implementation can land; the existing trial remains a separate attainment requirement.
- Reworking all intent/metric writers or changing unrelated approval workflows.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest, including real subprocess and filesystem integration tests | Existing Python project; concurrency cannot be proved by prompt text |
| Scope | Local repository and its registered worktrees; existing supported host procedures | No multi-host coordination requirement |
| Invocation budget | One bounded collection attempt per relevant stage entry/resume and closeout; material observations may invoke one additional attempt when relevant evidence changes; no idle polling | Prevent persistent control machinery |
| Write wait | At most 5 seconds waiting for a writer lock per invocation, then explicit pending/retry-at-next-trigger status | Proposed responsiveness bound; no LLM call, human wait or full task under the lock |
| Security/authority | Approval of an activated trial's collection policy authorizes mechanical updates only; final user assessment requires explicit user evidence | Round 1 user selection |
| Compatibility | Read existing trial PLANs and task documents without rewriting on query; old policy remains effective until explicitly revised | Historical approvals cannot be inferred from installing code |
| Storage | Existing PLAN is the durable trial record; versioned typed trial metadata and linked evidence, not a parallel authoritative database | Existing artifact conventions and recoverable state |
| Platform | Writes require proven mutual exclusion and atomic publication on the current filesystem; unsupported environments remain readable and refuse writes with a reason | No unlocked fallback may claim safety |
| Crash guarantee | Abrupt writer-process termination on a functioning local filesystem; no promise of power-loss recovery or network-filesystem semantics | Keep guarantees testable and bounded |
| Testing quality | Tier 2, mutation threshold 70 for changed collection Python code; PLAN binds the final coverage set before implementation | Independent tests must exercise failures of exclusion, deduplication and authority |

### Proposed public and durable contract

The DRI accepted these contracts after Round 2 and the independent-review repairs.

Public commands (existing intent commands retain their behavior):

- `hm intent trial status <trial-id> --json`: read-only, including legacy records.
- `hm intent trial reconcile <trial-id> --dry-run --json`: read-only proposed mechanical diff.
- `hm intent trial reconcile <trial-id> --json`: apply only under the activated trial's recorded policy authority; unchanged replay succeeds without a new write.
- `hm intent trial record-decision <trial-id> --file <decision-file> --expected-revision <digest> --json`: persist an explicitly supplied user policy decision, assessment or bounded source-review disposition. It cannot infer a user decision from agent narrative. Decision identity, actor, time, evidence references, kind and payload are required; repeated identical identity/payload is a no-op and conflicting reuse is rejected. The decision file is data, never executable content.
- Root selection follows the existing CLI's root option. Trial ID is a validated slug resolving a trial PLAN under the base repository, never an arbitrary path.

Status JSON must carry a schema version, trial ID, activation/policy revision, source snapshot/provenance, discovered candidate IDs, committed cohort IDs, collection state, outcome state, actionable reasons and next action. A legitimate absent trial differs from invalid/unreadable trial input. Workflow activation discovery is independent of whether an intent exists. No-trial workflow checks return a no-op without prompts.

The trial PLAN remains authoritative for activation, collection authority, frozen membership and user judgments. Proposed versioned metadata belongs in its frontmatter; the visible Trial section is a derived presentation of that metadata after migration. Authoritative decisions must never exist only in the derived section. Existing prose and its historical values remain available in a preserved migration snapshot/reference. Human assessment is an explicit dated user decision with evidence references; agent narrative alone is not a human decision. A later invocation may derive outcome from that recorded decision, never invent it. After an explicit user answer, the workflow records that exact decision through record-decision and reads it back; merely asking or quoting the answer does not complete persistence. Policy revocation and assessment use the same protected writer as collection. A policy replacement decision may be recorded against the legacy trial revision without requiring the former collector's acknowledgment: the explicit user decision is the replacement authority. Direct edits to a derived Trial table are not silently interpreted as new assessments; report the discrepancy and route an explicit decision through the protected writer.

Per-task structured evidence remains attached to its existing stage artifact (RESEARCH/SPEC before PLAN; PLAN thereafter), with stable IDs and provenance. A move/link to PLAN must not duplicate the event. Exact key layout and parser internals are PLAN decisions; required semantics are trial/task/event identity, first-start claim and sources, observation/terminal evidence references, source revision/content identity, and intervention markers. Sessions are provenance, not ownership or deduplication identity.

Source discovery covers the base start ledger, trial references and registered task worktrees/landed artifacts. It does not scan arbitrary directories. Divergent copies retain provenance and require a documented authoritative relation; newest filesystem mtime alone is not such a relation. A snapshot identifies its sources and completeness limitations. Revalidate relevant source/destination identities before committing a decision; a changed input returns a conflict or a recomputed bounded attempt, never an update based on stale contents.

Automatic cohort commitment uses a bounded coverage record, not an assumption that readable logs are complete. It names an interval from activation or the previous accepted boundary through an observed cutoff, the enumerated base ledger/trial references/registered worktrees/landed task artifacts, their revision or content identities, ordered task starts and exclusions, and unresolved gaps. Commitment is allowed only when every inventoried source is readable, the identities still match at commit, each eligible task has an attributable first start, ordering is unambiguous, and the preceding interval has been accepted. For newly observed intervals, structured stage-entry acknowledgments and source reconciliation provide that acceptance only when no source has missing/contradictory starts or reported collection failure. For legacy intervals not covered by acknowledgments, a user source-review decision explicitly accepts the enumerated population and exclusions through the stated cutoff; mere readability or silence cannot accept it. That decision attests only to the bounded reviewed evidence, not universal historical completeness. An unresolved decision remains provisional; a decision resolving specified gaps enables the next invocation to enroll the eligible prefix. New sources or changed identities invalidate the affected provisional coverage until reviewed/reconciled again. Later evidence contradicting a committed population raises an order/source conflict without replacing members.

Raw-source acceptance fixtures must distinguish: readable legacy logs without source-review (provisional); the same logs with a matching accepted source-review and attributed starts (enroll); review with unresolved gaps (provisional); and post-review source drift (conflict). Ambiguous equal-time starts require independent order evidence or an explicit source-review resolution. Missing timestamps may be resolved only with cited evidence, never by substituting ingestion time. Future active-trial stage entry preserves a structured start acknowledgment or visibly reports collection failure while leaving independent task work possible. PLAN selects the reconciliation algorithm, not the acceptance boundary.

All supported writers of the tracked base trial record must cooperate, including decision recording, collection, task landing and supported legacy finalize/stash/restore paths. A read during a transient stash/restore must not be interpreted as missing historical work. Writes overlapping these operations must serialize or return a bounded conflict without losing evidence or judgments. The supported task completion/landing path must persist authorized trial deltas in Git through the existing approved commit workflow, without silently committing unrelated dirt or bypassing merge gates. Mechanical trial changes must not leave their own task permanently unable to land because the base was dirtied by collection. Historical task copies cannot overwrite canonical trial changes on landing. Unsupported arbitrary external edits/Git operations are outside the synchronization guarantee; detect observable conflicts instead of promising universal exclusion. PLAN chooses lock order and integration mechanics; acceptance uses actual supported landing/finalize paths, not only mocked collector writers.

Outcome precedence is retained: confirmed user-assessed continuity failure -> failed; otherwise a terminal member lacking required evidence -> insufficient_evidence; otherwise incomplete membership, terminality or assessment -> pending; passed only for three successful user assessments with required evidence. Collection completes only when all three committed members have terminal dispositions. Stage completion alone is not whole-task termination. Observed underlying task failure/abort does not automatically decide continuity success/failure.

Migration of the active trial must retain its original activation and historical named collector as provenance while recording the explicitly approved policy replacement. Policy revision does not require the former collector to reappear. This research/repair task remains visible as intervention-related evidence; eligibility is evaluated under the existing next-three rule, never silently excluded to improve results. The user determines continuity attribution and final verdict. A legacy destination conflict or missing migration authority yields a preview/pending reason, not a destructive conversion.

## 🔒 Irreversible Decisions

The DRI explicitly accepted all four decisions at interview close; acceptance is stamped in the machine companion.

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add versioned typed trial metadata to the existing trial PLAN; task evidence remains attached to existing stage artifacts, with one authoritative source per fact | schema/file format/storage layout | Persisted records must be readable across sessions and versions |
| IRR-002 | Expose `hm intent trial status`, dry-run/apply `hm intent trial reconcile`, and explicitly authorized `hm intent trial record-decision`, with versioned JSON | public API/CLI contract | Workflow procedures and user scripts depend on the command contract |
| IRR-003 | Replace named-session ownership with activated-policy authorization for mechanical collection only; preserve explicit human judgment and other existing approval boundaries | security/permission boundary | Changes which sessions may write shared trial state |
| IRR-004 | Migrate the current trial in place with retained activation, cohort/assessment history and intervention evidence; no automatic reset | data migration | History must survive replacement of the old policy and representation |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit, integration, captured native workflow execution | `test_session_independent_discovery`, `test_next_session_reconciles` and AC-009 rubric |
| S2 | property, subprocess integration | `test_replay_invariance`, `test_concurrent_commit`, `test_writer_kill_recovery` |
| S3 | golden cases, property, integration | `test_pending_reason_matrix`, `test_authority_preservation`, `test_stale_source_conflict` |
| S4 | integration, golden migration fixture | `test_legacy_trial_recovery`, `test_migration_replay_and_history` |

The user confirmed the oracle package in Round 2. Golden cases derive from the old approved trial rules and Round 1 choices, not implementation outputs. Property relations express those requirements independent of algorithm. Test IDs remain pending until execute collects real tests; the names above describe intended coverage. Review refinements below add adversarial inputs within the same confirmed oracle categories.

### AC-001: Read-only status distinguishes work from enrollment

With one eligible observed start `a`, accepted matching bounded coverage, evidence present and an empty cohort, report candidate `[a]`, committed `[]`, and `awaiting_reconciliation`; do not report no work. With no starts and an accepted empty bounded snapshot, report `no_candidates`. Missing/unreadable sources instead report `source_incomplete`; readable legacy sources without accepted population review report `source_review_required`. Status and dry-run leave every authoritative artifact byte-identical. A legacy collector policy yields `policy_revision_required` for an attempted mechanical write while still allowing discovery and an explicitly user-authorized policy decision.

Oracle: independent golden table plus before/after artifact hashes, grounded in the observed docs-release-sync backlog and existing no-write query contract.

### AC-002: Mechanical progress survives session replacement

Given active collection authority, accepted matching bounded coverage and unambiguous start evidence for task `a`, available storage and no competing writer, session B's next eligible invocation enrolls/updates `a` after session A ends. It requires neither A's acknowledgment nor another user confirmation. A legacy readable source set remains provisional until its population review is recorded; the same source set becomes enrollable on the next invocation after that explicit review resolves its gaps. If there is no active trial, the same workflow produces no trial write or question. Both RESEARCH/SPEC-only and PLAN-backed evidence are discoverable; an intermediate handoff does not mark the task terminal.

Oracle: independently authored golden sessions A/B with fixed inputs and expected membership; session names and missing old-session runtime are varied without changing the expected result.

### AC-003: Replay and evidence reordering preserve identity

Within the same fixed accepted source snapshot with unique first-start ordering, duplicating events, replaying reconciliation, resuming the same task, or permuting snapshot enumeration produces the same cohort and assessments as processing its deduplicated contents. This property does not equate a sequence of partially available snapshots with one complete snapshot. Partial arrivals without accepted coverage remain provisional; previously unavailable earlier evidence after commitment follows AC-005 and never replaces a member silently. Duplicate operations cause no additional authoritative change. Same identity with conflicting payload yields a conflict, not overwrite. Session ID changes do not change task identity.

Oracle: property over task/event IDs, source permutations and repeat counts; expected relation follows from the approved one-task-one-slot rule rather than a second implementation of the collector.

### AC-004: Concurrent and interrupted writes preserve committed state

Two processes applying independent permitted updates retain both effects with no duplicate slots or lost user judgment. Killing a process before or after atomic publication leaves a valid prior or complete next document; a subsequent process can read and apply remaining updates without a persistent session owner. A stale expected destination revision is rejected. Unsupported exclusion/atomic publication refuses a write; contention yields an explicit reason within the 5-second wait budget. No LLM/human wait occurs while holding the write exclusion.

The same preservation holds when one writer records a new explicit user assessment or policy revocation. Exercise actual supported task-land and legacy finalize/stash/restore overlap: updates either serialize and survive in the landed history, or return a conflict without corruption. In the uncontended authorized case, collection's own tracked delta is persistable through normal landing and does not cause an indefinite base-dirty refusal. The tests must read the final Git/document state, including a stale task copy, rather than assume collector-only locking is sufficient.

Oracle: conservation and linearizable-outcome property; subprocess synchronization controls overlap and termination. The oracle inspects independently read durable documents, not the writer's success message. Power-loss semantics are excluded.

### AC-005: Uncertain sources cannot silently change membership

Missing or contradictory first-start evidence, an inaccessible registered source, divergent base/worktree facts, a changed input snapshot or ambiguous equal-time order leaves dependent membership provisional and names the reason/source. Earlier late evidence cannot silently displace a committed member. Failures and aborts remain eligible under the existing rule. A completed later task is not preferred over an earlier incomplete task. A copied worktree trial document cannot overwrite the authoritative base trial.

Oracle: hardcoded adversarial chronology and expected pending/conflict outputs, authored from the approved start-order and retain-failures rules before implementation.

### AC-006: Collection cannot manufacture user judgment

Reconciliation may update mechanical evidence and derive state from an existing explicit user assessment. It leaves assessment fields, intent lifecycle/approval, metric values and trial activation unchanged. No assessment produces pending; terminal missing evidence produces insufficient_evidence; one explicit continuity failure produces failed even with collection still open; three successful user assessments with complete terminal evidence produce passed. New evidence may resolve insufficient_evidence but cannot erase a confirmed failure. Policy absence/revocation prevents writes.

The supported decision-recording path persists a newly supplied explicit user assessment, policy approval/revocation or source review with provenance and expected-revision protection, then returns a readback. The next session sees that exact decision. A stale revision or same decision ID with different payload is rejected; an identical replay changes nothing. No user decision/consent means no decision write. Policy revocation is ordered with collection: an update committed before revocation remains; one attempting commit after revocation cannot use the revoked authority.

Oracle: golden precedence table and preservation property grounded in the existing trial SPEC plus the user's authority choice.

### AC-007: Migration preserves history and is reviewable

A dry-run over a fixed legacy trial fixture shows the named-owner policy replacement and preserves activation, original cohort, failures, judgments, evidence links and collector provenance. Apply requires recorded authority for this policy revision and does not require old-session acknowledgment. Applying it twice has the same authoritative result as once. Missing authority or conflicting legacy/typed records produces a reason without changes. Recovery of the repository's current trial retains the docs-release-sync candidate and marks this repair/user intervention without awarding a successful verdict or resetting the cohort.

Oracle: an immutable legacy input fixture transcribed from the pre-change trial/task records, retained field expectations and user-selected no-reset invariant. Actual recovery evidence is separate from fixture evidence; no test changes the live trial.

### AC-008: Status exposes a next action without expanding work

Each pending reason identifies its affected source/task and a supported action: collect missing evidence, reconcile under existing authority, resolve order/source conflict, approve a policy change, wait for a known observation window, or request the user's assessment. No active trial is a no-op. The workflow continues independent authorized work when collection is pending; it does not create tasks, reset a trial, repeat a declined approval or infer authority from a status read.

Oracle: pre-authored golden reason/action mapping and authority-preservation assertions; missing-source and no-trial cases are distinct.

### AC-009: Workflow integration demonstrates unprompted recovery

Captured native workflow execution must demonstrate that session A leaves durable evidence and ends, and a separate session B entering the ordinary stage procedure discovers and reconciles it without a prompt instructing B to repair the trial. Cover entry/resume and closeout, missing execution PLAN, denied/revoked collection authority, unavailable source and intermediate handoff. A control removing the owning collection trigger must fail the same recovery assertion in the bounded fixture environment. Render the procedures for supported hosts and demonstrate callable local paths; text presence alone is insufficient. This finite protocol evidence does not certify the real three-task trial or ROI.

Oracle: the separately authored `intent_feedback_continuity` rubric, bound to generated procedure and captured execution evidence; expectations are derived from this interview and the original intent before implementation.

### AC-010: Existing trial recovery is reported separately from attainment

Implementation handoff includes the current trial's recovery preview/apply evidence, policy revision reference, candidate/committed counts, retained intervention history, remaining evidence/assessment gaps and the next supported action. A pending user assessment remains pending. It never labels implementation tests or this repair's successful execution as three successful real tasks.

Track implementation completion, live recovery (`pending`, `blocked`, `complete`) and trial outcome separately. Live recovery is complete only after authorized application and a subsequent independent status read confirm the retained activation/history, adopted policy and eligible membership/evidence. If blocked, retain a discoverable recovery obligation in the existing task artifact linked to the trial: operation ID, authority reference, exact blocker, required evidence/decision and next eligible entry/resume/closeout trigger. Responsibility belongs to the next authorized workflow invocation, not a named session. That invocation discovers the obligation even while the trial retains its legacy policy; when prerequisites clear it applies and reads back the recovery without a repair reminder. If storage prevents saving even the obligation, report that failure explicitly rather than claiming persistence. A blocked report is not completion of the user's recovery request; it may permit implementation landing while recovery remains visibly outstanding. Verify both the initial blocked state and the resumed apply/readback, without waiting for three trial outcomes.

Oracle: `intent_feedback_continuity` rubric over the task's recovery evidence and user-visible report. Existing trial rules and the user's keep-and-recover selection determine the expected distinction.

## ❓ Open Questions

Resolved in Round 1: reusable minimal scope under WORLD-INTENT-CLOSED-LOOP; automatic mechanical registration/update with user-owned final judgment; retain and recover the existing trial and intervention history.

No unresolved SPEC decisions. The user accepted the per-AC golden/property/rubric oracle package and then explicitly approved the repaired SPEC, including all four irreversible contracts, protected decision recording, bounded source review, the 5-second write-wait/unsupported-write behavior and resumable recovery. Legacy incomplete-start attribution remains evidence-dependent during execution; no fictitious source completeness or success verdict is authorized.

## 🔍 Refinement Decisions

- Round 1 (2026-09-23): user selected all three recommended options for purpose/scope, mechanical authority and existing-trial recovery. Final acceptance was subsequently provided after the review repairs.
- Round 2: user confirmed the oracle package. Independent review identified missing bounded coverage, user-decision persistence, real landing compatibility, snapshot/partial-arrival distinction and resumable live recovery; those are now explicit acceptance requirements. No new external dependency or daemon was introduced.
- Final acceptance: the user selected "Approve this SPEC and end interview" after reviewing the repaired contract. Accepted constraints include pytest, tier 2, no external dependency/daemon, unchanged artifact directories, conditional local-filesystem writes and explicit read-only status.
- The task is non-trivial and changes public/durable/authority contracts; Step 0 skip does not apply. Independent spec-validator dispatch is required once the draft is structurally checked.
- Research and current trial records provide knowledge context. The active intent has valid approval and an unmeasured primary metric. No intent mutation, metric measurement, trial enrollment or policy migration occurred during this SPEC stage.

### Feedback disposition

The research and this SPEC retain the backlog evidence and the current task's original research start. The old named-collector policy remains the live rule until an approved replacement is applied. No execution PLAN exists yet; transfer this disposition to PLAN Feedback when execute creates it. Stage completion is not a terminal trial task event. The DRI has explicitly accepted the concrete SPEC. The next action is the user-initiated execute stage; this acceptance does not itself apply a live trial migration or establish trial success.

## 🔎 Spec Validation

- Initial schema/cross-validation passed at block strictness; heuristic quality 92/100. This score is not behavioral validation.
- Second opinion: `model: codex`, `status: invoked`, `reason: null`. Findings 54223181af19ab84, 626ab922e4305162, 8397c59da39119de, 994bb22b41a59895 and e4ed01c95422d94b were accepted and addressed in the contract and AC-001 through AC-010.
- Single-pass spec-validator: `overall_assessment: MAJOR_REVISION`, with one critical missing-decision-persistence finding and four warnings matching the issues above. Circular-oracle, irreversible-decision and scope-boundary categories were clear. This records the original advisory verdict; edits have not been independently re-reviewed. No second dispatch was made.
- Repairs: explicit bounded source population review and raw-source cases; protected decision persistence/readback; actual landing/finalize preservation and Git persistence; snapshot-only permutation property; discoverable blocked recovery followed by actual apply/readback after prerequisites clear.
- Post-repair schema, six-rule cross-validation and block-strictness quality checks passed (92/100). This task's single spec-validator ledger run is coherent. The repository-wide ledger reports ten historical incoherent runs outside this task; those records were not changed or counted as this task's validation success.
