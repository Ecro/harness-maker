---
type: spec
task_slug: agent-code-reviewer
status: verified-skeleton
created: 2026-05-20
tier: 1
tags:
- harness-maker
- spec
- agent
- reviewer
- pilot-p3
test_framework: pytest
parent_spec: SPEC-reviewers
summary: code-reviewer agent renders with reframe Communication Protocol, narrow perms,
  and intended grading rubric.
---

## 🎯 Intent

The `code-reviewer` agent is the default code review path inside `/hm:exec-rev*` workflows. Its rendered prompt must (a) enforce the REFRAME Communication Protocol (anti-sycophancy), (b) deny all Write/Edit/destructive Bash patterns, (c) produce a grade-with-evidence verdict shape consumable by the autoloop convergence gate.

## 🌅 Outcomes

After /hm:make renders the agent, the resulting file:
1. Has frontmatter declaring `tools: Read, Grep, Glob` (read-only)
2. Body contains the REFRAME Communication Protocol section
3. Verdict format matches the consensus-arbiter input schema
4. Permissions deny block includes Bash(python:*), Bash(sh:*), Bash(eval *)

## 📋 In-Scope Scenarios

### AC-001: rendered output is snapshot-stable

**Given** a fixed harness.yaml
**When** render emits `.claude/agents/code-reviewer.md`
**Then** the bytes match `tests/snapshot/__snapshots__/agents/code-reviewer.snap`

### AC-002: frontmatter parses + denies write tools

**Given** the rendered agent file
**When** parsed as YAML frontmatter
**Then** `permissions.deny` contains `Write(*)`, `Edit(*)`, `Bash(rm:*)`, `Bash(python:*)`, `Bash(sh:*)`

### AC-003: body contains REFRAME Communication Protocol marker

**Given** the rendered body
**When** scanned
**Then** it contains the marker `<!-- @hm:communication_variant: reframe -->`

### AC-004: prompt fulfills SPEC AC (LLM judge)

**Given** the rendered prompt text
**When** scored against the agent_prompt rubric
**Then** `non_python_intent_alignment` score ≥ 80

## 🚫 Non-Goals

- The reviewer's runtime behavior under real LLM (covered by integration fixtures)
- Cursor IDE auto-discovery (manual + cursor-compat checklist)

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | default |
| Permissions | read-only + narrow Bash allow | CLAUDE.md security policy |
| Communication variant | reframe | PLAN-antisycophancy-2026-05 |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name |
|---|---|---|
| AC-001 | snapshot (Layer 1) | tests/snapshot/test_agents.py::test_code_reviewer_snapshot |
| AC-002 | schema (Layer 2) | tests/structural/test_reviewer_outputs.py::test_code_reviewer_perms |
| AC-003 | schema (Layer 2) | tests/structural/test_reviewer_prompts_contain_agentic_depth_clauses.py |
| AC-004 | LLM-judge (Layer 3) | tests/integration/test_spec_quality_live.py::test_code_reviewer_intent (INTEGRATION=1) |

## ❓ Open Questions

(None — pilot SPEC.)

## 🔍 Refinement Decisions

- 2026-05-20 R0: Tier 1 (T1 non-Python — all 3 ADR-009 layers required)
- 2026-05-20 R0: No mutation gate (non-Python); 3-layer verification per ADR-009

## 🔗 Machine Spec

See [SPEC-agent-code-reviewer.machine.yaml](./SPEC-agent-code-reviewer.machine.yaml).
