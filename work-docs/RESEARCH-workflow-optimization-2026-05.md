---
type: research
task_slug: workflow-optimization-2026-05
status: complete
created: 2026-05-17
tags: [harness-maker, research, workflows, latency, prompt-caching, preset]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[PLAN-health-consolidation]]"
  - "[[PLAN-deep-interview-llm-delegation]]"
  - "[[RESEARCH-loop-interview-intensity]]"
  - "[[RESEARCH-loop-longevity-strategies]]"
  - "[[PLAN-loop-interview-intensity]]"
  - "[[PLAN-llm-code-review-2026]]"
summary: "Workflow latency dominated by check-suite × N reruns, drift-gate × N reruns, 3-layer-gate × 3 in res-spec-plan, and missing cache_control on relevance/secscan."
---

# RESEARCH — Workflow Stage Optimization (2026-05)

## 🎯 Recommended Direction

**대부분의 절감은 품질 손실 0 — 캐싱·중복 제거·이미 SKILL.md 에 약속된 fresh-skip 헬리스틱의 강제다.** 가장 큰 leverage 는 (a) `exec-rev-wrap-ver` 안에서 **전체 check suite 가 4번 실행**되는 것 → 1-2번으로 축약 (b) `relevance-filter` / `security-scanner` 의 LLM system prompt 에 `cache_control: ephemeral` 추가 (c) `research-crawler` 의 24h HTTP cache 추가 (CLAUDE.md 가 약속하지만 코드에 없음). Side preset 한정으로는 **3-Layer Deep Interview Gate 의 라운드 캡을 3→1 로 (또는 Phase 0 rubric 만으로 stop)** + **`res-spec-plan` 안의 3중 gate 를 1번으로 합치는** 큰 리프트가 가능. Stage 내부 phase 자체엔 preset 분기가 0개이므로 — 분기 추가 자체가 신규 작업.

## 🔍 Refinement Decisions

- **Discovery lens**: Technical architecture (workflow templates · cost markers) + Risk (quality regression vs latency) + User-workflow (실행 시간 체감). arXiv/벤치마크 렌즈 미사용 — 내부 audit.
- **Skip Phase 0/0.5 interview**: 토픽 명확 (전체 workflow 감사). 대신 audit 깊이를 ultrathink 수준으로.
- **Scope**: 7 atomic stage + 4 fused workflow + 6 meta command + 11 skill. ADR 작성 X — 본 문서는 informational, decision 은 `/hm:plan` 에서.

## 🛠️ Approaches Found

본 문서는 단일 추천이 아닌 **다층 최적화 메뉴**다. `/hm:plan` 에서 어느 하위 집합을 ADR 화할지 결정.

### Layer A — Universal quality-neutral wins (Side + Production 모두)

#### A1. 전체 check suite re-run 4× → 1-2× 로 축약

| Field | Content |
|-------|---------|
| Approach | Single Source of Truth for "full verification suite passed" |
| Assumption | 같은 commit/diff 에서 lint + mypy + pytest 결과는 결정적 → 첫 PASS 이후 동일 input 에 대해 재실행 불필요 |
| Evidence | `exec-rev-wrap-ver.md` 분석: **4번 실행 위치** — execute Phase D (per-PLAN-phase × 4 checks · `templates/stages/execute.md.j2 L191-203`), review build-verify in auto-fix (`review.md.j2 L288-294`), wrapup Step 2 (`wrapup.md.j2 L69-94`), verify Check 2 (`verify.md.j2 L56-82`). `wrapup.md.j2 L93` 는 명시적으로 "Step 2 failure → STOP, no retry" — Step 2 는 정말 final safety net 인데, execute Phase D 가 이미 같은 commit 에서 통과했다면 동일 결과 보장 |
| Trade-off | Skip 조건 누락 시 (git mutation, env 변경, hook 변경) false-positive 가능 → file-hash 기반 invariant 필요. 안전한 fallback: env hash + diff hash + tool-version hash 일치 시만 skip |
| Compatibility | `wrapup` / `verify` 가 stage_marker file 로 "verified-at: <sha>" 기록 → 다음 stage 가 sha 일치 시 skip. 100% backward-compatible (sha mismatch → 기존대로 재실행) |
| Risk | low — `verify --force` flag 가 이미 존재 (`verify.md.j2 L31`); 같은 패턴 확장 |

