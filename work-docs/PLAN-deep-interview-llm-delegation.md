---
type: plan
task_slug: deep-interview-llm-delegation
status: complete
created: 2026-05-10
tags: [harness-maker, plan, interview, requirements-elicitation, prompt-engineering, llm-quality]
research_doc: "[[RESEARCH-deep-interview-llm-delegation]]"
interview_rounds: 3
adrs: 4
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Add 3-layer deep interview gate (GCIC+Implicit Probing+Ambiguity Score) to spec/plan/research/loop"
---

# 🎯 Executive Summary

**What**: 4개의 인터뷰 탑재 스테이지(spec/plan/research --deep/loop)에 **3-layer deep interview gate**를 추가한다.

**Why**: ReqElicitGym(arXiv 2602.18306) 실증 연구에서 최고 성능 LLM의 암묵적 요구사항 포착률은 IRE=0.32 — 68%를 놓친다. 특히 Style 요구사항. 현재 harness-maker 인터뷰는 명시적 질문 카테고리만 커버하고, 역방향 probing과 정량적 수렴 판단이 없다.

**Key Decisions**:
- ADR-001: Implicit Probing = LLM 동적 생성 + CLARITI 필터(relevance×answerability ≥ 0.7)
- ADR-002: GCIC는 기존 구조 위에 overlay (renaming 없음)
- ADR-003: Ambiguity Score 시각 표시 + 2-round streak convergence
- ADR-004: 4스테이지 동시 구현, j2 템플릿 수정 → /hm:make 렌더

**Impact**: 암묵적 요구사항 포착률 ~32% → ~55~65% 예상 (Layer 2 추가 기준). 총 질문 수 -40% (CLARITI 필터). 수렴 신뢰성 향상 (false-convergence 감소).

---

## 📚 Prior Work

- [[work-docs/RESEARCH-deep-interview-llm-delegation.md]] — arXiv 9개 논문 분석. 핵심: LHAW 4차원, CLARITI 필터, Ouroboros streak
- [[work-docs/RESEARCH-loop-interview-intensity.md]] — loop 4-gate 수렴 + intensity 인터뷰. ADR-003의 streak=2 직접 근거
- [[.claude/memory/failures.md]] — `snapshot-regen-inside-worktree`: snapshot은 반드시 repo root에서 실행
- [[.claude/memory/wiki.md]] — `loop-4gate-convergence`: convergence는 독립 게이트 원칙

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|-------|----------|-------------------|---------|--------|------|-------|
| 1 | 적용 깊이 | Scope | 4 스테이지를 동일 수준 적용할까? | A:동일/B:spec·plan 풀, research·loop 부분/C:loop 제외 | A — All same | — | — |
| 2 | Implicit Probing 방식 | Architecture | 동적 생성 vs 고정 3문? | A:LLM동적+CLARITI/B:고정3문/C:pool에서LLM선택 | A — LLM dynamic | CLAUDE.md 원칙: LLM판단 > 패턴 | ADR-001 |
| 3 | GCIC 통합 방식 | Architecture | gap-check overlay vs 기존 구조 renaming? | A:overlay/B:renaming/C:메타 체크만 | A — overlay | 기존 YAML 파일 보호, 최소 diff | ADR-002 |
| 4 | Score 가시성 | Architecture | 시각 표시 vs 내부 신호 vs pass/fail 체크리스트? | A:시각표시/B:내부신호/C:체크리스트 | A — visual | 디버깅 용이, 투명성 | ADR-003 |
| 5 | Streak 요건 | Architecture | 1회 vs 2회 연속 통과? | A:1회/B:2회 | B — 2 rounds | Ouroboros 원칙 동일 적용 | ADR-003 |
| 6 | 구현 phasing | Implementation | 4개 동시 vs 순차? | A:동시/B:spec→plan→loop→research | A — all at once | 일관성 우선 | ADR-004 |
| 7 | 대상 파일 | Implementation | j2만 vs rendered만 vs 둘 다? | A:j2/B:rendered/C:둘다 | C — both | j2 수정 → /hm:make → rendered 확인 | ADR-004 |
| V1 | GCIC/Score 차원 불일치 | Resolution | Inputs·Context를 Score에 포함할지? | validator 지적 | Layer1=4dim, Layer3=3dim Ouroboros | Inputs·Context는 Layer1에서만 gate | ADR-003 |
| V2 | Research --deep 교체 vs 추가 | Resolution | 기존 5문 rubric 교체 vs additive? | validator 지적 | ADDITIVE — 기존 rubric 유지 + GCIC overlay 추가 | breaking change 방지 | — |

