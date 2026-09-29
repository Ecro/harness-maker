---
type: review
task_slug: top-issues-2026-09
status: APPROVED
created: 2026-09-30
run_id: 3f6cd717ca37
reviewers_invoked: [code-reviewer (design+functionality+robustness+consistency), security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
second_opinion_results: [{model: codex, status: skipped, reason: "codex CLI usage limit until 2026-10-04"}]
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: top-issues-2026-09
  computed_at: 2026-09-30T00:00:00Z
---

# REVIEW — top-issues-2026-09

## 🎯 Round 1 Summary

- **Grade C.** There are three consensus-passed P1s from single-lens votes, plus one P1 that the
  orchestrator found itself (below). Pending fixes: all four P1s. Eight P2 and seven P3 findings
  are carried for a human sweep (the P2/P3 queue rule).
- **Coverage.** All seven lenses were exercised (`blocks_approval: false`).
- **Pass 1 / Pass 2 collapsed.** The diff is an uncommitted worktree. There is no PR title,
  description, author or commit message to redact, so the redacted and full contexts would have
  been byte-identical. One pass was run and is recorded here as a deviation.
- **Codex was skipped** because the CLI hit its usage limit. That is a warn-and-proceed outcome,
  so the voter pool this round was the four Claude dispatches only.
- **Dogfood.** Step 3.4 ran the new `review_churn attribute` from this worktree's source on the
  round-1 payload: 18 of 18 were stamped `none`, which is correct for round 1. The payload was
  persisted (`3f6cd717ca37-round1-merged.json`).

## 🔍 Drift Findings

None. `command_registry.py` and `documentation_contract.py` (plus
`test_documented_commands_exist.py`) were edited outside the phase scopes as written. Execute
reported those edits (PLAN "Stage exit"), and the PLAN scopes were amended with that reason
before this review ran.

## ✅ Consensus Findings (round 1)

| id | Sev | Lens | Location | Summary |
|---|---|---|---|---|
| 081ddfc3 | P1 | functionality | verification_cache.py:521 | `run_gates` writes a run-authored PASS marker when zero commands ran (all CI gates non-blocking) |
| db1aa405 | P1 | concurrency | verification_cache.py:489 | Gate timeout kills only the direct child; grandchildren keep running on the tree |
| 22071e4e | P1 | concurrency | verification_cache.py:486 | Per-command timeout with no overall deadline; total can exceed the 600 s host cap |
| cc6ec677 | P2 | robustness | verification_cache.py:421 | Docstring implies the run stays under 600 s (same root cause as 22071e4e, different tier: kept independent) |
| 8b9ccd8e | P2 | functionality | verification_cache.py:490 | `shlex.split` mis-runs CI commands with shell operators or env prefixes |
| 5cad42ed | P2 | robustness | review_churn.py:638 | Quoted non-ASCII paths (`core.quotepath`) break the path key, so findings are stamped `none` |
| 200f8232 | P2 | functionality | review_churn.py:756 | Whole-file findings (line 0) are attributed by proximity to line 0 |
| 9e6c5e80 | P2 | consistency + concurrency | review_churn.py:778 | Hand-rolled fixed-name tmp + replace (collision and leak) instead of `io_utils.atomic_write` |
| 2e1b08d6 | P2 | security | verification_cache.py:486 | `run` executes the checked-out tree's workflow commands; the trust boundary is undocumented |
| d2dc6673 | P2 | concurrency | verification_cache.py:383 | `mark-pass` can overwrite a run-written marker (a safe-direction downgrade) |
| b7d8809f | P2 | tests | test_render_review_attribution.py:40 | The same-file binding test compares two identical placeholders |
| 26e339e3 | P3 | security | verification_cache.py:441 | `writer` is self-declared: accident protection, not a security boundary |
| 7cc4f57d | P3 | security | verification_cache.py:490 | `shlex.split` ValueError is uncaught, which breaks the 0/1/3/4 exit contract |
| 1772092b | P3 | security | review_churn.py:778 | Predictable `.tmp` sibling follows a pre-planted symlink |
| 0bf90611 | P3 | security | review.md.j2:409 | `{slug}` is unquoted in the attribute recipe |
| f59b6c0c | P3 | tests | test_render_review_attribution.py:20 | Arm (b) predicate clauses are not bound to the (b) sentence |
| 0c63e376 | P3 | tests | test_verification_cache_run.py:105 | The property test samples an 8-point space and may miss the exit-4 case |
| ffdb58e3 | P3 | tests | test_verification_cache_run.py:174 | Sound; optionally assert the rejected marker was rewritten |

The special-attention tests carried from execute's exhausted A.5 were re-examined by the tests
lens. `test_cached_only_for_own_marker` was judged **sound**: writer provenance, command hash and
command list are each pinned by a distinct fixture. `test_caused_by_single_owner` holds for the
failure it targeted; residual tightening is carried as P3.

### Orchestrator finding (main loop, not a lens vote)

| id | Sev | Location | Summary |
|---|---|---|---|
| main-offbyone | P1 | review_churn.py `attribute_findings` / SPEC S1 | **Off-by-one against the loop's own labels.** The Auto-Fix Loop pins iteration N's fixes as `r{N}-pre/post` (review.md.j2:843-901; repair rounds are `2,3,…`, L1131), and round N's findings come from the re-review that follows. `attribute` looks up `r{N-1}`, so in real use round 2 would find no `r1` refs and stamp everything `unknown`. No lens raised this: every fixture used the SPEC's own (wrong) convention, so all 30 tests were green on a verb that never attributes anything in production. The fix changes the SPEC wording (`fix-r<N>`, refs `r{N}`) and requires re-approval under the standing instruction. |

It is recorded here rather than voted, because it is an orchestrator observation. It is applied
in iteration 2 with the three P1s above. The discovery route was the dogfood run, which asked
"which ref would round 2 read?"

## ⚠️ Weak Consensus
None.

## 📝 Manual-Only Findings
None.

## 🤝 Disagreements
- The overall-deadline issue was raised at P1 by concurrency (22071e4e) and at P2 by robustness
  (cc6ec677). The two are not bridged across tiers (Step 4c) and are kept as independent
  findings. One fix resolves both.

## 🧊 Cross-model findings (frozen @ round 1)
- codex: `skipped` (CLI usage limit until 2026-10-04). No findings, nothing to re-read in later rounds.

### Iteration 2 (Grade: C → A)
Fixes applied: 4
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Zero blocking gates → EXIT_DEGRADED, no marker (081ddfc3) | verification_cache.py | Applied · caused_by=none |
| 2 | P1 | Each gate runs in its own session; timeout `killpg`s the group (db1aa405) | verification_cache.py | Applied · caused_by=none |
| 3 | P1 | Whole-run deadline `RUN_DEADLINE_S=570`; each gate gets min(per-command, remaining) (22071e4e; also resolves P2 cc6ec677 and the ValueError half of P3 7cc4f57d) | verification_cache.py | Applied · caused_by=none |
| 4 | P1 | Off-by-one: round N attributed against `r{N}` / `fix-r{N}` (main-offbyone); SPEC S1/S2/AC-001/002/014 corrected, re-approved | review_churn.py, review.md.j2, SPEC | Applied · caused_by=none |

New tests for the windows these repairs reach (Phase D.5):
- `test_no_blocking_gate_is_degraded_not_a_pass`
- `test_timeout_kills_the_whole_process_group`: a grandchild must not write after the timeout. While
  building this test, a fixture defect surfaced: the key's `_tool_versions` probe was calling the fake
  tool's `--version` with the spawn/sleep knobs set. The fake now answers `--version` immediately.
- `test_run_deadline_caps_the_sum_of_commands`
- `test_unbalanced_quote_is_a_failure_inside_the_exit_contract`
- A new AC-002 golden row: a round-2 finding with only `r1` refs pinned gets `unknown`. This
  discriminates the old off-by-one.

Verify: `test_review_churn_attribute` and `test_verification_cache_run` are green. The structural, render and snapshot suites
passed after re-freezing (802 passed). The aggregate surface is still below the pre-task value (claude
357,684 < 357,790).

Remaining: 15 (8 P2, 7 P3, all accepted and carried for a human sweep) | New issues introduced: 0 (re-review skipped)
Churn: 0.285 (max: specs/SPEC-top-issues-2026-09.machine.yaml, measured 15, excluded 0)
rereview: skipped — churn 0.29 < 0.30
Dogfood: `attribute --round 2` read `r2` and kept every carried id's round-1 value (`none` ×15).

## Confirmation Pass 1 (frozen `84b92570`, span `5611d09f..84b92570`)

- **Coverage:** all 7 lenses were exercised.
- **New severe findings:** 2, both P1 and both from the concurrency lens.
- **Both were introduced by iteration 2's own fix**, which is the `fix-introduced-defect-passes-all-gates` shape:
  - **P1 (concurrency):** `start_new_session` orphans a running gate when `run` is interrupted or
    terminated. Only `TimeoutExpired` triggered `killpg`. Core/robustness raised the same issue at P2.
  - **P1 (concurrency):** the post-kill `proc.communicate()` was unbounded. A `setsid` descendant holding
    the pipe open would block forever and defeat `RUN_DEADLINE_S`.
- **New P2/P3 findings, carried for a human sweep:**
  - The deadline excludes key computation.
  - Gate stdin is inherited.
  - Strict decoding misreports a passing gate as "could not start".
  - The `--mode full` key ignores untracked files (reachable only via an explicit flag).
  - Attribution fixtures are round-2 only (need r3 cases).
  - The `context_lint` docstring is stale.

### Confirm-1 repair round (budgeted separately; does not increment iteration_count)

- **C.0 root cause:** `_run_gate` cleaned the group on the timeout branch only, and its reap had no bound.
- **Scope:** `_run_gate`, plus a SIGTERM→`_TerminatedError` bridge scoped to the gate loop. Termination
  maps to exit 1.
- **Non-goals:** the P2s above.

| # | Severity | Summary | Status |
|---|---|---|---|
| 1 | P1 | `except BaseException` → `_kill_group` (killpg plus a reap bounded by `REAP_TIMEOUT_S=5`, then close/kill/wait) | Applied · caused_by=fix-r2 |
| 2 | P1 | SIGTERM bridge (main thread only, restored after the loop); `main` maps `_TerminatedError` → exit 1, no marker | Applied · caused_by=fix-r2 |

- **New tests (D.5 windows):**
  - `test_termination_kills_the_gate_group_and_stays_in_the_exit_contract`: the fake gate SIGTERMs its
    parent after spawning a grandchild.
  - `test_reap_is_bounded_when_a_descendant_holds_the_pipe`: a `setsid` descendant holds stdout.
- **Verification:** 12 + 68 passed.
- **Churn:** 0.163.
- **`caused_by=fix-r2` is hand-applied here.** A confirm-pass finding has no automatic attribution
  (SPEC non-goal). The span was verified by reading the r2 fix, which introduced `start_new_session`.

## Confirmation Pass 2 (frozen `3db2288f`, span `5611d09f..3db2288f`)

All 7 lenses were exercised. **Zero new P0/P1 findings, so the review is APPROVED.** The pass
raised new P2/P3 findings, carried for a human sweep. They concern the signal safety of the
confirm-1 repair; none is a regression of the P1s:

- Only SIGTERM is bridged; SIGHUP is not.
- A second signal can arrive during cleanup, and there is a gap between `Popen` and `try`.
- The final `wait` in `_kill_group` can raise and replace the original exception, so an
  interrupt is misreported as a timeout (the exit code is still 1).
- `None` is overloaded in the SIGTERM restore.
- `pin_ref` and `oscillation_path` take a slug with no validation. These are pre-existing verbs.
- P3: no test checks that the handler is restored or covers the Ctrl-C path.

## 🔁 Oscillation
None (`review_churn oscillation --rounds 2` → `[]`).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 18 (+1 orchestrator P1) | — |
| 2         | A     | 4             | 15 (P2/P3) | 0 (re-review skipped, churn 0.29) |
| confirm-1 | —     | 2 (repair)    | +6 P2/P3  | 2 P1 (fix-introduced) |
| confirm-2 | A     | —             | +8 P2/P3  | 0 P0/P1 |

Final grade: A
Iterations used: 2 / 3 (+ confirm-1 repair, budgeted separately)
Exit reason: converged
Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 4 (iteration 2's fixes were not re-reviewed because the churn gate skipped it; the confirmation pass covered them) · prior-fix 2 (the confirm-1 P1s, caused by fix-r2) · unattributed 0

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/observability/verification_cache.py | 622 → 658 (r2) | null → null | null → null | measured |
| src/harness_maker/review_churn.py | 970 → 972 (r2) | null → null | null → null | measured |

Values are from 5c's rows. The collector reported `measured` with null cyclomatic and nesting
values. That is recorded as-is, not re-derived.

## Carried P2/P3 backlog (human sweep, next task)

- **review_churn:** quotepath (5cad42ed), line 0 (200f8232), atomic_write (9e6c5e80/1772092b),
  slug validation on pre-existing verbs, round-3 fixtures.
- **verification_cache:**
  - shlex operators (8b9ccd8e) and the trust boundary doc (2e1b08d6)
  - markers: mark-pass overwrite (d2dc6673), forgeable writer doc (26e339e3), full-mode untracked key
  - process handling: deadline margin, stdin DEVNULL, decode errors, SIGHUP, the second-signal
    window, cleanup exception masking, restore sentinel
- **Templates:** unquoted slug (0bf90611).
- **Tests:** the placeholder-binding control (b7d8809f), the arm (b) clause binding (f59b6c0c), the
  deterministic 8-case property (0c63e376), and the handler-restore and Ctrl-C tests.
- **Docs:** context_lint docstring.

## Post-approval fix found at /hm:verify (dogfood)

- **Defect.** Running this task's own `run` against this repo exposed a sizing problem.
  `primary_commands()` includes `uv run pytest -x --tb=short -n auto --dist loadfile`, and that
  gate alone took 425 s and 702 s in this session. Both exceed the 570 s default run deadline.
  The new verify and wrapup recipes would therefore always report `timed out` on a long suite,
  which regresses on the old flow of one Bash call per command.
- **Fix.** A new `--deadline-s` flag (default still 570) controls the run deadline. The recipes
  now call `run … --timeout-s 3600 --deadline-s 3600` in the background. A foreground-only host
  is told to drop both flags. Tests: `test_deadline_flag_lifts_and_tightens_the_run_budget`, plus
  render assertions that the run line carries both flags and the word `background`. The
  aggregate surface is still below the pre-task value (claude 357,700).
- **Delta review.** The delta `refs/hm-churn/v1/top-issues-2026-09-verify-fix-pre..post` was
  reviewed by a single focused code-reviewer (see below).

### Fix-delta review result (verify-fix-pre..post)

| Sev | Finding | Resolution |
|---|---|---|
| P1 | The background recipe branched on the host-reported exit status. That status is unreliable (project memory `project_background_exit_code_unreliable`). | Fixed: the recipes now branch on the `"exit"` field of `run`'s JSON line, and a missing line counts as not a pass. |
| P2 | Codex variant: foreground `Bash(...)` with 3600 s caps, and the prose gave it no way to run in the background. | Fixed: the codex snippet keeps the defaults ("Foreground call"). Only the Claude variant lifts the budgets and runs in the background. The render test is now variant-aware. |
| P2 | SPEC S5 and the constraints still described the old 540 s/600 s design. | Fixed: S5 and the constraints table now cover `--deadline-s` and the background recipe. |

**Field validation of the confirm-1 repair.** The first background Check 2 run was stopped
mid-suite by the host (TaskStop). `run` printed `[verify] terminated — the running gate's group was
killed; no marker`, and no pytest, mypy or ruff process was left running.

Aggregate surface after the fix: claude 357,552 and codex 311,672, both below the pre-task values.
