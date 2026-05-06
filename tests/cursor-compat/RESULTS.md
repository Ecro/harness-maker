# Phase 1 Verification Results

> **Status**: 미실행 (사용자가 IDE 에서 검증 후 채움)
> **Plan**: `work-docs/plans/PLAN-cursor-target-support.md` §3, §5 Phase 1
> **Checklist**: `MANUAL_CHECKLIST.md`

---

## 메타

| 항목 | 값 |
|------|-----|
| 검증 일시 | TBD |
| harness-maker 버전 (pyproject.toml) | TBD |
| harness-maker 버전 (.claude-plugin/plugin.json) | TBD |
| Fixture commit SHA | TBD |
| Plan 버전 (PLAN-cursor-target-support.md Created 행) | 2026-05-06 |
| Cursor 버전 | TBD |
| Claude Code 버전 | TBD |
| OS / 환경 | TBD |

> 메타 채우는 명령은 `MANUAL_CHECKLIST.md` 의 "메타 정보 채우기" 섹션 참조.

---

## 결과 표

| 가정 | 검증 항목 | Cursor 결과 | Claude Code 결과 | 비고 |
|------|-----------|-------------|------------------|------|
| **A1** | agent 목록 표시 (`A1.list`) | TBD | TBD | |
| **A1** | agent dispatch (`A1.dispatch`) | TBD | TBD | |
| **A1** | frontmatter strict-reject 없음 (`A1.frontmatter`) | TBD | TBD | `is_background`, `readonly` 키 처리 |
| **A2** | hook fire on PreToolUse (`A2.fire`) | TBD | TBD | matcher: `Edit\|Write\|Read\|Bash` |
| **A2** | PascalCase 키 호환 (`A2.case`) | TBD | TBD | Cursor 가 `PreToolUse` 그대로 받음? |
| **A3** | skill auto-discover (`A3.auto-discover`) | TBD | TBD | trigger: `phase 1 skill test` |
| **A3** | `user-invocable: true` slash 호출 (`A3.user-invocable`) | TBD | TBD | 어느 prefix 작동? `/phase1-test-skill` 또는 `/test-skill` |
| **A3** | frontmatter strict-reject 없음 (`A3.frontmatter`) | TBD | TBD | |
| **A4** | 슬래시 명령 dropdown 표시 (`A4.command-discover`) | TBD | TBD | 어느 prefix? `/hm:test-research` 또는 `/test-research` |
| **A4** | Agent Mode Q&A loop (`A4.agent-mode`) | TBD | N/A | 자연어 fallback 작동? |
| **A4** | Plan Mode AskQuestion (`A4.plan-mode-askquestion`) | TBD | N/A (항상 구조화) | 구조화 UI 표시? |
| **A4** | Plan Mode 출력 (`A4.plan-mode`) | TBD | N/A | |

> 값 표기: `PASS` / `FAIL` / `PARTIAL` (사유 비고 열에)

---

## FAIL 상세 (해당 항목별로 복사하여 채움)

### FAIL — `<예: A1.dispatch>` in `<예: Cursor>`

- **현상**:
- **로그 / 메시지**:
- **스크린샷 경로**: `tests/cursor-compat/screenshots/A1-dispatch-cursor.png`
- **PLAN §3 "Fail 시 영향" 행 적용**: (예) `.cursor/agents/` 별도 렌더 추가, single source 가정 무효화

(템플릿 — FAIL 항목별 복사)

---

## 종합 판정

- [ ] **A1–A4 모두 PASS** → Phase 2 (`/myplan`) 진입
- [ ] **일부 FAIL** → PLAN-cursor-target-support.md 갱신 후 재 review (커밋: `docs(plan): cursor-target Phase 1 verification — <항목> failed`)
- [ ] **일부 PARTIAL** → Phase 2 의 onboarding 가이드 항목으로 처리, PASS 로 분류

### 다음 단계 결정

(검증 후 채움)

---

## 참고

- 본 검증은 manual. CI 자동화는 불가 (사용자가 Cursor IDE 사용, CLI 사용 X).
- 회귀 방지는 (a) 본 fixture + manual checklist 를 release 마다 1회 재실행, (b) unit + snapshot test 로 디스크 산출물 (frontmatter, parser 정합성, render 결정성) 을 CI 에서 잡음.
- `.gitignore` 가 IDE 자동 생성 파일 (`.cursor/`, `.claude/settings.local.json` 등) 을 가려주므로 fixture 는 검증 사이에 깨끗 유지.

---

## Phase 2.8 — Production hook 작동 검증

> Phase 2.4 의 reconcile 매트릭스 대신 production-style hook command
> (`uv run --with <pkg> python -m harness_maker.gates.X`) 가 Cursor IDE 에서
> 실제로 작동하는지 검증. 절차: `MANUAL_CHECKLIST.md` 의 Phase 2.8 섹션.

| 가정 | 검증 항목 | Cursor 결과 | Claude Code 결과 | 비고 |
|------|-----------|-------------|------------------|------|
| **Phase 2.8** | hook fire on PreToolUse (`Phase2.8.fire`) | TBD | TBD | matcher: 우리 production hooks.json 의 PreToolUse |
| **Phase 2.8** | `uv run --with <path>` resolves (`Phase2.8.uv-resolves`) | TBD | TBD | jinja `harness_maker_src_path` 가 정확한 absolute path 인지 |
| **Phase 2.8** | `python -m harness_maker.gates.X` 모듈 로드 (`Phase2.8.module-loads`) | TBD | TBD | dev dep 또는 plugin install 필요 여부 |
| **Phase 2.8** | hook command exit-clean (`Phase2.8.exit-clean`) | TBD | TBD | graceful exit 0 / 2 (block); stack trace 부재 |
