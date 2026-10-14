# BASELINE-DELTA — hm-light-lane-s2b

Re-frozen inside this task, not left as an in-flight allowance: the Claude aggregate fell 15.9%,
past `test_a_large_shrink_means_the_baseline_went_stale`'s 5% band.

Direction: `aggregate_chars.claude` **fell** by 50,294 chars (315,578 → 265,284);
`aggregate_chars.codex` did **not move** (283,669). Codex stage skills run their bodies inline, so
the five bodies that left the Claude commands are still in the skills (AC-006, pinned by
`tests/render/test_render_light_lane_s2b.py::test_codex_stage_skills_unchanged`). This repo's
`.claude/harness.yaml` has `delegation.stages: [wrapup, verify]`, `loop.enabled: false` and
`worktree.enabled: true`, so wrapup and verify move here; under the default `delegation.stages: []`
they stay inline and byte-identical to `d2c0ab0`.

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.wrapup.chars`, `.round_trips` (`wrapup`) | 53107 → 33099 chars, 32 → 20 trips | Steps 1–5.6 left the command for `.claude/hm/wrapup-steps.md`; the command keeps the preflight, Step 0.5, Steps 5.7 and 6 → 8 and a pointer whose STOP stops before 5.7 and 6, so a missing file cannot reach a commit. The `hm` calls of Steps 1–5.6 are now read on demand. One call was **added**: the `!test -r` existence check before the dispatch (review round 1, S1) |
| `surface.claude.verify.chars`, `.round_trips` (`verify`) | 23120 → 16435 chars, 10 → 7 trips | The check bodies left for `.claude/hm/verify-checks.md`; `## Output` stays, and the degraded inline section carries the pointer. Gate 0 is kept in the command (loop-on only). One call was **added**: the `!test -r` existence check before the dispatch (review round 1, S1) |
| `surface.claude.review.chars`, `.round_trips` (`review`) | 77384 → 60617 chars, 33 → 20 trips | The auto-fix rounds left for `.claude/hm/review-autofix.md` and the confirmation pass for `.claude/hm/review-confirmation.md`, each read only when a round fixes or the grade gate reaches confirmation. Not a delegated stage, so this moves on every config |
| `surface.claude.execute.chars`, `.round_trips` (`execute`) | 51819 → 44985 chars, 19 → 18 trips | Phase A.5 left for `.claude/hm/execute-a5.md`; the `stage_agent_ledger` block that closes A.5 stays in the command, so the pointer is followed by the ledger line it always preceded. Not delegated; moves on every config |
| `aggregate_chars.claude` (`aggregate_chars`) | 315578 → 265284 | The four Claude rows above |
| `aggregate_chars.codex` | 283669 → 283669 | Unchanged by design (AC-006) |
| `payload_digest`, `render_sha` | mechanical | `render_sha` is the merge-base `d2c0ab0`; the generator refuses a task-branch HEAD |

AC-009 (wrapup + verify + review + execute, Claude): 205,430 → 155,136, a cut of 50,294 against
the frozen values. The SPEC prints the before value as 204,430; the four components it lists
(53,107 + 23,120 + 77,384 + 51,819) sum to 205,430, which the test uses. Either way the 40,000
floor is met.

The five reference files total 5 more rendered files per target (`.claude/hm/`), and the moved text
is held byte-identical by sha256 against fixtures captured from `d2c0ab0` in a temporary worktree
(`tests/fixtures/light_lane_s2b/`).

The values above are after `/hm:review` round 1, whose fixes added 1,646 Claude chars back across the
four commands (wrapup +710, verify +432, review +479, execute +25) plus the prefaces in the five
reference files: the Step 0.5 existence check (S1, one call each on wrapup and verify), the stop clause
on the two review pointers (C2), the `confirm-1` and `tdd_active` pointer conditions (K1, C3), the
mismatch bullet's pointer (K2), and the reworded degraded-path lines (K5). Codex did not move. The
baseline was re-frozen in that fix commit by this same subject, not left as an in-flight allowance.

The confirmation pass then added 292 Claude chars (wrapup +199, verify +93): the existence checks name
the delegate's `<brief.base_root>` path, and the wrapup mismatch bullet carries the shared missing-file
clause. The frozen `round_trips` above stay the command's own (the surface baseline counts commands as
shipped); `tests/structural/test_roundtrip_budget.py` now counts each command plus the reference files
it points at, and its table was re-based to that quantity (execute 19, review 33, verify 11, wrapup 33,
which is the d2c0ab0 count plus one `!test -r` each on verify and wrapup). Codex did not move; the Codex
`stage-delegate.toml` renders the pre-2b blanket rule, unchanged.

Ownership (ADR-010): the baseline is re-frozen by the task that moved it, after its own tests
were green, with one attribution row per moved key, never by whichever later task trips the
ratchet (`ratchet-rebaselined-by-its-own-subject`).

Golden re-capture (`autopilot_gate_golden.json`, `wrapup_intent_hardening/goldens.json`) and the
snapshot regeneration (`tests/snapshot/regenerate.py`) are recorded in their module docstrings.
`test_loop_opt_in._LOOP_ON_RECAPTURES` holds the loop-on hashes of the four stage bodies that
shrank, the two new loop-sensitive reference files and `loop.md`.
