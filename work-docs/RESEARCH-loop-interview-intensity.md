---
type: research
task_slug: loop-interview-intensity
status: complete
created: 2026-05-10
tags: [harness-maker, research, autoloop, interview, exit-criteria, convergence, intensity]
mtime_warn_days: 14
libs_fetched: []
sources:
  - https://github.com/Q00/ouroboros/blob/main/README.ko.md
  - https://github.com/Q00/ouroboros/blob/main/src/ouroboros/bigbang/ambiguity.py
  - https://github.com/Q00/ouroboros/blob/main/src/ouroboros/evolution/convergence.py
  - https://github.com/Q00/ouroboros/blob/main/src/ouroboros/evolution/loop.py
  - https://github.com/Q00/ouroboros/blob/main/src/ouroboros/bigbang/interview.py
  - https://github.com/Q00/ouroboros/blob/main/src/ouroboros/evaluation/pipeline.py
related_docs:
  - "[[work-docs/RESEARCH-loop-longevity-strategies.md]]"
  - "[[work-docs/PLAN-loop-longevity-strategies.md]]"
  - "[[.claude/commands/hm/loop.md]]"
  - "[[.claude/skills/autoloop-driver/SKILL.md]]"
  - "[[src/harness_maker/autoloop_driver.py]]"
summary: "Pre-loop intensity interview + multi-gate convergence (Ouroboros-inspired) eliminates single-LLM false-convergence"
---

# 🎯 Recommended Direction

**Two changes, one principle**: 루프 시작 전 `loop_intensity` 인터뷰를 추가하고(`--intensity quick|standard|thorough|maximum`), 현재의 단일 LLM 판단("evaluate stopping_criteria") 수렴 체크를 **다층 독립 게이트**로 교체한다.

근거: Ouroboros (`Q00/ouroboros`)를 직접 분석한 결과, 이 시스템이 "LLM이 애매하게 멈추는 문제"를 실제로 해결한 방식은 수렴 판단을 **9개의 독립 게이트**로 쪼개는 것이었다. 단일 LLM 판단 1개 → 기계적 체크 + 개별 LLM 체크 + streak 카운터로 분해. harness-maker 현재 구현은 improve mode에서 "No issues OR criteria met → mark converged"라는 단 한 줄로 수렴을 결정 — 이것이 애매한 종료의 근본 원인이다.

---

## 🔍 Ouroboros 분석 요약

### 철학: "먼저 측정하라, 판단 말고"

Ouroboros는 harness-maker와 목적이 다르다(스펙 수렴 vs 코드 구현 루프). 하지만 **수렴 판단을 LLM에 위임하는 문제**를 둘 다 공유하고, Ouroboros가 더 앞서 해결했다.

#### 인터뷰 종료 조건 (harness-maker 인터뷰 참고)

Ouroboros의 인터뷰는 "사용자가 충분하다고 느끼면 종료"가 아니다:

```python
# ambiguity.py
AMBIGUITY_THRESHOLD = 0.2              # 80% 명확도 이상이어야 Seed 허용
SUCCESS_CRITERIA_CLARITY_FLOOR = 0.70  # Success Criteria 단독으로도 최소 70% 필요
AUTO_COMPLETE_STREAK_REQUIRED = 2      # 2 연속 라운드에서 threshold 통과해야 자동 종료
```

```
Ambiguity = 1 − Σ(clarityᵢ × weightᵢ)
  Goal (40%) + Constraint (30%) + Success Criteria (30%) ≤ 0.2 → 진행 허용
```

각 차원이 floor를 만족하고, 2 라운드 연속 threshold를 통과해야 인터뷰 자동 종료. "한 번 좋아 보여서 종료" 금지.

#### 수렴 판단: 9개 독립 게이트

`convergence.py`에서 확인된 게이트 전체:

| # | Gate | 타입 | 기계적/LLM |
|---|------|------|-----------|
| G1 | Ontology stability (similarity ≥ 0.95) | 수렴 | 수식 |
| G2 | Stagnation window (N연속 안정) | 수렴 | 수식 |
| G3 | Repetitive feedback detection (질문 반복 ≥70%) | 수렴 | 수식 |
| G4 | Hard cap (max_generations) | 강제 종료 | 수식 |
| G5 | Eval gate (score ≥ 0.7 AND approved) | **차단** | LLM |
| G6 | Per-AC gate (모든 AC 개별 통과) | **차단** | 기계적 |
| G7 | Regression gate (이전에 통과했던 AC 재실패 금지) | **차단** | 기계적 |
| G8 | Evolution gate (온톨로지가 한 번도 변하지 않으면 차단) | **차단** | 수식 |
| G9 | Validation gate (validation skipped/error 시 차단) | **차단** | 기계적 |

