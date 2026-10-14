---
type: review
task_slug: hm-light-lane-bench
status: APPROVED
created: 2026-10-14
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
review_base: e9b619847a097e9a688832a6dc44316e6cb2a393
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hm-light-lane-bench
  computed_at: 2026-10-14T17:30:00Z
---

# REVIEW — hm-light-lane-bench (stage 4 runner of HM-LIGHT-LANE)

Run on the PR branch. Lane `full`, preset Production. Diff `review_base..d652803` for round 1,
`d652803..bd59777` for the confirmation pass.

**Procedure deviations, stated so nobody infers a step that did not run:**
- Round 1 was two dispatches (core lenses; security + concurrency + tests lenses), not four.
- Pass 2 was the main loop checking each finding against the code, not a second dispatch.
- The confirmation pass was one `code-reviewer` dispatch with no Bash; it read the tree and did
  not execute tests. It returned FAIL (one P1), so a second fix round followed
  (`bd59777..1774197`), verified by the full test suite rather than a further dispatch.
- The cross-model second opinion was skipped (`codex` CLI not installed; warn and proceed).
- No live run: the runner has driven only the fake `claude`. The first live run starts with a
  canary cell (SPEC Open Questions) to check that user-level settings stay out of both arms.

## Round 1

30 findings: P1 6 (Ctrl-C does not stop paid agents; a lost cost recorded as $0; agent env and
HOME unscrubbed; user `~/.claude` loaded; hidden tests readable and writable in the checkout;
graded hidden copies reachable from later runs), P2 15, P3 9. All fixed in `bd59777`; none
declined. Table in that commit's body.

**Incident during the fix round:** a RED-proof test run against the old runner (no lock, no
`--claude-bin`) launched the real `claude -p` once for about 6 minutes before it was killed; the
spend was not measured. Every test now puts a failing `claude` stub first on PATH (`_no_real_claude`,
and `_env()` for the module-scoped fixture).

## Confirmation pass

FAIL: N1 (P1) — the recorded `--value` and the final metric line used the rounded CLI ratio while
the verdict used `max(CLI, transcript)`, so the ledger could read met on a missed run. N2–N9 (P2–P3):
post-agent crash rows lost their cost, transcript root ignored `CLAUDE_CONFIG_DIR`, a spawn/kill
race, surviving grandchildren after a normal exit, the module fixture outside the PATH stub, a
vacuous exit-code assertion, `runner_hash` missing `pass_env` and the CLI version, untracked files
outside the harness stamp, budget-capped runs counted silently. All fixed in `1774197`, each with
a test.

## Grade

**A** after the second fix round: no open P0/P1, full suite green except the eight known
environment failures. Status APPROVED.
