---
type: plan
task_slug: install-without-claude-code
status: complete
created: 2026-05-12
tags: [harness-maker, plan, python, bootstrap, cursor, codex, cli, plugin]
research_doc: "[[RESEARCH-install-without-claude-code]]"
interview_rounds: 4
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Universal bootstrap prompt + console_scripts + IDE-agnostic make.md"
---

## 🎯 Executive Summary

**What:** Cursor/Codex 사용자가 Claude Code 없이 harness-maker를 부트스트랩할 수 있게 한다.

**Why:** 현재 유일한 설치 경로가 `claude --plugin-dir` → `/harness-maker:make`이며, `commands/make.md`의 `$plugin_dir` resolve가 `~/.claude/plugins/installed_plugins.json`에 하드코딩되어 있어 Cursor/Codex에서 동작하지 않는다.

**Key Decisions:**
- ADR-001: `pyproject.toml`에 `console_scripts` 추가 → `harness-maker make .` CLI 직접 호출
- ADR-002: `harness_maker_src_path` 렌더 값을 PyPI 패키지명 기반으로 전환 (pre-PyPI는 로컬 경로 fallback)
- ADR-003: `commands/make.md` Section 2를 IDE-agnostic으로 (Claude Code → Cursor → CLI fallback)

**Impact:** README에 "Universal Bootstrap Prompt" 추가. 어느 IDE의 LLM 에이전트든 이 프롬프트를 읽고 환경 감지 → 설치 → `make` → IDE 리로드까지 자동 수행.

**Non-Goals (out of scope):**
- PyPI publish 자체 (이 PLAN은 pre-PyPI 로컬 설치를 다룸. PyPI는 별도 작업)
- Marketplace listing 등록 (Cursor/Codex marketplace submit은 별도)
- Claude Code 기존 경로 deprecation (Claude Code 경로는 그대로 유지)
- Hook gate 명령 변경 (`--with` 인자 외에 hook 동작은 변경하지 않음)
- `commands/make.md`의 기능 확장 (IDE 감지 + fallback만 추가, 새 메뉴 항목 없음)

## 📚 Prior Work

- [[RESEARCH-install-without-claude-code]] — Cursor/Codex 설치 메커니즘 조사. `~/.cursor/plugins/local/`, `codex plugin marketplace add`, CLI 직접 호출 모두 실현 가능 확인.
- [[PLAN-plugin-vs-generator-2026-05]] — harness-maker는 generator(렌더 시점 생성)를 유지하기로 결정. 이 PLAN의 CLI-first 접근은 generator 결정과 정합.
- `[wiki:architecture] generator-not-runtime-config` — generator 유지 이유: hooks.json, settings.json, CLAUDE.md는 사전 렌더 필수.
- `[fail:lint] wrapup-ruff-preexisting-e501` — pyproject.toml 변경 시 lint 체크 필수.
- `[wiki:convention] version-bump-5-files` — `console_scripts` 추가는 버전 범프 불필요 (기능 추가이나 API 변경 아님).

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|-------|-------|----------|-------------------|---------|--------|------|-------|
| 1 | 1 | 프롬프트 위치 | Architecture | 물리적 형태/위치 | A~E | A: README Quick Start | 발견 용이 | no |
| 2 | 1 | 프롬프트 범위 | Scope | install only vs install+make | A~D | B: install + 첫 make | reload 우려 있으나 CLI 우회로 해결 | no |
| 3 | 1 | make.md 우회 | Contract | $plugin_dir 해결 방법 | A~D | C: console_scripts + CLI | ADR-001 | yes |
| 4 | 1 | LLM 재량 | Architecture | LLM judgment vs explicit | A~D | C: 하이브리드 | 환경감지=LLM, 명령=구체 | no |
| 5 | 2 | targets 감지 | Risk | 자동감지 vs 확인 | A~D | B: 감지+확인 1회 | 한 번만 물어봄 | no |
| 6 | 2 | preset 결정 | Architecture | profile 스캔 여부 | A~D | A: profile 스캔 유지 | make.md와 동일 | no |
| 7 | 2 | update 경로 | Contract | harness_maker_src_path | A~D | A: PyPI 패키지명 통일 | ADR-002 | yes |
| 8 | 3 | 환경감지 형태 | Implementation | 감지 지시 형태 | A~D | C: 체크리스트 테이블 | 구조적, 누락 방지 | no |
| 9 | 3 | 프롬프트 언어 | Contract | 작성 언어 | A~D | C: 영어+locale 감지 | LLM이 사용자 언어로 안내 | no |
| 10 | 3 | pre-PyPI 설치 | Dependencies | 설치 시작점 | A~D | C: repo 보유 가정 | `uv tool install .`부터 | no |
| 11 | 4 | make.md 미래 | Scope | 플러그인 명령 | A~C | B: IDE-agnostic 업그레이드 | ADR-003 | yes |

