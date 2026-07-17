---
type: research
task_slug: deep-interview-question-criteria
status: complete
created: 2026-05-18
tags: [harness-maker, research, deep-interview, preference-elicitation, value-of-information]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://arxiv.org/abs/2310.11589
  - https://arxiv.org/abs/2403.19154
  - https://arxiv.org/abs/2506.02827
  - https://arxiv.org/pdf/2502.04485
  - https://aclanthology.org/2025.trustnlp-main.4/
  - https://arxiv.org/html/2602.16699v1
  - https://docs.pyro.ai/en/stable/contrib.oed.html
  - https://proceedings.mlr.press/v206/bickfordsmith23a/bickfordsmith23a.pdf
  - https://plato.stanford.edu/entries/common-ground-pragmatics/
  - https://semantics.uchicago.edu/kennedy/classes/f07/pragmatics/stalnaker02.pdf
  - https://lawsofux.com/hicks-law/
  - https://lensym.com/blog/survey-fatigue-causes-prevention
  - https://dl.acm.org/doi/10.1145/3582272
related_docs:
  - "[[PLAN-deep-interview-llm-delegation]]"
  - "[[RESEARCH-deep-interview-llm-delegation]]"
  - "[[PLAN-loop-interview-intensity]]"
  - "[[PLAN-antisycophancy-2026-05]]"
summary: "Replace 3-layer ad-hoc gate with single inequality: EIG≥ε ∧ CLARITI≥0.7 ∧ ¬common-ground ∧ confidence<τ ∧ open-ended<2"
---

# RESEARCH — Deep-Interview Question Selection Criteria

> 질문: "LLM 과 사람의 intent 를 최대로 맞추되, 당연한 선택은 묻지 않는다" 의 **명확한 기준**을 세울 수 있는가?

## 🎯 Recommended Direction

**현재의 3-layer ad-hoc gate (5-rubric + GCIC + CLARITI + 5 implicit probes + 가중 ambiguity score + 2-streak)** 를 **단일 부등식**으로 통합한다:

> **Ask(Q) iff** `EIG(Q) ≥ ε_bits  ∧  TaskRelevance × UserAnswerability ≥ 0.7  ∧  slot ∉ common_ground  ∧  calibrated_confidence(slot) < τ  ∧  open_ended_count_turn < 2`

5개 항이 각각 학술 근거를 가진다 (EIG ← Bayesian Experimental Design / BED-LLM, CLARITI ← GATE/STaR-GATE, common-ground ← Clark/Grice 화용론, confidence calibration ← Calibrate-Then-Act, open-ended cap ← survey fatigue 연구). 현재 시스템의 "왜 score 가 Goal×0.4+Constraint×0.3+SC×0.3 인가?", "왜 streak 2 인가?" 같은 magic-number 의 근거 부재 문제를 해결하면서 동시에 **"당연한 것 묻지 않기"** 를 common-ground 항으로 명시 형식화한다.

이는 *informational* 권고 — 실제 채택 여부와 ε/τ 캘리브레이션은 `/hm:plan` 에서 결정.

## 🔍 Refinement Decisions

- `--deep` 미사용 (토픽이 충분히 구체적).
- Discovery lens: **Research/academic** (preference elicitation 이론) + **Technical architecture** (현재 구현 분석) + **User-workflow** (현재 5-question rubric 의 실제 friction 표면화).

## 🛠️ Approaches Found

### Approach 1 — Status quo + threshold tuning (최소 변경)

| Field | Content |
|-------|---------|
| Approach | 3-layer gate 유지, ε/τ 만 preset 별 재캘리브레이션 |
| Assumption | 현재 구조는 옳고, magic number 만 잘못 |
| Evidence | `interview.py:1002-1050` preset 별 max_rounds/streak_target 이미 분기. ADR-003 monotonicity rule 이 안전망 역할 |
| Trade-off | 학습 곡선 zero, but "왜 그 임계값?" 근거 부재 — Side preset 의 streak=1 / max_rounds=1 도 ad-hoc |
| Compatibility | 100% — 코드 변경 거의 없음 |
| Risk | low (구현) / medium (silent intent-miss 잔존) |

### Approach 2 — Single inequality rule (recommended)

