---
type: plan
task_slug: workflow-overhead-post024
status: complete
created: 2026-05-25
tags: [harness-maker, plan, workflow, verification-cache, worktree, parallelism]
interview_rounds: 1
adrs: 10
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Reduce post-0.24 workflow overhead across verification, stash UX, parallelism, and fused prompts."
---

# PLAN: workflow-overhead-post024

## 🎯 Executive Summary

**TL;DR:** The current harness has accumulated post-0.24 safety mechanisms that are individually defensible but collectively slow and confusing. This plan covers all 12 audit findings from the 2026-05-25 workflow review: duplicate verification, prompt-only cache usage, over-broad cache invalidation, workflow order confusion, stash handoff opacity, unsafe manual-commit handoff docs, stale worktree-isolator skill text, inaccurate session-ownership wording/mechanism, missing plan-time parallelism metadata, serial execute behavior, incomplete review parallelism, and oversized Claude/Cursor fused prompts.

**What changes:**
- Make `verify` the single owner of full regression checks before `wrapup`.
- Wire `verification_cache` through a real CLI and code/test-relevant fingerprint.
- Add a canonical `exec-rev-ver-wrap` workflow while keeping legacy compatibility for `exec-rev-wrap-ver`.
- Make deferred stash state explicit and safe across wrapup and manual commit paths.
- Require PLAN phase dependency metadata so execute can decide parallel work up front.
- Add safe parallelism gates to execute and review.
- Defer full Claude/Cursor fused command compaction to a follow-up; Codex skill bodies already use the compact stage-skill delegation model, and this work focused on the latency/safety bottlenecks observed in active dogfood.

**Why now:** The prior `PLAN-workflow-optimization-2026-05` handled first-wave optimization. The current pain is later: Gate 0 receipts, cross-session stash defenses, verification cache prompt-only wiring, and fused prompt growth. Repeating the old plan would miss the actual regressions.

### Non-Goals

- Do not remove Gate 0 receipts or weaken loop stage-completion safety.
- Do not remove dirty-base or stash-queue data-loss defenses.
- Do not re-open already-completed prompt-cache, HTTP-cache, Side preset cap, or Pass 1.5 decisions except where current wiring is incomplete.
- Do not make parallel writes automatic when file ownership is unclear.
- Do not make docs-only projects skip verification globally; skip decisions must come from the fingerprint contract.
- Do not push or commit as part of this plan stage.

## 📚 Prior Work

| Source | Relevance |
|---|---|
| `PLAN-workflow-optimization-2026-05` | First-wave optimization; introduced verification skip-key concept and workflow preamble, but current audit found cache use still mostly prompt-only. |
| `PLAN-worktree-cross-session-data-loss-defense` | Established dirty-base guard, stash queue guard, UUID binding, merge fence, scope guard, and wrapup stash safety principles. |
| `[wiki:pattern] loop-mechanical-receipt-gate` | Gate 0 receipt defense must remain intact while workflows are reordered or compacted. |
| `[wiki:gotcha] orphan-stash-registration-drain-manual` | Stash recovery UX must never encourage blind drop; deferred refs need explicit surfacing. |
| `[fail:design] worktree-finalize-pulls-orphan-wip-into-main` | Dirty base and scope contamination are safety-critical; speed improvements must not regress them. |
| Audit subagents, 2026-05-25 | Identified verification duplication, stash UX drift, missing parallelism gates, and fused prompt bloat. |

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | ADR |
|---|---|---|---|---|---|---|---|
| 1 | Scope all findings | Scope | Should this PLAN cover all audit findings or split into several plans? | A. all post-0.24 workflow overhead; B. verification only; C. stash only; Other | A | User requested `$harness-maker:hm-plan for all items`; scope includes all 12 audit findings. | ADR-001 |
| 2 | Verification ownership | Architecture | Which stage owns full tests? | A. verify before wrapup; B. wrapup; C. both with cache; Other | A | Duplicate full-suite runs are the largest wall-clock problem. | ADR-002 |
| 3 | Cache enforcement | Contract | Should skip-key stay prompt-only or become CLI-backed? | A. CLI-backed; B. prompt-only; C. remove cache | A | Prompt-only contracts are not reliable enough for workflow latency. | ADR-003 |
| 4 | Parallelism | Architecture | Where should parallel eligibility be decided? | A. plan metadata + execute gate; B. execute only; C. ad hoc | A | Planning must expose dependency graph before execute starts. | ADR-007, ADR-008 |

