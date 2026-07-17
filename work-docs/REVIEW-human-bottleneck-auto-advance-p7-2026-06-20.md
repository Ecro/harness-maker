---
type: review
task_slug: human-bottleneck-auto-advance
status: APPROVED
created: 2026-06-20
phase: 7
reviewers_invoked: [code-reviewer, code-reviewer, codex]
consensus_method: k-of-3 (2 Claude cross-check + Codex heterogeneous voter)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-20T00:00:00Z
---

# REVIEW — P7 ledger consumers + /hm:health smoke

## 🎯 Round 1 Summary

**Grade: A** (consensus-passed P0 = 0, P1 = 0).

Diff: `autopilot_caps gate-blocked` subcommand + `autopilot_ledger.smoke_check`/`main`
smoke CLI + the partial's gate-stop `gate_blocked` record + `health.md.j2` autopilot smoke
section + 8 snapshots + a new test file. k-of-3: **Codex clean, reviewer-B (templates)
clean.** Only reviewer-A raised findings (single-source → manual-only → Grade A). Both
were correct + low-cost and **voluntarily applied** (prior-phase precedent).

## 🔍 Drift Findings

`drift_verdict: clean`. All files in PLAN P7 scope (ledger consumers + health smoke + test
+ snapshots).

## ✅ Consensus Findings

None — no finding reached cross-reviewer agreement.

## 📝 Manual-Only Findings (reviewer-A, single-source) — applied

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| 1 | **P1** | `smoke_check` degraded predicate was `yaml_level != "gated"` → a typo'd / empty / pre-feature level (e.g. `"off"`, `""`) is treated as ARMED, so an empty ledger raises a false "armed but never fired" alarm. This INVERTS the codebase's canonical clamp-unknown-to-gated fail-safe (`autopilot.effective_level`) — the CLAUDE.md "absent-case = feature black hole" pattern. | **APPLIED** — positive allow-list: `_ARMED_LEVELS = {"auto_safe","full"}`, `degraded = yaml_level in _ARMED_LEVELS and count == 0`. Unknown/garbage → not-armed → never degraded. + `test_smoke_unknown_level_not_degraded`. |
| 2 | P2 | smoke CLI `--level` was a free string (no validation) | **APPLIED** — `choices=("gated","auto_safe","full")` (loud argparse error on a misspelled level; smoke_check also clamps). |

reviewer-A's non-finding notes (no action needed): `_total_entries` is correct (events
partition the lines disjointly, no double-count); the 3-pass file read is negligible for a
PIPE_BUF-capped JSONL; `gate-blocked --stage` is descriptive provenance (no control-flow
impact) so it needs no validation.

## 🤝 Disagreements

None. reviewer-B + Codex independently verified the focus areas reviewer-A flagged
(`_total_entries`, gate-stop ordering, cross-IDE gating) as clean; reviewer-A's P1/P2 were
on the smoke_check predicate, which the other two did not examine (no conflict).

## ⚙️ Verification (post-fix)

- `uv run pytest tests/unit/test_autopilot_ledger_health.py` → 7 passed (added unknown-level).
- `uv run ruff check` + `ruff format --check` → clean. `uv run mypy --strict` → clean.
- Full suite → green. Fix was src-only (no template change → no snapshot impact this round).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 2 (1×P1, 1×P2, voluntary manual-only) | 0 | 0 |

Final grade: **A**
Status: **APPROVED**
human_review_needed: false