| Field | Content |
|-------|---------|
| Approach | 위 5-term 부등식. 각 term 별 학술 근거 + citable provenance |
| Assumption | EIG 추정 LLM 호출 비용 < 사용자가 무의미 질문에 답하는 비용 |
| Evidence | BED-LLM 이 entropy baseline 대비 10-20% gain ([emergentmind](https://www.emergentmind.com/topics/expected-information-gain-eig)). Calibrate-Then-Act 가 두 단계 분리 (calibration ↔ action) 의 robustness 입증 ([arXiv 2602.16699](https://arxiv.org/html/2602.16699v1)). Common-ground 위반 = Grice Quantity maxim 위반 ([SEP](https://plato.stanford.edu/entries/common-ground-pragmatics/)) |
| Trade-off | 후보 질문당 1 추가 LLM call (EIG sampling 또는 self-report) → 인터뷰 latency ↑ ~30%. 단, 질문 자체 수는 줄어듦 (common-ground 컷) |
| Compatibility | Layer 1 (GCIC) 의 axis 4-dim 은 그대로 EIG 의 "posterior over slots" 로 매핑 가능. Layer 2 의 5-type 후보는 EIG ranking 의 입력 풀로 재사용. Layer 3 score 만 폐기 |
| Risk | medium — EIG 추정 정확도가 비싼 prompt 디자인에 민감. preset 별 cost-budget 가드 필수 |

### Approach 3 — STaR-GATE style learned Questioner (heavyweight)

| Field | Content |
|-------|---------|
| Approach | Questioner LLM 을 offline 으로 self-improvement (STaR-GATE) 로 fine-tune, runtime 은 단순 추론 |
| Assumption | 도메인별 Roleplayer + Oracle pair 를 만들 수 있다 (synthetic interview corpus) |
| Evidence | STaR-GATE: 2 iter 후 preference win rate +72% ([arXiv 2403.19154](https://arxiv.org/abs/2403.19154)). TO-GATE 가 "irrelevant question" failure mode 까지 해결 ([arXiv 2506.02827](https://arxiv.org/abs/2506.02827)) |
| Trade-off | offline training pipeline 필요 (Claude subscription 으로 가능하나 Roleplayer 정의가 어려움). harness-maker 의 stateless plugin 정체성과 충돌 |
| Compatibility | low — fine-tune 된 모델 배포 / 버전 추적 / 캐시 무효화 비용 큼 |
| Risk | high — over-engineering. 0.x 단계에 부적합 |

## ⚠️ Pitfalls

1. **EIG 추정 비용 > 절감 비용 ("cure worse than disease")** — 후보 질문 N 개 각각에 sampling 호출하면 인터뷰 자체보다 비싸진다. **완화**: full Monte Carlo 대신 LLM self-report proxy ("if you knew the answer to Q, would your downstream plan change? rate 0-1") 로 시작. ([BED-LLM 분석](https://www.emergentmind.com/topics/expected-information-gain-eig))

2. **Common-ground 오추론 → silent intent mismatch** — LLM 이 "이건 당연하다" 가정하고 묻지 않은 슬롯이 실제로는 사용자 의도와 다른 경우. 우리 시스템의 가장 큰 risk. **완화**: common-ground source 는 *명시 evidence* 만 (CLAUDE.md, harness.yaml, 이전 답변) — LLM 의 "보통 그렇잖아요" 추론은 common-ground 에 포함 금지. 추론은 항상 "LLM-inferred" 로깅. (현재 CLARITI 의 동일 패턴 유지)

3. **Calibration drift** — Opus 4.6 → 4.7 같은 모델 변경 시 `confidence < τ` threshold 의 의미가 바뀐다. **완화**: τ 는 모델 버전 + preset 의 함수 (`harness.yaml.interview.deep_gate.confidence_tau`), `/hm:health` Layer 1 sub-check 로 drift 감시.

4. **Locale-aware "당연한 것" 기대치 차이** — 한국어 사용자는 직접적 짧은 인터뷰를 선호 (memory feedback "직접적, no preamble"), 영어권은 explicit confirmation 을 선호. 동일한 EIG 임계값이 두 locale 에서 동일하게 작동하지 않을 수 있음. **완화**: ε 도 locale 함수, 또는 open-ended cap 만 locale-aware (en=2, ko=1).

5. **Question-fatigue 누적 — count 가 아닌 effort** — open-ended 3개 > rating-scale 15개 ([Lensym 연구](https://lensym.com/blog/survey-fatigue-causes-prevention)). 현재 시스템은 round 수만 cap, effort 안 잼. **완화**: 후보 질문에 cost-weight (open-ended=2, multi-choice=1, yes/no=0.5) 적용.

6. **Pre-seed bias (STaR-GATE TO-GATE motivation)** — 사용자가 "Y option 으로 가고 싶다" 라고 1번 답하면 이후 질문이 Y 를 검증하는 쪽으로 편향. **완화**: TO-GATE 의 trajectory diversity reward 와 동일 정신 — round 별 EIG ranking 에 "다른 분기 탐색" bonus 추가. ([arXiv 2506.02827](https://arxiv.org/abs/2506.02827))

## ❓ Open Questions

`/hm:plan` 단계에서 lock-in 필요:

1. **EIG 추정 메커니즘**: full MC sampling (BED-LLM) vs. LLM self-report proxy ("would knowing Q change the plan? 0-1") vs. answer-disagreement sampling (TrustNLP 2025). cost ↔ accuracy trade-off.
2. **Common-ground source 범위**: CLAUDE.md + harness.yaml 만? 같은 task slug 의 이전 RESEARCH/PLAN 도? cross-stage answer reuse 정책 (현재 plan 의 `answers_from_harness_yaml` 와 합치는지)?
3. **ε bit / τ confidence threshold 의 preset 별 캘리브레이션**: Side (max_rounds=1) vs Production (max_rounds=3) 각각 어떤 값? locale 별 분기 여부.
4. **현재 5 implicit probe type (WRONG/METHOD/STAKEHOLDER/STYLE/PERF / NOT-USEFUL/AVOID/DEPTH/AUDIENCE/TIME-SCOPE) 의 운명**: 폐기? "EIG ranking 의 후보 풀" 로 retain? type-label tracking 의 중복 회피 기능을 EIG 가 자동 흡수?
5. **Stage 별 migration 순서**: ADR-004 의 "4-stage 동시" 정신 유지 vs. research 만 먼저 → telemetry 수집 → spec/plan/loop 확산.
6. **Score 표시 정책**: 현재 Layer 3 의 visual `{score}/1.0 ✅⚠️` 가 사용자에게 progress 감각을 줌. 부등식 기반으로 바뀌면 표시 방식 — "5/5 conditions met" 같은 checklist 로 대체?
7. **Backward compat**: 기존 work-docs/loop-context/*.yaml 의 ambiguity score 필드 — deprecate / migrate / dual-write?

## 📚 Sources

**Value of Information / EIG**:
- [Pyro Optimal Experiment Design docs](https://docs.pyro.ai/en/stable/contrib.oed.html) — EIG 표준 정의
- [Bickford Smith et al. 2023 — Prediction-Oriented Bayesian Active Learning (PMLR)](https://proceedings.mlr.press/v206/bickfordsmith23a/bickfordsmith23a.pdf)
- BED-LLM (Bayesian Experimental Design for LLM info-gathering) — Rao-Blackwellized MC EIG, +10-20% over entropy baselines

**LLM preference elicitation**:
- [GATE — Eliciting Human Preferences with Language Models (ICLR 2025, arXiv 2310.11589)](https://arxiv.org/abs/2310.11589) — Li, Tamkin, Andreas, Goodman
- [STaR-GATE — Andukuri et al. 2024 (arXiv 2403.19154)](https://arxiv.org/abs/2403.19154) — self-improving Questioner, +72% pref win rate
- [TO-GATE 2025 (arXiv 2506.02827)](https://arxiv.org/abs/2506.02827) — trajectory optimization fix for irrelevant-question mode
- [Active Task Disambiguation with LLMs (arXiv 2502.04485)](https://arxiv.org/pdf/2502.04485) — explicit Bayesian framing

**Cognitive load / fatigue / pragmatics**:
- [Laws of UX — Hick's Law](https://lawsofux.com/hicks-law/)
- [Survey Fatigue — Lensym](https://lensym.com/blog/survey-fatigue-causes-prevention) — open-ended cost vs rating-scale
- [Stanford Encyclopedia of Philosophy — Common Ground in Pragmatics](https://plato.stanford.edu/entries/common-ground-pragmatics/)
- [Stalnaker 2002 — Common Ground](https://semantics.uchicago.edu/kennedy/classes/f07/pragmatics/stalnaker02.pdf)
- [ACM Cognitive Workload Survey (CSUR 2023)](https://dl.acm.org/doi/10.1145/3582272)

**Production / ambiguity detection**:
- [Ambiguity Detection via Answer Disagreement (TrustNLP 2025)](https://aclanthology.org/2025.trustnlp-main.4/) — 70.8% acc on ASQA/PACIFIC/ABG-COQA
- [Calibrate-Then-Act (arXiv 2602.16699)](https://arxiv.org/html/2602.16699v1) — decoupled calibration ↔ action gate

## 🔗 Related Internal Docs

- [[PLAN-deep-interview-llm-delegation]] — 현재 3-layer gate 의 origin plan (ADR-001~004)
- [[RESEARCH-deep-interview-llm-delegation]] — ReqElicitGym / LHAW / Ouroboros 의 empirical basis
- [[PLAN-loop-interview-intensity]] — autoloop interview 적응성 정책
- [[PLAN-antisycophancy-2026-05]] — communication-variant 와 인터뷰 톤의 직교성
- `templates/commands/hm/research.md.j2:90-162` — Phase 0 + 0.5 현재 source
- `templates/commands/hm/spec.md.j2:94-158` — spec stage gate
- `templates/commands/hm/plan.md.j2:226-282` — plan Step E exit check
- `templates/commands/hm/loop.md.j2:292-350` — loop Phase 4-H gate
- `src/harness_maker/interview.py:994-1050` — preset 별 deep_gate 임계값
