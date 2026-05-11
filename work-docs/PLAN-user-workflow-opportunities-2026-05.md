---
type: plan
task_slug: user-workflow-opportunities-2026-05
status: complete
created: 2026-05-11
tags: [harness-maker, plan, python, obsidian, second-brain, knowledge-graph]
research_doc: "[[RESEARCH-user-workflow-opportunities-2026-05]]"
interview_rounds: 8
adrs: 7
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Obsidian R/W Second Brain as a typed frontmatter/tag/link knowledge graph"
---

# PLAN - Obsidian Second Brain R/W Connector

## 🎯 Executive Summary

**What:** Implement the first user-workflow opportunity from `RESEARCH-user-workflow-opportunities-2026-05`: an Obsidian-targeted Second Brain connector with read/write access, full Markdown writes inside configured allowlisted vault folders, and typed notes that use frontmatter, tags, and links as first-class graph structure.

**Why:** harness-maker already has `ref_folders`, `refdocs_index`, `refdocs-search`, and `.claude/memory`, but those are either read-only reference search or repo-local memory. The next high-impact user workflow is a durable Obsidian knowledge graph that carries project decisions, preferences, failures, references, projects, and journals across sessions and directly improves stage behavior.

**Key Decisions:**
- ADR-001: Obsidian Second Brain R/W is the first product slice.
- ADR-002: Write authority covers full Markdown file writes inside allowlisted folders.
- ADR-003: Configured write allowlists are trusted completely.
- ADR-004: The first backend is raw filesystem Markdown, not Obsidian API/CLI.
- ADR-005: The information model is a typed knowledge graph, not plain vault search.
- ADR-006: Schema uses required core frontmatter plus recommended type-specific fields.
- ADR-007: First integration is stage-aware, not skill-only or command-only.

**Estimated impact:** Medium-high. The plan adds typed config, a new filesystem-backed module, stage-template guidance, index/retrieval support, and focused unit tests. It deliberately avoids Obsidian plugin/API dependencies.

## 📚 Prior Work

- `work-docs/RESEARCH-user-workflow-opportunities-2026-05.md`: recommends Second Brain first because it maps to the repeated user pain of re-explaining external context and fits existing `ref_folders`/memory infrastructure.
- `work-docs/RESEARCH-second-brain-obsidian-2026-05.md`: prior detailed Obsidian connector research referenced by the current research doc.
- `work-docs/PLAN-make-ux-gaps-2026-05.md`: established safe patterns for extending `HarnessConfig`, rendering YAML templates, and testing CLI/config round trips.
- `src/harness_maker/refdocs_index.py`: existing lossy metadata index for external docs; useful precedent for indexing Markdown frontmatter/headings while reading original files for answers.
- `src/harness_maker/models.py`: existing `RefFolder`, `HarnessConfig`, and `InterviewAnswers` schema patterns.
- `src/harness_maker/templates/stages/*.md.j2`: stage procedures are the right place for stage-aware retrieval/write guidance.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Product slice | Scope | Which first product slice should execute implement? | Second Brain / Issue intake / MCP safety / Evidence loop / Other | Second Brain first | Research recommendation accepted as the first slice. | ADR-001 |
| 2 | R/W requirement | Scope | Why read-only? Should R/W be required? | Read-only first / Draft-only / Direct R/W | Obsidian target with R/W required | User explicitly rejected read-only as insufficient. | ADR-001 |
| 3 | Write model | Contract | What write model should first implementation support? | Append/create / guarded blocks / full Markdown write / Local REST API / Other | Full Markdown file write in allowlisted folders | Highest-authority write model. | ADR-002 |
| 4 | Safety gate | Risk | What safety gate applies before vault writes? | confirm per write / audit+backup / tiered / trust allowlist / Other | Trust allowlist completely | No confirmation or backup for configured write folders. | ADR-003 |
| 5 | Backend | Architecture | What first backend? | filesystem / Obsidian CLI / Local REST API / abstraction / Other | Raw filesystem Markdown backend | Testable and avoids plugin/token setup. | ADR-004 |
| 6 | Information model | Architecture | What makes it a real Second Brain? | decision / reference / journal / hybrid typed | Hybrid typed with frontmatter, tags, links | User specified frontmatter, tags, and links as required graph structure. | ADR-005 |
| 7 | Schema strictness | Contract | How strict should first note schema be? | minimal / strict / core+recommended / infer / Other | Core schema plus type-specific recommended fields | Missing recommended fields warn rather than block. | ADR-006 |
| 8 | Workflow integration | Architecture | What is the first user-facing integration point? | skill-first / stage-aware / slash command / skill+stage / Other | Stage-aware integration | `hm-research`, `hm-plan`, `hm-review`, and `hm-wrapup` use typed notes directly. | ADR-007 |

