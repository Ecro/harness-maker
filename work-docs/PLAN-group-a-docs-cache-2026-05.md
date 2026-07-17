---
type: plan
task_slug: group-a-docs-cache-2026-05
status: planning
created: 2026-05-16
tags: [harness-maker, plan, follow-up, docs, cache]
parent_plan: "[[PLAN-personalization-depth-2026-05]]"
interview_rounds: 0
adrs: 1
validator_outcome: skipped (small follow-up scope)
summary: "0.12.1 quick-win: TECH_SPEC Personalization Architecture section + STACK_GLOB literal filenames in CACHED_MANIFESTS"
---

# PLAN — Group A follow-up (TECH_SPEC docs + STACK_GLOB cache)

## 🎯 Executive Summary

**What:** Two follow-up items from PLAN-personalization-depth-2026-05's deferred list (Group A — "immediate quick wins"):

1. **TECH_SPEC.md** missing the `## Personalization Architecture` section that 0.12.0 added to README.md. Without it, future plan-validator / agents reading TECH_SPEC won't know about Tracks A+D+B-start, ADR-011 rubric, `@hm:harness:*` markers, etc. → doc-drift footgun.
2. **`detection_cache.CACHED_MANIFESTS`** missing the literal-filename entries from `STACK_GLOB_MANIFESTS` (`package.yaml`, `stack.yaml`). Touching these manifests doesn't invalidate the profile cache → stale stack detection on csharp/haskell projects until 24h ceiling.

**Why:** Both are PLAN-personalization-depth-2026-05 follow-up items #6 and #3 in the original plan-close report.

**Key Decisions:**
- ADR-001: Add as new top-level `## 7. Personalization Architecture` section in TECH_SPEC.md (between current Section 6 Risks & Decisions and Appendix A). Avoids renumbering existing sections.

**Estimated impact:** Tiny. 1 docs PR + 1-line cache constant change + 1 regression test. 0.12.1 patch release.

## 📚 Prior Work

- **`work-docs/PLAN-personalization-depth-2026-05.md`** — parent PLAN. The Phase 12 agent flagged the TECH_SPEC.md deferral and the STACK_GLOB cache limitation explicitly. This PLAN closes both.
- **README.md** Personalization Architecture section (landed in 0.12.0 Phase 12) — TECH_SPEC version mirrors this with slightly more depth (rubric formulas, marker styles, ADR cross-refs).
- **`src/harness_maker/profile.py`** STACK_GLOB_MANIFESTS (csharp / haskell with mix of glob + concrete filenames).
- **`src/harness_maker/detection_cache.py`** `CACHED_MANIFESTS` constant — currently `_flatten_stack_manifests() + _FOREIGN_AI_CONFIGS`. Needs concrete-filename entries from `STACK_GLOB_MANIFESTS` added.

## 🎙️ Interview Transcript

Skipped — small follow-up scope (docs + 1-line constant + 1 test). Decisions all derive directly from parent PLAN's deferred-item list. No architectural ambiguity warranting interview.

## 📐 Architecture Decision Records

### ADR-001: New `## 7. Personalization Architecture` section in TECH_SPEC.md
**Status:** Accepted (2026-05-16, derived from PLAN-personalization-depth-2026-05 Phase 12 agent deviation note)
**Context:** TECH_SPEC.md has Sections 0-6 + Appendices A/B/C. The 0.12.0 Personalization Architecture content needs a home. Two placement options:
- (a) Insert inside Section 3 Architecture as 3.X subsection — too nested.
- (b) Insert as new top-level Section 7 between 6 (Risks & Decisions) and Appendix A — clean, zero renumbering.
**Decision:** Option (b). New `## 7. Personalization Architecture (0.12.0)` section.
**Consequences:**
- ✅ Zero renumbering of existing sections.
- ✅ Future versions can add Section 8, 9, etc. for next major features.
- ⚠️ TECH_SPEC table-of-contents (if any) needs update.
**Rejected alternatives:**
- (a) — too nested, mixes architecture-foundation with feature-architecture.
- Renumber Risks→7, Personalization→6 — disruptive, breaks existing cross-references.
**Source:** Parent PLAN Phase 12 agent deviation.

