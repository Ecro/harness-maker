---
type: research
task_slug: harness-gap-cot-2026-05
status: complete
created: 2026-05-08
tags: [harness-maker, research, claude-code, cursor, agent-harness, swe-bench, observability, reliability]
mtime_warn_days: 14
libs_fetched:
  - github/spec-kit
  - bmad-code-org/BMAD-METHOD
  - SuperClaude-Org/SuperClaude_Framework
  - ruvnet/ruflo (claude-flow)
  - buildermethods/agent-os
  - Pimzino/claude-code-spec-workflow
  - eyaltoledano/claude-task-master
  - wshobson/agents
  - neiii/bridle
  - github.com/anthropics/claude-code (issues)
sources:
  - https://github.com/github/spec-kit
  - https://github.com/buildermethods/agent-os
  - https://github.com/bmad-code-org/BMAD-METHOD
  - https://github.com/SuperClaude-Org/SuperClaude_Framework
  - https://github.com/ruvnet/ruflo
  - https://github.com/Pimzino/claude-code-spec-workflow
  - https://github.com/eyaltoledano/claude-task-master
  - https://github.com/wshobson/agents
  - https://github.com/neiii/bridle
  - https://arxiv.org/abs/2509.02360
  - https://arxiv.org/abs/2604.10508
  - https://arxiv.org/abs/2603.00539
  - https://arxiv.org/abs/2603.18740
  - https://arxiv.org/abs/2604.16706
  - https://arxiv.org/abs/2509.25238
  - https://arxiv.org/abs/2601.06112
  - https://arxiv.org/abs/2604.04853
  - https://arxiv.org/abs/2602.20478
  - https://arxiv.org/abs/2604.21570
  - https://arxiv.org/abs/2603.17973
  - https://arxiv.org/abs/2601.19106
  - https://arxiv.org/abs/2601.06007
  - https://arxiv.org/abs/2602.10133
  - https://arxiv.org/abs/2604.25850
  - https://arxiv.org/abs/2603.17104
  - https://github.com/anthropics/claude-code/issues/42796
  - https://github.com/anthropics/claude-code/issues/41930
  - https://github.com/anthropics/claude-code/issues/46829
  - https://github.com/anthropics/claude-code/issues/46917
  - https://github.com/anthropics/claude-code/issues/34685
  - https://github.com/anthropics/claude-code/issues/45893
  - https://github.com/anthropics/claude-code/issues/53262
  - https://simonwillison.net/2026/Apr/22/claude-code-confusion/
  - https://devinterrupted.substack.com/p/inventing-the-ralph-wiggum-loop-creator
  - https://medium.com/@malikchohra/i-built-a-memory-os-after-claude-code-hallucinated-42-of-my-code-1896334b9cfc
  - https://dev.to/willtorber/spec-kit-vs-bmad-vs-openspec-choosing-an-sdd-framework-in-2026-d3j
  - https://metr.org/blog/2026-1-29-time-horizon-1-1/
  - https://thenewstack.io/anthropic-launches-a-multi-agent-code-review-tool-for-claude-code/
related_docs:
  - "[[REVIEW-agents-skills-hooks-uplift-2026-05-08]]"
  - "[[REVIEW-cursor-compat-uplift-2026-05-08]]"
  - "[[plans/PLAN-cursor-compat-uplift]]"
summary: "Reliability Stack 우선 — 트래젝토리 드리프트/cost-bleed/심볼-진위/에피소딕 메모리/2-pass 리뷰가 7대 ROI 갭"
---

# Research: harness-maker 갭 분석 vs 2026-05 유명 하네스 + COT 신규 기능 발굴

> 본 문서는 `/hm:plan harness-gap-cot-2026-05` 가 Step 2 에서 frontmatter `research_doc:` 로 직접 read 함. spec/plan 진입 전 마지막 정찰.

## 🎯 Recommended Direction

**채택 방향: "Reliability Stack" 우선 + 스펙-드리븐 갭 보강 (Secondary).**

다른 하네스가 갖지 못한 영역에서 harness-maker 의 권능을 늘리려면, 새 reviewer prompt 를 더 추가하는 것보다 **tool / middleware / long-term memory** 레이어에 투자해야 한다 — 이는 arxiv 2604.25850 (Agentic Harness Engineering, Apr 2026) 의 ablation 이 명시적으로 보여주는 결론. 동시에 커뮤니티 페인 데이터(quota bleed, 42% hallucination, prod DB 삭제 사고)와 정확히 같은 곳을 가리킨다.

