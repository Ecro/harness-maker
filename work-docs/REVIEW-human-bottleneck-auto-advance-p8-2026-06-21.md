---
type: review
task_slug: human-bottleneck-auto-advance
status: APPROVED
created: 2026-06-21
phase: 8
reviewers_invoked: [code-reviewer, code-reviewer, codex]
consensus_method: k-of-3 (2 Claude cross-check + Codex heterogeneous voter)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-21T00:00:00Z
---

# REVIEW — P8 e2e + docs + timestamp fix (autonomy FINAL phase, version bump deferred)

## 🎯 Round 1 Summary

**Grade: A** (consensus-passed P0 = 0, P1 = 0).

Diff: `tests/e2e/test_autopilot_chain_e2e.py` (mechanical full-pipeline chain) + the ONE
functional change it caught (`_utc_now_iso` second→microsecond isoformat) + README autopilot
section + MANUAL_CHECKLIST cross-IDE caveat. k-of-3: all three reviewers verified the
functional change is **safe** and the e2e is **sound**; only single-source P2/P3 doc/comment
accuracy items — all voluntarily fixed.

## 🔍 Drift Findings

`drift_verdict: clean`. All in PLAN P8 scope (e2e + docs + the timestamp fix the e2e
surfaced). The **5-file version bump is intentionally deferred** to a coordinated 0.31.0
release (user decision; the concurrent worktree-concurrency feature has since landed FINAL).
This is a documented partial, not a scope miss.

## ✅ Consensus Findings

None — no finding reached cross-reviewer agreement on the same defect. (All three INDEPENDENTLY
confirmed the `_utc_now_iso` fix safe + `_parse_iso` backward-compatible with legacy `Z` rows +
the e2e deterministic — a strong agreeing signal, just not a defect.)

## 📝 Manual-Only Findings (single-source) — all applied

| # | Src | Sev | Finding | Disposition |
|---|-----|-----|---------|-------------|
| 1 | Codex | P3 | README "Cursor/Codex renders stay gated (no auto-invoke branch)" overstates — accurate for Codex (structural exclusion) but Cursor shares the `.claude` command file (block present, runtime no-op). Contradicts the new MANUAL_CHECKLIST + impl. | **APPLIED** — reworded: "excluded from the Codex render entirely, and a runtime no-op under Cursor (needs the Claude-only Skill tool + marker)." |
| 2 | reviewer-A | P2 | `count_events` docstring still claimed ledger ts is the old `...SSZ` "DIFFERENT shape" — stale after the `_utc_now_iso` fix (both isoformat now; the real parse-not-bytecompare reason is legacy `Z` rows on disk). | **APPLIED** — docstring updated to the post-fix rationale (legacy-Z back-compat). |
| 3 | reviewer-B | P2 | README "opt in with `harness-maker autopilot on`" — `on` arms `auto_safe` by default (cli.py); the prose implied `on` keeps `gated`/needs separate yaml. | **APPLIED** — "arms `auto_safe` by default (pass `--level full` for the wider policy)." |
| 4 | reviewer-B | P2 | README named `step_cap`/`time_cap_min` without their defaults (20/60) — user can't predict the halt point. | **APPLIED** — added "(default 20)" / "(default 60)". |
| 5 | reviewer-A | P2 | e2e step_cap test's determinism rests on an undocumented "step_cap fires before time_cap" invariant. | **APPLIED** — added a comment explaining the 600-min time cap guarantees the step cap wins regardless of real elapsed time. |

## 🤝 Disagreements

None. The reviewers split the surface (timestamp/e2e vs docs); Codex independently flagged the
same cross-IDE README inaccuracy reviewer-B's MANUAL_CHECKLIST cross-check implied. No conflict.

## ⚙️ Verification (post-fix)

- `uv run pytest tests/e2e/test_autopilot_chain_e2e.py` → 2 passed.
- `uv run ruff check` + `mypy --strict` (changed files) → clean.
- All fixes are doc/comment-only (no logic change) → no snapshot impact, full suite already green
  on the combined base (c2b7a1f + P8).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 5 (doc/comment, all manual-only) | 0 | 0 |

Final grade: **A**
Status: **APPROVED**
human_review_needed: false

> **Release note:** the autonomy feature is now code/docs/e2e COMPLETE (P0–P8). The only
> remaining item is the **5-file version bump + CHANGELOG release-sectioning**, deferred to a
> coordinated 0.31.0 release (now unblocked — worktree-concurrency also landed). That is a
> user-initiated release step (CLAUDE.md release procedure: 5-file sync → tag push → workflow),
> NOT part of this review/wrapup.
