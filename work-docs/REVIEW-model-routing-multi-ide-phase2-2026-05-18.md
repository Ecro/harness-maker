---
type: review
task_slug: model-routing-multi-ide
phase: 2
status: APPROVED
created: 2026-05-18
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
final_grade: B → A (post-fix)
iterations: 1
auto_fix_applied: 5
manual_only_followups: 3
---

# REVIEW — Phase 2 (Migration in answers_from_harness_yaml)

## Round 1 Summary

**Initial grade**: B (1 consensus-passed P1).
**Fixes applied**: 5 (1 consensus-passed + 4 manual high-value).
**Post-fix verification**: Phase 2 tests 6/6 GREEN; ruff + mypy clean.

## Consensus Findings

| # | Severity | File:Line | Title | Status |
|---|----------|-----------|-------|--------|
| 1 | P1 | interview.py:772 | `except (TypeError, ValueError)` doesn't catch `pydantic.ValidationError` — silent data loss on malformed agent_models entry | **Applied** — added ValidationError to except tuple |

## Manual-Only Findings (high-value, applied)

| # | Severity | Reviewer | Title | Status |
|---|----------|----------|-------|--------|
| C-M1 | P1 | code | Migration log fires on every fresh Phase 2 render cycle (templates still emit `recommended_model:`) | **Applied** — gated log on `schema_version < 2` |
| C-M2 | P1 | code | Log missing yaml_path identifier | **Applied** — added `str(yaml_path)` to log message |
| C-M3 | P1 | code | No test for ValidationError path | **Applied** — `test_agent_models_malformed_entry_drops_with_warning` (exposes the bug under fix) |
| S-M1 | P1 | security | Log forging via newlines/ANSI escapes in user-controlled `raw_recommended_model` | **Applied** — sanitize `\n` and `\x1b` before log interpolation |
| Bonus | (test caught) | n/a | Original `.get()`-based parsing silently dropped unknown fields (didn't reach Pydantic extra=forbid) | **Applied** — pass `**spec_kwargs` so unknown fields surface as ValidationError |

## Manual-Only Findings (deferred to follow-up)

| # | Severity | Reviewer | Title | Resolution |
|---|----------|----------|-------|------------|
| S-M2 | P1 | security | `io_utils.load_harness_yaml` provenance filter relies on user-controlled `generated_by: harness-maker` equality — attacker could prepend that key to a body doc to skip it | **Out of Phase 2 scope** (io_utils.py owned elsewhere). Follow-up: tighten filter to require both `generated_by` AND positional first-doc, OR require an additional invariant key. |
| S-M3 | P2 | security | `AgentModelSpec.claude/cursor` accept arbitrary strings — Phase 3 render path will embed them in agent frontmatter without allowlist | **Phase 3 follow-up**: add `pattern=r'^[a-z][a-z0-9-]{0,80}$'` Field constraint before render wiring (validator C-2 was a similar concern). |
| S-M4 | P2 | security | `mechanical_checks` strings flow unvalidated into rendered shell command blocks | **Out of Phase 2 scope** (separate path, predates this PR). |
| C-M4 | P2 | code | Fixture body stripped vs real Production harness.yaml (missing project, second_brain, etc.) | **Accepted** — current fixture exercises the migration path correctly; reverse-mapper for additional keys covered by separate tests. |
| C-M5 | P2 | code | `test_uses_io_utils_load_harness_yaml_for_provenance` duplicates `test_v1_with_provenance_loads_as_v2_with_default_model` | **Accepted** — slight overlap but different assertion focus; cost of keeping is one passing test, value is regression guard if io_utils helper signature changes. |

## Final Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1         | B     | 5             | 5 manual-only (3 deferred to follow-up, 2 accepted) | 1 (caught by tests after fix) |

Final grade: **A** (post auto-fix: 0 consensus-passed P0/P1, threshold exceeded)
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

## Phase 2 → Phase 3 handoff notes

Phase 3 must:
1. Wire `resolve_agent_spec` into renderer (`synthesize._agent_files`) — covers S-M3 by validating field shape before render.
2. Migrate `Production.yaml.j2` + `Side.yaml.j2` from `recommended_model:` → `default_model:` (templates currently still emit the deprecated key, which is why the migration log gating matters).
3. After Phase 3 lands, the migration log condition `if schema_version < 2:` becomes redundant for harness-maker-rendered files (they'll be v2 with default_model:). It still fires for genuine v1 files from older harness-maker versions — that's the intended use case.

## Post-fix verification

- `uv run pytest tests/unit/test_interview_migration_v1_to_v2.py`: **6 passed**
- `uv run ruff check`: clean
- `uv run mypy --strict src/harness_maker/interview.py`: clean
- Full suite re-running in background
