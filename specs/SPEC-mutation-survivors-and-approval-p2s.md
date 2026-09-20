---
type: spec
task_slug: mutation-survivors-and-approval-p2s
status: approved
created: 2026-09-20
tags: [harness-maker, spec, python, spec-approval, diagnostics, concurrency, mutation]
tier: 1
test_framework: pytest
summary: "A hold names the field that moved, concurrent writers stop losing each other's work, and the approval surface's unasserted branches get oracles"
---

# SPEC — A hold that names the field, a write that cannot be lost

## 🎯 Intent

The DRI approval gate shipped in `ai-native-sdlc-vs-intent-world` holds a land when a SPEC
was edited after approval, but it cannot say **what** changed: the stamp carries one hash over
the whole authored payload, so the operator is told "edited after approval" and left to diff by
hand. The same review carried two more P2s — `approve` / `mark_tested` / `mark_judged` do an
unlocked read-modify-write of one file, and an unreadable SPEC reports only its exception's
class name.

The first real mutation measurement of that surface (2026-09-20, 62.3%, filed in
`work-docs/MUTATION-ai-native-sdlc-vs-intent-world-2026-09-20.md`) named the third gap
concretely: 68 surviving mutants inside the approval surface, of which the size caps, two
boolean clauses and one error path are genuinely unasserted branches rather than message text.

## 🌅 Outcomes

An operator who edits an approved SPEC is told which fields moved, by name, instead of being
told only that something did. Two sessions writing the same machine SPEC at the same time —
a `/hm:wrapup` recording a test binding while the DRI approves from another terminal — both
survive. A SPEC that fails to load reports the validation error that made it fail. And the
branches the mutation run found unasserted have oracles, so a later refactor of them fails a
test rather than passing quietly.

## 📋 In-Scope Scenarios

### S1: A hold names the field that moved
**Given** a machine SPEC stamped by `hm spec_machine approve`
**When** one authored field is edited and `approval-status` runs
**Then** the reported detail names that field's path
**And** the state is still `invalid` and the land is still held

### S2: A stamp written before this change keeps working
**Given** a machine SPEC whose `approval` block carries `content_hash` but no per-field digests
**When** `approval-status` runs against an unedited copy
**Then** the state is `approved` and the land is `ok`
**And** an edited copy holds with the pre-change wording, naming no field

### S3: Two writers, no lost update
**Given** an approved machine SPEC on disk
**When** an `approve` and a `mark-tested` run as two concurrent OS processes against it
**Then** the file that remains on disk carries both effects — the stamp and the test binding
**And** neither process reports success for work the file does not contain

### S4: The lock is invisible to the repository
**Given** a project whose machine SPEC has just been written under the lock
**When** `git status` and `git check-ignore` are asked about the lock file
**Then** the lock file is ignored by git and appears as no dirt in the working tree

### S5: An unreadable SPEC says why
**Given** a machine SPEC whose YAML parses but fails model validation
**When** `approval-status` runs
**Then** the `malformed` detail carries the validation error's own message, not only its
exception class name
**And** the detail is length-capped so one oversized error cannot flood the caller

### S6: The branches the mutation run found have oracles
**Given** the approval surface's discovery and cap helpers
**When** each documented survivor branch is exercised at its boundary
**Then** a test fails for the wrong answer on that branch — the backslash and `"."` slug
clauses, the empty / `..` / normalising `spec.dir` cases, the md-parent rule, the subject-hash
size and count caps at and over the limit, the `hold_lines` empty-id fallback, and `approve`
with an empty `git config user.name`

## 🚫 Non-Goals

- Narrowing `paths_to_mutate` on `SPEC-ai-native-sdlc-vs-intent-world`. That edits an authored
  field, releases its DRI stamp, and is the DRI's decision, not this task's cleanup.
- Re-running the 5h52m mutation measurement as an exit criterion of this task.
- Asserting every surviving mutant. Message-text mutants are deliberately left alive: pinning
  every string makes a wording fix a test failure.
- Changing what the content hash covers. The deny-list is unchanged; only a per-field view of
  the same payload is added.