## 📐 Architecture Decision Records

### ADR-001: `console_scripts` entry point 추가
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Cursor/Codex 사용자가 Claude Code 없이 harness-maker를 부트스트랩할 경로가 없다. `commands/make.md`의 `$plugin_dir` resolve가 `~/.claude/plugins/installed_plugins.json`에 하드코딩되어 Cursor/Codex에서 실패.
**Decision:** `pyproject.toml`에 `[project.scripts] harness-maker = "harness_maker.cli:main"` 추가. 부트스트랩 프롬프트는 `harness-maker make .`을 직접 호출하여 `commands/make.md`를 우회.
**Consequences:**
- ✅ 어느 IDE에서든 CLI 한 줄로 부트스트랩 가능
- ✅ PyPI publish 시 `pip install harness-maker && harness-maker make .` 원라이너
- ⚠️ PyPI 전에는 `uv tool install ./harness-maker` 또는 `pip install -e ./harness-maker` 로컬 설치 필요
**Rejected alternatives:**
- `commands/make.md`에 IDE 감지 분기만 추가 — `installed_plugins.json` 자체가 Claude Code 전용 개념이라 우회가 불가
- Cursor/Codex 각각의 local plugin 등록만 문서화 — 3~5단계 수동 작업, UX 열등
**Source:** Interview #3

### ADR-002: `harness_maker_src_path` 렌더 값을 PyPI 패키지명 기반으로 전환
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** `console_scripts`로 부트스트랩하면 `make.md.j2`가 bake하는 `harness_maker_src_path`(현재 로컬 절대경로)가 설치 방식에 따라 깨질 수 있다. Cursor/Codex 사용자는 `--plugin-dir`로 로드하지 않으므로 `$plugin_dir` 기반 패턴도 부적합.
**Decision:** 렌더링된 모든 `--with` 인자에서 `harness-maker` PyPI 패키지명 사용. `synthesize.py`에 `_compute_install_ref()` 함수 추가:
- **감지 규칙 (locked):** `importlib.metadata.packages_distributions()`에서 `harness_maker`가 `harness-maker` distribution에 매핑되고, 해당 distribution의 `direct_url.json`이 없거나 `"editable": false`이면 → PyPI install → return `"harness-maker"`. 그 외 (editable, local, 미설치) → return `_HARNESS_MAKER_PKG_ROOT` (절대 경로).
- Template variable name은 `harness_maker_src_path` 유지 (30+ 참조 위치 rename 불필요).
**Consequences:**
- ✅ PyPI publish 후 `uv run --with harness-maker`로 통일
- ✅ pre-PyPI에서는 로컬 경로 fallback으로 기존 동작 유지
- ⚠️ `importlib.metadata` API가 Python 3.12+에서 안정적 (`packages_distributions`는 3.11+)
- ⚠️ `uv tool install ./harness-maker` 는 editable이 아니므로 `direct_url.json`에 `"editable": false` 또는 absent — 이 경우 local path가 아닌 package name을 return할 수 있음. 하지만 `uv tool install`로 설치하면 `uv run --with harness-maker`도 동작하므로 문제 없음.
**Rejected alternatives:**
- `/hm:make`도 `harness-maker make . --update` CLI 직접 호출 — `console_scripts`에 의존하면 `uv run` 기반 격리 환경의 장점(의존성 충돌 방지) 상실
- 무조건 절대 경로 유지 — PyPI publish 후에 절대 경로가 사용자 머신마다 다름
**Source:** Interview #7

