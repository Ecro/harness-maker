---
type: plan
task_slug: cursor-mdc-orphan-sweep
status: complete
created: 2026-05-28
tags: [harness-maker, plan, python, reconcile, orphan-sweep, cursor]
interview_rounds: 2
adrs: 5
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Fix orphan-sweep classifier gap that leaks provenance-stripped .mdc; ship 0.26.5; clean spoton"
---

# PLAN — cursor-mdc-orphan-sweep

## 🎯 Executive Summary

**TL;DR:** `~/spoton` is correctly on harness-maker **0.26.4** for all 92 manifest-managed
files, but a stale `.cursor/rules/harness.mdc` lingers after `cursor` was intentionally
dropped from `targets`. Root cause is a classifier gap in `reconcile._classify_orphan`:
a file with YAML frontmatter but **no `generated_by: harness-maker`** short-circuits to
`("theirs", KEEP)` *before* the render-manifest hash check that already sweeps pure-JSON
orphans. Because `.cursor/rules/*.mdc` is rendered with provenance deliberately stripped
(Cursor strict-rejects unknown frontmatter keys), it can never reach that check.

**What / Why:** Add the render-manifest full-file-hash check to the non-harness-provenance
frontmatter branch — mirroring the proven no-frontmatter branch. This makes unmodified,
blueprint-orphaned `.cursor/rules/*.mdc` (and `.cursor/commands/*.md`) sweepable while
preserving the R4 safety property (never delete what we cannot fingerprint as ours).

**Key Decisions:**
- cursor drop was intentional → clean up residue, do NOT re-add (→ ADR-001)
- fix scope = RC1 only, the classifier gap; legacy pre-tracking `.sh` untouched (→ ADR-002)
- preserve R4 — never auto-delete unfingerprintable files (→ ADR-003)
- no empty-directory pruning — file-only unlink, minimal change (→ ADR-004)
- ship via 0.26.5 patch bump → re-render spoton (→ ADR-005)

**Estimated impact:** ~1 line of behavior change in `_classify_orphan` + 5 regression
cases. Generalizable: fixes the leak for every consumer that drops a target whose assets
were rendered as pure-text. spoton residue removed on its 0.26.5 re-render.

## 📚 Prior Work

- **CLAUDE.md checkpoint #5** (fingerprint-based auto-upgrade vs preserve) — this fix is a
  textbook application: use `content_hash` to decide "ours" vs "theirs".
- **CLAUDE.md R4 safety property** (reconcile.py:536-539) — user-owned files under the
  five render roots that the renderer never wrote lack frontmatter AND have no manifest
  entry → "theirs"/KEEP. The fix must not erode this.
- **render.py:490-504** `_render_pure_text` — documents WHY provenance is sacrificed for
  `.cursor/rules/*.mdc` / `.cursor/commands/*.md` / `.sh` (external parser strict-reject).
  This is the upstream reason the orphan classifier cannot see our provenance.
- **Empirical forensic (this session, 2026-05-28):** live `.cursor/rules/harness.mdc`
  full-file sha256 `998eece03cd5…1448` == its `.hm-render-manifest.jsonl` entry → proven
  unmodified harness output. The pure-JSON siblings `.cursor/hooks.json` / `.cursor/mcp.json`
  were already swept on the 5/28 re-render (they hit the no-frontmatter branch); only the
  `.mdc` survived. The manifest path key is exactly `.cursor/rules/harness.mdc`, identical
  to the sweep's on-disk rel_key → the fix will fire on the next render.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Cursor 의도 | Scope | cursor가 targets에서 빠진 것이 의도된 제거인가? | 의도된 제거 — cursor 안 씀 | 잔재 정리 방향 | ADR-001 |
| 2 | 수정 범위 | Scope | root-cause 수정 범위 | RC1만 (orphan-sweep 분류기 갭) | legacy .sh 미포함 | ADR-002 |
| 3 | Sweep 안전성 | Risk | fingerprint 없는 legacy 파일 정책 | R4 유지 — auto-delete 금지 | health surface는 별건 | ADR-003 |
| 4 | 빈 dir 정리 | Architecture | 삭제 후 빈 .cursor/ 디렉토리 prune? | 파일만 unlink, 빈 dir 남김 | 변경 최소화 | ADR-004 |
| 5 | 배포 방식 | Phasing | spoton에 fix 적용/배포 경로 | 0.26.5 bump → spoton 재렌더 | 모든 consumer 혜택 | ADR-005 |

