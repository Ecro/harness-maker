---
type: spec
task_slug: sdlc-three-loops-gap
status: approved
created: 2026-09-27
tags: [harness-maker, spec, python, memory, intent-layer, knowledge]
test_framework: pytest
tier: 2
interview_rounds: 3
research_doc: "[[RESEARCH-sdlc-three-loops-gap]]"
summary: "Remove the dead JSONL memory tier; route intent-bearing claims to intent questions in both skills"
---
# Knowledge-loop cleanup: dead memory tier + fact/question boundary

## 🎯 Intent

External feedback claimed the Mission and Knowledge loops are empty or scattered. RESEARCH
refuted "empty" and found that the store count is not the problem; two concrete defects
survived: an unused JSONL memory tier in `harness_maker.memory`, and two stores
(`[wiki:fact]` and intent questions) that both record "what is true / what was refuted" with no
stated boundary. This task removes the first and draws the second — in the rule text **and** in
the project-knowledge procedure that currently routes every claim to the wiki.

## 🌅 Outcomes

- `harness_maker.memory` contains only live code (`_locking`); nothing in `src/` or `tests/`
  imports or uses the removed JSONL tier, and `memory_md` write paths still take the lock.
- An agent deciding where a new claim goes reads the same rule in both the project-knowledge and
  intent-layer skills; project-knowledge's description, body and procedure agree with it, and
  both skills say how to link a claim from the other store.
- Consumer projects that still hold `.claude/memory/{semantic,episodic,profile}/` directories
  see no change in worktree dirt classification.

## 📋 In-Scope Scenarios

### S1: Dead tier is gone, locking survives
**Given** the package source
**When** code imports `harness_maker.memory.episodic`, `.semantic`, `.profile` or `.retrieval`
**Then** the import fails with `ModuleNotFoundError`
**And** every `memory_md` write path (wiki upsert, failure append, session append) still acquires
`harness_maker.memory._locking.exclusive_lock`
**And** docstrings that contrast `memory_retrieve` with the removed `MemoryRetriever` are updated

### S2: Legacy directories stay harness churn
**Given** a consumer project with files under `.claude/memory/{semantic,episodic,profile}/`
**When** the create-guard and finalize dirt filters classify them
**Then** they are still treated as harness churn, not user dirt

### S3: One boundary rule, rendered twice, cross-referenced
**Given** a freshly rendered harness
**When** the rendered project-knowledge and intent-layer `SKILL.md` are read
**Then** both contain the locked boundary sentence verbatim
**And** each names the other skill

### S4: project-knowledge no longer routes intent-bearing claims to the wiki
**Given** the rendered project-knowledge skill
**When** the DRI asks to record a new claim that bears on an intent's metric or decision
**Then** its description, body and procedure hand that claim to the intent-layer skill (whose
consent rule governs the write) instead of `upsert-wiki`
**And** the skill states both link directions: a `[wiki:fact]` names the related question id in
its body; an intent question cites the fact with `--locator .claude/memory/wiki.md:<A-B>`

### S5: Removal is announced
**Given** the CHANGELOG `[Unreleased]` section at wrapup
**When** it is read before landing
**Then** it states the removal of `EpisodicStore`, `SemanticStore`, `ProfileStore`,
`MemoryRetriever` and the accepted `wiki_fact_entries_28d` window effect

Locked boundary sentence (golden, DRI-chosen in Round 2 — "intent decision" criterion):

> A claim that bears on an intent's metric or decision is an intent question (`hm intent question`, open → confirmed or wrong); any other domain fact is a `[wiki:fact]`. Record each claim in one place only and link to it from the other.

## 🚫 Non-Goals

- Merging `[wiki:fact]` and intent questions into one store.
- Migrating existing records: the rule applies to **new** claims only. The one existing
  `[wiki:fact]` (`mission-context-loop-outcome`) stays as it is.
- A "re-run the same task" step in the Knowledge loop.
- Two-person (lead approves / DRI proposes) mode or enforced `owners` separation — out of charter.
- Measuring any `never_measured` metric; their windows are open by design.
- Removing the three `.claude/memory/{semantic,episodic,profile}/` churn entries or gitignore lines.
- Behavioral evaluation of whether agents actually route claims by the rule.
- A built-wheel install check (Codex finding; rejected — `uv_build` packages the source tree and
  release CI builds from a fresh checkout).
