---
type: plan
task_slug: codex-stage-invocation
status: complete
created: 2026-09-22
tags: [harness-maker, plan, python, codex, invocation]
spec: "[[SPEC-codex-stage-invocation]]"
interview_rounds: 0
adrs: 2
validator_outcome: NOT_RUN
summary: "Normalize generated Codex invocation guidance while preserving executable and user content."
spec_need_verdict: change
spec_need_target: codex-stage-invocation
---

## 🎯 Executive Summary
Repair runtime invocation formatting at generation boundaries, including stage bodies and common skills. The accepted scope comes from SPEC-codex-stage-invocation. Implementation and review used hm/codex-stage-invocation. The user subsequently authorized wrapup and push to main on 2026-09-22.

## 📚 Prior Work
Existing stage_invocation converts only banner slash commands to incorrect at-sign syntax. SPEC-plan-stage-absorption removed plan; research hands off to spec. Memory lessons: test named dimensions across all outputs; inspect newly reachable formatting inputs; snapshot regeneration pins source paths.

## 📐 Architecture Decision Records
### ADR-001: Format owned Markdown before merging user blocks
Use the existing stage_invocation global as the common formatting API. Make it aware of fenced executable examples, inline shell payloads, paths and user-block markers. Apply it only to Codex Markdown output before content hashing and before preservation merging. Template-level use remains valid and idempotent. Do not transform TOML/JSON/raw shell outputs.
### ADR-002: Keep advertised skills tied to actual installed surfaces
Keep six atomic stage names and research-to-spec behavior. Codex help must not advertise Claude-only meta commands as locally generated skills. Plugin setup/update are separate installed surfaces, not assumed by project help. Correct explicit Codex examples in source templates and documentation; do not rewrite historical PLANs/SPECs.

## 🏗️ Technical Design
Affected: template_globals.py formatter, render.py Markdown boundary, Codex AGENTS/help/stage usage templates, corresponding pytest coverage and fixture hashes. Render normalization precedes merge so custom text remains untouched. Normalize both old /hm: and @hm- spellings to dollar mentions; preserve hm: IDs. Explicit source updates reduce contradictory instructions even in direct template consumers.

## 📝 Implementation Plan
### Phase 1: Runtime-correct guidance and regression coverage
- depends_on: []
- parallel_group: serial
- merge_hazards: Shared formatting and rendered fixture outputs; implement serially.
- scope: src/harness_maker/template_globals.py, render.py, relevant templates, tests/unit/test_stage_invocation_syntax.py, affected render tests and snapshots; README.md/README.ko.md and SPEC/PLAN documents. Out: CLI semantics, workflow enums, user memory.
- exit criterion: `uv run pytest tests/unit/test_stage_invocation_syntax.py` followed by affected render/snapshot suites, ruff, mypy, and a full pytest pass.
- risk: medium — dollar signs inside shell examples change execution.
- rollback point: revert this task diff before landing; base tree remains unchanged.
- status: complete under the explicit one-time live Claude verification exception
- A.4 initial evidence: 16 failed, 4 passed; baseline passing tests are existing registration, non-command, and runtime banner invariants. Preserve them as negative controls; dollar guidance tests are RED siblings.

## 🚧 Contract Boundaries
### Do not change
- `src/harness_maker/models.py` — workflow stage enum and persisted schema.
- `src/harness_maker/worktree.py` — task ownership and landing.
- Advisory: Preserve executable shell/code examples, internal hm:stage IDs, file paths, user extension blocks, and Claude/Cursor invocation forms.

## 🧪 Testing Strategy
Run pytest RED before code, test-reviewer three-lens gate, GREEN then affected tests. Side/Production × en/ko/ja-fallback matrix; full outputs for AGENTS, stage/help and common skills; shell and user-block preservation; second update idempotence; fixed six-stage minimum plus advertised skill availability. Full suite once at phase exit. T2 mutation deferred.

## ⚠️ Risks & Mitigation
| Risk | Mitigation |
|---|---|
| Dollar expansion in shell | Preserve executable fences and inline shell examples verbatim |
| Formatting after merge edits user prose | Format new owned content first; explicit preservation test |
| Stale at-sign direct templates | Correct source template literals as well as common helper |
| Unsupported Codex help commands | Test every help invocation against generated inventory |

## ✅ Success Criteria
- [x] AC-001 runtime-correct guidance across render matrix.
- [x] AC-002 executable content and other runtime contracts preserved.
- [x] AC-003 all recommendations resolve, six stages remain, no plan recommendation.
- [x] AC-004 updates repair owned guidance and preserve extensions idempotently.