Follow-up (validator NEEDS_REVISION resolution, all accepted as plan revisions — no user-facing
trade-off, defensible-default per deep-gate "never ask trivial/obvious"): added regression case
(d) path-scoping + byte-exact perturbation case; inserted pre-release real-residue validation
gate (Phase 2) ahead of the irreversible release; made Phase 5 exit a concrete diff allowlist;
corrected edited-`.mdc` KEEP narrative. See §🔍 Plan Validation.

## 📐 Architecture Decision Records

### ADR-001: Treat the cursor-target drop as intentional; clean up residue
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** spoton's `harness.yaml targets` changed to `[claude-code, codex]` between 5/24
and 5/28, orphaning `.cursor/rules/harness.mdc`. The fix direction depends on whether cursor
should stay.
**Decision:** cursor is no longer used. The goal is to remove the stale `.cursor/` asset, not
re-add cursor to targets.
**Consequences:**
- ✅ Aligns the on-disk state with the declared `targets`.
- ⚠️ The general orphan-sweep bug (next ADRs) must be fixed for the cleanup to be automatic.
**Rejected alternatives:**
- Re-add cursor to targets — Rejected: user confirmed cursor is intentionally dropped.
**Source:** Interview #1

### ADR-002: Fix scope = RC1 only (the `_classify_orphan` gap)
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** Two orphan classes exist in spoton — (A) `.cursor/rules/harness.mdc` with a
matching render-manifest hash, and (B) legacy `.sh` (statusline 5/4, hooks 3/17) that predate
render-manifest tracking and have no fingerprint.
**Decision:** Fix only RC1 — the classifier gap that fails to sweep provenance-stripped but
manifest-recorded files. Do not change policy for class B.
**Consequences:**
- ✅ Tight, generalizable, high-confidence change.
- ⚠️ Class-B legacy `.sh` residue remains (handled by ADR-003's keep policy).
**Rejected alternatives:**
- RC1 + legacy `.sh` cleanup policy — Rejected: broad scope, would pressure the R4 guarantee.
- spoton-only manual delete — Rejected: leaves the root cause unfixed for other consumers.
**Source:** Interview #2

### ADR-003: Preserve the R4 safety property — never auto-delete unfingerprintable files
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** Files rendered before `.hm-render-manifest.jsonl` existed (timeline starts 5/22)
have no recorded hash, so the sweep cannot prove ownership.
**Decision:** The sweep deletes a file only when its current full-file hash matches a
render-manifest entry **under the same path key**. No content-heuristic deletion. Files with
no manifest entry stay KEPT.
**Consequences:**
- ✅ Zero data-loss risk for user files and untrackable legacy residue.
- ⚠️ Legacy `.sh` residue is not auto-removed (acceptable; surfacing it in `/hm:health` is a
  separate, out-of-scope improvement).
**Rejected alternatives:**
- Heuristic/path-pattern deletion of legacy residue — Rejected: violates R4, risks user-file deletion.
**Source:** Interview #3

### ADR-004: No empty-directory pruning — file-only unlink
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** After the `.mdc` (the only file under `.cursor/rules/`) is swept, `.cursor/rules/`
and `.cursor/` become empty directories.
**Decision:** Keep the current `sweep_orphans` behavior — unlink files only; leave empty
directories. Empty `.cursor/` is harmless.
**Consequences:**
- ✅ Minimal diff; no new directory-traversal/removal logic to get wrong.
- ⚠️ An empty `.cursor/` directory remains on disk (cosmetic).
**Rejected alternatives:**
- Bottom-up rmdir of emptied render-root subtrees — Rejected: extra surface area for no
  functional gain; user chose minimal change.
**Source:** Interview #4

### ADR-005: Ship via 0.26.5 patch bump, then re-render spoton
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** spoton loads harness-maker from the `harness-maker-local` marketplace **cache**
snapshot (`…/cache/harness-maker-local/harness-maker/0.26.4`), not the live dev repo. The fix
only reaches spoton after the cache holds the fixed code.
**Decision:** Bump 0.26.4 → 0.26.5 (5-file version sync + CHANGELOG), release via the
`release.yml` tag-push pipeline, then re-render spoton with 0.26.5 so the fixed sweep removes
the orphan.
**Consequences:**
- ✅ Every consumer benefits; spoton remediation is verified end-to-end (orphan-sweep report).
- ⚠️ Public version churn if the release ships unvalidated — mitigated by the Phase 2
  pre-release validation gate against spoton's real residue (see ADR-002 of validator
  resolution / §Implementation Plan).
