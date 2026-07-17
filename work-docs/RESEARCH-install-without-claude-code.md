---
type: research
task_slug: install-without-claude-code
status: complete
created: 2026-05-12
tags: [harness-maker, research, installation, cursor, codex, bootstrap, plugin]
mtime_warn_days: 14
libs_fetched: []
sources:
  - https://cursor.com/docs/plugins.md
  - https://developers.openai.com/codex/plugins/build
  - https://developers.openai.com/codex/plugins
  - https://docs.claude.com/en/docs/claude-code/plugins
  - https://medium.com/@v.tajzich/how-to-write-and-test-cursor-plugins-locally-the-part-the-docs-dont-tell-you-4eee705d7f76
  - https://github.com/cursor/plugin-template/issues/4
related_docs:
  - "[[PLAN-plugin-vs-generator-2026-05]]"
  - "[[RESEARCH-plugin-vs-generator-2026-05]]"
  - "[[RESEARCH-codex-target-support]]"
  - "[[RESEARCH-onboarding-ux-2026-05]]"
summary: "Cursor/Codex-first install is feasible today via local-plugin + CLI; needs docs + minor scaffolding"
---

## 🎯 Recommended Direction

Cursor-first와 Codex-first 사용자 모두 **오늘 당장** 설치 가능한 메커니즘이 이미 존재한다 — 다만 문서화되지 않았고, UX가 Claude Code 사용자 대비 열등하다. 권장 방향: (1) 세 IDE 모두 커버하는 **Getting Started 문서** 작성, (2) `pyproject.toml`에 `console_scripts` 추가로 `harness-maker make` CLI 직접 호출 가능하게, (3) Cursor/Codex 각각의 local plugin install 절차를 README + 별도 가이드로 문서화.

## 🔍 Refinement Decisions

Discovery lens: Technical architecture / implementation + User-workflow / product opportunity

## 🛠️ Approaches Found

### Approach A — Local plugin symlink + CLI (최소 변경)

| Field | Content |
|-------|---------|
| Approach | 현재 존재하는 메커니즘을 문서화만 하는 방향 |
| Assumption | 사용자가 git clone + uv 설치를 할 수 있다 |
| Evidence | Cursor: `~/.cursor/plugins/local/` 에 symlink하면 local plugin으로 인식 (Cursor 공식 docs 확인). Codex: `~/.agents/plugins/marketplace.json` 에 local entry 추가하면 인식 (Codex 공식 docs 확인). CLI: `uv run python -m harness_maker.cli make <project>` 는 IDE 없이도 동작 (e2e 테스트 확인) |
| Trade-off | 변경 비용 최소. 하지만 사용자 경험이 Claude Code 대비 열등 (3~5단계 수동 작업 필요) |
| Compatibility | 현재 코드 변경 없음 |
| Risk | low |

**Cursor-first 구체적 절차 (현재 가능):**
1. `git clone` + `uv pip install -e ./harness-maker`
2. `ln -s /path/to/harness-maker ~/.cursor/plugins/local/harness-maker`
3. Cursor 재시작 (또는 Developer: Reload Window)
4. Cursor에서 `/harness-maker:make` 실행 가능 — `commands/make.md`가 로드됨
5. 단, `commands/make.md`의 `installed_plugins.json` 해석 로직이 Claude Code 전용이므로, `$plugin_dir` 해석에서 실패할 수 있음

**Codex-first 구체적 절차 (현재 가능):**
1. `git clone` + `uv pip install -e ./harness-maker`
2. `~/.agents/plugins/marketplace.json` 에 harness-maker entry 추가
3. 또는 `codex plugin marketplace add ./path/to/harness-maker` (local marketplace)
4. Codex 재시작 → plugin directory에서 설치
5. `commands/make.md`의 `installed_plugins.json` 로직은 Claude Code 전용 — Codex에서는 `uv run python -m harness_maker.cli make "$(pwd)"` 직접 호출이 현실적

**부트스트랩 문제:**
- Claude Code: 없음. `claude --plugin-dir` → `/harness-maker:make` → harness 생성.
- Cursor: 부분적. local plugin 로드 후 `/harness-maker:make` 실행은 가능하나, `commands/make.md` 내부에서 `installed_plugins.json` (Claude Code 전용 경로)를 읽어 `$plugin_dir`를 resolve하는 로직이 Cursor에서 작동하지 않음. **`/hm:make`는 harness가 이미 존재해야 사용 가능** (templates에서 렌더됨).
- Codex: 동일. `commands/make.md`의 plugin_dir resolve가 Claude Code 전용.

### Approach B — `console_scripts` + IDE-agnostic CLI bootstrap (중간 변경)

| Field | Content |
|-------|---------|
| Approach | `pyproject.toml`에 `[project.scripts]` 추가 → `harness-maker` CLI 명령 노출. 설치 후 어느 IDE에서든 `harness-maker make .` 으로 부트스트랩 가능 |
| Assumption | 사용자가 `uv tool install` 또는 `pip install` 할 수 있다 |
| Evidence | 현재 `pyproject.toml`에 `[project.scripts]` 없음. `cli.py`의 `make` 명령은 IDE 없이도 완전 동작 (e2e 테스트가 `python -m harness_maker.cli make` 패턴으로 검증). PyPI publish가 roadmap에 있음 |
| Trade-off | PyPI publish 전에도 `uv tool install ./harness-maker` 로 로컬 설치 가능. CLI first-class 시민이 되면 어느 IDE에서든 부트스트랩 통일 |
| Compatibility | 기존 플로우 깨지지 않음 (additive) |
| Risk | low |

구체적 변경:
```toml
[project.scripts]
harness-maker = "harness_maker.cli:main"
```