### Newly reachable window (Phase D.5)
- Full Markdown bodies (including Markdown-fenced summary examples) now reach the converter, where banners alone reached it before. Shell fences, inline shell strings, paths and user markers must retain bytes. `test_preserves_executable_and_non_codex_content` enters this window; text-fence and full rendered research assertions exercise conversion inside examples.
- Normalization runs before user-block merge. `test_update_repairs_guidance` uses actual merge reports and checks a well-formed AGENTS.md extension containing both legacy spellings over two updates. The legacy stage wrapper has duplicate extension IDs, which the existing merge parser rejects; that separate migration issue is outside this task and was not changed.
- Absent-case: false/missing Codex context bypasses Markdown normalization; `test_rewrites_only_for_codex`, Claude/Cursor output assertions and existing renderer tests cover it. No invocation tokens returns input unchanged.
- Test refinement: the shared skill reference is in its YAML description without inline backticks; corrected that assertion to the actual specified surface. The update test explicitly supplies merge_reports, as required by render's merge contract.

### Recovery-message coverage
The first GREEN probe exposed inline `BLOCKED: ... run /hm:review` messages that are prose despite inline-code formatting. Added assertions for verify, wrapup and verify-before-completion; observed RED (1 failed) before applying explicit `stage_invocation` at those template call sites. This keeps shell-payload classification conservative while making the three recovery messages runtime-correct.

### Verification selection
`hm test_dep_map` selected full with reason: `full suite: no test maps to specs/SPEC-codex-stage-invocation.machine.yaml, specs/SPEC-codex-stage-invocation.md`. Full pytest is run with the prescribed seven workers and `--dist loadfile`, excluding advisory checks. Ruff check/format and mypy --strict src tests passed before the final template-only recovery fix; changed Python/test paths are rechecked afterward.

## Final verification evidence
- Initial TDD screen: 16 failed, 4 existing negative controls passed. Test-reviewer round 1 FAIL was repaired; round 2 PASS. Spec-validator APPROVED; Codex second opinion invoked and findings incorporated.
- Final invocation regression suite: 20 passed. Related render/snapshot suite: 123 passed. After fixing full-suite findings, repaired-file suite: 104 passed (includes invocation, snapshots, project knowledge, autopilot golden, command-size budget and surface baseline).
- Ruff check: PASS. Ruff format --check: PASS. Final mypy --strict src tests: PASS (775 files). git diff --check: PASS. Final machine SPEC validation/cross-validation/quality check passes; quality 87. All four ACs bound to collected tests; no DRI approval stamp or landing asserted.
- Full suite attempt: 9 failed, 9103 passed, 100 skipped, 3 xfailed in 315.96 seconds. Five failures (two old at-sign expectations, two surface-size checks, one stale golden) repaired and reverified in the 104-pass run. No assertion thresholds relaxed. Removed whitespace growth rather than raising the surface budget.
- Autopilot SPEC golden mismatch reproduces with unmodified HEAD source in an isolated baseline extraction; recorded inherited drift and refreshed the fixture under its documented recapture procedure. Snapshot regeneration also refreshes the pre-existing spec/intent hashes; no corresponding source contract was changed.
- Four remaining live E2Es in tests/e2e/test_plugin_live.py are externally blocked: test_make_fresh_install_creates_harness_yaml, test_make_fresh_install_file_count, test_make_production_preset, test_make_no_interactive_prompts. Every Claude subprocess exits 1 with `You've hit your weekly limit · resets 10am (Asia/Seoul)`. This is not evidence of generated-harness success or failure. Do not claim all checks GREEN.

## External validation escalation
Binding constraint: the required live Claude service has exhausted its weekly quota. Read-only `stuck` analysis confirms all four tests fail before generated-output assertions. Recommendation A: retain the worktree and retry the four tests when service quota is available. No account or billing change is requested or performed. No immediate user decision is required; quota recovery must be verified before resuming.

[boundaries] comparison not performed — blocked exit. The formal GREEN-stage boundary gate remains pending with live E2E verification; changed paths below are retained for review. Base tracked files remain untouched; no commit, merge or task-land performed.

