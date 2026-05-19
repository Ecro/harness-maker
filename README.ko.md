<p align="center">
  <img src="https://raw.githubusercontent.com/Ecro/harness-maker/main/docs/assets/brand-block.png" alt="harness-maker" width="720">
</p>

# harness-maker

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org)
[![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-orange)](https://code.claude.com)
[![Cursor 2.4+ (3.2+ rec)](https://img.shields.io/badge/Cursor-2.4%2B_(3.2%2B_rec)-black)](https://cursor.com)
[![Built with uv](https://img.shields.io/badge/built_with-uv-261230.svg)](https://docs.astral.sh/uv/)

[English](https://github.com/Ecro/harness-maker/blob/main/README.md) · **한국어**

> **내 프로젝트를 아는 하네스 — 그 모양을 끝까지 지킵니다.**

인터뷰로 빚어진다. 등급으로 게이트된다. 스스로 진화한다. 모든 IDE에서 동작한다.

[왜?](#왜-harness-maker) ·
[어떻게 맞춰지나](#어떻게-내-프로젝트에-맞춰지나) ·
[빠른 시작](#빠른-시작) ·
[특장점](#특장점) ·
[Comparison](README.md#how-it-compares) ·
[Configuration](README.md#configuration) ·
[Targets](README.md#targets) ·
[FAQ](README.md#faq) ·
[Roadmap](README.md#roadmap) ·
[Deep dive](docs/HOW-IT-WORKS.md)

---

## 30초 만에 시도하기

Claude Code · Cursor · Codex CLI 중 하나의 AI 에이전트에 아래 프롬프트를 붙여넣으세요. IDE를 자동 감지하고, 매칭되는 플러그인을 Bash로 설치한 뒤, 인터뷰를 진행하고 personalization tier 리포트까지 출력합니다.

```
Install harness-maker for this project and bootstrap the harness end-to-end.

You are an AI agent running inside Claude Code, Cursor, or Codex CLI.
Detect which one (silently — don't ask me), install the matching plugin via
Bash (NOT slash commands typed by me), then invoke harness-maker:make and
hm:health via the Skill tool. Conduct the conversation in the language of
my first reply.

Install path per IDE:
  Claude Code:  Bash  claude plugin marketplace add Ecro/harness-maker
                Bash  claude plugin install harness-maker@harness-maker
                Then tell me: "Type /reload-plugins, then send any short message (e.g. `go`) to re-trigger me."
  Cursor:       Bash  git clone --depth 1 https://github.com/Ecro/harness-maker.git ~/.cursor/plugins/local/harness-maker
                Then tell me: "Reload the Cursor window (Ctrl+Shift+P → Reload Window)."
  Codex CLI:    Bash  codex plugin marketplace add Ecro/harness-maker
                Then tell me: "Open /plugins; if harness-maker isn't enabled, restart codex."

After the reload, run harness-maker:make (drive the interview — accept defaults
unless I object), then hm:health (read out the personalization tier and top
action items).
```

긴 형식 (IDE별 사용자 액션 수, Bash 권한 주의사항, 수동 설치 fallback)은 영문 [Quickstart](README.md#quickstart) 참조.

---

## 왜 harness-maker?

대부분의 AI 코딩 도구는 범용 템플릿에서 시작합니다 — 모든 프로젝트에 같은 reviewer, 모든 스택에 같은 프롬프트, 아무도 다시 손보지 않는 default. harness-maker는 정반대로 갑니다: **하네스가 당신의 프로젝트에 의해 빚어지고, 프로젝트가 변해도 그 모양을 유지합니다.**

| | 원칙 | 실제 의미 |
|--|---|---|
| 🎯 | **개인화 (Personalized)** | 프로파일러가 12개 이상의 스택/프레임워크/CI 신호를 읽음. 인터뷰가 10개 이상의 차원을 lock. `Side` 실험과 `Production` 서비스는 **구조적으로 다른** 하네스를 받음 — 다른 reviewer 셋, 다른 워크플로 stage, 다른 보안 게이트. 범용 default가 조용히 깔리는 일 없음. |
| 🛡️ | **신뢰 (Trusted)** | 모든 `/hm:execute`는 fresh worktree + TDD 루프. `/hm:review`는 보고만 하지 않음 — consensus-passed fix를 적용하고 등급 ≥ A까지 재리뷰. Mechanical check (lint/test)가 LLM reviewer가 토큰 쓰기 전에 게이트. |
| 🌱 | **자기진화 (Self-evolving)** | agent, skill, CLAUDE.md 어디든 손편집 — block-merge 마커가 `--update` 너머에서도 보존. 메모리가 프로젝트 고유 패턴을 축적; 반복되는 실패는 새 가드레일을 자동 제안. |
| 🌀 | **무방부패 (Anti-rot)** | 4개 소스 주간 크롤 (Anthropic, GitHub releases, arXiv, OSV CVE). 사용자 accept/reject 이력으로 적응형 relevance filter. 항상 수동 확인 — silent auto-apply 경로는 존재하지 않음. |
| 🎛️ | **다중 IDE (Multi-IDE)** | Claude Code + Cursor + Codex. 한 개의 `harness.yaml`, 세 개의 target-native 렌더. 기존 Cursor rules / Aider 설정 / Copilot instructions는 첫 실행에서 흡수 — 수동 포팅 0. |

---

## 어떻게 내 프로젝트에 맞춰지나

```
감지 (SENSE)  →  결정 (DECIDE)  →  렌더 (RENDER)  →  진화 (EVOLVE)
```

네 단계. 각 단계가 harness-maker가 당신을 위해 답하는 질문입니다 — 한 번, 그리고 계속.

### 1. 감지 (SENSE) — *이건 어떤 프로젝트인가?*

프로파일러가 묻기 전에 먼저 구체적 신호를 스캔합니다. 각 감지는 **confidence** (HIGH / MEDIUM / LOW)로 태깅되어, default가 silent 적용될지, 프롬프트로 물어볼지, 건너뛸지 결정합니다.

| 신호 | 감지 출처 |
|---|---|
| **Stack** (12개 이상) | `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pubspec.yaml`, … + 확장자 개수 |
| **Scale** | 소스 파일 총 개수, 모노레포 depth, `apps/` 또는 `packages/` 존재 |
| **Lifecycle** | Git commit velocity, branch protection 규칙, CI 워크플로 존재 |
| **Frameworks** | React / Vue / FastAPI / Django / Tauri / Zephyr / Next.js / Tailwind / Pydantic … (의존성 파싱, 키워드 추측 아님) |
| **Package manager** | uv · poetry · pnpm · yarn · cargo · go mod · gradle · maven |
| **CI provider** | GitHub Actions · GitLab CI · CircleCI · Bitbucket Pipelines |
| **외부 AI 설정** | 기존 `.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.continue/`, `.aider.conf.yml`, `.github/copilot-instructions.md` |

> **결과:** 24시간 캐시된 `ProjectProfile`. 인터뷰 전에 `harness-maker profile . --json`으로 확인 가능.

---

### 2. 결정 (DECIDE) — *이 프로젝트엔 어떤 하네스가 필요한가?*

짧은 인터뷰가 모든 하류 렌더에 영향을 주는 차원들을 lock합니다. 재실행 시 이전 답변을 silent 재사용; 명시적 `--reinterview`로 재질문.

| 차원 | 선택지 | 영향 |
|---|---|---|
| **Preset** | `Side` · `Production` | Reviewer 개수 (1 vs 5), 워크플로 stage 수, 보안 게이트 깊이, verify-required 플래그 |
| **Dev mode** | `task-driven` · `spec-driven` | SPEC stage가 필수인지 여부; plan stage가 execute로 chain 되는지 |
| **Targets** | `claude-code` · `cursor` · `codex` (다중 선택) | 어떤 IDE-native 자산 트리가 렌더되나 |
| **Locale** | `en` · `ko` · 임의 태그 | 인터뷰 텍스트 + 사용자 대면 에러 메시지 |
| **Workflows** | Atomic stage의 fused 시퀀스 | 어떤 `/hm:<name>` 슬래시 명령이 나타나나 |
| **Reviewers / skills** | Preset default + 오버라이드 | 어떤 agent와 skill이 설치되나 |
| **Ref folders** | 경로 + glob 쌍 | `refdocs-search` skill로 검색 가능한 외부 문서 |
| **Sibling repos** | 상대 경로 | 같은 하네스 세션을 공유할 인접 repo |
| **Second Brain** | Obsidian vault 경로 + project_id | 세션 간 메모리가 쓰여지는 곳 |
| **Recommended model** | 기본 `claude-opus-4-7` | 생성된 모든 agent의 model frontmatter |

> **결과:** `.claude/harness.yaml` — 업그레이드를 견디는 single source of truth.

---

### 3. 렌더 (RENDER) — *이게 어떻게 작동하는 하네스가 되나?*

하나의 source tree, 세 개의 IDE-native 렌더, 모두 단일 `harness.yaml`에서:

```
.claude/                 ← 단일 source: agents, skills, commands/hm/, hooks, memory, observability
├── .cursor/             ← + Cursor-native rules, hooks, mcp.json    (cursor target일 때)
├── .codex/              ← + Codex-native config.toml, agent TOML들   (codex target일 때)
├── AGENTS.md            ← + Codex root instructions                  (codex target일 때)
└── .agents/skills/      ← + Codex skill 경로                          (codex target일 때)
```

기본 렌더 위에 레이어링:

- **Domain packs** — `--add-domain python` (또는 `node`, `rust`)이 스택별 표준, agent, skill을 하네스에 그래프트. 커스텀 domain은 스텁으로 생성.
- **외부 설정 흡수** — 기존 Cursor rules, Aider 설정, Copilot instructions를 LLM이 `harness.yaml` 축으로 번역. `@hm:harness:*` inverted 마커가 재렌더 시에도 동기화 유지.
- **Sibling repos** — frontend + backend + library가 `harness.yaml`의 상대 경로 바인딩으로 한 세션을 공유. 머신 간 portable.
- **Ref folders + Second Brain** — 등록된 프로젝트 문서 + Obsidian vault 노트가 어떤 stage에서든 검색 가능.

> **결과:** 사용하는 모든 IDE가 같은 agent, 같은 skill, 같은 워크플로를 native로 봄. 수동 포팅 0.

---

### 4. 진화 (EVOLVE) — *어떻게 계속 유용하게 남나?*

세 개의 독립 피드백 루프가 프로젝트가 성장해도 하네스가 프로젝트에 정렬된 상태를 유지합니다.

**A. 내 편집이 업그레이드를 견딘다.**
`agents/code-reviewer.md`를 손편집하세요. 커스텀 skill을 추가하세요. CLAUDE.md 섹션을 고치세요. 모두 `harness-maker make --update`를 견딥니다 — 파일별 content hash + `@hm:user:*` block-merge 마커가 사용자 편집과 템플릿 소유 영역을 구분하기 때문. `@hm:harness:*` inverted 마커는 반대 (외부 설정용: 바깥은 보존, 안쪽은 교체).

**B. 하네스가 프로젝트를 학습한다.**
- `.claude/memory/wiki.md` — 패턴, 규약, 함정. 매 `/hm:wrapup`에서 새 항목 추가.
- `.claude/memory/failures.md` — 반복되는 실수, slug + count로 dedup.
- `.claude/memory/session/<date>.md` — 작업일별 non-obvious 결정사항.
- 어떤 failure slug라도 **count ≥ 3**에 도달하면, wrapup이 `pending-proposals.md`에 제안을 작성 — 그 재발을 막을 수 있었을 새 skill / rule / hook. 사용자가 검토하고 ingest 여부 결정.

**C. Default가 내 오버라이드에 적응한다.**
오버라이드 텔레메트리 (100% 로컬)가 default 변경마다 추적. `/hm:health`가 세 레이어 — 감지→권장 전환율, 오버라이드 안정성, 감사 주기 — 를 점수화하여 **Bronze → Silver → Gold → Platinum** tier를 산출, 순위가 매겨진 action item을 함께 surface. 하네스가 실제 사용 패턴에서 너무 벗어나면 audit이 어떤 default가 잘못됐는지 정확히 알려줍니다.

> **결과:** 하네스가 프로젝트와 함께 개선됨, 프로젝트에 거슬리지 않음. 이미 결정한 사항이 silent 재논의되는 일 없음.

각 단계의 메커니즘 — 전체 절차, 결정 경로, 내부 invariant — 는 [**docs/HOW-IT-WORKS.md**](docs/HOW-IT-WORKS.md) 참조.

---

## 빠른 시작

### Universal Bootstrap Prompt

> **AI 에이전트에 paste 하세요 — 현재 IDE (Claude Code / Cursor / Codex)를 감지해서
> 해당 IDE의 plugin install 을 Bash로 실행하고 (사용자가 슬래시 명령을 칠 필요 없음)
> 하네스까지 부트스트랩합니다.** 한 번의 paste, 모든 지원 IDE 대응.

**IDE 별 사용자 액션 수** (나머지는 AI 가 처리):

| IDE | Paste | 타이핑할 슬래시 | GUI / restart 액션 | 총 액션 |
|---|---|---|---|---|
| **Claude Code** | 1 | 1 (`/reload-plugins`) | 짧은 메시지 1개 (예: `go`) — Claude re-trigger 용 | **3** |
| **Cursor** | 1 | 0 | 1 (`Ctrl+Shift+P → Reload Window`) | **2-3** |
| **Codex CLI** | 1 | 0 | 0-1 (`/plugins` 에 harness-maker 없으면 codex restart) | **2-3** |

> **첫 사용 시 Bash 승인 가이드.** Claude Code / Cursor 가 아래 prompt 의 install 명령에 대해 Bash 권한을 요청. prompt 에 명시된 **정확한 명령만** 승인 (`claude plugin install harness-maker@harness-maker` for Claude Code, `git clone --depth 1 https://github.com/Ecro/harness-maker.git ~/.cursor/plugins/local/harness-maker` for Cursor). **`Bash(*)` 전체 허용은 거부** — AI 가 다른 명령을 요청하면 중지하고 검토. Cursor clone 은 public repo 의 현재 `main` 브랜치를 받고 이후 `git pull` 업데이트는 무결성 검증되지 않음 — threat model 에 따라 release tag 수동 pin 권장.

```
Install harness-maker for this project and bootstrap the harness end-to-end.

You are an AI agent running inside one of: Claude Code, Cursor, or Codex CLI.
Detect which one (silently — do NOT ask me), run the matching plugin install
via Bash (NOT slash commands typed by me), then invoke harness-maker:make
and hm:health via the Skill tool.

Step 1 — Detect the host IDE (silent):
  - Claude Code  → $CLAUDE_CODE is set, or ~/.claude/ exists, or you have
                   the Bash tool with access to the `claude` CLI
  - Cursor       → $CURSOR_SESSION is set, or ~/.cursor/ exists, or you have
                   Cursor's plugin manager available
  - Codex CLI    → $CODEX_SESSION is set, or ~/.codex/ exists, or the
                   `codex` command is on PATH

Step 2 — Install harness-maker as a plugin via Bash (skip when the
harness-maker:make skill is already available):

  IF Claude Code:
    Bash: claude plugin marketplace add Ecro/harness-maker
    Bash: claude plugin install harness-maker@harness-maker
    Then tell me verbatim: "Type /reload-plugins, then send any short message (e.g. `go`) to re-trigger me."

  IF Cursor:
    Bash: git clone --depth 1 https://github.com/Ecro/harness-maker.git ~/.cursor/plugins/local/harness-maker
    Then tell me verbatim: "Reload the Cursor window now (Ctrl+Shift+P → Reload Window)."

  IF Codex CLI:
    Bash: codex plugin marketplace add Ecro/harness-maker
    Then tell me verbatim: "Open Codex's /plugins list; if harness-maker isn't enabled, restart codex."

  IF you can't tell which IDE (or none of the above), STOP and ask me which
  IDE you're in.

Step 3 — After I confirm the reload/restart, invoke harness-maker:make via the
Skill tool (do NOT ask me to type any slash command) and drive the interview:
  • Confirm preset (Side / Production), dev mode, target IDEs, and locale.
  • Accept the recommended defaults unless I object.

Step 4 — After harness-maker:make finishes, invoke hm:health via the Skill tool
(again, do NOT ask me to type it):
  Produces a 3-section dashboard at .claude/observability/dashboard.md
  (structural / external-risks / personalization). Tell me the personalization
  tier and any high-priority action items.

Conduct the conversation in the language of my first reply; default to English
if you cannot tell.
```

<details>
<summary><strong>수동 설치 — IDE에 맞는 한 가지 선택</strong></summary>

#### Claude Code (plugin marketplace)

```
/plugin marketplace add Ecro/harness-maker
/plugin install harness-maker@harness-maker
```

이 repo가 marketplace metadata와 plugin 본체를 모두 담고 있어서 두 줄로 끝. Claude Code 재시작 후 `/harness-maker:make` 활성화.

#### Codex CLI (plugin marketplace)

```
codex plugin marketplace add Ecro/harness-maker
# 특정 릴리스로 고정 (재현성):
codex plugin marketplace add Ecro/harness-maker --ref v0.14.3
```

Codex 에서 `marketplace add`가 곧 설치 — 별도 install 단계 없음. 이후 Codex 안에서 `/plugins` 실행하여 활성화.

#### Cursor (Team marketplace 임포트 또는 local symlink)

Cursor의 공식 plugin marketplace는 큐레이션 방식 ([cursor.com/marketplace/publish](https://cursor.com/marketplace/publish), submit-and-review)이고 GitHub 직접 install은 Cursor 2.5+ 로드맵상 미지원. 현재 동작하는 두 경로:

**A. Team marketplace (Team / Enterprise plan):**
Dashboard → Settings → Plugins → Team Marketplaces → Import → `https://github.com/Ecro/harness-maker` 붙여넣기 → 팀원에게 푸시.

**B. Local 개발 install (커뮤니티 패턴):**

```bash
git clone https://github.com/Ecro/harness-maker.git ~/.cursor/plugins/local/harness-maker
```

Cursor 재시작 (Ctrl+Shift+P → "Reload Window")으로 plugin 인식.

#### PyPI (IDE plugin 미사용 — CI / headless / 스크립트)

IDE plugin 경로가 맞지 않을 때 (CI 스크립트, headless 서버, 자동화, 또는 Python CLI 도구 선호):

```bash
uv tool install harness-maker          # POSIX / macOS / WSL
# Native Windows / PowerShell:
irm https://astral.sh/uv/install.ps1 | iex
uv tool install harness-maker
```

이후:

```bash
cd your-project
harness-maker profile . --json
harness-maker make . --preset Production --locale ko --targets claude-code,cursor
```

일회성 렌더는 가능하지만, IDE 내 슬래시 명령 (`/hm:health`, `/hm:plan`, `/hm:execute` 등)은 IDE plugin이 로드해야 나타납니다.

</details>

하네스 렌더 이후 플래그로 진화:

```bash
harness-maker make . --audit           # 기존 .claude/ 를 rubric 으로 채점
harness-maker make . --add NAME        # 단일 skill/agent/command 추가
harness-maker make . --remove NAME     # 외과적 컴포넌트 제거
harness-maker make . --promote NAME    # ad-hoc 자산을 하네스로 승격
```

---

## 특장점

무엇이 컴포넌트인지가 아니라, 그것이 **당신의 프로젝트에 무엇을 해주는지**로 그룹화.

### 🎯 개인화 — *프로젝트에 맞춰진다*

- **프로젝트로 빚어진 하네스.** 프로파일러 + 10차원 인터뷰가 Side 실험과 Production 서비스에 **구조적으로 다른** 하네스를 생성. Reviewer 개수, 워크플로 stage, 보안 게이트 깊이, mechanical-check 강제 — 모두 답변에서 파생.
- **12+ 스택 감지.** Python · Node · Rust · Java · Kotlin · Swift · Dart · Ruby · PHP · C# · Elixir · Scala · C/C++ · Zig · Haskell. Framework + package-manager + CI provider는 manifest에서 파싱 (키워드 추측 X). manifest mtime 기반 24시간 캐시.
- **Confidence 기반 default.** 모든 감지가 HIGH/MEDIUM/LOW confidence 선언. HIGH → `# detected:` provenance와 함께 silent default. MEDIUM → 명시적 인터뷰 프롬프트. LOW → 건너뜀 (당신이 결정). Regression 테스트가 minor 버전 간 surprise silent default 변화를 방지.
- **적응형 개인화 tier.** `/hm:health`가 세 레이어 (감지→권장 전환율, 오버라이드 안정성, 감사 주기)를 점수화하여 Bronze → Silver → Gold → Platinum tier 보고. 한 axis가 5+ 회 오버라이드되면 default 변경 자동 제안. 100% 로컬 텔레메트리 — 프로젝트 밖으로 나가는 데이터 없음.
- **Domain packs.** `--add-domain python` (또는 `node`, `rust`)이 스택별 표준, agent, skill을 그래프트. 커스텀 domain은 스텁으로 — 팀이 자기 것을 추가하는데 harness-maker fork 불필요.
- **단일 명령, subcommand 폭증 없음.** `/harness-maker:make`가 유일한 진입점. 나머지는 모두 플래그 (`--audit`, `--add`, `--remove`, `--promote`, `--add-domain`, `--reinterview`, `--update`).

### 🛡️ 신뢰 — *등급 게이트된 작업*

- **등급 기반 auto-fix 루프.** `/hm:review`는 보고만 하지 않음. Consensus-passed fix 적용 → 재리뷰 (selective, 스코프 닿은 reviewer만 재spawn) → 재채점, 등급 ≥ threshold (기본 A) 또는 `max_review_rounds` 소진까지. Weak-consensus와 manual-only는 절대 auto-apply 안 됨.
- **LLM 토큰 전에 mechanical pre-check.** Lint clean + tests green이 reviewer가 spawn 되기 **전에** 강제. 첫 non-zero exit이 `## MECHANICAL_BLOCK: <cmd> exit=<N>`을 emit하고 halt. `--no-auto-fix`가 이 게이트를 우회하지 않음.
- **Conditional reviewer routing.** `.env` 변경 → security-reviewer. `/perf/` → performance-reviewer. `.tsx` → ux-reviewer. async/locking → concurrency-reviewer. 모든 diff에 모든 reviewer fan-out 보다 10× 저렴.
- **2-pass redaction (+47pp 정밀도).** Pass 1이 PR 메타데이터를 제거하여 finding이 author/title에 anchor되지 못하게. Pass 2가 전체 컨텍스트 복원 — reviewer가 각 Pass 1 finding을 validate 또는 drop. Anchoring 취약 diff에 대한 ablation 측정된 정밀도 증가.
- **7개 보안 게이트.** `secrets` · `permissions` (settings.json over-grant) · `hook-injection` (`rm -rf`, `curl|sh`, `eval`에 대한 AST 스캔) · `CVEs` (OSV.dev) · `hallucination` (존재하지 않는 import에 대한 AST 스캔) · `prod-name guard` · `prompt-injection`. Finding은 `.claude/observability/security/`에 로컬로만.
- **Privilege separation.** Reviewer agent는 `Write` / `Edit` / interpreter `Bash` 호출 deny. Executor agent는 `.worktrees/**` 쓰기만 allow + 시스템 경로에 대한 Edit/Write 페어 deny. Defense-in-depth가 prompt injection, agent compromise, tool_input poisoning을 모두 견딤.
- **Per-run worktree 격리.** 모든 execute가 fresh `git worktree`에서 실행. 실패한 run은 증거 보존; 성공한 run은 prefix-match로 auto-cleanup (Cursor 자체 worktree는 절대 건드리지 않음).

### 🌱 자기진화 — *프로젝트와 함께 성장한다*

- **Block-merge 보존.** 어떤 agent, skill, CLAUDE.md 섹션이든 손편집. `--update`를 견딤 — 파일별 content hash + `@hm:user:*` 마커가 사용자 편집과 템플릿 소유 영역을 분리하기 때문. `@hm:harness:*` inverted 마커는 외부 설정 흡수용으로 반대 동작.
- **3-tier 메모리 축적.** `wiki.md` (패턴) · `failures.md` (slug 기반 dedup된 반복 실수) · `session/<date>.md` (non-obvious 결정). Wrapup이 자동으로 쓰고, 모든 stage가 자동으로 읽음.
- **자기개선 failure 제안.** `[fail:*]` slug가 세션 간 3× 재발하면, wrapup이 `pending-proposals.md`에 제안 작성 — 그 재발을 막을 수 있었을 새 skill / rule / hook. 검토 후 ingest 결정.
- **ADR 시스템 = execute의 binding 제약.** `/hm:plan` 동안 promote 된 ADR은 `/hm:execute`의 hard 제약. 충돌은 blocker로 surface, silent proceed 절대 없음. 미래 세션이 이미 결정된 사항을 재논의하지 않음.
- **Refdocs search.** 아키텍처 문서, API spec, design 문서를 `harness.yaml`에 등록. `refdocs-search` skill이 무손실 full-text search 제공 — 청킹 없음, RAG 인덱스 없음.
- **선택적 Second Brain.** Obsidian vault 통합. Note 타입별 (decision · preference · failure · project · reference · journal) allowlist 된 쓰기 폴더. 플러그인 재설치나 머신 이동에도 세션 간 메모리 생존.
- **Brownfield-safe 업그레이드.** `Reconciler`가 기존 `.claude/`를 hash하고 충돌별 keep/replace/both 제공. 적용은 timestamped backup과 함께 ADD-only. 사용자 편집이 silent 덮어쓰여지지 않음.

### 🌀 무방부패 — *생태계 변화를 견딘다*

- **4-소스 주간 크롤.** Anthropic 블로그/changelog · `anthropics/claude-code` GitHub releases · arxiv cs.SE/CL/CR · OSV.dev CVE. `/hm:health`에서 `pending` 항목으로 manifest됨.
- **적응형 relevance filter.** Threshold 0.7로 시작, 소스별 accept/reject 이력 기반 ±0.05 조정. 항상 수동 확인 — `--auto-apply` 경로는 존재하지 않음.
- **통합 health 감사.** `/hm:health`가 세 개의 orthogonal 레이어 — Structural (70% 결정적 + 25% LLM rubric + 5% 캐시 진단), External Risks (anti-rot pending 큐), Personalization (Bronze→Platinum tier) — 를 합성. `.claude/observability/dashboard.md`에 3-섹션 대시보드. Auto-apply 절대 없음 (ADR-001).
- **SessionStart drift 알림.** 매 세션 오픈 시 hook이 실행되어, 실행 중인 플러그인 버전이 하네스를 렌더한 버전과 다르면 경고 — `/plugin update` 후 재렌더가 필요하다는 신호. 감지기가 최신 캐시된 플러그인 버전과 비교 (import된 `__version__`만이 아님).
- **Cache-miss 분류.** Prompt-cache 진단이 `min_threshold` · `invalidation` · `ttl` · `first` (cold start) 보고. AI-readiness의 5% 가중치가 cold-start 미스 (양성)와 구조적 미스 (actionable)을 구분.

### 🎛️ 다중 IDE — *하나의 source, 모든 IDE*

- **하나의 하네스, 세 개의 target.** Claude Code + Cursor (2.4+, 3.0+ 권장) + Codex CLI. 단일 `.claude/` source tree; Cursor가 native로 읽고 자신의 `.cursor/`로 hook과 rule 받음; Codex는 `.codex/`, `AGENTS.md`, `.agents/skills/`. 모두 하나의 `harness.yaml`에서 렌더.
- **외부 AI 설정 마이그레이션.** 6개의 알려진 외부 설정 감지 (`.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`, `.github/copilot-instructions.md`). LLM이 harness.yaml 축으로 번역. `@hm:harness:*` inverted 마커가 재렌더 너머에서도 동기화 유지.
- **Sibling repos.** Frontend + backend + library가 harness.yaml의 상대 경로로 한 세션에 바인딩. 머신 간 portable (상대 경로가 `git clone`을 견딤).

### 🔁 워크플로 프리미티브 — *나머지 툴체인*

- **구현 전 깊은 인터뷰.** `/hm:spec`이 6-카테고리 인터뷰 (Intent → Outcomes → In-Scope Scenarios → Non-Goals → Constraints → Verification)를 완전성 점수화하여 실행. `/hm:plan`이 9-카테고리 인터뷰 (scope → architecture → contract → risk → testing → phasing → dependencies → failure handling → observability)를 impact 순서로 실행. 모든 settled 결정이 binding ADR로 promote.
- **적응형 인터뷰 + 4-게이트 수렴 autoloop.** `/hm:loop`이 time-and-iteration-bounded 루프 실행. `autoloop-driver`가 goal을 읽고 누락된 것만 질문, loop intensity + exit checklist lock, 그 후 mechanical check + LLM judgment + regression 비교 + 2-iter convergence streak가 완료 수락 전 모두 필요.
- **3-tier 컨텍스트 로딩 + compaction 복구.** Hot tier (오늘 session) · Warm tier (failures + wiki 첫 60/40줄) · Cold tier (git log / PLAN on demand). `PreCompact` hook이 context compaction 전에 session flush; 다음 turn이 마커를 감지하고 마지막 in-progress phase에서 resume.
- **Cross-process 메모리 안전성.** `.claude/memory/` 쓰기는 re-entrant POSIX flock으로 serialize. Telemetry hook이 `O_APPEND`에 raw `os.write()`로 원자적 append (single-syscall, ≤PIPE_BUF) — concurrent Claude Code + Cursor 세션이 JSONL 라인을 interleave 불가.

각 기능의 완전한 메커니즘 — 모든 절차, 결정 경로, 내부 invariant — 는 [**docs/HOW-IT-WORKS.md**](docs/HOW-IT-WORKS.md) 참조.

---

## 안정성

harness-maker는 `0.x` 단계이며 1.0 약속이 정직해질 만큼의 의존 프로젝트가 누적되기 전까지는 이 상태를 유지합니다 ([ADR-001 in `work-docs/PLAN-oss-readiness-audit.md`](work-docs/PLAN-oss-readiness-audit.md) 참조).

**고정 표면(Frozen surfaces)** — deprecation cycle 없이는 어떤 0.x.minor에서도 깨지지 않습니다:

- **슬래시 명령 이름**: `/hm:make`, `/hm:research`, `/hm:plan`, `/hm:execute`, `/hm:review`, `/hm:wrapup`, `/hm:verify`, `/hm:health`, `/hm:loop`, `/hm:configure`, `/hm:personalization-audit`, `/harness-maker:make`.
- **`harness.yaml` 최상위 키**: `targets`, `preset`, `dev_mode`, `locale`, `reviewers`, `skills`, `agents`, `worktree`, `anti_rot`, `observability`, `ref_folders`, `second_brain`, `recommended_model`.
- **Plugin manifest 스키마**: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json` — 각 marketplace 공식 spec에 포함된 필드들.
- **로컬 전용 telemetry 보장** — [`PRIVACY.md`](PRIVACY.md) 참조. 문서-vs-실제 불일치는 P0 버그로 취급합니다.

**그 외 모든 것은 어떤 0.x.minor 에서든 바뀔 수 있습니다.** 내부 Python API, `.claude/observability/` 파일 포맷, 템플릿 내용, ADR 번호 부여, reviewer 프롬프트 표현, 인터뷰 문구. 1.0 전 reproducibility가 중요하다면 특정 릴리스로 핀 (`uvx --from harness-maker==0.17.0 ...`) 사용을 권장합니다.

**실제로 "깨진다"는 게 어떤 모양인지** — [`CHANGELOG.md`](CHANGELOG.md) 참조. 같은 minor 안의 patch (예: 0.15.0 → 0.15.3) 들은 deprecation 없이 직전 patch의 수정을 다시 손본 적이 있습니다. 0.x 단계의 의도된 속도입니다.

---

## 더 읽기

기술적 상세 (Requirements · How it works · Slash commands · Comparison · Configuration · Targets · Reconcile rules · Observability · Marketplace · FAQ · Roadmap · Development · Contributing) 는 영문 [README.md](README.md) 참조.

## 라이선스

MIT — [LICENSE](LICENSE) 참조.
