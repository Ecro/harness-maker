---
type: research
task_slug: codex-usage-guide
status: complete
created: 2026-05-10
tags: [harness-maker, research, codex, openai, workflow, agentic-coding]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://developers.openai.com/codex/learn/best-practices
  - https://developers.openai.com/codex/guides/agents-md
  - https://developers.openai.com/codex/concepts/sandboxing
  - https://developers.openai.com/codex/agent-approvals-security
  - https://developers.openai.com/codex/cli/slash-commands
  - https://developers.openai.com/codex/cli/reference
  - https://developers.openai.com/codex/skills
  - https://developers.openai.com/codex/subagents
  - https://developers.openai.com/codex/mcp
  - https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
  - https://help.openai.com/en/articles/11381614-codex-codex-andsign-in-with-chatgpt
related_docs:
  - "[[RESEARCH-codex-target-support]]"
  - "[[PLAN-codex-target-support]]"
  - "[[REVIEW-codex-target-support-2026-05-10]]"
  - "[[wiki:architecture/codex-triple-target-assets]]"
summary: "Codex works best as a scoped pair-programmer with persistent AGENTS.md, sandboxed autonomy, and test/review loops"
---

# 🎯 Recommended Direction

Codex를 잘 쓰는 핵심은 **한 번짜리 프롬프트를 잘 쓰는 것보다, 반복 가능한 작업 계약을 repo 안에 심는 것**이다. 기본 운영 방식은 `AGENTS.md`로 프로젝트 규칙을 자동 로드시키고, 작업 프롬프트에는 Goal / Context / Constraints / Done when 네 가지를 명시한 뒤, 구현 후 테스트와 `/review`까지 같은 루프 안에서 맡기는 것이다. 복잡하거나 모호한 작업은 바로 구현시키지 말고 `/plan` 또는 `@hm-research`/`@hm-plan`으로 먼저 범위를 좁힌다.

이 저장소에서는 이미 Codex target이 켜져 있고(`.claude/harness.yaml`), `AGENTS.md`, `.agents/skills/hm-*`, `.codex/agents/*.toml`, `.codex/hooks.json`, `.codex/config.toml`이 생성되어 있다. 따라서 “Codex 잘 쓰는 법”의 추천 경로는 **harness-maker의 stage skill을 적극 호출하면서, Codex의 기본 기능(permissions, status, review, subagents, MCP)을 작업 규모에 맞게 섞는 방식**이다.

---

## 🛠️ Approaches Found

| Approach | Assumption | Evidence | Trade-off | Compatibility | Risk |
|---|---|---|---|---|---|
| Prompt-only pair programming | 작업이 작고, repo 규칙을 매번 짧게 설명할 수 있다 | OpenAI best practices는 좋은 프롬프트에 Goal / Context / Constraints / Done when을 넣으라고 권장한다. | 빠르지만 같은 설명을 반복하고 누락이 쉽다. | 모든 Codex 표면에서 동작한다. | low |
| Persistent repo workflow with `AGENTS.md` and skills | 팀/프로젝트 규칙과 반복 워크플로가 중요하다 | Codex는 시작 시 `AGENTS.md` 체인을 읽고, skill은 명시/암시 호출된다. | 초기 작성과 유지보수 비용이 있다. | 이 저장소의 harness-maker Codex target과 가장 잘 맞는다. | low |
| Autonomous execution with sandbox + approvals | Codex가 파일 수정과 테스트 실행까지 맡아야 한다 | Codex sandbox는 명령 실행에도 적용되고, approval policy로 중단 지점을 제어한다. | 권한이 넓으면 위험하고, 좁으면 멈춤이 잦다. | 로컬 CLI/IDE에서 효과적이다. | medium |
| Delegation with subagents | 병렬 탐색, 리뷰, 대규모 구현처럼 독립적인 하위 작업이 있다 | Codex subagents는 명시 요청 시 병렬 실행 가능하며 built-in `explorer`/`worker`가 있다. | 토큰과 지연 시간이 증가한다. | 복잡한 코드베이스 탐색과 리뷰에 유용하다. | medium |

---

## ⚠️ Pitfalls

