---
type: research
task_slug: loop-longevity-strategies
status: complete
created: 2026-05-09
tags: [harness-maker, research, autoloop, loop-longevity, ralph-loop, context-management]
mtime_warn_days: 14
libs_fetched: []
sources:
  - https://github.com/snarktank/ralph
  - https://ghuntley.com/loop/
  - https://github.com/ghuntley/how-to-ralph-wiggum
  - https://github.com/alfredolopez80/multi-agent-ralph-loop
  - https://github.com/armgabrielyan/autoloop
  - https://github.com/yaoshengzhe/autoloop
  - https://github.com/disler/infinite-agentic-loop
  - https://github.com/karpathy/autoresearch
  - https://ralphloops.io/
  - https://medium.com/@fhinkel/overcome-context-limitations-with-ralph-c69d86b06b1d
  - https://code.claude.com/docs/en/hooks
  - https://claudefa.st/blog/tools/hooks/stop-hook-task-enforcement
  - https://platform.claude.com/docs/en/build-with-claude/compaction
  - https://codex.danielvaughan.com/2026/04/14/context-compaction-deep-dive-codex-cli-claude-code-opencode/
  - https://www.knightli.com/en/2026/04/27/ralph-autonomous-agent-loop-claude-code-amp/
  - https://beginnersinai.org/ralph-loop-explained/
related_docs:
  - "[[work-docs/PLAN-plugin-vs-generator-2026-05.md]]"
  - "[[docs/reference/autoloop-pattern.md]]"
  - "[[.claude/skills/autoloop-driver/SKILL.md]]"
  - "[[.claude/commands/hm/loop.md]]"
summary: "Stop hook + fresh-context-per-iter + raised caps = principal longevity levers; 5 gaps identified"
---

# 🎯 Recommended Direction

harness-maker의 `/hm:loop`는 이미 견고한 safety rail 구조를 갖추고 있으나, 외부 구현들이 2026년에 실증한 **세 가지 핵심 longevity 기법**을 미채택 상태다:

1. **Stop hook forced-continuation** — Claude Code 공식 `exit 2` 기법으로 중간 종료 차단.
2. **Fresh context per feature iteration** — driver가 누적 컨텍스트에서 실행되는 대신 per-iter sub-agent가 최소 컨텍스트만 수신.
3. **Independent verifier (no self-reporting bias)** — 대화 내역 없이 파일만 보는 검증 에이전트가 완료를 선언해야만 루프 종료.

세 가지 중 **2번(fresh context per iter)**은 harness-maker가 이미 `autoloop-coder` sub-agent를 통해 절반 구현했지만, driver 자체가 단일 긴 세션으로 실행되어 컨텍스트가 누적된다. 완전한 fresh context 패턴으로 전환하면 iter당 품질 일관성이 크게 향상된다.

---

## 🛠️ Approaches Found

### A. Ralph Loop (snarktank / ghuntley) — 원조 패턴

| Field | Content |
|-------|---------|
| Approach | Bash shell loop + prd.json progress + stop hook `exit 2` |
| Assumption | 각 iteration은 완전히 새로운 context window에서 시작 |
| Evidence | snarktank/ralph (400+ stars), ghuntley/how-to-ralph-wiggum, ralphloops.io 오픈 스펙 |
| Trade-off | context window를 매 iter마다 "malloc" (사양서 전체 재로드) → 토큰 비효율적이지만 로스 없음 |
| Compatibility | harness-maker의 loop-spec YAML과 구조적으로 유사 (prd.json ≈ loop-spec features 배열) |
| Risk | low |

**핵심 아이디어**: "fresh context every iteration = constant quality." iter 1과 iter 100의 품질이 동일하다. spec 입력은 고정, repo(세계)가 수렴한다. 컨텍스트 오염이 없으므로 루프를 얼마든지 길게 돌릴 수 있다.

**Stop hook 구현**:
```bash
# .claude/settings.json hooks
"Stop": [{
  "command": "python -m harness_maker.hooks.loop_gate",
  "timeout": 10
}]
# loop_gate: progress 파일 읽어 converged=False이면 {"decision":"block","reason":"..."} + exit 2
```
`stop_hook_active` 체크 없으면 무한 루프 → 반드시 가드 필요.

---

### B. multi-agent-ralph-loop (alfredolopez80) — 메모리 + 병렬 팀

| Field | Content |
|-------|---------|
| Approach | 4-layer MemPalace memory + parallel 6-agent team + 4-stage quality gate |
| Assumption | 818-token wake-up spec으로 context overhead 최소화; 학습 파이프라인이 루프 지속성 강화 |
| Evidence | 925+ tests, 22 active hooks, 10K 토큰 절감 (~29%) per session |
| Trade-off | 복잡성 높음. harness-maker 현재 아키텍처와 overlap 큼 |
| Compatibility | wiki.md/failures.md ↔ MemPalace layer 1 직접 매핑 가능 |
| Risk | medium (over-engineering risk) |

