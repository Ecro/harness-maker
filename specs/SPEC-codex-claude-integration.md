---
type: spec
task_slug: codex-claude-integration
status: approved
created: '2026-09-20'
tags:
- harness-maker
- spec
- codex
- claude
- plugins
test_framework: pytest
tier: 2
research_doc: '[[RESEARCH-codex-claude-integration]]'
summary: Reachable Codex setup/update and bounded authenticated Claude second opinions.
---

## 🎯 Intent
Make Codex a usable primary harness host with native plugin setup/update and Claude Code as an actual second-opinion provider. Extend the shipped pure foundations without restoring the retiring plan stage.

## 🌅 Outcomes
Users can discover setup/update after plugin installation, generate or update a Codex project with preserved customization, and receive a real Claude opinion through the existing review pipeline. Failures remain distinguishable from clean reviews or completed updates.

## 📋 In-Scope Scenarios

### S1: Discover setup and update skills from the installed Codex plugin
**Given** a native Codex installation without Claude caches
**When** the plugin is installed and its skills are loaded
**Then** setup and update entry points are discoverable and resolve the installed plugin root.

### S2: Use the matching Python engine for Codex project generation
**Given** a plugin manifest and a project without a harness
**When** setup runs through the bundled entry point
**Then** the matching stable engine generates Codex assets without requiring Claude installation.

### S3: Report plugin engine and project update outcomes independently
**Given** an existing installation and preserved user custom blocks
**When** an update or repeated identical update runs
**Then** all three observed identities must match before complete and custom blocks remain intact.

### S4: Invoke Claude with supplied context and disabled ambient tools
**Given** Claude is authenticated and required isolation flags are supported
**When** a second opinion is requested
**Then** the prompt goes through stdin with no shell expansion and ambient tools hooks plugins MCP and project instructions are unavailable.

### S5: Normalize actual Claude framing before strict finding validation
**Given** a result object or a bounded event array
**When** the transport receives provider output
**Then** exactly one successful terminal result with valid structured findings is accepted and missing duplicate ambiguous or malformed results are rejected.

### S6: Bound process lifetime output and failure diagnostics
**Given** a missing CLI authentication error timeout output flood or child process
**When** the transport runs or is cancelled
**Then** a typed failure is returned no clean vote is emitted secrets are omitted and owned processes are reaped.

### S7: Route Claude through the existing opinion workflow and ledger
**Given** a harness with second_opinion.models containing claude
**When** a supported review or spec validation dispatch runs
**Then** Claude findings and terminal failures are recorded with provider claude and existing Codex Antigravity and historical plan records still work.

### S8: Prove the user reachable installation update and opinion path
**Given** an isolated test installation and project
**When** the actual entry points run through install setup update and second opinion
**Then** the harness reaches Claude structured output and repeated update preserves user content with honest partial failure reporting.

## 🚫 Non-Goals
- Rewrite the global autopilot/session-identity system or restore hm-plan.
- Add a direct Anthropic API client, new credential store, or bypass-permissions default.
- Publish a new package/release or change the operator's active installation merely to obtain test evidence.
- Edit the concurrent plan-stage-absorption checkout.

## ⚠️ Constraints
| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | Existing repository CI |
| Process bound | 300 seconds default, configurable positive deadline; prompt/stdout/stderr each bounded | Prevent hangs and memory exhaustion |
| Security | stdin context, no shell interpolation, no tools/ambient customizations, fixed diagnostics | Reviewer cannot mutate the project |
| Authentication | Existing Claude CLI login; no mandatory API key | Match the requested Claude Code usage |
| Compatibility | Capability-checked CLI flags, fail closed if absent | Tested baseline Codex 0.155.1 / Claude 2.1.278 is not a promise about every release |
| Updates | Native plugin lifecycle, stable engine pin, preserve user blocks, never report complete on partial failure | Existing bootstrap and generator contracts |
| Integration order | Independent transport/package work first; reconcile shared files after absorption | Avoid conflicting stage/config ownership |

