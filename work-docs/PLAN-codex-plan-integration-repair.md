---
type: plan
task_slug: codex-plan-integration-repair
status: complete
created: 2026-09-20
tags: [harness-maker, plan, python, codex, migration]
spec: "[[SPEC-codex-claude-integration]]"
interview_rounds: 0
adrs: 1
validator_outcome: NOT_RUN
summary: Restore Codex/Claude integration after retirement of the plan stage.
spec_need_verdict: none
spec_need_target: codex-plan-integration-repair
---

## 🎯 Executive Summary
Repair the three verified integration regressions on 8597b0b8: legacy second-opinion agent names, the spec-validator model contract, and reverted English native-install instructions. Existing SPEC-codex-claude-integration AC-001/002/007 and SPEC-plan-stage-absorption retirement contracts remain authoritative; no new product capability or irreversible decision is introduced.

## 📚 Prior Work
The integration probe confirmed real native setup/update and authenticated Claude calls, but an upgraded agent allowlist retained plan-validator and suppressed reconciliation instructions. Fresh spec-validator output excluded Claude. README's native bootstrap guard failed locally and in CI. Preserve the absorbed spec/execute workflow while restoring the earlier native-install contract. Memory lesson: exercise the composed reader/renderer path and preserve independently landed work.

## 📐 Architecture Decision Records
ADR-001: normalize the exact retired agent name at the shared SecondOpinionConfig boundary, covering direct model loads and both YAML readers. Preserve explicit opt-outs, custom names, unrelated options and order. Collapse only collisions involving the replacement spec-validator. Render the validator's permitted models from the enabled model list, not a second hardcoded provider list.

## 🏗️ Technical Design
SecondOpinionConfig -> YAML reverse mapping -> synthesis -> target-native spec-validator. The repaired identity must reach every reader before rendering. Restore only README's Codex lifecycle/provider sections from the integration commit; retain stage-retirement documentation. No changes to transport, CLI authentication or installation execution are planned.

## 📝 Implementation Plan
### Phase 1 — regression oracles
depends_on: []; parallel_group: serial; merge_hazards: shared model/template contract. Scope: tests/unit/test_second_opinion_retired_agent.py and existing README guards. Exit: measured RED failures and independent A.5 review. Risk: low. Rollback: remove new tests.
### Phase 2 — implementation
depends_on: [1]; parallel_group: serial; merge_hazards: shared schema and generated templates. Scope: src/harness_maker/models.py, templates/agents/spec-validator_body.md.j2, templates/harness-yaml/Side.yaml.j2, README.md. Exit: regression tests, provider tests, ruff and strict mypy. Risk: medium. Rollback: revert only task-owned diff. No peer changes or workflow stage restoration.
### Phase 3 — review and completion
depends_on: [2]; parallel_group: serial; merge_hazards: generated baselines only if required by measured changes. Scope: task review/plan, necessary snapshot updates, wrapup-managed documents and memory. Exit: independent review, confirmation, full CI commands, native isolated smoke, worktree landing. Risk: medium. Rollback: preserve worktree on failure; no release/push without instruction.

### Confirmation repair — composed absorption path
Confirmation of the stored full span found two additional P1 defects: execute rejects a missing PLAN before its authoring step, and simultaneous non-isolated frontmatter upserts can overwrite the first decision. It also found a P2 test oracle that searches unrelated whole-stage words. Extend scope to templates/stages/execute.md.j2, spec_need.py, tests/unit/test_render_execute_spec_need.py and tests/unit/test_spec_need_frontmatter_upsert.py. Reuse the existing read-modify-write lock around the entire decision write; clarify optional PLAN entry; strengthen the bounded post-write guard oracle. No new product contract; absorption AC-002 preservation remains authoritative. Require focused RED/GREEN, repeated full CI and second frozen confirmation. Verification follow-up also strengthens tests/render/test_spec_validator_dispatch.py against the two nonblocking P2 mutants from confirmation 2; shorten the Inputs wording to meet the unchanged shipped-surface ratchet.

## 🚧 Contract Boundaries
### Do not change
- `src/harness_maker/claude_transport.py`
- `src/harness_maker/codex_setup.py`
- Advisory: never restore the removed plan stage or plan-validator agent.
- Advisory: preserve saved authentication, custom agents, explicit opt-outs and project user blocks.
- Advisory: tests use isolated temporary projects; do not regenerate the operator's active installation.

## 🧪 Testing Strategy
Migration examples bind exact replacement, collision handling, idempotence, both YAML key generations and disabled/custom allowlists. Composed render tests assert the upgraded validator actually receives reconciliation instructions and declares each enabled model. Existing README guards plus actual native smoke bind the public install instructions. Full CI follows targeted checks.

## ⚠️ Risks & Mitigation
| Risk | Mitigation |
|---|---|
| Migration broadens custom allowlists | Exact-name replacement only; explicit opt-out tests |
| Correct config but missing consumer instructions | YAML-to-render integration oracle |
| Documentation restoration revives plan stage | Restore bounded Codex sections; retired-command checks |

## ✅ Success Criteria
- [x] Old agent names migrate once without losing user choices.
- [x] Spec-validator reconciles Claude findings for fresh and upgraded projects.
- [x] English native install/update guidance matches the shipped entrypoints.
- [x] Review and verification pass; landing is handed to the parent wrapup owner.

## Completion evidence
Final review: APPROVED, grade A; all seven lenses and two frozen confirmation passes completed. All five consensus findings were repaired, including bounded post-verification edits checked by the original core/test reviewers. Final CI: 9014 passed, 100 skipped, 3 xfailed, 4 warnings in 415.26s; ruff, format (766 files), and strict mypy (762 source files) passed. All six verify checks passed in `.claude/observability/codex-plan-integration-repair/verify.json`. Wrapup independently confirmed the fresh relevant verification marker `dcaa02ee8e40fa0eab97b79cd4cf03d1da315acbb344fecc58313a6018b6fcb3` with `PYTEST_XDIST_AUTO_NUM_WORKERS=14`. Native install/update, authenticated hostile-Claude smoke, and the nine-check old-version upgrade passed. Snapshot and autopilot golden updates were limited to execute hashes.

Implementation and documentation are complete. Commit and landing remain assigned to the parent wrapup owner; this document does not claim those operations have already occurred. No task-specific machine SPEC exists, so Step 3.5 binding is not applicable.