## 📐 Architecture Decision Records

### ADR-001: Obsidian Second Brain R/W First
**Status:** Accepted (2026-05-11, via /hm:plan interview)
**Context:** The research doc ranks Second Brain as the strongest user-workflow opportunity. The user rejected a read-only interpretation because the desired product is a living Obsidian memory, not just external search.
**Decision:** The first implementation targets Obsidian/Markdown vaults and includes both read and write capabilities.
**Consequences:**
- ✅ Solves the repeated-context problem with a durable user-owned knowledge base.
- ⚠️ Expands the safety surface beyond existing read-only `ref_folders`.
**Rejected alternatives:**
- Issue intake first — Rejected because it has less direct fit with existing `ref_folders` and memory code.
- Read-only Second Brain — Rejected because it does not create a living Second Brain.
**Source:** Interview #1 and #2

### ADR-002: Full Markdown Writes Inside Allowlisted Folders
**Status:** Accepted (2026-05-11, via /hm:plan interview)
**Context:** R/W can mean append-only logs, guarded block updates, or arbitrary Markdown mutation.
**Decision:** The connector may create, overwrite, append, and exact-patch Markdown files within configured write-allowlisted Obsidian folders.
**Consequences:**
- ✅ Powerful enough to maintain decisions, preferences, failures, references, projects, and journals as real graph nodes.
- ⚠️ A broad allowlist can expose long-lived notes to accidental overwrite.
**Rejected alternatives:**
- Append/create only — Rejected as too weak for a useful knowledge graph.
- Guarded blocks only — Rejected as too constrained for natural Obsidian notes.
- Obsidian REST API as write authority — Rejected because it adds plugin setup and token handling to the first release.
**Source:** Interview #3

### ADR-003: Trust Configured Write Allowlists Completely
**Status:** Accepted (2026-05-11, via /hm:plan interview)
**Context:** Full Markdown writes need a concrete gate policy.
**Decision:** No per-write confirmation and no backup requirement apply once a path is inside a configured write allowlist.
**Consequences:**
- ✅ Low-friction stage operation; `hm-wrapup` can write learned notes without repeatedly stopping.
- ⚠️ User accepts that a bad allowlist can expose notes to overwrite or unwanted edits.
**Rejected alternatives:**
- Explicit confirmation per write — Rejected because it slows the intended workflow.
- Audit plus backup required — Rejected in favor of the fastest trusted-zone model.
- Tiered policy — Rejected because the user chose complete allowlist trust.
**Source:** Interview #4

### ADR-004: Raw Filesystem Markdown Backend First
**Status:** Accepted (2026-05-11, via /hm:plan interview)
**Context:** Obsidian CLI/API integration is more native but adds setup, plugin availability, token, and local service concerns.
**Decision:** Implement the first backend with Python filesystem operations over Markdown files.
**Consequences:**
- ✅ Deterministic tests with temporary vault fixtures.
- ✅ No runtime dependency on Obsidian desktop, CLI, plugins, or local network services.
- ⚠️ Obsidian-native behaviors such as live plugin commands and REST endpoints are out of scope.
**Rejected alternatives:**
- Obsidian CLI backend — Rejected because CLI availability and supported command surface vary by install.
- Obsidian Local REST API backend — Rejected because it requires a community plugin and auth token.
- Pluggable abstraction now — Rejected as premature until the filesystem contract lands.
**Source:** Interview #5

### ADR-005: Typed Knowledge Graph, Not Plain Vault Search
**Status:** Accepted (2026-05-11, via /hm:plan interview)
**Context:** A Second Brain is not a dump of raw documents. For harness-maker it must improve future decisions by preserving reusable judgment material.
**Decision:** Managed notes are typed graph nodes with YAML frontmatter, tags, and wiki-style links across `decision`, `preference`, `failure`, `project`, `reference`, and `journal` notes.
**Consequences:**
- ✅ Stages can retrieve only relevant memory types instead of loading the whole vault.
- ✅ Links/backlinks preserve why a decision, failure, or preference matters to a project.
- ⚠️ The connector must parse and preserve human-authored Markdown metadata.
**Rejected alternatives:**
- Untyped vault search — Rejected because it becomes private search rather than a Second Brain.
- Single-category memory — Rejected because decisions, preferences, failures, references, projects, and journals serve different stages.
**Source:** Interview #6

