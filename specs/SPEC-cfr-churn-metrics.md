---
type: spec
task_slug: cfr-churn-metrics
status: approved
created: 2026-07-03
tier: 2
tags:
- harness-maker
- spec
- python
- git-analytics
- dora-metrics
- observability
test_framework: pytest
research_doc: "[[RESEARCH-cfr-churn-metrics]]"
summary: "Opt-in local git analytics: rolling-window CFR + 14-day blame-survival churn, ledgered snapshots, /hm:metrics surface"
---

# SPEC: cfr-churn-metrics

## 🎯 Intent

AI-assisted development shifts quality failure into two lagging signals: releases that need remediation (CFR) and merged code that gets rewritten shortly after landing (post-merge churn — the "passed review, then thrown away" AI-slop signal). harness-maker users currently have no way to see either trend for their own project. This feature computes both metrics purely from local git history (no network, no CI/CD integration), records snapshots so the trend is visible over time, and lets the LLM interpret the trend against the project's own baseline and propose improvements. Accumulated local data is a future input for improving harness-maker itself (via the existing opt-in feedback transport — out of scope here).

## 🌅 Outcomes

- A user with `delivery_metrics.enabled: true` can run `/hm:metrics` and see: the rolling 4-week CFR (raw counts `failed/total`, never percentage alone), the 14-day post-merge churn trend, the delta against the project's own baseline, and an LLM-generated interpretation with concrete improvement suggestions.
- `/hm:health` shows a 1-2 line delivery-metrics narrative summary when the feature is enabled and data exists. Readiness score is **unchanged** (no new dimension).
- Projects without release tags still get CFR via the task-land fallback denominator; projects with neither get an explicit "not applicable" with the reason — never a silent 0%.
- Trend numbers are stable across repeated runs on unchanged history (LLM adjudications are ledgered and reused).
- Users with the feature disabled (the default) observe zero behavior change and zero file writes.

## 📋 In-Scope Scenarios

### AC-001: CFR computed from release tags over rolling window on golden fixture

**Given** a fixture repo with 3 release tags in the rolling 28-day window, one of which is followed by a revert/hotfix linked to it
**When** CFR is computed for the window
**Then** the result is `failed=1, total=3` with release unit `tag`
**And** the raw counts are carried in the result object (not only a ratio)

### AC-002: Task-land fallback supplies CFR denominator when no tags exist

**Given** a fixture repo with no release tags but with squash-land merges to the default branch inside the window
**When** CFR is computed
**Then** the release unit reported is `task-land` and the denominator equals the number of lands in the window

### AC-003: Absent-case yields explicit not-applicable, never silent zero

**Given** a fixture repo with neither release tags nor lands inside the window
**When** CFR is computed
**Then** the result status is `not_applicable` with a human-readable reason
**And** no snapshot row claiming CFR=0% is written

### AC-004: Churn counts LOC rewritten within 14 days, excluding whitespace-only changes

**Given** a fixture repo where commit A's lines are partially rewritten by commit B 10 days later, partially reformatted (whitespace-only) by commit C, and partially still intact
**When** churn is computed with blame-survival (`git blame -w -M -C` semantics)
**Then** only the genuinely rewritten LOC count as churned; whitespace-only reformatting and surviving lines do not

### AC-005: Metrics invariant to commits outside the measurement window

**Given** any synthetic git history with a fixed measurement window W
**When** arbitrary commits strictly older than the start of W are appended to the history
**Then** `compute_cfr` and `compute_churn` results for W are unchanged

### AC-006: CFR bounds hold and fix-only releases are excluded from denominator

**Given** any synthetic release history mixing normal, failed, and fix-only releases
**When** CFR is computed over the window
**Then** `0 <= failed <= total` always holds
**And** releases classified as fix-only remediation never count in the denominator
**And** at most one failure is attributed per release

### AC-007: Snapshot ledger appends and adjudication verdicts are reused

**Given** an enabled project where a metrics run required an LLM adjudication for an ambiguous `fix:` commit, recorded to the ledger
**When** metrics run a second time on unchanged history
**Then** a new snapshot row is appended to `.claude/observability/delivery-metrics.jsonl`
**And** the previously adjudicated commit is not re-judged (zero new adjudication requests)

### AC-008: Config defaults off and legacy harness.yaml loads without key

**Given** a `DeliveryMetricsConfig` constructed with no arguments, and a legacy `harness.yaml` lacking the `delivery_metrics:` key
**When** the config is instantiated / the legacy file is loaded
**Then** `enabled` is `False` in both cases and loading raises no error

### AC-009: Disabled feature performs zero writes

**Given** a project with `delivery_metrics.enabled: false` (or the key absent)
**When** any `/hm:` stage or health run executes
**Then** no `delivery-metrics.jsonl` ledger file is created and no delivery-metrics computation is invoked

