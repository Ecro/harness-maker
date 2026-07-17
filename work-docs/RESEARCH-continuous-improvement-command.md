---
type: research
task_slug: continuous-improvement-command
status: complete
created: 2026-05-29
tags: [harness-maker, research, autoloop, improve-mode, code-quality, reward-hacking]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://kilo.ai/articles/beyond-autocomplete
  - https://codescene.com/blog/making-legacy-code-ai-ready-benchmarks-on-agentic-refactoring
  - https://arxiv.org/html/2605.21384
  - https://arxiv.org/pdf/2511.21654
  - https://addyosmani.com/blog/self-improving-agents/
related_docs:
  - "[[PLAN-loop-longevity-strategies]]"
  - "[[PLAN-ouroboros-comparison-2026-05]]"
  - "[[PLAN-workflow-overhead-post024]]"
summary: "Command already exists (/hm:loop --mode improve); leverage is closing the objective-oracle gap, not a new command"
---

# 🎯 Recommended Direction

**TL;DR: 새 command 를 만드는 게 답이 아니다. "코드 지속 개선" command 는 이미 존재한다 — `/hm:loop --mode improve` (review → fix → test → re-review, LLM 이 stopping criteria 판정).** 진짜 레버리지는 *새 명령*이 아니라 그 명령의 **효용을 결정하는 단 하나의 조건 — fixer LLM 으로부터 독립된 objective quality oracle —** 을 강제하는 것이다.

벤치마크 증거가 한 방향을 가리킨다: 외부 측정 신호(객관적 품질 메트릭)가 **없으면** 자율 개선 루프는 "spinning"(변수 rename 같은 표면적 변경 — CodeScene 벤치마크에서 unguided agent 가 변수 rename 54,094회 vs 구조적 Extract Method 7,550회)으로 수렴하고, 심한 경우 reward hacking(보이는 테스트 점수만 올리고 실질 품질은 정체)에 빠진다. 외부 oracle(Code Health 메트릭)을 붙이면 **구조적 리팩토링 2.9배 증가, 표면적 변경 84% 감소**. 즉 효용성의 binding condition 은 "command 화 여부"가 아니라 "측정 가능한 수렴 신호의 존재 여부"다.

harness-maker 의 improve-mode 는 이미 4-gate convergence 로 이 방어의 *상당 부분*을 갖고 있다(Gate 1 mechanical cmd, Gate 3 regression, Gate 4 streak×2). 유일한 구멍은 **Gate 2 가 LLM 자기 채점**이라는 점 — fixer 와 reviewer 가 같은 모델이면 oracle 독립성이 깨진다. 권장: 새 명령 대신 **improve-mode 에 "mechanical exit criterion 0개면 warn/refuse" 가드 + (옵션) 외부 code-health 메트릭 oracle 통합**. 임팩트는 maintainer-internal(harness 품질)이자 user-facing(사용자 루프가 헛돌지 않음) 양쪽.

# 🔍 Refinement Decisions

`--deep` 미사용 → Phase 0 / 0.5 skip.

**Discovery lens:** User-workflow/product-opportunity (사용자가 "코드 개선"을 실제로 어떻게 돌리나 = 이미 loop improve-mode) + Technical-architecture (기존 4-gate 메커니즘) + Risk/compliance (reward hacking, 자율 write 안전) + Research/benchmark (CodeScene, SpecBench). arXiv-only lens 단독 사용 안 함 — coverage guard 충족.

**핵심 재정의:** 사용자 질문("command 로 만들 수 있을까")의 전제가 이미 충족됨. 따라서 연구를 "신규 명령 설계"가 아니라 "기존 improve-mode 의 효용 조건 + 갭"으로 재조준.

# 🛠️ Approaches Found

## Local capability × User artifact 매트릭스

