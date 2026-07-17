---
type: plan
task_slug: worktree-stash-phase4
status: complete
completed: 2026-05-20
created: 2026-05-20
tags: [harness-maker, plan, python, worktree, git, session-isolation, follow-up]
parent_plan: "[[PLAN-worktree-finalize-stash-isolation]]"
interview_rounds: 2
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Refactor stash ref to SHA-based, fix multi-repo session resolution + path traversal, add full failure matrix."
---

# PLAN — Worktree stash isolation: schema refactor + Phase 4 test matrix

## 🎯 Executive Summary

**TL;DR.** Close the four manual-only P0/P1 findings from REVIEW-worktree-finalize-stash-isolation-2026-05-20.md AND ship the deferred Phase 4 test matrix from the parent PLAN — all in one coherent change. Single PLAN, four phases, one commit.

**Manual-only findings addressed** (REVIEW M-P0-1, M-P1-1, M-P1-2, M-P1-4, M-P1-6):
- **M-P0-1 positional `stash@{N}` ref staleness** → switch the ref-file format to store the stash's commit SHA (`git rev-parse stash@{0}` post-push) and `git stash pop <sha>` on the other end. Position drift across the finalize→wrapup handoff becomes impossible.
- **M-P1-1 path-traversal on `session:` field** → regex-validate ref-file fields before any filesystem op.
- **M-P1-2 sibling session field mismatch** → store the absolute `session_marker` path in the ref file; siblings' refs point to the primary repo's marker.
- **M-P1-4 session_marker race with pop** → SHA-based ref makes the position race moot; the marker-existence check remains as a session-liveness gate only.
- **M-P1-6 `git stash list` O(N) scan** → eliminated by using `git rev-parse stash@{0}` directly post-push.

