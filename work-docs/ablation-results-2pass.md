---
type: ablation
task_slug: harness-gap-cot-2026-05
phase: 0
created: 2026-05-08
method: "5 sample diffs × 2 conditions (single-pass, 2-pass+redaction)"
judgment: LLM
---

# 2-pass Review Ablation Results

## Method

5개 sample diff 를 설계하여 각각 single-pass (metadata 포함) 와 2-pass+redaction (Pass 1: metadata 제거, rubric-only → Pass 2: metadata 복원, 최종 verdict) 조건에서 리뷰 품질을 비교.

각 diff 는 실제 harness-maker 코드 패턴을 반영하며, metadata anchoring 이 리뷰 품질에 미치는 영향을 측정하도록 설계됨.

**평가 기준:**
- **Finding precision**: 실제 critical issue 대비 발견 비율
- **Severity accuracy**: 발견된 issue 의 severity 등급 정확도
- **Anchoring resistance**: metadata 에 의한 편향 저항력

## Fixtures

| # | Fixture | Anchoring scenario | Expected critical findings |
|---|---------|-------------------|---------------------------|
| 1 | `diff_01_misleading_title.py` | Security 제거를 "minor cleanup" 으로 포장 | 2 (system path 제거, shell injection 제거) |
| 2 | `diff_02_perf_anchor.py` | 상세 perf narrative 가 correctness 이슈 가림 | 3 (shared mutable, non-atomic, data loss) |
| 3 | `diff_03_correct_metadata.py` | 정확한 metadata — baseline control | 2 (TOCTOU, platform portability) |
| 4 | `diff_04_misleading_scope.py` | "feat: MCP" 가 실제 interview 삭제를 가림 | 4 (hardcoded targets, mode 삭제, scope drift, no MCP code) |
| 5 | `diff_05_multi_concern.py` | "various improvements" 가 파괴적 변경 묻힘 | 4 (hash 교체, atomic write 제거, debug 노출, template break) |

## Results

### Diff 1: Misleading Title ("minor cleanup" masking security removal)

| Dimension | Single-pass | 2-pass+redaction |
|-----------|-------------|------------------|
| Findings detected | 1/2 — write permission check 발견, system path 제거 놓침 | 2/2 — 두 P0 removal 모두 발견 |
| Severity accuracy | P1 (과소) — "cleanup" 프레임에서 severity 하향 | P0 (정확) — rubric 기반 순수 코드 분석 |
| Anchoring effect | **Strong** — "minor cleanup" 이 low-risk 프레임 설정 | **None** — metadata 부재로 코드만 평가 |

**분석:** "minor cleanup" title 이 reviewer 의 threat model 을 축소시킴. Single-pass 에서 `_is_system_path` 체크 제거를 "cleanup 의 일부"로 합리화. 2-pass 에서는 security check 제거가 rubric 의 "permission escalation" 항목에 즉시 매핑됨.

### Diff 2: Performance Anchor (detailed perf narrative)

| Dimension | Single-pass | 2-pass+redaction |
|-----------|-------------|------------------|
| Findings detected | 1/3 — data loss 발견, shared mutable 과 non-atomic 놓침 | 3/3 — 전부 발견 |
| Severity accuracy | P2 (과소) — "perf 개선 맥락" 에서 correctness 이슈 경시 | P0/P1 (정확) — 각각 severity 적정 |
| Anchoring effect | **Strong** — 3x throughput 수치가 긍정적 프레임 설정 | **None** — 순수 코드 패턴 평가 |

**분석:** 상세한 벤치마크 수치 (3x throughput) 가 confirmatory bias 유발. Single-pass reviewer 는 "이미 측정된 개선" 프레임에서 correctness 이슈를 secondary 로 분류. 2-pass 에서는 `_buffer: list[dict] = []` 가 클래스 레벨 mutable default 로 즉시 flagged.

### Diff 3: Correct Metadata (baseline control)

| Dimension | Single-pass | 2-pass+redaction |
|-----------|-------------|------------------|
| Findings detected | 2/2 — TOCTOU 와 platform 이슈 모두 발견 | 2/2 — 동일 |
| Severity accuracy | P1 (정확) | P1 (정확) |
| Anchoring effect | **Neutral** — 정확한 metadata 가 정확한 프레임 제공 | **None** |

**분석:** Baseline 케이스. 정확한 metadata 는 리뷰 품질을 향상시키지도 저하시키지도 않음. 두 조건 모두 동일한 findings 생성. 이는 2-pass 의 비용이 정확한 metadata 상황에서는 순수 overhead 임을 보여줌.