## 🔒 Irreversible Decisions
| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add claude to second_opinion.models and provider telemetry; preserve existing provider identities and historical plan records. | schema/file format/storage layout | Independently authored configs and ledger consumers must agree on the persisted provider identity. |
| IRR-002 | Use existing Claude CLI authentication in capability-checked safe-mode, context on stdin and no ambient tools/customizations; never fall back to permission bypass or bare API-key-only mode. | security/permission boundary | This defines what user data and execution powers a secondary model receives; changing it silently would violate caller expectations. |
| IRR-003 | Expose bundled hm-make and hm-update skills using native Codex plugin add/marketplace upgrade and a matching stable Python engine; complete means plugin engine and generated project all match. | public API/CLI contract | Users automate these entry points and rely on update completion meaning all three layers rather than marketplace refresh alone. |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit + integration | AC-001 contract tests below |
| S2 | unit + integration | AC-002 contract tests below |
| S3 | unit + integration | AC-003 contract tests below |
| S4 | unit + integration + live smoke | AC-004 contract tests below |
| S5 | unit + integration | AC-005 contract tests below |
| S6 | unit + integration | AC-006 contract tests below |
| S7 | unit + integration | AC-007 contract tests below |
| S8 | unit + integration + live smoke | AC-008 contract tests below |

### AC-001: Discover setup and update skills from the installed Codex plugin
Predicate: `set(required_skills) <= set(discovered_skills)`.
Oracle: golden — Official package layout plus a fresh fixture containing no Claude cache; expected management skill names are declared before implementation.

### AC-002: Use the matching Python engine for Codex project generation
Predicate: `engine_version == expected_release and codex_assets_exist`.
Oracle: golden — The plugin manifest release and the existing generator target contract fix the expected engine identity and output paths independently of the setup implementation.

### AC-003: Report plugin engine and project update outcomes independently
Predicate: `status.state == expected_state and user_blocks_after == user_blocks_before`.
Oracle: golden — The shipped three-layer truth table and sentinel custom blocks are the oracle; inject a failure at each operation boundary and compare actual filesystem content.

### AC-004: Invoke Claude with supplied context and disabled ambient tools
Predicate: `captured_stdin == prompt and requested_tools == [] and shell is False`.
Oracle: golden — Captured process argv/stdin and an adversarial temporary fixture with hook and write sentinels independently establish the no-tools permission boundary; a real synthetic probe supplements stubs.

### AC-005: Normalize actual Claude framing before strict finding validation
Predicate: `outcome.status == expected_status and outcome.findings == expected_findings`.
Oracle: golden — Claude 2.1.278 authenticated probe produced an event array with one final result; hardcoded object and event fixtures plus conflicting duplicate records define the contract before code.

### AC-006: Bound process lifetime output and failure diagnostics
Predicate: `failure.code == expected_code and not child_alive and secret not in diagnostic`.
Oracle: golden — Independent fake executables deliberately hang spawn children flood pipes and echo a sentinel; OS process liveness and fixed error codes decide success.

### AC-007: Route Claude through the existing opinion workflow and ledger
Predicate: `record.model == "claude" and record.status == expected_status`.
Oracle: golden — Frozen provider fixtures and the existing ledger reader are the oracle; preserve old model/stage fixtures and add successful/failed Claude review/spec cases after absorption reconciliation.

### AC-008: Prove the user reachable installation update and opinion path
Predicate: `workflow_completed and user_blocks_after == user_blocks_before and live_result_valid`.
Oracle: golden — Real CLI installation/discovery and a synthetic authenticated Claude invocation are required evidence; deterministic subprocess fixtures cover failures and do not replace the real smoke path.

## ❓ Open Questions
- None: the DRI explicitly approved IRR-001..003 and implementation on 2026-09-20.
- Keep the security-capability baseline explicit; do not silently degrade if a CLI lacks isolation flags.

## 🔍 Refinement Decisions
Round 1 inherited intent and outcomes from the user's explicit request. Scenario and failure-path criteria are drafted from native CLI help, an actual authenticated protocol probe, the accepted foundation SPEC and existing generator preservation rules. Pytest and bounded subprocess operation are proposed defaults. Shared workflow integration waits for absorption reconciliation; this SPEC does not treat standalone parsing as end-to-end completion.

Round 2: the DRI explicitly approved the three decisions and requested execution.
