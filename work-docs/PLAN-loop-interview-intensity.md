---
type: plan
task_slug: loop-interview-intensity
status: complete
created: 2026-05-10
tags: [harness-maker, plan, autoloop, interview, exit-criteria, convergence, intensity]
research_doc: "[[RESEARCH-loop-interview-intensity]]"
interview_rounds: 3
adrs: 9
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "step 4-G intensity interview + 4-gate convergence replace single-LLM false-convergence"
---

# 🎯 Executive Summary

**What:** `/hm:loop` 시작 전 `loop_intensity` 인터뷰(step 4-G)를 추가하고, 현재의 단일 LLM 판단("evaluate stopping_criteria") 수렴 체크를 **4개 독립 게이트**로 교체한다.

**Why:** improve mode의 수렴 판단이 단일 LLM call 1개에 의존 — Ouroboros(`Q00/ouroboros`) 코드 분석에서 이것이 false convergence의 근본 원인임을 확인. Ouroboros는 9개 독립 게이트로 해결. 우리는 prompt-driven 환경에 맞게 4개 게이트로 적용.

**Key Decisions:**
- ADR-001: improve + feature 양쪽 모두에 적용
- ADR-002: 4-G는 4-A 이후, 4-B 이전 삽입
- ADR-003: feature mode checklist는 loop close 시점에만
- ADR-004: `ExitCriterion(BaseModel)` 타입 모델
- ADR-005: convergence_candidate_streak — 메모리만, 재시작 시 0 리셋
- ADR-006: intensity는 per-iter grade_threshold를 override 안 함
- ADR-007: `loop_intensity: Literal["quick","standard","thorough","maximum"] = "standard"`
- ADR-008: stopping_criteria measurable item 추출은 4-B 완료 후 재스캔
- ADR-009: `required=False` escape + 3회 연속 실패 시 override AskUserQuestion

**Estimated impact:** improve mode false convergence 제거. feature mode 루프 종료 전 품질 최종 검증 추가. 루프 시작 전 사용자가 강도와 exit criteria를 명시적으로 확정.

---

## 📚 Prior Work

- **RESEARCH-loop-interview-intensity.md** — Ouroboros 코드 직접 분석. 9-gate 수렴, ambiguity scoring, 인터뷰 streak 카운터 확인.
- **RESEARCH-loop-longevity-strategies.md** — G5 (false convergence via isolated verifier) 원래 식별. 이번 PLAN이 G5를 직접 해결.
- **PLAN-loop-longevity-strategies.md** — G1(stop hook), G3/G4(cap), G6(compaction) 이미 구현 완료 (0.7.3). 이번 PLAN은 해당 구현과 독립.
- **wiki.md `[wiki:architecture] generator-not-runtime-config`** — harness-maker는 Jinja2 pre-render. 새 step 4-G는 loop.md.j2 prompt text 추가로 구현 (Python 아님).
- **failures.md** — `extra="forbid"` + 새 필드: 새 필드에 default 있으면 기존 YAML 파싱 안전. 확인됨.

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Scope | Scope | intensity 인터뷰 + 다층 게이트: improve only vs both | 양쪽 모두 | feature mode도 loop-close 품질 게이트 필요 | ADR-001 |
| 2 | 4-G 위치 | Architecture | step 4-A 직후 vs 4-E 직후 vs 4-F 통합 | 4-B 직전 (4-A 직후) | intensity가 stopping_criteria 질문을 유도하도록 먼저 | ADR-002 |
| 3 | feature mode gate 시점 | Architecture | loop close vs per-iter | loop close | per-iter는 이미 grade_threshold+tests 2-gate 있음 | ADR-003 |
| 4 | Schema 타입 | Architecture | ExitCriterion(BaseModel) vs list[str] | ExitCriterion typed | mypy --strict 안전, cmd/label 구분 가능 | ADR-004 |
| 5 | Streak persistence | Architecture | YAML 저장 vs 메모리만 | 메모리만 | 스키마 단순, 재시작 시 2 iter 추가 허용 | ADR-005 |
| 6 | grade_threshold override | Architecture | intensity → per-iter grade_threshold도 덮어쓸지 | No — checklist만 | harness.yaml 설정 충돌 방지 | ADR-006 |
| 7 | intensity 타입 | Architecture | Literal 4개 값 vs str | Literal | pydantic strict=True에서 잘못된 값 즉시 오류 | ADR-007 |
| C1 | 4-G/4-B 순서 | Design | 4-G가 4-B 전이면 stopping_criteria 미반영 | 4-B 후 재스캔 추가 | validator C1 해결 | ADR-008 |
| C2 | feature escape hatch | Risk | checklist 실패 시 루프 무한 대기 방지 | required=False + 3회 override | validator C2 해결 | ADR-009 |

