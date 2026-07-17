---
type: research
task_slug: deep-interview-llm-delegation
status: complete
created: 2026-05-10
tags: [harness-maker, research, interview, requirements-elicitation, task-delegation, llm-quality, clarification]
mtime_warn_days: 30
libs_fetched: []
sources:
  - https://arxiv.org/abs/2602.18306  # ReqElicitGym
  - https://arxiv.org/abs/2507.02564  # LLMREI
  - https://arxiv.org/abs/2507.02858  # Follow-up question generation
  - https://arxiv.org/abs/2511.08798  # SAGE-Agent (Structured Uncertainty)
  - https://arxiv.org/abs/2602.10525  # LHAW (Underspecification taxonomy)
  - https://arxiv.org/abs/2603.26233  # Ask or Assume? (Coding agents)
  - https://arxiv.org/abs/2604.14624  # Asking What Matters / CLARITI
  - https://arxiv.org/abs/2512.13154  # MAC (Multi-agent clarification)
  - https://arxiv.org/abs/2506.02827  # TO-GATE
related_docs:
  - "[[work-docs/RESEARCH-loop-interview-intensity.md]]"
  - "[[work-docs/PLAN-loop-interview-intensity.md]]"
  - "[[src/harness_maker/interview.py]]"
  - "[[.claude/commands/hm/loop.md]]"
  - "[[src/harness_maker/templates/stages/plan.md.j2]]"
summary: "3-layer deep interview: LHAW 4-dimension coverage + CLARITI relevance×answerability filter + Ouroboros streak convergence"
---

# 🎯 Recommended Direction

**3-layer deep interview 구조**를 harness-maker 전 단계(make, loop, research --deep, plan)에 일관 적용한다.

Layer 1 — **Dimension Coverage** (LHAW 기반): Goals / Constraints / Inputs / Context 4개 차원을 빠짐없이 커버하는 질문 세트.  
Layer 2 — **Implicit Requirement Probing** (ReqElicitGym 기반): 명시 요구사항 수집 후, "이걸 틀렸다고 할 조건은?" / "어떤 가정을 하고 있나?" 형태의 역방향 질문으로 암묵적 요구사항 강제 표면화.  
Layer 3 — **Convergence Gate** (Ouroboros 기반): Ambiguity Score(Goal 40% + Constraint 30% + Success Criteria 30%) ≥ 0.8 & 2회 연속 통과 → 인터뷰 종료.

**핵심 필터**: 각 질문 후보를 생성하기 전, CLARITI 원칙으로 사전 평가 — Task Relevance("이걸 알면 결과 달라지나?") × User Answerability("사용자가 실제로 대답 가능한가?") 두 조건 모두 0.7 이상인 질문만 상정. 이 필터로 질문 수 약 40% 감소, 품질은 유지.

---

## 🔍 문제 정의: 왜 "Deep Interview"가 필요한가

LLM에게 업무를 위임할 때 품질은 아래 세 요소의 곱에 비례한다:

```
Output Quality ∝ Spec Completeness × Spec Precision × Ambiguity Resolution
```

현재 harness-maker 인터뷰의 갭:

| 단계 | 현재 커버 | 갭 |
|------|-----------|-----|
| `/hm:make` 인터뷰 | locale, preset, dev_mode, workflows, consensus | Goals/Constraints/Context 미수집 |
| `/hm:loop` 인터뷰 | intensity + exit criteria (2026-05-10 추가) | 암묵적 요구사항 미표면화, 수렴 판단 1-shot LLM |
| `/hm:research --deep` | 3-5개 고정 rubric 질문 | 동적 생성 아님, 수렴 기준 없음 |
| `/hm:plan` 인터뷰 | 태스크 설명 + ADR | LHAW 4차원 체계 없음 |

---

## 🛠️ Approaches Found

### Approach A: LHAW 4-Dimension Framework (권장 기반)

