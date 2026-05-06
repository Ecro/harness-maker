# PLAN: Cursor target 지원 (harness-maker)

> **Status**: draft (Phase 0/1 완료 후 myplan 단계로 갱신)
> **Created**: 2026-05-06
> **Slug**: cursor-target-support
> **Goal**: harness-maker 가 Claude Code 전용에서 벗어나 Cursor IDE 도 지원. 사용자가 `claude-code` / `cursor` / 둘 다 중 선택하여 그에 맞는 하네스를 렌더받을 수 있게 한다. harness-maker 자체도 Cursor Marketplace 에 publish.

---

## 0. 배경 한 줄

Cursor 2.4+ (2026-03~) 가 Claude Code 의 거의 모든 기능을 dual-write 호환 형태로 지원 (subagents, skills, hooks, commands, rules, MCP, Plan Mode, plugin marketplace). 즉 single source 로 양쪽 IDE 동작이 가능. 사용자는 IDE 선택의 자유를 갖고, 우리는 80% 자산을 single source 로 유지하면서 Cursor 전용 자산 (rules, commands 위치) 만 추가 렌더하면 됨.

---

## 1. Locked 결정

### 1.1 Architecture

- **새 축 `targets`**: `harness.yaml.targets: list[Target]` — `claude-code` | `cursor` multi-select. preset / dev_mode 와 직교.
- **인터뷰 정책**: 명시 multi-select 강제. **auto-detect 금지** (`.cursor/` 디렉토리 존재 여부 등으로 추론하지 않음). default fallback 은 옛 harness.yaml 에 키 없을 때만 `[claude-code]` + 경고 로그.
- **Single source 원칙**: agents / skills / hooks / MCP 자산은 `.claude/` 한 곳. Cursor IDE 가 native 로 읽음 (단, hooks 의 IDE 인식은 Phase 1 검증 미션).
- **Cursor 추가 자산**: `.cursor/rules/*.mdc`, `.cursor/commands/hm-*.md`, `.cursor/mcp.json` (필요 시).
- **harness-maker 자체 = dual plugin**: `.claude-plugin/plugin.json` + `.cursor-plugin/plugin.json` 동시 관리. 1차 릴리스부터.
- **버전 sync = 4 파일** (3 → 4 확장):
  | 파일 | 역할 |
  |------|------|
  | `.claude-plugin/plugin.json` | Claude Code `/plugin update` 기준 |
  | `.cursor-plugin/plugin.json` | Cursor Marketplace 기준 |
  | `pyproject.toml` | Python 패키지 |
  | `src/harness_maker/__init__.py` | 런타임 `__version__` |

### 1.2 harness.yaml 새 키

```yaml
targets:                # multi-select; 인터뷰 강제
  - claude-code
  # - cursor
recommended_model: claude-opus-4-7   # Cursor user 도 Anthropic 모델 권장
```

### 1.3 Cursor 사용자 모델 정책

- harness.yaml `recommended_model` + agent frontmatter `model` 에 명시. user override 자유.
- **prompt 자체는 model-agnostic 재작성 안 함** — 너무 큰 작업, 비용 대비 효용 낮음. `<thinking>` blocks 등 Claude-specific 표현 그대로.
- onboarding 문서에 "Anthropic 모델 권장" 명시.

### 1.4 Worktree 공유

- `.worktrees/` 단일 공유. Cursor 의 `/worktree` 자체 관리와 같은 디렉토리 사용.
- cleanup 은 prefix 매치로 자기 것만 (`phase-*`, `autoloop-*`). Cursor 가 만든 worktree 는 건드리지 않음.
- `.gitignore` 의 `.worktrees/` 한 줄로 양쪽 다 커버.

### 1.5 Rules 분할 정책 (Cursor target 시)

