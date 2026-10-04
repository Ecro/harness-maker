---
type: plan
task_slug: review-base-and-superseded-gaps
status: complete
created: 2026-10-04
tags: [harness-maker, plan, python, freeze, review-base, spec-machine, spec-drift]
spec: "[[SPEC-review-base-and-superseded-gaps]]"
interview_rounds: 0
adrs: 3
validator_outcome: NOT_RUN
summary: "Task-branch review_base = HEAD; spec_drift keeps oracle advisory; mark-judged refuses superseded"
spec_need_verdict: add
spec_need_target: review-base-and-superseded-gaps
---

# PLAN: review-base-and-superseded-gaps

## 🎯 Executive Summary

This task makes three small fixes, each in its own file, plus a documentation correction to a legacy SPEC.

1. **`freeze.resolve_review_base`** accepts `HEAD` from the merge-base candidates when HEAD is on a task branch, meaning a named branch other than the logical base branch. It also normalises a qualified `base_branch`.
2. **`spec_drift.scan`** checks the oracle advisory before the superseded skip.
3. **`spec_machine._mark_judged_locked`** refuses a superseded AC right after the AC lookup.
4. **SPEC-ai-review-exit-criteria** gets its `review_base` definition and its AC-004 predicate edited. AC-004 is edited, not retired.

The decisions come from the SPEC: rounds 1 and 2, the DRI's "task branch only" pre-decision, and the spec-validator and codex reconciliation.

## 📚 Prior Work

- `failures.md` `resolve-base-head-parent-empty-branch` (count 4) is the bug itself. Each occurrence was worked around with a manual `git update-ref`.
- `SPEC-ai-review-exit-criteria` (2026-08-15) introduced the HEAD skip. Its premise ("would diff only the last round's fixes") assumed fixes get committed between rounds. In the per-task model commits happen only at wrapup.
- `SPEC-spec-ac-superseded` introduced `superseded_by`. Its review carried 7d13ce3a (spec_drift) and 9218e7c9 (mark-judged).
- `failures.md` `assertion-invariant-over-named-dimension` (count 22): each test must vary the dimension it names. Base branch vs task branch vs detached HEAD is exactly that dimension, so every case gets its own fixture.
- `failures.md` `model-field-add-hits-hidden-gates`: no model field or CLI verb is added here, so that gate does not apply.

## 📐 Architecture Decision Records

### ADR-001: Task branch = named branch ≠ logical base branch
`git symbolic-ref --quiet --short HEAD`. When it fails (detached HEAD), the old fallback applies. When it equals the normalised base branch name, the old fallback applies. Otherwise, a merge-base candidate equal to HEAD is accepted.
**Decided by:** user (source: SPEC Pre-interview + Round 1 detached-HEAD answer)

### ADR-002: Normalise qualified base-branch values by stripping `refs/heads/`, `refs/remotes/origin/` and `origin/`
The stripped name is the logical name. It is used for both the branch-identity comparison and the merge-base candidates, so `remote = refs/remotes/origin/<name>` is no longer doubled.
**Decided by:** user (source: SPEC Round 2)

### ADR-003: Legacy AC-004 predicate is edited in place, not retired
The clause `review_base != head_sha` becomes `(on_task_branch or review_base != head_sha)`. The two freeze-fidelity clauses stay.
**Decided by:** user (source: SPEC Round 2)

## 🏗️ Technical Design

`resolve_review_base(base, base_branch=None)`:
- `branch = _normalise(base_branch or _default_base_branch(base))`.
- `current = _try_git(base, "symbolic-ref", "--quiet", "--short", "HEAD")`.
- `on_task_branch = current is not None and current != branch`.
- In the candidate loop, a candidate equal to `head` is accepted when `on_task_branch` and the rule is a merge-base rule (any rule other than `HEAD~1`, which can never equal HEAD).

`spec_drift.scan`:
- Move the `legacy-unspecified` append above the `superseded_by` `continue`.

`_mark_judged_locked`:
- After `ac is None`, add `if ac.superseded_by is not None: return [f"mark-judged: {ac_id} is superseded by {ac.superseded_by}; it owes no verdict"]`.

## 📝 Implementation Plan

### Phase 1 — Tests (RED) — DONE
- depends_on: none; parallel_group: none; merge_hazards: none
- **Scope in:**
  - `tests/unit/test_freeze_commit.py`: invert `:64`, and add the S1, S2, S3, S7 and S8 tests.
  - `tests/unit/test_review_base_and_superseded_gaps.py`: S5, S6 and S9.
- **Scope out:** everything in `src/`.
- **Exit:** `uv run pytest tests/unit/test_freeze_commit.py tests/unit/test_review_base_and_superseded_gaps.py` fails, and only the new or inverted tests fail.
- risk: low; rollback: delete the new test file and `git checkout` the freeze test.

