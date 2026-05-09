---
generated_by: harness-maker
harness_maker_version: 0.7.2
generated_at: '2026-01-01T00:00:00+00:00'
source_template: memory/failures.ko.md.j2
provenance: official
---
# Failures Log — Production preset

> 이 프로젝트에서 반복된 실수 / 함정을 기록합니다. wrapup 스테이지가 자동 추가합니다.
>
> **검색:** `rg -F "[fail:" .claude/memory/failures.md`
>
> **형식:**
> ```
> ## [fail:<category>] <slug> | <YYYY-MM-DD> | count:<N>
> <재현 조건 + 원인 + 해결책 한 단락>
> ```
> - `category`: import / test / render / hook / lint / type / runtime / design / other
> - `count`: 동일 실수 반복 시 헤딩만 업데이트 (중복 섹션 금지)
> - count ≥ 3 이면 wrapup 이 `.claude/memory/pending-proposals.md` 에 개선 제안 추가

---

<!-- @hm:user:entries -->
## [fail:test] snapshot-regen-inside-worktree | 2026-05-09 | count:1
Running `tests/snapshot/regenerate.py` inside a git worktree embeds the worktree absolute path in all rendered template outputs (via `synthesize._HARNESS_MAKER_PKG_ROOT = Path(__file__).parent.parent.parent`). The resulting SHA-256 hashes diverge from hashes computed when tests run in the main repo. Fix: always run `regenerate.py` from the main repo root. The session that ran it inside `.worktrees/execute-0924Z/` required a second regeneration from the main branch to produce correct stable hashes.

## [fail:test] typer-cli-runner-mix-stderr | 2026-05-09 | count:1
`CliRunner(mix_stderr=True)` raises `TypeError` — typer's `CliRunner.__init__()` does not accept `mix_stderr`. Only `unittest.mock`'s Click-based TestCase variant accepts that kwarg. Fix: remove `mix_stderr=True`; `result.output` in typer's CliRunner already captures both stdout and stderr by default.

## [fail:runtime] subprocess-missing-timeout | 2026-05-09 | count:1
`_run()` in `worktree.py` was written without `timeout=` on `subprocess.run()`. A hung git command (SSH auth prompt, NFS stall) would block the CLI indefinitely. Found by security-reviewer + concurrency-reviewer consensus (P1). Fix: `_GIT_TIMEOUT = 60` constant + `timeout=_GIT_TIMEOUT` in `_run()` + `except subprocess.TimeoutExpired as e: raise RuntimeError(f"timed out after {_GIT_TIMEOUT}s: ...") from e`. CLAUDE.md §외부 명령 호출 explicitly requires `timeout=N` — the rule was in CLAUDE.md from the start but missed during Phase 2 implementation.

## [fail:design] return-type-change-breaks-callers | 2026-05-09 | count:1
`worktree.create()` return type changed from `Path` to `list[Path]`. The e2e test at `tests/e2e/test_dogfood_sandbox.py:143` called `.exists()` on the returned value — which now returns a list, causing `AttributeError: 'list' object has no attribute 'exists'`. Caught by code-reviewer (finding E). Fix: `worktree.create("dev", repo)[0]`. Pattern: when changing a function's return type from scalar to container, grep ALL callers (unit tests, e2e tests, CLI entrypoints) before finalizing the change. The unit tests were updated but e2e was missed.

## [fail:test] boundary-test-no-sentinel | 2026-05-09 | count:1
`test_git_as_file_stops_walk` asserted `_find_marker(subdir) is None` but planted no marker above the boundary. The test passed regardless of whether the boundary guard worked, because no marker happened to exist above `tmp_path` in the test environment. Fix: always plant a marker ABOVE the boundary in a `try/finally` block so the test fails if the walk ignores the boundary. Pattern: boundary tests must prove both "find it when it should be found" AND "don't find it when the boundary blocks."

<!-- @hm:/user:entries -->
