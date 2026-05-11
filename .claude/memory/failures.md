---
generated_by: harness-maker
harness_maker_version: 0.9.4
generated_at: '2026-01-01T00:00:00+00:00'
source_template: memory/failures.en.md.j2
provenance: official
---
# Failures Log — Production preset

> Repeated mistakes / pitfalls in this project. The wrapup stage appends entries automatically.
>
> **Search:** `rg -F "[fail:" .claude/memory/failures.md`
>
> **Format:**
> ```
> ## [fail:<category>] <slug> | <YYYY-MM-DD> | count:<N>
> <reproduction trigger + root cause + resolution in one paragraph>
> ```
> - `category`: import / test / render / hook / lint / type / runtime / design / other
> - `count`: bump the heading only on repeats (never duplicate sections)
> - When count ≥ 3, wrapup adds an improvement proposal to `.claude/memory/pending-proposals.md`

---

<!-- @hm:user:entries -->
## [fail:test] snapshot-regen-inside-worktree | 2026-05-10 | count:3
Running `tests/snapshot/regenerate.py` inside a git worktree embeds the worktree absolute path in all rendered template outputs (via `synthesize._HARNESS_MAKER_PKG_ROOT = Path(__file__).parent.parent.parent`). The resulting SHA-256 hashes diverge from hashes computed when tests run in the main repo. Fix: always run `regenerate.py` from the main repo root. This recurred again in the make-ux-gaps loop — the worktree squash-merge left snapshots with worktree-specific hashes. Recurred a third time in deep-interview-llm-delegation: regen ran from main repo BEFORE worktree finalize, so old template sha256s were generated; worktree must be finalized (stage-only) first so new templates are present in main before running regen. Correct sequence: (1) run unit tests from worktree, (2) finalize stage-only, (3) regen from main repo root, (4) full pytest from main.

## [fail:test] typer-cli-runner-mix-stderr | 2026-05-09 | count:1
`CliRunner(mix_stderr=True)` raises `TypeError` — typer's `CliRunner.__init__()` does not accept `mix_stderr`. Only `unittest.mock`'s Click-based TestCase variant accepts that kwarg. Fix: remove `mix_stderr=True`; `result.output` in typer's CliRunner already captures both stdout and stderr by default.

## [fail:runtime] subprocess-missing-timeout | 2026-05-09 | count:1
`_run()` in `worktree.py` was written without `timeout=` on `subprocess.run()`. A hung git command (SSH auth prompt, NFS stall) would block the CLI indefinitely. Found by security-reviewer + concurrency-reviewer consensus (P1). Fix: `_GIT_TIMEOUT = 60` constant + `timeout=_GIT_TIMEOUT` in `_run()` + `except subprocess.TimeoutExpired as e: raise RuntimeError(f"timed out after {_GIT_TIMEOUT}s: ...") from e`. CLAUDE.md §외부 명령 호출 explicitly requires `timeout=N` — the rule was in CLAUDE.md from the start but missed during Phase 2 implementation.

## [fail:design] return-type-change-breaks-callers | 2026-05-09 | count:1
`worktree.create()` return type changed from `Path` to `list[Path]`. The e2e test at `tests/e2e/test_dogfood_sandbox.py:143` called `.exists()` on the returned value — which now returns a list, causing `AttributeError: 'list' object has no attribute 'exists'`. Caught by code-reviewer (finding E). Fix: `worktree.create("dev", repo)[0]`. Pattern: when changing a function's return type from scalar to container, grep ALL callers (unit tests, e2e tests, CLI entrypoints) before finalizing the change. The unit tests were updated but e2e was missed.

## [fail:test] boundary-test-no-sentinel | 2026-05-09 | count:1
`test_git_as_file_stops_walk` asserted `_find_marker(subdir) is None` but planted no marker above the boundary. The test passed regardless of whether the boundary guard worked, because no marker happened to exist above `tmp_path` in the test environment. Fix: always plant a marker ABOVE the boundary in a `try/finally` block so the test fails if the walk ignores the boundary. Pattern: boundary tests must prove both "find it when it should be found" AND "don't find it when the boundary blocks."

## [fail:test] class-methods-orphaned-by-partial-edit | 2026-05-10 | count:1
`TestCheckErrorCap` had 8 methods. The `Edit` tool's `old_string` captured only the first 3 methods (through `test_syntax_over_cap`), leaving the remaining 5 (`test_logical_under_cap`, `test_logical_at_cap`, `test_unknown_under_cap`, `test_unknown_at_cap`, `test_empty_counts_safe`) as un-indented dead defs. After the worktree merge, those 5 methods orphaned as nested function definitions inside the next test function (`test_s8_loop_context_backward_compat`). They compiled fine but were unreachable by pytest. Fix: always read the full class body before writing `old_string`; when editing a class, the `old_string` must include the full class through its last method (or use a marker at the class close). Grep for all `def test_` under a class before committing to the `old_string`.

## [fail:review] abbreviated-diff-causes-reviewer-false-positives | 2026-05-10 | count:1
When the review prompt for a large diff abbreviates template content with inline placeholders like `[...same 4-axis check, plan-specific dimension labels...]` or `[... Full gate text: 53 lines ...]`, reviewers interpret those placeholders as literal file content (stub/placeholder text in the template). In this case, code-reviewer raised P1 findings against plan.md.j2 for "Layer 1 placeholder stub" and "Full gate text stub" — both false positives. Fix: verify against actual file content with grep before applying single-source findings; drop false positives in the consensus step. Prevention: never abbreviate template body content in the diff context passed to reviewers; if the diff is too large, pass the full file via Read instead of an inline summary.

