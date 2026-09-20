---
type: review
task_slug: codex-claude-integration
status: APPROVED
grade: A
run_id: f37d5a60ef48
drift_verdict:
  task_slug: codex-claude-integration
  result: clean
  scope_violations: []
  scenario_misses: []
  computed_at: 2026-09-20T09:49:09.578398+00:00
---
# Review: Codex lifecycle and Claude integration

## Summary
Round 1: grade C (4 P1, 2 P2). Round 2: grade A after consolidated lifecycle/configuration repairs and acceptance-oracle completion. Confirmation 1 found one residual test subprocess-contract issue; the bounded confirmation repair passed focused checks and confirmation 2. Final full regression passed (9,142 passed, 101 skipped, 3 xfailed).

## Findings and resolutions
| ID | Severity | Finding | Lifecycle |
|---|---|---|---|
| b7e904a3210b8a4d | P1 | Regeneration deletes saved Claude options when the provider is disabled | resolved: targeted verification + independent re-review |
| f9963085c1292015 | P1 | Nonzero engine exits discard valid independent version observations | resolved: targeted verification + independent re-review |
| 9a234a01e5553991 | P1 | New subprocess calls omit the required check=True argument | resolved: targeted verification + independent re-review |
| 6ec6abf10c285bb1 | P1 | Setup timeout leaves descendant generators running | resolved: targeted verification + independent re-review |
| 6a97e936c0f7acc3 | P2 | Configured Claude model/deadline forwarding has no integration oracle | resolved: targeted verification + independent re-review |
| b5e9190cca0b3374 | P2 | Authenticated smoke lacks declared adversarial ambient-isolation oracle | resolved: targeted verification + independent re-review |

## Repair evidence
Process ownership spans uv, engine and generator. Checked failures retain engine observations; failed commands cannot report complete. Both presets retain disabled-provider options. Tests cover nonzero receipts and CalledProcessError, malformed manifests, descendant cleanup, configured model/deadline forwarding, and authenticated hostile hook/instruction/tool-write sentinels.

## Cross-model findings (frozen @ round 1)
Configured Codex voter: invoked once, zero findings, 51.46s. No PIDA subjects. Claude probes are acceptance tests, not additional review votes.

## Iterations
Round 1 exercised all seven lenses through four groups in two passes. Four-thread capacity queued the fourth group; every group returned before consolidation.
Round 2 repair churn: 0.4483; required core re-review found no new findings. Required AC-004/007 oracle gaps were completed as acceptance work.
Confirmation 1 frozen span: e5dfb2f3..7196981e. Core, concurrency and tests clean. Security identified missing check/timeout arguments in test subprocesses; no new product security defect.

## Verification
Focused implementation suite: 77 passed. Regression repair suite: 33 passed. Native authenticated hostile smoke: passed. Lint, format and strict type checks passed before confirmation.
First full suite: 6 failed, 9123 passed, 101 skipped, 3 xfailed. All six diagnosed: process-fixture startup timing, superseded README guard, detector set, and selector registration. The final rerun passed; see the final CI verification record below.

## Scope and boundaries
README guidance, its exact install-command guards, detector expectations and selector registration belong to the reachable installation/provider integration. No other worktree or active plugin installation was changed. Peer plan-stage-absorption is not landed; additive provider changes avoid its stage deletion and agent-default ownership. Historical plan ledger values remain supported.

## Counters
unreviewed_fix_count: 0
regression_attributed_n: 0
attribution_unknown_n: 0

Confirmation repair evidence: all new test subprocess calls are checked and bounded (AST audit); readiness PID publication is atomic. Focused suite: 41 passed. The second full run stopped on that fixture race after 3,249 passes; final full regression subsequently passed.

## Final confirmation and iteration summary
Confirmation 2 reviewed frozen whole span e5dfb2f3..166dbe75: all four groups returned no findings. Coverage CLI exercised design, functionality, robustness, consistency, security, concurrency and tests; no missing lenses. Confirmation repair resolved the test subprocess contract. Cross-model voters were not re-invoked. No oscillation detected.

| Iteration | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 | C | — | 6 | 6 |
| 2 | A | 6 | 0 | 0 |
| Confirmation 1 | — | — | 1 | 1 |
| Confirmation 2 | A | 1 | 0 | 0 |

Final grade: A. Iterations used: 2 / 3. Exit reason: converged.
Status: APPROVED. human_review_needed: false.
Counters: unreviewed 0 · prior-fix 0 · unattributed 0.
Latest native lifecycle/authenticated hostile smoke: PASS after confirmation repair. The verify stage subsequently confirmed full CI completion.

## Size and complexity (round 2 producer output)
| File | LOC | Cyclomatic | Max nesting | Status |
|---|---|---|---|---|
| scripts/codex_engine.py | 80 → 88 | 17 → 16 | 3 → 3 | measured |
| src/harness_maker/codex_setup.py | 112 → 174 | 20 → 36 | 3 → 3 | measured |
| Production.yaml.j2 | 155 → 155 | null | null | not-python |
| Side.yaml.j2 | 156 → 156 | null | null | not-python |
| test_codex_claude_live.py | 164 → 214 | 15 → 19 | 2 → 2 | measured |
| test_claude_provider_integration.py | 169 → 276 | 34 → 44 | 1 → 1 | measured |
| test_codex_setup.py | 264 → 323 | 64 → 78 | 2 → 3 | measured |

Final CI verification: 9,142 passed, 101 skipped, 3 xfailed (769.93s); lint, format and strict mypy all passed. Authenticated native integration passed separately with HM_CODEX_CLAUDE_LIVE=1.

Post-review wrapup: managed reference docs updated; 54 documentation contract checks passed. Main advanced to 697036be and the branch rebased cleanly; 196 combined integration/peer regression tests passed. A two-reference strict typing issue in the newly landed peer control fixture is repaired with direct owner imports and independently reviewed before landing.
