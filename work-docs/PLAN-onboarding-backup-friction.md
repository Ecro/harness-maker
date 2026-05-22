---
type: plan
task_slug: onboarding-backup-friction
status: complete
created: 2026-05-22
tags: [harness-maker, plan, brownfield, reconcile, preservation, backup, ux]
research_doc: "[[RESEARCH-onboarding-backup-friction]]"
interview_rounds: 6
adrs: 7
validator_outcome: NEEDS_REVISION_RESOLVED
phase_status:
  phase_0_audit_matrix: complete
  phase_1_3_hooks_merge_atomic: complete
  phase_2_toml_sh_markers: complete
  phase_4_gitignore_wiring: complete
  phase_5_prune_backups_cli: complete
  phase_6_make_prose: complete
  phase_7_e2e_on_disk: deferred  # Out of single-loop context budget; follow-up commit.
summary: "Audit brownfield in-place preservation; close hooks.json/TOML/sh gaps; auto-gitignore .backup-*/; CLI retention."
---

# PLAN — Brownfield onboarding preservation + backup housekeeping

## 🎯 Executive Summary

**TL;DR:** The user's reframe in Round 1 vetoed RESEARCH's "skip backup conditionally" recommendation. The real concern is not backup-as-friction but **whether existing commands/skills/agents/hooks survive at their original paths after a brownfield `/hm:make`**. This PLAN audits in-place preservation per file type, closes the gaps where `always-REPLACE` rules currently overwrite user content (hooks.json all three schemas, TOML, `.sh`), makes `.backup-*/` invisible to git, and adds a user-gated CLI for backup retention.

**What:** 7 phases delivering (a) `docs/reference/preservation-matrix.md` + cross-file-type test suite, (b) atomic ship of `.codex/hooks.json` literal-match fix + hooks.json in-place 3-way merge (Phases 1 and 3 ship together — see Risks), (c) extension of `@hm:user:*` block-marker support to TOML and sh at TOML/file-level only, (d) auto-gitignore entry for `.backup-*/`, (e) `harness-maker prune-backups` CLI subcommand with read-only default, (f) prose update in `commands/make.md`, (g) cross-IDE on-disk + manual IDE acceptance verification.

**Why:** Dogfood evidence — this repo accumulated 108 `.backup-<ts>/` directories — shows the current always-backup behavior is functioning, but the *trust* signal is broken: users worry that backup is masking a preservation gap. Audit + fix + housekeeping closes that signal.