### ADR-006: Core Schema With Recommended Type Fields
**Status:** Accepted (2026-05-11, via /hm:plan interview)
**Context:** Schema must be machine-readable without making human note-taking brittle.
**Decision:** Every managed note requires common frontmatter fields: `type`, `created`, `updated`, `tags`, and `links`. Known note types have recommended fields that generate warnings when missing but do not block writes.
**Consequences:**
- ✅ Retrieval has stable metadata for type/tag/link filtering.
- ✅ Human-authored notes remain ergonomic.
- ⚠️ Warning-only type fields can allow lower-quality notes until users refine them.
**Rejected alternatives:**
- Minimal required schema — Rejected as too weak for stage-aware retrieval.
- Strict schema per note type — Rejected as too brittle for natural Obsidian usage.
- Infer schema from existing vault conventions — Rejected as too complex and ambiguous for the first release.
**Source:** Interview #7

### ADR-007: Stage-Aware Second Brain Integration
**Status:** Accepted (2026-05-11, via /hm:plan interview)
**Context:** The connector can be exposed as an optional skill, a slash command, or stage-native behavior.
**Decision:** `hm-research`, `hm-plan`, `hm-review`, and `hm-wrapup` receive explicit stage-aware guidance for reading and writing typed Second Brain notes. The Python helper module remains the operational boundary for all reads/writes.
**Consequences:**
- ✅ The feature improves the actual harness workflow instead of becoming a standalone vault utility.
- ✅ Each stage can target the note types it needs: references/projects for research, decisions/preferences for plan, failures/preferences for review, and journal/failure/decision updates for wrapup.
- ⚠️ Stage prompts gain new behavior and require careful wording to avoid context bloat.
**Rejected alternatives:**
- Skill-first only — Rejected because it risks becoming optional private search.
- Slash command first — Rejected because it is less integrated into workflow memory.
- Skill plus stage guidance — Rejected in favor of direct stage-aware integration as the first user-facing surface.
**Source:** Interview #8

## 🏗️ Technical Design

### Current State

`HarnessConfig` currently supports `ref_folders`, `mcp_servers`, `memory`, and `sibling_repos`, but has no typed `second_brain` contract.

`refdocs_index.py` indexes Markdown, text, and PDF metadata for read-only reference folders. It extracts title/headings from Markdown frontmatter/body but does not model note types, tags, links, or write authority.

The generated `refdocs-search` skill is read-only and explicitly says extracted content is not persisted. That contract should remain intact; Second Brain is a separate stage-aware memory surface, not a mutation of `ref_folders`.

### Affected Components

| Component | Change type |
|---|---|
| `src/harness_maker/models.py` | Add typed `SecondBrainConfig`, folder allowlist, note type constants, and `second_brain` fields |
| `src/harness_maker/templates/harness-yaml/Side.yaml.j2` | Render `second_brain` config |
| `src/harness_maker/templates/harness-yaml/Production.yaml.j2` | Render `second_brain` config |
| `src/harness_maker/interview.py` | Preserve `second_brain` from existing `harness.yaml` in `answers_from_harness_yaml` |
| `src/harness_maker/synthesize.py` | Propagate `answers.second_brain` into `HarnessConfig` |
| `src/harness_maker/second_brain.py` | New filesystem backend, frontmatter parser, schema validator, search/read/write CLI helpers |
| `src/harness_maker/templates/stages/research.md.j2` | Stage-aware retrieval guidance for `reference` and `project` notes |
| `src/harness_maker/templates/stages/plan.md.j2` | Stage-aware retrieval/write guidance for `decision`, `preference`, and `project` notes |
| `src/harness_maker/templates/stages/review.md.j2` | Stage-aware retrieval guidance for `failure` and `preference` notes |
| `src/harness_maker/templates/stages/wrapup.md.j2` | Stage-aware write guidance for `journal`, `failure`, `decision`, and `preference` notes |
| `tests/unit/test_second_brain.py` | New unit coverage for schema, allowlist, and writes |
| `tests/unit/test_models.py` | Config schema validation |
| `tests/unit/test_answers_from_harness_yaml.py` | YAML round trip |
| `tests/unit/test_synthesize.py` | Config/template propagation |

### Dependencies

