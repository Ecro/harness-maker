# BASELINE-DELTA — hm-light-lane-s2

Re-frozen inside this task, not left as an in-flight allowance: the Claude aggregate fell 10.3%,
past `test_a_large_shrink_means_the_baseline_went_stale`'s 5% band.

Direction: both aggregates **fell**, `aggregate_chars.claude` by 36,176 chars and
`aggregate_chars.codex` by 21,176 chars. This repo's `.claude/harness.yaml` has
`loop.enabled: false`, so every loop-only branch SPEC-hm-light-lane-s2 gated stops rendering here.

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.execute.chars`, `.round_trips` (`execute`) | 63063 → 51676 chars, 25 → 19 trips | Gate 0 receipt, Step 0.2, Step 5 and the `execute-<uuid>` Quality Bar line are loop-only (AC-001); the auto-advance block became a stub (AC-003); C.0 and D.5 are three lines each (AC-008). Calls gone: `iter_receipts write`, `loop-mode-active`, `owned-crumb-add`, `finalize stage-only`, `finalize fail`, `post-commit-pop` |
| `surface.claude.review.chars`, `.round_trips` (`review`) | 87350 → 77378 chars, 35 → 33 trips | Step 2.5, step 5c and the Size & Complexity section removed (AC-007); Gate 0 and the two loop-mode pseudo-code lines are loop-only; stub. Calls gone: `iter_receipts write`, `review_churn complexity` |
| `surface.claude.spec.chars`, `.round_trips` (`spec`) | 46032 → 42326 chars, 10 → 9 trips | Gate 0 loop-only; stub. Call gone: `iter_receipts write` |
| `surface.claude.verify.chars`, `.round_trips` (`verify`) | 26703 → 23075 chars, 13 → 10 trips | Gate 0 and Check 5 loop-only; stub. Calls gone: `iter_receipts write`, `git status`, `git diff --check` |
| `surface.claude.research.chars`, `.round_trips` (`research`) | 23748 → 20416 chars, 8 → 7 trips | Gate 0 loop-only; stub |
| `surface.claude.wrapup.chars`, `.round_trips` (`wrapup`) | 56294 → 52986 chars, 33 → 32 trips | Gate 0 loop-only; stub |
| `surface.claude.health.chars` (`health`) | 9641 → 8643 chars | The `silent_intent_miss_rate` sub-check left `/hm:health` (AC-007) |
| `surface.claude.<cmd>.chars` (`configure`, `help`, `make`, `metrics`, `uninstall`) | +31 chars each | Not this task: stage 1 (PR #17, lever 5) added `disable-model-invocation: true` to these five and stayed inside the 5% band, so it never re-froze. Recorded here so the row is attributed. Stage 1's light-lane edits to the stage commands are folded into their rows above the same way |
| `surface.codex.hm-execute.chars`, `.round_trips` (`hm-execute`) | 64273 → 54789 chars, 26 → 20 trips | The same execute cuts on the Codex stage skill. The Codex auto-advance block is out of scope (Non-Goals) |
| `surface.codex.hm-review.chars`, `.round_trips` (`hm-review`) | 86880 → 80213 chars, 31 → 29 trips | Same as Claude review, without the stub |
| `surface.codex.<skill>.chars`, `.round_trips` (`hm-research`, `hm-spec`, `hm-verify`, `hm-wrapup`) | −1453, −394, −1749, −1429 chars; −1 trip each | Gate 0 loop-only (verify also Check 5's prose; its two `git` lines do not count as Codex calls) |
| `aggregate_chars.claude` (`aggregate_chars`) | 351388 → 315212 | The Claude rows above |
| `aggregate_chars.codex` | 304671 → 283495 | The Codex rows above |
| `payload_digest`, `render_sha` | mechanical | `render_sha` is the merge-base `e9b6198`; the generator refuses a task-branch HEAD |

AC-010 (spec + execute + review + verify, Claude): 223,148 → 194,455 against the frozen values.
The SPEC's 222,607 was measured on a fresh e9b6198 render; the 541 chars between the two are stage
1's net change to these four commands, which also stayed inside the band. Against 222,607 the cut
is 28,152 chars, over the 20,000 floor.

Ownership (ADR-010): the baseline is re-frozen by the task that moved it, after its own tests
were green, with one attribution row per moved key, never by whichever later task trips the
ratchet (`ratchet-rebaselined-by-its-own-subject`). The stage-1 rows are the one exception and
are labelled as such: stage 1 moved them inside the band and did not freeze.

Golden re-capture (`autopilot_gate_golden.json`) is recorded in the test module docstring. The
snapshots were regenerated with `regenerate.py`, and `test_loop_opt_in._LOOP_ON_RECAPTURES` holds
the loop-on hashes of the twelve stage bodies that became loop-sensitive.