**Rejected alternatives:**
- Local editable re-render without release — Rejected: other consumers stay unfixed; user
  wants the released fix. (Editable install is still used in Phase 2 for pre-release validation.)
**Source:** Interview #5

## 🏗️ Technical Design

### Current State
`src/harness_maker/reconcile.py::_classify_orphan` (lines 415-469) classifies each
blueprint-orphaned file under the five render roots:

```
fm = parse_frontmatter(file)
if fm and fm["generated_by"] == "harness-maker":      # our provenance present
    recorded = fm["content_hash"]
    if recorded != recompute(body): return ours-modified  # KEEP
    if recorded in manifest[path]:  return ours-clean      # DELETE
    return missing-in-manifest                              # KEEP
if fm is not None:               # ← LINE 463: frontmatter present, NOT our provenance
    return ("theirs", None)      # ← BUG: KEEP forever, manifest never consulted
# no frontmatter (pure-json / pure-toml / binary / .sh):
if current_hash in manifest[path]: return ours-clean       # DELETE
return ("theirs", None)                                     # KEEP
```

`.cursor/rules/harness.mdc` has Cursor frontmatter (`description`/`globs`/`alwaysApply`) but
no `generated_by`, so it lands at **line 463** and is kept — even though its full-file hash is
recorded in the manifest. Pure-JSON `.cursor/hooks.json` / `.cursor/mcp.json` have no
frontmatter, hit the bottom branch, match the manifest, and are correctly deleted. This
asymmetry is the entire defect.

### Affected Components
- `src/harness_maker/reconcile.py` — `_classify_orphan` (single behavior change).
- `tests/unit/test_reconcile_orphan_sweep.py` — regression cases.
- Version files (5) + `CHANGELOG.md` — release.
- `~/spoton` (separate repo) — remediation target.

### Dependencies
None added. Uses existing `_load_render_manifest`, `_sha256_bytes`, `parse_frontmatter`.

### Architecture / Design Decision (→ ADR-002, ADR-003)
Insert the manifest full-file-hash check into the `fm is not None` branch, *before* the
`("theirs", None)` return — identical shape to the no-frontmatter branch (reconcile.py:467):

```python
if fm is not None:
    # Frontmatter present but not harness-maker provenance. Could still be ours:
    # pure-text renders (.cursor/rules/*.mdc, .cursor/commands/*.md) carry only the
    # external consumer's frontmatter and have OUR provenance stripped (render.py:490),
    # but the render manifest records their full-file hash. Consult it — same per-path
    # scoping the no-frontmatter branch relies on — before declaring "theirs".
    if current_hash in manifest.get(rel_key, set()):
        return ("ours-clean", current_hash)
    return ("theirs", None)
```

**Why this preserves R4 (per-path scoping is load-bearing):** the check is
`manifest.get(rel_key, ...)`, keyed on the orphan's own path. A user-authored `.mdc` has no
manifest entry under its path → falls through to `("theirs", None)` → KEEP. A harness `.mdc`
the user edited has a full-file hash absent from the manifest → KEEP. Only a byte-identical-
to-manifest, blueprint-orphaned file is deleted.

**Narrative correction (validator C5):** for `.mdc` the edited-file KEEP is guaranteed by the
hash *missing* from `manifest[rel_key]` → fall-through to `("theirs", None)` at the new
branch — NOT by the `generated_by == harness-maker` "ours-modified" path (which `.mdc` never
reaches, having no `generated_by`).

**Byte-exact, not body-normalized (validator C1):** the comparison uses
`current_hash = sha256(raw_file_bytes)` against the manifest's `body_sha256`. For pure-text
renders these are equal because `_render_pure_text` (render.py:508-513) writes exactly the
normalized bytes it hashed, with nothing appended; raw-read returns identical bytes. No guard
is added (it would diverge `.mdc` from the proven no-frontmatter branch); the invariant is
pinned by a test instead.