**longevity 기여점**: 매 iter마다 wiki.md/failures.md 업데이트 (wrapup 때만이 아님). 에러 패턴을 빠르게 학습해 `failed_streak`을 낮게 유지 → 루프가 더 오래 지속.

---

### C. autoloop (yaoshengzhe) + Karpathy autoresearch — 독립 검증자

| Field | Content |
|-------|---------|
| Approach | 독립 verification agent (대화 내역 없음) + 파일+테스트만 검증 |
| Assumption | self-reporting bias 제거가 false convergence(조기 종료)의 주 원인 |
| Evidence | autoresearch: 700 experiments/2 days; autoloop: independent verifier eliminates bias |
| Trade-off | 추가 agent spawn → 비용 증가; 하지만 false convergence로 인한 재실행 비용 > 검증 비용 |
| Compatibility | harness-maker의 verify-before-completion skill이 유사하지만 conversation context에서 실행 |
| Risk | low |

**Karpathy 핵심 통찰**: bounded 실험 (5분 고정) + 명확한 metric = 수렴 보장. "얼마나 오래"보다 "무엇을 측정하는가"가 longevity를 결정한다.

---

### D. Claude Code Stop Hook 공식 메커니즘

| Field | Content |
|-------|---------|
| Approach | Stop hook에서 progress 체크 → `exit 2` + JSON `{"decision":"block","reason":"..."}` |
| Assumption | Claude Code의 공식 hook lifecycle을 loop continuation에 직접 활용 |
| Evidence | claudefa.st/blog/tools/hooks/stop-hook-task-enforcement, Claude Code 공식 docs |
| Trade-off | hook이 빠르게 실행되어야 함 (timeout 30s). 무한 루프 방지 위해 `stop_hook_active` 필드 체크 필수 |
| Compatibility | harness-maker는 이미 hooks.json 렌더 인프라 보유. 신규 hook 추가는 간단 |
| Risk | low (단, `stop_hook_active` 미체크 시 infinite loop 버그) |

---

## harness-maker 현황 분석: gap 식별

### 현재 `/hm:loop`의 longevity 한계 (2026-05 기준)

| # | Gap | 현재 값 | 이상적 값 | 영향 |
|---|-----|---------|---------|------|
| G1 | Stop hook 미사용 | 없음 | `exit 2` 가드 | 세션 자연 종료 시 루프 끊김 |
| G2 | Driver context 누적 | 단일 세션 실행 | per-iter sub-agent | iter > 15에서 품질 저하 |
| G3 | failed_streak cap이 tight | 3 | 5 (configurable) | 어려운 피처에서 조기 중단 |
| G4 | max_iter 기본값 | 30 | 50+ | 큰 spec 실행 불가 |
| G5 | verify-before-completion이 대화 내 실행 | conversation context | isolated sub-agent | false convergence 가능 |
| G6 | 컨텍스트 compaction 전략 없음 | global 85% | 60% + 중요 context pinning | 장시간 루프에서 spec 손실 |
| G7 | 반복 학습 시점 | 루프 종료 시 한 번 | per-iter append | failed_streak 패턴 누적 안 됨 |

### 현재 강점 (유지해야 할 것)

- **Coverage-driven adaptive interview**: Ralph 구현들 대부분이 없는 기능. zero ambiguity 보장이 루프 수렴의 근본.
- **5-stage pipeline**: research → plan-validate → execute → review → wrapup 구조는 어떤 Ralph 구현보다 체계적.
- **Error class caps** (`autoloop_driver.py`): syntax:5, logical:2, unknown:3 — 이미 구현됨. loop command에서 활성화만 하면 됨.
- **Single worktree per loop**: 0.5.5 이후 per-iter commit 폭발 방지. 올바른 설계.
- **Autonomous decision protocol**: AskUserQuestion 금지 + log-and-proceed. Ralph들과 동일.
- **loop-context YAML 지속성**: 재실행 시 인터뷰 재사용. Ralph prd.json 등가물.

---

## ⚠️ Pitfalls

1. **`stop_hook_active` 미체크 → 무한 루프**: Stop hook에서 `stop_hook_active` 필드를 체크하지 않으면 hook이 자기 자신의 continuation을 다시 막아 무한 루프. Claude Code 공식 docs에서 명시적으로 경고.

