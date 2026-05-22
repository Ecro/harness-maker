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

---

## Phase 2.8 — Production hook 작동 검증

> 위 A1–A4 manual checklist 와 별도. **Phase 1 fixture 의 simple echo hook**
> 이 fire 되더라도 production 은 `uv run --with <pkg> python -m
> harness_maker.gates.X` 패턴으로 호출 — 이 production-style command 가 Cursor
> IDE 환경에서 실제 작동하는지 검증.

### 절차 (Cursor IDE)

1. **실제 프로젝트** (또는 이 repo) 의 `.claude/` 가 비어있는 디렉토리에서:
   ```bash
   /harness-maker:make
   ```
   인터뷰에서 `targets=[claude-code, cursor]` 또는 `[cursor]` 선택.
2. 렌더된 `.claude/hooks/hooks.json` 확인 — `PreToolUse` matcher 와 command:
   ```bash
   jq '.hooks.PreToolUse' .claude/hooks/hooks.json
   ```
   command 가 `uv run --with /path/to/harness-maker python -m harness_maker.gates.permission_gate` 형식이어야.
3. Cursor IDE 에서 도구 사용 (예: 파일 편집) 시도:
   - **Claude Code 회귀**: 기준선으로 동작 확인 — Claude Code 에서 hook fire +
     `permission_gate` 실행 + exit 0 또는 stderr 메시지 보임
   - **Cursor 검증**: 같은 도구 사용 → hook fire 확인
4. 검증 항목:
   - **`Phase2.8.fire`**: Cursor 가 `PreToolUse` matcher 의 command 를 trigger 하는가?
   - **`Phase2.8.uv-resolves`**: `uv run --with <path>` 의 path resolution 이
     Cursor 환경에서 작동하는가? (`harness_maker_src_path` jinja 변수 → render
     시 절대 경로 박힘)
   - **`Phase2.8.module-loads`**: `python -m harness_maker.gates.permission_gate`
     가 ImportError / ModuleNotFoundError 없이 실행되는가?
   - **`Phase2.8.exit-clean`**: hook command 가 exit 0 또는 graceful exit 2 (블록)
     로 종료하는가? Stack trace 없음.

### 기록 (RESULTS.md)

위 4 항목별 PASS/FAIL 을 RESULTS.md 의 Phase 2.8 row 에 채움. FAIL 시
사유와 stderr 캡처를 비고에 기록.

### Fail 시 분기

- `Phase2.8.fire` FAIL → Cursor 의 hook event 매핑 (camelCase vs PascalCase)
  재검증 + `.cursor/hooks.json` 별도 렌더 + 스키마 변환 layer 도입
- `Phase2.8.uv-resolves` FAIL → harness-maker 가 `uv` 의존성 명시 또는
  Cursor 환경에서의 PATH 전파 가이드 필요
- `Phase2.8.module-loads` FAIL → harness-maker 가 dev dep 으로 사용자 프로젝트
  에 등록되어 있는지 확인 (`pyproject.toml` 의 dependency-groups.dev) +
  installation 가이드 갱신
- `Phase2.8.exit-clean` FAIL → `harness_maker.gates.X` 의 graceful exit
  policy 검토 + uncaught exception 의 user-facing message 개선

---

## Phase 2.9 — PreToolUse loop_gate 검증 (Cursor loop longevity)

> `harness_maker.hooks.loop_gate --mode pretooluse` 가 Cursor 의 `preToolUse`
> Bash hook 으로 fire 되는지, 그리고 `.hm-loop-active` marker 유무에 따라
> advisory stderr 메시지가 정확히 출력되는지 수동 확인.

### 절차 (Cursor IDE)

1. **실제 프로젝트** 에서 `/harness-maker:make` 로 하네스를 렌더 (targets 에
   `cursor` 포함).
2. `.cursor/hooks.json` 에 `preToolUse.Bash` 항목으로 `loop_gate --mode pretooluse`
   가 포함되어 있는지 확인:
   ```bash
   cat .cursor/hooks.json | python -m json.tool | grep loop_gate
   ```
   loop_gate 항목 있으면 PASS.

3. **marker 없음** — Cursor IDE 에서 Bash 도구를 실행 (예: `ls`):
   - **`Phase2.9.no-marker`**: hook 이 fire 되고 stderr 에 `[loop-gate]` 메시지가
     **없어야** 정상. exit 0.