**핵심 인사이트**: 수렴 신호(G1~G4)가 발생해도 차단 게이트(G5~G9) 중 하나라도 실패하면 루프가 계속된다. "보기엔 수렴했는데 실제론 아닌" 케이스를 각각의 독립 검증이 잡는다.

#### 3단계 평가 파이프라인

```
Stage 1 (Mechanical, $0): lint + build + test → 기계적 PASS/FAIL
Stage 2 (Semantic):       LLM이 출력 품질 평가 (score 0~1)
Stage 3 (Consensus):      Stage 2가 불확실할 때만, 복수 모델 합의
```

Stage 1이 실패하면 Stage 2, 3를 실행하지 않는다. 비용 최적화 + 기계적 게이트 우선.

---

## 🛠️ Approaches Found

### Approach A: `loop_intensity` = 6번째 context dimension

| Field | Content |
|-------|---------|
| Approach | `ImprovementContext`에 `loop_intensity: Literal["quick","standard","thorough","maximum"]` 추가 |
| Assumption | 강도가 다른 컨텍스트 차원들(purpose, invariants...)과 동등한 수준의 persistent 정보 |
| Evidence | Ouroboros: ambiguity 점수의 가중치 자체가 greenfield/brownfield에 따라 다름 (4번째 dimension) |
| Trade-off | `ImprovementContext` schema에 필드 추가 → `extra="forbid"` 하에 기존 context YAML 파싱 실패 위험 |
| Compatibility | `default="standard"` 설정하면 backward compat 보장 |
| Risk | low |

### Approach B: 인터뷰 단계 4-G "Loop Configuration" 신설

| Field | Content |
|-------|---------|
| Approach | 5 dimensions 수집 후, loop 시작 전 전용 `AskUserQuestion` 1회: intensity 선택 + default checklist 제시 + "추가할 기준이 있나요?" |
| Assumption | intensity는 loop 운용 매개변수지 컨텍스트 차원이 아님. 5개 차원과 분리가 설계적으로 깔끔 |
| Evidence | Ouroboros도 인터뷰(bigbang)와 루프 설정(EvolutionaryLoopConfig)을 완전히 분리 |
| Trade-off | 인터뷰 단계 한 스텝 추가 → 유저 답변 1개 더. "빠른 시작"의 마찰이 소폭 증가 |
| Compatibility | loop.md.j2 + SKILL.md.j2만 변경. Python schema는 Approach A와 조합 가능 |
| Risk | low |

### Approach C: 수렴 체크를 다층 게이트로 재설계 (anti-ambiguous-stop)

| Field | Content |
|-------|---------|
| Approach | improve mode 수렴 체크를 "evaluate stopping_criteria" 1개 → 4개 독립 게이트로 분해 |
| Assumption | 단일 LLM 판단 → False Convergence의 근본 원인. Ouroboros가 검증한 처방 |
| Evidence | convergence.py: 9개 게이트 중 기계적 체크(regression, validation)가 LLM gate보다 먼저 실행됨 |
| Trade-off | 프롬프트 텍스트 증가 (~30행). 하지만 loop 실행 중에는 이 텍스트가 수렴 판단의 precision을 높여 재실행 비용 절감 |
| Compatibility | loop.md.j2 step 6 iteration body만 수정. autoloop_driver.py 불변 |
| Risk | low |

---

## 📐 상세 설계 (권장 방향)

### 1. `loop_intensity` 인터뷰 (step 4-G 신설)