2. **Compaction이 사양서를 날릴 수 있음**: ghuntley가 "compaction is a lossy function, tower falls over" 라고 명명. 루프가 길어질수록 SKILL.md, loop-spec 내용이 compaction summary에서 누락될 수 있음. 해결: 중요 컨텍스트를 매 iter 시작 시 명시적으로 재로드.

3. **Self-reporting bias = false convergence**: 대화 내역을 가진 agent가 스스로 "완료"를 선언하면 실제 미완성이어도 종료. yaoshengzhe/autoloop가 독립 verifier로 해결한 문제.

4. **failed_streak=3 with cascading blockers**: iter N에서 외부 의존성(예: GitHub API rate limit)이 3회 연속 실패를 유발하면 loop가 실제 블로커 없이 중단. error class 분류(이미 `autoloop_driver.py`에 구현)를 loop command에 연결해야 함.

5. **Context 누적 + ping every 5 iters**: 현재 ping은 로그 출력뿐. iter 20-30에서 컨텍스트 사이즈를 측정하고 compaction을 명시적으로 트리거하는 로직 없음.

---

## ❓ Open Questions (`/hm:plan`이 잠가야 할 것)

1. **Stop hook 구현 범위**: `harness_maker.hooks.loop_gate`를 새 Python 모듈로 작성할지, 기존 hooks.json 렌더 템플릿에서 선택적으로 포함할지?

2. **Per-iter sub-agent 전환 방법**: driver context 누적 문제는 `/hm:loop`가 prompt-driven이기 때문에 Python으로 해결 불가. `ScheduleWakeup` + 상태 파일 패턴으로 per-iter fresh context를 구현할 수 있는가?

3. **failed_streak 기본값 변경 vs. 설정 가능 파라미터**: TECH_SPEC의 `max_iterations_per_phase: 5`와 정합성 맞춰야 함. `--failed-streak-cap N` 플래그 추가가 안전한가?

4. **max_iter 기본값 30 → 50+**: TECH_SPEC `max_global_iterations: 100`가 있으므로 loop command 기본값을 올려도 되는가, 아니면 spec에서 드라이브해야 하는가?

5. **독립 verifier 위치**: verify-before-completion skill을 isolated sub-agent로 실행하는 것 vs. 현재 conversation-embedded 실행. 비용 vs. accuracy trade-off 정량화 필요.

6. **compaction threshold 설정**: `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`를 loop 시작 시 60%로 변경하고 종료 후 복원할지, 전역 설정으로 낮출지?

---

## 📚 Sources

- [snarktank/ralph — 원조 Ralph Loop](https://github.com/snarktank/ralph)
- [ghuntley — everything is a ralph loop](https://ghuntley.com/loop/)
- [ghuntley/how-to-ralph-wiggum](https://github.com/ghuntley/how-to-ralph-wiggum)
- [alfredolopez80/multi-agent-ralph-loop — MemPalace + 병렬 팀](https://github.com/alfredolopez80/multi-agent-ralph-loop)
- [armgabrielyan/autoloop — agent-agnostic Karpathy inspired](https://github.com/armgabrielyan/autoloop)
- [yaoshengzhe/autoloop — independent verifier](https://github.com/yaoshengzhe/autoloop)
- [disler/infinite-agentic-loop](https://github.com/disler/infinite-agentic-loop)
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- [ralphloops.io — 오픈 스펙](https://ralphloops.io/)
- [Franziska Hinkelmann — Overcome context limitations with Ralph](https://medium.com/@fhinkel/overcome-context-limitations-with-ralph-c69d86b06b1d)
- [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks)
- [Stop hook task enforcement](https://claudefa.st/blog/tools/hooks/stop-hook-task-enforcement)
- [Compaction — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/compaction)
- [Context Compaction Deep Dive](https://codex.danielvaughan.com/2026/04/14/context-compaction-deep-dive-codex-cli-claude-code-opencode/)
- [Ralph Loop explained](https://beginnersinai.org/ralph-loop-explained/)
- [Ralph + Amp Loop — knightli.com](https://www.knightli.com/en/2026/04/27/ralph-autonomous-agent-loop-claude-code-amp/)

---

## 🔗 Related Internal Docs

- [[docs/reference/autoloop-pattern.md]] — 현재 `/hm:loop` 패턴 레퍼런스
- [[.claude/skills/autoloop-driver/SKILL.md]] — loop driver 오케스트레이션 WHY
- [[.claude/commands/hm/loop.md]] — 실제 loop 절차
- [[src/harness_maker/autoloop_driver.py]] — ErrorClass caps, convergence predicates (이미 구현)
- [[work-docs/PLAN-plugin-vs-generator-2026-05.md]] — 최근 관련 ADR
