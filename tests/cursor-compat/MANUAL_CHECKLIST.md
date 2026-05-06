# Phase 1 Manual Checklist (Cursor IDE + Claude Code)

> 이 체크리스트는 harness-maker 의 Cursor target 핵심 가정 (single source `.claude/` → 양쪽 IDE 작동) 을 검증하기 위해 **사용자가 IDE 에서 직접 따라가는 step-by-step 가이드**.

**예상 소요**: 30 분 (Cursor 1회차 ~20분 + 회귀용 Claude Code ~10분, 환경 setup 포함)

**필요 준비물**:
- Cursor IDE 2.4 이상 (3.0+ 권장)
- Claude Code 최신 (회귀 검증용)
- 본 repo clone 됨 — 아래 절차에서 `<repo-root>` 는 사용자 머신의 clone 경로로 치환

---

## 사전 준비

1. 터미널에서:
   ```bash
   cd <repo-root>/tests/cursor-compat/fixture
   ```
2. **Cursor IDE 에서**: File → Open Folder → 위 경로 선택
3. **Claude Code 에서**: 동일 경로에서 `claude` 실행
4. **메시지 확인 위치 사전 인지**:
   - **Claude Code**: hook 출력은 도구 결과 박스에 표시. agent / skill 응답은 chat
   - **Cursor**: hook 출력은 통합 콘솔 (View → Output → Hooks 채널) 또는 chat 의 도구 결과 영역. agent / skill 은 chat
   - 어느 쪽에서도 메시지 못 찾으면 stderr/stdout 분리 가능성 — RESULTS.md 의 비고에 기록
5. **fixture clean state 확인** — 검증 시작 전 + 종료 후 모두 실행:
   ```bash
   cd <repo-root>
   git status tests/cursor-compat/fixture/
   ```
   - **검증 시작 전**: clean (수정 사항 없음) 이어야 정상. 그렇지 않으면 직전 검증의 잔여물 → `git checkout tests/cursor-compat/fixture/` + `git clean -fd tests/cursor-compat/fixture/` 로 복원
   - **검증 종료 후**: `.gitignore` 가 `.cursor/`, `.claude/settings.local.json`, `.specstory/`, `.history/` 를 차단하므로 untracked 도 비어있어야 정상. 차이 발생 시 RESULTS.md 비고에 기록 (Cursor 가 새 메타 디렉토리 만들었을 가능성 → `.gitignore` 에 패턴 추가 후 PR 의 fix 로 commit)
   - **Cursor 와 Claude Code 검증 사이**: 각 IDE 검증 후 위 절차로 fixture 복원하여 다음 IDE 가 깨끗한 상태에서 시작

---

## A1 — Agent dispatch (single source `.claude/agents/`)

### Cursor IDE

1. Agents 목록 보기 (Cursor 3.0+ 의 Agents Window 또는 `/agents` 명령 또는 명령 팔레트)
2. **확인 1 (`A1.list`)**: `phase1-test-agent` 가 목록에 표시되는가?
   - YES → PASS
   - NO → FAIL (`.cursor/agents/` 별도 렌더 필요할 가능성)
3. **두 dispatch 방법 모두 시도** — 각각 별도 chat 세션에서 (이전 응답의 잔여 영향 회피):
   - **3a. description-based 자동 dispatch**: 새 chat 에서
     ```
     phase 1 agent test
     ```
     (frontmatter `description` 의 trigger phrase 와 user input 매칭으로 IDE 가 자동 dispatch — 비결정적)
   - **3b. @-mention 명시 dispatch**: 새 chat 에서
     ```
     @phase1-test-agent
     ```
     (Cursor / Claude Code 모두 sub-agent @-mention 지원 — 결정적)