설치 플로우:
```bash
# git clone 후
uv tool install ./harness-maker
# 또는
pip install -e ./harness-maker

# 어느 IDE에서든
cd your-project
harness-maker make .
```

### Approach C — IDE-specific `/add-plugin` 등록 (Marketplace listing, 큰 변경)

| Field | Content |
|-------|---------|
| Approach | 각 Marketplace에 정식 등록하여 `/add-plugin harness-maker` (Cursor) 또는 plugin directory (Codex) 에서 원클릭 설치 |
| Assumption | Marketplace 리뷰 프로세스 통과 가능. 오픈소스 요건 충족 (현재 private repo) |
| Evidence | Cursor Marketplace: 2026-02 출시, 수동 리뷰 필수, 오픈소스 필수. Codex: "official public plugins — coming soon" (아직 self-serve publish 없음) |
| Trade-off | 최고의 UX. 하지만 (1) repo를 public으로 전환해야 함, (2) Cursor 팀 리뷰 대기, (3) Codex는 아직 public plugin publish가 불가능 |
| Compatibility | 완전 호환 (additive) |
| Risk | medium — 외부 의존 (리뷰 프로세스, public 전환 결정) |

## ⚠️ Pitfalls

1. **`commands/make.md`의 `installed_plugins.json` resolve가 Claude Code 전용**: `~/.claude/plugins/installed_plugins.json` 읽기 → Cursor/Codex에는 이 파일 없음. Cursor/Codex에서 `/harness-maker:make` 실행 시 `$plugin_dir` resolve 실패. 이것이 가장 큰 실질적 blocker.

2. **`/add-plugin`은 Marketplace 등록 후에만 작동**: Cursor의 `/add-plugin` 명령은 local path나 GitHub URL을 받지 않음. Marketplace에 등록되지 않은 플러그인은 `~/.cursor/plugins/local/` 수동 배치만 가능.

3. **Codex official plugin directory는 아직 self-serve publish 불가**: "Adding plugins to the official Plugin Directory is coming soon" (공식 docs 원문). Local marketplace는 가능하나 one-click 배포는 불가.

4. **Cursor에서의 AskUserQuestion 호환성**: `commands/make.md`는 `AskUserQuestion()` 으로 인터뷰를 진행하는데, 이는 Claude Code 전용 API. Cursor에서는 agent가 직접 질문하는 형태로 동작할 수 있으나, 정확한 동작 방식이 검증되지 않았음.

5. **`uv run --directory "$plugin_dir"`**: make 명령이 plugin 소스 디렉토리에서 Python 모듈을 실행하는 패턴. Cursor/Codex local plugin의 경우 경로가 다름 (`~/.cursor/plugins/local/harness-maker` vs `~/.claude/plugins/cache/...`).

## ❓ Open Questions

1. **`commands/make.md`를 IDE-agnostic하게 만들 것인가, 아니면 IDE별 분기를 넣을 것인가?** `installed_plugins.json` resolve 로직이 핵심 blocker. 옵션: (a) IDE 감지 후 분기, (b) CLI fallback으로 `uv run --with harness-maker python -m harness_maker.cli make ...` 패턴 통일, (c) IDE별 `commands/make.md` 렌더.

2. **Cursor local plugin에서 `commands/make.md`가 정상 로드되는지 검증 필요.** `.cursor-plugin/plugin.json`의 `"commands": "./commands"` 가 local plugin에서도 인식되는지 — 경로 해석이 symlink를 따르는지.

3. **PyPI publish 시점은?** `console_scripts` 추가는 PyPI 전에도 가능 (`uv tool install`로 로컬 설치). 하지만 `uv tool install git+https://github.com/Ecro/harness-maker.git` 같은 원격 설치는 repo가 public이어야 가능.

4. **Codex에서 `/harness-maker:make`를 어떻게 호출하나?** Codex의 commands 디스커버리가 `.codex-plugin/plugin.json`을 읽는지, 아니면 `AGENTS.md` / `.agents/skills/`만 읽는지 확인 필요. Codex 공식 docs의 plugin manifest에는 `"skills"` 키만 있고 `"commands"` 키는 없음 — commands는 Codex에서 지원되지 않을 수 있음.

5. **Private repo 상태에서 Cursor Marketplace 등록이 가능한가?** Cursor Marketplace는 "every plugin is open source and manually reviewed" — public 전환 없이는 등록 불가.

## 📚 Sources

- Cursor Plugin Docs: https://cursor.com/docs/plugins.md — local test via `~/.cursor/plugins/local/`, `/add-plugin`은 marketplace only
- Codex Plugin Build Docs: https://developers.openai.com/codex/plugins/build — local marketplace via `marketplace.json`, `codex plugin marketplace add ./path`
- Codex Plugin Docs: https://developers.openai.com/codex/plugins — `/plugins` command, install flow
- Claude Code Plugin Docs: https://docs.claude.com/en/docs/claude-code/plugins — `--plugin-dir`, `plugin.json` manifest
- Cursor local plugin dev: https://medium.com/@v.tajzich/how-to-write-and-test-cursor-plugins-locally — `~/.cursor/plugins/local/` 확인
- Cursor plugin-template issues: https://github.com/cursor/plugin-template/issues/4 — local testing confirmed

## 🔗 Related Internal Docs

- [[PLAN-plugin-vs-generator-2026-05]] — generator vs runtime plugin 결정 (결론: generator 유지)
- [[RESEARCH-plugin-vs-generator-2026-05]] — 위 PLAN의 research
- [[RESEARCH-codex-target-support]] — Codex target 추가 시 아키텍처 결정
- [[RESEARCH-onboarding-ux-2026-05]] — 온보딩 UX 개선 research
