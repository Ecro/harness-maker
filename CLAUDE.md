# CLAUDE.md — harness-maker

> 이 파일은 Claude / autoloop CODER agent 가 본 프로젝트에서 작업할 때 따라야 하는 규칙·관례 모음. **모든 결정은 사용자가 사전에 lock-in 했음.** autoloop 빌드 중에는 AskUserQuestion 호출 금지 — 모호하면 본 문서 + TECH_SPEC.md 우선.

## LLM 활용 원칙 (최우선)

harness-maker 는 Claude Code + Cursor 양쪽 IDE 의 플러그인으로, **LLM 판단력을 최대한 활용하여 품질을 극대화**한다.

- **규칙 기반 대신 LLM 판단**: 패턴 매칭·키워드 필터로 해결할 수 있는 것도, LLM 이 더 정확하게 판단할 수 있으면 LLM 에 위임
- **모호함 감지**: 답변이 충분히 actionable 한지 판정은 LLM 이 직접 수행 (regex 로 vague 판정 금지)
- **질문 생성**: 인터뷰 follow-up 질문은 LLM 이 컨텍스트를 읽고 동적으로 생성 (고정 스크립트 금지)
- **추출·요약**: 소스 문서에서 목적·불변조건·우선순위 등을 뽑는 작업은 LLM 이 전체 문서를 읽고 추출
- **수렴 판단**: stopping criteria 만족 여부는 LLM 이 현재 상태를 읽고 판단

템플릿(`.j2`)이 생성하는 슬래시 명령 안에서 Claude 가 직접 판단·추출·생성하도록 프롬프트를 설계할 것. Python 레이어는 타입 계약·저장·안전 레일만 담당.

## 프로젝트 정체성
- **이름**: harness-maker (Claude Code + Cursor 플러그인)
- **단일 메타 명령**: `/harness-maker:make` (audit/add/remove/promote 플래그)
- **사용자 명령은 `/hm:` prefix** — 양쪽 IDE 모두 `/hm:<name>` 으로 호출
- **언어**: English-default (locale=en 디폴트). interview 첫 질문이 locale (free-text). 한국어 등 다른 locale 도 입력 가능, unknown locale 은 en 으로 silent fallback
- **타깃 IDE**: `targets` 축으로 사용자가 명시 선택 (아래 §Targets 정책 참조)

## Targets 정책

`harness.yaml.targets: list[Target]` — 사용자 하네스가 어느 IDE 에서 작동할지 결정하는 축. preset / dev_mode 와 직교.

- **값**: `claude-code` | `cursor` | `codex` (multi-select)
- **인터뷰 정책**: 명시 multi-select 강제. **auto-detect 금지** (`.cursor/` 디렉토리 존재 여부 등으로 추론하지 않음). 사용자 의도 확인 필수.
- **Default fallback**: 옛 harness.yaml 에 `targets` 키 없을 때만 `[claude-code]` silent fallback + 경고 로그. 신규 인터뷰는 항상 명시 선택.
- **Single source 원칙**: agents / skills / hooks / MCP 자산은 `.claude/` 한 곳에서 양쪽 IDE 가 공유 (Cursor 가 `.claude/agents/` 를 native 로 읽음, hooks schema 호환 — IDE 모드 인식은 Phase 1 manual 검증 결과 따름).
- **Cursor 추가 자산**: `targets` 에 `cursor` 포함 시에만 `.cursor/rules/*.mdc`, `.cursor/commands/hm-*.md`, `.cursor/mcp.json` 추가 렌더.
- **Cursor 사용자 모델 권장**: `harness.yaml.recommended_model: claude-opus-4-7` + agent frontmatter `model` 명시. user override 자유. prompt 자체는 model-agnostic 재작성 안 함 (`<thinking>` blocks 등 Claude-specific 표현 유지).
- **최소 지원 Cursor 버전**: 2.4 (subagents + skills + Claude Code hooks 호환 최초 도입). Cursor 3.0 이상 권장.
- **Codex dual role** (PLAN-codex-second-llm-integration ADR-009): `codex` 는 IDE asset 렌더링 (`.codex/`) 뿐 아니라 second-LLM provider 역할도 한다. `harness.yaml.codex_second_opinion.enabled=true` 면 `code-reviewer / consensus-arbiter / plan-validator` 가 `codex exec` 을 호출 (Bash dispatch only, no MCP). 두 축은 직교 — `targets` 에 `codex` 없어도 `codex_second_opinion` 활성화 가능 (사용자 측 `codex` CLI + `codex login` 만 있으면 됨). 실패 정책은 warn-and-proceed.

## 기술 결정 (변경 금지)

### Runtime / Tooling
- **언어**: **Python only** (Bash 사용 금지). Statusline 등 hook 도 `python -m harness_maker.<module>` 호출.
- **Python**: 3.12+
- **Package manager**: `uv` + `pyproject.toml` + `uv.lock`
- **Test**: `pytest`
- **Lint + Format**: `ruff check` + `ruff format`
- **Type**: `mypy --strict`
- **Template engine**: `Jinja2`
- **License**: MIT
- **Version 시작**: `0.1.0`
- **CI**: GitHub Actions (lint + test on PR)