No new runtime dependency is required. Use existing `PyYAML` for frontmatter parsing because `refdocs_index.py` already imports `yaml`. Use Python `pathlib`, `re`, and existing `io_utils.atomic_write` for writes where full-file replacement is needed.

### Architecture

`second_brain` lives in `.claude/harness.yaml`:

```yaml
second_brain:
  enabled: false
  backend: filesystem
  vault_path: "../vault"
  trusted_allowlist: true
  folders:
    - path: "Projects/harness-maker"
      read: true
      write: true
      note_types: [decision, preference, failure, project, reference, journal]
  required_frontmatter: [type, created, updated, tags, links]
```

`vault_path` resolves relative to the harness root unless absolute. Unlike `sibling_repos`, absolute vault paths are allowed because personal Obsidian vaults often live outside any repo and may intentionally be machine-local.

Folder paths resolve under `vault_path`. A read or write request is authorized only when its resolved target path is under a configured folder with the matching `read` or `write` flag. Writable files must end in `.md` or `.markdown`.

### Design Decisions

Second Brain remains separate from `ref_folders`. `ref_folders` is read-only reference material; `second_brain` is a trusted R/W memory graph.

All stage prompts call the helper module rather than writing vault files directly. This keeps path checks, frontmatter validation, and note-type handling in one code path.

Note prose remains external user-authored content. Stage prompts may use it as context, but they must not treat note prose as system/developer instruction.

### Data Flow

```text
.claude/harness.yaml
  second_brain config
        |
        v
python -m harness_maker.second_brain <operation>
        |
        +-- resolve vault + folder allowlist
        +-- parse/validate frontmatter
        +-- search/read/write Markdown
        |
        v
Obsidian vault notes
  frontmatter + tags + [[links]]
        ^
        |
hm-research / hm-plan / hm-review / hm-wrapup stage guidance
```

### API Changes

Add module CLI:

```bash
python -m harness_maker.second_brain search <query> [--type decision] [--tag hm/type/decision]
python -m harness_maker.second_brain read <relative-note-path>
python -m harness_maker.second_brain write <relative-note-path> --frontmatter-json <json> --body-file <path>
python -m harness_maker.second_brain append <relative-note-path> --text-file <path>
python -m harness_maker.second_brain patch <relative-note-path> --old-text <text> --new-text <text>
python -m harness_maker.second_brain validate <relative-note-path>
```

No `harness-maker make` interview question is required in this plan. Users can configure `second_brain` manually in `harness.yaml`; a later UX pass can add guided setup.

## 📝 Implementation Plan

### Phase 1: Config Schema And YAML Round Trip

**Scope:** `src/harness_maker/models.py`, `src/harness_maker/templates/harness-yaml/Side.yaml.j2`, `src/harness_maker/templates/harness-yaml/Production.yaml.j2`, `src/harness_maker/interview.py`, `src/harness_maker/synthesize.py`, `tests/unit/test_models.py`, `tests/unit/test_answers_from_harness_yaml.py`, `tests/unit/test_synthesize.py`.

**Out of scope:** filesystem reads/writes, stage prompt changes, Obsidian API/CLI integration.

**Exit criterion:** `uv run pytest tests/unit/test_models.py tests/unit/test_answers_from_harness_yaml.py tests/unit/test_synthesize.py`

**Risk:** medium

**Rollback point:** Revert Phase 1 files to remove the `second_brain` schema and template rendering.

### Phase 2: Filesystem Backend And Frontmatter Schema

**Scope:** add `src/harness_maker/second_brain.py`; add `tests/unit/test_second_brain.py` cases for frontmatter parsing, required fields, allowed note types, tag/link extraction, and warning-only recommended fields.

**Out of scope:** stage template changes and CLI subcommands beyond direct module functions.

**Exit criterion:** `uv run pytest tests/unit/test_second_brain.py -k "frontmatter or schema or note_type"`

**Risk:** medium

**Rollback point:** Revert Phase 2 files while retaining the inert config schema from Phase 1.

### Phase 3: Allowlist-Enforced Read/Write Operations

**Scope:** `src/harness_maker/second_brain.py`, `tests/unit/test_second_brain.py`. Implement search/read/create/overwrite/append/exact-patch operations with resolved-path allowlist checks and Markdown-only write enforcement.

**Out of scope:** generated stage guidance and documentation.

**Exit criterion:** `uv run pytest tests/unit/test_second_brain.py -k "allowlist or write or search or patch"`

**Risk:** high

