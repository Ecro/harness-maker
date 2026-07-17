---
type: review
task_slug: human-bottleneck-auto-advance
status: APPROVED
created: 2026-06-20
phase: 5
reviewers_invoked: [code-reviewer, code-reviewer, codex]
consensus_method: k-of-3 (2 Claude cross-check + Codex heterogeneous voter)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-20T00:00:00Z
---

# REVIEW — P5 runaway caps + kill switch + minimal ledger (human-bottleneck-auto-advance)

## 🎯 Round 1 Summary

**Grade: A** (consensus-passed P0 = 0, P1 = 0).

Diff under review (3 new files, +340): `src/harness_maker/autopilot_caps.py`,
`src/harness_maker/autopilot_ledger.py`, `tests/unit/test_autopilot_caps.py`.

k-of-3: 2 Claude code-reviewers + Codex. **No finding reached cross-reviewer
consensus at P0/P1** (the two P1s were each single-source → `manual-only` → grade A).
Per the established precedent in this feature, the correct single-source findings were
**voluntarily applied** because both P1s are real and one defeats the ledger's core
ADR-009 contract — shipping them would be negligent even at a rubric "A".

## 🔍 Drift Findings

`drift_verdict: clean`. The diff matches PLAN P5 scope. Note: `autopilot_ledger.py` is
nominally P7 ("ledger") territory, but P5's own exit criterion requires *"each cap-halt
writes a `halted_cap` ledger event"*, so the **minimal** ledger writer is in-scope for
P5; P7 extends it with the `advanced`/`gate_blocked` call-sites + `/hm:health` smoke.
Not a violation — documented scope overlap mandated by the exit criterion.

## ✅ Consensus Findings (2-of-3)

| Severity | File:line | Finding | Disposition |
|---|---|---|---|
| P2/P3 | autopilot_caps.py:63 | `created_at` re-parsed in `evaluate_boundary`, duplicating `active_marker`'s parse — invariant lives in a comment, not a contract | **ACCEPTED as-is** — both reviewers explicitly called it acceptable given the comment; threading the parsed datetime out of `active_marker` expands scope into the P2 marker module. Documented coupling. Does NOT affect grade (P2/P3). |

## 📝 Manual-Only Findings (single-source — applied per precedent)

| # | Source | Sev | Finding | Disposition |
|---|--------|-----|---------|-------------|
| 1 | **Codex** | P1 | `append_event`: `record.update(fields)` ran AFTER setting `event`, so `fields={"event":"pass"}` overwrites the validated event → an iter_receipts.Verdict literal reaches disk, defeating ADR-009 at the append boundary | **APPLIED** — merge `fields` FIRST, then set authoritative `ts`+`event` LAST so a caller's reserved key can never win. + `test_fields_cannot_overwrite_event`. (Both Claude reviewers missed this — the Codex third vote earned its seat.) |
| 2 | code-reviewer B | P1 | `ledger_path` dropped the absolute-`observability_dir` containment guard that the mirrored `codex_ledger.emit` carries → an absolute dir writes the ledger outside `project_root` | **APPLIED** — mirror codex_ledger: resolve + `is_relative_to(project_root)` or raise. + `test_absolute_observability_dir_{escape_raises,within_root_ok}`. |
| 3 | code-reviewer B | P2 | `EVENTS` disjointness from `Verdict` + `LedgerEvent`↔`EVENTS` consistency were test-only, not structural | **APPLIED** — `EVENTS = frozenset(get_args(LedgerEvent))` (derived, single source) + a module-level `assert EVENTS.isdisjoint(get_args(Verdict))` makes ADR-009 an import-time invariant. |
| 4 | code-reviewer A | P2 | No test pinned the time_cap `>=` boundary at exactly the cap | **APPLIED** — `test_time_cap_halts_at_exact_cap`. |
| 5 | code-reviewer A | P3 | step-vs-time cap precedence untested | **APPLIED** — `test_step_cap_wins_over_time_cap`. |
| 6 | code-reviewer A | P3 | `record_cap_halt` accepted a naive datetime → tz-ambiguous ledger ts | **APPLIED** — normalize naive `now` to UTC before isoformat. |

## 🤝 Disagreements

- **autopilot_caps.py:63 re-parse**: reviewer A rated P2, reviewer B rated P3. Both
  CONCLUDE identically ("latent coupling, invariant in a comment"). Resolved as
  non-blocking; accepted as-is (lower-bound disposition).

## ⚙️ Verification (post-fix)

- `uv run pytest tests/unit/test_autopilot_caps.py` → 18 passed (13 original + 5 added).
- `uv run ruff check` + `ruff format --check` (3 files) → clean.
- `uv run mypy --strict` (2 src modules) → clean.
- Full suite → green (re-run after `autopilot_ledger` gained the `iter_receipts` import).
- **No template change → no snapshot impact.**

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 0 consensus P0/P1 | — |
| (voluntary)| A    | 6 (2×P1, 2×P2, 2×P3) | 0 | 0 |

Final grade: **A**
Status: **APPROVED**
human_review_needed: false