### Plugin 구조 (Claude Code + Cursor + Codex 공식 spec)

harness-maker 는 **triple plugin** — 세 marketplace 모두에 등록 가능:

- `.claude-plugin/plugin.json` — Claude Code manifest
- `.cursor-plugin/plugin.json` — Cursor Marketplace manifest (schema 거의 동일)
- `.codex-plugin/plugin.json` — Codex CLI manifest
- `skills/<name>/SKILL.md` — Anthropic SKILL.md 표준, 양쪽 공유 (loose md 금지)
- `agents/<name>.md` — sub-agent 정의, 양쪽 공유
- `commands/<name>.md` — 슬래시 명령, 양쪽 공유
- `hooks/hooks.json` — **Hook schema diverges by design**: Cursor IDE reads `.cursor/hooks.json` (lowercase camelCase + `version: 1`); Claude Code reads `.claude/hooks/hooks.json` (PascalCase + nested `{hooks:[],matcher:}`). Each IDE owns its own file with its own native schema. Verified empirically via kairos 0.5.7 metrics forensic 2026-05-08 (`tests/cursor-compat/results-2026-05-08.md`). Do NOT collapse to single source — Cursor 2.4+ hooks-compat docs apply to CLI only, IDE reads the dedicated `.cursor/` location.
- `rules/<name>.mdc` — Cursor 전용 (Claude Code 미사용)
- `mcp.json` — MCP server 정의, 양쪽 공유
- `lib/` — 내부 헬퍼
- `templates/` — 사용자 하네스로 렌더되는 자산

### 사용자 하네스 구조 (= 우리 templates/ 가 렌더하는 결과)

**공통 (모든 targets)**:
- `.claude/harness.yaml` — single source of truth
- `.claude/agents/<name>.md` — sub-agent (Cursor 도 native 로 읽음)
- `.claude/skills/<name>/SKILL.md` — skill (양쪽 표준 호환)
- `.claude/commands/hm/<name>.md` — `/hm:` 슬래시 명령
- `.claude/hooks/hooks.json` — hook 정의 (Cursor IDE 인식은 Phase 1 검증)
- `.claude/lib/`, `.claude/observability/`
- `.worktrees/` (gitignored)

**Cursor target 추가** (`targets` 에 `cursor` 포함 시):
- `.cursor/rules/<name>.mdc` — Cursor rules (CLAUDE.md 의 .mdc 변환본)
- `.cursor/commands/hm-<name>.md` — Cursor 위치의 슬래시 명령 (Phase 1 검증 결과 따라 `.claude/commands/` 만으로 가능할 수 있음)
- `.cursor/mcp.json` — MCP server (Cursor 별도 위치)

**Codex target 추가** (`targets` 에 `codex` 포함 시):
- `.codex/config.toml` — Codex CLI 전역 설정 (features, mcp_servers)
- `.codex/hooks.json` — Codex hooks (PascalCase + PermissionRequest 이벤트)
- `.codex/agents/<name>.toml` — 에이전트 TOML (developer_instructions = agent body)
- `AGENTS.md` — 프로젝트 루트 instructions (block-merge markers 포함)
- `.agents/skills/<name>/SKILL.md` — 기존 11개 skill 의 Codex 경로 dual-render
- `.agents/skills/hm-<stage>/SKILL.md` — 7개 atomic stage 용 stage-trigger skill

**Worktree 공유**: `.worktrees/` 단일 디렉토리. Cursor 의 `/worktree` 자체 관리와 같은 위치. cleanup 은 prefix 매치로 자기 것만 (`execute-*`, `plan-*`, `phase-*`, `autoloop-*`).

## 코드 스타일
- 파일 상단 docstring 1줄 (모듈 목적)
- 함수 docstring: WHY only (WHAT 은 코드가 말함)
- 주석 최소 — non-obvious 만
- 변수명은 영어. 사용자 출력은 locale 따름.
- 에러 메시지: locale 따라 분기 (en/ko 빌트인, 그 외 en fallback). system error 는 영어 그대로 + 현재 locale 요약

## 테스트 정책
- 모든 LLM 호출은 **subscription 통해 실제 호출 가능** (Anthropic API 결제 X — Claude Code 환경)
- 단위 테스트는 mock 우선 (속도)
- Integration / e2e 는 실제 호출 가능 (test fixture 안에서)
- 외부 API (arxiv, GitHub, OSV.dev) 는 mock + 캐시. 실제 호출은 `INTEGRATION=1` env 시만.
- GitHub API 는 unauthenticated (60/h) + `~/.cache/harness-maker/` 캐시 공유

## Git 정책
- 커밋 메시지: `<type>: <short subject>` 또는 autoloop 자동 형식 `autoloop(harness-maker): phase N - <name>`
- type: `feat | fix | chore | ci | test | docs | refactor`
- **Remote**: `git@github.com-personal:Ecro/harness-maker.git` (**public**). push 허용 — backup 용도.
  - 사용자가 명시적으로 요청해야 push (자동 push 금지).
  - 공개 repo 이므로 raw.githubusercontent.com URL 사용 가능 (README 의 이미지 등). 비밀·자격 증명·미공개 작업물은 commit 금지.