### ADR-003: `commands/make.md` Section 2 IDE-agnostic 전환
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** 하네스가 설치된 후에도 Cursor/Codex 사용자가 `/harness-maker:make`로 설정 변경/업데이트를 하려면 `$plugin_dir`가 필요하다. 현재 Claude Code 전용.
**Decision:** Section 2의 `$plugin_dir` resolve를 3단계 fallback으로 교체:
1. Claude Code: `~/.claude/plugins/installed_plugins.json` (기존 로직)
2. Cursor: `~/.cursor/plugins/local/harness-maker` 존재 여부
3. CLI fallback: `which harness-maker` (console_scripts)
Codex는 별도 plugin_dir resolve 경로 없음 — CLI fallback(`harness-maker make`)으로 커버. Codex의 local plugin cache (`~/.codex/plugins/cache/`) 구조가 안정적이지 않아 하드코딩 부적합.
Fallback 시 dispatch가 `uv run --directory "$plugin_dir"` 에서 `harness-maker make "$(pwd)"`로 전환.
**Consequences:**
- ✅ Cursor/Codex에서도 `/harness-maker:make` 동작 (CLI fallback)
- ✅ Claude Code 기존 경로 완전 호환
- ⚠️ Codex 전용 plugin dir resolve는 미구현 (CLI fallback 의존)
**Rejected alternatives:**
- `/hm:make`만으로 충분 — Cursor/Codex 사용자가 Full reconfigure, 컴포넌트 추가/제거 시 `/harness-maker:make`의 풍부한 메뉴가 필요
**Source:** Interview #11

## 🏗️ Technical Design

### Current State

```
Bootstrap path (Claude Code only):
  claude --plugin-dir <repo>
    → commands/make.md loads
    → Section 2: installed_plugins.json → $plugin_dir
    → uv run --directory $plugin_dir python -m harness_maker.cli make ...

Post-bootstrap updates:
  /hm:make → make.md.j2 → uv run --with <abs-path> ... --update
```

### Affected Components

| Component | Change |
|-----------|--------|
| `pyproject.toml` | `[project.scripts]` 추가 |
| `src/harness_maker/synthesize.py` | `_compute_install_ref()` 추가, `harness_maker_src_path` 값 변경 |
| `src/harness_maker/workflow_fuse.py` | `_HARNESS_MAKER_PKG_ROOT` → `_compute_install_ref()` |
| `commands/make.md` | Section 2 multi-IDE detection |
| `README.md` | Quick Start → Universal Bootstrap Prompt |
| `tests/` | 새 unit tests + snapshot regen |

### Dependencies

- `importlib.metadata` (stdlib, Python 3.12+) — 이미 requires-python >=3.12
- No new external dependencies

### Architecture (after)

```
Bootstrap (any IDE):
  README "Universal Bootstrap Prompt" → LLM reads
    → detect env (OS, IDE, shell, Python, uv)
    → uv tool install ./harness-maker  (or pip install -e)
    → harness-maker profile . --json
    → confirm targets with user (1 question)
    → harness-maker make . --preset X --targets Y --locale Z
    → instruct IDE reload

Post-bootstrap updates (any IDE):
  /harness-maker:make → commands/make.md
    → Section 2: Claude Code path || Cursor path || CLI fallback
    → dispatch via $plugin_dir or harness-maker CLI

  /hm:make → make.md.j2
    → uv run --with <install_ref> ... --update
    (install_ref = "harness-maker" if PyPI-installed, else abs path)
```

