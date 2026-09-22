---
id: WORLD-INTENT-CLOSED-LOOP
title: Close the loop between the world model and intent workflow
scope:
- Connect observations, world-state updates, intent decisions, and authorized execution
  without repeated user instructions to connect the feedback; define the trigger,
  responsible role, evidence, and recorded disposition for each handoff.
- Continue execution within agreed scope; consult the user for goal or scope changes
  and unresolved uncertainty. On agreed-work completion or goal attainment, record
  results and termination rationale and stop.
- For missed targets, missing measurements, or conflicting assumptions, perform additional
  measurement and diagnosis within existing scope and authority before deciding the
  next action.
- Keep observations, intents, one or more SPEC/PLAN executions, outcomes, and subsequent
  decisions traceable through stable references and explicit authoritative records.
- Evaluate existing specs/ and work-docs/ conventions first; justify alternative artifact
  locations by role, lifetime, and operator navigation. Verify discoverability and
  preserve history and references if paths change.
- Demonstrate successful feedback-to-decision continuity in all three consecutive
  real tasks using execution and conversation evidence, with final assessment by the
  user. Normal approval questions and justified termination are not failures.
state: proposed
created_at: '2026-09-22T00:02:18Z'
schema_version: 1
rejected: []
depends_on: []
approval: null
revisit_when: null
observed: null
note: null
closed_at: null
statement: The world model and intent workflow carry observations through state updates
  into the next decision across three consecutive real tasks without the user having
  to re-instruct the connection, proceeding to the next execution within the agreed
  scope. Changes to goals or scope and unresolved uncertainty are referred to the
  user. The visible artifact layout follows existing workflow conventions, with explicit
  rationale for any alternative placement.
metric_id: intent_world_closed_loop_cycles
out_of_scope:
- Detailed implementation, task-unit and observation-window definitions, and concrete
  acceptance criteria are deferred to a subsequent SPEC.
- Automatic approval, expansion beyond agreed goals or scope, or removal of existing
  human decision authority and quality gates.
- Continuing to invent work after agreed-work completion or goal attainment.
---
## Problem

The creator identified the central problem as feedback failing to reach the next
decision unless the user explicitly reconnects it. Existing observation, metric,
approval, and outcome records do not by themselves establish this operational
continuity. This is the creator's problem statement, not a measured failure rate;
the baseline remains unmeasured.

Artifact placement must also make the loop understandable through the existing
workflow. Users should be able to find its records without knowing internal modules.

## Proposed outcome

Across three consecutive real tasks, observations update the world model and inform
the next decision without the user having to say that the results must be reflected
in subsequent work. The agent proceeds to execution within agreed scope, while the
user decides changes to goals or scope and unresolved uncertainty. Each handoff
identifies its trigger, responsible role, evidence, and recorded disposition.

When agreed work is complete or the goal is attained, the agent records results and
termination rationale and stops. If a new goal or expanded scope is warranted, it
proposes that change and asks the user. Missed targets, missing measurements, and
conflicting assumptions lead to additional measurement and diagnosis within scope;
unresolved uncertainty is referred to the user.

Success requires all three consecutive tasks to satisfy feedback continuity. The
user makes the final assessment from execution and conversation records tracing
observation, state update, and next decision. Normal approval or decision questions
and evidence-backed termination are not failures; requiring the user to reconnect
feedback is. Records and links alone do not demonstrate success.

Completion evidence must also explain the artifact layout and demonstrate how an
operator finds the intent, supporting world state, related SPECs/PLANs, results, and
next decision. The task-count metric alone does not establish layout suitability.

## Affected users and systems

Operators and workflow agents use the same traceable records across intent commands,
SPEC/PLAN creation, execution, review, and wrapup. One intent may span multiple SPECs;
completion of an individual task must remain distinguishable from achievement of
the intent. Relevant storage includes `intent/`, `specs/`, `work-docs/`, and
`.claude/intent.yaml` / `.claude/intent/`, subject to the subsequent layout decision.

## Constraints

- Preserve human decision authority and existing quality gates. In-scope continuation
  does not authorize new goals, expanded scope, or bypassing existing approval boundaries.
- Do not silently treat missing data, missed targets, contradictions, or stale evidence
  as success; record the investigation and resulting decision or question for the user.
- Identify the authoritative record for each kind of information and distinguish
  persisted facts from derived status or generated views; avoid competing copies.
- Evaluate existing `specs/` and `work-docs/` conventions first. Justify any alternative
  by artifact role, lifetime, and operator navigation before choosing it. If paths
  change, preserve references, history, and approvals through a documented transition.
- Keep this intent at outcome level. The subsequent SPEC defines concrete acceptance
  criteria, implementation, and the operational demonstration and layout review.

## Open questions

- Which existing workflow boundaries implement the agreed feedback and escalation
  responsibilities, and where should their decisions and termination evidence live?
- How should question dependencies and revisit conditions be authored and maintained?
- Should intent records live in `work-docs/` or a dedicated directory? Where should
  shared world state, task evidence, and derived views live, and why?
- How should repeated or delayed feedback be linked across multiple SPECs without
  duplicate follow-up work or premature intent closure?
- What task unit and observation window will define the consecutive real-task trial,
  and how will execution and conversation evidence be collected for user assessment?
- Which layout walkthrough will demonstrate discoverability and placement rationale?
