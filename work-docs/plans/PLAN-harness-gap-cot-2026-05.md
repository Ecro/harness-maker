---
type: plan
task_slug: harness-gap-cot-2026-05
status: planning
created: 2026-05-08
tags: [harness-maker, plan, python, jinja2, reliability, observability, memory, security, drift, hallucination]
research_doc: "[[RESEARCH-harness-gap-cot-2026-05]]"
interview_rounds: 6
adrs: 10
validator_outcome: APPROVED
summary: "Reliability Stack 7대 + spec rubric — drift·hallucination·memory·review·cascade·cost·guard"
---

# PLAN: harness-gap-cot-2026-05

## 🎯 Executive Summary

**TL;DR:** harness-maker 0.7.0 에 Reliability Stack 7대 기능 + spec strength rubric + TDAD 를 단일 릴리스로 추가. 총 12 phase (Phase 0 ablation 포함).

**What:** 2026-05 갭 분석(RESEARCH-harness-gap-cot-2026-05)에서 식별된 community pain point(quota bleed, 42% hallucination, prod DB 삭제)와 학술 연구(SWE-PRM, MemMachine, AgentProp-Bench)에서 도출된 reliability 인프라 기능 7개 + spec 품질 게이트 1개 + 코드↔테스트 의존성 힌트(TDAD)를 harness-maker 0.7.0 에 구현.

**Why:** arxiv 2604.25850 ablation 이 보여주듯, 에이전트 하네스의 품질 개선은 system-prompt 가 아닌 tool/middleware/memory 레이어 투자에서 나옴. 현재 harness-maker 는 prompt 계층(reviewer agents, slash commands)은 성숙하나, drift detection/hallucination prevention/cost observability 등의 인프라가 부재.

**Key Decisions (ADR-001 ~ ADR-010):**
- ADR-001: 7개 Primary + spec rubric + TDAD 전부 단일 릴리스
- ADR-002: 에피소딕 메모리 3층 구조 (episodic + semantic + profile)
- ADR-003: 드리프트 baseline 다층 fallback (SPEC → PLAN → prompt)
- ADR-004: OTel 거부, 자체 JSONL + OTel-호환 export
- ADR-005: Consensus scope-aware 재설계
- ADR-006: Spec strength rubric — spec-driven 에서만 강제
- ADR-007: Multi-provider routing 명시 거부 (Anthropic-only)
- ADR-008: Production-name guard — deny + 시퀀스 패턴 감지
- ADR-009: 에러 클래스 분류를 LLM 판단에 위임
- ADR-010: 드리프트 점수 하이브리드 산출 (cosine pre-filter → LLM)

**Estimated impact:** reliability 게이트 5종 추가(hallucination, drift, cascade, prod-name, spec-quality), observability JSONL 도입, 장기 메모리 3층 구조 확립, TDAD 기반 회귀 방지.

## 📚 Prior Work