- CLAUDE.md → `.cursor/rules/*.mdc` 4–6개 도메인별 분할 (확정).
- **단계 분리**: 1차 릴리스에서는 **단일 `harness.mdc` (alwaysApply: true)** 로 시작, CLAUDE.md 그대로 .mdc 변환. 분할은 2차에서 사용자 피드백 반영 후. (review 결과 반영, C1)
- 2차 분할 후보: `autoloop.mdc` (alwaysApply: true), `code-style.mdc` (globs: `**/*.py`), `security.mdc` (alwaysApply: true), `workflow.mdc` (description 기반 auto-attach), `context-rules.mdc`.

### 1.6 Plugin 분배

- 1차 릴리스: `.cursor-plugin/plugin.json` 추가만.
- 2차: Cursor Marketplace 에 publish (`cursor.com/marketplace/publish`).

---

## 2. Capability matrix (정정 후, 2026-04 기준)

| Claude Code 자산 | Cursor 처리 | 우리 렌더 위치 |
|-|-|-|
| `.claude/agents/*.md` | Cursor 가 native 로 읽음 (project subagents 우선순위) | single source `.claude/agents/` |
| `.claude/skills/*/SKILL.md` | Anthropic SKILL.md 표준 채택 | single source `.claude/skills/` |
| `.claude/hooks/hooks.json` | Cursor 2.4+ Claude Code hooks schema 호환 명시 (changelog 근거); IDE 모드 인식은 Phase 1 검증 | single source `.claude/hooks/` (검증 결과 따라 `.cursor/hooks.json` 분기 가능) |
| `.claude/settings.json` mcpServers | Cursor 는 `.cursor/mcp.json` 별도 위치 | dual: `.claude/settings.json` + `.cursor/mcp.json` (Cursor target 시) |
| `CLAUDE.md` | Cursor 미지원 | dual: `CLAUDE.md` + `.cursor/rules/*.mdc` (Cursor target 시) |
| `.claude/commands/hm/*.md` | Cursor 는 `.cursor/commands/<name>.md` 별도 (`.claude/commands/` 호환은 Phase 1 검증) | dual or single (Phase 1 결과 따름) |
| Plan Mode (Cursor 전용) | Shift+Tab 진입, AskQuestion 통합 | `/hm:research` 등 명령에 자연어 힌트 |
| Worktrees | Cursor `/worktree` 자체, 공유 사용 | `.worktrees/` 단일 |

---

## 3. 검증 안 된 가정 (Phase 1 게이트)

이 4개가 **myplan 진입 전 필수 검증**. 하나라도 fail 시 설계 일부 재작업.

| # | 가정 | 검증 fixture | PASS 기준 | Fail 시 영향 |
|-|-|-|-|-|
| A1 | Cursor IDE 가 `.claude/agents/` 읽음 | `tests/cursor-compat/agents/test-agent.md` (cross-frontmatter: name, description, model + `is_background: false`, `readonly: true`) | **모두 PASS 필요** — `A1.list` (목록 표시) AND `A1.dispatch` (trigger 시 dispatch) AND `A1.frontmatter` (strict-reject 부재). 각 항목은 RESULTS.md 표 참조. | `.cursor/agents/` 별도 렌더 추가, single source 가정 무효화 |
| A2 | Cursor IDE 가 Claude Code hooks 인식 | `tests/cursor-compat/.claude/hooks/hooks.json` (PreToolUse, matcher 확장) | **모두 PASS 필요** — `A2.fire` (hook 실행 메시지 보임) AND `A2.case` (PascalCase 키 호환). | `.cursor/hooks.json` 별도 + 스키마 변환 layer 추가 |
| A3 | SKILL.md frontmatter 호환 | `tests/cursor-compat/skills/test-skill/SKILL.md` (name, description, when_to_use, user-invocable: true) | **모두 PASS 필요** — `A3.auto-discover` (trigger 시 자동) AND `A3.user-invocable` (slash 호출, 두 prefix 중 하나) AND `A3.frontmatter` (strict-reject 부재). | `.cursor/skills/` 별도 frontmatter 변환 |
| A4 | Plan Mode 통합 + slash command 흐름 | `/hm:research` 본문에 자연어 Plan Mode 힌트 + 호출 | **`A4.command-discover` AND `A4.agent-mode` PASS 필수**; `A4.plan-mode-askquestion` 은 PARTIAL (자연어 fallback) 허용. | command-discover fail 시 `.cursor/commands/` 별도 렌더; Q&A fail 시 자연어 chat 다운그레이드 + onboarding 가이드 |

