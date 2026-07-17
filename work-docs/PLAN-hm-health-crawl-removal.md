---
type: plan
task_slug: hm-health-crawl-removal
status: complete
created: 2026-05-22
tags: [harness-maker, plan, hm-health, deprecation, refactor, adr-supersession]
research_doc: "[[RESEARCH-hm-health-crawl-removal]]"
interview_rounds: 2
adrs: 4
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Scrap /hm:health external_risks layer → 2-layer audit; v0.22.3 + ADR-0007 supersedes ADR-0006."
---

# 🎯 Executive Summary

**TL;DR.** Remove the `external_risks` crawl layer from `/hm:health` (4 sources × LLM relevance × adaptive threshold × per-item AskUserQuestion). Reduce to a 2-layer audit (structural + personalization). Ship as v0.22.3 patch with ADR-0007 superseding ADR-0006.

**What.** Delete `crawler/anthropic_blog.py`, `crawler/arxiv.py`, `crawler/github_releases.py`, `relevance.py` (full file — crawl scoring + stale-asset bundle). Keep `crawler/osv_dev.py` (consumed by `secscan/dependency_cves.py` via `/hm:verify`). Delete `research-crawler` + `relevance-filter` skills. Delete `harness-maker health-finalize` CLI subcommand. Delete Verify command's Check 4 (`_verify_external_risks_check`). Scrub string-literal references across 10 surfaces flagged by validator.

**Why.** 2026-05-22 user run: 12 items filtered through adaptive threshold, 1 accepted (already-known), 11 rejected — 91% noise. CVE coverage (the one source with rare-but-critical value) already lives in `secscan/dependency_cves.py` consumed by `/hm:verify`. Crawl is wrong-stage push: research belongs in `/hm:research`, not `/hm:health`.