---

## 📐 Architecture Decision Records

### ADR-001: Implicit Probing = LLM 동적 생성 + CLARITI 필터
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** 고정 역방향 3문은 컨텍스트에 무관하게 항상 발화 — solo script 태스크에 "검토자 기준"을 묻는 것은 사용자 피로만 높임. CLAUDE.md 최우선 원칙: "규칙 기반 대신 LLM 판단".
**Decision:** 명시 수집 완료 후, LLM이 현재 컨텍스트를 읽고 5개 후보 question 유형(하단 §Architecture 참조) 중 CLARITI 필터(task relevance × user answerability ≥ 0.7) 통과한 1–3개를 동적 생성.
**Consequences:**
- ✅ 컨텍스트에 맞는 질문만 발화 → 사용자 피로 감소, 답변 품질 향상
- ⚠️ 생성 질문이 라운드마다 비결정적 — 단, CLARITI 필터가 최소 품질 보장
**Rejected alternatives:**
- Fixed 3 questions — 항상 동일 질문 → 무관한 컨텍스트에 noise
- Pool에서 LLM 선택 (5→2) — 여전히 부분 고정. 완전 동적 생성보다 coverage 낮음
**Source:** Interview #2

### ADR-002: GCIC = 기존 인터뷰 구조 위에 overlay (renaming 없음)
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** 기존 구조 변경 시: spec 6-category → 기존 SPEC 파일 호환 깨짐, loop 5차원 → loop-context YAML on-disk 파일 파싱 실패 위험. CLAUDE.md §6 양방향 매퍼: "persist한 것은 reverse mapper가 있어야".
**Decision:** 기존 인터뷰 카테고리(spec: Intent/Outcomes/Scenarios/Non-Goals/Constraints/Verification, loop: purpose/invariants/priority/test_reliability/stopping_criteria)는 변경 없음. 기존 답변 수집 완료 후 GCIC gap-check step을 overlay로 실행. LLM이 수집된 답변을 GCIC 4차원에 매핑하고 미커버 차원만 추가 질문.
**Consequences:**
- ✅ 기존 YAML/SPEC 파일 완전 backward-compat
- ✅ 최소 diff — 각 스테이지 템플릿에 새 섹션 삽입만
- ⚠️ GCIC 차원과 기존 카테고리 사이에 개념적 overlap. 단, 실제 충돌 없음.
**Rejected alternatives:**
- Full renaming — loop-context YAML 파일(extra="forbid") 파싱 실패. 대규모 migration 필요
- Phased dim-by-dim rename — 결국 full rename과 동일 cost, 혼란만 가중
- GCIC as separate post-interview command — 기존 인터뷰와 분리 실행 시 UX 단절. 하나의 흐름이어야 함
**Source:** Interview #3

