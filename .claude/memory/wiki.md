---
generated_by: harness-maker
harness_maker_version: 0.7.4
generated_at: '2026-01-01T00:00:00+00:00'
source_template: memory/wiki.ko.md.j2
provenance: official
---
# Wiki Index — Production preset

> 프로젝트별 패턴 / 컨벤션 인덱스. wrapup 스테이지가 자동 추가합니다.
>
> **검색:** `rg -F "[wiki:" .claude/memory/wiki.md`
>
> **형식:**
> ```
> ## [wiki:<category>] <slug> | <YYYY-MM-DD>
> <패턴 설명: 언제 쓰는지, 왜 이 방법인지 한 단락>
> ```
> - `category`: pattern / convention / gotcha / architecture / tooling / api / other
> - slug 는 kebab-case. 동일 패턴 업데이트 시 헤딩 날짜만 갱신 (중복 섹션 금지)

---

<!-- @hm:user:entries -->
## [wiki:architecture] multi-repo-worktree-sibling | 2026-05-09
`sibling_repos` in harness.yaml lists relative paths (no absolute paths — cross-machine portability). `worktree.create` emits one path per line: line 1 = primary WT, lines 2+ = sibling WTs. The loop driver reads all non-empty lines. Gate now globs `.claude/.hm-loop-*` (per-session files) and allows writes in ANY matching WT path. Finalize is fail-fast: first merge failure halts, marker file KEPT so gate stays active for the session; re-running finalize skips already-cleaned WTs via `wt.is_dir()` check. `execute.md.j2` carries a `SIBLING_WORKTREE_PATHS` sentinel comment — absent means stale template, CLI emits primary-only with a stderr warning. Tests live in `test_worktree_multi.py` (worktree) and `test_interview_sibling.py` (interview/round-trip).

## [wiki:convention] how-it-works-grade-table | 2026-05-09
`/hm:review` grade table: A=P0:0,P1:0 / B=P0:0,P1:1-2 / C=P0:0,P1≥3 / D=P0:1-2 / F=P0≥3. The field is `grade_threshold` (default A), not `max_grade_threshold`. P2/weak-consensus/manual-only findings do NOT lower the grade — only `consensus-passed` P0/P1 count.

## [wiki:gotcha] docs-grade-table-wrong-3x | 2026-05-09
When documenting the review grade table, all boundary values were wrong on first attempt: thresholds were offset (A included P1≤2, B included P1≤5, etc). Root cause: grade table was reconstructed from memory instead of reading `review.md` source. Fix: always read the skill source file before documenting grade logic.

## [wiki:architecture] generator-not-runtime-config | 2026-05-09
harness-maker must stay a generator (Jinja2 pre-render), not a pure plugin that reads harness.yaml at runtime. Three file categories are irreducible: (1) hooks.json — IDE-specific schemas (PascalCase vs lowercase camelCase) consumed pre-LLM, no plugin-system injection hook; (2) settings.json — permission sandbox established before LLM runs, cannot be self-set; (3) CLAUDE.md — technically injectable but would break the `<!-- @hm:user:* -->` block-merge contract and content_hash KEEP/REPLACE/MERGE_BLOCK reconciliation that lets user customizations survive upgrades. Agents/skills/commands could be runtime-configured but the complexity delta is not eliminated since the three infra files still need rendering. See ADR-001 in PLAN-plugin-vs-generator-2026-05.

## [wiki:gotcha] worktree-snapshot-harness-path | 2026-05-09
`test_synthesize_snapshot.py` compares `body_sha256` of rendered files. The `ai-readiness.md.j2` template embeds `{{ harness_maker_src_path }}` which resolves to `_HARNESS_MAKER_PKG_ROOT = str(Path(__file__).parent.parent.parent)` — an absolute path. When pytest runs from a worktree (`.worktrees/execute-*/`) the path differs from the main repo, producing a different hash. All 8 snapshot tests fail in the worktree but pass on the main repo. Always run snapshot tests from the main repo directory to verify.

## [wiki:architecture] per-session-worktree-marker | 2026-05-09
ADR-006: per-session marker files replace the single global `.hm-loop-active`. Pattern: `_write_loop_marker(project_root, primary_wt_name, wt_paths)` writes `.claude/.hm-loop-{primary_wt_name}` (newline-joined absolute paths). `_clear_loop_marker(project_root, wt_name)` deletes only that file. `_detect_existing_worktree` drops the marker-based Signal 1 — each session creates its own WT, no sentinel needed. Gate upgrade (Phase 3): glob `.claude/.hm-loop-*`, union all paths, ANY-match. Key invariant: marker kept on `finalize fail` so gate continues protecting surviving worktrees; cleared only on full success.

## [wiki:pattern] sibling-rollback-on-create-failure | 2026-05-09
`worktree.create()` with sibling repos: if any sibling `git worktree add` fails, rollback all already-created siblings then primary with `contextlib.suppress(RuntimeError)` best-effort cleanup, then re-raise. Pattern: `sibling_wts: list[Path] = []`, append after each successful add, except-block iterates `zip(sibling_wts, siblings[:len(sibling_wts)], strict=False)` then handles primary. `contextlib.suppress` preferred over try/except to satisfy ruff SIM105. Timeout errors (60s) also trigger rollback since `_run()` raises `RuntimeError` for both `CalledProcessError` and `TimeoutExpired`.

## [wiki:pattern] loop-gate-stop-hook-guard | 2026-05-09
The `.hm-loop-active` marker file (placed at git root by `loop.md.j2` step 5, removed before wrapup in step 7) is the signal the `loop_gate.py` Stop hook reads. Key invariants: (1) `stop_hook_active: true` in stdin JSON must be checked BEFORE `_find_marker()` — Claude Code re-fires Stop on every `/stop` attempt, so the guard prevents infinite loop; (2) `.git`-as-file (worktree `gitdir:` pointer) counts as a git boundary — walk stops on both `Path.is_dir()` and `Path.exists()` for `.git`; (3) Cursor has no Stop event equivalent — PreToolUse advisory only, always exits 0; (4) Step 7 deletes the marker FIRST, before wrapup, so a wrapup crash cannot leave a stale marker that blocks future sessions.

## [wiki:pattern] loop-4gate-convergence | 2026-05-10
`/hm:loop` convergence uses 4 independent gates instead of a single LLM judgment: Gate 1 (Mechanical — run `ExitCriterion.cmd` items, skip `cmd=""`; `required:false` = warning only), Gate 2 (LLM individual — evaluate each criterion label independently; deadlock detector increments `criterion_ambiguity_counts[label]` on "Ambiguous", triggers `AskUserQuestion` at count 3), Gate 3 (Regression — compare exit-code + set of failing test names vs `runtime.last_test_result` baseline; skip on iter 1), Gate 4 (Streak — single reset site, increment on all-pass, reset to 0 on any fail, converged at ≥ 2). All four ephemeral counters (`convergence_streak`, `checklist_fail_counts`, `criterion_ambiguity_counts`, `last_test_result`) persist to the `runtime:` block of the loop-context YAML so they survive `/compact`. Recovery instruction lives in loop.md.j2 step 6. The checklist gate (step 7) fires BEFORE marker deletion so re-entry cycles remain under the Stop hook guard.

<!-- @hm:/user:entries -->