---

## 📐 Architecture Decision Records

### ADR-001: improve + feature 양쪽 모두 적용
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** loop_intensity 인터뷰와 exit_criteria_checklist를 improve mode만 적용할지, 두 모드 모두 할지 결정 필요.
**Decision:** 두 모드 모두 적용. feature mode에서는 exit_criteria_checklist가 loop close 시 최종 품질 게이트로만 작동 (per-iter에는 영향 없음).
**Consequences:**
- ✅ 루프 전체에 일관된 품질 기준. feature mode도 "완료"전 최종 검증 받음
- ⚠️ feature mode 변경 폭이 improve-only보다 약 2배
**Rejected alternatives:**
- improve only — feature mode는 per-feature AC가 있어 충분하다는 논리였지만, 루프 전체 품질 기준(security, regression 등)은 feature AC와 별개
**Source:** Interview #1

### ADR-002: step 4-G 위치 — 4-A 직후, 4-B 직전
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** intensity를 언제 물어야 stopping_criteria 질문 자체를 intensity에 맞게 유도할 수 있는가.
**Decision:** 4-A(read and extract) 직후, 4-B(interview for missing) 직전에 삽입. 4-A가 stopping_criteria를 이미 추출했으면 4-G에서 활용; 아직 미결이면 4-B에서 이후 수집.
**Consequences:**
- ✅ intensity가 stopping_criteria 질문의 구체성 수준을 유도 가능
- ⚠️ 4-A에서 stopping_criteria 미추출 시 4-G checklist는 intensity 기본값만 → ADR-008으로 보완
**Rejected alternatives:**
- 4-E 직후 — stopping_criteria는 이미 수집됐지만 "intensity가 먼저, 그에 맞는 기준을 수집"이라는 사용자 의도와 역순
- 4-F에 통합 — AskUserQuestion이 너무 많은 걸 한번에 묻게 됨
**Source:** Interview #2

### ADR-003: feature mode checklist — loop close 시점만
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** feature mode는 이미 per-iter "grade_threshold + tests pass" 2-gate 수렴이 작동 중.
**Decision:** exit_criteria_checklist는 feature mode에서 loop close 시 모든 features completed 후 최종 품질 게이트로만 실행. per-iteration 로직 불변.
**Consequences:**
- ✅ 기존 per-iter 수렴 로직 안전. 변경 폭 최소
- ⚠️ feature mode에서 loop-close checklist가 fail하면 이미 "완료"된 features를 되돌려야 할 수 있음 → ADR-009 escape hatch 필요
**Rejected alternatives:**
- per-iter마다 checklist — 매 iter grade_threshold가 intensity로 교체됨, 기존 harness.yaml 설정과 충돌
**Source:** Interview #3

### ADR-004: ExitCriterion(BaseModel) 타입 모델
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** exit_criteria_checklist의 각 항목이 cmd(실행 가능 명령어)와 label(LLM 판단 기준)을 구별해야 Gate 1(기계적)과 Gate 2(LLM)를 다르게 처리할 수 있음.
**Decision:** `ExitCriterion(BaseModel)` — `label: str`, `cmd: str = ""`, `required: bool = True`. `cmd == ""`이면 Gate 1 스킵, Gate 2만.
**Consequences:**
- ✅ mypy --strict 안전. Gate 1/2 분기 명확
- ✅ `required=False`로 ADR-009 escape hatch 자연스럽게 구현
- ⚠️ 코드 ~15행 추가
**Rejected alternatives:**
- `list[str]` — cmd와 label 구분 불가, Gate 1 실행 불가능
**Source:** Interview #4