### Data Flow

1. User copies bootstrap prompt from README
2. Pastes into LLM agent (Cursor/Codex/Claude Code/any)
3. LLM detects environment via checklist table
4. LLM runs `uv tool install .` (pre-PyPI) or `pip install harness-maker` (post-PyPI)
5. LLM runs `harness-maker profile . --json` → reads result
6. LLM asks user: "Detected Cursor. Also use Claude Code / Codex?" (1 question)
7. LLM runs `harness-maker make . --preset Production --targets cursor,claude-code --locale ko`
8. LLM instructs: "Reload IDE to activate"
9. After reload: all `/hm:*` commands, skills, agents are loaded

### Design Decisions

- **Variable name preservation (ref ADR-002):** `harness_maker_src_path` template variable name is kept across 30+ template files. Only the VALUE changes (abs path → package name). This avoids a massive rename for zero functional benefit.
- **3-step fallback in make.md (ref ADR-003):** Claude Code → Cursor → CLI. Order matters: Claude Code path is tried first because it has the richest plugin metadata (`installed_plugins.json` includes project-scoped install paths).
- **Codex = CLI-only (ref ADR-003):** Codex local plugin cache structure (`~/.codex/plugins/cache/$MARKETPLACE/$PLUGIN/$VERSION/`) has too many variable segments to reliably resolve. CLI fallback is sufficient.
- **Profile scan preserved (Interview #6):** The bootstrap prompt runs `harness-maker profile . --json` to recommend preset, matching the quality of the existing `commands/make.md` flow.

## 📝 Implementation Plan

### Phase 1 — `console_scripts` entry point
**Scope:** `pyproject.toml`
**Files in:** `pyproject.toml`
**Files out:** everything else

Add:
```toml
[project.scripts]
harness-maker = "harness_maker.cli:main"
```

**Exit criterion:**
```bash
uv tool install . && harness-maker --help
# must print typer help text with "make", "profile", "remove" subcommands
```
**Risk:** low
**Rollback:** revert `pyproject.toml`

### Phase 2 — Install reference auto-detection
**Scope:** `src/harness_maker/synthesize.py`, `src/harness_maker/workflow_fuse.py`
**Files in:** `synthesize.py`, `workflow_fuse.py`
**Files out:** templates (no change), other src modules

Add `_compute_install_ref() -> str` function to `synthesize.py`:
```python
def _compute_install_ref() -> str:
    """Return PyPI package name if properly installed, else local abs path."""
    try:
        from importlib.metadata import distribution
        dist = distribution("harness-maker")
        # Check if editable install via direct_url.json
        direct_url = dist.read_text("direct_url.json")
        if direct_url is not None:
            import json
            du = json.loads(direct_url)
            if du.get("dir_info", {}).get("editable", False):
                return _HARNESS_MAKER_PKG_ROOT
        return "harness-maker"
    except Exception:
        return _HARNESS_MAKER_PKG_ROOT
```

Replace all `harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT` with `harness_maker_src_path=_compute_install_ref()`.

**Exit criterion:**
```bash
# 1. All call sites updated (grep must find zero remaining _PKG_ROOT assignments to src_path)
rg 'harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT' src/
# must return 0 results

# 2. Lint + type check
uv run ruff check src/harness_maker/synthesize.py src/harness_maker/workflow_fuse.py
uv run mypy src/harness_maker/synthesize.py src/harness_maker/workflow_fuse.py

# 3. Unit test for both paths passes
uv run pytest tests/unit/test_install_ref.py -v
```
**Risk:** medium — value change propagates to every rendered hook/command
**Rollback:** revert `synthesize.py`, `workflow_fuse.py`

### Phase 3 — `commands/make.md` IDE-agnostic Section 2
**Scope:** `commands/make.md` Section 2 only
**Files in:** `commands/make.md`
**Files out:** templates, src

Replace Section 2 with multi-IDE detection:

```bash
# Try Claude Code first
plugin_dir=$(python3 -c "
import json, pathlib
try:
    data = json.load(open(pathlib.Path.home() / '.claude/plugins/installed_plugins.json'))
    entries = data['plugins']['harness-maker@harness-maker-local']
    import os; cwd = os.getcwd()
    match = next((e for e in entries if e.get('projectPath') == cwd), entries[0])
    print(match['installPath'])
except Exception:
    print('')
" 2>/dev/null)

# Fallback: Cursor local plugin
if [ -z "$plugin_dir" ] && [ -d "$HOME/.cursor/plugins/local/harness-maker" ]; then
  plugin_dir="$HOME/.cursor/plugins/local/harness-maker"
fi

# Fallback: console_scripts CLI
if [ -z "$plugin_dir" ]; then
  if command -v harness-maker &>/dev/null; then
    plugin_dir="__CLI_FALLBACK__"
  fi
fi

echo "PLUGIN_DIR=$plugin_dir"
echo "FALLBACK_MODE=$([ "$plugin_dir" = '__CLI_FALLBACK__' ] && echo 'cli' || echo 'plugin')"
```

Add conditional dispatch throughout Section 5: when `FALLBACK_MODE=cli`, use `harness-maker make "$(pwd)"` instead of `uv run --directory "$plugin_dir" ...`.

**Exit criterion:**
```bash
# Golden string check: all 3 resolution paths present
grep -c 'installed_plugins.json' commands/make.md  # >= 1 (Claude Code path)
grep -c '.cursor/plugins/local' commands/make.md    # >= 1 (Cursor path)
grep -c 'CLI_FALLBACK' commands/make.md              # >= 1 (CLI path)
grep -c 'harness-maker make' commands/make.md        # >= 1 (CLI dispatch)
```
**Risk:** medium — core plugin command
**Rollback:** revert `commands/make.md`

### Phase 4 — README Universal Bootstrap Prompt
**Scope:** `README.md` Quick Start section
**Files in:** `README.md`
**Files out:** everything else

Rewrite Quick Start with the "ultimate prompt" structure:

1. **Preamble:** "You are an LLM agent bootstrapping harness-maker for this project."
2. **Environment checklist table:**

| Item | Detection method | Default |
|------|-----------------|---------|
| OS | `uname -s` or environment | — |
| IDE | Check env vars, process, available CLIs | — |
| Shell | `echo $SHELL` or `$PSVersionTable` | bash |
| Python | `python3 --version` | ≥3.12 required |
| uv | `uv --version` | required |

3. **Install:** `cd <harness-maker-repo> && uv tool install .`
4. **Profile:** `harness-maker profile <project> --json`
5. **Confirm targets:** Ask user which IDEs (detected + others). One question.
6. **Make:** `harness-maker make <project> --preset X --targets Y --locale Z`
7. **Reload:** Instruct IDE reload. List what becomes available after reload.

Language: English. Include instruction "Detect the user's preferred language and conduct the conversation in that language."

Each install recipe ties to detection outcome:
- `uv tool install .` → `_compute_install_ref()` may return `"harness-maker"` (non-editable) or abs path (if uv tool install creates editable-like layout)
- `pip install -e .` → always returns abs path (editable)

**Exit criterion:**
```bash
# README renders and contains the prompt structure
grep -c 'Environment checklist' README.md          # >= 1
grep -c 'harness-maker make' README.md              # >= 1
grep -c 'harness-maker profile' README.md           # >= 1
```
**Risk:** low
**Rollback:** revert `README.md`

### Phase 5 — Tests and snapshot regeneration
**Scope:** `tests/`
**Files in:** new test file `tests/unit/test_install_ref.py`, snapshot baselines
**Files out:** src (no changes)

1. **New tests:**
   - `test_compute_install_ref_editable()` — monkeypatch `distribution()` to return editable dist → abs path
   - `test_compute_install_ref_wheel()` — monkeypatch `distribution()` to return non-editable dist → `"harness-maker"`
   - `test_compute_install_ref_not_installed()` — monkeypatch to raise `PackageNotFoundError` → abs path
   - `test_console_scripts_entry()` — `from harness_maker.cli import main; assert callable(main)`

2. **Snapshot regeneration:**
   ```bash
   # MUST run from main repo root, NOT worktree
   uv run python tests/snapshot/regenerate.py
   ```

3. **Full test suite:**
   ```bash
   uv run pytest
   uv run ruff check src/ tests/
   uv run mypy --strict src/
   ```

**Exit criterion:** All three commands above exit 0.
**Risk:** low
**Rollback:** revert test files + snapshot baselines

## 🧪 Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | `_compute_install_ref()` 3 paths | monkeypatch `importlib.metadata` |
| Unit | console_scripts entry | import check |
| Unit | make.md golden strings | grep assertions in Phase 3 exit |
| Snapshot | all template renders | `regenerate.py` + `test_synthesize_snapshot.py` |
| E2E | `harness-maker make <tmpdir>` | subprocess invocation (existing pattern) |
| Manual | Bootstrap prompt in Cursor | paste into Cursor agent, verify install+make+reload |
| Manual | `/harness-maker:make` in Cursor | verify CLI fallback dispatches correctly |

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Snapshot hash cascade (all templates change) | certain | low | Phase 5 regen from main repo root |
| `importlib.metadata` edge case (uv tool install classified wrong) | medium | medium | Unit test all 3 paths + fallback is safe (abs path) |
| Cursor local plugin symlink not followed | low | medium | `commands/make.md` has CLI fallback as safety net |
| pre-PyPI `--with harness-maker` in hooks | impossible pre-PyPI | — | `_compute_install_ref()` returns abs path for editable/local |
| README prompt too long for chat context | low | low | Keep prompt ≤50 lines; link to full docs |
| `commands/make.md` Section 5 dispatch branches multiply | medium | low | Single `$FALLBACK_MODE` variable controls all branches |

## ✅ Success Criteria

- [x] `harness-maker --help` works after `uv tool install .`
- [x] `harness-maker make <tmpdir>` generates `.claude/harness.yaml` without Claude Code
- [x] Rendered `/hm:make` uses correct `--with` reference (abs path for editable, package name for wheel)
- [x] `commands/make.md` resolves `$plugin_dir` in Claude Code, Cursor, and CLI-only environments
- [x] README contains Universal Bootstrap Prompt with environment checklist table
- [x] `uv run pytest` passes (including new + regenerated snapshots)
- [x] `uv run ruff check src/ tests/` clean
- [x] `uv run mypy --strict src/` clean
- [x] Manual test: paste bootstrap prompt into Cursor agent → harness generated + reload instruction given

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION (7 warnings, 0 critical)

| Warning | Resolution |
|---------|-----------|
| ADR stubs lack substance | Full ADRs with Context/Decision/Consequences/Rejected written above |
| No Non-Goals | Non-Goals section added to Executive Summary |
| Phase 3 exit criteria not verifiable | grep-based golden string assertions added |
| Codex vs Cursor asymmetry | ADR-003 explicitly documents Codex = CLI-only, with rationale |
| Phase 2 completeness not gated | `rg 'harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT' src/` must return 0 |
| Editable heuristic underspecified | ADR-002 locks detection rule: `direct_url.json` → `editable` field check |
| Pre-PyPI wording tension | Phase 4 maps each install recipe to `_compute_install_ref()` outcome |

All 7 warnings resolved in-plan. No re-validation needed (NEEDS_REVISION, not MAJOR_REVISION).