- **RESEARCH-harness-gap-cot-2026-05**: 본 PLAN 의 직접 입력. 9개 하네스 벤치마크 + 16편 arxiv + community pain 분석.
- **PLAN-cursor-compat-uplift / PLAN-agents-skills-hooks-uplift**: 0.6.2 에서 cursor target + dual-render 완료. 이번 PLAN 은 기능적 확장, 구조적 변경은 최소.
- **REVIEW-agents-skills-hooks-uplift-2026-05-08**: M1-M9 수동 fix 에서 발견된 consensus cross-check 함정(Pitfall #7)이 본 PLAN Phase 5 의 직접 동기.
- **memory [[feedback_domain_content_ownership]]**: 도메인 콘텐츠는 user author — persona library 확장 거부의 근거.
- **memory [[project_targets_axis]]**: claude-code + cursor only — multi-CLI fan-out defer 근거.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|-------|-------|----------|-------------------|---------|--------|------|-------|
| 1 | R1 | 0.7.0 scope | Scope boundaries | 7개 Primary 중 몇 개? | all/top3/incremental/top3+secondary/other | A — 전부 단일 릴리스 | 12 phase 수용 | ADR-001 |
| 2 | R1 | 2-pass ablation | Risk tolerance | ablation 선행 여부 | yes/no/defer/other | A — Phase 0 ablation | counter-intuitive claim 검증 | — |
| 3 | R2 | Episodic memory schema | Contract | 메모리 구조? | new_dir/extend_session/3layer/other | C — 3층 구조 | MemMachine 전체 도입 | ADR-002 |
| 4 | R2 | Drift baseline | Contract | drift 진실 소스? | spec/summary/prompt/multilayer/other | D — 다층 fallback | SPEC→PLAN→prompt 순위 | ADR-003 |
| 5 | R2 | OTel dependency | Dependencies | OTel 도입? | full/self_jsonl/phased/other | B — 자체 JSONL | "100% 로컬" 원칙 부합 | ADR-004 |
| 6 | R2 | Consensus fix | Architecture | 비-overlap 문제? | scope_aware/min_threshold/domain_weight/other | A — scope-aware | Pitfall #7 직접 해결 | ADR-005 |
| 7 | R3 | Spec strength | Scope boundaries | 강제력? | specdriven_only/all_enforce/defer/other | A — spec-driven만 강제 | task-driven 은 권고만 | ADR-006 |
| 8 | R3 | Multi-provider | Scope boundaries | routing 도입? | reject/prm_only/defer/other | A — 명시 거부 | Anthropic-only by design | ADR-007 |
| 9 | R3 | Bench harness | Scope boundaries | 0.7.0 포함? | in/defer/internal/other/done | B — defer | cost-heavy | — |
| 10 | R3 | Persona library | Scope boundaries | starter set? | user_only/starter/template/other | A — user-author 유지 | 코어 9개 유지, bloat 방지 | — |
| 11 | R4 | Tool cascade | Architecture | chaos test 범위? | recovery_only/basic_chaos/full_bench/other | A — recovery only | chaos test 0.8.0 defer | — |
| 12 | R4 | Prod-name guard | Architecture | 보호 범위? | pattern_match/workflow_graph/deny_regex/other | A — deny + 시퀀스 패턴 | secscan 확장 | ADR-008 |
| 13 | R4 | Error class cap | Architecture | 분류 기준? | 3bucket/2bucket/llm_judge/other | C — LLM 판단 | LLM-first 원칙 부합 | ADR-009 |
| 14 | R4 | Context guard | Implementation | 강제 위치? | lint_extend/hook/both/done | A — lint 확장 | 정적 검사만 | — |
| 15 | R5 | Phase order | Phasing | 순서 승인 | ok/adjust/done | A — 승인 | — | — |
| 16 | R5 | Additional | — | 추가 사항? | no/yes | A — 없음 | — | — |
| 17 | R6 | Drift method | Architecture | 산출 방식? | llm/embedding/hybrid/other | C — 하이브리드 | cosine pre-filter → LLM | ADR-010 |
| 18 | R6 | TDAD (Pitfall #3) | Implementation | 대응? | nongoal/phase10/phase11/other | C — Phase 11 신규 | execute template 수정 | — |
| 19 | R6 | Pitfalls #8/#9/#11 | Scope boundaries | 추적? | all_nongoal/8_only/other | A — 모두 Non-Goal | 문서화만 | — |
| 20 | R6 | Ablation criteria | Risk tolerance | 판정 기준? | fp/grade/llm/other | C — LLM 판정 | 5개 결과 종합 | — |

## 📐 Architecture Decision Records

### ADR-001: 0.7.0 에 7개 Primary + Spec Strength + TDAD 전부 포함
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** RESEARCH 가 식별한 7대 Reliability Stack 기능이 모두 독립적이나, 릴리스 범위를 어디까지 잡을지 결정 필요.
**Decision:** 7개 Primary + 1 Secondary(spec strength rubric) + TDAD 전부 0.7.0 단일 릴리스. 12 phase 분할로 관리.
**Consequences:**
- ✅ 릴리스 후 즉시 전체 reliability stack 활성화
- ⚠️ 구현 부피 큼 (12 phase). 단, 각 feature 독립적이라 phase 간 rollback 용이
**Rejected alternatives:**
- Top-3만 (drift + hallucination + memory) — 나머지 4개의 ROI 도 즉시 필요
- 점진 배포 (0.7.0 = 1-2개씩) — 릴리스 빈도 증가 관리 부담
**Source:** Interview #1

### ADR-002: 에피소딕 메모리 3층 구조 (episodic + semantic + profile)
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** 기존 `.claude/memory/` 는 `wiki.md` + `failures.md` + `session/` 의 flat 구조. 장기 에피소딕 메모리 추가 시 구조 결정 필요.
**Decision:** MemMachine(2604.04853) 전체 패턴 도입 — `.claude/memory/episodic/`, `.claude/memory/semantic/`, `.claude/memory/profile/` 3층. 기존 wiki/failures 는 semantic layer 로 자연 매핑, session/ 은 episodic 의 raw source.
**Consequences:**
- ✅ 이웃 확장 retrieval, cross-session 학습, 사용자 프로필 개인화 가능
- ⚠️ 디렉토리 구조 변경 — 기존 memory 사용자 데이터 마이그레이션 필요 (backward compat)
**Rejected alternatives:**
- 신규 episodic/ 만 추가 (session/ 과 분리) — semantic/profile 없으면 retrieval 품질 제한
- session/ 확장 (포맷 개선만) — 3층 대비 기능 제한
**Source:** Interview #3

### ADR-003: 드리프트 baseline 다층 fallback (SPEC → PLAN → prompt)
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** trajectory drift monitor 가 "원래 의도"와 현재 실행 경로를 비교하려면 truth source 필요.
**Decision:** 다층 fallback — SPEC 있으면 SPEC acceptance criteria, 없으면 PLAN summary, 둘 다 없으면 원래 사용자 prompt.
**Consequences:**
- ✅ dev_mode 무관하게 항상 작동 (SPEC 없는 task-driven 에서도 prompt fallback)
- ⚠️ 구현 복잡도 증가 (3단계 resolution 로직)
**Rejected alternatives:**
- SPEC only — SPEC 없는 task-driven 에서 작동 불가
- harness.yaml summary only — 추상도 너무 높아 drift 감도 부족
- 원래 prompt only — 짧아서 정밀도 낮음
**Source:** Interview #4

### ADR-004: OTel 거부, 자체 JSONL + OTel-호환 export
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** AgentTrace(2602.10133)의 3-surface OTel schema 도입 여부.
**Decision:** otelpy 의존 거부. 자체 JSONL 포맷으로 cost/cache/latency 기록, OTel-compatible export 함수만 제공.
**Consequences:**
- ✅ CLAUDE.md "100% 로컬" 원칙 유지, 의존성 최소
- ⚠️ OTel ecosystem 도구(Jaeger, Grafana)와 직접 연동 불가 — export 변환 필요
**Rejected alternatives:**
- otelpy 전체 도입 — 의존성 + 사이즈 증가, 로컬 원칙 위반
- Phase 1 JSONL → 추후 OTel opt-in — 2단계 구현 부담
**Source:** Interview #5

### ADR-005: Consensus scope-aware 재설계
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** Pitfall #7 — 비-overlap 전문 reviewer 간 cross-check 시, scope 밖 finding 에 대해 상대방이 검증 불가 → 모든 finding 이 single-source → grade 자동 A.
**Decision:** reviewer-scope-aware consensus — 각 reviewer 의 전문 scope 를 메타데이터로 선언. scope 밖 finding 은 cross-check 면제, 해당 scope 전문 reviewer 의 단독 verdict 를 valid 로 인정.
**Consequences:**
- ✅ 전문 영역 finding 이 cross-check 규칙에 의해 묵살되지 않음
- ⚠️ scope 선언 정확도가 grade 품질 결정 — scope overlap 정의 필요
**Rejected alternatives:**
- minimum 2-reviewer threshold — scope 무관 강제 시 전문성 없는 reviewer 의 noise 증가
- domain-expert 가중치 — 복잡, scope-aware 가 더 명확
**Source:** Interview #6

### ADR-006: Spec Strength Rubric — spec-driven 에서만 강제
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** SpecSyn(2604.21570) 기반 spec 품질 평가 도입 시, 약한 스펙을 어떤 dev_mode 에서 차단할지.
**Decision:** dev_mode=spec-driven 에서만 약한 스펙 차단 (block). task-driven 에서는 점수 표시 + 권고만 (warn).
**Consequences:**
- ✅ task-driven 사용자에게 불필요한 friction 없음
- ⚠️ task-driven 에서 약한 스펙으로 진행 가능 — 자발적 개선만 의존
**Rejected alternatives:**
- 모든 dev_mode 에서 강제 — user friction 과도
- 0.8.0 defer — 7개 Primary 와 함께 ship 가능한 수준
**Source:** Interview #7

### ADR-007: Multi-provider Routing 명시 거부
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** claude-flow/task-master 가 multi-provider routing 제공. PRM-monitor 에 open-weight 모델 사용 use-case 부상.
**Decision:** 명시 거부. harness-maker 는 Anthropic-only by design. multi-provider routing layer 도입하지 않음.
**Consequences:**
- ✅ 단순성 유지, Claude-specific prompt 패턴 최적화 가능
- ⚠️ open-weight PRM 활용 불가
**Rejected alternatives:**
- PRM-monitor 에만 open-weight 허용 — scope creep 위험
- future phase defer — 불필요 (원칙적 거부)
**Source:** Interview #8

### ADR-008: Production-Name Guard — deny + 시퀀스 패턴 감지
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** 현재 security_scanner 는 개별 파일 경로/환경변수 deny 리스트. PocketOS prod DB 삭제 사례.
**Decision:** 기존 deny 리스트 + 시퀀스 패턴 감지 (예: Read(prod.db) → Write(prod.db) 연속 호출 탐지). 워크플로우 그래프 전체 분석은 하지 않음.
**Consequences:**
- ✅ 기존 secscan 확장으로 구현 가능, Read→Write 시퀀스 같은 위험 패턴 포착
- ⚠️ 전체 워크플로우 그래프 분석보다 커버리지 낮음
**Rejected alternatives:**
- 워크플로우 그래프 분석 — 구현 복잡도 과도
- deny 리스트 + 환경별 regex 만 — 시퀀스 패턴 미포착
**Source:** Interview #12

### ADR-009: 에러 클래스 분류를 LLM 판단에 위임
**Status:** Accepted (2026-05-08, via /hm:plan interview)
**Context:** Pitfall #6 — 자기-수정 루프가 logical 에러는 못 고침 (syntax 80%+ vs logical ~45%). 에러 클래스별 autoloop 반복 cap 필요.
**Decision:** LLM 이 에러 메시지를 읽고 분류 (syntax/import, type/runtime, logical/assertion, unknown). 분류별 max_iter 차등 적용.
**Consequences:**
- ✅ 정적 regex 보다 정확한 분류, 새 에러 패턴에 자동 적응
- ⚠️ LLM 호출 추가 비용 (에러 발생 시에만, 빈도 낮음)
**Rejected alternatives:**
- 3-bucket 정적 분류 — 경계 케이스에서 오분류
- 2-bucket (recoverable/non-recoverable) — 너무 단순
**Source:** Interview #13

### ADR-010: 드리프트 점수 하이브리드 산출 (cosine pre-filter → LLM)
**Status:** Accepted (2026-05-08, via /hm:plan validator follow-up)
**Context:** LLM-first 원칙 vs 비용. 매 stage 마다 LLM 호출은 과도, 순수 embedding 은 정밀도 부족.
**Decision:** 하이브리드 — 1차 cosine similarity 계산, `cos_sim < 0.7` 일 때만 LLM 정밀 판정 (drift score 0-1 반환). LLM-first 원칙 유지하면서 비용 절감.
**Consequences:**
- ✅ 대부분 case 에서 LLM 불호출 (비용 절감), 의심 case 에서만 정밀 판정
- ⚠️ embedding 모델 선택 필요 (Anthropic embedding API 또는 경량 local model)
**Rejected alternatives:**
- 순수 LLM 전용 — 비용 과도 (매 stage 호출)
- 순수 embedding + cosine — 정밀도 부족, LLM-first 원칙 위반
**Source:** Interview #17 (validator follow-up)

## 🏗️ Technical Design

### Current State

harness-maker 0.6.2 는 다음을 갖춤:
- 7 atomic stages (research/spec/plan/execute/review/wrapup/verify)
- 5 reviewer agents + 4 worker agents (9 total)
- 5-gate security scanner (secrets/permissions/hook-injection/CVE/prompt-injection)
- telemetry (post-tool-use hook, basic cost tracking)
- context_lint (line count lint)
- cache_diagnostics (basic cache analysis)
- Flat memory: wiki.md + failures.md + session/

### Affected Components

| Component | Change | Phase |
|-----------|--------|-------|
| `src/harness_maker/memory/` | 신규 패키지 — 3-layer memory (episodic/semantic/profile) | 3 |
| `src/harness_maker/drift_monitor.py` | 신규 — hybrid drift score + multi-layer baseline | 4 |
| `src/harness_maker/secscan/hallucination.py` | 신규 — AST + package introspection gate | 2 |
| `src/harness_maker/secscan/prod_name_guard.py` | 신규 — environment regex + sequence pattern | 8 |
| `src/harness_maker/tool_cascade.py` | 신규 — recovery taxonomy (retry/switch/abort) | 7 |
| `src/harness_maker/spec_quality.py` | 신규 — LLM-based spec strength rubric | 9 |
| `src/harness_maker/test_dep_map.py` | 신규 — 코드↔테스트 의존성 힌트 | 11 |
| `src/harness_maker/telemetry.py` | 확장 — JSONL cost/cache/latency 기록 | 1 |
| `src/harness_maker/cache_diagnostics.py` | 확장 — cache-TTL 회귀 감지 | 1 |
| `src/harness_maker/context_lint.py` | 확장 — window % hard-cap + cache layout lint + MCP budget warn | 1, 10 |
| `src/harness_maker/security_scanner.py` | 확장 — hallucination + prod-name gate 통합 | 2, 8 |
| `src/harness_maker/conditional_router.py` | 확장 — reviewer scope 메타데이터 | 5 |
| `src/harness_maker/autoloop_driver.py` | 확장 — LLM 에러 분류 + 클래스별 cap | 10 |
| `templates/agents/consensus-arbiter.md` | 수정 — scope-aware consensus | 5 |
| `templates/stages/review.md.j2` | 수정 — 2-pass review (Phase 0 결과 따름) | 6 |
| `templates/stages/execute.md.j2` | 수정 — TDD 일반 문구 제거 + 의존성 힌트 | 11 |
| `templates/skills/trajectory-monitor/` | 신규 — drift monitor skill | 4 |

### Dependencies

- 외부 추가 의존 없음 (ADR-004: OTel 거부). stdlib `ast` + 기존 `anthropic`, `httpx` 활용.
- Phase 3(memory) → Phase 4(drift) 순서 의존 (drift monitor 가 episodic memory 참조 가능)
- Phase 0(ablation) → Phase 6(2-pass review) 순서 의존
- Phase 5(consensus) → Phase 6(2-pass review) 선후관계 권장
- 나머지 phase 간 의존 없음

### Design Decisions

- **LLM-first (CLAUDE.md 최우선):** 에러 분류(ADR-009), spec 품질 평가(ADR-006), drift score 정밀 판정(ADR-010), ablation 결과 판정(Interview #20) 모두 LLM 판단 위임. Python 레이어는 입출력 계약 + 저장 + 안전 레일만.
- **Self JSONL (ADR-004):** OTel-compatible 필드명 사용 (span_id, trace_id, timestamps) 하되 otelpy 미사용. export 는 `telemetry.export_otel()` 함수로 변환.
- **Hybrid drift (ADR-010):** 조건식 `cos_sim < 0.7` — cosine similarity 가 threshold 미만일 때만 LLM 정밀 판정 호출. threshold 는 `harness.yaml.drift.threshold` 로 사용자 설정 가능 (default 0.7).
- **Scope metadata (ADR-005):** 각 reviewer agent frontmatter 에 `review_scope: [security|performance|code|ux|concurrency]` 필드 추가. consensus-arbiter 가 이 필드로 cross-check 면제 결정.
- **Sequence pattern (ADR-008):** tool call 로그에서 sliding window (default 5 calls) 로 위험 시퀀스 패턴 매칭. 패턴은 YAML configurable.

### Data Flow

1. **Cost observability flow:** tool-call hook → telemetry.py (JSONL append) → cache_diagnostics.py (TTL 분석) → context_lint.py (window % 경고)
2. **Hallucination gate flow:** generated code → AST parse → import/symbol 추출 → package index lookup (stdlib + installed) → 미등록 심볼 → finding 생성 → security_scanner 통합
3. **Drift monitor flow:** SPEC/PLAN/prompt (다층 fallback) → baseline text → embedding → per-stage output embedding → cosine similarity → `cos_sim < 0.7` 이면 LLM 정밀 판정 → drift score (0-1) → threshold 초과 시 경고
4. **Memory flow:** stage 완료 → episodic/ (raw event JSONL) → semantic/ (LLM 요약 + keyword index) → profile/ (사용자 패턴 누적) → retrieval (neighbor expansion from episodic/)
5. **TDAD flow:** 파일 수정 목록 → test_dep_map.py (import graph + test filename convention) → 영향 받는 테스트 목록 → execute stage 에 구체적 힌트 삽입

### API Changes

- `harness.yaml` 에 `drift.threshold` (float, default 0.7) 키 추가
- `harness.yaml` 에 `memory.layers` (list, default [episodic, semantic, profile]) 키 추가
- reviewer agent frontmatter 에 `review_scope` 필드 추가
- security_scanner 에 hallucination gate + prod-name gate 추가 (기존 5-gate → 7-gate)

## 📝 Implementation Plan

### Phase 0: 2-pass Review Ablation
- **Scope (in):** `tests/ablation/` (신규), `work-docs/ablation-results-2pass.md` (신규)
- **Scope (out):** 기존 review stage, reviewer agents
- **Exit criterion:** `work-docs/ablation-results-2pass.md` 작성 완료. 5개 sample diff 에 대해 single-pass / 2-pass+redaction 결과 비교표 포함. LLM 이 5개 결과를 읽고 "2-pass 가 종합적으로 더 나은가" 판정 (binary: pass/fail + 1줄 근거).
- **Risk:** low
- **Rollback:** N/A (순수 연구, 기존 코드 미변경)

### Phase 1: Cost/Cache Observability + Context Guard
- **Scope (in):** `src/harness_maker/telemetry.py`, `src/harness_maker/cache_diagnostics.py`, `src/harness_maker/context_lint.py`, `templates/hooks/` (cost hook)
- **Scope (out):** reviewer agents, memory, security scanner
- **Exit criterion:** `uv run pytest tests/unit/test_telemetry.py tests/unit/test_cache_diagnostics.py tests/unit/test_context_lint.py -v` 전체 pass + JSONL 출력 검증 (cost record 1건 이상 포함). context_lint 에서 window 40% 초과 시 경고 발생 확인.
- **Risk:** low
- **Rollback:** Phase 1 시작 전 커밋으로 git revert (telemetry/context_lint/cache 관련 변경만 되돌림)

### Phase 2: AST Hallucination Gate
- **Scope (in):** `src/harness_maker/secscan/hallucination.py` (신규), `src/harness_maker/security_scanner.py` (통합)
- **Scope (out):** memory, drift, review stage
- **Exit criterion:** `uv run pytest tests/unit/test_hallucination_gate.py -v` 전체 pass. 알려진 hallucination fixture (존재하지 않는 import `from nonexistent_pkg import FakeClass`) 감지 확인.
- **Risk:** medium (AST parsing edge cases — dynamic imports, conditional imports)
- **Rollback:** Phase 1 완료 커밋으로 revert

### Phase 3: Episodic Memory (3-layer)
- **Scope (in):** `src/harness_maker/memory/` (신규 패키지 — `__init__.py`, `episodic.py`, `semantic.py`, `profile.py`, `retrieval.py`), `templates/memory/` (신규 templates), `src/harness_maker/models.py` (memory schema)
- **Scope (out):** 기존 `wiki.md`, `failures.md` 파일 포맷 미변경 (backward compat)
- **Exit criterion:** `uv run pytest tests/unit/test_memory/ -v` 전체 pass. write → read → retrieve (neighbor expansion) 사이클 검증. 기존 wiki.md/failures.md 와 공존 확인.
- **Risk:** medium (schema 설계, backward compat migration path)
- **Rollback:** Phase 2 완료 커밋으로 revert

### Phase 4: Trajectory Drift Monitor
- **Scope (in):** `src/harness_maker/drift_monitor.py` (신규), `templates/skills/trajectory-monitor/SKILL.md` (신규), `templates/agents/trajectory-monitor.md` (신규)
- **Scope (out):** review stage, consensus, security scanner
- **Exit criterion:** `uv run pytest tests/unit/test_drift_monitor.py -v` 전체 pass. (1) cosine pre-filter 가 mock embedding 으로 동작 확인 (2) `cos_sim < 0.7` 일 때 LLM 정밀 판정 호출 확인 (3) 다층 fallback(SPEC→PLAN→prompt) 동작 확인.
- **Risk:** medium (embedding 품질, threshold 튜닝)
- **Rollback:** Phase 3 완료 커밋으로 revert

### Phase 5: Consensus Scope-Aware Fix
- **Scope (in):** `templates/agents/consensus-arbiter.md` (수정), `src/harness_maker/conditional_router.py` (scope metadata 확장), reviewer agent templates (frontmatter `review_scope` 추가)
- **Scope (out):** review stage template, 2-pass review
- **Exit criterion:** `uv run pytest tests/unit/test_consensus.py -v` 전체 pass. security-reviewer 의 단독 security finding 이 cross-check 면제되어 grade 에 반영되는 시나리오 확인.
- **Risk:** low
- **Rollback:** Phase 4 완료 커밋으로 revert

### Phase 6: 2-pass Review (conditional on Phase 0)
- **Scope (in):** `templates/stages/review.md.j2` (수정), `templates/agents/code-reviewer.md` (수정), 기타 reviewer templates
- **Scope (out):** consensus (Phase 5 에서 완료), memory, drift
- **Exit criterion (ablation pass):** `uv run pytest tests/unit/test_2pass_review.py -v` 전체 pass. 시나리오: (1) metadata redaction 이 PR title/description 마스킹, (2) rubric-only verdict 가 finding list 반환, (3) conditional explanation 이 사용자 요청 시에만 첨가.
- **Exit criterion (ablation fail):** "2-pass 거부" ADR 작성 + `git diff --exit-code templates/stages/review.md.j2` 로 review stage 미변경 확인.
- **Risk:** medium (counter-intuitive claim — ablation 결과 의존)
- **Rollback:** Phase 5 완료 커밋으로 revert

### Phase 7: Tool Cascade Firewall
- **Scope (in):** `src/harness_maker/tool_cascade.py` (신규), `templates/hooks/` (cascade hook), `src/harness_maker/models.py` (recovery taxonomy types)
- **Scope (out):** chaos test (0.8.0 defer)
- **Exit criterion:** `uv run pytest tests/unit/test_tool_cascade.py -v` 전체 pass. retry(3회) → switch(대체 tool) → abort 시퀀스 확인. 실패 카운터 JSONL 기록 확인.
- **Risk:** low
- **Rollback:** Phase 6 완료 커밋으로 revert

### Phase 8: Production-Name Guard
- **Scope (in):** `src/harness_maker/secscan/prod_name_guard.py` (신규), `src/harness_maker/security_scanner.py` (통합)
- **Scope (out):** 기존 5 gates 미변경
- **Exit criterion:** `uv run pytest tests/unit/test_prod_name_guard.py -v` 전체 pass. `Read(prod.db) → Write(prod.db)` 시퀀스 패턴 감지 + `prod-*` 환경명 regex 매칭 확인.
- **Risk:** low
- **Rollback:** Phase 7 완료 커밋으로 revert

### Phase 9: Spec Strength Rubric
- **Scope (in):** `src/harness_maker/spec_quality.py` (신규), `templates/stages/spec.md.j2` (수정 — quality check 삽입), `templates/commands/hm/spec.md.j2` (수정)
- **Scope (out):** plan/execute stage
- **Exit criterion:** `uv run pytest tests/unit/test_spec_quality.py -v` 전체 pass. dev_mode=spec-driven 에서 약한 스펙(vague acceptance criteria) 차단 확인. dev_mode=task-driven 에서 경고만 확인.
- **Risk:** low
- **Rollback:** Phase 8 완료 커밋으로 revert

### Phase 10: Error-Class LLM Cap + MCP Budget Warn
- **Scope (in):** `src/harness_maker/autoloop_driver.py` (확장), `src/harness_maker/context_lint.py` (MCP 수 경고 추가)
- **Scope (out):** memory, drift, security
- **Exit criterion:** `uv run pytest tests/unit/test_autoloop_driver.py tests/unit/test_context_lint.py -v` 전체 pass. LLM 에러 분류 mock 으로 syntax→5회 cap / logical→2회 cap 적용 확인. MCP 서버 >6 시 경고 확인.
- **Risk:** low
- **Rollback:** Phase 9 완료 커밋으로 revert

### Phase 11: 코드↔테스트 의존성 힌트 (TDAD)
- **Scope (in):** `src/harness_maker/test_dep_map.py` (신규), `templates/stages/execute.md.j2` (일반 TDD 문구 제거 + 구체적 테스트 힌트 생성 로직)
- **Scope (out):** review stage, memory, security
- **Exit criterion:** `uv run pytest tests/unit/test_dep_map.py -v` 전체 pass. execute template 에서 "TDD 따르라" 일반 문구 제거 확인 + 파일 수정 시 영향 받는 테스트 목록 힌트 생성 확인.
- **Risk:** low
- **Rollback:** Phase 10 완료 커밋으로 revert

## 🧪 Testing Strategy

### Phase-Exit 대응 테스트 매핑

| Phase | Unit test | Integration (INTEGRATION=1) |
|-------|-----------|--------------------------|
| 0 | N/A (ablation — LLM 판정) | N/A |
| 1 | test_telemetry, test_cache_diagnostics, test_context_lint | — |
| 2 | test_hallucination_gate | test_hallucination_real (pip index, vcr cassette fallback) |
| 3 | tests/unit/test_memory/ | test_memory_retrieval |
| 4 | test_drift_monitor | test_drift_pipeline |
| 5 | test_consensus | — |
| 6 | test_2pass_review (conditional) | — |
| 7 | test_tool_cascade | — |
| 8 | test_prod_name_guard | — |
| 9 | test_spec_quality | — |
| 10 | test_autoloop_driver, test_context_lint | — |
| 11 | test_dep_map | — |

### Unit Tests (all phases)
- 각 phase 별 `tests/unit/test_<module>.py` 신규/확장
- LLM 호출은 `mock_anthropic_client` fixture 사용 (CLAUDE.md 정책)
- `freeze_time` 으로 timestamp 결정성 보장

### Integration Tests
- `tests/integration/test_memory_retrieval.py` — 3-layer memory write-retrieve cycle
- `tests/integration/test_drift_pipeline.py` — SPEC → drift score end-to-end
- `tests/integration/test_hallucination_real.py` — 실제 AST + pip index 조회
  - 네트워크 의존: `pytest.mark.skipif(not os.getenv("INTEGRATION"))` + vcr cassette fallback for CI

### E2E Tests
- `tests/e2e/test_plugin_live.py` 확장 — 신규 secscan gates 포함 (hallucination + prod-name)
- Manual checklist: `tests/cursor-compat/MANUAL_CHECKLIST.md` 에 신규 항목 추가

## ⚠️ Risks & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 12 phase 가 릴리스 지연 | High | Medium | 각 phase 독립적 → 병렬 작업 가능. 위험 phase(2,3,4) 를 앞으로 배치 |
| AST hallucination gate 의 dynamic import 미감지 | Medium | Medium | stdlib `ast` 한계 인정 → 정적 분석 범위만 커버, 미감지는 warn |
| 3-layer memory 기존 데이터 마이그레이션 | Medium | Low | 기존 wiki.md/failures.md 미변경 (공존). 신규 layer 는 빈 상태 시작 |
| 2-pass review ablation 이 negative 결과 | Low | Medium | Phase 0 에서 조기 발견 → Phase 6 skip, 기존 review pipeline 유지 |
| LLM 에러 분류 정확도 | Medium | Low | 분류 실패 시 default bucket (conservative cap) 적용. 분류 결과 JSONL 로그 |
| Drift score embedding 품질 | Medium | Medium | 초기 threshold 보수적 설정 (0.7), `harness.yaml.drift.threshold` 로 사용자 조정 |
| context_lint window 40% cap 이 과도한 경고 | Low | Low | warn-only (block 아님), 사용자 설정으로 threshold 조정 가능 |
| Hybrid drift 의 embedding 모델 선택 | Low | Medium | Anthropic embedding API 우선, 실패 시 경량 local model fallback |

## Out of 0.7.0 (Non-Goals)

- **Pitfall #8** (plugin update broken): 업스트림 CC `/plugin update` 이슈 — harness-maker 범위 밖. `/hm:refresh` 가 우회 경로.
- **Pitfall #9** (worktree ≠ 완전 격리): 외부 자원(DB, API) 격리는 사용자 책임. worktree-isolator SKILL.md 에 명시 추가만 (별도 phase 불필요).
- **Pitfall #11** (vendor 수치 신뢰): ai-readiness rubric 에서 "동료 검증된 수치만" 규칙 이미 있음. 추가 조치 불필요.
- **Bench harness (/hm:bench)**: cost-heavy. 0.8.0+ 검토.
- **Persona library 확장**: 코어 9개 유지, 도메인은 user-author 위임 (ADR-001 범위 외).
- **Multi-provider routing**: Anthropic-only 명시 거부 (ADR-007).
- **Chaos test**: ReliabilityBench 패턴 0.8.0 defer (Interview #11).

## ✅ Success Criteria

- [ ] 7개 Primary feature + spec strength rubric + TDAD 모든 unit test pass
- [ ] `uv run pytest` 전체 pass (기존 + 신규)
- [ ] `ruff check` + `ruff format --check` 통과
- [ ] `mypy --strict` 0 error
- [ ] 2-pass review ablation 결과 기록 완료 (LLM 판정 포함)
- [ ] Phase 0 결과에 따른 Phase 6 결정 기록 (도입 ADR 또는 거부 ADR)
- [ ] JSONL telemetry 출력 검증 (cost record 포함)
- [ ] hallucination gate 가 알려진 가짜 import 감지
- [ ] drift monitor 가 hybrid 산출 (cosine pre-filter → LLM) 동작
- [ ] drift monitor 가 SPEC/PLAN/prompt 다층 fallback 동작
- [ ] episodic memory write → retrieve 사이클 동작
- [ ] consensus-arbiter 가 scope-aware cross-check 수행
- [ ] prod-name guard 가 Read→Write 시퀀스 감지
- [ ] spec strength rubric 이 spec-driven 에서 약한 스펙 차단
- [ ] error-class cap 이 LLM 분류 기반으로 적용
- [ ] MCP 서버 >6 시 context_lint 경고 발생
- [ ] execute template 에서 일반 TDD 문구 제거 + 의존성 힌트 생성

## 🔍 Plan Validation

### 1차 검증 (plan-validator)
- **결과:** MAJOR_REVISION
- **Critical:** 드리프트 점수 산출 방식 모순 (embedding vs LLM) — ADR-010 신설로 해소
- **Warnings (6건):** Phase 1 rollback 문구 수정 / Pitfall #3 → Phase 11 추가 / Pitfall #8/#9/#11 → Non-Goals 문서화 / Phase 6 exit 정량화 / Testing 매핑표 추가 / Executive Summary ADR 목록 + ablation 기준 추가

### Follow-up 인터뷰 (Round 6)
- Interview #17-#20: 드리프트 하이브리드, TDAD Phase 11, 잔여 pitfall Non-Goal, ablation LLM 판정 확정

### 2차 검증 (plan-validator)
- **결과:** APPROVED
- **Suggestions (2건, non-blocking):**
  1. cosine threshold 조건 문구 통일 → `cos_sim < 0.7` 로 고정 (본 문서에 반영 완료)
  2. Phase 6 ablation 실패 분기 exit 재현성 → `git diff --exit-code` 추가 (본 문서에 반영 완료)