### ADR-005: convergence_candidate_streak — 메모리만
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** Gate 4 (2연속 통과해야 수렴 선언)의 streak 카운터를 재시작 후에도 유지할지.
**Decision:** loop 실행 중 working memory에만 유지. 루프 재시작 시 streak = 0. 최대 2 iter 추가 발생 허용.
**Consequences:**
- ✅ ImprovementContext schema 변경 없음. 단순
- ⚠️ 재시작 시 streak 리셋 → 이미 2번 통과했어도 다시 2번 필요. 실제로는 루프가 수렴 직전이면 재시작 후 2 iter만 추가
**Rejected alternatives:**
- YAML 저장 — 스키마 필드 1개 추가, 루프 재시작 시 "가짜 수렴 연속" 문제 (crash 후 stale streak)
**Source:** Interview #5

### ADR-006: intensity는 per-iter grade_threshold를 override하지 않음
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** intensity가 per-iter review grade_threshold (harness.yaml에서 설정)도 제어해야 일관성이 있지만, harness.yaml 설정과 충돌 위험.
**Decision:** `loop_intensity`는 loop-close `exit_criteria_checklist`에만 영향. per-iter grade_threshold는 harness.yaml의 `review.grade_threshold` 그대로.
**Consequences:**
- ✅ harness.yaml과 충돌 없음. 기존 동작 보존
- ⚠️ intensity=thorough를 선택해도 per-iter review는 harness.yaml 기준 — 사용자가 harness.yaml을 별도 조정해야 완전한 "thorough"
**Rejected alternatives:**
- override — harness.yaml 설정과 충돌, 어느 값이 우선인지 혼란
**Source:** Interview #6

### ADR-007: `loop_intensity: Literal["quick","standard","thorough","maximum"] = "standard"`
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** 타입을 엄격히 잡아 잘못된 값 조기 발견 vs 커스텀 값 허용의 유연성.
**Decision:** `Literal["quick","standard","thorough","maximum"]`로 pydantic strict=True 검증. 기존 YAML에 필드 없으면 default "standard" 적용.
**Consequences:**
- ✅ 잘못된 값 YAML 파싱 단계에서 즉시 오류. mypy도 잡음
- ⚠️ 사용자 커스텀 강도 불가. 4개 외 값은 파싱 실패
**Rejected alternatives:**
- `str` — fallback 로직 필요, 테스트하기 어려움
**Source:** Interview #7

### ADR-008: stopping_criteria measurable item 추출 — 4-B 완료 후 재스캔
**Status:** Accepted (2026-05-10, validator C1 해결)
**Context:** 4-G가 4-B 전에 실행되므로, 4-B에서 새로 수집된 stopping_criteria의 measurable item이 exit_criteria_checklist에 누락될 수 있음.
**Decision:** 4-B 인터뷰 완료 후(stopping_criteria가 새로 수집되거나 업데이트된 경우), loop.md step 4-G의 "measurable item 추출" 로직을 한 번 더 실행해 exit_criteria_checklist에 append. 4-G AskUserQuestion은 재실행 안 함 — 추출만.
**Consequences:**
- ✅ 4-B에서 수집된 stopping_criteria의 specific measurable criteria가 checklist에 반영
- ✅ 추가 AskUserQuestion 없이 조용히 처리
- ⚠️ 4-G의 "추가할 기준?" 이후에 추출되므로 사용자가 4-G에서 이미 추가한 것과 중복될 수 있음 → LLM이 중복 제거
**Source:** Validator critique C1

### ADR-009: feature mode escape hatch — required=False + 3회 연속 실패 AskUserQuestion
**Status:** Accepted (2026-05-10, validator C2 해결)
**Context:** feature mode에서 loop-close checklist가 fail하면 루프가 forever stuck. `required=True` 항목 실패 시 출구가 없었음.
**Decision:** 두 계층의 escape hatch:
1. 4-G에서 default checklist 제시 시, non-critical 항목은 `required=False`로 제시하고 사용자가 toggle 가능 — `required=False` 항목 실패는 warning만, 수렴 차단 안 함.
2. `required=True` 항목이 3회 연속 loop-close 시도에서 fail → AskUserQuestion: "항목 X가 3회 연속 실패. (a) 수정 후 재시도 (b) 이 기준을 required=False로 downgrade (c) 루프 강제 종료"
**Consequences:**
- ✅ 루프 forever stuck 방지
- ✅ `required=False` 활용으로 기존 ExitCriterion 타입 추가 변경 없음
- ⚠️ override 옵션 (b)를 선택하면 initially-required 기준이 silently downgraded — loop.md에서 명시적 경고 메시지 필요
**Source:** Validator critique C2

