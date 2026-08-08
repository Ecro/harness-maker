# Failure Archive 2026

> Entries evicted from `.claude/memory/failures.md` by `upsert-failure`:
> `count:1` and older than 90 days at eviction time.
> Archived, never deleted — a `count>=2` entry is exempt at any age.

## [fail:test] typer-cli-runner-mix-stderr | 2026-05-09 | count:1
`CliRunner(mix_stderr=True)` raises `TypeError` — typer's `CliRunner.__init__()` does not accept `mix_stderr`. Only `unittest.mock`'s Click-based TestCase variant accepts that kwarg. Fix: remove `mix_stderr=True`; `result.output` in typer's CliRunner already captures both stdout and stderr by default.

## [fail:runtime] subprocess-missing-timeout | 2026-05-09 | count:1
`_run()` in `worktree.py` was written without `timeout=` on `subprocess.run()`. A hung git command (SSH auth prompt, NFS stall) would block the CLI indefinitely. Found by security-reviewer + concurrency-reviewer consensus (P1). Fix: `_GIT_TIMEOUT = 60` constant + `timeout=_GIT_TIMEOUT` in `_run()` + `except subprocess.TimeoutExpired as e: raise RuntimeError(f"timed out after {_GIT_TIMEOUT}s: ...") from e`. CLAUDE.md §외부 명령 호출 explicitly requires `timeout=N` — the rule was in CLAUDE.md from the start but missed during Phase 2 implementation.

## [fail:design] return-type-change-breaks-callers | 2026-05-09 | count:1
`worktree.create()` return type changed from `Path` to `list[Path]`. The e2e test at `tests/e2e/test_dogfood_sandbox.py:143` called `.exists()` on the returned value — which now returns a list, causing `AttributeError: 'list' object has no attribute 'exists'`. Caught by code-reviewer (finding E). Fix: `worktree.create("dev", repo)[0]`. Pattern: when changing a function's return type from scalar to container, grep ALL callers (unit tests, e2e tests, CLI entrypoints) before finalizing the change. The unit tests were updated but e2e was missed.

## [fail:test] boundary-test-no-sentinel | 2026-05-09 | count:1
`test_git_as_file_stops_walk` asserted `_find_marker(subdir) is None` but planted no marker above the boundary. The test passed regardless of whether the boundary guard worked, because no marker happened to exist above `tmp_path` in the test environment. Fix: always plant a marker ABOVE the boundary in a `try/finally` block so the test fails if the walk ignores the boundary. Pattern: boundary tests must prove both "find it when it should be found" AND "don't find it when the boundary blocks."

