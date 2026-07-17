---
type: plan
task_slug: untested-trio-fix-2026-05-19
status: complete
created: 2026-05-19
tags: [harness-maker, plan, python, worktree, second-brain, code-review-followup]
interview_rounds: 3
adrs: 10
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Fix P0-2 (worktree cleanup prefix safety) + P1-3 (second_brain write timestamp auto-fill, all 3 mutators); P0-1 deferred"
---

# PLAN — Fix P0-2 + P1-3 (untested trio follow-up)

## 🎯 Executive Summary

**TL;DR:** Implement 2 of the 3 fixes recommended in `REVIEW-untested-trio-summary-2026-05-19.md`. P0-1 (traversal validator) deferred — user explicitly chose not to touch it because legitimate `../sibling-name` usage exists in 4+ test files.

**Fixes in scope:**
1. **P0-2** — `_list_worktrees` (in `worktree.py`) adds an owned-prefix filter `('execute-', 'plan-', 'phase-', 'autoloop-')`. Aligns code with CLAUDE.md's documented cross-tool safety claim.
2. **P1-3** — `write_note` / `append_note` / `patch_note` auto-fill `created` / `updated` timestamps; **append/patch additionally re-serialize frontmatter** so the `updated` bump actually lands on disk (validator C-1 resolution). `write_note` also reads on-disk `created` if the target file already exists (validator W-3 resolution — preserves historical creation timestamp).

**Estimated diff:** ~110 LOC src + ~200 LOC tests + 1 CLAUDE.md line.

**Key decisions (links to ADRs):**
- P0-1 deferred (ADR-001)
- P0-2 via centralized `_list_worktrees` filter (ADR-002)
- P1-3 scope = timestamps only (no tag/project_id injection) (ADR-003)
- Owned prefix set = 4 prefixes (ADR-004)
- Existing orphan markers untouched by this PLAN (ADR-005)
- Timestamp policy — created if-missing + on-disk-preserve / updated always-bump (ADR-006)
- Regression coverage = unit tests only (ADR-007)
- write_note preserves on-disk `created` (ADR-008)
- append/patch re-serialize frontmatter so `updated` bump lands on disk (ADR-009)
- `_autofill_timestamps` does NOT mutate caller's dict (ADR-010)

## 📚 Prior Work

- Parent: `[[PLAN-untested-trio-review-2026-05-19]]` (deep code review that produced the fix candidates)
- Findings sources:
  - P0-2: `[[REVIEW-sibling-repo-2026-05-19]]` B3 / D1
  - P1-3: `[[REVIEW-second-brain-2026-05-19]]` I1 (critical)
  - Cross-cutting: `[[REVIEW-untested-trio-summary-2026-05-19]]` items 2 + 3
- Origin context: `[[PLAN-multi-repo-mgmt-2026-05]]` introduced multi-repo worktree pattern (sibling REVIEW D2)