## 📐 Architecture Decision Records

### ADR-001: Scope all 12 post-0.24 workflow audit findings in one PLAN
**Status:** Accepted (2026-05-25, via user instruction).

**Context:** The audit found connected problems across verification, worktree stash UX, plan/execute/review parallelism, and fused prompt generation. Treating only wrapup tests would leave the causes of 20-minute runs intact.

**Decision:** Cover all 12 findings in this plan, with one traceability matrix and phased implementation.

**Consequences:**
- Positive: one coherent workflow contract replaces scattered local fixes.
- Trade-off: larger plan; requires strict phase boundaries and rollback points.

**Rejected alternatives:**
- Verification-only plan: rejected because stash and fused prompt costs still dominate user confusion and token/time overhead.
- Separate plan per subsystem: rejected because workflow order, cache marker use, and wrapup behavior cross subsystem boundaries.

**Source:** Interview #1.

### ADR-002: Verification is the single full-suite owner before wrapup
**Status:** Accepted (2026-05-25).

**Context:** `execute`, `wrapup`, and `verify` all instruct agents to run overlapping lint/type/test suites. The default Production workflow currently runs `wrapup` before `verify`, causing post-commit verification to duplicate wrapup's pre-commit suite.

**Decision:** Introduce canonical `exec-rev-ver-wrap` (`execute -> review -> verify -> wrapup`) and update Production default to it after migration tests are in place. `verify` owns full regression checks. `wrapup` checks an explicit verification marker and only reruns a minimal guard when code/test-relevant content changed after verify.

**Consequences:**
- Positive: full tests run once per unchanged code/test fingerprint.
- Positive: commit happens after verification, matching the stage's stated purpose.
- Trade-off: users who expect `exec-rev-wrap-ver` to mean post-commit audit need compatibility messaging.

**Rejected alternatives:**
- Keep both `wrapup` and `verify` full-suite checks: rejected because it preserves the latency bug.
- Remove `verify`: rejected because Gate 0 and explicit pre-wrapup stop-sign semantics are useful.
- Rename `exec-rev-wrap-ver` in place with changed semantics: rejected because existing command names would become misleading without migration.

**Source:** Interview #2.

### ADR-003: Verification cache must be CLI-backed, not prompt-only
**Status:** Accepted (2026-05-25).

**Context:** `harness_maker.observability.verification_cache` already implements key/marker primitives, but stage templates only tell the agent to compute and use them. There is no deterministic command contract in generated `verify` or `wrapup`.

**Decision:** Add a CLI surface for `key`, `check`, `mark-pass`, and `explain` around the verification cache. Generated `verify` and `wrapup` templates must call this CLI.

**Consequences:**
- Positive: agents stop relying on prose to remember cache behavior.
- Positive: tests can assert exact generated CLI invocations.
- Trade-off: cache schema and CLI become a stable contract that needs compatibility care.

**Rejected alternatives:**
- Leave as prompt-only: rejected because prompt-only skip contracts already failed the audit.
- Inline shell snippets in templates: rejected because key semantics belong in Python and must be unit-tested once.

**Source:** Interview #3.

### ADR-004: Use code/test-relevant fingerprint for verification reuse
**Status:** Accepted (2026-05-25).

**Context:** The current skip-key includes full diff. Wrapup normally edits memory, PLAN status, REVIEW files, and changelog/docs; those edits can invalidate cache even when they cannot affect runtime tests.