**Key decisions (links to ADRs):**
- [ADR-001](#adr-001-always-backup-is-non-negotiable) — Always backup; conditional-skip vetoed.
- [ADR-002](#adr-002-audit-plus-full-gap-closure-scope) — Full gap closure, not audit-only.
- [ADR-003](#adr-003-hooksjson-in-place-3-way-merge) — settings.json pattern reused for hooks.json.
- [ADR-004](#adr-004-toml-marker-scope) — All blueprint TOML, TOML/file-level only.
- [ADR-005](#adr-005-backup-housekeeping-gitignore-auto-retention-user-gated) — Gitignore auto, retention user-gated.
- [ADR-006](#adr-006-hooksjson-entry-discriminator-schema-aware) — Schema-aware entry identity + manifest extension.
- [ADR-007](#adr-007-tomlsh-marker-syntax-and-scope) — `# @hm:user:NAME`; TOML-level only (no inside-string).

**Estimated impact:** ~9 source files touched (reconcile.py, render.py, block_merge.py, cli.py, models.py for new enum, commands/make.md, three test files + two new test files + one new doc file). Risk profile: 1 medium-high phase (Phase 3 — schema-aware merge), 2 medium (Phases 2 and 7), 4 low.

## 📚 Prior Work

- **RESEARCH-onboarding-backup-friction.md** — surfaced the friction, recommended Approach A+D+B (conditional skip + gitignore/retention + `--no-backup`). Round 1 vetoed Approach A and B. Approach D survives in modified form (gitignore auto, retention CLI-gated not auto).
- **RESEARCH-onboarding-ux-2026-05.md** — broader receipt-first onboarding work; Approach C (receipt-first preview) is out of scope for this PLAN.
- **`[wiki:pattern] interview-mid-round-reframe-pattern` (2026-05-20)** — Round 1 explicitly surfaced the philosophy assumption *before* drilling into implementation, per this lesson. The reframe arrived in Round 1, not Round 4. Worked as intended.
- **`[wiki:pattern] orphan-sweep-content-hash-gating` (2026-05-17)** — `.hm-render-manifest.jsonl` already records shipped file hashes. Per ADR-006, Phase 3 extends the manifest write to record the MERGED hooks.json hash (not the template-only hash), so `sweep_orphans()`'s `_classify_orphan` will see "ours-clean" rather than "theirs" for unchanged merged files.
- **`[wiki:gotcha] worktree-finalize-untracked-loss` (2026-05-22)** — backup retention pruning must be user-gated, not auto. ADR-005 codifies this.
- **`[wiki:architecture] codex-triple-target-assets` (2026-05-10)** — confirms `.codex/hooks.json` ships from `templates/codex/hooks.json.j2`; the reconcile literal-match in `reconcile.py:136` omits it, producing the KEEP-fallback bug Phase 1 fixes.
- **`[wiki:gotcha] add-f-for-new-memory-files` (2026-05-16)** — gitignore changes must remain idempotent; `worktree._ensure_gitignore_entry` (proven pattern) is reused in Phase 4.

## 🎙️ Interview Transcript

| # | Round | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | 1 | Architecture / philosophy | 백업의 기본 철학은? | always-but-invisible (Option B), with REFRAME | User reframed mid-question: real concern is in-place preservation, not backup itself. RESEARCH conditional-skip recommendation vetoed. | ADR-001 |
| 2 | 2 | Scope | Audit 후 gap 을 어디까지 잡을까? | 전면 gap closure (Option C) | hooks.json sidecar 포함 — JSON 은 comment 불가하므로 별도 architecture 필요. | ADR-002 |
| 3a | 3 | Contract shape | hooks.json gap-closing architecture | In-place 3-way merge | settings.json 패턴 재사용; brownfield migration 불필요. | ADR-003 |
| 3b | 3 | Architecture | TOML marker scope | 모든 blueprint TOML | config.toml + agents/*.toml 둘 다 marker 인식. | ADR-004 |
| 3c | 3 | Implementation phasing | `.backup-*/` housekeeping | Gitignore 자동, retention CLI 명시 명령 | auto-prune 금지 — `[wiki:gotcha] worktree-finalize-untracked-loss` 와 정합. | ADR-005 |
| 4 | 4 | Exit | Plan 해상도 충분? | End interview — write PLAN | 5-term gate: 모든 잔여 후보 EIG fail → ADR-006/007 은 defensible default. | — |
| 5a | 5 | Implementation phasing | validator critical #2: Phase 1 ↔ Phase 3 ordering | Phase 1 + Phase 3 atomic ship (one PR/commit) | Phase 1 exit criterion 에 'MUST NOT be merged independently of Phase 3' 명시. | ADR-006 (revised) |
| 5b | 5 | Contract shape | validator critical #3: developer_instructions marker scope | TOML-level marker only | ADR-007 의 'inside-string markers' 주장 retract. body 전체 교체만 가능. | ADR-007 (revised) |
| 6 | 6 | Cleanup | Validator 2nd pass NEEDS_REVISION (W1 xfail, W2 dispatch predicate, S3 parse_segments naming) | All three: validator recommendations applied verbatim | Mechanical PLAN-text fixes; no ADR re-revision needed. | — |

## 📐 Architecture Decision Records

### ADR-001: Always-backup is non-negotiable
**Status:** Accepted (2026-05-22, via /hm:plan interview Round 1)
**Context:** RESEARCH-onboarding-backup-friction.md recommended skipping backup when reconcile decides KEEP-only (Approach A). The user vetoed this when asked the underlying philosophy question.
**Decision:** `backup()` continues to run unconditionally whenever `.claude/` exists and is non-empty (current `cli.py:353-354` behavior preserved). Friction reduction comes from gitignore + housekeeping, not from skipping backup.
**Consequences:**
- ✅ No reduction in the safety net's coverage. Even buggy reconcile/render decisions are still recoverable from `.backup-<ISO>/`.
- ✅ User trust signal is "backup always runs" — predictable.
- ⚠️ Disk usage continues to grow without user-initiated prune. Mitigated by [ADR-005](#adr-005-backup-housekeeping-gitignore-auto-retention-user-gated).
**Rejected alternatives:**
- Conditional skip on KEEP-only — Rejected because the user's stance is verification-first.
- Opt-in `--no-backup` — Rejected because it puts the burden of correctness on user invocation discipline.
- Receipt-first preview — Out of scope; covered by [[RESEARCH-onboarding-ux-2026-05]].
**Source:** Interview #1 (Round 1).

### ADR-002: Audit plus full gap closure scope
**Status:** Accepted (2026-05-22, via /hm:plan interview Round 2)
**Context:** After Round 1 reframed the goal as preservation verification, the empirical reconcile matrix showed three file types are `always-REPLACE`: hooks.json (three schemas), TOML, `.sh`. The user chose to close all three gaps, not just document them.
**Decision:** PLAN deliverables = (a) preservation-matrix doc + cross-file-type tests, (b) hooks.json in-place merge, (c) TOML/sh `#`-comment block-marker support, (d) `.codex/hooks.json` reconcile literal-match fix, (e) `.backup-*/` gitignore wiring, (f) backup retention CLI.
**Consequences:**
- ✅ Backup becomes a secondary safety net for the only remaining gap (user editing a `.toml`/`.sh` file *without* using markers), not the primary recovery mechanism for whole file categories.
- ✅ User-facing matrix doc makes the trust contract auditable.
- ⚠️ Largest possible PLAN scope inside this slug — 7 phases.
**Rejected alternatives:**
- Audit-only — Rejected because it leaves the gaps as-is.
- TOML+sh only — Rejected because hooks.json is the most-edited file type in practice.
- User-marker-instruction-only — Rejected because relying on users to learn marker syntax for a JSON file (impossible — no comments) doesn't work.
**Source:** Interview #2 (Round 2).

### ADR-003: hooks.json in-place 3-way merge
**Status:** Accepted (2026-05-22, via /hm:plan interview Round 3a)
**Context:** JSON forbids comments, so the existing `@hm:user:*` marker mechanism doesn't apply. Two architectures considered: sidecar split (`hooks.user.json` + `hooks.shipped.json` → `hooks.json` at render time) versus in-place 3-way merge (read existing `hooks.json`, identify shipped-vs-user entries, merge in place).
**Decision:** In-place 3-way merge. Mirrors the existing `_shallow_merge_existing_json` + `_merge_permissions` pattern used for `settings.json`. The user only ever sees one `hooks.json` file; no migration needed for brownfield projects.
**Consequences:**
- ✅ Brownfield migration is trivial — existing user hooks survive Phase 3 transparently.
- ✅ Schema parity with settings.json — same mental model.
- ⚠️ Per-entry discriminator design needed ([ADR-006](#adr-006-hooksjson-entry-discriminator-schema-aware)).
- ⚠️ Manifest write path must be extended so `sweep_orphans()` doesn't misclassify merged files as "theirs" (see ADR-006 manifest section).
**Rejected alternatives:**
- Sidecar split — Rejected because brownfield migration is awkward and three files is more confusing than one.
**Source:** Interview #3 (Round 3a).

### ADR-004: TOML marker scope
**Status:** Accepted (2026-05-22, via /hm:plan interview Round 3b; clarified Round 5b)
**Context:** Extending block-merge support to TOML hash-comment markers. Three scopes possible: `config.toml` only; `config.toml` + `agents/*.toml`; all blueprint TOML.
**Decision:** All blueprint TOML accepts TOML-level (`# @hm:user:NAME`) markers. Round 5b clarification: **markers are recognized only at TOML statement level** — they are NOT recognized inside multi-line string values like `developer_instructions = """ … """`. To preserve a custom agent body, the user wraps the entire `developer_instructions = """ … """` assignment with `# @hm:user:body-override` / `# @hm:/user:body-override` at TOML statement level. Partial-body edits inside the triple-quoted string are not supported by this PLAN.
**Consequences:**
- ✅ Symmetric with markdown agent bodies (which already accept `<!-- @hm:user:* -->`).
- ✅ User can extend shipped Codex agents with custom `[some_field]` blocks or wrapped-body replacements without losing them on re-render.
- ✅ block_merge parser stays single-pass; no two-pass TOML string descent.
- ⚠️ Partial edits inside `developer_instructions` not preserved without wrapping. Documented in preservation matrix as a known limitation.
**Rejected alternatives:**
- config-only — Rejected because agent TOML is the more common edit target.
- Two-pass parser (TOML descent into string values + markdown HTML markers inside) — Rejected per Round 5b: parser complexity + test surface jump not justified for the partial-edit case.
**Source:** Interview #3 (Round 3b), clarified by Interview #5b (Round 5).

### ADR-005: Backup housekeeping — gitignore auto, retention user-gated
**Status:** Accepted (2026-05-22, via /hm:plan interview Round 3c)
**Context:** `.backup-*/` accumulates indefinitely (108 dirs in dogfood). Two housekeeping pieces: (a) hide from `git status` via `.gitignore`, (b) prune old snapshots.
**Decision:** (a) On every `/hm:make` run that produces a backup, idempotently append `.backup-*/` to `<project_root>/.gitignore` via the proven `worktree._ensure_gitignore_entry` helper. (b) Pruning is exposed as a separate CLI subcommand `harness-maker prune-backups`, with read-only default (lists candidates without deleting). `--apply` flag required to actually delete. No automatic pruning during `/hm:make`.
**Consequences:**
- ✅ First-impression friction (`.backup-<ts>` showing up in `git status`) disappears.
- ✅ Destructive action is always user-initiated; no surprise deletes.
- ⚠️ Disk continues to grow unless user runs prune. Mitigated by mentioning the command in `commands/make.md` and in the prune dry-run's own audit line.
**Rejected alternatives:**
- Auto-prune on every `/hm:make` — Rejected per `[wiki:gotcha] worktree-finalize-untracked-loss`.
- Gitignore-only, retention deferred — Rejected because the dogfood signal (108 dirs) makes deferral indefensible.
**Source:** Interview #3 (Round 3c).

### ADR-006: hooks.json entry discriminator (schema-aware)
**Status:** Accepted (2026-05-22, default lock-in via Round 4 exit gate; revised by validator critical #1 + Round 5)
**Context:** ADR-003's in-place merge needs to identify which entries in an existing `hooks.json` are shipped (template-owned) versus user-added (must be preserved). The three schemas this PLAN supports have **different entry shapes**, verified against `templates/hooks/hooks.json.j2`, `templates/codex/hooks.json.j2`, and `templates/cursor/hooks.json.j2`:

- **Claude Code** (`hooks/hooks.json`): `{event: [{matcher?, hooks: [{type, command, timeout?, statusMessage?}]}]}` — `command` is **nested** inside `hooks[0]`; `matcher` is optional (absent on `SessionStart`, `Stop`).
- **Codex** (`.codex/hooks.json`): same nested PascalCase shape as Claude — entries on `PermissionRequest`, `SessionStart`, and `Stop` have NO `matcher`. Stop has two matcher-less entries with different commands.
- **Cursor** (`.cursor/hooks.json`): flat lowercase camelCase `{event: [{matcher?, command}]}` — `command` lives at entry level; `stop` and `preCompact` entries have NO `matcher`.

The Round-4 default of `(entry["matcher"], entry["command"])` would `KeyError` on the nested schemas and silently mis-classify matcher-less entries on all three schemas.

**Decision:** Per-entry identity is **schema-aware**, dispatched on the file path:

- For `hooks/hooks.json` (Claude) and `.codex/hooks.json` (Codex), per-entry identity = tuple `(matcher_or_empty, nested_command, nested_type)` where:
  - `matcher_or_empty = entry.get("matcher", "")`
  - `nested_command = entry["hooks"][0]["command"]` (the FIRST nested hook; entries with multiple nested hooks dedup on the first only).
  - `nested_type = entry["hooks"][0].get("type", "command")`
- For `.cursor/hooks.json` (Cursor), per-entry identity = tuple `(matcher_or_empty, command_string)` where:
  - `matcher_or_empty = entry.get("matcher", "")`
  - `command_string = entry["command"]`

An entry is "shipped" iff its identity tuple appears in the freshly-rendered template's entry set for the same event; otherwise it's "user". Merge result per event = template entries in template order, plus existing entries whose identity is NOT in the template set, in original disk order.

**Manifest extension (resolves validator warning #8):** After `_merge_hooks_json` writes the merged result, the render path records the **merged file's SHA-256 hash** in `.hm-render-manifest.jsonl` (not the template-only hash). Without this, `_classify_orphan` (`reconcile.py:411-428`) would see merged bytes that don't match any manifest entry and classify the file as "theirs" → permanent KEEP+warn for every brownfield project. The manifest-write call in `render.py` already accepts a per-file hash argument; Phase 3 routes the merged hash there.

**Consequences:**
- ✅ Discriminator works correctly across all three real shipped schemas (no KeyError, no silent mis-classification).
- ✅ User entries with NEW matcher OR NEW command always survive.
- ⚠️ If a user MODIFIES a shipped entry's matcher (keeping command identical) the modification is wiped on re-render. Documented in preservation matrix as a known limitation; users should add a new entry rather than mutate shipped ones.
- ⚠️ For nested schemas, entries with multiple `hooks: [...]` array members (rare) dedup only on `hooks[0]`. Documented as a known limitation; current templates always use length-1 hooks arrays.
- ⚠️ Malformed JSON or unexpected schema (e.g., `hooks` not a list) → fall back to template-overwrite (REPLACE behavior) with a warning logged. Backup remains the recovery path (per ADR-001).
**Rejected alternatives:**
- Single-schema discriminator (Round 4 default) — Rejected: would crash on day one (validator critical #1).
- Per-entry hash recorded in manifest — Rejected because the manifest currently tracks per-file; per-entry granularity adds significant schema complexity. Per-file merged-hash is sufficient for sweep_orphans correctness.
- First-shipped-commit tracking — Rejected because it requires git-aware logic.
**Source:** Round 4 exit gate (initial default) + validator critical #1 + Round 5a (atomic-ship gate also referenced here).

### ADR-007: TOML/sh marker syntax and scope
**Status:** Accepted (2026-05-22, default lock-in via Round 4; revised by Round 5b)
**Context:** ADR-004 extends block-marker support to TOML and `.sh`. The existing parser handles `<!-- @hm:user:NAME -->` HTML-comment markers in markdown. TOML and `.sh` use `#` line comments.

Validator critical #3 surfaced a design gap in the initial ADR-007: it claimed markers INSIDE `developer_instructions` (a multi-line TOML string) follow markdown convention. `block_merge.parse_segments()` is line-by-line and dispatched on file extension, with no mechanism to descend into TOML string values and re-parse with a different syntax. That claim was retracted by Round 5b.

**Decision:**

1. **Marker syntax for hash-comment file types:** `# @hm:user:NAME` and `# @hm:/user:NAME`. Each marker occupies its own line; leading whitespace tolerated; trailing content rejected per existing strict-parse rule.
2. **Scope:** TOML and `.sh` files in the blueprint accept these markers at the file's top-level statement level only. **Multi-line string values are opaque** — markers inside them are NOT recognized.
3. **Parser dispatch:** `block_merge.parse_segments(text, style: MarkerStyle = MarkerStyle.HTML_COMMENT)` **already accepts a `style` parameter** in the current codebase (block_merge.py:172); Phase 2's work on the parser is therefore zero-line. The actual Phase 2 changes are: (a) extend `detect_marker_style()` to return `MarkerStyle.HASH_COMMENT` for `.toml` and `.sh` suffixes (resolves validator warning #4 — currently only `.yml`/`.yaml` map to `HASH_COMMENT`), and (b) wire `reconcile.py`'s TOML+sh branches to pass the path through `detect_marker_style()` before calling `has_markers()` / `parse_segments()`.
4. **Full-body replacement for TOML agents:** A user who wants to override an entire agent body wraps the entire `developer_instructions = """ … """` assignment with TOML-level markers — e.g., `# @hm:user:body-override` ... `developer_instructions = """ custom """` ... `# @hm:/user:body-override`.

**Consequences:**
- ✅ Symmetric naming across file types — users learn one marker family.
- ✅ Single-pass parser; no two-pass TOML string descent.
- ✅ `detect_marker_style()` remains the canonical extension point.
- ⚠️ Partial edits inside `developer_instructions` not preserved without TOML-level wrapping. Documented in preservation matrix.
**Rejected alternatives:**
- Two-pass parser (TOML descent + inner HTML markers) — Rejected per Round 5b: complexity not justified.
- TOML-specific marker syntax (e.g., `# [hm-user:NAME]`) — Rejected because consistency across file types beats schema-specific cleverness.
- Reuse HTML-comment markers in TOML (`# <!-- @hm:user:NAME -->`) — Rejected because the leading `<!--` is meaningless noise outside HTML/Markdown.
**Source:** Round 4 exit gate (initial default) + Round 5b.

## 🏗️ Technical Design

### Current State

Brownfield reconciliation produces per-file decisions:

```
existing file at blueprint path  →  reconcile decision  →  preservation outcome
─────────────────────────────────────────────────────────────────────────────
markdown w/o frontmatter         →  KEEP                →  ✅ in-place
markdown @hm:user:* (both sides) →  MERGE_BLOCK         →  ✅ user blocks
markdown hash-mismatch, no markers→ KEEP                →  ✅ in-place
harness.yaml                     →  REPLACE + merge     →  ✅ user keys
settings.json                    →  REPLACE + merge     →  ✅ permissions union
hooks/hooks.json                 →  REPLACE             →  ❌ user entries lost
.cursor/hooks.json               →  REPLACE             →  ❌ user entries lost
.codex/hooks.json                →  (no literal match)  →  ⚠️ KEEP fallback bug
.codex/config.toml               →  REPLACE             →  ❌ user keys lost
.codex/agents/*.toml             →  REPLACE             →  ❌ user edits lost
.claude/lib/*.sh                 →  REPLACE             →  ❌ user edits lost
AGENTS.md                        →  MERGE_BLOCK         →  ✅ user blocks
user-owned file outside blueprint → orphan-sweep "theirs"→ ✅ KEEP+warn
```

### Affected Components

- `src/harness_maker/models.py` — new `ReconcileDecision.MERGE_JSON` enum value (Phase 3) to signal that the file should be in-place 3-way merged at render time.
- `src/harness_maker/reconcile.py` — decision matrix: (Phase 3) `hooks/hooks.json`, `.cursor/hooks.json`, AND `.codex/hooks.json` all map to `ReconcileDecision.MERGE_JSON` instead of `REPLACE`. Phase 2 replaces TOML+sh `always-REPLACE` branches with marker-aware `MERGE_BLOCK` fallback. Phases 1 and 3 ship atomically (see Risks).
- `src/harness_maker/block_merge.py` — parser: (Phase 2) extend `detect_marker_style()` to return `HASH_COMMENT` for `.toml` and `.sh` suffixes; extend `parse_segments()` to accept either marker syntax based on style. Single parser pass; no descent into string values.
- `src/harness_maker/render.py` — (Phase 3) new `_merge_hooks_json(out: Path, new_data: dict, schema: Literal["nested", "flat"]) -> dict` helper. Schema-aware per ADR-006. The render dispatch loop (currently `render.py:848-856`, calling `_render_pure_json` unconditionally for hooks files) is updated to check whether the file's `ReconcileDecision` is `MERGE_JSON`; if so, the dispatcher loads existing JSON, calls `_merge_hooks_json` with the schema flag determined by the file path, and writes the merged result. Manifest write records the merged hash (resolves validator warning #8).
- `src/harness_maker/cli.py` — (Phase 3) builds `merge_json_paths` set from `conflicts` similarly to existing `merge_paths`, threads through to `render()`. (Phase 4) calls `_ensure_gitignore_entry(target, ".backup-*/")` after `backup()`. (Phase 5) new `prune_backups` Typer subcommand.
- `commands/make.md` — (Phase 6) prose updates referencing matrix doc + prune CLI.
- `docs/reference/preservation-matrix.md` — (Phase 0) new doc.
- Tests: `tests/unit/test_reconcile.py`, `tests/unit/test_block_merge.py`, `tests/unit/test_render.py`, `tests/unit/test_cli.py`, `tests/unit/test_onboarding_ux_contract.py`, new `tests/unit/test_preservation_matrix.py`, new `tests/e2e/test_preservation_e2e.py`.

### Render dispatch mechanism (resolves validator warning #5)

Current dispatch (`render.py:848-856`):
```python
if _is_hooks_json(fe) or _is_cursor_mcp_json(fe) or _is_codex_hooks_json(fe):
    _render_pure_json(...)  # unconditional overwrite
```

Phase 3 dispatch (three-predicate form preserved; `.cursor/mcp.json` deliberately retains its existing pure-render path — it is NOT a hook file and is not in scope for this PLAN):
```python
if _is_hooks_json(fe) or _is_cursor_mcp_json(fe) or _is_codex_hooks_json(fe):
    if _is_cursor_mcp_json(fe):
        # .cursor/mcp.json is MCP server config, NOT a hook file.
        # Retains the existing pure-render path unchanged by this PLAN.
        _render_pure_json(...)
    elif fe.path in merge_json_paths:
        # reconcile decided MERGE_JSON because an existing hooks.json is on disk
        existing = _load_existing_hooks_json(out_path)
        schema = "flat" if str(fe.path) == ".cursor/hooks.json" else "nested"
        merged = _merge_hooks_json(existing, new_data, schema)
        content = json.dumps(merged, ...)
        write_atomic(out_path, content)
        # record MERGED hash in manifest, not template-only hash:
        manifest_hash = sha256(content)
    else:
        # No existing hooks file (fresh install) — pure-render path
        _render_pure_json(...)
```

`merge_json_paths` is a new `set[Path]` parameter on `render()`, parallel to the existing `merge_paths` (which is for MERGE_BLOCK). The CLI builds both sets from the conflict list:
```python
merge_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.MERGE_BLOCK}
merge_json_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.MERGE_JSON}
```

### Dependencies

None new. **Phase 1 and Phase 3 ship atomically** (one PR, one commit) — see ADR-006 manifest section and Risks. Phases 2 and 3 depend on Phase 0 (matrix shape locked in by tests). Phase 5 is independent. Phases 6-7 depend on 0-5.

### Architecture

```
                       Phase 0 (audit + matrix + RED tests)
                              │
                              ▼
                     Phase 1+3 atomic ship (one PR)
                     ─────────────────────────────
                     • .codex/hooks.json literal-match
                     • hooks.json schema-aware MERGE_JSON
                     • manifest extension (merged hash)
                     • ReconcileDecision.MERGE_JSON enum
                              │
                              ▼
              Phase 2 (TOML/sh marker support — detect_marker_style)
                              │
              ┌───────────────┴─────────────────┐
              ▼                                 ▼
     Phase 4 (gitignore)               Phase 5 (prune CLI)
              │                                 │
              └────────────┬────────────────────┘
                           ▼
                Phase 6 (commands/make.md prose)
                           │
                           ▼
              Phase 7 (e2e on-disk + manual IDE checklist)
```

### Design Decisions referencing ADRs

- Preservation policy per file type: ADR-002 + ADR-003 + ADR-004 + ADR-007.
- Backup behavior: ADR-001 + ADR-005.
- hooks.json merge semantics: ADR-003 + ADR-006.
- Phase atomic-ship constraint: Round 5a → ADR-006 manifest section.

### Data Flow

When `/hm:make` runs on a brownfield project after this PLAN ships:

1. `backup()` snapshots `.claude/`, `.cursor/`, `.codex/`, `.agents/`, `AGENTS.md` to `.backup-<ISO>/` (unchanged).
2. `_ensure_gitignore_entry(project_root, ".backup-*/")` appends to user's `.gitignore` if missing (new — Phase 4).
3. `reconcile()` produces per-file decisions; literal-match list now includes `.codex/hooks.json` (Phase 1, shipping atomic with Phase 3); TOML and `.sh` branches now look for `@hm:user:*` markers and fall back to MERGE_BLOCK when present, else REPLACE (Phase 2); hooks.json branches produce `MERGE_JSON` (Phase 3).
4. CLI builds `merge_paths` + `merge_json_paths` from conflict list; passes both to `render()`.
5. `render()` writes; for any file with reconcile decision MERGE_JSON: schema-aware in-place 3-way merge per ADR-006. Manifest records the merged-file hash.
6. `sweep_orphans()` (unchanged) now sees merged hooks.json as "ours-clean" via manifest match, not "theirs".

### API Changes

- `harness-maker prune-backups [--keep-last N=5] [--keep-days D=14] [--apply]` — new CLI subcommand. Read-only default; `--apply` actually deletes. Public-facing.
- No changes to the `make` command flag surface.
- New internal: `ReconcileDecision.MERGE_JSON` enum value, `render(merge_json_paths=...)` parameter. Not user-visible.

## 📝 Implementation Plan

### Phase 0 — Audit + preservation-matrix doc + RED tests

- **Scope (in):**
  - `docs/reference/preservation-matrix.md` — new doc with the matrix from §"Current State" above, expanded to include per-cell verification status (verified / gap / known-limitation), and explicit notes for the partial-edit limitation inside `developer_instructions` (per ADR-004 + ADR-007) and the matcher-modification limitation (per ADR-006).
  - `tests/unit/test_preservation_matrix.py` — new table-driven test where each cell is one parametrized test case asserting the documented preservation outcome. Cells corresponding to current gaps assert the *desired* outcome. **CI-gate safety (validator 2nd-pass W1):** TOML and `.sh` matrix cells are marked `@pytest.mark.xfail(strict=True, reason="Phase 2 not yet landed")` so the full preservation-matrix suite does not block the Phase 1+3 PR's CI run on those still-RED cells. The hooks.json cells are NOT marked xfail — they are intended to flip to GREEN in Phase 1+3, which ships next.
- **Scope (out):** Any production-code change.
- **Exit criterion:** `uv run pytest tests/unit/test_preservation_matrix.py -v` runs to completion. Hooks.json RED cells fail (expected — flipped by Phase 1+3); TOML/sh cells xfail with strict=True; GREEN cells (markdown variants, harness.yaml, settings.json, AGENTS.md, user-owned outside blueprint) pass.
- **Risk:** low (read-only).
- **Rollback:** revert Phase 0 commit; no other state changes.

### Phase 1 + 3 — Atomic ship: `.codex/hooks.json` literal-match + hooks.json schema-aware in-place merge

> **Critical phasing constraint (validator critical #2, Round 5a):** Phase 1 and Phase 3 ship as ONE PR / ONE commit-series, not independently. Phase 1 alone (literal-match → REPLACE) would lose any user-added Codex hooks for the window between Phase 1 and Phase 3 landing on main. Atomic ship eliminates that window.

- **Scope (in):**
  - `src/harness_maker/models.py` — add `ReconcileDecision.MERGE_JSON` enum value.
  - `src/harness_maker/reconcile.py:136` — extend literal-match to `hooks/hooks.json`, `.cursor/hooks.json`, AND `.codex/hooks.json`; all three map to `ReconcileDecision.MERGE_JSON` (replacing the current `REPLACE`).
  - `src/harness_maker/render.py` — new `_merge_hooks_json(existing: dict, new_data: dict, schema: Literal["nested", "flat"]) -> dict` helper. Implements the schema-aware discriminator from ADR-006. Per-event list union: template entries in template order, then existing entries whose identity tuple is NOT in template set.
  - `src/harness_maker/render.py` — dispatch loop updated: check `fe.path in merge_json_paths`; if yes, load existing, schema-dispatch on path (`.cursor/hooks.json` → flat; others → nested), invoke `_merge_hooks_json`, write merged result, record **merged hash** in manifest (resolves validator warning #8).
  - `src/harness_maker/cli.py` — build `merge_json_paths` set from conflicts; pass to `render()`.
  - Tests: `tests/unit/test_reconcile.py` — `.codex/hooks.json` produces `MERGE_JSON`; `hooks/hooks.json` and `.cursor/hooks.json` switch from REPLACE to `MERGE_JSON`. `tests/unit/test_render.py` — `_merge_hooks_json` cases per schema, including matcher-less entries (Stop, SessionStart, PermissionRequest), entries with `hooks: [{type, command, timeout, statusMessage}]`, malformed JSON falls back to REPLACE-with-warning. `tests/unit/test_render.py` — manifest records merged hash, sweep_orphans classifies merged file as ours-clean.
  - Matrix doc updated: three hooks.json cells flip to `✅ in-place merge — user entries preserved`; `.codex/hooks.json` literal-match note removed.
- **Scope (out):** TOML/sh markers (Phase 2); gitignore wiring (Phase 4).
- **Exit criterion:** All of the following green in a single CI run:
  - `uv run pytest tests/unit/test_reconcile.py -v -k "hooks_json"` green.
  - `uv run pytest tests/unit/test_render.py -v -k "merge_hooks_json"` green.
  - `uv run pytest tests/unit/test_preservation_matrix.py -v -k "hooks_json"` — Phase 0 RED cells for hooks.json flip to GREEN.
  - Round-trip test per schema: render → add user entry → re-render → user entry survives, shipped entries updated.
  - Manifest test: sweep_orphans does NOT classify merged hooks.json as "theirs".
  - **Atomicity check:** Phase 1 changes and Phase 3 changes appear in the same commit-series; no intermediate commit ships `.codex/hooks.json` REPLACE without the merge logic also present.
- **Risk:** medium-high. Three schemas; schema-aware dispatch; manifest extension; multiple touch points (models.py, reconcile.py, render.py, cli.py). Failure mode: silent user content loss if discriminator mis-classifies. Mitigation: extensive parametrized tests across all three schemas + every documented matcher-less event.
- **Rollback:** revert the entire atomic PR. `.codex/hooks.json` returns to KEEP-fallback bug; other hooks.json files return to always-REPLACE.

### Phase 2 — TOML/sh `#`-comment block-marker support

- **Scope (in):**
  - `src/harness_maker/block_merge.py` — extend `detect_marker_style()` to return `MarkerStyle.HASH_COMMENT` for `.toml` and `.sh` suffixes (resolves validator warning #4). **No change to `parse_segments` signature** — the `style: MarkerStyle = MarkerStyle.HTML_COMMENT` parameter already exists at block_merge.py:172 (validator 2nd-pass S3). `HASH_COMMENT` mode already recognizes `# @hm:user:NAME` / `# @hm:/user:NAME` on their own line (leading whitespace tolerated; trailing content rejected per existing strict-parse rule). No descent into TOML multi-line string values.
  - `src/harness_maker/reconcile.py` — TOML branch (`reconcile.py:147-155`) and sh branch (`reconcile.py:159-167`) replaced: call `detect_marker_style(fe.path)` then check `has_markers()` / `parse_segments()` with that style; if both shipped template and existing file have markers, return MERGE_BLOCK; else REPLACE.
  - Tests: `tests/unit/test_block_merge.py` — new test for `detect_marker_style('.toml')` and `detect_marker_style('.sh')` returning `HASH_COMMENT`; regression test asserting `detect_marker_style('.md')` still returns `HTML_COMMENT`; `tests/unit/test_reconcile.py` — new TOML+sh marker scenarios.
  - `tests/unit/test_preservation_matrix.py` — remove `pytest.mark.xfail` from TOML/sh cells; they should now pass with strict=True under the new path-based dispatch (validator 2nd-pass W1 cleanup).
  - Matrix doc updated: `.toml` + `.sh` cells flip to `✅ MERGE_BLOCK when TOML-level markers present`; partial-edit-inside-string limitation noted.
- **Scope (out):** hooks.json (Phase 1+3); migration tooling; descent into TOML string values.
- **Exit criterion:** Phase 0's RED tests for TOML/sh cells flip to GREEN. `uv run pytest tests/unit/test_block_merge.py tests/unit/test_reconcile.py -v` green. Round-trip test: write a `.codex/config.toml` with a `# @hm:user:my-mcp` block, re-render, assert block survives. Regression test: existing `.md` files with HTML-comment markers still parse correctly via `detect_marker_style`.
- **Risk:** medium. `block_merge.py` is the R4-canonical silent-loss surface; parser change must be paired with rigorous tests. The `detect_marker_style` extension is a small but load-bearing change; a regression here could silently break markdown parsing.
- **Rollback:** revert block_merge.py + reconcile.py changes. `.toml` and `.sh` files return to always-REPLACE behavior; matrix annotation reverts to gap.

### Phase 4 — `.backup-*/` auto-gitignore wiring

- **Scope (in):**
  - `src/harness_maker/cli.py` — after the `backup()` call site (cli.py:354), call `_ensure_gitignore_entry(target, ".backup-*/")`. If the helper isn't accessible from CLI context, move it to `io_utils.py`; the helper is in `worktree.py:990-1025` today and is import-safe.
  - Tests: `tests/unit/test_cli.py` — new test asserting `.backup-*/` appears in `<project_root>/.gitignore` after a brownfield `/hm:make` run; idempotent on second run.
- **Scope (out):** Pruning (Phase 5); non-`.backup-*/` gitignore entries.
- **Exit criterion:** `uv run pytest tests/unit/test_cli.py -v -k "gitignore"` green. Manual on dogfood: after this Phase lands, `.backup-*/` no longer surfaces in `git status -s` (covered by §Testing Strategy §Manual, not promoted to a Success Criterion).
- **Risk:** low. Helper is proven (worktree precedent). Idempotent: only appends if pattern not already present (substring match), so user's existing `!.backup-*/` un-ignore directive — if any — isn't disturbed.
- **Rollback:** revert cli.py change. `.gitignore` line stays in user projects but is harmless.

### Phase 5 — `harness-maker prune-backups` CLI subcommand

- **Scope (in):**
  - `src/harness_maker/cli.py` — new Typer command `prune_backups` with flags `--keep-last N` (default 5), `--keep-days D` (default 14), `--apply` (default False = dry-run). Keep-window semantics: keep if (rank ≤ N) OR (age ≤ D days). Other backups are prune candidates. Without `--apply`, print candidate list + total disk savings. With `--apply`, `shutil.rmtree` each candidate atomically.
  - Tests: `tests/unit/test_cli.py` — dry-run lists correct candidates; `--apply` deletes; invalid flag combinations rejected; empty backup-set produces no errors.
- **Scope (out):** Auto-prune integration into `/hm:make`; cross-repo prune.
- **Exit criterion:** `uv run pytest tests/unit/test_cli.py -v -k "prune_backups"` green. Manual on dogfood: `harness-maker prune-backups` lists ~103 candidates (108 minus the 5 most-recent), prints disk savings; `--apply` deletes them; `ls .backup-* | wc -l` ≤ 5.
- **Risk:** low. Read-only default + explicit `--apply` gate.
- **Rollback:** revert the new Typer command and tests. Dogfood `.backup-*/` dirs stay; no user-facing regression.

### Phase 6 — `commands/make.md` prose + UX contract test update

- **Scope (in):**
  - `commands/make.md` — add a sentence to §4.3 ("Safety receipt preview") and §3 ("Update" branch) referencing `docs/reference/preservation-matrix.md` and the prune CLI. Translation maintained for live-locale rendering. Existing `.backup-<timestamp>` string mentions preserved.
  - `tests/unit/test_onboarding_ux_contract.py` — extend `test_make_command_explains_receipt_safety_boundaries()`'s required-string list with exactly these two new strings: `"docs/reference/preservation-matrix.md"` and `"harness-maker prune-backups"`. Existing required strings (`.backup-<timestamp>`, `@hm:user:*`, `KEEP`, etc.) preserved.
- **Scope (out):** Other slash command files; receipt-first preview.
- **Exit criterion:** `uv run pytest tests/unit/test_onboarding_ux_contract.py::test_make_command_explains_receipt_safety_boundaries -v` green with both `"docs/reference/preservation-matrix.md"` and `"harness-maker prune-backups"` in the asserted list AND found in `commands/make.md`.
- **Risk:** low (prose only).
- **Rollback:** revert commands/make.md + test changes.

### Phase 7 — Cross-IDE on-disk verification + manual IDE acceptance checklist

> Per CLAUDE.md §"무언가를 고치거나 개선하기 전에" checkpoint 8: IDE-acceptance verification for Cursor and Codex is **manual** (no IDE-driven CI automation). On-disk reconcile output verification is automated.

- **Scope (in):**
  - **Automated:** `tests/e2e/test_preservation_e2e.py` — new e2e module. Scenarios: (a) fresh `/hm:make` on a sandbox project, (b) user edits one file per gap-closed type, (c) `/hm:make` again, (d) assert user edit survives **on disk**. Repeat per target (claude-code, cursor, codex). Gated by `INTEGRATION=1`.
  - **Manual:** `tests/cursor-compat/MANUAL_CHECKLIST.md` — extend with new preservation checklist items: (a) Cursor IDE fires merged hooks after `/hm:make --update`, (b) Codex CLI loads merged hooks after `/hm:make --update`. Dogfood pass on this repo verifies post-Phase-4 `git status` is clean and `docs/reference/preservation-matrix.md` content matches reality.
- **Scope (out):** Performance benchmarks; cross-version migration tests.
- **Exit criterion:** Two parts (split per validator warning #7):
  - **(a) Automated:** `INTEGRATION=1 uv run pytest tests/e2e/test_preservation_e2e.py -v` green — verifies on-disk reconcile + merge outcomes per schema across all three target file trees.
  - **(b) Manual:** Items in `tests/cursor-compat/MANUAL_CHECKLIST.md` checked off for Cursor + Codex IDE hook acceptance. This is explicitly not automated per CLAUDE.md checkpoint 8.
- **Risk:** medium (e2e tests touch real disk, more failure modes; sandbox setup must be deterministic; manual checklist execution depends on availability of Cursor 2.4+ and Codex CLI).
- **Rollback:** revert e2e test file + manual-checklist diff. Production code unaffected; unit + integration tests still authoritative.

## 🧪 Testing Strategy

### Unit

- **block_merge parser** — table-driven tests for both syntax modes (HTML, hash). Edge cases: nested markers (rejected), unbalanced markers (raises ParseError), trailing content on marker line (rejected). Regression: existing HTML-marker tests still green after `detect_marker_style` extension.
- **reconcile decision matrix** — one parametrized test per `(file_type, has_markers, content_hash_match)` cell. Asserts the documented decision per Phase 0 matrix. Includes new MERGE_JSON cells for hooks.json.
- **`_merge_hooks_json` discriminator** — per-schema (Claude nested, Codex nested, Cursor flat) tests; matcher-less events (Stop, SessionStart, PermissionRequest, preCompact); entries with auxiliary fields (timeout, statusMessage); duplicate-entry semantics; malformed-disk-file fallback to overwrite-from-template with warning logged.
- **Manifest extension** — after `_merge_hooks_json` writes, manifest entry's `content_hash` matches the merged file's SHA-256; `sweep_orphans` classifies as "ours-clean".
- **gitignore idempotent append** — empty file, file with existing entry, file with `!.backup-*/` un-ignore directive (must NOT add a conflicting line), missing file.
- **prune_backups dry-run vs --apply** — keep-window math (union semantics: rank ≤ N OR age ≤ D); disk-savings calculation; `--apply` actually deletes; empty backup-set graceful.

### Integration

- **Per-file-type round-trip** (Phase 0 matrix tests): for each preservation-promised file type, simulate (write existing → render → check preservation outcome). Lives in `tests/unit/test_preservation_matrix.py` as parametrized cases.
- **Brownfield migration** — user has pre-Phase-3 `hooks.json` with custom entries; first post-Phase-3 `/hm:make` preserves entries without explicit migration. Test on all three schemas.

### Manual (per CLAUDE.md checkpoint 8)

- **Dogfood**: After all phases land, on this repo:
  1. `git status -s` → no `.backup-*/` lines shown (visual check; not a Success Criterion).
  2. `harness-maker prune-backups` → lists ~103 candidates; report sane.
  3. `harness-maker prune-backups --apply` → confirms deletion; verify by `ls .backup-* | wc -l` ≤ 5.
  4. Edit a `.codex/config.toml` user block; `/hm:make --update`; verify block survives.
- **Cursor IDE acceptance** — `tests/cursor-compat/MANUAL_CHECKLIST.md` items: after a merged-hooks-json scenario, verify Cursor actually fires the merged user hook (no CI automation per CLAUDE.md checkpoint 8).
- **Codex CLI acceptance** — same shape for Codex CLI hooks.

## ⚠️ Risks & Mitigation

| Risk | Phase | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| `block_merge.py` parser regression silently drops user content (R4 canonical) | 2 | low | high | Phase 2 lands AFTER atomic Phase 1+3 ship; new parser tests > 20 cases; matrix-doc updated only after tests green; `detect_marker_style` extension covered by regression test for HTML callers. |
| `_merge_hooks_json` schema mis-classification causes day-one crash or silent loss | 1+3 | medium | high | Schema-aware discriminator per ADR-006 verified against the actual three templates; parametrized tests for every matcher-less event (Stop, SessionStart, PermissionRequest, preCompact); malformed JSON → REPLACE-with-warning fallback. |
| Phase 1 (literal-match) merged independently of Phase 3 (merge logic) — would lose user Codex hooks in the gap window | 1+3 | low (gated) | high | **Atomic ship constraint:** Phase 1 changes and Phase 3 changes appear in ONE PR / ONE commit-series; Phase 1+3 exit criterion includes an explicit atomicity check; no intermediate state on main. |
| `(matcher_or_empty, command)` discriminator collapses semantically-distinct entries | 1+3 | low | low | Documented in ADR-006 + matrix as known limitation. Users with conflicting entries must use unique commands. |
| Manifest extension missed → sweep_orphans permanently warns about hooks.json | 1+3 | low | medium | Explicit test: after merge, manifest entry matches merged hash; sweep_orphans returns "ours-clean". Resolves validator warning #8. |
| `harness-maker prune-backups --apply` deletes user-recoverable state on accident | 5 | low | high | Read-only default + explicit `--apply` flag. List output shows full disk-savings breakdown. |
| Auto-gitignore append conflicts with user's `!.backup-*/` un-ignore directive | 4 | very low | low | Idempotent substring match only adds the line if not present; doesn't disturb un-ignore directives. |
| `developer_instructions` partial-body edits not preserved without wrapping | 2 | medium | low | Documented in matrix + ADR-004 + ADR-007. `commands/make.md` Phase 6 prose mentions wrapping pattern. |
| `detect_marker_style` extension breaks existing `.md` parsing | 2 | low | high | Regression test in Phase 2 asserts HTML callers still see `MarkerStyle.HTML_COMMENT`; only `.toml` and `.sh` flip. |
| e2e tests flake on sandbox setup | 7 | medium | low | `INTEGRATION=1` gate; CI failures advisory; deterministic fixture seeding. |
| Manual IDE checklist for Cursor/Codex not executed before release | 7 | medium | medium | Phase 7 exit criterion explicitly requires both (a) automated and (b) manual passes; release-runbook references checklist. |

## ✅ Success Criteria

1. `docs/reference/preservation-matrix.md` exists and is referenced from `commands/make.md` §4.3.
2. `tests/unit/test_preservation_matrix.py` green; every documented "in-place preserved" cell passes its parametrized test.
3. `tests/unit/test_reconcile.py`, `tests/unit/test_block_merge.py`, `tests/unit/test_render.py`, `tests/unit/test_cli.py`, `tests/unit/test_onboarding_ux_contract.py` all green.
4. `INTEGRATION=1 uv run pytest tests/e2e/test_preservation_e2e.py -v` green for all three target file trees.
5. After Phase 4 lands, the new `tests/unit/test_cli.py::test_gitignore_appends_backup_glob` (or equivalent) passes — auto-gitignore wiring verified by unit test, not by shell pipeline (resolves validator warning #6).
6. `harness-maker prune-backups` shows expected candidate list; `--apply` reduces backup-dir count.
7. `ruff check`, `ruff format --check`, `mypy --strict src/` all green.
8. `commands/make.md` UX contract test passes with required strings `"docs/reference/preservation-matrix.md"` and `"harness-maker prune-backups"` (in addition to all existing required strings).
9. Manual checklist items in `tests/cursor-compat/MANUAL_CHECKLIST.md` for Cursor + Codex hook acceptance executed and recorded (per CLAUDE.md checkpoint 8).

## 🔍 Plan Validation

**Initial validator pass:** MAJOR_REVISION (3 critical, 4 warnings, 1 nit).

**Resolution log:**

| # | Severity | Topic | Resolution |
|---|---|---|---|
| 1 | critical | ADR-006 discriminator broken for actual schemas | ADR-006 rewritten as schema-aware (nested vs flat) with explicit identity tuples per schema. Verified against `templates/hooks/hooks.json.j2`, `templates/codex/hooks.json.j2`, `templates/cursor/hooks.json.j2`. Matcher-less events explicitly enumerated. |
| 2 | critical | Phase 1↔3 ordering ambiguity | Round 5a interview: atomic ship chosen. Phase 1 and Phase 3 merged into "Phase 1+3" single section; exit criterion includes explicit atomicity check; Risks table row updated; architecture diagram reflects single phase. |
| 3 | critical | ADR-007 inside-string HTML markers unverifiable | Round 5b interview: TOML-level markers only. ADR-007 retracts inside-string claim; documented limitation in matrix; ADR-004 Round-5b clarification added. |
| 4 | warning | `detect_marker_style` not updated in Phase 2 | Phase 2 scope explicitly adds `detect_marker_style` extension; regression test for HTML callers required. |
| 5 | warning | Render dispatch mechanism underspecified | New §"Render dispatch mechanism" added with concrete enum (`ReconcileDecision.MERGE_JSON`) + `merge_json_paths` parameter; CLI builds the set parallel to existing `merge_paths`. |
| 6 | warning | Success Criterion #5 uses shell grep | Replaced with unit-test reference: `test_gitignore_appends_backup_glob` (Phase 4). Manual git-status check demoted to §Testing Strategy §Manual. |
| 7 | warning | Phase 7 e2e overstates automation | Phase 7 exit criterion split into (a) automated on-disk and (b) manual IDE checklist per CLAUDE.md checkpoint 8. Success Criterion #9 added for manual pass. |
| 8 | warning | Manifest extension needed despite ADR-006 claim | ADR-006 now explicitly documents the manifest extension: merged hash recorded in `.hm-render-manifest.jsonl`; sweep_orphans test added to Phase 1+3 exit criterion. |
| 9 | nit | Phase 6 exit criterion misaligned | Phase 6 exit criterion now lists the exact required strings to add and asserts both presence in test + presence in source. |

**Second validator pass:** NEEDS_REVISION (0 critical, 2 warnings + 1 suggestion). Per /hm:plan procedure, NEEDS_REVISION resolves via interview-rounds + mechanical fix (no further validator pass).

**Second-pass resolution log (Round 6):**

| # | Severity | Topic | Resolution |
|---|---|---|---|
| W1 | warning | Phase 0 RED tests for TOML/sh would block Phase 1+3 CI gate | Phase 0 scope-in now marks TOML/sh matrix cells `pytest.mark.xfail(strict=True, reason="Phase 2 not yet landed")`. Phase 2 scope-in removes the xfail markers as cells flip GREEN. |
| W2 | warning | Phase 3 dispatch pseudocode dropped `_is_cursor_mcp_json` predicate | §"Render dispatch mechanism" pseudocode restored to three-predicate form; `.cursor/mcp.json` deliberately retains its existing pure-render path (MCP server config, not a hook file; out of PLAN scope). |
| S3 | suggestion | `parse_segments(style=...)` parameter already exists | ADR-007 §Decision bullet 3 and Phase 2 scope-in now correctly state that `style: MarkerStyle` parameter pre-exists at block_merge.py:172; Phase 2 parser-side work is zero-line. Real Phase 2 work is `detect_marker_style` + reconcile dispatch wiring. |

**Final state:** All validator findings resolved (3 critical + 4 warning + 1 nit from pass 1 → 0 critical + 2 warning + 1 suggestion from pass 2 → 0 outstanding after Round 6). Plan accepted via NEEDS_REVISION_RESOLVED. No third validator pass per "re-run validator once only" rule in /hm:plan procedure.
