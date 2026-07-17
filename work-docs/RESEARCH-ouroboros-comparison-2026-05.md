---
type: research
task_slug: ouroboros-comparison-2026-05
status: complete
created: 2026-05-09
tags: [harness-maker, research, ouroboros, prior-art, agent-os, specification-first, comparison]
mtime_warn_days: 30
libs_fetched: []
sources:
  - https://github.com/Q00/ouroboros
  - https://pypi.org/project/ouroboros-ai/
related_docs:
  - work-docs/RESEARCH-plugin-vs-generator-2026-05.md
  - work-docs/RESEARCH-harness-gap-cot-2026-05.md
summary: "ouroboros는 multi-runtime specification-first agent OS; harness-maker와 구조가 달라 경쟁보단 참조 대상"
---

# 🎯 Recommended Direction

**ouroboros와 harness-maker는 직접 경쟁자가 아니다.** 핵심 설계 철학이 다르다 — ouroboros는 *specification-first 단일 워크플로우*를 7개 런타임에 공통 제공하는 Agent OS이고, harness-maker는 *per-project 개인화된 harness를 생성해 user 프로젝트에 주입*하는 generator다. 단, ouroboros에서 실질적으로 빌릴 수 있는 아이디어가 3개 있다: **3-stage evaluation 파이프라인**, **bounded-loop auto 명령**, **brownfield 온보딩 스킬**.

---

# 🛠️ Approaches Found

## Approach A: ouroboros — Static Plugin + MCP Server

| Field | Content |
|-------|---------|
| Approach | PyPI 패키지 + Claude plugin marketplace 배포. Skills가 MCP tool로 dispatch |
| Assumption | 모든 사용자가 동일한 specification-first 워크플로우(interview→seed→run→evaluate→evolve)를 원함 |
| Evidence | `ooo auto` 단일 명령으로 전 과정 자동화; MCP `ouroboros_interview` / `ouroboros_evaluate` 등이 실제 실행 담당 |
| Trade-off | 개인화 없음. 모든 프로젝트가 동일한 prompts 받음. 대신 `claude plugin update`로 즉시 최신화 가능 |
| Compatibility | 7개 런타임(Claude Code, Codex CLI, OpenCode, Hermes, Kiro, Copilot CLI, Gemini CLI) 지원 |
| Risk | low (3,759 stars, MIT, 활발한 업데이트) |

### 세부 구조

**배포 방식**:
- PyPI: `pip install ouroboros-ai[claude]`
- Claude marketplace: `claude plugin marketplace add Q00/ouroboros`
- 사용자 프로젝트에 아무 파일도 생성하지 않음 — 플러그인 자체가 실행 컨텍스트

**핵심 워크플로우** (`interview → seed → run → evaluate → evolve`):
- `ooo interview`: Socratic 인터뷰 (목표 모호성 ≤ 0.2 달성 목표)
- `ooo seed`: 인터뷰 결과를 불변 Seed spec으로 crystallize
- `ooo run`: Seed 기반 코드 실행
- `ooo evaluate`: 3-stage 평가 파이프라인 (아래 참조)
- `ooo evolve`: spec 진화 (코드가 아닌 spec을 수정)
- `ooo auto`: 위 전체를 단일 명령으로 자동화 (bounded rounds)

**3-stage 평가 파이프라인** (핵심 차별점):
1. **Mechanical Verification** ($0 비용): lint, build, test, static analysis, coverage
2. **Semantic Evaluation** (LLM): AC compliance, goal alignment scoring, drift measurement
3. **Multi-Model Consensus** (frontier tier, optional): 여러 모델이 vote, majority ratio 결정

**Persistence**: aiosqlite + SQLAlchemy async (sessions, seeds, evaluations을 SQL로 추적)

**자기 업데이트**: 각 스킬 실행 전 GitHub releases API 체크 → 새 버전이 있으면 사용자에게 물어보고 `claude plugin update ouroboros@ouroboros` 자동 실행

**훅 구조**:
```json
{
  "SessionStart": "session-start.py",
  "UserPromptSubmit": "keyword-detector.py",
  "PostToolUse Write|Edit": "drift-monitor.py"
}
```

## Approach B: harness-maker — Generator

| Field | Content |
|-------|---------|
| Approach | Jinja2 template render → user 프로젝트의 `.claude/` + `.cursor/`에 맞춤 파일 생성 |
| Assumption | 프로젝트마다 다른 context(locale, preset, domains, reviewers, targets)가 필요하고 그것을 agent/skill 프롬프트에 주입해야 함 |
| Evidence | `code-reviewer.md.j2`의 `{% for d in config.project.domains %}`, `Production.json.j2` vs `Side.json.j2`, 이중 hooks schema (Claude Code PascalCase vs Cursor camelCase) |
| Trade-off | update friction (재렌더 필요). 대신 block-merge markers로 사용자 편집 보존 |
| Compatibility | Claude Code + Cursor 양쪽 지원 (dual-IDE target) |
| Risk | low (현재 설계) |

---

# 📊 Feature Matrix 비교