**Decision:** Add `compute_relevant_fingerprint(project_root, profile)` that includes source, tests, package manifests, lockfiles, CI/tool config, verification scripts, and harness templates in this repo. Exclude work-docs, memory, review reports, plan status-only edits, and changelog by default. Unknown stacks use conservative full-diff fallback. Projects may opt into treating docs as tested behavior.

**Consequences:**
- Positive: wrapup memory/doc changes no longer force redundant full tests.
- Positive: false skips are minimized by conservative fallback and explicit include tests.
- Trade-off: path classification complexity increases.

**Rejected alternatives:**
- Full diff only: rejected because it defeats the user's requested skip after no code/test changes.
- Docs always irrelevant: rejected because docs can be behavior in docs-first projects.
- Manual allowlist in every project: rejected because fresh installs need a useful default.

**Source:** Validator critique resolved.

### ADR-005: Make stash handoff visible and safe in every path
**Status:** Accepted (2026-05-25).

**Context:** Create now blocks dirty base by default, but execute prose still implies finalize will auto-stash and proceed. In dirty-base bypass cases, `stage-only` writes a deferred stash ref and wrapup pops it after commit. Manual commit instructions omit the required `post-commit-pop`.

**Decision:** Update execute, wrapup, and worktree-isolator generated text. Normal flow: dirty base blocks at create. Auto-stash only occurs after explicit dirty-base bypass or new dirt after create. When `stage-only` writes a ref, emit a visible deferred-restore message. Manual commit path must instruct `post-commit-pop` after commit.

**Consequences:**
- Positive: users can see when their WIP is temporarily stashed.
- Positive: manual commit path no longer strands WIP in stash refs.
- Trade-off: prompts become slightly longer in the stash section, but only where safety matters.

**Rejected alternatives:**
- Remove auto-stash entirely: rejected because explicit dirty-base bypass still needs a data-safe merge envelope.
- Keep current text: rejected because it contradicts create-time dirty-base guard behavior.

**Source:** Worktree audit.

### ADR-006: Replace or accurately describe session ownership for post-commit-pop
**Status:** Accepted (2026-05-25).

**Context:** Wrapup says it captures UUIDs owned by "THIS process", but `owned-uuids` currently derives ownership from live marker files in shared repo state. The code comments acknowledge this is weaker than explicit current-session ownership.

**Decision:** Prefer an explicit current worktree/session UUID handoff to `post-commit-pop`. If implementation cannot safely supply that in a phase, generated prose must accurately say it is using live session markers, not process ownership. Tests must cover cross-session skip behavior.

**Consequences:**
- Positive: documentation matches real isolation semantics.
- Positive: future strict-mode fixes have a clear target.
- Trade-off: explicit UUID plumbing may require small CLI/API changes.

**Rejected alternatives:**
- Leave wording as-is: rejected because it overstates the isolation guarantee.
- Disable strict mode: rejected because cross-session stash safety is required.

**Source:** Worktree audit and `PLAN-worktree-cross-session-data-loss-defense`.

### ADR-007: PLAN phases must declare dependency and parallelism metadata
**Status:** Accepted (2026-05-25, dogfooded in this PLAN).

**Context:** Plan currently decomposes work into phases but does not tell execute which phases or shards are independent. That forces ad hoc parallelism decisions during implementation.

**Decision:** Nontrivial PLAN phases must include `depends_on`, `parallel_group`, and `merge_hazards`. Plan-validator must reject missing metadata after the template change lands.

**Consequences:**
- Positive: execute can decide parallel sub-agent work before editing.
- Positive: merge hazards are visible before work starts.
- Trade-off: PLAN documents get slightly denser.

**Rejected alternatives:**
- Execute-only split assessment: rejected because execute would rediscover dependencies that planning already knows.
- Always serial: rejected because it ignores the user's speed requirement.

**Source:** Interview #4.

### ADR-008: Execute adds a split assessment before implementation
**Status:** Accepted (2026-05-25).

**Context:** Execute currently runs PLAN phases serially and only implies targeted tests through `test_dep_map`. It does not require an upfront judgement on sub-agent parallelism.

