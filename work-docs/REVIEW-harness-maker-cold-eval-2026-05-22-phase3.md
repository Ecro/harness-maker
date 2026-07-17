---
type: review
task_slug: harness-maker-cold-eval
status: in-progress
created: 2026-05-22
phase_scope: "Phase 3 (launch-baseline) only"
reviewers_invoked: []
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: harness-maker-cold-eval
  computed_at: "2026-05-22T04:45:00Z"
  note: "Phase 3 of PLAN-harness-maker-cold-eval. Sole deliverable: docs/observability/launch-baseline.md committed within 24h of v0.22.0 tag (2026-05-22 04:37 UTC) with Day-0 snapshot + 30/60/90-day ISO target dates + retrospect-trigger TODO. PLAN cycle (Phase 1.1-1.5 + Phase 1.2 + Phase 2 + Phase 3) now fully closed."
---

# REVIEW — harness-maker-cold-eval Phase 3 — 2026-05-22

## 🎯 Round 1 Summary

**Grade**: A* (mechanical) — ruff + mypy + Phase 3 exit criteria 3/3 met.
**Status**: APPROVED for wrapup.
**Auto-fix**: not engaged (no consensus-passed findings).

**What shipped (Phase 3 — single sub-phase):**

`docs/observability/launch-baseline.md` (new file, ~70 lines). Captures:
- Day-0 metrics table sourced from 3 reproducible CLI commands (pypistats API, `gh api`, `gh api .../discussions`).
- ISO target dates: Day +30 = 2026-06-21, Day +60 = 2026-07-21, Day +90 = 2026-08-20 (derived from v0.22.0 tag date 2026-05-22).
- Snapshot log table with 4 rows (Day 0 filled, +30/+60/+90 pending).
- Retrospect-trigger TODO at Day +90: two-branch decision tree (≥3× growth → `harness-maker-v0.23-uvx-cta-plan`; otherwise → `harness-maker-personalization-retrospect`).
- Honest caveats: PyPI download noise floor (TestPyPI smoke-installs + bots inflate Day-0); GitHub stars = lagging; Discussions count of 1 is maintainer-opened (not external).

**Day-0 snapshot (numbers locked into baseline.md):**

| Metric | Value | Note |
|---|---|---|
| PyPI weekly downloads | **1,424** | likely noise-inflated (see baseline notes) |
| GitHub stars | **2** | unchanged from RESEARCH cold-eval |
| GitHub forks | 0 | |
| GitHub watchers | 0 | |
| GitHub open issues | 0 | |
| Discussions count | 1 | maintainer-opened, no external |

**Phase D verification:**
- `uv run ruff check src/ tests/` — ✅ (no Python change, but ran for completeness)
- `uv run mypy --strict src/` — ✅
- pytest skipped (docs-only diff)
- Phase 3 exit criteria: `test -f docs/observability/launch-baseline.md` ✅, Day-0 PyPI snapshot present ✅, ISO target dates committed ✅ (3/3 — validator critique #7 revision)

## 🔍 Drift Findings

`drift_verdict.result = clean`. Sole change is `docs/observability/launch-baseline.md` which is exactly the Phase 3 scope. Phase 1 (v0.21.0+v0.21.1) and Phase 2 (v0.22.0) already shipped — full PLAN cycle now closed.

## ✅ Consensus Findings / ⚠️ Weak Consensus / 🤝 Disagreements

None — single-file docs-only addition. Reviewer pipeline not engaged for the same reason as the prior 3 wrapup-phase REVIEWs in this PLAN cycle (no semantic code paths to review; mypy/ruff already green; baseline is a static-data artifact whose accuracy depends on the CLI commands documented inside it).

## 📝 Manual-Only Findings

### M1 — Day-0 PyPI 1,424 weekly is suspicious-high for a 2-star project
- **Severity**: information (not a defect)
- **Issue**: PyPI weekly downloads of 1,424 for a project at 2 GitHub stars is anomalously high. Plausible inflation sources: TestPyPI smoke-installs from `release.yml` (publish-testpypi job runs on every tag — we've had 4 tags this week: v0.20.2, v0.21.0, v0.21.1, v0.22.0); maintainer's own dev installs across worktrees; bots that crawl new PyPI uploads.
- **Mitigation**: baseline.md "Notes" section documents this honestly. Day +30 trend interpretation: a flat curve at ~1,400/week throughout means effectively "no organic growth" regardless of the absolute number. The 3× threshold (4,272/week) should be read as *sustained* across multiple Day windows, not a one-day spike. ADR-008 retrospect at Day +90 will surface whether this metric choice was the right one.
- **Source**: `pypistats.org/api/packages/harness-maker/recent`.

### M2 — "100% local telemetry" claim still holds
- **Severity**: information
- **Issue**: All 3 Day-0 measurement commands query *public* GitHub + PyPI endpoints (not the harness's internal `.claude/observability/*` files). The "100% local telemetry" PRIVACY commitment is intact. baseline.md notes explicitly: "all signals are publicly observable."

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A* (mechanical) | —             | 0 | —   |

Final grade: **A\* (mechanical)** — Phase 3 exit criteria 3/3 met, drift clean, no consensus findings.
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: **false**

**Wrapup hand-off note**: this is the *closing* REVIEW for the cold-eval cycle. Wrapup commit should mark PLAN-harness-maker-cold-eval `status: complete` (all phases done — Phase 1 in v0.21.0+v0.21.1, Phase 2 in v0.22.0, Phase 3 in this turn). Version bump v0.22.0 → **v0.22.1** (patch, docs-only). The 4 dangling `.claude/.hm-finalize-stash-*` ref files (cumulative from 5/21 + 5/22 × 3) are still present — surface to the user as the final cleanup item but don't block wrapup.