추가 Phase 1 검증:
- **B11**: 옛 harness.yaml 에 `targets` 없는 fixture 로 re-render → fallback 작동 확인
- **B13**: reconcile.py 가 `.cursor/` 디렉토리 enumerate 하는지 검증
- **F1**: Cursor permission system 추가 docs 조사 (`permissionMode`, `sandbox.json` 등가물)

---

## 4. 빠진 고려사항 (Phase 2 myplan 에서 lock-in)

### 호환성 / 시맨틱 갭

- **B1** ✅ Anthropic 모델 권장으로 해결
- **B2**: tool 이름 매핑 검증 (`Read`, `Grep`, `Glob`, `Bash` 등이 Cursor 에서 동일 작동? Cursor 의 `Task → Agent` rename 같은 차이 매핑표)
- **B7**: user 의 `~/.claude/CLAUDE.md` global 5-stage 워크플로우 (`/research /myplan /execute /review /wrapup`) 를 Cursor 사용자에게 어떻게 제공? harness-maker 책임 범위 명시 필요

### 디렉토리 / Schema

- **B3**: `.claude/lib/` Python helper 의 dual-plugin 모드에서 위치 결정
- **B4** ✅ worktree 공유로 해결
- **B11** Phase 1 에서 검증
- **B12**: `interview.answers_from_harness_yaml` 의 `targets` reverse mapping (옛 harness.yaml 호환)
- **B13** Phase 1 에서 검증

### 보안 / 권한

- **F1**: Cursor `permissionMode` / `sandbox.json` 정합성 (Phase 1 추가 조사)
- **F2**: reviewer agent allow/deny 정책이 Cursor 에서 강제되는 메커니즘

### 빌드 / 배포

- **B10**: Cursor 측 e2e 는 IDE manual 검증이라 CI 자동화 불가. CI 에서는 unit + snapshot test 로 디스크 산출물 (frontmatter, parser 정합성, render 결정성) 만 잡고, IDE 인식은 manual 체크리스트 (`tests/cursor-compat/MANUAL_CHECKLIST.md`) 로 회귀 방지.
- **B14**: `dev_mode × targets` 6 cross product 테스트 매트릭스 (전부 / minimal / sample)
- **C2** ✅ dual plugin = `.cursor-plugin/plugin.json` 추가만, marketplace publish 는 분리

---

## 5. Phases

### Phase 0 — CLAUDE.md 업데이트 (1 turn)

**Files**
- `CLAUDE.md`

**변경 사항**
| 섹션 | 변경 |
|-|-|
| 버전업 정책 | 3 파일 → 4 파일 (`.cursor-plugin/plugin.json` 추가) |
| Plugin 구조 | `.cursor-plugin/plugin.json` 추가 명시 |
| 사용자 하네스 구조 | `.cursor/rules/`, `.cursor/commands/`, `.cursor/mcp.json` 조건부 (targets 에 cursor 포함 시) |
| 보안/권한 | Cursor `permissionMode`, `sandbox.json` 정합성 stub (Phase 1 결과 채움) |
| 체크리스트 #2 | Cursor `.mdc` parser, `.cursor-plugin/plugin.json` parser 추가 |
| 체크리스트 #8 | Cursor IDE manual 검증 default + unit/snapshot test 강화 정책 |
| 새 섹션 — Targets 정책 | targets 축 + 인터뷰 강제 multi-select + default fallback 정책 |

