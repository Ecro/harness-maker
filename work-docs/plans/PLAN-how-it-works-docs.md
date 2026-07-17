---
type: plan
task_slug: how-it-works-docs
status: complete
created: 2026-05-09
tags: [harness-maker, plan, documentation, korean, reference]
interview_rounds: 3
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "harness-maker 플러그인 사용자 대상 한글 종합 동작 설명 문서 작성 (docs/HOW-IT-WORKS.md, v0.7.1 기준)"
---

# harness-maker HOW-IT-WORKS 문서 작성 계획

## 🎯 Executive Summary

**What:** `docs/HOW-IT-WORKS.md` — harness-maker 플러그인 사용자를 위한 한글 종합 동작 설명 문서 신규 작성.

**Why:** 현재 TECH_SPEC.md(1,587줄)와 ARCHITECTURE.md는 구현자/기여자 관점으로 작성되어 있고, README는 Quick Start 수준에 그침. 플러그인 사용자가 "이 명령을 실행하면 내부에서 무슨 일이 일어나는가"를 이해할 수 있는 문서가 없음.

**Key Decisions:**
- 워크플로우 중심 구조 (→ ADR-001)
- 단일 파일 `docs/HOW-IT-WORKS.md` (→ ADR-002)
- 0.7.1 스냅샷, 수동 유지보수 (→ ADR-003)

**Coverage:** 14 commands + 11 skills + 12 agents + 5 hook 이벤트 유형 = 37개 컴포넌트 전체.

**Scope lock-in (Phase 0 확인):**
- commands: 14개 (`.claude/commands/hm/`)
- skills: 11개 (`.claude/skills/`)
- agents: 12개 (`.claude/agents/`)
- hook 이벤트: 5종 (PreToolUse, PostToolUse, PreCompact, SessionStart, Stop)

---

## 📚 Prior Work

| 문서 | 역할 | 본 계획에서 활용 방식 |
|------|------|--------------------|
| TECH_SPEC.md (1,587줄) | 구현 사양 | §3 단계별 절차 사실 확인 |
| ARCHITECTURE.md | 아키텍처 다이어그램 | §1, §2 개요 참고 |
| docs/reference/autoloop-pattern.md | /hm:loop 패턴 | §4.5 시나리오 트레이스 |
| docs/reference/block-merge-spec.md | 블록 병합 스펙 | §3.4 Execute 상세 |
| README.md | Quick Start | 본 문서의 선행 참고로 언급 |

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question (요약) | Options | Choice | Note |
|---|-------|----------|----------------|---------|--------|------|
| 1 | 독자 대상 | Scope boundaries | 문서의 주요 독자는? | 플러그인 사용자 / 내부 기여자 / 둘 다 | **플러그인 사용자** | Python 내부(모듈/함수) 설명 불필요 |
| 2 | 저장 위치 | Architecture | 어디에 저장? | docs/HOW-IT-WORKS.md / docs/guide/ 분할 / README 통합 | **docs/HOW-IT-WORKS.md** | 단일 파일, 검색·공유 용이 |
| 3 | 문서 구조 | Architecture | 어떻게 구조화? | 워크플로우 중심 / 컴포넌트 알파벳순 / 1부+2부 혼합 | **워크플로우 중심** | — |
| 4 | 설명 깊이 | Scope | 각 컴포넌트당 얼마나? | 목적+절차+연동 / 목적+입출력만 / 목적만 | **목적+단계별 절차+연동 관계** | — |
| 5 | 기술 용어 | Scope | 한글 번역 vs 영어 원어? | 영어 그대로 / 한글+영어 병기 | **영어 그대로** | skill, agent, hook, worktree 등 원어 유지 |
| 6 | Fusion commands | Scope | /hm:exec-rev-wrap-ver 등? | 간략 언급+개별 단계 링크 / 동일 상세 / 기본 7단계만 | **간략 언급+링크** | — |
| 7 | 유지보수 | Risk tolerance | 어떻게 유지보수? | 0.7.1 스냅샷 / 템플릿 자동화 / 사람이 PR | **0.7.1 스냅샷** | 추후 수동 업데이트 |
| 8 | 시나리오 예제 | Testing depth | 실행 트레이스 포함? | 포함(상세 흐름) / 알고리즘만 / 간단 예제 | **포함** (/hm:loop 단계별 트레이스) | — |

---

## 📐 Architecture Decision Records