### ADR-003: Ambiguity Score = 시각 표시 + 2-round streak, Layer1은 4dim, Layer3은 3dim
**Status:** Accepted (2026-05-10, via /hm:plan interview + validator V1 resolution)
**Context:** Ouroboros에서 검증: 단일 LLM "looks good" 판단은 false-convergence의 근본 원인. ReqElicitGym에서 확인: LLM의 자체 이해도 과대평가 경향. LHAW는 Goals/Constraints/Inputs/Context 4차원. Ouroboros는 Goal(40%)+Constraint(30%)+SuccessCriteria(30%) 3차원 가중 수식.
**Decision:**
- Layer 1 GCIC gap-check: 4차원 (Goals/Constraints/Inputs/Context) — 각 0/0.5/1.0 평가
- Layer 3 Ambiguity Score: 3차원 가중 수식 (Goal×0.4 + Constraint×0.3 + SC×0.3)
- Inputs, Context: Layer 1에서 gap 발견 시 CLARITI 필터 통과 질문 → 해소된 Inputs는 Constraints/Goals Score에 귀속됨
- 표시 형식: 차원별 점수 + 가중 합계 + ✅/⚠️ 아이콘
- 수렴 조건: 총점 ≥ 0.8 AND 모든 차원 ≥ 0.7, 2회 연속
- **Score monotonicity rule**: 이전 라운드와 동일한 답변 상태에서 점수는 감소 불가. 0.1 이상 감소 시 LLM은 반드시 이유를 명시해야 함 (validator warning #6 해결)
**Consequences:**
- ✅ 투명한 진행 상황 표시. 디버깅 용이.
- ✅ 2-round streak → false-convergence 방지
- ⚠️ 최소 2라운드 소요 (단일 라운드 종료 불가)
**Rejected alternatives:**
- 1-round — Ouroboros 실증에서 false-convergence 직접 원인
- Score 내부 신호만 — LLM 오채점 시 디버깅 불가
**Source:** Interview #4, #5, Validator V1

### ADR-004: 4스테이지 동시 구현, j2 + rendered 둘 다
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** 스테이지가 혼재하는 기간을 최소화해야 UX 일관성 보장. j2만 변경 시 /hm:make 전까지 실제 사용자는 old behavior.
**Decision:** 4개 j2 템플릿 동시 수정 → /hm:make로 렌더 → 렌더된 .md 파일도 commit. 버전업(4파일)을 Phase 0으로 선행.
**Consequences:**
- ✅ UX 일관성. 사용자가 어떤 스테이지를 먼저 써도 동일 경험.
- ⚠️ 단일 PR에서 8개 파일(j2 4 + rendered 4) + 버전 4파일 변경
**Rejected alternatives:**
- 순차 (spec→plan→loop→research) — 혼재 기간에 UX 불일치
**Source:** Interview #6, #7

---

## 🏗️ Technical Design

### Current State

| Stage | Interview mechanism | Gap |
|-------|---------------------|-----|
| `spec.md.j2` | 6-category (Intent/Outcomes/Scenarios/Non-Goals/Constraints/Verification) | Layer1·2·3 없음 |
| `plan.md.j2` | unlimited-round priority-ordered interview + ADR | Layer1·2 없음, Layer3(score)은 Step E에 부재 |
| `research.md.j2` | `--deep` Phase 0: 고정 rubric 5문 | LLM-동적 아님, CLARITI 없음, Layer3 없음 |
| `loop.md.j2` | 4-G(intensity)+4-B(5dim)+4-C(ambiguity)+4-D(features)+4-E(convergence) | Layer1·2 없음, 4-E 이후 정량 수렴 없음 |

### Affected Components

```
src/harness_maker/templates/stages/spec.md.j2      ← add §2.5 (3-layer gate)
src/harness_maker/templates/stages/plan.md.j2      ← add to Step E exit check
src/harness_maker/templates/stages/research.md.j2  ← Phase 0: add GCIC overlay AFTER rubric
src/harness_maker/templates/commands/hm/loop.md.j2 ← add §4-H after §4-E

.claude/commands/hm/spec.md      ← rendered (via /hm:make)
.claude/commands/hm/plan.md      ← rendered (via /hm:make)
.claude/commands/hm/research.md  ← rendered (via /hm:make)
.claude/commands/hm/loop.md      ← rendered (via /hm:make)

tests/snapshot/                  ← baseline update
pyproject.toml                   ← version bump
src/harness_maker/__init__.py    ← version bump
.claude-plugin/plugin.json       ← version bump
.cursor-plugin/plugin.json       ← version bump
```

**No Python code changes.** `interview.py`, `synthesize.py`, `models.py`, `harness.yaml` schema 모두 불변.

### 3-Layer Deep Interview Gate Text (shared structure)

각 스테이지 템플릿에 삽입할 공통 gate 구조 (스테이지별 삽입 위치와 헤딩 번호만 다름):

---

```markdown
#### [STAGE-SPECIFIC HEADING]. 3-Layer Deep Interview Gate

이 게이트는 스테이지별 명시 인터뷰 카테고리 완료 **후**, 인터뷰 종료 **전**에 항상 실행된다.

**Layer 1 — GCIC Gap Check**

지금까지 수집된 답변을 4개 차원에 매핑:
- **Goals**: 달성해야 할 최종 상태가 명확히 정의됐나? (score: 0.0 = 없음 / 0.5 = 부분 / 1.0 = 명확)
- **Constraints**: 위반하면 안 되는 경계가 명확히 정의됐나? (score: 0.0 / 0.5 / 1.0)
- **Inputs**: 사용 가능한 리소스·시작 상태가 명확히 정의됐나? (score: 0.0 / 0.5 / 1.0)
- **Context**: 환경(팀·툴링·타임라인·검토자)이 명확히 정의됐나? (score: 0.0 / 0.5 / 1.0)

차원 점수 < 0.7이면, AskUserQuestion 전에 **CLARITI 필터** 적용:
1. Task Relevance: "이 차원을 알면 태스크 결과가 실질적으로 달라지나?" (0–1)
2. User Answerability: "사용자가 지금 현실적으로 대답 가능한가?" (0–1)
→ 둘 다 ≥ 0.7이면 질문 생성. 하나라도 < 0.7이면 해당 차원은 "LLM-inferred"로 로깅하고 건너뜀.

**Layer 2 — Implicit Probing**

현재 수집된 컨텍스트를 읽고, LLM이 아래 5개 후보 유형 중 컨텍스트에 가장 relevant한 1–3개 역방향 질문을 동적으로 생성:
- "이 결과를 보고 **잘못됐다**고 할 조건은?" (암묵적 거부 기준)
- "내가 어떤 **방식**으로 구현할 거라 가정하나?" (암묵적 방법 제약)
- "이 결과를 **누가** 검토·사용하고, 그 기준은?" (암묵적 이해관계자)
- "어떤 **형식·스타일** 요구가 있나?" (Style 요구사항 — ReqElicitGym 최대 취약점)
- "어떤 **성능·규모** 기대치가 있나?" (암묵적 벤치마크)

각 후보에 CLARITI 필터 적용 (relevance × answerability ≥ 0.7). 통과한 것만 AskUserQuestion에 포함.

**MUST NOT repeat**: 이전 라운드에서 이미 물어본 질문 유형은 재발화 금지. 새 NEEDS 라운드에서는 새로운 유형만 선택.

**Layer 3 — Ambiguity Score (매 라운드 표시)**

수집 상태를 정량화하여 표시:

```
Ambiguity Score: {X.X}/1.0  (Goal×40% + Constraint×30% + SC×30%)
  Goals:             {g:.1f}/1.0  {"✅" if g≥0.8 else "⚠️"}
  Constraints:       {c:.1f}/1.0  {"✅" if c≥0.8 else "⚠️"}
  Success Criteria:  {sc:.1f}/1.0 {"✅" if sc≥0.8 else "⚠️"}
  Weighted total:    {g*0.4 + c*0.3 + sc*0.3:.2f}
  → {"PASS" if total≥0.8 and all≥0.7 else "NEEDS"} (연속 streak: {N}/2)
```

- Inputs·Context: Layer 1에서 gap 발견 시 해소됐으면 Goals/Constraints Score에 반영됨. 별도 가중치 없음.
- **Score monotonicity rule**: 이전 라운드 대비 동일 답변 상태에서 점수 감소 불가. 0.1 이상 감소 시 반드시 이유 명시.

**수렴 조건**: weighted total ≥ 0.8 AND 모든 차원 ≥ 0.7, **2회 연속** → 인터뷰 종료.
- NEEDS이면: Layer 1로 재진입(실패 차원에 집중), Layer 2 new probes 생성 (이전 질문 반복 금지).
- 최대 3라운드. 3라운드 후에도 NEEDS이면 "현재 정보로 진행" 선택지 + AskUserQuestion 1회.
```

---

### Insertion Points per Stage

**spec.md.j2**: `### Step 2 — Interview (default ON)` > `#### 2.1 Six interview categories` 블록 **다음**에 `#### 2.5 — 3-Layer Deep Interview Gate` 추가.

**plan.md.j2**: `#### Step E — Exit check` 의 "Zero high/medium-impact ambiguities remain" 조건 **앞**에 gate 삽입. Exit = gate PASS(2회 streak) AND zero remaining ambiguities.

**research.md.j2**: `### Phase 0 — Refinement interview (only when --deep is set)` 의 기존 rubric 5문 섹션 **다음**에 `#### Phase 0.5 — 3-Layer Deep Interview Gate` 추가. 기존 rubric은 유지 (additive). 다만 Phase 0.5의 GCIC gap-check에서 rubric이 커버한 차원은 건너뜀.

**loop.md.j2**: `#### 4-E. Convergence` 섹션 **다음**에 `#### 4-H. 3-Layer Deep Interview Gate` 추가. 4-H 완료(2-round streak PASS) 후 → 4-F (Persist context).

---

## 📝 Implementation Plan

### Phase 0 — Version bump (4 files)
**Scope**: pyproject.toml, src/harness_maker/__init__.py, .claude-plugin/plugin.json, .cursor-plugin/plugin.json
**Change**: 현재 0.8.0 → 0.8.1 (동작 변경이므로 patch bump)
**Exit criterion**: `grep -r "0.8.1" pyproject.toml src/harness_maker/__init__.py .claude-plugin/plugin.json .cursor-plugin/plugin.json | wc -l` = 4
**Risk**: low
**Rollback**: git checkout the 4 files

### Phase 1 — spec.md.j2
**Scope**: `src/harness_maker/templates/stages/spec.md.j2` only
**Change**: Insert `#### 2.5 — 3-Layer Deep Interview Gate` after `#### 2.1 Six interview categories` block (before `#### 2.2 Promotion rule`)
**Exit criterion**: `grep -c "GCIC Gap Check" src/harness_maker/templates/stages/spec.md.j2` ≥ 1
**Risk**: low
**Rollback**: git checkout src/harness_maker/templates/stages/spec.md.j2

### Phase 2 — plan.md.j2
**Scope**: `src/harness_maker/templates/stages/plan.md.j2` only
**Change**: In `#### Step E — Exit check`, insert gate section before the final exit condition. Gate PASS(2-round) becomes one of two AND conditions for exit.
**Exit criterion**: `grep -c "GCIC Gap Check" src/harness_maker/templates/stages/plan.md.j2` ≥ 1
**Risk**: low
**Rollback**: git checkout src/harness_maker/templates/stages/plan.md.j2

### Phase 3 — research.md.j2
**Scope**: `src/harness_maker/templates/stages/research.md.j2` only
**Change**: After Phase 0 rubric 5-question block, insert `#### Phase 0.5 — 3-Layer Deep Interview Gate`. Existing rubric untouched. Gate's Layer 1 skips dims already answered by rubric.
**Exit criterion**: `grep -c "GCIC Gap Check" src/harness_maker/templates/stages/research.md.j2` ≥ 1 AND `grep -c "Scope narrowing" src/harness_maker/templates/stages/research.md.j2` ≥ 1 (rubric still present)
**Risk**: low
**Rollback**: git checkout src/harness_maker/templates/stages/research.md.j2

### Phase 4 — loop.md.j2
**Scope**: `src/harness_maker/templates/commands/hm/loop.md.j2` only
**Change**: Insert `#### 4-H. 3-Layer Deep Interview Gate` between `#### 4-E. Convergence` and `#### 4-F. Persist context`
**Exit criterion**: `grep -c "GCIC Gap Check" src/harness_maker/templates/commands/hm/loop.md.j2` ≥ 1
**Risk**: medium (loop.md.j2는 600+ lines — 삽입 위치 정확도 필수. 4-E와 4-F 사이의 정확한 라인 확인 후 삽입)
**Rollback**: git checkout src/harness_maker/templates/commands/hm/loop.md.j2

### Phase 5 — Render + verify
**Scope**: `.claude/commands/hm/` (rendered output)
**Change**: `uv run python -m harness_maker.cli make "$(pwd)" --update`
**Exit criterion**: `grep -c "GCIC Gap Check" .claude/commands/hm/spec.md .claude/commands/hm/plan.md .claude/commands/hm/research.md .claude/commands/hm/loop.md | grep -v ":0"` — 4줄 모두 non-zero
**Risk**: low (idempotent render, re-runnable on failure)
**Rollback**: re-run Phase 1–4 if templates are correct; if render fails, diagnose CLI error first

### Phase 6 — Snapshot baselines update
**Scope**: `tests/snapshot/`
**Change**: `python tests/snapshot/regenerate.py` from **repo root** (not worktree)
**Exit criterion**: `uv run pytest tests/snapshot/ -q` → 0 failures
**Risk**: low
**Rollback**: git checkout tests/snapshot/

### Phase 7 — Full test suite + lint + context lint
**Scope**: read-only verification
**Check**:
```bash
uv run pytest --tb=short -q
uv run ruff check src/
uv run mypy --strict src/
# Context lint: rendered files stay within Production 500-line limit
wc -l .claude/commands/hm/loop.md .claude/commands/hm/spec.md .claude/commands/hm/plan.md
```
**Exit criterion**: 0 failures, 0 ruff errors, 0 mypy errors. loop.md < 700 lines (현재 655 + 약 50라인 추가 예상 → 705 전후 — CLAUDE.md Production 500행 제한 초과 여부 확인; 초과 시 renderer가 warn)
**Risk**: low
**Rollback**: N/A (read-only)

---

## 🚫 Non-Goals (명시적 제외)

이 PLAN이 **건드리지 않는 것들**:
- `interview.py` — Python 인터뷰 로직. 변경 없음.
- `synthesize.py` — 렌더 로직. 변경 없음.
- `models.py` / `InterviewAnswers` / `ImprovementContext` — 스키마 변경 없음.
- `harness.yaml` 스키마 — 변경 없음.
- spec의 6-category 기존 body text — 구조 유지, 새 섹션만 추가.
- loop의 5차원(purpose/invariants/...) 기존 body text — 구조 유지.
- `.cursor/rules/*.mdc` — Cursor 사이드 파일 변경 없음.
- `loop-context/*.yaml` on-disk 파일 — backward-compat 유지.
- SPEC 파일(`specs/SPEC-*.md`) — 변경 없음.

---

## 🧪 Testing Strategy

### Automated
- Snapshot tests: 4개 스테이지 × 2개 preset(Side/Production) baseline 업데이트
- `grep` exit criteria: 각 Phase에서 "GCIC Gap Check" 존재 확인

### Manual (named checklist items)

다음 시나리오를 `/hm:spec`, `/hm:plan`, `/hm:research --deep`, `/hm:loop` 각각에서 수동 검증:

| # | Scenario | Expected |
|---|----------|---------|
| M1 | 의도적으로 모호한 goal("make it better") 입력 후 Layer 3 실행 | Score < 0.8 표시, NEEDS 출력 |
| M2 | 모든 답변을 명확히 입력 후 2라운드 진행 | Round 1: PASS, Round 2: PASS, 인터뷰 종료 |
| M3 | Solo script 태스크에서 Layer 2 Implicit Probing | "이해관계자" 질문이 CLARITI < 0.7로 skip됨 |
| M4 | 이전 라운드와 동일한 답변으로 NEEDS 반복 | 동일 질문 유형 재발화 없음 |
| M5 | 3라운드 후에도 NEEDS | "현재 정보로 진행" AskUserQuestion 표시 |
| M6 | Score 표시 형식 | `Ambiguity Score: 0.78/1.0 (Goal:0.85 ✅ Constraint:0.70 ✅ SC:0.75 ✅)` |

---

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|-----------|
| loop.md.j2 삽입 위치 오판 (600+ lines) | medium | Read 4-E~4-F 사이 exact lines 확인, unique anchor text로 삽입 |
| LLM이 동일 답변 상태에서 라운드마다 다른 점수 산출 (flapping) | medium | ADR-003 monotonicity rule: 감소 시 이유 명시 강제. 최대 3라운드로 무한 loop 방지 |
| Context lint 초과: loop.md 700행 근접 | medium | Phase 7에서 wc -l 체크. 초과 시 gate 텍스트 condensing 또는 include macro 도입 |
| Snapshot regen을 worktree 안에서 실행 | low | failures.md 항목 존재. Phase 6에서 "repo root" 명시 |
| Research --deep 기존 rubric + Phase 0.5 gate = 질문 과다 | low | Phase 0.5 Layer 1이 rubric 커버 차원 skip. 실제 추가 질문 ≤ 3개 |
| /plugin update 미인지 (버전 미변경 시) | high | Phase 0 버전 bump 선행으로 해결 |
| Phases 1-4 이후 Phase 5 실패 시 partial state | low | Phase 5 idempotent (재실행 가능). 실패 시 git reset으로 일괄 롤백 |

---

## ✅ Success Criteria

- [x] 4개 j2 템플릿 각각 `grep -c "GCIC Gap Check"` ≥ 1
- [x] 4개 rendered .md 파일 각각 `grep -c "GCIC Gap Check"` ≥ 1
- [x] Research --deep: `grep -c "Scope narrowing"` ≥ 1 (기존 rubric 유지 확인)
- [x] `uv run pytest --tb=short -q` → 0 failures
- [x] `uv run ruff check src/` → 0 errors
- [x] `uv run mypy --strict src/` → 0 errors
- [x] 버전 4파일 동기화: `grep -r "0.8.1" pyproject.toml src/harness_maker/__init__.py .claude-plugin/plugin.json .cursor-plugin/plugin.json | wc -l` = 4
- [x] Snapshot baselines updated and passing
- [x] M1~M6 manual scenarios verified on at least one stage

---

## 🔍 Plan Validation

**Validator outcome**: NEEDS_REVISION (10 warnings) → RESOLVED

| # | Warning | Resolution |
|---|---------|-----------|
| W1 | Layer1 4dim vs Layer3 3dim 불일치 | ADR-003에 명시: I·C는 Layer1에서 gate, Score는 Ouroboros 3dim formula. Monotonicity rule 추가 |
| W2 | Phase 4 exit criterion `grep -c '4-H'` 불일치 | `grep -c 'GCIC Gap Check'`로 통일 (Phase 1–4 일관) |
| W3 | Research --deep: replace vs additive 모순 | 명확히 ADDITIVE — 기존 rubric 유지 + Phase 0.5 overlay |
| W4 | Layer2 NEEDS 라운드에서 반복 질문 위험 | "MUST NOT repeat" 규칙 명시 |
| W5 | Testing 너무 얇음 | M1~M6 named manual checklist 추가 |
| W6 | LLM score inconsistency 위험 | Monotonicity rule을 ADR-003에 포함, Risks table에 추가 |
| W7 | 버전 bump 없음 | Phase 0 버전 bump 선행 |
| W8 | Non-Goals 없음 | §Non-Goals 섹션 추가 |
| W9 | ADR-002 rejected alternatives 부족 | ADR-002에 3개 rejected 옵션 |
| W10 | Cross-phase rollback 모호 | Phase 5 idempotent 명시, git reset 전략 |