**Primary 7대 추가 기능 (research-grounded + community-pain-grounded)**:
1. 트래젝토리 드리프트 스코어 + PRM-스타일 trajectory-monitor agent
2. AST + 패키지 introspection 심볼-진위 (hallucination) 게이트
3. `.claude/memory/episodic/` 영구 에피소딕 메모리 + 이웃 확장 retrieval
4. 2-pass 리뷰 (메타데이터 redaction → rubric-only verdict → 필요 시만 explanation)
5. 툴 캐스케이드 방화벽 + 회복 분류체계 (retry → switch → abort) + chaos test
6. Cost/cache observability — quota-bleed 알람 + cache-TTL 회귀 감지
7. Production-name 가드 + 권한 시퀀스 분석 (개별 deny 가 아닌 워크플로우 단위)

**Secondary (스펙-드리븐 갭 보강)**:
- 스펙 strength rubric (SpecSyn-inspired) — 약한 스펙 차단
- adversarial 스펙 review (spec-kit `/clarify` 와 동등 + 그 위)
- bidirectional spec↔code sync 스테이지

**Tertiary (defer)**: persona library 양적 확장, 다중 CLI fan-out (≥3 IDE), 실시간 대시보드. 이들은 표면 다양성은 늘지만 reliability-ROI 가 낮음.

이 방향은 *informational* — `/hm:plan` 이 인터뷰로 최종 lock-in.

## 🛠️ Approaches Found

### A. Reliability Stack (PRIMARY)

