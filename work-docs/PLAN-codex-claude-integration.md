---
type: plan
task_slug: codex-claude-integration
status: complete
spec: "[[SPEC-codex-claude-integration]]"
research_doc: "[[RESEARCH-codex-claude-integration]]"
spec_need_verdict: add
spec_need_target: codex-claude-integration
---
# Execution plan

Agent-authored phase decomposition under the approved SPEC; no resurrected hm-plan interview.

## 📝 Implementation Plan
### Phase 1: stage-independent Claude process transport
Scope: new src/harness_maker/claude_transport.py and tests/unit/test_claude_transport.py; preserve claude_response strict result validation. Cover AC-004/005/006 with synthetic executables and a real CLI smoke. Capability check, bounded stdin/stdout/stderr, isolated cwd, safe-mode/no-tools, unique terminal result normalization, process-group cleanup. depends_on: []; parallel_group: private-foundations; merge_hazards: none. Risk: medium. Exit: targeted pytest, ruff, strict mypy and independent test review. Rollback: remove unconnected module and tests. Status: complete.

### Phase 2: reachable Codex package setup/update
Scope: .codex-plugin/plugin.json, new skills/hm-make/SKILL.md and skills/hm-update/SKILL.md, bundled scripts/codex_setup.py, scripts/codex_engine.py, src/harness_maker/codex_setup.py and test coverage; README.md/README.ko.md install guidance and its command allowlist. Reuse stable release identity and existing make generation; never depend on Claude caches or bootstrap through a module absent in the release being installed. Track installed plugin root/version, selected engine version, and actual project regeneration independently; failure cannot report complete. Cover AC-001/002/003 and package portion of AC-008. depends_on: []; parallel_group: serial-public-contract; merge_hazards: package public surface. Risk: medium. Exit: clean fixture package discovery + setup/update integration, preservation/idempotence/failure tests, manifest/skill validators. Rollback: revert package entrypoints. Status: complete.

### Phase 3: shared provider/workflow integration
Scope: models.py, second_opinion_invoke.py, codex_ledger.py, interview.py, command registry if necessary, opinion dispatch templates, tool detection, provider adapter, ledger schema, generated contract tests. AC-007 and end-to-end AC-008. depends_on: [1,2]; parallel_group: serial-integration; merge_hazards: plan-stage-absorption owns shared model/generator/template changes. Reconcile against the absorbed spec/execute contract before editing shared stage ownership; never modify the peer checkout. Preserve historical plan records and existing Codex/Antigravity behavior. Risk: medium. Exit: config/render/invoker/ledger regressions and real Claude opinion through user entrypoint. Rollback: additive provider integration only. Status: complete.

### Phase 4: review, verify, wrapup
Full skill procedures; bind all acceptance tests, independent review, CI lint/format/type/full tests. No implementation-stage commits. Live plugin smoke uses an isolated fixture and no edits to the user's active installation. Finish only when the integrated user paths pass; do not relabel foundations as the full task.

## ADRs
- IRR-001..003 are approved in the SPEC; this document adds no irreversible decision.
- Keep process transport private and independent of workflow stage identity.
- Synthetic executable fixtures supply failure/security oracles; authenticated CLI smoke supplements them.

## 🚧 Contract Boundaries
### Do not change
- Advisory: never write into other task worktrees or mutate the operator's active installation for testing.
- Advisory: preserve existing project custom blocks and saved authentication; never read or log credential values.
- Advisory: no restoration of hm-plan and no shared stage-ownership edits before absorption reconciliation.

## Execution notes
Phase 1 private tests/module ownership may be delegated while the parent handles package work. Shared public schema/CLI integration is serial. Existing research and memory retrieval are reused.

Phase 1/2 A.5 round 1 FAIL was repaired with installed-root execution, actual asset checks, precise partial outcomes, nonempty findings, cancellation and child cleanup oracles. Round 2 PASS for S1-S6. Phase B RED: 2 missing-module collection errors, zero tests executed. Phase C subsequently completed.

Phase 3 A.5 first round found a success fixture missing required confidence. Repaired the fixture, validated it with the existing strict parser, reran RED (11 failed, 1 legacy regression passed), and independent retry PASS. Phase C public routing tests: 12 passed; prior provider regression set passed. Peer absorption reconciliation: preserve its pending AtomicStage removal and agent default rename; additive provider changes do not edit either ownership boundary.

Native lifecycle smoke exposed a published-engine update guard depending on caller cwd: invoking a fixture project from our task worktree was rejected. Repair runs the generator with the target project as cwd. Newly reachable window: update from an arbitrary caller worktree into a separate project; native lifecycle smoke must cover this exact path and sentinel preservation. No bypass environment flag is introduced.

First complete regression pass: 6 failed, 9123 passed, 101 skipped, 3 xfailed (931.81s). Classified failures: two new subprocess tests timed out before child startup under concurrent load (increase fixture deadline, retain timeout and real PID oracle); two README guards froze the superseded unavailable-native-plugin contract (replace with approved AC-001 native commands + bundled bootstrap guard, backed by real smoke); one detector expected old provider keys (extend exact expected set); one selector registration missing for the new package test (register the real manifest/engine suite). These repairs extend Phase 3 generated-contract/test integration scope to test_dep_map.py and affected regression fixtures; they do not change workflow stage ownership.

Review round 1: four P1 lifecycle/config issues and two test-oracle gaps. Lifecycle model re-derived as independent observations plus a command success condition; one owned process group spans uv, engine and generator and is terminated on every exit. Consolidated repair preserves verified engine observations on nonzero exits while preventing complete, emits nondefault saved disabled-provider configuration, and checks process statuses. Round 2 independent core review resolved all P1s. New windows are failure receipts (returncode and CalledProcessError), absent/disabled settings, malformed manifests and project generation descendants; covering tests enter each window. Required AC-004/007 oracle completion added actual saved-option forwarding and adversarial authenticated hook/instruction/tool-write sentinel checks.

Confirmation repair: all newly introduced test subprocess.run calls now use check=True and explicit deadlines. An AST audit verifies the contract. The second full run stopped after 3,249 passes on a fixture readiness-file race; publishing the PID JSON with atomic rename fixes the test observer without changing product behavior. Focused repair verification: 41 passed, strict mypy passed. Final full regression passed: 9,142 passed, 101 skipped, 3 xfailed; lint, format and strict mypy passed. Confirmation 2 returned no findings across all seven lenses, grade A APPROVED. The authenticated native lifecycle smoke passed separately. All eight mechanical acceptance criteria are bound; no judgment acceptance criteria remain. Wrapup documentation is complete; commit and landing remain owned by the main agent.

Wrapup integration: main advanced to 697036be (withdrawal-criterion-window); rebase was clean. Combined provider/lifecycle and peer window/render/document checks passed (196 tests). Strict mypy exposed two imported attributes used through world in the peer control fixture; import intent and resolve_base_root directly from their owning modules. This compatibility repair changes no runtime implementation or control behavior.

Wrapup receipts: 8 pytest-bindable ACs forward-bound, 0 pending, 0 judgment ACs. Locked memory CLI updated the native-install gotcha and two existing failure recurrences; one newly threshold-reaching failure received a proposal. promotion evaluated: 3 candidates, 2 promoted; the native-install gotcha stays project-local. Intent assumption/outcome writes remain answer-gated and were not performed.
