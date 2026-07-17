---
type: research
task_slug: harness-trends-2026-05
status: complete
created: 2026-05-11
tags: [harness-maker, research, agent-harness, agent-evaluation, self-evolving-agents, arxiv]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://arxiv.org/abs/2603.03329
  - https://arxiv.org/abs/2603.03823
  - https://arxiv.org/abs/2604.20801
  - https://arxiv.org/abs/2604.08988
  - https://arxiv.org/abs/2604.18240
  - https://arxiv.org/abs/2601.21557
  - https://arxiv.org/abs/2603.09619
  - https://arxiv.org/abs/2601.12560
  - https://arxiv.org/abs/2512.03262
  - https://arxiv.org/abs/2509.16941
  - https://arxiv.org/abs/2504.01848
  - https://github.blog/ai-and-ml/generative-ai/multi-agent-workflows-often-fail-heres-how-to-engineer-ones-that-dont/
related_docs:
  - "[[RESEARCH-harness-gap-cot-2026-05]]"
  - "[[RESEARCH-loop-longevity-strategies]]"
  - "[[RESEARCH-ouroboros-comparison-2026-05]]"
  - "[[PLAN-plugin-vs-generator-2026-05]]"
summary: "Top-3: harness synthesis, CI-style longitudinal eval, agentic judge/typed verification"
---

# 🎯 Recommended Direction

2026년 5월 기준 harness 쪽의 핵심 이동은 **prompt/agent 추가**가 아니라 **harness 자체를 합성하고, 장기 CI 흐름으로 평가하고, 검증자를 agent화하되 typed boundary로 강제하는 방향**이다.

harness-maker에 가장 큰 임팩트가 예상되는 3가지는 다음 순서다.

1. **Harness Synthesis / Meta-Harness Evolution**: AutoHarness와 AgentFlow 계열처럼 역할, prompt, tool, handoff, retry 정책을 실험 대상으로 올리고, 실패 신호로 harness를 수정한다. 현재 harness-maker의 anti-rot, review, autoloop를 "사람이 설계한 고정 절차"에서 "held-out eval로 개선되는 절차"로 확장할 수 있다.
2. **Longitudinal CI Evaluation**: SWE-CI처럼 단발 pass/fail이 아니라 여러 commit/반복/미래 변경에서 correctness가 유지되는지를 본다. harness-maker의 `/hm:loop`, worktree isolation, wrapup memory와 직접 맞물린다.
3. **Agentic Verification with Typed Boundaries**: AJ-Bench, GitHub multi-agent guidance, Agentic AI taxonomy가 같은 방향을 가리킨다. LLM-as-judge보다 환경과 tool을 직접 확인하는 judge agent, 그리고 schema/action/MCP boundary 검증이 필요하다.

이 권고는 `/hm:plan`에서 lock-in할 후보 방향이다. 특히 1번은 성능 잠재력이 가장 크지만 Goodharting과 verifier tampering 리스크가 있어, 2번과 3번의 검증 레이어 없이 단독 도입하면 위험하다.

# 🛠️ Approaches Found

## 10개 후보 트렌드 풀

| # | 트렌드 | 근거 | harness-maker 적용 가능성 | 선별 |
|---|--------|------|---------------------------|------|
| 1 | 자동 harness 합성 | AutoHarness는 Gemini-2.5-Flash가 TextArena 145개 게임에서 illegal move를 모두 방지하는 code harness를 합성했다고 보고 | stage/skill/hook/reviewer 설정을 eval 기반으로 제안하는 `/hm:evolve` | Top 3 |
| 2 | multi-agent harness search | AgentFlow는 역할, prompt, tool, topology, coordination protocol까지 typed graph DSL로 탐색 | reviewer routing, subagent topology, retry 정책을 search space로 명시 | Top 3 후보에 포함, 1번과 병합 |
| 3 | CI 기반 장기 유지보수 eval | SWE-CI는 평균 233일, 71 commit 이력을 가진 100개 repo task에서 장기 maintainability를 평가 | loop-context + worktree + future-test replay suite | Top 3 |
| 4 | self-evolving agent benchmark | SEA-Eval은 episodic task 성공률보다 cross-task evolutionary gain/stability를 평가 | memory/wiki/failures가 실제로 다음 task 성공률을 올리는지 측정 | 후보 |
| 5 | Agent-as-a-Judge / AJ-Bench | AJ-Bench는 judge agent가 환경/tool을 직접 사용해 evidence를 수집하고 state/process를 검증 | verify/review를 "대화 판단"에서 "증거 수집 판단"으로 전환 | Top 3 |
| 6 | typed schema/action boundary | GitHub는 multi-agent failure를 distributed-system 문제로 보고 schema/action/MCP boundary를 강조 | agent handoff JSON schema, invalid payload retry/escalate | Top 3에 포함, 5번과 병합 |
| 7 | context engineering as discipline | Context Engineering 논문은 relevance/sufficiency/isolation/economy/provenance를 핵심 기준으로 제시 | context-linter를 token 길이에서 provenance/economy 점수로 확장 | 후보 |
| 8 | meta context engineering | MCE는 skill/context artifact를 co-evolve해 평균 16.9% 상대 개선을 보고 | skill templates와 memory retrieval 정책을 자동 ablation | 후보 |
| 9 | security-first coding-agent eval | SUSVIBES는 기능 정답이어도 secure rate가 매우 낮음을 보고 | security-scanner를 optional이 아니라 wrapup hard gate로 강화 | 후보 |
| 10 | contamination-resistant long-horizon benchmark | SWE-Bench Pro/PaperBench는 held-out/commercial/long-horizon/task-rubric 평가 흐름을 강조 | 자체 benchmark set의 frozen/held-out split, rubric versioning | 후보 |

