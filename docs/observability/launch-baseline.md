# Launch Baseline — Day-0 Snapshot (v0.22.0)

> PLAN-harness-maker-cold-eval Phase 3 deliverable. ADR-008 primary metric =
> PyPI weekly downloads; secondary = GitHub stars + Discussions activity.
> Locked at v0.22.0 tag push (commit `067c748`).
> No opt-in telemetry; all signals are publicly observable.

## Day-0 (2026-05-22, v0.22.0 release)

| Metric | Source | Value |
|---|---|---|
| **PyPI weekly downloads** | `pypistats.org/api/packages/harness-maker/recent` | **1,424** |
| PyPI last-day downloads | same | 304 |
| PyPI last-month downloads | same | 1,424 (package <30 days old — month = week) |
| **GitHub stars** | `gh api repos/Ecro/harness-maker` | **2** |
| GitHub forks | same | 0 |
| GitHub watchers (subscribers) | same | 0 |
| GitHub open issues | same | 0 |
| GitHub Discussions count | `gh api .../discussions` | 1 |
| GitHub Discussions enabled | repo settings | true |
| Repo public-since | `created_at` | 2026-05-03 (Day 19 of public life) |
| First PyPI publish | release.yml history | 2026-05-21 (v0.15.3 per CLAUDE.md §PyPI 노출) |
| v0.22.0 tag commit | `git rev-parse v0.22.0` | `067c748` |

### Reproducibility commands
The exact CLI invocations that produced the table above (run from main, no auth needed for PyPI; `gh` uses your existing GitHub auth):

```bash
# PyPI weekly + last-day + last-month
curl -s https://pypistats.org/api/packages/harness-maker/recent | jq .

# GitHub stars / forks / watchers / open_issues / has_discussions / created_at
gh api repos/Ecro/harness-maker --jq \
  '{stars: .stargazers_count, forks: .forks_count, watchers: .subscribers_count, open_issues: .open_issues_count, has_discussions: .has_discussions, created_at: .created_at}'

# Discussions count
gh api repos/Ecro/harness-maker/discussions --jq 'length'
```

## Target dates — 30 / 60 / 90 day snapshots

| Checkpoint | ISO date | Action |
|---|---|---|
| Day +30 | **2026-06-21** | Re-run the 3 reproducibility commands above; append a row to the table below; record the delta vs Day-0. |
| Day +60 | **2026-07-21** | Same. |
| Day +90 | **2026-08-20** | Same. Then execute the retrospect-trigger TODO below. |

### Snapshot log (filled in as dates arrive)

| Date | PyPI weekly | GitHub stars | Discussions | Notes |
|---|---|---|---|---|
| 2026-05-22 (Day 0) | 1,424 | 2 | 1 | baseline |
| 2026-06-21 (Day 30) | _pending_ | _pending_ | _pending_ | |
| 2026-07-21 (Day 60) | _pending_ | _pending_ | _pending_ | |
| 2026-08-20 (Day 90) | _pending_ | _pending_ | _pending_ | |

## Retrospect-trigger TODO (Day +90)

When all 3 target dates above have been logged with snapshots, kick off
one of two follow-up plans:

- **If PyPI weekly downloads have grown ≥3× from Day-0 baseline (≥4,272/week)**
  → kick off plan `harness-maker-v0.23-uvx-cta-plan`. The personalization
  headline is landing; promote the `uvx harness-maker profile .` no-install
  wedge (RESEARCH-harness-maker-cold-eval §Wedge Reality Check, Approach C)
  to the README hero as the 30-second proof artifact for non-installers.

- **Otherwise** (growth <3×) → kick off plan
  `harness-maker-personalization-retrospect`. ADR-008's PyPI-downloads-as-
  primary-metric choice deserves re-examination: the noise floor includes
  CI mirrors, curiosity installs, and bot traffic. A flat 90-day curve is
  ambiguous — could be "headline didn't land" OR "metric was wrong choice."
  The retrospect plan triages: re-measure with a stricter proxy (unique
  `/hm:make` completion telemetry — would require breaking the "100% local"
  privacy commitment, so this is the harder path), or re-frame success
  around qualitative signals (Discussions activity quality, external
  contributor PRs, awesome-list inclusion velocity).

## Notes (read before treating this baseline as gospel)

- **PyPI downloads noise**: 1,424/week on Day 0 for a project at 2 stars is
  surprising-high. Possible noise sources: TestPyPI smoke-install during
  release.yml runs (publish-testpypi job runs on every tag); maintainer's
  own dev installs across worktrees; bots crawling new PyPI uploads.
  Day +30 trend matters more than absolute Day 0 — if the curve is flat at
  ~1,400/week throughout, that's effectively "no organic growth" regardless
  of the headline number. Interpret the 3× threshold as ≥4,272/week of
  *sustained* level across multiple Day windows, not a one-day spike.
- **GitHub stars** = lagging signal. Stars come after PyPI usage (someone
  installs → uses → returns → stars). A 30-day window may not capture this
  loop.
- **Discussions count = 1** on Day 0. That is the discussion the maintainer
  opened. External contributor discussions are the signal worth tracking;
  none yet.
- This baseline was committed within 24h of the v0.22.0 tag, per PLAN
  Phase 3 exit criterion (validator critique #7 revision: must be a real
  artifact committed to main, not a calendar reminder).