- 로컬 author: `Ecro <e839638@gmail.com>` (project-scoped git config).
- 모든 phase 완료 시 자동 commit (autoloop wrapup stage). push 는 별도.

## 버전업 정책

버전 번호는 **다섯 파일을 동시에** 수정해야 한다. 하나라도 빠지면 `/plugin update` 또는 Cursor / Codex Marketplace 가 잘못된 버전을 보고함:

| 파일 | 역할 |
|------|------|
| `.claude-plugin/plugin.json` | Claude Code `/plugin update` 가 읽는 기준 버전 |
| `.cursor-plugin/plugin.json` | Cursor Marketplace 가 읽는 기준 버전 |
| `.codex-plugin/plugin.json` | Codex CLI 가 읽는 기준 버전 |
| `pyproject.toml` | Python 패키지 버전 |
| `src/harness_maker/__init__.py` | `__version__` 런타임 값 |

> **왜:** Claude Code 의 `/plugin update` 는 `.claude-plugin/plugin.json` 의 `version` 필드를 기준으로 최신 여부를 판단한다. Cursor 도 `.cursor-plugin/plugin.json`, Codex 도 `.codex-plugin/plugin.json` 으로 동일 판단. `pyproject.toml` 만 올리고 세 manifest 가 구버전이면 모두 "already at latest" 로 오보. (0.4.9 릴리스 시 발견; cursor 도입 시 4 파일, codex 도입 시 5 파일로 확장)

## 릴리스 절차 (race-free)

5 파일 버전 동기화 + CHANGELOG 엔트리 commit 한 뒤, **boundary-parse tests 를 로컬에서 advisory 로 실행 권장**:

```
INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v
```

PLAN-test-fidelity-gap Layer 1 (ADR-003/004): 이 단계는 PR 을 막지 않는다.
release.yml 의 `boundary-advisory` 잡이 tag push 후 동일 suite 를 자동 실행 +
결과를 GitHub Release page 의 body 에 append 하므로, 로컬에서 빼먹어도 visible.
단 5-file version sync 와 같은 자리에 두고 같이 돌리면 release 전에 빨간 줄을
미리 잡는다.

그 다음 tag push:

```
git tag -a vX.Y.Z -m "..."
git push origin main vX.Y.Z
```

**그 후 아무것도 더 하지 말 것.** `.github/workflows/release.yml` 이 tag push 를
받아 `quality-gate → build → publish-testpypi → publish-pypi → github-release`
순서로 모든 산출물을 만든다. github-release 잡이 GitHub Release 페이지를 자동
생성하니, **수동으로 `gh release create` 호출 금지**.

> **왜:** 0.15.3 릴리스 때 tag push 직후 `gh release create` 를 수동 실행했더니
> workflow 의 `github-release` 잡이 "a release with the same tag name already
> exists" 로 fail. 산출물·publish 는 모두 성공했지만 latest tag 가 빨갛게
> 표시됨. push 만 하고 workflow 가 끝낼 때까지 기다리는 것이 race-free.

워크플로 실패 시:
- `quality-gate` 실패 → ruff/mypy/pytest 로컬에서 재현, fix commit, 새 patch tag
- 그 외 잡 실패 → `gh run view <id> --log-failed` 로 진단 후 fix patch tag.
  **이미 created 된 GitHub Release / PyPI publish 는 되돌리지 않음** (immutable).

PyPI 노출: harness-maker 는 **0.15.3 부터 PyPI 에 publish 됨** (Trusted
Publisher via GitHub OIDC; 자세한 건 `release.yml` 의 `publish-pypi` 잡).
이전 릴리스 (0.15.2 이하) 는 GitHub Release 만 존재 — Claude Code /
Cursor / Codex 의 plugin marketplace 가 GitHub 에서 직접 fetch.

## 보안 / 권한 (v1.6, REVIEW-2026-05-08 개정)

> **⚠️ 집행 현실 정정 (2026-06-02 — codex permission probe + Claude Code 공식 docs):**
> 아래 agent 별 `permissions.allow/deny` frontmatter 블록은 **Claude Code 가 집행하지
> 않는다.** subagent frontmatter 의 공식 인식 필드는 `name / description / tools /
> disallowedTools / model / permissionMode / hooks / …` 뿐 — `permissions` 는 그
> 목록에 없어 **silent ignore** 된다 (`sub-agents.md`). command 단위 allow/deny 는
> **오직 `settings.json`** (user/project/local/managed) 에서만 deny-first 로 집행된다
> (`permissions.md`). 결과:
> - read-only reviewer 의 *실제* 경계는 **`tools:` 에 Bash 부재** (도구 자체가 없음 — 이건 집행됨). frontmatter `deny` 는 의도 표기일 뿐, 보안 경계 아님.
> - `tools:` 에 Bash 가 있으면 frontmatter deny 와 무관하게 `sh`/`python`/`rm` 실행 가능. executor 의 `Write(/etc/**)`·`Edit(~/.ssh/**)` deny 도 동일하게 cosmetic — `Write`/`Edit` 도구가 있으면 경로 무관 write 가능.
> - **per-agent** command scoping 은 frontmatter 로 표현 불가. 진짜 경계는 (a) `tools:`/`disallowedTools` 도구 가감, (b) `settings.json` deny(단 session-wide — 전 agent·메인 공통이라 `python -m harness_maker …` 같은 자기 호출까지 막힘 주의), (c) agent 식별 기반 PreToolUse hook, (d) sandbox. 넷 다 `--dangerously-skip-permissions`/`bypassPermissions` 모드에선 무력화됨.
> 아래 블록은 **의도(intent) 문서**로만 유지한다. 실제 집행이 필요하면 위 (a)~(d) 로 옮길 것. 상세: [[fail:design subagent-frontmatter-permissions-not-enforced]], PLAN-spoton-codex-rm-stash-rootcause 후속.

