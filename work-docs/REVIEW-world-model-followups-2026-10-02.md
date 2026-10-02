---
type: review
task_slug: world-model-followups
status: APPROVED
created: 2026-10-02
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
run_id: 70e2bb292bcf
human_review_needed: false
drift_verdict:
  result: scope_violation
  scope_violations:
    - commands/make.md
  scenario_misses: []
  task_slug: world-model-followups
  computed_at: 2026-10-02T09:30:00Z
---

# REVIEW — world-model-followups

## 🎯 Round 1 Summary

Grade **B** (P0 0 · P1 2 · P2 5, all `consensus-passed`, all `accepted`). Lens coverage complete
(7/7, `blocks_approval: false`). Pass 1 raised 16; Pass 2 kept 7 (below). Codex second opinion:
not run (no vote recorded for this run). Auto-fix loop entered for the two P1s.

## 🔍 Drift Findings

`scope_violation` (drift record, not a code defect): `commands/make.md` is outside every PLAN
phase's listed scope. It is the AC-009 forwarding repair — `--world-model-name/--world-model-handle`
on every `make "$(pwd)"` dispatch, including the multi-line one — recorded in PLAN §Phase D.5 with
its test (`test_ac009_every_dispatch_forwards_world_model_flags`). `tests/unit/test_loop_opt_in.py`
and `tests/structural/test_autopilot_gate_render.py` are counted under Phase 4 (golden re-captures).
Incomplete phase: none. Scenario misses: none (AC-001..015 each have a test).

## ✅ Consensus Findings (round 1)

| id | Sev | Lens | Finding | File | Round 2 |
|---|---|---|---|---|---|
| a003ff68 | P1 | functionality | Slug-prefix globs attribute another task's SPEC/REVIEW files to this slug (`demo` read `demo-two`'s) | `world_model_digest.py:152` | **resolved** |
| 6d4374d1 | P1 | concurrency | `next_stage` ran for every worktree before the `MAX_TASKS` slice; no total deadline | `world_model_digest.py:231` | **resolved** |
| 5a2dbc40 | P2 | robustness | Whole span ledger read into memory | `world_model_digest.py:75` | carried |
| 23ab1ccd | P2 | design | Digest reaches into private `autopilot._freshness` | `world_model_digest.py:178` | carried |
| ff606ab0 | P2 | concurrency | `_verify_done` runs `git diff` in live task worktrees; may take `index.lock` | `observability/verification_cache.py:302` | carried |
| 63e23fc7 | P2 | concurrency | A worktree vanishing mid-scan voids the digest or yields a bogus `next_stage` | `world_model_digest.py:48` | carried |
| b257eb78 | P2 | tests | AC-009 reference is a monkeypatched stub of `intent_cli.status_report` | `test_world_model_digest.py:511` | carried |

Dropped at Pass 2 (rationale): security-1 (commit subjects reach the model — the old briefing
already ran `git log`; clipped 60 chars, 1.5 KB cap), security-2 (hostile `.git` pointer needs write
access to gitignored `.worktrees/`), core-2 (`human_review_needed` lives in the REVIEW body, and
wrapup owns that gate), core-4 (P3-class indirection), concurrency-4 (duplicate of 5a2dbc40),
tests-1/3/4/5 (P3 oracle-tightening on render tests whose phrases are already pinned elsewhere).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None.

## 🤝 Disagreements

concurrency-2 arrived at P1 from the concurrency lens and was carried at P2 after Pass 2: the
contention is opportunistic (git's stat refresh) and `_verify_done` runs only for tasks whose
review is already APPROVED, so it is not on the common briefing path.

## 🧊 Cross-model findings (frozen @ round 1)

No cross-model vote this run.

### Iteration 2 (Grade: B → A)
Fixes applied: 2

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | REVIEW/SPEC matched exactly: `REVIEW-<slug>-<YYYY-MM-DD>.md` (`_REVIEW_DATE`), `SPEC-<slug>.md` / `SPEC-<slug>.machine.yaml` | `world_model_digest.py` | Applied · caused_by=none |
| 2 | P1 | Entries sorted and sliced to `MAX_TASKS` before `next_stage`; `DEADLINE_S = 5.0` monotonic budget, `null` past it | `world_model_digest.py` | Applied · caused_by=none |

Tests added with the fixes: `test_review_fix_hyphen_prefix_slug_ignores_sibling_artifacts`,
`test_review_fix_artifact_checks_only_for_shown_tasks` (7 tasks → 5 evaluated; deadline −1 → `null`).
Verification: targeted tests 79 passed; `mypy --strict src tests` clean; ruff check/format clean.

Remaining: 5 (P2, carried) | New issues introduced: 0
Churn: 0.127 (max: `src/harness_maker/world_model_digest.py`, measured 2, excluded 0)
Re-review: skipped — `churn 0.13 < 0.30` (`review_consensus plan`)

## 🔒 Confirmation pass 1 (frozen `d76831c1`, span `7aeb2f47..d76831c1`)

**Deviation, recorded:** `hm freeze read-base` returned `42e858f8` — `HEAD~1` of the task branch,
which would have re-reviewed the already-landed `world-model-name` commit (66 files). The branch had
no commits of its own when round 1 resolved the base. The pass used the merge-base `7aeb2f47`
(= the task's actual start, 20 code files). Worth a look in `freeze resolve-base`.

Coverage 7/7 (`blocks_approval: false`). **New consensus-passed P0/P1: 0 → APPROVED.** No fixes
applied in the pass.

| Lens | Sev | Finding | File |
|---|---|---|---|
| tests | P2 | `digest()["autopilot"]` has no behavioral test (session scoping, freshness, corrupt marker) | `world_model_digest.py:194` |
| tests | P2 | AC-001 property accepts the `digest too large` fallback — no content-conservation check | `test_world_model_digest.py:242` |
| tests | P2 | AC-002 property passes a digest that always returns `unavailable` | `test_world_model_digest.py:302` |
| consistency | P2 | `--world-model-name` flag path still prints English-only name errors | `cli.py:1836` |
| consistency | P2 | Two catalogs for name-rule messages (`_NAME_MESSAGES` vs i18n en), already worded differently | `world_model.py:467` |
| concurrency | P3 | `DEADLINE_S` gates task start only; one started task can run past 5 s | `world_model_digest.py:251` |
| functionality | P3 | Name with `|` breaks the `/hm:help` table row | `help.en.md.j2:62` |
| design | P3 | Literal `"maker"` duplicates `world_model.DEFAULT_HANDLE` | `modular_edit.py:263` |
| design | P3 | `getattr(split, "mapping")` hides a typed field; a rename fails silently | `world_model_digest.py:124` |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 7         | —   |
| 2         | A     | 2             | 5         | 0   |

Final grade: A
Iterations used: 2 / 3
Exit reason: converged
Confirmation: pass 1 clean (new severe 0); pass 2 not needed

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `src/harness_maker/world_model_digest.py` | 283 → 306 | 72 → 75 | 3 → 3 | measured |
| `tests/unit/test_world_model_digest.py` | 541 → 572 | 57 → 61 | 6 → 6 | measured |

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 2 · prior-fix 0 · unattributed 0

## Carried for a human sweep (accepted, not fixed — P2/P3 are outside the fix queue at grade A)

Round 1: 5a2dbc40, 23ab1ccd, ff606ab0, 63e23fc7, b257eb78. Confirmation pass: the nine rows above.
Cheapest with the most value: the two consistency P2s (one message catalog, flag path through
i18n) and the autopilot behavioral test.
