---
type: review
task_slug: review-effect-measurement
created: 2026-10-17
spec: "[[SPEC-review-effect-measurement]]"
plan: "[[PLAN-review-effect-measurement]]"
reviewers: [code-reviewer, codex]
rounds: 2
---

# REVIEW — review-effect-measurement

Round 1 had two voters, `code-reviewer` and `codex` (second opinion, `status: invoked`, 46 s). Findings that
both voters raised were accepted under K=2. Findings that only one voter raised went to `code-verifier` with
oracle output reproduced in the worktree: 8 in, 8 accepted.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P1 | src/harness_maker/review_effect.py:292 | `escape` stored `--commit` unresolved. A short SHA bypassed the duplicate check and the candidate stayed listed | accepted | K=2 (code-reviewer #1, codex 02599d51) |
| F2 | P1 | src/harness_maker/review_effect.py:236 | Blame boundary lines (`^` + 39 hex) failed the 40-hex match, so the hints were lost. Fixed with `--porcelain` | accepted | code-verifier S3 (rates it P2; the reviewer's P1 is kept) |
| F3 | P2 | src/harness_maker/review_effect.py:487 | `clopper_pearson(550, 1100)` raised OverflowError. Fixed with a log-space pmf | accepted | code-verifier S1, oracle |
| F4 | P2 | src/harness_maker/review_effect.py:345 | Multiline Compare and BoolOp nodes were never candidates, contrary to AC-008's "first line" rule | accepted | code-verifier S2, oracle |
| F5 | P2 | src/harness_maker/review_effect.py:419 | `seed` dropped the file mode (atomic_write's temp file is 0600). Symlinks are now skipped | accepted | K=2 (code-reviewer #4, codex 96175f87) |
| F6 | P2 | src/harness_maker/review_effect.py:661 | The dirty-tree refusal printed a placeholder. It now names the exact scratch-worktree command and a safe in-scratch restore; it never suggests discarding user changes | accepted | code-verifier S4 |
| F7 | P2 | src/harness_maker/review_effect.py:258 | A malformed review `ts` crashed `escape-candidates`. It is now skipped with a warning | accepted | code-verifier S5, oracle |
| F8 | P2 | tests/unit/test_review_effect.py:198 | The AC-007 test left seeded recall, by_status, unrecognized_n and the `[lo, hi]` format unasserted | accepted | code-verifier S6 |
| F9 | P2 | tests/integration/test_review_effect_land.py:92 | There was no land-level `unparseable` and single-warning test | accepted | code-verifier S7 |
| F10 | P2 | src/harness_maker/review_effect.py:446 | `score` raised KeyError on a malformed manifest entry. It is now exit 2 | accepted | code-verifier S8, oracle |
| F12 | P2 | src/harness_maker/review_effect.py:233 | Round 2: git's trailing TAB on a header path with a space was kept, so blame failed and hints were silently empty | accepted | code-verifier R2-1, oracle |
| F13 | P2 | src/harness_maker/review_effect.py:342 | Round 2: both diff parsers read `--- `/`+++ ` inside a hunk as a header. Replaced by one `_hunks` parser that tracks header state | accepted | code-verifier R2-2 (code-evident; not reproduced) |
| F14 | P2 | tests/integration/test_review_effect_git.py:336 | Round 2: seed's symlink skip had no test | accepted | code-verifier R2-3 |
| F11 | P2 | specs/SPEC-review-effect-measurement.md AC-010 | Drift: the md said "Claude and Codex variants", but Codex renders no `/hm:metrics`. The md wording was corrected; the machine predicate is unchanged | accepted | code-reviewer (judged legitimate) |

## Round notes

- **`hm check` round 0.**
  - First run: `metrics.md` was 3108 chars, over the 3000 budget (SPEC-hm-overhaul-p1 AC-004). The new step
    was shortened.
  - Second run: the only failure left was `tests/unit/test_bench_light_lane.py`, whose hm arm fetches from
    PyPI and fails DNS in this environment. That test does not touch this task's code; see the wrapup note.
- **Full suite (bench file excluded, no `-x`)** found two more failures: the aggregate surface ratchets
  (+457 chars). Both were resolved by PLAN ADR-006, a re-freeze attributed in
  `BASELINE-DELTA-review-effect-measurement.md`. That growth is the SPEC's one allowed `/hm:metrics` step,
  plus −36 from #39 that had never been folded. It is recorded as a decision, not a finding.
- **Round 2.** `code-reviewer` alone, because codex is frozen after round 1 (one call per review). It judged
  all eleven round-1 fixes correct and found no P0/P1. It raised three P2s (F12–F14), which `code-verifier`
  accepted. Every accepted finding from both rounds has a regression test, in the `review round 1/2
  regressions` blocks.