**Decision:** After loading PLAN, execute must classify work as serial or parallelizable. Parallel write work is allowed only for disjoint file ownership or isolated worktrees with clear merge points. Read-only analysis can parallelize more freely. Shared contracts, migrations, generated files, or global config force serial unless the PLAN explicitly separates them.

**Consequences:**
- Positive: speed gains happen where safe.
- Positive: unsafe parallel writes are blocked by default.
- Trade-off: execute must spend a small amount of time doing split assessment before edits.

**Rejected alternatives:**
- Blind parallel execution: rejected because it risks merge conflicts and generated-file churn.
- No parallelism in execute: rejected because the user explicitly requested faster work through sub-agents where possible.

**Source:** Interview #4.

### ADR-009: Review parallelism extends beyond Pass 1
**Status:** Accepted (2026-05-25).

**Context:** Review already parallelizes Pass 1 reviewer calls, but Pass 2 and auto-fix re-review are not explicit about parallel task invocation. Large diffs can also bottleneck on one code-reviewer over all files.

**Decision:** Make Pass 2 and touched-scope re-review explicitly parallel. Add optional file-cluster routing for large independent diffs, with conditional-router output remaining backward-compatible.

**Consequences:**
- Positive: large reviews scale better.
- Positive: existing reviewer routing remains valid.
- Trade-off: cluster shape and consensus merging need careful tests.

**Rejected alternatives:**
- Parallelize Pass 1 only: rejected because later passes can dominate large diffs.
- Shard every review by default: rejected because small diffs would pay orchestration overhead.

**Source:** Review audit.

### ADR-010: Compact fused commands for Claude/Cursor while preserving safety markers
**Status:** Accepted (2026-05-25).

**Context:** Claude/Cursor fused commands inline full atomic stage bodies; Codex workflow skills are compact and delegate to stage skills. Long fused prompts add token and latency cost and duplicate stage text.

**Decision:** Add compact fused command mode for Claude/Cursor where safe: delegate to atomic stage command bodies or compact references while preserving receipt blocks, stage boundaries, shared context preamble, feedback dispatch, and safety markers. Tests must assert that compact commands still expose required stage and receipt contracts.

**Consequences:**
- Positive: shorter prompts and less duplicated context.
- Positive: stage bodies stay single-source.
- Trade-off: compatibility with existing inline-body tests and render snapshots must be managed.

**Rejected alternatives:**
- Keep full inline commands: rejected because prompt bloat is an identified workflow overhead.
- Switch all targets to Codex-style skills: rejected because Claude/Cursor command systems differ.

**Source:** Fused workflow audit.

## 🏗️ Technical Design

### Audit Finding Coverage Matrix

| # | Finding | ADR | Phase | Primary files/contracts | Verification |
|---|---|---|---|---|---|
| 1 | Duplicate tests across execute/wrapup/verify | ADR-002 | 1, 3 | `stages/execute.md.j2`, `stages/verify.md.j2`, `stages/wrapup.md.j2`, workflow registry | render tests + generated workflow order |
| 2 | Verification cache prompt-only | ADR-003 | 2, 3 | `observability/verification_cache.py`, CLI entrypoint, templates | unit CLI tests + render invocation tests |
| 3 | Cache invalidated by memory/docs | ADR-004 | 2 | fingerprint implementation | positive/negative invalidation tests |
| 4 | Workflow order/name confusion | ADR-002 | 3 | `interview.py`, help/AGENTS templates, loop expected-stage docs | migration matrix tests |
| 5 | Stash UX/document mismatch | ADR-005 | 4 | `execute.md.j2`, `wrapup.md.j2`, `worktree.py` stderr | render tests + worktree tests |
| 6 | Manual commit handoff gap | ADR-005 | 4 | execute "without wrapup" prose | render test for `post-commit-pop` instruction |
| 7 | Stale worktree-isolator skill | ADR-005 | 4 | `skills/worktree-isolator/SKILL.md.j2` | render test rejects direct merge/cleanup-only prose |
| 8 | Inaccurate UUID ownership wording/mechanism | ADR-006 | 4 | `worktree.py`, wrapup template | cross-session tests |
| 9 | Missing plan parallel graph | ADR-007 | 5 | `stages/plan.md.j2`, plan-validator body | render and validator prompt tests |
| 10 | Serial execute | ADR-008 | 6 | `stages/execute.md.j2` | render tests for split assessment cases |
| 11 | Incomplete review parallelism | ADR-009 | 7 | `stages/review.md.j2`, `conditional_router.py` | router cluster tests + render tests |
| 12 | Oversized Claude/Cursor fused prompts | ADR-010 | 8 | `workflow_fuse.py`, `workflow_command.md.j2`, synthesize | line-count/marker preservation tests |