---

## 🏗️ Technical Design

### Current State

| Component | Current | Gap |
|-----------|---------|-----|
| `ImprovementContext` | 5 fields: purpose, invariants, priority, test_reliability, stopping_criteria | loop_intensity, exit_criteria_checklist 없음 |
| `loop.md.j2` step 4 | 4-0 ~ 4-F (intensity 없음) | 4-G 없음 |
| `loop.md.j2` step 6 | improve: "evaluate stopping_criteria → converged" | single LLM judgment, streak 없음, regression check 없음 |
| `loop.md.j2` step 7 | feature: loop close → wrapup | exit_criteria_checklist 검증 없음 |
| `SKILL.md.j2` | safety rails 기술 | 새 gate 설명 없음 |

### Affected Components

```
src/harness_maker/
  autoloop_driver.py                        ← ExitCriterion NEW, LoopIntensity NEW,
                                              ImprovementContext 2 fields added

src/harness_maker/templates/
  commands/hm/loop.md.j2                    ← step 4-G NEW (after 4-A, before 4-B)
                                              step 4-B post-hook for checklist merge (ADR-008)
                                              step 4-F: context YAML schema updated
                                              step 6: 4-gate convergence (improve)
                                              step 7: loop-close checklist gate (feature)
  skills/autoloop-driver/SKILL.md.j2        ← convergence invariants section update

tests/unit/
  test_autoloop_driver.py                   ← ExitCriterion, LoopIntensity tests

tests/snapshot/ (update only)
```

### Architecture

```
User types /hm:loop <goal>
         │
         ▼
   step 4-A: read source material, extract 5 dimensions
         │
         ▼
   step 4-G (NEW):
     AskUserQuestion → intensity (quick|standard|thorough|maximum)
     Derive default exit_criteria_checklist from intensity
     Scan extracted stopping_criteria for measurable items → append
     "추가할 기준?" → user additions
     Persist loop_intensity + exit_criteria_checklist to loop-context YAML
         │
         ▼
   step 4-B: interview for missing dimensions
     (stopping_criteria collected here if not in 4-A)
         │
         ▼
   step 4-B post-hook (ADR-008):
     If stopping_criteria was newly collected/updated:
       Scan for measurable items → append to exit_criteria_checklist (dedup)
         │
         ▼
   ... 4-C, 4-D, 4-E, 4-F (unchanged) ...
         │
         ▼
   Loop runs (step 6):
     IMPROVE MODE — per-iter convergence check:
       Gate 1 [Mechanical]: run ExitCriterion.cmd items
       Gate 2 [LLM individual]: evaluate each ExitCriterion.label
         └─ same criterion ambiguous 3× → AskUserQuestion deadlock override
       Gate 3 [Regression]: compare to prev iter (skip on iter 1)
       Gate 4 [Streak]: gates 1+2+3 pass 2× consecutive → converged
         │
         ▼ (improve: converged)
         │
     FEATURE MODE — step 7 loop close:
       convergence predicate met (e.g., all-features-completed)
       → run Gate 1 + Gate 2 on exit_criteria_checklist
       → required=False items: warning only, do NOT block
       → required=True failures: AskUserQuestion if 3× consecutive
       → all required=True pass → converged
```

### New Python Types

