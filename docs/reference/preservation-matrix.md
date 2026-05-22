# Preservation Matrix

> **Audit deliverable for** [PLAN-onboarding-backup-friction]. This document
> answers the question "when I run `/hm:make` on a project where I already have
> custom commands/skills/agents/hooks, does the harness keep them in place?"

## TL;DR

Backup (`backup()`) runs unconditionally per [ADR-001] and is the secondary
safety net. **In-place preservation is the primary mechanism.** This document
enumerates every file type the renderer touches and states whether user content
is preserved at the original path after a brownfield `/hm:make` run.

| Legend | Meaning |
|---|---|
| ✅ | In-place preserved by reconcile/render semantics. Backup recovery not needed. |
| ⚠️ | Preserved only under a documented condition (e.g. markers present). |
| ❌ | Currently overwritten; backup is the only recovery. |

The ❌ cells are the closure targets of [PLAN-onboarding-backup-friction]
phases 1+3 and 2.

## Matrix

| # | File class | Path examples | Current behavior (pre-PLAN) | Target behavior (post-PLAN) | Verified by |
|---|---|---|---|---|---|
| M1 | Markdown without frontmatter | `.claude/commands/my-custom.md` user-authored | reconcile → `KEEP` (no-frontmatter rule, `reconcile.py:168-176`) | unchanged ✅ | `test_preservation_matrix.py::test_m1_markdown_no_frontmatter` |
| M2 | Markdown with `@hm:user:*` markers (both sides) | shipped agent edited inside marker block | reconcile → `MERGE_BLOCK` (block-marker rule) | unchanged ✅ | `test_m2_markdown_block_marker_merge` |
| M3 | Markdown — hash mismatch, no markers | shipped file user edited outside marker | reconcile → `KEEP` (`_decide_user_modified` fallback, `reconcile.py:256`) | unchanged ✅ | `test_m3_markdown_hash_mismatch_no_markers` |
| M4 | `harness.yaml` | always present | REPLACE + `_preserve_yaml_user_keys` + `answers_from_harness_yaml` | unchanged ✅ user top-level keys preserved | `test_m4_harness_yaml_preserves_user_keys` |
| M5 | `settings.json` | always present | REPLACE + `_shallow_merge_existing_json` + `_merge_permissions` (list union) | unchanged ✅ user keys + permissions preserved | `test_m5_settings_json_preserves_permissions` |
| M6a | `hooks/hooks.json` (Claude PascalCase nested) | shipped | **always-REPLACE** ❌ | **`MERGE_JSON`** (Phase 1+3, schema-aware merge per [ADR-006]) | `test_m6a_claude_hooks_json_merges` |
| M6b | `.cursor/hooks.json` (Cursor flat camelCase) | shipped | **always-REPLACE** ❌ | **`MERGE_JSON`** (Phase 1+3) | `test_m6b_cursor_hooks_json_merges` |
| M6c | `.codex/hooks.json` (Codex PascalCase + PermissionRequest) | shipped | `.codex/hooks.json` NOT in reconcile literal-match → falls through to KEEP-fallback (latent bug, [ADR-002]) | **`MERGE_JSON`** (Phase 1+3 fixes both literal-match AND wires merge) | `test_m6c_codex_hooks_json_merges` |
| M7a | `.codex/config.toml` | shipped | **always-REPLACE** ❌ | ⚠️ **reconcile returns `MERGE_BLOCK` when markers present; render's `_render_pure_toml` falls back to template overwrite** (Phase 2 half-shipped — detection complete, render merge deferred — see "Phase 2 render-merge follow-up" below) | `test_m7a_codex_config_toml_marker_aware` (decision) + e2e xfail |
| M7b | `.codex/agents/*.toml` | shipped 6+ agents | **always-REPLACE** ❌ | ⚠️ same half-shipped state as M7a | `test_m7b_codex_agent_toml_marker_aware` (decision) + e2e xfail |
| M8 | `.claude/lib/*.sh` | shipped wrappers | **always-REPLACE** ❌ | ⚠️ same half-shipped state as M7a (no shipped `.sh` templates yet; dispatch ready) | `test_m8_claude_lib_sh_marker_aware` xfail (no template) |
| M9 | `AGENTS.md` (project root) | shipped | `MERGE_BLOCK` (codex-agents-merge rule, `reconcile.py:122-129`) | unchanged ✅ user blocks preserved | `test_m9_agents_md_block_merge` |
| M10 | User custom file at blueprint root, NOT in blueprint | `.codex/agents/my-custom.toml` user-authored | orphan-sweep classifies as "theirs" → KEEP+warn | unchanged ✅ | `test_m10_user_orphan_kept` |
| M11 | `.cursor/mcp.json` | shipped | pure-render REPLACE | unchanged (out of PLAN scope; not a hook file) | `test_m11_cursor_mcp_json_replaces` |

