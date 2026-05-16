# Block-merge spec (Layer 3 reconcile)

> Reconcile mode that preserves user edits while still accepting template updates. Two marker families coexist orthogonally: `@hm:user:*` (harness-generated files, user edits live *inside* markers) and `@hm:harness:*` (foreign-tool files harness-maker inherits, harness content lives *inside* markers, user content lives *outside*).

*Last reviewed against code: 2026-05-16 (0.12.1). The `@hm:user:*` family (0.11.x and earlier) operates on `.md` files only. The `@hm:harness:*` family (introduced 0.12.0 for M17 foreign-config migration) dispatches by file extension and supports `.md` / `.mdc` / `.yml` / `.yaml` / `.json`.*

## Marker syntax

### `@hm:user:*` family (existing, 0.11.x and earlier)

For files harness-maker **generates** (skills, agents, slash commands, etc.). Expressed as Markdown HTML comments — invisible in rendered Markdown, visible only in a text editor.

```markdown
<!-- @hm:block:<id> -->
{template-owned content}
<!-- @hm:/block:<id> -->

<!-- @hm:user:<id> -->
{user-owned content — preserved across template upgrades}
<!-- @hm:/user:<id> -->
```

- `<id>` — `[a-z][a-z0-9-]{0,30}` lowercase letters, digits, and hyphens
- Duplicate `<id>` values within the same file are not allowed
- The `<id>` in `<!-- @hm:/block:<id> -->` must exactly match the opening tag (drift detection)
- Nesting is not allowed (v1) — do not place another `block` or `user` inside a `block`

### `@hm:harness:*` family (0.12.0+, **inverted ownership**)

For foreign-AI-config files harness-maker **inherits** (M17): `.cursor/rules/*.mdc`, `CLAUDE.md`, `AGENTS.md`, `.continue/config.yaml`, `.aider.conf.yml`, `.github/copilot-instructions.md`. Here the harness owns a fenced region *inside* the markers; everything *outside* the markers is user content that survives byte-for-byte.

`MarkerStyle` dispatches by file extension:

| File extension | Marker style | Syntax |
|---|---|---|
| `.md`, `.mdc` | `HTML_COMMENT` | `<!-- @hm:harness:<id> --> ... <!-- @hm:/harness:<id> -->` |
| `.yml`, `.yaml` | `HASH_COMMENT` | `# @hm:harness:<id>` ... `# @hm:/harness:<id>` |
| `.json` | `JSON_KEY` | Top-level `"_hm_harness"` key holds harness-managed object; all other keys are user-owned and preserved |

The two families **coexist orthogonally** in the same file — each is parsed independently, so a `.md` file can have both `@hm:user:*` blocks (user additions inside) *and* `@hm:harness:*` blocks (harness regions inside, user content outside).

## Ownership semantics

### `@hm:user:*` (template-generated files)

| Block type | Owner | Behavior on update |
|---|---|---|
| `block:<id>` | harness-maker template | Always REPLACE; warn if frontmatter hash mismatches (signals that the user has edited it) |
| `user:<id>` | Project user | Always KEEP (the initial placeholder from a new template is discarded) |
| Free-floating outside markers | Template (default) | REPLACE — lines not wrapped in a marker are treated as template-owned |

**Constraint**: User edits made inside a `block:` region or outside any marker will be lost on update. To preserve changes, move them into a `user:` block or submit a PR. The `block:` marker is optional — it exists solely for drift warnings. Plain preservation only requires wrapping content in a `user:` block.

### `@hm:harness:*` (inherited foreign-config files, 0.12.0+)

Inverted relative to `@hm:user:*` — the *defaults flip*. Here harness-maker is a guest in the user's file, not the host.

| Region | Owner | Behavior on update |
|---|---|---|
| Inside `<!-- @hm:harness:<id> --> … <!-- @hm:/harness:<id> -->` | harness-maker | Always REPLACE (regenerated from template + current `harness.yaml`) |
| Outside any `@hm:harness:*` marker | Project user | Always KEEP byte-for-byte |
| Free-floating content outside markers | Project user (default) | KEEP — lines not wrapped in a `@hm:harness:*` marker are treated as user-owned |