| Field | Content |
|-------|---------|
| Approach | 모든 인터뷰를 Goals/Constraints/Inputs/Context 4차원 체계로 구조화 |
| Assumption | 스펙 미달의 근본 원인은 이 4개 차원 중 하나가 빠져서 발생 |
| Evidence | arXiv 2602.10525 (LHAW): 실증 실험에서 285개 태스크 분석 결과 스펙 갭은 전량 이 4차원으로 분류 가능 |
| Trade-off | 질문 수 증가 (dimension별 최소 1개씩). CLARITI 필터로 비필수 질문 제거 필요 |
| Compatibility | interview.py 에 `dimension: Literal["goal","constraint","input","context"]` 메타데이터 추가로 통합 가능 |
| Risk | low |

**4차원 상세**:
```
Goals      — 태스크가 달성해야 하는 것 (what success looks like)
Constraints — 위반하면 안 되는 경계 (runtime, budget, format, scope)
Inputs     — 사용 가능한 자원과 시작 상태 (files, APIs, prior context)
Context    — 환경과 시스템 컨텍스트 (team, tech stack, deadline, reviewers)
```

**Impact별 심각도 (LHAW 분류)**:
- outcome-critical: 없으면 태스크가 일관적으로 실패
- divergent: 없으면 결과가 실행마다 다름
- benign: LLM이 추론으로 메울 수 있음

인터뷰는 outcome-critical과 divergent만 질문. benign은 LLM이 추론.

---

### Approach B: CLARITI 2-Axis Question Filter (권장 필터)

| Field | Content |
|-------|---------|
| Approach | 질문 생성 전 Task Relevance × User Answerability 필터로 비효율 질문 사전 제거 |
| Assumption | 나쁜 질문의 원인은 두 가지: 알아도 결과에 영향 없거나(저 relevance) / 사용자가 대답 못함(저 answerability) |
| Evidence | arXiv 2604.14624 (CLARITI): Shapley attribution으로 relevance 측정, 두 필터 적용 시 GPT-5 수준 품질에서 질문 41% 감소 |
| Trade-off | 사전 relevance 추정에 LLM 판단 1회 추가 (비용 소폭 증가) |
| Compatibility | AskUserQuestion 직전에 LLM 내부 추론으로 수행 — Python 코드 변경 불필요 |
| Risk | low |

**적용 방법 (슬래시 명령 프롬프트에 추가)**:
```
질문 생성 전 내부 체크:
1. Task Relevance: "이 정보를 알면 태스크 결과가 실질적으로 달라지는가?" (0~1)
2. User Answerability: "사용자가 지금 이 질문에 현실적으로 답할 수 있는가?" (0~1)
둘 다 0.7 미만이면 질문 생략. 목표: 총 질문 수 5개 이하.
```

---

### Approach C: Bayesian EVPI 질문 순서화 (SAGE-Agent 방식)

| Field | Content |
|-------|---------|
| Approach | 질문 순서를 EVPI(Expected Value of Perfect Information) 내림차순으로 정렬 |
| Assumption | "가장 중요한 것부터" 순서가 조기 종료 + 핵심 누락 방지 |
| Evidence | arXiv 2511.08798 (SAGE-Agent): EVPI 기반 질문 순서로 7~39% coverage 향상, 질문 1.5~2.7배 감소 |
| Trade-off | EVPI 계산 자체가 LLM 추론 — 순서 오판 가능. 단, 단순 heuristic도 효과적 |
| Compatibility | 질문 목록 생성 후 LLM이 내부적으로 순서 재정렬 — 슬래시 명령 프롬프트 수정으로 구현 |
| Risk | low |

**Heuristic EVPI 순서 (추론 기반)**:
```
High EVPI: Goals > Constraints > Success Criteria > Context > Inputs
  Why: Goal을 모르면 모든 것이 흔들림. Input은 대부분 컨텍스트에서 추론 가능.
```

