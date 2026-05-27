---
type: plan
task_slug: second-brain-fix
status: complete
created: 2026-05-27
tags: [harness-maker, plan, python, second-brain, obsidian, config, search]
spec: "[[SPEC-second-brain]]"
interview_rounds: 4
adrs: 3
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Fix non-functional Second Brain: config, dead fields, search quality, error UX"
---

## 🎯 Executive Summary

**TL;DR:** Second Brain is enabled but fully non-functional due to misconfigured `vault_path` (points to non-existent subdir) and empty `folders: []`. Additionally, two config fields (`trusted_allowlist`, `required_frontmatter`) are stored but never read at runtime.

**What:** Fix config to make Second Brain operational, remove dead `trusted_allowlist` field, wire `required_frontmatter` to runtime validation, improve search quality with scoring, and make degraded-mode errors more visible.

**Why:** Every workflow stage (`research`, `plan`, `review`, `wrapup`) invokes `python -m harness_maker.second_brain search ...` which silently returns `[]` — the feature is a no-op despite being "enabled."

**Key Decisions:**
- ADR-001: Remove `trusted_allowlist` (dead field, no semantic meaning)
- ADR-002: Wire `required_frontmatter` to `validate_note()` runtime
- ADR-003: Search scoring via word-boundary + title/tag boost (no external deps)

**Estimated impact:** 5 files modified in `src/`, 1 config edit, ~3 test files updated.

## 📚 Prior Work

- `CHANGELOG.md` 0.13.1: provenance-frontmatter loader fix (prevented `_load_config` crash)
- `CHANGELOG.md` 0.26.x: timestamp auto-fill ADRs, empty-folders degrade guard
- `docs/followups/io-utils-migration.md` references `PLAN-second-brain-write-failure` (absent from workspace)
- ADR-002 (existing): smart vault existence check — parent `.obsidian/` probe
- ADR-008 (existing): graceful degrade when `folders: []`

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Fix scope | Scope boundaries | 이번 fix 의 범위 | C. 전면 리뷰 | config + dead config + search + error UX + docs | — |
| 1 | Vault folder | Architecture | vault 내 harness-maker 노트 위치 | A. 99_HM/harness-maker/ | 새로 생성, read+write | — |
| 2 | Dead config | Contract shape | required_frontmatter / trusted_allowlist 처리 | required_frontmatter → 런타임 반영; trusted_allowlist → 제거 | backward-compat 불필요 | ADR-001, ADR-002 |
| 2 | Search quality | Architecture | search 품질 개선 방향 | C. 기본 개선 | word-boundary + title/tag boost + scoring, 외부 dep 없음 | ADR-003 |
| 3 | Error UX | Failure handling | folders: [] 일 때 동작 정책 | B. warn-loud | stderr 강조 + exit 0 유지 | — |
| 3 | trusted_allowlist | Contract shape | 필드 처리 | A. 제거 | SecondBrainConfig 에서 삭제 | ADR-001 |
| 4 | Read scope | Scope boundaries | 기존 vault 폴더 read 접근 | C. 자체만 | 99_HM/harness-maker/ 만, 기존 vault 노트 접근 안 함 | — |

## 📐 Architecture Decision Records

### ADR-001: Remove `trusted_allowlist` from SecondBrainConfig
**Status:** Accepted (2026-05-27, via /hm:plan interview)
**Context:** `trusted_allowlist: true` is stored in harness.yaml and validated in Pydantic model, but no runtime code reads it. The field has no defined semantic — it was likely a placeholder for a future "bypass folder checks" feature that was never implemented.
**Decision:** Remove the field from `SecondBrainConfig` model. On-disk harness.yaml MUST be migrated (field stripped) BEFORE the model change lands — `_load_config()` calls `model_validate()` directly with `extra="forbid"`, so the field's presence post-removal causes immediate RuntimeError.
**Consequences:**
- ✅ Config surface is honest — no misleading knobs
- ⚠️ On-disk harness.yaml with the removed key must be migrated before model deploy (Phase 1 handles this)
- ⚠️ User projects with existing harness.yaml containing `trusted_allowlist` will need re-render; `_parse_second_brain` in `interview.py` already catches ValidationError with fallback for the reverse-mapper path
**Rejected alternatives:**
- Wire as "vault-wide read bypass" — Security model deliberately uses per-folder allowlists; a global bypass undermines it.
- Switch `extra="forbid"` to `extra="ignore"` — Would silently swallow all unknown fields, hiding future typos and drift.
**Source:** Interview #3