*Note on wikilinks: this project does NOT yet have an Obsidian Second Brain vault populated with these REVIEW notes — the references resolve to files under `work-docs/` (this repo's `.md` files). Wikilink syntax is preserved for future Second Brain auto-injection.*

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | → ADR |
|---|-------|-------|----------|--------|-------|
| 1 | R1 | Traversal policy (P0-1) | Scope | Skip — do not modify | ADR-001 |
| 2 | R1 | P0-2 fix form | Architecture | Code fix: `_list_worktrees` prefix filter | ADR-002 |
| 3 | R1 | P1-3 scope (tags / project_id) | Architecture | Timestamps only | ADR-003 |
| 4 | R2 | Owned prefix set | Contract | `execute-/plan-/phase-/autoloop-` (4) | ADR-004 |
| 5 | R2 | Existing orphan worktrees / markers | Scope | Out-of-scope for this PLAN | ADR-005 |
| 6 | R2 | Update strategy | Contract | created if-missing-only / updated always | ADR-006 |
| 7 | R2 | Regression depth | Testing | Unit tests only | ADR-007 |
| 8 | R3 (validator) | append/patch on-disk bump (C-1) | Architecture | Include — re-serialize frontmatter | ADR-009 |
| 9 | R3 (validator) | write_note on-disk created (W-3) | Architecture | Yes — read existing, preserve | ADR-008 |
| 10 | R3 (validator) | sentinel test for `_OWNED_PREFIXES` (W-1) | Testing | Drop — accept manual-update risk | (risk register) |
| 11 | R3 (validator) | caller dict mutation (W-2) | Contract | Helper must not mutate caller's dict | ADR-010 |

## 📐 Architecture Decision Records

### ADR-001: Defer P0-1 (traversal validator)
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** Trio REVIEW B1 across refdocs + sibling_repo flagged `..` traversal unrejected. Research showed 4+ existing test files + `interview._ask_sibling_repos` docstring rely on legitimate single-level `../<name>` patterns.
**Decision:** No code change to `RefFolder.path` / `sibling_repos` validators. The B1/S1 finding remains as a known posture gap documented in the trio REVIEWs.
**Consequences:**
- ✅ Zero migration burden, zero regression risk
- ⚠️ The filesystem-disclosure posture gap (refdocs B1) persists — acceptable in single-user local model
**Rejected alternatives:**
- At-most-one-`..` rule — Rejected: user chose not to fix at all
- Outright reject — Rejected: would break 4+ test files
- Opt-in flag — Rejected: PLAN scope is P0-2 + P1-3 only
**Source:** Interview #1

### ADR-002: P0-2 via centralized `_list_worktrees` filter
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** `_list_worktrees` is the single chokepoint for `cleanup_all`; filtering at source is more defensive than filtering at each call site.
**Decision:** Add `_OWNED_PREFIXES` module constant in `worktree.py`. Inside `_list_worktrees`, after the existing `WORKTREE_DIR_NAME` + `is_relative_to(base)` checks, also gate on `p.name.startswith(_OWNED_PREFIXES)`.
**Consequences:**
- ✅ Cursor or any other tool's worktrees under `.worktrees/<other-prefix>/` are immune to `cleanup_all`
- ✅ CLAUDE.md's documented safety claim now holds in code
- ⚠️ Future new stage prefixes must be added to `_OWNED_PREFIXES` — accepted manual-update risk (sentinel test dropped per ADR resolution; risk listed in register)
**Rejected alternatives:**
- Docs-only fix (CLAUDE.md rewritten to match impl) — Rejected: safety-by-default beats documentation-of-unsafety
- Config-driven owned_prefixes (harness.yaml field) — Rejected: 4-constant hardcode sufficient
- Per-call-site filtering — Rejected: scattered enforcement is harder to audit
**Source:** Interview #2

### ADR-003: P1-3 scope = timestamps only (no tag / project_id injection)
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** Three scope levels were offered. User chose tightest.
**Decision:** Auto-fill only `created` / `updated`. Required tags (`hm/second-brain`, `hm/type/<note_type>`) and project_id namespace remain user-supplied; their missing-state continues to surface as warnings.
**Consequences:**
- ✅ Smallest behavior change; no opinion-injection into user-supplied content
- ⚠️ Wrapup-stage minimal call still warns on tags/project_id — those warnings remain in JSON output (REVIEW I4 separate concern)
**Rejected alternatives:**
- Auto-inject required tags — Rejected: semantic change to user content
- Auto-inject project_id — Rejected: cross-project decision notes may legitimately lack the local project_id
**Source:** Interview #3

### ADR-004: Owned prefix set = `('execute-', 'plan-', 'phase-', 'autoloop-')`
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** CLAUDE.md mentions `phase-*` + `autoloop-*`; codebase actually creates `execute-*` + `plan-*` (worktree.scope: [execute, plan]). Summary recommended 4 (union).
**Decision:** Module constant `_OWNED_PREFIXES: tuple[str, ...] = ("execute-", "plan-", "phase-", "autoloop-")`. Also update CLAUDE.md §"Worktree 공유" to list all 4 prefixes (one-line edit).
**Consequences:**
- ✅ All current real-world creation paths covered
- ⚠️ Adding a new stage prefix requires updating this tuple — risk listed in register
**Rejected alternatives:**
- Two-prefix (CLAUDE.md literal) — Rejected: would leak `execute-*` / `plan-*` orphans
- Config-driven — Rejected: premature
**Source:** Interview #4

### ADR-005: Existing orphan markers not touched by this PLAN
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** Live exercise during trio REVIEW left 8+ `.claude/.hm-loop-execute-*` marker files from past sessions. `git worktree list --porcelain` (Phase 0 enumeration) confirms NONE of these have corresponding active worktrees registered with git — they are pure marker-file orphans, not git-worktree orphans.
**Decision:** This PLAN ships code only. Marker-file cleanup is a separate concern (deserves its own PLAN, e.g. mtime > 30-day sweep). The prefix filter does NOT affect marker files (markers live in `.claude/.hm-loop-*`, not `.worktrees/`).
**Consequences:**
- ✅ Scope-tight PLAN
- ⚠️ Marker file pile-up persists — cosmetic, no correctness impact
**Rejected alternatives:**
- Add orphan-marker-sweep phase — Rejected: scope creep
**Source:** Interview #5

### ADR-006: Timestamp policy — created if-missing / updated always-bump
**Status:** Accepted (2026-05-19, via /hm:plan interview; refined via validator R3)
**Context:** "updated" semantically means "last touch time"; always-bump is consistent. "created" should reflect first-write time.
**Decision:** `_autofill_timestamps(fm)` helper:
```python
def _autofill_timestamps(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """Return a NEW dict with created (if missing) and updated (always) set.

    Mutation-free per ADR-010: caller's input dict is not modified.
    """
    out = dict(frontmatter)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out.setdefault("created", now)
    out["updated"] = now
    return out
```
Format: `"%Y-%m-%dT%H:%M:%SZ"` — matches `refdocs_index.py:64` project convention.
**Consequences:**
- ✅ Wrapup minimal call succeeds (resolves REVIEW I1)
- ✅ `append_note` / `patch_note` callers see `updated` bump on disk (per ADR-009 frontmatter re-serialization)
- ⚠️ User explicitly supplying past `updated` is overwritten — documented contract
**Rejected alternatives:**
- if-missing-only for both — Rejected: `updated` wouldn't reflect last touch
- Always overwrite both — Rejected: would lose user-supplied `created` history
**Source:** Interview #6

### ADR-007: Regression coverage = unit tests only
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** User chose tight scope. The wrapup-template integration test was an alternative but would duplicate existing `test_second_brain.py` infrastructure.
**Decision:** Unit tests directly against `write_note` / `append_note` / `patch_note` / `_list_worktrees`. No new integration / e2e tests in this PLAN. Phase 3 includes one **smoke** script that exercises write→append→patch on a minimal frontmatter to surface the integration-style failure mode.
**Consequences:**
- ✅ Fast feedback loop
- ⚠️ Wrapup template invocation is exercised only transitively via the smoke
**Rejected alternatives:**
- Unit + e2e — Rejected: scope-tight; e2e in follow-up
**Source:** Interview #7

### ADR-008: `write_note` preserves on-disk `created` (read-existing-first)
**Status:** Accepted (2026-05-19, via validator W-3 resolution)
**Context:** Without this, calling `write_note` twice with no `created` in fm would install a NEW `created` on the second call (the first call's `now` is wiped from disk because the second call's fm has no `created` either). Critical history-loss.
**Decision:** When `target_path.exists()`, `write_note` reads the existing file, parses its frontmatter, propagates the on-disk `created` into the new frontmatter via `setdefault` BEFORE `_autofill_timestamps` runs.
```python
if path.exists():
    try:
        existing_text = path.read_text(encoding="utf-8")
        existing_fm, _ = parse_frontmatter(existing_text)
        if "created" in existing_fm and "created" not in frontmatter:
            frontmatter = {**frontmatter, "created": existing_fm["created"]}
    except OSError:
        pass  # treat as fresh write
```
**Consequences:**
- ✅ Historical `created` is preserved across re-writes
- ✅ Race mitigation: read-existing-then-merge reduces (but does not eliminate) the concurrent-writer last-call-wins window
- ⚠️ One extra read per existing-file write — negligible cost
**Rejected alternatives:**
- Accept last-writer-wins — Rejected: invisible history loss is unacceptable per validator C-1 / W-3
**Source:** Interview #9

### ADR-009: `append_note` / `patch_note` re-serialize frontmatter
**Status:** Accepted (2026-05-19, via validator C-1 resolution)
**Context:** Existing `append_note` (`second_brain.py:158-171`) and `patch_note` (`:174-189`) mutate the local frontmatter dict but write `existing + text` / `existing.replace(...)` raw — the mutation NEVER reaches disk. Without this fix, ADR-006's "updated bumps on append/patch" claim would be a no-op on disk.
**Decision:** Restructure both functions to:
1. Read existing file → `parse_frontmatter(existing)` → `(fm, body)`
2. For `append_note`: compute `new_body = body + text` (whitespace handling preserved by including `text` verbatim)
3. For `patch_note`: compute `new_body = body.replace(old_text, new_text, 1)`; raise if `old_text not in body`
4. `fm = _autofill_timestamps(fm)` to bump `updated`
5. `_format_note(fm, new_body)` → `atomic_write`

The behavior difference for `patch_note`: the previous implementation searched for `old_text` in the *full file* (frontmatter included). The new implementation searches only the *body*. This is corrective — patching against the frontmatter block was undefined behavior and not exercised by any test.
**Consequences:**
- ✅ `updated` bump lands on disk for all 3 mutators (resolves validator C-1)
- ✅ frontmatter is the canonical YAML again (no drift from manual concat)
- ⚠️ `patch_note` no longer matches `old_text` inside frontmatter — corrective change documented
**Rejected alternatives:**
- Defer to follow-up PLAN — Rejected: validator surfaced this as critical; deferring would ship the silent-no-bump bug
- Use string-replacement on the full file (preserve current scope) — Rejected: doesn't solve the on-disk update; would still need a final yaml round-trip
**Source:** Interview #8

### ADR-010: `_autofill_timestamps` does NOT mutate caller's dict
**Status:** Accepted (2026-05-19, via validator W-2 resolution)
**Context:** Slash-command templates and Python callers can reuse a frontmatter dict across multiple write_note calls. If `_autofill_timestamps` mutates in place, the second call sees the first call's `created` (locked by setdefault) → all notes share the first note's creation timestamp.
**Decision:** Helper signature: `_autofill_timestamps(fm: dict) -> dict` returns a NEW dict (via `dict(fm)` shallow copy). Caller's input is untouched.
**Consequences:**
- ✅ Caller can reuse the same template-fm dict across multiple notes safely
- ⚠️ One small allocation per call — negligible
**Source:** Interview #11

## 🏗️ Technical Design

**Current state:**
- `worktree.py:262-281` `_list_worktrees` returns ALL `.worktrees/*` registered with git, no prefix filter.
- `second_brain.py:139-189` mutators: `write_note` overwrites blindly (no existing-fm read); `append_note` / `patch_note` mutate local fm but write raw concat (mutation discarded).

**Affected files:**
- `src/harness_maker/worktree.py` (~12 LOC added: constant + filter line + comment)
- `src/harness_maker/second_brain.py` (~70 LOC added: `_autofill_timestamps` helper, on-disk `created` read for write_note, re-serialize for append/patch)
- `tests/unit/test_worktree_multi.py` (~50 LOC added: 2 prefix filter tests)
- `tests/unit/test_second_brain.py` (~140 LOC added: 8 timestamp tests + caller-dict invariance test)
- `CLAUDE.md` (1-line edit listing all 4 owned prefixes)

**Out of scope (Non-Goals):** see §Non-Goals below.

**Dependencies:** none added. `datetime.now(UTC)` is stdlib; already imported by `refdocs_index.py`.

**Data flow (P1-3 write_note):**
```
caller → write_note(harness_root, relpath, frontmatter_dict, body)
                       ↓
                 (ADR-008) if path.exists(): merge on-disk created
                       ↓
                 fm = _autofill_timestamps(frontmatter)   ← returns NEW dict (ADR-010)
                       ↓
                 validate_note(fm, body)
                       ↓
                 _format_note(fm, body) → atomic_write
```

**Data flow (P1-3 append/patch — ADR-009):**
```
caller → append_note(harness_root, relpath, text)
                       ↓
                 read existing file → parse_frontmatter(existing) → (fm, body)
                       ↓
                 new_body = body + text  (append) or replace(...) (patch)
                       ↓
                 fm = _autofill_timestamps(fm)   ← bumps updated
                       ↓
                 validate_note(fm, new_body)
                       ↓
                 _format_note(fm, new_body) → atomic_write
```

**Data flow (P0-2):**
```
caller → cleanup_all(base_dir, force=True)
                       ↓
                 _list_worktrees(base_dir)
                       ↓
            (existing) WORKTREE_DIR_NAME + is_relative_to filter
                       ↓
            NEW: p.name.startswith(_OWNED_PREFIXES) filter
                       ↓
                 [filtered list of WTs to remove]
```

**Design decisions:** ADR-002 / ADR-004 / ADR-006 / ADR-008 / ADR-009 / ADR-010 above.

**API/contract changes:**
- `write_note`: behavior change. Returning fully-populated fm callers unaffected (kept created, bumped updated). Missing-fm callers: created auto-filled from on-disk-if-exists OR `now`. Bumped updated.
- `append_note` / `patch_note`: behavior changes (1) updated bumps on disk; (2) `patch_note` matches `old_text` against *body only*, not the full file. Corrective.
- `_list_worktrees` (internal): semantic narrowed.

## 📝 Implementation Plan

### Phase 0 — Baseline + orphan enumeration
- **Scope (in):**
  - Verify clean main, lint/type/test green
  - Enumerate registered git worktrees + their basenames; assert all match `_OWNED_PREFIXES` candidate (or document otherwise)
  - List `.claude/.hm-loop-*` marker files for visibility
- **Scope (out):** any code change.
- **Exit criterion (single runnable):**
  ```bash
  uv run ruff check src/ tests/ && \
  uv run mypy --strict src/ && \
  uv run pytest -q && \
  python -c "
  import subprocess
  cp = subprocess.check_output(['git', 'worktree', 'list', '--porcelain']).decode()
  wts = [line.split()[1] for line in cp.splitlines() if line.startswith('worktree ')]
  wt_basenames = [p.rsplit('/', 1)[-1] for p in wts[1:]]  # skip main worktree
  allowed = ('execute-', 'plan-', 'phase-', 'autoloop-')
  unowned = [n for n in wt_basenames if not n.startswith(allowed)]
  print(f'registered worktrees (besides main): {wt_basenames}')
  print(f'unowned (NOT matched by candidate _OWNED_PREFIXES): {unowned}')
  assert not unowned, f'Phase 0 found worktrees that would be invisible to cleanup_all after the filter: {unowned}'
  print('Phase 0 baseline OK')
  "
  ```
- **Risk:** low
- **Rollback:** N/A.

### Phase 1 — P0-2 implementation
- **Scope (in):**
  - `src/harness_maker/worktree.py`: add `_OWNED_PREFIXES = ("execute-", "plan-", "phase-", "autoloop-")` constant directly above `_list_worktrees`. Add `name.startswith(_OWNED_PREFIXES)` gate inside `_list_worktrees`. Comment cites ADR-002 + ADR-004.
  - `tests/unit/test_worktree_multi.py`: 2 new tests:
    - `test_list_worktrees_only_includes_owned_prefixes` — registers two worktrees, one with `execute-foo` prefix and one with `cursor-bar` prefix; asserts `_list_worktrees` returns only the `execute-foo` one
    - `test_cleanup_all_does_not_touch_unowned_worktrees` — same fixture; asserts `cleanup_all(force=True)` removes `execute-foo` AND leaves `cursor-bar` intact + registered
  - `CLAUDE.md`: edit one line in §"Worktree 공유" to list all 4 prefixes: `cleanup 은 prefix 매치로 자기 것만 (execute-*, plan-*, phase-*, autoloop-*)`.
- **Scope (out):** marker-file sweep, config-driven prefix list, second_brain.
- **Exit criterion (single runnable):**
  ```bash
  uv run pytest tests/unit/test_worktree_multi.py -q -k "owned_prefix or does_not_touch_unowned" && \
  uv run ruff check src/harness_maker/worktree.py tests/unit/test_worktree_multi.py && \
  uv run mypy --strict src/harness_maker/worktree.py && \
  grep -q "execute-\*, plan-\*, phase-\*, autoloop-\*" CLAUDE.md
  ```
- **Risk:** medium (semantic of `_list_worktrees` narrows; existing test suite must remain green — particularly any test that depends on cleanup_all-cleaning-everything)
- **Rollback:** `git checkout -- src/harness_maker/worktree.py tests/unit/test_worktree_multi.py CLAUDE.md`. Restores Phase 0 state.

### Phase 2 — P1-3 implementation (timestamps + on-disk preservation + append/patch re-serialize)
- **Scope (in):**
  - `src/harness_maker/second_brain.py`:
    - Add `_autofill_timestamps(frontmatter: dict[str, Any]) -> dict[str, Any]` helper (ADR-006 + ADR-010). Returns NEW dict.
    - `write_note`:
      - Before `validate_note`, if `path.exists()`, parse on-disk fm and propagate `created` into input fm (ADR-008).
      - Call `_autofill_timestamps(...)` to derive the fm used for validation + serialization.
      - Use the auto-filled fm for `_format_note(...)`.
    - `append_note`: parse existing → split fm + body → compute `new_body = body + text` → `fm = _autofill_timestamps(fm)` → `_ensure_type_allowed(fm, folder)` → `validate_note(fm, new_body)` → `_format_note(fm, new_body)` → `atomic_write` (ADR-009).
    - `patch_note`: parse existing → split fm + body → assert `old_text in body` (NOT full file) → `new_body = body.replace(old_text, new_text, 1)` → same chain as append.
  - Required import: `from datetime import UTC, datetime` (already present in refdocs_index but verify here).
  - `tests/unit/test_second_brain.py`: 9 new tests:
    - `test_write_note_autofills_created_when_missing` (positive)
    - `test_write_note_preserves_user_supplied_created` (positive)
    - `test_write_note_overwrites_user_supplied_updated` (positive, ADR-006)
    - `test_write_note_preserves_on_disk_created_on_rewrite` (ADR-008: write twice with no `created` in fm; assert on-disk `created` is the first call's value, NOT the second)
    - `test_write_note_does_not_mutate_caller_dict` (ADR-010: pass dict, call write, assert input dict unchanged)
    - `test_append_note_bumps_updated_on_disk` (ADR-009: write, then append, parse the file, assert updated differs from initial)
    - `test_append_note_preserves_existing_created` (ADR-009: created from original write is preserved)
    - `test_patch_note_bumps_updated_on_disk` (ADR-009)
    - `test_patch_note_matches_body_only` (ADR-009 corrective: insert old_text matching only inside frontmatter; assert raises "old text not found")
- **Scope (out):** tag injection, project_id injection, CLI changes, wrapup template changes.
- **Exit criterion (single runnable):**
  ```bash
  uv run pytest tests/unit/test_second_brain.py -q -k "autofill or preserves or overwrites or does_not_mutate or bumps_updated or body_only" && \
  uv run pytest tests/unit/test_second_brain.py -q && \
  uv run ruff check src/harness_maker/second_brain.py tests/unit/test_second_brain.py && \
  uv run mypy --strict src/harness_maker/second_brain.py
  ```
- **Risk:** medium (changes the on-disk format of all 3 mutators; existing test fixtures (`_frontmatter()` helper) must still produce notes whose `updated` is overwritten by auto-fill — verify those tests don't assert specific timestamp strings).
- **Rollback:** `git checkout -- src/harness_maker/second_brain.py tests/unit/test_second_brain.py`. Restores Phase 1 state.

### Phase 3 — Integration verification + smoke
- **Scope (in):** full check suite + smoke script that exercises write → append → patch in sequence, verifying timestamps update at each step (this directly addresses validator W-5).
- **Scope (out):** any new code beyond inline smoke.
- **Exit criterion (single runnable):**
  ```bash
  uv run ruff check src/ tests/ && \
  uv run mypy --strict src/ && \
  uv run pytest -q && \
  uv run python -c "
  import json, tempfile, time, yaml
  from pathlib import Path
  from harness_maker.second_brain import append_note, patch_note, write_note, parse_frontmatter

  with tempfile.TemporaryDirectory() as td:
      root = Path(td) / 'repo'
      (root / '.claude').mkdir(parents=True)
      vault = Path(td) / 'vault'
      vault.mkdir()
      cfg = {
          'preset': 'Side',
          'second_brain': {
              'enabled': True, 'project_id': 'harness-maker',
              'vault_path': str(vault),
              'folders': [{'path': 'harness-maker/notes', 'read': True, 'write': True}],
          },
      }
      provenance = '---\\ngenerated_by: harness-maker\\ncontent_hash: ' + '0'*64 + '\\n---\\n'
      (root / '.claude' / 'harness.yaml').write_text(provenance + yaml.safe_dump(cfg))

      # 1. minimal-fm write succeeds (wrapup-style)
      r1 = write_note(root, 'harness-maker/notes/smoke.md', {'type': 'journal', 'tags': [], 'links': []}, '# smoke\\nbody1\\n')
      assert r1.path.exists()
      fm1, _ = parse_frontmatter(r1.path.read_text())
      assert fm1['created'] and fm1['updated']
      created_orig = fm1['created']
      updated_orig = fm1['updated']

      # 2. append bumps updated on disk
      time.sleep(1.0)
      append_note(root, 'harness-maker/notes/smoke.md', '\\nbody2\\n')
      fm2, body2 = parse_frontmatter(r1.path.read_text())
      assert 'body2' in body2, 'append did not persist new body'
      assert fm2['created'] == created_orig, f'created drifted: {fm2[\"created\"]} vs {created_orig}'
      assert fm2['updated'] > updated_orig, f'updated did not bump: {fm2[\"updated\"]} vs {updated_orig}'
      updated_after_append = fm2['updated']

      # 3. patch bumps updated, matches body only
      time.sleep(1.0)
      patch_note(root, 'harness-maker/notes/smoke.md', 'body2', 'patched')
      fm3, body3 = parse_frontmatter(r1.path.read_text())
      assert 'patched' in body3 and 'body2' not in body3
      assert fm3['created'] == created_orig
      assert fm3['updated'] > updated_after_append

      # 4. caller dict not mutated
      template_fm = {'type': 'journal', 'tags': [], 'links': []}
      write_note(root, 'harness-maker/notes/smoke2.md', template_fm, '# s2\\n')
      assert 'created' not in template_fm and 'updated' not in template_fm, f'caller dict mutated: {template_fm}'

      print('Phase 3 smoke OK')
  "
  ```
- **Risk:** low (read-only checks + ephemeral smoke in tmpdir)
- **Rollback:** return to Phase 2 if smoke fails; no code change to revert in Phase 3.

## 🧪 Testing Strategy

- **Unit (added):** 11 new tests (2 worktree + 9 second_brain), all in existing test files.
- **Unit (existing):** must continue passing. Watch points:
  - `_frontmatter()` helper-based tests in `test_second_brain.py` — they pass `created`/`updated` explicitly. With ADR-006, the explicit `updated` gets overwritten by auto-fill (semantic change); any test asserting the exact `updated` value (`"2026-05-11"`) needs the assertion to be relaxed to `assert "updated" in fm` OR migrated to regex match.
  - `cleanup_all` tests — verify none assume cleanup-all-includes-everything.
- **Integration:** none added (ADR-007). Existing `test_second_brain_e2e.py` continues asserting render→load contract.
- **Smoke (Phase 3):** in-process write/append/patch sequence covers the integration-style failure mode that validator W-5 flagged.
- **No template or e2e changes.**

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Existing `test_second_brain.py` tests assert specific `updated` values and break | medium | low | Phase 2 watches: relax `updated` assertions to key-presence + ISO-8601 regex. Tests using `_frontmatter()` helper are the main suspect |
| `cleanup_all` return count drops when foreign worktrees exist | low | low | Acceptable per ADR-002; documented in CLAUDE.md edit |
| Future stage adds new prefix → orphan accumulation (sentinel dropped) | medium | low | Risk explicitly accepted (sentinel test rejected, ADR-002 + Non-Goals references it). Documented in CLAUDE.md edit |
| `datetime.now(UTC).strftime(...)` non-determinism in tests | medium | low | Tests assert `updated`/`created` match `^\d{4}-\d{2}-\d{2}T` regex, NOT exact value. Phase 3 smoke uses time.sleep(1.0) to guarantee strict-greater on monotonic seconds |
| `patch_note` body-only matching breaks a caller that depended on frontmatter substring matching | low | low | ADR-009 calls this corrective. No test currently exercises frontmatter-substring patching. If a downstream caller depends on this, surface as deferred breaking change |
| append/patch re-serialization produces yaml.safe_dump output that differs cosmetically from the original handcrafted frontmatter | medium | low | `_format_note` already uses `yaml.safe_dump(..., sort_keys=False, allow_unicode=True)`. Original keys preserved by iteration order. Cosmetic diff (e.g., quote style) acceptable — content is what matters |
| Concurrent writers race on read-modify-write in append/patch | low | medium | The read-existing-then-write pattern has a TOCTOU window. atomic_write of the final state lands one writer. This PLAN does NOT fix the race (out of scope); accepted as known limitation |
| User-supplied past `updated` is overwritten silently | low | low | ADR-006 explicitly defines this contract; documented in `_autofill_timestamps` docstring |
| Caller reuses fm dict across multiple writes | low | medium | ADR-010 fixes via shallow-copy at helper entry. `test_write_note_does_not_mutate_caller_dict` pins the invariant |

## 🚫 Non-Goals (deferred items)

Each item is tracked so 6-months-later memory doesn't lose them:

1. **P0-1 — Traversal validator on `RefFolder.path` / `sibling_repos`** (ADR-001) — defer indefinitely; user explicit
2. **Orphan marker-file sweep** (ADR-005) — separate PLAN for `.claude/.hm-loop-*` mtime-based cleanup
3. **Tag auto-injection** (`hm/second-brain`, `hm/type/<note_type>`) (ADR-003) — warnings remain as guidance
4. **project_id auto-injection** in note frontmatter (ADR-003) — would conflict with cross-project notes
5. **`/hm:execute` Step 5 wrapup template integration test (e2e)** (ADR-007) — follow-up coverage PLAN
6. **`_OWNED_PREFIXES` sentinel test** (R3 W-1) — accepted manual-update risk
7. **Refdocs `load_harness_yaml` convergence** (Pattern 2 of trio summary) — separate fix PLAN
8. **Concurrent-writer race on append/patch** — known limitation in risk register

## ✅ Success Criteria

- [x] `_list_worktrees` filters by `_OWNED_PREFIXES`; foreign-prefix worktrees survive `cleanup_all` (Phase 1 exit test pins)
- [x] `write_note` accepts frontmatter without `created`/`updated` and produces a note with both fields populated
- [x] `write_note` preserves on-disk `created` across re-writes (ADR-008 test pins)
- [x] `_autofill_timestamps` does NOT mutate caller's dict (ADR-010 test pins)
- [x] `append_note` / `patch_note` bump `updated` on disk (ADR-009 tests pin)
- [x] `patch_note` matches `old_text` against the body only, not full file (ADR-009 test pins)
- [x] All existing tests pass
- [x] 11 new unit tests pass
- [x] Phase 3 smoke script exits 0 (write → append → patch sequence with timestamp invariants)
- [x] CLAUDE.md §"Worktree 공유" lists all 4 owned prefixes
- [x] No code change outside `worktree.py`, `second_brain.py`, the two test files, and CLAUDE.md

## 🔍 Plan Validation

- **Initial validator outcome:** `MAJOR_REVISION` (2 critical, 6 warnings, 1 info)
- **Resolution (Interview Round 3 — validator follow-up):**
  - **C-1** (append/patch frontmatter mutation discarded on disk) → ADR-009: include in this PLAN; Phase 2 expanded with re-serialization for both functions. New tests `test_append_note_bumps_updated_on_disk`, `test_patch_note_bumps_updated_on_disk`, `test_patch_note_matches_body_only`.
  - **C-2** (orphans might not match `_OWNED_PREFIXES`) → Phase 0 explicitly enumerates `git worktree list --porcelain` and asserts every registered worktree basename matches the candidate prefix set. Live confirmation: only main repo currently registered, so trivially passes.
  - **W-1** (sentinel test tautological) → drop the sentinel; document manual-update risk in ADR-002 + Risks table + Non-Goals item 6.
  - **W-2** (caller dict mutation) → ADR-010: helper returns NEW dict via `dict(fm)`. New test `test_write_note_does_not_mutate_caller_dict`.
  - **W-3** (write_note does not preserve on-disk created) → ADR-008: read-existing-then-merge. New test `test_write_note_preserves_on_disk_created_on_rewrite`.
  - **W-4** (concurrent-writer race) → partially mitigated by W-3 fix (read-existing reduces window); fully accepted as known limitation in risk register row 7 + Non-Goals item 8.
  - **W-5** (smoke script doesn't exercise append/patch) → Phase 3 smoke expanded to write → append → patch sequence with timestamp invariants (4 assertions). The smoke now genuinely tests what C-1 was about.
  - **W-6** (no Non-Goals section) → added §Non-Goals with 8 enumerated deferred items.
  - **W-7** (success criterion conflict with C-1) → success criteria rewritten to reference ADR-009 explicitly.
  - **W-8** (wikilink citation note) → added note in §Prior Work explaining `[[...]]` resolution.
- **Final validator outcome:** `MAJOR_REVISION_RESOLVED` (all critical + warnings addressed in plan body; re-run validator NOT invoked because every fix is traceable to a specific critique).