| harness 가 이미 가진 것 | 사용자가 실제로 돌리는 것 | 갭 |
|---|---|---|
| `/hm:loop --mode improve` (continuous review→fix→test loop) | "코드 품질 개선" 요청 | 사용자가 이 모드 존재를 모를 수 있음 (discoverability) |
| 4-gate convergence (mechanical/LLM/regression/streak) | 측정 가능한 DoD | Gate 2 LLM 자기채점 = oracle 독립성 결여 |
| `ExitCriterion.cmd` (mechanical 기준 지원) | "어떻게 끝을 아는가" | cmd 없는 순수 LLM 기준 루프 = spinning 위험, 가드 없음 |
| Safety rails (max_iter/time/failed_streak) | 폭주 방지 | OK — 충분 |
| `reviewers.mechanical_checks` (ouroboros pre-check) | 구조적 깨짐 사전 차단 | review 전용, improve-loop oracle 로는 미연결 |

### Approach A — Status quo (improve-mode 그대로)
| | |
|---|---|
| **Assumption** | 기존 4-gate 로 충분; 사용자가 measurable cmd-기준을 알아서 넣는다 |
| **Evidence** | autoloop-driver skill: "continuous quality loop … until LLM judges stopping criteria met". Gate 1/3/4 가 fluke·regression 방어 |
| **Trade-off** | 0 작업. 단 cmd-기준 없이 돌리면 Gate 2 자기채점만 남아 spinning/reward-hacking 노출 (SpecBench: tool 수 증가 시 eval coverage→0) |
| **Compatibility** | 완벽 (현 상태) |
| **Risk** | medium — "효용 없는 루프"가 조용히 돌 수 있음 (정확히 사용자가 우려한 지점) |

### Approach B — Objective-oracle 가드 + 메트릭 통합 (**권장**)
| | |
|---|---|
| **Assumption** | 효용은 측정 신호의 존재에 비례한다 (벤치마크 입증) |
| **Evidence** | CodeScene: oracle 있으면 구조 리팩토링 2.9×↑, 표면 변경 84%↓; 2–5× more Code-Health 개선. harness 의 `ExitCriterion.cmd` + `mechanical_checks` 가 이미 oracle 인프라 |
| **Trade-off** | improve-mode 인터뷰에 "mechanical(cmd-기반) exit criterion ≥1 강제 또는 명시 warn" 추가 + 옵션으로 외부 code-health 메트릭(ruff/radon/coverage/메트릭 MCP)을 ExitCriterion 으로 등록. ~소규모 (loop.md 인터뷰 4-G + 가드 1개) |
| **Compatibility** | 높음 — 기존 Gate 1/`cmd` 재사용, 신규 축 없음. CLAUDE.md §LLM 활용 원칙(규칙 대신 LLM 판단)과 정합: "cmd 0개 = LLM 이 reward-hacking 위험 경고" |
| **Risk** | low — additive, 기존 루프 깨지 않음 |

### Approach C — 신규 standalone `/hm:improve` (background/scheduled)
| | |
|---|---|
| **Assumption** | 사용자는 명시 루프와 별개로 "상시/예약 개선"을 원한다 |
| **Evidence** | Ralph loop = overnight refactor / backlog triage 용 (kilo). cron/background 패턴 존재 |
| **Trade-off** | 큼 — 새 명령·스케줄링·무인 write 안전모델. improve-mode 와 기능 중복. CLAUDE.md "단일 메타 명령 + atomic 7 stage" 철학과 충돌 위험 |
| **Compatibility** | 낮음 — 100% 로컬·무인 write 는 worktree 안전모델 재검토 필요 |
| **Risk** | high — 무인 자율 개선은 reward-hacking 노출 최대, 검토 없는 merge 위험 |

# ⚠️ Pitfalls