### AC-010: Rendered command surfaces trend, raw counts, and LLM interpretation

**Given** a harness rendered with `delivery_metrics.enabled: true`
**When** the `/hm:metrics` command file and `/hm:health` command file are rendered
**Then** the metrics command contains the trend-display, raw-counts (`failed/total`), baseline-delta, and LLM-interpretation instruction blocks, and the health command contains the delivery-metrics narrative block
**And** rendering with `enabled: false` omits the `/hm:metrics` command entirely

## 🚫 Non-Goals

- **No CI/CD or GitHub API integration** — pure local git analysis (no-network obligation, PLAN-oss-readiness-audit ADR-005).
- **No cross-project aggregation in v1** — per-project local ledger only; future transport is the existing opt-in feedback module.
- **No readiness score dimension** — Goodhart guard: metrics inform reflection, never a score penalty. `/hm:health` gets narrative only.
- **No stage-blocking gate** — bad CFR/churn never blocks `/hm:` stages.
- **No force-push / history-rewrite recovery** — rewritten history is measured as-is.
- **No non-git VCS support.**

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | project default (CLAUDE.md locked) |
| Language / typing | Python 3.12+, `mypy --strict`, `ruff` | project default |
| Network | zero network I/O | `tests/unit/test_no_network.py` positive obligation |
| Subprocess | args-list, `timeout` mandatory, no `shell=True` | CLAUDE.md 외부 명령 호출 |
| Performance | single metrics run ≤ 30s on a ≤2000-commit repo; per-run blame file cap 500 with loud "N files skipped" line | blame-survival cost bound; no silent caps |
| Churn algorithm | blame-survival single tier (`-w -M -C` semantics), 14-day window | interview R1; whitespace/move noise defense |
| CFR window | rolling 28 days, own-baseline comparison | user definition; DORA own-baseline guidance |
| Storage | `.claude/observability/delivery-metrics.jsonl`, O_APPEND atomic line pattern | inherits churn-prefix gitignore + dirt-filter forgiveness |
| Config | `delivery_metrics:` block, `enabled: false` default, strict Pydantic, wired into `HarnessConfig` + interview mirror | feedback-module precedent; absent-case = silent off |
| Determinism | LLM adjudications ledgered and reused; Python computation pure given history | interview R2; run-to-run stability |

## ✅ Verification Criteria

| Scenario | Verification mode | Test reference |
|---|---|---|
| AC-001 | unit (golden fixture repo) | pending — `tests/unit/test_delivery_metrics.py::test_cfr_tagged_golden` |
| AC-002 | unit (golden fixture repo) | pending — `test_cfr_task_land_fallback` |
| AC-003 | unit (golden fixture repo) | pending — `test_cfr_absent_case_not_applicable` |
| AC-004 | unit (golden fixture repo) | pending — `test_churn_blame_survival_excludes_whitespace` |
| AC-005 | property (metamorphic) | pending — `test_property_window_outside_invariance` |
| AC-006 | property (invariant) | pending — `test_property_cfr_bounds_and_fix_only_exclusion` |
| AC-007 | integration (ledger + adjudication reuse) | pending — `test_ledger_append_and_adjudication_reuse` |
| AC-008 | unit (config contract) | pending — `test_config_default_off_and_legacy_load` |
| AC-009 | integration (zero side effects) | pending — `test_disabled_zero_writes` |
| AC-010 | unit (render-grep snapshot) | pending — `test_render_metrics_command_blocks` |

## ❓ Open Questions

None blocking — interview resolved all SPEC-scope items.

Plan-scope handoffs (feed `/hm:plan` ADRs; how-decisions, not what-decisions):
- Default release-tag pattern value (`v*` proposed) and its config field shape.
- Ledger row schema field list (snapshot vs adjudication event types).
- `/hm:metrics` flag surface (`--window`, `--path` scoping) and interview question wording for enabling the feature.
- Perf budget calibration on real repos (30s/500-file cap are SPEC defaults; plan may tighten).

## 🔍 Refinement Decisions

- R1: Release unit = tag pattern with task-land fallback; surface = new `/hm:metrics` + health narrative; default OFF (opt-in); churn = blame-survival single tier.
- R2: LLM adjudications ledgered + reused (run-to-run stability); 6 non-goals adopted as proposed; oracle = golden fixture repos + property invariants.
- §2.5 gate: perf-budget question skipped (CLARITI fail — constraint set with rationale); adjudication timing + output locale skipped (common ground).

## 🔗 Machine Spec

See [SPEC-cfr-churn-metrics.machine.yaml](./SPEC-cfr-churn-metrics.machine.yaml).
