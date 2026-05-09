---
type: plan
task_slug: multi-repo-mgmt-2026-05
status: complete
created: 2026-05-09
tags: [harness-maker, plan, worktree, multi-repo, sibling-repos, python]
research_doc: "[[RESEARCH-multi-repo-mgmt-2026-05]]"
interview_rounds: 3
adrs: 6
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "sibling_repos field + multi-worktree create/gate/finalize for 2-repo logical projects"
---

# PLAN — Multi-repo Support (sibling_repos)

## 🎯 Executive Summary

**What:** Add `sibling_repos` to harness.yaml so 2+ repos forming one logical project share a single harness and get coordinated worktree isolation.

**Why:** `worktree.create` / `worktree_gate` assume a single git repo. An active loop blocks all writes outside the primary worktree — including files in a sibling repo. Users must disable worktree isolation entirely to make cross-repo edits.

**Key Decisions (→ ADRs):**
- Harness in one designated primary repo; siblings listed in `sibling_repos` (ADR-001)
- `worktree create` emits multi-line stdout: line 1 = primary path, 2+ = sibling paths (ADR-002)
- Finalize fail-fast: first merge failure halts; marker KEPT until all succeed (ADR-003)
- Wrapup auto-commits each repo sequentially; fails loudly on sibling commit failure (ADR-004)
- Finalize failure: per-repo status to stderr + marker retained for re-run idempotency (ADR-005)

**Estimated impact:** ~350 lines Python across 6 files + 2 template files. Zero breaking changes for existing single-repo users.

---

## 🚫 Non-Goals

The following are explicitly OUT OF SCOPE for this plan:

- **Auto-detection of sibling repos** via `.git` walk or `.cursor/` heuristics — user must declare them explicitly (same policy as `targets` auto-detect prohibition in CLAUDE.md)
- **Transitive siblings** — `sibling_repos` is a flat list; siblings of siblings are not followed
- **Per-sibling workflow names** — all sibling repos run the same workflow as primary
- **Atomic cross-repo commit semantics** — each repo gets an independent commit; no 2-phase-commit or merge-queue coordination
- **Parent-dir-as-workspace** — parent directory of repos is not a harness install target
- **Cursor IDE native multi-repo** — Cursor Phase 1 manual checklist is unchanged; only Claude Code flow is updated here

---

## 📚 Prior Work