```
step 4-G. Loop intensity & exit criteria 확정

단계 4-B~4-E 완료 후 루프 시작 전에, AskUserQuestion 1회:

질문: "이 루프를 어떤 강도로 실행할까요?"
옵션:
  - quick:    tests pass + lint clean                   (빠른 피드백, 품질 게이트 느슨)
  - standard: tests pass + review grade B + mypy pass   (균형)  ← default
  - thorough: tests pass + review grade A + mypy strict + ruff clean + all ACs
  - maximum:  thorough + security scan pass + no regressions from prior runs

강도 선택 후:
1. 선택된 강도의 default exit criteria checklist를 보여준다
2. stopping_criteria(4-B에서 수집)와 합산한 최종 checklist를 제시
3. "추가로 확인해야 할 기준이 있나요?" 묻기

최종 exit_criteria_checklist를 loop-context YAML에 저장.
```

#### 강도별 default checklist

| Intensity | Default Exit Criteria Checklist |
|-----------|--------------------------------|
| `quick`   | `uv run pytest --tb=short` GREEN, `ruff check` 0 errors |
| `standard`| quick + `uv run mypy --strict src/` clean + review grade ≥ B |
| `thorough`| standard + review grade = A + all acceptance criteria explicitly verified |
| `maximum` | thorough + security scan pass + no test regressions vs prior iter |

**핵심**: checklist 항목은 **실행 가능한 명령어** 형태로 저장. "tests pass"가 아니라 `uv run pytest --tb=short` — 수렴 체크 시 Claude가 이를 실행해서 PASS/FAIL을 얻어야 한다.

### 2. loop-context YAML schema 확장

```yaml
context:
  purpose: ...
  invariants: [...]
  priority: ...
  test_reliability: ...
  stopping_criteria: "..."   # 기존 prose (유지)
  loop_intensity: thorough   # NEW — default: standard
  exit_criteria_checklist:   # NEW — intensity default + user additions
    - cmd: "uv run pytest --tb=short"
      label: "All tests green"
      required: true
    - cmd: "uv run mypy --strict src/"
      label: "Type check clean"
      required: true
    - cmd: "review grade = A"
      label: "Review grade A (run /hm:review)"
      required: true
    - label: "All acceptance criteria explicitly verified"
      required: true
  notes: [...]
```

`loop_intensity` 와 `exit_criteria_checklist` 둘 다 `default_factory` 없이는 기존 YAML 파싱 실패. `ImprovementContext`에 `loop_intensity: str = "standard"` + `exit_criteria_checklist: list[dict[str, str]] = Field(default_factory=list)` 필수.

### 3. 수렴 체크 다층 게이트 (step 6 iteration body 수정)

현재 (ambiguous):
```
→ evaluate stopping_criteria. No issues OR criteria met → mark converged
```

개선 후 (4개 독립 게이트, Ouroboros-inspired):
```
수렴 선언 전 4개 게이트를 순서대로 통과해야 한다:

Gate 1 [기계적]: exit_criteria_checklist의 cmd 항목을 실행.
  → 하나라도 실패 → 수렴 거부. `failed_streak += 1`이 아닌 "계속" (진행 중인 것)

Gate 2 [LLM, 개별]: 각 "label" 항목을 개별 평가. aggregate "looks good"으로 묶지 말 것.
  → 기준: "이 항목이 현재 상태에서 명확히 충족되는가? 애매하면 NO"
  → 하나라도 NO → 수렴 거부

Gate 3 [회귀]: 이전 iter에서 통과했던 기계적 체크가 현재 iter에서 실패하는가?
  → YES → 수렴 거부 + 회귀 항목 report

Gate 4 [연속성]: 위 3개 게이트 모두 연속 2회 통과해야 수렴 선언.
  → "한 번 좋아 보임"으로 종료 금지. convergence_candidate_streak 카운터 유지.

모든 게이트 통과 → converged = True
```

---

## ⚠️ Pitfalls

1. **`extra="forbid"` 하에 새 필드 추가 시 기존 YAML 파싱 실패**: `ImprovementContext`에 `loop_intensity`, `exit_criteria_checklist` 추가 시 반드시 `default` 값 설정. 기존 loop-context 파일에 해당 키가 없으면 pydantic validation error.

2. **checklist 항목을 prose로 쓰면 Gate 1 실행 불가**: `cmd` 필드 없는 항목(label-only)은 Gate 2(LLM)만 체크. 설계 시 `required=true`인 항목은 반드시 `cmd` 병기 권장.

3. **intensity 선택 → 잘못된 default checklist**: `thorough`를 선택했는데 실제 프로젝트에 `mypy --strict` 설정이 없으면 Gate 1이 항상 fail → 루프 무한 진행. 4-G에서 체크리스트 제시 시, 해당 명령어가 프로젝트에 적용 가능한지 LLM이 판단 후 제시해야 함.

