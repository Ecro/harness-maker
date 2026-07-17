---
type: plan
task_slug: health-consolidation
status: planning
created: 2026-05-16
tags: [harness-maker, plan, refactor, observability, ai-readiness, refresh, personalization-audit, health, reconcile]
interview_rounds: 9
adrs: 6
validator_outcome: APPROVED_PRE_MERGE_REBASE
summary: "Consolidate /hm:ai-readiness + /hm:refresh + /hm:personalization-audit into /hm:health; add reconcile orphan-sweep"
---

# PLAN: Health Consolidation

## 🎯 Executive Summary

**TL;DR.** Replace three audit-like commands (`/hm:ai-readiness`, `/hm:refresh`, `/hm:personalization-audit`) with a single `/hm:health` command that exposes three orthogonal layers: **structural** quality (ai-readiness), **external risks** (refresh's anti-rot signals), and **personalization** accuracy (ADR-011 rubric). Drop only `version-drift` detection (SessionStart hook already covers it); keep arxiv as a refresh source (a recent wiki refresh proved its value — `785179e` archived 4 arxiv entries). Scores remain **separated** in `dashboard.md` (three fields, not averaged). Refresh's "no auto-apply" hard rule extends to the entire command. Add `content_hash`-gated orphan-sweep to `reconcile()` so the three legacy commands actually get cleaned up.

**Why.** Three audit commands fragment the user mental model. Three rubrics scoring orthogonal concerns is fine, but three command surfaces with overlapping vocabulary is not. The static quality (ai-readiness), the external-world signal (refresh's 3 remaining crawlers + stale-asset scan), and the recommendation-accuracy signal (personalization audit) all answer "is my harness healthy?" through different lenses — they belong under one verb. Orphan-sweep is reusable beyond this PR: every future command removal benefits.

**Key decisions (ADRs).**
- ADR-001: Auto-fix forbidden. All items route through `accept` / `reject` / `defer`.
- ADR-002: Scores stay split. Three fields (`structural`, `external_risks`, `personalization`). Amended by ADR-006.
- ADR-003: No deprecation window. Three legacy commands removed atomically; relies on ADR-005.
- ADR-004: No observability-file compatibility shim.
- ADR-005: Reconcile gains `content_hash`-gated orphan-sweep (file-level analogue of the block-level `_orphans` quarantine already in `block_merge.py`).
- ADR-006: `/hm:health` absorbs `/hm:personalization-audit`; ADR-011's rubric and module are reused unchanged.

**Estimated impact.** ~850 LOC delta (orphan-sweep ~150, personalization integration ~100 net beyond the earlier estimate) across `src/harness_maker/`, ~5 templates removed/created, 1 verify-stage rewrite, 5-file version bump (0.12.1 → 0.13.0). Baseline drifted 0.12.0 → 0.12.1 during execute (main commits d69289b, 438faa6, 9d20c90) — target 0.13.0 unchanged.

## 📚 Prior Work

- `PLAN-llm-code-review-2026.md` — established Health-score-based verify gate; this PLAN preserves Check 3 by keeping `structural` semantics intact.
- `PLAN-personalization-depth-2026-05` (merged as `0296eed`) — established `personalization_audit.py` module + ADR-011 (L1×0.4 + L2×0.3 + L3×0.3 rubric). This PLAN reuses both unchanged; only the command surface changes.
- `.claude/skills/research-crawler/SKILL.md` and `.claude/skills/relevance-filter/SKILL.md` — existing anti-rot architecture. We keep all four sources (incl. arxiv); drop one signal (version-drift) duplicated by the SessionStart drift hook.
- `src/harness_maker/block_merge.py` (lines 285-599) — block-level `_orphans` quarantine pattern. ADR-005 is the file-level analogue: same fingerprint principle, broader scope.
- CLAUDE.md "사용자 상태 보존 계약" pre-fix checklist Items 1 + 5 — ADR-005 is the canonical example of fingerprint-based auto-upgrade vs preserve.
- CLAUDE.md "버전업 정책" — 5-file version sync (Phase 4 exit criterion).
- Recent commits: `785179e` (4 arxiv entries archived to wiki) confirmed arxiv produces value; `0296eed` (personalization-depth, 12 phases, 0.12.0 bump) added the third audit surface.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Stage separation | Architecture | Should `/hm:verify` collapse into `/hm:wrapup`? | No — atomic-stage principle. | — |
| 2 | Refresh ownership | Scope | Is refresh user-facing or hm-internal? | Mixed (4/6 user-facing). | — |
| 3 | Auto-fix policy | Risk | Auto-fix or ask? | Always structured question. | ADR-001 |
| 4 | Score / dashboard merge | Architecture | One score or split? | Split scores; merge dashboard only. | ADR-002 |
| 5 | Deprecation policy | Risk | How long do legacy commands survive? | Immediate removal. | ADR-003 |
| 6 | Observability compat | Contract | Migrate or break? | Break. No shim. | ADR-004 |
| 7 | Orphan handling | Architecture | Build a reconcile sweep? | Yes — content_hash-gated. | ADR-005 |
| 8 | personalization-audit relationship (merge-rebase) | Architecture | Keep separate, dashboard-only merge, or full absorb? | Full absorb into `/hm:health`. | ADR-006 |
| 9 | arxiv removal re-confirm (merge-rebase) | Scope | Drop arxiv given wiki uses it? | Keep arxiv; drop version-drift only. | (scope-only, no ADR) |

## 📐 Architecture Decision Records

### ADR-001: Health uses structured-question gating for all items
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** `/hm:ai-readiness` auto-fixes "AI-fixable" items; `/hm:refresh` forbids any auto-apply (hard rule); `/hm:personalization-audit` is read-only by ADR-011 design. Consolidation needs one policy.
**Decision:** Adopt the strictest stance. Every health item — across all three layers — routes through one structured question (`accept` / `reject` / `defer`). No silent fixes, ever. For personalization ActionItems, this preserves ADR-011's "audit is read-only" contract.
**Consequences:**
- ✅ One mental model across three layers.
- ✅ Eliminates silent dependency bumps, settings.json rewrites, or default-value flips.
- ⚠️ More clicks for items ai-readiness used to fix unattended.
**Rejected alternatives:**
- Per-layer branching (structural=auto, others=ask) — fuzzy boundary; reintroduces the schism.
- Full auto-fix with P0-security carve-out — user favored the conservative side.
**Source:** Interview #3

### ADR-002: Scores stay split; only dashboard merges
**Status:** Accepted (2026-05-16, via /hm:plan interview). Amended by ADR-006 (third field).
**Context:** `/hm:verify` Check 3 reads a Health delta. Collapsing health into one number kills the ability to distinguish "my code regressed" from "outside world changed" from "my recommendations are drifting".
**Decision:** Three fields in `dashboard.md`: `structural: <0-100>`, `external_risks: <int pending count at relevance ≥ 0.8>`, `personalization: <0-100 composite>`. Verify Check 3 reads `structural`; Check 4 reads `external_risks`; **verify does NOT gate on personalization** (it is a drift signal, not a correctness signal). No averaging.
**Consequences:**
- ✅ Verify's two existing checks survive intact.
- ✅ Clean separation of three orthogonal signals.
- ⚠️ Three numbers to interpret. Dashboard layout (one section per layer) handles this.
**Rejected alternatives:**
- Unified Health score — conflates orthogonal signals; Check 4 would have to die.
**Source:** Interview #4, amended by Interview #8

### ADR-003: Immediate removal of three legacy commands; `/hm:make --update` reconciles
**Status:** Accepted (2026-05-16, via /hm:plan interview, expanded for ADR-006). Depends on ADR-005.
**Context:** Users have rendered `/hm:ai-readiness`, `/hm:refresh`, and `/hm:personalization-audit` into harness directories. A new release deleting all three must handle existing files.
**Decision:** Remove the three command templates atomically in 0.13.0. Reconcile's new orphan-sweep (ADR-005) deletes rendered files where `content_hash` matches "ours"; preserves user-edited copies with a warning. No deprecation window, no shim, no forwarding alias. Same policy for all three commands.
**Consequences:**
- ✅ One audit command in the rendered harness.
- ✅ Zero compatibility branches.
- ⚠️ Users with edited copies must delete manually; warning surfaces this.
**Rejected alternatives:**
- 1-minor deprecation window — 0.x alpha justifies aggressive change.
- Permanent alias — defeats consolidation.
**Source:** Interview #5, expanded by Interview #8

### ADR-004: No observability-file compatibility shim
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** Existing harnesses have `.claude/observability/dashboard.md` (old schema), `.claude/observability/refresh/*.jsonl`, and `.claude/observability/adaptive/{overrides.jsonl, last-audit.txt}`. The release changes the first two; the third stays intact (personalization layer reads it as-is per ADR-011).
**Decision:** Hard cut for the first two. `dashboard.md` overwritten on first `/hm:health` run with the three-section schema. `refresh/` directory replaced by `health/`; old `refresh/` left for manual delete. Adaptive directory (`overrides.jsonl`, `last-audit.txt`) UNCHANGED — personalization layer continues to read the existing files. Verify Check 3/4 read only the new schema; missing prior treated as "no baseline → PASS".
**Consequences:**
- ✅ Cleaner code path; zero schema branching.
- ✅ Personalization telemetry (Phase 9 of personalization-depth) survives intact.
- ⚠️ User loses `decisions.jsonl` adaptive-threshold history; restarts from default 0.7. (Distinct from `adaptive/overrides.jsonl` — those are personalization recommendation overrides, kept intact.)
- ⚠️ First post-upgrade verify run sees no prior dashboard → "no-baseline PASS" (explicit reason string in JSONL).
**Rejected alternatives:**
- Auto-migration script — code complexity for low-value data.
- Dual-read compatibility — schema-drift footgun.
**Source:** Interview #6

### ADR-005: Reconcile gains content_hash-gated orphan-sweep
**Status:** Accepted (2026-05-16, via /hm:plan validator follow-up). File-level analogue of block-level pattern already in `block_merge.py`.
**Context:** `src/harness_maker/reconcile.py` (verified at 871c507 and HEAD) only iterates `blueprint.files` — files on disk but absent from the blueprint are never deleted. Without a sweep, ADR-003 cannot deliver. `block_merge.py` already implements the same fingerprint principle at the block level (`_orphans` quarantine for `<!-- @hm:user:* -->` markers, lines 285-599) — ADR-005 extends the pattern to whole files.
**Decision:** Extend `reconcile()` with an orphan-sweep pass:
1. Enumerate every file under `.claude/`, `.cursor/`, `.codex/`, `.agents/`, and root-level `AGENTS.md` (per targets enabled).
2. Compute the set of "expected" files = paths in `blueprint.files`.
3. For each on-disk file NOT in expected:
   - If frontmatter has `generated_by: harness-maker` AND `content_hash` matches the historical hash registry (stored at `.claude/.hm-render-manifest.jsonl`, append-only on every render) → delete silently.
   - Else (user-edited, lacking frontmatter, or unknown hash) → KEEP. Emit a one-line warning per file in `/hm:make --update` stdout AND append to `.claude/observability/orphans-<date>.jsonl`.
4. Bash / pure-text files (lack frontmatter by design) — look up the path in the historical manifest. If present with matching hash → delete. Otherwise KEEP.
**Consequences:**
- ✅ ADR-003 becomes implementable for all three commands at once.
- ✅ Reusable for every future command/skill removal.
- ✅ User edits never lost silently — fingerprint mismatch always preserves.
- ⚠️ New file `.claude/.hm-render-manifest.jsonl` introduced. Must be gitignored (Phase 0 template addition).
- ⚠️ One additional pass per render; `O(files in .claude/)` ≈ negligible at expected scale (< 500 files).
**Rejected alternatives:**
- ADR-003 weakening (rely on SessionStart drift to nag users into manual delete) — leaves three stale files indefinitely.
- Defer to a separate 0.14.0 PR — ADR-003 promised but undelivered creates a transitional limbo.
**Source:** Interview #7 (validator follow-up)

### ADR-006: /hm:personalization-audit absorbed into /hm:health; module + rubric unchanged
**Status:** Accepted (2026-05-16, via /hm:plan merge-rebase interview). Amends ADR-002.
**Context:** Commit `0296eed` (personalization-depth, Phase 10) added `/hm:personalization-audit` with a 3-layer rubric (ADR-011: L1×0.4 + L2×0.3 + L3×0.3). The structure is parallel to `/hm:ai-readiness`'s rubric but measures an orthogonal concern (recommendation-conversion accuracy, not structural quality). Three audit commands fragment the user mental model.
**Decision:** `/hm:health` runs three layers in sequence:
1. **Structural** — existing ai-readiness Layer 1+3 (unchanged).
2. **External risks** — refresh's 3 remaining crawlers (anthropic_blog, github_releases, osv_dev) + arxiv + stale-asset scan + LLM relevance filter.
3. **Personalization** — invoke `harness_maker.personalization_audit.run()` (existing module, ADR-011 rubric UNCHANGED). The CLI surface for personalization audit (`harness-maker personalization-audit`) is REMOVED; the module is invoked only from inside `harness-maker health`. The slash command `/hm:personalization-audit` is removed atomically (ADR-003).
**Consequences:**
- ✅ One audit verb. Three layers visible in one dashboard.
- ✅ ADR-011 algorithm preserved bit-for-bit; no rubric drift.
- ✅ `adaptive/overrides.jsonl` and `last-audit.txt` continue to be read/written by `personalization_audit.run()` exactly as before.
- ⚠️ `harness-maker health` runtime grows by the personalization-audit cost (~100-500ms for typical projects). Acceptable.
- ⚠️ Phase 1 must wire the personalization module's output (composite score, ActionItems) into the new dashboard's third section.
**Amends ADR-002:** Adds a third dashboard field `personalization: <0-100>` alongside `structural` and `external_risks`. Verify Check 3/4 contracts UNCHANGED — verify does not read `personalization`.
**Rejected alternatives:**
- Keep separate commands — user explicitly chose absorption.
- Dashboard-only merge, commands separate — user explicitly chose full absorption.
- Rewrite ADR-011 rubric inside health — pointless churn; recent commit established it.
**Source:** Interview #8 (merge-rebase)

## 🏗️ Technical Design

### Current state (post `0296eed`)
- `/hm:ai-readiness` — 3-layer rubric → single Health score → dashboard.md → auto-fixes the AI-fixable bucket inline.
- `/hm:refresh` — crawl(blog, GH, arxiv, OSV) + stale-asset scan + version-drift → relevance-filter → proposed-`<date>`.md → per-item structured question.
- `/hm:personalization-audit` — `personalization_audit.run()` → 3-layer rubric (ADR-011) → composite score + ActionItems. Read-only.
- `reconcile.py` — iterates `blueprint.files`; no orphan-sweep.
- Verify Check 3 reads `Health: NN` from dashboard.md (single scalar).
- Verify Check 4 reads `refresh/pending.jsonl`.

### Affected components
| File | Change |
|------|--------|
| `src/harness_maker/relevance/__init__.py` | Drop `detect_version_drift`, `build_drift_lines` only |
| `src/harness_maker/ai_readiness/` | Split-score implementation (`structural` field) + integration hook for personalization (Phase 1) |
| `src/harness_maker/personalization_audit.py` | UNCHANGED (rubric and behavior preserved per ADR-006) |
| `src/harness_maker/cli.py` | Remove `ai-readiness*` + `refresh*` + `personalization-audit` subcommands; add `health` + `health-finalize` that internally orchestrates all three layers |
| `src/harness_maker/reconcile.py` | Add orphan-sweep with content_hash gating (ADR-005) |
| `src/harness_maker/render.py` | Append to `.hm-render-manifest.jsonl` on every render |
| `src/harness_maker/observability/dashboard.py` | New 3-section schema writer |
| `src/harness_maker/observability/` (paths) | `refresh/` → `health/` everywhere; `adaptive/` UNCHANGED |
| `src/harness_maker/templates/commands/hm/ai-readiness.md.j2` | DELETE |
| `src/harness_maker/templates/commands/hm/refresh.md.j2` | DELETE |
| `src/harness_maker/templates/commands/hm/personalization-audit.md.j2` | DELETE |
| `src/harness_maker/templates/commands/hm/health.md.j2` | CREATE (3-layer structured-question-only flow) |
| `src/harness_maker/templates/stages/verify.md.j2` | Check 3 reads `structural`; Check 4 reads `external_risks`; missing-prior = "no-baseline PASS"; `personalization` field NOT read by verify |
| `src/harness_maker/templates/skills/ai-readiness-rubric/SKILL.md.j2` | Description updated to reference `/hm:health` |
| `src/harness_maker/templates/skills/research-crawler/SKILL.md.j2` | Description updated; 4 sources still listed |
| `src/harness_maker/templates/skills/relevance-filter/SKILL.md.j2` | Description aligned |
| `src/harness_maker/templates/gitignore.j2` (or equivalent) | Add `.hm-render-manifest.jsonl` |
| `CLAUDE.md` | Replace `/hm:ai-readiness`, `/hm:refresh`, `/hm:personalization-audit` mentions with `/hm:health`; add one-line note "health is a command, not a stage; absorbs three predecessors as of 0.13.0"; the 7-item Atomic-stage list at line 145 UNCHANGED |
| `README.md` | Command table edit |
| `CHANGELOG.md` | 0.13.0 entry summarizing ADRs 1-6 |
| 5 version files | `0.12.0` → `0.13.0` |
| `tests/` | New unit + e2e files per Phase 0/1/3/4 scope below |

### Not changed (intentional)
- `src/harness_maker/crawler/arxiv.py` — KEPT (Interview #9). `feedparser` runtime dep KEPT. `test_arxiv.py` KEPT. TECH_SPEC.md arxiv references KEPT.
- `src/harness_maker/personalization_audit.py` — KEPT verbatim per ADR-006.
- `src/harness_maker/rubrics/personalization.yaml` — KEPT verbatim per ADR-006.
- `.claude/observability/adaptive/` directory and contents — KEPT per ADR-004 amendment.
- `src/harness_maker/recommendation.py`, `detection_cache.py`, `foreign_config.py`, `models.py`, `profile.py` (personalization-depth additions) — UNRELATED to this PR; KEPT.

### Architecture (target state)
```
/hm:health (single command, three layers)
    |
    +-- Step 1: structural
    |     -> ai_readiness Layer 1+3 (existing)
    |     -> writes `structural: NN` to dashboard.md
    |
    +-- Step 2: external_risks
    |     -> crawler/{anthropic_blog, github_releases, arxiv, osv_dev}.crawl()
    |     -> relevance.detect_stale_assets()
    |     -> LLM relevance filter
    |     -> writes `external_risks: N + items` to dashboard.md
    |
    +-- Step 3: personalization
    |     -> personalization_audit.run()    # ADR-011 rubric, unchanged
    |     -> writes `personalization: NN + ActionItems` to dashboard.md
    |
    +-- Step 4: atomic dashboard.md write (three sections)
    |
    +-- Step 5: per-item structured question (no auto-apply, EVER)
          accept -> patch file (stale-asset: update_last_reviewed_at; CVE: issue stub; structural gap: edit referenced file; personalization ActionItem: harness.yaml default change)
          reject -> append decisions.jsonl
          defer  -> keep in pending queue

reconcile() (target state)
    |
    +-- Pass 1: render every blueprint file (existing)
    +-- Pass 2: orphan-sweep (ADR-005)
          for each file under .claude/, .cursor/, .codex/, .agents/, AGENTS.md:
              if path in blueprint.files: skip
              elif fingerprint("ours") matches: delete
              else: keep + warn
```

### Data flow
- `dashboard.md` (new schema):
  ```yaml
  ---
  generated_by: harness-maker
  generated_at: <iso8601>
  ---
  # Health

  ## Structural
  score: NN / 100
  signals_failed: [...]

  ## External risks
  pending: N
  items:
    - source: osv.dev
      id: CVE-2026-...
      severity: high
      relevance: 0.82
      first_seen: <iso8601>

  ## Personalization
  composite: NN / 100
  tier: bronze | silver | gold | platinum
  layers:
    l1_conversion: 0.0-1.0
    l2_stability: 0.0-1.0
    l3_cadence: 0.0-1.0
  action_items: [...]   # ADR-011 evidence schema
  ```
- `.claude/observability/health/decisions.jsonl` — append-only audit log (all three layers).
- `.claude/observability/adaptive/overrides.jsonl` + `last-audit.txt` — UNCHANGED (read/written by `personalization_audit` module).
- `.claude/.hm-render-manifest.jsonl` — append-only registry for orphan-sweep "ours" check.

### API changes (CLI)
| Old | New |
|-----|-----|
| `harness-maker ai-readiness <root>` | `harness-maker health <root>` |
| `harness-maker ai-readiness-finalize ...` | `harness-maker health-finalize ...` |
| `harness-maker refresh-*` | (removed; folded into `health`) |
| `harness-maker personalization-audit <root>` | (removed; folded into `health`. Module API `personalization_audit.run()` UNCHANGED.) |

## 📝 Implementation Plan

### Phase 0 — Reconcile orphan-sweep + render manifest (framework groundwork)
**Scope (in):**
- `src/harness_maker/render.py` — append to `.hm-render-manifest.jsonl` on every file render (path + content_hash + timestamp)
- `src/harness_maker/reconcile.py` — orphan-sweep pass per ADR-005
- Helper: `is_ours(path, manifest)` — frontmatter-or-manifest lookup
- `src/harness_maker/templates/gitignore.j2` — add `.hm-render-manifest.jsonl`
- Unit tests:
  - `tests/unit/test_reconcile_orphan_sweep.py` — fixture matrix: ours-clean, ours-modified, theirs, missing-frontmatter-in-manifest, missing-frontmatter-not-in-manifest
  - `tests/unit/test_render_manifest.py` — manifest append idempotency, hash collision handling

**Scope (out):** any health command surface, template changes, version bump.

**Exit criterion:** `uv run pytest -q` GREEN; `uv run mypy --strict src/` GREEN; running `reconcile()` on a sandbox where a fake template was removed deletes "ours" copy and warns on "theirs" copy.

**Risk:** medium — touches framework that every render path goes through.

**Rollback point:** `main` (before any Phase 0 commit).

### Phase 1 — Core refactor (CLI + version-drift drop + split scores + dashboard 3-section writer + personalization integration + obs dir rename)
**Scope (in):**
- Drop `detect_version_drift` and `build_drift_lines` from `src/harness_maker/relevance/__init__.py` (and any caller). version-drift detection lives only in SessionStart drift hook now.
- Implement split scores in `src/harness_maker/ai_readiness/` — `structural` field for the existing 3-layer score.
- Wire `personalization_audit.run()` into the new dashboard third section. Mapping: composite → `personalization`, layers/action_items pass through.
- Rewrite `src/harness_maker/cli.py`:
  - REMOVE: `ai-readiness`, `ai-readiness-finalize`, `refresh*`, `personalization-audit` subcommands.
  - ADD: `health`, `health-finalize`. `health` orchestrates all three layers in order and writes the unified dashboard.md.
- New 3-section schema writer in `src/harness_maker/observability/dashboard.py`.
- Rename `refresh/` → `health/` everywhere in `src/harness_maker/observability/` (loaders + path constants). `adaptive/` UNCHANGED.
- Unit tests:
  - `tests/unit/test_relevance.py` — assert `detect_version_drift` no longer importable; `detect_stale_assets` unchanged; arxiv crawler still imported.
  - `tests/unit/test_ai_readiness.py` — assert split-score schema (`structural` field).
  - `tests/unit/test_observability_dashboard.py` — assert three-section markdown output; assert old single-scalar schema unparseable by new reader.
  - `tests/unit/test_cli.py` — assert removed subcommands not registered; `health` registered.
  - `tests/unit/test_health_personalization_integration.py` — assert `personalization_audit.run()` output flows into dashboard third section verbatim (composite, layers, action_items all present, ADR-011 rubric unchanged).

**Scope (out):** template files, verify-stage template, version bump, e2e tests, CLAUDE.md edits.

**Exit criterion:** `uv run pytest -q` GREEN; `uv run mypy --strict src/` GREEN; `uv run ruff check src/ tests/` GREEN; a unit-level sanity invocation of `harness-maker health` against a fixture project produces a 3-section `dashboard.md`.

**Risk:** high — three layers must orchestrate without breaking ADR-011 rubric or the existing personalization telemetry contract. The integration test gates this.

**Rollback point:** Phase 0 commit.

### Phase 2 — Templates: delete 3 legacy, create `health.md.j2`, update skills
**Scope (in):**
- DELETE `src/harness_maker/templates/commands/hm/ai-readiness.md.j2`
- DELETE `src/harness_maker/templates/commands/hm/refresh.md.j2`
- DELETE `src/harness_maker/templates/commands/hm/personalization-audit.md.j2`
- CREATE `src/harness_maker/templates/commands/hm/health.md.j2`:
  - Three sequential layers (structural / external_risks / personalization).
  - Structured-question-only flow at end (accept / reject / defer per item across all three layers).
  - No batching contract (ADR-001 accepts extra clicks).
- Update `src/harness_maker/templates/skills/ai-readiness-rubric/SKILL.md.j2` — description references `/hm:health` Step 1.
- Update `src/harness_maker/templates/skills/research-crawler/SKILL.md.j2` — description references `/hm:health` Step 2; 4 sources listed.
- Update `src/harness_maker/templates/skills/relevance-filter/SKILL.md.j2` — description aligned.
- Snapshot regeneration: `uv run python -m harness_maker.cli regenerate`.

**Scope (out):** verify-stage rewrite, e2e tests, version bump.

**Exit criterion:** `uv run pytest -q` GREEN (snapshot tests in particular); rendering a fresh sandbox produces `commands/hm/health.md` but none of the three legacy commands; orphan-sweep on an upgraded sandbox deletes all three legacy files (verified by sandbox fixture, not yet e2e).

**Risk:** low — pure template change; orphan-sweep (Phase 0) handles deletion in user harnesses.

**Rollback point:** Phase 1 commit.

### Phase 3 — Verify stage rewrite + new e2e fixtures
**Scope (in):**
- Update `src/harness_maker/templates/stages/verify.md.j2`:
  - Check 3 reads `structural` from new dashboard.md.
  - Check 4 reads `external_risks` from new dashboard.md.
  - Both checks emit explicit "no-baseline PASS" reason when prior dashboard absent or schema-mismatched.
  - `personalization` field NOT read by verify (ADR-002 amendment).
- CREATE `tests/e2e/test_verify_health_dashboard.py`:
  - Engineered delta cases (PASS / FAIL for Check 3 with structural deltas; PASS / FAIL for Check 4 with external_risks counts).
  - Missing-baseline case (dashboard.md absent → no-baseline PASS).
  - Pre-0.13.0 schema case (old single-scalar dashboard.md → treated as missing-baseline).
  - Personalization-field-present case (verify ignores it; no spurious PASS/FAIL).
  - Verify invocation via `subprocess.run(["uv", "run", "python", "-m", "harness_maker.cli", "verify", ...])` against `tmp_path` sandbox.
- CREATE `tests/e2e/test_reconcile_orphan_sweep.py`:
  - Sandbox at 0.12.0 fixture state with all three legacy commands rendered. Apply blueprint with all three removed; assert deletion + warning behavior for "ours" vs "theirs".

**Scope (out):** version bump, CLAUDE.md edits.

**Exit criterion:** `uv run pytest -q` GREEN including the two new e2e files; both new test files runnable in CI (no Claude binary required — pure CLI subprocess).

**Risk:** medium — verify is the autoloop M8 invariant. Silent regression breaks every autoloop iteration.

**Rollback point:** Phase 2 commit.

### Phase 4 — Docs + version bump + sandbox reconcile e2e
**Scope (in):**
- `CLAUDE.md` edit scope (explicit):
  1. Replace `/hm:ai-readiness`, `/hm:refresh`, `/hm:personalization-audit` references with `/hm:health` (grep for each).
  2. Add one-line note in the commands section: "Note: /hm:health is a command, not a stage. It absorbs three predecessors as of 0.13.0. The 7 atomic stages remain unchanged."
  3. Atomic-stage list at line 145 — **UNCHANGED**.
- `README.md` command table edit (three commands → one).
- `CHANGELOG.md` — 0.13.0 entry summarizing ADRs 1-6.
- 5-file version sync to `0.13.0`:
  - `.claude-plugin/plugin.json`
  - `.cursor-plugin/plugin.json`
  - `.codex-plugin/plugin.json`
  - `pyproject.toml`
  - `src/harness_maker/__init__.py`
- CREATE `tests/e2e/test_make_update_0_12_1_to_0_13_0.py`:
  - Render a fixture sandbox at the 0.12.1 state (commit hash `d69289b` or its tag).
  - Run `subprocess.run(["uv", "run", "python", "-m", "harness_maker.cli", "make", "--update"], cwd=sandbox)`.
  - Assert: `commands/hm/ai-readiness.md`, `commands/hm/refresh.md`, `commands/hm/personalization-audit.md` all gone; `commands/hm/health.md` present; `harness.yaml` stamped `0.13.0`.
  - Assert: user-edited legacy file (theirs fixture) preserved + warning in stdout.
  - Assert: `.claude/observability/adaptive/` directory untouched.

**Exit criterion:** All five version strings equal `0.13.0`; the new e2e asserts above hold in CI; `CHANGELOG.md` has a single 0.13.0 entry naming ADRs 1-6.

**Risk:** low — mechanical edits; e2e provides safety net.

**Rollback point:** Phase 3 commit.

## 🧪 Testing Strategy

- **Unit tests (Phase 0):**
  - `test_reconcile_orphan_sweep.py` — 5 fixture cases.
  - `test_render_manifest.py` — append idempotency, hash collision handling, multi-run survival.
- **Unit tests (Phase 1):**
  - `test_relevance.py` — `detect_version_drift` removed; arxiv still imported; `detect_stale_assets` unchanged.
  - `test_ai_readiness.py` — `structural` field schema.
  - `test_observability_dashboard.py` — 3-section markdown; old schema unparseable.
  - `test_cli.py` — 3 legacy subcommands removed; `health` registered.
  - `test_health_personalization_integration.py` — personalization_audit output mapped into dashboard third section verbatim; ADR-011 rubric output unchanged.
- **Snapshot tests (Phase 2):**
  - `uv run python -m harness_maker.cli regenerate` diff shows: deletions for three legacy command templates; addition for `health.md.j2`; modifications for three skill files.
- **E2E tests (Phase 3):**
  - `test_verify_health_dashboard.py` — engineered deltas + missing-baseline + old-schema + personalization-field-ignored cases.
  - `test_reconcile_orphan_sweep.py` — sandbox sweep on all three removed templates simultaneously.
- **E2E test (Phase 4):**
  - `test_make_update_0_12_0_to_0_13_0.py` — version-stamped fixture migration including `adaptive/` directory preservation assertion.
- **Manual (out-of-CI):**
  - Run `/hm:health` in this repo. Confirm dashboard.md has three sections, structured questions fire for each item, no silent fixes.
  - Run `/hm:verify` against the new dashboard.md and confirm Check 3 / Check 4 behave correctly on real data.

## ⚠️ Risks & Mitigation

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R1 | Verify Check 3 misreads new schema and silently PASSes | HIGH | Phase 3 e2e (engineered deltas + missing-baseline + old-schema cases) blocks merge. |
| R2 | Reconcile deletes user-edited legacy file silently | HIGH | ADR-005 + Phase 0 fixture matrix asserts "theirs" copies always preserved with warning. |
| R3 | personalization_audit integration breaks ADR-011 rubric (regression in conversion/stability/cadence math) | HIGH | Phase 1 `test_health_personalization_integration.py` asserts module output unchanged bit-for-bit. ADR-006 commits to verbatim reuse. |
| R4 | `adaptive/overrides.jsonl` accidentally swept by orphan-sweep (it lacks frontmatter and is not in blueprint.files) | HIGH | ADR-005 manifest-lookup falls back to KEEP when manifest entry absent. `adaptive/*` files are user-data, never rendered, so they never enter the manifest → KEEP. Phase 0 fixture must cover the "user-data file outside blueprint" case explicitly. |
| R5 | WSL2 NTFS path corrupts a file during snapshot regen | MEDIUM | All writes go through `atomic_write` (CLAUDE.md pattern). |
| R6 | 5-file version sync misses one manifest | MEDIUM | Phase 4 e2e asserts all five strings. CLAUDE.md version-up policy lists all five. |
| R7 | Orphan-sweep wrongly deletes a copy-pasted file with `generated_by: harness-maker` frontmatter | MEDIUM | ADR-005 requires BOTH `generated_by` AND `content_hash` in the historical manifest. Copy-paste lacks manifest entry → KEEP + warn. |
| R8 | `.hm-render-manifest.jsonl` missed from user gitignore | LOW | Phase 0 adds it to template gitignore; existing harnesses get it via block-merge marker on `/hm:make --update`. |
| R9 | Loss of `decisions.jsonl` (refresh's adaptive threshold history) confuses users | LOW (accepted) | ADR-004 accepts. Threshold restarts from default 0.7; convergence within ~5 decisions. |
| R10 | User had personalization recommendations queued in `adaptive/overrides.jsonl` that get re-presented in health's third layer (perceived duplication) | LOW | personalization_audit.run() already de-duplicates against `last-audit.txt` timestamp per ADR-011. Behavior unchanged. |

## ✅ Success Criteria

- [ ] `/hm:health` is the only audit-style command in the rendered harness.
- [ ] `dashboard.md` exposes `structural`, `external_risks`, and `personalization` fields with correct values on a real run.
- [ ] No item is auto-fixed by `/hm:health`; every action requires a structured-question response (across all three layers).
- [ ] Verify Check 3 reads `structural`; Verify Check 4 reads `external_risks`. Verify does NOT read `personalization`. Missing-baseline emits explicit "no-baseline PASS" reason.
- [ ] `personalization_audit.run()` module behavior unchanged — ADR-011 rubric output bit-identical to the pre-PR state on the same input.
- [ ] All five version files report `0.13.0`.
- [ ] `test_make_update_0_12_0_to_0_13_0.py` GREEN in CI: three legacy commands removed, health present, `adaptive/` preserved.
- [ ] arxiv crawler and `feedparser` dep retained; only `detect_version_drift` removed.
- [ ] CLAUDE.md 7-item Atomic-stage list at line 145 unchanged.
- [ ] `decisions.jsonl` records every structured-question answer across all three layers with timestamp + action.
- [ ] `.hm-render-manifest.jsonl` written on every render; consulted on every orphan-sweep.
- [ ] Orphan-sweep preserves "theirs" copies with explicit warning; deletes "ours" copies silently.
- [ ] `.claude/observability/adaptive/` directory untouched by `/hm:make --update` reconcile.

## 🔍 Plan Validation

**Round 1:** MAJOR_REVISION (3 critical + 5 warnings). Resolved by introducing ADR-005, Phase 0, explicit e2e test files, and tighter CLAUDE.md scope.

**Round 2:** APPROVED. All 8 Round-1 critiques returned `KEEP_RESOLVED`. Zero new concerns.

**Round 3 (merge-rebase update, 2026-05-16):** Post-`0296eed` reality check uncovered:
- `/hm:personalization-audit` command exists and parallels ai-readiness in structure → ADR-006 added, scope expanded from 2 to 3 absorbed commands.
- Version baseline shifted from 0.11.6 → 0.12.0 (already consumed by personalization-depth) → all version references updated to `0.12.1 → 0.13.0`. (Round 4 mid-execute drift: 0.12.0 → 0.12.1 landed on main during loop iter 1; fixture commit hash and test file name updated accordingly; target 0.13.0 unchanged.)
- arxiv usage validated by `785179e` (4 wiki entries) → Phase 1 stops removing arxiv; only `detect_version_drift` dropped.
- `block_merge.py` already implements block-level `_orphans` pattern → ADR-005 explicitly cites it as the file-level analogue (no algorithm reinvention).
- `adaptive/` directory must be preserved by orphan-sweep → R4 added with explicit fixture case.

Round 3 changes are scope refinements, not contradictions to Round 2 — re-validation is OPTIONAL. Frontmatter `validator_outcome: APPROVED_PRE_MERGE_REBASE` reflects that the architectural skeleton remains valid; surgical scope adjustments do not warrant a third full validator pass unless the user requests one.
