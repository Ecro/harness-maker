---
type: research
task_slug: intent-feedback-continuity
status: complete
created: 2026-09-23
tags: [harness-maker, research, python, intent, feedback, concurrency, field-validation]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://kubernetes.io/docs/concepts/architecture/controller/
  - https://kubernetes.io/docs/concepts/architecture/leases/
  - https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/
  - https://man7.org/linux/man-pages/man2/flock.2.html
  - https://www.sqlite.org/atomiccommit.html
related_docs:
  - "[[PLAN-world-intent-closed-loop-trial]]"
  - "[[SPEC-world-intent-closed-loop-trial]]"
  - "[[PLAN-world-intent-closed-loop]]"
  - "[[SPEC-world-intent-closed-loop]]"
  - "[[REVIEW-world-intent-closed-loop]]"
  - "[[EVIDENCE-world-intent-closed-loop]]"
  - "[[PLAN-docs-release-sync]]"
  - "[[RESEARCH-cell-dev-future-and-intent-layer-fit]]"
summary: "Replace session-owned collection with rebuildable status; serialize only durable decisions."
---

# Research: intent feedback continuity across sessions

## 🎯 Recommended Direction

**Use session-independent, evidence-derived reconciliation at existing workflow boundaries; keep human assessment explicit and serialize only the durable writes that remain.** Start with a read-only status projection over existing records. Do not start by building a collector service, heartbeat system, general event store, or new database.

The primary benefit is user-facing: a subsequent session can discover unfinished feedback work without the user reconstructing the handoff. The present blocker is an unnecessarily persistent writing monopoly, not a demonstrated need for a continuously running coordinator. Separate discovery and aggregation from cohort commitment and human judgment. Existing stage hooks can invoke a small deterministic helper; the agent handles semantic evidence interpretation and authorized decisions. This is an informational recommendation; SPEC and PLAN must settle the contract before implementation.

### Observed problem and limits

- The authoritative trial PLAN says `collecting`, `pending`, `Enrolled: 0/3`. Activation is `2026-09-22T02:45:59.012195Z`. It names one collector session and requires that session's explicit stop acknowledgment for transfer. See [trial PLAN](../../../work-docs/PLAN-world-intent-closed-loop-trial.md), Trial section.
- The base stage ledger has a first start for `docs-release-sync` at `2026-09-22T03:39:48.368348Z`. Its PLAN contains wrapup evidence, measurement, an explicit keep-intent-open decision, and repeated shared-trial-update-pending entries. Its final paragraph attributes pending enrollment to the named collector rule. See [task evidence](../../../work-docs/PLAN-docs-release-sync.md), Feedback section.
- Thus **registered zero is not observed-work zero**. There is at least one candidate with evidence awaiting reconciliation, not a verified successful trial row. The old collector's actual runtime state is unknown; absence of updates does not prove it is dead.
- This research preflight added `intent-feedback-continuity` at `2026-09-23T12:55:56.463716Z`. A read-only scan found those two distinct post-activation first starts and zero malformed JSON/time rows. This does not prove complete telemetry or eligibility. No trial slots were assigned.
- The current intent metric remains `never_measured`; the intent is active with valid approval. The confirmed gap is shared collection/assessment continuity. It does not establish failure of every within-task feedback connection or demonstrate a productivity regression.
- The user's questions in this conversation exposed the backlog. Preserve that intervention as evidence for assessment; neither silently count it as success nor automatically declare a particular trial row failed without attribution and user judgment.

### Scope

In scope: evidence discovery across task worktrees/sessions; honest backlog status; recoverable aggregation; cohort integrity; human assessment; migration of the present stuck trial; tests for continued progress after session/process loss.

Out of scope: autonomous new goals, automatic semantic success judgment, global workflow rewrite, multi-host distributed coordination, background services, changing intent approval boundaries, or proving the entire intent layer's return on investment from three tasks.

## 🔍 Refinement Decisions

Discovery lenses: **user workflow first**, then technical architecture and concurrency/recovery risk. No deep interview: the preceding conversation already defines the failure and desired outcome. Research is the requested stage; autopilot was scoped to `research` only, with no authorization inferred for implementation.