**기대 효과**: 큰 프로젝트에서 wall-clock 2-3분 절약 per workflow (mypy --strict + 1885 test suite 기준). 품질 보존.

#### A2. Drift gate 1×만 실행 (현재 3-4×)

| Field | Content |
|-------|---------|
| Approach | Drift detection 을 review stage 단독 owner 로 |
| Assumption | execute Step 4, wrapup Step 3, verify Check 1 의 drift 체크는 review Step 2 의 결과를 신뢰하면 reentrant 불필요 |
| Evidence | execute Step 4 (`execute.md.j2 L210-220`), review Step 2 (`review.md.j2 L110-116`), wrapup Step 3 (`wrapup.md.j2 L96-103` — 이미 "advisory"), verify Check 1 (`verify.md.j2 L44-54`). wrapup Step 3 코멘트 "advisory" → 이미 부분 무력화 의도. review 가 단독으로 책임지면 LLM-heavy drift 진단이 1번 |
| Trade-off | review-only workflow (`exec-rev`) 에서는 wrapup 이 없으니 영향 X. `exec-rev-wrap-ver` 에서 review→wrapup→verify 순서로 drift 가 단방향 cascade — review 가 놓친 drift 는 wrapup/verify 에서도 어차피 같은 알고리즘이라 못 잡음 |
| Compatibility | Side default `exec-rev-wrap` 변화 없음. `verify` 는 read-only stage 이므로 Check 1 을 "verify only that review's drift verdict was recorded" 로 demote 가능 |
| Risk | low — drift 는 advisory 가 default. P0 차단은 review 의 grade gate 가 담당 |

#### A3. `relevance-filter` 에 `cache_control: ephemeral` 추가

| Field | Content |
|-------|---------|
| Approach | Per-item LLM 호출의 system prompt 캐싱 |
| Assumption | `src/harness_maker/relevance.py` 의 `_build_relevance_system_prompt` 는 CLAUDE.md + README 발췌를 prefix 로 매번 rebuild — N items 만큼 prefix tokens 재전송 |
| Evidence | `rg cache_control src/` → 2개 호출 사이트만 (`foreign_config.py:308`, `llm_judge.py:79`). `relevance.py` 의 `score_item` 은 우회. ai-readiness-rubric 이 이미 `llm_judge` 경유로 캐싱 → 동일 패턴 적용 |
| Trade-off | 없음 — Anthropic prompt cache 는 5분 TTL, batch 안에서 N items 가 동일 prefix 면 hit 률 90%+. 첫 호출만 full cost, 나머지는 input cache discount |
| Compatibility | API-only 변경, 호출자 영향 0 |
| Risk | very low — 캐시 miss 시 기존 비용으로 fallback |

**기대 효과**: `/hm:health` Step 2 에서 N=20-50 items 처리 시 prompt cost 60-80% 절감.

#### A4. `security-scanner` Gate 5 (prompt-injection) 에 `cache_control` 추가

| Field | Content |
|-------|---------|
| Approach | A3 와 동일 패턴 |
| Assumption | `security_scanner.py:100-178` 의 prompt-injection LLM second pass — *.md / *.txt corpus 위에서 medium-severity 후보를 per-file 평가 → 매번 동일 rubric system prompt |
| Evidence | `rg cache_control` 결과에 secscan 없음. SKILL.md 가 명시적으로 "expensive when LLM scanner on (N items × 1 call)" |
| Trade-off | 없음 |
| Compatibility | API-only |
| Risk | very low |

#### A5. `research-crawler` 에 HTTP cache 추가 (CLAUDE.md 약속이행)

| Field | Content |
|-------|---------|
| Approach | 24h ETag/timestamp 캐시 `~/.cache/harness-maker/crawler/<source>/<date>.json` |
| Assumption | CLAUDE.md L: "GitHub API 는 unauthenticated (60/h) + `~/.cache/harness-maker/` 캐시 공유" — 약속이지만 `src/harness_maker/crawler/{github_releases,anthropic_blog,arxiv,osv_dev}.py` 에 캐시 구현 없음 (4개 모두 fresh `httpx.Client`) |
| Evidence | audit 결과: "research-crawler has no HTTP cache despite CLAUDE.md promising shared cache" |
| Trade-off | Stale data 가능 — 24h TTL 또는 `--no-cache` flag. CVE/security feed 는 짧은 TTL (1h) 권장 |
| Compatibility | crawler return 형식 불변 |
| Risk | medium — OSV.dev CVE 데이터는 fresh 가 중요. TTL 별도 (Anthropic blog/arxiv 24h, OSV.dev/GitHub release 1h) |