### ADR-001: 워크플로우 중심 구조 채택
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** 문서 독자가 "이 명령을 실행하면 무슨 일이 일어나는가"를 추적하는 플러그인 사용자. 컴포넌트 알파벳순 나열보다 실행 흐름 중심이 맥락 이해에 유리함.
**Decision:** 1부 = 워크플로우 시나리오(단계별 명령 상세), 2부 = 컴포넌트 레퍼런스(skills/agents/hooks) 구조 채택.
**Consequences:**
- ✅ 사용자가 자신의 작업 흐름에서 각 컴포넌트의 역할을 맥락 속에서 파악 가능
- ⚠️ 특정 컴포넌트를 직접 찾으려면 2부 레퍼런스 섹션으로 이동해야 함 (목차로 완화)
**Rejected alternatives:**
- 컴포넌트 백과사전(알파벳순) — 연동 흐름이 보이지 않아 "왜 이 skill이 여기서 쓰이는가" 파악 불가
**Source:** Interview #3

### ADR-002: 단일 파일 (docs/HOW-IT-WORKS.md)
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** docs/guide/ 분할(commands.md, skills.md, …) vs 단일 파일 선택.
**Decision:** 단일 파일 채택.
**Consequences:**
- ✅ grep/검색/공유/오프라인 열람 용이. 목차(ToC) 앵커로 내부 탐색 가능.
- ⚠️ 분량이 많아지면 스크롤이 불편. 목차를 상세히 작성해 완화.
**Rejected alternatives:**
- docs/guide/ 분할 — 파일 간 크로스 링크 유지 비용, IDE에서 탭 이동 번거로움
**Source:** Interview #2

### ADR-003: 0.7.1 스냅샷, 수동 유지보수
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** 자동화(Jinja2 템플릿화)하면 /hm:make 실행마다 재생성 가능하나, 구현 비용 대비 0.7.1 ROI 부족. 나중에 버전 드리프트가 생기면 추가 투자를 결정할 수 있음.
**Decision:** 현재 0.7.1 기준 스냅샷으로 작성. 파일 상단에 버전/날짜 명시. 이후 코드 변경 시 별도 문서 PR로 수동 업데이트.
**Consequences:**
- ✅ 즉시 구현 가능, 복잡도 0
- ⚠️ 버전 업 시 문서 지체(drift) 발생 가능. "0.7.1 기준" 명시로 독자에게 알림.
**Rejected alternatives:**
- 템플릿 자동 생성 — 구현 비용 과대
- 사람이 PR — 동일하지만 책임 소재만 명시한 것, 현 결정과 동일 의미
**Source:** Interview #7

---

## 🏗️ Technical Design

### Non-Goals (명시적 범위 제외)

- **설치/업그레이드 절차** — README에서 커버
- **트러블슈팅 가이드** — 별도 이슈/위키
- **Python 내부 구현 상세** — 모듈, 함수, 데이터 모델 설명 불필요
- **타 플러그인/도구 비교** — 본 문서 범위 밖
- **버전 간 마이그레이션 가이드** — CHANGELOG에서 커버

### 문서 최종 구조