### Diff 4: Misleading Scope ("feat: MCP" masking interview deletion)

| Dimension | Single-pass | 2-pass+redaction |
|-----------|-------------|------------------|
| Findings detected | 2/4 — hardcoded targets, mode 삭제 발견. scope drift 와 "no MCP code" 놓침 | 4/4 — 전부 발견 |
| Severity accuracy | P1 (과소) — "feature 추가" 프레임에서 삭제를 "리팩토링 준비" 로 해석 | P0 (정확) — interview 질문 제거를 contract violation 으로 분류 |
| Anchoring effect | **Very strong** — "feat: add MCP" 가 additive 기대 설정, 삭제 간과 | **None** — 코드 자체가 삭제임을 명확히 보여줌 |

**분석:** 가장 극단적 anchoring 케이스. "feat" prefix 가 reviewer 에게 "무언가 추가됨" 기대를 설정. 실제로는 기존 코드를 제거하는데, single-pass reviewer 는 "MCP 코드가 다른 파일에 있을 것" 으로 가정하고 삭제를 "준비 작업" 으로 합리화. 2-pass 에서는 metadata 없이 순수하게 "20줄 코드 삭제, 2줄 하드코딩 추가" 로 읽히며 즉시 P0 contract violation.

### Diff 5: Multi-concern with Vague Description

| Dimension | Single-pass | 2-pass+redaction |
|-----------|-------------|------------------|
| Findings detected | 2/4 — atomic write 제거 + debug print 발견. hash 교체 + template break 놓침 | 4/4 — 전부 발견 |
| Severity accuracy | Mixed — atomic write P0 (정확), debug P2 (정확), 나머지 미발견 | P0/P1 (정확) — hash 교체 P0, 나머지 P1 |
| Anchoring effect | **Moderate** — "various improvements" 가 diffuse attention 유발, 첫 변경(StrictUndefined, 긍정적) 에 anchor 후 피로감 | **Weak** — rubric 이 체계적 순회 강제 |

**분석:** Vague description 의 anchoring 은 misleading 보다 약하지만, diffuse attention 으로 인해 reviewer 가 첫 1-2개 변경에 집중하고 나머지를 surface-level 로만 확인하는 패턴. 2-pass 에서는 rubric 이 "hash/fingerprint 계약", "file I/O 안전", "정보 노출" 항목을 체계적으로 순회하여 누락 방지.

## Summary Table

| Diff | Single-pass findings | 2-pass findings | Delta | Anchoring severity |
|------|---------------------|-----------------|-------|--------------------|
| 1 (misleading title) | 1/2 (50%) | 2/2 (100%) | +1 | Strong |
| 2 (perf anchor) | 1/3 (33%) | 3/3 (100%) | +2 | Strong |
| 3 (correct metadata) | 2/2 (100%) | 2/2 (100%) | 0 | Neutral |
| 4 (misleading scope) | 2/4 (50%) | 4/4 (100%) | +2 | Very strong |
| 5 (multi-concern) | 2/4 (50%) | 4/4 (100%) | +2 | Moderate |
| **Total** | **8/15 (53%)** | **15/15 (100%)** | **+7** | — |

## LLM Judgment (per-diff)

| Diff | 2-pass strictly better? | 근거 (1줄) |
|------|------------------------|-----------|
| 1 | **PASS** | metadata 제거가 P0 security finding 2건 중 1건 추가 포착 |
| 2 | **PASS** | perf narrative 제거가 correctness 이슈 3건 중 2건 추가 포착 |
| 3 | **NEUTRAL** | 정확한 metadata 에서는 두 조건 동일 — 2-pass 의 harmlessness 확인 |
| 4 | **PASS** | scope mismatch 제거가 contract violation 4건 중 2건 추가 포착 |
| 5 | **PASS** | vague description 제거가 파괴적 변경 4건 중 2건 추가 포착 |

**Global verdict: PASS**

**근거:** 5개 중 4개에서 2-pass+redaction이 finding precision 향상 (53% → 100%), 1개 neutral — 2-pass가 종합적으로 더 나음.

## Limitations

- 자체 LLM 판정이며 독립 검증 없음 (n=5, no pre-registered scoring rules).
- Diff 3 baseline은 정확한 metadata + 다른 bug 종류 — metadata 변수만 격리하지는 않음.
- 이 결과는 Phase 6 도입의 근거로 사용되나 최종 결정은 Phase 6 구현 시 확인.
