# Follow-up: `io_utils.load_harness_yaml()` migration

> **Source PLAN:** [PLAN-second-brain-write-failure](../../work-docs/PLAN-second-brain-write-failure.md) — ADR-001 & ADR-007.
> **Created:** 2026-05-17. **Direct migrations completed:** 2026-05-17 (same day, follow-up commit).

`harness_maker.io_utils.load_harness_yaml(path)` centralises the
provenance-frontmatter-aware loader for `.claude/harness.yaml`. The Second
Brain connector migrated in the parent PR; the two direct callers below have
been migrated in this follow-up commit.

## Direct migration candidates (parse `harness.yaml`) — ✅ DONE

| File | Status | Notes |
|---|---|---|
| `src/harness_maker/verify.py` | ✅ Migrated 2026-05-17 | Replaced `list(yaml.safe_load_all(...))` parse-check with `load_harness_yaml(hy)`. Behavior unchanged — both raise `yaml.YAMLError` on malformed input; existing `if not hy.exists():` branch handles the missing-file path. |
| `src/harness_maker/worktree.py` (`_scope_includes`, `_load_sibling_dirs`) | ✅ Migrated 2026-05-17 | Both functions replaced their `yaml.safe_load_all` loops with `load_harness_yaml()` + direct `.get()` access. The loader returns the last non-provenance mapping, so a single `data.get("worktree")` / `data.get("sibling_repos")` lookup is equivalent to scanning all docs (provenance never carries these keys). Behavior identical to the prior multi-doc-iter implementation; `OSError` / `yaml.YAMLError` still produce the early-return / empty-result paths. |

`# TODO(io-utils-migration)` markers removed from both files. 62 unit tests
(`tests/unit/test_verify.py`, `tests/unit/test_worktree.py`,
`tests/unit/test_io_utils.py`) pass against the migrated code with zero
behavioural change.

## Related but out of scope (different file types) — NOT migrated

| File | What it parses | Note |
|---|---|---|
| `src/harness_maker/autoloop_driver.py` (line 233) | `loop-spec.yaml`, `loop-context/<slug>.yaml` | Frontmatter convention is shared, but file type differs. A future generic `load_yaml_with_frontmatter(path)` could subsume both. `# TODO(io-utils-migration)` marker retained pending that generic helper. |
| `src/harness_maker/context_lint.py` (line 42) | Strips frontmatter for body-line counts (agents, skills, commands) | Pure text strip; never parses YAML body. Out of scope. `# TODO(io-utils-migration)` marker retained as a breadcrumb only. |

## Out-of-scope guardrails (still apply going forward)

- Do not introduce caller-specific branches in `load_harness_yaml`.
  Caller-side post-processing (e.g., picking sub-keys, schema validation)
  stays in the caller.
- Keep the "last non-provenance mapping wins" contract — provenance
  frontmatter (`generated_by: harness-maker`) is filtered out; user data
  is whatever remains.