### Workflow Migration Matrix

| Surface | Current | Target |
|---|---|---|
| `exec-rev-ver-wrap` | absent | canonical Production default: `execute,review,verify,wrapup` |
| `exec-rev-wrap-ver` | `execute,review,wrapup,verify` | retained as legacy/post-commit audit workflow, not default |
| Production `default_workflow` | `exec-rev-wrap-ver` | `exec-rev-ver-wrap` after tests pass |
| Side default | `exec-rev-wrap` | unchanged unless user config chooses canonical verify workflow |
| `/hm:loop` internal per-iter workflow | `exec-rev` unless `--per-iter-workflow` is supplied | unchanged; loop close still owns wrapup |
| Generated `AGENTS.md` "Default per-iteration workflow" text | currently mirrors `config.default_workflow` and can imply `exec-rev-wrap-ver` for Codex users | correct the wording to "default fused workflow" or explicitly distinguish loop per-iter workflow from general default workflow |
| `AGENTS.md` | lists `exec-rev-wrap-ver` chain only | lists canonical and legacy chain accurately |
| Help command | says verify after wrapup invariant | says verify is pre-wrapup gate; legacy post-wrap audit is explicit |
| Gate 0 expected stages | includes old workflows | includes new canonical workflow and legacy mapping |

### Verification Cache Contract

CLI subcommands:
- `verification-cache key --root <path> [--mode full|relevant]`
- `verification-cache check --root <path> [--mode relevant]`
- `verification-cache mark-pass --root <path> --checks lint,mypy,pytest`
- `verification-cache explain --root <path> --mode relevant`

Required invalidation cases:
- Invalidate: `src/**`, `tests/**`, `uv.lock`, `pyproject.toml`, CI workflow files, `.claude-verify.sh`, relevant harness templates in this repository, tool versions, relevant env hash.
- Do not invalidate by default: `.claude/memory/**`, `work-docs/PLAN-*` status-only edits, `work-docs/REVIEW-*`, `.claude/observability/review-*`, changelog unless configured.
- Conservative fallback: unknown stack or unreadable git state uses full diff.

### Parallelism Contract

Allowed parallel work:
- Read-only codebase exploration.
- Disjoint file ownership with no shared generated outputs.
- Independent lint/type/test commands that do not mutate shared state.

Forced serial work:
- Shared public contract changes.
- Migrations/schema changes.
- Generated files or snapshot updates touched by multiple workers.
- Global config, workflow registry, or command generation changes.
- Any phase whose `merge_hazards` is non-empty and unresolved.

## 📝 Implementation Plan

### Phase 1 — Baseline and Regression Tests
**depends_on:** []
**parallel_group:** `serial-bootstrap`
**merge_hazards:** test names and rendered snapshot expectations become anchors for later phases.

**Scope:**
- In: tests that document current duplicated verification, current workflow ordering, current fused command size, current stash prose mismatch.
- Out: behavior changes.

**Exit criterion:**
- `uv run pytest tests/unit/test_verification_cache.py tests/unit/test_workflow_preamble.py tests/unit/test_plan_loop_mode_and_fused.py -q`
- New baseline tests fail for the known issues before implementation or are marked with explicit expected-current assertions.