4. **marker 있음** — 프로젝트 루트에서:
   ```bash
   touch .hm-loop-active
   ```
   이후 Cursor IDE 에서 Bash 도구 실행:
   - **`Phase2.9.advisory-msg`**: stderr/output 에
     `[loop-gate] /hm:loop active` 메시지가 보이는가?
   - **`Phase2.9.still-exits-0`**: hook 이 exit 0 으로 종료하여 도구 실행이
     **block 되지 않는가**? (preToolUse exit 2 = tool cancel. 이 hook 은
     항상 exit 0 이어야 함)
   - 테스트 후 정리: `rm .hm-loop-active`

### 기록 (RESULTS.md)

`Phase2.9.no-marker`, `Phase2.9.advisory-msg`, `Phase2.9.still-exits-0` 각
PASS/FAIL 을 RESULTS.md Phase 2.9 row 에 기입.

### Fail 시 분기

- `Phase2.9.no-marker` FAIL (메시지 잘못 출력) → `_find_marker` 로직 오류. cwd
  탐색 경계 확인.
- `Phase2.9.advisory-msg` FAIL (메시지 미출력) → Cursor 가 hook stderr 을
  Output 패널에 표시하지 않을 수 있음. stdout 으로 전환 고려.
- `Phase2.9.still-exits-0` FAIL (도구 block) → `_pretooluse` 가 exit 0 을
  반환하는지 코드 재확인. 다른 hook 이 exit 2 를 반환하는 충돌 가능성 배제.

---

## Phase 3 — README one-prompt paste flow (Cursor + Claude Code)

> PLAN-readme-one-prompt-autoinstall 의 paste flow 가 실제 IDE 에서 promise (per-IDE step budget 표 의 액션 수) 와 일치하는지 확인. 매번 fresh-state IDE 에서 수동 측정.

**예상 소요**: 10 분 (Claude Code 5분 + Cursor 5분)

### Phase 3.1 — Claude Code paste flow

1. **Fresh state**: harness-maker 미설치 환경 (`~/.claude/plugins/installed_plugins.json` 에 `harness-maker@harness-maker` 없음). 이미 있으면 먼저:
   ```bash
   claude plugin uninstall harness-maker@harness-maker
   ```
2. 빈 tmp 디렉토리에서 `claude` 실행, 새 세션 시작.
3. README.md 의 Quickstart > Universal Bootstrap Prompt 코드 펜스 안 내용을 **그대로 paste**.
4. **관찰 (정상 경로)**:
   - Claude 가 IDE 감지 → Claude Code branch 선택
   - Claude 가 Bash 권한 요청 → 사용자 1회 승인
   - Claude 가 `claude plugin marketplace add Ecro/harness-maker` 실행
   - Claude 가 `claude plugin install harness-maker@harness-maker` 실행
   - Claude 가 메시지 출력: `Type /reload-plugins now, then press enter once.`
5. 사용자가 `/reload-plugins` type → enter 한 번.
6. **관찰**: Claude 가 후속 turn 에서 Skill(harness-maker:make) 자동 발사 — `harness-maker:make` 인터뷰 시작.
7. 인터뷰 끝나면 Claude 가 자동으로 Skill(hm:health) 발사 → `.claude/observability/dashboard.md` 생성.

**총 사용자 액션 측정**: paste(1) + Bash 승인(1) + `/reload-plugins`(1) + enter(1) = **3-4** (Bash 승인 제외 시 3, README 의 표에 명시된 2-3 과 일치하는지 확인)

**Fail 분기**:
- Claude 가 슬래시 명령 typing 을 요청 → README 의 prompt 가 잘못 읽힘. prompt 의 `via Bash (NOT slash commands typed by me)` 문구 강도 부족.
- `/reload-plugins` 후 Claude 가 자동 이어가지 않음 → `manual-enter-required` 가정이 맞음. README 의 "press enter once" 문구가 작동하는지 확인.
- Bash 권한 거부 → Claude 가 graceful fallback 으로 manual 안내해야 함. 그렇지 않으면 prompt 의 에러 처리 부실.

### Phase 3.2 — Cursor paste flow

1. **Fresh state**: `~/.cursor/plugins/local/harness-maker/` 디렉토리 없음. 있으면:
   ```bash
   rm -rf ~/.cursor/plugins/local/harness-maker
   ```