- Reviewer agent (code, security, perf, ux, concurrency) — `permissions.allow: [Read(*), Grep(*), Glob(*), Bash(git diff:*), Bash(git log:*), Bash(git status:*)]`, `deny: [Write(*), Edit(*), Bash(rm:*), Bash(curl:*), Bash(npm:*), Bash(eval *), Bash(python:*), Bash(node:*), Bash(sh:*), Bash(bash:*)]`. **Why 추가 Bash deny**: REVIEW M7 발견 — 단순 rm/curl/npm 차단만으로는 `Bash(python -c "...")` / `Bash(sh -c "...")` 우회 가능. 인터프리터 호출도 모두 deny.
- Executor agent — `allow: [Read(*), Grep(*), Glob(*), Write(.worktrees/**), Edit(.worktrees/**), Bash(uv run:*), Bash(pytest:*), Bash(npm test:*), Bash(cargo test:*), Bash(git diff:*), Bash(git log:*), Bash(git status:*)]`, `deny: [Write(/etc/**), Write(~/.ssh/**), Write(~/.aws/**), Edit(/etc/**), Edit(~/.ssh/**), Edit(~/.aws/**), Bash(curl * | sh), Bash(eval *), Bash(rm -rf /:*)]`. **Why Edit/Write 페어링**: REVIEW M1 발견 — `Write(/etc/**)` 만 deny 면 `Edit(/etc/sudoers)` 로 동일 파일 수정 가능 (escalation path). 같은 시스템 경로에 대해 Write 와 Edit 은 항상 페어로 deny.
- **Main-session `settings.json` deny (opt-in, default OFF — 2026-05-31):** 위 reviewer/executor *agent* deny 와 별개로, 사용자 메인 세션의 `settings.json.permissions.deny` 는 **기본 빈 리스트**다 (`rm`/`curl|sh`/`/etc`/`~/.ssh` write 미차단 — 솔로 작업 효율). 전체 destructive baseline 은 `harness.yaml.permissions.deny_dangerous: true` 로 opt-in. **Why**: 솔로 프로젝트에서 `Bash(rm:*)` 기본 차단이 비효율적이라는 사용자 피드백. **Reviewer agents 의 `Bash(rm:*)` deny 는 유지** (read-only — rm 할 이유 없음). `readiness.py` 의 `permissions_deny_present` / `deny_covers_dangerous` 두 signal 은 opt-out 시 N-A (passed=True, no penalty) — 의도된 config 선택은 finding 이 아님. 스키마: `models.PermissionsConfig.deny_dangerous` (default False), 양 `settings/*.json.j2` 가 `config.permissions.deny_dangerous` 로 분기.
- 모든 generated 파일은 frontmatter 에 `generated_by + content_hash + source_template + harness_maker_version`

> **Cursor target 의 권한 매핑** (Phase 1 검증 결과 채움):
> Cursor 의 `permissionMode`, `sandbox.json` 등가물이 위 allow/deny 정책을 어떻게 강제하는지 미정의. Phase 1 검증 fixture 로 확인 후 본 섹션 갱신.

## Context Lint (v1.6)
- CLAUDE.md ≤ Side 200행 / Production 500행
- agent prompt ≤ Side 150행 / Production 200행
- skill SKILL.md ≤ Side 100행 / Production 150행
- `.cursor/rules/*.mdc` ≤ 500행 (Cursor 권장. 분할 권장 임계 200행)
- 초과 시 renderer 가 warn

## Workflow (autoloop CODER 가 알아야 할 점)
- **Atomic stage**: 7개 (research/spec/plan/execute/review/wrapup/verify)
- **Workflow** = 사용자 명명 fused stage 시퀀스 → 1 명령 1 turn
- Renderer 가 stage prompt fragment 들을 합성해 단일 명령 파일 생성

## 실행 주의
- WSL2 NTFS 환경 인지 (vault 경로). Edit 대신 Write 강제 시점 있음.
- Worktree base_dir 는 `.worktrees/` (Cursor 와 공유). 사용자 프로젝트의
  `.gitignore` 에 추가는 사용자 책임 — 본 repo 자체는 gitignore 됨.
- `.claude/.hm-loop-active` 은 자동 gitignore 추가 (worktree.create 시
  idempotent line-append; H3 round). marker 가 commit 되면 협업자 측에서
  존재하지 않는 worktree path 로 gate 가 블록 → 강제 footgun.
- 100% 로컬 telemetry — 외부 전송 금지