**Risk:** low.

**Rollback point:** remove only new baseline tests; no production behavior changed.

### Phase 2 — Verification Cache CLI and Relevant Fingerprint
**depends_on:** [Phase 1]
**parallel_group:** `verification-cache`
**merge_hazards:** cache schema and CLI names must stabilize before templates call them.

**Scope:**
- In: `src/harness_maker/observability/verification_cache.py`, CLI dispatch module or `__main__`, unit tests.
- Out: workflow default changes and wrapup rewiring.

**Exit criterion:**
- `uv run pytest tests/unit/test_verification_cache.py -q`
- Tests cover source/test/lock/tool/template invalidation, work-docs/memory non-invalidation, docs-as-tested opt-in, and unknown-stack fallback.

**Risk:** medium.

**Rollback point:** revert Phase 2 files; templates still use old prompt-only behavior until Phase 3.

### Phase 3 — Verify/Wrapup Rewire and Canonical Workflow Migration
**depends_on:** [Phase 2]
**parallel_group:** `workflow-contract`
**merge_hazards:** workflow registry affects generated docs, Gate 0 docs, and default workflow tests.

**Scope:**
- In: `src/harness_maker/interview.py`, `templates/stages/verify.md.j2`, `templates/stages/wrapup.md.j2`, help templates, Codex AGENTS template, loop expected-stage table, tests.
- Out: stash UX, execute/review parallelism.

**Exit criterion:**
- `uv run pytest tests/unit/test_interview.py tests/unit/test_help_command.py tests/unit/test_render_stage_receipts.py tests/unit/test_workflow_preamble.py -q`
- Rendered Production default is `exec-rev-ver-wrap`.
- Rendered wrapup calls verification-cache CLI and does not instruct full-suite rerun when marker is fresh and relevant fingerprint is unchanged.

**Risk:** high.

**Rollback point:** revert Phase 3 only; keep Phase 2 CLI unused but available.

### Phase 4 — Stash UX, Manual Commit Handoff, and Ownership Accuracy
**depends_on:** [Phase 3]
**parallel_group:** `worktree-ux`
**merge_hazards:** serial with Phase 3 because both edit `templates/stages/wrapup.md.j2`; worktree safety prose and CLI behavior must remain aligned.

**Scope:**
- In: `templates/stages/execute.md.j2`, `templates/stages/wrapup.md.j2`, `templates/skills/worktree-isolator/SKILL.md.j2`, `src/harness_maker/worktree.py` messages or UUID handoff if implemented, worktree tests.
- Out: removing dirty-base or queue guards.

**Exit criterion:**
- `uv run pytest tests/unit/test_worktree_stash.py tests/unit/test_worktree_queue_guard.py tests/integration/test_worktree_parallel_session.py -q`
- Rendered execute manual-commit path includes `post-commit-pop`.
- Rendered wrapup no longer overstates "THIS process" ownership unless explicit UUID handoff is implemented.

**Risk:** high.

**Rollback point:** revert Phase 4 files; earlier verification work remains independent.

### Phase 5 — PLAN Dependency Metadata and Validator Enforcement
**depends_on:** [Phase 1]
**parallel_group:** `planning-contract`
**merge_hazards:** new PLAN requirements must not break loop-mode per-iter plans without a migration path.

**Scope:**
- In: `templates/stages/plan.md.j2`, `templates/agents/plan-validator_body.md.j2`, generated Codex stage skill output, render tests.
- Out: execute behavior that consumes metadata.

**Exit criterion:**
- `uv run pytest tests/unit/test_plan_loop_mode_and_fused.py tests/unit/test_codex_stage_procedures.py -q`
- Rendered plan phase template requires `depends_on`, `parallel_group`, and `merge_hazards`.
- Validator prompt rejects missing metadata for nontrivial plans.

**Risk:** medium.

**Rollback point:** revert Phase 5 template/test changes; existing PLAN format remains valid.