2. Cursor IDE 열기, 빈 폴더 (또는 본 repo 의 `tests/cursor-compat/fixture`) 에서 새 chat 세션 시작.
3. README.md 의 Quickstart > Universal Bootstrap Prompt 코드 펜스 paste.
4. **관찰**:
   - Claude 가 IDE 감지 → Cursor branch 선택
   - Claude 가 Bash 권한 요청 → 사용자 1회 승인
   - Claude 가 `git clone https://github.com/Ecro/harness-maker.git ~/.cursor/plugins/local/harness-maker` 실행
   - Claude 가 메시지 출력: `Reload the Cursor window now (Ctrl+Shift+P → Reload Window).`
5. 사용자가 `Ctrl+Shift+P` → `Reload Window` 선택. Cursor 가 reload.
6. Reload 후 chat 다시 열기. Claude 가 자동 이어가지 않음 — 사용자가 짧은 메시지 (예: `continue`) 입력.
7. **관찰**: Claude 가 harness-maker:make skill 발사 → 인터뷰 → hm:health 자동.

**총 사용자 액션 측정**: paste(1) + Bash 승인(1) + `Reload Window`(1 GUI) + continue 메시지(1) = **3-4** (README 표의 2 와 일치하는지 확인 — Bash 승인 + continue 메시지는 표 외 일 수 있음, RESULTS.md 에 차이 기록)

**Fail 분기**:
- Cursor 의 chat 세션이 reload 후 새 세션으로 시작 → context 손실. paste prompt 다시 필요. 이 경우 README 의 promise 가 Cursor 에서 깨짐 → 별도 ADR 필요.
- `git clone` 실패 (네트워크 / 권한) → manual fallback 명시되어 있는지 확인.

### Phase 3.3 — Codex CLI paste flow

(Codex CLI 사용자 별도 검증 — Phase 3.3 는 codex CLI 가 설치된 환경에서만)

1. **Fresh state**: codex 의 marketplace 목록에 `harness-maker` 없음.
2. 빈 디렉토리에서 `codex` 실행, 새 세션 시작.
3. README.md 의 Quickstart 코드 펜스 paste.
4. **관찰**:
   - AI 가 Codex CLI branch 선택
   - AI 가 `codex plugin marketplace add Ecro/harness-maker` 실행 (Bash)
   - AI 가 메시지: `Open Codex's /plugins list; if harness-maker isn't enabled, restart codex.`
5. 사용자가 `/plugins` type → harness-maker 확인. 없으면 `Ctrl+C` 후 `codex` 재실행.
6. 이후 harness-maker:make / hm:health 진행 (Codex 의 skill 호출 방식 따름).

**Fail 분기**: Codex CLI 의 plugin lifecycle 이 marketplace-add ≠ install 일 수도 — `/plugins` 목록에 없으면 별도 `codex plugin install` 필요한지 확인.

---

## Phase 7 manual IDE acceptance — brownfield preservation (v0.23.0)

> 사용자가 Cursor 2.4+ / Codex CLI 환경에서 직접 실행. 자동화 e2e (`tests/e2e/test_preservation_e2e.py`, INTEGRATION=1) 는 on-disk reconcile + render 출력을 검증하지만, **IDE 가 실제로 merged hooks.json 을 fire 하는지** 는 IDE-driven runtime 이라 manual 검증.

**예상 소요**: 15분 (Cursor 8분 + Codex CLI 7분; v0.23.0 plugin update 후 1회 충분)

### C7.1 — Cursor IDE: merged hooks.json 실제 fire

**시나리오**: brownfield project 에서 user 가 custom hook entry 를 추가한 후 `/hm:make --update` 실행, Cursor 가 실제로 merged hook 을 fire 하는지 확인.

1. **준비**: Cursor 2.4+ 에서 harness-maker 가 설치된 brownfield project 열기 (이미 `.claude/`, `.cursor/` 가 있는 상태).
2. `.cursor/hooks.json` 을 IDE 에서 직접 열어 `preToolUse` 배열에 다음 entry 추가:
   ```json
   {"matcher": "Read", "command": "echo USER_CUSTOM_HOOK_FIRED && exit 0"}
   ```
   파일 저장.