#### A6. 일관된 fresh-skip 헬리스틱 강제 (이미 SKILL.md 에 약속됨, 미시행)

| Field | Content |
|-------|---------|
| Approach | "지난 N분 안에 같은 input 으로 PASS 됐으면 skip" 패턴을 4개 skill 에 강제 |
| Assumption | SKILL.md 들이 이미 명시하지만 강제 코드 없음: `agent-quality-rubric` ("skip Platinum/Gold already-scored"), `security-scanner` ("skip when clean scan <24h ago AND no lock changes"), `verify-before-completion` ("skip when previous PASS in same session is still valid"), `context-linter` (이미 cheap, 변화 X) |
| Evidence | audit 결과 4개 모두 "SKILL doc encourages... but not enforced" |
| Trade-off | Skip 조건 만족 시 매 invocation 0 cost. 미만족 시 기존 비용 |
| Compatibility | 100% backward — skip 여부는 함수 entry 의 cheap pre-check |
| Risk | low |

#### A7. Memory tier loading: per-workflow once (현재 per-stage)

| Field | Content |
|-------|---------|
| Approach | Fused workflow 의 prefix 단계에서 hot/warm 메모리 1번 로드 → 후속 stage 가 컨텍스트에 이미 보유 |
| Assumption | `exec-rev-wrap-ver` 에서 execute/review/wrapup/verify 가 각자 session/failures/wiki 를 다시 읽음. 같은 conversation context 안에서 cache hit 이지만 token cost 는 발생 |
| Evidence | execute.md.j2 L59-61, review.md.j2 L38-40, wrapup.md.j2 L34 — 같은 3개 파일 |
| Trade-off | LLM 컨텍스트가 부풀어도 prompt cache 가 흡수. 진짜 절감은 atomic-only 사용 사례 0 — fused workflow 에서만 |
| Compatibility | atomic stage 단독 호출 시 이전과 동일 — fused workflow 의 wrapper preamble 이 prefix 로 inject |
| Risk | very low |

#### A8. Reviewer Pass 1.5 verifier 활성화 (deferred, ADR-008)

| Field | Content |
|-------|---------|
| Approach | code-verifier agent 를 Pass 1 결과 reduce-only 검증으로 활성화하여 Pass 2 LLM 호출 회수 축소 |
| Assumption | 현재 Pass 1 (redacted) → Pass 2 (full context) 가 always 2회. Pass 1.5 (drop/demote false positives) 활성 시 Pass 2 가 받는 findings 수 감소 → Pass 2 의 LLM 부담 감소 |
| Evidence | `review.md.j2 L143-149` "documented as deferred, ADR-008; not auto-invoked" |
| Trade-off | code-verifier agent 추가 LLM 호출. 하지만 verifier 는 reduce-only 라 cheap (KEEP/DROP/DEMOTE only) |
| Compatibility | reviewer set 확장, 이미 agent 정의는 존재 (`templates/agents/code-verifier.md.j2`) |
| Risk | low — verifier 가 잘못 DROP 해도 Pass 2 가 final say |

### Layer B — Side preset 한정 절감 (품질 양보 OK)

#### B1. Side 에서 3-Layer Deep Interview Gate 의 라운드 캡 축소

| Field | Content |
|-------|---------|
| Approach | Side preset: max 3 rounds → max 1 round; 2-consecutive-PASS → 1-PASS |
| Assumption | Side 의 dev velocity 가 quality bar 보다 우선. Phase 0 rubric 만으로 충분한 시그널 |
| Evidence | research/spec/plan 3개 stage 모두 동일 gate (`research.md.j2 L160`, `spec.md.j2 L153`, `plan.md.j2 L278`). 현재 Side preset 에서도 동일 round cap |
| Trade-off | Side 프로젝트의 spec/plan 모호도 약간 증가. 하지만 Side 는 `exec-rev-wrap` 이 default → spec/plan 자체가 스킵됨 |
| Compatibility | Jinja `{% if preset == 'Side' %}` 분기 도입 — **stage template 에 최초의 preset 분기**. 신중한 PR 필요 |
| Risk | medium — 인터뷰 단축은 모호한 ADR 로 이어질 수 있음. Side 의 명시 정책 (CLAUDE.md "Side 는 빠르게") 과 정합 |