4. **확인 2 (`A1.dispatch`)**: 3a 와 3b **중 하나 이상**이 정확히 다음 한 줄 출력하는가?
   ```
   PHASE-1 A1 PASSED — agent dispatched from .claude/agents/ in Cursor
   ```
   - 둘 다 PASS → `A1.dispatch` = PASS (비고: "auto + @-mention 둘 다 작동")
   - 3b 만 PASS → `A1.dispatch` = PASS (비고: "@-mention 만, description 매칭 실패 — production agent 의 description 정밀화 검토 필요")
   - 3a 만 PASS → `A1.dispatch` = PASS (비고: "description 매칭만, @-mention 실패")
   - 둘 다 FAIL → `A1.dispatch` = FAIL (사유 기록: 응답 없음 / 다른 응답 / 에러)
5. **확인 3 (`A1.frontmatter`)**: agent frontmatter 의 cross-compat 키 strict-reject 여부 확인
   - Cursor 가 `is_background: false`, `readonly: true` 같은 키 또는 (없는 경우) `tools` 키를 만나 에러를 띄우는가?
   - 콘솔 / Output 채널 / chat 출력 어디에도 schema 에러 없음 → PASS
   - 에러 → FAIL (메시지 캡처)

### Claude Code (회귀)

1. `/agents` 입력 → `A1.list` claude-code 열
2. 동일 trigger `phase 1 agent test` 입력 → `A1.dispatch` claude-code 열
3. agent 로드 시 schema 에러 부재 확인 → `A1.frontmatter` claude-code 열

---

## A2 — Hook fire (single source `.claude/hooks/hooks.json`)

> hook matcher 가 `Edit|Write|Read|Bash` 로 넓게 잡혀 있으므로 어떤 도구든 호출되면 fire 된다.

### Cursor IDE

1. 새 chat 에서 다음 명시 명령:
   ```
   Use the Read tool to read tests/cursor-compat/fixture/.claude/agents/phase1-test-agent.md and tell me the first line.
   ```
   (Read 도구를 명시 호출하도록 강제. 자연어 hint 보다 결정적.)
2. **확인 1 (`A2.fire`)**: 도구 사용 직전에 hook 이 fire 되어 다음 메시지가 어딘가에 보이는가?
   ```
   PHASE-1 A2 PASSED — hook fired on PreToolUse(Edit|Write|Read|Bash)
   ```
   확인할 위치:
   - chat 의 도구 결과 영역
   - View → Output 채널 (Cursor 는 "Hooks" 또는 "Tasks" 채널 가능)
   - 통합 터미널의 hook 로그
   - YES → PASS (single source hooks.json 작동)
   - NO → FAIL (`.cursor/hooks.json` 별도 + 스키마 변환 필요)
3. **확인 2 (`A2.case`)**: hooks.json 의 PascalCase (`PreToolUse`) 표기를 Cursor 가 그대로 받아주는가?
   - hook 이 fire 됐다면 PASS
   - schema 에러가 떠 있으면 콘솔 로그 캡처 → camelCase (`preToolUse`) 변환 layer 필요

### Claude Code (회귀)

1. 동일 명령 입력 → hook fire 메시지 확인 → `A2.*` claude-code 열

---

## A3 — Skill auto-discovery (single source `.claude/skills/`)

### Cursor IDE

1. 새 chat 에서 정확히:
   ```
   phase 1 skill test
   ```
   (frontmatter 의 `when_to_use` 와 일치하는 trigger)
2. **확인 1 (`A3.auto-discover`)**: skill 이 활성화되어 정확히 다음 한 줄 응답이 오는가?
   ```
   PHASE-1 A3 PASSED — skill loaded from .claude/skills/test-skill/ in Cursor
   ```
   - YES → PASS
   - NO → FAIL (skill 무시됨 / 다른 응답)
3. 새 chat 에서 slash 명령으로 직접 호출 — **두 prefix 모두 시도**:
   - `/phase1-test-skill`
   - `/test-skill`
