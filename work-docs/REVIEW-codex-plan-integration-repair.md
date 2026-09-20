---
type: review
task_slug: codex-plan-integration-repair
status: APPROVED
created: 2026-09-21
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, code-verifier, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: codex-plan-integration-repair
  computed_at: 2026-09-20T15:07:51.652939+00:00
---

## Round 1 Summary
All seven lenses returned no findings for the task delta. CLI grade A, no human review needed. A.5 passed; focused tests passed (75). Initial full CI: 9011 passed, 100 skipped, 3 xfailed. Ruff, format, strict mypy passed. Live native install/update and authenticated hostile-Claude smoke passed. Actual e1a84311-to-current project update passed all nine preservation and consumer checks.

## Drift Findings
No task drift. The stored review base e1a84311 predates the already-landed plan absorption; confirmation therefore reviews that whole integration as well. The PLAN scope now includes the confirmed absorption repairs below.

## Consensus Findings
Confirmation 1 returned two P1 findings and one P2. All seven lenses exercised, CLI grade B. One separately budgeted confirmation repair follows.

| ID | Lens | Severity | Finding | State |
|---|---|---|---|---|
| repair-confirm-consistency | consistency | P1 | execute Inputs requires the PLAN before Step 0 creates it | resolved |
| repair-confirm-concurrency | concurrency | P1 | simultaneous non-isolated upserts can replace the first SPEC decision | resolved |
| repair-confirm-tests | tests | P2 | whole-stage keyword assertions miss removal of the post-write guard | resolved |

## Weak Consensus
None.

## Manual-Only Findings
None.

## Disagreements
Codex raised duplicate built-in allowlist normalization as P2. Mode-B verifier rejected it against the explicit collision policy and identical rendered consumer bytes. No invented, omitted or duplicate disposition IDs (one input, one rejection).

## 🧊 Cross-model findings (frozen @ round 1)
```json
{
  "frozen_at_round": 1,
  "models": [
    "codex"
  ],
  "findings": [
    {
      "id": "e1e39e6db1517edb",
      "severity": "P2",
      "file": "src/harness_maker/models.py",
      "line": 569,
      "summary": "The migration deduplicates every existing `spec-validator` entry whenever `plan-validator` is present, rather than collapsing only the collision introduced by replacing the retired name. For example, `[\"spec-validator\", \"spec-validator\", \"plan-validator\"]` becomes `[\"spec-validator\"]`, altering pre-existing entries and their multiplicity. Track whether the replacement itself collides, while leaving original `spec-validator` entries unchanged.",
      "evidence": "The condition checks only the replacement value and membership in `migrated`; it cannot distinguish an original `spec-validator` from one produced by migrating `plan-validator`. The new tests cover duplicate custom agents but not duplicate existing `spec-validator` entries.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "rejected",
      "oracle_result": "PLAN permits replacement collisions; effective allowlist and rendered consumer bytes are unchanged.",
      "status": "resolved"
    }
  ]
}
```

## Review Iteration Summary
Round 1: A, zero active findings. Confirmation 1: B, two new P1 and one P2, full lens coverage. No round-limit reset; review run 692c4c590fe5 remained open until confirmation 2 below.

## Size & Complexity
No auto-fix round was run before confirmation 1; no complexity measurement is claimed.

## Confirmation 2 and verification follow-up
All seven lenses completed the second frozen pass over e1a84311..7293524a. Both P1 findings and the guard P2 were resolved. CLI grade A, human_review_needed=false, with two nonblocking P2 test-oracle findings (repair-confirm-conditional and repair-confirm-round-count) in the already-landed absorption tests. No third confirmation pass ran; the review closed APPROVED.

Verification then found the longer Inputs sentence exceeded the existing shipped-surface ratchet by 32 characters. The same contract was shortened to `reuse; Step 0 creates it if absent`, without baseline relaxation; the original core reviewer confirmed no regression. Both remaining test oracles were strengthened in their owning blocks. An independent tests verifier re-ran the two reported in-memory mutants and confirmed they now fail, with intended output passing. These bounded post-review edits were checked directly; the second freeze does not claim to contain them. Targeted final checks: 18 passed, including both size guards. Final full CI passed: 9014 passed, 100 skipped, 3 xfailed, 4 warnings in 415.26s. Ruff, format (766 files), and strict mypy (762 source files) passed. All six verify checks passed (`.claude/observability/codex-plan-integration-repair/verify.json`). The final run includes the execute-only snapshot and autopilot golden hash refreshes, with no size-budget baseline relaxation. Wrapup independently confirmed the fresh relevant verification marker `dcaa02ee8e40fa0eab97b79cd4cf03d1da315acbb344fecc58313a6018b6fcb3`.

Final grade: A. Iterations used: 1 regular round plus one separately budgeted confirmation repair; two confirmation passes. Exit reason: converged. All five consensus findings resolved. Cross-model finding remains rejected, without a new vote. Unreviewed fixes: 0; prior-fix regressions: 0; unattributed regressions: 0.

### Measured confirmation repair size
| File | LOC | Cyclomatic | Max nesting | Status |
|---|---|---|---|---|
| src/harness_maker/spec_need.py | 736 → 739 | 86 → 86 | 3 → 3 | measured |
| src/harness_maker/templates/stages/execute.md.j2 | 987 → 987 | null → null | null → null | not-python |
| tests/unit/test_render_execute_spec_need.py | 137 → 148 | 18 → 21 | 1 → 1 | measured |
| tests/unit/test_spec_need_frontmatter_upsert.py | 221 → 292 | 36 → 54 | 3 → 3 | measured |
| work-docs/PLAN-codex-plan-integration-repair.md | 58 → 61 | null → null | null → null | not-python |
| work-docs/REVIEW-codex-plan-integration-repair.md | null → 69 | null → null | null → null | not-python |