#### B2. Side 에서 reviewer Pass 1 redaction 생략

| Field | Content |
|-------|---------|
| Approach | Side reviewer set = `[code-reviewer]` 1개 → cross-reviewer bias mitigation 불필요 → Pass 1+2 → Pass 2 only |
| Assumption | Pass 1 의 redaction 목적은 여러 reviewer 가 같은 metadata 보고 cargo-cult 합의하는 것 방지. Reviewer 가 1명이면 bias source 자체가 없음 |
| Evidence | audit 결과 Side enabled reviewers = `["code-reviewer"]` (interview.py:118). review.md.j2 Pass 1+2 는 2회 LLM. Single reviewer 환경에서는 Pass 1 의 redaction → reasoning 비교 가치 0 |
| Trade-off | 없음 (재현 가능한 정합 손실 없음 — Pass 2 가 final verdict) |
| Compatibility | review.md.j2 conditional 추가: `{% if config.reviewers.enabled|length == 1 %}skip Pass 1{% endif %}` — preset 직접 분기 아니라 reviewer-count 기반이라 더 범용 |
| Risk | low |

**기대 효과**: Side review 의 LLM 호출 50% 감소.

#### B3. Side default `max_review_rounds: 3 → 2`

| Field | Content |
|-------|---------|
| Approach | Side harness.yaml default `reviewers.max_review_rounds: 2` (현재 3) |
| Assumption | Side 는 grade target 도 더 낮음 (B vs A). 2 라운드면 보통 수렴 |
| Evidence | `review.md.j2 L70` default 3. interview.py 가 Side/Prod 동일하게 설정 추정 |
| Trade-off | Auto-fix loop 가 2번까지만 시도 → 잔여 issue 는 human review needed flag |
| Compatibility | harness.yaml field 변경, 사용자 override 가능 |
| Risk | low |

#### B4. Side 에서 spec-quality gate 의 `dev_mode == 'spec-driven'` HALT 미적용

| Field | Content |
|-------|---------|
| Approach | Side preset 인터뷰 default `dev_mode = task-driven` 으로 — 현재 이미 그럴 가능성 |
| Assumption | `spec.md.j2 L249-256` 의 HALT 는 dev_mode=spec-driven 시만 발동. Side+task-driven 조합이면 WARN only → 이미 사실상 적용됨 |
| Evidence | `interview.py` 의 `recommend_dev_mode` 가 Side 에 task-driven 추천하는지 확인 필요 — **open question** |
| Trade-off | N/A (이미 그럴 가능성) |
| Compatibility | N/A |
| Risk | very low |

#### B5. `res-spec-plan` 의 3중 GCIC gate 를 단일 gate 로 합침 (Side only)

| Field | Content |
|-------|---------|
| Approach | research Phase 0.5 + spec Step 2.5 + plan Step E 를 fused workflow 안에서는 1번만 수행 (research 가 먼저 통과시키면 spec/plan 이 score 상속) |
| Assumption | GCIC 4축 (Goals/Constraints/Inputs/Context) 은 한 task slug 안에서 안정. research 가 score ≥0.8 통과하면 spec/plan 도 같은 답변 셋에서 PASS |
| Evidence | audit 결과: 3개 gate 가 "동일 구조 + 다른 question pool". score 형식 동일 (G×0.4 + C×0.3 + OC×0.3) |
| Trade-off | spec/plan 의 Layer 2 probing (WRONG/METHOD/STAKEHOLDER/STYLE/PERF) 이 research 의 5-type (NOT-USEFUL/AVOID/DEPTH/AUDIENCE/TIME-SCOPE) 와 다름 → 합치면 일부 probe 누락. Side 는 ROI 가 낮음 |
| Compatibility | fused workflow 만 영향. atomic stage 단독 사용 시 기존대로 |
| Risk | medium-high — Production 에서는 절대 적용 X. Side fused workflow `res-spec-plan` 자체가 Production-only starter 이므로 (`interview.py:54-89`) 이 최적화는 사실 적용 불가 |