**When each family applies**:

- `@hm:user:*` — files harness-maker **generates** end-to-end (e.g., `.claude/agents/code-reviewer.md`, `.claude/skills/*/SKILL.md`). The harness wrote the whole file; the user gets fenced regions to extend it.
- `@hm:harness:*` — files harness-maker **inherits** from another AI tool (e.g., `.cursor/rules/main.mdc` after foreign-config import, `CLAUDE.md` extended with harness-managed sections, `AGENTS.md`). The user wrote (or another tool wrote) the whole file; the harness gets fenced regions inside.

## Reconcile decision tree

The decision tree dispatches first by file extension (`MarkerStyle`) and then by family. Per file:

```
0. Resolve MarkerStyle by file extension:
     .md, .mdc        → HTML_COMMENT
     .yml, .yaml      → HASH_COMMENT
     .json            → JSON_KEY
     other            → no marker support (skip family handling)

1. Has @hm:harness:* markers in NEW template?
   1a. Yes → apply merge_inverted (see "merge_inverted algorithm" below).
            Result: harness regions replaced; everything outside preserved.
   1b. No → fall through to step 2.

2. Has @hm:user:* family marker logic apply?
   2a. No frontmatter → KEEP (legacy / user file)
   2b. Frontmatter present and `content_hash == sha256(body)` (unmodified)
       → REPLACE (whole-file overwrite, regardless of markers)
   2c. Frontmatter present and hash mismatch (user has made edits)
       2c-i.  NEW template has markers + OLD body also has markers + OLD parses cleanly
              → MERGE_BLOCK (block-level merge)
       2c-ii. NEW + OLD both have markers, but OLD fails to parse (user broke marker syntax)
              → KEEP whole-file (reason: hash-mismatch-malformed-markers)
              → User edits take priority; avoids silent loss from falling through to REPLACE
       2c-iii. All other cases (either side has no markers)
              → KEEP whole-file (legacy fallback)
```

