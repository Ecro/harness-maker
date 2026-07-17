---
type: research
task_slug: llm-code-review-2026
status: complete
created: 2026-05-11
tags: [harness-maker, research, code-review, multi-agent, llm-prompting, 2026-state-of-the-art]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://arxiv.org/html/2505.16339v1
  - https://arxiv.org/html/2404.18496v2
  - https://arxiv.org/html/2602.13377v1
  - https://arxiv.org/html/2510.09721v3
  - https://arxiv.org/html/2502.01853v2
  - https://conf.researchr.org/details/fse-2025/fse-2025-student-research-competition/5/AutoReview-An-LLM-based-Multi-Agent-System-for-Security-Issue-Oriented-Code-Review
  - https://cursor.com/blog/building-bugbot
  - https://cursor.com/bugbot
  - https://claude.com/blog/code-review
  - https://code.claude.com/docs/en/sub-agents
  - https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md
  - https://openai.com/index/introducing-upgrades-to-codex/
  - https://www.coderabbit.ai/blog/gpt-5-5-benchmark-results
  - https://www.greptile.com/benchmarks
  - https://jetxu-llm.github.io/LlamaPReview-site/
  - https://github.com/karpathy/nanochat
  - https://github.com/ai-boost/awesome-harness-engineering
  - https://arxiv.org/pdf/2305.06599
related_docs:
  - "[[RESEARCH-harness-gap-cot-2026-05]]"
  - "[[RESEARCH-deep-interview-llm-delegation]]"
  - "[[RESEARCH-ouroboros-comparison-2026-05]]"
  - "[[REVIEW-codex-loop-execute-gaps-2026-05-11]]"
summary: "harness-maker /hm:review is already SOTA in 2026 — three high-leverage deltas: verifier sub-role, repo-graph context, agentic depth-on-demand."
---

# RESEARCH — LLM 으로 코드 리뷰를 정말 제대로 하는 방법 (2026)

## 🎯 Recommended Direction

**harness-maker 의 현재 `/hm:review` 는 2026 시점 SOTA 와 동급 또는 그 이상**이다 (two-pass redaction +47pp, OBSERVE→INFER→CONCLUDE 추론 체인, surface+reasoning consensus, P0/P1-only grade gate, auto-fix loop, mechanical pre-checks). 추가로 채워야 할 진짜 갭은 단 3 가지:

1. **Verifier-as-separate-role** (Anthropic pattern, <1% incorrect findings) — Pass 1 bug-finder 와 Pass 2 contextual verdict 사이에 **별도 verifier 역할** 1 회. 현재 같은 reviewer 가 Pass 2 에서 자기 finding 을 재검증 → confirmation bias 위험. 비용 거의 무료, ROI 가장 높음.
2. **Repo-graph context** (Greptile 82% vs CodeRabbit 44% catch rate, +38pp) — changed-files 만이 아니라 **호출자/피호출자 그래프**를 reviewer 컨텍스트로 미리 inject. 단, false-positive 도 5.5x 증가 (Greptile 11 vs CodeRabbit 2) → 그래프 컨텍스트가 reviewer 를 더 "공격적" 으로 만들면 consensus filter 부담 가중.
3. **Agentic depth-on-demand** (Cursor pipeline→agentic transition: 0.4 → 0.7 bugs/run, 52% → 70% resolution) — 현재 reviewer 는 고정 sequence (read → walk runtime path → emit findings). 동적으로 더 깊이 파야 할 곳에 tool call 추가하도록 prompt 재설계.

근본 메타-원칙은 변하지 않았다: **consensus + verifier + 명시적 추론 체인 + severity ranking + auto-fix** 가 2026 의 winning combo. harness-maker 는 이미 다 한다. 보강은 marginal.

> 이건 *informational direction* — `plan` 단계에서 ADR 로 확정.

## 🛠️ Approaches Found

### Approach A — Verifier-as-separate-role 추가 (Anthropic Claude Code pattern)