## Multi-session worktree (PLAN-worktree-cross-session-data-loss-defense)

**3회째 incident** (2026-05-23) 후 land 한 5-layer defense — 모두 동시 regression 해야 contamination 재발 가능:

| Layer | ADR | What it blocks | Escape flag |
|---|---|---|---|
| 1 queue-guard | ADR-003 | `worktree create` when ≥2 unpopped finalize stashes | `--allow-stash-queue` |
| 2 dirty-base-guard | ADR-002 | `worktree create` when base has user dirt (harness artifacts excluded) | `--allow-dirty-base` |
| 3 Session UUID | ADR-004 | Cross-session refs in `post-commit-pop` (different `session_uuid` → SKIP) | (none — legacy refs get one-shot migration) |
| 4 merge fence | ADR-005 | Parallel finalize merge race (flock primary + O_EXCL secondary; reliable on WSL2/NTFS) | `--lock-timeout <sec>` |
| 5 scope-guard | ADR-006 | Merge sweeps unrelated staged files (warn-only first, halt-mode after Phase 6) | `--skip-scope-guard` |

**LLM behavior contract** (ADR-008):
- `[finalize] stash-pop conflict` signal: NEVER recommend `git stash drop` without `git stash show -p <ref>` diff preview to user.
- Recovery procedure when stash conflict happens: `git reflog --all | grep "wip(execute)"` → cherry-pick chronological → resolve sandbox conflicts with `--ours`. Documented in `templates/commands/hm/wrapup.md.j2` Step 7.5 with `<!-- @hm:drop-policy:user-confirmed -->` marker block.