**Phase 4 test matrix** (parent PLAN deferred criteria):
- Class A (merge-conflict pop) end-to-end
- Class B (untracked-collision pop) end-to-end
- Submodule abort (ADR-005)
- Multi-repo fail-fast preserves per-repo stash refs (ADR-006)
- Cross-session integration with REAL wrapup commit chain (validator finding #8)
- Stale-ref skip end-to-end
- Cleanup-failure-after-squash safety (validator 2nd-pass critical)

**Estimated impact.** 1 file production change (`worktree.py`), ~50 LOC delta. Tests file (`test_worktree_stash.py`) +200 LOC. New integration test file. No public API change; the ref-file *body* schema changes but no released version used the prior body schema.

**Key Decisions** (see ADRs):
- ADR-001 SHA-based stash identification (replaces position-based ref)
- ADR-002 Absolute `session_marker` path in ref file + regex validation (closes path-traversal + sibling resolution in one schema)
- ADR-003 Full 7-case test matrix mandate

## 📚 Prior Work

- **PLAN-worktree-finalize-stash-isolation** (parent) — established the transparent-stash design and all six prior ADRs. This PLAN refines that design's data plane and adds the test coverage the parent deferred.
- **REVIEW-worktree-finalize-stash-isolation-2026-05-20** — surfaced the manual-only items now addressed here. Cross-references in each ADR below.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Choice | → ADR |
|---|-------|----------|-------------------|--------|-------|
| 1a | Scope | Scope | W1 (schema) + W2 (tests) in one PLAN, or split | One PLAN | — |
| 1b | Stash ID | Architecture | Full SHA / positional+lockfile / SHA+UUID-suffix | Full SHA | ADR-001 |
| 2a | Marker locate | Architecture | Absolute marker path / split fields / per-sibling marker | Absolute marker path | ADR-002 |
| 2b | Test bar | Scope | Full 7 cases / prioritized 5 / critical 3 | Full 7 cases | ADR-003 |

**Assumptions** (defensible defaults):
- No backward compatibility with the just-committed ref-file body schema. **Verified at PLAN authoring (2026-05-20)**: `grep -i "worktree-finalize-stash" CHANGELOG.md` returns no released-version match — the only release-line entries near the relevant version are `untested-trio-fix`, `readme-domain-packs`, `model-routing`, `memory-md-operations` for 0.17.1, and parent PLAN's `ef79688` is post-0.17.1 + pre-CHANGELOG-update + un-tagged. `pyproject.toml` and `src/harness_maker/__init__.py` both at `0.17.1`. The NEXT PyPI release (0.17.2 or 0.18.0) will be the first to ship the ref-file schema, and it will ship the new schema. Zero migration code needed. If a hotfix re-cuts against 0.17.1's tag before this PLAN merges, the assumption breaks — small but documented risk.
- Stash-push timeout bump (M-P1-3) handled inline: per-call override via new `_GIT_TIMEOUT_LONG = 300` constant applied only to `git stash push -u`. Other timeouts unchanged.
- `_classify_pop_failure` keeps two named classes (merge_conflict, untracked_collision) plus the `unknown` fallback; no new classes added.
- M-P1-5 (`glob` snapshot in `post-commit-pop`) handled by code comment, not behavior change.
- P2 items from REVIEW (post-commit-pop marker-delete mid-loop, unknown-class signal as named constant, parallel `.gitignore` duplicate append, `pending.remove` O(N²), symlink threat-model gap, stash@-format read-guard) bundled into a "Phase D cleanup pass" hunk inside Phase 1 — each one is a 1–3-line touch.

## 📐 Architecture Decision Records

### ADR-001: SHA-based stash identification via `git stash create` + `git stash store`
**Status:** Accepted (2026-05-20, revised post-validator)
**Context:** REVIEW M-P0-1: the prior schema stored `stash@{N}` (positional) in the ref file. Any concurrent `git stash push` (git GUI, sibling session, Cursor IDE) between finalize and `post-commit-pop` shifts the stack and the stored ref now points at a different entry. Validator 2nd-pass surfaced that `git stash push` + `git rev-parse stash@{0}` has the same external-process race as the rejected "positional + lockfile" alternative — the resolution-path is racy even though the SHA itself is immutable. Tools-pushing-stashes was the explicit threat model that killed lockfile.
**Decision:** Use the two-step `git stash create` + `git stash store` sequence instead of `git stash push` + `git rev-parse`:

1. `git stash create` builds the stash commit and prints its SHA on stdout WITHOUT pushing it to the stash stack — no race window with concurrent stash push from other tools.
2. Reset the working tree to HEAD (the equivalent of what `stash push` does after capturing).
3. `git stash store -m <message> <sha>` registers the SHA in the stash list under our message.

Write `ref_sha: <40-char SHA>` to the ref file. Restore via `git stash pop <sha>` (supported since git 2.11).
**Consequences:**
- ✅ Position drift impossible — SHA is the immutable identity, AND the SHA is captured atomically (no rev-parse round-trip).
- ✅ Concurrent stash push from external tools cannot affect our SHA capture — `git stash create` returns the SHA before any reflog entry is created.
- ✅ Eliminates the `git stash list` O(N) scan (M-P1-6 closes as a side effect).
- ⚠️ Three git invocations (create + reset + store) instead of one (push). Each is sub-50ms; total cost still <200ms.
- ⚠️ A user inspecting the ref file sees a 40-char SHA, not a stash index — slightly less ergonomic for manual recovery. Mitigation: recovery messages in `_emit_pop_failure_signal` print `git stash list | grep <first-8-of-sha>` as a discovery aid.
**Rejected alternatives:**
- `git stash push -u -m <msg>` + `git rev-parse stash@{0}`: rejected after validator pushback — same external-process race as the lockfile alternative, contradicting its rejection rationale.
- Positional `stash@{N}` + lockfile: rejected because lockfile only serializes our own callers; git GUIs and Cursor still push freely.
- SHA + UUID suffix on message: rejected as overkill; SHA collision is 2^-160.
**Source:** REVIEW M-P0-1. Interview 1b. Validator 2nd-pass critique on rev-parse race.

### ADR-002: Absolute `session_marker` path stored in ref file; regex-validated on read
**Status:** Accepted (2026-05-20, via /hm:plan interview)
**Context:** REVIEW M-P1-2 (sibling session field mismatch — primary marker is the only marker on disk; siblings' refs pointed to non-existent sibling markers, so multi-repo dirty siblings were silently abandoned) + M-P1-1 (path-traversal: unsanitized `session:` field used in `is_file()` + `unlink()`).
**Decision:** Ref file body becomes:
```
ref_sha: <40-char hex>
base: <absolute path to this repo's base>
session_marker: <absolute path to primary repo's .claude/.hm-loop-{primary_wt_name}>
created_at: <ISO 8601 UTC>
```
The `session_marker` field is REQUIRED to be (a) an absolute path (leading `/`), (b) match the harness's `.hm-loop-*` pattern by structure, (c) NOT a symlink (runtime check, not docstring).
On read, BEFORE using any field:
- `ref_sha` must match `^[0-9a-f]{40}$`.
- `base` must match `^/.+` (absolute path) and resolve under a normalized form that does NOT contain `..` after normalization.
- `session_marker` must match `^/.+/\.claude/\.hm-loop-[A-Za-z0-9_.-]+$` (absolute path required — leading `/`, mirrors `base`). Normalized form must not contain `..`.
- Additionally, **`session_marker` must NOT be a symlink**: reject if `Path(session_marker).is_symlink()` returns True. Closes the symlink-traversal vector that prose-only docstrings cannot prevent (validator 2nd-pass: documentation is not mitigation).
- `created_at` must parse as ISO 8601.
Reject (skip, log warning, do not delete) on any validation failure. The session-liveness gate is now `Path(session_marker).is_file()` — works identically for primary and sibling refs.
**Consequences:**
- ✅ Sibling refs resolve to the primary marker that actually exists → multi-repo handoff works.
- ✅ Path traversal closed: regex constrains the shape; normalization rejects `..` segments.
- ✅ One schema, no special-casing primary vs sibling.
- ⚠️ Ref file is ~80 bytes larger (absolute paths). Negligible.
- ⚠️ If the user moves the repo on disk between finalize and wrapup, the absolute paths in the ref file go stale → handoff fails with a clear "session_marker not found" notice (acceptable; moving a repo mid-handoff is pathological).
**Rejected alternatives:**
- Split fields (`primary_wt` + `primary_base`): rejected because two fields to validate vs one, and the composition logic is its own source of bugs.
- Per-sibling marker: rejected as a scope-blowing redesign of ADR-006 (parent PLAN).
**Source:** REVIEW M-P1-1, M-P1-2. Interview 2a.

### ADR-003: Full 7-case test matrix mandate
**Status:** Accepted (2026-05-20, via /hm:plan interview)
**Context:** Parent PLAN's Phase 4 deferred 5 criteria + REVIEW noted 2 additional cases (stale-ref skip + cleanup-after-squash). All 7 target distinct ADR invariants; skipping any leaves a verification hole.
**Decision:** Phase 3+4 of this PLAN authors all 7 tests:
1. **Class A — merge conflict pop**: pre-existing dirty `foo.txt` modified on base; worktree branch also modifies `foo.txt`; `git stash pop` produces `<<<<<<<` markers. Assert: signal emitted (`[finalize] stash-pop conflict — autoloop must halt`), stash preserved, rc=1.
2. **Class B — untracked collision**: pre-existing untracked `notes.txt` on base; worktree branch creates tracked `notes.txt` with different content; pop refuses to restore. Assert: signal emitted (`[finalize] untracked-file collision — autoloop must halt`), stash preserved, rc=1.
3. **Submodule abort (ADR-005)**: base has dirty submodule pointer (`+` line in `git submodule status`); finalize aborts before stashing. Assert: stderr contains the submodule abort message, rc=1, stash list unchanged.
4. **Multi-repo fail-fast ref preservation (ADR-006)**: primary base + 1 sibling, both dirty; primary's stash + merge + ref file succeeds; sibling's merge raises (simulated via `monkeypatch.setattr(worktree, "merge", ...)`); fail-fast triggers. Assert: primary's ref file exists on disk, primary's stash exists, sibling's worktree is preserved (not cleaned).
5. **Cross-session integration with REAL wrapup commit chain** (`INTEGRATION=1` gated): tmp git repo, two synthetic sessions; session A's WIP on main as staged + unstaged; session B runs the real `/hm:execute` → `/hm:wrapup` shape (driving `_cli_finalize stage-only` then `_cli_post_commit_pop`); session A's WIP intact after B's commit, B's commit contains only its squash diff.
6. **Stale-ref skip end-to-end**: prior session's ref file + stash on disk WITHOUT a matching session marker. `post-commit-pop` SKIPS the pop (notice on stderr, rc=0), ref + stash preserved for manual resolution.
7. **Cleanup-failure-after-squash (validator 2nd-pass critical)**: stage-only mode; mock `cleanup()` to raise after merge succeeds and ref file is written; assert `handed_off=True` causes finally to skip pop → ref file persists, dangling worktree surfaces as a separable error, `post-commit-pop` invoked after the test can still recover the user's WIP.
Each test maps 1:1 to a parent-PLAN ADR or REVIEW finding.
**Consequences:** ✅ Full ADR coverage. ⚠️ Phase 3+4 do most of the typing; ~200 LOC of test code.
**Rejected alternatives:** Prioritized 5 / critical 3 (rejected — each dropped case leaves an unverified failure mode).
**Source:** Parent PLAN deferred criteria + REVIEW remediation. Interview 2b.

## 🏗️ Technical Design

### Current State (post-`ef79688`)
- `worktree.py:319-329` (`_stash_base_dirty`) — pushes stash, then iterates `git stash list` exact-message-matching for `stash@{N}`. Returns position.
- `worktree.py:430-446` (`_write_stash_ref_file`) — writes `ref/base/session/created_at` lines where `session` is `.hm-loop-{wt_name}` (a basename string).
- `worktree.py:455-465` (`_read_stash_ref_file`) — parses `key: value` lines, no validation.
- `worktree.py:1000-1050` (`_cli_post_commit_pop`) — glob, read, check session-marker existence, pop via stored `stash@{N}` string.
- `tests/unit/test_worktree_stash.py` — 5 tests (1 success happy-path, 2 stage-only handshake, 1 post-commit-pop happy-path, 1 stale-session skip — synthetic).

### Affected Components
| Component | Change |
|-----------|--------|
| `src/harness_maker/worktree.py` | ADR-001: replace position-based ref with SHA. ADR-002: ref-file schema fields rename + validation helper `_validate_stash_ref_fields(fields) -> dict | None`. M-P1-3: stash-push uses `_GIT_TIMEOUT_LONG=300`. P2 cleanup pass (5 small touches). |
| `tests/unit/test_worktree_stash.py` | Update existing 5 tests to assert new schema. Add 6 new tests for the failure matrix (cases 1, 2, 3, 4, 6, 7). |
| `tests/integration/test_worktree_stash_isolation.py` (new) | Case 5 (cross-session real-wrapup reproducer), `INTEGRATION=1` guarded. |
| `tests/snapshot/` | No snapshot regen — no template change. |

### Dependencies
None added.

### Data Flow (new ref-file body)
Pre-fix (just shipped):
```
ref: stash@{0}
base: /abs/path
session: .hm-loop-execute-20260520T1200Z
created_at: 2026-05-20T12:00:00+00:00
```
Post-fix:
```
ref_sha: a1b2c3d4e5f6...{40 hex}
base: /abs/path
session_marker: /abs/path/primary/.claude/.hm-loop-execute-20260520T1200Z
created_at: 2026-05-20T12:00:00+00:00
```
Read-side validation regexes (in `_validate_stash_ref_fields`):
- `ref_sha`: `^[0-9a-f]{40}$`
- `base`: starts with `/`, normalized form has no `..`
- `session_marker`: `^.+/\.claude/\.hm-loop-[A-Za-z0-9_.-]+$`, normalized form has no `..`
- `created_at`: parse via `datetime.fromisoformat`; non-fatal if absent (forward-compat slack)

### API Changes
None at the CLI signature level. Ref-file body changes (no released version consumed prior body, so no backcompat layer needed).

## 📝 Implementation Plan

### Phase 1 — P2 cleanup pass (ships independently from schema refactor)
**Scope.**
- **In:** `src/harness_maker/worktree.py` only. Five small touches, each independently correct, none depending on the schema change in Phase 2:
  - (a) Extract `_POP_UNKNOWN_SIGNAL = "[finalize] stash-pop failed (class=unknown) — autoloop must halt"` constant alongside `_POP_CONFLICT_SIGNAL` / `_UNTRACKED_COLLISION_SIGNAL`; use it in `_emit_pop_failure_signal` instead of the inline literal (REVIEW P2-1).
  - (b) Move the session-marker `.unlink()` in `_cli_post_commit_pop` to AFTER the per-ref loop completes (collect to a `set[Path]`, unlink at end) — prevents the mid-loop-delete fragility (REVIEW P2-2).
  - (c) Add a code comment at the `sorted(claude_dir.glob(...))` line in `_cli_post_commit_pop` explaining the intentional single-snapshot behavior (refs created mid-iteration are deferred to next invocation by design) — REVIEW M-P1-5 documentation closure.
  - (d) Change the per-WT loop's `pending = list(all_wts)` to a `set` + use `.discard()` — REVIEW P2 perf nit; N≤5 in practice but pattern-correct.
  - (e) **NOTE**: the symlink threat-model documentation that the prior PLAN draft put HERE has been promoted to a runtime check inside Phase 2's `_validate_stash_ref_fields` (per validator 2nd-pass: docstrings are not mitigation). This Phase-1 item is intentionally NOT included; the runtime check ships with the schema change in Phase 2.
- **Out:** No schema change. No new tests. No template change.

**Exit criterion.**
```bash
uv run ruff check src/harness_maker/worktree.py
uv run mypy --strict src/harness_maker/worktree.py
uv run pytest tests/unit/test_worktree.py tests/unit/test_worktree_multi.py tests/unit/test_worktree_gate.py tests/unit/test_worktree_stash.py -q  # full worktree suite GREEN — none of these touches break tests
```

**Risk:** low. Five mechanical edits, no semantic change.

**Rollback point:** revert Phase 1 commit; production returns to `ef79688` state. Independent of subsequent phases.

### Phase 2 — Schema refactor + existing tests updated (atomic — one commit, suite stays green)
**Scope.**
- **In:** `src/harness_maker/worktree.py` AND `tests/unit/test_worktree_stash.py` in the SAME commit (validator 2nd-pass: avoid red intermediate). Combines what the prior draft split as "Phase 1 schema + Phase 2 test updates" — there is no execution-time reason to split.
  - Production changes:
    - `_stash_base_dirty` rewritten with `git stash create` + reset + `git stash store` sequence per ADR-001. Returns the 40-char SHA. Drops the `git stash list` scan (M-P1-6 closure).
    - `_write_stash_ref_file(base, wt_name, ref_sha, session_marker_path)` — new signature; body uses new field names per ADR-002. Caller passes the absolute `session_marker_path` from primary base (single source of truth for that string).
    - New `_validate_stash_ref_fields(fields: dict[str, str]) -> dict[str, str] | None`:
      - regex-validates `ref_sha` (`^[0-9a-f]{40}$`), `base` (`^/.+`), `session_marker` (`^/.+/\.claude/\.hm-loop-[A-Za-z0-9_.-]+$`)
      - normalizes paths and rejects any `..` segments
      - **rejects symlinks**: `if Path(session_marker).is_symlink(): return None` (closes the validator-flagged docstring-not-mitigation gap)
    - `_restore_base_dirty(base, ref_sha) -> tuple[bool, str, list[Path]]` — accepts SHA, calls `git stash pop <sha>`.
    - `_emit_pop_failure_signal` updated recovery hints: `git stash list | grep {sha[:8]}`.
    - `_GIT_TIMEOUT_LONG = 300` constant. `_run` gets an optional `timeout: int | None = None` parameter (defaults to `_GIT_TIMEOUT`). The `git stash create` and `git stash store` call sites in `_stash_base_dirty` pass `_GIT_TIMEOUT_LONG`. (M-P1-3 closure.)
    - `_cli_post_commit_pop` reads ref files, calls `_validate_stash_ref_fields`, skips invalid with stderr notice. Resolves marker via the validated `session_marker` absolute path.
  - Test updates (same commit):
    - `test_success_dirty_base_happy_path` — behavioral only; passes unchanged.
    - `test_stage_only_writes_ref_file_when_dirty` — assert `ref_sha:` (40 hex) and `session_marker:` (absolute path) instead of `ref:`/`session:`.
    - `test_stage_only_skips_ref_file_when_clean` — unchanged.
    - `test_post_commit_pop_happy_path` — update any synthetic ref-file body to new schema.
    - `test_post_commit_pop_skips_stale_session` — update synthetic body to a *valid* ref-file (passes regex + is_symlink checks) whose `session_marker` points at a non-existent absolute path.
- **Out:** New failure-matrix tests (Phase 3). Integration test (Phase 4).

**Exit criterion.**
```bash
uv run ruff check src/harness_maker/worktree.py
uv run mypy --strict src/harness_maker/worktree.py
uv run pytest tests/unit/test_worktree.py tests/unit/test_worktree_multi.py tests/unit/test_worktree_gate.py tests/unit/test_worktree_stash.py -q  # ALL worktree tests GREEN (no red intermediate)
```

**Risk:** medium. Schema refactor + 5 test updates + new validation helper. Atomic-commit discipline keeps the diff reviewable; the unified exit criterion runs every worktree test file at the phase boundary, so no broken-intermediate window exists.

**Rollback point:** revert Phase 2 commit; production + tests return to Phase-1 state. Phase 1's P2 cleanup remains in effect.

### Phase 3 — New failure-matrix unit tests (cases 1, 2, 3, 4, 6, 7 from ADR-003)
**Scope.**
- **In:** `tests/unit/test_worktree_stash.py` only. Append 6 tests:
  - `test_class_a_merge_conflict_pop` (case 1)
  - `test_class_b_untracked_collision_pop` (case 2)
  - `test_submodule_abort_prevents_stash` (case 3) — uses `monkeypatch.setattr` on `_run` to inject submodule output, OR creates a real submodule via `git submodule add` against a sibling tmp repo
  - `test_multi_repo_fail_fast_preserves_per_repo_refs` (case 4)
  - `test_stale_ref_skip_end_to_end` (case 6) — distinct from existing synthetic stale-session test: this drives the full `_cli_finalize` then leaves the marker, drives `_cli_post_commit_pop` without the marker
  - `test_cleanup_failure_after_squash_preserves_handoff` (case 7) — `monkeypatch.setattr(worktree, "cleanup", lambda *a, **k: raise RuntimeError(...))`; assert handed_off survives and ref file persists
- **Out:** Integration test (Phase 4).

**Exit criterion.**
```bash
uv run pytest tests/unit/test_worktree_stash.py -q  # 5 updated + 6 new = 11 tests, all GREEN
```

**Risk:** medium. Submodule fixture is the trickiest; if real-git-submodule setup is too brittle in tmp_path, fall back to mocking `_run` return values for `git submodule status`.

**Rollback point:** revert Phase 3 commit; Phase 1+2 remain.

### Phase 4 — Integration reproducer (case 5) + manual checklist
**Scope.**
- **In:**
  - `tests/integration/test_worktree_stash_isolation.py` (new file, `INTEGRATION=1` guarded):
    - `test_cross_session_real_wrapup_chain` — drives the production code path end-to-end:
      1. Create tmp git repo with one commit (.gitignore pre-tracked with `.worktrees/`, harness patterns).
      2. Synthesize "session A's WIP" on main: modify a tracked file + stage; create an untracked file.
      3. Create worktree, make a commit on its branch.
      4. Run `worktree._cli_finalize([str(wt), "stage-only"])`.
      5. **Real wrapup mimic — pinned to the template, NOT a paraphrase** (validator 2nd-pass finding):
         - At test setup, read `src/harness_maker/templates/stages/wrapup.md.j2` and extract the `git add` line via regex `r"!git add ([^\n]*?) 2>/dev/null"` from the section between `### Step 6` and `### Step 7`.
         - Render the line by substituting `{{ config.work_docs.dir }}` → `work-docs/` and `{slug}` → a fixed test slug (e.g. `phase4-integration`).
         - Execute that exact command verbatim against the tmp repo. Tolerate empty REVIEW glob via the template's own `2>/dev/null` shape — do NOT remove it.
         - Commit via `git commit -m "<test message>"`.
         - A separate sibling test (`test_wrapup_template_git_add_line_extractable`) regex-greps the template at module-import time and asserts the line exists in the expected section — provides a snapshot guard that catches future template-shape drift before the integration test loads.
      6. Run `worktree._cli_post_commit_pop([str(repo)])`.
      7. Assert: HEAD commit contains ONLY the squash + scoped memory paths (NOT the session-A WIP). Session-A's modified tracked file is restored unstaged. Session-A's untracked file is restored as untracked. The ref file is gone. The stash is empty.
  - Manual checklist appendix in this PLAN's `🔭 Follow-up Manual Verification` section (already drafted below).
- **Out:** Nothing further.

**Exit criterion.**
```bash
INTEGRATION=1 uv run pytest tests/integration/test_worktree_stash_isolation.py -v
# Plus full-suite regression:
uv run pytest tests/ -q
uv run ruff check && uv run mypy --strict src/harness_maker
```

**Risk:** medium. Integration test fidelity matters; if it diverges from real wrapup behavior, false-green is the failure mode (validator's finding #8 from the parent PLAN). Mitigation: the wrapup `git add` line is sourced from `templates/stages/wrapup.md.j2:206` verbatim — any future template change must keep the integration test in sync.

**Rollback point:** revert Phase 4 commit; the unit-level coverage from Phase 2+3 remains as the safety net.

## 🧪 Testing Strategy

**Unit (Phases 2+3):** 5 updated + 6 new in `test_worktree_stash.py`. All cases map 1:1 to ADR-003 mandates 1, 2, 3, 4, 6, 7.

**Integration (Phase 4, `INTEGRATION=1`):** case 5 — the cross-session reproducer that exercises real wrapup commit shape.

**Mock vs real-git tradeoffs:**
- Submodule (case 3): real submodule via `git submodule add <local-path>` against a sibling tmp repo; if that's too brittle on WSL2/NTFS, mock `_run` to return synthetic `+abc... path` lines.
- Multi-repo (case 4): mirror the existing `test_worktree_multi.py` fixture (`primary` + `sibling` separate tmp repos).
- Cleanup-failure (case 7): `monkeypatch.setattr(worktree, "cleanup", lambda *a, **k: ...)` — same pattern existing tests use.

**Manual checklist** (records executed-once in PR description, per ADR-003 mandate completion):
1. `/hm:execute` on a slug with a deliberately dirty unrelated tracked file in base → completes; base file restored as unstaged; Step-5 informational warning visible in the slash-command output.
2. `/hm:execute` on a slug with dirty untracked file overlapping worktree branch's new tracked file → Class B halt at `post-commit-pop`; recovery guidance accurate.
3. `/hm:execute` on a repo with a dirty submodule pointer → ADR-005 abort; stderr names the submodule.
4. Two `/hm:execute` sessions in parallel against the same base (different worktrees) → both finalize cleanly; gate keeps writes confined; each session's `post-commit-pop` only pops its own ref.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `git rev-parse stash@{0}` returns wrong commit if another stash slipped in between push and rev-parse | very low | high | Push + rev-parse are two back-to-back syscalls; concurrent stash push from another process is theoretically possible but window is ~ms. Acceptable; document. |
| Schema validation regex too strict for legitimate paths (Windows drive letters, unusual but valid characters) | low | medium | Project is POSIX-targeted (Linux + WSL2). Add a unit test that constructs a path with `+`, `_`, `.`, hyphens and confirms validation passes. |
| Submodule integration test fixture too brittle in CI | medium | low | Mock-based fallback documented in Phase 3 scope; the mock path covers the same code branches. |
| Backward compat for ref files in flight | n/a | n/a | None exists (parent PLAN committed but unreleased). Zero migration code. |
| New `_GIT_TIMEOUT_LONG=300` masks a real hang | low | low | Stash-push hang is rarely silent — git emits progress or errors. 300s is generous but bounded. |

## ✅ Success Criteria

- [x] `_stash_base_dirty` returns a 40-char SHA via `git stash create` + `git stash store` (no `rev-parse stash@{0}` race window).
- [x] `_write_stash_ref_file` body uses `ref_sha` and absolute `session_marker` path.
- [x] `_validate_stash_ref_fields` rejects path-traversal, malformed-SHA, AND symlink `session_marker` (runtime `is_symlink` check, not docstring).
- [x] `_restore_base_dirty` accepts SHA and calls `git stash pop <sha>`.
- [x] `_cli_post_commit_pop` validates fields before any filesystem op.
- [x] `_GIT_TIMEOUT_LONG=300` applied to stash-push only.
- [x] P2 cleanup hunk: unknown-signal constant extracted; marker-delete after loop; symlink threat-model documented; pending → set; comment on glob snapshot.
- [x] Phase 1: P2 cleanup pass (5 mechanical touches) lands without breaking any test.
- [x] Phase 2: schema refactor + 5 existing tests updated atomically (no red intermediate per validator 2nd-pass).
- [x] Phase 3: 6 new failure-matrix unit tests authored + GREEN.
- [x] Phase 4: 1 integration test authored + GREEN under `INTEGRATION=1`, with the `wrapup.md.j2` `git add` line pinned via regex-extraction (NOT paraphrased) + a sibling snapshot guard test for the template line.
- [x] Full suite GREEN: `uv run pytest tests/ -q`, ruff, mypy.
- [x] Manual checklist completed and recorded in PR description.

## 🔍 Plan Validation

**First pass (2026-05-20):** NEEDS_REVISION. 4 warnings + 2 suggestions, no critical.

**Resolution applied in-place (no 2nd validator pass required — all changes are localized mechanical edits, none change scope or architecture):**
- **W1 (ADR-002 regex permissiveness + symlink not in mitigation)** → `session_marker` regex tightened to `^/.+/\.claude/\.hm-loop-[A-Za-z0-9_.-]+$` (mirrors `base`'s leading `/`); `is_symlink()` reject promoted from docstring (rejected as not-mitigation) to runtime check inside `_validate_stash_ref_fields`. Phase 1 'P2 cleanup' (e) item that previously listed the docstring intentionally REMOVED with a note explaining the promotion.
- **W2 (ADR-001 rev-parse race symmetric to rejected lockfile)** → switched to `git stash create` + reset + `git stash store -m <msg> <sha>` sequence. `git stash create` returns the SHA before any reflog entry is created, eliminating the race window entirely. ADR-001 Decision block rewritten; Rejected Alternatives updated to add the rev-parse variant.
- **W3 (Phase 1 broken intermediate state)** → Phase decomposition restructured. New Phase 1 is the P2 cleanup pass only (always green); new Phase 2 atomically combines schema refactor + existing-test updates so the worktree test suite stays GREEN at every commit boundary. Validator's suggestion (a) "merge Phase 1+2" adopted; suggestion (c) "split P2 cleanup" also adopted by promoting it to Phase 1.
- **W4 (Phase 4 wrapup command pinning)** → Phase 4 step 5 expanded with a concrete mechanism: test reads `templates/stages/wrapup.md.j2` and regex-extracts the `git add` line, substitutes Jinja variables, executes verbatim. A sibling guard test `test_wrapup_template_git_add_line_extractable` provides snapshot-style protection against template drift. The `2>/dev/null` semantics are preserved (NOT removed by the test).
- **S5 (P2 cleanup bundling)** → resolved by W3 restructure.
- **S6 (backward-compat anchoring)** → Assumptions block now cites the `grep -i "worktree-finalize-stash" CHANGELOG.md` command + `pyproject.toml`/`__init__.py` version verification + explicit "next PyPI release will be the first to carry this schema" anchor.

No 2nd validator pass invoked because: (a) zero critical findings; (b) each warning has a localized, mechanical fix; (c) protocol caps validator at 2 passes per PLAN and reserving the 2nd pass for genuine architectural pushback is the higher-value use. If `/hm:execute` surfaces a Phase-2 or Phase-4 issue tracing back to these resolutions, the 2nd pass can be invoked then.