**Acceptance**
- CLAUDE.md 가 Phase 1 검증 fixture 작성 시 충분한 컨텍스트 제공
- 4 파일 sync 정책 명시
- targets 축 정책 단락 추가됨

---

### Phase 1 — 가정 검증 (게이트)

**Files**
- `tests/cursor-compat/` (신설)
  - `agents/test-agent.md` — A1 검증
  - `.claude/hooks/hooks.json` + `.cursor/hooks.json` 비교 — A2 검증
  - `skills/test-skill/SKILL.md` — A3 검증
  - `commands/test-research.md` — A4 검증
  - `harness.yaml` minimal — re-render fallback (B11)
  - `README.md` — 검증 결과 기록

**검증 절차** (사용자가 Cursor IDE 사용 — CLI 사용 X)

자동화 가능한 부분 (CI):
1. `python -m harness_maker.cli render` 옛 harness.yaml fixture (targets 키 없음) → `[claude-code]` fallback + 경고 로그 확인 (B11)
2. `python -m harness_maker.cli render` Cursor target → `.cursor/` 출력 + reconcile 산출물 hash 검증 (B13)
3. snapshot test: 렌더된 `agents/test-agent.md`, `skills/test-skill/SKILL.md`, `hooks.json` 의 frontmatter / JSON 형식이 Cursor 표준 만족
4. parser test: `.mdc` 가 valid YAML frontmatter, `.cursor-plugin/plugin.json` 이 valid JSON

Manual 검증 (사용자가 IDE 에서 직접 — `tests/cursor-compat/MANUAL_CHECKLIST.md` 에 step-by-step 기록):
5. **A1**: Cursor IDE 에서 fixture 디렉토리 open → `/agents` 목록에 `test-agent` 표시 또는 agent dispatch 로 인식되는지 확인
6. **A2**: 도구 사용 트리거 (예: 파일 편집) → hook fire 확인, exit 2 시 block 작동 확인
7. **A3**: skill auto-discovered (chat 컨텍스트에 등장 또는 slash 명령으로 호출 가능)
8. **A4**: `/hm:research` 호출 → 인터뷰 흐름 작동 (Agent Mode 자연어 OK 또는 Plan Mode 진입 권유)
9. 결과를 `tests/cursor-compat/RESULTS.md` 에 PASS/FAIL + 스크린샷/로그로 기록

**Acceptance**
- A1–A4 manual 검증 결과 `tests/cursor-compat/RESULTS.md` 에 기록
- B11 + B13 fixture 작성 (자동화 검증 자체는 Phase 2 implementation 후로 deferred — Phase 2 acceptance 에 포함)
- A1–A4 모두 PASS (또는 PARTIAL with onboarding 가이드 처리 가능) 시 Phase 2 진입
- A1–A4 일부 FAIL 시 plan §3 "Fail 시 영향" 행 적용 → 본 PLAN 갱신 후 재 review

---

### Phase 2 — `/myplan` 진입 (Phase 1 PASS 후)

이 시점에 implementation plan 을 신규 작성. 다룰 결정:

1. `.cursor/commands/` 별도 렌더 vs `.claude/commands/` 만 사용 (A4 결과 따라)
2. `.cursor/rules/` 1차는 단일 mdc — frontmatter 와 본문 정확한 mapping
3. `.cursor/mcp.json` 추출 정책 — `.claude/settings.json` 의 mcpServers 이전 경로
4. Plan Mode 통합 trigger — `/hm:research` 가 Cursor 에서 어떤 자연어로 Plan Mode 권유
5. e2e 검증 fixture 설계 (CI 가용성 결과 따라 manual / automated)
6. dev_mode × targets 6 cross product 테스트 매트릭스
7. tool 이름 / model id mapping (B2)
8. user global workflow 명령 정책 (B7)

