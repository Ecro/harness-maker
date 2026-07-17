---
type: review
task_slug: model-routing-multi-ide
phase: 1
status: APPROVED
created: 2026-05-18
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
final_grade: A
iterations: 1
auto_fix_applied: 1
manual_only_findings: 7
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: model-routing-multi-ide
  computed_at: 2026-05-18
---

# REVIEW — Phase 1 (Schema + presets module + canonical ID table)

## 🎯 Round 1 Summary

**Grade: A** (P0=0, P1=0 consensus-passed; threshold met).
**Fixes applied: 4** (1 consensus-passed + 3 manual-only high-value).
**Manual-only remaining: 4** (1 P0 explicitly Phase 3 scope; 1 P1 architectural follow-up; 2 P2 minor).

## 🔍 Drift Findings

Clean. All Phase 1 changes are within the PLAN-stated scope:
- `src/harness_maker/models.py` (in scope: schema)
- `src/harness_maker/presets.py` (in scope: new module)
- `tests/unit/test_models_agent_models.py`, `test_presets.py`, `test_no_raw_cursor_model_ids_in_templates.py` (in scope: new tests)
- `tests/unit/test_schema_migration.py` (in scope: schema_version bump cascade — 1-line fix)
- `work-docs/PLAN-model-routing-multi-ide.md` (in scope: deviation log)

No edits outside Phase 1 scope.

## ✅ Consensus Findings (consensus-passed)

| # | Severity | File:Line | Title | Status |
|---|----------|-----------|-------|--------|
| 1 | P2 | presets.py:124 | `_spec_from_default_model` substring ordering is load-bearing but undocumented (both reviewers, same line, aligned reasoning) | **Applied** — added explicit ordering rationale comment |

## 📝 Manual-Only Findings (single-reviewer, surfaced but not auto-applied)

### From code-reviewer

| # | Severity | File:Line | Title | Status |
|---|----------|-----------|-------|--------|
| C1 | P1 | models.py:596 | InterviewAnswers lacks dual-key guard — will explode in Phase 2's `load_harness_yaml` path | **Applied** (high-value, blocks Phase 2) |
| C2 | P2 | presets.py:55 | `_spec()` `# type: ignore[arg-type]` silences mypy on 28 preset entries | **Applied** — introduced `_Effort` Literal type alias, removed type: ignore |
| C3 | P2 | test_models_agent_models.py:106 | Missing IA dual-key precedence test | **Applied** — added `test_interview_answers_default_model_wins_when_both_provided` |
| C4 | P2 | Production.yaml.j2:4 | schema_version=2 file still emits deprecated `recommended_model:` key | **Manual — Phase 3 scope** (template migration); noted for executor handoff |

### From security-reviewer

| # | Severity | File:Line | Title | Status |
|---|----------|-----------|-------|--------|
| S1 | P0 | synthesize.py:195 | `resolve_agent_spec` never called — entire routing machine is dead code today | **Manual — Phase 3 scope** (renderer wiring is Phase 3's explicit purpose). Surface to executor. |
| S2 | P1 | models.py:487 | `default_model`/`AgentModelSpec.claude`/`cursor` are free-text with no pattern validation — potential YAML injection vector once Phase 3 wires the render path | **Manual — architectural follow-up** (PLAN didn't call for it). Recommendation: revisit before Phase 3 closes; add `pattern=r'^[a-z][a-z0-9-]{0,80}$'` Field constraint. |
| S3 | P2 | presets.py:124 | Same as consensus #1 (different angle: regex `\b` boundary) | Subsumed by consensus #1 fix (ordering comment) |
| S4 | P2 | test_no_raw_cursor_model_ids_in_templates.py:19 | Lint only scans `.j2`, not Python `.py` files for raw concrete IDs | **Manual — follow-up** (Phase 1 scope is templates per ADR-003; Python-side scan worth adding in Phase 3 when synthesize.py touches concrete IDs) |

## 🤝 Disagreements

None. No reviewer-reasoning conflicts on shared findings.

## Final Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1         | A     | 4 (1 consensus + 3 manual-high-value) | 4 manual-only | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

## Phase 1 → Phase 2 handoff notes

For the next /hm:execute invocation:
- **Phase 2 will reach** the IA dual-key path (`load_harness_yaml` → `InterviewAnswers.model_validate`). The guard is now in place.
- **Phase 3 owes** (a) wiring `resolve_agent_spec` into `synthesize._agent_files` + Jinja2 context (S1); (b) migrating `Production.yaml.j2` + `Side.yaml.j2` to emit `default_model:` not `recommended_model:` (C4); (c) revisiting field-value regex validation before render wires up to user files (S2).

## Post-review verification

- `uv run pytest` on the 4 affected test files: **43 passed, 0 failed**
- `uv run ruff check`: clean
- `uv run mypy --strict src/harness_maker/models.py src/harness_maker/presets.py`: clean
- Full suite (pre-fix): 2037 passed / 0 failed / 20 skipped