The local user-workflow source is the actual docs-release-sync handoff history, rather than generic productivity claims. Existing Obsidian reference/project searches for `intent collector feedback` returned no matches. No reference folders are configured. External sources establish mechanisms, not evidence that those mechanisms improve this harness's real outcomes.

Relevant retrieved memory anchors, treated as historical leads rather than current implementation proof:

1. `[wiki:architecture] world-intent-closed-loop`: feedback hooks and single-collector trial are separate from attainment.
2. `[wiki:architecture] per-session-marker-scoping`: session claim is not reliable runtime liveness; checked against current worktree code.
3. `[fail:process] peer-lands-mid-task-shared-files`: stale task copies can overwrite concurrent work.
4. `[fail:test] assertion-invariant-over-named-dimension`: exercise behavior and negative controls, not instruction text alone.
5. `[fail:design] fix-introduced-defect-passes-all-gates`: a safety repair can introduce a different failure while tests stay green.
6. `[fail:test] snapshot-regen-inside-worktree`: validate actual generated behavior/population before trusting fixtures.

### Local capability × user artifact

| Existing capability | Existing user artifact | Reuse and gap |
|---|---|---|
| Stage preflight emits task start | Base `.claude/observability/stage-spans.jsonl` | Discover candidate chronology; emission is best-effort, not a completeness guarantee |
| Per-task feedback | `work-docs/PLAN-*.md` | Preserve observations, decisions and authority; prose is not a trustworthy deterministic outcome oracle |
| Trial activation and cohort policy | Trial PLAN and SPEC | Keep policy and stable cohort visible; remove dependence on a conversation's survival through an approved revision |
| Intent status | `intent/`, `.claude/intent.yaml`, metrics history | Keep task completion separate from attainment; expose collection lag without inventing measurements |
| Git worktree discovery and base-root resolution | Registered worktrees plus landed task docs | Include unlanded evidence with provenance; do not merge whole stale trial copies |
| File locking and atomic replacement | `io_utils.py`, worktree merge fence | Reuse design cautiously; current general RMW lock has unlocked fallback behavior |

## 🛠️ Approaches Found

### A. Retain manual collection with explicit operator recovery

| Field | Assessment |
|---|---|
| Assumption | This is only a one-off three-task trial; further automation would not repay itself |
| Evidence | Three rows are small; existing task evidence is already available. Current rule blocks transfer without the old collector, so a user-authorized policy amendment is necessary |
| Trade-off | Lowest implementation cost; user must restore and operate collection, undermining the intended reduction in reminders |
| Compatibility | High after explicit policy amendment; no new storage |
| Risk | Low data-change risk, medium recurring workflow risk |

This is a legitimate immediate recovery option, not a demonstration that automatic continuity works. Record the manual intervention and original pending interval. Do not relabel recovery as an uninterrupted successful trial. Prefer A if the trial will end permanently and there is no recurring shared-feedback need.

### B. Rebuildable status and short serialized decisions — recommended

| Field | Assessment |
|---|---|
| Assumption | Sessions share a local repository; existing stage boundaries recur and artifacts survive sessions |
| Evidence | Base-root start ledger and task Feedback already exist; controller reconciliation [S1] supplies a recovery pattern; explicit operation identity [S2] supports replay without duplication |
| Trade-off | Small parser/reconciler and structured metadata contract; no progress while no eligible invocation runs |
| Compatibility | High for existing artifact paths; structured trial fields and changed collection authority need approval/specification |
| Risk | Medium: source completeness, cross-worktree snapshots, platform locking and accidental overwrite require tests |

Proposed operation, with names illustrative rather than a locked CLI design:

1. Resolve the base repository using the existing resolver. Read trial activation/policy and source references. If no trial is active, return without prompts or writes.
2. Build a **read-only view** of discovered starts, provisional candidate order, available terminal evidence, finalized cohort and user assessments. Distinguish `no_candidates`, `awaiting_evidence`, `awaiting_reconciliation`, `awaiting_user_assessment`, and `collection_complete` as derived reasons, not necessarily a new lifecycle enum.
3. Preserve source provenance: repository/task identity, source path and revision/content fingerprint, observation time, ingestion time if available, and evidence reference. Do not parse arbitrary prose into a claimed human verdict. Start with one small typed block inside existing task/trial artifacts if needed; avoid a parallel truth store.
4. Any authorized session may invoke reconciliation. Discovery requires no collector identity or durable write. A durable cohort decision or recorded assessment is applied by a deterministic writer in a brief repository-shared critical section, with the current destination re-read and expected revision validated. Preserve human-authored sections and reject conflicts.
5. Retry by stable trial/task/operation identity, never session ID. Repeated processing has no extra effect; the same operation identity with different contents is a conflict. Recompute the display from authoritative facts rather than incrementing counters.
6. Trigger at existing stage entry/resume and closeout; use material-observation hooks only when relevant state changes. A status read can reveal pending work but must remain read-only. No daemon or repeated idle polling. With valid evidence and available storage, the **next eligible invocation** must discover the backlog regardless of the previous session.

The controller pattern supports recalculating from observed state instead of depending on one remembered handoff; adopting that principle does not require Kubernetes or a continuously running service [S1]. This architecture is an inference for this repository, not a result established by that source.

#### Preserve the hard boundaries

- **Discovery is not enrollment; enrollment is not assessment.** Existing user approval of a trial does not automatically authorize arbitrary intent/metric changes. The revised collection policy must explicitly authorize its mechanical writes once; avoid asking on every identical replay.
- The committed cohort and user verdict are durable decisions, not disposable projections. Keep failures and aborts. A later earlier-start record must raise an order conflict, not silently replace a committed member.
- `stage_spans` cannot prove that no start is missing. Reconcile known worktree/task evidence and report completeness unknown when sources disagree. Empty/missing logs are not zero work. New trial registration may need a stronger persisted start acknowledgment; SPEC must decide without making optional telemetry a universal workflow gate.
- Before PLAN exists, use current RESEARCH/SPEC evidence as the existing procedure permits. Do not create a fake execution PLAN solely to satisfy collection.
- Include only explicitly discovered/registered local worktrees; keep source identity when landed and unlanded versions differ. Do not pick an arbitrary newest file or last writer.
- A lock coordinates cooperating writers; it is not permission, nor protection against arbitrary concurrent hand edits. Revision checks and explicit conflict reporting remain necessary.
- Never hold a write lock during an LLM call, interview, subprocess measurement or whole task. Under normal local `flock` semantics, the lock ends when all corresponding file descriptors close [S3]. This is a process-scoped critical section, not a session lease.
- `io_utils.rmw_lock` currently continues unlocked on missing `fcntl` and selected unsupported-filesystem errors. It cannot be reused unchanged to promise cross-platform exclusion. The merge fence has a separate fallback mechanism, but extracting/reusing it requires focused review. Unsupported writes must return a visible pending reason, not silently proceed.
- Atomic replacement alone prevents partial-file visibility, not lost read-modify-write updates. Do not claim power-loss durability merely because `os.replace` is used. If the requirement grows to durable multi-record transactions, SQLite becomes a concrete alternative [S5], not a default dependency for this three-row problem.

#### Honest migration and validation

First show a dry-run reconciliation of the existing activation, docs-release-sync evidence and this research's start. Preserve the current record unchanged until the policy is revised. Retain original timestamps, reminders, pending intervals and any failures. Do not reset the existing cohort or silently exclude this repair task because it would be inconvenient. Explicitly decide its eligibility and label it as intervention-related; it cannot establish unprompted continuity merely because the repair eventually works.

Minimum behavioral acceptance candidates:

| Case | Required observable result |
|---|---|
| Session A exits after recording task evidence; session B resumes | B discovers and processes eligible backlog without A's acknowledgment or a user reminder |
| Writer killed before/after commit | Next invocation recovers; no partial authoritative record or duplicate operation |
| Two sessions reconcile concurrently | Same cohort and retained assessments; no lost update |
| Repeated invocation and same slug resume | Same membership and equivalent status |
| Late earlier start or missing start source | Visible provisional/order conflict; no silent cohort replacement |
| Base plus stale/unlanded worktree copies | Correct provenance, no overwrite from stale trial copies |
| No active trial / unsupported locking / read-only query | No mutation; explicit reason when a requested write cannot run |
| Aborted work, missing conversations, real continuity failure | No conversion into success; existing failure precedence preserved |
| Research-only task or intermediate stage handoff | No invented PLAN or inferred whole-task termination |
| Real future session handoff | Execution and conversation evidence reviewed by the user; fixtures alone cannot close the intent |

Test the distinct properties: safety (no corruption/unauthorized decisions), progress (next eligible session handles backlog), and user value (fewer reminder/re-explanation steps at acceptable cost). Removing a session-owner check is insufficient if the new helper is never invoked. Mutation/control tests should disable the owning trigger and show a behavioral difference. Track pending duration, reminder count, extra tool calls and prompt surface against the existing workflow; do not infer ROI from three protocol passes.

### C. Collector lease with expiry, heartbeat and takeover

| Field | Assessment |
|---|---|
| Assumption | Long-running exclusive ownership is essential, potentially across hosts |
| Evidence | Kubernetes leases support heartbeat and leader selection [S4]; this repository's session registry uses the short-lived CLI PID, which is unsuitable as session liveness (`worktree.py`, task claim documentation) |
| Trade-off | Requires renewal, expiry, stale-owner write rejection, clock/pause policy, and recovery; adds ongoing operational cost |
| Compatibility | Lower: introduces durable coordination and a host/session lifecycle dependency |
| Risk | High relative to the small local aggregation task |

Do not select C merely because a collector already exists. Expiration by itself does not make a resumed old writer safe; write-time authority validation is still needed. Reconsider only if actual requirements demand work that cannot fit a brief transaction or span multiple machines. A scheduler/database/queue bundle is an even larger extension and lacks supporting local evidence here.

## ⚠️ Pitfalls

- **Fixing corruption by making progress impossible.** The single-collector rule was a review repair, not an original product requirement: PLAN-world-intent-closed-loop, Review repairs round 2. Validate session abandonment as well as noncollector refusal.
- **Confusing atomic replacement with serialization.** The repository's `rmw_lock` docstring explains why concurrent readers can lose an update even with atomic file replacement. Platform fallback is part of the guarantee [S3].
- **Adding lease machinery to avoid a short transaction.** Leases have real renewal/leadership responsibilities [S4]. There is no demonstrated need for persistent leadership here.
- **Deduplicating by similar text or session.** Explicit operation identity distinguishes replay from a distinct intent; conflicting reuse must be detected [S2].
- **Treating a rebuilt view as permission to rewrite history.** Frozen cohort and human assessment survive replay; derived counters can be rebuilt, decisions cannot be silently replaced.
- **Overstating the ledger.** Preflight emission errors warn and continue (`worktree._emit_stage_span`); valid existing rows do not establish complete coverage.
- **Measuring the repair as independent success.** This task arose from user intervention. Preserve that fact; a repaired pipeline may demonstrate recovery but cannot erase a prior continuity failure.
- **Equating trial reporting with the whole feedback loop.** docs-release-sync contains actual within-task measurements and a next decision. An aggregate helper cannot judge whether those were causally useful or manufacture missing conversation evidence.
- **Unbounded infrastructure creep.** Earlier internal research recommended durable state without scheduler machinery. This recommendation keeps that boundary and adds only the missing recoverable read/commit path.

## ❓ Open Questions

These are SPEC decisions, not reasons to postpone this research recommendation:

1. Is this a one-off trial repair (A), or should session-independent collection be a reusable harness capability (B)? Recommendation: B as a minimal reader plus narrowly scoped writer, without a general workflow engine.
2. Which existing artifact owns typed cohort/assessment metadata, and what is the smallest task evidence block needed? Prefer existing PLAN records; do not create duplicate authoritative stores.
3. What confirms first-start completeness, and how are legacy/missing timestamps reconciled? Define provisional status, late evidence handling and freeze criteria explicitly.
4. Which platforms/filesystems are supported for shared writes? Decide strict fallback/unsupported behavior and crash guarantees before reusing locking helpers.
5. How will the current trial policy be amended and this repair task assessed? Preserve original evidence; user decides eligibility, failure attribution and any separate future validation window. No silent reset.

### Workflow feedback for this research

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| Base trial 0/3 plus docs-release-sync Feedback and stage ledger | WORLD-INTENT-CLOSED-LOOP | Observations recorded here; canonical trial and intent unchanged | Separate registration backlog from observed work and verified success | Research agent; user for assessment | User requested research; existing collector rule remains active | SPEC should define revised collection authority and migration |
| Current research start at 2026-09-23T12:55:56.463716Z | Active trial / intent-feedback-continuity | Candidate evidence retained; eligibility and collector update pending | Do not allocate a slot or claim unprompted success | Existing named collector; user | No collector transfer authorized | Reconcile under current authority or an explicitly approved policy revision |
| Read-only intent status: primary metric never_measured, active approval valid | WORLD-INTENT-CLOSED-LOOP | Unchanged | No attainment/closure claim | User | Existing judgment boundary | Research-only stop; SPEC is the next explicit stage |

No execution PLAN exists for this research yet. Transfer this evidence to PLAN Feedback when execute creates one. Research completion is not automatically terminal completion of the broader task; no terminal trial row is invented here.

## 📚 Sources

- **S1 — Kubernetes Controllers:** https://kubernetes.io/docs/concepts/architecture/controller/ — observed/desired state reconciliation and reporting. Pattern reference only, not a Kubernetes adoption proposal.
- **S2 — AWS Builders' Library, Making retries safe with idempotent APIs:** https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/ — explicit request identity, atomic association of identity and effect, conflicting parameter reuse.
- **S3 — Linux man-pages, flock(2):** https://man7.org/linux/man-pages/man2/flock.2.html — advisory exclusion, nonblocking acquisition and descriptor lifetime. Filesystem/platform qualifications apply.
- **S4 — Kubernetes Leases:** https://kubernetes.io/docs/concepts/architecture/leases/ — heartbeats, renewal and leader selection, used to assess alternative C.
- **S5 — SQLite Atomic Commit:** https://www.sqlite.org/atomiccommit.html — transactional recovery alternative if requirements exceed one local document. Search result consulted; not used to assert details of an unreviewed implementation.

## 🔗 Related Internal Docs

- [[PLAN-world-intent-closed-loop-trial]] — activation, named collector, empty cohort and transfer rule.
- [[SPEC-world-intent-closed-loop-trial]] — start-ordered real tasks, failures retained, user assessment required.
- [[PLAN-world-intent-closed-loop]] — review repair introduced named collector and acknowledged transfer.
- [[SPEC-world-intent-closed-loop]] — overall feedback continuity and authority contract.
- [[REVIEW-world-intent-closed-loop]] — concurrency and behavioral-evidence review history.
- [[EVIDENCE-world-intent-closed-loop]] — synthetic protocol evidence, explicitly separate from field trial.
- [[PLAN-docs-release-sync]] — real observations, decisions and pending collector handoff.
- [[RESEARCH-cell-dev-future-and-intent-layer-fit]] — local precedent for state-first scope and avoiding unproven schedulers; external claims there were not revalidated here.
- Code inspected at task baseline `5ba91a72f032aac587bae7d0c19a0242e30b8071`: `src/harness_maker/stage_spans.py` (`ledger_path`, `emit_event`); `worktree.py` (`task_preflight`, `_emit_stage_span`, `_acquire_merge_fence`); `io_utils.py` (`rmw_lock`, `atomic_write`); `world.py` (`_rmw_lock`); `tests/unit/test_world_intent_protocol_evidence.py`; generated intent-layer workflow-feedback reference and source template.