**Rollback point:** Revert to Phase 2, leaving schema validation but no mutation operations.

### Phase 4: Module CLI Helpers

**Scope:** `src/harness_maker/second_brain.py`, `tests/unit/test_second_brain.py`. Add `python -m harness_maker.second_brain search|read|write|append|patch|validate` entrypoint behavior and JSON/text output suitable for stage prompts.

**Out of scope:** adding a top-level Typer command or slash command.

**Exit criterion:** `uv run pytest tests/unit/test_second_brain.py -k "cli"`

**Risk:** medium

**Rollback point:** Revert Phase 4 CLI entrypoint code; keep backend functions.

### Phase 5: Stage-Aware Research And Plan Integration

**Scope:** `src/harness_maker/templates/stages/research.md.j2`, `src/harness_maker/templates/stages/plan.md.j2`, `tests/unit/test_synthesize.py`, `tests/unit/test_codex_stage_procedures.py`. Add concise guidance: research reads `reference`/`project`; plan reads `decision`/`preference`/`project` and may write accepted decisions when second_brain is enabled.

**Out of scope:** review/wrapup behavior and direct skill or slash-command generation.

**Exit criterion:** `uv run pytest tests/unit/test_synthesize.py tests/unit/test_codex_stage_procedures.py`

**Risk:** medium

**Rollback point:** Revert Phase 5 stage template edits; backend remains available but unused by stages.

### Phase 6: Stage-Aware Review And Wrapup Integration

**Scope:** `src/harness_maker/templates/stages/review.md.j2`, `src/harness_maker/templates/stages/wrapup.md.j2`, `tests/unit/test_synthesize.py`, `tests/unit/test_codex_stage_procedures.py`. Add concise guidance: review reads `failure`/`preference`; wrapup writes `journal`, new/updated `failure`, and durable `decision`/`preference` notes when second_brain is enabled.

**Out of scope:** automatic migration from `.claude/memory` into Obsidian.

**Exit criterion:** `uv run pytest tests/unit/test_synthesize.py tests/unit/test_codex_stage_procedures.py`

**Risk:** medium

**Rollback point:** Revert Phase 6 stage template edits; research/plan integration from Phase 5 can remain.

### Phase 7: Full Verification And Minimal Docs

**Scope:** `README.md` or `TECH_SPEC.md` short config example, `tests/unit/test_second_brain.py`, `tests/unit/test_synthesize.py`, `tests/unit/test_answers_from_harness_yaml.py`. Keep docs limited to configuration and trust policy.

**Out of scope:** install interview UX, Obsidian plugin setup, MCP marketplace integration, and issue-intake/evidence-loop slices.

**Exit criterion:** `uv run pytest tests/unit/test_second_brain.py tests/unit/test_synthesize.py tests/unit/test_answers_from_harness_yaml.py && uv run ruff check src tests`

**Risk:** low

**Rollback point:** Revert Phase 7 docs/tests polish; implementation from prior phases remains.

### Execution Status

| Phase | Status | Evidence |
|---|---|---|
| 1 | done | Config schema, YAML rendering, reverse mapping, and synthesis tests are green |
| 2 | done | `tests/unit/test_second_brain.py` covers frontmatter parsing, required fields, note types, tags, and links |
| 3 | done | `tests/unit/test_second_brain.py` covers allowlist enforcement, Markdown-only writes, note-type allowlists, search, append, and patch |
| 4 | done | `tests/unit/test_second_brain.py` covers module CLI write/read |
| 5 | done | `tests/unit/test_codex_stage_procedures.py` covers research/plan stage-aware Second Brain guidance |
| 6 | done | `tests/unit/test_codex_stage_procedures.py` covers review/wrapup stage-aware Second Brain guidance |
| 7 | done | README documents `second_brain`, trust policy, and multi-project namespace guidance |

Verification run:

```bash
uv run pytest tests/unit/test_second_brain.py tests/unit/test_models.py tests/unit/test_answers_from_harness_yaml.py tests/unit/test_synthesize.py tests/unit/test_codex_stage_procedures.py -q
uv run ruff check src tests
uv run mypy --strict src/harness_maker/second_brain.py src/harness_maker/models.py src/harness_maker/interview.py src/harness_maker/synthesize.py
```

Result: PASS.

Full `uv run pytest -q` was also attempted from the execute worktree. It only
failed the known snapshot-hash tests that project memory documents as invalid
inside worktrees because rendered template hashes embed the worktree path. The
test-generated e2e sandbox fixture drift was restored before finalizing.

