---
type: spec
task_slug: codex-stage-invocation
status: approved
created: 2026-09-22
tags: [harness-maker, spec, python, codex, invocation]
test_framework: pytest
interview_rounds: 1
tier: 2
summary: "Render executable Codex skill guidance consistently across generated harness documents."
---

## 🎯 Intent
Codex users copy Claude-only slash commands from harness output and receive unrecognized-command errors. Existing conversion emits an incorrect at-sign mention and covers only terminal banners. The user requested runtime-correct guidance and authorized implementation in a worktree.

## 🌅 Outcomes
Users can copy `$hm-spec <slug>` and other supported stage invocations from Codex guidance. Claude Code and Cursor retain their invocation syntax. Removed stages are not advertised as next steps.

## 📋 In-Scope Scenarios

### S1: Codex invocation guidance uses dollar skill mentions
**Given** a Codex harness, **When** stages, help and AGENTS.md are generated, **Then** usage and next-step instructions use `$hm-<stage>` including the research to spec handoff.

### S2: Executable content and other runtimes retain their contracts
**Given** executable shell examples, internal stage IDs, file paths, preserved user blocks and Claude/Cursor output, **When** Codex guidance is formatted, **Then** those contracts are unchanged.

### S3: Recommendations reference existing workflow stages
**Given** the current workflow with no plan stage, **When** stage next-step banners and help are rendered, **Then** recommendations reference existing stage skills and research recommends spec; no plan skill is advertised.

### S4: Update rendering repairs existing Codex guidance
**Given** a previously generated Codex harness containing slash or at-sign guidance and a user extension, **When** updated from current templates, **Then** owned guidance uses dollar mentions and the extension is preserved.

## 🚫 Non-Goals
- Reintroducing hm-plan or changing workflow stage order.
- Changing CLI flags, stage event IDs, shell execution, permissions or user extensions.
- Installing into other projects or releasing the plugin.
- Initial scope excluded landing. On 2026-09-22 the user subsequently authorized
  wrapup and push to main, and explicitly waived live Claude CLI verification for
  this invocation only. This does not change CI or waive future verification.

## ⚠️ Constraints
| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | Existing project suite |
| Compatibility | Claude Code and Cursor guidance unchanged | Multi-target generation |
| Security | Executable fenced examples and inline shell payloads preserved | Dollar signs must not become shell variable expansions |
| Performance | Local deterministic formatting | No runtime network call |
| Scope | Source templates, formatting, related tests and generated fixtures | Changes survive regeneration |

## 🔒 Irreversible Decisions
None. This corrects display guidance to existing host contracts without changing the public CLI, schemas, dependencies, permissions or stored data.

## ✅ Verification Criteria
| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit / integration | `test_codex_guidance_uses_dollar_mentions` |
| S2 | unit / integration | `test_preserves_executable_and_non_codex_content` |
| S3 | unit / integration | `test_recommendations_resolve_to_skills` |
| S4 | unit / integration | `test_update_repairs_guidance` |

### AC-001: Codex invocation guidance uses dollar skill mentions
Verified by `tests/unit/test_stage_invocation_syntax.py::test_codex_guidance_uses_dollar_mentions`.

### AC-002: Executable content and other runtimes retain their contracts
Verified by `tests/unit/test_stage_invocation_syntax.py::test_preserves_executable_and_non_codex_content`.

### AC-003: Recommendations reference existing workflow stages
Verified by `tests/unit/test_stage_invocation_syntax.py::test_recommendations_resolve_to_skills`.

### AC-004: Update rendering repairs existing Codex guidance
Verified by `tests/unit/test_stage_invocation_syntax.py::test_update_repairs_guidance`.

Oracle provenance: expected `$skill-name` spelling comes from the user report and the official OpenAI build-skills documentation (https://learn.chatgpt.com/docs/build-skills), not the implementation. Exact preservation fixtures represent pre-existing shell, path, user-extension and non-Codex contracts. Stage availability is checked against actually generated skill paths and the existing plan-stage-absorption SPEC.

## ❓ Open Questions
None. The user approved the proposed scope and requested skill-driven implementation; explicitly requested no intent link. No formal machine acceptance stamp is asserted before a concrete SPEC approval.

## 🔍 Refinement Decisions
- Round 1: Reused the accepted four-part proposal; pytest and targeted render/update checks follow existing project conventions.
- Preserve executable content and user blocks; normalize owned prose before preservation merge.
- No irreversible decision; implementation remains in the requested task worktree.

## Concrete oracle bindings
- AC-001: `codex_documents` is the rendered file map. `required_guidance` includes AGENTS.md → `$hm-execute task-slug`, research → `Invoke via `$hm-research <topic>`, research → `Y → run `$hm-spec {slug}``, help → `$hm-research`, `$intent-layer`, `$project-knowledge`. Cover Side/Production and en/ko/ja-fallback, plus shared skills.
- AC-002: `format_codex` is the host formatter. `protected_examples` include bash `echo "run /hm:spec"`, unlabelled `Bash("echo /hm:spec")`, Python `command = "/hm:spec"`, inline `echo "run /hm:spec"`, `--stage hm:spec`, `/tmp/hm:spec`, `.claude/commands/hm/spec.md`, and user blocks with both legacy spellings. A text fence containing `/hm:spec topic` becomes `$hm-spec topic`. Claude research retains `Y → run `/hm:spec {slug}`` and Cursor retains slash invocation.
- AC-003: `required_stage_names` is independently fixed as hm-research, hm-spec, hm-execute, hm-review, hm-verify, hm-wrapup. Also require hm-loop and hm-help in help. Extract recommendations from nonempty Next banners and the help table; all must resolve. Historical mentions of removed plan are permitted as history, not recommendations.
- AC-004: Re-render a legacy research skill with both slash and at-sign spellings, retaining a well-formed AGENTS.md user extension containing `/hm:spec` and `@hm-spec`. Both updates must contain corrected research invocation and handoff; after the second update the full frozen-time output is identical and extension text is byte-identical.

## 🔎 Spec Validation
Second opinion: codex invoked successfully; three P2 suggestions addressed by concrete oracle bindings, fixed required stage inventory and explicit conversion boundaries. P3 update idempotence incorporated. No irreversible decision was identified.

Spec-validator: APPROVED, no critiques in all four categories. Machine acceptance remains unstamped; user authorized implementation, not landing.

Execution refinement: update preservation is exercised on AGENTS.md, whose user blocks are well-formed. Existing stage-skill wrappers duplicate the extensions marker and the existing merge parser rejects them; changing that unrelated migration behavior is outside this invocation fix. Shared-skill evidence checks its description, where the stage reference actually appears.