## 🏗️ Technical Design

### Affected Components

| Component | Change type | Phase |
|-----------|-------------|-------|
| `TECH_SPEC.md` | Append `## 7. Personalization Architecture (0.12.0)` section (~50-80 lines) | Phase 1 |
| `src/harness_maker/detection_cache.py` | Extend `CACHED_MANIFESTS` with `_STACK_GLOB_CONCRETE` (literal filenames from STACK_GLOB_MANIFESTS, excluding `*`-glob patterns) | Phase 2 |
| `tests/unit/test_detection_cache.py` | NEW test: `test_cache_invalidated_when_stack_glob_concrete_manifest_changes` (e.g. touch `stack.yaml`) | Phase 2 |

### Dependencies

No new Python runtime dependency. No new test framework. Reuse existing.

## 📝 Implementation Plan

### Phase 1: TECH_SPEC.md Personalization Architecture section

**Scope:** Append a new `## 7. Personalization Architecture (0.12.0)` section to `TECH_SPEC.md`, inserted BETWEEN current `## 6. Risks & Decisions` (ends line ~1514) and `## Appendix A: Decisions Log` (starts line 1515). Content mirrors README.md Personalization Architecture section but with more depth on the ADR-locked formulas/markers/rubric tiers.

Section structure (~50-80 lines):
- `### 7.1 Three Tracks` — Track A (Detection Depth), Track D (Foreign AI Config Migration), Track B-start (Adaptive). One paragraph each citing key ADR numbers.
- `### 7.2 Confidence-Bucketed Recommendation UI` — ADR-004 + ADR-007: HIGH (silent + yaml comment) / MEDIUM (explicit AskUserQuestion) / LOW (no surface).
- `### 7.3 Foreign Config Marker Family (`@hm:harness:*` inverted)` — ADR-009 + amendment: `@hm:user:*` vs `@hm:harness:*` semantics, MarkerStyle dispatch (HTML_COMMENT for `.md`/`.mdc`, HASH_COMMENT for `.yml`, JSON_KEY for `.json`), 0.11.x migration fingerprint.
- `### 7.4 Personalization Rubric (ADR-011 v0)` — composite-score model with locked formulas: L1×0.4 + L2×0.3 + L3×0.3, tier boundaries (Bronze<40 / Silver 40-64 / Gold 65-85 / Platinum>=85), evidence schema `{n_observations, top_3_signals, confidence}`.
- `### 7.5 Telemetry — Local-Only, Opt-Out` — ADR-005 positive obligation referencing `tests/unit/test_no_network.py`; dual capture sites (`/hm:configure-exit` primary + SessionStart secondary); `schema_version: 1` mandatory.
- `### 7.6 Cursor Power-User Constraint` — ADR-003: single-source means we re-generate `.cursor/rules/` on every render. Opt-out flag deferred to follow-up PLAN.

**Out of scope:** README.md (already done). Section number changes elsewhere in TECH_SPEC. Any new ADR.

**Exit criterion:** TECH_SPEC.md contains `## 7. Personalization Architecture` heading. Manual verification — `grep "^## 7\. Personalization Architecture" TECH_SPEC.md` returns 1 match. Existing Sections 0-6 and Appendices A/B/C all still present with their original numbering.

**Risk:** very low. Docs-only.

**Rollback point:** Revert Phase 1 by removing the appended section from TECH_SPEC.md.

### Phase 2: STACK_GLOB literal filenames in CACHED_MANIFESTS

**Scope:** Extend `src/harness_maker/detection_cache.py`'s `CACHED_MANIFESTS` constant to include LITERAL filenames from `STACK_GLOB_MANIFESTS` (skipping `*`-pattern entries which cannot be stat'd).

Currently `STACK_GLOB_MANIFESTS = {"csharp": ["*.csproj", "*.sln"], "haskell": ["package.yaml", "*.cabal", "stack.yaml"]}`. Concrete filenames: `package.yaml`, `stack.yaml`. Add these to `CACHED_MANIFESTS`.