```python
# src/harness_maker/autoloop_driver.py

from typing import Literal

LoopIntensity = Literal["quick", "standard", "thorough", "maximum"]

class ExitCriterion(BaseModel):
    """One item in the exit criteria checklist.

    cmd="" means LLM-only gate (Gate 2 only, Gate 1 skipped).
    required=False means failure is a warning, not a convergence blocker.
    """
    model_config = ConfigDict(strict=True, extra="forbid")

    label: str
    cmd: str = ""
    required: bool = True


class ImprovementContext(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    purpose: str
    invariants: list[str] = Field(default_factory=list)
    priority: str
    test_reliability: str
    stopping_criteria: str
    loop_intensity: LoopIntensity = "standard"
    exit_criteria_checklist: list[ExitCriterion] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

### Intensity → Default Checklist

| Intensity | Default ExitCriteria (rendered in 4-G prompt) |
|-----------|----------------------------------------------|
| `quick`   | `{test_cmd}` GREEN (`required=True`, `cmd="{test_cmd}"`); `ruff check` 0 errors (`required=True`, `cmd="ruff check"`) |
| `standard`| quick + `uv run mypy --strict src/` clean (`required=True`); review grade ≥ B (`required=False`, label-only) |
| `thorough`| standard + review grade = A (`required=True`, label-only); all ACs verified individually (`required=True`, label-only) |
| `maximum` | thorough + security scan PASS (`required=False`, label-only); no test regressions vs prior iter (`required=True`, label-only) |

`{test_cmd}`: detect from pyproject.toml → `uv run pytest --tb=short`; Makefile → `make test`; package.json → `npm test`; default → `pytest --tb=short`.

### Gate 2 Deadlock Detector

```
Per-criterion: maintain ambiguity_count[criterion_label] in working memory
When Gate 2 evaluates criterion.label:
  If verdict = ambiguous:
    ambiguity_count[label] += 1
    If ambiguity_count[label] >= 3:
      AskUserQuestion:
        "Exit criterion '{label}' has been judged ambiguous 3 times in a row.
         (a) Continue trying — loop will keep running
         (b) Accept as satisfied — treat this criterion as passed for this run
         (c) Remove this criterion from checklist"
      User choice recorded. streak NOT reset for this criterion from iter N+1.
  Else:
    ambiguity_count[label] = 0
```

---

## 📝 Implementation Plan

### Phase 1 — Python schema (`autoloop_driver.py`)

**Scope IN:**
- `src/harness_maker/autoloop_driver.py` — add `LoopIntensity` Literal type, `ExitCriterion` model, update `ImprovementContext` (2 new fields with defaults)
- `tests/unit/test_autoloop_driver.py` — add tests for ExitCriterion validation, LoopIntensity validation, ImprovementContext backward compat (old YAML without new fields still parses)

**Scope OUT:** All template files (.j2), any snapshot tests

**Exit criterion:**
```bash
uv run pytest tests/unit/test_autoloop_driver.py -v       # all pass
uv run mypy --strict src/harness_maker/autoloop_driver.py # clean
# Verify backward compat:
python -c "
from harness_maker.autoloop_driver import ImprovementContext
ctx = ImprovementContext(purpose='p', priority='q', test_reliability='r', stopping_criteria='s')
assert ctx.loop_intensity == 'standard'
assert ctx.exit_criteria_checklist == []
print('backward compat OK')
"
# Verify Literal rejection:
python -c "
from harness_maker.autoloop_driver import ImprovementContext
try:
    ImprovementContext(purpose='p', priority='q', test_reliability='r', stopping_criteria='s', loop_intensity='ultra')
    raise AssertionError('should have rejected')
except Exception as e:
    print(f'Literal rejects invalid: {e}')
