---
type: plan
task_slug: reconcile-schemas-always-replace
status: complete
created: 2026-06-03
tags: [harness-maker, plan, python, reconcile, render, codex]
interview_rounds: 1
adrs: 1
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Force-REPLACE .claude/schemas/*.json on reconcile so rendered schema fixes reach existing installs"
---

# PLAN: reconcile-schemas-always-replace

## 🎯 Executive Summary

**TL;DR** — `reconcile()` returns `KEEP("no-frontmatter")` for any rendered file without provenance frontmatter. `.claude/schemas/*.json` (pure-JSON codex `--output-schema` contracts) hit that branch, so `/hm:make --update` **never overwrites an existing schema**. The 0.28.7 `codex-finding.schema.json` strict-mode fix therefore reaches **fresh installs only** — existing installs (the population with the bug) keep their broken schema. Add a forced-REPLACE reconcile branch for `.claude/schemas/*.json`, mirroring the `settings.json`/`config-always-replace` precedent.

**What/Why** — schemas are machine artifacts with **zero user-editable content** (a fixed contract consumed by `codex exec`), so REPLACE-on-render is the correct semantics; KEEP (the default for frontmatter-less files) freezes them forever.

**Key decision** — ADR-001: `.claude/schemas/*.json` → forced REPLACE via a single shared schema-path predicate (no render change; reconcile-only).

**Estimated impact** — `reconcile.py` (one branch) + a shared predicate reuse + unit/equivalence/CLI-boundary tests + patch bump 0.28.7→0.28.8. The reconcile fix itself reaches existing installs (it's Python code re-fetched on `/plugin update`, not a rendered artifact — so it doesn't suffer the bug it fixes).

## 📚 Prior Work

- **PLAN-codex-finding-schema-strict-mode** — the 0.28.7 fix whose reach this gap limits. Its execution log already flagged the live-schema KEEP behavior; this PLAN is the root-cause fix.
- `[wiki:gotcha] reconcile-phantom-hash-heal` — direct precedent for flipping `KEEP→REPLACE` for a scoped file class (the phantom-hash heal). Same shape: a class of files that KEEP-froze forever, fixed by a targeted reconcile branch.
- `[wiki:gotcha] orphan-sweep-keeps-provenance-stripped-renders` — the per-path manifest-hash check lives in the **orphan sweep** (`_classify_orphan`), NOT main `reconcile()`. Confirms the main loop's no-frontmatter branch is unconditional KEEP.
- `[wiki:architecture] codex-second-llm-integration` ADR-008 — schemas are pure JSON, no provenance, rendered via `_render_pure_json`; `render._is_schemas_json` predicate already exists.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Fix scope | Scope/architecture | schemas-only REPLACE vs whole-class vs generic predicate? | **Surgical: `schemas/*.json` REPLACE only** | mcp.json/.mdc are the same KEEP-forever class BUT carry user content (servers / rule prose) → need MERGE not REPLACE → separate task. | ADR-001 |

**Skipped (gate):** REPLACE-vs-MERGE for schemas (locked — zero user-extensible structure; confidence ≥0.95); always-REPLACE-vs-hash-guarded (locked — we *want* to overwrite the stale render; `backup()` covers recovery); testing depth (resolved by validator W3 → CLI-boundary test).

## 📐 Architecture Decision Records

### ADR-001: `.claude/schemas/*.json` → forced REPLACE on reconcile
**Status:** Accepted (2026-06-03, via /hm:plan interview)
**Context:** `reconcile()` 231-239 returns `KEEP("no-frontmatter")` unconditionally for frontmatter-less rendered files. Pure-JSON schemas have no provenance frontmatter (ADR-008), so they freeze on every re-render — rendered schema fixes never reach existing installs.
**Decision:** Add a path-based forced-REPLACE branch for `.claude/schemas/*.json` in reconcile's special-case block (160-230), **before** the no-frontmatter KEEP at 231. Use a **single shared schema-path predicate** so reconcile and render agree on "what is a schema" (see Technical Design). `reason="schema-always-replace"`. No render change — `cli.py` keeps REPLACE paths in the blueprint and the existing `_is_schemas_json` → `_render_pure_json` dispatch writes them.
**Consequences:**
- ✅ Existing installs get rendered-schema updates on `/hm:make --update`.
- ⚠️ A hand-edited schema is overwritten on re-render — accepted: schemas have zero user-editable content by design, and `cli.py` `backup()` snapshots `.claude/` before render (recoverable under `.backup-<ts>/`).
**Rejected alternatives:**
- MERGE — rejected: schemas have no user-extensible structure / no `@hm:user:` markers (JSON can't carry them); nothing to merge.
- Leave KEEP — rejected: the fix never reaches existing installs (the whole point).
- Generic "zero-user-content" predicate — rejected: over-match risk; no defensible boundary today.
- Whole-class incl. `.cursor/mcp.json` / `.cursor/rules/*.mdc` — rejected: those carry **user content** (user-added MCP servers; user rule prose) → REPLACE would clobber it; they need per-type MERGE → separate task (Non-Goal).
**Source:** Interview #1.

## 🏗️ Technical Design

**Current State** — `reconcile.py:231-239`: `parse_frontmatter` returns `fm=None` for pure JSON → `KEEP("no-frontmatter")`. `cli.py:367-371`: KEEP paths are filtered out of the render blueprint (`new_files = [f for f in bp.files if f.path not in keep_paths]`), so a KEEP'd schema is never re-written.

**Fix** — add, in the 160-230 special-case block (alongside `settings.json`/`AGENTS.md`/hooks.json/`.toml`/`.sh`), a branch:
```
if _is_schema_path(fe.path):   # shared predicate (see below)
    conflicts.append(ConflictItem(path=fe.path,
        decision=ReconcileDecision.REPLACE, reason="schema-always-replace"))
    continue
```
Placed before line 231 so it pre-empts the no-frontmatter KEEP. `cli.py` then leaves the schema in the blueprint → `render` writes it via `_is_schemas_json` → `_render_pure_json`; `_write_harness_manifest(written)` records the NEW hash.

**Predicate sharing (resolves validator W1)** — reconcile and render MUST classify "schema path" identically (reconcile decides REPLACE; render decides pure-JSON write via `_is_schemas_json`). Do NOT hand-roll a second `str(...).endswith(".json")` check. Order of preference at execute time:
1. Import `render._is_schemas_json` into reconcile and call it on `fe` — **first verify no import cycle** (`reconcile` is called by `cli` before `render`; `render` is not expected to import `reconcile`). If clean, reuse directly.
2. If a cycle exists, extract the predicate to a tiny shared helper (e.g. `harness_maker.paths._is_schemas_json` or a function on `models`) that both `render` and `reconcile` import.
A test pins the two classifications equivalent over a fixture set (Phase 1).

**Manifest / orphan-sweep (resolves validator W2)** — on the first `--update` after upgrade: the stale schema flips KEEP→REPLACE → render writes it → `_write_harness_manifest(written)` records its new hash (it was previously absent/stale because KEEP'd files are excluded from `written`). The orphan-sweep cannot delete the schema: it is present in `full_bp` (cli.py keeps the *unfiltered* blueprint for orphan classification — `full_bp = bp` before the KEEP filter), so it's never an orphan candidate. Phase 2 asserts the post-REPLACE manifest entry exists; Technical Design cites `full_bp` as the non-interaction reason rather than asserting it bare.

**Path form** — in reconcile, `fe.path` for the schema is `Path("schemas/codex-finding.schema.json")` (inside-`.claude/`, no prefix — matches the existing `Path("hooks/hooks.json")` literals). `render._is_schemas_json` uses `str(fe.path).startswith("schemas/") and fe.path.suffix == ".json"`.

**API Changes** — none external. Internal: reconcile gains one branch + (possibly) a shared predicate import.

## 📝 Implementation Plan

### Phase 1 — reconcile RED tests (behavior + predicate equivalence)
- **depends_on:** `[]` | **parallel_group:** `serial-tdd` | **merge_hazards:** none (new/extended test file)
- **Scope in:** `tests/unit/test_reconcile.py` (or new `test_reconcile_schemas.py`). **Out:** all source.
- **Exit (RED against current code):**
  1. Fixture: an existing `.claude/` dir containing a STALE `schemas/codex-finding.schema.json` (old shape, no frontmatter) + a blueprint carrying the new schema → assert `reconcile()` returns **REPLACE** for that path (currently returns KEEP — RED).
  2. Fresh-install case: schema path absent on disk → not classified KEEP (renders normally).
  3. Predicate-equivalence test: the reconcile schema-path classifier and `render._is_schemas_json` agree over a fixture set (`schemas/x.json` → True; `schemas/README.md`, `hooks/hooks.json`, `agents/x.md` → False).
- **Risk:** low. **Rollback:** delete tests.

### Phase 2 — forced-REPLACE branch + shared predicate (GREEN)
- **depends_on:** `[1]` | **parallel_group:** `serial-tdd` | **merge_hazards:** `reconcile.py` (+ `render.py` ONLY if predicate extraction is needed)
- **Scope in:** `src/harness_maker/reconcile.py` (+ shared-predicate location per Technical Design). **Out:** `cli.py` (no change).
- **Exit:**
  1. Phase 1 tests GREEN.
  2. Broadened no-regression gate (validator W4): `uv run pytest tests/unit/test_reconcile*.py tests/unit/test_render*.py tests/unit/test_cli*.py tests/unit/test_reconcile_orphan_sweep.py` all green.
  3. Manifest assertion (validator W2): after a forced-REPLACE render of a stale schema, the schema's NEW body hash appears in `.hm-render-manifest.jsonl`.
- **Risk:** low. **Rollback:** `git checkout reconcile.py` (+ render.py if touched).

### Phase 3 — CLI-boundary test (required; no unit-test escape — validator W3)
- **depends_on:** `[2]` | **parallel_group:** `serial-boundary` | **merge_hazards:** none (test only)
- **Scope in:** a boundary test (e.g. `tests/integration/test_boundary_*` or `tests/unit/test_reconcile_schemas.py` exercising `cli.make`). **Out:** source.
- **Exit:** end-to-end via `cli.make`: seed a temp project dir whose `.claude/schemas/codex-finding.schema.json` is the STALE shape, run `make(target, --update)` (programmatically, no TTY), and assert the on-disk schema file is **overwritten with the new shape** (this exercises reconcile → `cli.py` keep-filter → render dispatch → disk write, the boundary a reconcile-only unit test does NOT cover — CLAUDE.md checkpoint 8). INTEGRATION-gate only if it needs network/codex (it does not — pure render), so keep it CI-runnable.
- **Risk:** low. **Rollback:** delete test.

### Phase 4 — version bump + CHANGELOG + full gate
- **depends_on:** `[1,2,3]` | **parallel_group:** `serial-release` | **merge_hazards:** 5 version files must stay in sync
- **Scope in:** `.claude-plugin/`, `.cursor-plugin/`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`, `CHANGELOG.md`.
- **Exit:** `ruff check` + `ruff format --check` + `mypy --strict src` + full `pytest` green; 5-file bump **0.28.7→0.28.8**; CHANGELOG entry. (No tag push — separate user-initiated release step.)
- **Risk:** low. **Rollback:** `git checkout` version files.

## 🧪 Testing Strategy

- **Unit:** reconcile REPLACE-for-stale-schema (RED→GREEN); fresh-install; predicate-equivalence vs `render._is_schemas_json`; no-regression across reconcile/render/cli/orphan suites; post-REPLACE manifest-hash assertion.
- **Boundary (CI-runnable):** `cli.make --update` overwrites a stale on-disk schema (Phase 3) — the required end-to-end proof.
- **No codex/integration network test** — reconcile + render are pure logic; the boundary test uses `cli.make` only.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| reconcile/render schema predicates drift | medium | high (re-introduces KEEP-forever for a future schema) | Single shared predicate + equivalence test (Phase 1/2) |
| Manifest not recorded post-REPLACE on existing installs | low | medium | Phase 2 manifest-hash assertion; `_write_harness_manifest(written)` records it |
| Orphan-sweep deletes the schema | low | high | It's in `full_bp` (unfiltered), never an orphan candidate — cited, not assumed |
| Over-broad path match under `schemas/` | low | low | require `schemas/` prefix + `.json` suffix; only codex-finding exists today |
| Clobber user-edited schema | low | low | accepted (ADR-001): zero user content + `backup()` |

## ✅ Success Criteria

- [x] `reconcile()` returns REPLACE for an existing stale `.claude/schemas/*.json`.
- [x] reconcile and `render._is_schemas_json` classify schema paths identically (reused the ONE predicate — drift structurally impossible; scoping test confirms).
- [x] Post-REPLACE: schema's new hash recorded in `.hm-render-manifest.jsonl`; orphan-sweep leaves it.
- [x] CLI-boundary test: real reconcile+render mirroring `cli.py:367-371` overwrites a stale on-disk schema with the new shape.
- [x] No regression across reconcile/render/cli/orphan suites; full gate green; 0.28.8 synced across 5 files + CHANGELOG.

## 🔍 Plan Validation

- **Validator outcome:** NEEDS_REVISION (0 critical, 3 warnings + 1 suggestion) → **resolved**.
- **Codex second opinion:** ⚠️ **skipped** — `codex exec` Bash invocation denied by the permission gate; verdict is Claude-only (warn-and-proceed, ADR-003 of PLAN-codex-second-llm-integration).

| Finding | Severity | Resolution |
|---------|----------|------------|
| W1 — predicate drift (local check vs `render._is_schemas_json`) | warning | Single shared predicate (import-first, extract-if-cycle) + equivalence test (Phase 1/2). |
| W2 — manifest/orphan-sweep interaction untested | warning | Post-REPLACE manifest-hash assertion (Phase 2) + `full_bp` non-orphan citation in Technical Design. |
| W3 — Phase 3 OR-escape lets boundary test be skipped | warning | Removed the unit-test proxy; required `cli.make` end-to-end overwrite test (Phase 3). |
| W4 — Phase 2 gate scoped to reconcile-only | suggestion | Broadened Phase 2 green gate to reconcile+render+cli+orphan suites. |

## Non-Goals

- `.cursor/mcp.json` / `.cursor/rules/*.mdc` KEEP-forever — same root class, but they carry **user content** → need per-type MERGE, not REPLACE → separate future task.
- No `render.py` behavior change (only a possible predicate extraction).
- No generic "zero-user-content" REPLACE predicate.
- No git tag push (user-initiated release step).

## 🔧 Execution Log (/hm:execute — 2026-06-03)

Worktree `execute-730867835d28-20260602T1613Z`. TDD machine A→A.5→B→C→D.

| Phase | Status | Notes |
|-------|--------|-------|
| 1 — RED reconcile + boundary tests | ✅ DONE | `tests/unit/test_reconcile_schemas.py` (4 tests: REPLACE / fresh-install / predicate-scoping / CLI-boundary disk-overwrite + W2 manifest). test-reviewer PASS; RED confirmed (S1 KEEP→expected REPLACE; S4 stale schema not overwritten). |
| 2 — forced-REPLACE branch (GREEN) | ✅ DONE | `reconcile.py`: import `_is_schemas_json` from render (no cycle — reconcile already imports render; **W1 resolved by reusing the ONE predicate**, no extraction); branch before no-frontmatter KEEP → `REPLACE("schema-always-replace")`. No render/cli change. Broadened gate green (153 reconcile/render/cli tests). |
| 3 — CLI-boundary test (W3) | ✅ DONE | `test_make_overwrites_stale_schema_on_disk` mirrors cli.py:367-371 with REAL reconcile+render → asserts stale schema overwritten on disk + recorded in `.hm-render-manifest.jsonl` (W2). No unit-test escape. |
| 4 — version bump + CHANGELOG | ✅ DONE | 5-file sync 0.28.7→**0.28.8**; CHANGELOG entry; version sync/drift tests pass. |

**Quality gate (worktree):** ruff ✅ · ruff format ✅ · mypy --strict (102 files) ✅ · full unit suite ✅ (exit 0).

**Staged changeset (uncommitted — wrapup owns commit):** `M reconcile.py` · `A test_reconcile_schemas.py` · `M`×5 version files + `M CHANGELOG.md`.

**W1 note:** the PLAN allowed import-or-extract for the shared predicate; execute found reconcile **already** imports from render (line 46) with no reverse import → reused `render._is_schemas_json` directly. No second predicate exists, so drift is structurally impossible (the equivalence test became a scoping sanity-check rather than a drift guard).