Implementation:
- Add a `_flatten_stack_glob_concrete()` helper that returns the non-glob entries from `STACK_GLOB_MANIFESTS`:
  ```python
  def _flatten_stack_glob_concrete() -> tuple[str, ...]:
      """Extract literal filenames (no `*`) from STACK_GLOB_MANIFESTS for cache mtime tracking.
      Glob patterns like `*.csproj` cannot be stat()'d, so they remain out of CACHED_MANIFESTS
      and rely on the 24h ceiling for cache invalidation (Phase 3 known limitation, partially closed here)."""
      out: list[str] = []
      for patterns in STACK_GLOB_MANIFESTS.values():
          for pat in patterns:
              if "*" not in pat:
                  out.append(pat)
      return tuple(sorted(set(out)))
  ```
- Update `CACHED_MANIFESTS`:
  ```python
  CACHED_MANIFESTS: tuple[str, ...] = (
      _flatten_stack_manifests()
      + _flatten_stack_glob_concrete()
      + _FOREIGN_AI_CONFIGS
  )
  ```
- Update the relevant TODO comment in `detection_cache.py` (if any) to note that the concrete-filename portion is now covered.

Test:
- `test_cache_invalidated_when_stack_glob_concrete_manifest_changes` in `tests/unit/test_detection_cache.py`:
  - Build fixture project with `stack.yaml` present.
  - Call `load_or_run` once (cache miss → write cache).
  - Touch `stack.yaml` (update mtime).
  - Call `load_or_run` again → must return None (cache invalidated).

**Out of scope:** Adding `*`-glob patterns to invalidation logic (would require os.listdir + glob scan per check, deferred).

**Exit criterion:**
```bash
cd /home/noel/harness-maker/.worktrees/execute-20260516T1329Z && uv run pytest tests/unit/test_detection_cache.py -q && uv run mypy --strict src/harness_maker/detection_cache.py && uv run ruff check src/harness_maker/detection_cache.py tests/unit/test_detection_cache.py
```

**Risk:** low.

**Rollback point:** Revert Phase 2 by removing `_flatten_stack_glob_concrete()` from `CACHED_MANIFESTS` composition.

### Execution Status

| Phase | Status | Evidence |
|-------|--------|----------|
| 1     | not started | TECH_SPEC.md Section 7 to be added |
| 2     | not started | CACHED_MANIFESTS extension + test |

## 🧪 Testing Strategy

- Phase 1: manual grep verification.
- Phase 2: unit test asserting cache invalidates on `stack.yaml` mtime bump. Full regression `uv run pytest tests/unit/` must remain green (~1847 baseline, 8 pre-existing snapshot drift resolved by Phase 10 of parent PLAN).

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| TECH_SPEC.md section numbering collision (existing 0-6) | low | ADR-001 chose new Section 7 after 6, before Appendix A — zero conflict. |
| Glob-pattern handling regression on existing Phase 2/3 tests | low | Phase 2 only ADDS to CACHED_MANIFESTS via tuple concatenation — additive change. Existing tests preserved. |
| TECH_SPEC content out of sync with README (drift) | low | Phase 1 mirrors README's section. ADR-011 / @hm:harness:* / etc. cited by number → drift detection via grep. |

## ✅ Success Criteria

- [ ] `## 7. Personalization Architecture (0.12.0)` section present in `TECH_SPEC.md` with subsections 7.1-7.6.
- [ ] Existing TECH_SPEC sections (0-6 + Appendices A/B/C) intact with original numbering.
- [ ] `CACHED_MANIFESTS` includes `package.yaml` AND `stack.yaml` from `STACK_GLOB_MANIFESTS`.
- [ ] `test_cache_invalidated_when_stack_glob_concrete_manifest_changes` test passes.
- [ ] Full unit suite remains green (`uv run pytest tests/unit/ -q`).
- [ ] `mypy --strict` + `ruff` clean on touched files.

## 🔍 Plan Validation

Skipped — small follow-up scope. plan-validator agent dispatch reserved for substantial PLANs with multiple architectural ADRs. This PLAN has one ADR (placement choice) and two atomic phases.
