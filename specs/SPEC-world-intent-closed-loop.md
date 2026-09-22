---
type: spec
task_slug: world-intent-closed-loop
status: approved
created: 2026-09-22
tags: [harness-maker, spec, intent, feedback, workflow]
test_framework: pytest
tier: 2
interview_rounds: 1
intent: WORLD-INTENT-CLOSED-LOOP
summary: "Connect observed evidence to authorized next decisions and demonstrate three real task cycles"
---

# World and intent feedback continuity

## 🎯 Intent

The operator currently has to reconnect observations to subsequent decisions. The
existing intent states and recording commands do not by themselves establish that
continuity. Implement the outcome in `intent/WORLD-INTENT-CLOSED-LOOP.md`: carry
evidence through a world-state update and a reasoned next decision, continue work
within existing authority, and stop on agreed completion.

The baseline remains unmeasured. Earlier `RESEARCH-mission-context-loop` cautioned
against adding a parallel orchestration system; this SPEC reuses current workflows.
Its historical measurements are not current adoption evidence. Current local
evidence: `templates/stages/wrapup.md.j2` Step 5.7 asks separate recording/closure/
measurement questions; `autopilot_caps._objective_check` checks active intent and
valid approval, but neither alone proves feedback reached the next decision.

## 🌅 Outcomes

- An operator can trace an observation to its authoritative state, the relevant
  intent, the SPEC/PLAN task, and the resulting decision using repository links.
- The workflow agent initiates that connection at a relevant observation, task
  entry/resume, and task close-out without waiting for a user reminder.
- Each disposition names its evidence, responsible role, authority, and either
  next action or termination reason. A task finishing does not imply its intent
  has succeeded; one intent may span multiple SPECs.
- Implementation readiness and real-use outcome are reported separately. This
  repository's next three real tasks after activation supply the outcome trial;
  no result is asserted merely because implementation tests passed.

## 📋 In-Scope Scenarios

### S1: Observation reaches a decision
**Given** a linked intent and new relevant evidence during an authorized task.
**When** the agent reaches the next decision that depends on that evidence.
**Then** it identifies the affected claim or metric and proposes or performs the
authorized state update before using it, reads back the resulting state, and
records the evidence reference and disposition in the task PLAN's `Feedback` section.
**And** a required consent that has not been given remains explicitly pending;
the agent neither claims the update occurred nor treats silence as consent.

### S2: Continue authorized work and preserve human decisions
**Given** an observation has been resolved and work remains in the agreed scope.
**When** the agent selects the next action.
**Then** it proceeds when the action is authorized and its prerequisites pass;
otherwise it asks the specific outstanding decision or approval, with evidence.
**And** a scope expansion, goal change, invalid approval, declined write, or
unresolved decision cannot be converted to permission by a continuation rule.
Host runtimes without stage invocation tools must present an actionable handoff
and its limitation; the workflow must not claim a stage ran when it did not.

### S3: Missing or contradictory evidence
**Given** a target is missed, a measurement is absent, evidence is stale, or claims conflict.
**When** a dependent next decision is due.
**Then** the agent first performs available measurement/diagnosis within scope and
authority, links the result, and either makes a supported decision or refers the
remaining uncertainty to the user. It does not silently declare success.
**And** an open observation window yields a dated deferred assessment and its
next eligible trigger, not repeated measurement attempts or a fabricated value.
Independent authorized work may continue while the dependent decision is pending.

### S4: Completion, replay, and delayed feedback
**Given** a task finishes, a prior observation is encountered again, or delayed
evidence arrives after an intent has closed.
**When** the agent evaluates what to do next.
**Then** it distinguishes task completion from intent attainment, records the
reason for stopping or continuing, and references any existing disposition or
follow-up instead of creating duplicate work. Closed/dropped records are not
rewritten. Delayed evidence may justify a linked proposal under existing consent.
**And** absent authorized remaining work, it stops; it does not invent tasks to
extend the run, satisfy a metric, or complete the trial.