**Recovery from accidental drop** (precedent: 2026-05-23 morning's 4 dropped stashes recovered via `git reflog --all` cherry-pick — see session log 21:30 UTC). The finalize logic creates `wip(execute): capture uncommitted work` commits on the per-worktree branch BEFORE attempting cleanup; even if the stash is dropped, the WIP commit on the branch ref survives until gc.

**Keep-base-clean (PLAN-worktree-base-artifact-pollution)** — the 5 layers above stop *contamination*; this work stops the layers from *firing on the harness's own churn* (the real cause of constant stash warnings + blocked parallel `create`). One shared source of truth, `worktree._HARNESS_CHURN_PREFIXES`, drives three things:
- **gitignore** (`_ensure_harness_gitignore`, ADR-002) — appended at make time (`cli.py`) AND every `worktree create` (idempotent, subsumption-safe). Covers `.claude/observability/`, `.claude/.hm-iter-receipts/`, `.claude/loop-specs/`, `.claude/.hm-session-uuid`, `.claude/.hm-render-manifest.jsonl`, `.claude/memory/{semantic,episodic,profile}/`, `work-docs/loop-context/`, `work-docs/p5-batch-state.yaml`. Deliverables (PLAN/REVIEW/RESEARCH/SPEC, human memory tiers) are deliberately NOT ignored — wrapup commits them.
- **both dirt-filters** (ADR-003) — `_is_harness_artifact` (finalize) recognizes the churn set as a UNION with the legacy 3 prefixes; `_is_create_guard_harness_artifact` (create) inherits it via delegation, so committed-then-modified `work-docs/` churn no longer blocks `create`. Still a strict subset — genuine user `.claude/agents`/`skills`/`harness.yaml` edits remain "dirt" the finalize stash preserves (narrow-filter invariant).
- **wrapup deliverable commit** (ADR-004) — `git add` now also stages RESEARCH + SPEC, so they stop lingering as untracked dirt.
- **accepted limitation**: a user who already *committed* `.claude/` churn keeps a cosmetic `M .claude/observability/...` in `git status` (gitignore can't untrack; we never auto-`git rm --cached` — CLAUDE.md git policy). It neither blocks nor stashes. Opt-in manual cleanup: `git rm -r --cached .claude/observability .claude/.hm-iter-receipts` then commit.

## Second Brain 승급 파이프라인 (PLAN-second-brain-promotion)

로컬 `.claude/memory/` 와 Obsidian Second Brain 은 **두 개의 평행 기억 시스템이 아니라 승급 파이프라인**이다:

- **로컬 `.claude/memory/`** = 프로젝트 작업 기억 (wiki/failures/session, 빠르고 풍부, 매 wrapup Step 5.1–5.5 에서 채워짐).
- **Obsidian Second Brain** = 큐레이션된 cross-project durable 지식. wrapup **Step 5.6** 이 자격 있는 로컬 엔트리만 `second_brain promote` 로 승급 (ADR-002).

핵심 계약:
- **Step 5.6 은 advisory 가 아니라 must-evaluate 번호 단계** (ADR-001, 이전 PLAN-second-brain-write-failure ADR-006 의 "Advisory" 결정을 supersede). 매 wrapup 마다 평가 필수 — 기록은 LLM 이 "cross-project durable?" 판정 통과한 것만 (ADR-003). count gate 없음 → synthetic note 없음.
- **`promote_note` / `second_brain promote` 가 안전 레일**: 결정적 파일명 `<type>-<slug>.md` + `project_id`/`hm_source` link-back + 멱등 (같은 `--source-slug` 재승급 = in-place 갱신, 중복 0). Python 이 경로·dedup·네임스페이스 소유, LLM 이 판단·본문 소유 (ADR-004).
- **vault 는 별도 git repo** — 승급 노트는 wrapup 커밋에 포함되지 않음 (vault 자체 sync 가 담당).
- **알려진 한계 (ADR-005)**: 승급은 `/hm:wrapup` 에서만 발동한다. 수동/quick 커밋 위주 워크플로우는 승급이 안 일어난다 — vault 는 wrapup 을 도는 만큼만 채워진다. hook/별도 명령은 의도적으로 안 만듦. Step 5.6 의 `promotion evaluated: N candidates, M promoted` receipt (ADR-006) 가 under-promotion 을 가시화한다.

## Autoloop 빌드 중 모호함 발생 시
1. TECH_SPEC.md Section 4 의 phase task 우선
2. 본 CLAUDE.md 우선
3. `docs/reference/autoloop-pattern.md` 의 autonomous decision protocol (DD#8) 따름 — log 후 진행
4. **AskUserQuestion 호출 금지**

## 구현 패턴 (CODER 가 따라야 할 코드 관례)

### Atomic file write (디스크 corrupt 방지)
모든 파일 write 는 atomic 패턴 강제:
```python
import os, tempfile
from pathlib import Path

def atomic_write(path: Path, content: str) -> None:
    """tempfile + os.rename — 인터럽트 시 corrupt 0."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)  # atomic on POSIX + Windows
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
```
plain `open(path, "w")` 사용 금지 (단, 명백히 임시 디렉토리 안에서만 OK).

### LLM mock 패턴 (테스트 결정성)
사용자 정책: 실제 호출은 Claude Code subscription 통해 가능하지만, **단위 테스트는 mock 우선** (속도·결정성).

```python
# tests/unit/conftest.py
import pytest
from anthropic.types import Message, TextBlock, Usage

@pytest.fixture
def mock_anthropic_client(monkeypatch):
    """Claude SDK 호출을 deterministic mock 으로 대체."""
    class _MockClient:
        def __init__(self, *_a, **_kw): ...
        @property
        def messages(self):
            return self
        def create(self, *_a, **_kw):
            return Message(
                id="msg_test",
                type="message",
                role="assistant",
                model="claude-opus-4-7",
                content=[TextBlock(type="text", text='{"applicability_score": 0.85, "risk": "low"}')],
                stop_reason="end_turn",
                stop_sequence=None,
                usage=Usage(input_tokens=10, output_tokens=20),
            )
    monkeypatch.setattr("anthropic.Anthropic", _MockClient)
    return _MockClient
```
Integration test 는 `tests/integration/` 에 두고 `pytest.mark.skipif(not os.getenv("INTEGRATION"))` 가드.

### Worktree cleanup 정책
- 정상 종료: `harness.yaml.worktree.cleanup` 따름 (default `on_success`)
- **autoloop iter / phase blocker 발생 시 강제 cleanup**: `worktree.cleanup_all(force=True)` 호출 → halt 전 모든 `.worktrees/*` 제거 (디스크 누적 방지). 단, `--debug-worktree` 플래그 시 보존.
- stale-artifact janitor: `prune_stale(base)` 가 **`worktree create` 시점에만** 실행된다 (`_cli_create`, `--debug-worktree` 시 skip). orphan `.hm-loop-*` 마커, dangling `.worktrees/*`, 그리고 finalize-stash ref 를 정리한다. ref drain 정책: stash object 가 이미 사라진(gc/drop) ref 는 즉시 제거(복원할 내용 없음), 살아있지만 내용이 HEAD 에 없는 ref 는 preserve+warn (PLAN-worktree-base-artifact-pollution ADR-005). **24h/주기 기반 hook 은 없다** — 예전 문서의 "weekly `/hm:health` cleanup" 주장은 코드에 존재한 적 없는 오류였다.
- **Cursor 와 공유 시 주의**: prefix 매치로 자기 것만 cleanup (`execute-*`, `plan-*`, `phase-*`, `autoloop-*`). Cursor 가 만든 worktree (다른 prefix) 는 건드리지 않음.

### Snapshot test 결정성
Renderer 의 `freeze_time` 인자 적극 활용. snapshot 비교 시 `generated_at` 필드 마스크:
```python
def normalize_for_snapshot(text: str) -> str:
    """frontmatter 의 generated_at 만 마스크 (다른 필드는 결정적)."""
    return re.sub(r'^generated_at:.*$', 'generated_at: <FROZEN>', text, flags=re.M)
```

### 외부 명령 호출
- `subprocess.run(..., check=True, capture_output=True, text=True, timeout=N)` — timeout 필수
- shell=True 금지 (security_scanner 의 hook injection 검사가 자기 코드도 잡으면 안 됨)
- 외부 명령 실패 시 graceful fallback (예: GitHub API rate limit → empty result + 경고 로그)

### Communication variant policy (PLAN-antisycophancy-2026-05)

- 새 agent dispatcher template 추가 시 source frontmatter 에 `communication_variant: full|reframe|soft` **필수**. 누락 시 render 시 Jinja `UndefinedError` + `/hm:health` Layer 1 `communication_protocol` sub-check 가 actionable item 으로 surface (silent-miss = R4 canonical failure mode).
- 분류:
  - **FULL** — 일반 executor 형 (autoloop-coder, executor, stuck, trajectory-monitor — JSON output, REFRAME inapplicable).
  - **REFRAME** — reviewer / evaluator 형 (10 reviewer agents). FULL + "Input Processing" 섹션 (confirmation bias 완화).
  - **SOFT** — idea / brainstorm 형. 현재 consumer 없음 (dormant ship).
- Output frontmatter / TOML metadata 에는 키 노출 X — body 안 HTML comment 마커 `<!-- @hm:communication_variant: X -->` 로만 식별. Cursor `.mdc` / Codex TOML strict parser 호환 (ADR-004).
- Skill 도 동일 패턴, **4 LLM-judgment skill 만 적용** — agent-quality-rubric, ai-readiness-rubric, security-scanner, refdocs-search (ADR-005, reduced from 5 in 0.22.3 per ADR-0007). 7 procedural skill 제외.
- Render path: `render._extract_source_communication_variant` 가 pre-render 단계에서 source frontmatter 에서 regex 로 추출 (yaml.safe_load 는 `{{ name }}` 같은 Jinja expression 에 fail). Codex 는 dispatcher source 우회하므로 `synthesize._COMMUNICATION_VARIANT` table 명시.
- 변경 후 `/hm:health` 실행하여 silent-miss + source ↔ output drift 확인.

## 무언가를 고치거나 개선하기 전에 — 필수 체크리스트

> **이 섹션은 다음 fix/feature 시작 전에 반드시 읽고 통과시킬 것.**
> 0.1.0 → 0.3.5 patch 5번을 거치며 같은 패턴의 실수가 반복됨. 매번
> 회귀 테스트가 잡아주는 게 아니라 **구현 전에 8개 체크포인트를
> 통과**해야 다음에 같은 함정 안 밟음.

각 체크포인트는 "현실에서 한 번 깨졌던 사례 + 그래서 다음엔 어떻게
미리 잡을지" 형태. 새 PR 의 description 에 **각 항목 OK/N-A 표기 권장**.

### 1. 사용자 상태 보존 계약을 먼저 그려라
사용자 디스크에 쓸 때마다 묻는다: **"이 write 가 사용자가 손댄 무엇을
지울 수 있나?"** 답이 "있다" 면 보존 정책 설계 필수.
- 0.3.0: block-merge marker (`@hm:user:*` 안의 사용자 추가가 템플릿
  업그레이드를 견디게)
- 0.3.1: `settings.json` shallow merge (Claude Code 가 쓴 `enabledPlugins`
  보존)
- 0.3.2: `answers_from_harness_yaml` (재렌더 시 인터뷰 답변 silent 재사용)
패턴: **policy flag (default = preserve user) + slash 명령에서
`AskUserQuestion` 으로 의도 묻기**.

### 2. 외부 소비자의 파서 정합성 확인
우리가 렌더하는 파일은 우리가 아니라 **다른 도구가 읽음**. 그 도구의
parser 가 받아들이는 형식을 따라야 함.
- `settings.json` → Claude Code 가 pure JSON 으로 기대 (YAML frontmatter
  prefix 박으면 permissions 무시됨, 0.3.1 fix)
- `hooks/hooks.json` → jq-parseable pure JSON
- `lib/*.sh` → bash 가 `---` 를 명령으로 해석, frontmatter 금지
  (`_render_pure_text`)
- `.cursor/rules/*.mdc` → Cursor 가 frontmatter 로 `description`, `globs`,
  `alwaysApply` 만 인식. 우리 `content_hash` 등 추가 필드를 strict-reject
  하는지는 Phase 1 검증 결과 따름. reject 시 `_render_cursor_mdc()`
  분기에서 우리 메타는 별도 sidecar (`.hm-meta.yaml`) 로 분리 고려.
- `.cursor/mcp.json` → Cursor pure JSON, frontmatter 금지
- `.cursor-plugin/plugin.json` / `.claude-plugin/plugin.json` → 두
  marketplace 가 schema 검증. 알 수 없는 필드는 일반적으로 무시되나
  manifest 표준 외 키 추가 금지.
- `.claude/harness.yaml` → 렌더러가 **provenance YAML frontmatter** 를
  prefix 로 박는다 (`generated_by`, `content_hash`, …). 결과 파일은
  multi-document YAML stream 이므로 단일 `yaml.safe_load` 는 거부한다.
  새 reader 는 `harness_maker.io_utils.load_harness_yaml()` 헬퍼를 쓰거나,
  `safe_load_all` 의 마지막 non-empty mapping 을 사용해야 한다.
  Reverse mapper: `interview.answers_from_harness_yaml`.

새 파일 종류 추가 시: 그 파일을 누가 읽는지 + 그 reader 가 frontmatter
허용하는지 먼저 확인. 안 되면 `_is_pure_text` / `_is_hooks_json` 같은
디스패치 분기 추가.

### 3. 설정 precedence 의식
Claude Code 는 `~/.claude/settings.json` (user) → `<project>/.claude/settings.json`
(project) → `<project>/.claude/settings.local.json` 순으로 우선 적용. **하위
레벨에 키를 쓰면 상위가 가려짐**.
- 같은 패턴: `permissions`, `env` 도 project 가 user-global 을 가림
- Cursor 도 동일 패턴: enterprise → team → project (`<root>/.cursor/`) → user (`~/.cursor/`)

새 키 쓰기 전에 상위 레벨에 같은 키 있는지 확인. 있으면 keep / combine /
overwrite 분기 줄지 결정.

### 4. CLI 와 slash 명령의 책임 분리
- **CLI** (`harness_maker.cli`) = flag-driven, no stdin/AskUserQuestion.
  테스트 가능, CI 안전, 슬래시 명령에서 호출 가능
- **Slash 명령** (`commands/*.md`, `templates/commands/hm/*.md.j2`) = 사용자
  intent 수집 (`AskUserQuestion`) → CLI 에 적절한 flag 조합으로 dispatch

CLI 에 `input()` / `AskUserQuestion` 박지 말 것 — 슬래시 명령 컨텍스트에는
stdin 이 안 통해 hang. 0.3.2 의 non-tty fallback 도 같은 원리.

### 5. 자동-업그레이드 vs 보존 분기 (fingerprint 기반)
사용자 파일에 박힌 값을 만질 때: **이게 우리가 박은 거냐 사용자가 박은
거냐** 를 fingerprint 로 판정.
- `content_hash` 비교: frontmatter hash 가 일치하면 "ours" → 자동 업그레이드.
  다르면 "theirs" → KEEP.
- explicit policy 가 있으면 자동-업그레이드 무시 + policy 우선.

같은 fingerprint 패턴이 필요할 만한 곳: 사용자 hooks.json, 사용자 추가
agent/skill 파일. 그 위치에 우리 출력 박을 때 fingerprint set 만들어두면
나중에 업그레이드 깔끔.

### 6. 양방향 매퍼 (write 한 건 read 도 가능해야)
디스크에 persist 하는 모든 포맷은 **reverse mapper** 가 있어야 추후
재사용 가능.
- `synthesize.py` → `harness.yaml` 쓰기
- `interview.answers_from_harness_yaml` → `harness.yaml` 읽어서 InterviewAnswers
  복원 (0.3.2)
- `render.py` → frontmatter 에 `content_hash`
- `reconcile.py` → 같은 hash 로 KEEP/REPLACE 결정

새 persist 포맷 도입 시 "이걸 다음 번에 누가 읽을까?" 답이 있어야 함.
Schema gap (옛 버전 파일에 새 키 없음) 은 default fallback 으로 처리.
예: `targets` 키 없는 옛 harness.yaml → `[claude-code]` silent fallback +
경고 로그.

### 7. 테스트 결정성 + 환경 격리
사용자 환경 (HOME, env vars, 시계) 을 읽는 코드는 **테스트에서 격리** 필수.
안 그러면 개발자 머신 의존 + CI 비결정적.
- `freeze_time` (0.1.x): `generated_at` 결정적
- `Path.home()` mocking (0.3.5): test 가 개발자의 `~/.claude/settings.json`
  에 의존하지 않게
- `regenerate.py` 도 HOME pin: snapshot 결정성
- LLM mock: `mock_anthropic_client` fixture
- 외부 API: `INTEGRATION=1` 가드

새 코드가 환경 변수 / HOME / 외부 API / 시계 읽으면 **autouse fixture 또는
명시 monkeypatch** 추가가 PR 의 일부.

### 8. Integration 경계 한 줄 테스트
unit test 다 통과해도 **integration 경계** (CLI 실행, 외부 도구 호출,
파일 시스템 효과) 가 깨질 수 있음.
- 예: 모듈 import 는 통과해도 `uv run` 으로 다른 cwd 에서 실행하면 실패.
  unit 으론 못 잡음 → `tests/e2e/test_plugin_live.py` 로 실제 claude 바이너리
  호출해서 검증.
- **Cursor target 추가 시**: 사용자는 Cursor IDE 사용 (CLI 사용 X). e2e
  자동화는 IDE 기반이라 어렵고 **manual 검증이 default**. CI 에서는
  unit + snapshot test 로 디스크 산출물 (frontmatter 형식, parser 정합성,
  render 결정성) 을 최대한 잡음. IDE 인식 여부 (slash 명령 표시,
  agent dispatch, hook fire, skill auto-load) 는 manual 체크리스트로
  README 또는 `tests/cursor-compat/MANUAL_CHECKLIST.md` 에 명시.

새 사용자-경계 코드 (CLI 명령, 슬래시 명령, hook) 는 **bash 또는
subprocess 로 실제 실행하는 e2e 한 케이스** 라도 추가.

---

## 사용자 voice
- 직접적 (no preamble, no flattery)
- 우려 먼저, 동의 나중
- 동의 시 WHY 설명
- 새 증거 없이 fold 하지 않음

---

*Cross-refs last verified: 2026-05-07 (0.5.x). TECH_SPEC.md §4 / docs/reference/autoloop-pattern.md DD#8 / tests/cursor-compat/MANUAL_CHECKLIST.md — 모두 유효.*