### Data Flow (before → after)
```
.cursor/rules/harness.mdc  (Cursor fm, no generated_by; cursor dropped from blueprint)
  BEFORE: parse_frontmatter → fm≠None, no generated_by → line 463 → ("theirs") → KEEP   [leak]
  AFTER : parse_frontmatter → fm≠None, no generated_by → 998eece0 ∈ manifest[".cursor/
          rules/harness.mdc"] → ("ours-clean") → unlink → report.deleted               [fixed]
```

### API Changes
None. `_classify_orphan` signature and return contract unchanged; only an additional code
path before an existing return.

## 📝 Implementation Plan

### Phase 1 — Fix `_classify_orphan` + regression tests
- **depends_on:** []
- **parallel_group:** serial-fix
- **merge_hazards:** none
- **Scope (in):** `src/harness_maker/reconcile.py` (the `fm is not None` branch);
  `tests/unit/test_reconcile_orphan_sweep.py`.
- **Scope (out):** render.py, CLI, version files, any `.sh` handling.
- **Regression cases (all in test_reconcile_orphan_sweep.py):**
  - (a) orphaned `.cursor/rules/x.mdc` with Cursor-only frontmatter whose full-file hash IS
    in the manifest under its path → classified `ours-clean` → deleted.
  - (b) user-authored `.cursor/rules/user.mdc`, no manifest entry → `theirs` → KEEP.
  - (c) harness `.mdc` edited (current hash ≠ manifest) → `theirs` → KEEP.
  - (d) **path-scoping R4 guard:** orphan `.mdc` whose byte-hash exists in the manifest only
    under a *different* path key → KEEP. (Locks that the lookup is `manifest[rel_key]`, not a
    global hash set — the single most important R4 guard.)
  - (e) **byte-exact invariant:** same logical `.mdc` body but with a trailing-newline / CRLF
    perturbation (hash differs from manifest) → KEEP. Documents that the sweep is byte-exact,
    and that sweep safety depends on `_render_pure_text` writing normalized bytes verbatim.
- **Exit criterion:** `uv run pytest tests/unit/test_reconcile_orphan_sweep.py -q` green AND
  full `uv run pytest` green AND `uv run mypy --strict src/` clean.
- **Risk:** medium (sweep deletes files; correctness is safety-critical).
- **Rollback point:** revert `reconcile.py` to current HEAD.

### Phase 2 — Pre-release validation against spoton's REAL residue (gate before any release)
- **depends_on:** [1]
- **parallel_group:** serial-fix
- **merge_hazards:** none
- **Scope (in):** a read-only fixture/test that copies spoton's actual
  `~/spoton/.cursor/rules/harness.mdc` + `~/spoton/.claude/.hm-render-manifest.jsonl` into a
  temp project root, builds a blueprint with `targets=[claude-code, codex]` (no cursor), runs
  `sweep_orphans`, and asserts the `.mdc` is in `report.deleted`. Run against an **editable**
  install of the Phase-1 code (no version bump yet, no tag).
- **Scope (out):** mutating real spoton; tag push; PyPI.
- **Exit criterion:** the temp-fixture `sweep_orphans` deletes `.cursor/rules/harness.mdc`
  (present in `report.deleted`) using spoton's real manifest — proving the manifest-key match
  and the fix on real data BEFORE the irreversible release.
- **Risk:** low (read-only copy into tmp; no real-FS mutation).
- **Rollback point:** Phase 1 state (delete the fixture; no release happened).

### Phase 3 — Version bump 0.26.5 + CHANGELOG
- **depends_on:** [2]
- **parallel_group:** serial-release
- **merge_hazards:** the 5 version files must move together (`.claude-plugin/plugin.json`,
  `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`,
  `src/harness_maker/__init__.py`) + `CHANGELOG.md` — serial, single commit.
- **Scope (in):** the 5 version files + CHANGELOG entry describing the orphan-sweep fix.
- **Scope (out):** code logic (frozen after Phase 1).
- **Exit criterion:** `grep -rl '0.26.5'` shows all 5 files; CHANGELOG has a 0.26.5 entry;
  no file still reads 0.26.4 among the five.