4. **확인 2 (`A3.user-invocable`)**: 둘 중 하나라도 명령 dropdown 에 표시되고 호출 가능?
   - YES → PASS (어느 prefix 인지 비고에 기록)
   - NO → FAIL
5. **확인 3 (`A3.frontmatter`)**: SKILL.md frontmatter 의 `when_to_use`, `user-invocable` 같은 Anthropic 표준 키 strict-reject 여부 → schema 에러 없음 → PASS

### Claude Code (회귀)

1. 동일 trigger `phase 1 skill test` → `A3.auto-discover` claude-code 열
2. 두 prefix 시도 → `A3.user-invocable` claude-code 열
3. schema 에러 부재 확인 → `A3.frontmatter` claude-code 열

---

## A4 — Slash command + Q&A loop

### Cursor IDE — Agent Mode (기본)

1. 새 chat 에서 **두 prefix 모두 시도**:
   - `/hm:test-research`
   - `/test-research`
2. **확인 1 (`A4.command-discover`)**: 둘 중 하나라도 슬래시 명령 dropdown 에 표시되는가?
   - YES → PASS (어느 prefix 인지 비고에 기록)
   - NO → FAIL (`.cursor/commands/` 위치 별도 렌더 필요)
3. dropdown 에서 선택하여 명령 실행
4. Cursor 가 사용자에게 IDE / 모드 선택 4지 질문을 던짐
5. "Cursor (Agent Mode, default)" 라고 답변
6. **확인 2 (`A4.agent-mode`)**: 명령이 답변을 받아 정확히 다음 한 줄 출력하는가?
   ```
   PHASE-1 A4 PASSED — slash command + Q&A loop works in Cursor (Agent Mode, default)
   ```
   - YES → PASS (자연어 fallback OK)
   - NO → FAIL (사유 기록)

### Cursor IDE — Plan Mode

1. 새 chat 에서 **Shift+Tab** 으로 Plan Mode 진입
2. 명령 실행 (위에서 확인된 prefix)
3. **확인 3 (`A4.plan-mode-askquestion`)**: Plan Mode 의 AskQuestion 이 4지 선택을 구조화 UI 로 표시?
   - YES → PASS
   - NO → FAIL (자연어 chat 으로만 작동하면 PARTIAL)
4. "Cursor (Plan Mode)" 답변 → 한 줄 출력 확인 → `A4.plan-mode` PASS / FAIL

### Claude Code (회귀)

1. `/hm:test-research` 입력 (Claude Code 의 공식 prefix)
2. AskUserQuestion 이 4지 구조화 UI 로 표시 → `A4.command-discover` + `A4.plan-mode-askquestion` claude-code 열 (Claude Code 는 항상 구조화)
3. "Claude Code" 선택 → 한 줄 출력 확인 → `A4.agent-mode` claude-code 열

---

## 결과 기록

위 모든 step 의 PASS / FAIL 을 `RESULTS.md` 의 표에 채우고, FAIL 항목은 사유·로그·스크린샷을 첨부.

### 메타 정보 채우기 (RESULTS.md 상단)

검증 시작 전 다음 정보 확인:
```bash
# harness-maker 버전
grep '^version' <repo-root>/pyproject.toml
grep '^"version"' <repo-root>/.claude-plugin/plugin.json

# fixture commit SHA (이 fixture 가 어느 시점인지 고정)
cd <repo-root> && git rev-parse HEAD

# Cursor 버전
# Cursor → About 메뉴 또는 cursor --version (CLI 가 있다면)

# Claude Code 버전
claude --version
```

### 분기 결정

- **A1–A4 모두 PASS**: `PLAN-cursor-target-support.md` Phase 2 (myplan) 진입
- **일부 FAIL**: PLAN §3 "Fail 시 영향" 행 적용 → 본 PLAN 갱신 후 재 review
- **PARTIAL** (자연어 fallback 으로만 작동): Phase 2 에서 onboarding 가이드 추가로 처리. PASS 로 분류.