```
docs/HOW-IT-WORKS.md
│
├── 머리말 (버전, 독자, 목차)
│
├── 1. harness-maker란?
│   ├── 무엇을 하는가
│   ├── 핵심 철학 (LLM 판단 최대 활용)
│   └── 주요 구성요소 한눈에 보기
│
├── 2. 전체 워크플로우
│   ├── 7단계 흐름도 (ASCII)
│   ├── 단계 간 데이터 흐름
│   └── 언제 어느 단계를 쓰는가
│
├── 3. 7단계 상세 (각 단계: 목적 / 절차 / 호출 컴포넌트 / 입출력)
│   ├── 3.1 Research (/hm:research)
│   ├── 3.2 Spec (/hm:spec)
│   ├── 3.3 Plan (/hm:plan)
│   ├── 3.4 Execute (/hm:execute)
│   ├── 3.5 Review (/hm:review)
│   ├── 3.6 Verify (/hm:verify)
│   └── 3.7 Wrapup (/hm:wrapup)
│
├── 4. 통합 명령 (Fusion Commands)
│   ├── 4.1 /hm:res-spec-plan
│   ├── 4.2 /hm:exec-rev
│   ├── 4.3 /hm:exec-rev-wrap
│   ├── 4.4 /hm:exec-rev-wrap-ver
│   └── 4.5 /hm:loop — 전체 시나리오 트레이스
│
├── 5. Skills 레퍼런스 (11개 각각: 목적 / 호출 시점 / 절차 / 연동)
│   ├── autoloop-driver
│   ├── worktree-isolator
│   ├── verify-before-completion
│   ├── security-scanner
│   ├── refdocs-search
│   ├── relevance-filter
│   ├── research-crawler
│   ├── context-linter
│   ├── conditional-router
│   ├── agent-quality-rubric
│   └── ai-readiness-rubric
│
├── 6. Agents 레퍼런스 (12개 각각: 목적 / 권한 범위 / 절차 / 호출 주체)
│   ├── autoloop-coder
│   ├── executor
│   ├── code-reviewer
│   ├── security-reviewer
│   ├── security-auditor
│   ├── performance-reviewer
│   ├── concurrency-reviewer
│   ├── ux-reviewer
│   ├── test-reviewer
│   ├── consensus-arbiter
│   ├── plan-validator
│   └── stuck
│
├── 7. Hooks 레퍼런스
│   ├── 7.1 PreToolUse (permission-gate, worktree-gate)
│   ├── 7.2 PostToolUse (telemetry, post-write-reminder)
│   ├── 7.3 PreCompact (flush-session)
│   ├── 7.4 SessionStart (sessionstart-drift)
│   └── 7.5 Stop (현재 핸들러 없음)
│
├── 8. 특수 명령
│   ├── 8.1 /hm:refresh
│   └── 8.2 /hm:ai-readiness
│
└── 9. 부록: 핵심 설정 파일
    ├── harness.yaml
    ├── .claude/settings.json (permissions)
    └── hooks.json
```

### 소스 파일 → 문서 섹션 매핑

| 소스 파일 | 문서 섹션 |
|----------|----------|
| `.claude/commands/hm/research.md` | §3.1 |
| `.claude/commands/hm/spec.md` | §3.2 |
| `.claude/commands/hm/plan.md` | §3.3 |
| `.claude/commands/hm/execute.md` | §3.4 |
| `.claude/commands/hm/review.md` | §3.5 |
| `.claude/commands/hm/verify.md` | §3.6 |
| `.claude/commands/hm/wrapup.md` | §3.7 |
| `.claude/commands/hm/res-spec-plan.md` | §4.1 |
| `.claude/commands/hm/exec-rev.md` | §4.2 |
| `.claude/commands/hm/exec-rev-wrap.md` | §4.3 |
| `.claude/commands/hm/exec-rev-wrap-ver.md` | §4.4 |
| `.claude/commands/hm/loop.md` | §4.5 |
| `.claude/commands/hm/refresh.md` | §8.1 |
| `.claude/commands/hm/ai-readiness.md` | §8.2 |
| `.claude/skills/*/SKILL.md` (11개) | §5 |
| `.claude/agents/*.md` (12개) | §6 |
| `.claude/hooks/hooks.json` | §7 |
| TECH_SPEC.md | §1, §2, §3 (사실 확인) |
| docs/reference/autoloop-pattern.md | §4.5 |
| docs/ARCHITECTURE.md | §1, §2 |

---

## 📝 Implementation Plan

### Phase 0: 컴포넌트 카운트 lock-in [완료]

**Scope:** 실제 디렉토리 파일 수 확인 및 목표 숫자 검증
**Exit criterion:** 아래 수치가 plan 목표(14/11/12)와 일치
**Risk:** low
**Rollback:** N/A (읽기 전용)

실측 결과:
- `.claude/commands/hm/`: 14개 ✅
- `.claude/skills/`: 11개 ✅
- `.claude/agents/`: 12개 ✅
- hooks.json 이벤트: 5종 ✅

---

### Phase 1: Source 읽기 및 노트 작성

**Scope:**
- 14개 command .md 파일 전체 읽기
- 11개 skill SKILL.md 전체 읽기
- 12개 agent .md 전체 읽기
- `.claude/hooks/hooks.json` 읽기
- TECH_SPEC.md §1-4 핵심 절 읽기
- docs/reference/autoloop-pattern.md 읽기
- 노트를 `work-docs/notes/how-it-works-research.md`에 기록