### S5: Find the authoritative records
**Given** an operator starts from a SPEC or PLAN serving this intent.
**When** they follow its documented links.
**Then** they can find the intent, authoritative claims and measurements, task
evidence, result, and next decision without knowing Python module names.
**And** existing record paths, identities, approval hashes and legacy read support
remain compatible; task records reference shared state instead of copying it.

### S6: Three consecutive real tasks
**Given** the implemented workflow is applied to this repository and the trial
activation timestamp and applied revision are recorded before sampling starts.
**When** the next three distinct real task slugs begin here under that workflow.
**Then** all three are enrolled in start order, including later failure, abort or
missing evidence. Stage reruns/resumes of one slug remain one task. Synthetic
fixtures and the already-started implementation task are excluded.
**And** execution and conversation references show whether each task connected
observation, state update, next decision, and authorized continuation or justified
termination without a user reconnecting the feedback. The user judges each row.
The observation window is event-bounded: activation until all three enrolled
tasks have terminal dispositions. Concurrent completion order does not change
enrollment order. Pending tasks keep collection open without hiding an already
confirmed failure; no elapsed
time or shortage of real work counts as success.

### S7: Codex stage continuation
**Given** Codex runs an armed autopilot stage with its mandatory gate classified.
**When** the unchanged boundary CLI returns a decision.
**Then** a successful decision loads the next local `hm-<stage>` SKILL.md with the
returned task slug and executes it in the same conversation without a routine
next-stage confirmation. A missing skill or unsupported runtime gets an honest
handoff; a false decision stops. Existing quality, intent approval, cap, loop
ownership and merge gates remain effective. Gated mode does not auto-advance.

## 🚫 Non-Goals

- Moving `intent/`, `specs/`, `work-docs/`, or shared state; introducing a second
  source of truth, external database, daemon, new public CLI, or external dependency.
- Automatically approving/activating/closing intents, changing consent policy,
  bypassing quality gates, or silently expanding scope.
- Fixing every measured project metric or redesigning verification caching.
- Automatically choosing new goals, manufacturing trial tasks, or claiming
  production adoption from fixtures, code coverage, links alone, or prompt keywords.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest for deterministic contracts; evidence rubric for behavior | Existing repository convention; text presence is insufficient |
| Compatibility | Keep existing canonical paths, CLI semantics, legacy reads and approval rules | Operator chose no migration |
| Security / authority | Existing permissions and recorded user consent remain binding | Continuation is not new authority |
| Performance | Reuse task records and stage boundaries; no background polling | Avoid recurring orchestration overhead; no invented numeric budget |
| Ownership | Workflow agent gathers/connects evidence; user owns goals, approvals and final trial assessment | Existing intent responsibility split |
| Runtime | Claude/Codex/Cursor rendered workflows describe the same decision obligations using available host tools | Do not require one host's stage tool on another |
| Evidence | Preserve source references and timestamps; missing/unavailable records mean insufficient evidence | Prevent inferred success and retrospective sample selection |

Record responsibilities (the location choice is settled; implementation mechanics
and test bindings belong to the PLAN):

| Record | Authoritative location | Link responsibility |
|---|---|---|
| Intent scope and lifecycle | `intent/<ID>.md` | SPEC/PLAN frontmatter `intent` identifies it |
| Purpose, metric definitions, questions | `.claude/intent.yaml` | Feedback cites stable question/metric IDs |
| Metric observations | `.claude/intent/metrics.yaml` | Feedback cites metric ID and observation timestamp |
| Code-absent project facts | `.claude/memory/wiki.md` via existing project-knowledge procedure | Cite existing subject anchor; no duplicate fact store |
| Acceptance criteria / execution | `specs/SPEC-<slug>.*`, `work-docs/PLAN-<slug>.md` | PLAN links SPEC; both link intent |
| Observation-to-decision disposition | PLAN `Feedback` section | Evidence locator, affected ID, update status, decision, owner, authority, next action/stop reason, existing follow-up link |
| Trial evidence and user assessments | `work-docs/PLAN-world-intent-closed-loop-trial.md`, `Trial` section | Activation revision/time plus three ordered task rows with execution/conversation links |
| Derived status | `hm intent status --json` | Recomputed view, not a competing durable state file |