---

### Approach D: Implicit Requirement Probing (ReqElicitGym 인사이트)

| Field | Content |
|-------|---------|
| Approach | 명시 수집 완료 후, 암묵적 요구사항을 역방향 질문으로 강제 표면화 |
| Assumption | 사용자는 당연하다고 생각하는 것은 말하지 않음. 특히 style/format 관련 |
| Evidence | arXiv 2602.18306 (ReqElicitGym): IRE 최고점 0.32. Style 요구사항은 모든 LLM이 가장 많이 놓침 |
| Trade-off | 인터뷰 1-2 라운드 추가 |
| Compatibility | step 4-E (loop) 또는 plan.md.j2 에 "implicit probing" 섹션 추가 |
| Risk | low |

**역방향 질문 세트 (3개 고정)**:
```
1. "이 결과를 보고 '잘못됐다'고 할 조건이 있다면?" → 암묵적 거부 기준 표면화
2. "내가 어떤 방식으로 구현할 거라고 가정하고 있나?" → 암묵적 방법 제약 표면화
3. "이 결과를 누가 검토하고, 그 사람의 기준은?" → 암묵적 이해관계자 표면화
```

---

## 📐 통합 설계: 3-Layer Deep Interview

### 전체 흐름

```
Phase 0: Context Scan (30초)
  → 태스크 설명을 읽고 4차원(GCIC) 갭 목록 생성
  → EVPI 순서로 정렬
  → CLARITI 필터 적용 (relevance×answerability ≥ 0.7)

Phase 1: Explicit Coverage (≤ 4 questions)
  → AskUserQuestion: 고EVPI 순으로 Gap 해소
  → 각 답변 수신 시 remaining gap 목록 업데이트

Phase 2: Implicit Probing (1 AskUserQuestion, 3개 역방향 질문)
  → 반드시 실행 (explicit이 완전해 보여도)
  → 답변에서 새 Gap 발견 시 Phase 1 재진입 (최대 1회)

Phase 3: Convergence Check
  → Ambiguity Score = Goal(40%) + Constraint(30%) + SuccessCriteria(30%)
  → 각 차원: 명확히 정의됨(1.0) / 어느정도(0.7) / 모호(0.3) / 없음(0)
  → Score ≥ 0.8 AND 모든 outcome-critical gap 해소 → 종료
  → Score < 0.8 → Phase 1 재진입 (절대 최대: 총 3라운드)
```

### 단계별 적용

**`/hm:make` (하네스 설정 인터뷰)**:
현재 locale/preset/dev_mode/workflows 수집 완료 후:
- Phase 2 (Implicit Probing)만 추가: "이 하네스로 어떤 종류의 작업을 가장 많이 할 것 같나요? 가장 중요하게 생각하는 품질 기준은?"
- 설정 인터뷰 특성상 Phase 1은 existing questions가 대체

**`/hm:loop` (루프 위임 인터뷰)**:
이미 구현된 loop_intensity + exit_criteria 인터뷰에 추가:
- Phase 0: 태스크 설명에서 GCIC 갭 분석
- Phase 2: 역방향 3문 ("잘못됐다는 조건", "가정한 방식", "검토자 기준")
- Phase 3: Ambiguity Score ≥ 0.8 체크

**`/hm:research --deep` (리서치 심화 인터뷰)**:
현재 고정 rubric 5문 → 동적 EVPI 순 질문으로 교체:
- Phase 0: 토픽에서 4차원 갭 분석
- Phase 1: ≤3문 (CLARITI 필터 적용)
- Phase 2: 1문 ("이 리서치가 무엇을 찾으면 실패인가?" — 역방향)
- Phase 3: Ambiguity 체크 없이 명시 skip 옵션 포함