**Exit criterion:**
- `work-docs/notes/how-it-works-research.md` 존재
- 37개 컴포넌트명 모두 포함됨 (grep으로 확인)
  - commands 14개: research, spec, plan, execute, review, verify, wrapup, loop, refresh, ai-readiness, res-spec-plan, exec-rev, exec-rev-wrap, exec-rev-wrap-ver
  - skills 11개: autoloop-driver, worktree-isolator, verify-before-completion, security-scanner, refdocs-search, relevance-filter, research-crawler, context-linter, conditional-router, agent-quality-rubric, ai-readiness-rubric
  - agents 12개: autoloop-coder, code-reviewer, concurrency-reviewer, consensus-arbiter, executor, performance-reviewer, plan-validator, security-auditor, security-reviewer, stuck, test-reviewer, ux-reviewer

**Risk:** low
**Rollback:** N/A (읽기 전용, 노트 파일 삭제)

---

### Phase 2: 문서 뼈대 + 섹션 1-2

**Scope:**
- `docs/HOW-IT-WORKS.md` 신규 생성
- 머리말 (버전 명시: "harness-maker 0.7.1 기준 · 2026-05-09")
- 목차 (ToC, 앵커 링크)
- §1 harness-maker란? (개요, 핵심 철학, 구성요소 지도)
- §2 전체 워크플로우 (ASCII 흐름도, 단계 간 데이터 흐름, 사용 결정 가이드)

**Exit criterion:**
- `docs/HOW-IT-WORKS.md` 존재
- "harness-maker 0.7.1" 텍스트 포함
- "## 1." + "## 2." 헤더 포함
- ASCII 흐름도 (`Research → Spec → ...`) 포함

**Risk:** low
**Rollback:** `git reset HEAD~1` (이 Phase 완료 후 commit)

---

### Phase 3: §3 — 7단계 상세

**Scope:** `### 3.1 Research` ~ `### 3.7 Wrapup`. 각 단계마다:
- 목적 (한 문장)
- 언제 실행하는가 (전제 조건)
- 단계별 절차 (numbered list)
- 이 단계에서 호출하는 skill / agent
- 출력물 (생성되는 파일/아티팩트)
- 주의사항 / 제약

**Exit criterion:**
- 7개 `### 3.` 서브섹션 존재
- research, spec, plan, execute, review, verify, wrapup 단어 각각 `grep` 매치

**Risk:** low
**Rollback:** `git reset HEAD~1`

---

### Phase 4: §4 — Fusion commands + /hm:loop 시나리오 트레이스

**Scope:** `### 4.1` ~ `### 4.5`
- 4.1~4.4: 각 fusion command를 "= A + B + C 를 순서대로 실행" 한 문단 + 구성 단계 링크
- 4.5 `/hm:loop`: feature/improve 두 모드 설명 + **iteration 전체 흐름을 단계별 numbered list로** (loop 진입 → interview → plan → worktree 생성 → execute → review → verify → wrapup → 다음 iter or 완료)

**Exit criterion:**
- `### 4.5` 존재
- `/hm:loop` 아래 numbered list ≥ 8항목 (iteration 전 단계 커버)

**Risk:** low
**Rollback:** `git reset HEAD~1`

---

### Phase 5: §5-6 — Skills + Agents 레퍼런스

**Scope:** 23개 서브섹션 (11 skills + 12 agents). 각 항목마다:
- **Skills:** 목적 / 언제 호출되는가 (트리거) / 동작 절차 / 연동 컴포넌트
- **Agents:** 목적 / 권한 범위 (allow/deny 요약) / 동작 절차 / 호출 주체

**Exit criterion:**
- 11개 skill 이름 모두 `grep` 매치: autoloop-driver, worktree-isolator, verify-before-completion, security-scanner, refdocs-search, relevance-filter, research-crawler, context-linter, conditional-router, agent-quality-rubric, ai-readiness-rubric
- 12개 agent 이름 모두 `grep` 매치: autoloop-coder, code-reviewer, concurrency-reviewer, consensus-arbiter, executor, performance-reviewer, plan-validator, security-auditor, security-reviewer, stuck, test-reviewer, ux-reviewer

**Risk:** low
**Rollback:** `git reset HEAD~1`

---

### Phase 6: §7-9 — Hooks + 특수 명령 + 부록

**Scope:**
- §7 Hooks: 5가지 이벤트 유형 각각의 트리거 조건, 실행 모듈, 동작
  - Stop 이벤트는 현재 핸들러 없음을 명시
- §8 특수 명령: /hm:refresh (크롤러 + 관련성 필터 파이프라인), /hm:ai-readiness (3-레이어 평가)
- §9 부록: harness.yaml 주요 필드, settings.json permissions 구조, hooks.json 구조