### Phase 2 — Implementation (GREEN) — DONE
- depends_on: 1; parallel_group: none; merge_hazards: none
- **Scope in:**
  - `src/harness_maker/freeze.py`
  - `src/harness_maker/observability/spec_drift.py`
  - `src/harness_maker/spec_machine.py`
  - `specs/SPEC-ai-review-exit-criteria.md`
  - `specs/SPEC-ai-review-exit-criteria.machine.yaml`
- **Exit:**
  - both test files pass;
  - `ruff check`, `ruff format --check` and `mypy --strict` pass on the changed source files;
  - the full suite passes (AC-010).
- risk: medium, because freeze sits on the review path. Rollback: `git checkout` the three source files.

## 📓 Execution Notes

- **A.4:** 10 failed, 22 passed.
  - Every new pass is a justified negative control: base-branch, detached and main CLI fallbacks, plus the live judgment control.
  - The first run also passed `test_ac006_mark_judged_refuses_superseded[cli]` falsely: exit 1 came from `SubjectHashError`. It was fixed to assert that stderr names the AC and says `superseded`.
- **A.5:**
  - Round 1 FAIL (1 blocking): the AC-009 substring check accepted inverted predicate shapes. It was rewritten to an AST `Or(on_task_branch, review_base != head_sha)` check.
  - Round 2 PASS.
- **Mutation check at phase exit:** 6 mutants, all killed.
  - M1: no normalisation.
  - M2: any named branch counts as a task branch.
  - M3: detached HEAD counts as a task branch.
  - M4: spec_drift order reverted.
  - M5: superseded skip dropped.
  - M6: mark-judged check moved after the hash.
- **D.5 newly-reachable window:** `resolve_review_base` now returns `HEAD` for any *named* branch other than the logical base branch whose merge-base with it is HEAD. That covers:
  - a zero-commit task branch (S1);
  - a zero-commit task branch behind the base (S2);
  - a qualified base-branch spelling on such a branch (S8).
  - It also covers a non-`hm/` feature branch under worktree OFF. This is accepted: the task-branch definition is "named branch ≠ base branch" (ADR-001).
  - Tests that enter the window: the S1, S2, S8 and S7[task-branch] tests in `tests/unit/test_freeze_commit.py`.
  - Absent cases: `base_branch` absent goes through default resolution (S3, S7). `superseded_by` absent is covered by the live controls in the S5/S6 tests.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/` — no stage prose changes; the template calls `resolve-base` the same way
- `src/harness_maker/command_registry.py` — no new CLI verb
- Advisory: `hm freeze` argument names and JSON output shape stay as they are
- Advisory: the legacy SPEC's `test_ids`, `pending_test` and approval state stay as they are

## 🧪 Testing Strategy

- **git-topology unit tests** build throwaway repos under `tmp_path`. Each S3 case gets its own fixture (base branch, base branch with origin, detached HEAD, single commit).
- **CLI test (S7)** calls `freeze_main([...])` without `--base-branch`.
- **spec_drift and mark-judged tests** use hand-written fixture specs in `tmp_path`, and read bytes before and after.
- **S9** reads the committed legacy SPEC files.
- **Full suite** runs once at phase exit, in the background.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The base branch is misclassified as a task branch, so Side mode stores HEAD | low | high | S3 runs with `base_branch=None`, and S7 covers `main` via the CLI |
| `origin/main` normalisation changes the remote-preference test | low | medium | `test_base_resolution_prefers_the_remote_tracking_ref` must pass unmodified |
| This task's own review hits the old bug (released 0.62.0 plugin) | high | low | Verify `refs/hm-freeze/v1/<slug>-base` against `git merge-base` at review round 1 and correct it if needed |

## ✅ Success Criteria

- [x] AC-001: a zero-commit task branch gives HEAD, and the freeze diff contains only the untracked file
- [x] AC-002: a task branch that fell behind gives its fork point
- [x] AC-003: on the base branch (default, and with origin), detached HEAD gives HEAD~1, and a single commit gives the empty tree
- [x] AC-004: a task branch with its own commits gives the fork point
- [x] AC-005: spec_drift keeps the oracle advisory and does not report the AC as resolved-but-pending
- [x] AC-006: mark-judged refuses before the hash, names the AC id, and leaves the file byte-identical
- [x] AC-007: the CLI stores HEAD on a task branch and HEAD~1 on main, and the freeze parent equals the stored base
- [x] AC-008: qualified base-branch values are normalised
- [x] AC-009: the legacy SPEC text and the AC-004 predicate are corrected
- [x] AC-010: the full suite is green, and only the one existing test is inverted