> **B5 결론: 적용 불가 (architectural mismatch).** Side preset 은 애초에 `res-spec-plan` 을 starter set 에 안 넣음. Side 사용자가 명시 호출 시에만 발생 — 그 경우엔 사용자가 풀 인터뷰를 원한 것.

#### B6. Side `plan.md` Step 3 unlimited round 에 hard cap (예: 5)

| Field | Content |
|-------|---------|
| Approach | `plan.md.j2 L111` Step 3 의 `unlimited rounds` 를 Side preset 시 `max 5` 로 |
| Assumption | Side 는 rapid prototype, 8+ 라운드 인터뷰는 over-engineering |
| Evidence | audit 결과: plan Step 3 main loop unlimited (line 111) |
| Trade-off | 모호도 잔존 시 ADR 가 incomplete. 하지만 Side 정책상 "WARN only, continue" |
| Compatibility | Jinja preset 분기 신규 도입 |
| Risk | low |

### Layer C — 구조적 리프트 (둘 다 적용 가능, 더 큰 변경)

#### C1. 공통 메모리/메타 prefix 를 fused workflow head 에 inject

| Field | Content |
|-------|---------|
| Approach | `templates/commands/hm/workflow_command.md.j2` 에 stage 진입 직전 단일 prefix block — 메모리 로드 + harness.yaml 파싱 + drift baseline 캡쳐 |
| Assumption | 4개 atomic stage 가 같은 prefix 반복 — fused 환경에서는 1번만 |
| Evidence | A7 와 같은 발견. wrapper template 이 이미 존재 |
| Trade-off | atomic stage 단독 호출 시 prefix 부재 시 fallback 필요 (`if not loaded then load`) |
| Compatibility | atomic stage 호환성 유지하려면 stage 내부의 메모리 로드는 idempotent guard 로 변환 |
| Risk | medium — 리팩터링 범위 |

#### C2. `verify-before-completion` 의 `Preset.SIDE` hardcoding 제거

| Field | Content |
|-------|---------|
| Approach | Check 3 baseline 비교에서 `Preset.SIDE` 하드코딩 (`compute_readiness(Preset.SIDE)`) → `harness.yaml.preset` 으로 |
| Assumption | Production 사용자가 Side baseline 으로 비교 받는 정확성 버그 |
| Evidence | audit 결과 명시. SKILL.md 의 cost description 과 무관한 correctness bug |
| Trade-off | 없음 (버그 픽스) |
| Compatibility | 100% — Production baseline 이 더 strict 라 false-negative 만 감소 |
| Risk | very low |

#### C3. `/hm:health` per-item AskUserQuestion 을 max-3 batch 로

| Field | Content |
|-------|---------|
| Approach | unresolved item N 개를 3개씩 묶어 multi-select 로 일괄 accept/reject/defer |
| Assumption | 현재 health.md `Never batch into yes/no over multiple items` 정책 → fatigue. multi-select 는 정책에 위배 X (각 item 의 답이 다를 수 있음) |
| Evidence | health.md L: "1 per unresolved item across the 3 layers (no batching... explicit Never batch into yes/no over multiple items)" |
| Trade-off | UI 가 multi-question 한 화면에 표시 → 사용자 인지 부담 약간 증가, 하지만 round-trip 횟수 N/3 로 축소 |
| Compatibility | AskUserQuestion 의 1-4 question batch 가 native 지원 |
| Risk | low |

#### C4. `/hm:refresh` deprecation / merge into `/hm:health`

| Field | Content |
|-------|---------|
| Approach | refresh.md 를 `/hm:health` 의 Step 2 external_risks 로 정식 흡수, alias 유지 |
| Assumption | refresh.md frontmatter version 0.11.5 — 0.13.0 health-consolidation 이 partial migration. crawler+relevance-filter 패턴이 동일 |
| Evidence | `git log` 의 commit `82eaddb feat(0.13.0): consolidate audit commands into /hm:health`. refresh.md 가 0.11.5 라 v 누락 |
| Trade-off | Backward compat: `/hm:refresh` 호출 시 health Step 2 로 redirect + deprecation notice |
| Compatibility | 100% — alias 만 두면 됨 |
| Risk | low |

#### C5. `/hm:loop` Gate 2 LLM eval 빈도 감소 (every-iter → every-N-iter)

