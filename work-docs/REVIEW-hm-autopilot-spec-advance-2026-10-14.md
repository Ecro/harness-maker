---
type: review
task_slug: hm-autopilot-spec-advance
status: APPROVED
created: 2026-10-14
reviewers_invoked: [code-review]
consensus_method: single
review_base: d48bdc0b6b49aa8f5db4512d2a841e827d23d1dc
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hm-autopilot-spec-advance
  computed_at: 2026-10-14T23:30:00Z
---

# REVIEW — hm-autopilot-spec-advance

Light lane, run on the session branch with no per-task worktree. The reviewed diff is
`review_base..working tree`, excluding regenerated outputs (snapshots, `autopilot_gate_golden.json`,
`surface_baseline.json`, the `_LOOP_ON_RECAPTURES` hashes).

**Procedure deviations, so nobody assumes a step ran that did not:**
- One review dispatch, one round. This session had no Agent tool, so the `code-reviewer` agent could
  not be dispatched. The `code-review` skill (forked execution, medium effort) reviewed the diff in its
  place. There was no lens fan-out, no grade gate, no confirmation pass and no second opinion.
- The SPEC is not approved. Approval belongs to the DRI (`hm spec_machine approve` was not run).

## Findings and dispositions

| # | Sev | Finding | Disposition |
|---|---|---|---|
| 1 | P1 | Step 5 said "at `auto_full` autopilot advances" without a condition. `boundary` still halts at `auto_full` on caps, `narrow_end`, `merge_gate`, `bad_slug`, `objective_gate`, a derived `blocked` or an absent flag | **Fixed.** The text now reads "at `auto_full` the boundary answers it, and its `proceed: true` advances WITHOUT an approval". The test pins the `proceed: true` wording |
| 2 | P2 | Other stop cues remain: the Stage terminal line, the banner's "STOP — user-initiated", and Outputs' "`approved` (ready for `/hm:execute`)" | **Declined (scope).** The Stage terminal line already says `proceed: true` supersedes it. The banner prints only when the stage stops. The bench runs quoted Step 5 and the directive, and both are fixed. Follow-up if a re-bench still shows stops |
| 3 | P2 | AC-001's predicate compared the whole Step 5 across arms, but the approve-call fence differs by design. It also omitted the wrapup clause | **Fixed.** It now compares the tail after "Otherwise leave" and asserts the wrapup clause, matching the test |
| 4 | P3 | `pending_test: true` on ACs whose tests exist | **Declined.** This matches the repo convention (SPEC-hm-light-lane-s2b ships the same way). `mark-tested` happens at wrapup |
| 5 | P2 | AC-002's level-invariance test also passes on the old template, and it skipped `ask` | **Partly fixed.** `ask` was added. AC-002 guards the AC-005 gated-delta contract, not the fix itself; AC-001 is the one that catches a revert |
| 6 | P2 | The Codex advance partial's "do not bypass an explicit user-decision requirement" could still read as a reason to stop | **Declined (scope).** The bench was Claude-only. The directive's new sentence reaches both runtimes, and "Mandatory approvals inside the next skill" refers to the next skill, not this SPEC |
| 7 | P3 | The directive's `plan` clause is unreachable (`_JUDGMENT_GATED_STAGES` is `{review, spec}`) | **Declined.** It predates this task and is out of scope |
| 8 | P3 | `render_sha` was written through `build_baseline()` because `main()` refused on a stale local `main` | **Declined.** d48bdc0 is `origin/main` itself. The reachability test already failed in this environment before the change. Recorded in the BASELINE-DELTA |
| 9 | P3 | The CHANGELOG said "Re-render with `/hm:make`" | **Fixed.** It now says `/harness-maker:make` |

## Verification

- New tests: `tests/render/test_render_spec_autopilot_advance.py` (2) and
  `tests/unit/test_autopilot_spec_advance_directive.py` (1). They were RED before the fix (the
  level-invariance guard was green by design) and are GREEN after.
- Full suite, ruff, ruff format and mypy --strict: see the commit's test run. The only failures are
  the known environment failures.
