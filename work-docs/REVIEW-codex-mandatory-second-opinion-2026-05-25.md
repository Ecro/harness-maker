---
type: review
task_slug: codex-mandatory-second-opinion
status: in-progress
created: 2026-05-25
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: codex-mandatory-second-opinion
  computed_at: 2026-05-25T02:30:00Z
---

# REVIEW — codex-mandatory-second-opinion

## 🎯 Round 1 Summary

- **Reviewers:** code-reviewer (opus), security-reviewer (opus). 2-pass redaction was a no-op (local uncommitted diff carries no PR title/author/commit-message anchoring to redact).
- **Round 1 grade:** **A** by the consensus-passed count (0 consensus-passed P0/P1). But code-reviewer surfaced a real single-source P1 root cause (contract stated in 3 places, only 1 updated) that the orchestrator judged correct and **fixed in round 2** rather than letting the consensus math ship it.
- **Round 2 grade (after fix):** **A** — root cause resolved and render-verified.
- **Status:** APPROVED. `human_review_needed: false`.

## 🔍 Drift Findings

`drift_verdict: clean`. All 6 substantive changed files map to PLAN phases:
`second_opinion_codex.md.j2` (Phase 1), `plan.md.j2` + `models.py` + `interview.py`
(Phase 2), `test_render_codex_partial_include.py` (Phase 3), `CHANGELOG.md` (Phase 4).
`uv.lock` is the 0.26.1 version-sync artifact (rode in via `--allow-dirty-base`),
not feature scope. No scenario misses (no SPEC). No P1 drift.

## ✅ Consensus Findings (consensus-passed)

None. With 2 reviewers and `cross-check`, the contract findings below were
single-source (code-reviewer's domain — security-reviewer correctly found
nothing in its domain, which is concurrence on security, not disagreement on
the contract). Per strict consensus they tag `manual-only`; the orchestrator
nonetheless confirmed them correct and fixed them (see Manual-Only + Iteration 2).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (single-source, orchestrator-adjudicated)

| # | Sev | File:line | Finding | Adjudication |
|---|-----|-----------|---------|--------------|
| 1 | P1 | plan-validator_body.md.j2:54 | Canonical "Return ONLY this JSON" schema block omits the new top-level `codex_status`/`codex_reconciliation` keys; a literal LLM drops them → relay no-ops | **VALID → FIXED** (round 2) |
| 2 | P1 | plan.md.j2:357 | Step 4 dispatch prompt `Return JSON: {overall, critiques}` also omits the new keys (same root cause) | **VALID → FIXED** (round 2) |
| 3 | P2 | plan.md.j2:367 | Disabled relay allegedly leaves a double blank line before `### Step 5` (snapshot drift) | **DROPPED — false positive.** Empirically disproved: normalized disabled-render diff vs main was byte-IDENTICAL. With `trim_blocks=False`, each tag line's trailing newline reconstructs the original blank line exactly. Direct evidence over abstract reasoning. |

**Security:** code-reviewer + security-reviewer both confirmed the `codex exec`
Bash recipe is unchanged (shared across the `name` branch) and its defenses are
intact: `prompt_tmp` + no-inline-heredoc / no-eval, `--sandbox read-only`,
`--ask-for-approval never`, hermetic `--ignore-user-config --ignore-rules`,
double-quoted `--output-schema "<path>"` where `output_schema_path` is
hard-validated (`models.py:470-492`). The new relay is pure prose gated on
`config.codex_second_opinion.enabled`; `codex_skip_reason` originates from the
validator's own output (numeric exit status), not adversarial reviewed content —
no stored-prompt-injection / stdout→LLM sink. security-reviewer: `[]`.

## 🤝 Disagreements

None on severity. The only divergence was domain coverage (security clean vs
code-reviewer's contract P1), resolved by orchestrator adjudication.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A*    | —             | 2×P1 (manual-only) + 1×P2 | — |
| 2         | A     | 2 (both P1 root cause) | 0 | 0 |

\* Round-1 consensus-passed count was already A, but the manual-only P1s were
real reliability defects (would silently no-op the loud-skip + reconciliation
contract this PLAN exists to guarantee). They were fixed rather than waved
through — letting a verified-correct P1 ship would violate the quality bar.

### Iteration 2 (Grade: A → A) — fixes applied

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Partial now explicitly EXTENDS the "Return ONLY this JSON" schema (the canonical anchor) — when enabled, plan-validator MUST carry the two top-level keys alongside the 3 existing ones | `second_opinion_codex.md.j2` | Applied |
| 2 | P1 | Step 4 dispatch prompt gate-extends the requested JSON with `codex_status`/`codex_reconciliation` when `codex_second_opinion.enabled` | `plan.md.j2` | Applied |

**Verification of fixes (render-level):**
- ENABLED: plan-validator body carries the EXTENDS wording + `codex_status` + `codex_reconciliation`; Step 4 prompt lists `codex_status: invoked|skipped, codex_reconciliation: [...]`.
- DISABLED: Step 4 prompt and whole plan command carry **no** `codex_status` token (gate-extend is inline `{% if %}` → byte-clean).
- `ruff check` clean, `mypy --strict` clean (102 files), codex unit tests green.

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false