**Acceptance** (myplan 완료 시점):
- 위 1–8 결정 모두 lock-in (AskUserQuestion 으로 사용자 확인)
- B11 자동화 검증 통과: 옛 harness.yaml fixture 가 `[claude-code]` silent fallback + 경고 로그
- B13 자동화 검증 통과: `reconcile.py` 가 `.cursor/` 디렉토리도 backup/scan 범위에 포함
- Cursor target 렌더 결과의 snapshot test 통과 (frontmatter 형식, parser 정합성, render 결정성)
- production hook command (`uv run --with ... python -m harness_maker.gates.X`) 가 Cursor IDE 에서 작동하는지 manual 추가 검증
- Phase 3 (execute) 진입 준비 완료

---

### Phase 3+ — execute / review / wrapup

Phase 2 myplan 결과대로 실 구현. CLAUDE.md "Workflow" 의 atomic stage 규약 따름.

---

## 6. 위험 / 모니터링

### 의존성 위험

- **D1**: "Cursor 가 `.claude/` 읽는다" 가정에 의존 → Cursor 향후 deprecate 시 우리 설계 일부 깨짐. **완화**: 명시적 `.cursor/` 미러를 phased 로 추가 가능하도록 render dispatch 를 확장 가능하게 설계.
- **D2**: Cursor 가 fast-moving (3.x 가 4월에 release). **완화**: 최소 지원 버전 명시 (`Cursor 2.4+`), README 에 호환 매트릭스, monthly review.
- **D3**: AskQuestion 이 Plan Mode 한정. **완화**: 자연어 fallback + onboarding 문서.

### 호환성 매트릭스

릴리스 전 검증해야 할 조합 (B14):
- `targets=[claude-code]` × `preset∈{Side,Production}` × `dev_mode∈{spec,task}` (4 조합, 기존 회귀)
- `targets=[cursor]` × 위 4 조합 (4 조합, 신규)
- `targets=[claude-code, cursor]` × 위 4 조합 (4 조합, 신규)
- 합계 12 조합. 최소 지원 cell: 6 (각 target 의 Side+spec, Side+task, Production+spec)

---

## 7. 다음 액션

**즉시 다음 turn 에 가능**:
- Phase 0 (CLAUDE.md 업데이트) 시작 — single Edit/Write turn 가능

**사용자 환경 의존**:
- Phase 1 (검증 fixture) — 사용자가 Cursor IDE 에서 fixture 디렉토리 open. 자동화된 부분 (B11/B13/snapshot/parser) 은 CI 에서, IDE 인식 (A1–A4) 은 사용자가 직접 IDE 에서 manual 확인 후 `RESULTS.md` 에 기록.

**Phase 0 와 Phase 1 의 순서 결정 필요**:
- 옵션 a: Phase 0 → Phase 1 → Phase 2 (선형, 권장)
- 옵션 b: Phase 0 + Phase 1 fixture 작성 병렬, 검증 실행만 차단 (Phase 1 게이트는 검증 결과)

---

## 8. 기록

### 메모리 저장된 결정

- `project_targets_axis.md` — targets 축 신설
- `project_dual_plugin_manifest.md` — dual plugin + 4 파일 sync
- `project_cursor_model_policy.md` — Anthropic 모델 권장
- `project_worktree_share_policy.md` — `.worktrees/` 공유

### 참조

- Cursor Plugin 공식 spec: `https://github.com/cursor/plugins`
- Cursor Subagents docs: `https://cursor.com/docs/subagents`
- Cursor Hooks docs: `https://cursor.com/docs/hooks`
- Cursor Plan Mode docs: `https://cursor.com/docs/agent/plan-mode`
- Anthropic SKILL.md 표준: 32+ 도구 채택 (Cursor 2.4 포함)
- Claude Code Sub-agents docs: `https://code.claude.com/docs/en/sub-agents`
