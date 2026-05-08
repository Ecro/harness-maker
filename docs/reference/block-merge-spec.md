# Block-merge spec (Layer 3 reconcile)

> Reconcile mode that preserves user edits while still accepting template updates. v1 constraint: flat blocks, `.md` files only.

*Last reviewed against code: 2026-05-07 (0.7.1). Block-merge markers (`@hm:user:*`) currently operate on `.md` files only. `.cursor/rules/*.mdc` files are handled separately due to frontmatter constraints.*

## Marker syntax

Expressed as Markdown HTML comments — invisible in rendered Markdown, visible only in a text editor.

```markdown
<!-- @hm:block:<id> -->
{template-owned content}
<!-- @hm:/block:<id> -->

<!-- @hm:user:<id> -->
{user-owned content}
<!-- @hm:/user:<id> -->
```

- `<id>` — `[a-z][a-z0-9-]{0,30}` lowercase letters, digits, and hyphens
- Duplicate `<id>` values within the same file are not allowed
- The `<id>` in `<!-- @hm:/block:<id> -->` must exactly match the opening tag (drift detection)
- Nesting is not allowed (v1) — do not place another `block` or `user` inside a `block`

## Ownership semantics

| Block type | Owner | Behavior on update |
|---|---|---|
| `block:<id>` | harness-maker template | Always REPLACE; warn if frontmatter hash mismatches (signals that the user has edited it) |
| `user:<id>` | Project user | Always KEEP (the initial placeholder from a new template is discarded) |
| Free-floating outside markers | Template (default) | REPLACE — lines not wrapped in a marker are treated as template-owned |

**Constraint**: User edits made inside a `block:` region or outside any marker will be lost on update. To preserve changes, move them into a `user:` block or submit a PR. The `block:` marker is optional — it exists solely for drift warnings. Plain preservation only requires wrapping content in a `user:` block.

## Reconcile decision tree

Per file:

```
1. No frontmatter → KEEP (legacy/user file)
2. Frontmatter present and `content_hash == sha256(body)` (unmodified)
   → REPLACE (whole-file overwrite, regardless of markers)
3. Frontmatter present and hash mismatch (user has made edits)
   3a. NEW template has markers + OLD body also has markers + OLD parses cleanly
       → MERGE_BLOCK (block-level merge)
   3b. NEW + OLD both have markers, but OLD fails to parse (user broke marker syntax)
       → KEEP whole-file (reason: hash-mismatch-malformed-markers)
       → User edits take priority; avoids silent loss from falling through to REPLACE
   3c. All other cases (either side has no markers)
       → KEEP whole-file (legacy fallback)
```

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

- Nested blocks
- JSON/YAML markers (key-level merge)
- Partial auto-update within `user:` blocks (e.g., domain standard patches)
- 3-way merge with `git merge-file` (for preserving user edits inside `block:` regions)