### This task's navigation path

Start from [WORLD-INTENT-CLOSED-LOOP](../intent/WORLD-INTENT-CLOSED-LOOP.md)
and its metric ID `intent_world_closed_loop_cycles`. The
[metric definition and governing questions](../.claude/intent.yaml) and
[measurement history](../.claude/intent/metrics.yaml) are authoritative; look up
that same stable metric ID. No observation for it is recorded yet.

Follow the [implementation PLAN](../work-docs/PLAN-world-intent-closed-loop.md)
for execution and Feedback dispositions,
[observed evidence](../work-docs/EVIDENCE-world-intent-closed-loop.md) for native
traces and failed controls, and the
[review result](../work-docs/REVIEW-world-intent-closed-loop.md) plus
[verification receipt](../work-docs/RECEIPT-world-intent-closed-loop-verification.md)
for implementation acceptance. The
[next decision](../work-docs/PLAN-world-intent-closed-loop.md#completion-disposition)
is to keep the intent active and apply the separately approved
[real-task trial SPEC](SPEC-world-intent-closed-loop-trial.md).
Its PLAN is created on activation after application; this document does not claim
that future evidence exists or substitute implementation tests for it.

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Retain existing authoritative stores; place linked task dispositions in PLAN `Feedback` and the trial in its separate PLAN `Trial` | schema/file format/storage layout | Workflow consumers and durable references depend on record placement and required fields; later relocation needs compatibility handling |

No new CLI/API, migration, external dependency or expanded permission boundary is
authorized. If implementation requires one, return that decision to the user.

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | integration + rubric | Feed a recorded observation into a temporary project; compare update status and decision against the authored case; inspect actual workflow evidence |
| S2 | integration + rubric | Exercise authorized continuation, missing approval, scope expansion, denied consent and unavailable stage tools; verify no unauthorized mutation or false execution claim |
| S3 | integration + rubric | Exercise missing/stale/conflicting evidence and an open measurement window; inspect bounded diagnosis and the unresolved/deferred disposition |
| S4 | integration + rubric | Resume the same observation, finish a task with remaining intent work, and provide delayed evidence for a terminal intent; verify references, no duplicate task and preserved terminal bytes |
| S5 | compatibility + manual rubric | Before/after fixtures preserve records and approvals; follow links from SPEC and PLAN to each authoritative item and decision |
| S7 | render + boundary integration + independent workflow review | Codex next-skill dispatch for clear gates; pending/blocked, missing skill, loop ownership and gated-mode controls |
| S6 | manual rubric | User assesses all three enrolled rows from execution/conversation evidence; no synthetic substitute |

### AC-001: Evidence precedes the dependent decision
At each of observation, entry/resume, and close-out, the agent must initiate
the connection without a feedback-reminder. Fixtures cover each trigger with
ordinary task instructions only; removing that trigger must fail the fixture.
S1 passes only if the trace has the real observation, affected state ID, authorized
write/readback or explicit pending consent, and a next decision citing that state.

### AC-002: Continuation respects existing authority
S2 passes only if authorized work proceeds, required approvals remain explicit,
and refusal, uncertainty, or unavailable tools never become a false success claim.

### AC-003: Evidence gaps receive an explicit disposition
S3 passes only if missing, stale, conflicting and not-yet-measurable data lead to
supported diagnosis, a specific pending question, or dated deferral.

### AC-004: Completion and replay do not create extra work
S4 passes only if task versus intent outcome is distinguished, replay links the
prior disposition, terminal records remain unchanged, and continuation has scope.

### AC-005: Existing records remain discoverable and authoritative
S5 passes only if all required records and decisions are reachable through valid
links, and unchanged records retain their meaning, identity and approval validity.

### AC-006: Trial protocol preserves enrollment and assessment
The implementation must support the S6 protocol and distinguish enrollment,
evidence and user assessment. Adversarial fixtures cover concurrent completion,
resume of one slug, aborted tasks, absent evidence, failure and a denied reset.
The real trial is accepted separately by
[SPEC-world-intent-closed-loop-trial](SPEC-world-intent-closed-loop-trial.md),
which serves the same intent. The trial succeeds only when all three enrolled tasks satisfy the continuity rubric and
the user assesses all three as successful. Abort/failure is not silently excluded:
an aborted task can demonstrate a successful, evidence-backed termination, while
missing trace evidence is `insufficient_evidence` and a user feedback-reminder is
`failed`. A failed trial remains reported; replacing rows or starting another
window requires an explicit new decision, never an automatic reset.

### AC-007: Codex follows authorized next-stage decisions
S7 passes only when Codex output contains an executable boundary check and
same-conversation next-skill execution, with task slug propagation and explicit
missing-skill handling. It must not require Claude's Skill tool or treat an armed
marker as permission. False decisions, genuine pending approvals and quality
failures still stop; step/time limits and merge boundaries are unchanged.

Oracle provenance: the existing intent defines continuity and retained human
authority; the operator's 2026-09-22 answers choose existing locations and this
repository's next three tasks. The per-AC `world_intent_*` rubrics express those requirements, authored before
implementation. Each AC binds only its own rubric, not the future real-task trial. Deterministic fixtures
must encode the stated counterexamples, not expectations inferred from code.
Structural render tests supplement, but cannot replace, behavioral evidence.

Implementation acceptance covers AC-001–007 through fixtures and workflow review.
The separate trial SPEC remains open after implementation completion; the intent
must not close as met before that trial succeeds. Report collection status
(`not_started`, `collecting`, `complete`) separately from outcome (`pending`,
`failed`, `insufficient_evidence`, `passed`). A confirmed continuity failure takes
precedence; without one, any terminal row missing required evidence yields
`insufficient_evidence`; otherwise unfinished enrollment or assessment is
`pending`; only three user-assessed successful rows yield `passed`. Later supplied
evidence can resolve insufficiency but cannot erase a confirmed failure. Normal
approval questions are not trial failures.

## ❓ Open Questions

- No unresolved operator scope choice. The user accepted both SPECs and authorized
  implementation, then explicitly included the Codex autopilot connection repair.
- PLAN must choose concrete trigger integration points and tests for each host,
  specify source-reference capture/resume mechanics, and map each fixture to its
  actual observable surface. These are implementation decisions, not permission
  to change the record or authority contracts above.

## 🔍 Refinement Decisions

- Round 1, 2026-09-22: reuse WORLD-INTENT-CLOSED-LOOP; operator chose existing
  record locations with link/discovery improvements and this repository's next
  three real task slugs. Keep implementation and field validation separate.
- Operational precision: count start order, preserve failed/aborted rows,
  use an event-bounded window, and require source evidence plus final user judgment.
- Prior failure memory `assertion-invariant-over-named-dimension` requires
  counterexamples that fail when the feedback/authority obligation is removed;
  snapshots or keyword assertions alone cannot establish these outcomes.

- Separate implementation and real-trial SPECs prevent future adoption evidence
  from blocking initial application. Both retain the same intent link.

## 🔎 Spec Validation

- Structural/schema and Markdown/YAML cross-validation: passed at block strictness.
- Second opinion: `model: codex`, `status: invoked`, `reason: null`.
  The initial findings were resolved: all-three-terminal window for concurrent
  tasks (`a758ad1b050dd7df`), failure versus pending state precedence
  (`818f4324c58b94ce`), and unprompted connection at each required trigger
  (`1a825b6831a1eb09`).
- One-pass spec-validator assessment: `APPROVED`. No circular-oracle,
  irreversible-decision or scope-boundary finding. Its one suggestion, to name
  the separate trial PLAN explicitly in the authoritative-location table, was
  applied. This reviewer verdict is advisory and is not the user's acceptance.

- Scope addition, 2026-09-22: user explicitly requested repairing the Codex
  autopilot connection here. Latest official documentation supports skill selection
  and persistent work; no new Goal, hook or public CLI is required for this repair.