| 필드 | 내용 |
|------|------|
| Approach | tool/middleware/memory 레이어에 7개 신규 capability 추가 |
| Assumption | gain 의 본질은 system-prompt 가 아닌 인프라 레이어 (2604.25850 ablation) |
| Evidence | SWE-PRM +10.6pp on SWE-bench Verified (2509.02360); AST-introspection 100% precision / 87.6% recall (2601.19106); MemMachine production validation (2604.04853); AgentProp-Bench tool-cascade 0.62 propagation rate (2604.16706); cache layout rules give 41-80% cost reduction (2601.06007); 커뮤니티 quota bleed top-issue (CC #41930, #46829, #46917); 42% hallucinated imports + 25% duplicate components (Malik Chohra Medium 2026-05); PocketOS prod DB 삭제 (Live Science 2026-04-24) |
| Trade-off | 구현 부피 큼 (7 sub-feature). 그러나 각 sub-feature 가 독립 — phase 분할 가능. 컨텍스트 lint 부담 약간 증가 |
| Compatibility | harness-maker 기존 atomic-stage 구조 + skill 시스템과 직접 정합. trajectory-monitor 는 skill 로 추가. 메모리는 `.claude/memory/episodic/` 추가. 가드는 hooks + security-scanner skill 확장 |
| Risk | medium. 일부 claim (2-pass 리뷰가 single-pass 보다 우수)이 counter-intuitive — 작은 ablation 권장 |

### B. Spec-Driven 갭 보강 (SECONDARY)

| 필드 | 내용 |
|------|------|
| Approach | spec-kit/BMAD 가 점유한 영역에서 **두 가지** 만 가져와 우리화 — spec strength rubric + adversarial clarify lens. **constitution gate** 와 **multi-stage SDLC 페르소나(BMAD)**는 우리 방향과 어긋남 (LLM-first + atomic stage 와 충돌) |
| Assumption | 우리 사용자(개인 개발자, dev_mode=task-driven default)는 BMAD-스타일 21-role 무거움 보다 가벼운 spec-quality gate 가 더 유용 |
| Evidence | spec-kit 71k stars (가장 빠른 성장), `/speckit.constitution` 패턴 보편화; arxiv 2602.00180 (50% LLM 코드 에러 감소); SpecSyn (2604.21570) 스펙 강도 평가 frame |
| Trade-off | 우리 `/hm:spec` 무거워짐 — 약한 스펙은 인터뷰 재진입. dev_mode=spec-driven 에서 가장 유용, task-driven 에서는 opt-in |
| Compatibility | 기존 spec stage 확장. spec-quality.score 가 ai-readiness rubric 과 같은 LLM-judge 패턴 재사용 |
| Risk | low |

### C. Persona Library 양적 확장 (defer)

| 필드 | 내용 |
|------|------|
| Approach | wshobson 83개 / claude-flow 54개 / BMAD 21개 / SuperClaude 9개 — 우리 5 reviewer + 4 worker = 너무 적은가? |
| Evidence | 양적 우위는 분명하나 quality dilution 위험 (community: "MCP 6개 넘으면 mis-pick 증가" — nimbalyst.com). agent-quality-rubric 이 이미 우리 측 quality gate |
| Trade-off | 양 vs 질. dev_mode=task-driven 에서 추가 페르소나가 reviewer 와 중복될 위험 |
| Compatibility | agent-quality-rubric 통과만 시키면 추가 가능 — 그러나 사용자 도메인별이라 우리가 아닌 user 가 author (cf. domain-content-ownership feedback memory) |
| Risk | medium — bloat. 권장: 사용자 add_domain 으로 위임, 우리 코어는 늘리지 않음 |

### D. Multi-CLI fan-out (defer)

| 필드 | 내용 |
|------|------|
| Approach | bridle 는 7 CLI 지원. agent-os/spec-kit 은 3. 우리는 2 (Claude Code + Cursor) |
| Evidence | 2026-03-31 Claude Code 소스 leak 으로 internals 공개. OpenCode/Codex/Amp 호환은 *기술적으로* 가능 |
| Trade-off | 매트릭스 폭발 — 각 IDE 의 hook schema / agent 포맷 / slash 명령 위치 다름. 0.6.2 P3 의 dual-render 가 이미 schema divergence 비용 입증. 추가 IDE 마다 manual 검증 + 회귀 테스트 누적 |
| Compatibility | low. 0.6.x 의 single-source 원칙이 깨짐. 사용자 사용률 (개인 개발자 — Claude Code + Cursor 가 지배적) 대비 ROI 낮음 |
| Risk | high (유지보수 부담) |

## ⚠️ Pitfalls

1. **"More reasoning = better" 가정의 함정.** arxiv 2603.00539 (Are LLMs Reliable Code Reviewers, Feb 2026) — 정교한 explanation+fix 프롬프트가 정확한 코드를 *결함으로 오판*하는 over-correction 을 *악화*. 우리 cross-check consensus 는 정확히 이 패턴. (실증 ablation 권장 후 도입.)

2. **Bug-free framing → 보안 리뷰 정확도 16-93pp 저하** (arxiv 2603.18740). PR 제목/설명을 reviewer 가 보면 confirmation bias. metadata-redaction 단계 추가 필요.

3. **"Follow TDD" 일반 프롬프트가 회귀를 *늘림*** (arxiv 2603.17973). 6.08% → 9.94%. 대신 code↔test dependency map 으로 "이 파일 수정 시 영향 받는 테스트는 X" 같은 구체적 hint 가 1.82% 까지 감소. 우리가 prompt 에 "TDD 따르라" 박지 말 것.

4. **1M context 광고 ≠ 1M 사용 가능.** Claude Opus 4.6 self-report 가 40% 부터 degradation 인정 (CC #34685). MRCR 76% accuracy at 1M. 우리 컨텍스트 가드를 advertised window 의 40% 로 hard-cap 권장.

5. **Cache 디자인 실수가 비용을 *늘림*** (arxiv 2601.06007). 동적 placeholder 가 정적 reference 앞에 오면 cache miss 폭발. CC #46829/#46917 의 회귀가 이 클래스. 우리 prompt 템플릿에 cache-layout 린트 필요.

6. **자기-수정 루프가 logical 에러는 못 고침** (arxiv 2604.10508). syntax/name 에러는 80%+ 수정 가능, logical assertion 은 ~45%. 우리 autoloop 는 제한 없이 반복 — 에러 클래스별 cap 필요.

7. **Specialist reviewer 의 cross-check 함정.** 우리 자체 회귀 (2026-05-08 session note `decision:review-cross-check-with-disjoint-specialists`) — 비-overlap 전문 reviewer 면 모든 finding 이 single-source 가 되어 cross-check 규칙 하에 grade 자동 A. consensus rule 을 reviewer-scope-aware 로 개선 필요.

8. **"Plugin update" 함정.** CC `/plugin update` 가 fast-forward 안 함 (#29071, #31462). 우리 4-파일 버전 sync 는 부분 해결이지만, 사용자 측 update flow 가 broken — 우리 `/hm:refresh` 가 우회 경로로 작동하는 게 다행이지만 업스트림 의존.

9. **Worktree 가 항상 정답은 아님.** Trigger.dev 는 GitButler 로 이동 — DB / 외부 서비스 격리가 worktree 만으로 안 됨. 우리는 코드-only worktree 인정 + 외부 자원은 사용자 책임 명시 필요.

10. **MCP 6개 천장.** community consensus — bloated tool list 가 mis-pick 증가. 우리는 MCP budget 경고 미구현.

11. **vendor 발표 신뢰성.** "Claude Mythos 93.9% SWE-bench" 같은 vendor-only 수치 검증 안 됨 (arxiv 2506.17208 — 리더보드 제출자 분석). 우리 ai-readiness rubric 의 외부 비교 baseline 사용 시 동료 검증된 수치만.

## ❓ Open Questions

`/hm:plan harness-gap-cot-2026-05` 의 인터뷰가 lock-in 해야 할 것:

1. **스코프 선택**: 7개 Primary feature 중 0.7.0 에 *몇 개* 들어가야 하나? 
   - (A) 전부 단일 릴리스 (12-16 phase)
   - (B) Top-3 만 (4-6 phase) — drift score, hallucination gate, episodic memory
   - (C) phase별 배포 — 0.7.0 = 1-2개 / 0.8.0 = 다음 / ...
2. **2-pass 리뷰 도입 전 ablation**: counter-intuitive claim — 우리 자체 mini-bench (5개 sample diff) 로 single-pass vs two-pass + redaction 비교 후 도입 여부 결정 → ablation 자체가 phase 0?
3. **에피소딕 메모리 schema**: `.claude/memory/episodic/` vs 기존 `.claude/memory/{wiki,failures,session}.md` 와의 관계. 신규 directory 인가, session/ 의 확장인가?
4. **트래젝토리 드리프트 비교 baseline**: spec embedding vs original prompt vs harness.yaml `summary` 필드. 어디서 truth 를 잡나?
5. **OpenTelemetry observability** 도입 여부: AgentTrace (2602.10133) 의 3-surface schema — 외부 의존 (otelpy) 추가가 받을 만한가, 아니면 자체 jsonl + OTel-호환 export 만?
6. **Spec strength rubric** 의 강제력: dev_mode=spec-driven 에서만 강제 vs task-driven 에서도 권고? 약한 스펙 차단이 user friction 으로 갈 위험.
7. **Multi-provider model routing (claude-flow / task-master 패턴)** — 명시 거부인가 (Anthropic-only by design — CLAUDE.md), Phase X 에서 검토인가? Open-weight model 로 PRM-monitor 돌리는 use-case 부상.
8. **Bench harness 자체** (`/hm:bench` for SWE-bench Lite slice): 0.7.0 에 포함? user 환경에서 bench 돌리는 건 cost-heavy.
9. **Plugin Marketplace 등록 시점**: 0.6.x 까지는 `~/.claude/plugins/cache/` 로컬 install. spec-kit (71k stars) / claude-flow (31.8k) 와 경쟁하려면 marketplace 진입 필요한지 — public repo 공개 일정과 묶임.
10. **Persona library 위임 정책 명문화** — "도메인 페르소나는 user author" 메모리는 있으나, 우리가 "starter set" 5-10개를 ship 할지 (BMAD 21 에 비해 과소) lock-in.

## 📚 Sources

### Harness landscape (Survey agent)
- [github/spec-kit](https://github.com/github/spec-kit) — 71k stars, fastest-growing SDD toolkit
- [GitHub blog SDD](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- [DeepWiki speckit.constitution](https://deepwiki.com/github/spec-kit/5.1-speckit.constitution)
- [buildermethods/agent-os v3](https://github.com/buildermethods/agent-os) — standards-injection
- [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) — 21-role SDLC personas
- [SuperClaude_Framework](https://github.com/SuperClaude-Org/SuperClaude_Framework)
- [ruvnet/ruflo (claude-flow)](https://github.com/ruvnet/ruflo) — 31.8k stars
- [Pimzino/claude-code-spec-workflow](https://github.com/Pimzino/claude-code-spec-workflow)
- [eyaltoledano/claude-task-master](https://github.com/eyaltoledano/claude-task-master)
- [wshobson/agents](https://github.com/wshobson/agents) — 83 specialists
- [neiii/bridle](https://github.com/neiii/bridle) — multi-CLI harness manager

### Recent papers (Arxiv agent)
- [SWE-PRM 2509.02360](https://arxiv.org/abs/2509.02360) — +10.6pp SWE-bench Verified
- [How Many Tries 2604.10508](https://arxiv.org/abs/2604.10508) — iter cap by error class
- [Reliable Code Reviewers 2603.00539](https://arxiv.org/abs/2603.00539) — over-correction
- [Confirmation Bias 2603.18740](https://arxiv.org/html/2603.18740v1) — metadata redaction
- [AgentProp-Bench 2604.16706](https://arxiv.org/html/2604.16706) — tool cascades
- [PALADIN 2509.25238](https://arxiv.org/pdf/2509.25238) — recovery taxonomy
- [ReliabilityBench 2601.06112](https://arxiv.org/html/2601.06112v1) — chaos for agents
- [MemMachine 2604.04853](https://arxiv.org/html/2604.04853v1) — episodic+semantic+profile
- [Codified Context 2602.20478](https://arxiv.org/html/2602.20478v1)
- [SpecSyn 2604.21570](https://arxiv.org/html/2604.21570v1) — spec strength
- [TDAD 2603.17973](https://arxiv.org/abs/2603.17973) — code↔test dep map
- [Hallucination Detection 2601.19106](https://arxiv.org/abs/2601.19106) — AST+introspection
- [Don't Break the Cache 2601.06007](https://arxiv.org/html/2601.06007)
- [AgentTrace 2602.10133](https://arxiv.org/abs/2602.10133) — 3-surface OTel
- [Agentic Harness Engineering 2604.25850](https://arxiv.org/abs/2604.25850) — observability-driven evolution
- [Faithfulness Loss 2603.17104](https://arxiv.org/html/2603.17104v1)

### Community pain (Pain agent)
- [CC #42796 — Feb regression](https://github.com/anthropics/claude-code/issues/42796)
- [CC #41930 — quota drain](https://github.com/anthropics/claude-code/issues/41930)
- [CC #46829 — cache TTL regression](https://github.com/anthropics/claude-code/issues/46829)
- [CC #46917 — cache_creation inflation](https://github.com/anthropics/claude-code/issues/46917)
- [CC #34685 — 1M Opus 4.6 degradation](https://github.com/anthropics/claude-code/issues/34685)
- [CC #45893 — production outage](https://github.com/anthropics/claude-code/issues/45893)
- [CC #53262 — HERMES.md billing](https://github.com/anthropics/claude-code/issues/53262)
- [Simon Willison — pricing](https://simonwillison.net/2026/Apr/22/claude-code-confusion/)
- [Geoffrey Huntley — Ralph](https://devinterrupted.substack.com/p/inventing-the-ralph-wiggum-loop-creator)
- [Malik Chohra — 42% hallucinations](https://medium.com/@malikchohra/i-built-a-memory-os-after-claude-code-hallucinated-42-of-my-code-1896334b9cfc)
- [DEV — SDD frameworks 2026](https://dev.to/willtorber/spec-kit-vs-bmad-vs-openspec-choosing-an-sdd-framework-in-2026-d3j)
- [METR Time Horizon 1.1](https://metr.org/blog/2026-1-29-time-horizon-1-1/)
- [Anthropic multi-agent code review](https://thenewstack.io/anthropic-launches-a-multi-agent-code-review-tool-for-claude-code/)

## 🔗 Related Internal Docs

- [[REVIEW-agents-skills-hooks-uplift-2026-05-08]] — 0.6.2 P5 reviewer/skill/hook 개정 (M1-M9 manual fix)
- [[REVIEW-cursor-compat-uplift-2026-05-08]] — kairos forensic 기반 dual-render 의도 입증
- [[plans/PLAN-cursor-compat-uplift]] — 0.6.2 cursor 호환 phase 0-7
- 메모리 [[project_review_grade_gate]] — review grade-A gate + auto-fix loop (현재 cross-check 함정 §Pitfalls #7 와 직접 충돌, 본 research 의 Reliability Stack 도입 후 consensus rule 재설계 필요)
- 메모리 [[project_targets_axis]] — claude-code + cursor 만 — Multi-CLI fan-out (Approach D) defer 결정의 근거
- 메모리 [[feedback_domain_content_ownership]] — 도메인 콘텐츠는 user author — Persona Library 양적 확장 (Approach C) defer 의 근거
- 2026-05-08 session [[decision:review-cross-check-with-disjoint-specialists]] — 본 research §Pitfalls #7 의 같은 사건
- 2026-05-08 session [[decision:cursor-compat-dual-render-kept]] — schema divergence 비용 실측 사례, Multi-CLI fan-out 회피 근거
