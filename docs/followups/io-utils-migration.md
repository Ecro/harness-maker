# Follow-up: `io_utils.load_harness_yaml()` migration

> **Source PLAN:** [PLAN-second-brain-write-failure](../../work-docs/PLAN-second-brain-write-failure.md) — ADR-001 & ADR-007.
> **Created:** 2026-05-17.

`harness_maker.io_utils.load_harness_yaml(path)` centralises the
provenance-frontmatter-aware loader for `.claude/harness.yaml`. The Second
Brain connector migrated in this PLAN; four pre-existing readers remain on
legacy strategies and should be migrated to keep parser handling consistent
and prevent future drift (RESEARCH §Pitfall 2).

## Direct migration candidates (parse `harness.yaml`)

| File | Current strategy | Notes |
|---|---|---|
| `src/harness_maker/verify.py` (line 34) | `yaml.safe_load_all` + iterate | Works today, but rolls its own multi-doc handling. |
| `src/harness_maker/worktree.py` (lines 315, 340) | `yaml.safe_load_all` + iterate | Two sites; same pattern. |

Each direct call site has a `# TODO(io-utils-migration)` comment marker so
this tracker stays discoverable from the source.

## Related but out of scope (different file types)

| File | What it parses | Note |
|---|---|---|
| `src/harness_maker/autoloop_driver.py` (line 233) | `loop-spec.yaml`, `loop-context/<slug>.yaml` | Frontmatter convention is shared, but file type differs. A future generic `load_yaml_with_frontmatter(path)` could subsume both. |
| `src/harness_maker/context_lint.py` (line 42) | Strips frontmatter for body-line counts (agents, skills, commands) | Pure text strip; never parses YAML body. Out of scope. |

## Migration steps per caller

1. Replace local parse with `from harness_maker.io_utils import load_harness_yaml`.
2. Call `data = load_harness_yaml(path)`; `data` is a `dict[str, Any]`,
   empty when the file has no top-level mapping or is empty.
3. Drop the `_strip_frontmatter` helper / inline `safe_load_all` walker.
4. Remove the `# TODO(io-utils-migration)` marker.
5. Run that module's existing tests; no behavior change expected.

## Out-of-scope guardrails

- Do not introduce caller-specific branches in `load_harness_yaml`.
  Caller-side post-processing (e.g., picking sub-keys, schema validation)
  stays in the caller.
- Keep the "last non-empty mapping wins" contract — provenance frontmatter
  is the first doc, user data is the last.