"
```
Risk: **low** | Rollback: `git revert` Phase 1 commit (independent, no template deps)

---

### Phase 2 — `loop.md.j2` — step 4-G + 4-B post-hook

**Scope IN:**
- `src/harness_maker/templates/commands/hm/loop.md.j2`
  - NEW step `4-G` section (after 4-A, before 4-B): AskUserQuestion for intensity + default checklist table + "추가할 기준?" + persist
  - NEW step `4-B post-hook` paragraph: "If stopping_criteria was newly collected, scan for measurable items and append to exit_criteria_checklist (dedup)"
  - Update step `4-F` context YAML schema block to include `loop_intensity` and `exit_criteria_checklist` fields

**Scope OUT:** step 6 convergence, step 7 loop close, SKILL.md.j2

**Exit criterion:**
```bash
uv run pytest tests/snapshot/ -v -k loop   # snapshot updated: 4-G section present
grep -A 3 "4-G" .claude/commands/hm/loop.md  # "4-G" heading exists
grep "loop_intensity" .claude/commands/hm/loop.md  # field in 4-F schema block
grep "required=False" .claude/commands/hm/loop.md  # escape hatch phrasing present
```
Risk: **low** | Rollback: `git revert` Phase 2 + Phase 1 (2 commits)

---

### Phase 3 — `loop.md.j2` — step 6 convergence (improve) + step 7 close (feature)

**Scope IN:**
- `src/harness_maker/templates/commands/hm/loop.md.j2`
  - step 6: replace improve mode "evaluate stopping_criteria → converged" with 4-gate system + deadlock detector prose (ADR-009)
  - step 7: add feature mode loop-close checklist gate with required=False warning + 3-consecutive-failure AskUserQuestion escape (ADR-009)

**Scope OUT:** Phase 2 additions, SKILL.md.j2, Python schema

**Exit criterion:**
```bash
uv run pytest tests/snapshot/ -v -k loop   # snapshot updated
grep "Gate 1" .claude/commands/hm/loop.md
grep "Gate 2" .claude/commands/hm/loop.md
grep "Gate 3" .claude/commands/hm/loop.md
grep "Gate 4" .claude/commands/hm/loop.md
grep "required=False" .claude/commands/hm/loop.md  # escape hatch (ADR-009)
grep "3.*consecutive\|3회.*연속" .claude/commands/hm/loop.md  # deadlock trigger
# Manual verification (documented in Phase 5):
# - improve mode: Gate 1 runs cmd items; Gate 2 evaluates labels; Gate 3 skipped iter 1;
#   Gate 4 streak=2 required; deadlock override at 3× ambiguous
# - feature mode: checklist gate fires after convergence predicate; required=False = warning only
```
Risk: **low** | Rollback: `git revert` Phase 3 + Phase 2 + Phase 1 (cascade)

---

### Phase 4 — `autoloop-driver/SKILL.md.j2`

**Scope IN:**
- `src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2`
  - Update "Safety Rails" section: add description of 4 convergence gates + streak
  - Update "Coverage-Driven Adaptive Interview" section: add 6th dimension (loop_intensity) to the five dimensions table; add 4-G step

**Scope OUT:** loop.md.j2, Python schema

**Exit criterion:**
```bash
uv run pytest tests/snapshot/ -v -k autoloop-driver   # snapshot updated
grep "exit_criteria_checklist" .claude/skills/autoloop-driver/SKILL.md
grep "loop_intensity" .claude/skills/autoloop-driver/SKILL.md
```
Risk: **low** | Rollback: `git revert` Phase 4 (only SKILL.md changes, no runtime impact)

---

### Phase 5 — Full suite + snapshot regen + manual verification

**Scope IN:**
- Snapshot regeneration: `python tests/snapshot/regenerate.py` (from main repo root, not worktree)
- Full test suite + type + lint
- Manual verification checklist (scenarios that can't be covered by unit tests)

**Exit criterion:**
```bash
# From main repo root (not .worktrees/):
uv run pytest --tb=short                    # all pass
uv run mypy --strict src/                   # clean
uv run ruff check                           # 0 errors
# No literal "extra" fields snuck into test fixtures:
grep -rn "loop_intensity\|exit_criteria" tests/ --include="*.yaml" | wc -l  # ≥1 (schema tests)
```

**Manual verification checklist (gate logic correctness):**
```
[ ] improve mode, iter 1: Gate 3 (regression) is explicitly skipped
[ ] improve mode, streak=1 after first all-gate pass: loop continues
[ ] improve mode, streak=2 after second all-gate pass: converged
[ ] improve mode, Gate 1 cmd fails: streak resets to 0
[ ] improve mode, Gate 2 same criterion ambiguous 3×: deadlock AskUserQuestion fires
[ ] feature mode, all-features-completed: checklist runs
[ ] feature mode, required=False item fails: warning only, does NOT block convergence
[ ] feature mode, required=True item fails 3×: AskUserQuestion escape fires
[ ] backward compat: old loop-context YAML without loop_intensity/exit_criteria_checklist parses with defaults
```
Risk: **low** | Rollback: N/A (verification only)

---

## 🧪 Testing Strategy

### Unit tests — Phase 1

- `test_exit_criterion_defaults` — ExitCriterion() with only label; cmd="", required=True defaults
- `test_exit_criterion_required_false` — ExitCriterion(label="x", required=False) parses
- `test_loop_intensity_valid_values` — all 4 Literal values accepted
- `test_loop_intensity_invalid_rejects` — "ultra", "max", "THOROUGH" rejected at parse time
- `test_improvement_context_backward_compat` — old YAML without new fields parses with defaults
- `test_improvement_context_full_fields` — all fields round-trip YAML

### Snapshot tests — Phases 2, 3, 4

Generated loop.md and SKILL.md snapshots updated. Use `normalize_for_snapshot()` for `generated_at` masking.

### Manual — Phase 5

8 gate scenarios listed in Phase 5 exit criterion. No automated harness for prompt-driven gate logic — accepted per CLAUDE.md §테스트 정책 (integration boundary; manual check for prompt correctness).

---

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| `extra="forbid"` rejects old YAML with unrecognized fields | medium | new fields have defaults → old YAML without them parses fine. Risk is old YAML WITH extra fields (hand-written) → unit test `test_improvement_context_backward_compat` catches |
| 4-G checklist missing stopping_criteria items (ADR-008) | low | 4-B post-hook re-scans and appends; dedup via LLM judgment |
| Gate 2 deadlock on thorough/maximum intensity | medium | deadlock detector (3× ambiguous → AskUserQuestion override). Documented expected behavior per tier |
| Feature mode forever stuck on required=True failure | medium | 3-consecutive-failure AskUserQuestion escape (ADR-009) |
| Rollback cascade: phases not independently revertible | accepted | Phases 1→5 are dependency-ordered. Rollback = `git revert` this phase AND all later phases. Tag `pre-loop-intensity` before Phase 1 |
| Snapshot tests fail if regenerated from worktree (template path embedding) | known | Always run `tests/snapshot/regenerate.py` from main repo root. Documented in `[fail:test] snapshot-regen-inside-worktree` |
| autoloop-coder doesn't learn about exit_criteria_checklist | accepted | autoloop-coder is an implementation worker, not a convergence evaluator. Gate evaluation is the driver's responsibility (Claude-as-orchestrator reading loop.md). No contract change needed for coder. |

---

## ✅ Success Criteria

- [x] `ExitCriterion`, `LoopIntensity` in autoloop_driver.py with mypy --strict clean
- [x] Old loop-context YAML (without new fields) parses without error
- [x] loop.md contains step 4-G with intensity table + "추가할 기준?" + 4-B post-hook
- [x] loop.md step 6 contains Gate 1, Gate 2, Gate 3, Gate 4 with streak=2 requirement
- [x] loop.md Gate 2 deadlock detector (3× ambiguous → AskUserQuestion) present
- [x] loop.md step 7 feature-mode checklist gate with required=False warning + 3× escape
- [x] SKILL.md updated with new convergence invariants
- [x] `uv run pytest --tb=short` all pass
- [x] `uv run mypy --strict src/` clean
- [x] `uv run ruff check` 0 errors
- [x] Manual verification checklist (8 items in Phase 5) confirmed

---

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION → RESOLVED

| Critique | Severity | Resolution |
|----------|----------|------------|
| C1: 4-G before 4-B → stopping_criteria not yet available | warning | **Resolved** — 4-B post-hook re-scans newly-collected stopping_criteria and appends measurable items to checklist (ADR-008) |
| C2: feature mode forever stuck when checklist fails | critical | **Resolved** — `required=False` for non-blocking + 3-consecutive-failure AskUserQuestion override (ADR-009). Escape hatch in Phase 3 exit criterion (grep check) |
| C3: autoloop-coder contract gap | warning | **Resolved as accepted risk** — autoloop-coder is implementation worker, not convergence evaluator. Gates are evaluated by Claude-as-orchestrator reading loop.md. No contract change needed. Documented in Risks table |
| C4: phases not independently revertible | warning | **Resolved** — rollback restated as "this phase AND all later phases"; pre-loop-intensity tag created before Phase 1 |
| C5: Gate 2 deadlock on thorough/maximum | warning | **Resolved** — deadlock detector added: same criterion ambiguous 3× → AskUserQuestion override. Documented in Gate 2 design |
| C6: gate logic testing is shallow | warning | **Resolved** — 8-item manual verification checklist added to Phase 5 exit criterion. Prompt-driven gate logic cannot be unit-tested without mocking Claude itself |