**`/hm:plan` (플랜 인터뷰)**:
현재 ADR 중심 → GCIC 명시 체계 추가:
- Phase 0-1: 태스크의 4차원 갭 해소
- Phase 2: "이 플랜으로 구현하면 안 되는 것이 있나?" (암묵적 제약 표면화)
- Phase 3: Ambiguity Score 0.8+ → 플랜 확정

---

## 📊 예상 효과 (논문 수치 기반)

| 지표 | 현재 | 개선 후 | 근거 |
|------|------|---------|------|
| 암묵적 요구사항 포착률 | ~32% | ~55~65% | ReqElicitGym + Implicit Probing 추가 |
| 질문당 정보 획득량 | baseline | +7~39% | EVPI 순서화 (SAGE-Agent) |
| 총 질문 수 | 미제어 | -40% | CLARITI 필터 |
| False Convergence | 단일 LLM 판단 | 최소화 | Streak 2회 + Ambiguity Score |

---

## ⚠️ Pitfalls

1. **CoT 추가만으로 Coverage 향상 착각**: ReqElicitGym 실증에서 CoT는 TKQR(질문 효율)만 향상, IRE(실제 요구사항 포착률)는 통계적으로 유의미한 향상 없음. Coverage는 Implicit Probing Phase가 담당해야 함.

2. **질문 수 최소화 집착 → Implicit 무시**: CLARITI 필터로 질문 수 줄이더라도 Implicit Probing 3문은 항상 실행. "명시적으로 다 물어봤으니 괜찮다"는 착각 금지.

3. **Ambiguity Score 자가 채점 과대**: LLM이 자기 이해도를 과대평가하는 경향 있음 (ReqElicitGym에서 확인). Score 임계값을 0.8로 올리고, "모든 outcome-critical gap이 해소됐는가?"를 별도 조건으로 추가.

4. **Style 요구사항 무시**: ReqElicitGym의 최대 취약점. "어떤 스타일/형식으로 보여줘야 하나?"를 Phase 1 Context 차원에 명시 포함.

5. **사용자 인터뷰 피로**: 총 질문 수가 5~7개 넘으면 사용자가 "그냥 해줘"로 단답 → 품질 저하. 최대 AskUserQuestion 2회(Phase 1: 1~2문 묶음, Phase 2: 3문 묶음)로 설계.

6. **Converge 속도 ≠ Converge 품질**: Ouroboros가 증명. Streak이 빠르면 false convergence 위험. 2회 연속 통과 요건은 타협하지 않는다.

---

## ❓ Open Questions (`/hm:plan`이 잠가야 할 것)

1. **4차원 갭 분석의 구현 위치**: Python(interview.py)에서 분석 후 질문 생성 vs. 슬래시 명령 프롬프트에서 Claude가 직접 수행. Python은 타입 안전하지만 동적 분석이 어려움. 슬래시 명령은 LLM 판단력 최대 활용 가능 (CLAUDE.md 최우선 원칙). **추천**: 슬래시 명령에서 Claude가 수행 — Python은 데이터 수집만.

2. **Ambiguity Score 계산 구현**: LLM이 내부적으로 계산 후 Boolean만 반환 vs. 실제 float 기록. 기록하면 YAML에 저장 가능 (디버깅 용이). 미기록이면 simpler.

3. **Implicit Probing을 언제 skip하나**: 태스크가 매우 단순하거나(1줄 수정) quick intensity를 선택한 경우, 역방향 3문 강제 실행은 과도할 수 있음. Skip 조건 정의 필요.

4. **기존 loop-context YAML에 GCIC 추가**: 현재 `ImprovementContext`는 purpose/invariants/priority/test_reliability/stopping_criteria/loop_intensity/exit_criteria_checklist. 여기에 `goals`/`constraints`/`inputs`/`context` 4필드 추가 시 schema 크기 증가. 필드 통합 or 분리 전략 결정 필요.

