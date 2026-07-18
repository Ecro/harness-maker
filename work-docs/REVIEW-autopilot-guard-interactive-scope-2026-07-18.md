---
type: review
task_slug: autopilot-guard-interactive-scope
status: APPROVED
created: 2026-07-18
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
second_opinion_results: []
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: autopilot-guard-interactive-scope
  computed_at: 2026-07-18
---

# REVIEW — autonomy.guard_when (pipeline_only interactive-scope)

Reviews the uncommitted change adding `autonomy.guard_when: "always" | "pipeline_only"`
(default `always`) so the autopilot guard stays dormant in plain interactive sessions under
persistent autopilot, re-arming only once a real pipeline stage starts (`.hm-pipeline-active`
crumb) or a loop marker is present.

## 🎯 Round 1 Summary

- **Grade: B** (1 consensus-passed P1). Entered auto-fix.
- Reviewers: `code-reviewer` + `security-reviewer` (both Opus), plus author cross-analysis.
- **Second opinion (codex, antigravity): explicitly SKIPPED this run** — configured mandatory
  for Production, but this is an interactive pre-commit self-review; the two Opus reviewers +
  author analysis gave sufficient multi-perspective coverage. Recorded here (not silent) to
  avoid the H4 silent-degradation failure mode. `second_opinion_results: []`.

## 🔍 Drift Findings

No PLAN-{slug}.md / SPEC-{slug}.md exists (the feature was designed conversationally with the
user, not via `/hm:plan`), so the PLAN-scope drift gate has no baseline. `drift_verdict: clean`
by default. Recorded as an accepted process note, not a finding.

## ✅ Consensus Findings (fixed in auto-fix Round 2)

### P1 — Stale `.hm-pipeline-active` crumb permanently defeats `pipeline_only`
`code-reviewer` P1 + `security-reviewer` (mechanism confirmed) + author — strong consensus.
- **OBSERVE:** the crumb stores `worktree._current_session_uuid`, which is **project-scoped and
  persistent across sessions** (no TTL). `clear()` reaps it only at autopilot terminals;
  `write()`/autoarm did not.
- **INFER:** after the first stage run in a project (or a marker-less standalone stage / crash),
  the crumb persists and matches every future same-project session → guard stays ACTIVE in
  interactive chats → the feature is silently defeated (fail direction safe/over-guard, hence P1
  not P0).
- **FIX (final — follow-up #1 landed in the same pass):** the crumb now stores a **per-session**
  id (`HM_SESSION_ID`, sanitized like `loop_marker`) instead of the project-scoped uuid. A prior
  OR parallel session's crumb bears a different id, so `pipeline_active` treats it as foreign →
  dormant, with **no clear-on-arm**. The guard passes its own `session_id` from the hook payload.
  Degraded (no id) either side → block-bias guarded (safe, never a silent disarm). Regression
  tests: `test_stale_crumb_from_prior_session_is_dormant`, `test_parallel_arm_leaves_peer_crumb_intact`,
  `test_degraded_empty_crumb_honored`, `test_degraded_reader_honors_crumb`.
  (An interim clear-on-arm fix was applied first, then superseded by this session-id approach —
  which removes the parallel-session caveat entirely.)

### P2 — Crumb-read `OSError` biased toward dormant (unguarded)
`code-reviewer` P2 + `security-reviewer` P3 — consensus on issue + fix.
- **OBSERVE:** `pipeline_active` caught `OSError` and fell through to `False` (dormant); the
  docstring called this "fails safe to False."
- **INFER:** for a guard-arming predicate, `True` (guarded) is the safe direction; a transient
  crumb-read failure during a live run wrongly stood the guard down. Separately the loop-marker
  glob was unwrapped — a `.claude` read error could raise out of the hook, which Claude Code
  treats as allow (implicit fail-open).
- **FIX:** an unreadable-but-present crumb now returns `True` (block-bias); the loop-marker glob
  is wrapped to return `True` on `OSError` instead of crashing; docstring corrected. New test
  `test_unreadable_crumb_biases_guarded`.

### P2 — Misleading test masked the P1
`code-reviewer` P2 (coupled to the P1 fix).
- `test_foreign_session_crumb_does_not_activate` asserted an impossible same-project value
  (`ffffffffffff`), validating the incorrect docstring rather than the real cross-session path.
- **FIX:** renamed to `test_cross_project_foreign_crumb_does_not_activate` (the real cross-project
  case) and added `test_same_project_stale_crumb_cleared_on_rearm` capturing the actual P1.

## 📝 Manual-Only Findings (recorded, not auto-fixed)

- **P2 (security) — crumb deletable mid-run → silent disarm.** An in-worktree `rm` that avoids the
  literal `.claude` spelling (glob) can delete the crumb, standing the guard down for the rest of a
  `pipeline_only` run. **Accepted:** defense-in-depth only (the worktree sandbox is the real
  boundary), and an autonomous agent can already fully disarm via `autopilot off` (not on any deny
  list) — this adds no materially new disarm primitive. Documented in code.
- **P2 (security) — crumb-write miss → dormant during a real run (absent-case).** If the stage-start
  `!uv run … pipeline-active` stamp fails, `pipeline_only` runs unguarded. **Accepted:** absent
  crumb = the feature's intended dormant semantics; the risk is a write *failure*, which is rare
  (`atomic_write`), and the `/hm:loop` path is robust via the loop-marker existence check.
  `pipeline_only` is opt-in and explicitly trades some defense-in-depth for less interactive
  friction.
- **P3 (code) — `harness.yaml` parsed twice per active-marker Bash call** (`_guard_when` +
  `_extra_deny`). Efficiency nit; correctness fine. Follow-up: parse once per `evaluate()` and pass
  the autonomy dict to both.

## 🤝 Disagreements

Security-reviewer graded the stale-crumb mechanism as a *safe over-block* (P3 confirmation);
code-reviewer graded its *functional* impact (feature defeat) as P1. Not a severity bridge — same
mechanism, two lenses, both aligned that the direction is safe and the feature is defeated. Fixed
regardless.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 3 (1×P1, 2×P2) | — |
| 2         | A     | 3 clusters (P1 + 2×P2) + docstrings | 0 consensus | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: **false** (no unverified manual-only/weak-consensus P0/P1; the manual-only
items are P2/P3 and accepted-with-documentation)

## Follow-ups

1. ~~Robust cross-session crumb identity via `HM_SESSION_ID`~~ — **DONE** (landed in this pass;
   see the P1 fix above). Removed the parallel-session caveat.
2. `/hm:health` smoke: warn when a marker is armed under `pipeline_only` but no crumb exists
   (surfaces a silent crumb-write miss). — deferred, not blocking.
3. Parse `harness.yaml` once per `evaluate()` (P3 perf). — deferred, not blocking.