**Key Decisions** (linked to ADRs):
- [ADR-0007 supersedes ADR-0006](#adr-001-write-adr-0007-superseding-adr-0006) — first supersession precedent in this repo
- [Version 0.22.2 → 0.22.3 patch](#adr-002-version-bump-0223-patch) — internal-surface justification
- [Fold `health-finalize` into `health`](#adr-003-fold-health-finalize-subcommand-into-health) — CLI surface simplification
- [Delete stale-asset code with relevance.py](#adr-004-delete-stale-asset-code-with-relevancepy) — ADR-006 bundled it; orphan

**Estimated impact.** 4 source-module deletions + 1 source-file purge + 2 skill template deletions + 1 CLI subcommand deletion + Verify Check 4 removal + 10 string-literal scrub surfaces + 6 test file deletions/updates + ADR-0007 + 5-file version sync. ~600-800 lines net deletion.

# 📚 Prior Work

**RESEARCH-hm-health-crawl-removal.md** — full motivation, 3-approach comparison (full demolition vs soft-deprecate vs replace with `/hm:trends`), 7 open questions enumerated for interview.

**ADR-0006 (Three-layer health audit)** — the decision being reversed. Established the 3-layer dashboard (structural / external_risks / personalization) in 0.13.0. Bundled crawler + LLM relevance filter + stale-asset detection into the external_risks layer.

**PLAN-health-consolidation.md** — original consolidation work that birthed ADR-0006.

**`[wiki:pattern] breaking-enum-change-pre-flight-grep-discipline`** (2026-05-22) — directly applicable lesson. Removal/rename tasks need explicit pre-flight `grep -rn` covering string-literal references (mypy doesn't catch `set` literals, `dict` keys, docstrings, `PINNED_SKILLS`-style tuples). Validator's 7 string-literal warnings in this PLAN's first pass confirm the pattern.

**`[wiki:gotcha] worktree-finalize-untracked-loss`** (2026-05-22) — `work-docs/` is gitignored; `worktree.finalize` only transfers tracked files. PLAN and RESEARCH for this work were written to base `work-docs/`, not a worktree. Phase 1-7 execute work goes to worktree; final PLAN/RESEARCH/REVIEW writes stay on main.

**`[wiki:pattern] snapshot-regen-on-main-not-worktree-discipline`** (2026-05-22) — Phase 2's snapshot regen runs on `main` after worktree finalize, not inside the worktree.

**`[decision:harness-maker-cold-eval-phase2]`** (2026-05-22 14:00 UTC) — most recent BREAKING change (lifecycle enum v0.22.0) used minor bump. This PLAN's ADR-002 deliberately departs from that precedent (patch instead of minor) with explicit reasoning tied to the internal-surface nature.

# 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|-------|----------|-------------------|---------|--------|------|-------|
| R1.1 | ADR strategy | Architecture | ADR-006 폐기 시 ADR 정책: supersede vs amend? | A. ADR-0007 supersedes / B. ADR-006 in-place amend / Other | A | First supersession precedent in repo | ADR-001 |
| R1.2 | Version bump | Risk tolerance | 0.22.3 patch vs 0.23.0 minor for BREAKING dashboard schema + CLI subcommand removal? | A. 0.23.0 minor / B. 0.22.3 patch / Other | B | dashboard.md + health-finalize are internal surfaces (slash template auto-updates); no scripted external user | ADR-002 |
| R1.3 | CLI surface | Architecture | `health-finalize` 처리: keep with `--external-risks-json` removed vs fold into `health`? | A. Keep finalize / B. Fold to single `health` / Other | B | personalization stays Claude-judged inside slash template; Python CLI emits structural only | ADR-003 |
| R2.1 | Stale-asset fate | Scope | `relevance.py:200-435` stale-asset code (ADR-006 bundled it; no production caller): delete with relevance.py vs migrate to new module? | A. Delete with relevance.py / B. Migrate to stale_assets.py / Other | A | ADR-006 consistency; orphan code; test_relevance_stale.py also deleted | ADR-004 |
| R2.2 | End interview | Process | Validator의 나머지 9개 (mechanical scope additions): 추가 round 필요? | A. End — plan 재작성 / B. Re-check deprecation warning option / Other | A | All 9 are mechanical (scope additions or string-literal scrubs); no architectural choice | — |

# 📐 Architecture Decision Records

### ADR-001: Write ADR-0007 superseding ADR-0006

**Status:** Accepted (2026-05-22, via `/hm:plan` interview Round 1)

**Context:** ADR-0006 (Three-layer health audit, 2026-05-17) consolidated 3 separate audits into `/hm:health` with a 3-layer dashboard including `external_risks` (crawler + LLM relevance + stale-asset detection). 2026-05-22 runtime evidence shows the external_risks layer fires 91% noise (12 items, 1 accept). The decision is being reversed, not refined.

**Decision:** Write new `docs/adr/0007-two-layer-health-audit.md` with `Status: accepted`. ADR-0006 status field updated to `superseded by [ADR-0007](0007-two-layer-health-audit.md) 2026-05-22`. ADR-0006 body retains its original content plus a 1-paragraph "Reversal rationale" appendix.

**Consequences:**
- ✅ Audit trail clean: ADR-0006 + ADR-0007 form a paired reversal record
- ✅ Establishes supersession precedent for this repo (first instance)
- ✅ Future ADR reversals follow the same `Status: superseded by ADR-NNNN` form
- ⚠️ ADR file numbering becomes non-contiguous (existing gaps at 0003-0005, 0008-0010; ADR-0007 fills the next monotonic slot)

**Rejected alternatives:**
- ADR-006 in-place amend — Rejected because `Decision reversed` paragraphs inside an Accepted-status ADR muddy the canonical state. Supersession pattern is the standard convention for "this decision no longer applies."

**Source:** Interview Round 1, Question 1.

---

### ADR-002: Version bump 0.22.3 (patch)

**Status:** Accepted (2026-05-22, via `/hm:plan` interview Round 1)

**Context:** Removing `external_risks` layer changes (a) `dashboard.md` schema (the `## External risks` section disappears), (b) deletes CLI subcommand `harness-maker health-finalize`, (c) deletes `--external-risks-json` flag. Precedent v0.22.0 (lifecycle enum 4-tier → 3-tier) used minor bump for BREAKING. Below-1.0 BREAKING-bump policy is not explicitly defined in `CLAUDE.md`.

**Decision:** Bump 0.22.2 → 0.22.3 (patch), NOT 0.23.0 (minor).

**Consequences:**
- ✅ Tight cadence — recent v0.22.x cycle stays within patch series
- ✅ Reflects internal-surface nature of the changes (no external API contract broken)
- ⚠️ Accepted risk #1: 0.22.3 lacks semver protection for users who shell-script `harness-maker health-finalize`. Evidence supporting acceptance: subcommand introduced 0.13.0 as internal CLI bridge between Python (structural) and Claude (external_risks + personalization); no public README/AGENTS.md documentation of the subcommand; only known caller is the `/hm:health` slash template which auto-updates via `/hm:make --update`; 9 months in production without an external surfacing.
- ⚠️ Accepted risk #2: dashboard.md schema change means existing user dashboards retain a stale `## External risks` section until next `/hm:health` run. Parser handles missing key gracefully (returns empty dict). CHANGELOG documents cleanup.
- ⚠️ Accepted risk #3: orphan `decisions.jsonl` and `raw-*.jsonl` artifacts remain on existing user disks (gitignored on user side; harmless; CHANGELOG provides optional cleanup hint).

**Rejected alternatives:**
- 0.23.0 minor — Rejected because v0.22.0 minor-as-BREAKING precedent applied to an *external* Python type (`ProjectProfile.lifecycle` enum, consumed by `synthesize.py` + `interview.py` + test fixtures), not to a slash-template-internal CLI bridge. Surface character is different.
- Deprecation warning in 0.22.2 first, then remove in 0.22.3 — Rejected (Round 2): same accepted-risk evidence holds; adding a deprecation cycle for an unscripted internal subcommand is overengineering.

**Source:** Interview Round 1, Question 2 + Round 2, Question 2.

---

### ADR-003: Fold `health-finalize` subcommand into `health`

**Status:** Accepted (2026-05-22, via `/hm:plan` interview Round 1)

**Context:** `harness-maker health-finalize` exists because 3-layer flow split work between Python (structural — fast, file-system parsing) and Claude (external_risks + personalization — LLM-judged). With 2-layer audit, personalization remains Claude-judged inside the `/hm:health` slash template; the Python CLI just emits structural scores.

**Decision:** Delete `@app.command("health-finalize")` entirely (cli.py:1073). The remaining `@app.command("health")` outputs structural scores; the slash template appends personalization-judged content to `dashboard.md` itself.

**Consequences:**
- ✅ Single CLI subcommand surface for health (`harness-maker health`)
- ✅ Eliminates the bridging-JSON file (`.health-external-risks.tmp.json`, `.health.tmp.json` — both orphan after removal)
- ⚠️ `dashboard.md` rendering becomes a hybrid: Python emits structural section, Claude (inside slash template) edits personalization section in place. Atomic write discipline (`harness_maker.io_utils.atomic_write`) applies on both sides.

**Rejected alternatives:**
- Keep `health-finalize` with `--external-risks-json` removed — Rejected because the subcommand's reason-for-existence was the external_risks split; with external_risks gone, retaining the subcommand keeps a vestigial bridge.

**Source:** Interview Round 1, Question 3.

---

### ADR-004: Delete stale-asset code with relevance.py

**Status:** Accepted (2026-05-22, via `/hm:plan` interview Round 2)

**Context:** Validator (first pass) identified `relevance.py:200-435` as a second concern: `StaleAsset`, `detect_stale_assets`, `build_proposal_lines`, `update_last_reviewed_at`, `StaleAssetUpdateError`. ADR-006 bundled stale-asset detection into the external_risks layer. Production callers: zero (only `tests/unit/test_relevance_stale.py` and a `add_domain.py:52` docstring reference).

**Decision:** Delete the stale-asset code with the rest of `relevance.py`. Delete `tests/unit/test_relevance_stale.py`. Update `add_domain.py:52` to drop the docstring reference.

**Consequences:**
- ✅ Consistent with ADR-006 reversal scope (entire external_risks layer goes)
- ✅ Eliminates dead code path (mypy --strict passes, but file-system observation shows zero production caller)
- ⚠️ If a future feature wants `last_reviewed_at` introspection, it would need to be re-implemented from scratch. Acceptable given zero current usage.

**Rejected alternatives:**
- Migrate stale-asset code to new `harness_maker/stale_assets.py` module — Rejected because there is no production caller to preserve; keeping the code "in case" perpetuates the dead-code rot pattern that the wiki pattern `breaking-enum-change-pre-flight-grep-discipline` explicitly warns against.

**Source:** Interview Round 2, Question 1.

# 🏗️ Technical Design

## Current State

```
/hm:health (3 layers per ADR-0006)
├── structural (Python, harness_maker health --json-output)
│   └── 3-layer AI-readiness rubric per ADR-0002
├── external_risks (Claude-driven, this PLAN scraps)
│   ├── research-crawler skill → 4 sources (anthropic_blog/github_releases/arxiv/osv_dev)
│   ├── relevance-filter skill → LLM scoring + adaptive threshold (history-driven)
│   ├── stale-asset detection (relevance.py:200-435, no production caller)
│   └── harness-maker health-finalize CLI bridge (cli.py:1073)
└── personalization (Claude-driven, kept)
    └── ADR-0011 rubric: L1 conversion (0.4) + L2 stability (0.3) + L3 cadence (0.3)
```

## Target State (after this PLAN)

```
/hm:health (2 layers, per new ADR-0007)
├── structural (Python, harness_maker health --json-output)
│   └── Unchanged — 3-layer AI-readiness rubric per ADR-0002
└── personalization (Claude-driven, kept)
    └── Unchanged — ADR-0011 rubric (L1/L2/L3 weights unchanged)
```

OSV CVE detection survives via separate `secscan/dependency_cves.py` consumed by `/hm:verify` Check 5 (independent code path; unchanged by this PLAN).

## Affected Components

| Layer | Component | Action |
|-------|-----------|--------|
| Source modules | `src/harness_maker/crawler/{anthropic_blog,arxiv,github_releases}.py` | DELETE |
| Source modules | `src/harness_maker/relevance.py` (entire) | DELETE (ADR-004) |
| Source modules | `src/harness_maker/crawler/{__init__.py,osv_dev.py}` | KEEP (osv_dev only); trim `__init__.py` |
| Source modules | `src/harness_maker/models.py:CrawlItem` | KEEP class; trim docstring |
| Source modules | `src/harness_maker/cache.py:SOURCE_TTLS` | KEEP; trim to osv_dev key only |
| Source modules | `src/harness_maker/memory_retrieve.py` | UPDATE: inline `WORD_RE` (preserve ASCII semantics) |
| Source modules | `src/harness_maker/synthesize.py:_ALL_SKILLS` | UPDATE: drop 'research-crawler', 'relevance-filter' |
| Source modules | `src/harness_maker/interview.py:_ALL_SKILLS` (+ `_PROD_ENABLED_SKILLS`) | UPDATE: drop entries |
| Source modules | `src/harness_maker/communication_audit.py:PINNED_SKILLS` | UPDATE: drop 'relevance-filter' |
| Source modules | `src/harness_maker/add_domain.py:52` | UPDATE: drop docstring reference |
| Source modules | `src/harness_maker/spec_inventory/{batch_generator,catalog}.py` | UPDATE: trim string-literal classifications |
| CLI | `cli.py @app.command("health")` (line 989) | UPDATE: drop external_risks placeholder + `--skip-llm` flag |
| CLI | `cli.py @app.command("health-finalize")` (line 1073) | DELETE entire subcommand (ADR-003) |
| CLI | `cli.py @app.command("verify")` (line 1405) | UPDATE: delete Check 4 invocation, fix denominator in `_emit_verify_text` |
| CLI | `cli.py _verify_external_risks_check` (line 1586) | DELETE entire function |
| CLI | `cli.py:552, :703` "3-layer" string literals | UPDATE: scrub |
| Observability | `src/harness_maker/observability/dashboard.py` | UPDATE: drop external_risks parameter, parser branch, section emitter |
| Slash template | `src/harness_maker/templates/commands/hm/health.md.j2` | UPDATE: rewrite Step 2 deletion → 2-layer |
| Skill templates | `src/harness_maker/templates/skills/{research-crawler,relevance-filter}/` | DELETE both dirs |
| Verify template | `src/harness_maker/templates/stages/verify.md.j2` | UPDATE: delete Check 4 description |
| Cursor template | `src/harness_maker/templates/cursor/rules/harness.mdc.j2:120` | UPDATE: drop 4-source crawl description |
| Scripts | `.claude-verify.sh` (lines 279-280, 289-302, 298, 606, 647) | UPDATE: rewrite phase_5; trim asset assertions; fix R2 imports; reduce skill count |
| Tests (DELETE) | `tests/unit/test_crawler_anthropic_blog.py` (or `tests/unit/crawler/test_anthropic_blog.py`), `test_crawler_arxiv.py`, `test_crawler_github_releases.py`, `test_relevance.py`, `test_relevance_stale.py` | DELETE |
| Tests (UPDATE) | `tests/integration/test_health_dashboard_roundtrip.py`, `tests/e2e/test_verify_health_dashboard.py`, `tests/unit/test_communication_audit*.py`, `tests/unit/test_synthesize*.py`, `tests/unit/test_interview*.py` | UPDATE: 2-layer schema + 3-check verify |
| Tests (KEEP) | `tests/unit/test_crawler_osv_dev.py` | KEEP unchanged |
| Docs | `docs/adr/0006-three-layer-health-audit.md` | AMEND: Status → superseded |
| Docs | `docs/adr/0007-two-layer-health-audit.md` | CREATE (this PLAN's ADR-001 + ADR-002 + ADR-003 + ADR-004 form its content) |
| Docs | `CLAUDE.md`, `CHANGELOG.md`, `specs/SPEC-tpl-health-md.{md,machine.yaml}` | UPDATE: scrub references |
| Version sync | 5 files (`pyproject.toml`, `src/harness_maker/__init__.py`, 3× `plugin.json`) | UPDATE: 0.22.2 → 0.22.3 |
| Rendered (this repo) | `.claude/skills/{research-crawler,relevance-filter}/`, `.agents/skills/{research-crawler,relevance-filter}/`, `.claude/observability/.health-external-risks.tmp.json`, `.claude/observability/.health.tmp.json` | DELETE rendered copies; re-render templates |

## Dependencies

- `secscan/dependency_cves.py` imports `from harness_maker.crawler import osv_dev` — Phase 4 must preserve this export. Verified.
- `memory_retrieve.py` imports `from harness_maker.relevance import WORD_RE` — Phase 1 relocates to inline constant with byte-identical regex (`[A-Za-z0-9_]+`, ASCII-only). Korean tokenization issue is out of scope; documented in Risks.

## Data Flow (post-removal)

```
/hm:health invocation
├── Step 1 (structural)
│   └── harness-maker health . --json-output → JSON → atomic_write tmp file
└── Step 2 (personalization, Claude-judged inside slash template)
    ├── Read structural JSON
    ├── Read .claude/observability/personalization.jsonl
    ├── Apply ADR-0011 rubric (L1/L2/L3 weights)
    └── Write dashboard.md (Python-section structural + Claude-section personalization)
```

`harness-maker health-finalize` subcommand DELETED. Slash template handles the personalization section directly via Read/Edit on `dashboard.md`. Atomic write via `harness_maker.io_utils.atomic_write` enforced.

## API Changes

| API | Before | After |
|-----|--------|-------|
| `harness-maker health` | Emits structural + placeholder external_risks dict + `--skip-llm` flag | Emits structural only; `--skip-llm` flag removed |
| `harness-maker health-finalize` | Combines structural + external_risks + personalization | **DELETED** |
| `harness-maker verify` | 6 checks (Check 4 = external_risks) | 5 checks (Check 4 removed; renumber 5→4, 6→5; `_emit_verify_text` denominator → `f"/{len(checks)}"`) |
| `dashboard.md` schema | 3 sections (Structural / External risks / Personalization) | 2 sections (Structural / Personalization) |
| Skills | `research-crawler`, `relevance-filter`, + 9 others | + 9 others (the 2 deleted) |

# 📝 Implementation Plan

7 phases, outside-in deletion ordering (remove callers first, then delete producers). Each phase commits atomically to a worktree branch; finalize-back to `main` after exit criterion green.

## Phase 1 — Pre-flight grep + WORD_RE relocation

**Scope (files in):**
- `src/harness_maker/memory_retrieve.py` — replace `from harness_maker.relevance import WORD_RE` with inline `WORD_RE = re.compile(r"[A-Za-z0-9_]+")` (byte-identical to current; preserve ASCII-only semantics).

**Scope (files out):** all others.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_memory_retrieve*.py -x   # green
# Production imports of relevance.py outside test files must be 0:
grep -rn "from harness_maker.relevance\b\|import relevance\b\|harness_maker\.relevance\." src/ \
  | grep -v __pycache__ | grep -v "\.backup-" | grep -v "^src/harness_maker/relevance.py:"
# Must show: ZERO lines.
```

**Risk:** low. **Rollback point:** N/A (first phase).

## Phase 2 — Template + skill registry + string-literal scrub

**Scope (files in):**
- `src/harness_maker/templates/commands/hm/health.md.j2` — delete Step 2 (external_risks) entirely; rewrite to 2-layer (structural + personalization). Update Layer table at top.
- DELETE: `src/harness_maker/templates/skills/research-crawler/` (entire dir).
- DELETE: `src/harness_maker/templates/skills/relevance-filter/` (entire dir).
- `src/harness_maker/communication_audit.py:25` — remove `'relevance-filter'` from `PINNED_SKILLS` tuple.
- `src/harness_maker/synthesize.py:118` `_ALL_SKILLS` — remove `'relevance-filter'`, `'research-crawler'`.
- `src/harness_maker/interview.py:109` `_ALL_SKILLS` — same. (`:138` `_PROD_ENABLED_SKILLS = list(_ALL_SKILLS)` auto-trims.)
- `src/harness_maker/templates/cursor/rules/harness.mdc.j2:120` — delete `/hm:refresh` 4-source description.
- `src/harness_maker/cli.py:552` — update `_emit_install_summary` (remove "3-layer harness health").
- `src/harness_maker/cli.py:703` — update second "3-layer" echo line (drop "3-layer" word).

**Scope (files out):** Python source modules — Phase 3/4.

**Exit criterion:**
```bash
uv run pytest tests/snapshot \
  tests/unit/test_communication_audit*.py \
  tests/unit/test_synthesize*.py \
  tests/unit/test_interview*.py -x   # green
grep -n "external_risks\|research-crawler\|relevance-filter\|anthropic_blog\|3-layer" \
  src/harness_maker/templates/commands/hm/health.md.j2 \
  src/harness_maker/templates/cursor/rules/harness.mdc.j2 \
  src/harness_maker/communication_audit.py \
  src/harness_maker/synthesize.py \
  src/harness_maker/interview.py \
  src/harness_maker/cli.py
# Must show: ZERO matches in the 8 listed files (other files like ADR-0006 may retain references intentionally).
```

**Risk:** medium (snapshot regen + multi-file scrub). **Rollback point:** revert Phase 2 commit.

## Phase 3 — Observability + CLI + Verify rewrite

**Scope (files in):**
- `src/harness_maker/observability/dashboard.py`:
  - Remove `external_risks: dict[str, Any]` parameter from `render` signature (line ~72).
  - Delete external_risks parser branch (lines ~193, 209, 225-229).
  - Delete "External risks" section emitter.
  - Update `parse_dashboard` to drop `external_risks` key from its output dict.
- `src/harness_maker/cli.py @app.command("health")` (line 989):
  - Remove `external_risks` dict placeholder (lines ~1051-1052, 1058, 1067).
  - DELETE `--skip-llm` flag definition (lines 992-996) and any internal `skip_llm` parameter usage.
- `src/harness_maker/cli.py @app.command("health-finalize")` (line 1073) — DELETE entire subcommand block (~lines 1073-1150 + supporting helpers if internal-only).
- `src/harness_maker/cli.py @app.command("verify")` (line 1405) `verify_stage_cmd`:
  - DELETE `check4 = _verify_external_risks_check(...)` (line 1464).
  - Renumber remaining check IDs: keep current IDs 1, 2, 3, 5, 6 OR renumber to 1-5 (consistent with `_emit_verify_text` denominator fix below). Decision: renumber to 1-5 for clarity.
- `src/harness_maker/cli.py _verify_external_risks_check` (lines 1586-1657) — DELETE entire function.
- `src/harness_maker/cli.py _emit_verify_text` (line 1709) — change `f"[{cid}/6]"` to `f"[{cid}/{total}]"` where `total = len(checks)` passed in.
- `src/harness_maker/templates/stages/verify.md.j2` — delete Check 4 description block (lines ~106-118); renumber subsequent checks.
- `tests/integration/test_health_dashboard_roundtrip.py` — drop `_EMPTY_EXTERNAL_RISKS` fixture + external_risks assertions; update to 2-layer schema.
- `tests/e2e/test_verify_health_dashboard.py` — delete `test_check4_*` cases; update to 5-check verify.
- `tests/unit/test_health_personalization_integration.py` — audit (likely no change needed).

**Scope (files out):** crawler / relevance source modules (Phase 4).

**Exit criterion:**
```bash
uv run pytest -x   # full suite green
uv run mypy --strict src/   # green
uv run python -m harness_maker.cli --help 2>&1 | grep -c "health-finalize"   # 0
uv run python -m harness_maker.cli verify --help 2>&1 | grep -ic "external"   # 0
# Verify denominator dynamic:
grep -n '"/6"\|f"\[{.*}/6\]"' src/harness_maker/cli.py   # 0
```

**Risk:** medium-high (touches dashboard.py + 3 CLI subcommands + verify template + 3 test files). **Rollback point:** revert Phase 3 commit; Phase 1+2 stable.

## Phase 4 — Delete crawler + relevance + stale-asset source

**Scope (files in — deletions):**
- `src/harness_maker/crawler/anthropic_blog.py`
- `src/harness_maker/crawler/arxiv.py`
- `src/harness_maker/crawler/github_releases.py`
- `src/harness_maker/relevance.py` (entire file — includes stale-asset half per ADR-004)
- `tests/unit/crawler/test_anthropic_blog.py` (exact path TBD by pre-flight find)
- `tests/unit/crawler/test_arxiv.py`
- `tests/unit/crawler/test_github_releases.py`
- `tests/unit/test_relevance.py`
- `tests/unit/test_relevance_stale.py`

**Scope (files in — updates):**
- `src/harness_maker/crawler/__init__.py` — trim exports to `osv_dev` (and any osv_dev-adjacent symbols only).
- `src/harness_maker/models.py:212-216` — update `CrawlItem` docstring + `source: str` comment to reference only `osv_dev`.
- `src/harness_maker/cache.py:88` `SOURCE_TTLS` — trim to `{"osv_dev": TTL_1H}` only.
- `src/harness_maker/spec_inventory/batch_generator.py:85` — trim classification tuple (remove `'anthropic-blog'`, `'arxiv'`, `'github-releases'`).
- `src/harness_maker/spec_inventory/catalog.py:38` — change bucket description from "Anti-rot crawler (anthropic_blog/arxiv/github/osv)" to "OSV CVE crawler".
- `src/harness_maker/add_domain.py:52` — delete `detect_stale_assets` docstring reference.
- `.claude-verify.sh`:
  - Lines 279-280 — remove `research-crawler` and `relevance-filter` SKILL.md.j2 assertions.
  - Lines 289-302 `phase_5()` — rewrite to only test osv_dev (or delete `phase_5()` entirely if redundant with `uv run pytest`).
  - Line 298 — fix `from harness_maker.crawler import` to only `osv_dev`.
  - Line 606 (R2 anti-rot check) — remove crawler/relevance imports; check only osv_dev.
  - Line 647 — update skill-count assertion (drop 2 from total).

**Scope (files in — kept, no change):**
- `src/harness_maker/crawler/osv_dev.py`
- `tests/unit/test_crawler_osv_dev.py`
- `src/harness_maker/models.py:CrawlItem` class itself (osv_dev consumer)

**Exit criterion:**
```bash
# Mypy-invisible string-literal sweep:
grep -rn "anthropic_blog\|github_releases\|arxiv\.py\|from harness_maker\.relevance\|StaleAsset\|detect_stale_assets\|build_proposal_lines" \
  src/ tests/ .claude-verify.sh \
  | grep -v __pycache__ | grep -v "\.backup-" \
  | grep -v "^src/harness_maker/crawler/osv_dev.py:" \
  | grep -v "^tests/unit/test_crawler_osv_dev.py:"
# Must show: ZERO matches.

uv run pytest -x   # green
uv run mypy --strict src/   # green
bash .claude-verify.sh phase_5   # green (osv_dev-only)
bash .claude-verify.sh final_acceptance   # green (R2 + skill count both pass)
INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -x   # advisory regression gate per release procedure
```

**Risk:** medium. **Rollback point:** revert Phase 4 commit; Phase 1-3 stable.

## Phase 5 — ADR-0007 + SPEC + CHANGELOG + 5-file version sync

**Scope (files in):**
- CREATE: `docs/adr/0007-two-layer-health-audit.md`. Body contains the 4 ADRs from this PLAN (ADR-001 supersession + ADR-002 patch-bump risk acceptance + ADR-003 fold-finalize + ADR-004 stale-asset deletion) rolled into a single ADR document; cross-references this PLAN by slug.
- AMEND: `docs/adr/0006-three-layer-health-audit.md`:
  - Status field → `Superseded by [ADR-0007](0007-two-layer-health-audit.md) (2026-05-22)`.
  - Append `## Reversal rationale` section (1-2 paragraphs) referencing 2026-05-22 runtime observation (12 items → 1 accept), citing this PLAN slug + RESEARCH doc slug.
- AMEND (verify-then-edit): `specs/SPEC-tpl-health-md.md` + `.machine.yaml`:
  - Current skeleton ACs do not reference external_risks per Read. If grep `external_risks\|research-crawler\|relevance-filter` returns hits → update; else leave unchanged.
- AMEND: `CLAUDE.md`:
  - Grep for `3-layer health`, `external_risks`, `research-crawler`, `relevance-filter`. Remove or rewrite each occurrence to reflect 2-layer health.
- UPDATE: `CHANGELOG.md` `[Unreleased]`:
  - Add `### Removed` section:
    - external_risks dashboard layer (per ADR-0007)
    - `research-crawler` skill
    - `relevance-filter` skill
    - `harness-maker health-finalize` subcommand
    - `harness-maker health --skip-llm` flag
    - 4-source crawler modules: `anthropic_blog.py`, `arxiv.py`, `github_releases.py` (osv_dev preserved)
    - Stale-asset detection (no production caller; ADR-004)
    - Verify Check 4 (external_risks)
  - Add `### Migration` paragraph:
    - "Optional: existing users may `rm -rf .claude/observability/health/raw-*.jsonl .claude/observability/health/decisions.jsonl .claude/observability/.health-external-risks.tmp.json` to clean orphan artifacts. These are gitignored and harmless to leave."
  - Tag version `0.22.3` with release date.
- 5-file version sync (`0.22.2` → `0.22.3`):
  - `pyproject.toml` `[project].version`
  - `src/harness_maker/__init__.py` `__version__`
  - `.claude-plugin/plugin.json` `version`
  - `.cursor-plugin/plugin.json` `version`
  - `.codex-plugin/plugin.json` `version`

**Exit criterion:**
```bash
# Version sync — exactly 5 files at 0.22.3:
{ grep -l '^version = "0.22.3"' pyproject.toml; \
  grep -l '__version__ = "0.22.3"' src/harness_maker/__init__.py; \
  grep -l '"version": "0.22.3"' .claude-plugin/plugin.json .cursor-plugin/plugin.json .codex-plugin/plugin.json; \
} | sort -u | wc -l   # must show 5

# ADR cross-references intact:
grep -l "ADR-0007" docs/adr/0006-three-layer-health-audit.md   # must exist
grep -l "supersedes ADR-0006\|supersedes \[ADR-0006\]" docs/adr/0007-two-layer-health-audit.md   # must exist

# Non-ADR scrubbing complete:
grep -rn "3-layer health\|external_risks\|research-crawler\|relevance-filter" \
  CLAUDE.md specs/SPEC-tpl-health-md.md specs/SPEC-tpl-health-md.machine.yaml
# Must show: ZERO

# CHANGELOG has [Unreleased] → 0.22.3 entry with ### Removed:
grep -A 30 "0.22.3" CHANGELOG.md | grep -c "### Removed"   # 1
```

**Risk:** low. **Rollback point:** revert Phase 5 commit.

## Phase 6 — Re-render rendered assets in this repo

**Scope (files in — deletions):**
- `.claude/skills/research-crawler/` (entire dir)
- `.claude/skills/relevance-filter/` (entire dir)
- `.agents/skills/research-crawler/` (Codex path)
- `.agents/skills/relevance-filter/` (Codex path)
- `.claude/observability/.health-external-risks.tmp.json` (orphan tmp file)
- `.claude/observability/.health.tmp.json` (verify before delete — likely orphan)

**Scope (files in — re-render):**
- Run `uv run harness-maker make --update` to re-render templates with 2-layer health.
- Verify `.claude/commands/hm/health.md` no longer has Step 2.
- Verify `.cursor/rules/harness.mdc` no longer describes 4-source.

**Scope (files out):**
- `.claude/observability/health/raw-*.jsonl` (user-side data; leave; gitignored)
- `.claude/observability/health/decisions.jsonl` (user-side data; leave; gitignored)

**Exit criterion:**
```bash
ls .claude/skills/ .agents/skills/ 2>/dev/null | grep -E "research-crawler|relevance-filter" | wc -l   # 0
grep -n "Step 2\|external_risks\|research-crawler\|relevance-filter" \
  .claude/commands/hm/health.md .cursor/rules/harness.mdc 2>/dev/null   # ZERO
```

**Risk:** low. **Rollback point:** revert Phase 6 commit.

## Phase 7 — Wrapup

**Scope:**
- Standard `/hm:wrapup`: stage + commit + tag v0.22.3.
- Skip push (per CLAUDE.md "사용자가 명시적으로 요청해야 push").
- Wiki entry in `.claude/memory/wiki.md`:
  - `[wiki:pattern] adr-supersession-precedent-2026-05-22` — document the supersession form (Status field update + Reversal rationale appendix in old ADR; cross-link in new ADR), cite first-instance status.
  - Cross-reference `[wiki:pattern] breaking-enum-change-pre-flight-grep-discipline` (2026-05-22) — validator's 10 string-literal warnings confirmed the pattern; this PLAN's per-phase explicit grep scope is the application.

**Exit criterion:**
```bash
git status   # clean
git log -1 --format='%s'   # matches conventional-commits subject
git tag --list v0.22.3   # exists
```

**Risk:** low. **Rollback point:** N/A (final phase; revert at commit-level if needed).

# 🧪 Testing Strategy

**Unit tests (Phase 1-4):**
- Phase 1 — `test_memory_retrieve*.py` to confirm WORD_RE inline relocation preserves tokenizer behavior.
- Phase 2 — `test_synthesize*.py`, `test_interview*.py`, `test_communication_audit*.py` to confirm `_ALL_SKILLS` / `PINNED_SKILLS` removal doesn't break skill-discovery logic.
- Phase 3 — full `uv run pytest -x` after dashboard.py + cli.py edits. `mypy --strict` catches signature mismatches.
- Phase 4 — full `uv run pytest -x` after module deletions. `bash .claude-verify.sh phase_5` and `final_acceptance` to confirm verify-script integrity.

**Integration tests:**
- Phase 3 — `tests/integration/test_health_dashboard_roundtrip.py` updated to 2-layer fixture; verify round-trip Python emit → Claude personalization append → parse.
- Phase 4 — `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -x` (release procedure boundary-advisory gate).

**E2E tests:**
- Phase 3 — `tests/e2e/test_verify_health_dashboard.py` updated to 5-check verify (was 6).
- Phase 6 — manual smoke after `harness-maker make --update` re-render: open `.claude/commands/hm/health.md` and verify Step 2 absent.

**Snapshot tests:**
- Phase 2 — `uv run pytest tests/snapshot` after template edits. Snapshot regen runs on `main` after worktree finalize (per `[wiki:pattern] snapshot-regen-on-main-not-worktree-discipline`).

**Manual verification (after Phase 6):**
- Invoke `/hm:health` in this repo; confirm dashboard.md has 2 sections (Structural / Personalization), no External risks.
- Invoke `/hm:verify`; confirm 5 checks numbered 1-5, no Check 4 placeholder.

# ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hidden consumer of `relevance.py` outside surfaced 8 surfaces | low | high | Phase 1 + Phase 4 explicit `grep -rn` exit criteria scope every flagged surface (validator-derived inventory) |
| `secscan/dependency_cves.py` `osv_dev` import regression after Phase 4 | low | high | `crawler/__init__.py` preserves `osv_dev` export; Phase 4 exit runs `INTEGRATION=1 boundary_*` regression tests |
| Snapshot regen drift across 2 presets × 3 IDEs after Phase 2/6 | medium | medium | Phase 2 exit runs `tests/snapshot`; Phase 6 re-runs full make → snapshot diff visible in commit |
| Mypy-invisible string-literal misses (PINNED_SKILLS, _ALL_SKILLS, SOURCE_TTLS, docstrings, dict keys) | low | medium | Validator-driven inventory; per-phase `grep -n` exit criteria scope every identified file |
| `.claude-verify.sh` `final_acceptance()` overlooked | low | medium | Phase 4 exit explicitly runs `bash .claude-verify.sh final_acceptance` (validator second-pass finding) |
| Verify command Check 4 dangling post-Phase 3 (`_emit_verify_text` `/6` hardcoded) | low | medium | Phase 3 scope explicitly converts denominator to `f"/{total}"` dynamic; exit grep `grep -c '"/6"'` returns 0 |
| Worktree-finalize untracked-loss for `work-docs/` (2026-05-22 lesson) | medium | medium | PLAN + RESEARCH written to base `work-docs/`; only source edits go to worktree |
| ADR-002 patch-bump: hypothetical external scripter Makefile uses `health-finalize` | low | low | Accepted risk per ADR-002 Consequences; CHANGELOG `### Removed` documents the surface change |
| Migration: existing user dashboards retain stale `## External risks` section | medium | low | Parser drops the key; next `/hm:health` regenerates clean; documented in ADR-0007 Consequences |
| WORD_RE ASCII-only regex doesn't tokenize Korean (existing bug; out of scope here) | high | low | Conservative preserve-byte-identical inline (`[A-Za-z0-9_]+`); explicit out-of-scope note in PLAN; file follow-up task in `failures.md` if user wants |

# ✅ Success Criteria

All 7 phases land green per their exit criteria, and at end:

- [x] `uv run pytest -x` green
- [x] `uv run mypy --strict src/` green
- [x] `uv run ruff check . && uv run ruff format --check .` green
- [x] `bash .claude-verify.sh all` green (or at minimum `phase_5` + `final_acceptance`)
- [x] `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -x` green
- [x] `git grep -E "anthropic_blog|github_releases|arxiv\.py|relevance\.py|research-crawler|relevance-filter|external_risks|health-finalize|3-layer"` returns ONLY:
  - 5-file version-sync paths (harmless)
  - `docs/adr/0006-three-layer-health-audit.md` (intentional historical record)
  - `docs/adr/0007-two-layer-health-audit.md` (intentional cross-reference)
  - `CHANGELOG.md` `[Unreleased]` `### Removed` block (intentional)
  - `work-docs/PLAN-hm-health-crawl-removal.md` + `RESEARCH-hm-health-crawl-removal.md` (intentional)
  - `.backup-*` paths (ignored)
- [x] `/hm:health` produces 2-section dashboard (Structural + Personalization), no External risks
- [x] `/hm:verify` produces 5 checks (no Check 4)
- [x] `harness-maker --help` does not list `health-finalize`
- [x] `secscan/dependency_cves.py` still resolves `osv_dev.crawl` (verified by `/hm:verify` smoke + `INTEGRATION=1` boundary test)
- [x] 5-file version sync at `0.22.3`
- [x] ADR-0006 status field shows `superseded by ADR-0007`
- [x] CHANGELOG `[Unreleased]` documents removal under `0.22.3`
- [x] Tag `v0.22.3` exists locally (push deferred per CLAUDE.md)

# 🔍 Plan Validation

**First pass (sonnet plan-validator agent):** `MAJOR_REVISION` — 3 critical + 7 warning critiques.

| Critique | Severity | Resolution |
|----------|----------|------------|
| Phase 1 missed stale-asset code in relevance.py:200-435 (test_relevance_stale.py imports StaleAsset directly) | critical | Round 2 user decision → delete with relevance.py (ADR-004); added to Phase 4 scope; test deletion explicit |
| Phase 3 missed `_verify_external_risks_check` + `verify_stage_cmd` Check 4 + `verify.md.j2` Check 4 description | critical | Added to Phase 3 scope (all 3 files) |
| `.claude-verify.sh` phase_5 + skill assertions + R2 anti-rot import break post-deletion | critical | Added to Phase 4 scope (5 line-range edits) |
| `communication_audit.py:25` PINNED_SKILLS contains 'relevance-filter' | warning | Added to Phase 2 scope |
| `synthesize.py:118` + `interview.py:109` `_ALL_SKILLS` lists | warning | Added to Phase 2 scope |
| `cache.py:88` SOURCE_TTLS dict 3 dead keys | warning | Added to Phase 4 scope |
| `templates/cursor/rules/harness.mdc.j2:120` 4-source description | warning | Added to Phase 2 scope |
| ADR-002 patch-bump needs explicit accepted-risk + evidence in ADR-0007 | warning | ADR-002 (above) now contains 3 explicit accepted-risk items with evidence |
| `spec_inventory/{batch_generator,catalog}.py` string-literal classifications | warning | Added to Phase 4 scope |
| `models.py:212-216` CrawlItem docstring | warning | Added to Phase 4 scope |

**Second pass (sonnet plan-validator agent):** `NEEDS_REVISION` — 5 warning, 0 critical.

| Critique | Severity | Resolution |
|----------|----------|------------|
| `cli.py:703` second "3-layer" string outside Phase 2/5 scope | warning | Added to Phase 2 scope (alongside :552) |
| `cli.py:1709` `_emit_verify_text` hardcoded `/6` denominator | warning | Added to Phase 3 scope — change to `f"/{total}"` dynamic; exit grep verifies |
| `cli.py:992-996` `--skip-llm` flag dangling on `health` after external_risks removal | warning | Added to Phase 3 scope — delete flag definition + body |
| Phase 1 WORD_RE: original ASCII-only `[A-Za-z0-9_]+`, plan proposed `\w+` (Unicode = scope creep) | warning | Resolution: preserve byte-identical `[A-Za-z0-9_]+` (Korean tokenization improvement is out-of-scope; risk register documents) |
| Phase 4 exit doesn't run `.claude-verify.sh final_acceptance()` (only `phase_5`) | warning | Added `final_acceptance` to Phase 4 exit criterion (alongside `phase_5`) |

**Outcome:** `NEEDS_REVISION_RESOLVED`. All 10 first-pass + 5 second-pass critiques folded into phase scopes or accepted-risk ADR entries.

**Re-validation policy:** procedure permits only one re-validator pass; second pass returned no critical findings; resolution is direct edit into PLAN scope. No third pass required.