5. **loop --deep 플래그**: `/hm:loop` 에 `--deep` 플래그 추가 시, 기본(--standard)과 어떻게 다른 인터뷰를 실행할지 정의 필요. 기본은 intensity만, --deep은 full 3-layer.

---

## 📚 Sources

### 핵심 논문 (2025-2026)

- [LLMREI: Automating Requirements Elicitation Interviews with LLMs](https://arxiv.org/abs/2507.02564) — LLM 인터뷰 챗봇으로 요구사항 73.7% 자동 추출 (arXiv 2507.02564, July 2025)
- [ReqElicitGym: Evaluation Environment for Interview Competence](https://arxiv.org/abs/2602.18306) — 7개 대표 LLM 실증 평가: 최고 IRE=0.32, 암묵적 요구사항 <50% 포착, Style 요구사항이 가장 취약 (arXiv 2602.18306, Feb 2026)
- [Requirements Elicitation Follow-Up Question Generation](https://arxiv.org/abs/2507.02858) — "실수 유형 기반" follow-up 질문이 인간 질문보다 우수 (arXiv 2507.02858, July 2025)
- [Structured Uncertainty guided Clarification for LLM Agents (SAGE-Agent)](https://arxiv.org/abs/2511.08798) — POMDP+EVPI 기반 최적 질문 선택, 7-39% coverage 향상, 질문 1.5-2.7배 감소 (arXiv 2511.08798, Nov 2025)
- [LHAW: Controllable Underspecification for Long-Horizon Tasks](https://arxiv.org/abs/2602.10525) — Goals/Constraints/Inputs/Context 4차원 스펙 갭 분류 체계 (arXiv 2602.10525, Feb 2026)
- [Ask or Assume? Uncertainty-Aware Clarification-Seeking in Coding Agents](https://arxiv.org/abs/2603.26233) — 코딩 에이전트에서 "언제 물어보나" 보정: 단순 태스크는 가정, 복잡 태스크는 능동적 질문 (arXiv 2603.26233, March 2026)
- [Asking What Matters: Reward-Driven Clarification / CLARITI](https://arxiv.org/abs/2604.14624) — Task Relevance × User Answerability 2축 필터로 질문 41% 감소, GPT-5 수준 품질 유지 (arXiv 2604.14624, April 2026)
- [MAC: Multi-Agent Framework for Interactive User Clarification](https://arxiv.org/abs/2512.13154) — 단일 정밀 clarification 질문 + 전문가 에이전트 라우팅 (arXiv 2512.13154, Dec 2025)
- [TO-GATE: Clarifying Questions via Trajectory Optimization](https://arxiv.org/abs/2506.02827) — 궤도 최적화로 clarification 질문 생성 및 응답 요약 (arXiv 2506.02827, June 2025)

### 내부 Prior Art
- [Q00/ouroboros ambiguity.py](https://github.com/Q00/ouroboros/blob/main/src/ouroboros/bigbang/ambiguity.py) — Ambiguity Score 수식: Goal(40%)+Constraint(30%)+SuccessCriteria(30%), 2회 streak
- [Q00/ouroboros convergence.py](https://github.com/Q00/ouroboros/blob/main/src/ouroboros/evolution/convergence.py) — 9개 수렴 게이트

---

## 🔗 Related Internal Docs

- [[work-docs/RESEARCH-loop-interview-intensity.md]] — Ouroboros 기반 loop intensity 인터뷰 설계 (이 연구의 직접 선행)
- [[work-docs/PLAN-loop-interview-intensity.md]] — 4-gate convergence + intensity 인터뷰 구현 계획
- [[src/harness_maker/interview.py]] — 현재 make 인터뷰 구현 (locale/preset/dev_mode/workflows)
- [[src/harness_maker/templates/stages/plan.md.j2]] — plan 단계 프롬프트 (4차원 갭 분석 추가 대상)
- [[.claude/commands/hm/loop.md]] — loop 명령 (Phase 2 implicit probing 추가 대상)