1. **“고쳐줘”만 던지는 것**: Codex는 불완전한 프롬프트에도 쓸만하지만, 대형 repo에서는 목표·관련 파일·제약·완료조건이 없으면 추측이 늘어난다. 최소 템플릿은 `Goal / Context / Constraints / Done when`이다.
2. **구현과 검증을 분리하지 않는 것**: Codex가 코드를 만든 뒤 테스트, lint, 타입체크, diff review까지 이어가게 해야 한다. OpenAI 문서도 테스트와 리뷰 루프를 명시적으로 권장한다.
3. **모든 작업을 full access로 돌리는 것**: `danger-full-access`와 `approval_policy = "never"` 조합은 외부에서 충분히 격리된 환경에서만 써야 한다. 일반 로컬 작업은 `workspace-write` + `on-request`가 더 나은 기본값이다.
4. **`AGENTS.md`를 너무 크게 만드는 것**: Codex는 프로젝트 지침을 루트부터 현재 디렉터리까지 병합하지만 기본 크기 제한이 있다. harness-maker Production preset은 이미 그 한계에 가까울 수 있으므로, 핵심 규칙만 유지하고 세부 절차는 skills나 문서 링크로 분리하는 편이 안전하다.
5. **subagent를 남용하는 것**: Codex는 명시 요청이 있을 때만 subagent를 spawn하고, 각 subagent는 별도 모델/도구 작업을 소비한다. “보안, 성능, 동시성, 테스트 flake를 각각 검토”처럼 독립성이 있을 때만 쓴다.
6. **MCP를 많이 붙이는 것**: MCP는 자주 바뀌는 외부 컨텍스트나 반복 도구 접근에 좋지만, 무작정 연결하면 설정과 권한 표면만 커진다. docs, GitHub, browser/Figma처럼 실제 반복 루프를 줄이는 것부터 붙인다.
7. **Codex CLI와 ChatGPT 플랜/API 계정 차이를 혼동하는 것**: Help Center 기준 Codex는 ChatGPT 플랜에 포함될 수 있고, CLI의 ChatGPT sign-in은 API 계정 연결과 로컬 credential 생성을 포함한다. 조직/요금제/데이터 공유 설정에 따라 정책이 달라질 수 있으므로 팀 환경에서는 관리자 설정을 확인해야 한다.

---

## ❓ Open Questions

1. 개인 기본값을 `~/.codex/AGENTS.md`에 둘지, 프로젝트별 `AGENTS.md`에만 둘지 정해야 한다. 개인 취향은 global, 팀 규칙은 repo가 맞다.
2. 이 저장소의 기본 로컬 권한을 `workspace-write/on-request`로 낮출지, 현재처럼 작업 세션별로 `danger-full-access/never`를 허용할지 정해야 한다.
3. Codex에서 harness-maker stage를 호출할 때 `@hm-research`, `@hm-plan` 같은 skill 명시 호출을 표준으로 할지, 자연어 implicit trigger에 맡길지 정해야 한다.
4. 어떤 MCP가 실제 반복 작업을 줄이는지 정해야 한다. 이 저장소 기준 1순위는 OpenAI Docs MCP, GitHub, Context7 계열 문서 검색이다.
5. subagent 병렬화는 사용자가 명시 요청할 때만 가능하므로, 리뷰/탐색 프롬프트 템플릿에 “spawn agents” 문구를 넣을지 결정해야 한다.

---

## 📚 Sources

- OpenAI Codex Best Practices: https://developers.openai.com/codex/learn/best-practices
- Codex `AGENTS.md` discovery: https://developers.openai.com/codex/guides/agents-md
- Codex sandboxing and approvals: https://developers.openai.com/codex/concepts/sandboxing
- Codex agent approvals and security config examples: https://developers.openai.com/codex/agent-approvals-security
- Codex CLI slash commands: https://developers.openai.com/codex/cli/slash-commands
- Codex CLI command line options: https://developers.openai.com/codex/cli/reference
- Codex skills: https://developers.openai.com/codex/skills
- Codex subagents: https://developers.openai.com/codex/subagents
- Codex MCP: https://developers.openai.com/codex/mcp
- Using Codex with your ChatGPT plan: https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- Codex CLI and Sign in with ChatGPT: https://help.openai.com/en/articles/11381614-codex-codex-andsign-in-with-chatgpt

---

## 🔗 Related Internal Docs

- `[[RESEARCH-codex-target-support]]`: Codex target 추가 시 필요한 `.codex/`, `.agents/`, `AGENTS.md` 자산 조사.
- `[[PLAN-codex-target-support]]`: stage command를 Codex skill로 노출하기로 한 ADR, AGENTS.md parity, agent TOML 전략.
- `[[REVIEW-codex-target-support-2026-05-10]]`: Codex target 구현 리뷰와 TOML/AGENTS.md/PermissionRequest 관련 리스크.
- `[[wiki:architecture/codex-triple-target-assets]]`: 현재 harness-maker가 Codex target에서 생성하는 6개 자산 카테고리.

---

## Practical Operating Notes

### 프롬프트 기본형

```text
Goal: <무엇을 바꿀지>
Context: <관련 파일/오류/문서/이전 결정>
Constraints: <건드리지 말 것, 스타일, 테스트 범위, 권한 제한>
Done when: <통과해야 할 테스트/검증/리뷰 기준>
```

### 작업 크기별 기본 선택

| 작업 | 추천 방식 |
|---|---|
| 파일 하나 설명, 작은 수정 | 일반 Codex prompt + `/status`로 환경 확인 |
| 모호한 기능/버그 | `/plan` 또는 `@hm-research` 먼저 |
| repo 규칙 반복 | `AGENTS.md` 또는 skill로 승격 |
| 구현 후 품질 확인 | 테스트 실행 요청 + `/diff` + `/review` |
| 독립 축이 많은 리뷰/탐색 | “spawn one agent per point”처럼 명시 요청 |
| 외부 최신 문서/도구 필요 | MCP 또는 `--search`/공식 docs 확인 |