3. Cursor chat 에서 `/hm:make` (Update branch) 실행.
4. **확인 #1 — preservation**: 명령 종료 후 `.cursor/hooks.json` 다시 열어 `USER_CUSTOM_HOOK_FIRED` 라인이 남아있는지 확인. 사라졌으면 P0 — REVIEW report 에 보고.
5. **확인 #2 — runtime fire**: Cursor 가 다른 turn 에서 `Read` 도구 호출 시 IDE 의 통합 콘솔 (View → Output → Hooks 채널) 또는 chat 의 도구 결과 박스에 `USER_CUSTOM_HOOK_FIRED` 표시되는지 관찰. 안 보이면 schema 호환성 (lowercase `preToolUse` + flat `{matcher, command}`) 문제일 수 있음 — `tests/cursor-compat/results-2026-05-08.md` 의 검증 결과와 비교.
6. **회복 확인**: `git status` 에 `.backup-<ts>/` 나타나지 않으면 Phase 4 gitignore 자동 wiring 작동 확인. 나타나면 P1 — wiring 미적용.

**Fail 분기**:
- preservation 실패 → `tests/unit/test_preservation_matrix.py::test_m6b_cursor_hooks_json_merges` 가 unit 에서는 GREEN 인데 IDE 환경에서 깨짐 → render 의 schema dispatch 가 잘못된 경로 — render.py 의 `schema = "flat" if str(fe.path) == ".cursor/hooks.json" else "nested"` 분기 재검토.
- runtime fire 실패 → schema 출력은 맞지만 Cursor 가 안 읽음 → `tests/cursor-compat/results-2026-05-08.md` 의 kairos 0.5.7 forensic 시점부터 Cursor 가 변했을 가능성 — 별도 ADR 로 schema drift 검증.

### C7.2 — Codex CLI: merged hooks.json + PermissionRequest

**시나리오**: Codex 의 nested PascalCase 스키마 + matcher-less `PermissionRequest` event 가 user-added entry 보존 + 실제 fire.

1. **준비**: Codex CLI 환경에서 harness-maker brownfield project (이미 `.codex/`, `AGENTS.md` 있음).
2. `.codex/hooks.json` 의 `PermissionRequest` 배열에 다음 entry 추가:
   ```json
   {"hooks": [{"type": "command", "command": "echo CODEX_PERMISSION_HOOK_FIRED && exit 0"}]}
   ```
3. Codex CLI 에서 `/hm:make` 실행 (Update branch).
4. **확인 #1 — preservation**: `.codex/hooks.json` 다시 열어 `CODEX_PERMISSION_HOOK_FIRED` 라인 보존 확인.
5. **확인 #2 — runtime fire**: Codex 가 permission gate 가 fire 되는 작업 (e.g. Bash 명령) 호출 시 `CODEX_PERMISSION_HOOK_FIRED` 출력 관찰.
6. **gitignore wiring 확인**: 동일 (C7.1 #6 와 같음).

**Fail 분기**:
- Codex 가 `PermissionRequest` 의 matcher-less 두 번째 entry 를 무시 → Codex schema 가 첫 번째 entry 만 처리하도록 변경되었을 가능성 — Codex CLI changelog 확인.

### C7.3 — Codex `.codex/config.toml` user-block survives (xfail expected)

**알림**: Phase 2 render merge for HASH_COMMENT 파일은 v0.23.0 에서 **deferred** 상태 (docs/reference/preservation-matrix.md "Phase 2 render-merge follow-up" 섹션). 다음 step 은 **현재 fail 이 expected** 임을 확인하는 negative test.

1. `.codex/config.toml` 의 shipped `# @hm:user:extensions` 블록 안에 user 가 직접 다음 입력:
   ```toml
   [mcp_servers."manual-test-server"]
   command = "echo PHASE2_USER_BLOCK_SURVIVED"
   ```
2. Codex CLI 에서 `/hm:make --update` 실행.
3. **확인 (현재 expected behavior)**: `.codex/config.toml` 다시 열어 `manual-test-server` 가 **사라졌고**, shipped 의 default `# Add custom Codex configuration here...` 프로즈로 돌아왔는지 확인. 만약 보존되었다면 Phase 2 follow-up 이 이미 land 한 상태 — preservation-matrix.md 의 ⚠️ 표기를 ✅ 로 업데이트.
4. **회복 검증**: `.backup-<ts>/.codex/config.toml` 안에 `manual-test-server` 가 있어야 함 (backup = 회복 수단 per ADR-001).

이 step 의 fail (= user block survives) 는 좋은 fail. 의도된 deferral 이 closed 됐다는 signal.