## Changed paths retained in the task worktree
- `README.ko.md`
- `README.md`
- `specs/SPEC-codex-stage-invocation.machine.yaml`
- `specs/SPEC-codex-stage-invocation.md`
- `src/harness_maker/render.py`
- `src/harness_maker/template_globals.py`
- `src/harness_maker/templates/agents/_partials/stage_end_summary.md.j2`
- `src/harness_maker/templates/codex/AGENTS.md.j2`
- `src/harness_maker/templates/commands/hm/configure.md.j2`
- `src/harness_maker/templates/commands/hm/health.md.j2`
- `src/harness_maker/templates/commands/hm/help.en.md.j2`
- `src/harness_maker/templates/commands/hm/help.ko.md.j2`
- `src/harness_maker/templates/commands/hm/loop-p5-batch.md.j2`
- `src/harness_maker/templates/commands/hm/loop.md.j2`
- `src/harness_maker/templates/commands/hm/metrics.md.j2`
- `src/harness_maker/templates/skills/verify-before-completion/SKILL.md.j2`
- `src/harness_maker/templates/stages/execute.md.j2`
- `src/harness_maker/templates/stages/research.md.j2`
- `src/harness_maker/templates/stages/verify.md.j2`
- `src/harness_maker/templates/stages/wrapup.md.j2`
- `tests/render/test_render_project_knowledge.py`
- `tests/snapshot/prod-firmware.expected.yaml`
- `tests/snapshot/prod-tauri-app.expected.yaml`
- `tests/snapshot/side-python-cli.expected.yaml`
- `tests/snapshot/side-tauri-app.expected.yaml`
- `tests/structural/autopilot_gate_golden.json`
- `tests/structural/test_autopilot_gate_render.py`
- `tests/structural/test_documented_commands_exist.py`
- `tests/unit/test_codex_phase4.py`
- `tests/unit/test_help_command.py`
- `tests/unit/test_stage_invocation_syntax.py`
- `work-docs/PLAN-codex-stage-invocation.md`

## Review follow-up
Review completed: grade A, APPROVED; see REVIEW-codex-stage-invocation-2026-09-22.md.
Three P1 guidance defects repaired (SPEC recovery, unavailable health/configure recommendations,
and shared-skill activation mentions). One P2 regression assertion gap remains.
Related verification passed; external live E2E limitation above remains, so plan status stays
verification-blocked. No commit or landing.

## Wrapup verification recovery (2026-09-22)
The user authorized wrapup and push to main. The first CI verification retry stopped
with two autopilot tests failing (6294 passed, 6 skipped). Both were caused by
test-generated session-aaa, b2-ask-session and degraded markers in /tmp/.claude:
resolve_marker_root resolved independent temporary projects to /tmp, sharing state
and looking up SPEC acceptance in the wrong root. Preserved the residual directory
at /tmp/hm-test-state-backup-rs_m5pxm/claude; no source/test assertions changed.
Both affected test files then passed (30 tests); the shared directory was not recreated.

Full CI retry: `uv run pytest -x --tb=short -n auto --dist loadfile`: 1 failed,
9030 passed, 77 skipped, 3 xfailed in 244.72 seconds. Autopilot failures did not recur.
Remaining failure: tests/e2e/test_plugin_live.py:108
(test_make_fresh_install_creates_harness_yaml), Claude rc=1 with
`You've hit your weekly limit · resets 10am (Asia/Seoul)`. The run stopped early,
so no claim that all remaining live E2Es passed. Ruff lint/format and strict mypy pass.
No passing verification marker, completed PLAN status, commit, landing or push.
The next required step is restoring Claude CLI quota and rerunning CI verification.


## Authorized wrapup completion (2026-09-22)
The user explicitly authorized a one-time exception for live Claude CLI checks,
verification in Codex, and commit/push to main if no other issue remained. This
supersedes the earlier blocked next-step notes for this invocation only. No test
or CI definition was changed; no general full-verification success marker was written.

- `uv run pytest -x --tb=short -n auto --dist loadfile --ignore=tests/e2e/test_plugin_live.py`:
  **9109 passed, 100 skipped, 3 xfailed**, 4 warnings in 260.66 seconds.
- Ruff lint and format passed; strict mypy passed over 775 source files.
- The prior two autopilot failures did not recur after the preserved `/tmp/.claude`
  state was moved out of ancestor discovery. This was an environment repair, with
  no weakened assertions or source changes.
- Only `tests/e2e/test_plugin_live.py` was excluded for this run. Its previous
  Claude quota failure remains unvalidated; this result is not a full live-Claude pass.
- Review drift verdict is clean for this task; review grade A, APPROVED remains.
  The accepted P2 Production recovery-message assertion gap is explicitly deferred.
- SPEC binding: 4 pytest-bindable ACs forward-bound, 0 pending; 0 judgment bound,
  0 judgment unbound. `find-unbound` and `find-unjudged` both passed.
- Intent is not in use for this task, as requested. Landing and push are owned by
  the parent wrapup stage; this document does not claim those operations occurred.
