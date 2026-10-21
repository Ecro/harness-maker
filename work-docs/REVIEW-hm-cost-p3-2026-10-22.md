---
type: review
task_slug: hm-cost-p3
created: 2026-10-22
spec: "[[SPEC-hm-cost-p3]]"
plan: "[[PLAN-hm-cost-p3]]"
rounds: 2
reviewers: [code-reviewer, codex]
summary: Two rounds. Round 1 raised 9 code-reviewer and 2 Codex findings; 9 accepted and fixed, 1 rejected with authority, 1 duplicate. Round 2 found none. AC-005's pre-registered 10.0 bar was missed at 11.36, which stopped the task before wrapup until the DRI chose to land it with the miss recorded.
---

# REVIEW — hm-cost-p3

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1 | P1 | src/harness_maker/templates/stages/spec.md.j2:88 | The defaults rule could settle a WHY, WHAT, scope or trade-off critique and, under auto_full, stamp with no DRI turn. Fix: such critiques go to Open Questions; critical ones are surfaced before any stamp | accepted | SPEC AC-001 |
| R2 | P1 | src/harness_maker/templates/stages/execute.md.j2:82 | The post-REVIEW check named only exit 1 on an unresolved row; a real gate failure or exits 3–5 were unspecified. Fix: act on its exit as at Bind, with the unresolved-row exception | accepted | SPEC AC-003 |
| C1 | P1 | src/harness_maker/check.py:1278 | A pass recorded earlier survived a later fresh failure on the same tree (a gate reading state outside the tree), so `--reuse` reprinted the pass. Fix: a non-zero fresh run unlinks the record; `test_a_fresh_failure_drops_an_earlier_pass`, mutation-checked | accepted | SPEC S4 |
| R3 | P2 | src/harness_maker/check.py:1182 | The key omitted the harness config (it may be git-ignored) and HEAD could move during the run. Fix: config hashed into the fingerprint; no record when HEAD moved; `test_an_ignored_config_change_runs_fresh`, mutation-checked | accepted | SPEC S3 |
| R4a | P2 | src/harness_maker/check.py:173 | An unreadable file has a constant digest, so a change inside it is invisible. Fix: no record when any digest is `unreadable:*`; `test_an_unreadable_file_is_never_recorded` | accepted | SPEC S3 |
| R4b | P2 | src/harness_maker/check.py:173 | Symlink targets are hashed as `link:<target>`, not content | rejected | SPEC constraint: the fingerprint is `check.snapshot`, the same notion of tree as `tree_changed` |
| R5 | P2 | src/harness_maker/check.py:1241 | A reused pass repeats an hours-old CVE lookup. Fix: stated in the `--reuse` help; no TTL | accepted | SPEC constraint: reuse is opt-in for wrapup right after execute |
| R6 | P2 | src/harness_maker/templates/stages/execute.md.j2:13 | `&&` silently skips later steps after a failure. Fix: "a chain stops at its first failure, so report it" | accepted | SPEC AC-004 |
| R7 | P2 | tests/unit/test_hm_cost_p3_reuse.py:98 | `chmod 0o500` is ignored by root. Fix: skip on euid 0 | accepted | test hygiene |
| R8 | P2 | tests/unit/test_hm_cost_p3_reuse.py:73 | The failed-run row never asserted that no record exists. Fix: `_seed` asserts it; config and unreadable-file tests added | accepted | SPEC AC-002 |
| R9 | P2 | tests/unit/test_hm_cost_p3_templates.py:31 | The Open Questions phrase was searched in the whole render. Fix: asserted inside Step 3 | accepted | SPEC AC-001 |
| C2 | P1 | tests/integration/test_hm_cost_p3_bar.py:21 | AC-005's SHA fixture and re-run rows were missing | duplicate | PLAN P4 (the bench ran after review) |
| G1 | — | tests/unit/test_overhaul_p1_hm_check.py:801 | Found by the gate, not a reviewer: SPEC-hm-overhaul-p1 AC-005 forbids any byte written under the root, .git included, which IRR-002's git-dir record breaks. Fix: `_every_byte` skips exactly `.git/hm/check-verdict.json` (PLAN ADR-009) | accepted | SPEC-hm-cost-p3 IRR-002 |

Round 2 (fixes only): no findings.

## AC-005 — pre-registered bar missed

| run | harness | transcript ratio | CLI ratio | hidden pass plain / hm |
|---|---|---|---|---|
| before (hm-cost-p2, counted) | 94a6d1f32935 | 12.21 | 11.04 | 15/15 / 15/15 |
| this task | cdf28dce3b12 | **11.36** | 10.27 | 15/15 / 15/15 |

The bar was ≤ 10.0, so AC-005 fails as written. The run was clean (no budget-capped, leak-suspect or
judge-truncated run; `--reuse` hit in 14 of 15 runs). Spend fell 5% ($0.786 → $0.746 per hm run); the
estimate of 8x assumed a reused gate saves tokens, but it saves test wall time — see
RESEARCH-hm-cost-p3, "Measured after the change". Re-running until a pass would be a reinterpretation of a
pre-registered rule, and changing the approved AC is the DRI's decision, so the task stops here with the
branch ready.

**DRI decision (2026-10-22):** land with the miss recorded and the 10.0 bar unchanged. AC-005 was reworded
to that record and re-approved; its test pins the single violation (`tier-1 transcript ratio 11.359 > 10.0`),
which fails if a later run changes it.

## Notes

- Execute's per-round `hm check` rerun was dropped in favour of one unconditional post-REVIEW check; round 2
  found that safe.
- ADR-004: AC-002's `written_by_failed_run` row says "the gate is then fixed" in its oracle_evidence while
  its expected exit is 1; the test follows the table (gate still failing).
