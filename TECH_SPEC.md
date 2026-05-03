# TECH_SPEC: harness-maker

> **상태:** v2.1 (autoloop dry-run 분석 fixes 반영) · **작성:** 2026-05-03 · **언어:** 한국어 (Korean)
> Claude Code 플러그인 — 어떤 프로젝트든 `/harness-maker:make` 한 번에 맞춤 하네스(.claude/) 자동 생성·갱신. autoloop 으로 자율 빌드 가능한 형식.

## 0. Loop Configuration

```json
{
  "phases": 10,
  "max_iterations_per_phase": 5,
  "max_global_iterations": 100,
  "verify_command": "bash .claude-verify.sh",
  "progress_file": ".claude-progress.json",
  "repo_path": "/home/noel/harness-maker"
}
```

**Loop behavior:**
- 각 Phase 의 모든 Task 완료 → Phase Exit Criteria 검증
- Phase Exit Criteria 실패 시 max 5회 재시도 → 그래도 실패 시 blocker 기록 후 HALT
- AskUserQuestion 호출 금지 — 모든 결정은 본 spec + CLAUDE.md 우선 (DD#8 autonomous decision protocol)
- 진행 상태는 `.claude-progress.json` 에 atomic write
- Final Acceptance (Section 5) 실패는 HALT 안 함 — 보고만, 사용자 사후 review

---

## 1. Product Vision

### Problem Statement
사용자(`/home/noel`)는 22+ Claude-active 프로젝트를 한 사람이 운영. 각 프로젝트의 하네스 구성 fragmentation 심각:
- 8개 프로젝트는 하네스 무
- 1개 (spoton) 만 heavy
- vault 가 사실상 메인 hub
- 명령 표면 일치도 ≈ 30%
- 메모리 표준 일치도 ≈ 40%

수동 큐레이션은 22 프로젝트 × 항목별로 시간 부족. 사람이 결정해야 할 것 vs 자동화 가능한 것 의 경계 재설정 필요.

### Solution
**harness-maker** — Claude Code 플러그인. **단 하나의 메타 명령** `/harness-maker:make` 로 사용자 프로젝트 `.claude/` 안에 *맞춤 하네스 (commands·skills·agents·hooks·monitoring·anti-rot·worktree·security 자산)* 인터뷰 기반 생성. 사용자 일상 명령은 `/hm:` prefix (`/hm:dev`, `/hm:loop`, `/hm:monitor`, ...). Brownfield + Greenfield-with-spec 모두 지원.

### Target User
1. **사용자 본인 (1차)**: 22 프로젝트에 점진 적용. dogfood.
2. (Phase 10+) 외부 사용자 — Solo 개발자, marketplace 배포 검토.

### Success Metrics
- [ ] `/harness-maker:make` 가 빈 디렉토리에서 10분 내 완전한 하네스 생성
- [ ] `/harness-maker:make` 가 기존 .claude/ 풍부한 디렉토리에서 충돌 reconcile + ADD-only 적용
- [ ] 생성된 `/hm:dev`, `/hm:loop`, `/hm:monitor`, `/hm:refresh` 모두 정상 동작
- [ ] statusline 에 효율·Health·fresh 3 지표 실시간 표시
- [ ] `/hm:refresh` 가 4 source 크롤 → 패치 제안 → 사용자 confirm
- [ ] `/hm:execute` 가 worktree 격리 안에서 동작
- [ ] `/hm:verify` 가 5종 보안 게이트 검출 (sandbox 시드 vulnerability)
- [ ] 모든 generated 파일에 provenance frontmatter (hash + version)
- [ ] Reviewer agent 가 `Write` 시도 시 settings.json 차단 (권한 분리)
- [ ] CLAUDE.md / agent prompt 길이 제한 lint 동작

### NON-GOALS (의도적 배제, 변경 금지)
- 크로스-에이전트 portability (.agents 컨벤션, AGENTS.md 동기화) — Claude 전용
- Brainstorming · systematic-debugging 사전 게이트 — 사용자 결정
- Cursor / Aider / Codex 호환 — Phase 10+ 검토 안 함
- 팀 협업 기능 — hiloop 영역
- 클라우드 백엔드 — 100% 로컬 (telemetry 도)
- vault 자체 대체 — vault 는 hub
- 펌웨어/embedded 팀 governance 자동화
- Mode 분류 (M1-M4) — 폐기, 2 preset(Side/Production) 으로 대체

---

## 2. Technical Constitution

### Tech Stack
| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Language | Python | 3.12+ | 단일 언어 (Bash 사용 금지) |
| Package Manager | uv | latest | pyproject.toml + uv.lock |
| Type Check | mypy | latest | strict mode, 0 error |
| Linting | ruff | latest | check + format |
| Testing | pytest | 8+ | mock 우선, integration 는 INTEGRATION=1 시 |
| Templates | Jinja2 | 3+ | 모든 렌더링 |
| YAML | PyYAML | 6+ | harness.yaml 파싱 |
| LLM SDK | anthropic | latest | Claude Code subscription 활용 |
| HTTP | httpx | latest | arxiv·GitHub·OSV.dev API |
| Hash | hashlib (stdlib) | - | sha256 frontmatter |
| RSS | feedparser | latest | Anthropic blog crawl |
| CLI (옵션) | typer | latest | dev tooling 만 (plugin entry 는 .md) |
| CI | GitHub Actions | - | lint + test on PR |
| License | MIT | - | LICENSE 파일 |

### Project Structure (Plugin = ~/harness-maker)
```
harness-maker/
├── README.md
├── LICENSE                              # MIT
├── CLAUDE.md                            # autoloop CODER 가이드
├── TECH_SPEC.md                         # 본 문서 (vault symlink target)
├── pyproject.toml                       # uv project
├── uv.lock
├── .gitignore
├── .claude-verify.sh                    # autoloop verify entry point
├── .claude-progress.json                # autoloop runtime state (gitignored)
├── .claude-plugin/
│   └── plugin.json                      # Claude Code 공식 manifest
├── .claude/                             # harness-maker 자체 dogfood (Phase 9)
│   └── obsidian.json                    # vault path 가리키기
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── harness_maker/                   # Python 패키지
│       ├── __init__.py                  # __version__ = "0.1.0"
│       ├── cli.py                       # dev tooling (typer)
│       ├── i18n.py                      # locale resolver
│       ├── profile.py                   # 시그널 추출
│       ├── interview.py                 # preset + 차원 인터뷰
│       ├── synthesize.py                # preset + answers → blueprint
│       ├── reconcile.py                 # Brownfield 충돌 해결
│       ├── render.py                    # Jinja2 렌더 + frontmatter 부착
│       ├── verify.py                    # smoke (yaml lint, hooks parse, frontmatter)
│       ├── modular_edit.py              # --add / --remove
│       ├── workflow_fuse.py             # atomic stages → fused workflow command
│       ├── statusline.py                # `python -m harness_maker.statusline`
│       ├── telemetry.py                 # post-tool-use hook
│       ├── context_lint.py              # 길이 + 중요도 lint
│       ├── provenance.py                # frontmatter 부착·검증
│       ├── crawler/
│       │   ├── __init__.py
│       │   ├── anthropic_blog.py
│       │   ├── github_releases.py
│       │   ├── arxiv.py
│       │   ├── osv_dev.py
│       │   └── reference_repos.py
│       ├── relevance.py                 # adaptive threshold filter
│       ├── readiness.py                 # Health 6-dim 계산
│       ├── agent_quality.py             # Platinum/Gold/Silver/Bronze
│       ├── conditional_router.py        # 변경 영역 → reviewer 선택
│       ├── worktree.py                  # git worktree 라이프사이클
│       ├── security_scanner.py          # 5 gates orchestrator
│       ├── secscan/
│       │   ├── secrets.py
│       │   ├── permissions.py
│       │   ├── hook_injection.py
│       │   ├── dependency_cves.py
│       │   └── prompt_injection.py
│       └── autoloop_driver.py           # /hm:loop 의 driver
├── commands/                            # 메타-툴은 단 1개 명령
│   └── make.md                          # /harness-maker:make
├── skills/                              # 메타-툴 자체 skills
│   ├── profile-project/SKILL.md
│   ├── interview-config/SKILL.md
│   ├── synthesize-blueprint/SKILL.md
│   ├── reconcile-brownfield/SKILL.md
│   ├── render-blueprint/SKILL.md
│   ├── verify-harness/SKILL.md
│   └── modular-edit/SKILL.md
├── templates/                           # ★ 사용자 .claude/ 로 렌더되는 자산
│   ├── harness-yaml/
│   │   ├── Side.yaml.j2
│   │   └── Production.yaml.j2
│   ├── claude-md/
│   │   ├── Side.ko.md.j2
│   │   ├── Side.en.md.j2
│   │   ├── Production.ko.md.j2
│   │   └── Production.en.md.j2
│   ├── settings/
│   │   ├── Side.json.j2
│   │   └── Production.json.j2
│   ├── memory/
│   │   ├── failures.ko.md.j2
│   │   ├── failures.en.md.j2
│   │   ├── wiki.ko.md.j2
│   │   └── wiki.en.md.j2
│   ├── stages/                          # atomic stage prompt fragments
│   │   ├── research.md.j2
│   │   ├── spec.md.j2
│   │   ├── plan.md.j2
│   │   ├── execute.md.j2
│   │   ├── review.md.j2
│   │   ├── wrapup.md.j2
│   │   └── verify.md.j2
│   ├── commands/                        # → user .claude/commands/hm/
│   │   └── hm/
│   │       ├── atomic_command.md.j2     # 7 atomic 각각 렌더
│   │       ├── workflow_command.md.j2   # fused workflow 각각 렌더
│   │       ├── loop.md.j2               # /hm:loop
│   │       ├── monitor.md.j2            # /hm:monitor
│   │       └── refresh.md.j2            # /hm:refresh
│   ├── skills/                          # → user .claude/skills/
│   │   ├── verify-before-completion/SKILL.md.j2
│   │   ├── conditional-router/SKILL.md.j2
│   │   ├── ai-readiness-rubric/SKILL.md.j2
│   │   ├── agent-quality-rubric/SKILL.md.j2
│   │   ├── research-crawler/SKILL.md.j2
│   │   ├── relevance-filter/SKILL.md.j2
│   │   ├── autoloop-driver/SKILL.md.j2
│   │   ├── worktree-isolator/SKILL.md.j2
│   │   ├── security-scanner/SKILL.md.j2
│   │   └── context-linter/SKILL.md.j2
│   ├── agents/                          # → user .claude/agents/
│   │   ├── code-reviewer.md.j2
│   │   ├── security-reviewer.md.j2
│   │   ├── security-auditor.md.j2
│   │   ├── performance-reviewer.md.j2
│   │   ├── ux-reviewer.md.j2
│   │   ├── concurrency-reviewer.md.j2
│   │   ├── consensus-arbiter.md.j2
│   │   ├── autoloop-coder.md.j2
│   │   └── executor.md.j2
│   ├── hooks/
│   │   └── hooks.json.j2
│   └── observability/
│       ├── dashboard.ko.md.j2
│       └── dashboard.en.md.j2
└── tests/
    ├── conftest.py
    ├── unit/                            # 단위 테스트 (mock 위주)
    │   ├── test_profile.py
    │   ├── test_interview.py
    │   ├── test_synthesize.py
    │   ├── test_reconcile.py
    │   ├── test_render.py
    │   ├── test_verify.py
    │   ├── test_modular_edit.py
    │   ├── test_workflow_fuse.py
    │   ├── test_context_lint.py
    │   ├── test_provenance.py
    │   ├── test_relevance.py
    │   ├── test_readiness.py
    │   ├── test_agent_quality.py
    │   ├── test_conditional_router.py
    │   ├── test_worktree.py
    │   ├── test_security_scanner.py
    │   ├── test_autoloop_driver.py
    │   └── crawler/
    │       ├── test_anthropic_blog.py
    │       ├── test_github_releases.py
    │       ├── test_arxiv.py
    │       └── test_osv_dev.py
    ├── fixtures/                        # 합성 검증용 가짜 프로젝트
    │   ├── side-python-cli/             # Side x Python
    │   ├── side-tauri-app/              # Side x Tauri
    │   ├── prod-tauri-app/              # Production x Tauri
    │   └── prod-firmware/               # Production x C/Zephyr
    ├── snapshot/                        # expected blueprint snapshots
    │   ├── side-python-cli.expected.yaml
    │   ├── side-tauri-app.expected.yaml
    │   ├── prod-tauri-app.expected.yaml
    │   └── prod-firmware.expected.yaml
    ├── integration/                     # INTEGRATION=1 시만
    │   ├── test_make_greenfield.py
    │   ├── test_make_brownfield.py
    │   ├── test_refresh_real_crawl.py
    │   └── test_loop_minimal.py
    └── e2e/
        └── test_dogfood_sandbox.py
```

### Code Style
- 파일 상단 1-line docstring (모듈 목적)
- 함수 docstring: WHY only (WHAT 은 코드)
- 주석 최소 — non-obvious 만
- 변수·함수명 영어 / 사용자 출력은 locale 따름
- 에러 메시지: locale=ko 시 한국어 + system error 영어 그대로
- mypy strict 통과 (Any 금지, 명시적 type hint)
- ruff 모든 룰 통과 (선택 룰셋: E, F, W, I, N, UP, B, A, C4, RET, SIM, PT)

### Git 정책
- 커밋: `<type>: <subject>` 또는 autoloop 자동 형식 `autoloop(harness-maker): phase N - <name>`
- type: `feat | fix | chore | ci | test | docs | refactor`
- **No remote** — local commits only. push 금지.
- 모든 phase wrapup stage 에서 자동 commit

### 외부 API 정책
- LLM 호출은 Claude Code subscription 통해 (API key 없이)
- arxiv·GitHub·OSV.dev: unauthenticated, `~/.cache/harness-maker/` 캐시 공유
- 외부 호출은 fixture mock 우선. 실제 호출은 INTEGRATION=1 env 시만.

### 보안 / 권한 (v1.6)
- **Reviewer agent** (code, security, perf, ux, concurrency, security-auditor, consensus-arbiter):
  - allow: `[Read(*), Grep(*), Bash(git diff:*), Bash(git log:*)]`
  - deny: `[Write(*), Edit(*), Bash(rm:*), Bash(curl:*), Bash(npm install:*), Bash(eval:*)]`
- **Executor agent** (autoloop-coder, executor):
  - allow: `[Read(*), Grep(*), Write(.worktrees/**), Edit(.worktrees/**), Bash(npm test:*), Bash(pytest:*), Bash(cargo test:*), Bash(uv run:*)]`
  - deny: `[Write(/etc/**), Write(~/.ssh/**), Write(~/.aws/**), Bash(curl * | sh), Bash(eval *), Bash(rm -rf /:*)]`
- 모든 generated 파일은 frontmatter:
  ```yaml
  generated_by: harness-maker
  harness_maker_version: "0.1.0"
  generated_at: "<ISO-8601>"
  source_template: "templates/<path>"
  content_hash: "sha256:<hex>"
  provenance: "official"  # official | community | user-modified
  ```

### Context Lint (v1.6)
| 자산 | Side 한계 | Production 한계 |
|---|---|---|
| CLAUDE.md | 200 행 | 500 행 |
| agent prompt | 100 행 | 200 행 |
| skill SKILL.md | 50 행 | 150 행 |
| workflow command (fused) | 300 행 | 600 행 |

초과 시 renderer 가 warn (override: `harness.yaml.context_lint.strict: false`).

---

## 3. Architecture

### 시스템 묘사

```
┌──────────────────────────────────────────────────────────────────────┐
│                            사용자                                     │
│                  /harness-maker:make  (단 하나)                       │
│           [--audit | --add X | --remove X | --promote]                │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
            ┌────────────────────┴─────────────────────┐
            │   harness-maker 플러그인 (메타-툴)         │
            │   역할: 사용자 .claude/ 를 생성·갱신만     │
            ├────────────────────────────────────────┤
            │  ① Profiler          (시그널 추출)        │
            │  ② Interviewer       (Preset + 10+ 차원) │
            │  ③ Synthesizer       (preset → blueprint)│
            │  ④ Reconciler        (Brownfield 충돌)   │
            │  ⑤ Renderer          (Jinja2 + frontmatter)│
            │  ⑥ Verifier          (smoke 검증)         │
            │  ⑦ ModularEditor     (--add / --remove)  │
            │  ⑧ I18n              (locale 인지)        │
            │  자체 업데이트: Claude Code plugin auto-update │
            └────────────────────────────────────────┘
                                 │  생성·렌더
                                 ▼
        ┌─────────────────────────────────────────────────────┐
        │  <project>/.claude/  (생성된 하네스 = 모든 런타임)      │
        │  ├── harness.yaml       (single source of truth)     │
        │  ├── settings.json      (statusLine, permissions)    │
        │  ├── commands/                                        │
        │  │   └── hm/                                          │
        │  │       ├── research.md ┐                            │
        │  │       ├── spec.md     │                            │
        │  │       ├── plan.md     ├ atomic stages (항상 7개)   │
        │  │       ├── execute.md  │   /hm:<stage>              │
        │  │       ├── review.md   │                            │
        │  │       ├── wrapup.md   │                            │
        │  │       ├── verify.md   ┘                            │
        │  │       ├── dev.md      ┐                            │
        │  │       ├── careful.md  ├ workflows (사용자 명명)     │
        │  │       ├── ...         ┘                            │
        │  │       ├── loop.md       → /hm:loop                 │
        │  │       ├── monitor.md    → /hm:monitor              │
        │  │       └── refresh.md    → /hm:refresh (anti-rot)   │
        │  ├── skills/  (10 skills)                             │
        │  ├── agents/  (9 agents)                              │
        │  ├── hooks/hooks.json (statusline + telemetry)        │
        │  ├── lib/  (statusline.py wrapper)                    │
        │  ├── .worktrees/  (gitignored)                        │
        │  └── observability/                                    │
        │      ├── dashboard.md                                 │
        │      ├── metrics.jsonl                                │
        │      ├── refresh/                                      │
        │      │   ├── raw-<date>.jsonl                        │
        │      │   └── proposed-<date>.md                       │
        │      └── security/                                     │
        │          └── findings-<date>.jsonl                   │
        └─────────────────────────────────────────────────────┘
```

### Data Model (핵심 Pydantic 모델)

```python
# src/harness_maker/models.py

from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field

class Locale(str, Enum):
    KO = "ko"
    EN = "en"

class Preset(str, Enum):
    SIDE = "Side"
    PRODUCTION = "Production"

class ModelTier(str, Enum):
    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"

class AtomicStage(str, Enum):
    RESEARCH = "research"
    SPEC = "spec"
    PLAN = "plan"
    EXECUTE = "execute"
    REVIEW = "review"
    WRAPUP = "wrapup"
    VERIFY = "verify"

class ProjectProfile(BaseModel):
    """Profiler output."""
    stack: list[str]
    scale: str  # small | medium | large
    lifecycle: str  # experiment | active | maintenance
    existing_dotclaude: bool
    spec_only: bool  # TECH_SPEC.md 만 있는 경우
    vault_member: bool

class WorkflowDef(BaseModel):
    """User-named workflow (fused stages)."""
    name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    stages: list[AtomicStage]

class HarnessConfig(BaseModel):
    """harness.yaml schema."""
    locale: Locale = Locale.KO
    preset: Preset = Preset.SIDE
    workflows: dict[str, list[AtomicStage]]
    default_workflow: str
    execution: dict  # { default: "step" | "autoloop" }
    reviewers: dict  # { list, consensus, routing }
    caching: str  # aggressive | conservative | adaptive | off
    hooks: dict  # { statusline-monitor, telemetry-collector }
    memory: dict  # { files: [failures.md, wiki.md] }
    autoloop: dict  # { allowed, default_time_h, default_max_iter }
    anti_rot: dict  # { threshold, auto_apply, schedule }
    dashboard: dict  # { path }
    models: dict  # { preset_default, stages, agents }
    worktree: dict  # { enabled, base_dir, cleanup, scope, merge_strategy }
    security: dict  # { enabled, scan_on, checks, on_finding }
    context_lint: dict  # { strict }

class Blueprint(BaseModel):
    """Synthesizer output."""
    config: HarnessConfig
    files: list["FileEntry"]
    
class FileEntry(BaseModel):
    """One file to render."""
    path: Path  # .claude/commands/hm/dev.md 같은 상대 경로
    template: str  # templates/commands/hm/workflow_command.md.j2
    context: dict  # Jinja2 context vars
    frontmatter: dict  # provenance fields

class ReconcileDecision(str, Enum):
    KEEP = "keep"
    REPLACE = "replace"
    BOTH = "both"

class ConflictItem(BaseModel):
    existing_path: Path
    new_path: Path
    decision: ReconcileDecision | None = None
```

### 핵심 메커니즘 (모두 Phase 4-8 에서 구현)

**(M1) Profiler → Interviewer → Synthesizer → Renderer pipeline (Phase 2)**
1. Profiler 가 stack/scale/lifecycle/existing_dotclaude/spec_only 감지
2. Interviewer 가 preset 추천 + 10+ 차원 override Q (workflow naming, reviewers, models, autoloop, anti-rot, worktree, security, context_lint, memory, caching)
3. Synthesizer 가 deterministic 매핑 → Blueprint
4. Renderer 가 Jinja2 + provenance frontmatter 부착해 .claude/ 에 출력

**(M2) Reconciler — Brownfield 충돌 해결 (Phase 5)**
- 기존 .claude/ 인덱싱 → 신규 blueprint 충돌 후보 N
- 항목별 사용자 선택 (keep/replace/both) — autoloop 환경에선 frontmatter hash 기반 자동 결정
- Hash 일치 = 우리 것 (overwrite 안전), Hash 없음/불일치 = 사용자/타 출처 (보존)
- backup → `.claude/.backup-<date>/` → ADD-only apply

**(M3) Workflow Engine — atomic + fused (Phase 5)**
- Atomic stage 7개 → 각각 `/hm:<stage>` 자동 노출
- Workflow = 사용자 명명 stage 시퀀스 → Renderer 가 fragment 합성 → 단일 `/hm:<name>` 명령
- `harness.yaml.workflows` 키에 정의, `/harness-maker:make` 재실행으로 추가 가능

**(M4) Anti-rot (Phase 4)**
3-Stage 파이프라인:
1. Crawl (주 1회): Anthropic blog/changelog + GitHub releases + arxiv (cs.SE/cs.CL/cs.CR) + reference repos (superpowers, oh-my-claudecode, Archon, ECC, OpenHarness, wshobson, claude-code-templates) + OSV.dev
2. Filter (LLM): adaptive threshold (start 0.7, accept/reject 비율 따라 ±0.05)
3. Propose: `/hm:refresh` 가 AskUserQuestion (accept/reject/defer). **항상 manual confirm.**

**(M5) Monitoring 3 metrics (Phase 3)**
- 효율 (cache hit %) — 매 turn, statusline 🪙
- Health (0-100) — 6-dim (docs/tests/CI/obs/security/governance) + Agent quality drill-down (Platinum/Gold/Silver/Bronze) + ceremony penalty
- fresh (days since refresh) — statusline 🔄
- Telemetry 100% 로컬 (`metrics.jsonl` 외부 전송 0)

**(M6) Conditional Router (Phase 5)**
- 변경 파일 영역 → reviewer 자동 선택
- auth/.env → security · perf-critical → performance · ui/.tsx → ux · worker/thread/isr → concurrency
- override: `harness.yaml.reviewers.routing: always-all`

**(M7) Autoloop driver (Phase 6)**
- `/hm:loop "<goal>" [--time 8h] [--max-iter 30] [--workflow X] [--dry-run]`
- Token 무제한, 시간·iter 만 limit
- 매 iter 가 자체 worktree (Phase 7 통합)
- iter 5회마다 사용자 ping, 3회 연속 실패 → stop

**(M8) Verify-before-completion 게이트 (Phase 6)**
- `/hm:wrapup` 또는 autoloop iter 완료 직전 자동 호출
- 체크리스트: PLAN/SPEC 충족 / 회귀 게이트 / Health -5 이내 / Anti-rot pending / 보안 high finding 0건 / Worktree merge 가능

**(M9) Worktree 격리 (Phase 7)**
- `/hm:execute` 시 자동 git worktree 생성 (`.worktrees/<workflow>-<ts>/`)
- LLM 이 worktree 안에서만 파일 수정
- 성공 시 cleanup, 실패 시 보존

**(M10) 5 Security Gates (Phase 7)**
| 검사 | 기법 | 트리거 |
|---|---|---|
| secrets | regex + entropy (gitleaks-style) | pre_commit · pre_wrapup · refresh |
| permissions | settings.json `allow` 과확장 검사 | refresh · /harness-maker:make |
| hook injection | hooks.json 위험 명령 (rm -rf, curl pipe sh, eval) AST | pre_wrapup · refresh |
| dependency CVEs | OSV.dev 조회 (package-lock·Cargo.lock·requirements.txt) | weekly |
| prompt injection | hidden instruction 패턴 + 권한 분리 architecture | LLM 호출 직전 |

**(M11) Context Lint (Phase 8)**
- Renderer Apply 직전 길이·중요도 검사. 초과 시 warn + 자동 요약 제안.

**(M12) Privilege Separation (Phase 8)**
- Reviewer agent settings.json `permissions.deny: [Write, Edit, Bash exec]`
- Executor agent settings.json `permissions.allow: [Write(.worktrees/**)]`
- Worktree 와 결합 → 격리·분리 이중 방어

**(M13) Provenance Frontmatter (Phase 8)**
- 모든 생성 자산 상단 frontmatter (generated_by, harness_maker_version, content_hash, source_template, generated_at, provenance)
- `/hm:refresh` 가 hash 비교 → 사용자 수정 감지 → silent overwrite 차단
- Brownfield reconcile 가 frontmatter 로 ours/theirs 판별

### Preset 디폴트 비교

| 차원 | Side | Production |
|---|---|---|
| Reviewers | `[code]` (1) | `[code, security, perf, ux, concurrency]` (5) |
| Consensus | cross-check | cross-check |
| Routing | conditional | conditional |
| Caching | aggressive | aggressive |
| Workflow 추천 시드 | dev=[plan,execute,review,wrapup] + quick=[execute] | 위 + careful=[research,spec,plan,execute,review,wrapup,verify] + audit=[review] |
| default_workflow | dev | dev |
| Model preset_default | sonnet | sonnet |
| Autoloop allowed | true | true |
| Memory | failures.md + wiki.md | failures.md + wiki.md |
| Anti-rot threshold | adaptive (0.7) | adaptive (0.7) |
| Anti-rot auto_apply | false | false |
| Hooks | statusline + telemetry | statusline + telemetry |
| Verify-before-completion | optional | required |
| Worktree scope | [execute] | [execute, plan] |
| Security on_finding.high | warn | block |
| Context lint | enabled | enabled (더 엄격) |
| 파일 개수 (대략) | 25-30 | 35-45 |

---

## 4. Implementation Phases

### Phase 1: Project Scaffold + Plugin Manifest + i18n MVP

**Objective:** Python 패키지 + uv + 공식 plugin manifest + i18n 모듈 + Q1 locale 동작.

**Research targets (autoloop Stage 1 자동 fetch):**
- Claude Code plugin manifest spec: https://code.claude.com/docs/en/plugins
- Claude Code plugins reference (전체 schema): https://code.claude.com/docs/en/plugins-reference
- uv 사용법: https://docs.astral.sh/uv/
- pyproject.toml schema: https://packaging.python.org/en/latest/specifications/pyproject-toml/

#### Tasks

- **Task 1.1: uv 프로젝트 초기화**
  - Do: `uv init --package` 실행 후 pyproject.toml 설정 — name="harness-maker", version="0.1.0", python ">=3.12", license="MIT", deps=[jinja2>=3, pyyaml>=6, pydantic>=2, anthropic, httpx, feedparser, typer, rich], dev=[pytest>=8, pytest-asyncio, ruff, mypy]. ruff config (E,F,W,I,N,UP,B,A,C4,RET,SIM,PT 룰셋). mypy strict.
  - Files: `pyproject.toml`, `uv.lock`, `src/harness_maker/__init__.py` (with `__version__ = "0.1.0"`)
  - Done when: `uv sync` 성공, `uv run python -c "import harness_maker; print(harness_maker.__version__)"` 가 "0.1.0" 출력
  - Verify: `bash .claude-verify.sh phase_1_uv`
  - Commit: `feat(phase1): initialize uv project with core dependencies`

- **Task 1.2: 공식 Plugin manifest**
  - Do: `.claude-plugin/plugin.json` 생성 — name="harness-maker", description="프로젝트 맞춤 하네스 자동 생성 + anti-rot + 모니터링", version="0.1.0", author={name: "noel"}, license="MIT". 공식 spec 준수 — 어떤 다른 디렉토리도 .claude-plugin/ 안에 두지 않음.
  - Files: `.claude-plugin/plugin.json`
  - Done when: `jq -r .name .claude-plugin/plugin.json` 가 "harness-maker"
  - Verify: `bash .claude-verify.sh phase_1_manifest`
  - Commit: `feat(phase1): add Claude Code plugin manifest`

- **Task 1.3: 메타-툴 entry command**
  - Do: `commands/make.md` 생성 — `/harness-maker:make` 명령 정의. 단 하나의 슬래시 명령. argparse: `--audit, --add, --remove, --promote`. 본문은 placeholder ("Phase 2 구현 예정") + 실행 시 `python -m harness_maker.cli make $ARGUMENTS` 호출.
  - Files: `commands/make.md`, `src/harness_maker/cli.py` (typer skeleton)
  - Done when: `cat commands/make.md` 가 `/harness-maker:make` 라우팅 보임, `uv run python -m harness_maker.cli --help` 정상
  - Verify: `bash .claude-verify.sh phase_1_command`
  - Commit: `feat(phase1): add /harness-maker:make entry command`

- **Task 1.4: i18n 모듈 + Q1 locale**
  - Do: `src/harness_maker/i18n.py` 구현. `resolve_locale(project_dir: Path) -> Locale` — `.claude/harness.yaml` 의 locale 키 우선, 없으면 None 반환 (호출자가 Q1 처리). `t(key: str, locale: Locale, **vars) -> str` — 메시지 카탈로그 lookup. 카탈로그는 `src/harness_maker/i18n_messages.py` (dict). 최소 키: `q1_choose_language`, `apply_done`, `error_no_yaml`. Test: `tests/unit/test_i18n.py` — locale 미존재 시 None, ko/en 메시지 lookup 테스트.
  - Files: `src/harness_maker/i18n.py`, `src/harness_maker/i18n_messages.py`, `tests/unit/test_i18n.py`
  - Done when: `uv run pytest tests/unit/test_i18n.py -v` 통과
  - Verify: `bash .claude-verify.sh phase_1_i18n`
  - Commit: `feat(phase1): implement i18n module with ko/en messages`

- **Task 1.5: README + LICENSE + CI 스켈레톤**
  - Do: `README.md` (1 page — 프로젝트 목적, Quick Start placeholder, License). `LICENSE` (MIT, copyright "noel"). `.github/workflows/ci.yml` — uv setup → ruff check → ruff format --check → mypy --strict → pytest. matrix: python 3.12.
  - Files: `README.md`, `LICENSE`, `.github/workflows/ci.yml`
  - Done when: 3 파일 존재, ci.yml 이 ruff+mypy+pytest 모두 호출
  - Verify: `bash .claude-verify.sh phase_1_meta`
  - Commit: `chore(phase1): add README, MIT LICENSE, CI workflow`

**Phase 1 Exit Criteria:**
```bash
uv sync \
  && uv run python -c "from harness_maker import __version__; assert __version__ == '0.1.0'" \
  && jq -r .name .claude-plugin/plugin.json | grep -q '^harness-maker$' \
  && test -f commands/make.md \
  && uv run pytest tests/unit/test_i18n.py -v \
  && uv run ruff check src/ \
  && uv run mypy --strict src/ \
  && test -f README.md && test -f LICENSE && test -f .github/workflows/ci.yml
```

---

### Phase 2: Profiler + Interviewer + Synthesizer + Renderer + Reconciler + 4 Fixtures

**Objective:** `/harness-maker:make` 의 핵심 파이프라인 동작. 4 fixture 에 적용해 expected blueprint 일치.

**Research targets (autoloop Stage 1 자동 fetch):**
- Pydantic v2 patterns: https://docs.pydantic.dev/latest/
- Jinja2 templating: https://jinja.palletsprojects.com/en/3.1.x/
- AskUserQuestion tool spec (Claude Code SDK): https://code.claude.com/docs/en/sub-agents

#### Tasks

- **Task 2.1: Pydantic 모델 정의**
  - Do: `src/harness_maker/models.py` 에 Section 3 Data Model 의 모든 모델 구현 (Locale, Preset, ModelTier, AtomicStage, ProjectProfile, WorkflowDef, HarnessConfig, Blueprint, FileEntry, ReconcileDecision, ConflictItem). pydantic v2 strict.
  - Files: `src/harness_maker/models.py`, `tests/unit/test_models.py`
  - Done when: `uv run python -c "from harness_maker.models import HarnessConfig, Blueprint, ProjectProfile"` 성공, model validation 테스트 통과
  - Verify: `bash .claude-verify.sh phase_2_models`
  - Commit: `feat(phase2): define Pydantic models for harness config and blueprint`

- **Task 2.2: Profiler 구현**
  - Do: `src/harness_maker/profile.py` — `profile(project_dir: Path) -> ProjectProfile`. 시그널: (a) stack — package.json/pyproject.toml/Cargo.toml/CMakeLists.txt/go.mod 존재 검사, (b) scale — 파일 개수 < 50 small / 50-500 medium / >500 large, (c) lifecycle — git commit 빈도 (last 30 days commits), (d) existing_dotclaude — `.claude/` 존재 여부, (e) spec_only — `TECH_SPEC.md` 존재 + 코드 파일 0개 시 true, (f) vault_member — `.claude/obsidian.json` 존재. mock 시그널로 unit test.
  - Files: `src/harness_maker/profile.py`, `tests/unit/test_profile.py`
  - Done when: 4 fixture 디렉토리에서 profile 호출 시 expected ProjectProfile 반환
  - Verify: `bash .claude-verify.sh phase_2_profile`
  - Commit: `feat(phase2): implement Profiler with multi-stack detection`

- **Task 2.3: Interviewer 구현**
  - Do: `src/harness_maker/interview.py` — `interview(profile: ProjectProfile, autoloop_mode: bool = False) -> dict[str, Any]`. autoloop_mode=True 시 모든 default 자동 채택 (AskUserQuestion 호출 X). interactive 모드 시 preset 추천 + 10 차원 질문: workflow names, default_workflow, reviewers, consensus, caching, models, autoloop, memory, anti_rot, worktree, security, context_lint. ko/en 메시지 카탈로그 활용.
  - Files: `src/harness_maker/interview.py`, `tests/unit/test_interview.py`
  - Done when: autoloop_mode 테스트가 모든 dimension 에 대한 default 답 채택 확인. interactive mode 는 mocked input 으로 테스트.
  - Verify: `bash .claude-verify.sh phase_2_interview`
  - Commit: `feat(phase2): implement Interviewer with autoloop + interactive modes`

- **Task 2.4: Synthesizer 구현**
  - Do: `src/harness_maker/synthesize.py` — `synthesize(profile: ProjectProfile, answers: dict) -> Blueprint`. preset+answers 를 deterministic 매핑해 Blueprint(HarnessConfig + list[FileEntry]) 생성. Side preset → 25-30 파일, Production → 35-45 파일. Side 와 Production 의 정확한 파일 리스트는 본 spec Section 2 의 templates/ 트리에서 도출 (모든 .j2 파일이 → 사용자 .claude/ 의 어떤 경로로 갈지 매핑).
  - Files: `src/harness_maker/synthesize.py`, `tests/unit/test_synthesize.py`
  - Done when: Side preset blueprint 가 25-30 파일, Production 35-45 파일 포함, 모든 FileEntry 가 valid template 경로 보유
  - Verify: `bash .claude-verify.sh phase_2_synthesize`
  - Commit: `feat(phase2): implement Synthesizer (preset + answers → Blueprint)`

- **Task 2.5: Renderer 구현 (provenance frontmatter 포함, deterministic 모드)**
  - Do: `src/harness_maker/render.py` — `render(blueprint: Blueprint, target_dir: Path, *, dry_run: bool = False, freeze_time: datetime | None = None)`. Jinja2 환경 셋업 (`templates/` 가 search path). 각 FileEntry 마다 (a) 템플릿 렌더, (b) provenance frontmatter (generated_by, harness_maker_version, generated_at = freeze_time or now(), source_template, content_hash sha256 of body **excluding frontmatter**, provenance="official") 부착, (c) target_dir 에 **atomic write** (`tempfile.NamedTemporaryFile(dir=target_dir.parent, delete=False)` → `os.rename`). dry_run=True 시 디스크 변경 0, 변경 목록만 반환. **freeze_time 인자 = 테스트 결정성 보장 (snapshot 비교에 필수)**.
  - Files: `src/harness_maker/render.py`, `tests/unit/test_render.py`
  - Done when: 빈 fixture 디렉토리에서 Side blueprint 렌더 → 25-30 파일 모두 frontmatter 포함, content_hash 가 실제 hash 와 일치
  - Verify: `bash .claude-verify.sh phase_2_render`
  - Commit: `feat(phase2): implement Renderer with Jinja2 + provenance frontmatter`

- **Task 2.6: Reconciler 구현 (Brownfield)**
  - Do: `src/harness_maker/reconcile.py` — `reconcile(existing_dir: Path, blueprint: Blueprint) -> list[ConflictItem]`. 기존 .claude/ 인덱싱. 각 신규 FileEntry 와 비교. 충돌 분류: (a) frontmatter 있고 hash 일치 → 우리 것, overwrite 안전 (decision=REPLACE 자동), (b) frontmatter 없음 또는 hash 불일치 → 사용자/타 출처 (decision=KEEP 디폴트, autoloop 환경 자동), (c) 신규 only → ADD. backup 함수 — `.claude/.backup-<ISO>/`.
  - Files: `src/harness_maker/reconcile.py`, `tests/unit/test_reconcile.py`
  - Done when: brownfield fixture (시드된 기존 .claude/) 에서 reconcile → 충돌 N건 분류 정확. backup 디렉토리 생성 확인.
  - Verify: `bash .claude-verify.sh phase_2_reconcile`
  - Commit: `feat(phase2): implement Reconciler with frontmatter-based conflict resolution`

- **Task 2.7: Verifier 구현 (smoke)**
  - Do: `src/harness_maker/verify.py` — `verify(target_dir: Path) -> list[str]` (errors). 검사: harness.yaml YAML lint, hooks/hooks.json JSON parse, 모든 .md 파일에 provenance frontmatter 존재, settings.json permissions schema valid.
  - Files: `src/harness_maker/verify.py`, `tests/unit/test_verify.py`
  - Done when: valid blueprint 렌더 결과에서 errors == [], 의도적 손상 시 errors 검출
  - Verify: `bash .claude-verify.sh phase_2_verifier`
  - Commit: `feat(phase2): implement Verifier with yaml/json/frontmatter checks`

- **Task 2.8: 4 Fixture + Snapshot Test (deterministic)**
  - Do: `tests/fixtures/{side-python-cli, side-tauri-app, prod-tauri-app, prod-firmware}/` 디렉토리 생성. 각 fixture 에 시드 파일 (pyproject.toml or package.json 등 Profiler 가 stack 감지 가능하게). `tests/snapshot/<fixture>.expected.yaml` — 각 fixture 에 대한 expected Blueprint (preset, 파일 리스트 + 각 파일의 content_hash, harness.yaml 내용). `tests/unit/test_synthesize_snapshot.py` — 4 fixture profile → synthesize → render(target=tmp, freeze_time=datetime(2026,1,1,0,0,0,tzinfo=UTC)) → snapshot 비교. **timestamp 는 freeze_time 으로 고정 → frontmatter content 결정적 → snapshot 안정**. Render 결과 파일 개수도 단언 (Side: 25-30, Production: 35-45 fixture 별 expected 값 사용).
  - Files: `tests/fixtures/*/`, `tests/snapshot/*.expected.yaml`, `tests/unit/test_synthesize_snapshot.py`
  - Done when: 4 fixture 모두 snapshot 일치, 각 fixture 의 file count 가 expected range 안
  - Verify: `bash .claude-verify.sh phase_2_fixtures`
  - Commit: `test(phase2): add 4 fixtures with deterministic snapshot tests`

- **Task 2.9: CLI integration — `make` 명령 동작**
  - Do: `src/harness_maker/cli.py` 의 `make` 함수 완성. 흐름: profile → (autoloop_mode True 일 시 default) interview → synthesize → (existing_dotclaude 시) reconcile → render. `uv run python -m harness_maker.cli make <fixture-dir> --autoloop` 명령으로 4 fixture 모두 정상 적용.
  - Files: `src/harness_maker/cli.py` (확장)
  - Done when: 4 fixture 모두 CLI 호출 → .claude/ 생성 → verify pass
  - Verify: `bash .claude-verify.sh phase_2_cli_make`
  - Commit: `feat(phase2): wire CLI make command end-to-end`

**Phase 2 Exit Criteria:**
```bash
uv run pytest tests/unit/ -v \
  && uv run ruff check src/ \
  && uv run mypy --strict src/ \
  && for fix in side-python-cli side-tauri-app prod-tauri-app prod-firmware; do
       rm -rf tests/fixtures/$fix/.claude
       uv run python -m harness_maker.cli make tests/fixtures/$fix --autoloop || exit 1
       test -f tests/fixtures/$fix/.claude/harness.yaml || exit 1
       count=$(find tests/fixtures/$fix/.claude -type f | wc -l)
       case "$fix" in
         side-*)  [[ $count -ge 25 && $count -le 32 ]] || { echo "$fix: expected 25-30, got $count"; exit 1; } ;;
         prod-*)  [[ $count -ge 35 && $count -le 47 ]] || { echo "$fix: expected 35-45, got $count"; exit 1; } ;;
       esac
     done
```

---

### Phase 3: Monitoring 3 Metrics (효율 + Health + fresh)

**Objective:** 사용자 하네스에 statusline·dashboard·telemetry 자산 렌더되어 3 지표 실시간 표시. Health 6-dim + Agent quality drill-down 계산 동작.

**Research targets (autoloop Stage 1 자동 fetch):**
- Claude Code statusline JSON input format: https://code.claude.com/docs/en/statusline
- Claude Code hooks (PostToolUse, format): https://code.claude.com/docs/en/hooks
- Claude Code session data fields available to statusline scripts (stdin JSON schema)

#### Tasks

- **Task 3.1: statusline 구현**
  - Do: `src/harness_maker/statusline.py` — `python -m harness_maker.statusline` 실행 시 stdin 으로 Claude Code 세션 데이터 받아 stdout 으로 statusline 출력. 형식: `<project> | <preset> | 🪙<eff>% | 🎯<health> | 🔄<fresh>d`. 데이터 source: `.claude/observability/metrics.jsonl` 의 마지막 N 항목 + harness.yaml 의 preset.
  - Files: `src/harness_maker/statusline.py`, `tests/unit/test_statusline.py`
  - Done when: mock metrics.jsonl 로 호출 시 expected 문자열 출력
  - Verify: `bash .claude-verify.sh phase_3_statusline`
  - Commit: `feat(phase3): implement statusline with 3 metrics`

- **Task 3.2: telemetry hook 구현**
  - Do: `src/harness_maker/telemetry.py` — `python -m harness_maker.telemetry` 가 PostToolUse hook 으로 호출됨. stdin 으로 hook input 받아 metrics.jsonl 에 turn 단위 기록 (input_tokens, output_tokens, cache_read, cost).
  - Files: `src/harness_maker/telemetry.py`, `tests/unit/test_telemetry.py`
  - Done when: mock hook input 으로 호출 → metrics.jsonl 에 줄 추가 검증
  - Verify: `bash .claude-verify.sh phase_3_telemetry`
  - Commit: `feat(phase3): implement telemetry collector hook`

- **Task 3.3: Health 6-dim 계산**
  - Do: `src/harness_maker/readiness.py` — `compute_health(project_dir: Path, preset: Preset) -> dict`. 6 dim 각각 0-100 점수: docs (CLAUDE.md/README/ADR 존재 + 길이), tests (test/ 디렉토리 + 커버리지 grep), CI (.github/workflows 존재), observability (metrics.jsonl + dashboard 존재), security (.claude/observability/security/findings 의 high count), governance (Production 만 가중치, ADR/CONTRIBUTING 존재). composite = 가중평균 + ceremony penalty.
  - Files: `src/harness_maker/readiness.py`, `tests/unit/test_readiness.py`
  - Done when: 4 fixture 각각 Health 점수 계산, 빈 fixture 는 낮은 점수, 풍부한 fixture 는 높은 점수
  - Verify: `bash .claude-verify.sh phase_3_health`
  - Commit: `feat(phase3): implement Health 6-dim composite scoring`

- **Task 3.4: Agent quality drill-down**
  - Do: `src/harness_maker/agent_quality.py` — `score_agent(agent_md: Path) -> dict`. 3-layer 평가: (a) Static — 길이·구조·permissions 정의 존재, (b) LLM judge — agent prompt 를 Claude 에게 평가 요청 (quality 0-100, mock 가능), (c) Monte Carlo — 동일 prompt 10회 실행 결과 일관성 (지금은 placeholder). 종합 → Platinum (≥90) / Gold (80-89) / Silver (70-79) / Bronze (<70).
  - Files: `src/harness_maker/agent_quality.py`, `tests/unit/test_agent_quality.py`
  - Done when: mock agent .md 로 등급 결정 통과
  - Verify: `bash .claude-verify.sh phase_3_agent_quality`
  - Commit: `feat(phase3): implement Agent quality rubric (Platinum/Gold/Silver/Bronze)`

- **Task 3.5: Dashboard 렌더 + monitor 명령**
  - Do: `templates/observability/dashboard.{ko,en}.md.j2` 작성 — 3 지표 + Health 6-dim + Agent quality drill-down + Anti-rot pending 섹션. `templates/commands/hm/monitor.md.j2` 작성 — `/hm:monitor` 명령으로 Python 으로 지표 계산 후 dashboard 갱신.
  - Files: `templates/observability/dashboard.{ko,en}.md.j2`, `templates/commands/hm/monitor.md.j2`
  - Done when: Side fixture 에서 make → /hm:monitor 호출 시 dashboard.md 갱신 (mock metrics 활용)
  - Verify: `bash .claude-verify.sh phase_3_dashboard`
  - Commit: `feat(phase3): add dashboard template + /hm:monitor command`

- **Task 3.6: hooks.json + settings.json 템플릿**
  - Do: `templates/hooks/hooks.json.j2` — PostToolUse 에 telemetry hook, statusLine 에 statusline 호출. `templates/settings/{Side,Production}.json.j2` — statusLine + permissions allow list (read-only 기본 + 권한 분리는 Phase 8 에서 강화).
  - Files: `templates/hooks/hooks.json.j2`, `templates/settings/{Side,Production}.json.j2`
  - Done when: 렌더된 hooks.json 이 jq 통과, settings.json 이 statusLine 가리킴
  - Verify: `bash .claude-verify.sh phase_3_hooks_settings`
  - Commit: `feat(phase3): add hooks.json + settings.json templates`

**Phase 3 Exit Criteria:**
```bash
uv run pytest tests/unit/ -v \
  && uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop \
  && jq . tests/fixtures/side-python-cli/.claude/hooks/hooks.json > /dev/null \
  && test -f tests/fixtures/side-python-cli/.claude/observability/dashboard.md \
  && uv run python -m harness_maker.statusline < tests/data/mock-session.json | grep -E '🪙[0-9]+ \| 🎯[0-9]+ \| 🔄[0-9]+d'
```

---

### Phase 4: Anti-rot Pipeline (4-source crawl + adaptive threshold + manual confirm)

**Objective:** `/hm:refresh` 명령이 사용자 하네스에 렌더되어 주 1회 자동 + 수동 호출. 4 source 크롤 → adaptive filter → propose UI. **항상 manual confirm.**

**Research targets (autoloop Stage 1 자동 fetch):**
- arxiv API spec: https://info.arxiv.org/help/api/user-manual.html
- GitHub REST API releases endpoint: https://docs.github.com/en/rest/releases/releases
- GitHub API rate limits (unauthenticated 60/h): https://docs.github.com/en/rest/overview/rate-limits-for-the-rest-api
- OSV.dev API: https://google.github.io/osv.dev/api/
- Anthropic news index page (HTML scrape — RSS 없음): https://www.anthropic.com/news
- Claude Code release notes: https://github.com/anthropics/claude-code/releases
- feedparser library: https://feedparser.readthedocs.io/en/latest/
- httpx async client: https://www.python-httpx.org/

#### Tasks

- **Task 4.1: Crawler — Anthropic blog/changelog (HTML scrape)**
  - Do: `src/harness_maker/crawler/anthropic_blog.py` — `fetch_recent(since: datetime) -> list[CrawlItem]`. **Anthropic 는 공식 RSS 없음.** httpx 로 `https://www.anthropic.com/news` HTML 가져와 BeautifulSoup4 (의존성 추가) 또는 정규식으로 article 카드 파싱 → CrawlItem(title, url, published, summary). 캐시: `~/.cache/harness-maker/anthropic-blog.json` (12h TTL). 실패 시 graceful skip + 경고 로그.
  - Files: `src/harness_maker/crawler/anthropic_blog.py`, `tests/unit/crawler/test_anthropic_blog.py`, `pyproject.toml` (beautifulsoup4 추가)
  - Files: `src/harness_maker/crawler/anthropic_blog.py`, `tests/unit/crawler/test_anthropic_blog.py`
  - Done when: mock RSS feed 으로 호출 시 CrawlItem list 반환, 캐시 hit 시 네트워크 호출 X
  - Verify: `bash .claude-verify.sh phase_4_anthropic`
  - Commit: `feat(phase4): implement Anthropic blog crawler`

- **Task 4.2: Crawler — GitHub releases**
  - Do: `src/harness_maker/crawler/github_releases.py` — `fetch_releases(repo: str, since: datetime) -> list[CrawlItem]`. httpx 로 `api.github.com/repos/{repo}/releases` 호출 (unauthenticated). repos: anthropics/claude-code, obra/superpowers, Yeachan-Heo/oh-my-claudecode, scalarian/oh-my-codex, wshobson/agents, davila7/claude-code-templates, coleam00/Archon, affaan-m/everything-claude-code, HKUDS/OpenHarness. 캐시: `~/.cache/harness-maker/gh-{repo}.json` (24h TTL). rate limit 감지 시 graceful skip.
  - Files: `src/harness_maker/crawler/github_releases.py`, `tests/unit/crawler/test_github_releases.py`
  - Done when: mock 응답으로 CrawlItem list, rate limit 응답 시 빈 리스트 + 경고 로그
  - Verify: `bash .claude-verify.sh phase_4_github`
  - Commit: `feat(phase4): implement GitHub releases crawler with caching`

- **Task 4.3: Crawler — arxiv**
  - Do: `src/harness_maker/crawler/arxiv.py` — `fetch_recent(categories: list[str], terms: list[str], since: datetime) -> list[CrawlItem]`. arxiv API (export.arxiv.org/api/query) 호출. categories: cs.SE, cs.CL, cs.CR. terms: ["coding agent", "prompt engineering", "agent harness", "agent eval", "prompt injection"]. 캐시: `~/.cache/harness-maker/arxiv.json` (7d TTL).
  - Files: `src/harness_maker/crawler/arxiv.py`, `tests/unit/crawler/test_arxiv.py`
  - Done when: mock 응답으로 CrawlItem list, 캐시 hit 검증
  - Verify: `bash .claude-verify.sh phase_4_arxiv`
  - Commit: `feat(phase4): implement arxiv crawler with category+term filter`

- **Task 4.4: Crawler — OSV.dev**
  - Do: `src/harness_maker/crawler/osv_dev.py` — `query_cve(packages: list[Package]) -> list[Vulnerability]`. OSV.dev API. package-lock.json/Cargo.lock/requirements.txt 파싱.
  - Files: `src/harness_maker/crawler/osv_dev.py`, `tests/unit/crawler/test_osv_dev.py`
  - Done when: mock package list 로 Vulnerability list 반환
  - Verify: `bash .claude-verify.sh phase_4_osv`
  - Commit: `feat(phase4): implement OSV.dev CVE query`

- **Task 4.5: Relevance filter (adaptive threshold)**
  - Do: `src/harness_maker/relevance.py` — `score(item: CrawlItem, harness_yaml: dict, history: list) -> float`. LLM 호출 (Claude Code subscription). 입력: CrawlItem + harness.yaml 요약 + 과거 accept/reject 이력. 출력: applicability_score (0-1), risk (low/med/high), proposed_change. threshold = adaptive: start 0.7, accept >80% → -0.05, reject >50% → +0.05. mock LLM 으로 unit test.
  - Files: `src/harness_maker/relevance.py`, `tests/unit/test_relevance.py`
  - Done when: mock LLM 응답으로 점수 산출 및 threshold 적응 검증
  - Verify: `bash .claude-verify.sh phase_4_relevance`
  - Commit: `feat(phase4): implement adaptive relevance filter`

- **Task 4.6: research-crawler skill 템플릿**
  - Do: `templates/skills/research-crawler/SKILL.md.j2` — 사용자 하네스가 호출할 skill. description: "Crawl 4 sources for harness updates". 본문: Python 모듈 호출 절차.
  - Files: `templates/skills/research-crawler/SKILL.md.j2`
  - Done when: 렌더된 SKILL.md 가 valid frontmatter + description 포함
  - Verify: `bash .claude-verify.sh phase_4_skill_template`
  - Commit: `feat(phase4): add research-crawler skill template`

- **Task 4.7: relevance-filter skill 템플릿**
  - Do: `templates/skills/relevance-filter/SKILL.md.j2`
  - Files: `templates/skills/relevance-filter/SKILL.md.j2`
  - Done when: 렌더된 SKILL.md 정상
  - Verify: `bash .claude-verify.sh phase_4_filter_template`
  - Commit: `feat(phase4): add relevance-filter skill template`

- **Task 4.8: /hm:refresh 명령 템플릿 (manual confirm UI)**
  - Do: `templates/commands/hm/refresh.md.j2` — `/hm:refresh` 명령. 흐름: (1) 4 crawler 호출, (2) relevance filter, (3) threshold 통과 항목 → `.claude/observability/refresh/proposed-<date>.md` 생성, (4) 각 제안에 대해 AskUserQuestion (accept/reject/defer), (5) accept → 해당 .claude/ 자산 패치 + commit. **자동 적용 절대 X.**
  - Files: `templates/commands/hm/refresh.md.j2`
  - Done when: 렌더된 refresh.md 가 manual confirm 흐름 포함, autoloop 환경에선 propose 까지만 실행 (accept 시뮬레이션)
  - Verify: `bash .claude-verify.sh phase_4_refresh_template`
  - Commit: `feat(phase4): add /hm:refresh command template with manual confirm`

**Phase 4 Exit Criteria:**
```bash
uv run pytest tests/unit/crawler/ tests/unit/test_relevance.py -v \
  && uv run python -c "from harness_maker.crawler import anthropic_blog, github_releases, arxiv, osv_dev; print('all ok')" \
  && for tpl in research-crawler relevance-filter; do
       test -f templates/skills/$tpl/SKILL.md.j2 || exit 1
     done \
  && test -f templates/commands/hm/refresh.md.j2 \
  && grep -q "AskUserQuestion" templates/commands/hm/refresh.md.j2  # manual confirm 존재 확인
```

---

### Phase 5: Workflow Engine + Conditional Router + Modular Installer

**Objective:** atomic stage 7개 + 사용자 명명 fused workflow 가 사용자 하네스에 렌더. Conditional Router 가 변경 영역 따라 reviewer 선택. `--add` / `--remove` 모듈식 설치 동작.

**Research targets (autoloop Stage 1 자동 fetch):**
- Claude Code skill spec (SKILL.md frontmatter): https://code.claude.com/docs/en/skills
- Claude Code subagent spec (agent .md frontmatter): https://code.claude.com/docs/en/sub-agents
- Slash command subdirectory namespace (`commands/hm/<name>.md` → `/hm:<name>`): https://code.claude.com/docs/en/plugins-reference

#### Tasks

- **Task 5.1: Atomic stage prompt fragments**
  - Do: `templates/stages/{research,spec,plan,execute,review,wrapup,verify}.md.j2` 7개 작성. 각 fragment 는 ~50-150 행 (Side 한계 안). 각 stage 의 instructions 명확히. Variables: {{ project_name }}, {{ feature }}, {{ workflow_context }}.
  - Files: `templates/stages/*.md.j2`
  - Done when: 7 fragment 모두 valid Jinja2, 렌더 시 정상 출력
  - Verify: `bash .claude-verify.sh phase_5_stages`
  - Commit: `feat(phase5): add 7 atomic stage prompt fragments`

- **Task 5.2: Workflow fuse 로직**
  - Do: `src/harness_maker/workflow_fuse.py` — `fuse(stages: list[AtomicStage], workflow_name: str) -> str`. atomic stage fragment 들을 하나의 prompt 로 합성. 각 fragment 사이에 명확한 separator (`## Stage: <name>`) 삽입. 출력은 단일 `/hm:<workflow>` 명령 .md 파일 본문.
  - Files: `src/harness_maker/workflow_fuse.py`, `tests/unit/test_workflow_fuse.py`
  - Done when: 예시 workflow `dev=[plan,execute,review,wrapup]` 합성 → 4 fragment 가 순서대로 결합된 prompt 출력
  - Verify: `bash .claude-verify.sh phase_5_fuse`
  - Commit: `feat(phase5): implement workflow fusion logic`

- **Task 5.3: Atomic + workflow 명령 템플릿**
  - Do: `templates/commands/hm/atomic_command.md.j2` — Renderer 가 7 atomic 각각 렌더해 `commands/hm/{stage}.md` 생성. `templates/commands/hm/workflow_command.md.j2` — Renderer 가 harness.yaml.workflows 순회하며 각 workflow 에 대해 fused command 생성.
  - Files: `templates/commands/hm/atomic_command.md.j2`, `templates/commands/hm/workflow_command.md.j2`, `src/harness_maker/render.py` 확장 (workflow 루프 추가)
  - Done when: Side fixture 적용 시 commands/hm/ 에 7 atomic + N workflow 명령 모두 생성
  - Verify: `bash .claude-verify.sh phase_5_commands_render`
  - Commit: `feat(phase5): wire atomic + workflow command rendering`

- **Task 5.4: Conditional Router**
  - Do: `src/harness_maker/conditional_router.py` — `route_reviewers(changed_files: list[Path], preset_reviewers: list[str], routing: str) -> list[str]`. routing="conditional" 시 변경 파일 영역 매핑 (auth/.env→security, perf-critical→performance, ui/.tsx→ux, worker/thread/isr→concurrency). routing="always-all" 시 preset_reviewers 모두.
  - Files: `src/harness_maker/conditional_router.py`, `tests/unit/test_conditional_router.py`
  - Done when: changed_files 다양한 조합으로 expected reviewer set 반환
  - Verify: `bash .claude-verify.sh phase_5_router`
  - Commit: `feat(phase5): implement Conditional Router`

- **Task 5.5: conditional-router skill 템플릿 + agents**
  - Do: `templates/skills/conditional-router/SKILL.md.j2`. 9 agent template: `templates/agents/{code,security,performance,ux,concurrency}-reviewer.md.j2`, `consensus-arbiter.md.j2`, `autoloop-coder.md.j2`, `executor.md.j2`. 각 agent .md 에 frontmatter (name, description, permissions) — **Claude Code SubAgent permissions 의 정확한 frontmatter 스키마는 research target URL 의 doc 따라 확정 (allow/deny 필드명·구조 검증 필수)**. 권한 분리는 placeholder (Phase 8 에서 강화). security-auditor 는 Phase 7 에서 추가.
  - Files: `templates/skills/conditional-router/SKILL.md.j2`, `templates/agents/*.md.j2` (8개)
  - Done when: Production fixture 적용 시 .claude/agents/ 에 8 agent 생성
  - Verify: `bash .claude-verify.sh phase_5_agents`
  - Commit: `feat(phase5): add Conditional Router skill + 8 agent templates`

- **Task 5.6: Modular Installer (--add / --remove)**
  - Do: `src/harness_maker/modular_edit.py` — `add(component: str, target_dir: Path)`, `remove(component: str, target_dir: Path)`. component 형식: `reviewer:security`, `hook:pre-push-smoke`, `skill:tdd-conditional`. 추가/제거 시 (a) 해당 template 렌더, (b) `.claude/harness.yaml` 동기화 (예: reviewers.list 에 추가), (c) verifier 재실행. CLI 통합: `cli.py make --add ...`.
  - Files: `src/harness_maker/modular_edit.py`, `tests/unit/test_modular_edit.py`
  - Done when: Side fixture 에서 `make --add reviewer:security` → security-reviewer.md 추가, harness.yaml 갱신
  - Verify: `bash .claude-verify.sh phase_5_modular`
  - Commit: `feat(phase5): implement modular --add / --remove installer`

- **Task 5.7: Workflow naming + interview 통합**
  - Do: `src/harness_maker/interview.py` 확장 — Q-workflows 단계: preset 별 추천 workflow 시드 제시 (Side: dev+quick / Production: 위 + careful + audit), 사용자가 이름 확정/수정/제거/추가. workflow 이름 검증 (`[a-z][a-z0-9-]*`, 예약어 = atomic stage 이름 + "make" 차단). default_workflow 결정.
  - Files: `src/harness_maker/interview.py` (확장), `tests/unit/test_interview.py` (확장)
  - Done when: autoloop_mode 시 추천 시드 그대로 채택, interactive 시 mock 입력으로 workflow rename 검증
  - Verify: `bash .claude-verify.sh phase_5_workflow_interview`
  - Commit: `feat(phase5): wire workflow naming into interview`

**Phase 5 Exit Criteria:**
```bash
uv run pytest tests/unit/test_workflow_fuse.py tests/unit/test_conditional_router.py tests/unit/test_modular_edit.py tests/unit/test_interview.py -v \
  && uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop \
  && for stage in research spec plan execute review wrapup verify; do
       test -f tests/fixtures/side-python-cli/.claude/commands/hm/$stage.md || exit 1
     done \
  && test -f tests/fixtures/side-python-cli/.claude/commands/hm/dev.md \
  && uv run python -m harness_maker.cli make tests/fixtures/prod-tauri-app --autoloop --add reviewer:security \
  && test -f tests/fixtures/prod-tauri-app/.claude/agents/security-reviewer.md
```

---

### Phase 6: Autoloop driver + Verify-before-completion gate

**Objective:** `/hm:loop` 명령이 사용자 하네스에 렌더되어 자율 반복 동작. `/hm:verify` 가 wrapup 직전 자동 호출되는 gate skill 동작.

**Research targets (autoloop Stage 1 자동 fetch):**
- 본 repo 의 autoloop 패턴 reference (자족적, vault 의존 X): docs/reference/autoloop-pattern.md
- AHE — Agentic Harness Engineering: https://arxiv.org/abs/2604.25850
- Inside the Scaffold (5 loop primitives): https://arxiv.org/abs/2604.03515
- superpowers verify-before-completion 패턴: https://github.com/obra/superpowers

#### Tasks

- **Task 6.1: Autoloop driver 로직**
  - Do: `src/harness_maker/autoloop_driver.py` — `run(goal: str, args: dict)`. parse_goal → feature_list. while not converged: next_feature → workflow 실행 (fused command 호출 시뮬레이션) → state update. safety: iter % 5 == 0 시 ping, 3회 연속 실패 시 stop, time/iter cap. token 무제한.
  - Files: `src/harness_maker/autoloop_driver.py`, `tests/unit/test_autoloop_driver.py`
  - Done when: mock workflow 실행으로 수렴 시뮬레이션, dry-run 모드에서 디스크 변경 0
  - Verify: `bash .claude-verify.sh phase_6_driver`
  - Commit: `feat(phase6): implement autoloop driver`

- **Task 6.2: /hm:loop 명령 템플릿**
  - Do: `templates/commands/hm/loop.md.j2` — autoloop_driver 호출. argparse: `<goal>` (required), `--time 8h`, `--max-iter 30`, `--workflow <name>`, `--convergence "<criterion>"`, `--dry-run`.
  - Files: `templates/commands/hm/loop.md.j2`
  - Done when: 렌더된 loop.md 정상, autoloop 인자 파싱 명세 명확
  - Verify: `bash .claude-verify.sh phase_6_loop_template`
  - Commit: `feat(phase6): add /hm:loop command template`

- **Task 6.3: autoloop-coder + autoloop-driver skill 템플릿**
  - Do: `templates/agents/autoloop-coder.md.j2` — autoloop 의 main worker agent. `templates/skills/autoloop-driver/SKILL.md.j2` — driver 호출 가이드.
  - Files: `templates/agents/autoloop-coder.md.j2`, `templates/skills/autoloop-driver/SKILL.md.j2`
  - Done when: 렌더 후 frontmatter 검증 통과
  - Verify: `bash .claude-verify.sh phase_6_autoloop_assets`
  - Commit: `feat(phase6): add autoloop-coder agent + autoloop-driver skill templates`

- **Task 6.4: Verify-before-completion 게이트 구현**
  - Do: `templates/skills/verify-before-completion/SKILL.md.j2` — /hm:wrapup 또는 autoloop iter 완료 직전 자동 호출되는 skill. 체크리스트: PLAN/SPEC 충족 / 회귀 게이트 / Health 점수 -5 이내 / Anti-rot pending defer 또는 처리 / 보안 high finding 0건 / Worktree merge 가능. 각 체크는 bash 또는 Python 호출. 실패 시 wrapup 차단.
  - Files: `templates/skills/verify-before-completion/SKILL.md.j2`
  - Done when: SKILL.md 가 6 체크 모두 명시, 각 체크에 검증 명령 명확
  - Verify: `bash .claude-verify.sh phase_6_verify_gate`
  - Commit: `feat(phase6): add verify-before-completion gate skill`

- **Task 6.5: ai-readiness-rubric + agent-quality-rubric skill 템플릿**
  - Do: `templates/skills/ai-readiness-rubric/SKILL.md.j2` — Health 6-dim 계산 가이드 (readiness.py 호출). `templates/skills/agent-quality-rubric/SKILL.md.j2` — Platinum/Gold/Silver/Bronze 평가 가이드 (agent_quality.py 호출). Bronze 등급 자동으로 anti-rot patch 후보 등록 절차 명시.
  - Files: `templates/skills/ai-readiness-rubric/SKILL.md.j2`, `templates/skills/agent-quality-rubric/SKILL.md.j2`
  - Done when: 렌더 후 valid frontmatter + description
  - Verify: `bash .claude-verify.sh phase_6_health_skills`
  - Commit: `feat(phase6): add Health + Agent quality rubric skills`

**Phase 6 Exit Criteria:**
```bash
uv run pytest tests/unit/test_autoloop_driver.py -v \
  && uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop \
  && test -f tests/fixtures/side-python-cli/.claude/commands/hm/loop.md \
  && test -f tests/fixtures/side-python-cli/.claude/skills/verify-before-completion/SKILL.md \
  && test -f tests/fixtures/side-python-cli/.claude/skills/ai-readiness-rubric/SKILL.md \
  && test -f tests/fixtures/side-python-cli/.claude/skills/agent-quality-rubric/SKILL.md \
  && test -f tests/fixtures/side-python-cli/.claude/agents/autoloop-coder.md
```

---

### Phase 7: Worktree Isolation + 5 Security Gates

**Objective:** `/hm:execute` 가 자동 git worktree 안에서 동작. 5 security gate 모두 검출 가능 (sandbox 시드된 vulnerability 사용).

**Research targets (autoloop Stage 1 자동 fetch):**
- git worktree CLI: https://git-scm.com/docs/git-worktree
- gitleaks 패턴 카탈로그 (regex 참고용): https://github.com/gitleaks/gitleaks
- OSV.dev API query format: https://google.github.io/osv.dev/api/
- CVE-2025-59536 (skill poisoning): https://arxiv.org/abs/2604.03081
- OWASP LLM prompt injection: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- Archon worktree 패턴 참고: https://github.com/coleam00/Archon
- ECC AgentShield 보안 스캐폴딩 패턴: https://github.com/affaan-m/everything-claude-code

#### Tasks

- **Task 7.1: Worktree 라이프사이클**
  - Do: `src/harness_maker/worktree.py` — `create(workflow: str, base_dir: Path) -> Path` (`.worktrees/<workflow>-<ts>/` 생성), `cleanup(wt_path: Path, on_success: bool)`, `merge(wt_path: Path, strategy: str)`. git worktree CLI 호출. .gitignore 자동 추가 검증.
  - Files: `src/harness_maker/worktree.py`, `tests/unit/test_worktree.py`
  - Done when: temp git repo 에서 worktree 생성·cleanup·merge 동작 확인
  - Verify: `bash .claude-verify.sh phase_7_worktree`
  - Commit: `feat(phase7): implement git worktree lifecycle`

- **Task 7.2: worktree-isolator skill 템플릿**
  - Do: `templates/skills/worktree-isolator/SKILL.md.j2` — `/hm:execute` 호출 시 자동 worktree 생성, 변경 격리, 성공 시 cleanup 절차. harness.yaml.worktree 설정 참조.
  - Files: `templates/skills/worktree-isolator/SKILL.md.j2`
  - Done when: 렌더된 SKILL.md 가 4-step 흐름 명시
  - Verify: `bash .claude-verify.sh phase_7_worktree_skill`
  - Commit: `feat(phase7): add worktree-isolator skill template`

- **Task 7.3: Security gate — secrets**
  - Do: `src/harness_maker/secscan/secrets.py` — `scan(target_dir: Path) -> list[Finding]`. regex 패턴: AWS_ACCESS_KEY, GitHub PAT, Anthropic API key, .env 누출, generic high-entropy strings. severity: high.
  - Files: `src/harness_maker/secscan/secrets.py`, `tests/unit/test_secrets_scan.py`
  - Done when: seeded 가짜 secret 들을 detect, 빈 디렉토리는 0 finding
  - Verify: `bash .claude-verify.sh phase_7_secrets`
  - Commit: `feat(phase7): implement secrets scanner`

- **Task 7.4: Security gate — permissions**
  - Do: `src/harness_maker/secscan/permissions.py` — `scan(settings_json: Path) -> list[Finding]`. settings.json 의 `permissions.allow` 안의 과확장 패턴 검출 (`Bash(*)`, `Write(/**)` 등). severity: high (catch-all) / medium (broad path).
  - Files: `src/harness_maker/secscan/permissions.py`, `tests/unit/test_permissions_scan.py`
  - Done when: catch-all 검출, 정상 narrow 패턴은 finding 0
  - Verify: `bash .claude-verify.sh phase_7_permissions`
  - Commit: `feat(phase7): implement permissions scanner`

- **Task 7.5: Security gate — hook injection**
  - Do: `src/harness_maker/secscan/hook_injection.py` — `scan(hooks_json: Path) -> list[Finding]`. 위험 패턴 list: `rm -rf`, `curl <url> | sh`, `eval`, `wget ... | bash`. AST 또는 regex.
  - Files: `src/harness_maker/secscan/hook_injection.py`, `tests/unit/test_hook_injection.py`
  - Done when: seeded 위험 hook 검출, 정상 hook 0 finding
  - Verify: `bash .claude-verify.sh phase_7_hook_injection`
  - Commit: `feat(phase7): implement hook injection scanner`

- **Task 7.6: Security gate — dependency CVEs**
  - Do: `src/harness_maker/secscan/dependency_cves.py` — `scan(target_dir: Path) -> list[Finding]`. package-lock.json/Cargo.lock/requirements.txt/uv.lock 파싱 → package list → osv_dev.query_cve(). severity: high (CVSS ≥ 7) / medium (4-6.9) / low (<4).
  - Files: `src/harness_maker/secscan/dependency_cves.py`, `tests/unit/test_cve_scan.py`
  - Done when: mock OSV 응답으로 Vulnerability list, severity 분류 정확
  - Verify: `bash .claude-verify.sh phase_7_cve`
  - Commit: `feat(phase7): implement dependency CVE scanner`

- **Task 7.7: Security gate — prompt injection**
  - Do: `src/harness_maker/secscan/prompt_injection.py` — `scan(text: str) -> list[Finding]`. hidden instruction 패턴 (zero-width chars, base64 instructions, "ignore previous", "system:" injection). severity: high.
  - Files: `src/harness_maker/secscan/prompt_injection.py`, `tests/unit/test_prompt_injection.py`
  - Done when: seeded 가짜 injection 검출, 정상 텍스트 0 finding
  - Verify: `bash .claude-verify.sh phase_7_prompt_injection`
  - Commit: `feat(phase7): implement prompt injection scanner`

- **Task 7.8: Security scanner orchestrator + skill + agent**
  - Do: `src/harness_maker/security_scanner.py` — `scan_all(target_dir: Path, harness_config: dict) -> list[Finding]`. 5 gate 호출 → findings → `.claude/observability/security/findings-<date>.jsonl` 저장. on_finding 정책 적용 (high=block/warn/allow). `templates/skills/security-scanner/SKILL.md.j2`, `templates/agents/security-auditor.md.j2`.
  - Files: `src/harness_maker/security_scanner.py`, `templates/skills/security-scanner/SKILL.md.j2`, `templates/agents/security-auditor.md.j2`, `tests/unit/test_security_scanner.py`
  - Done when: 5 seeded vulnerability 모두 검출, findings.jsonl 생성, security-auditor agent 렌더 정상
  - Verify: `bash .claude-verify.sh phase_7_orchestrator`
  - Commit: `feat(phase7): wire security scanner orchestrator + skill + auditor agent`

- **Task 7.9: harness.yaml schema 확장 (worktree + security)**
  - Do: `templates/harness-yaml/{Side,Production}.yaml.j2` 에 `worktree:` 와 `security:` 섹션 추가. Side: worktree.scope=[execute], security.on_finding.high=warn. Production: scope=[execute, plan], on_finding.high=block.
  - Files: `templates/harness-yaml/{Side,Production}.yaml.j2`
  - Done when: 렌더된 harness.yaml 이 Pydantic HarnessConfig validation 통과
  - Verify: `bash .claude-verify.sh phase_7_yaml_schema`
  - Commit: `feat(phase7): extend harness.yaml schema with worktree + security`

**Phase 7 Exit Criteria:**
```bash
uv run pytest tests/unit/test_worktree.py tests/unit/test_secrets_scan.py tests/unit/test_permissions_scan.py tests/unit/test_hook_injection.py tests/unit/test_cve_scan.py tests/unit/test_prompt_injection.py tests/unit/test_security_scanner.py -v \
  && bash .claude-verify.sh phase_7_seeded_vulns
```

---

### Phase 8: Context Lint + Privilege Separation + Provenance Frontmatter

**Objective:** Renderer 에 context lint 통합 (verbose 차단). Reviewer agent 의 settings.json permissions 권한 분리. 모든 generated 파일 provenance frontmatter (Phase 2 에서 부분 구현 → 여기서 검증·refresh hash 비교).

**Research targets (autoloop Stage 1 자동 fetch):**
- Claude Code settings.json permissions schema (allow/deny 형식): https://code.claude.com/docs/en/settings
- Evaluating AGENTS.md (verbose context 실증): https://arxiv.org/abs/2602.11988
- OpenClaw — Privilege Separation (권한 분리 ASR 0.31% vs 14%): https://arxiv.org/abs/2603.13424
- Supply-Chain Poisoning (provenance 도입 근거): https://arxiv.org/abs/2604.03081
- AgentBound capability framework: https://arxiv.org/abs/2510.21236

#### Tasks

- **Task 8.1: Context Lint 구현**
  - Do: `src/harness_maker/context_lint.py` — `lint(file_path: Path, asset_type: str, preset: Preset) -> list[str]` (warnings). 한계: CLAUDE.md (Side 200/Prod 500), agent (100/200), skill SKILL.md (50/150), workflow command (300/600). 초과 시 자동 요약 제안.
  - Files: `src/harness_maker/context_lint.py`, `tests/unit/test_context_lint.py`
  - Done when: 초과 파일에 warning, 정상 파일 0 warning
  - Verify: `bash .claude-verify.sh phase_8_context_lint`
  - Commit: `feat(phase8): implement context lint with length thresholds`

- **Task 8.2: Renderer 에 context lint 통합**
  - Do: `src/harness_maker/render.py` 확장 — Apply 직전 렌더된 모든 파일에 context_lint 호출. warning 출력. `harness.yaml.context_lint.strict: true` 시 초과 = error (Apply 차단). default false.
  - Files: `src/harness_maker/render.py` (확장), `tests/unit/test_render.py` (확장)
  - Done when: 의도적 verbose 템플릿 시 warning 출력, strict=true 시 차단
  - Verify: `bash .claude-verify.sh phase_8_render_lint`
  - Commit: `feat(phase8): wire context lint into renderer`

- **Task 8.3: context-linter skill 템플릿**
  - Do: `templates/skills/context-linter/SKILL.md.j2` — 사용자 하네스 안의 자가 lint skill (`/hm:execute` 또는 `/hm:wrapup` 직전 호출 가능).
  - Files: `templates/skills/context-linter/SKILL.md.j2`
  - Done when: 렌더 통과
  - Verify: `bash .claude-verify.sh phase_8_lint_skill`
  - Commit: `feat(phase8): add context-linter skill template`

- **Task 8.4: 권한 분리 — Reviewer agents permissions**
  - Do: `templates/agents/{code,security,security-auditor,performance,ux,concurrency}-reviewer.md.j2` 의 frontmatter 에 read-only permissions. **반드시 Claude Code SubAgent 공식 spec (https://code.claude.com/docs/en/sub-agents + https://code.claude.com/docs/en/settings) 의 정확한 schema 확인 후 적용** — 만약 SubAgent frontmatter 가 `tools: [Read, Grep]` 식 allowlist 만 지원하고 deny list 미지원이면, allowlist 만으로 read-only 강제 (Write/Edit/Bash exec 도구 자체 제외). 6 reviewer 일관 적용.
  - Files: `templates/agents/{code,security,security-auditor,performance,ux,concurrency}-reviewer.md.j2`
  - Done when: 렌더된 agent .md 의 frontmatter 에 deny 리스트 존재
  - Verify: `bash .claude-verify.sh phase_8_reviewer_perms`
  - Commit: `feat(phase8): enforce read-only permissions on all reviewer agents`

- **Task 8.5: 권한 분리 — Executor agent**
  - Do: `templates/agents/executor.md.j2` — write 가능하지만 `.worktrees/**` 안에서만. `permissions.allow: [Read(*), Grep(*), Write(.worktrees/**), Edit(.worktrees/**), Bash(npm test:*), Bash(pytest:*), Bash(uv run:*), Bash(cargo test:*)]`, `deny: [Write(/etc/**), Write(~/.ssh/**), Write(~/.aws/**), Bash(curl * | sh), Bash(eval *), Bash(rm -rf /:*)]`. autoloop-coder.md.j2 도 동일 정책.
  - Files: `templates/agents/executor.md.j2`, `templates/agents/autoloop-coder.md.j2` (확장)
  - Done when: 렌더 후 권한 정책 검증
  - Verify: `bash .claude-verify.sh phase_8_executor_perms`
  - Commit: `feat(phase8): add executor agent with worktree-bounded write permissions`

- **Task 8.6: Provenance 검증 + refresh hash 비교**
  - Do: `src/harness_maker/provenance.py` — `verify_file(file_path: Path) -> tuple[bool, str]` (hash 일치 여부, source_template). `compute_hash(file_path: Path) -> str`. `parse_frontmatter(file_path: Path) -> dict`. `/hm:refresh` 시 사용자 수정 감지: 각 파일의 frontmatter content_hash vs 실제 hash 비교 → 불일치 시 사용자 confirm 필수 (autoloop 환경에선 KEEP 자동).
  - Files: `src/harness_maker/provenance.py`, `tests/unit/test_provenance.py`
  - Done when: 정상 generated 파일 verify 통과, 의도적 수정 시 mismatch 검출
  - Verify: `bash .claude-verify.sh phase_8_provenance_verify`
  - Commit: `feat(phase8): implement provenance hash verification`

- **Task 8.7: Reconciler + refresh 의 provenance 연동**
  - Do: `src/harness_maker/reconcile.py` 확장 — frontmatter 있는 기존 파일 vs 신규 blueprint hash 비교 → 일치 시 자동 REPLACE, 불일치 시 KEEP. `/hm:refresh` 시 모든 .claude/ 자산 hash 검증 → 사용자 수정 파일은 silent overwrite 차단.
  - Files: `src/harness_maker/reconcile.py` (확장), `templates/commands/hm/refresh.md.j2` (확장)
  - Done when: brownfield fixture 에서 hash-based 자동 분류 검증
  - Verify: `bash .claude-verify.sh phase_8_reconcile_provenance`
  - Commit: `feat(phase8): wire provenance into Reconciler + /hm:refresh`

**Phase 8 Exit Criteria:**
```bash
uv run pytest tests/unit/test_context_lint.py tests/unit/test_provenance.py tests/unit/test_reconcile.py -v \
  && uv run python -m harness_maker.cli make tests/fixtures/prod-tauri-app --autoloop \
  && python -c "
import json, yaml
from pathlib import Path
for agent in ['code-reviewer','security-reviewer','security-auditor','performance-reviewer','ux-reviewer','concurrency-reviewer']:
    md = Path('tests/fixtures/prod-tauri-app/.claude/agents/' + agent + '.md').read_text()
    fm = yaml.safe_load(md.split('---')[1])
    assert 'Write(*)' in fm['permissions']['deny'], agent + ' missing Write deny'
    assert 'Edit(*)' in fm['permissions']['deny'], agent + ' missing Edit deny'
print('reviewer permission separation OK')
"
```

---

### Phase 9: Dogfood — sandbox 적용

**Objective:** harness-maker 자체를 1개 sandbox 프로젝트에 적용해 모든 R1-R6 + 모든 메커니즘 동작 검증. Python CLI entry + Claude Code 플러그인 entry 둘 다 검증.

**Research targets:** None — Phase 9 는 integration test only. 외부 doc fetch 불필요.

#### Tasks

- **Task 9.1: Sandbox 프로젝트 생성**
  - Do: `tests/e2e/sandbox/` — 빈 Python 프로젝트 디렉토리. pyproject.toml + 1 hello_world.py. git init.
  - Files: `tests/e2e/sandbox/`, `tests/e2e/sandbox/pyproject.toml`, `tests/e2e/sandbox/hello_world.py`
  - Done when: 디렉토리 + 시드 파일 존재, git init 됨
  - Verify: `bash .claude-verify.sh phase_9_sandbox_init`
  - Commit: `test(phase9): create sandbox project for dogfood`

- **Task 9.2: /harness-maker:make 적용**
  - Do: sandbox 에서 `uv run python -m harness_maker.cli make tests/e2e/sandbox --autoloop` 실행. Side preset 적용. 모든 자산 생성 확인 (harness.yaml, commands/hm/*, skills/, agents/, hooks/, observability/dashboard.md).
  - Files: `tests/e2e/sandbox/.claude/` (생성)
  - Done when: .claude/ 디렉토리 가 25-30 파일, 모두 provenance frontmatter
  - Verify: `bash .claude-verify.sh phase_9_apply`
  - Commit: `test(phase9): apply harness-maker to sandbox`

- **Task 9.3: 생성된 명령 실행 검증**
  - Do: e2e test — 사용자 하네스의 `/hm:quick`, `/hm:dev`, `/hm:loop`, `/hm:monitor`, `/hm:refresh` 각각이 호출 가능한지 확인 (실제 LLM 호출 X — 명령 파일 존재 + frontmatter valid + parseable). `/hm:execute` 가 worktree 격리 동작 (mock).
  - Files: `tests/e2e/test_dogfood_sandbox.py`
  - Done when: 5+ 명령 모두 valid + parseable + worktree skill 호출 시 .worktrees/ 생성
  - Verify: `bash .claude-verify.sh phase_9_commands`
  - Commit: `test(phase9): verify all generated commands callable`

- **Task 9.4: Security gate 동작 검증**
  - Do: sandbox 에 의도적으로 시드: 가짜 .env (AWS_ACCESS_KEY=AKIA...), settings.json 에 `Bash(*)` 과확장, hooks.json 에 `curl url | sh`, requirements.txt 에 알려진 vulnerable 패키지, 코드에 hidden instruction. `/hm:verify` 또는 직접 security_scanner.scan_all 호출 → 5 finding 모두 검출.
  - Files: `tests/e2e/sandbox/.env.seeded`, etc. + `tests/e2e/test_dogfood_sandbox.py` (확장)
  - Done when: 5 finding 모두 정확히 분류
  - Verify: `bash .claude-verify.sh phase_9_security`
  - Commit: `test(phase9): verify all 5 security gates detect seeded vulns`

- **Task 9.5: 3 지표 출력 검증**
  - Do: sandbox 에서 mock metrics.jsonl 시딩 후 `python -m harness_maker.statusline` 호출 → expected 형식 출력. `/hm:monitor` 호출 → dashboard.md 갱신, 3 metric 모두 표시.
  - Files: `tests/e2e/test_dogfood_sandbox.py` (확장)
  - Done when: statusline 출력에 🪙·🎯·🔄 모두 존재, dashboard.md 에 Health 6-dim + Agent quality 섹션 존재
  - Verify: `bash .claude-verify.sh phase_9_metrics`
  - Commit: `test(phase9): verify 3 metrics displayed correctly`

- **Task 9.6: Reconcile 검증 (Brownfield)**
  - Do: sandbox `.claude/` 에 의도적으로 사용자 수정 파일 1개 생성 (hash 깨뜨리기). `make` 재실행 → reconcile 가 KEEP 결정 (autoloop 자동). 사용자 수정 파일 보존 확인.
  - Files: `tests/e2e/test_dogfood_sandbox.py` (확장)
  - Done when: 사용자 수정 파일 그대로, 다른 파일은 갱신
  - Verify: `bash .claude-verify.sh phase_9_reconcile`
  - Commit: `test(phase9): verify Brownfield reconcile preserves user edits`

- **Task 9.7: Plugin entry 검증 (Claude Code 호출)**
  - Do: subprocess 로 `claude --plugin-dir /home/noel/harness-maker -p "/harness-maker:make tests/e2e/sandbox-plugin-test --autoloop"` 실행 (또는 `--dangerously-skip-permissions` 필요 시). Claude Code 가 본 플러그인 로드 → /harness-maker:make 명령 라우팅 → `python -m harness_maker.cli make` 호출 → sandbox-plugin-test/.claude/ 생성 검증. **Python CLI entry 와 Plugin entry 둘 다 동일 결과** 보장.
  - Files: `tests/e2e/test_plugin_entry.py`, `tests/e2e/sandbox-plugin-test/`
  - Done when: subprocess exit 0, sandbox-plugin-test/.claude/harness.yaml 존재, Python CLI 결과와 file count·content 일치 (timestamp 무시)
  - Verify: `bash .claude-verify.sh phase_9_plugin_entry`
  - Commit: `test(phase9): verify Claude Code plugin entry matches CLI entry`

**Phase 9 Exit Criteria:**
```bash
uv run pytest tests/e2e/ -v \
  && test -f tests/e2e/sandbox/.claude/harness.yaml \
  && test -f tests/e2e/sandbox/.claude/commands/hm/loop.md \
  && test -f tests/e2e/sandbox/.claude/commands/hm/monitor.md \
  && test -f tests/e2e/sandbox/.claude/commands/hm/refresh.md \
  && test -f tests/e2e/sandbox/.claude/observability/dashboard.md \
  && test -f tests/e2e/sandbox-plugin-test/.claude/harness.yaml  # plugin entry path
```

---

### Phase 10: Polish (README + Docs + Final Cleanup)

**Objective:** 외부 공개 가능한 상태. README 완성, CONTRIBUTING, 최종 lint/type/test 0 error.

**Research targets (autoloop Stage 1 자동 fetch):**
- Claude Code marketplace 등록: https://code.claude.com/docs/en/plugin-marketplaces
- README best practices: https://www.makeareadme.com/

#### Tasks

- **Task 10.1: README.md 완성**
  - Do: 1-page README — 프로젝트 소개 (1단락), Quick Start (`uv sync && claude --plugin-dir . && /harness-maker:make`), 기능 요약 (단일 명령, 2 preset, 3 metric, anti-rot, worktree, security), 비교표 (vs ohmyclaudecode/superpowers/Archon — 차별점 짧게), License.
  - Files: `README.md` (확장)
  - Done when: README 가 Quick Start + 기능 요약 + 비교 + License 모두 포함
  - Verify: `bash .claude-verify.sh phase_10_readme`
  - Commit: `docs(phase10): write comprehensive README`

- **Task 10.2: CONTRIBUTING.md**
  - Do: `docs/CONTRIBUTING.md` — 기여 가이드. 새 skill/agent 템플릿 추가 방법, 새 preset 추가 (yaml schema 확장), 테스트 작성 패턴, PR 체크리스트.
  - Files: `docs/CONTRIBUTING.md`
  - Done when: 외부 기여자가 따라할 수 있는 가이드 완성
  - Verify: `bash .claude-verify.sh phase_10_contributing`
  - Commit: `docs(phase10): write contributing guide`

- **Task 10.3: ARCHITECTURE.md (도메인 지식 추출)**
  - Do: `docs/ARCHITECTURE.md` — TECH_SPEC Section 3 의 메커니즘 13개를 외부 독자가 이해할 수 있게 풀어쓴 문서. 시스템 다이어그램, data flow, 각 메커니즘의 의도.
  - Files: `docs/ARCHITECTURE.md`
  - Done when: 외부 독자가 코드 안 봐도 시스템 이해 가능
  - Verify: `bash .claude-verify.sh phase_10_architecture`
  - Commit: `docs(phase10): write ARCHITECTURE.md`

- **Task 10.4: 최종 lint + type + test**
  - Do: 전체 코드베이스 ruff format 적용, ruff check 0 error, mypy --strict 0 error, pytest 모든 테스트 통과. pyproject.toml version bump? (유지 — 0.1.0).
  - Files: 전체
  - Done when: lint 0, type 0, pytest 0 fail
  - Verify: `bash .claude-verify.sh phase_10_final_quality`
  - Commit: `chore(phase10): final cleanup — lint, type, test all green`

- **Task 10.5: Marketplace prep (optional)**
  - Do: `.claude-plugin/plugin.json` 에 homepage, repository (placeholder), keywords 추가. README 에 marketplace 등록 절차 placeholder.
  - Files: `.claude-plugin/plugin.json`, `README.md` (확장)
  - Done when: plugin.json 이 marketplace 호환 schema (Claude Code 공식 spec 참조)
  - Verify: `bash .claude-verify.sh phase_10_marketplace`
  - Commit: `feat(phase10): prepare plugin.json for marketplace submission`

**Phase 10 Exit Criteria:**
```bash
uv run ruff check src/ tests/ \
  && uv run ruff format --check src/ tests/ \
  && uv run mypy --strict src/ \
  && uv run pytest tests/ -v --tb=short \
  && test -f README.md && test -f docs/CONTRIBUTING.md && test -f docs/ARCHITECTURE.md \
  && grep -q "Quick Start" README.md \
  && grep -q "license" .claude-plugin/plugin.json
```

---

## 5. Final Acceptance Criteria

### R1-R6 검증 (모든 핵심 요구사항)

- [ ] **R1 Locale-first**: 빈 sandbox 에서 `cli make --interactive` 호출 시 Q1 (한국어/English) 가 첫 질문. `.claude/harness.yaml` 에 locale 키 저장.
- [ ] **R2 Anti-rot**: 4 source crawler 모두 호출 가능. relevance filter adaptive threshold 동작. `/hm:refresh` 가 propose 까지 진행 후 manual confirm 대기 (자동 적용 절대 X).
- [ ] **R3 Monitoring**: statusline 에 🪙효율% · 🎯Health · 🔄fresh d 모두 표시. dashboard.md 에 Health 6-dim + Agent quality drill-down (Platinum/Gold/Silver/Bronze) 섹션 포함. metrics.jsonl 외부 전송 0.
- [ ] **R4 Workflow**: 7 atomic stage (`/hm:research` ... `/hm:verify`) 자동 노출. 사용자 명명 fused workflow N개 (`/hm:dev`, `/hm:careful`) 단일 명령으로 호출 가능. atomic vs fused 둘 다 동작.
- [ ] **R5 Autoloop**: `/hm:loop "<goal>"` 호출 시 driver 가 token 무제한, 8h/30iter 디폴트로 자율 반복. dry-run 모드 동작. iter 5 ping, 3-fail stop.
- [ ] **R6 Per-project preset**: 2 preset (Side/Production) 인터뷰 → 10+ 차원 override → harness.yaml 에 저장. 4 fixture 모두 expected blueprint 일치.

### 메커니즘 검증

- [ ] (M1) Profiler→Interviewer→Synthesizer→Renderer pipeline 4 fixture 통과
- [ ] (M2) Reconciler 가 hash-based 자동 분류, backup 디렉토리 생성
- [ ] (M3) Workflow Engine atomic + fused 모두 렌더
- [ ] (M4) Anti-rot 4 source 호출 가능 + adaptive threshold 적응
- [ ] (M5) 3 metrics 실시간 + Health 6-dim + Agent quality drill-down
- [ ] (M6) Conditional Router 가 changed_files → reviewer 자동 선택
- [ ] (M7) Autoloop driver state machine 동작
- [ ] (M8) Verify-before-completion 가 wrapup 직전 6 체크 모두 실행
- [ ] (M9) Worktree 격리 — `.worktrees/<workflow>-<ts>/` 생성·cleanup
- [ ] (M10) 5 Security Gates 모두 seeded vulnerability 검출
- [ ] (M11) Context Lint 가 verbose 차단
- [ ] (M12) Privilege Separation — reviewer settings.json 에 `Write` deny, executor 에 `Write(.worktrees/**)` allow
- [ ] (M13) Provenance Frontmatter — 모든 generated 파일에 hash + version, refresh 시 사용자 수정 감지

### 자산 존재 검증

- [ ] Skills (10): verify-before-completion, conditional-router, ai-readiness-rubric, agent-quality-rubric, research-crawler, relevance-filter, autoloop-driver, worktree-isolator, security-scanner, context-linter
- [ ] Agents (9): code-reviewer, security-reviewer, security-auditor, performance-reviewer, ux-reviewer, concurrency-reviewer, consensus-arbiter, autoloop-coder, executor
- [ ] Commands (10+): /hm:research, spec, plan, execute, review, wrapup, verify (atomic 7개) + /hm:loop, /hm:monitor, /hm:refresh (메타 3개) + N user workflows
- [ ] Hooks: hooks.json 에 statusLine + telemetry-collector
- [ ] Templates: harness-yaml/{Side,Production} + claude-md × {ko,en} × 2 preset + memory × {failures,wiki} × {ko,en} + settings × 2 preset + dashboard × {ko,en}

### Verification Script (`.claude-verify.sh`)

상세는 `.claude-verify.sh all` 참조. 모든 체크는 phase 별 + final all 두 가지 모드 지원.

```bash
bash .claude-verify.sh all
# 위 모든 항목을 체크 → exit 0 = 모두 통과 / non-zero = 실패 항목 출력
```

---

## 6. Risks & Decisions

### Architecture Decision Records

- **ADR-1: Python only (Bash 사용 금지)**
  - Context: 초기 spec 은 Bash + Python 혼용
  - Decision: Python 단일 — Bash 제거. statusline 도 `python -m harness_maker.statusline` 호출.
  - Rationale: 일관성, type checking, test framework 통합. WSL2 환경 안정성.

- **ADR-2: 단일 메타-툴 명령**
  - Context: 초기 spec 은 /harness-maker:make + refresh + audit + monitor + loop + add 6개 명령
  - Decision: `/harness-maker:make` 단 1개. audit/add/remove/promote 는 플래그.
  - Rationale: "메타-툴은 생성기" 원칙. /loop /monitor /refresh 등 일상 명령은 사용자 하네스 안에 렌더 (`/hm:` prefix).

- **ADR-3: /hm: prefix (subdirectory namespace 활용)**
  - Context: 사용자가 직접 만든 명령과 ownership 구별 필요
  - Decision: `.claude/commands/hm/<name>.md` → `/hm:<name>`. 사용자 명령은 prefix 없이 `.claude/commands/<name>.md` → `/<name>`.
  - Rationale: Manifest tracking 불필요. 자연스러운 ownership 분리.

- **ADR-4: Workflow = Prompt Fusion (사용자 명명)**
  - Context: spec/task methodology 2x2 매트릭스로 시작
  - Decision: 일반화 — 7 atomic stage + N 사용자 명명 fused workflow. Renderer 가 stage prompt fragment 합성해 단일 command 생성.
  - Rationale: human-in-the-loop 최소화 (1 입력 → 1 turn). 사용자가 도메인 맞춤 workflow 명명.

- **ADR-5: 100% local telemetry**
  - Context: external observability 가능
  - Decision: metrics.jsonl 은 .claude/observability/ 에만, 외부 전송 0.
  - Rationale: 프라이버시·신뢰. anti-rot 의 서비스 호출은 user-initiated 만.

- **ADR-6: Anti-rot 항상 manual confirm**
  - Context: low-risk auto-apply 옵션 검토
  - Decision: 모든 risk 등급에서 사용자 confirm 강제. auto_apply=false 고정.
  - Rationale: silent change 방지. K1 (잘못된 patch) 위험 완화.

- **ADR-7: Worktree per execute (Archon/superpowers/OMX 표준)**
  - Context: 변경 격리 방법
  - Decision: `/hm:execute` 자동 git worktree 생성, 성공 시 cleanup.
  - Rationale: main branch 오염 방지. autoloop 매 iter 격리. 산업 표준.

- **ADR-8: 권한 분리 아키텍처 (OpenClaw)**
  - Context: prompt injection 방어
  - Decision: reviewer = Read+Grep only / executor = Write(.worktrees/**) only. settings.json 에 명시적 deny 리스트.
  - Rationale: arxiv 2603.13424 — 필터 단독 14% ASR vs 권한 분리 0.31% (323배 감소).

- **ADR-9: Provenance Frontmatter (Supply-Chain Poisoning 대응)**
  - Context: skill default-trust 위험 (CVE-2025-59536)
  - Decision: 모든 generated 자산에 frontmatter (generated_by + content_hash + source_template + version).
  - Rationale: arxiv 2604.03081. silent overwrite 차단. Brownfield reconcile 의 ours/theirs 판별 강화.

- **ADR-10: Context Lint (verbose 차단)**
  - Context: AGENTS.md verbose 가 성공률 ↓
  - Decision: Renderer 에 길이 한계 적용 (CLAUDE.md Side 200/Prod 500 등).
  - Rationale: arxiv 2602.11988 — verbose context = -성공률, +20% 비용.

### Risks (K1-K17)

| ID | 위험 | 영향 | 완화 |
|---|---|---|---|
| K1 | arxiv 크롤이 noise → 잘못된 패치 | high | adaptive threshold + 항상 manual confirm |
| K2 | autoloop runaway | high | iter cap + time cap + 3 fail stop + iter 5 ping |
| K3 | Template 자체가 stale → 자기-순환 | med | refresh 대상에 self template 포함 |
| K4 | 모니터링이 압도적 | med | statusline 3 지표 fixed, dashboard on-demand |
| K5 | i18n 비대칭 | med | template diff 비대칭 시 빌드 fail (CI 게이트) |
| K6 | hiloop skill 이름 충돌 | low | `harness-maker:` namespace 명시 |
| K7 | 22 프로젝트 한꺼번에 적용 → 회귀 폭발 | high | dry-run 강제 첫 회 / per-project apply / backup 보존 |
| K8 | WSL2 NTFS Edit hazard | med | renderer 가 자동 Write tool 강제 |
| K9 | autoloop 외부 서비스 호출 비용 | med | dry-run 디폴트, 외부 API 호출 confirm |
| K10 | 사용자 voice leak | low | prefs (memory) 의 voice 가이드 인지 |
| K11 | Brownfield .claude/ 풍부 시 reconcile 복잡 | high | backup + ADD-only + 항목별 reconcile UI + provenance hash |
| K12 | Worktree 잔존물 디스크 누적 | med | .gitignore 자동 + cleanup=on_success default + weekly cleanup hook |
| K13 | 보안 스캔 false positive 폭발 | med | on_finding.high=warn (Side default) + allowlist 파일 + per-finding silence |
| K14 | 보안 스캔 결과 누출 | low | findings .gitignore + 100% 로컬 정책 |
| K15 | Context verbose → 성공률 -·비용 +20% | high | context-linter Side 200/Prod 500 한계 |
| K16 | Reviewer agent prompt injection 으로 Write 권한 획득 | high | settings.json 권한 분리 — reviewer Write/Edit deny |
| K17 | 사용자 수정 파일 silent overwrite | med | provenance hash 비교 → 불일치 시 confirm 필수 |

---

## Appendix A: Decisions Log (v0.1 → v2.0)

상세 변경 이력은 본 spec 의 모든 ADR + Risk + Goal 결정에 흡수. 핵심 변천:

- **v0.1** (Draft): 6 R 요구사항, M1-M4 mode 분류, 5 모니터링 지표, 4 명령, 8 phase
- **v1.0**: M1-M4 폐기, 2 preset (Side/Production), 3 지표 압축, 단일 메타 명령, 12주 phase
- **v1.1**: 메타-툴 / 런타임 분리 (모든 일상 명령 → 사용자 하네스로 이동)
- **v1.2**: /hm: prefix
- **v1.3**: Workflow 추상화 (atomic + fused) + Model tier 설정
- **v1.4**: Worktree 격리 + 5 Security Gates (Archon/ECC 영향)
- **v1.5**: Agent quality drill-down (Health 의 sub-rubric)
- **v1.6**: Context lint + Privilege separation + Provenance frontmatter (arxiv 2602.11988 / 2603.13424 / 2604.03081)
- **v2.0**: autoloop-ready 형식 — Section 0-6 구조, 10 phase, 모든 R/M/A 가 Section 4 task 또는 Section 5 verify 에 명시 매핑
- **v2.1** (본 spec): autoloop dry-run 분석 결과 10 fix 적용 — (C1) Renderer freeze_time 인자, (C2) Phase 9 plugin entry subprocess 검증 task 추가, (C3) Phase 4 Anthropic URL 명시 (HTML scrape, RSS 없음), (I1) SubAgent permissions 공식 schema research note, (I2) vault autoloop 절대경로 → docs/reference/autoloop-pattern.md 자족적 reference, (I3) atomic write 패턴 CLAUDE.md, (I4) LLM mock pytest fixture 패턴 CLAUDE.md, (I5) worktree cleanup on autoloop failure CLAUDE.md, (M1) Phase 9 "Research targets: None" 명시, (M2) Phase 2 file count assertion verify 추가

---

## Appendix B: Glossary

| 용어 | 의미 |
|---|---|
| 하네스 | Claude Code 사용을 위한 프로젝트별 설정·스크립트·메모리 묶음 (`.claude/` 트리) |
| Synthesizer | preset + 사용자 응답 → blueprint 매핑 (deterministic) |
| Blueprint | 생성될 파일 목록 + 각 파일의 내용 (Apply 전 단계) |
| Preset | Side / Production — 10+ 차원의 디폴트 번들 |
| Reconciler | Brownfield 에서 기존 .claude/ 와 신규 blueprint 충돌 해결 |
| Anti-rot | 시간이 지나도 하네스가 stale 하지 않도록 자동 최신화 (manual confirm) |
| Autoloop | 목표 한 줄 → 수렴까지 자율 반복 사이클 (8h/30iter 디폴트) |
| 효율 / Health / fresh | 3 핵심 지표 (cache hit% / readiness 0-100 / days since last refresh) |
| Atomic stage | 7개 빌트인 (`research`, `spec`, `plan`, `execute`, `review`, `wrapup`, `verify`). 각 `/hm:<stage>` |
| Workflow (fused) | 사용자 명명 stage 시퀀스. Renderer 가 fragment 합성 → 1 명령 1 turn |
| Conditional Routing | 변경 파일 영역 따라 reviewer 선택 |
| Verify-before-completion | /hm:wrapup 직전 자동 게이트 |
| Modular installer | preset 외 단위 설치 (`make --add reviewer:security`) |
| Worktree 격리 | `/hm:execute` 가 git worktree 안에서만 동작 |
| 5 security gates | secrets · permissions · hook injection · CVE · prompt injection |
| Agent quality rubric | per-agent Platinum/Gold/Silver/Bronze (Health drill-down) |
| Context lint | Generator 단계의 verbose 차단 |
| 권한 분리 | reviewer = Read/Grep only, executor = Write(.worktrees/**) only |
| Provenance frontmatter | 모든 생성 자산에 generated_by + content_hash + source_template |
| fixture | 합성 검증용 가짜 프로젝트 (Side/Production × Python/Tauri/Firmware) |

---

## Appendix C: Sources & Citations

**경쟁/참고 framework:**
- hiloop: ai-readiness-rubric (Health), failures.md/wiki.md memory, autoloop-coder agent
- Synthesis (Rajiv Pant, 2026-04): `.agents/` 컨벤션 (현재 미채택, Open Question)
- claude-statusline-enhanced: cache hit 표시
- obra/superpowers: verify-before-completion 게이트, 멀티-호스트 매니페스트
- wshobson/agents: Conditional Routing + agent별 model tier + 3-layer eval (agent quality)
- davila7/claude-code-templates: Modular installer 패턴
- coleam00/Archon (v1.4 추가): YAML workflow + worktree 격리 + deterministic 노드
- affaan-m/everything-claude-code (ECC): AgentShield 보안 스캐폴딩
- scalarian/oh-my-codex: tmux worktree 라이프사이클
- HKUDS/OpenHarness: Auto-Compaction 멀티-데이 세션
- Yeachan-Heo/oh-my-claudecode: 키워드 기반 모드 자동 활성화 패턴

**arxiv 학술 근거 (v1.6, 2025-11~2026-05):**
- AHE — Agentic Harness Engineering ([arxiv 2604.25850](https://arxiv.org/abs/2604.25850)): anti-rot 자동 진화 closed-loop 정당화
- OpenDev ([arxiv 2603.05344](https://arxiv.org/abs/2603.05344)): 5-layer defense-in-depth → 5 security gates 정당화
- Inside the Scaffold ([arxiv 2604.03515](https://arxiv.org/abs/2604.03515)): 5 loop primitives 분류
- Evaluating AGENTS.md ([arxiv 2602.11988](https://arxiv.org/abs/2602.11988)): verbose context = -성공률, +20% 비용 → context lint 도입 근거
- Routing/Cascades ([arxiv 2602.09902](https://arxiv.org/abs/2602.09902)): static routing optimal → model tier 정당화
- OpenClaw — Privilege Separation ([arxiv 2603.13424](https://arxiv.org/abs/2603.13424)): 권한 분리 ASR 0.31% vs 필터 14% → 권한 분리 도입 근거
- Supply-Chain Poisoning ([arxiv 2604.03081](https://arxiv.org/abs/2604.03081), CVE-2025-59536): provenance frontmatter 도입 근거

---

**v2.0 확정** (autoloop-ready). `vault/.claude/commands/autoloop.md` 가 본 spec 의 Section 0-6 을 파싱해 자율 빌드 가능. Phase 0 kickoff 가능.