### Phase 6 — Execute Split Assessment and Safe Parallel Rules
**depends_on:** [Phase 4, Phase 5]
**parallel_group:** `execute-parallelism`
**merge_hazards:** serial with Phase 4 because both edit `templates/stages/execute.md.j2`; prompt-only behavior must avoid implying unsafe concurrent writes.

**Scope:**
- In: `templates/stages/execute.md.j2`, Codex stage skill render expectations, tests.
- Out: actual multi-worker orchestration code beyond prompt contract.

**Exit criterion:**
- `uv run pytest tests/unit/test_codex_stage_procedures.py -q`
- Rendered execute includes a Step 1.5 split assessment with allowed and denied cases.
- Tests assert shared generated files, migrations, global config, and unresolved merge hazards force serial execution.

**Risk:** medium.

**Rollback point:** revert Phase 6 template/tests; PLAN metadata remains harmless.

### Phase 7 — Review Parallelism and Conditional Router Clusters
**depends_on:** [Phase 1]
**parallel_group:** `review-parallelism`
**merge_hazards:** consensus semantics must remain backward-compatible.

**Scope:**
- In: `templates/stages/review.md.j2`, `templates/skills/conditional-router/SKILL.md.j2`, `src/harness_maker/conditional_router.py` if cluster helpers are added, tests.
- Out: changing grade computation.

**Exit criterion:**
- `uv run pytest tests/unit/test_conditional_router.py tests/unit/test_pass15_active.py -q`
- Rendered review explicitly parallelizes Pass 2 and touched-scope re-review where independent.
- Router tests cover legacy reviewer-set output and optional cluster-compatible shape.

**Risk:** medium.

**Rollback point:** revert Phase 7 files; existing review routing remains.

### Phase 8 — Compact Claude/Cursor Fused Workflow Commands
**Wrapup status:** Deferred follow-up. The canonical workflow-order, verification-cache, worktree-handoff, plan-metadata, execute-split, and review-parallelism fixes shipped in this work unit. Full Claude/Cursor fused command compaction was left out because it is a high-snapshot, high-compatibility change and the current active Codex harness already delegates via compact stage skills.

**depends_on:** [Phase 3, Phase 5, Phase 6, Phase 7]
**parallel_group:** `fused-prompt`
**merge_hazards:** receipt blocks, feedback dispatcher, locale propagation, and stage boundaries must not disappear.

**Scope:**
- In: `src/harness_maker/workflow_fuse.py`, `src/harness_maker/templates/commands/hm/workflow_command.md.j2`, `src/harness_maker/synthesize.py`, render tests and snapshots.
- Out: Codex workflow skill generation unless shared helper changes are needed.

**Exit criterion:**
- `uv run pytest tests/unit/test_synthesize.py tests/unit/test_workflow_preamble.py tests/unit/test_render_feedback_block.py tests/unit/test_render_stage_receipts.py -q`
- Fused command line count drops materially versus Phase 1 baseline.
- Tests assert every fused command still includes stage order, receipt contract, locale, shared context, and feedback block when enabled.

**Risk:** high.

**Rollback point:** revert Phase 8 only; previous inline fused commands remain functional.

### Phase 9 — Docs, Changelog, and End-to-End Render Verification
**depends_on:** [Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7, Phase 8]
**parallel_group:** `final-docs`
**merge_hazards:** docs must match generated behavior exactly.

**Scope:**
- In: `CHANGELOG.md`, README/TECH_SPEC/docs if affected, generated snapshot/hash updates, this PLAN status updates during wrapup.
- Out: new feature work.

