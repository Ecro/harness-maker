---
type: review
task_slug: spec-test-accumulation
status: APPROVED
created: 2026-05-30
reviewers_invoked: [code-reviewer, performance-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: spec-test-accumulation
  computed_at: 2026-05-30T00:00:00Z
---

# REVIEW: spec-test-accumulation

## 🎯 Round 1 Summary

- **Reviewers:** code-reviewer · performance-reviewer · security-reviewer (conditional routing — Python logic + templates + new subprocess CLIs; no auth/secrets/UI surface → security-auditor & ux-reviewer not routed).
- **Consensus note:** one reviewer per domain (disjoint scopes), so no finding reaches multi-reviewer surface+reasoning consensus — all are formally `manual-only`. **Formal grade = A** (0 consensus-passed P0/P1).
- **Action taken:** rather than ship known-valid `manual-only` findings, the stage orchestrator applied fixes for the 3 genuinely-valid ones (1 security P1, 2 correctness P2) + 1 doc note, and added a contract-lock test for the 1 non-bug. Performance review: clean.
- **Final grade: A · Status: APPROVED.**

## 🔍 Drift Findings

`drift_verdict: clean`. All changed source maps to a PLAN phase. Two scope notes (already surfaced in the execute summary, not violations): the CLI landed in `spec_machine.__main__` / `spec_mutation.__main__` rather than `cli.py` (templates call `python -m`, so this is correct); `spec_mutation.py` + the `_check_pytest_collect` `-q` fix were added to make Phase 2's template instruction real (latent-bug class). dev_mode=task-driven → drift is advisory regardless.

## ✅ Consensus Findings

None — single reviewer per domain, no cross-reviewer surface match. (See note above.)

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (single-source; valid ones fixed)

| # | Sev | Reviewer | File:line | Finding | Resolution |
|---|-----|----------|-----------|---------|------------|
| S-P1 | P1 | security | `spec_machine.py:_check_pytest_collect` | `test_id` file tokens spliced into pytest argv with no `--` fence → option injection (`-pevil::x` → `pytest -p evil`) from an authored `machine.yaml`. Same trust boundary the project already guards for `paths_to_mutate`; asymmetric gap. | **FIXED** — drop tokens whose file starts with `-` + add `--` positional fence before file args. Test `test_check_pytest_collect_drops_option_like_test_id`. |
| C-P2a | P2 | code | `spec_drift.py:scan` | When pytest is absent, `unresolved_test_ids` degrades to `[]` (all-resolved) → every pending-with-ids AC false-flags as resolved-but-pending. | **FIXED** — guard the resolved-but-pending pass behind `shutil.which("pytest")`. Test `test_scan_resolved_but_pending_skipped_when_pytest_absent`. |
| C-P2c | P2 | code | `spec_machine.py:mark_tested` | Persisted `pending_test=false` BEFORE validating → a failing validate leaves a half-bound AC on disk. | **FIXED** — validate-before-persist: pre-check resolution; on failure the file is left untouched. Test `test_mark_tested_unresolved_does_not_mutate_file`. |
| C-P2d | P2 | code | `spec_machine.py:mark_tested` CLI | `--ac AC-X` alone flips an AC to non-pending with zero test_ids → a state `validate()` later rejects. | **FIXED** — refuse to bind an AC whose merged test_ids are empty. Test `test_mark_tested_refuses_zero_test_ids`. |
| C-P2b | P2 | code | `spec_machine.py:_dump_machine_yaml` | `model_dump` round-trip materializes default fields + drops inline comments → diff-noise on first write-back. | **DOC** — no data loss (all fields preserved); documented as the accepted cost of ADR-005's post-finalize design in the docstring. |
| C-P1 | P1 | code | `spec_machine.py:_check_pytest_collect` | Worried class-nested nodeids (`f.py::TestC::test`) might false-fail. | **NOT A BUG** — declared test_id must equal the exact pytest nodeid (that is rule-3's contract). Added contract-lock test `test_mark_tested_resolves_class_nested_nodeid` proving an exact class nodeid resolves. |

## 🤝 Disagreements

None — reviewers had disjoint scopes; no severity conflicts.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 4 (+1 doc, +1 lock-test) | 0 | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

Verification after fixes: affected unit suites green (89 tests), `mypy --strict` clean, `ruff` clean. Fixes touched only `spec_machine.py` + `spec_drift.py` (no template/snapshot impact). Full-suite re-run confirmed separately.