| 기능 | ouroboros | harness-maker |
|------|-----------|---------------|
| **배포** | PyPI + Claude marketplace | Claude Code + Cursor plugin |
| **런타임 지원** | 7개 (Claude Code, Codex, OpenCode, Hermes, Kiro, Copilot, Gemini) | 2개 (Claude Code, Cursor) |
| **핵심 철학** | Specification-first (interview → spec → code) | Generator (project-tailored harness) |
| **개인화** | 없음 (모든 사용자 동일) | 높음 (locale, preset, targets, domains, reviewers) |
| **Persistence** | SQL (aiosqlite + SQLAlchemy) | YAML (harness.yaml) |
| **평가 파이프라인** | 3-stage (Mechanical → Semantic → Multi-model) | Grade-gated review + auto-fix loop |
| **자동화** | `ooo auto` (one-shot full pipeline) | `/hm:loop` (phase-by-phase) |
| **사용자 편집 보존** | 없음 (plugin update가 덮어씀) | Block-merge markers (`@hm:user:*`) |
| **업그레이드** | 즉시 (`claude plugin update`) | `/hm:make --update` + 재렌더 |
| **anti-rot** | 없음 (version check만) | ArXiv/GitHub/OSV 크롤러 + relevance scoring |
| **Brownfield 지원** | `ooo brownfield` 스킬 있음 | 없음 |
| **AI-readiness 측정** | 없음 | 3-layer rubric (deterministic + LLM + cache-diagnostic) |
| **Worktree isolation** | 없음 | `.worktrees/` + fingerprint |
| **Hooks schema** | Claude Code 단일 (PascalCase) | Claude Code (PascalCase) + Cursor (camelCase) dual |
| **Context lint** | 없음 | 행 수 제한 enforced |
| **별 수** | 3,759 | private |

---

# ⚠️ Pitfalls

## ouroboros 관찰 사항

1. **MCP tool dependency**: 모든 핵심 기능이 MCP server에 의존. MCP가 등록 안 되어 있거나 ToolSearch로 로드 안 되면 fallback이 없거나 불완전. `SKILL.md`가 매번 "ToolSearch로 먼저 load하라" 주석을 다는 것이 이 취약성의 증거.

2. **개인화 한계**: `ooo interview`가 모든 프로젝트에서 동일한 Socratic 질문 패턴을 쓴다. Python 도메인 특화 reviewer, Rust 빌드 규칙, 한국어 locale 같은 것은 설계 범위 밖.

3. **SQL-first persistence**: aiosqlite + SQLAlchemy는 강력하지만 `cat .claude/harness.yaml` 처럼 투명하게 검사하기 어렵다. 세션 복구 디버깅이 복잡.

4. **버전 체크 코드가 각 SKILL.md에 중복**: `interview/SKILL.md`, `seed/SKILL.md` 등이 각자 동일한 curl + jq 버전체크 코드를 포함. SKILL.md가 길어지는 원인.

## harness-maker 관점에서 ouroboros가 잘 푼 것

1. **`ooo auto`의 경계 보장**: `max_interview_rounds`, `max_repair_rounds` 파라미터로 무한루프 방지. `/hm:loop`의 longevity 문제와 같은 맥락.

2. **Semantic evaluation 스코어링**: 단순 pass/fail 대신 "goal alignment score", "drift measurement"를 수치로 내놓음. harness-maker의 review grade (A~F)보다 세밀.

3. **brownfield 스킬**: 기존 프로젝트 온보딩. harness-maker는 신규 프로젝트 중심이고 기존 코드베이스에 harness를 얹는 시나리오가 약하다.

---

# ❓ Open Questions

이 비교에서 나온 actionable question들 — plan으로 넘기기 전에 우선순위 결정 필요:

1. **3-stage evaluation 차용 여부**: ouroboros의 mechanical → semantic → multi-model 파이프라인을 `/hm:review` 안에 통합할 가치가 있는가? 현재 harness-maker는 LLM reviewer agent가 grade를 주지만 mechanical step (lint/test 자동 실행)이 structured하게 분리되어 있지 않다.

2. **brownfield 스킬 필요성**: 사용자 기반이 신규 프로젝트 위주인가, 기존 코드베이스 온보딩이 실제 pain point인가? ouroboros 3,759 stars 중 상당수가 brownfield 시나리오일 가능성.

3. **`ooo auto` 등가 명령**: `/hm:loop`를 좀 더 one-shot으로 만드는 것과, auto 스타일의 bounded pipeline을 별도 명령으로 추가하는 것 중 어느 방향이 맞는가?

4. **MCP-first vs generator**: ouroboros처럼 MCP tool을 핵심 실행 레이어로 쓰는 방향을 harness-maker에서도 고려할 수 있는가? 현재 Python + Jinja2 generator가 MCP 없이 작동하는 것은 장점이기도 하지만 MCP 에코시스템에서 벗어난 셈.

---

# 📚 Sources

- https://github.com/Q00/ouroboros — source code (README, CLAUDE.md, skills/, hooks/, commands/, pyproject.toml, src/)
- https://pypi.org/project/ouroboros-ai/ — PyPI listing (PyPI 페이지는 별도 fetch 안 했지만 pyproject.toml에서 메타 확인)

---

# 🔗 Related Internal Docs

- [[work-docs/RESEARCH-plugin-vs-generator-2026-05.md]] — generator vs static plugin 설계 결정 5개 binding constraint
- [[work-docs/RESEARCH-harness-gap-cot-2026-05.md]] — 유사 prior art 20+ 분석 (SuperClaude, BMAD, task-master 등)
- [[work-docs/PLAN-multi-repo-mgmt-2026-05.md]] — 현재 진행 중 plan