- Fixing the stale `_HARNESS_CHURN_PREFIXES` name in CLAUDE.md (noted for wrapup, not an AC).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo standard (CLAUDE.md) |
| Type / lint | `mypy --strict`, `ruff` clean | Repo standard |
| Snapshots | Rendered-skill snapshots regenerated in the task worktree | Memory: snapshot regen in worktree is correct |
| Skill size | Both SKILL.md stay ≤ 300 lines | Context Lint |
| Compatibility | `_HARNESS_CHURN_DIRS` memory entries unchanged | Existing consumer dirs must not become user dirt |
| Measurement window | **Accepted contamination** (DRI, Round 3): the rule lands inside the `wiki_fact_entries_28d` window (2026-09-19..10-17) and diverts intent-bearing claims out of `[wiki:fact]`. The landing date is recorded in the CHANGELOG so the 10-17 reading can be interpreted against it; the pre-registered thresholds are not changed. | Honors the pre-registered rule while disclosing the input change |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Remove `EpisodicStore`, `SemanticStore`, `ProfileStore`, `MemoryRetriever` from the published `harness_maker.memory` package | public API/CLI contract | Names disappear from a PyPI release; restoring them later is a new release, not an undo |

## Acceptance Criteria

### AC-001: Dead memory tier modules removed
Modules `episodic`, `semantic`, `profile`, `retrieval` under `harness_maker.memory` are not
importable, and no module in `src/` or `tests/` (except `tests/unit/test_memory_tier_removed.py`)
imports them or uses the four class names as identifiers (AST check; string literals and prose
are out of scope).

### AC-002: memory_md write paths still take the lock
Each `memory_md` write path — wiki upsert, failure append, session append — calls
`exclusive_lock` at least once.

### AC-003: Legacy memory-tier dirs stay harness churn
Files under the three legacy memory-tier directories are classified as harness artifacts by the
existing dirt-filter tests, and `_HARNESS_CHURN_DIRS` still lists the three prefixes.

### AC-004: Boundary rule rendered in both skills
Both rendered skills contain the locked boundary sentence verbatim and name the other skill.

### AC-005: project-knowledge routes intent-bearing claims to intent-layer
The rendered project-knowledge description and procedure name the intent-layer skill for
intent-bearing claims, and the skill states the wiki-locator link direction.

### AC-006: Removal and window effect recorded in CHANGELOG
The `[Unreleased]` section names the four removed classes and the accepted window effect —
checked once at wrapup, not by a permanent test (the section is renamed at release).

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `tests/unit/test_memory_tier_removed.py::test_dead_tier_not_importable`, `::test_no_imports_remain`, `::test_memory_md_writes_take_lock` |
| S2 | unit | `tests/unit/test_worktree_churn_pollution.py::test_is_harness_artifact_recognizes_churn`, `tests/unit/test_worktree_task_lifecycle.py::test_path_owner_machine_memory_tiers_are_operational`, `tests/unit/test_memory_tier_removed.py::test_churn_dirs_retained` |
| S3 | unit | `tests/unit/test_memory_tier_removed.py::test_boundary_rule_in_both_skills` |
| S4 | unit + review | `tests/unit/test_memory_tier_removed.py::test_project_knowledge_routes_intent_claims`; `/hm:review` reads the full rendered skill for leftover contradictions |
| S5 | manual (wrapup) | Before land, read `CHANGELOG.md` `[Unreleased]`: four class names + window note present |

## 🔎 Spec Validation

spec-validator pass 1: **MAJOR_REVISION** (advisory). Codex second opinion: invoked, 7 findings
(5 accepted, 2 rejected). Resolved in Round 3: critical "project-knowledge contradicts the rule"
→ S4/AC-005; window contamination → Constraints (accepted by DRI); existing records → Non-Goals
(new claims only); AC-001 AST scope; AC-003 real constant + behavioural tests; lock-acquisition
AC-002; AC-004 mutual reference; AC-005→AC-006 one-time wrapup check. Rejected: "changelog text
saying kept" (contrived), built-wheel check (see Non-Goals).

## ❓ Open Questions

(none)

## 🔍 Refinement Decisions

- Round 1: scope = dead tier removal + boundary statement; two-person mode = non-goal; intent
  link = none.
- Round 2: boundary criterion = "bears on an intent decision"; legacy churn entries kept;
  IRR-001 recorded; no new intent drafted.
- Step 1 correction: `wiki_fact_entries_28d` window open until 2026-10-17 — RESEARCH amended.
- Round 3: boundary lands now with the window contamination accepted and disclosed;
  project-knowledge procedure rewritten to match; new claims only; DRI approved.