## Top 3 상세

| Field | Content |
|-------|---------|
| Approach | **A. Harness Synthesis / Meta-Harness Evolution** |
| Assumption | harness-maker의 큰 성능 차이는 모델 교체보다 stage graph, prompt, tool permission, reviewer topology, retry/rollback policy에서 나온다. |
| Evidence | AutoHarness는 code harness 합성만으로 smaller model이 larger model을 이기는 사례를 보고했다. AgentFlow는 model 고정 상태에서 harness 변경만으로 public benchmark success rate가 수배 변할 수 있다고 보고한다. MCE도 skill/context co-evolution이 평균 16.9% 상대 개선을 보였다고 보고한다. |
| Trade-off | eval harness와 held-out set 없이는 Goodharting이 쉽다. 생성된 harness가 verifier나 benchmark를 과최적화할 수 있다. |
| Compatibility | 높음. 이미 `.agents/skills`, `harness.yaml`, reviewer routing, memory tiers, anti-rot crawler가 있어 search 대상이 명확하다. |
| Risk | high. 반드시 frozen baseline, held-out tasks, verifier tamper guard와 함께 설계해야 한다. |

| Field | Content |
|-------|---------|
| Approach | **B. Longitudinal CI Evaluation** |
| Assumption | 실제 agent harness 품질은 한 번의 issue 해결보다 이후 변경에서 regression을 덜 만들고 유지보수 비용을 낮추는 능력으로 드러난다. |
| Evidence | SWE-CI는 static functional correctness에서 dynamic long-term maintainability로 평가 패러다임을 이동시킨다. SWE-Bench Pro도 hours-to-days급 multi-file task와 held-out/commercial split을 강조한다. PaperBench는 hierarchical rubric으로 긴 연구 재현 task를 세분 평가한다. |
| Trade-off | 테스트 비용이 커진다. repo history replay, future test replay, benchmark fixture 관리가 필요하다. |
| Compatibility | 매우 높음. harness-maker는 이미 worktree isolation, loop-context YAML, wrapup memory, review grade를 갖고 있다. CI replay layer를 붙이기 좋다. |
| Risk | medium. 작은 repo에서는 benefit이 낮고, fixture 유지가 부담이다. |

| Field | Content |
|-------|---------|
| Approach | **C. Agentic Verification with Typed Boundaries** |
| Assumption | multi-agent failure는 "더 똑똑한 agent"보다 bad handoff, loose action, unverified state, late validation에서 많이 나온다. |
| Evidence | GitHub는 multi-agent workflow를 chat이 아니라 distributed system처럼 다루라고 권고하며 typed schemas/action schemas/MCP boundary를 강조한다. AJ-Bench는 Agent-as-a-Judge가 environment/tool 기반 evidence를 수집해 LLM-as-judge보다 나은 경향을 보인다고 보고한다. Agentic AI taxonomy도 perception/planning/action/tool/collaboration layer로 평가를 분리한다. |
| Trade-off | schema 작성 비용과 migration 부담이 있다. 너무 세밀하면 agent flexibility가 줄고, 너무 느슨하면 효과가 없다. |
| Compatibility | 높음. review consensus, conditional-router, security-scanner, verify-before-completion의 입력/출력을 schema화하면 단계적으로 도입 가능하다. |
| Risk | medium. schema가 실제 workflow를 충분히 표현하지 못하면 false fail이 늘 수 있다. |

# ⚠️ Pitfalls