- **Risk:** low.
- **Rollback point:** Phase 2 state.

### Phase 4 — Release (tag push → release.yml)
- **depends_on:** [3]
- **parallel_group:** serial-release
- **merge_hazards:** none (post-commit operation).
- **Scope (in):** advisory boundary tests locally
  (`INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v`), then
  `git tag -a v0.26.5 -m "…"; git push origin main v0.26.5`. **User-initiated push only**
  (git policy: no auto-push). Do NOT run `gh release create` (documented 0.15.3 race).
- **Scope (out):** any manual release-page creation.
- **Exit criterion:** `gh run list --workflow release.yml` shows the v0.26.5 run green
  (quality-gate → build → publish-testpypi → publish-pypi → github-release).
- **Risk:** medium — **irreversible** once published; fix-forward only via a new patch tag.
- **Rollback point:** none (immutable); forward-fix with 0.26.6 if needed. Phase 2 gate is
  the guard that makes this acceptable.

### Phase 5 — Remediate & confirm spoton
- **depends_on:** [4]
- **parallel_group:** serial-remediation
- **merge_hazards:** none (separate repo `~/spoton`; no harness-maker merge interaction).
- **Scope (in):** refresh spoton's plugin cache to 0.26.5 (`/plugin update` or local
  marketplace re-sync), re-render via `/hm:make --update`, inspect the orphan-sweep report.
- **Scope (out):** committing spoton (left to the user); touching legacy `.sh` (R4 keeps them).
- **Exit criterion (concrete allowlist — validator C4):**
  1. `test ! -f ~/spoton/.cursor/rules/harness.mdc` (file absent), AND
  2. the `/hm:make --update` orphan-sweep report lists `.cursor/rules/harness.mdc` under
     **deleted** (proves `ours-clean` classification, not mere absence), AND
  3. `git -C ~/spoton status --short` changes are limited to {the deleted `.mdc`, a new
     `.backup-*` dir, observability writes} — no unexpected managed-file churn, AND
  4. `.claude/lib/*.sh` and `.claude/hooks/*.sh` still present (R4 / ADR-003 confirmed).
- **Risk:** medium (real-FS mutation on spoton).
- **Rollback point:** spoton auto-creates a `.backup-<ts>` before re-render; restore from it.

## 🧪 Testing Strategy

- **Unit (Phase 1):** 5 cases (a–e) above in `tests/unit/test_reconcile_orphan_sweep.py`,
  mock-only, deterministic. Cases (d) and (e) are the R4 / byte-exact safety locks.
- **Integration / real-data (Phase 2):** read-only fixture using spoton's actual `.mdc` +
  `.hm-render-manifest.jsonl` to validate against production residue before release.
- **Release advisory (Phase 4):** `INTEGRATION=1 … test_boundary_*.py` per CLAUDE.md release
  procedure (advisory, also re-run by `release.yml` `boundary-advisory`).
- **Manual (Phase 5):** spoton re-render + orphan-sweep-report inspection + git-diff allowlist.

## ⚠️ Risks & Mitigation

| Risk | Sev | Mitigation |
|------|-----|------------|
| Manifest-hash check deletes a user file | high | Per-path scoping (`manifest[rel_key]`); user files have no entry under their path. Locked by test (d). |
| `current_hash` (raw) ≠ manifest (normalized) breaks the match silently in future | med | `_render_pure_text` writes normalized bytes verbatim (render.py:508-513); empirically verified for spoton's `.mdc`. Pinned by test (e); no guard (would diverge from proven branch). |
| spoton manifest path key ≠ sweep rel_key → delete never fires | med | Verified: manifest records `.cursor/rules/harness.mdc`, matching disk rel_key. Re-confirmed end-to-end by Phase 2 against real manifest before release. |
| Public release ships an unvalidated fix → version churn | med | Phase 2 pre-release gate validates on real residue before the irreversible Phase 4 tag push. |
| Release race (manual `gh release create`) | low | CLAUDE.md race-free procedure — tag push only, let `release.yml` create the GitHub Release. |
| Over-sweep of other provenance-stripped files (`.cursor/commands/*.md`, `.sh`) | low | Intended: those become sweepable only when byte-identical to a manifest entry AND blueprint-orphaned. Legacy `.sh` predate tracking (no entry) → still KEEP (R4). |