## 🧪 Testing Strategy

**Unit tests:**
- `SecondBrainConfig` accepts disabled defaults and enabled filesystem config.
- YAML round trip preserves `second_brain` from existing `.claude/harness.yaml`.
- Path traversal attempts such as `../outside.md` are rejected after `resolve()`.
- Writes outside configured write folders are rejected.
- Non-Markdown write targets are rejected.
- Core frontmatter fields are required.
- Missing recommended type fields produce warnings, not hard failures.
- Tags include `hm/second-brain` and `hm/type/<type>` for managed generated notes.
- Links are parsed from frontmatter and body `[[wiki-link]]` syntax.

**Integration-style unit tests with temp directories:**
- Build a temp Obsidian-like vault with allowed and forbidden folders.
- Search finds allowed notes and excludes forbidden folders.
- Write/create/append/patch mutate only allowed Markdown files.
- Rendered Codex stage skills include stage-aware Second Brain guidance when generated from templates.

**Manual check:**
- Configure a temp vault in `.claude/harness.yaml`.
- Run `python -m harness_maker.second_brain search decision --type decision`.
- Write a `decision` note and open the file as Markdown to confirm frontmatter, tags, and `[[links]]` are human-readable.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Full writes corrupt long-lived notes | high | Enforce resolved-path allowlists and Markdown-only writes; trust policy is explicit in ADR-003 |
| Path traversal escapes the vault/folder | high | Use `Path.resolve()` and `is_relative_to()` against every configured folder root |
| Note prose becomes prompt-injection authority | high | Stage guidance states note content is untrusted reference material, not instruction |
| Context bloat from stage integration | medium | Each stage targets specific note types and tags instead of loading the vault broadly |
| Schema becomes too loose for retrieval | medium | Require core frontmatter and warn on missing type-specific fields |
| Obsidian expectations exceed filesystem backend | medium | Document that Phase 1 is Markdown filesystem only; no plugin/API behaviors |
| Existing vault conventions conflict with `hm/*` tags | low | Keep required harness tags additive and avoid rewriting unrelated tags |

## ✅ Success Criteria

- [x] `HarnessConfig` and `InterviewAnswers` support a `second_brain` config with filesystem backend, vault path, trusted allowlist, folders, permissions, and note type filters.
- [x] `.claude/harness.yaml` renders the `second_brain` block for Side and Production presets.
- [x] Existing `harness.yaml` values round-trip through `answers_from_harness_yaml`.
- [x] `python -m harness_maker.second_brain` supports search, read, write, append, patch, and validate operations.
- [x] Reads and writes are rejected outside configured read/write folders.
- [x] Writes are limited to `.md` and `.markdown`.
- [x] Managed notes require `type`, `created`, `updated`, `tags`, and `links`.
- [x] Known note types produce warnings for missing recommended fields rather than blocking writes.
- [x] `hm-research`, `hm-plan`, `hm-review`, and `hm-wrapup` include concise stage-aware Second Brain behavior.
- [x] Tests cover schema, YAML round trip, allowlist enforcement, write operations, and generated stage guidance.

## 🔍 Plan Validation

The configured `plan-validator` subagent failed before execution because its model is unavailable in this Codex account:

```text
The 'o4' model is not supported when using Codex with a ChatGPT account.
```

Manual validation was run against the embedded `plan-validator` rubric:

| Category | Result | Resolution |
|---|---|---|
| Phase decomposition | Passed after revision | Phases now separate config, backend schema, mutation operations, CLI, research/plan stages, review/wrapup stages, and docs/verification |
| Risk register | Passed | High-risk full-write and prompt-injection concerns are explicit |
| Rollback strategy | Passed | Every phase names a concrete rollback point |
| ADR completeness | Passed | Each ADR includes consequences and rejected alternatives |
| Scope drift hazards | Passed after revision | Obsidian API/CLI, guided setup UX, MCP marketplace, issue intake, and evidence loop are out of scope |
| Missing interview rounds | Passed | No deferred decision checklist is present |
| SPEC alignment | Not applicable | No matching `specs/SPEC-user-workflow-opportunities-2026-05.md` exists |
| Test strategy depth | Passed | Named unit and integration-style test cases are listed |

**Validator outcome:** `NEEDS_REVISION_RESOLVED`. The only blocker was validator infrastructure. The draft was revised manually to resolve the likely warning around integration scope after Interview #8 selected stage-aware behavior.