**Exit criterion:**
- PreToolUse, PostToolUse, PreCompact, SessionStart, Stop 5개 키워드 모두 `grep` 매치
- "hm:refresh" + "hm:ai-readiness" 모두 포함

**Risk:** low
**Rollback:** `git reset HEAD~1`

---

### Phase 7: 검증

**Scope:** 완성 문서 품질 검증 (4-항목 grep 체크)

**Exit criterion:**
1. `grep -c "### " docs/HOW-IT-WORKS.md` ≥ 30 (서브섹션 수)
2. 37개 컴포넌트명 모두 grep 매치 (Phase 5 exit criterion 동일)
3. `grep -c "^\d\+\." docs/HOW-IT-WORKS.md` ≥ 20 (/hm:loop 트레이스 포함 확인)
4. PreToolUse, PostToolUse, PreCompact, SessionStart 4개 각각 grep 매치

**Risk:** low
**Rollback:** 실패한 섹션 Phase로 회귀 후 `git reset HEAD~1`

---

## 🧪 Testing Strategy

**자동 검증 (Phase 7):**
- grep 기반 컴포넌트명 누락 탐지
- 서브섹션 수 체크
- /hm:loop 트레이스 numbered list 존재 확인

**수동 검증 (문서 작성 후):**
- 문서를 처음부터 읽으며 흐름 이해 가능 여부 확인
- 임의로 한 컴포넌트(예: worktree-isolator)를 목차에서 찾아 레퍼런스 섹션 탐색 가능한지 확인

**단위 테스트:** 해당 없음 (문서 생성 태스크)

---

## ⚠️ Risks & Mitigation

| 위험 | 가능성 | 충격 | 완화 방안 |
|------|--------|------|----------|
| 소스 파일(.md)과 실제 동작 간 괴리 | low | medium | Phase 1에서 TECH_SPEC.md와 교차 확인. 불일치 발견 시 TECH_SPEC 우선. |
| 문서 분량 과다 | medium | low | Non-Goals 명시. 각 컴포넌트당 코드 레벨 설명 배제. |
| 컴포넌트 누락 | low | medium | Phase 7 grep 검증으로 탐지. |
| 버전 드리프트 (0.8.x 이후) | high | low | 파일 상단에 "0.7.1 기준" 명시. |
| Phase 간 롤백 복잡성 | low | low | Phase별 commit 단위 확립 → `git reset HEAD~1` 단일 rollback 경로. |

---

## ✅ Success Criteria

- [ ] `docs/HOW-IT-WORKS.md` 신규 생성, 파일 상단에 "0.7.1" 버전 명시
- [ ] 목차(ToC)에 모든 주요 섹션 앵커 링크 포함
- [ ] 7단계 단계별 상세 절차 (§3)
- [ ] 4개 fusion command 간략 설명 + 링크 (§4.1~4.4)
- [ ] /hm:loop 전체 시나리오 트레이스 ≥ 8단계 numbered list (§4.5)
- [ ] 11개 skill 각각 설명 (§5)
- [ ] 12개 agent 각각 설명 (§6)
- [ ] 5가지 hook 이벤트 유형 모두 설명 (§7)
- [ ] /hm:refresh, /hm:ai-readiness 설명 (§8)
- [ ] 한국어로 작성, 기술 용어(skill/agent/hook/worktree)는 영어 그대로

---

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION → NEEDS_REVISION_RESOLVED

| # | 경고 | 해결 방식 |
|---|------|----------|
| W1 | Phase 1 exit criterion 검증 불가 | `work-docs/notes/how-it-works-research.md` 파일 경로 + 37개 컴포넌트명 grep 기준으로 수정 |
| W2 | 컴포넌트 개수(14/11/12) 검증 부재 | Phase 0 추가 — 실제 디스크 카운트로 lock-in. 실측 완료(14/11/12 확인). |
| W3 | Phase 7 검증이 헤더 수에만 의존 | grep 4항목으로 교체: 서브섹션 수 + 37개 컴포넌트명 + 트레이스 numbered list + hook 이벤트명 |
| W4 | Non-Goals 섹션 부재 | §Technical Design에 Non-Goals 5항목 명시 추가 |
| S1 | Rollback 전략이 phase 의존성 무시 | Phase별 commit 단위 확립 → `git reset HEAD~1` 단일화. Risk 표에 추가. |
| S2 | ADR에 거부 대안 없음 | 각 ADR에 Rejected alternatives 추가 |
