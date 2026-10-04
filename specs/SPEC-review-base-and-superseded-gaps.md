---
type: spec
task_slug: review-base-and-superseded-gaps
status: approved
created: 2026-10-04
tags: [harness-maker, spec, python, freeze, review-base, spec-machine, spec-drift]
test_framework: pytest
tier: 2
interview_rounds: 2
summary: "Zero-commit task branches review from HEAD; superseded ACs keep the oracle advisory and refuse mark-judged"
---

# SPEC: review-base-and-superseded-gaps

## 🎯 Intent

This task fixes three defects that the last two tasks carried.

`hm freeze resolve-base` stores `HEAD~1` as `review_base` when a task branch has no commits of its own. In the per-task model all task work stays uncommitted until wrapup, so `HEAD~1` pulls the previously landed task into the review span. This happened four times (failures.md `resolve-base-head-parent-empty-branch`), twice of them today. Each time the ref was corrected by hand with `git update-ref`.

The other two come from SPEC-spec-ac-superseded's review (carried 7d13ce3a and 9218e7c9). That SPEC says "every authored-content check (predicate, oracle, rubric) still applies" to a superseded AC. Two places break that rule:
- spec_drift's superseded skip also drops the `missing_oracle_source` advisory.
- `mark-judged` still writes a verdict onto a superseded judgment AC, while `mark-tested` already refuses one.

## 🌅 Outcomes

- **Zero-commit task branch.** `review_base` is the fork point, and `hm freeze resolve-base` stores exactly that. The confirmation-pass diff then contains exactly the task's uncommitted work, with no hand-run `update-ref`.
- **Base branch (worktree OFF) and detached HEAD.** The candidate chain is unchanged: a merge-base that is not HEAD, else `HEAD~1`, else the empty tree.
  - With no branch, nothing separates the task's work from earlier commits, and over-scoping is the safer error.
  - This holds on the shipped CLI path, where `--base-branch` is absent, and when `--base-branch` is given as `refs/heads/<b>`, `origin/<b>` or `refs/remotes/origin/<b>`.
- **spec_drift on a superseded AC** whose `oracle_source` is `legacy-unspecified`:
  - still reported under `missing_oracle_source`;
  - absent from `coverage_gaps`;
  - absent from `resolved_but_pending`, even when it is `pending_test: true` with resolvable `test_ids`.
- **`hm spec_machine mark-judged`** refuses a superseded AC before it hashes the subject. It exits non-zero, names the AC, and leaves the file byte-identical.
- **SPEC-ai-review-exit-criteria now matches the code.** Its `review_base` definition and its machine AC-004 predicate state the task-branch exception. AC-004 is edited, not retired, so its freeze-fidelity clauses stand.

## 📋 In-Scope Scenarios

### S1: Zero-commit task branch reviews from its fork point
**Given** a repo whose `main` has two commits, and a branch `hm/task` created at `main`'s tip with no commits of its own and one uncommitted new file
**When** `resolve_review_base(repo)` runs on `hm/task` with the base branch left to default resolution
**Then** it returns `HEAD` (equal to `git merge-base HEAD main`)
**And** a freeze commit parented on it differs from it only by the uncommitted file. The second `main` commit's file is not in the diff.

### S2: Zero-commit task branch that fell behind main
**Given** `hm/task` was created at `main`'s tip with no commits of its own, and `main` then gained a commit (a peer task landed)
**When** `resolve_review_base` runs on `hm/task`
**Then** it returns the recorded fork point, which is `HEAD`. It does not return `main`'s new tip or `HEAD~1`.

### S3: Base branch and detached HEAD keep the existing fallback
**Given** a repo whose `main` has two commits
**When** `resolve_review_base(repo)` runs with the base branch left to default resolution:
- on `main`;
- on `main` with `refs/remotes/origin/main` at the same commit;
- with HEAD detached at `main`'s tip.

**Then** it returns `HEAD~1` in each case
**And** on a single-commit repo it still returns the empty tree