| Field | Content |
|-------|---------|
| Approach | `exit_criteria_checklist` 의 LLM-judged criteria 를 매 iter X 가 아니라 2-3 iter 마다 |
| Assumption | criteria 가 충족-안됨 → 충족 으로 바뀌는 데 보통 multi-iter 소요. 매 iter eval 은 over-sampling |
| Evidence | loop.md L: "Gate 2 per-criterion LLM eval (every iter)". `failed_streak_cap: 5` 가 이미 multi-iter tolerance |
| Trade-off | 수렴 감지가 1-2 iter 지연 → 추가 1-2 iter cost vs LLM eval 절감 trade-off. 균형점 정확히 산출 필요 |
| Compatibility | loop intensity tier 에 `eval_frequency` 추가 — quick=3, standard=2, thorough/maximum=1 |
| Risk | medium — 수렴 감지가 너무 늦으면 wrap 지연. ablation 필요 |

### Layer D — 잘못된 가정 / 적용 불가 (기록만)

#### D1. Stage 내부 preset 분기 추가 — 작은 효과 대비 큰 비용

| Field | Content |
|-------|---------|
| Approach | execute/review/wrapup/verify 안에 `{% if preset == 'Side' %}` 분기 추가 |
| 결론 | **하지 않음.** Side 는 이미 `exec-rev-wrap` (4 stage 중 3) default — stage 자체를 누락시킴으로써 절감. 추가 분기는 maintenance burden ↑↑, 절감 marginal. CLAUDE.md "stage 내부 preset 분기 0" 이 의도된 단순성 |

#### D2. Plan-validator 호출 제거

| Field | Content |
|-------|---------|
| 결론 | **하지 않음.** plan-validator 가 MAJOR_REVISION 잡아낸 사례가 work-docs/PLAN-* 여러 건 — 제거 시 품질 손실 명확 |

## ⚠️ Pitfalls

1. **Skip 헬리스틱의 sha invariant**: A1 (check suite skip) 은 commit sha 만이 아니라 (diff hash + tool version hash + env hash) 모두 일치할 때만 안전. 같은 sha 라도 `uv.lock` 변경, mypy 버전 변경 시 결과 다름. **kairos 0.5.7 metrics forensic 2026-05-08** 사례와 같은 silent divergence 위험.

2. **prompt cache 5분 TTL**: A3/A4 의 `cache_control: ephemeral` 은 5분 안에 다음 호출 와야 hit. N=100 items 의 batch 면 보통 OK 하지만, user pause 가 5분 넘으면 cache miss → 첫 호출 cost 다시. mitigation: `cache_control: persistent` 검토.

3. **drift gate 단일화 (A2) 의 false-negative**: review 가 catch 못한 drift 가 wrapup 단계에서 발견되는 경우 있음 (특히 사용자가 wrapup 전 추가 ad-hoc edit). 대응: wrapup Step 3 advisory 유지 (REMOVE 가 아니라 DEMOTE).

4. **3-Layer Gate cap 축소 (B1) 의 ADR 부실**: research 의 score=0.8 이 spec/plan 에서도 충분하다는 보장 없음 — `spec` 의 Layer 2 type 들 (WRONG/METHOD/STAKEHOLDER) 은 research 가 묻지 않은 차원. mitigation: B5 는 적용 불가 결론.

5. **`/hm:refresh` deprecation (C4) 의 hook 누락**: refresh.md 에 박힌 hooks (예: pre-commit 의 staleness check) 가 health 로 안 옮겨졌을 수 있음. 통합 전 grep 필요.

6. **B2 의 1-reviewer 가정 깨짐**: 사용자가 Side preset 에서 `--with-reviewers=security-reviewer` ad-hoc 추가하면 count=2 가 됨 → 분기 잘못 발동. 조건은 `enabled set ∪ ad-hoc set` 의 cardinality 로 평가해야 함.

7. **HTTP cache (A5) TTL 의 CVE 위험**: OSV.dev 1h TTL 도 0-day disclosure 시 너무 길 수 있음. critical CVE 알림은 별도 path 필요.

## ❓ Open Questions (for `/hm:plan` to lock down)

1. **A1 의 skip key 구성**: `commit_sha + diff_hash + uv.lock_hash + tool_versions_hash` — 정확한 hash 입력 결정 필요. 어디 파일에 stage_marker 기록? `.claude/observability/verify-cache.json`?