## [fail:render] toml-section-header-variable-injection | 2026-05-10 | count:1
Jinja2 template used `[mcp_servers.{{ server_name }}]` in `config.toml.j2`. TOML interprets unquoted dotted keys as nested table hierarchies — a server name like `server.name` creates `mcp_servers["server"]["name"]` (wrong nesting) instead of `mcp_servers["server.name"]` (intended). The `_render_pure_toml()` validator passes because the output IS valid TOML, just with unexpected structure. Caught by security-reviewer in review. Fix: `[mcp_servers."{{ server_name }}"]` — TOML quoted-key syntax safely handles dots, spaces, and special characters. Rule: any Jinja2 variable injected into a TOML section header key MUST use `"{{ var }}"` quoting.

## [fail:render] yaml-colon-in-unquoted-frontmatter-description | 2026-05-10 | count:1
`skills/conditional-router/SKILL.md.j2` description contained `` `routing: conditional` `` unquoted in YAML frontmatter. `yaml.safe_load()` in `_split_template_frontmatter()` raised `YAMLError` (mapping values not allowed), function returned `({}, rendered)` — frontmatter not extracted. Renderer prepended provenance block on top of the still-present template frontmatter, producing two `---` blocks. Codex reports "missing field description" since it only reads the first block. Fix: double-quote any description that contains `: ` sequences. The silent `except yaml.YAMLError: return {}, rendered` path makes this failure non-obvious — no CLI warning, no verify error, only an IDE-level symptom.

## [fail:design] codex-helpers-ignore-user-config | 2026-05-11 | count:1
`_codex_stage_skills()` and `_codex_target_files()` each constructed `HarnessConfig()` locally, so rendered Codex skill bodies always embedded factory-default paths and workflow names regardless of the user's `harness.yaml`. Root cause: both functions were implemented as standalone helpers with no access to the live `config_dump` from `synthesize()`; `synthesize()` also called them BEFORE computing `config_dump`. Review caught this as two independent 2/2 consensus-passed P1 findings. Fix: move `config = HarnessConfig(...)` and `config_dump = config.model_dump()` to the TOP of `synthesize()` (before file_specs), add `config_dump: dict[str, object] | None = None` parameter to both helpers, thread via `_codex_target_files(fused_workflows, config_dump=config_dump)`. Added config-threading verification tests (`test_codex_stage_skills_uses_passed_config_dump`, `test_codex_target_files_threads_config_dump_to_stage_skills`).

## [fail:review] reviewer-subagent-model-unsupported | 2026-05-11 | count:2
During `/hm:review`, configured reviewer agents failed to spawn because their fixed `o4-mini` role model is not supported for this Codex account. The stage recovered by recording reviewer unavailability and completing a local orchestrator review plus full test verification, but true cross-reviewer consensus was unavailable. Same root cause hit `/hm:plan` Step 4 plan-validator dispatch (the "o4" string also rejected on ChatGPT-tier). **Resolution (2026-05-11)**: dropped per-agent `model = "..."` from rendered `.codex/agents/*.toml` (ADR-001 / PLAN-codex-plan-validator-model-unavailable). Codex now inherits the user's `~/.codex/config.toml` profile default. Live probes confirmed `gpt-5.5` works on this account while `o4`, `o4-mini`, `gpt-5-codex`, `gpt-5.5-codex` all return HTTP 400. Template gate `{% if model_codex %}` preserved for a deferred opt-in HarnessConfig knob.

## [fail:render] yaml-empty-list-renders-null | 2026-05-11 | count:1
Jinja2 rendering `folders:` with no list items produced YAML null instead of `[]`, so `SecondBrainConfig` strict validation rejected the default rendered config and `answers_from_harness_yaml` silently fell back to disabled defaults. Fix: branch in YAML templates and render `folders: []` when empty; add a round-trip test that default `second_brain` reuses without warning. Pattern: every optional rendered YAML list needs an explicit empty-list representation, not a bare key.

## [fail:workflow] worktree-merge-stale-base | 2026-05-11 | count:1
`worktree finalize stage-only` failed with `error: Your local changes to the following files would be overwritten by merge` because the worktree's branch was created from `bc19c26` but main advanced to `dbfdf24` (another stage's commit) before this stage tried to merge back. `git merge --squash` from the older base detects "conflicts" with the new main commits on the same files even when the modified regions don't overlap. From the worktree the symptom looked like main had 53 modified files staged/unstaged (the entire post-`bc19c26` delta showing as "uncommitted" because the worktree didn't have those commits in its base). Resolution: `cd <WT> && git rebase main` (main repo is local — no remote needed), then retry `worktree finalize stage-only`. Rebase is clean when the new main commits don't touch the worktree's modified regions; conflicting regions require manual resolution. Diagnostic: run `git status` inside the **main repo** path (not the worktree) — if main itself shows clean, the "WIP" you see from the worktree is the new main commits the worktree hasn't caught up to.

<!-- @hm:/user:entries -->
