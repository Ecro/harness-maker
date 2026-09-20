---
type: spec
task_slug: codex-main-independent
status: draft
created: '2026-09-20'
tags:
- harness-maker
- spec
- codex
- claude
test_framework: pytest
tier: 2
research_doc: '[[RESEARCH-codex-main-runtime]]'
interview_rounds: 0
summary: Stage-independent package identity and Claude result parsing foundations.
---

## 🎯 Intent
Implement the independent foundation slice authorized by the operator while plan-stage absorption is in flight. Reuse the existing task worktree.

## 🌅 Outcomes
Internal callers can resolve the engine requirement, distinguish partial updates, and reject invalid Claude responses. This slice does not install plugins or enable Claude review in the live workflow.

## 📋 In-Scope Scenarios

### S1
**Given** a stable plugin release with an optional Codex cachebuster
**When** the engine requirement is resolved
**Then** the stable PyPI release is selected.

### S2
**Given** a foreign package or unsupported release string
**When** resolution is requested
**Then** it raises ValueError instead of constructing a requirement.

### S3
**Given** observed package, engine and project identities
**When** update state is evaluated
**Then** complete requires all three identities to match their respective targets.

### S4
**Given** a successful Claude result envelope and schema-conforming findings
**When** the response is parsed
**Then** all finding fields survive, and an empty array remains a valid opinion.

### S5
**Given** a failed process, error envelope, duplicate keys or malformed payload
**When** the response is parsed
**Then** a typed error is returned rather than a clean opinion.

### S6
**Given** bounded raw bytes including sensitive text
**When** the output exceeds the explicit limit
**Then** a fixed error code is raised without echoing raw data.

## 🚫 Non-Goals
- No shared config, generator, stage, ledger, or schema changes.
- No live process invocation, credential handling, network calls or installation.
- No new CLI or public workflow entry; integration follows absorption.

## ⚠️ Constraints
| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | Existing repository tooling |
| Output limit | 1 MiB by default; caller can set a positive bound | Bound parsing cost |
| Compatibility | Stable x.y.z releases and optional +codex suffix only | Reject unsupported versions explicitly |
| Security | Pure functions; fixed diagnostic codes | No mutation or provider-data leakage |

## 🔒 Irreversible Decisions
None in this internal, unconnected slice. Public distribution and invocation permission choices remain in the parent task.

## ✅ Verification Criteria

### AC-001: Resolve a stable engine release independently of a Codex cachebuster
Unit: `tests/unit/test_codex_bootstrap.py::test_s1_cachebuster_is_not_a_python_release`.

### AC-002: Reject unsupported or unsafe package identities
Unit: `tests/unit/test_codex_bootstrap.py::test_s2_unsupported_release_is_rejected`.

### AC-003: Report completion only when package engine and project agree
Unit: `tests/unit/test_codex_bootstrap.py::test_s3_completion_requires_all_three_layers`.

### AC-004: Preserve valid structured findings including an empty opinion
Unit: `tests/unit/test_claude_response.py::test_s4_finding_fields_are_preserved`.

### AC-005: Reject failed ambiguous or malformed provider output
Unit: `tests/unit/test_claude_response.py::test_s5_failures_never_become_clean_opinions`.

### AC-006: Bound output bytes without echoing provider data
Unit: `tests/unit/test_claude_response.py::test_s6_size_limit_counts_bytes_and_does_not_echo_input`.

## ❓ Open Questions
None for this slice. Live invocation and package distribution decisions remain deferred in the parent research.

## 🔍 Refinement Decisions
Inherited from the operator: advance independent work in the existing worktree; defer shared integration. No second architecture interview was conducted. This draft has no DRI approval stamp and does not authorize landing.
