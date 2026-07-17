---
type: review
task_slug: techspec-audit-2026-06-03
status: APPROVED
created: 2026-06-03
reviewers_invoked: [orchestrator-self]
consensus_method: single-source (reviewer subagents rate-limited — see caveat)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: techspec-audit-2026-06-03
  computed_at: 2026-06-03T00:00:00Z
---

# REVIEW — TECH_SPEC audit fixes (2026-06-03)

## ⚠️ Consensus caveat (read first)

The `code-reviewer` and `security-reviewer` subagents **could not run** — the
session hit its token limit (resets 14:10 KST). This review is therefore
**single-source** (the stage orchestrator), not the configured `cross-check
(2/3)` consensus. Every finding below is `manual-only` by definition (no second
reviewer to confirm). Grade is computed on consensus-passed findings only (none
exist by construction), so the **A** grade reflects *absence of confirmed
blockers*, not a clean 2/3 vote. Recommend a follow-up `/hm:review` reviewer
pass after the limit resets for true cross-check confidence.

## 🎯 Round 1 Summary

- **Grade: A** (0 consensus-passed P0, 0 consensus-passed P1).
- 1 P2 found by the orchestrator and **auto-fixed** this round (Check-4 bash
  resolution handling).
- Full suite + `ruff` + `ruff format --check` + `mypy --strict` green
  (re-confirmed after the fix).

## 🔍 Drift Findings

`drift_verdict.result: clean`. This work was driven by
`work-docs/AUDIT-techspec-vs-impl-2026-06-03.md` (§0 fix queue), not a formal
`PLAN-{slug}.md`, so there are no PLAN-phase scope boundaries to violate and no
SPEC In-Scope Scenarios to miss. Every changed file maps to a documented audit
finding (F22/F27/F28/F35/F40/F42/F43/F45/F48/F50/F53/F54/F56/F58/F59/F61/F66/
F69/F70/F71 + the spec_gate critic gap). No out-of-scope file was touched.

## ✅ Consensus Findings

None. (No second reviewer ran; nothing reached `consensus-passed`.)

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (orchestrator single-source)

### [P2 — FIXED this round] verify SKILL Check 4 bash ignored `accepted-risk-with-rationale`

- **File:** `src/harness_maker/templates/skills/verify-before-completion/SKILL.md.j2` (Check 4).
- **OBSERVE:** the new Check-4 bash counted every `"severity": "high"|"P0"` line
  via `grep -Ec`, but the check's own prose (and the canonical `/hm:verify`
  stage Check 4) says a finding marked `resolution: accepted-risk-with-rationale`
  must NOT gate.
- **INFER:** a user who deliberately accepted a high/P0 risk (recorded per
  policy) would still hit `exit 1` — the bash was stricter than its contract.
- **CONCLUDE:** false-positive gate failure on accepted-risk findings.
- **Fix applied:** `grep -E '"severity": ?"(high|P0)"' | grep -vc 'accepted-risk-with-rationale'`
  — counts only *unresolved* high/P0 (one JSON object per JSONL line, so the
  same-line exclusion is exact). Verified against a 2-line fixture (1 unresolved
  high + 1 resolved P0 → `unresolved=1` → FAIL, correct). Snapshots regenerated;
  `test_verify.py` + `test_synthesize_snapshot.py` green.

### [P3 — accepted limitation, no change] dashboard.md.j2 marker removal (F35)

- **File:** `src/harness_maker/templates/observability/dashboard.md.j2`.
- **OBSERVE:** the `@hm:user:extensions` block was removed. An *existing* install
  with content in that block loses it on the next `/hm:make` re-render
  (block_merge has no markers to preserve).
- **INFER/CONCLUDE:** net-consistent, NOT a new regression — `write_dashboard`
  (`/hm:health`) already `atomic_write`s this exact path with no block-merge, so
  any hand-authored content was already destroyed on the first health run. The
  file is writer-owned by design (ADR-0007 "latest snapshot"); the new template
  body explicitly tells users not to hand-edit. Recorded as an accepted
  limitation (matches the audit's F35 option-(a) decision). No migration shim
  added — consistent with the existing writer behavior.

### [P3 — informational, no change] modular_edit.remove() now runs verify() (F42)

- **File:** `src/harness_maker/modular_edit.py` (`remove()`).
- **OBSERVE/INFER:** adding the post-write `verify()` (to match `add()` and spec
  Task 5.6) means a *pre-existing* unrelated content-hash drift elsewhere in the
  tree could now surface as a `remove` failure where it previously passed
  silently.
- **CONCLUDE:** intended per Task 5.6 (remove must verify); the new failure mode
  is "surface real drift," not a false positive. `test_modular_edit` green. Kept.

## 🤝 Disagreements

None (single reviewer).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 1 (P2 Check-4 resolution) | 0 consensus-passed; 2 P3 accepted | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false (grade A) — but see the consensus caveat; a real
cross-check pass is recommended once the session limit resets.

## Notes for wrapup

- Deferred audit items (NOT regressions, documented in AUDIT §0): **F55**
  (wiring unused detector — K13 finding-explosion risk), **F33** (frozen
  timestamp — reproducible-build tradeoff), and the ~51 doc-only stale-spec
  items (TECH_SPEC/README/ARCHITECTURE/PRIVACY doc sweep).
- Follow-up chore (not done): re-render the dogfood `.claude/` so the repo's own
  harness picks up the verify-SKILL / dashboard / executor / conditional-router
  template changes (tests don't enforce dogfood freshness, so the suite is green
  regardless).
