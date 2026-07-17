---
type: review
task_slug: human-bottleneck-auto-advance
status: APPROVED
created: 2026-06-20
reviewers_invoked: [code-reviewer (×2), codex]
consensus_method: k-of-3 (2 Claude + Codex)
codex_status: invoked
phase: 2
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-20T00:00:00Z
final_grade: A
status_final: APPROVED
human_review_needed: false
---

# REVIEW — human-bottleneck-auto-advance Phase 2 (autopilot marker + CLI)

## 🎯 Round 1 Summary

- **Scope:** Phase 2 staged diff — `autopilot.py` (marker module), `cli.py` (`autopilot` command), `worktree.py` (churn-file +1), `tests/unit/test_autopilot.py`.
- **Voters:** 2× code-reviewer (cross-check) + Codex gpt-5.5 (k-of-3, Production-mandatory). `codex_status: invoked`.
- **Grade: A** (consensus-passed P0=0, P1=0). Threshold A met → **APPROVED**.
- A large quality pass was applied despite grade A: the findings cluster on this project's #1 failure mode (absent-case = feature black hole), so closing them now is cheaper than a later regression. All review fixes are additive (schema guard + validation + tests) — no behavior the prior tests covered changed.

## 🔍 Drift Findings

**clean.** All four changed files are within PLAN Phase 2 scope (autopilot module + CLI + churn-file + tests). No scope drift, no scenario miss.

## ✅ Consensus Findings

| Sev | Tag | Finding | Sources | Disposition |
|-----|-----|---------|---------|-------------|
| P2 | consensus-passed | `test_active_marker_foreign_uuid` (+ the effective_level foreign test) relied on a random uuid ≠ `"ffffffffffff"` — probabilistic, violates checkpoint-7 determinism | code-reviewer A (P2) + B (P1) | **APPLIED** — both tests now `monkeypatch` `autopilot._current_session_uuid` to a fixed value; mismatch is deterministic |

(Severity resolved to P2: the real-world failure probability is ~10⁻¹⁴ — a determinism-hygiene issue, not a correctness defect. Grade-neutral.)

## ⚠️ Weak Consensus

| Finding | Sources | Resolution |
|---------|---------|-----------|
| `effective_level` returned `yaml_level` unguarded on absent/invalid/foreign marker | Codex (P1: "should clamp to gated") + code-reviewer B (P1: "validate the garbage value") — OBSERVE aligned, CONCLUDE diverged | **APPLIED a unifying fix**: `effective_level` now clamps an unknown/typo/empty `yaml_level` to `"gated"` (+ warn), while a *valid* committed level is still honored (correct ADR-006 precedence: active-marker > yaml). This satisfies B (no garbage propagation) and Codex (invalid → gated) without contradicting reviewer A (who verified the marker→yaml fallback chain as sound). |
| CLI `level` handling — `# type: ignore[arg-type]` on `write()` + a failed `on` leaving a prior valid marker | code-reviewer A (P2: validate level, drop the suppression) + Codex (P2: failed-on fail-open) — same locus (cli.py level path) | **APPLIED**: `level` is validated upfront against `{gated,auto_safe,full}` with a clear error → `Exit(2)` BEFORE any marker write; the suppression is replaced by an explicit `cast` after the runtime narrowing. A failed `on` is now transactional (validated before write) — prior marker stays intact, proven by `test_cli_failed_on_preserves_prior_marker`. |

## 📝 Manual-Only Findings (single-source) — all APPLIED

| Sev | Finding | Source | Fix |
|-----|---------|--------|-----|
| P1 | Empty pipeline (`[]`) is schema-valid → silent Phase-3 no-op | reviewer A | `AutopilotMarker.pipeline = Field(min_length=1)` + `test_load_empty_pipeline_rejected` |
| P1 | extra-key rejection (`extra="forbid"`) untested | reviewer A | `test_load_extra_key_rejected` |
| P1 | empty-file fail-safe (partial-write survivor, WSL2/NTFS) untested | reviewer B | `test_load_empty_file_returns_none` |
| P1 | dirt-filter coverage tested only at tuple-membership, not call-site | reviewer B | `test_dirt_filters_recognize_marker` invokes `_is_harness_artifact` + `_is_create_guard_harness_artifact` on a porcelain line |
| P2 | `--pipeline` CLI path (valid + invalid) untested | reviewer B | `test_cli_custom_pipeline_valid` + `test_cli_invalid_pipeline_exits_2` |
| P2 | `created_at`: `now or ...` swallows an explicit `""` | reviewer A | changed to `now if now is not None else ...` |
| P3 | malformed-marker shape tests | Codex | covered by the empty-pipeline + extra-key tests above |
| P2 | 3-tier→2-mechanism collapse undocumented; project-scoped uuid caveat | reviewer B | docstring NOTEs added to `effective_level` + `active_marker` |

## 🤝 Disagreements

The `effective_level` finding is the one genuine cross-voter divergence (Codex "force gated" vs reviewer B "validate" vs reviewer A "already correct"). Resolved by the clamp-invalid-to-gated fix, which is consistent with all three: valid yaml honored (A), garbage rejected (B), invalid→gated (Codex).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 4 source hardening (effective_level clamp, pipeline min_length, CLI level validation, created_at) + 8 test additions + 2 doc notes (all voluntary; grade already met) | 0 consensus-passed P0/P1 | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

Post-fix verification: `tests/unit/test_autopilot.py` 22 passed (14 → 22); full `pytest` exit 0; `ruff check` + `ruff format --check` clean; `mypy --strict` clean (the `cast` removed the `# type: ignore`).
