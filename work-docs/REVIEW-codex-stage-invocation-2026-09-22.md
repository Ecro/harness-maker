---
type: review
task_slug: codex-stage-invocation
status: APPROVED
grade: A
human_review_needed: false
created: 2026-09-22
run_id: 5c79d2238f76
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: reviewer-lens
intent: null
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: codex-stage-invocation
  computed_at: 2026-09-22T01:31:31Z
---

# Review: Codex stage invocation

## Round 1 Summary

Grade B: two accepted consensus P1 findings and one accepted P2 coverage gap.
All seven mandatory lenses returned both passes. No intent link; skipped.
Reviewer payload files contain faithful extracted findings, not verbatim transcripts.

## Drift Findings

Changes fit the invocation rendering, generated guidance, documentation, tests and
snapshot scopes of the PLAN. No scope drift.

## Consensus Findings

- `bcfc945213a7d5a3` — P1, accepted, pending. verify.md.j2:198–199 leaves
  `/hm:spec` in reachable Check 6 recovery. The mixed unlabelled fence protects
  shell commands but also skips these sentences. Explicitly format the two prose lines.
- `366e664651bc633d` — P1, accepted, pending. verify.md.j2:128 and wrapup.md.j2:545
  recommend skills not emitted by synthesize. Common verify-before-completion guidance
  has the same defect. Use the existing health CLI and wrapup_docs configuration.
- `b04d303d1e12d798` — P2, accepted, pending. test_stage_invocation_syntax.py:112
  misses Production SPEC recovery: the 47 existing tests passed with the broken text.
  Add explicit recovery and preserved-waiver assertions in a follow-up test change.
  Not auto-fix eligible at grade B under hm-review's P0/P1 selection rule.

## Weak Consensus / Manual-Only Findings

None.

## Disagreements

Functionality reports the source defect at P1; tests reports the missing oracle at P2.
These remain independent findings; severities were not merged.

## 🧊 Cross-model findings (frozen @ round 1)

second_opinion_results: [{model: codex, status: invoked, reason: null}]
findings: []
Codex invoked once (99.82466805000013 seconds); no PIDA candidates.

## Consolidated repair model — round 2

Group: runtime-specific workflow guidance. Dimensions: runtime, prose versus executable
payload, owned versus user content, and available versus absent skills. Fix both P1s in
one consolidated edit: preserve Claude text and shell payloads; select callable Codex
recovery/configuration guidance. No new public skill or CLI interface.
Covering tests read: test_stage_invocation_syntax.py, test_render_verify_spec_need.py,
and test_verify.py:test_preset_dynamic. Baseline: 47 passed.

## Round 2 repair and verification

[Fix #1] P1 bcfc945213a7d5a3: explicitly formatted the two Check 6 recovery sentences.
[Fix #2] P1 366e664651bc633d: selected existing health CLI and wrapup_docs configuration
for Codex in verify, wrapup and common pre-completion templates.
No tests edited; no fixes reverted. Related pytest selection: 91 passed.
Direct Side/Production rendered recovery and availability assertions passed.
An initial broad grep also matched historical health references; narrowed the manual
probe to actionable recommendations, without changing production code to satisfy it.
Ruff check, format check (779 files), git diff --check passed.

Churn ratio 1.0 (new REVIEW artifact; template ratios 0.0057–0.0565).
CLI rereview: `churn 1.00 >= 0.30`; functionality reviewer re-dispatched.
Both P1 findings resolved, no new findings. P2 coverage enhancement remains pending.
Grade A; cumulative coverage has all seven lenses. Confirmation pending.

## Confirmation 1 and bounded repair

All seven lenses exercised on frozen tree 5ef55394f73872253f1c960e4e260aa9784bf85f.
New accepted consensus P1 `4d60159e962f1946` (consistency): shared skill activation
conditions require @intent-layer/@project-knowledge, contradicting corrected dollar help.
Not a proven loader failure; an explicit instruction mismatch. Existing P2 retained.
No other new findings. Enter the one permitted confirmation repair, separate from round budget.

[Fix #3] P1: change only the Codex activation mentions in intent-layer and project-knowledge.
Covering tests read: test_render_intent_layer.py and test_render_project_knowledge.py.
Grouped model remains runtime × owned prose × callable skill names; shell and Claude content unchanged.

The fixed review base also includes inherited commit 66b6564b (intent creation quality),
six files/218 insertions/22 deletions before this task. Confirmation reviewed the whole
span; these inherited changes are not task scope drift. The shared-skill activation
mismatch is relevant to this task's newly corrected help and is repaired here.

## Final confirmation and validation

confirm-2 frozen artifact: 3d17cdde8ddb57e0d4900b692f4c9b2b0c0342b4.
All seven mandatory lenses exercised; zero new severe findings. Cross-model result
re-read unchanged, never re-invoked. P1 4d60159e962f1946 resolved.
Final grade A, APPROVED, human_review_needed=false. P2 b04d303d1e12d798 remains accepted/pending.

Confirmation repair: 91 shared-skill/invocation/snapshot tests passed; direct rendered
activation checks passed. Earlier repair: 91 tests passed; structural surface/budget/
command/telemetry checks: 55 passed. These selections overlap, not a unique total.
Final ruff check/format and diff whitespace checks passed. No test file was edited during review.
Previously recorded four Claude live E2Es remain externally unverified due to quota;
this review does not claim full-suite GREEN or deployment readiness.

## Review Iteration Summary

| Iteration | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 (initial) | B | 0 | 2 P1 + 1 P2 | 3 |
| 2 | A | 2 P1 | 1 P2 | 0 |
| confirm-1 | B | 0 | 1 P1 + 1 P2 | 1 P1 |
| bounded confirmation repair | A | 1 P1 | 1 P2 | 0 |
| confirm-2 | A | 0 | 1 P2 | 0 |

Iterations used: 2 / 3, plus one separately budgeted confirmation repair.
Exit reason: converged. All four findings accepted; three P1 resolved, one P2 pending.
No rejected, duplicate, unresolved, weak-consensus or manual-only findings.
P2 was not eligible for automatic repair at grade A/B; follow-up regression assertion recommended.
Counters: unreviewed 0 · prior-fix 0 · unattributed 0. No new finding was caused by a fix.
No oscillation detected across repair endpoints 2,3. No reverted fixes or build breaks.
Repair churn: 0.028985507246376812; selective rereview skipped (`churn 0.03 < 0.30`),
then mandatory full confirmation covered both modified templates.
No branch commit, merge, or landing; HEAD remains 66b6564baac5450f0714ffc22ad83b1be107dfca.

## 📏 Size & Complexity

Measured from review_churn complexity endpoints, not estimates. Nesting is null because
these artifacts are not Python and the producer does not emit nesting measurements.

| File | LOC before → after | Cyclomatic | Max nesting | Status |
|---|---|---|---|---|
| verify-before-completion/SKILL.md.j2 | 123 → 124 | null | null | not-python |
| stages/verify.md.j2 | 393 → 393 | null | null | not-python |
| stages/wrapup.md.j2 | 876 → 877 | null | null | not-python |
| REVIEW artifact (round 2 measurement) | null → 66 | null | null | not-python |
| intent-layer/SKILL.md.j2 | 112 → 112 | null | null | not-python |
| project-knowledge/SKILL.md.j2 | 69 → 69 | null | null | not-python |