- Any change to `world.py`'s locking behaviour beyond routing it through the shared helper.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | The repo's suite; `/hm:execute` Phase A writes against it |
| Digest payload | Identical to `approval_content_hash`'s payload | Two payload builders would drift, and the drift would be silent — the digest would vouch for a field the hash does not cover |
| Backward compatibility | A stamp with no per-field digests stays valid | Invalidating them would release the `ai-native-sdlc-vs-intent-world` approval on a code change alone |
| Lock scope | One lock file per guarded file, under a gitignored directory | `[fail:test] fix-introduced-defect-passes-all-gates` (2026-09-17): a lock fix put its lock file in a TRACKED directory and shipped as repo dirt |
| Concurrency evidence | Two real OS processes | `flock` is an inter-process lock; two threads in one process do not reproduce the race |
| Mutation | `verification_tier: 1`, threshold 85, `paths_to_mutate` = the new digest module only | A whole-module target cannot finish inside the gate's 600 s cap (1303 mutants measured), so a T1 gate on `spec_machine.py` could only ever report `truncated` |
| Detail cap | ≤ 200 characters | `codex_ledger.cap_oracle_result` precedent: an uncapped string fails validation downstream and the whole row is lost |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | The `approval` stamp gains a per-field digest map | schema/file format/storage layout | Every consumer of the stamp — `approval-status`, the land hold, any later reader — sees the new key. Once stamps carrying it exist across repos, removing it strips their diagnostic and breaks any reader keyed on it |
| IRR-002 | A stamp without the digest map stays valid | data migration | This decides whether existing approvals survive the upgrade. Reversing it later forces every project holding an approved SPEC to re-stamp before it can land |
| IRR-003 | The lock key rule: one lock file per guarded file, under a gitignored directory | public API/CLI contract | Mutual exclusion holds only while every writer agrees on the key. A later writer that derives a different path gets no exclusion and no error — the failure is silent by construction |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_ac_003_a_hold_names_the_edited_field` |
| S2 | unit | `test_ac_004_a_stamp_without_digests_is_still_approved` |
| S3 | integration | `test_ac_005_two_processes_writing_lose_nothing` |
| S4 | unit | `test_ac_006_the_lock_file_is_git_ignored` |
| S5 | unit | `test_ac_007_malformed_detail_carries_the_validation_error` |
| S6 | unit | `test_ac_008_slug_rejection_table`, `test_ac_009_spec_dir_table`, `test_ac_010_md_parent_rule`, `test_ac_011_subject_hash_caps_at_the_boundary`, `test_ac_012_hold_line_id_fallback`, `test_ac_013_approve_without_a_git_identity` |
| S1 (coverage invariant) | unit | `test_ac_001_every_hashed_field_has_its_own_digest` |
| S1 (exclusion invariant) | unit | `test_ac_002_an_excluded_field_moves_neither_digest_nor_hash` |

### AC-001: every hashed field has its own digest, and only those
The digest map's key set equals the field set the content hash covers, for any SPEC — including
keys the model does not declare (`extra="allow"` round-trips them) and excluding every
deny-listed tooling field. Both views are derived from one payload builder, so a field the hash
covers can never be missing from the map.

### AC-002: an excluded field moves neither the digest map nor the hash
Editing `last_mutation_run`, `spec_quality_score`, `spec_quality_score_at`, a per-AC
`test_ids` / `pending_test` / `judgment_*`, or the `approval` block itself leaves the content
hash and every digest byte-identical. This is the deny-list's existing contract, restated
against the new view so the two cannot drift apart.

### AC-003: a hold names the edited field
When exactly one authored field changes after approval, `approval_state` reports `invalid`
and its detail names that field's path (for example `ac[1].expected`). When several change,
the detail names up to five, sorted, then the count of the rest. The land stays held: naming
the field changes the message, never the verdict.

### AC-004: a stamp without digests is still approved
A stamp carrying `content_hash` but no digest map keeps its state — `approved` when the
content is unchanged, `invalid` when it is not — and the invalid case falls back to the
pre-change wording, naming no field. No SPEC approved before this change needs re-stamping.

### AC-005: two processes writing the same SPEC lose nothing
An `approve` and a `mark-tested` launched as two concurrent OS processes against one machine
SPEC both complete, and the file on disk afterwards carries the approval stamp AND the test
binding. Neither process may exit zero for an effect the file does not hold.

### AC-006: the lock file is git-ignored
The lock guarding a machine SPEC's read-modify-write resolves under a directory git already
ignores, and `git status --porcelain` reports no entry for it after a guarded write. A lock in
a tracked directory ships as repo dirt — the recorded 2026-09-17 regression.

### AC-007: a malformed SPEC reports the validation error
When the model rejects a machine SPEC, the `malformed` detail carries the validation error's
own message — the field and reason — not only the exception's class name, capped at 200
characters so one oversized error cannot flood the caller.

### AC-008: the slug rejection table
`_is_plain_slug` accepts a plain name and rejects the empty string, `"."`, `".."`, a slug
containing `/`, and a slug containing a backslash. Each rejection is a row, so no clause of the
predicate can be deleted without a row failing.

### AC-009: the spec.dir normalisation table
`_spec_dir` returns the default for an absent, empty, whitespace-only, absolute or
`..`-containing value, and otherwise returns the configured value normalised with a single
trailing slash — `./specs/` and `specs` both resolving to `specs/`.

### AC-010: an md file counts only inside a configured spec dir
`_changed_spec_units` counts a changed `SPEC-<slug>.md` when its parent is one of the
configured spec dirs and ignores it when it is not, while a `machine.yaml` counts from any
parent. A repo-root md that merely matches the filename must not enter the land decision.

### AC-011: the subject-hash caps hold at the boundary
`compute_subject_hash` raises `SubjectHashError` when the file count, the per-file size, or the
total byte count crosses its cap, and succeeds at exactly the cap. The at-limit case is what
distinguishes `>` from `>=`; an empty expansion and an unreadable file each raise with their
own message.

### AC-012: a hold line with no irreversible ids prints the placeholder
`hold_lines` renders `-` in the id column for a held SPEC whose irreversible list is empty, and
renders the ids space-joined when it is not. The line stays parseable either way.

### AC-013: approve without a git identity fails and writes nothing
A human `approve` where the base root's `git config user.name` is empty raises `ApprovalError`
and leaves the machine SPEC byte-identical — no partial stamp, no cleared previous approval.

## ❓ Open Questions

None. Every question raised in the interview was answered; the resolutions are below.

## 🔍 Refinement Decisions

- Round 1 — the digest logic lives in a new small module, not inside `spec_machine.py`: a
  whole-module mutation target cannot finish inside the gate's 600 s cap, so the placement
  decides whether this SPEC's own tier-1 gate can ever run. Concurrency is proven with two OS
  processes, not threads. Survivor coverage spans the whole approval surface's real gaps, not
  only the code this task touches.
- Round 2 — `verification_tier: 1` with `paths_to_mutate` naming the new module alone. A stamp
  without per-field digests stays valid and falls back to the pre-change hold wording; the
  alternative (invalidate and require re-approval) would release a DRI stamp on a code change.
- Round 3 — three irreversible decisions recorded. Adding a helper to `io_utils` was dropped
  from the list: an added function breaks no existing consumer, and the real cross-unit
  contract is the lock key rule, which is IRR-003. A hold naming many fields prints at most
  five, sorted, then a count — defaulted, not asked.