## ✅ Success Criteria

- [x] `_classify_orphan` consults the manifest in the non-harness-provenance frontmatter branch.
- [x] Regression cases (a)–(e) pass; full suite + `mypy --strict` green.
- [x] Phase 2 fixture deletes spoton's real `.cursor/rules/harness.mdc` (pre-release).
- [x] All 5 version files + CHANGELOG at 0.26.5 (`release.yml` v0.26.5 run triggered by this wrapup's tag push — Phase 4).
- [x] REVIEW grade A / APPROVED, `drift_verdict: clean`.

**⏳ Deferred to Phase 5 (post-release, separate step — needs the released/cached 0.26.5 + the spoton repo):**
- After spoton 0.26.5 re-render: `.cursor/rules/harness.mdc` absent, listed deleted in the orphan-sweep report, git diff within the allowlist.
- Legacy `.claude/lib/*.sh` and `.claude/hooks/*.sh` still present (R4 preserved).

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION → **resolved** (no critical findings; diagnosis and
one-line fix confirmed correct against source). All five warnings/suggestions folded into the
plan as revisions (defensible-default; no user-facing trade-off requiring a new interview round):

| # | Validator finding | Severity | Resolution |
|---|-------------------|----------|------------|
| C1 | normalization-equivalence is silent/fragile; no guard, pin with test | warning | Added test case (e) byte-exact perturbation; explicitly no phase-1 guard. |
| C2 | missing path-scoping test → future global-lookup refactor silently deletes colliding user files | warning | Added test case (d) — hash present under a *different* path → KEEP. |
| C3 | Phase 4 (spoton) depended on full irreversible release before first real-data validation | warning | Inserted Phase 2 pre-release validation gate against spoton's real residue/manifest. |
| C4 | Phase exit "no unexpected changes" subjective | warning | Phase 5 exit is now a 4-item concrete allowlist (file absent + report-deleted + git-diff allowlist + R4 .sh present). |
| C5 | edited-`.mdc` KEEP narrative attributed to wrong branch | suggestion | Corrected in §Technical Design: KEEP via hash-miss fall-through (reconcile.py:464), not the ours-modified path. |

**Clean categories (validator):** rollback-strategy, adr-completeness, scope-drift-hazards,
missing-interview-rounds, spec-alignment.

## 🚦 Execution Status (2026-05-28, /hm:execute)

| Phase | Status | Notes |
|---|---|---|
| 1 — `_classify_orphan` fix + 5 regression tests (a–e) | ✅ DONE | reconcile.py:463 branch now consults manifest by per-path full-file hash; test-reviewer PASS; RED→GREEN confirmed (only case (a) was RED pre-fix). |
| 2 — pre-release validation vs spoton's REAL residue | ✅ DONE | `/tmp/validate_spoton_mdc.py` copied spoton's actual `.cursor/rules/harness.mdc` + real 216KB manifest → fixed sweep classified ours-clean → deleted. PASS. |
| 3 — 0.26.5 bump (5 files + CHANGELOG) + snapshot regen | ✅ DONE | 5-file sync verified; uv.lock re-pinned; 8 synthesize snapshots regenerated **from main** (per `[fail:test] snapshot-regen-inside-worktree`), 1-line (version) delta each. |
| 4 — release (tag push → release.yml) | ⏳ PENDING (user) | Out of execute scope — git policy: push is user-initiated. Run after wrapup commits. |
| 5 — spoton remediation (re-render with 0.26.5) | ⏳ PENDING (post-release) | Needs released/cached 0.26.5 + the spoton repo. Cross-repo; runs after Phase 4. |

**Phase D verification (all GREEN from main):** ruff check ✓ · ruff format ✓ · `mypy --strict src/` ✓ · full `tests/unit/` ✓ (incl. regenerated snapshots).

**Stage exit:** 17 files staged on `main`, NO commit (wrapup owns it). HEAD unchanged at `6232adb`. Worktree `execute-c50684ab98cf-20260528T0401Z` finalized stage-only + cleaned. No scope contamination.
