---
type: review
task_slug: self-prune-loop
created: 2026-11-23
spec: "[[SPEC-self-prune-loop]]"
summary: Two code-reviewer rounds; 3 P0 protection bypasses and 2 P1 decide defects found and fixed; codex second opinion skipped (CLI not installed).
---

# REVIEW-self-prune-loop-2026-11-23

Voters: code-reviewer (2 rounds, with a probe script against a spec.md fixture). Second opinion:
codex `skipped` (CLI not installed; warn-and-proceed). Single-voter findings were accepted on the
reviewer's reproduced probe output, each fixed with a regression test.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1-1 | P0 | scripts/self_prune.py:88 | `./.claude/...` path spelling bypassed protection | accepted | probe hits=0; fixed by `bench.edit_rel`, test_ac_003_protection_bypasses |
| R1-2 | P0 | scripts/self_prune.py:112 | `old` spanning from an unprotected into a protected section not caught | accepted | probe; fixed: every heading in the span + enclosing sections |
| R1-3 | P0 | scripts/self_prune.py:98 | edits checked against the original render, applied sequentially (insert heading, then drop it) | accepted | probe; fixed: sequential simulation via `bench.apply_edit` |
| R1-4 | P1 | scripts/self_prune.py:213 | raw counts compared without equal run sets (budget-capped baseline) | accepted | fixed: unequal (task, rep) cells -> hold, test_ac_005_unequal_runs_hold |
| R1-5 | P1 | scripts/bench_light_lane.py:3718 | variant.json written before the consistency check; decide trusted it | accepted | fixed: written after ensure_consistent; decide checks rows' `variant` |
| R1-6 | P2 | scripts/self_prune.py:111 | only the nearest heading checked, not ancestors | accepted | fixed: `_enclosing` |
| R1-7 | P2 | scripts/self_prune.py:266 | dir with no tier-2 rows still produced a ledger row | accepted | fixed: exit 2 (parametrized mismatch case) |
| R1-8 | P2 | scripts/self_prune.py:183 | identity ignored runner settings the variant hash hides | accepted | fixed for row fields judge_model, max_budget_usd; claude version not on rows (known gap, SELF-PRUNE.md Limits) |
| R1-9 | P2 | tests/unit/test_self_prune.py:180 | no test for the bypasses | accepted | test_ac_003_protection_bypasses |
| R1-10 | P2 | tests/unit/test_self_prune.py:280 | metrics filtering untested; mismatch only on model | accepted | noise rows + 6 parametrized mismatch cases |
| R1-11 | P3 | tests/unit/test_self_prune.py:222 | render check not fence-aware | accepted | uses `bench.headings` |
| R1-12 | P3 | scripts/self_prune.py:251 | ledger rewrite could lose concurrent rows | accepted | single O_APPEND write |
| R1-13 | P3 | scripts/bench_light_lane.py:3517 | misleading arm/variant error on an arm typo | accepted | message names the arms |
| R2-1 | P1 | scripts/self_prune.py:117 | an edit adding a code fence hides later headings from protection | accepted | probe; fixed: `plan` refuses a `new` that adds a heading or fence line (test in test_ac_003_protection_bypasses) |
| R2-2 | P3 | scripts/self_prune.py:334 | reject overridden by hold on unequal cells reads confusingly | accepted | reasons now lead with "inconclusive" and mark the rest "on unequal cells" |
| R2-3 | P3 | scripts/self_prune.py:126 | replace span counted one extra line when `old` ends with a newline | accepted | `rstrip("\n")` before counting |

Also changed outside the new files: `tests/unit/test_bench_tier3.py` pins `ALL_ARMS`; the pin now
includes `hm-variant` (the SPEC adds that arm by design).