| Field | Content |
|-------|---------|
| Approach | Bug-finder agents → **verifier agents** → severity ranker → output. Verifier 는 finder 와 다른 prompt, 다른 인스턴스. |
| Assumption | Confirmation bias 는 같은 agent 의 self-verify 로는 해결 안 됨. 별도 verifier 인스턴스가 finding 마다 "이게 정말 버그인가?" 만 묻는 reductive pass. |
| Evidence | Claude Code blog: "less than 1% of findings are marked incorrect" with parallel finder + separate verifier. Anthropic 내부 PR review 의 16% → 54% substantive comments. ([source](https://claude.com/blog/code-review)) |
| Trade-off | Token cost ~1.3x (verifier 가 finding 만 read, full diff 안 봄). Pass 2 contextual verdict 와 일부 중복 — **합칠지 추가할지** 결정 필요. |
| Compatibility | 현재 `two_pass_review.merge` CLI 가 이미 Pass1/Pass2 통합 — verifier 를 Pass 1.5 로 끼우거나, 별도 step `verify_findings` 로 추가. Reviewer permission boundary (read-only) 동일. |
| Risk | low |

### Approach B — Repo-graph context inject (Greptile / LlamaPReview pattern)

| Field | Content |
|-------|---------|
| Approach | 사전 indexing 으로 호출 그래프/심볼 그래프 구축 → reviewer 가 changed symbol 의 caller/callee 를 자동 read. "ripple effect" finding (unchanged code 가 깨질 가능성) 신설. |
| Assumption | Changed files 만 보면 변경이 다른 곳에 미치는 영향 못 봄. Greptile 데이터: "indexes entire repository, builds a code graph" → 82% catch rate vs CodeRabbit 44%. |
| Evidence | Greptile 2026 benchmarks (82% catch, 11 FP). CodeRabbit 2026 추가 기능 발표: "code graph analysis for understanding dependencies". LlamaPReview: "retrieves related code...finds related, unchanged code to surface ripple effects." ([source](https://www.greptile.com/benchmarks)) ([source](https://jetxu-llm.github.io/LlamaPReview-site/)) |
| Trade-off | 인덱스 빌드 비용 (1회 cold ~수십초~수분, incremental cheap). False-positive 5.5x 증가 위험 → consensus threshold 상향 또는 `--ripple-confidence` 필터 신설 필요. WSL2 NTFS 환경 인지 — 인덱스 캐시 경로 주의. |
| Compatibility | 현재 stage 는 `git diff` 만 input. Graph builder 를 별도 Phase 0.5 로 도입 (deterministic, mechanical pre-check 와 같은 위치). Reviewer 들에게 `related_symbols.json` 같은 형태로 전달. |
| Risk | medium (FP 증가, 그래프 빌드 성능, 캐시 무효화 복잡도) |

### Approach C — Agentic depth-on-demand (Cursor BugBot Fall 2025 transition)

| Field | Content |
|-------|---------|
| Approach | Reviewer 가 고정 "read → walk → emit" 대신 **자체 reasoning loop** 안에서 "여기 더 파야겠다 → Grep / Read / git log 호출" 동적 결정. Aggressive prompt: "investigate every suspicious pattern." |
| Assumption | Pipeline (fixed sequence) 은 깊이 부족, agentic loop 은 의심 지점에 컴퓨트 집중 → 같은 토큰으로 더 깊은 finding. Cursor 데이터: 0.4 → 0.7 bugs/run, 52% → 70% resolution rate. |
| Evidence | Cursor blog "Building a better Bugbot": "small changes in tool design or availability had an outsized impact on outcomes." Pipeline 의 8-pass majority voting → agentic loop 으로 대체. ([source](https://cursor.com/blog/building-bugbot)) |
| Trade-off | Token 비용 변동성 ↑ (보수적 prompt 보다 1.5-3x). Determinism 저하 (snapshot test 영향). Stage prompt 가 reviewer 의 자율도를 어디까지 허용할지 명시 필요. |
| Compatibility | 현재 reviewer agent 정의는 Read/Grep/Glob/git diff 만 allow — agentic loop 에 필요한 tool 권한은 이미 충분. Prompt 재설계 + per-reviewer token budget 명시가 핵심 변경점. |
| Risk | medium (cost variance, determinism, prompt drift) |

### 참고 — Approach 비교 매트릭스

| Dim | A (Verifier) | B (Repo-graph) | C (Agentic depth) |
|-----|---|---|---|
| Implementation effort | S (1-2일) | L (1-2주) | M (3-5일) |
| Token cost delta | +30% verifier pass | +20% related-code read | +50-200% variable |
| Determinism impact | none | low (cache-controlled) | high |
| Cited gain | <1% wrong findings (Anthropic) | +38pp catch rate (Greptile) | +75% bugs/run (Cursor) |
| FP risk | ↓ (de-noise) | ↑↑ (5.5x in Greptile data) | ↑ (aggressive prompt) |
| 현재 stage 와 정합 | ★★★ | ★★ | ★★ |

## ⚠️ Pitfalls

1. **단일 LLM judge 의 confirmation bias** — Same model self-verifying 자체 finding 은 false-positive 거의 못 거름. AutoReview FSE 2025 + Claude Code 둘 다 별도 verifier agent 사용한 이유. [source](https://conf.researchr.org/details/fse-2025/fse-2025-student-research-competition/5/AutoReview-An-LLM-based-Multi-Agent-System-for-Security-Issue-Oriented-Code-Review)
2. **Metadata anchoring** — PR title / commit message / author 가 reviewer 를 lock-in 시킴. harness-maker 는 이미 two-pass redaction 으로 해결 (Phase 0 ablation +47pp). 외부 도구 대부분 미해결.
3. **장황한 출력** — 2505.16339 발견: "low-priority or unclear findings" 가 신뢰 무너뜨림. 사용자 원하는 건 file:line 정확히 + 짧게 + 우선순위. harness-maker 의 P0/P1-only grade gate 가 이 통제 — 유지해야 함.
4. **속도** — 2505.16339 P9: "wouldn't use this if it took...minutes". CodeRabbit 의 2-4 분이 상한선. harness-maker 가 reviewer parallel 호출 유지하는 한 안전.
5. **Repo-graph cold cache** — Greptile 의 multi-hop 이 "takes longer per review". 인덱스 도입 시 incremental update 필수. NTFS/WSL2 환경에서 캐시 무효화 함정. [source](https://www.greptile.com/benchmarks)
6. **Tool over-restriction** — Anthropic subagent docs: read-only 자체는 좋지만 권한이 너무 좁으면 reviewer 가 context 못 끌어옴. 우리 `git diff:* / git log:* / git status:*` 허용은 적절, 그러나 agentic depth 도입 시 `Grep`/`Glob` 의 패턴 범위 점검 필요. [source](https://code.claude.com/docs/en/sub-agents)
7. **AI-가 쓴 코드를 AI 가 리뷰** — Karpathy nanochat 정책: "contributors must declare any parts that had substantial LLM contribution and that they have not written or that they do not fully understand." 우리 stage 가 사람-인-루프 강제 (`human_review_needed` flag) 하는 것과 같은 신호. 무자각 auto-fix 가 가장 위험. [source](https://github.com/karpathy/nanochat)
8. **벤치마크 시그널의 함정** — Greptile 자사 벤치마크는 자신에게 유리하게 설계됨. AIMultiple / techsy 309-PR 평가에서는 CodeRabbit completeness 1/5. Single-source 비교는 무의미 — 다중 reviewer + 도메인-적합 evaluation 만 의미. [source](https://techsy.io/blog/best-ai-code-review-tools)

## ❓ Open Questions

`/hm:plan` 단계에서 lock-in 해야 할 결정:

1. **Approach A (verifier sub-role) 채택 여부 + Pass2 와의 관계** — 별도 step 추가 vs Pass2 안에 통합. ROI 가장 높지만 reviewer agent 정의에 새 역할 추가 필요.
2. **Approach B (repo-graph) 의 sub-scope** — 도입한다면 전체 그래프 인덱싱인가 vs changed-symbol 의 1-hop caller/callee 만인가. 후자가 cost/risk 균형 좋음.
3. **Approach C (agentic depth) 의 가드레일** — per-reviewer token budget? max tool calls? 아니면 단순히 prompt 만 reword? Determinism 보존 vs depth 트레이드오프.
4. **현재 grade gate (A/B/C/D/F) 가 충분히 sharp 한가** — Claude Code 의 "less than 1% incorrect" 는 verifier 후 측정. 우리도 final-report 후 incorrect rate metric 을 telemetry 에 추가할지.
5. **Ripple-effect finding** 을 별도 severity tier 로 둘지 (P1+? P2?). 현재 P0/P1 만 grade 계산 — 도입 시 oversaturation 위험.
6. **LLM-generated code 표식 정책** — Karpathy 식 declare-LLM-contribution 룰을 harness-maker 자체 PR 에 적용할지. 자체-소비형 메타 정책.

## 📚 Sources

### 논문 (arxiv 2025-2026)
- ["A Survey of Code Review Benchmarks and Evaluation Practices in Pre-LLM and LLM Era"](https://arxiv.org/html/2602.13377v1) — 99 papers, 58 pre-LLM + 41 LLM, 2026
- ["A Comprehensive Survey on Benchmarks and Solutions in Software Engineering of LLM-Empowered Agentic System"](https://arxiv.org/html/2510.09721v3) — 150+ papers, prompt vs fine-tune vs agentic taxonomy
- ["AI-powered Code Review with LLMs: Early Results"](https://arxiv.org/html/2404.18496v2) — 4-agent system, GPT-4
- ["Rethinking Code Review Workflows with LLM Assistance: An Empirical Study"](https://arxiv.org/html/2505.16339v1) — 개발자 perception, proactive vs reactive, RAG 필요성
- ["AutoReview: An LLM-based Multi-Agent System for Security Issue-Oriented Code Review"](https://conf.researchr.org/details/fse-2025/fse-2025-student-research-competition/5/AutoReview-An-LLM-based-Multi-Agent-System-for-Security-Issue-Oriented-Code-Review) — Detector + Locator + Repairer, F1 +18.72%
- ["Security and Quality in LLM-Generated Code: A Multi-Language, Multi-Model Analysis"](https://arxiv.org/html/2502.01853v2) — multi-tool comparison, single tool 의존 위험
- ["Structured Chain-of-Thought Prompting for Code Generation"](https://arxiv.org/pdf/2305.06599) — SCoT (sequence/branch/loop) 추론 체계

### 실제 도구 (architecture 공개)
- [Cursor — Building a better Bugbot](https://cursor.com/blog/building-bugbot) — pipeline→agentic transition, validator model, majority voting
- [Cursor Bugbot landing page](https://cursor.com/bugbot) — 2M PR/month, "frontier + in-house models" combo
- [Anthropic Code Review plugin](https://claude.com/blog/code-review) — multi-agent dispatcher, parallel finders + verifier, <1% incorrect, 16% → 54% PRs with substantive comments
- [Claude Code subagent docs](https://code.claude.com/docs/en/sub-agents) — read-only reviewer 권한 모범, memory dir 패턴
- [anthropics/claude-code code-review command source](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md)
- [OpenAI Codex GPT-5.5 upgrades](https://openai.com/index/introducing-upgrades-to-codex/) — "high-signal code review" 자체 표어
- [CodeRabbit GPT-5.5 benchmark](https://www.coderabbit.ai/blog/gpt-5-5-benchmark-results) — model upgrade vs review precision
- [Greptile 2025-2026 benchmarks](https://www.greptile.com/benchmarks) — 82% catch (Greptile) vs 58% (Bugbot) vs 44% (CodeRabbit), 11 vs 2 FP
- [LlamaPReview](https://jetxu-llm.github.io/LlamaPReview-site/) — ripple effect 패턴, 4k+ repos

### 유명인 / harness 패턴
- [karpathy/nanochat](https://github.com/karpathy/nanochat) — LLM-contribution declare 정책 (PR 정책 차원)
- [ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) — read-only reviewer permission, tool annotation (readOnlyHint / destructiveHint), 5-layer permission evaluation

### 시장 평가
- [techsy.io 2026 AI code review ranking](https://techsy.io/blog/best-ai-code-review-tools) — 309 PRs 평가
- [ucstrategies.com CodeRabbit 2026 review](https://ucstrategies.com/news/coderabbit-review-2026-fast-ai-code-reviews-but-a-critical-gap-enterprises-cant-ignore/)

## 🔗 Related Internal Docs

- [[RESEARCH-harness-gap-cot-2026-05]] — OBSERVE/INFER/CONCLUDE 추론 체인 도입 배경
- [[RESEARCH-deep-interview-llm-delegation]] — LLM judge 패턴 일반화 (review 도 동형)
- [[RESEARCH-ouroboros-comparison-2026-05]] — 다른 harness 들과 review 정책 비교
- [[REVIEW-codex-loop-execute-gaps-2026-05-11]] — 가장 최근의 자체 review 실 사례
- `src/harness_maker/templates/stages/review.md.j2` — 현재 review stage 구현 (수정 대상)
- `.claude/memory/failures.md [fail:review] reviewer-subagent-model-unsupported` — reviewer 모델 가용성 fallback 미비 (2026-05-11 발견)
- `.claude/memory/failures.md [fail:review] abbreviated-diff-causes-reviewer-false-positives` — 컨텍스트 abbreviate 시 FP 발생 (Anti-pattern)