- RESEARCH-multi-repo-mgmt-2026-05: surfaces the structural gap in `worktree.py` and `worktree_gate.py`.
- CLAUDE.md §Worktree cleanup 정책: prefix-match cleanup (`phase-*`, `autoloop-*`) — sibling worktrees must use a distinct slug suffix to avoid Cursor collision.
- CLAUDE.md §8체크포인트 §2 (외부 소비자 파서 정합성): `.hm-loop-active` is read by `worktree_gate` — format change must be backward-compatible.
- `models.py RefFolder`: uses portable relative-path `str` for cross-repo paths — same convention adopted for `sibling_repos`. (Note: RefFolder is read-only; `sibling_repos` is read-write — roles differ.)

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|-------|----------|----------|---------|--------|------|-------|
| 1 | 설치 위치 | Architecture | Harness 설치 위치 | Primary repo / Parent dir / Independent | Primary repo (repo-a), `sibling_repos: [../repo-b]` | — | ADR-001 |
| 2 | stdout 계약 | Contract | worktree create stdout 형식 | Multi-line / Single-line+file / list-active | Multi-line: line 1 = primary, 2+ = siblings | execute.md.j2 업데이트 필요 | ADR-002 |
| 3 | Finalize 실패 | Risk | partial failure 정책 | Fail-fast / Best-effort / Undo-on-fail | Fail-fast (양쪽 보존, 이미 성공한 squash 취소 안 함) | — | ADR-003 |
| 4 | Wrapup commit | Contract | multi-commit 흐름 | 순차 auto-commit / Primary만 / 수동 | 순차 auto-commit (같은 메시지) | — | ADR-004 |
| V1 | Finalize 복구 | Risk (validator #2/#8) | 실패 후 gate 보호 + 복구 경로 | finalize-resume 서브커맨드 / per-repo 상태 출력만 | Per-repo 상태 출력 + marker 유지 (서브커맨드 없음) | 재시도는 finalize 재실행 (wt.is_dir() skip으로 idempotent) | ADR-005 |
| P | 병렬 세션 격리 | Architecture | 2개 세션이 동일 worktree 공유 방지 | Single global `.hm-loop-active` / Per-session `.hm-loop-{wt-name}` | Per-session 파일; `_detect_existing_worktree`에서 marker 기반 검색 제거 (path-only) | 각 세션이 독립 WT 생성 | ADR-006 |

---

## 📐 Architecture Decision Records

### ADR-001: Primary repo model — not parent dir

**Status:** Accepted (2026-05-09)

**Context:** A 2-repo logical project needs a harness anchor point. The parent directory is often not a git repo, so `git worktree add` cannot be called there.

**Decision:** Harness is installed in one designated primary repo (e.g., `repo-a`). Sibling repos are listed in `harness.yaml.sibling_repos` as **relative paths** (absolute paths rejected by Pydantic validator — cross-machine portability). Paths are resolved against the primary repo root at runtime. Claude Code is opened at the primary repo.

**Consequences:**
- ✅ Zero structural changes to harness installation flow.
- ✅ `git worktree add` always has a valid git repo as base.
- ✅ Relative paths survive git commits and cross-machine clones.
- ⚠️ Parent-dir-as-workspace not supported (see Non-Goals).
- ⚠️ Absolute paths are rejected — users who paste absolute paths get a clear error at interview time.

**Rejected alternatives:**
- Parent dir harness — `git worktree add` fails on non-git dir; harness renders but isolation silently skips.
- Independent harness per repo — no coordination; `worktree_gate` in each repo still blocks cross-repo writes.

**Source:** Interview #1

---

### ADR-002: Multi-line stdout for `worktree create`

**Status:** Accepted (2026-05-09)

**Context:** `execute.md` parses `worktree create` stdout as `<WT>`. With siblings, the agent needs all worktree paths.

**Decision:** `worktree create` emits one absolute path per line: line 1 = primary, lines 2+ = siblings (same order as `sibling_repos`). Empty output = "no isolation" (unchanged). `execute.md.j2` updated with multi-line parsing instructions and `<WT-{slug}>` naming.

**Stale-execute.md mitigation:** `_cli_create` inspects the rendered `.claude/commands/hm/execute.md` for the sentinel string `SIBLING_WORKTREE_PATHS`. If sibling repos are configured but the sentinel is absent, emits a warning to stderr and falls back to primary-only stdout (safe degradation, gate still protects both via `.hm-loop-active`). User is instructed to run `make --update`.

**Consequences:**
- ✅ Agent has complete information about all active worktrees.
- ✅ Single-repo: one line emitted (unchanged).
- ✅ Stale execute.md: degrades safely (primary-only) + visible warning, not silent failure.
- ⚠️ `execute.md.j2` template update required; existing rendered files stale until `make --update`.

**Rejected alternatives:**
- Single-line + agent reads `.hm-loop-active` — implicit, harder to document.
- Separate `list-active` subcommand — splits responsibility, extra `!` block.

**Source:** Interview #2 + validator critical #1 (stale-file mitigation added)

---

### ADR-003: Fail-fast finalize; marker KEPT until all succeed

**Status:** Accepted (2026-05-09)

**Context:** Multi-repo finalize can partially succeed. On failure, the gate must continue protecting surviving worktrees.

**Decision:** `_cli_finalize` processes repos in order (primary first). On first failure: halt, emit per-repo status to stderr (`succeeded:[...], failed:[repo-X], pending:[...]`), **keep `.hm-loop-active` intact** (do NOT clear — gate continues protecting all worktrees). Repos that already succeeded remain squash-merged (no undo). Marker is only cleared when ALL repos finalize successfully.

**Idempotent re-run:** Each repo's worktree directory is cleaned up immediately upon successful merge. On re-run of `finalize <WT> stage-only`, repos whose worktree dir no longer exists (`not wt.is_dir()`) are skipped — only failed/pending repos are retried.

**Consequences:**
- ✅ Gate stays active after partial failure — sibling worktree files are protected.
- ✅ Re-run is safe: completed repos skip automatically.
- ✅ Per-repo status gives user actionable information.
- ⚠️ Primary can be squash-merged while sibling is not — user must rerun finalize after fixing sibling conflict. User confirmed this is acceptable.

**Rejected alternatives:**
- Clear marker on failure — rejected because gate stops protecting surviving worktrees.
- `finalize-resume` subcommand — rejected in favor of simpler re-runnable main command.
- Best-effort — partial success state is worse than clear halt.

**Source:** Interview #3 + validator critical #2 → Interview V1

---

### ADR-004: Wrapup sequential auto-commit, fail-loud on sibling failure

**Status:** Accepted (2026-05-09)

**Context:** Wrapup currently runs one `git commit`. With siblings, each needs an independent commit.

**Decision:** Wrapup reads `sibling_repos` from `harness.yaml`, resolves paths, commits primary first then each sibling with the same message. On sibling commit failure: surface the offending repo to the user + suggest manual retry. Do NOT rollback the primary commit — consistent with ADR-003 fail-fast philosophy (completed work is not undone).

**Consequences:**
- ✅ Consistent commit message across all repos.
- ✅ Fail-loud on sibling failure: user has clear actionable state.
- ⚠️ Primary committed while sibling is not — user must commit sibling manually on failure.

**Rejected alternatives:**
- Primary-only auto-commit + manual sibling — inconsistent state, user burden.
- Rollback primary on sibling failure — `git revert` of squash commit is complex; user confirmed fail-fast without undo.

**Source:** Interview #4 + validator warning #7

---

### ADR-005: Per-repo status output + marker retention on finalize failure

**Status:** Accepted (2026-05-09)

**Context:** Validator identified that clearing `.hm-loop-active` on partial finalize failure disables gate protection for surviving worktrees, leaving them unprotected.

**Decision:** Finalize failure path: keep marker intact; emit structured status to stderr. Re-run `worktree finalize` is the recovery mechanism. Idempotency is achieved via worktree directory existence check (cleaned dirs are skipped automatically). No new `finalize-resume` subcommand.

**Consequences:**
- ✅ Gate protection maintained throughout failure + recovery.
- ✅ No new CLI surface to document.
- ✅ Re-run is self-describing via stderr status output.
- ⚠️ User must re-run `worktree finalize` manually after fixing the sibling conflict.

**Source:** Interview V1 (validator critical #2 follow-up)

---

### ADR-006: Per-session marker files + path-only idempotent detection

**Status:** Accepted (2026-05-09)

**Context:** The single `.hm-loop-active` marker is a global slot — last-write wins. When two Claude Code sessions run in parallel on the same project, Session B's `_detect_existing_worktree` reads Session A's marker and returns Session A's worktree path instead of creating its own. Both sessions operate in one worktree → write collision and context contamination.

**Decision:**
1. Replace `.hm-loop-active` with per-session marker files: `.claude/.hm-loop-{wt-basename}` (e.g., `.hm-loop-execute-20260509T0817Z`). One file per active session — coexist at OS level without contention.
2. Remove Signal 1 (marker-based) from `_detect_existing_worktree`; keep only Signal 2 (path-based: CWD is already inside `.worktrees/<name>/`). Loops must CD into `<WT>` before dispatching sub-commands — this is already the execute stage §0 convention (`!cd <WT> && <cmd>`).
3. Gate scans `glob(".hm-loop-*")` in `.claude/` and collects all paths across all matching files → `any()` match allows write.
4. `.gitignore` pattern: `.claude/.hm-loop-*` (replaces `.claude/.hm-loop-active`).
5. Finalize deletes only its own session's marker file (`.hm-loop-{primary-wt-basename}`).

**Consequences:**
- ✅ Parallel sessions each get an independent worktree — no collision.
- ✅ Gate correctly protects all concurrent sessions' worktrees simultaneously.
- ✅ Stale markers from crashed sessions are harmless: gate filters non-existent paths at read time.
- ⚠️ Loops must CD into `<WT>` before sub-commands for path-based detection to work. Already the convention in execute.md §0 (`!cd <WT> && uv run ...`).
- ⚠️ Backward compat: pre-ADR-006 `.hm-loop-active` files (different name) are ignored by new gate. Users with an in-flight loop at upgrade time must finalize it first.

**Rejected alternatives:**
- Session ID in filename — no stable session ID exposed by Claude Code runtime.
- Multiple entries in one file with locking — concurrent atomic-append is OS-complex; per-file coexistence is naturally atomic.

**Source:** User observation (2026-05-09) — parallel worktree collision in multi-session use

---

## 🏗️ Technical Design

### Current State

```
worktree.create(workflow, base_dir: Path) -> Path
  git worktree add -b <name> <path>  [cwd=base_dir]
  _write_loop_marker(base_dir, wt_path)  → single-path file

.hm-loop-active:  /abs/path/.worktrees/execute-ts   (one line, global slot)

worktree_gate:
  active_wt = _read_active_worktree()   → Path | None
  allow iff target.is_relative_to(active_wt)

finalize <WT> stage-only:
  capture_pending(wt)
  merge(wt, squash, commit=False)
  cleanup(wt, force=True)
  _clear_loop_marker_if_matches(project_root, wt)   ← always clears

⚠️ Problem: parallel sessions share the same global marker → Session B
   reuses Session A's worktree instead of creating its own.
```

### Affected Components

| Component | Change | Risk |
|-----------|--------|------|
| `models.py` | `sibling_repos: list[str]` + Pydantic absolute-path validator | low |
| `worktree.py` | `create` multi-repo; `_write_loop_marker` → per-session file; `_cli_create` loads sibling_repos + stale-file warning; `_cli_finalize` fail-fast multi-repo + per-session file deletion; `_detect_existing_worktree` Signal 1 removed | medium |
| `gates/worktree_gate.py` | scan `.hm-loop-*` glob; collect all paths; `any()` match | low |
| `interview.py` | sibling_repos question + path validation + `answers_from_harness_yaml` | low |
| `synthesize.py` | pass-through `sibling_repos` | low |
| `templates/harness-yaml/*.yaml.j2` | render `sibling_repos` field | low |
| `templates/commands/hm/execute.md.j2` | multi-line stdout parse; `<WT-{slug}>` naming; `SIBLING_WORKTREE_PATHS` sentinel | medium |
| `templates/commands/hm/wrapup.md.j2` | sequential multi-repo commit blocks; fail-loud on sibling failure | low |

### Architecture After Change

```
worktree.create(workflow, base_dir: Path, sibling_dirs: list[Path] | None = None) -> list[Path]
  # Branch pre-flight: find suffix free in ALL repos simultaneously
  suffix = _find_free_suffix(workflow, ts, [base_dir, *sibling_dirs])
  primary_wt = git worktree add -b suffix.primary <path>  [cwd=base_dir]
  sibling_wts = [
    git worktree add -b suffix.{slug} <path>  [cwd=sibling]
    for sibling, slug in zip(sibling_dirs, slugs)
  ]
  _write_loop_marker(base_dir, [primary_wt, *sibling_wts])
  # stale execute.md check → stderr warning if SIBLING_WORKTREE_PATHS sentinel absent
  return [primary_wt, *sibling_wts]

# Per-session marker file (ADR-006): .claude/.hm-loop-{wt-basename}
.hm-loop-execute-20260509T1234Z:          ← Session A's marker
  /abs/path/repo-a/.worktrees/execute-20260509T1234Z
  /abs/path/repo-b/.worktrees/execute-20260509T1234Z-repo-b

.hm-loop-execute-20260509T0900Z:          ← Session B's marker (parallel)
  /abs/path/repo-a/.worktrees/execute-20260509T0900Z

worktree_gate:
  all_paths = scan(".claude/.hm-loop-*") → collect all paths from all files
  allow iff any(target.is_relative_to(wt) for wt in all_paths)

_detect_existing_worktree(base):
  Signal 2 ONLY (path-based): base path contains ".worktrees/<name>" → return that
  Signal 1 (marker-based) REMOVED — parallel sessions must not cross-detect

_cli_finalize(args):
  # marker = .claude/.hm-loop-{primary_wt.name}  (ADR-006: per-session file)
  marker_file = project_root / ".claude" / f".hm-loop-{primary_wt.name}"
  all_wts = _read_paths_from_file(marker_file)
  succeeded, failed, pending = [], None, list(all_wts)
  for wt in all_wts:
    if not wt.is_dir():       # already finalized in a prior run → skip
      succeeded.append(wt); pending.remove(wt); continue
    capture_pending(wt)       # may raise
    merge(wt, strategy, commit=auto_commit)  # may raise
    on RuntimeError as e:
      failed = wt; pending.remove(wt) if wt in pending else None
      print(f"succeeded:{succeeded}\nfailed:{[wt]}\npending:{pending}", stderr)
      # KEEP marker_file — gate stays active for this session
      return 1
    cleanup(wt, force=True)   # cleanup immediately after successful merge
    succeeded.append(wt); pending.remove(wt)
  marker_file.unlink(missing_ok=True)   # delete only THIS session's file
  return 0
```

### Branch Naming

**Pre-flight strategy (cross-repo collision safe):**
```python
def _find_free_suffix(workflow: str, ts: str, repos: list[Path]) -> str:
    """Find a base name free in ALL repos before creating any worktree."""
    for attempt in range(100):
        name = f"{workflow}-{ts}" if attempt == 0 else f"{workflow}-{ts}-{attempt}"
        # Each sibling gets name + "-{slug}" variant; check all repos
        if all(_branch_free(repo, name, slug) for repo, slug in zip(repos, slugs)):
            return name
    raise RuntimeError("exhausted 100 branch-name attempts")
```

- Primary branch: `{name}` (e.g., `execute-20260509T1234Z`)
- Sibling branch: `{name}-{slug}` where `slug = Path(sibling_dir).name`
- Sibling slugs guaranteed distinct from primary because primary has no suffix.
- Two siblings with same basename (e.g., `../a/app` and `../b/app`) → their slugs both `app` → collision in THEIR repos. Solution: use full relative path hash as slug for such edge cases (Phase 2 implementation detail).

### Data Flow

```
Interview
  Q: sibling repos? → sibling_repos: ["../repo-b"]
        ↓
Synthesize → HarnessConfig.sibling_repos (absolute path rejected by validator)
        ↓
Render:
  .claude/harness.yaml       → sibling_repos: ["../repo-b"]
  commands/hm/execute.md     → SIBLING_WORKTREE_PATHS sentinel + multi-line parse
  commands/hm/wrapup.md      → sequential commit blocks

Runtime (execute):
  worktree create "$(pwd)"
    → reads harness.yaml.sibling_repos → resolves ../repo-b
    → _find_free_suffix → suffix free in both repos
    → creates primary WT + sibling WT
    → checks execute.md for SIBLING_WORKTREE_PATHS sentinel
      → absent: stderr warning, emit primary path only (safe degradation)
      → present: emit all paths
    → .hm-loop-active: two paths

Agent sees:
  <WT>          = /repo-a/.worktrees/execute-ts        (primary)
  <WT-repo-b>   = /repo-b/.worktrees/execute-ts-repo-b (sibling)

worktree_gate:
  Write /repo-a/.worktrees/execute-ts/src/foo.py       → ALLOW
  Write /repo-b/.worktrees/execute-ts-repo-b/bar.ts    → ALLOW
  Write /repo-a/src/foo.py                             → BLOCK

finalize <primary_WT> stage-only:
  reads .hm-loop-active → [primary_wt, sibling_wt]
  primary: capture + squash-merge + cleanup
  sibling: capture + squash-merge + cleanup
  on failure: emit succeeded/failed/pending, KEEP marker, exit 1
  on full success: _clear_loop_marker, exit 0

Re-run after failure:
  finalize <primary_WT> stage-only (same command)
  primary wt: not wt.is_dir() → skip (already cleaned)
  sibling wt: wt.is_dir() → process (retry)

wrapup:
  git add -A && git commit -m "..." in repo-a (primary)
  git add -A && git commit -m "..." in repo-b (sibling)
  on sibling commit failure: loud error + manual retry hint; primary commit NOT reverted
```

### API Changes

```python
# models.py — HarnessConfig + InterviewAnswers
sibling_repos: list[str] = Field(default_factory=list)

@field_validator("sibling_repos", mode="before")
@classmethod
def _reject_absolute(cls, v: list[str]) -> list[str]:
    for p in v:
        if Path(p).is_absolute():
            raise ValueError(f"sibling_repos must be relative paths; got absolute: {p!r}")
    return v

# worktree.py
def create(workflow: str, base_dir: Path, sibling_dirs: list[Path] | None = None) -> list[Path]:
    """Returns [primary_wt, *sibling_wts]. Single-repo → list of length 1."""

def _write_loop_marker(project_root: Path, wt_paths: list[Path]) -> None:
    """Newline-separated paths. Replaces single-path version."""

def _clear_loop_marker(project_root: Path) -> None:
    """Unconditional clear. Replaces _clear_loop_marker_if_matches."""

# gates/worktree_gate.py
def _read_active_worktrees(project_root: Path) -> list[Path]:
    """Replaces _read_active_worktree. Splits on \\n, filters empty/missing."""
```

---

## 📝 Implementation Plan

### Phase 1 — Model update + absolute-path validator ✅ DONE

**Scope IN:** `src/harness_maker/models.py`

Add `sibling_repos: list[str] = Field(default_factory=list)` to `HarnessConfig` and `InterviewAnswers`. Add `@field_validator("sibling_repos")` rejecting absolute paths.

**Exit criterion:**
```bash
uv run mypy --strict src/harness_maker/models.py
uv run pytest tests/unit/test_models.py -v
```
`HarnessConfig(sibling_repos=["../repo-b"])` validates. `HarnessConfig(sibling_repos=["/abs/repo-b"])` raises `ValueError`.

**Risk:** low  
**Rollback:** git revert Phase 1 changes to `models.py`.

---

### Phase 2 — `worktree.create` multi-repo + marker format + stale-file detection ✅ DONE (reviewed, Grade A)

**Scope IN:** `src/harness_maker/worktree.py` — `create`, `_write_loop_marker`, `_clear_loop_marker` (new, replaces `_clear_loop_marker_if_matches`), `_cli_create`, `cleanup_all`

**Scope OUT:** `worktree_gate.py`, templates, `interview.py`

**Key changes:**

1. `_find_free_suffix(workflow, ts, repos, slugs)` — pre-flight: checks branch availability in ALL repos before any `git worktree add`. Raises after 100 attempts.
2. `create(workflow, base_dir, sibling_dirs=None) -> list[Path]`:
   - Calls `_find_free_suffix`
   - Creates primary worktree, then each sibling with `{name}-{slug}` branch
   - Returns `[primary_wt, *sibling_wts]`
3. `_write_loop_marker(project_root, primary_wt_name, wt_paths: list[Path])` — atomic write of newline-joined paths to `.claude/.hm-loop-{primary_wt_name}` (per-session file, ADR-006).
4. `_detect_existing_worktree`: Remove Signal 1 (marker-based scan). Keep Signal 2 only (path-based: base.parts contains `.worktrees/<name>`). Parallel sessions now each create their own WT.
5. `_cli_create`:
   - Reads `harness.yaml.sibling_repos`, resolves against `base_dir`
   - Calls new `create`
   - Checks `.claude/commands/hm/execute.md` for `SIBLING_WORKTREE_PATHS` sentinel; if sibling_dirs and sentinel absent → `stderr: "[WARNING] execute.md stale — run 'make --update'"` + emit primary path only
   - Otherwise emits all paths (one per line)
5. `cleanup_all`: reads `.hm-loop-active` to discover sibling dirs (not just primary repo).
6. `_clear_loop_marker(project_root)` — unconditional clear (used only on full success).

**Backward compatibility:** `create(workflow, base_dir)` (no sibling_dirs) → `[primary_wt]`. Single-path `.hm-loop-active` parses as list of 1.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_worktree.py -v        # existing pass
uv run pytest tests/unit/test_worktree_multi.py -v  # new multi-repo tests pass
uv run mypy --strict src/harness_maker/worktree.py
```
New tests cover: create returns list; multi-path `.hm-loop-active`; pre-flight collision avoidance; stale-file sentinel detection → primary-only fallback.

**Risk:** medium  
**Rollback:** Phase 1 state.

---

### Phase 3 — `worktree_gate` multi-path ANY-match [DEFERRED to follow-up]

**Scope IN:** `src/harness_maker/gates/worktree_gate.py`

1. `_read_active_worktrees(project_root) -> list[Path]` — glob `.claude/.hm-loop-*`, read all matching files, split each on `\n`, collect all paths, filter empty/non-existent. Supports any number of parallel sessions simultaneously.
2. Gate: `any(target.is_relative_to(wt) for wt in active_wts)` → allow; else block.
3. Block message lists all active worktrees across all sessions.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_worktree_gate.py -v
```
Test cases: allow write in primary WT; allow write in sibling WT; block write outside both; backward-compat single-path marker.

**Risk:** low  
**Rollback:** Phase 2 state.

---

### Phase 4 — `worktree.finalize` fail-fast + marker retention [DEFERRED to follow-up]

**Scope IN:** `src/harness_maker/worktree.py` — `_cli_finalize`

**Algorithm:**
```python
# ADR-006: per-session marker file — primary wt basename → file name
marker_file = project_root / ".claude" / f".hm-loop-{primary_wt.name}"
all_wts = _read_paths_from_file(marker_file)   # reads only THIS session's file
succeeded, pending = [], list(all_wts)
for wt in all_wts:
    if not wt.is_dir():      # already cleaned in prior run — skip
        succeeded.append(wt); pending.remove(wt); continue
    try:
        captured = _capture_pending_in_worktree(wt)
        merge(wt, strategy=strategy, commit=auto_commit)
    except RuntimeError as e:
        print(f"[finalize] succeeded:{[str(s) for s in succeeded]}", file=sys.stderr)
        print(f"[finalize] failed:{[str(wt)]}", file=sys.stderr)
        print(f"[finalize] pending:{[str(p) for p in pending if p != wt]}", file=sys.stderr)
        print(f"[finalize] marker kept — re-run 'worktree finalize <WT> ...' after resolving conflict", file=sys.stderr)
        # DO NOT delete marker_file — gate stays active for this session
        return 1
    cleanup(wt, on_success=on_success)   # cleanup immediately after merge
    succeeded.append(wt); pending.remove(wt)
marker_file.unlink(missing_ok=True)   # delete only THIS session's file
return 0
```

**Exit criterion:**
```bash
uv run pytest tests/unit/test_worktree_multi.py -v
```
Specific cases:
- `test_finalize_all_success` → marker cleared, exit 0.
- `test_finalize_primary_ok_sibling_fail` → primary cleaned, sibling wt preserved, marker kept, exit 1, stderr has succeeded/failed/pending.
- `test_finalize_rerun_after_partial` → `wt.is_dir()` skip for primary, sibling retried.

**Risk:** medium  
**Rollback:** Phase 3 state.

---

### Phase 5 — `interview.py` sibling_repos question [DEFERRED to follow-up]

**Scope IN:** `src/harness_maker/interview.py`

1. Add question: "Sibling repos (part of this same logical project)? Enter relative paths, one per line. Leave empty to skip."
2. Validation: warn (not error) on missing dir or non-git dir — portability concern.
3. Reject absolute paths at input time (mirrors model validator).
4. `answers_from_harness_yaml`: read `sibling_repos` field.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_interview.py -v
uv run pytest tests/unit/test_interview_sibling.py -v   # new
```
`answers_from_harness_yaml` with `sibling_repos: ["../repo-b"]` → `InterviewAnswers.sibling_repos == ["../repo-b"]`.

**Risk:** low  
**Rollback:** Phase 4 state.

---

### Phase 6 — `synthesize.py` + `harness.yaml.j2` [DEFERRED to follow-up]

**Scope IN:** `src/harness_maker/synthesize.py`, `src/harness_maker/templates/harness-yaml/{Side,Production}.yaml.j2`

1. `synthesize.py`: pass `sibling_repos` through to `HarnessConfig`.
2. Templates: render `sibling_repos` list (empty → `sibling_repos: []`).

**Exit criterion:**
```bash
uv run pytest tests/unit/test_synthesize_snapshot.py -v   # snapshots updated
```

**Risk:** low  
**Rollback:** Phase 5 state.

---

### Phase 7 — `execute.md.j2` template update [DEFERRED to follow-up]

**Scope IN:** `src/harness_maker/templates/commands/hm/execute.md.j2`

**Changes:**
1. Add `SIBLING_WORKTREE_PATHS` sentinel string (plain text comment in template — survives render).
2. Update §0 worktree creation instructions:
   - "Line 1 = primary worktree path → use as `<WT>`"
   - "Lines 2+ = sibling worktree paths → use as `<WT-{slug}>` where slug is derived from the path's second-to-last component (e.g., `.../repo-b/.worktrees/...` → slug = `repo-b`)"
   - "Empty output → no isolation (unchanged)"
3. Finalize call at end of stage: unchanged (`finalize <WT> stage-only` — `_cli_finalize` auto-discovers siblings from `.hm-loop-active`).

**Exit criterion:**
```bash
uv run pytest tests/unit/test_render_execute.py -v   # snapshot-based
```
Two snapshot variants:
1. `sibling_repos=[]` → single-repo execute.md (no sibling instructions, sentinel present).
2. `sibling_repos=["../repo-b"]` → multi-repo execute.md (sibling instructions present).

**Risk:** medium  
**Rollback:** Phase 6 state.

---

### Phase 8 — `wrapup.md.j2` template update [DEFERRED to follow-up]

**Scope IN:** `src/harness_maker/templates/commands/hm/wrapup.md.j2`

Add sibling commit block:
```jinja2
{% if harness.sibling_repos %}
### Sibling repo commits

For each sibling repo, commit with the same message:
{% for sibling in harness.sibling_repos %}
```bash
# {{ sibling }}
(cd "$(git rev-parse --show-toplevel)/{{ sibling }}" && git add -A && git commit -m "$(cat <<'EOF'
{commit_message}
EOF
)")
```
If this commit fails: fix the conflict in `{{ sibling }}` and re-run the commit manually. The primary repo commit is NOT reverted.
{% endfor %}
{% endif %}
```

**Exit criterion:**
```bash
uv run pytest tests/unit/test_render_wrapup.py -v   # snapshot-based
```
Two variants: with/without `sibling_repos`.

**Risk:** low  
**Rollback:** Phase 7 state.

---

### Phase 9 — Full test suite + mypy + ruff [DEFERRED to follow-up]

**Scope IN:** `tests/`

New test files:
- `tests/unit/test_worktree_multi.py` — create/finalize/cleanup_all for 2-repo; uses `tmp_path` + `git init` subprocess.
- `tests/unit/test_worktree_gate.py` (extended) — multi-path marker cases.
- `tests/unit/test_interview_sibling.py` — sibling_repos Q + round-trip.
- `tests/unit/test_render_execute.py` — execute.md snapshot variants.
- `tests/unit/test_render_wrapup.py` — wrapup.md snapshot variants.

**Exit criterion:**
```bash
uv run pytest --tb=short            # all green
uv run mypy --strict src/           # 0 errors
uv run ruff check src/ tests/       # 0 errors
uv run ruff format --check src/ tests/
```

**Risk:** low  
**Rollback:** Phase 8 state.

---

## 🧪 Testing Strategy

### Unit tests (automated, per phase)

| Phase | File | Key scenarios |
|-------|------|---------------|
| 1 | `test_models.py` | relative path OK; absolute path raises ValueError |
| 2 | `test_worktree_multi.py` | create returns list; multi-path marker; pre-flight finds free suffix across both repos; stale sentinel → primary-only fallback |
| 3 | `test_worktree_gate.py` | allow primary; allow sibling; block outside; single-path backward-compat |
| 4 | `test_worktree_multi.py` | finalize all-success; primary-ok-sibling-fail (marker kept, exit 1); re-run skip (wt.is_dir() False) |
| 5 | `test_interview_sibling.py` | Q rendered; absolute path warning; `answers_from_harness_yaml` round-trip |
| 6 | `test_synthesize_snapshot.py` | `sibling_repos: []` in all snapshots |
| 7 | `test_render_execute.py` | sentinel present in both variants; sibling instructions in multi-repo variant |
| 8 | `test_render_wrapup.py` | sibling block present/absent per variant |

### Manual validation (post-Phase-9)

1. `harness-maker make` in repo-a with `sibling_repos: ["../repo-b"]` completes.
2. `worktree create execute $(pwd)` → 2 lines output.
3. Write to primary WT → gate allows; write to sibling WT → gate allows; write to main branch → gate blocks.
4. Simulate sibling merge failure → stderr shows succeeded/failed/pending, marker intact.
5. Re-run `finalize` → primary skipped, sibling retried.
6. Wrapup → commit in both repos.

---

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Stale execute.md (ADR-002 concern) | high | medium | Sentinel check in `_cli_create` → stderr warning + primary-only degradation (not silent failure) |
| Sibling branch-name collision (same repo slug) | low | medium | Pre-flight checks ALL repos; edge case of identical slugs → hash-based disambiguation in Phase 2 |
| `git worktree add` race (concurrent loop start) | very low | low | Existing retry-with-suffix logic extended to sibling creation; pre-flight is a best-effort heuristic |
| Partial finalize state on crash (no `finally`) | low | medium | `_cli_finalize` wraps in try/finally for `_clear_loop_marker` only on success; marker kept on exception |
| Wrapup sibling commit failure leaves repos inconsistent | low | medium | Fail-loud with manual retry hint; primary commit NOT reverted (consistent with ADR-003/004) |
| Sibling path not portable across machines | medium | low | Absolute paths rejected at model + interview time; relative paths survive with same directory structure |
| Backward-compat: old `.hm-loop-active` ignored by new gate (ADR-006) | low | low | Gate glob `.hm-loop-*` does not match `.hm-loop-active` — in-flight loops at upgrade time must finalize first; document in upgrade notes |
| `wrapup.md.j2` `$(git rev-parse --show-toplevel)` from inside subshell | low | medium | Test in Phase 8 snapshot; fallback to `$PWD` if `rev-parse` fails |

---

## ✅ Success Criteria

- [ ] `HarnessConfig(sibling_repos=["../repo-b"])` validates; absolute path raises `ValueError`
- [ ] `worktree create execute $(pwd)` with `sibling_repos: ["../repo-b"]` emits 2 lines
- [ ] With stale execute.md (no sentinel): emits 1 line + stderr warning
- [ ] `.hm-loop-active` contains both paths (newline-separated)
- [ ] `worktree_gate` allows write in primary WT, allows write in sibling WT, blocks write outside both
- [ ] `worktree finalize` all-success: marker cleared, exit 0
- [ ] `worktree finalize` primary-ok-sibling-fail: marker KEPT, stderr shows succeeded/failed/pending, exit 1
- [ ] Re-run `finalize` after partial failure: completed repo skipped, failed repo retried
- [ ] Wrapup commits primary and sibling repos sequentially
- [ ] Wrapup sibling failure: loud error + primary commit NOT reverted
- [ ] Two parallel sessions each create their own independent worktree (per-session marker files)
- [ ] Gate allows writes from BOTH sessions simultaneously (glob scan)
- [ ] Finalize deletes only its own session's marker — other sessions' markers untouched
- [ ] `.gitignore` contains `.claude/.hm-loop-*` (not the old `.claude/.hm-loop-active`)
- [ ] All existing single-repo tests pass (no regression)
- [ ] `ruff check` + `mypy --strict` + `pytest` all green

---

## 🔍 Plan Validation

**First pass:** MAJOR_REVISION (2 critical, 5 warnings, 1 suggestion)

**Resolutions:**

| Critique | Severity | Resolution |
|----------|----------|------------|
| Stale execute.md silent failure | critical | ADR-002 updated: sentinel check in `_cli_create` → stderr warning + primary-only degradation (Interview #2 revised) |
| Finalize clears marker on failure → gate disabled | critical | ADR-003 + ADR-005: marker KEPT until all success; `_clear_loop_marker` only on full success path (Interview V1) |
| Absolute paths not validated | warning | Phase 1: Pydantic `@field_validator` rejects absolute paths; ADR-001 updated (design decision) |
| Branch-name collision pre-flight | warning | Phase 2: `_find_free_suffix` pre-flights ALL repos before any create (design decision) |
| Phase 7 exit is manual only | warning | Phase 7 exit → snapshot tests `test_render_execute.py` with 2 variants (design decision) |
| No Non-Goals section | warning | Added `## 🚫 Non-Goals` section (design decision) |
| ADR-004 wrapup failure mode undocumented | warning | ADR-004 updated: fail-loud on sibling commit failure, primary NOT reverted (design decision) |
| Missed recovery interview round | suggestion | Interview V1 conducted; ADR-005 added (Interview V1) |
| Parallel session isolation | post-plan observation | ADR-006 added: per-session `.hm-loop-{wt-name}` files; Signal 1 removed from `_detect_existing_worktree`; gate scans glob |

**Final outcome:** NEEDS_REVISION_RESOLVED