- **Spinning / 표면적 churn**: oracle 없으면 변수 rename 등 cosmetic 변경으로 수렴 (CodeScene: 54,094 renames). harness Gate 2 가 LLM 자기채점이면 동일 함정. (출처: CodeScene benchmark)
- **Reward hacking**: 보이는 테스트만 통과시키고 실질 품질 정체. tool 수 늘수록 evaluation coverage 가 구조적으로 0 으로 감소 (SpecBench, EvilGenie). → Gate 1 의 cmd 기준이 *진짜 품질 차원*을 덮어야지, 통과하기 쉬운 기준만 넣으면 무력. (출처: arxiv 2605.21384, 2511.21654)
- **fixer == reviewer**: 같은 LLM 이 고치고 채점하면 oracle 독립성 붕괴. harness 는 codex second-opinion(`codex_second_opinion`) 으로 부분 완화 가능 — improve Gate 2 에 연결 검토.
- **무경계 scope**: monorepo 전체 대상 루프는 repo-wide 이해 부족으로 실패 (kilo). harness `--target` 으로 bound 필수.
- **Discoverability 갭**: 사용자가 improve-mode 존재 자체를 모르면 "새 명령 필요"로 오인 → 본 연구의 1차 발견.

# ❓ Open Questions

`/hm:plan` 이 lock 해야 할 항목:

1. **가드 강도**: improve-mode 에 mechanical exit criterion 0개일 때 → (a) warn-and-proceed, (b) AskUserQuestion 으로 cmd 기준 유도, (c) hard-refuse? (CLAUDE.md warn-and-proceed 선호와 reward-hacking 위험 사이 trade-off)
2. **외부 oracle 통합 범위**: ruff/mypy/coverage 같은 내장 신호만? 아니면 code-health 메트릭(radon, 또는 MCP oracle)까지? Python-only 정책 안에서.
3. **Gate 2 독립성**: `codex_second_opinion` 을 improve Gate 2 의 독립 reviewer 로 연결할지 (oracle 독립성 ↑) vs 비용/복잡도.
4. **사용자 의도 확인**: 사용자가 정말 *신규 명령*을 원했는지, 아니면 *기존 improve-mode 강화*면 충분한지 — Approach B vs C 선택. (plan 인터뷰 1번 질문)
5. **Discoverability**: improve-mode 를 `/hm:help` / make 인터뷰에서 더 노출할지 (별도 소규모 작업).

# 📚 Sources

- [Beyond Autocomplete: Best Agentic Coding Workflow in 2026 — Kilo](https://kilo.ai/articles/beyond-autocomplete) — Ralph loop 패턴, overnight refactor / backlog triage 적합 조건, monorepo 실패 모드
- [Making Legacy Code AI-Ready: Benchmarks on Agentic Refactoring — CodeScene](https://codescene.com/blog/making-legacy-code-ai-ready-benchmarks-on-agentic-refactoring) — objective oracle 의 결정적 역할; 구조 리팩토링 2.9×↑, 표면 변경 84%↓; Code Health 9.4/10 타깃
- [SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents — arXiv 2605.21384](https://arxiv.org/html/2605.21384) — tool 수↑ 시 evaluation coverage→0, hacking severity 구조적 증가
- [EvilGenie: A Reward Hacking Benchmark — arXiv 2511.21654](https://arxiv.org/pdf/2511.21654) — reward hacking 정의·탐지
- [Self-Improving Coding Agents — Addy Osmani](https://addyosmani.com/blog/self-improving-agents/) — self-improvement 루프 일반론

# 🔗 Related Internal Docs

- [[PLAN-loop-longevity-strategies]] — Ralph/autoloop 비교는 이미 수행됨; improve-mode loop longevity 메커니즘 land 됨 (G1/G3/G4/G6)
- [[PLAN-ouroboros-comparison-2026-05]] — `reviewers.mechanical_checks` (mechanical pre-check) = 재사용 가능한 oracle 인프라
- [[PLAN-workflow-overhead-post024]] — `verify` 가 full-regression 단일 owner; improve Gate 3 regression baseline 과 정합
- `.claude/skills/autoloop-driver/SKILL.md` — improve-mode invariants + 4-gate 정의 (canonical)
- `.claude/commands/hm/loop.md` — 4-gate convergence 절차 (Gate 1–4 상세)