### ADR-002: Wire `required_frontmatter` to runtime validation
**Status:** Accepted (2026-05-27, via /hm:plan interview)
**Context:** `validate_note()` hardcodes `["type", "created", "updated", "tags", "links"]`. The config field `required_frontmatter` exists in `SecondBrainConfig` but is never read. Users expect changing the config to change validation behavior.
**Decision:** `validate_note()` will accept an optional `required_fields` parameter. When `None`, falls back to the hardcoded default (preserving current behavior for callers that don't pass config). `write_note`/`append_note`/`patch_note` will thread `cfg.required_frontmatter` through.
**Consequences:**
- ✅ Config actually controls behavior
- ✅ Default fallback preserves backward compat for direct `validate_note()` callers (tests, external scripts)
- ⚠️ Notes written with fewer required fields may not validate if config is later tightened
**Rejected alternatives:**
- Remove `required_frontmatter` entirely — User explicitly chose to wire it (value in customization).
**Source:** Interview #2

### ADR-003: Search scoring with word-boundary + title/tag boost
**Status:** Accepted (2026-05-27, via /hm:plan interview)
**Context:** Current search is substring-match only, no ranking. Results are returned in filesystem iteration order, not relevance order.
**Decision:** Add a scoring function: (1) word-boundary matches score higher than substring, (2) title matches get 3× boost, (3) tag matches get 2× boost, (4) results sorted by score descending. Pure Python, no external deps.
**Consequences:**
- ✅ More relevant results appear first
- ✅ No new dependencies
- ⚠️ Scoring heuristic may need tuning over time
**Rejected alternatives:**
- TF-IDF (whoosh) — Adds dependency for marginal gain on small vaults
- LLM rerank — API cost per search, overkill for filesystem notes
**Source:** Interview #2

## 🏗️ Technical Design

### Current State

```
second_brain.py
├── _load_config()       → reads harness.yaml, validates, returns SecondBrainConfig
├── validate_note()      → HARDCODED required fields ["type","created","updated","tags","links"]
├── search_notes()       → substring match, no scoring, filesystem order
├── write/append/patch   → folders: [] → raises SecondBrainError
└── CLI entry point      → delegates to above functions

SecondBrainConfig (models.py)
├── enabled, backend, project_id, vault_path
├── trusted_allowlist    → NEVER READ at runtime ← REMOVE
├── required_frontmatter → NEVER READ at runtime ← WIRE
└── folders: list[SecondBrainFolder]
```

### Affected Components

| File | Change |
|------|--------|
| `.claude/harness.yaml` | Fix vault_path, add folder, remove trusted_allowlist |
| `src/harness_maker/models.py` | Remove `trusted_allowlist` from SecondBrainConfig |
| `src/harness_maker/second_brain.py` | Wire required_frontmatter, improve search scoring, enhance warnings |
| `src/harness_maker/interview.py` | Remove trusted_allowlist from `_ask_second_brain` if referenced |
| `src/harness_maker/templates/harness-yaml/*.yaml.j2` | Remove trusted_allowlist from rendered config |
| `tests/unit/test_second_brain.py` | Update for scoring, required_frontmatter wiring |
| `tests/unit/test_models.py` | Remove trusted_allowlist tests |
| `tests/integration/test_second_brain_e2e.py` | Update fixtures |

### Design Decisions

- **Scoring function** (ADR-003): `_score_result(query_tokens, relpath, title, tags, body)` returns float. Sorted descending before truncating at `limit`.
- **required_frontmatter threading** (ADR-002): `validate_note(frontmatter, body, *, required_fields=None)` — optional kwarg. Write/append/patch pass `cfg.required_frontmatter`.
- **Warn-loud** mechanism: `logger.warning` → `print(..., file=sys.stderr)` with clear remediation message in CLI context.

## 📝 Implementation Plan

### Phase 1: Config fix + migration
- `depends_on`: []
- `parallel_group`: `config`
- `merge_hazards`: `.claude/harness.yaml` (single writer)
- **Scope (in):** `.claude/harness.yaml`
- **Scope (out):** All Python code
- **Tasks:**
  1. Fix `vault_path` to `/mnt/c/Users/euncheol.ro/Documents/obsidian-vault`
  2. Add folder: `99_HM/harness-maker/` (read: true, write: true, note_types: all)
  3. Remove `trusted_allowlist: true` line (ADR-001 migration — must happen before Phase 2 model change lands to avoid `extra="forbid"` runtime error)
  4. Create vault subdir if absent: `mkdir -p "/mnt/c/.../obsidian-vault/99_HM/harness-maker"`
- **Exit criterion:** `uv run python -m harness_maker.second_brain --root . search 'harness' 2>&1` returns no ValidationError and no "folders is empty" warning (vault-existence warnings about missing subdir are acceptable until Phase 5 or are eliminated by task 4)
- **Risk:** low
- **Rollback:** revert harness.yaml edit

### Phase 2: Model cleanup (remove trusted_allowlist)
- `depends_on`: [1]
- `parallel_group`: `model-refactor`
- `merge_hazards`: `models.py` (shared model file)
- **Scope (in):** `src/harness_maker/models.py`, `src/harness_maker/interview.py`, `src/harness_maker/templates/harness-yaml/*.yaml.j2`, `src/harness_maker/synthesize.py`, `tests/unit/test_models.py`, `tests/unit/test_harness_yaml_migration.py`, `README.md`, `docs/HOW-IT-WORKS.md`
- **Scope (out):** `second_brain.py` (touched in later phases)
- **Tasks:**
  1. Remove `trusted_allowlist` field from `SecondBrainConfig` in `models.py`
  2. Remove from template renders (`Side.yaml.j2`, `Production.yaml.j2`)
  3. Remove from `interview.py` if referenced in `_ask_second_brain`
  4. Add warn-and-strip in `_load_config`: before `model_validate`, pop `trusted_allowlist` from raw dict with warning log (upgrade migration for other projects' on-disk harness.yaml)
  5. Update `test_models.py` assertions that check `trusted_allowlist`
  6. Update migration test fixtures
  7. Grep-clean all `trusted_allowlist` references in docs/README
  8. Add regression test: legacy harness.yaml with `trusted_allowlist` still loads successfully (warn-and-strip path)
- **Exit criterion:** `uv run pytest tests/unit/test_models.py -v -k second_brain && ruff check src/harness_maker/models.py && uv run python -m harness_maker.second_brain --root . search 'test'`
- **Risk:** low
- **Rollback:** Phase 1

### Phase 3: Wire required_frontmatter to validate_note
- `depends_on`: [2]
- `parallel_group`: `serial-second-brain-py`
- `merge_hazards`: `second_brain.py` validate_note signature change
- **Scope (in):** `src/harness_maker/second_brain.py`, `tests/unit/test_second_brain.py`
- **Scope (out):** search scoring, error UX
- **Tasks:**
  1. Add optional `required_fields: list[str] | None = None` param to `validate_note()`
  2. When `None`, fall back to current hardcoded list (backward compat for direct callers)
  3. In `write_note`/`append_note`/`patch_note`, pass `cfg.required_frontmatter` through
  4. In CLI `validate` subcommand, load config and pass `cfg.required_frontmatter` to `validate_note`
  5. Add test: custom `required_frontmatter: ["type", "tags"]` → validate_note only checks those
  6. Add test: CLI validate respects config-driven required fields
- **Exit criterion:** `uv run pytest tests/unit/test_second_brain.py::test_validate_note_uses_config_required_frontmatter -v`
- **Risk:** medium (signature change touches all write paths)
- **Rollback:** Phase 2

### Phase 4: Search quality improvements
- `depends_on`: [3]
- `parallel_group`: `serial-second-brain-py`
- `merge_hazards`: `second_brain.py` search_notes function
- **Scope (in):** `src/harness_maker/second_brain.py`, `tests/unit/test_second_brain.py`
- **Scope (out):** validate_note, write paths, models
- **Tasks:**
  1. Add `_score_result(query_tokens, relpath, title, tags, body)` → float
  2. Word-boundary match: +2 per token matched as whole word
  3. Title match: 3× multiplier
  4. Tag match: 2× multiplier
  5. Sort results by score descending before truncating at limit
  6. Add test: title-match result ranks above body-only match
- **Exit criterion:** `uv run pytest tests/unit/test_second_brain.py -v -k "search_score or search_rank"` passes
- **Risk:** low
- **Rollback:** revert scoring additions (search still works without)

### Phase 5: Error UX enhancement
- `depends_on`: [4]
- `parallel_group`: `serial-second-brain-py`
- `merge_hazards`: `second_brain.py` _load_config warning path
- **Scope (in):** `src/harness_maker/second_brain.py`, `tests/unit/test_second_brain.py`
- **Scope (out):** scoring, validation, models
- **Tasks:**
  1. Replace `logger.warning(...)` with `print(f"⚠️  WARNING: ...", file=sys.stderr)` in CLI context
  2. Add remediation message: `"ACTION: run /hm:configure or add folders to .claude/harness.yaml"`
  3. Add test: capfd assertion on stderr content
- **Exit criterion:** `uv run pytest tests/unit/test_second_brain.py -v -k "warn_loud or degraded_stderr"` passes
- **Risk:** low
- **Rollback:** Phase 4

### Phase 6: Tests + documentation
- `depends_on`: [1, 2, 3, 4, 5]
- `parallel_group`: `serial-final`
- `merge_hazards`: none
- **Scope (in):** `tests/unit/test_second_brain.py`, `tests/unit/test_models.py`, `tests/integration/test_second_brain_e2e.py`, `docs/HOW-IT-WORKS.md`
- **Scope (out):** source code (no production changes)
- **Exit criterion:** `uv run pytest tests/ -v --tb=short` all green; `ruff check src/`; `mypy --strict src/harness_maker/second_brain.py src/harness_maker/models.py`
- **Risk:** low
- **Rollback:** N/A (test-only)

## 🚫 Non-Goals

- No new external dependencies (whoosh, faiss, etc.)
- No Obsidian API integration (filesystem only)
- No access to existing vault folders beyond `99_HM/harness-maker/`
- No LLM-based reranking for search
- No SPEC refinement in this task (SPEC remains `verified-skeleton`)

## 🧪 Testing Strategy

| Phase | Level | What | Test file |
|-------|-------|------|-----------|
| 2 | Unit | SecondBrainConfig without `trusted_allowlist` | `tests/unit/test_models.py` |
| 2 | Unit | Migration fixtures tolerate missing field | `tests/unit/test_harness_yaml_migration.py` |
| 3 | Unit | `validate_note` with custom `required_fields` | `tests/unit/test_second_brain.py` |
| 3 | Unit | write/append/patch thread cfg.required_frontmatter | `tests/unit/test_second_brain.py` |
| 4 | Unit | `_score_result` scoring logic | `tests/unit/test_second_brain.py` |
| 4 | Unit | search results sorted by score | `tests/unit/test_second_brain.py` |
| 5 | Unit | warn-loud stderr output | `tests/unit/test_second_brain.py` |
| 6 | Integration | Render → load → search roundtrip | `tests/integration/test_second_brain_e2e.py` |
| 6 | Integration | boundary parse with updated config | `tests/integration/test_boundary_harness_yaml.py` |
| 6 | Manual | `uv run python -m harness_maker.second_brain search 'test'` on live vault | CLI |

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing harness.yaml with `trusted_allowlist` fails Pydantic `extra="forbid"` after model change | High | Medium | Template re-render strips it; `_parse_second_brain` already catches ValidationError with fallback |
| `required_frontmatter` wiring breaks existing write callers | Low | Medium | Optional kwarg with default None preserves old behavior |
| Vault path on WSL may not be accessible on all machines | Medium | Low | Smart check (ADR-002) already warns; tests use tmp dirs |
| Scoring heuristic gives unexpected ordering | Low | Low | Default limit=20 is generous; can tune weights later |

## ✅ Success Criteria

- [x] `uv run python -m harness_maker.second_brain --root . search 'harness'` executes without warnings
- [x] `uv run python -m harness_maker.second_brain --root . write '99_HM/harness-maker/test-note.md' --frontmatter-json '{"type":"decision","tags":["hm/second-brain"],"links":[]}' --body-file /dev/stdin <<< "Test"` succeeds
- [x] `trusted_allowlist` does not appear in `SecondBrainConfig` or rendered templates
- [x] Custom `required_frontmatter: ["type", "tags"]` in config → `validate_note` only requires those two
- [x] Search results sorted by relevance score (title match > tag match > body match)
- [x] Empty folders produces visible stderr warning with `/hm:configure` remediation
- [x] All tests green: `uv run pytest tests/ -v`
- [x] Type check: `mypy --strict src/harness_maker/second_brain.py src/harness_maker/models.py`

## 🔍 Plan Validation

**First pass:** MAJOR_REVISION (3 critical, 5 warnings)

| # | Severity | Issue | Resolution |
|---|----------|-------|------------|
| 1 | Critical | Phase 2 model change + `extra="forbid"` breaks runtime on existing harness.yaml | Phase 1 now removes `trusted_allowlist` from harness.yaml before model change |
| 2 | Critical | Phases 3/4/5 all modify `second_brain.py` in parallel → merge conflict | Serialized: 3→4→5 with `depends_on` chain |
| 3 | Critical | Phase 2 exit runs tests that assert `trusted_allowlist` but scope excludes tests | Phase 2 scope expanded to include relevant test files |
| 4 | Warning | Phase 3/5 exit criteria not runnable commands | Replaced with concrete pytest node paths |
| 5 | Warning | `trusted_allowlist` in README/docs not in Phase 2 scope | Phase 2 scope expanded to docs |
| 6 | Warning | SPEC is skeleton, plan goals exceed locked SPEC AC | Accepted — SPEC refinement is non-goal for this task |
| 7 | Warning | Missing plan sections (Non-Goals, Testing Strategy detail) | Added |
| 8 | Warning | ADR-001 understates breaking-change blast | Phase 1 migration handles it; ADR consequence updated in text |

**Second pass:** NEEDS_REVISION (4 warnings, 0 critical). All resolved:
- W1: Upgrade migration for other projects → Phase 2 task 4 (warn-and-strip in `_load_config`)
- W2: CLI validate doesn't thread required_frontmatter → Phase 3 task 4
- W3: Phase 1 exit may hit vault-existence warning → Exit criterion narrowed + task 4 creates subdir
- W4: Structural completeness → Rollback points already present; full sections maintained

**Final outcome:** APPROVED (all criticals resolved, all warnings addressed).