4. **convergence_candidate_streak을 loop-context YAML에 persist하지 않으면 재시작 시 streak 초기화**: 루프 재시작 시 streak을 0으로 리셋하는 것이 안전. 단, 이로 인해 convergence 지연이 최대 2 iter 추가 발생 — 허용 범위.

5. **Ouroboros의 Evolution Gate (온톨로지가 한 번도 변하지 않으면 차단)**: harness-maker의 improve mode에서도 동일 함정 존재 — iter마다 아무것도 바꾸지 않은 채 stopping_criteria를 충족했다고 LLM이 판단하면 수렴. Gate 2에서 "실제 코드 변경이 있었는가?" 항목 추가 고려.

---

## ❓ Open Questions (`/hm:plan`이 잠가야 할 것)

1. **`ImprovementContext` schema 변경 범위**: `loop_intensity: str = "standard"` + `exit_criteria_checklist: list[dict] = []` 추가 시 `extra="forbid"` 유지 여부. 유지하면 미지원 필드를 가진 옛 YAML이 여전히 파싱되지만(new fields have defaults), 옛 YAML에 예상치 못한 키가 있으면 pydantic이 거부 → `extra="ignore"`로 전환 검토.

2. **exit_criteria_checklist 스키마 타입**: `list[dict[str, str]]` vs 전용 `ExitCriterion` pydantic model. 후자가 mypy --strict 에 더 안전하지만 schema 변경 폭이 큼.

3. **Gate 4 (연속성 streak)**: loop-context에 `convergence_candidate_streak: int = 0` 저장 vs. 루프 실행 중 메모리만 유지. 재시작 복원 여부 결정 필요.

4. **feature mode에도 다층 게이트 적용**: 현재 feature mode는 "workflow returned success (review verdict ≥ grade_threshold and tests pass)" — 이미 2개 게이트. improve mode와 통일할지, feature mode는 현행 유지할지.

5. **4-G 인터뷰 skip 조건**: 기존 loop-context에 `loop_intensity`가 이미 있으면 skip. `--intensity` 플래그로 override 허용할지. 기존 spec 파일에 `intensity` 필드가 있으면 자동 적용할지.

---

## 📚 Sources

- [Q00/ouroboros README.ko.md](https://github.com/Q00/ouroboros/blob/main/README.ko.md) — Ambiguity Score 수식, 수렴 조건, Double Diamond 철학
- [ouroboros/bigbang/ambiguity.py](https://github.com/Q00/ouroboros/blob/main/src/ouroboros/bigbang/ambiguity.py) — 실제 ambiguity 점수 계산 구현: 가중치, floor, streak
- [ouroboros/evolution/convergence.py](https://github.com/Q00/ouroboros/blob/main/src/ouroboros/evolution/convergence.py) — 9개 수렴 게이트 전체 구현
- [ouroboros/evolution/loop.py](https://github.com/Q00/ouroboros/blob/main/src/ouroboros/evolution/loop.py) — EvolutionaryLoop: gen 1 vs gen 2+ 분기, SIGINT 처리
- [ouroboros/bigbang/interview.py](https://github.com/Q00/ouroboros/blob/main/src/ouroboros/bigbang/interview.py) — InterviewEngine: perspective rotation, round 무제한
- [ouroboros/evaluation/pipeline.py](https://github.com/Q00/ouroboros/blob/main/src/ouroboros/evaluation/pipeline.py) — 3단계 평가: Mechanical → Semantic → Multi-Model Consensus

---

## 🔗 Related Internal Docs

- [[work-docs/RESEARCH-loop-longevity-strategies.md]] — G5 (false convergence) gap 원래 식별
- [[work-docs/PLAN-loop-longevity-strategies.md]] — G1(stop hook), G3/G4(cap), G6(compaction) 이미 구현. 이번 연구는 **G5 직접 해결**
- [[.claude/commands/hm/loop.md]] — step 4 (interview), step 6 (iteration body) 수정 대상
- [[.claude/skills/autoloop-driver/SKILL.md]] — safety rails + convergence invariants 업데이트 대상
- [[src/harness_maker/autoloop_driver.py]] — `ImprovementContext` schema 확장 대상