2. **A2 의 drift gate cascade**: review Step 2 만 owner 로 → wrapup Step 3 와 verify Check 1 은 record-check 로 demote. 명확한 demote 정책 필요 — "review 가 drift 발견 시 wrapup 가 차단" vs "verify 가 review 산출물 신뢰 후 record 만 보고"?

3. **A3/A4 의 `cache_control` 적용 범위**: `relevance.py` / `security_scanner.py` 의 LLM call site 가 system prompt + user msg 형태인지 단일 prompt 형태인지 확인 필요 — Anthropic API 의 cache_control 은 system 또는 messages 의 content block 에 붙음.

4. **A5 의 cache 디렉토리 정책**: `~/.cache/harness-maker/` (CLAUDE.md 약속) vs `.claude/cache/` (project-local). XDG 표준은 전자, project-isolation 은 후자.

5. **A6 의 fresh-skip threshold**: `agent-quality-rubric` "skip Platinum/Gold" 는 명확. `security-scanner` "24h ago AND no lock changes" 는 lock = `uv.lock` 만? `package.json`? `Cargo.lock`?

6. **B1/B6 의 preset 분기 도입 정책**: CLAUDE.md "stage 자체엔 preset 분기 0" 원칙을 깰지, 아니면 harness.yaml field (예: `interview.max_rounds: 3`) 로 우회할지. 후자가 더 정합.

7. **B3 의 default 변경 영향**: 기존 Side 하네스 (이미 max_review_rounds=3 으로 렌더됨) 들은 어떻게 마이그레이션? `/hm:make` 자동 update 가 user override 를 덮어쓰지 않게 (CLAUDE.md §1).

8. **C1 prefix block 의 reentrancy**: atomic stage 단독 호출 시 prefix 부재 — guard 패턴은 stage 내부에 `if memory_loaded == False: load` 로? 아니면 fused-only 분기?

9. **C5 의 ablation**: Gate 2 frequency 2 vs 3 에 의한 수렴 지연 측정. work-docs/ablation-results-2pass.md 와 같은 형식의 표 필요.

## 📚 Sources

내부 audit 만 사용 — 외부 URL/library doc 없음. arXiv/web search 미수행 (lens 결정).

- 내부 grep / 코드 read 결과:
  - `src/harness_maker/templates/stages/{research,spec,plan,execute,review,wrapup,verify}.md.j2`
  - `src/harness_maker/templates/commands/hm/*.j2` (rendered: `.claude/commands/hm/*.md`)
  - `src/harness_maker/templates/skills/*/SKILL.md.j2` (rendered: `.claude/skills/*/SKILL.md`)
  - `src/harness_maker/templates/harness-yaml/{Side,Production}.yaml.j2`
  - `src/harness_maker/templates/settings/{Side,Production}.json.j2`
  - `src/harness_maker/{interview,synthesize,recommendation,readiness,context_lint,relevance,security_scanner,agent_quality,llm_judge,foreign_config}.py`
  - `src/harness_maker/crawler/{__init__,anthropic_blog,github_releases,arxiv,osv_dev}.py`

## 🔗 Related Internal Docs

- [[PLAN-health-consolidation]] — 0.13.0 commit `82eaddb` 가 audit 명령들을 `/hm:health` 로 합침. `/hm:refresh` 는 부분 마이그레이션.
- [[PLAN-deep-interview-llm-delegation]] — 3-Layer Gate 의 LLM 위임 결정 배경. B1/B6 의 round cap 변경 시 이 결정과 충돌 여부 확인.
- [[RESEARCH-loop-interview-intensity]] / [[PLAN-loop-interview-intensity]] — loop 의 intensity tier 가 이미 quality vs speed lever 임. C5 는 그 확장.
- [[RESEARCH-loop-longevity-strategies]] — `failed_streak_cap`, `max_iter` 등 안전 캡 설계. C5 의 "convergence 감지 지연" 위험과 정합 필요.
- [[PLAN-llm-code-review-2026]] — Pass 1/1.5/2 redaction 의 ADR-008 위치. A8 직접 영향.
- [[ablation-results-2pass]] — 2-pass redaction 효과 측정. A8 / B2 의 ROI 계산에 사용.
