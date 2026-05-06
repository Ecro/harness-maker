# tests/cursor-compat — Phase 1 가정 검증 fixture

> 목적: harness-maker 의 **Cursor target 지원** 핵심 가정 (single source `.claude/` → 양쪽 IDE 작동) 을 사용자가 IDE 에서 직접 검증.

이 디렉토리는 **PLAN-cursor-target-support.md Phase 1 (검증 게이트)** 의 산출물.
Phase 2 (myplan) 진입 전에 A1–A4 가정을 PASS / FAIL 로 분류해야 함.

## 파일 구성

| 경로 | 역할 |
|------|------|
| `MANUAL_CHECKLIST.md` | 사용자가 IDE 에서 따라가는 step-by-step 검증 가이드 |
| `RESULTS.md` | 검증 결과 기록 템플릿 (PASS / FAIL + 스크린샷·로그) |
| `fixture/` | IDE 가 open 할 minimal harness — `.claude/` 단일 위치만 사용 |
| `fixture/.gitignore` | IDE 자동 생성 파일 (`.cursor/`, `.claude/settings.local.json` 등) 차단 |
| `fixture/.claude/agents/phase1-test-agent.md` | A1: agent 인식 검증 |
| `fixture/.claude/skills/test-skill/SKILL.md` | A3: skill auto-discovery 검증 |
| `fixture/.claude/commands/hm/test-research.md` | A4: 슬래시 명령 + Q&A 루프 검증 |
| `fixture/.claude/hooks/hooks.json` | A2: hook fire 검증 (production 과 동일 schema) |
| `fixture/.claude/settings.json` | minimal stub — production 환경에 가까운 fixture |
| `fixture/.claude/harness.yaml` | B11: targets 키 없는 옛 형식 (자동화 검증은 Phase 2 implementation 후) |

## 검증 모델

| 검증 | 모드 | 시점 |
|------|------|------|
| A1–A4 | Manual (사용자가 Cursor IDE 에서 fixture 디렉토리 open) | Phase 1 (지금) |
| B11 | 자동화 (`python -m harness_maker.cli render`) | Phase 2/3 implementation 후 |
| B13 | 자동화 (`reconcile.py` 의 `.cursor/` enumerate) | Phase 2/3 implementation 후 |
| 회귀 방지 | Manual 체크리스트 + unit/snapshot test | 1차 릴리스 이후 |

> **CI 자동화 정책**: 사용자는 Cursor IDE 사용 (CLI 사용 X). IDE 인식 검증은 자동화 불가. CI 에서는 unit + snapshot test 로 디스크 산출물 (frontmatter 형식, parser 정합성, render 결정성) 만 잡음.

## 사용 방법

1. **Claude Code 검증**: 이 fixture 디렉토리 open + `MANUAL_CHECKLIST.md` 의 Claude Code 섹션 따라하기 → `RESULTS.md` 의 Claude Code 열 채우기
2. **Cursor 검증**: 동일 fixture 디렉토리를 Cursor IDE 로 open + `MANUAL_CHECKLIST.md` 의 Cursor 섹션 따라하기 → `RESULTS.md` 의 Cursor 열 채우기
3. **분기 결정**:
   - 모두 PASS: Phase 2 (myplan) 진입
   - 일부 FAIL: PLAN-cursor-target-support.md 의 §3 "Fail 시 영향" 행 적용 → 본 PLAN 갱신 후 재 review

## 비고

- fixture 는 `.cursor/` 디렉토리를 일부러 만들지 않음 — single source `.claude/` 가정 검증이 목적
- Phase 2 에서 Cursor 별도 위치 (`.cursor/rules/`, `.cursor/commands/`) 검증이 필요해지면 `fixture-cursor-explicit/` 추가 fixture 신설
- 모든 fixture 의 frontmatter 는 Claude Code + Cursor 양쪽 cross-compat 키를 의도적으로 포함 (예: `is_background`, `readonly`, `when_to_use`, `user-invocable`)