### S4: Task branch with its own commits is unchanged
**Given** `hm/task` has one commit of its own on top of `main`
**When** `resolve_review_base` runs
**Then** it returns the fork point (`main`'s tip)

### S5: spec_drift keeps the oracle advisory for a superseded AC
**Given** a specs dir with one machine SPEC holding:
- a superseded AC with `oracle_source: legacy-unspecified`, `pending_test: false` and `test_ids: []`;
- a superseded AC with `pending_test: true` and a `test_ids` entry that resolves to a real test file;
- a live AC with `oracle_source: legacy-unspecified`.

**When** `spec_drift` scans it
**Then** `missing_oracle_source` contains the first superseded AC and the live AC
**And** `coverage_gaps` contains neither superseded AC
**And** `resolved_but_pending` does not contain the second superseded AC

### S6: mark-judged refuses a superseded judgment AC
**Given** a machine SPEC with a `type: judgment` AC that carries `superseded_by`, and a `judgment_subject_paths` entry that does not exist on disk
**When** `mark_judged(...)` runs for that AC with a valid verdict and non-empty evidence, or the `mark-judged` CLI runs for it
**Then** the call returns an error list whose first entry names the AC id and says it is superseded. It does not return a subject-hash error. The CLI exits non-zero.
**And** the file's bytes are identical before and after

### S7: The CLI stores the fork point on a zero-commit task branch
**Given** the S1 topology, and separately the S3 `main` topology
**When** `hm freeze resolve-base --slug <s> --root <repo>` runs without `--base-branch`, then `hm freeze commit --slug <s> --pass confirm-1`
**Then** on `hm/task` the stored `refs/hm-freeze/v1/<s>-base` equals `HEAD`, and on `main` it equals `HEAD~1`
**And** the freeze commit's parent equals the stored ref

### S8: A qualified --base-branch is normalised to the branch name
**Given** the S3 `main` topology with `refs/remotes/origin/main` present
**When** `resolve_review_base(repo, base_branch=v)` runs for each `v` in `refs/heads/main`, `origin/main`, `refs/remotes/origin/main`
**Then** each returns `HEAD~1`, the same as `base_branch="main"`
**And** on the S1 `hm/task` topology each returns `HEAD`

### S9: The legacy SPEC states the exception
**Given** `specs/SPEC-ai-review-exit-criteria.md` and its `.machine.yaml`
**When** they are read after this task
**Then** the `review_base` definition in the `.md` names the zero-commit task-branch exception. It no longer lists "a branch with no commits of its own" as a case where HEAD is skipped.
**And** machine AC-004 has no `superseded_by` and still asserts frozen-tree fidelity and `freeze_commit_parent == review_base`. Its `review_base != head_sha` clause is limited to the non-task-branch case.

## 🚫 Non-Goals

- The other carried P2s from SPEC-spec-ac-superseded:
  - the retire same-target no-op runs before the target checks;
  - the target-approval TOCTOU;
  - the CLI `validate` / `check --all` dangling-target wiring.
- The P3s carried from that review.
- `review_base` going stale after a rebase (`review-base-stale-after-rebase`).
- `resolve-base` preferring `origin/main` over local `main` (`resolve-base-prefers-pushed-over-head`).
- Changing `hm freeze` arguments or output shape.
- Authoring the legacy SPEC's pending tests. Its `test_ids`, `pending_test` and approval state are left as they are.
- Releasing a new plugin version.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo standard |
| Base-branch identity | The logical base branch name is `base_branch` (or the default-resolved name) with a leading `refs/heads/`, `refs/remotes/origin/` or `origin/` removed | A qualified value must not make the base branch look like a task branch (DRI, round 2) |
| Task-branch test | `git symbolic-ref --quiet --short HEAD` succeeds and differs from the logical base branch name | A detached HEAD has no branch and keeps the conservative fallback (DRI, round 1) |
| HEAD acceptance | Only on a task branch, from the merge-base candidates; every other path keeps the existing skip | Matches the DRI's "task branch only" scope |
| Atomic refusal | `mark-judged` checks `superseded_by` right after the AC lookup, before the type check and before `compute_subject_hash` | Mirrors `mark-tested`'s byte-identical refusal; an unhashable subject must not mask the refusal |
| Existing tests | `test_review_base_never_resolves_to_head_on_a_branch_with_no_own_commits` is the only existing test whose assertion is inverted. Every other existing test passes unmodified | Keeps the rest of the suite an honest regression oracle |
| Absent case | An AC without `superseded_by` is judged and scanned exactly as before | Absent-case rule |
| Test isolation | git-topology tests build throwaway repos under `tmp_path` | They must not read or mutate this repo, except S9, which only reads the committed legacy SPEC |

## 🔒 Irreversible Decisions

none

## ✅ Verification Criteria

S1–S4, S7 and S8 are tested in `tests/unit/test_freeze_commit.py`. S5, S6 and S9 are tested in `tests/unit/test_review_base_and_superseded_gaps.py`.

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (git) | `test_review_base_is_head_on_a_task_branch_with_no_own_commits` |
| S2 | unit (git) | `test_review_base_is_the_fork_point_when_a_zero_commit_task_branch_fell_behind` |
| S3 | unit (git) | `test_review_base_keeps_the_fallback_on_the_base_branch_and_detached_head`, `test_review_base_falls_back_to_the_empty_tree_on_a_single_commit_repo` |
| S4 | unit (git) | `test_review_base_is_the_fork_point_on_a_task_branch` |
| S5 | unit | `test_ac005_spec_drift_keeps_oracle_advisory_for_superseded` |
| S6 | unit | `test_ac006_mark_judged_refuses_superseded` |
| S7 | unit (CLI) | `test_the_cli_stores_head_on_a_zero_commit_task_branch_and_head_parent_on_main` |
| S8 | unit (git) | `test_a_qualified_base_branch_is_normalised` |
| S9 | unit (reads committed files) | `test_ac009_legacy_spec_states_the_task_branch_exception` |
| all | structural | full suite green (AC-010) |

### AC-001: A zero-commit task branch resolves review_base to HEAD
### AC-002: A zero-commit task branch that fell behind still resolves to its fork point
### AC-003: The base branch and a detached HEAD keep the HEAD~1 and empty-tree fallback
### AC-004: A task branch with its own commits still resolves to the fork point
### AC-005: spec_drift reports the oracle advisory for a superseded AC
### AC-006: Mark-judged refuses superseded ACs atomically
### AC-007: The resolve-base CLI stores the right base on both topologies
### AC-008: A qualified base branch is normalised to its name
### AC-009: The legacy SPEC states the task-branch exception
### AC-010: The full suite stays green

## 🔎 Spec Validation

- **Reviewers.** spec-validator (pass 1) returned MAJOR_REVISION (advisory). The codex second opinion was invoked. Both were reconciled in round 2.
- **Accepted:**
  - pin the default (`base_branch=None`) path and the CLI;
  - scope the existing-test inversion to one test;
  - cover resolved-but-pending in S5;
  - make the refusal-before-hash ordering and the AC id in the error observable;
  - relabel the AC-006 oracle as golden;
  - add the legacy-SPEC AC as an edit, not a retire.
- **Rejected:**
  - codex ce040d7f (fork-point may return HEAD). On a task branch it is reached only when both merge-base calls fail, and then it fails too.
  - "Referenced test ids". `referenced_test_ids` is never read in `scan()`, so the clause was dropped as unobservable.

## ❓ Open Questions

(none)

## 🔍 Refinement Decisions

- **Pre-interview (user):**
  - `resolve-base` returns HEAD only on a task branch; the base-branch case keeps `HEAD~1`.
  - All three fixes run as one task through the pipeline.
- **Round 1:**
  - Intent: none.
  - A detached HEAD keeps the `HEAD~1` fallback.
  - Irreversible decisions: none.
- **Round 2:**
  - The legacy SPEC-ai-review-exit-criteria is corrected in this task (definition text plus an edited AC-004 predicate) and verified by AC-009.
  - A qualified `--base-branch` is normalised to the short name.
  - The DRI approved the SPEC with these changes applied.