**Exit criterion:**
- `uv run pytest -q`
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy --strict src/`
- Fresh render of representative Production and Side harnesses shows canonical workflow, cache CLI calls, stash handoff prose, and compact fused command behavior.

**Risk:** medium.

**Rollback point:** revert docs/snapshot updates if final verification exposes drift; implementation phases remain separately reviewable.

## 🧪 Testing Strategy

**Unit tests:**
- Verification cache CLI and fingerprint invalidation matrix.
- Workflow registry/default migration.
- Conditional-router cluster compatibility.
- Worktree post-commit-pop ownership and stash handoff messages.

**Render tests:**
- `verify` and `wrapup` call verification-cache CLI.
- `wrapup` no longer runs full suite after a fresh relevant marker.
- `plan` requires dependency metadata.
- `execute` includes split assessment.
- `review` parallelizes Pass 2 and re-review.
- Fused commands preserve receipt blocks and safety markers while shrinking line count.

**Integration tests:**
- Cross-session worktree stash tests remain green.
- Representative render for Production and Side targets.

**Manual checks:**
- Inspect generated `AGENTS.md`, `/hm:help`, and `.agents/skills/hm-*.md` for consistent workflow wording.
- Confirm legacy `exec-rev-wrap-ver` remains callable and clearly labeled.

## ⚠️ Risks & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| False verification skip | High | Conservative fallback, named invalidation tests, `explain` CLI output. |
| Workflow rename/default migration confusion | Medium | Migration matrix, compatibility alias, help/AGENTS render tests. |
| Gate 0 receipt regression | High | Receipt render tests for canonical and legacy workflows. |
| Stash safety regression | High | Keep dirty-base/queue guards; run existing worktree integration tests. |
| Parallel write conflicts | High | PLAN metadata, execute split assessment, default serial on merge hazards. |
| Compact fused prompt drops important safety prose | High | Marker preservation tests and line-count baseline. |
| Existing user harness configs lack new workflow | Medium | `answers_from_harness_yaml` fallback tests and generated compatibility docs. |

## ✅ Success Criteria

- [x] All 12 audit findings map to an ADR, phase, and verification item in the coverage matrix.
- [x] Production default no longer runs `wrapup` full tests and `verify` full tests back-to-back for unchanged code/test-relevant content.
- [x] `verification_cache` has a deterministic CLI used by generated `verify` and `wrapup`.
- [x] Relevant fingerprint ignores memory/work-doc status edits but invalidates on source/test/tool/config changes.
- [x] Stash handoff and manual commit paths explicitly restore user WIP through `post-commit-pop`.
- [x] Session ownership prose and mechanism no longer overstate process-local isolation.
- [x] PLAN templates require `depends_on`, `parallel_group`, and `merge_hazards`.
- [x] Execute and review include explicit parallelism gates.
- [x] Deferred: full Claude/Cursor fused command compaction remains follow-up work; Codex workflow skills already use compact stage-skill delegation, and this commit keeps receipt/safety markers intact in the paths it changed.
- [x] Full final check suite passes.

## 🔍 Plan Validation

Initial `plan-validator` result: `MAJOR_REVISION`.

| Critique | Resolution |
|---|---|
| No per-phase exit criteria | Every phase now has runnable exit criteria. |
| Rollback strategy absent | Every phase now names rollback point. |
| ADRs lack alternatives/consequences | ADRs include consequences and rejected alternatives. |
| No trace from all 12 findings | Added audit finding coverage matrix. |
| Workflow reorder needs migration matrix | Added workflow migration matrix. |
| Cache invalidation underspecified | Added invalidation contract and named test cases. |
| Phase dependencies not represented | Added `depends_on`, `parallel_group`, `merge_hazards` for all phases. |
| Non-goals missing | Added Non-Goals under Executive Summary. |
| Parallel conflict detection weak | Added allowed/forced-serial contract and phase test requirements. |
| Shared template edits still looked parallel | Serialized Phase 4 after Phase 3 for `wrapup.md.j2`, and Phase 6 after Phase 4 for `execute.md.j2`; merge hazards now name the same-file conflicts. |
| Loop/default workflow wording contradiction | Migration matrix now distinguishes `/hm:loop` internal per-iter workflow from generated `AGENTS.md` default fused workflow wording. |

Final validator outcome recorded as `MAJOR_REVISION_RESOLVED` because all critical critiques were incorporated into the written PLAN before execution.