1. **Self-improvement without held-out eval**: AutoHarness/MCE류를 그대로 따라가면 내부 점수만 올리는 harness가 생길 수 있다. frozen baseline, held-out tasks, rubric versioning이 선행돼야 한다.
2. **Verifier tampering**: self-evolving loop가 metric runner, judge prompt, fixture를 바꿔 점수를 올리는 경로를 막아야 한다. eval runner는 read-only, 별도 process, hash-pinned fixture가 필요하다.
3. **단발 성공률 과신**: SWE-CI가 지적한 것처럼 단일 patch pass/fail은 장기 유지보수를 설명하지 못한다. `/hm:wrapup` success가 future commit stability를 의미하지 않는다.
4. **LLM-as-judge 과신**: AJ-Bench는 단순 judge prompt보다 environment-aware judge가 필요하다고 본다. review agent가 실제 파일, test, state를 확인하지 않으면 그럴듯한 판정만 남는다.
5. **Multi-agent handoff를 자연어로 방치**: GitHub가 강조하듯 schema/action boundary가 없으면 field drift, ordering assumption, stale state가 downstream으로 전파된다.
6. **보안은 기능 테스트로 대체되지 않음**: SUSVIBES는 기능적으로 맞는 agent output도 secure rate가 낮을 수 있음을 보여준다. security gate는 별도 axis여야 한다.
7. **Context bloat를 성능 개선으로 착각**: context engineering 연구 흐름은 많은 context보다 relevance, isolation, economy, provenance를 강조한다. 현재 context-linter의 line-count 중심 규칙은 충분하지 않다.

# ❓ Open Questions

1. **Top 3 중 첫 구현 순서**: `/hm:evolve`형 meta-harness부터 갈지, `/hm:ci-eval`형 long-term benchmark부터 갈지 결정 필요. 안전성 관점에서는 CI eval이 먼저다.
2. **Held-out benchmark source**: 내부 `work-docs`/기존 failures에서 만든 project-native fixture를 쓸지, SWE-Bench Lite류 외부 fixture를 일부 가져올지 선택해야 한다.
3. **Schema enforcement 범위**: review finding, plan validation, worker output, wrapup report 중 어디부터 typed schema를 강제할지 결정 필요.
4. **Verifier isolation**: judge agent와 metric runner를 같은 session에서 돌릴지, 별도 read-only process/worktree에서 돌릴지 선택해야 한다.
5. **Security gate 강제력**: 현재 security-scanner를 wrapup hard gate로 올릴지, high-severity만 block할지 lock-in 필요.
6. **Context quality metric**: context-linter를 line threshold에서 relevance/sufficiency/isolation/economy/provenance rubric으로 확장할지 검토 필요.

# 📚 Sources

- [AutoHarness: improving LLM agents by automatically synthesizing a code harness](https://arxiv.org/abs/2603.03329) — code harness 자동 합성, illegal action 방지, smaller model이 larger model을 앞서는 사례.
- [SWE-CI: Evaluating Agent Capabilities in Maintaining Codebases via Continuous Integration](https://arxiv.org/abs/2603.03823) — CI loop 기반 장기 maintainability 평가.
- [Synthesizing Multi-Agent Harnesses for Vulnerability Discovery](https://arxiv.org/abs/2604.20801) — typed graph DSL로 role/prompt/tool/topology/protocol search.
- [SEA-Eval: A Benchmark for Evaluating Self-Evolving Agents Beyond Episodic Assessment](https://arxiv.org/abs/2604.08988) — self-evolving agent의 cross-task gain/stability 평가.
- [AJ-Bench: Benchmarking Agent-as-a-Judge for Environment-Aware Evaluation](https://arxiv.org/abs/2604.18240) — tool/environment 기반 judge agent benchmark.
- [Meta Context Engineering via Agentic Skill Evolution](https://arxiv.org/abs/2601.21557) — skill/context artifact co-evolution.
- [Context Engineering: From Prompts to Corporate Multi-Agent Architecture](https://arxiv.org/abs/2603.09619) — context quality criteria: relevance, sufficiency, isolation, economy, provenance.
- [Agentic Artificial Intelligence: Architectures, Taxonomies, and Evaluation](https://arxiv.org/abs/2601.12560) — perception/brain/planning/action/tool/collaboration taxonomy.
- [Is Vibe Coding Safe? Benchmarking Vulnerability of Agent-Generated Code in Real-World Tasks](https://arxiv.org/abs/2512.03262) — functionally correct output와 secure output의 괴리.
- [SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?](https://arxiv.org/abs/2509.16941) — long-horizon, held-out/commercial split, contamination-resistant 평가.
- [PaperBench: Evaluating AI's Ability to Replicate AI Research](https://arxiv.org/abs/2504.01848) — hierarchical rubric 기반 long task 평가.
- [GitHub Blog: Multi-agent workflows often fail](https://github.blog/ai-and-ml/generative-ai/multi-agent-workflows-often-fail-heres-how-to-engineer-ones-that-dont/) — typed schemas, action schemas, MCP boundary, distributed-system framing.

# 🔗 Related Internal Docs

- [[RESEARCH-harness-gap-cot-2026-05]] — 2026-05 harness gap과 reliability stack prior art.
- [[RESEARCH-loop-longevity-strategies]] — Stop hook, fresh context, independent verifier 관련 기존 조사.
- [[RESEARCH-ouroboros-comparison-2026-05]] — 3-stage evaluation, bounded auto, brownfield 비교.
- [[PLAN-plugin-vs-generator-2026-05]] — generator vs plugin 설계 제약.
