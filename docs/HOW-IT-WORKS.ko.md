[🇺🇸 English](HOW-IT-WORKS.md)

# harness-maker 동작 원리 완전 가이드

> **대상 독자**: harness-maker 를 처음 접하는 개발자, 또는 내부 동작을 깊이 이해하고 싶은 사용자.
> **버전**: 0.7.1 기준. 코드 세부 구현이 아닌 **절차·흐름·책임** 중심 설명.

---

## 목차

1. [harness-maker 란?](#1-harness-maker-란)
2. [전체 아키텍처](#2-전체-아키텍처)
3. [7단계 원자 워크플로우](#3-7단계-원자-워크플로우)
   - 3.1 [/hm:research — 탐색](#31-hmresearch--탐색)
   - 3.2 [/hm:spec — 인수 조건](#32-hmspec--인수-조건)
   - 3.3 [/hm:plan — 구현 계획](#33-hmplan--구현-계획)
   - 3.4 [/hm:execute — TDD 구현](#34-hmexecute--tdd-구현)
   - 3.5 [/hm:review — 코드 리뷰](#35-hmreview--코드-리뷰)
   - 3.6 [/hm:verify — 완료 검증](#36-hmverify--완료-검증)
   - 3.7 [/hm:wrapup — 커밋 마무리](#37-hmwrapup--커밋-마무리)
4. [퓨전 명령](#4-퓨전-명령) <!-- @hm:axis-removed -->
5. [/hm:loop — 자동 반복 루프](#5-hmloop--자동-반복-루프)
6. [특수 명령](#6-특수-명령)
   - 6.1 [/hm:refresh — 안티-rot 업데이트](#61-hmrefresh--안티-rot-업데이트)
   - 6.2 [/hm:ai-readiness — AI 준비도 분석](#62-hmai-readiness--ai-준비도-분석)
   - 6.3 [/hm:personalization-audit — Composite-score 루브릭](#63-hmpersonalization-audit--composite-score-루브릭)
7. [스킬 참조](#7-스킬-참조)
8. [에이전트 참조](#8-에이전트-참조)
9. [훅 상세](#9-훅-상세)
10. [부록](#10-부록)
11. [특장점: 일반 AI 워크플로우와 무엇이 다른가](#11-harness-maker-특장점-일반-ai-워크플로우와-무엇이-다른가)
    - 11.1 [3-tier 메모리 계층](#111-3-tier-메모리-계층--세션을-넘어-지식이-축적된다)
    - 11.2 [실패 카운트 → 자동 개선 제안](#112-실패-카운트--자동-개선-제안-루프)
    - 11.3 [PreCompact 훅 + checkpoint:compaction](#113-precompact-훅--checkpointcompaction--컨텍스트-압축에도-작업이-유실되지-않는다)
    - 11.4 [프롬프트 캐시 진단 (Layer 3)](#114-프롬프트-캐시-진단-layer-3--왜-캐시-미스가-나는지-원인별로-분류한다)
    - 11.5 [Context Linter](#115-context-linter--프롬프트-크기-통제가-곧-캐시-효율이다)
    - 11.6 [Conditional Router](#116-conditional-router--필요한-리뷰어만-호출해-토큰을-아낀다)
    - 11.7 [2-pass 리댁션 (+47pp)](#117-2-pass-리댁션-47pp-precision--메타데이터-앵커링을-차단한다)
    - 11.8 [consensus-arbiter](#118-consensus-arbiter--같은-위치-를-넘어-같은-이유-를-따진다)
    - 11.9 [ADR 기반 결정 영속화](#119-adr-기반-결정-영속화--설계-선택의-why-가-코드베이스에-산다)
    - 11.10 [Fingerprint + Block-Merge Marker](#1110-생성-파일-fingerprint--block-merge-marker--업그레이드가-사용자-수정을-덮지-않는다)
    - 11.11 [Drift Gate + pending-drift.md](#1111-drift-gate--pending-driftmd--범위-이탈이-다음-세션에-전달된다)
    - 11.12 [레퍼런스 문서 2-tier 검색](#1112-레퍼런스-문서-2-tier-검색--대용량-지식-베이스도-문맥에-맞는-것만-읽는다)
    - 11.13 [안티-rot 시스템](#1113-안티-rot-시스템--하네스-자체가-낡지-않는다)
    - 11.14 [7차원 AI Readiness + 루브릭 YAML](#1114-7차원-ai-readiness--확장-가능한-루브릭-yaml)
    - 11.15 [워크트리 격리의 결정적 실행](#1115-워크트리-격리의-결정적deterministic-실행)
    - 11.16 [무엇이 실제로 에이전트 경계를 강제하는가](#1116-무엇이-실제로-에이전트-경계를-강제하는가)
    - 11.17 [단일 커밋 계약 + WHY 중심 커밋 메시지](#1117-단일-커밋-계약--why-중심-커밋-메시지)
    - 11.18 [LLM-판단 우선 아키텍처](#1118-llm-판단-우선-아키텍처--규칙-기반을-피한다)
    - 11.19 [원자 파일 쓰기](#1119-원자-파일-쓰기--인터럽트에도-파일이-깨지지-않는다)
    - 11.20 [100% 로컬 텔레메트리](#1120-100-로컬-텔레메트리)
    - 11.21 [Deep Interview (spec/plan)](#1121-deep-interview--추측-대신-대화로-아키텍처를-잠근다)
    - 11.22 [loop 적응형 인터뷰 + 수렴 루프](#1122-hmloop-적응형-인터뷰--수렴-루프--반복-실행이-목표를-향해-수렴한다)
    - 11.23 [TDD Phase A.5 테스트 품질 게이트](#1123-tdd-phase-a5-게이트--테스트가-진짜-red-인지-구현-전에-검증한다)
    - 11.24 [`stuck` 에스컬레이션 에이전트](#1124-stuck-에스컬레이션-에이전트--블로킹이-두-번-반복되면-전용-분석가가-개입한다)
    - 11.25 [6-checkpoint verify 게이트](#1125-6-checkpoint-verify-게이트--완료를-diff-와-건강-지표로-이중-검증한다)

---

## 1. harness-maker 란?

harness-maker 는 **Claude Code 와 Cursor 양쪽 IDE** 에서 동작하는 듀얼 플러그인이다.
핵심 역할은 하나: **LLM 기반 개발 워크플로우를 구조화**하여 사람이 코드를 직접 쓰던
방식과 같은 수준의 품질 보증(리뷰·테스트·보안 검사)을 AI-driven 개발에도 적용한다.

### 무엇을 제공하는가

| 범주 | 내용 |
|------|------|
| **명령(Commands)** | `/hm:` 접두어 슬래시 명령 14개 (원자 7 + 퓨전 4 + 특수 2 + 루프 1) |
| **스킬(Skills)** | 명령에서 호출하는 재사용 능력 모듈 11개 |
| **에이전트(Agents)** | 특정 역할의 서브-에이전트 12개 |
| **훅(Hooks)** | 도구 호출 전후에 자동 실행되는 이벤트 핸들러 5종 |

### 설계 원칙

- **LLM 판단 우선**: 패턴 매칭보다 LLM 이 문맥을 읽고 직접 판단
- **원자성**: 각 단계는 독립 실행 가능. 단계 간 결합은
  `/hm:loop --per-iter-stages` 또는 autopilot 이 담당
- **워크트리 격리**: 구현 변경은 `.worktrees/<name>-<ts>/` 안에서만 발생 — 메인 브랜치 보호
- **커밋은 wrapup 이 한 번만**: 여러 단계를 거쳐도 커밋은 wrapup 이 단 한 번 생성
- **외부 전송 없음**: 모든 텔레메트리는 100% 로컬

---

## 2. 전체 아키텍처

```
┌──────────────────────────────────────────────────────────────────────┐
│                     사용자 슬래시 명령 호출                           │
│          /hm:research  /hm:spec  /hm:plan  /hm:execute  ...          │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      harness.yaml (단일 진실 원천)                    │
│   locale, preset (Side/Production), dev_mode, targets (claude/cursor) │
│   worktree.scope, max_review_rounds, preferred_model, ...            │
└──────────┬───────────────────────────────────────┬───────────────────┘
           │                                       │
           ▼                                       ▼
┌─────────────────────┐               ┌────────────────────────────────┐
│   스킬 (11개)        │               │      에이전트 (12개)            │
│  context-linter      │               │  code-reviewer                 │
│  worktree-isolator   │               │  plan-validator                │
│  conditional-router  │◄──호출──────►│  test-reviewer                 │
│  verify-before-      │               │  consensus-arbiter             │
│    completion        │               │  stuck (에스컬레이션)           │
│  security-scanner    │               │  autoloop-coder                │
│  refdocs-search      │               │  ...                           │
│  relevance-filter    │               └────────────────────────────────┘
│  research-crawler    │
│  ai-readiness-rubric │
│  agent-quality-rubric│
│  autoloop-driver     │
└─────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        훅 (5 이벤트 타입)                             │
│  SessionStart → 드리프트 감지                                         │
│  PreToolUse   → 권한 게이트 / 워크트리 게이트                          │
│  PostToolUse  → 텔레메트리 / 쓰기 후 리마인더                          │
│  PreCompact   → 세션 컨텍스트 플러시                                   │
│  Stop         → (현재 비어있음)                                        │
└──────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      디스크 산출물                                     │
│  work-docs/PLAN-{slug}.md     work-docs/RESEARCH-{slug}.md           │
│  specs/SPEC-{slug}.md         docs/REVIEW-{slug}-{date}.md           │
│  .claude/memory/{wiki,failures,session}.md                           │
│  .claude/observability/{metrics,security,refresh}/                   │
└──────────────────────────────────────────────────────────────────────┘
```

### 파일 구조 요약

```
<project>/
├── harness.yaml              ← 하네스 전체 설정 (타깃, preset, 언어 등)
├── .claude/
│   ├── commands/hm/          ← 슬래시 명령 파일들
│   ├── skills/               ← 스킬 SKILL.md 파일들
│   ├── agents/               ← 에이전트 정의 파일들
│   ├── hooks/hooks.json      ← 훅 이벤트 정의
│   ├── memory/               ← wiki.md / failures.md / session/
│   └── observability/        ← metrics.jsonl / security/ / refresh/
│       └── adaptive/         ← overrides.jsonl (0.12.0+: M18 yaml-override 텔레메트리)
├── work-docs/
│   ├── PLAN-{slug}.md        ← 구현 계획
│   └── RESEARCH-{slug}.md    ← 리서치 결과
├── specs/
│   └── SPEC-{slug}.md        ← 인수 조건
└── .worktrees/               ← 격리된 구현 작업 공간 (gitignored)
    └── execute-<ts>/
```

### 0.12.0 신규 소스 모듈 (recommendation + telemetry + audit)

Personalization-depth 트랙 지원을 위해 0.12.0 에서 Python 모듈 4개 + 루브릭 YAML 1개가 추가되었다. 기존 M1-M14 모듈 옆에 위치하며 같은 규약을 따른다 (`models.py` 의 typed contract, atomic write, `tests/unit/` 테스트):

```
src/harness_maker/
├── recommendation.py          ← M16: Confidence 버킷 기반 추천 레지스트리
├── detection_cache.py         ← M15: manifest-mtime + 24h 상한 프로필 캐시
├── foreign_config.py          ← M17: foreign AI config 감지 + LLM 매핑 + 적용
├── personalization_audit.py   ← M19: composite-score 루브릭 러너 (/hm:personalization-audit)
└── rubrics/
    └── personalization.yaml   ← ADR-011 v0 루브릭 (locked 공식 + tier 경계)
```

---

## 렌더 파이프라인

`/harness-maker:make` (및 렌더된 `/hm:make`)는 `harness.yaml`을 디스크 위 하네스로 만든 뒤,
git 결정까지 끝까지 가이드한다. 이 흐름은 의도적으로 git worktree 안에서 돌지 **않는다** —
`make`는 실제 `.claude/`에 쓰고, 안전성은 backup + reconcile + 읽기 전용 미리보기에서 오며,
이는 비-git 프로젝트도 작동하게 한다.

**1. 해석 + 미리보기 (재렌더 한정).** `.claude/`가 이미 있고 비어있지 않으면 make는 먼저
`--dry-run`을 돌려 NEW / REPLACE / KEEP / MERGE 카운트(KEEP = 내 편집이 그대로 보존되는 파일;
MERGE = `@hm:user:*` 블록이 새 템플릿에 block-merge됨)를 보여주고, 쓰기 전에 확인을 받는다.
신규 설치는 미리보기를 건너뛰고 바로 적용. 덮어쓰기 전에 기존 생성물은 `.backup-<ts>/`
(자동 gitignore)로 복사된다.

**2. 적용 + 설명.** 파일이 쓰여지고, CLI가 안정적인 `render-summary:` 라인
(`files= keep= merge= targets=`)을 내보내면 슬래시 명령이 이를 사용자 locale의 평이한 설명으로
바꾼다 — 무엇이 바뀌고, 무엇이 보존되고, 현재 버전. 신규 설치는 조용하다: structural-health
스캔은 **깨끗하면 조용**하고 **실제 P0/P1이 있을 때만 loud**하다 (전체 스캔은 언제든
`/hm:health`).

**3. git 처분 — 마지막 한 걸음.** 파일이 의도대로 git에 들어가기 전까지 렌더는 "끝"이 아니다.
`harness-maker git-status`가 선택된 모든 target root(`.claude/`, 그리고 해당 target이면
`.cursor/`, `.codex/`, `.agents/`, `AGENTS.md`)에 걸쳐 렌더 manifest를 — 운영 churn은 제외하고 —
검사해 다음 중 하나를 보고한다:

| 상태 | make의 동작 |
|------|------------|
| git 저장소 아님 | 알려줌; 추적을 원하면 `git init` 제안; git 명령 실행 안 함 |
| 미결정 (tracked도 ignored도 아님) | **중립적으로** 질문 — *commit*(팀과 공유) 또는 *gitignore*(로컬 유지). 권장 옵션 없음. |
| 이미 commit됨 | 없음 — 단, 재렌더가 새 파일을 추가했으면 그것만 staging 제안 (전체 재질문 아님) |
| 이미 gitignore됨 | 없음 |

결정은 **매 실행마다 git 상태에서 추론, 저장 안 함**이라 재렌더가 다시 묻지 않는다. churn
(`observability/`, iter-receipts, `.backup-*`)이 이미 gitignore되어 commit이 깨끗하고;
`git-ignore-roots`는 target root 전체를 ignore하며 쓰기가 적용되지 않으면 **loud하게 실패**하므로
슬래시 명령이 거짓 성공을 보고할 수 없다.

---

## 3. 7단계 원자 워크플로우

7단계는 각각 독립된 슬래시 명령으로 호출 가능하다. 순서대로 실행하면 완전한 개발 사이클이 된다.

```
research → spec → plan → execute → review → verify → wrapup
```

단계마다 **고유한 책임**이 있고, 이전 단계의 산출물을 입력으로 받는다.

---

### 3.1 /hm:research — 탐색

**목적**: 새로운 기능 구현 전 필요한 정보를 체계적으로 수집한다.

#### 실행 절차

**Phase 0 — 탐색 깊이 결정**

`--deep` 플래그 유무로 두 경로로 분기된다.

- `--deep` 없음: 코드베이스 + 메모리 + 기존 PLANs 만 탐색
- `--deep` 있음: 위에 더해 외부 소스(라이브러리 문서, 웹 검색, refdocs) 까지 탐색

**Phase 1 — 정보 수집**

4개 소스에서 병렬로 수집:

1. **코드베이스 탐색**: 관련 파일/모듈 식별, 기존 패턴 확인
2. **메모리 탐색**: `.claude/memory/wiki.md`, `failures.md` 에서 과거 실패/교훈 확인
3. **기존 PLAN 탐색**: `work-docs/PLAN-*.md` 에서 유사 작업의 선례 확인
4. **외부 소스** (`--deep` 시): `refdocs-search` 스킬 + Context7 MCP + 웹 검색

`refdocs-search` 스킬을 통해 참조 문서 폴더(`ref_folders`)에서 2-tier 검색을 수행한다:
- Tier 1: 경량 ripgrep 인덱스로 관련 파일 후보 추림
- Tier 2: 원본 파일 직접 Read 로 실제 내용 확인

**Phase 2 — 분석**

`relevance-filter` 스킬이 수집된 항목을 LLM 판단으로 점수화한다:
- 기본 임계값 0.7 (0~1.0)
- 수락/거절 비율에 따라 ±0.05 자동 조정 (적응형 임계값)
- 임계값 이상만 RESEARCH 문서에 포함

**Phase 3 — RESEARCH 문서 작성**

`work-docs/RESEARCH-{slug}.md` 를 생성. 7개 섹션 포함:
1. 요약 (핵심 결론 3-5개)
2. 코드베이스 현황
3. 관련 패턴 및 선례
4. 외부 레퍼런스 (수집된 라이브러리/문서 인용)
5. 갭 분석 (현재 상태 vs 목표 상태)
6. 권장 접근법
7. 미해결 질문 (spec 에서 다뤄야 할 것들)

**Phase 4 — 유효성 검사**

RESEARCH 문서가 7개 섹션을 모두 갖추고 있는지, `libs_fetched` / `sources` 필드가 frontmatter 에 기록되었는지 확인한다.

#### 출력물
- `work-docs/RESEARCH-{slug}.md` (frontmatter + 7개 섹션)
- frontmatter 에 수집된 라이브러리와 소스 목록 기록

---

### 3.2 /hm:spec — 인수 조건

**목적**: 구현 전에 "무엇을 만들어야 하는가"를 명확하게 정의한다. 6개 카테고리 인터뷰를 통해 SPEC 문서를 작성한다.

#### 실행 절차

**Step 0 — 기존 SPEC 확인**

`specs/SPEC-{slug}.md` 가 이미 존재하면:
- `status: approved` + 미해결 질문 없음 → 스킵, plan 으로 넘어가도 된다고 알림
- `status: draft` → 미해결 질문들만 이어서 인터뷰

**Step 1 — 6개 카테고리 인터뷰**

구조화 질문 도구 (`AskQuestion` in Cursor, `AskUserQuestion` in Claude Code) 로 사용자와 대화하며 6개 카테고리를 확정한다:

| # | 카테고리 | 내용 |
|---|---------|------|
| 1 | **Intent** | 이 기능/변경이 해결하는 문제가 무엇인가? |
| 2 | **Outcomes** | 성공했을 때 어떤 상태가 되어야 하는가? |
| 3 | **In-Scope Scenarios** | 구체적인 Given/When/Then 시나리오 (S1, S2, …) |
| 4 | **Non-Goals** | 명시적으로 범위 밖인 것들 |
| 5 | **Constraints** | 기술 제약 (언어, 라이브러리, 성능 요건 등) |
| 6 | **Verification** | 각 시나리오의 검증 방법 (unit/integration/manual) |

In-Scope Scenarios 는 BDD 형식 사용:
```
**Given** <전제 조건>
**When** <행위>
**Then** <기대 결과>
```

**Step 2 — SPEC 초안 작성**

6개 카테고리 답변을 SPEC 문서로 통합. frontmatter 에 `test_framework` 기록 (Phase A 가 사용).

**Step 3 — 미해결 질문 명시**

`## ❓ Open Questions` 섹션에 아직 확정 안 된 사항 기록. 모두 해소되면 `status: approved` 로 변경.

**Step 4 — SPEC 품질 게이트 (Step 4.5)**

5개 차원으로 0~100점 채점:
1. 시나리오 완성도 (Given/When/Then 구조)
2. 비목표 명확성
3. 검증 방법 구체성
4. 제약 조건 명시
5. 미해결 질문 처리 여부

점수 미달 시 인터뷰를 재진행하여 보완.

**Step 5 — 최종 SPEC 저장**

`specs/SPEC-{slug}.md` 에 저장. frontmatter 에:
- `status: approved | draft`
- `test_framework: pytest | gtest | vitest | ...`
- `created: {date}`

#### 출력물
- `specs/SPEC-{slug}.md` (frontmatter + 6개 카테고리 + 검증 기준표)

---

### 3.3 /hm:plan — 구현 계획

**목적**: 코드를 쓰기 전에 "어떻게 만들 것인가"를 결정한다. 심층 인터뷰로 아키텍처 결정(ADR)을 확정하고, 구현 단계를 세분화한다.

#### 실행 절차

**Step 0 — 스킵 휴리스틱 (4개 기준 모두 충족 시 인터뷰 건너뜀)**

| 기준 | 스킵 조건 |
|------|---------|
| 범위 | 단일 파일 또는 설정/문서만 변경 |
| 아키텍처 | 컴포넌트 경계 변경 없음, 새 모듈 없음 |
| 계약 | API/IPC/DB 스키마/파일 형식 변경 없음 |
| 위험 | 1시간 내 롤백 가능, 사용자 영향 없음 |

4개 중 하나라도 해당되면 인터뷰 진행.

**Step 1 — 내부 초안 작성 (사용자에게 미표시)**

코드베이스를 읽고 내부적으로:
- 잠정 아키텍처 (컴포넌트, 경계, 데이터 흐름)
- 후보 단계 분해
- 폭발 반경 순으로 정렬한 모호한 점 목록

**Step 2 — SPEC 상속 확인**

SPEC 파일이 있으면 읽어서 상태 확인:

- **Case A** — `status: approved` + 미해결 질문 없음: 인터뷰 생략, Step 3.0 (간단 확인) 만 수행
- **Case B** — `status: draft`: SPEC에서 해소된 카테고리는 재질문 않고, 남은 질문만 인터뷰
- **Case C** — SPEC 없음: 처음부터 전체 인터뷰

**Step 3.0 — Case A 에서의 간단 확인**

구조화 질문 도구로 딱 하나만 물음:
- "단계 분해로 바로 진행" vs "먼저 아키텍처 결정이 있음" vs "여러 아키텍처 질문 있음"

**Step 3 — 인터뷰 루프**

> **언어 규칙**: 라이브 인터뷰 UI 는 `harness.yaml.locale` 언어로 진행 (ko→한국어, en→영어, 미지원 언어→영어 fallback). 단, **디스크에 저장되는 PLAN 문서는 항상 영어**. 사용자 자유형 답변은 Step 5 에서 영어로 번역하여 아카이빙.

무제한 라운드. 각 라운드는 A→E 단계:

**A. 현재 계획 상태 시각화** (필요한 경우):
- 기본: 산문/불릿 형식
- 비교할 때: 표
- 위상 파악 시: ASCII 박스
- Mermaid 는 최종 PLAN 문서에만 사용 (터미널에서는 날 텍스트로 보임)

**B. 구조화 질문** (우선순위 순서):
1. 범위 경계 (안/밖, 호환성 파괴 여부)
2. 아키텍처 (컴포넌트 소유권, 패턴 선택)
3. 계약 형태 (API 시그니처, 스키마, 파일 형식)
4. 위험 허용도 (단계적 vs 빅뱅, 롤백 전략)
5. 테스트 깊이 (단위/통합/수동)
6. 구현 순서 (피처 플래그, 의존성)
7. 의존성 (라이브러리 추가 vs 직접 구현)
8. 실패 처리 (재시도 정책, 서킷 브레이크)
9. 관측 가능성 (로그 레벨, 메트릭 이름)

라운드 2 부터는 "인터뷰 충분함 — 종료" 옵션 제공.

**C. 답변을 Interview Entry 로 기록**

| # | 토픽 | 카테고리 | 질문 | 선택 | 비고 | → ADR |

**D. ADR 승격 체크**

다음 중 하나라도 해당되면 공식 **ADR (Architecture Decision Record)** 생성:
- 컴포넌트 경계/소유권 변경
- 새 계약 (API, IPC, 스키마) 도입/변경
- 합리적인 대안을 거부
- 장기 영향이 있는 결정
- 미래 유연성 제한 (프레임워크, 라이브러리 고정)

ADR 형식:
```markdown
### ADR-{NNN}: {제목}
**Status:** Accepted ({날짜}, via /hm:plan interview)
**Context:** 이 결정이 필요했던 이유
**Decision:** 선택한 것
**Consequences:**
- ✅ 긍정적 결과
- ⚠️ 수용된 트레이드오프
**Rejected alternatives:** 거부된 대안과 이유
**Source:** Interview #{N}
```

**E. 종료 체크**

사용자가 "충분함 — 종료" 선택 또는 모든 고영향 모호점 해소 시 인터뷰 종료.

**Step 4 — plan-validator 에이전트 호출**

인터뷰 종료 후, 완성된 PLAN 초안을 `plan-validator` 에이전트에게 전달:

- `APPROVED` → 그대로 PLAN 저장
- `NEEDS_REVISION` (경고만) → 경고별 1회 추가 인터뷰 라운드 후 저장
- `MAJOR_REVISION` (심각한 문제) → 추가 인터뷰 후 재검증 1회. 두 번째도 MAJOR_REVISION 이면 사용자에게 에스컬레이션

**Step 5 — PLAN 문서 작성**

`work-docs/PLAN-{slug}.md` 에 10개 필수 섹션:
1. 🎯 Executive Summary
2. 📚 Prior Work
3. 🎙️ Interview Transcript
4. 📐 Architecture Decision Records
5. 🏗️ Technical Design
6. 📝 Implementation Plan (각 단계: 범위 / 완료 기준 / 위험 / 롤백 포인트)
7. 🧪 Testing Strategy
8. ⚠️ Risks & Mitigation
9. ✅ Success Criteria
10. 🔍 Plan Validation

각 구현 단계에는 **4개 필수 필드**: 범위, 완료 기준(실행 가능한 명령), 위험도(`low|medium|high`), 롤백 포인트.

**Step 6 — 저장 후 검증**

파일을 읽어서: frontmatter 시작, Interview Transcript 섹션 존재, ADR 수 일치, 4개 필드 모두 있는지 확인.

#### 출력물
- `work-docs/PLAN-{slug}.md` (frontmatter + 10개 섹션)
- ADR 세트 (ADR-001, ADR-002, …)

---

### 3.4 /hm:execute — TDD 구현

**목적**: PLAN 의 각 단계를 TDD 방식으로 구현한다. 테스트 먼저 작성하고, 테스트 품질 검증 후, 구현하고, 검증하는 4단계를 각 PLAN 단계마다 반복한다.

> **0.12.0 스코프 확장**: execute 는 이제 M16 추천 레지스트리 (`src/harness_maker/recommendation.py`) 와 M17 foreign-config apply 경로 (`src/harness_maker/foreign_config.py`) 도 포함한다. PLAN 단계가 이 둘 중 하나라도 건드리면 conditional router 가 diff 를 `code-reviewer` 로 라우팅한다 (`foreign_config.py` 는 LLM-mapped 입력 처리 때문에 `security-reviewer` 도 추가).

#### 실행 절차

**Step 0 — 워크트리 격리 (결정적 실행)**

`worktree-isolator` 스킬이 설명하는 내용을 harness-maker CLI 로 직접 실행:

```bash
uv run python -m harness_maker.worktree create execute "$(pwd)"
```

출력 분기:
- **절대 경로** (`/path/to/.worktrees/execute-20260509T0402Z`) → 격리 활성화. 이 경로(`<WT>`)를 이후 모든 파일 접근에 사용
- **빈 출력** → `worktree.scope` 에 `execute` 미포함. 격리 없이 현재 디렉토리에서 작업

> **주의**: 각 `!` 블록은 독립 서브셸이므로 셸 변수가 유지되지 않는다. `<WT>` 는 리터럴 절대 경로로 매번 대체해야 한다.

**Step 1 — PLAN 및 플래그 파싱**

`work-docs/PLAN-{slug}.md` 를 완전히 읽고 추출:
- 단계 목록 (범위/완료기준/위험/롤백)
- ADR (구속력 있는 제약 — 구현 시 위반 불가)
- frontmatter 의 `spec:`, `research_doc:` 참조

`--no-tdd` 플래그 유무로 `tdd_active` 설정.

**Step 2 — SPEC 및 RESEARCH 캐시 해소**

SPEC 파일 있으면 완전히 읽어서:
- `test_framework` 추출 → Phase A 에서 사용
- `## 📋 In-Scope Scenarios` 추출 → Phase A 테스트 대상
- `## ✅ Verification Criteria` 추출 → Phase B RED 게이트 명령

RESEARCH 파일이 `mtime_warn_days` (기본 7일) 보다 오래됐으면: 경고 후 진행, PLAN 에 staleness 기록.

**Step 3 — PLAN 단계별 TDD 머신**

각 PLAN 단계에 대해 Phase A → A.5 → B → C → D 순으로 실행:

#### Phase A — 테스트 작성 (`tdd_active=false` 시 건너뜀)

SPEC In-Scope Scenarios 를 기반으로 테스트 파일 작성:

1. `test_framework` 에 맞는 테스트 파일을 프로젝트의 테스트 디렉토리에 작성
2. 함수 이름에 시나리오 ID 포함: `test_s1_<이름>`, `test_s2_<이름>`
3. Assertions 는 시나리오의 `**Then**` 절과 정확히 일치
4. **테스트는 초기에 RED 여야 함** — 아직 존재하지 않는 함수에 의존

#### Phase A.5 — test-reviewer 게이트 (`tdd_active=false` 시 건너뜀)

작성된 테스트 파일을 `test-reviewer` 에이전트에게 전달:

```
Task(subagent_type="test-reviewer", prompt="<SPEC 본문 + Phase A 테스트 파일 경로>")
```

결과 처리:
- `overall_assessment: PASS` → Phase B 진행
- `overall_assessment: FAIL` → `blocking_issues[]` 의 테스트 재작성 (`passing_tests[]` 는 동결)
  → test-reviewer 재호출 → **최대 2회 재시도**
  → 2회 연속 FAIL 시: 최신 결과 표시 후 사용자에게 에스컬레이션

#### Phase B — RED 게이트 (`tdd_active=false` 시 건너뜀)

SPEC `## ✅ Verification Criteria` 의 테스트 명령을 실행:

```bash
cd <WT> && <test_command>
```

기대 결과: **올바른 이유로 FAIL** (구현 없음, not 문법 오류).
만약 우연히 PASS 하면 → Phase A 로 돌아가 재작성 (false-RED 는 Phase A.5 에서 걸렸어야 할 것).

#### Phase C — GREEN 까지 구현

구현 코드 작성. 제약:
- **미테스트 코드 경로 없음** — 모든 public 함수는 Phase A 테스트로 커버
- **ADR 위반 불가** — ADR 충돌 시 Phase D 블로커로 기록
- 편집 후마다 컴파일/타입 체크 (배치하지 않음)

#### Phase D — GREEN 후 검증

```bash
cd <WT> && ruff check          # 린트
cd <WT> && mypy --strict       # 타입
cd <WT> && pytest tests/ -q    # 전체 테스트
cd <WT> && <exit-criterion>    # PLAN 단계 완료 기준
```

실패 처리:
- 컴파일/타입/린트 실패 → Phase C 로 돌아가 수정
- 새로운 테스트 실패 → 회귀. 해당 변경 찾아 수정 또는 롤백
- 완료 기준 실패 → PLAN 단계 미완성. 수정 또는 에스컬레이션

**Step 4 — 단계 종료 (커밋 없음)**

모든 PLAN 단계 GREEN 후:
1. 워크트리 작업 트리가 깨끗한지 확인 (범위 밖 편집 없음)
2. **변경 사항을 staged 또는 unstaged 로 남김 — `git commit` 실행 금지**
3. PLAN 파일의 단계 상태 업데이트 (in-progress/done/blocked)

단계 블로커 발생 시:
- PLAN 의 해당 단계에 블로커 문서화
- 정확한 실패 출력과 함께 사용자에게 표시
- 범위 변경 불가 (조용히 변경 금지)

**Step 5 — 워크트리 파이널라이즈**

성공 시:
```bash
uv run python -m harness_maker.worktree finalize <WT> stage-only
```

블로커 시:
```bash
uv run python -m harness_maker.worktree finalize <WT> fail
```

`stage-only`: 브랜치를 메인으로 stage-merge 후 워크트리 삭제 (커밋은 wrapup 이 담당).

#### 출력물
- 코드 + 테스트 **staged but uncommitted** (커밋은 `/hm:wrapup` 에서)
- 단계 상태 업데이트된 PLAN 파일 (마찬가지로 uncommitted)

---

### 3.5 /hm:review — 코드 리뷰

**목적**: 구현된 변경을 다수의 전문 리뷰어가 독립적으로 검토하고, 합의를 거쳐 품질 등급을 산출한다. 문제가 있으면 자동 수정 루프를 돌린다.

#### 실행 절차

**Step 1 — 2-pass 리댁션 (diff 전처리)**

원본 diff 에서 노이즈를 제거하는 두 단계:

Pass 1 — 구조적 리댁션 (결정적 규칙):
- 로그/타임스탬프/자동생성 주석 제거
- 이진 파일/잠금 파일/마이그레이션 diff 제거
- 불변 줄 (공백/공행만 변경) 제거

Pass 2 — 의미 리댁션 (LLM 판단):
- Pass 1 이후 남은 diff 를 LLM 이 읽어 "앵커링 위험" 부분 추가 제거
- 리뷰어가 실제 변경 의도에 집중할 수 있게 함
- 이 2-pass 시스템으로 앵커링 감수성 대비 **+47%p precision 향상**

**Step 2 — Conditional Router 로 리뷰어 선택**

`conditional-router` 스킬이 diff 경로 패턴을 분석하여 리뷰어를 선택:

| 파일 패턴 | 추가 리뷰어 |
|----------|-----------|
| `.env`, `/auth/`, `/secret` | security-reviewer |
| `/perf/`, `benchmark`, `hot` | performance-reviewer |
| `.tsx`, `.jsx`, `/ui/` | ux-reviewer |
| `thread`, `isr`, `worker`, `async` | concurrency-reviewer |
| **항상** | code-reviewer (무조건 포함) |

**Step 3 — 병렬 리뷰 실행**

선택된 리뷰어들이 동시에 독립적으로 실행된다. 각 리뷰어는 **read-only** 에이전트 — 코드를 수정하지 않고 findings 만 반환.

각 finding 구조:
```json
{
  "severity": "P0 | P1 | P2",
  "file": "경로",
  "line": 줄번호,
  "summary": "무엇이 잘못됐는지 (≤80자)",
  "suggestion": "구체적 수정 방법 (≤200자)",
  "reasoning": { "observe": "...", "trace": "...", "infer": "...", "conclude": "..." }
}
```

P0/P1 에는 4-step reasoning 필수 (Observe → Trace → Infer → Conclude).

**Step 4 — consensus-arbiter 합의 필터**

`consensus-arbiter` 에이전트가 여러 리뷰어의 findings 를 통합:

**Surface Match** (같은 파일 + 줄±5 + 같은 severity tier):
- 2개 이상 리뷰어가 같은 위치 발견 → **consensus-passed**
- 1개만 발견 → **weak-consensus** 또는 **manual-only**

**Reasoning Alignment** (OBSERVE→INFER→CONCLUDE 단계별 정렬):
- 같은 위치라도 reasoning 이 다르면 약한 합의
- 범위 한정 findings (특정 리뷰어 전문 영역) 는 cross-check 면제 → 자동 consensus-passed

합의 태그: `consensus-passed | weak-consensus | manual-only`

**Step 5 — 등급 산출**

P0/P1 개수 기반 등급:

| P0 | P1 | 등급 |
|----|----|------|
| 0 | 0 | **A** |
| 0 | 1–2 | **B** |
| 0 | ≥ 3 | **C** |
| 1–2 | * | **D** |
| ≥ 3 | * | **F** |

**Step 6 — 자동 수정 루프**

등급이 `grade_threshold` (기본 A) 미달 시 자동 수정 루프 진입:

```
리뷰 → 수정 → 재리뷰 → 수정 → ... (max_review_rounds 까지)
```

- `executor` 에이전트가 P0/P1 findings 를 순서대로 수정
- 수정 후 리뷰 재실행
- 등급 달성 또는 `max_review_rounds` 도달 시 루프 종료

**Step 7 — REVIEW 문서 저장**

`work-docs/REVIEW-{slug}-{date}.md` 에 저장:
- 최종 등급
- 각 finding 과 합의 태그
- 수정 루프 히스토리

#### 출력물
- `work-docs/REVIEW-{slug}-{date}.md`
- 변경 사항 staged (수정된 경우)

---

### 3.6 /hm:verify — 완료 검증

**목적**: 커밋 전 마지막 관문. 6개 체크포인트를 순서대로 검사하고, 첫 번째 실패에서 블로킹한다.

#### 6개 체크포인트 상세

**Check 1 — PLAN/SPEC 이행 (LLM 직접 판단)**

사람이 판단. subprocess 에 위임하지 않음:
```bash
ls work-docs/PLAN-*.md        # PLAN 파일 찾기
git diff HEAD~1 HEAD           # 변경 확인
```
PLAN 의 각 항목이 diff 에 있는지 LLM 이 직접 대조. 체크박스 체크만으로는 PASS 불가 — 실제 코드 변경이 있어야 함.

실패 시: `BLOCKED: check 1 (PLAN-fulfillment) — <항목> not found in diff`

**Check 2 — 회귀/스모크 게이트**

```bash
bash .claude-verify.sh phase_${CURRENT_PHASE}
```
프로젝트별 검증 스크립트 실행.

**Check 3 — 헬스 점수 기준선 -5 이내**

`compute_readiness()` 로 현재 composite 점수 계산.
`.claude/observability/metrics.jsonl` 의 베이스라인 대비 5점 이상 하락 시 FAIL.

**Check 4 — 안티-rot 펜딩 해소**

```bash
test ! -f .claude/observability/refresh/pending.jsonl || \
  grep -q '"action":"defer"' .claude/observability/refresh/pending.jsonl
```
처리되지 않은 갱신 제안이 있으면 FAIL (defer 처리된 것은 OK).

**Check 5 — high-severity 보안 발견 없음**

```bash
count=$(grep -c '"severity":"high"' .claude/observability/security/findings.jsonl)
[ "$count" -eq 0 ]
```

**Check 6 — 워크트리 merge-safe**

```bash
git diff --check
git merge-tree $(git merge-base HEAD main) HEAD main | grep -q "<<<<<<<" && exit 1
```
충돌 마커 없음 확인.

#### 실패 동작

첫 번째 실패한 체크에서 즉시 중단:
```
BLOCKED: check <N> (<이름>) — <이유>
```

각 블로킹 체크에 대한 remediation 힌트:
- PLAN 미이행 → 미완료 항목 목록 표시
- 스모크 실패 → 실패 테스트 재실행
- 헬스 점수 하락 → 6차원 breakdown 표시
- 펜딩 refresh → `/hm:refresh` 실행 안내
- 보안 high → 발견 목록 표시
- 머지 충돌 → 충돌 경로 표시

`--force` 플래그 시 첫 번째 실패에서 멈추지 않고 계속 진행 (결과는 jsonl 에 기록).

#### 출력물
- 텍스트 결과 + `.claude/observability/verify-{date}.jsonl`

---

### 3.7 /hm:wrapup — 커밋 마무리

**목적**: 전체 워크플로우의 마지막 단계. 단 하나의 커밋을 생성하고, 메모리를 업데이트하고, 작업을 정리한다.

#### 실행 절차

**Step 1 — 사전 비행 체크**

- staged 변경이 있는지 확인
- 타입 체크, 린트, 테스트 통과 여부 재확인
- 범위 밖 편집 없는지 확인 (PLAN 스코프 대비)

**Step 2 — 최종 verify 패스**

`verify-before-completion` 스킬의 6개 체크를 실행. 하나라도 FAIL 이면 커밋 중단.

**Step 3 — Drift 게이트**

예상치 못한 파일 변경이 없는지 확인. `git diff --stat` 결과를 PLAN 스코프와 비교.

**Step 4 — PLAN 상태 업데이트**

`PLAN-{slug}.md` 의 `status:` 를 `planning` → `complete` 로 변경.

**Step 5 — 메모리 업데이트**

두 메모리 파일 업데이트 (session 티어는 checkpoint 전용 — wrapup 이 아니라 `flush_session` hook 이 기록):
- `.claude/memory/wiki.md` — 재사용 가능한 패턴/관례 추가
- `.claude/memory/failures.md` — 이번 작업에서 발생한 실패와 해결책

**Step 6 — 커밋 생성**

```bash
git add <scope-files>
git commit -m "$(cat <<'EOF'
<type>: <short subject>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

단 **하나의 커밋**. 여러 단계를 거쳐도 커밋은 항상 이 시점에 한 번만.

커밋 타입: `feat | fix | chore | ci | test | docs | refactor`

#### 출력물
- git 커밋 생성
- 업데이트된 메모리 파일들
- `status: complete` PLAN 파일

---

## 4. 퓨전 명령 <!-- @hm:axis-removed -->

퓨전 명령은 없습니다. 7개 원자 단계는 `/hm:loop` (`--per-iter-stages`, 기본 <!-- @hm:axis-removed -->
`execute,review`) 또는 autopilot 의 `autonomy.pipeline` 으로 연결합니다.
융합 워크플로 축은 0.47.0 에서 제거됐습니다 — PLAN-harness-diet ADR-001/002/014 참조. <!-- @hm:axis-removed -->

---

## 5. /hm:loop — 자동 반복 루프

**목적**: 하나의 목표를 향해 여러 번 반복하며 점진적으로 개선한다. 루프마다 독립된 워크트리를 사용하고, 안전 레일이 무한 반복을 방지한다.

> **학습된 패턴 (PLAN-personalization-depth-2026-05, validator W5)**: validator-driven phase merge. 인접한 두 루프 단계가 겹치는 diff 를 생성하면서 validator 가 신호 손실 없이 합칠 수 있는 경우, 루프는 둘을 머지한다 — 반복 라운드 한 번과 리뷰어 spawn 세트 한 번을 절약. 이제는 opt-in 이 아닌 기본 패턴.

### 두 가지 모드

| 모드 | 사용 방법 | 동작 |
|------|---------|------|
| **feature** | `/hm:loop feature <설명>` | 새 기능을 여러 반복으로 점진 구현 |
| **improve** | `/hm:loop improve <설명>` | 기존 코드를 반복적으로 개선 |

### 5단계 필수 컨텍스트 차원

루프 시작 전 `autoloop-driver` 스킬이 5개 차원을 수집:

| 차원 | 내용 |
|------|------|
| **purpose** | 이 루프가 달성하려는 것 |
| **invariants** | 절대 깨지면 안 되는 불변 조건 |
| **priority** | 품질 vs 속도 vs 커버리지 중 무엇이 우선인가 |
| **test_reliability** | 테스트가 신뢰할 수 있는가? flaky 테스트가 있는가? |
| **stopping_criteria** | 언제 루프가 완료되었다고 판단할 것인가 |

**커버리지 기반 적응형 인터뷰**: LLM 이 사용자의 초기 설명을 읽어 이미 답변된 차원을 추출하고, **부족한 차원만** 질문한다. 고정 스크립트 없음.

### 반복 사이클

```
루프 시작
│
├─ 워크트리 생성 (루프당 하나 — 반복마다 생성 안 함)
│
└─ 반복 1, 2, 3, ... (안전 레일 도달 전까지)
   │
   ├─ 컨텍스트 로드 (이전 반복 결과, 현재 상태)
   ├─ 이번 반복 목표 설정
   ├─ exec-rev 실행 (기본 워크플로우)
   ├─ verify-before-completion 스킬 실행
   ├─ stopping_criteria 평가
   └─ 달성 시 루프 종료 / 미달 시 다음 반복
│
└─ wrapup 실행 (루프 전체에서 단 한 번)
```

### 안전 레일

| 레일 | 기본값 | 의미 |
|------|-------|------|
| `max_iter` | 30회 | 최대 반복 횟수 |
| `max_time` | 8시간 | 최대 실행 시간 |
| `failed_streak` | 3 | 연속 실패 3회 시 중단 |

### 루프 시나리오 추적 예시 (feature 모드, 3반복)

```
1. /hm:loop feature "CSV 파서에 에러 핸들링 추가"
2. autoloop-driver 가 설명 분석 → purpose 확인됨, invariants/priority 미확인
3. 구조화 질문: "불변 조건과 우선순위는?" 
4. 사용자 답변: "기존 API 유지, 품질 우선"
5. 루프 시작, 워크트리 생성: .worktrees/autoloop-20260509T0500Z
6. [반복 1] 에러 타입 분류 로직 구현 + 테스트 → 리뷰 → B등급
7. verify-before-completion → PASS
8. stopping_criteria 평가: "에러 핸들링 완전히 구현됐는가?" → 아직 부분
9. [반복 2] 에러 메시지 로컬라이제이션 추가 → 테스트 → 리뷰 → A등급
10. stopping_criteria 평가: "완전히 구현됐는가?" → YES
11. 루프 종료, wrapup 실행 (단 한 번의 커밋)
```

---

## 6. 특수 명령

---

### 6.1 /hm:refresh — 안티-rot 업데이트

**목적**: 하네스 자체가 낡지 않도록 Anthropic 공식 변경사항, 보안 취약점, 관련 연구를 주기적으로 크롤링한다.

#### 실행 절차

**Step 1 — 4개 소스 크롤링 (`research-crawler` 스킬)**

`harness_maker.crawler` 모듈의 4개 크롤러가 모두 실행:

| 소스 | 크롤 대상 |
|------|---------|
| Anthropic 블로그/changelog | 새 기능, API 변경, 모델 업데이트 |
| GitHub 릴리스 | `anthropics/claude-code` + 참조 레포들의 새 릴리스 |
| arxiv (cs.SE/cs.CL/cs.CR) | 관련 연구 논문 |
| OSV.dev CVE 피드 | `uv.lock` 의 의존성 보안 취약점 |

부분 실패 시 graceful degradation: 실패한 소스는 빈 결과로 처리 + stderr 경고.
결과는 `.claude/observability/refresh/raw-{date}.jsonl` 에 저장.

**Step 2 — Stale 자산 스캔**

현재 하네스의 모든 자산 (commands, skills, agents) 을 스캔하여:
- 오래된 패턴 사용 여부
- 새 버전에서 제거된 API 사용 여부
- 보안 정책 위반 여부

**Step 3 — 버전 드리프트 체크**

현재 harness-maker 버전과 최신 릴리스 비교.

**Step 4 — 관련성 필터링 (`relevance-filter` 스킬)**

크롤된 항목을 LLM 이 0~1.0 으로 점수화:
- 0.7 이상만 제안 목록에 포함
- 수락/거절 비율에 따라 임계값 자동 조정

**Step 5 — 제안 문서 작성**

`work-docs/proposed-{date}.md` 에 제안 목록 저장.

**Step 6 — 사용자 확인 (구조화 질문)**

각 제안에 대해 개별 확인:
- "적용", "연기", "무시" 중 선택
- **자동 적용 없음** — 모든 변경은 사용자 명시적 승인 필요

24시간 이내 `raw-{date}.jsonl` 이 이미 있으면 크롤 건너뜀 (중복 방지).

---

### 6.2 /hm:ai-readiness — AI 준비도 분석

**목적**: 현재 코드베이스가 AI-assisted 개발에 얼마나 적합한지 3레이어 루브릭으로 평가하고, 개선 로드맵을 제시한다.

#### 3레이어 루브릭 구조

```
Composite Score = 70% × readiness + 25% × llm_judge_avg + 5% × cache_score
```

**Layer 1 — 결정적 신호 (자동)**

정량 측정:
- 문서화 비율 (docstring, README)
- 테스트 커버리지
- 타입 힌트 완성도
- 모듈 결합도 (coupling)
- 파일 크기 분포

**Layer 2 — LLM 루브릭 판단**

루브릭 YAML 파일들을 LLM 이 평가:
- 각 루브릭 항목에 대해 0~100 점수
- OBSERVE→INFER→CONCLUDE 추론 체인 포함
- `llm_judge_avg` = 모든 루브릭 항목 평균

**Layer 3 — 캐시 진단**

Anthropic 프롬프트 캐시 효율성 분석:
- 컨텍스트 hit rate
- TTL 소진 패턴
- 캐시 inefficiency 원인 분석

#### 실행 절차

**Step 1 — 구조적 분석**

```bash
uv run python -m harness_maker.cli ai-readiness .
```

Layer 1 (결정적) + Layer 3 (캐시) 분석. 결과를 구조화된 JSON 으로 반환.

**Step 2 — LLM 루브릭 평가**

Layer 2: 각 루브릭 YAML 을 순서대로 LLM 이 평가.
루브릭 예시: `readability.yaml`, `testability.yaml`, `modularity.yaml`

**Step 3 — 대시보드 작성**

3레이어 점수를 통합하여 `docs/ai-readiness-{date}.md` 생성:
- 전체 composite 점수
- 6차원 breakdown
- 각 차원의 상세 근거

**Step 4 — 개선 우선순위 결정**

발견된 문제를 두 범주로 분류:
- **AI-fixable**: `/hm:loop improve` 로 자동 개선 가능한 것
- **Human-required**: 아키텍처 결정 등 사람이 개입해야 하는 것

각 AI-fixable 항목에 대해 `/hm:loop` 명령을 제안.

#### 출력물
- `docs/ai-readiness-{date}.md` (대시보드)
- `ImprovementPlan` 구조체 (루프에 전달 가능)

---

### 6.3 /hm:personalization-audit — Composite-score 루브릭

**목적**: 누적된 텔레메트리 (M18 overrides) + 현재 `harness.yaml` + 캐싱된 `ProjectProfile` 로부터 personalization fit 점수를 계산하고, *어떤* harness 축이 실제 워크플로우와 어긋나 있는지 순위가 매겨진 액션 아이템 목록으로 제시한다.

0.12.0 에서 M19 메커니즘으로 추가. 100% 로컬 — `tests/unit/test_no_network.py` 가 네트워크 호출이 없음을 보장한다 (ADR-005 positive obligation).

#### 3레이어 루브릭 구조 (ADR-011 v0, locked)

```
Composite = L1 conversion × 0.4 + L2 stability × 0.3 + L3 cadence × 0.3
```

**Layer 1 — Conversion (추천 수락률)**

```
L1 = (medium_accepted + high_silent) / max(total_recommendations, 1) × 100
```

M16 추천 레지스트리의 HIGH-confidence 사일런트 디폴트가 그대로 유지된 비율 + MEDIUM-confidence 질문이 수락으로 전환된 비율. 낮은 conversion 은 사용자가 원하지 않는 것을 추천하고 있다는 신호.

**Layer 2 — Stability (override 변동성)**

```
L2 = 100 - min(100, override_events_last_30d × 5)
```

사용자가 `harness.yaml` 축을 반복적으로 뒤집는 프로젝트를 감점한다. 이는 추천이 틀려서 사용자가 우회 작업을 하고 있다는 의미.

**Layer 3 — Cadence (audit + telemetry 위생)**

```
100  if (지난 14일 내 audit 실행) AND (disable_telemetry == False)
 50  둘 중 하나만 충족
  0  둘 다 미충족
```

#### 등급 경계

| 등급 | Composite 범위 |
|------|----------------|
| **Bronze** | < 40 |
| **Silver** | 40 – 64 |
| **Gold** | 65 – 85 |
| **Platinum** | ≥ 85 |

#### 출력

`PersonalizationPlan`:
- Composite 점수 (0-100) + 레이어별 점수 (L1, L2, L3)
- 순위가 매겨진 `PersonalizationActionItem` 목록. 각 항목은 필수 `evidence = {n_observations, top_3_signals, confidence}` 포함.

**Evidence drop 규칙** (ADR-010 mode C 노이즈 완화): `n_observations` 가 없거나 `top_3_signals` 가 없는 액션 아이템은 순위 매김 전에 폐기한다. 근거가 추천 자체보다 얇은 항목은 사용자에게 도달하지 않는다.

#### 실행 절차

**Step 1 — 입력 로드**

- `.claude/observability/adaptive/overrides.jsonl` (M18 텔레메트리, schema_version-aware)
- `harness.yaml` (현재 축 값들)
- `~/.cache/harness-maker/profile-<repo-hash>.json` (M15 캐싱된 `ProjectProfile`)

**Step 2 — 레이어 점수 계산**

`personalization_audit.run_audit()` 가 `rubrics/personalization.yaml` 을 읽고 위의 locked 공식을 적용한다. `ai_readiness.py` 의 `rubric_loader` 패턴을 재사용 — 향후 새 레이어 추가는 YAML 편집 + 작은 Python 변경.

**Step 3 — 액션 아이템 생성 + 필터**

각 레이어가 액션 아이템을 기여할 수 있다. Evidence drop 규칙 (ADR-010) 이 `n_observations` 또는 `top_3_signals` 가 누락된 항목을 잘라낸다.

**Step 4 — 보고서 렌더**

Composite 점수, 등급, 레이어 breakdown, 살아남은 액션 아이템.

#### Local-only 보장

`tests/unit/test_no_network.py` 가 audit 실행 중 모든 아웃바운드 소켓 호출을 차단한다. ADR-005 가 이를 positive obligation 으로 명시 — audit 은 완전 오프라인 동작 필수.

#### 출력물

- Stdout 보고서 (composite + 등급 + 레이어 + 액션 아이템)
- 파일 쓰기 없음 — audit 은 read-only 진단. 재실행 시 새 스냅샷.

#### 보정 노트

v0 루브릭은 잠정적. 30+ 프로젝트가 audit 실행을 누적한 후 등급 경계와 가중치를 재검토한다 (ADR-011 deferred decision).

---

## 7. 스킬 참조

스킬은 명령에서 호출하는 재사용 능력 모듈이다. 에이전트와 달리 독립 실행 컨텍스트가 없고, 호출한 명령의 컨텍스트 안에서 실행된다.

### 7.1 agent-quality-rubric

**역할**: 에이전트 파일의 품질을 4-tier 로 평가한다.

**Tier 등급**:
- 🥇 Platinum: 정적 구조 + Layer-2 LLM 판단 모두 최고
- 🥈 Gold: 정적 구조 우수, LLM 판단 보통
- 🥉 Silver: 일부 구조적 문제
- 🟫 Bronze: 구조 부족, 자동 anti-rot 플래그

**평가 과정**:
1. 정적 구조 체크 (frontmatter 완성도, 섹션 존재 여부, 권한 선언)
2. Layer-2 LLM 루브릭 (prompt 품질, 추론 가이드 명확성)
3. Composite 점수 계산
4. Bronze → anti-rot 펜딩 큐 등록

**트리거**: `/hm:ai-readiness`, `/hm:refresh` 의 stale-asset 스캔

---

### 7.2 ai-readiness-rubric

**역할**: `/hm:ai-readiness` 명령의 3레이어 루브릭 실행 핵심. `run_ai_readiness()` 함수 진입점.

**입력**: `Path` (프로젝트 루트), `Preset` (Side/Production)
**출력**: `ImprovementPlan` (scores + priority improvements + loop suggestions)

3레이어 상세는 [6.2절](#62-hmai-readiness--ai-준비도-분석) 참조.

---

### 7.3 autoloop-driver

**역할**: `/hm:loop` 명령의 WHY 를 설명하고, 5차원 컨텍스트 수집 방법을 정의한다.

**핵심 기여**:
- 5개 필수 차원 정의 (purpose, invariants, priority, test_reliability, stopping_criteria)
- 커버리지 기반 적응형 인터뷰 원리 (추출 먼저, 질문 나중)
- 안전 레일 문서화

이 스킬은 **문서 스킬** — 직접 코드를 실행하지 않고 `/hm:loop` 명령이 어떻게 동작해야 하는지 가이드를 제공한다.

---

### 7.4 conditional-router

**역할**: diff 파일 경로를 분석하여 어떤 전문 리뷰어를 호출할지 결정한다.

**라우팅 테이블**:

| 파일 패턴 | 리뷰어 | 예시 경로 |
|----------|-------|---------|
| `.env`, `/auth/`, `/secret` | security-reviewer | `src/auth/login.py` |
| `/perf/`, `benchmark`, `hot` | performance-reviewer | `tests/benchmark/sort.py` |
| `.tsx`, `.jsx`, `/ui/` | ux-reviewer | `src/ui/Button.tsx` |
| `thread`, `isr`, `worker`, `async` | concurrency-reviewer | `lib/async_worker.py` |
| **(항상)** | code-reviewer | — |

code-reviewer 는 항상 포함. 나머지는 패턴 매칭에 따라 추가.

---

### 7.5 context-linter

**역할**: CLAUDE.md, 에이전트, 스킬, 워크플로우 파일의 줄 수가 preset 별 한계를 초과하지 않는지 검사한다.

**Preset 별 한계**:

| 자산 타입 | Side preset | Production preset |
|---------|------------|-----------------|
| CLAUDE.md | ≤200줄 | ≤500줄 |
| 에이전트 prompt | ≤100줄 | ≤200줄 |
| 스킬 SKILL.md | ≤50줄 | ≤150줄 |
| 워크플로우 | ≤300줄 | ≤600줄 |
| `.cursor/rules/*.mdc` | ≤500줄 (Cursor 권장) | ≤500줄 |

한계 초과 시: renderer 가 경고 발생. `/hm:ai-readiness` 와 `/hm:refresh` 스캔 시 자동 감지.

---

### 7.6 refdocs-search

**역할**: 사용자가 등록한 참조 문서 폴더에서 2-tier 검색을 수행한다.

**지원 포맷**: `.md`, `.txt` (ripgrep), `.pdf` (Read multimodal)
**미지원**: DOCX (변환 없이 직접 검색 불가)

**2-tier 검색 과정**:
1. **Tier 1 (손실적 인덱스)**: ripgrep 으로 키워드 매칭 → 후보 파일 목록 추림
2. **Tier 2 (원본 확인)**: 후보 파일들을 Read 로 직접 읽어서 실제 내용 확인

PDF 의 경우 multimodal Read 로 페이지별 직접 처리.

**트리거**: `/hm:research --deep` 실행 시

---

### 7.7 relevance-filter

**역할**: 수집된 항목 목록을 LLM 이 읽고 관련성 점수를 매겨 필터링한다.

**적응형 임계값**:
- 시작값: 0.7
- 수락 비율이 높으면 임계값 +0.05 (더 엄격하게)
- 거절 비율이 높으면 임계값 -0.05 (더 관대하게)
- 범위: 0.5 ~ 0.9

**사용 위치**: `/hm:research` (Phase 2), `/hm:refresh` (Step 4)

---

### 7.8 research-crawler

**역할**: 4개 외부 소스를 크롤링하고 결과를 JSONL 파일로 저장한다.

**크롤러 모듈**:
```python
anthropic_blog.crawl()    # Anthropic 블로그/changelog
github_releases.crawl()   # GitHub 릴리스 (claude-code + 참조 레포)
arxiv.crawl("cat:cs.SE OR cat:cs.CL OR cat:cs.CR")
osv_dev.crawl(packages=osv_dev.parse_uv_lock("uv.lock"))
```

**동작 특성**:
- 모든 4개 소스가 실행됨 (하나 실패해도 나머지 계속)
- 24시간 이내 raw 파일 있으면 크롤 생략
- 오프라인 상태 시: 조용히 건너뜀 + stderr 경고
- **직접 변경 없음** — raw 데이터만 저장, 실제 적용은 `/hm:refresh` 가 담당

**출력**: `.claude/observability/refresh/raw-{date}.jsonl`

---

### 7.9 security-scanner

**역할**: 5-gate 보안 스캔을 실행하고 findings 를 JSONL 로 저장한다.

**5개 게이트**:

| 게이트 | 내용 | Severity |
|-------|------|---------|
| 1. Secrets | API 키, 토큰, 비밀번호 정규식 탐지 | high |
| 2. Permissions | catch-all `Bash(*)`, 과도한 경로 패턴 | high/medium |
| 3. Hook injection | `rm -rf`, `curl \| sh`, `eval`, 리버스셸 | high |
| 4. CVEs | OSV.dev 기반 의존성 취약점 (CVSS ≥7 → high) | high/medium/low |
| 5. Prompt injection | 제로폭 문자, "ignore previous", base64 블록 | medium/high |

게이트 5 (Prompt injection) 의 경우:
- 정규식 1차 필터링 후
- **LLM 이 직접 후보를 읽어** 실제 injection 시도인지 false positive 인지 판단
- LLM 판단으로 severity 조정 가능

**출력**: `.claude/observability/security/findings-{date}.jsonl`
high-severity findings → wrapup/verify 블로킹

---

### 7.10 verify-before-completion

**역할**: wrapup 이전 또는 루프 반복 종료 시 6개 체크포인트를 실행하는 강제 게이트.

6개 체크 상세는 [3.6절](#36-hmverify--완료-검증) 참조.

**호출 위치**:
- `/hm:wrapup` 의 Step 2
- `/hm:loop` 의 각 반복 종료 시
- 수동: `/hm:verify`

---

### 7.11 worktree-isolator

**역할**: `/hm:execute` 등 격리가 필요한 단계에서 워크트리를 생성하고 관리한다.

**4단계 흐름**:

1. **`harness.yaml.worktree.scope` 확인**: 현재 단계가 scope 에 있으면 격리 실행
2. **`worktree.create()` 호출**: `.worktrees/<stage>-<UTC-ts>/` 에 새 워크트리 생성
3. **워크플로우 실행**: 에이전트의 모든 Write/Edit 이 워크트리 안에서만 발생
4. **종료 처리**:
   - 성공 → `worktree.merge()` + `worktree.cleanup(on_success=True)`
   - 실패 → `worktree.cleanup(on_success=False)` (워크트리 보존, 수동 트리아지용)

**idempotent**: 이미 워크트리 안에 있으면 기존 경로 반환 (중첩 워크트리 없음).

**설정**:
```yaml
worktree:
  scope: [execute]        # 격리 대상 단계 목록
  branch_prefix: hm-      # 브랜치 이름 접두어
```

---

## 8. 에이전트 참조

에이전트는 독립된 컨텍스트를 가진 서브-에이전트이다. 주 Claude 컨텍스트가 Task 도구로 호출하면 별도 LLM 호출이 발생하고 결과를 반환한다.

### 8.1 autoloop-coder

**역할**: `/hm:loop` 에서 각 반복의 구현을 담당하는 제한적 스코프 에이전트.

**권한 (허용)**:
- `Read(*)`, `Grep(*)`, `Glob(*)` — 읽기 전체
- `Write(.worktrees/**)`, `Edit(.worktrees/**)` — 워크트리 내 쓰기만

**스코프 (지시 사항일 뿐 — 강제 아님)**: 에이전트는 `/etc/**`, `~/.ssh/**`,
`~/.aws/**` 밖으로 나가지 말고 `curl | sh`, `eval`, 파괴적 `rm` 을 피하라고
*지시받는다*. Subagent frontmatter 에는 `permissions:` 필드가 없어 Claude
Code 는 그런 블록을 있어도 조용히 무시한다 — 진짜 경계는 에이전트의
`tools:` 리스트다 (Write/Edit/Bash 가 경로 제한 없이 부여됨). §11.16 참고.

**모델**: 기본 모델 (autoloop context 에서 opus 권장)

**동작**: 워크트리 안에서만 파일을 수정. open-ended 탐색 없음, 제한된 범위 구현만.

---

### 8.2 code-reviewer

**역할**: 모든 `/hm:review` 에서 항상 포함되는 범용 코드 리뷰어.

**권한**: Read, Grep, Glob + `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git status:*)`
**금지**: Write(*), Edit(*), 모든 실행 Bash (rm, curl, npm, eval, python, node, sh, bash)

**검토 영역**: 정확성, 가독성, 유지보수성, 기본 보안/성능 위생

**모델**: sonnet

**특징**: 모든 리뷰에 포함 (conditional-router 가 추가 전문 리뷰어를 선택해도 code-reviewer 는 항상 있음)

---

### 8.3 concurrency-reviewer

**역할**: 스레드 안전성, 데드락, ISR 안전성, async 정확성 전문 리뷰어.

**트리거** (conditional-router 가 선택): `thread`, `isr`, `worker`, `async` 포함 파일

**검토 영역**:
- 공유 가변 상태 접근
- 락 획득 순서 (데드락 가능성)
- ISR 컨텍스트에서의 안전성
- async/await 올바른 사용

**권한**: code-reviewer 와 동일 (Read-only)
**모델**: sonnet

---

### 8.4 consensus-arbiter

**역할**: 여러 리뷰어의 findings 를 통합하여 합의 태그를 붙인다.

**합의 알고리즘**:

1. **Surface Match**: 같은 파일 + 줄±5 + 같은 severity tier
2. **Reasoning Alignment**: OBSERVE→INFER→CONCLUDE 단계별 정렬 확인
3. **스코프 한정 findings**: 특정 리뷰어 전문 영역 → cross-check 없이 자동 consensus-passed

**출력 태그**:
- `consensus-passed`: 2개 이상 리뷰어가 같은 발견, reasoning 일치
- `weak-consensus`: 같은 위치지만 reasoning 다름, 또는 1개 리뷰어만 발견
- `manual-only`: 자동 판단 불가, 사람이 검토 필요

**권한**: Read, Grep, Glob (읽기 전용)
**모델**: sonnet

---

### 8.5 executor

**역할**: `/hm:review` 의 자동 수정 루프에서 P0/P1 findings 를 실제로 수정하는 에이전트.

**권한 (허용)**:
- `Read(*)`, `Grep(*)`, `Glob(*)` — 읽기 전체
- `Write(.worktrees/**)`, `Edit(.worktrees/**)` — 워크트리 내 쓰기만
- `Bash(uv run:*)`, `Bash(pytest:*)`, `Bash(npm test:*)`, `Bash(cargo test:*)` — 테스트 실행
- `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git status:*)` — git 읽기

**하지 말라고 지시됨** (지시일 뿐, 강제 아님 — §11.16 참고): 시스템 경로 쓰기,
`curl | sh`, `eval`, 파괴적 `rm`. 실제 경계는 에이전트의 `tools:` 리스트다.
**모델**: sonnet

---

### 8.6 performance-reviewer

**역할**: 핫패스 회귀, 할당 핫스팟, 알고리즘 비효율성 전문 리뷰어.

**트리거** (conditional-router): `/perf/`, `benchmark`, `hot` 포함 파일

**검토 영역**:
- O(n²) 등 비효율적 알고리즘
- 핫패스에서의 불필요한 할당
- 캐시 미스 패턴
- I/O 블로킹

**권한**: Read-only (code-reviewer 와 동일)
**모델**: sonnet

---

### 8.7 plan-validator

**역할**: `/hm:plan` Step 4 에서 PLAN 초안의 품질을 독립적으로 비판한다.

**호출 시점**: PLAN 파일을 디스크에 쓰기 **전** — 아직 임시 상태인 초안을 검증

**판정 결과**:
- `APPROVED`: 그대로 저장
- `NEEDS_REVISION`: 경고 목록 포함. 각 경고에 대해 인터뷰 라운드 후 저장
- `MAJOR_REVISION`: 심각한 문제. 추가 인터뷰 후 재검증. 두 번째도 MAJOR 이면 에스컬레이션

**검토 항목**: exit criterion 검증 가능성, ADR 수 일치, 단계별 4필드 완성도, Non-Goals 존재, 리스크 구체성

**권한**: Read, Grep, Glob (읽기 전용)
**모델**: opus

---

### 8.8 security-auditor

**역할**: 심층 5-gate 보안 감사. `security-reviewer` 보다 더 깊은 분석.

**차이**: security-reviewer 는 diff 의 변경된 부분만 spot-check. security-auditor 는 **전체 코드베이스** 를 5-gate 로 완전 감사.

**5개 게이트 (security-scanner 스킬과 동일)**:
1. Secrets (소스/설정 내 비밀)
2. Permission escalation (settings.json 권한)
3. Hook injection (hooks.json 위험 패턴)
4. CVEs (OSV.dev 의존성)
5. Prompt injection (LLM 으로 흐르는 문자열)

**게이트 3 특이사항**: stdout → LLM injection 클래스도 검사:
- 훅의 stdout 이 LLM 에게 보여지면 (PostToolUse, PreToolUse advisory)
- 사용자가 쓸 수 있는 파일 (`wiki.md`, `harness.yaml`) 내용이 stdout 으로 나가면
- 이는 저장된 프롬프트 인젝션 벡터 → finding 발생

**4-step reasoning**: 모든 P0/P1 finding 에 OBSERVE→TRACE→INFER→CONCLUDE 필수

**출력**: JSON (overall_assessment, gates[], findings[])
**권한**: Read, Grep, Glob, Bash (읽기 전용 + Bash 로 스캔)
**모델**: sonnet

---

### 8.9 security-reviewer

**역할**: `/hm:review` 에서 보안 관련 diff 를 전문으로 검토하는 conditional reviewer.

**트리거** (conditional-router): `.env`, `/auth/`, `/secret` 포함 파일

**검토 영역**:
- plaintext 비밀, hardcoded 토큰
- 인증 흐름 취약점 (TOCTOU, 깨진 리다이렉트)
- SQL injection, 커맨드 인젝션, XSS, SSRF, 경로 탐색
- 새 의존성 CVE
- `settings.json` 과대 권한
- `hooks.json` 위험 패턴

**security-auditor 와 차이**: 리뷰어는 diff 범위만, 감사는 전체 코드베이스.

**권한**: Read-only
**모델**: sonnet

---

### 8.10 stuck

**역할**: 워크플로우가 블로킹될 때 호출되는 마지막 수단 에스컬레이션 분석 에이전트.

**트리거 조건**:
- `/hm:execute` Phase A.5: test-reviewer FAIL 재시도 예산 소진
- `/hm:execute` Phase D: PLAN 범위 변경 없이 수정 불가한 실패
- `/hm:execute` ADR 충돌: 구현이 ADR 을 위반해야만 진행 가능
- `/hm:review` 합의 교착: 3개 리뷰어가 동일 이슈에 상충 CONCLUDE
- `/hm:plan` plan-validator: 2차 MAJOR_REVISION

**분석 과정**:

1. 전체 컨텍스트 읽기 (PLAN, SPEC, REVIEW, 최근 3개 리뷰어 출력, 실패 로그)
2. **단일 구속 제약** 식별 (증상이 아닌 근본 아키텍처/계약/시간 제약)
3. 2-3개 구체적 해결 경로 제안 (각각 trade-off + 관련 ADR/Interview 번호)
4. 우선 결정과 가장 일관된 경로 권장
5. 에스컬레이션 노트를 `.claude/memory/escalations/escalation-{slug}-{date}.md` 에 저장

**특징**: 문제를 직접 고치지 않음 — 읽기 전용 조언자.
**모델**: opus (복잡한 추론 필요)

---

### 8.11 test-reviewer

**역할**: `/hm:execute` Phase A.5 게이트. Phase A 에서 작성된 테스트 파일의 품질을 검증한다.

**검토 기준 3가지**:

1. **SPEC 정렬**: 모든 In-Scope Scenario 가 테스트로 커버되었는가?
2. **8개 금지 패턴**: 다음 중 하나라도 해당되면 FAIL
   - Tautology (`assert True`, `assert len(x) >= 0`)
   - Stub-only (`pass`, `raise NotImplementedError`)
   - Framework-check-only (임포트 성공만 검증)
   - Over-mocking (테스트 대상 자체를 mock)
   - Scenario-ID 불일치
   - 매직 값 assertion (SPEC 에 없는 상수)
   - 실패 억제 (`try...except: pass`)
   - private/internal 상태 assertion
3. **RED-correctness**: Phase C 구현 전에 실제로 실패하는가?

**출력 JSON**:
```json
{
  "overall_assessment": "PASS | FAIL",
  "per_scenario": [...],
  "scenarios_missing": [...],
  "blocking_issues": [...],
  "passing_tests": [...]
}
```

`passing_tests[]` 는 동결 — 재시도 시 이 테스트들은 재작성하지 않음.

**권한**: Read, Grep, Glob (읽기 전용)
**모델**: sonnet

---

### 8.12 ux-reviewer

**역할**: UI 변경의 접근성, 일관성, 인터랙션 품질 전문 리뷰어.

**트리거** (conditional-router): `.tsx`, `.jsx`, `/ui/` 포함 파일

**검토 영역**:
- 접근성: 키보드 네비게이션, ARIA, 포커스 관리, 컬러 대비
- 일관성: 디자인 시스템 컴포넌트 사용 여부
- 누락 상태: loading/empty/error 상태 처리
- 플랫폼 관례 위반
- 텍스트 명확성 및 i18n 준비

**WCAG 참조**: 접근성 발견 시 WCAG 기준 코드 포함 (예: `"WCAG 2.1 SC 2.4.7"`)

**권한**: Read-only
**모델**: sonnet

---

## 9. 훅 상세

훅은 특정 이벤트가 발생할 때 자동으로 실행되는 Python 모듈이다. `.claude/hooks/hooks.json` 에 정의되며, harness-maker 가 관리한다.

### 훅 정의 구조 (hooks.json)

```json
{
  "hooks": [
    {
      "type": "PostToolUse",
      "matcher": "Write|Edit|MultiEdit",
      "command": "python -m harness_maker.hooks.post_write_reminder"
    }
  ]
}
```

### 9.1 SessionStart

**이벤트**: Claude Code 세션이 시작될 때 한 번 실행

**핸들러**: `harness_maker.hooks.sessionstart_drift`

**동작**:
1. 현재 하네스 상태와 `harness.yaml` 기준값 비교
2. 마지막 세션 이후 예상치 못한 파일 변경 감지 (drift)
3. drift 발견 시 세션 시작 메시지에 경고 포함

**목적**: "아, 누군가 설정 파일을 건드렸네" 를 세션 시작에서 바로 인지

---

### 9.2 PreToolUse

**이벤트**: 도구 호출 **직전**에 실행. 도구 실행을 차단할 수 있음.

**두 핸들러**:

**1. permission_gate** (matcher: `Bash`)

```python
harness_maker.gates.permission_gate
```

- `harness.yaml` 의 `permissions.allow/deny` 와 Bash 명령 비교
- deny 목록에 해당하는 Bash 명령은 차단
- 예: `Bash(eval *)`, `Bash(rm -rf /:*)` → BLOCK

**2. worktree_gate** (matcher: `Write|Edit|MultiEdit`)

```python
harness_maker.gates.worktree_gate
```

- 파일 쓰기 목표가 워크트리 안인지 확인 (`worktree.scope` 에 현재 단계 포함 시)
- 워크트리 바깥에 쓰려는 시도를 감지하고 경고
- 실수로 메인 브랜치의 파일을 직접 편집하는 것 방지

---

### 9.3 PostToolUse

**이벤트**: 도구 호출 **완료 후** 실행.

**두 핸들러**:

**1. telemetry** (matcher: `*` — 모든 도구)

```python
harness_maker.telemetry
```

- 모든 도구 호출을 `.claude/observability/metrics.jsonl` 에 기록
- 기록 내용: 도구 이름, 입력 요약, 결과 코드, 타임스탬프
- **100% 로컬** — 외부 전송 없음
- 헬스 점수 계산의 원데이터

**2. post_write_reminder** (matcher: `Write|Edit|MultiEdit`)

```python
harness_maker.hooks.post_write_reminder
```

- 파일을 쓴 직후 실행
- 수정된 파일이 특정 조건을 충족하는지 리마인더
- 예: `settings.json` 수정 후 "권한 정책 준수 여부 확인" 알림

---

### 9.4 PreCompact

**이벤트**: 컨텍스트 압축 **직전** 실행. 컨텍스트 손실 전 중요 정보 저장 기회.

**두 핸들러** (auto 와 manual 각각):

```python
harness_maker.hooks.flush_session
```

**동작**:
1. 현재 세션의 중요 상태를 `.claude/memory/session/<date>.md` 에 기록
2. 진행 중인 작업, 현재 단계, 블로커 등을 checkpoint 로 저장
3. 컨텍스트가 압축되어도 다음 세션에서 재개 가능

`checkpoint:compaction` 항목이 있으면: 이전 세션이 중간에 중단됨 → `.claude-progress.json` 확인 후 마지막 in-progress 단계부터 재개.

**두 경우**:
- `matcher: auto` — Claude 가 자동으로 컨텍스트 압축 시
- `matcher: manual` — 사용자가 수동으로 `/compact` 실행 시

---

### 9.5 Stop

**이벤트**: Claude 세션이 종료될 때.

**현재 상태**: `[]` (빈 배열) — 현재 핸들러 없음.

향후 확장 지점: 세션 종료 시 최종 정리 작업, 장기 워크트리 청소 등.

---

### 훅 보안 고려사항

hooks.json 은 security-auditor 의 **게이트 3** 검사 대상:
- `rm -rf /` 등 위험 명령 패턴
- `curl ... | sh` 원격 실행
- `eval "$..."` 인젝션
- 사용자 쓰기 가능 파일 → stdout → LLM 인젝션 경로

훅 코드 수정 시 항상 `/hm:audit` 또는 security-scanner 스킬로 검토 권장.

---

## 10. 부록

### A. harness.yaml 주요 설정

```yaml
# 언어 설정 (인터뷰 및 문서 출력 언어)
locale: ko               # en | ko | ja | 기타 → en fallback

# 타깃 IDE (멀티 선택)
targets:
  - claude-code
  - cursor

# 프리셋 (컨텍스트 크기/권한 엄격도)
preset: Side             # Side | Production

# 개발 모드 (spec-driven vs task-driven)
dev_mode: spec-driven    # spec-driven | task-driven

# 워크트리 격리
worktree:
  scope: [execute]       # Side preset 기본값. Production preset 은 [execute, plan]
  cleanup: on_success    # on_success | always | never

# 리뷰 설정
max_review_rounds: 3     # 자동 수정 루프 최대 횟수
grade_threshold: A       # 이 등급 이상이면 wrapup 진행 (기본값 A)

# 루프 안전 레일
loop:
  max_iter: 30
  max_time: 8h
  failed_streak: 3

# 레퍼런스 문서 폴더
ref_folders:
  - ./docs/reference
  - ~/knowledge-base
```

---

### B. 메모리 구조

```
.claude/memory/
├── wiki.md           ← 재사용 가능한 패턴, 관례, 교훈
├── failures.md       ← 실패 사례와 해결책 ([fail:] 태그)
├── session/
│   └── <date>.md     ← compaction 체크포인트 (checkpoint:compaction 항목)
└── escalations/
    └── escalation-{slug}-{date}.md  ← stuck 에이전트 에스컬레이션 노트
```

- **wiki.md**: 나중에 비슷한 작업 시 참조할 패턴. wrapup 이 자동 추가.
- **failures.md**: `rg -F "[fail:" .claude/memory/failures.md` 로 검색. execute 시 워밍업에 사용.
- **session/\<date\>.md**: PreCompact 훅이 자동 저장. `checkpoint:compaction` 항목으로 중단된 세션 재개.

---

### C. 관측 가능성 구조

```
.claude/observability/
├── metrics.jsonl                    ← 도구 호출 텔레메트리 (PostToolUse 수집)
├── security/
│   └── findings-{date}.jsonl       ← security-scanner 발견사항
└── refresh/
    ├── raw-{date}.jsonl             ← research-crawler 원시 데이터
    └── pending.jsonl                ← 처리되지 않은 갱신 제안
```

---

### D. 워크트리 생명주기

```
생성: .worktrees/execute-20260509T0402Z/
  └─ HEAD 에서 새 브랜치 시작
  └─ 이름 형식: <stage>-<UTC-timestamp>

격리 실행:
  └─ 모든 Write/Edit 이 워크트리 안에서만 발생
  └─ 메인 브랜치의 작업 트리는 변경 없음

성공 시 (stage-only):
  └─ git: 브랜치를 메인으로 stage-merge
  └─ git worktree remove (워크트리 디렉토리 삭제)
  └─ 커밋은 /hm:wrapup 에서

실패 시 (fail):
  └─ 워크트리 보존 (.worktrees/execute-<ts>/ 남아있음)
  └─ 수동 트리아지 가능
  └─ /hm:refresh 또는 weekly cleanup 이 24h 이상 stale 삭제
```

---

### E. 권한 매트릭스 요약

| 에이전트 타입 | Read | Write | Edit | Bash |
|-------------|------|-------|------|------|
| 리뷰어 (code, security, perf, ux, concurrency) | ✅ 전체 | ❌ | ❌ | git diff/log/status 만 |
| executor | ✅ 전체 | ✅ .worktrees/** 만 | ✅ .worktrees/** 만 | uv/pytest/테스트 실행 |
| autoloop-coder | ✅ 전체 | ✅ .worktrees/** 만 | ✅ .worktrees/** 만 | (executor 와 유사) |
| consensus-arbiter | ✅ 전체 | ❌ | ❌ | ❌ |
| plan-validator | ✅ 전체 | ❌ | ❌ | ❌ |
| test-reviewer | ✅ 전체 | ❌ | ❌ | ❌ |
| stuck | ✅ 전체 | 에스컬레이션 노트만 | ❌ | ❌ |
| security-auditor | ✅ 전체 | ❌ | ❌ | 스캔용 Bash |

---

### F. 자주 묻는 질문

**Q: 커밋이 여러 개 생기지 않나요?**

A: 아닙니다. `execute`, `review` 단계는 커밋하지 않습니다. `wrapup` 이 단 하나의 커밋을 생성합니다. `/hm:loop` 로 여러 단계를 이어 돌려도 마찬가지.

**Q: 워크트리가 너무 많이 쌓이면?**

A: `/hm:refresh` 실행 시 24시간 이상 stale 워크트리를 청소합니다. 자동 루프 블로커 발생 시에는 `worktree.cleanup_all(force=True)` 로 즉시 정리.

**Q: `--no-tdd` 를 언제 써야 하나요?**

A: (1) 순수 리팩토링 — 기존 테스트가 이미 커버, (2) 문서/설정만 변경, (3) 긴급 수정 — SPEC+테스트가 이미 정확히 있을 때. 그 외에는 TDD 기본.

**Q: 리뷰 등급이 B 미만이면 어떻게 되나요?**

A: 자동 수정 루프 진입 (executor 에이전트가 P0/P1 findings 수정). `max_review_rounds` 이내에 목표 등급 달성 못 하면 사용자에게 보고, wrapup 중단.

**Q: stuck 에이전트는 언제 호출되나요?**

A: 자동으로 호출되는 것이 아닙니다. 각 단계가 블로킹 조건을 감지했을 때 해당 단계가 stuck 에이전트를 `Task()` 로 호출합니다. 수동으로 "우리 X에서 막혔는데 최소 유감 unblock은 뭔가?" 처럼 사용 가능.

**Q: Cursor 와 Claude Code 중 어디서 실행되는지 어떻게 알 수 있나요?**

A: harness-maker 는 양쪽 모두에서 동일하게 동작합니다. `targets` 설정에 `cursor` 포함 시 Cursor 전용 자산 (`.cursor/rules/*.mdc`, `.cursor/mcp.json`) 이 추가로 렌더됩니다. 핵심 로직은 `.claude/` 하나에서 양쪽이 공유합니다.

---

## 11. harness-maker 특장점: 일반 AI 워크플로우와 무엇이 다른가

> 이 섹션은 "어떻게 동작하는가"가 아니라 **"왜 이렇게 설계됐는가"** 를 다룬다.
> 각 특장점에는 없었을 때 어떤 문제가 생기는지(Before)와 있으면 어떻게 되는지(After)를 함께 설명한다.

### 11.1 3-tier 메모리 계층 — 세션을 넘어 지식이 축적된다

**일반 Claude 세션의 한계**: 매 세션은 빈 종이에서 시작한다. 어제 해결한 버그 패턴, 지난주에 확정한 설계 결정, 반복해서 밟는 함정 — 모두 다시 설명해야 한다.

harness-maker 는 3계층 메모리로 이 문제를 해결한다:

```
Hot tier  → .claude/memory/session/<today>.md   (compaction 체크포인트 — execute 재개)
Warm tier → .claude/memory/wiki.md              (재사용 패턴·관례)
          → .claude/memory/failures.md          (실패 사례 + 해결책)
Cold tier → git log, work-docs/PLAN-*.md       (결정 이력)
```

**wrapup 이 매 작업 단위마다 메모리를 갱신**한다:

- `wiki.md`: `[wiki:pattern]`, `[wiki:convention]` 등 카테고리 태그로 분류. `rg -F "[wiki:" wiki.md` 로 즉시 검색.
- `failures.md`: `[fail:import]`, `[fail:hook]` 등. **같은 slug 는 중복 섹션 대신 count 를 증가**시킨다. `rg -F "[fail:" failures.md` 로 반복 패턴 추적.

다음 세션의 execute 가 Warm tier 를 로드할 때는 `rg -F "[fail:" failures.md` 로 현재 작업 영역과 관련된 실패 패턴만 타깃 검색한다. 전체 파일을 읽지 않아도 된다.

---

### 11.2 실패 카운트 → 자동 개선 제안 루프

**일반 워크플로우**: 같은 실수를 3번 해도 3번 모두 수동으로 고친다. 아무도 "왜 이걸 계속 틀리나?" 라는 질문을 체계적으로 묻지 않는다.

harness-maker 는 wrapup 이 실패 항목의 `count` 를 추적하고, **count ≥ 3 이 되면 자동으로 개선 제안을 생성**한다:

```markdown
# .claude/memory/pending-proposals.md
## Proposal: {제목} (2026-05-09)
**Triggered by:** [fail:hook] ws2-ntfs-edit (count: 3)
**Proposed mechanism:** 새 스킬 | 규칙 업데이트 | 에이전트 추가 | 훅 수정
**Rationale:** 이 실패가 자동화된 가드로 방지됐을 3번의 이유
```

사용자가 제안을 검토하고 채택하면 새 스킬/에이전트/훅이 하네스에 추가된다. **harness-maker 가 스스로의 업그레이드를 제안하는 피드백 루프**다.

---

### 11.3 PreCompact 훅 + checkpoint:compaction — 컨텍스트 압축에도 작업이 유실되지 않는다

**일반 워크플로우**: Claude 컨텍스트가 꽉 차면 자동 압축(compaction)이 발생한다. 진행 중인 작업 상태가 날아가고, 어디서부터 다시 시작해야 하는지 알 수 없다.

harness-maker 는 `PreCompact` 훅이 압축 **직전**에 발동한다:

```
PreCompact → flush_session → .claude/memory/session/<today>.md 에 상태 기록
```

저장 내용:
- 현재 진행 중인 stage (execute Phase C 등)
- `.claude-progress.json` 에 in-progress 단계 상태
- `checkpoint:compaction` 마커

다음 세션에서 Hot tier 를 읽으면 `checkpoint:compaction` 항목을 발견하고 `.claude-progress.json` 을 참조해 **마지막 in-progress 단계부터 정확히 재개**한다. 수동으로 "어디까지 했더라?" 를 물을 필요가 없다.

---

### 11.4 프롬프트 캐시 진단 (Layer 3) — 왜 캐시 미스가 나는지 원인별로 분류한다

**배경**: Anthropic 프롬프트 캐시는 5분 TTL 이다. 캐시가 잘 적중하면 토큰 비용이 줄고 응답이 빠르다. 그런데 캐시 미스가 왜 나는지 일반적으로는 알 수 없다.

`ai-readiness-rubric` 의 Layer 3 는 `metrics.jsonl` (모든 도구 호출 로그)을 분석해 **캐시 미스 원인을 4가지로 분류**한다:

| 분류 | 의미 | 대처 |
|------|------|------|
| `min_threshold` | 프리픽스가 Anthropic 캐시-쓰기 최소 크기 미달 | 컨텍스트 증가 또는 다른 캐시 전략 |
| `invalidation` | 프리픽스가 변경돼 캐시 무효화 | 컨텍스트 안정성 개선 |
| `ttl` | 마지막 사용 후 >5분 경과 | loop 대기시간을 270s 이내로 조정 |
| `first` | 첫 사용 (예상된 미스) | 정상, 조치 불필요 |

이 분류 결과가 AI Readiness composite score 의 5%(`cache` 레이어)를 구성한다. **`ttl` 미스가 많으면 loop 타이밍 문제, `invalidation` 미스가 많으면 컨텍스트 구조 문제**라는 진단을 내릴 수 있다.

---

### 11.5 Context Linter — 프롬프트 크기 통제가 곧 캐시 효율이다

**일반 워크플로우**: 에이전트 프롬프트, CLAUDE.md, 스킬 파일이 점점 길어진다. 길어질수록 모델 attention 이 분산되고, 프롬프트 캐시 적중에 불리해진다.

`context-linter` 는 모든 생성 자산에 **preset 별 줄 수 한계**를 강제한다:

```
Side preset:    CLAUDE.md ≤200줄, agent ≤150줄, skill ≤100줄
Production:     CLAUDE.md ≤500줄, agent ≤200줄, skill ≤150줄
```

한계 초과 시: "trim 권장 줄 수 + 인라인 대신 외부 문서 링크 사용" 제안.

**왜 이것이 캐시와 연결되는가**: 프리픽스가 작을수록 캐시에 올리기 쉽고, 변경이 적을수록 `invalidation` 미스도 줄어든다. 컨텍스트 크기 통제 = 캐시 hit rate 최적화의 선행 조건.

---

### 11.6 Conditional Router — 필요한 리뷰어만 호출해 토큰을 아낀다

**일반 워크플로우**: 코드를 리뷰할 때 모든 전문 리뷰어를 동시에 호출하면 토큰 비용과 지연이 커진다.

`conditional-router` 스킬은 변경된 파일 경로를 분석해 **관련 있는 리뷰어만 선택**한다:

```
diff 경로 분석 → 보안 코드? security-reviewer 추가
               → UI 파일?   ux-reviewer 추가
               → 동시성?    concurrency-reviewer 추가
               → 성능?      performance-reviewer 추가
               + code-reviewer 항상 포함
```

`routing: always-all` 설정으로 항상 전체를 호출하는 것도 가능하지만, 기본값은 conditional 라우팅. **불필요한 전문 리뷰어를 생략 → 토큰 비용 + 리뷰 레이턴시 절감**.

---

### 11.7 2-pass 리댁션 (+47pp precision) — 메타데이터 앵커링을 차단한다

**일반 리뷰의 함정**: PR 제목이 "성능 최적화"라고 되어 있으면, 리뷰어 LLM 이 그 프레임에 앵커링돼 보안 문제를 간과할 수 있다. 저자 이름, 커밋 메시지, PR 설명이 모두 "앵커"가 된다.

harness-maker 의 2-pass 리댁션:

```
Pass 1: PR title/author/description → [REDACTED]
        리뷰어가 순수 코드만 보고 판단 → 금지되지 않은 편견 없이 findings 생성

Pass 2: 메타데이터 복원
        Pass 1 findings 에 맥락 반영 → 맥락이 찝찝한 발견 제거
        Pass 2 가 Pass 1 findings 를 override (CP10 계약)
```

ablation 실험에서 **+47 percentage-point precision 향상** 확인. CLI 기반 리댁션으로 결정적 처리 (`python -m harness_maker.two_pass_review redact`).

---

### 11.8 consensus-arbiter — "같은 위치" 를 넘어 "같은 이유" 를 따진다

**일반 멀티-리뷰어 방식의 문제**: 3개 리뷰어가 같은 줄을 지적해도 "race condition" vs "null deref" vs "wrong timeout" 이라고 다르게 진단할 수 있다. 단순 위치 매칭으로 합의 처리하면 3개가 동의한 것처럼 보이지만 실제로는 의견이 다른 상태.

consensus-arbiter 의 2단계 필터:

**Step 1 — Surface Match (후보 선별)**:
같은 파일 + 줄±5 + 같은 severity tier → 후보

**Step 2 — Reasoning Alignment (검증)**:
OBSERVE → INFER → CONCLUDE 체인 비교:
- CONCLUDE 가 같은 실행 위험을 지목 → `consensus-passed` (강한 합의)
- OBSERVE 일치, CONCLUDE 다름 → `weak-consensus` (양쪽 모두 보존, 수동 검토)
- OBSERVE 일치, reasoning 한쪽 부재 → `manual-only` (자동 수정 불가)

**자동 수정은 `consensus-passed` 만**. Weak-consensus 와 manual-only 는 사용자에게 별도 표시. 가짜 합의로 잘못된 수정이 적용되는 것을 방지.

---

### 11.9 ADR 기반 결정 영속화 — 설계 선택의 WHY 가 코드베이스에 산다

**일반 워크플로우**: "왜 Redis 대신 SQLite 를 썼나?" 라는 질문에 답할 수 있는 사람이 팀에 없어지면 영원히 알 수 없다. 다음 AI 세션은 이미 거부된 대안을 다시 제안한다.

harness-maker 의 `/hm:plan` 은 모든 아키텍처 결정을 ADR (Architecture Decision Record) 로 공식화한다:

```markdown
### ADR-001: Redis 대신 SQLite 사용
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** 단일 인스턴스 배포, 외부 서비스 의존성 최소화 요건
**Decision:** SQLite
**Consequences:**
- ✅ 외부 인프라 없이 동작
- ⚠️ 동시 쓰기 성능 제한
**Rejected alternatives:** Redis — 외부 서비스 운영 부담
**Source:** Interview #2
```

ADR 은 `/hm:execute` 에서 **구속력 있는 제약**이 된다. 구현이 ADR 을 위반해야 하는 상황이 오면 silent 진행 없이 에스컬레이션. 미래 AI 세션도 ADR 을 읽어 같은 결정을 반복하거나 이미 거부된 대안을 다시 고려하지 않는다.

---

### 11.10 생성 파일 Fingerprint + Block-Merge Marker — 업그레이드가 사용자 수정을 덮지 않는다

**일반 생성 도구의 문제**: 템플릿이 업그레이드되면 사용자가 직접 수정한 내용이 덮어씌워진다.

harness-maker 의 두 가지 보호 장치:

**1. content_hash fingerprint** (모든 생성 파일 frontmatter):
```yaml
content_hash: ca17023045fbd8f5ef8ad569d25098c062bd31ffaacb89bda428dd1b80eb87bd
```
재렌더 시: hash 일치 → "우리 것" → 자동 업그레이드 안전
hash 불일치 → "사용자 수정 있음" → KEEP (덮어쓰지 않음)

**2. Block-Merge Marker** (사용자 커스터마이제이션 영역):
```
<!-- @hm:user:extensions -->
사용자가 직접 추가한 내용 (이 블록은 upgrade 시 보존)
<!-- @hm:/user:extensions -->
```
템플릿 upgrade 가 이 블록 바깥을 업데이트해도 블록 안은 그대로 유지.

---

### 11.11 Drift Gate + pending-drift.md — 범위 이탈이 다음 세션에 전달된다

**일반 워크플로우**: 작업하다 보면 PLAN 범위 밖 파일이 바뀌거나, PLAN 에서 명시한 파일이 실수로 누락된다. 커밋 후에야 발견한다.

wrapup 의 Drift Gate 는 **커밋 전 advisory 체크**를 수행한다:

```
staged 파일 ∉ PLAN 스코프          → pending-drift.md 에 기록
PLAN 스코프 파일 ∉ staged          → incomplete-phase 경고
SPEC 시나리오 ∉ diff 테스트 커버리지 → missing-coverage 경고
```

커밋을 블록하지 않는다(advisory). 대신 `.claude/memory/pending-drift.md` 에 기록해 다음 세션의 Hot tier 에서 참조한다. 모른 채 넘어가는 대신 **추적 가능한 빚**으로 전환.

---

### 11.12 레퍼런스 문서 2-tier 검색 — 대용량 지식 베이스도 문맥에 맞는 것만 읽는다

**일반 워크플로우**: 관련 문서가 많으면 전부 컨텍스트에 올리거나, 아니면 검색하지 않는다.

`refdocs-search` 스킬은 `harness.yaml.ref_folders` 에 등록된 레퍼런스 폴더에 2-tier 검색을 수행한다:

```
Tier 1 (손실적 인덱스): ripgrep → 키워드 매칭으로 후보 파일 목록
Tier 2 (원본 확인):   Read   → 후보 파일 직접 읽어 실제 내용 검증
```

PDF 는 Read multimodal 로 페이지별 처리. DOCX 는 미지원(변환 필요).

**토큰 효율성**: 전체 지식 베이스를 컨텍스트에 올리는 대신, Tier 1 에서 관련 없는 파일을 걸러내고 Tier 2 에서 실제 내용만 올린다. `relevance-filter` 가 이어서 점수화해 0.7 미만 항목을 추가로 제거.

---

### 11.13 안티-rot 시스템 — 하네스 자체가 낡지 않는다

**일반 AI 개발 도구의 아이러니**: AI 도구가 새로운 Claude 기능을 활용하지 못하거나, 보안 취약점이 있는 의존성을 사용하거나, 베스트 프랙티스가 바뀌었는데 모른다.

harness-maker 는 주기적으로 **자기 자신의 freshness 를 검사**한다:

```
research-crawler → 4소스 크롤 (Anthropic 블로그/GitHub 릴리스/arxiv/OSV.dev CVE)
relevance-filter → LLM 관련성 점수화 (적응형 threshold: 0.5~0.9)
pending.jsonl   → 미처리 제안 큐
```

적응형 threshold 의 작동 방식:
- 과거 수락률 > 80% → 임계값 +0.05 (더 엄격하게, 노이즈 줄임)
- 과거 수락률 < 50% → 임계값 -0.05 (더 관대하게, 놓치지 않음)
- 범위: 0.5 ~ 0.9 (사용자 행동이 threshold 를 학습)

**verify-before-completion 이 pending.jsonl 을 게이트로 사용**: 미처리 제안이 있으면 wrapup 전 경고. `defer` 처리된 것만 OK.

---

### 11.14 7차원 AI Readiness + 확장 가능한 루브릭 YAML

**일반 접근**: 코드 품질은 테스트 커버리지 하나로 측정.

harness-maker 의 Layer 1 은 **7개 차원으로 AI-assistedness 를 정량화**:

| 차원 | 측정 대상 |
|------|---------|
| `context_quality` | CLAUDE.md 구조, 명확성, 크기 |
| `guardrails` | 권한 deny 규칙, 보안 게이트 |
| `verification` | 테스트 존재, CI 설정 |
| `workflow_clarity` | 슬래시 명령 완성도, stage 순서 |
| `memory_continuity` | wiki.md/failures.md 존재 + 내용 |
| `observability_setup` | metrics.jsonl, security findings |
| `governance` | ADR 존재, CONTRIBUTING.md |

Layer 2 의 루브릭은 확장 가능하다:

```yaml
# .claude/rubrics/my-custom-rubric.yaml
dimension: api-documentation
target: "src/**/*.py"
rubrics:
  - id: docstring-present
    description: Public functions have docstrings
    severity: P1
    action: Add one-line docstring explaining WHY, not WHAT
```

`.claude/rubrics/` 에 YAML 파일을 추가하면 다음 `/hm:ai-readiness` 에서 자동으로 적용. **프로젝트별 품질 기준을 코드로 표현** — 사람이 직접 체크하지 않아도 된다.

---

### 11.15 워크트리 격리의 결정적(Deterministic) 실행

**일반 접근의 위험**: 스킬이 trigger-based dispatch 방식이면 IDE 환경에 따라 확률적으로 실행될 수 있다. Cursor IDE 에서 trigger 가 silent skip 되면 메인 브랜치에 직접 편집이 일어난다.

harness-maker 는 워크트리 격리를 **항상 CLI 직접 호출로 결정적으로 수행**한다:

```bash
# 스킬에 위임하지 않고 CLI 를 직접 호출 — IDE 환경 무관
uv run python -m harness_maker.worktree create execute "$(pwd)"
```

각 `!` 블록이 독립 서브셸이므로 셸 변수가 유지되지 않는다 → 절대 경로를 매번 리터럴로 사용. Cursor 든 Claude Code 든 동일한 격리 보장.

---

### 11.16 무엇이 실제로 에이전트 경계를 강제하는가

> **2026-07-17 정정 (0.40.0).** 이 섹션은 예전에 에이전트 `permissions:`
> frontmatter 를 위한 "Write+Edit 페어링 불변식"을 문서화했다. 그 불변식은
> 겉치레였다: **subagent frontmatter 에는 `permissions:` 필드가 없어서**
> Claude Code 는 그런 블록을 전부 조용히 무시했다. 주석만 다는 대신 블록
> 자체를 삭제했다 — 이미 이 문서를 읽은 독자 한 명을 오도한 뒤였다.

서브에이전트를 실제로 묶는 것은 두 가지뿐이다:

1. **`tools:`** — 에이전트가 갖지 않은 도구는 사용할 수 없다. 이것이 진짜
   경계이며, read-only 리뷰어가 실제로 read-only 인 이유다: Bash 자체가
   없으니 `python -c "..."` 로 우회할 방법이 없다. `Bash` 를 다시 넣으면
   frontmatter 로는 좁힐 수 없는 무제한 쉘이 열린다.
2. **`settings.json` 의 `permissions`** — 강제되긴 하지만 **세션 전체
   단위**다: 메인 세션과 모든 에이전트에 동일하게 적용된다. "이 에이전트는
   `rm` 을 실행할 수 없다" 같은 표현은 불가능하다.

에이전트별 명령 스코핑은 frontmatter 로 표현할 수 없다. 필요하다면 에이전트
식별 기반 PreToolUse 훅이나 샌드박스가 유일한 방법이고, 둘 다
`--dangerously-skip-permissions` / `bypassPermissions` 에서 무력화된다.

**조용히 아무 효과도 없는 rule shape** (`permission_syntax.is_matchable_rule`
가 oracle 이고, `test_permission_syntax.py` 가 회귀 시 빌드를 fail 시킨다):

| Shape | 절대 매치되지 않는 이유 |
|---|---|
| `Write(<path>)`, `NotebookEdit(<path>)`, `Glob(<path>)` | 파일-권한 체크는 `Edit`/`Read` 만 참조한다 — `Edit(<path>)` 로 써야 한다 |
| `Bash(curl * \| sh)` | Bash 규칙은 `&&`, `\|\|`, `;`, `\|`, `&` 로 split 한 뒤 서브커맨드 단위로 매치된다 — separator 를 넘나드는 규칙은 절대 매치될 수 없고, 아무 경고도 뜨지 않는다 |

harness-maker 는 39개 릴리스 동안 이 셋을 그대로 배포했다. 그 위에 달린
설명은 우회 경로를 닫는다고 주장했지만, 한 번도 실제로 작동한 적이 없었다.

---

### 11.17 단일 커밋 계약 + WHY 중심 커밋 메시지

**일반 워크플로우**: execute → 커밋, review-fix → 커밋, 메모리 업데이트 → 커밋... git log 가 구현 중간 상태로 가득 찬다.

harness-maker 는 **wrapup 이 단 하나의 커밋**을 생성한다:

```
staged (execute 구현)
+ memory updates (wiki + failures)
+ PLAN status update
= 하나의 커밋
```

커밋 메시지는 **WHY 중심**:
```
feat(csv-parser): handle malformed headers without crashing

Error scenarios weren't specified in original SPEC (ADR-002 accepted this
gap). Chose fail-fast over silent recovery per Interview #3 — preserves
data integrity at cost of usability for edge cases.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

WHAT 은 diff 가 말한다. 커밋 메시지는 미래의 독자(새벽 2시의 oncall)에게 **의도와 맥락**을 전달한다. `git log` 가 의사결정 이력이 된다.

---

### 11.18 LLM-판단 우선 아키텍처 — 규칙 기반을 피한다

harness-maker 가 **regex/규칙 대신 LLM 판단을 사용**하는 구체적 사례들:

| 작업 | 나쁜 접근 | harness-maker 접근 |
|------|---------|----------------|
| "답변이 충분히 구체적인가?" 판단 | vague 키워드 regex | LLM 이 actionability 평가 |
| 인터뷰 후속 질문 생성 | 고정 질문 스크립트 | LLM 이 컨텍스트 읽고 동적 생성 |
| refresh 항목 관련성 점수화 | 키워드 매칭 | LLM 이 프로젝트 스택과 비교 판단 |
| prompt injection 후보 판정 | regex 만으로 결정 | regex 1차 → LLM 이 false positive 제거 |
| loop 종료 조건 평가 | 규칙 기반 체크리스트 | LLM 이 stopping_criteria 충족 여부 판단 |
| 누락된 인터뷰 차원 탐지 | 고정 체크리스트 | LLM 이 설명 읽어 이미 답된 차원 추출 |

이 설계 원칙은 CLAUDE.md 에 명시됨: "규칙 기반 대신 LLM 판단을 활용하여 품질을 극대화한다."

---

### 11.19 원자 파일 쓰기 — 인터럽트에도 파일이 깨지지 않는다

모든 파일 쓰기는 `tempfile + os.replace` 패턴:

```python
fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
# ... 내용 쓰기 ...
os.replace(tmp, path)  # POSIX + Windows 에서 atomic
```

중간에 프로세스가 종료돼도:
- 성공 전: `.tmp` 파일만 있음 (원본 그대로)
- 성공 후: 원자적 replace (중간 상태 없음)

WSL2/NTFS 환경에서 Edit 도구가 파일을 corrupt 할 수 있는 알려진 문제가 있어, harness-maker 는 해당 환경에서 `Write` (전체 파일 재기록) 를 강제한다.

---

### 11.20 100% 로컬 텔레메트리

`PostToolUse` 훅이 **모든 도구 호출을 캡처**한다 (matcher: `*`):

```jsonl
{"tool": "Edit", "file": "src/parser.py", "ts": "2026-05-09T04:02:12Z", "result": "ok"}
{"tool": "Bash", "cmd": "pytest -x", "ts": "2026-05-09T04:02:45Z", "result": "pass"}
```

이 데이터가 여러 목적으로 재사용된다:

| 소비처 | 사용 방식 |
|--------|---------|
| `verify-before-completion` Check 3 | health baseline vs 현재 점수 비교 |
| `ai-readiness-rubric` Layer 3 | cache miss 원인 분류 |
| `/hm:ai-readiness` 대시보드 | observability_setup 차원 점수 |

**외부로 전송되지 않는다**. CI 환경, private 레포, air-gapped 시스템 모두 동일하게 작동.

---

### 11.21 Deep Interview — 추측 대신 대화로 아키텍처를 잠근다

**Before**: 대부분의 AI 워크플로우는 작업 설명만 받고 구현에 들어간다. 모호한 요구사항은 구현 중에 발견되고, 그때 다시 돌아가서 고치는 비용이 발생한다.

**After**: `/hm:spec` 과 `/hm:plan` 은 구현 전에 심층 인터뷰를 시행한다. 질문은 고정 스크립트가 아니라 LLM 이 컨텍스트를 읽어 동적으로 생성한다.

#### /hm:spec 의 6-카테고리 인터뷰

SPEC 인터뷰는 **6개 카테고리를 순서대로** 커버한다:

| 카테고리 | 확인하는 것 |
|---------|-----------|
| Intent (의도) | 왜 이 기능이 필요한가, 무엇을 해결하는가 |
| Outcomes (성과) | 완료 기준, 측정 가능한 지표 |
| In-Scope Scenarios | "주어진 X일 때, Y하면 Z가 되어야 한다" 형식의 구체적 시나리오 |
| Non-Goals | 명시적으로 포함하지 않는 것 |
| Constraints | 기술적·비즈니스적 제약 |
| Verification | 어떻게 완료를 증명할 것인가 |

6개 카테고리 커버리지와 시나리오 구체성을 **completeness scorer** 가 0-1 점수로 평가한다. 점수 미달 시 부족한 카테고리만 추가 질문한다. 완료된 SPEC 은 `status: approved` 로 마킹되어 이후 `/hm:plan` 이 재질문을 생략한다 (Case A — 중복 인터뷰 없음).

#### /hm:plan 의 9-카테고리 우선순위 인터뷰

PLAN 인터뷰는 "어떻게 만들 것인가"를 결정한다. 질문 카테고리는 **영향도 역순**으로 진행된다:

1. Scope boundaries — 무엇이 포함/제외되는가
2. Architecture — 컴포넌트 소유권, 패턴 선택
3. Contract shape — API 서명, DB 스키마, 파일 형식
4. Risk tolerance — 안전/점진 vs 빠른/대담, 롤백 전략
5. Testing depth — 단위/통합/수동 범위
6. Implementation phasing — feature flag, 순서, 의존성
7. Dependencies — 라이브러리 추가 vs 직접 구현
8. Failure handling — 재시도, circuit-break, fallback
9. Observability — 로그 레벨, 메트릭 이름, 알림 임계값

#### ADR 자동 승격 — 5개 기준 중 하나라도 해당하면

인터뷰 답변이 다음 중 하나를 충족하면 해당 결정이 **Architecture Decision Record** 로 자동 승격된다:
- 컴포넌트 경계/소유권 변경
- 새로운 계약 (API, IPC, 스키마, 파일 형식, 프로토콜)
- 합리적인 대안을 명시적으로 기각
- 이번 태스크를 넘어서는 장기적 영향 (precedent 설정)
- 미래 유연성 제약 (프레임워크, 라이브러리, 프로토콜 고착)

ADR 에는 `Context / Decision / Consequences / Rejected Alternatives` 가 기록된다. `/hm:execute` 는 이를 **바인딩 제약**으로 취급 — ADR 에 위배되는 구현이 필요하면 blocker 로 에스컬레이션하지 않음.

#### plan-validator 에이전트 게이트

인터뷰 종료 후 PLAN 을 디스크에 쓰기 전에 `plan-validator` 에이전트가 독립적으로 검토:
- `APPROVED` → 바로 저장
- `NEEDS_REVISION` → 경고별 1회 추가 인터뷰 후 저장
- `MAJOR_REVISION` → 추가 인터뷰 → 재검증 1회. 두 번째도 통과 못 하면 사용자에게 에스컬레이션

#### "미결 결정 없음" 규칙

PLAN 저장 전, "Accept?", "OK?", "Verify?", "Should we?" 같은 표현을 스캔한다. 이런 표현이 남아 있으면 **놓친 인터뷰 라운드**를 의미한다 — PLAN 에는 체크리스트가 없고, 모든 판단은 인터뷰 트랜스크립트나 ADR 에 이미 기록된 상태여야 한다.

---

### 11.22 /hm:loop 적응형 인터뷰 + 수렴 루프 — 반복 실행이 목표를 향해 수렴한다

**Before**: "이 코드를 개선해줘" 같은 열린 요청은 한 턴으로 끝나거나, 각 턴이 서로 맥락을 잃고 무관한 방향으로 진행된다.

**After**: `/hm:loop` 는 **time-and-iteration bounded** 루프를 실행한다. 각 반복이 이전 반복의 결과를 읽고, 목표를 향해 수렴하는지 LLM 이 판단한다.

#### 두 가지 모드

| 모드 | 명령 | 목적 |
|-----|------|-----|
| **feature** | `/hm:loop feature "설명"` | 목표 또는 SPEC 파일을 향해 점진적 구현 |
| **improve** | `/hm:loop improve "설명"` | 기존 코드를 반복적으로 개선, 수렴 조건 충족 시 종료 |

#### autoloop-driver 의 5차원 적응형 인터뷰

루프 시작 전 `autoloop-driver` 스킬이 **LLM 이 설명을 읽어 이미 답된 차원을 추출**하고, 부족한 차원만 질문한다:

| 차원 | 내용 |
|------|------|
| purpose | 이 루프가 달성해야 하는 것 |
| invariants | 반복 중 깨뜨리면 안 되는 불변조건 |
| priority | 어떤 측면이 가장 중요한가 |
| stopping_criteria | 언제 "충분히 완료됐다"고 보는가 |
| out_of_scope | 명시적으로 건드리지 않을 것 |

"CSV 파서에 에러 핸들링 추가" 처럼 상세한 설명이면 purpose 는 이미 답된 것으로 처리하고 나머지 차원만 질문한다. **고정 스크립트 없이** LLM 판단으로 필요한 질문만 한다.

#### 단일 워크트리 공유 + autoloop-coder 권한 제한

루프 전체에서 **하나의 워크트리**를 공유한다. 반복마다 새 브랜치를 만들면 체크아웃 오버헤드가 누적되는데, 단일 공유 워크트리는 이를 방지한다.

코드 작성은 `autoloop-coder` 에이전트가 수행:
- **write-tool-only**: 탐색 없이 지정된 작업만 실행 (open-ended exploration 금지)
- 워크트리 경계 내 쓰기만 허용
- CLAUDE.md + TECH_SPEC.md 우선 — 모호하면 자율 결정 후 log, **사용자 질문 도구 호출 금지**

#### 수렴 판단은 LLM 이 한다

각 반복 종료 시 `autoloop-driver` 가 `stopping_criteria` 를 현재 코드 상태와 비교해 수렴 여부를 판단한다. 고정 규칙 체크리스트가 아니라 **LLM 이 결과물 전체를 읽고** "이 정도면 목표가 달성됐는가"를 판단한다. 판단이 YES 면 루프를 종료하고 wrapup 으로 진행한다.

#### 시간·반복 횟수 경계 + 증거 보존

무한 루프 방지를 위해:
- `max_iterations` (기본값: harness.yaml 설정에 따름)
- `max_duration_minutes` (시간 초과 시 안전 종료)

실패한 반복은 워크트리를 보존(`fail` finalize) 해 사용자가 어느 단계에서 멈췄는지 확인할 수 있다.

---

### 11.23 TDD Phase A.5 게이트 — 테스트가 진짜 RED 인지 구현 전에 검증한다

**Before**: AI 가 테스트와 구현을 함께 쓰거나, 테스트를 썼어도 항상 통과하는 tautology 테스트를 쓴다. 테스트가 실제로 구현 부재를 잡는지 아무도 확인하지 않는다.

**After**: `/hm:execute` 는 테스트를 구현 전에 작성하고 (Phase A), `test-reviewer` 에이전트가 테스트 파일을 독립 검토한다 (Phase A.5). 구현은 Phase C 에서 시작한다.

#### 8개 금지 패턴 — 하나라도 해당하면 FAIL

`test-reviewer` 에이전트가 아래 패턴을 탐지하면 `FAIL` 판정:

| 패턴 | 예시 | 문제 |
|-----|-----|-----|
| Tautology | `assert True`, `assert len(x) >= 0` | 구현과 무관하게 항상 통과 |
| Stub-only | `pass`, `raise NotImplementedError` | 실질적 검증 없음 |
| Framework-check-only | `import mymodule; assert True` | 임포트 성공만 검증 |
| Over-mocking | 테스트 대상 자체를 mock | 실제 코드를 테스트하지 않음 |
| Scenario-ID 불일치 | `test_s3_foo` 가 Scenario 3 이 아님 | SPEC 추적 불가 |
| 매직 값 assertion | SPEC 에 없는 상수 비교 | SPEC 와 테스트 분리 |
| 실패 억제 | `try...except: pass` | 에러를 무시하는 테스트 |
| private 상태 assertion | `._internal_state == x` | 구현 세부사항에 결합 |

#### passing_tests[] 동결 + RED-correctness

`test-reviewer` 가 `PASS` 판정한 테스트는 `passing_tests[]` 로 기록되어 **이후 재시도에서 재작성 불가** — 이미 검증된 테스트를 수정하면 품질 기준이 무의미해지기 때문이다.

테스트를 수정한 뒤에는 Phase B (RED 게이트) 에서 실제로 FAIL 하는지 확인한다. 우연히 PASS 하면 (false-RED) Phase A 로 돌아가 재작성 — 구현이 없어도 통과하는 테스트는 의미가 없다.

재시도 예산: **2회**. 2회 연속 FAIL 이면 `stuck` 에이전트로 에스컬레이션.

---

### 11.24 `stuck` 에스컬레이션 에이전트 — 블로킹이 두 번 반복되면 전용 분석가가 개입한다

**Before**: 워크플로우가 막히면 사용자가 오류 메시지를 읽고 직접 원인을 찾는다. 여러 시스템(PLAN, SPEC, REVIEW, ADR)에 분산된 정보를 종합해야 한다.

**After**: `stuck` 에이전트가 모든 컨텍스트를 읽어 **단일 구속 제약** (single binding constraint) 을 찾고 2-3개의 구체적 해결 경로를 제안한다. 각 경로는 trade-off 와 관련 ADR 번호를 포함한다.

#### 트리거 조건

| 상황 | 세부 |
|-----|-----|
| Phase A.5 재시도 소진 | test-reviewer 2회 연속 FAIL |
| Phase D 수정 불가 | PLAN 범위 변경 없이는 해결 불가한 실패 |
| ADR 충돌 | 구현이 ADR 을 위반해야만 진행 가능 |
| 리뷰 교착 | 3개 리뷰어가 동일 이슈에 상충 CONCLUDE |
| plan-validator 2차 MAJOR | 두 번의 검증에서 모두 심각한 문제 |

#### 분석 방법

`stuck` 에이전트는 전체 PLAN + SPEC + REVIEW + 최근 3개 리뷰어 출력 + 실패 로그를 읽은 뒤:

1. **증상 vs 근본 제약 분리** — "테스트가 실패한다" 가 아니라 "ADR-002 가 이 API 형식을 금지하는데 SPEC S3 이 그 형식을 요구한다" 같은 근본 제약을 찾는다
2. **2-3개 해결 경로 제안** — 각각의 trade-off 와 관련 ADR/Interview 번호 포함
3. **우선 경로 권장** — 현재 결정 맥락과 가장 일관된 경로를 권장
4. **에스컬레이션 노트 저장** — `.claude/memory/escalations/escalation-{slug}-{date}.md`

`stuck` 은 **읽기 전용 조언자** — 직접 코드를 수정하지 않는다. 결정은 사용자에게 돌아간다.

---

### 11.25 6-checkpoint verify 게이트 — "완료"를 diff 와 건강 지표로 이중 검증한다

**Before**: "테스트가 통과하면 완료"로 간주한다. PLAN 에 쓴 내용이 실제 구현됐는지, 보안 취약점이 없는지, 다른 품질 지표가 후퇴하지 않았는지는 검사하지 않는다.

**After**: `/hm:verify` (= `verify-before-completion` 스킬) 가 6개 체크포인트를 순서대로 실행하고 **첫 번째 실패에서 즉시 블로킹**한다.

#### 6개 체크포인트

| # | 체크 | 판정 방식 | 실패 시 |
|---|-----|---------|--------|
| 1 | PLAN 이행 | **LLM 이 diff 와 PLAN 항목을 직접 대조** | 미이행 항목 목록 표시 |
| 2 | 회귀/스모크 | `.claude-verify.sh` 실행 | 실패 테스트 출력 |
| 3 | 헬스 점수 -5 이내 | `compute_readiness()` vs 베이스라인 | 6차원 breakdown |
| 4 | 안티-rot 펜딩 해소 | `pending.jsonl` 미처리 항목 확인 | `/hm:refresh` 실행 안내 |
| 5 | high-severity 보안 없음 | `findings.jsonl` count 확인 | 발견 목록 표시 |
| 6 | 워크트리 merge-safe | `git diff --check` + 충돌 마커 확인 | 충돌 경로 표시 |

#### Check 1 이 LLM 판단인 이유

PLAN 이행 여부는 체크박스 체크만으로는 판정할 수 없다. PLAN 의 "CSVParser.parse() 구현" 항목이 실제로 `git diff` 에 있는지, 구현 내용이 PLAN 의 의도와 일치하는지는 **LLM 이 두 문서를 동시에 읽고 판단**한다. subprocess 로 자동 판정하면 PLAN 에 체크만 하고 코드를 안 쓴 경우를 못 잡는다.

#### Check 3 이 단순 테스트 통과와 다른 이유

테스트는 통과해도 AI Readiness composite 점수가 5점 이상 하락할 수 있다. 예를 들어 새 코드가 문서화 비율을 낮추거나, 모듈 결합도를 높이거나, 타입 힌트를 빠뜨리면 테스트는 통과해도 Check 3 에서 잡힌다. 이 체크는 "지금 잘 동작하는가"가 아니라 "코드베이스 전반의 품질이 후퇴하지 않았는가"를 측정한다.

---

### 특장점 요약표

| 특장점 | 해결하는 문제 | 관련 컴포넌트 |
|--------|------------|------------|
| 3-tier 메모리 | 세션 간 지식 유실 | wiki.md / failures.md / session/ |
| 실패→개선 루프 | 같은 실수 반복 | wrapup count≥3 / pending-proposals |
| PreCompact + checkpoint | 컨텍스트 압축 시 작업 유실 | flush_session 훅 / .claude-progress.json |
| 캐시 miss 원인 분류 | 왜 비싼지 모름 | Layer 3 cache_diagnostics (Claude Code 세션 트랜스크립트 기반) |
| Context Linter | 프롬프트 bloat → 캐시 비효율 | context-linter 스킬 |
| Conditional Router | 불필요한 리뷰어 → 토큰 낭비 | conditional-router 스킬 |
| 2-pass 리댁션 | 메타데이터 앵커링 | two_pass_review CLI (+47pp) |
| Reasoning Alignment | 가짜 합의 → 잘못된 수정 | consensus-arbiter 에이전트 |
| ADR 시스템 | 설계 결정 WHY 유실 | /hm:plan interview / PLAN-*.md |
| Fingerprint + Block-merge | 업그레이드가 커스터마이제이션 덮음 | content_hash / @hm:user:* markers |
| Drift Gate | 범위 이탈 감지 못함 | wrapup Step 3 / pending-drift.md |
| 2-tier refdocs 검색 | 대용량 지식 베이스 전체 로드 | refdocs-search + relevance-filter |
| 안티-rot 시스템 | 하네스 자체가 낡음 | research-crawler / pending.jsonl |
| 7차원 AI Readiness | AI 준비도 단일 지표 | ai-readiness-rubric / rubrics/*.yaml |
| 결정적 워크트리 격리 | IDE 환경 따라 격리 확률적 실패 | worktree CLI 직접 호출 |
| `tools:` 기반 에이전트 경계 | frontmatter permissions 는 silent-ignore (가짜 경계) | agent `tools:` allowlist / 메인세션 settings.json deny |
| 단일 커밋 + WHY 메시지 | git log 가 중간 상태로 오염 | wrapup Step 7 |
| LLM 판단 우선 | regex/규칙의 false positive/negative | 전 시스템 |
| 원자 파일 쓰기 | 인터럽트 시 파일 corruption | atomic_write 패턴 |
| 100% 로컬 텔레메트리 | 외부 전송 우려 | PostToolUse hook / metrics.jsonl |
| Deep Interview (spec/plan) | 추측으로 구현 → 나중에 재작업 | 6-카테고리/9-카테고리 + ADR 승격 + plan-validator |
| loop 적응형 인터뷰 + 수렴 루프 | 열린 요청이 발산하거나 맥락 유실 | autoloop-driver / autoloop-coder / stopping_criteria |
| TDD Phase A.5 테스트 품질 게이트 | tautology 테스트가 false-GREEN 을 만들고 구현으로 진행 | test-reviewer / 8-banned-patterns / passing_tests[] freeze |
| stuck 에스컬레이션 에이전트 | 블로킹 시 원인 파악과 해결 경로 탐색이 사용자 몫 | stuck / escalation-{slug}-{date}.md |
| 6-checkpoint verify 게이트 | 테스트 통과 ≠ 완료 (PLAN 이행·건강 지표·보안 미확인) | verify-before-completion / Check1 LLM 대조 / Check3 헬스 회귀 |

---

*이 문서는 harness-maker 0.7.1 기준. 생성: `/hm:execute how-it-works-docs`*
