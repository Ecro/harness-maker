---
type: review
task_slug: human-bottleneck-auto-advance
scope: the autonomy-FIX working-tree diff (resolves the 19 findings of REVIEW-...-fullreview-2026-06-21)
status: APPROVED
created: 2026-06-21
reviewers_invoked: [security-guard-rewrite, caps-and-wiring, templates-and-tests]
consensus_method: per-dimension reviewer + independent adversarial verifier (k-of-2)
grade: A
human_review_needed: false
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-21
  note: >
    No PLAN-{slug} for the fix work — it is driven by REVIEW-...-fullreview-2026-06-21.
    Every changed file maps to a fullreview finding; the concurrent-session files
    (worktree.py, test_worktree_task_land.py) are excluded from this change set. No
    out-of-scope edits.
---

# REVIEW — autonomy fix diff (round 2)

Reviewed the working-tree diff that fixes the 19 findings from the full-feature
retrospective: `autopilot_caps.py` (merge-gate, cap-clear, unknown-stage), `autopilot_guard.py`
(shlex rm tokenizer + cd-escape tracking + permission-regex parity), `autopilot.py`,
`autopilot_ledger.py`, `cli.py`, `workflow_fuse.py`, `stage_end_summary.md.j2`, and 6 test files.

Method: 3 dimension reviewers (security-guard-rewrite / caps-and-wiring / templates-and-tests),
each finding adversarially re-verified against the live code; the orchestrator independently
re-probed the rm tokenizer against 12 bypass vectors.

## 🎯 Summary

| | |
|---|---|
| **Grade** | **A** (0 consensus P0, 0 consensus P1) → APPROVED |
| **Confirmed** | 6 (1×P2, 5×P3) — all **resolved this round** |
| **Dropped/refuted** | 2 (self-concluded non-defects) |

The fixes are correct. No new P0/P1 was introduced by the rewrite — in particular the
shlex rm tokenizer closes the P1-2 traversal bypass without opening a regression (verified
against `rm -rf -- /etc`, `--no-preserve-root`, `$()`, glob, tilde-user, bare `..`). The
review found one residual edge bypass (brace expansion) and several test/robustness gaps,
all now closed.

## ✅ Consensus Findings (all resolved)

### P2-r2 — brace-expansion rm bypass (resolved)
`autopilot_guard.py` `_operand_escapes_worktree`: `rm -rf {/etc,/home}` was ALLOWED — bash
expands the brace list to absolute operands before the path is read. **Not a regression**
(the old prefix-char regex missed it too), but closed since this pass hardens the guard.
**Fix:** treat a token containing `{`…`,`…`}` as statically-unboundable → escape (same family
as `$`/`~`). Regression test `test_active_blocks_rm_brace_expansion` added.

### P3-r2 (×5 — resolved)
1. **malformed-cd asymmetry** — `_segment_is_cd_escape` now block-biases on a malformed
   (unclosed-quote) cd, matching `_segment_rm_escapes`. (Verifier confirmed this was
   theoretical-only — the unclosed quote that makes cd malformed also swallows the trailing
   `rm` in a real shell — but the contract-parity fix is cheap and correct.) Test added.
2. **rm test gap** — added regression tests pinning the `--` end-of-options skip
   (`rm -rf -- /etc`), `--no-preserve-root`, and `$()`/backtick substitution paths, plus a
   benign `rm -rf -- node_modules` control.
3. **cap-halt vs unknown_stage ordering** — `_cmd_boundary` now checks an unknown `--current`
   **before** the cap block, so a typo can never trigger the marker-clearing cap path and
   falsely claim a cap halt; the marker is preserved as designed.
4. **boundary fixture order** — `test_autopilot_boundary.py` now uses
   `list(AutonomyConfig().pipeline)` (verify-before-wrapup), one source of truth with the e2e
   and config tests; `next_stage(review)` assertion updated to `verify`.
5. **`..`-component over-block** — `rm -rf build/../dist` is blocked even though it resolves
   in-worktree. This is the intended fail-safe direction (static containment is undecidable);
   added a test pinning the behavior + a code comment.

## 📝 Dropped / Refuted (2)

- **count_events cross-session over-count** (P3→DROP): the finding self-concluded "not a
  defect"; the verifier confirmed `count_events` already scopes by `since=marker.created_at`,
  so prior-session rows are excluded.
- **double `gate_blocked` observability noise** (P3→DROP): two call-sites can emit
  `gate_blocked` for one logical stop — observability noise, not a correctness bug; the smoke
  check only cares about zero-vs-nonzero.

## Iteration record

### Iteration 1 (Grade A → A; hardening applied)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P2 | brace-expansion rm bypass | autopilot_guard.py | Applied |
| 2 | P3 | malformed-cd block-bias parity | autopilot_guard.py | Applied |
| 3 | P3 | rm `--`/`$()` regression tests | test_autopilot_guard.py | Applied |
| 4 | P3 | unknown_stage before cap block | autopilot_caps.py | Applied |
| 5 | P3 | canonical boundary fixture | test_autopilot_boundary.py | Applied |
| 6 | P3 | `..`-overblock test + comment | autopilot_guard.py / tests | Applied |

Remaining: 0 | New issues introduced: 0

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 6 (hardening) | 0         | 0   |

Final grade: A
Iterations used: 1 / 3
Status: APPROVED
human_review_needed: false

## Verification
- ruff ✅ / ruff format ✅ / mypy --strict ✅ (109 files)
- autopilot guard/caps/boundary/ledger/e2e tests ✅
- No template change this round → no snapshot impact.

## Out of scope (unchanged from fullreview)
- `test_worktree_stash_isolation.py::test_wrapup_template_git_add_line_extractable` fails on
  HEAD due to a **concurrent session's** commit (`394f86e`/`3c428a4`) adding `{{ wt_prefix }}`
  to `wrapup.md.j2` without updating the integration-test regex. Not part of the autonomy
  work; deferred to that author to avoid disturbing their in-flight WIP.