## Phase 2 render-merge follow-up (v0.23.x)

Phase 2 (TOML/sh hash-comment markers) shipped in two halves:

- ✅ **Detection complete (v0.23.0):** `block_merge.detect_marker_style` returns `HASH_COMMENT` for `.toml`/`.sh` suffixes; `reconcile._decide_hash_comment_branch` correctly returns `MERGE_BLOCK` when both the shipped template and the existing file carry `# @hm:user:start:NAME` markers; shipped `codex/config.toml.j2` and `codex/agent.toml.j2` carry empty `user_extensions` blocks ready for user content.
- ⚠️ **Render merge deferred:** `block_merge.merge()` is HTML_COMMENT-only by construction (`block_merge.py:477-479` explicitly documents this; adding a `style` parameter touches the marker-walk hot path with fence tracking, etc.). Until that lands, `render._render_pure_toml` ignores `merge_paths` and **template overwrite wins** — the user's content between `# @hm:user:*` markers is overwritten on re-render.

User data **is not lost** — `backup()` runs unconditionally per [ADR-001], so the prior file (with user content) is recoverable from `.backup-<ts>/`. The Phase 2 contract is the auto-merge path, not the safety net.

Follow-up scope (v0.23.x): extend `merge()` with `style: MarkerStyle` parameter, forward to `parse_segments` / `parse_user_blocks` / fence detection. e2e cell `test_e2e_codex_config_toml_user_block_survives` xfail-strict marker flips to GREEN at that point.

## Known limitations (documented contracts, not bugs)

1. **Matcher-mutation loss in hooks.json merge (ADR-006).** If a user modifies a shipped entry's `matcher` field while keeping the `command` identical, the modification is wiped on re-render because the discriminator identifies the entry as shipped. Workaround: add a new entry rather than mutating shipped ones.

2. **Partial body edits inside `developer_instructions` (TOML agent files) not preserved without wrapping (ADR-004 + ADR-007).** The block-merge parser does not descend into TOML multi-line string values. To preserve a custom body, the user wraps the entire `developer_instructions = """ … """` assignment with `# @hm:user:start:body_override` ... `# @hm:user:end:body_override` at TOML statement level. Partial-string edits are out of scope.

3. **Multi-nested-hook entries (ADR-006).** For Claude/Codex nested schemas, entries with multiple members in their inner `hooks: [...]` array dedup only on `hooks[0]`. Current templates always ship length-1 inner arrays; this limitation is a future-proofing note.

4. **Malformed JSON fallback (ADR-006).** If an existing `hooks.json` cannot be parsed as JSON, render falls back to template-overwrite (REPLACE) with a warning logged. Backup is the recovery path. Same fallback applies if the parsed JSON doesn't match the expected `{event: [entries]}` shape.

5. **`.cursor/mcp.json`** is not a hook file and is deliberately out of scope. It retains the pure-render REPLACE behavior. MCP server config is owned by the harness; users should add MCP servers via `/hm:configure` rather than editing this file directly.

## How to verify each cell

Each row's "Verified by" column names a test function in
[`tests/unit/test_preservation_matrix.py`]. The test module runs as part of
the standard pytest suite. Cells corresponding to Phase 1+3 / Phase 2 work
that has not yet landed are marked `pytest.mark.xfail(strict=True, reason="Phase X
not yet landed")` so the full suite can run without blocking PRs that are
not the gap-closing PRs themselves.

[ADR-001]: ../../work-docs/PLAN-onboarding-backup-friction.md#adr-001-always-backup-is-non-negotiable
[ADR-002]: ../../work-docs/PLAN-onboarding-backup-friction.md#adr-002-audit-plus-full-gap-closure-scope
[ADR-003]: ../../work-docs/PLAN-onboarding-backup-friction.md#adr-003-hooksjson-in-place-3-way-merge
[ADR-004]: ../../work-docs/PLAN-onboarding-backup-friction.md#adr-004-toml-marker-scope
[ADR-005]: ../../work-docs/PLAN-onboarding-backup-friction.md#adr-005-backup-housekeeping-gitignore-auto-retention-user-gated
[ADR-006]: ../../work-docs/PLAN-onboarding-backup-friction.md#adr-006-hooksjson-entry-discriminator-schema-aware
[ADR-007]: ../../work-docs/PLAN-onboarding-backup-friction.md#adr-007-tomlsh-marker-syntax-and-scope
[PLAN-onboarding-backup-friction]: ../../work-docs/PLAN-onboarding-backup-friction.md
[`tests/unit/test_preservation_matrix.py`]: ../../tests/unit/test_preservation_matrix.py