When both marker families are present in the same file, step 1 runs first (harness regions are refreshed inside the user's content), then step 2 logic applies to any `@hm:user:*` blocks within the harness-managed region.

## MERGE_BLOCK algorithm

OLD = current file on disk (may contain user edits), NEW = freshly rendered template output.

1. Start from NEW as the base (template's new structure and new placeholders)
2. Parse OLD by markers → collect the contents of each `user:<id>` block into a dict
3. Walk NEW; for each `user:<id>` block:
   - If the same `id` exists in the OLD dict → replace the NEW user block content with it (KEEP)
   - Otherwise → leave NEW as-is (initial placeholder)
4. `user:<id>` blocks that exist only in OLD (id no longer present in NEW) → appended to the end of the file as a quarantine section:
   ```markdown
   <!-- @hm:user:_orphans -->
   <!-- User block from a previous template version; no matching id in the new template. Manual cleanup required. -->
   ## (orphan) <id>
   {original content}
   <!-- @hm:/user:_orphans -->
   ```
5. If a `block:<id>` content in OLD mismatches the `blocks.<id>` hash in the frontmatter → warn (user has edited a template-owned block). REPLACE still proceeds.

Free-floating lines outside markers are not handled separately — the content outside markers in NEW is used as-is (REPLACE).

## `merge_inverted` algorithm (`@hm:harness:*`, 0.12.0+)

OLD = current file on disk (predominantly user content), NEW = freshly rendered harness regions.

1. Start from OLD as the base (preserve all user content unchanged).
2. Parse OLD by `@hm:harness:*` markers → collect a dict of `<id>` → (open_offset, close_offset).
3. Parse NEW by `@hm:harness:*` markers → collect `<id>` → body content.
4. Walk NEW marker dict; for each `<id>`:
   - If the same `<id>` exists in OLD → splice NEW's body into OLD between the OLD `open_offset` / `close_offset`, replacing only that fenced region. Marker lines stay where the user placed them.
   - If the `<id>` is missing in OLD → append the full `<!-- @hm:harness:<id> --> ... <!-- @hm:/harness:<id> -->` block to the end of the file (or after a configurable anchor) so the next render is idempotent.
5. `@hm:harness:<id>` blocks present in OLD but missing in NEW → strip the block (both markers + body) because the harness no longer claims that region. No quarantine: this is the inverse of `@hm:user:*`, so removing a stale harness region is the correct behavior.
6. `MarkerStyle.JSON_KEY` files use a structural variant: parse JSON, replace the top-level `_hm_harness` value with NEW's, leave every other key intact. Order-preserving via `collections.OrderedDict` so user-readable diffs stay minimal.

Free-floating user content outside `@hm:harness:*` markers is **never touched** — that is the inversion. Compare to `MERGE_BLOCK`, where free-floating lines are REPLACE by default.

## 0.11.x → 0.12.0 Migration

Files rendered by 0.11.x with no `@hm:harness:*` markers in body get a one-time upgrade on first encounter post-0.12.0. Detection rule (per ADR-009 amendment):

```
is_pre_0_12_0_render =
    frontmatter.generated_by == "harness-maker"
    AND no @hm:harness:* markers in body
```

**Behavior**:

1. On first encounter, the file is treated as wholly harness-owned — the whole file is rewritten with the new `@hm:harness:*` marker family. User edits made under the old (frontmatter-only) ownership model are not preserved at this step. (Rationale: the 0.11.x foreign-config render was never meant to be user-editable; the marker family makes user editing explicit going forward.)
2. The rewrite is idempotent — a second render against the now-marked file is a no-op.

**Test guard**: `test_apply_0_11_x_migration` in `tests/unit/test_foreign_config.py` verifies (a) the first render rewrites and (b) the second render is byte-identical to the first.

If a user wants to preserve 0.11.x edits across this upgrade, they must back the file up before the first 0.12.0 render. The `/hm:configure` exit prompt warns about this on the upgrade path.

## Frontmatter extension (v1.5+)

v1 uses only `content_hash` (whole-body). v1.5 will add:

```yaml
content_hash: <whole-body-sha256>
blocks:
  procedure: <hash>
  inputs: <hash>
  outputs: <hash>
```

`blocks` covers only `block:<id>` marker types (user blocks are user-owned and do not need a hash). The current `block_merge.detect_drift()` function is exported in anticipation of v1.5 but is not called anywhere yet.

## CLI output (v1)

```
harness applied to /home/noel/kairos/.claude (46 files)
  KEEP: 2 file(s) preserved as-is (no markers — won't receive new template content)
  MERGE_BLOCK: stages/review.md — preserved 3 user block(s): procedure-extras, extra-quality-checks, extensions
```

Planned additions in v1.5:
- `block:<id>` drift warning ("user edited inside template-owned block")
- Malformed marker warning ("KEEP due to user-introduced syntax error")

## Migration / compatibility

- Legacy files without markers (0.1.x, 0.2.x output) → handled by the existing KEEP/REPLACE logic. No new markers are added automatically.
- If a legacy file receives a REPLACE (i.e., the user has not modified it) → it is updated to the new template (which includes markers) → MERGE_BLOCK becomes available on the next render.
- To intentionally migrate a modified legacy file to marker mode → use the `--force` flag to overwrite the whole file, then re-add personal additions inside a `user:` block.

## Out of scope for v1 (future work)

- Nested blocks — **deferred**
- JSON/YAML markers (key-level merge) — **Closed in 0.12.0** (via `MarkerStyle.JSON_KEY` for `@hm:harness:*` on `.json` files, and `HASH_COMMENT` for `.yml`/`.yaml`). The `@hm:user:*` family still ships `.md`-only; cross-format support there remains deferred.
- Partial auto-update within `user:` blocks (e.g., domain standard patches) — **deferred**
- 3-way merge with `git merge-file` (for preserving user edits inside `block:` regions) — **deferred**
- Foreign AI config migration (`.cursor/rules/`, `CLAUDE.md`, `AGENTS.md`, `.continue/`, `.aider.conf.yml`, copilot-instructions) — **Closed in 0.12.0** via the new `@hm:harness:*` inverted marker family + M17 in `src/harness_maker/foreign_config.py`.
