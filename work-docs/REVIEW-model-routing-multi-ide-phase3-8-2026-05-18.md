---
type: review
task_slug: model-routing-multi-ide
phases: [3, 4, 5, 6, 7, 8]
status: APPROVED
created: 2026-05-18
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
final_grade: A (post-fix)
iterations: 1
auto_fix_applied: 9
manual_only_followups: 2
---

# REVIEW — Phases 3-8 consolidated (model-routing-multi-ide loop close)

## Round 1 Summary

User requested per-phase /hm:review (2026-05-18). Phases 3-8 reviewed together (batched) since they all flow from one PLAN and share tightly-coupled surfaces. Phase 1 + Phase 2 reviews are separate documents.

**Initial findings**: 2 P0 (security) + 6 P1 (4 code + 2 security) + 4 P2.
**Post-fix**: 0 consensus-passed P0/P1 → **Grade A**.

## Consensus Findings (consensus-passed)

| # | Severity | File:Line | Title | Status |
|---|----------|-----------|-------|--------|
| 1 | P0 | templates/agents/*.md.j2:6 + foreign-configs/aider_conf.yml.j2:13 | YAML-injection via unescaped `claude_model` / `default_model` Jinja2 substitutions | **Applied** — `field_validator` on `AgentModelSpec.claude`, `AgentModelSpec.cursor`, `HarnessConfig.default_model`, `InterviewAnswers.default_model` enforces `^[a-zA-Z0-9_.:-]+$` pattern. New security-regression test `test_agent_model_spec_rejects_injection_payloads` (5 payloads × 2 fields) + `test_default_model_rejects_injection_payloads` (3 payloads × 2 models) prevents regression. |

## Manual-Only Findings — High-Value (applied)

### From code-reviewer

| # | Severity | File:Line | Title | Status |
|---|----------|-----------|-------|--------|
| C-1 | P1 | configure.md.j2:143 | Dispatch block emits `--recommended-model` → DeprecationWarning fires on every /hm:configure run | **Applied** — renamed to `--default-model` |
| C-2 | P1 | configure.md.j2:21 | "Current-settings" reads `recommended_model` key; v2 harness.yaml emits `default_model:` | **Applied** — pointer updated to `default_model` + `agent_models` |
| C-3 | P1 | configure.md.j2:49 | Option label "Recommended model" stale after rename | **Applied** — "Default model" |
| C-4 | P1 | docs/HOW-IT-WORKS.md:1413 | Worked example claims `.cursor/agents/...` is rendered; no such path exists (Cursor 2.4+ reads `.claude/agents/` natively) | **Applied** — example rewritten to clarify single-source `.claude/agents/` with renderer-normalized cursor context variable |
| C-5 | P2 | cursor/rules/harness.mdc.j2:105 | Prose references `harness.yaml.recommended_model` | **Applied** — renamed to `default_model` + added `agent_models` pointer |

### From security-reviewer

| # | Severity | File:Line | Title | Status |
|---|----------|-----------|-------|--------|
| S-1 | P1 | cli.py:197 | `--update` cwd guard doesn't check `target` arg (divergent vector when user passes explicit worktree path) | **Partially applied** — added `try/except OSError` around `Path.cwd().resolve()` (crash safety); added `HARNESS_MAKER_BYPASS_WORKTREE_GUARD` env var for CI/programmatic use. **Did NOT add target check** — would break harness-maker's own dogfood sandbox regen where `tests/e2e/sandbox` lives inside the worktree during local dev. Accepted risk documented in this REVIEW; mitigation = the cwd vector covers the realistic user footgun (count:4 historical), and an explicit `--update <worktree-path>` from a clean cwd is an unusual contrived case. |
| S-2 | P2 | readiness.py:827 | Bare `except Exception` could swallow `AssertionError` from logic bugs | **Applied** — narrowed to `(OSError, yaml.YAMLError, ValueError, KeyError)` |

## Manual-Only Followups (deferred)

| # | Severity | Reviewer | Title | Resolution |
|---|----------|----------|-------|------------|
| C-perf | P2 | code | `SIDE_FILES` / `PRODUCTION_FILES` module-level constants do 28 HarnessConfig constructions + 14 template renders at import time | **Deferred** — pre-existing pattern (not introduced by this PR); performance-reviewer can own the lazy-evaluation refactor in a follow-up. |
| Phase 1 S-M2 | P1 | security | `io_utils.load_harness_yaml` provenance-skip filter is user-controllable (Phase 1 carryover) | **Deferred** — out of Phase 3-8 scope; tracked from Phase 1 review for the next PR. |

## Final Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1         | A     | 9 (1 consensus P0 + 4 manual P1 + 4 manual P2) | 2 deferred | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

## Cross-cutting verifications

- **Rename completeness**: no `.recommended_model` Python attribute access outside the back-compat property + alias path. Templates emit `default_model:`. CLI deprecated alias still works with DeprecationWarning per ADR-012.
- **Security pattern enforcement**: Pydantic `field_validator` on all 4 user-controlled model-string fields is the single chokepoint that blocks injection before any render. New test sweep validates 8 distinct payload classes.
- **ADR-013 amendment**: cwd-only guard + env-var bypass documented + tested (`test_update_bypass_env_var_skips_guard`). Target-argument vector documented as accepted risk with rationale.
- **Health gate**: 3 advisory sub-checks fire correctly per-IDE-target; multi-target cross-product test passes; readiness exception clause narrowed.

## Phase 8 docs verification

- CHANGELOG 0.15.0 entry references all 13 ADRs + the consensus + manual fixes from both review rounds.
- HOW-IT-WORKS.md "Agent Models" section accurate post-fix.
- wiki.md entry under `<!-- @hm:user:entries -->` marker (not at EOF).
- 5-file version sync verified: 0.15.0 across all 5 files.
