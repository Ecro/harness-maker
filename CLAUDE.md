# CLAUDE.md — harness-maker

> 이 파일은 Claude / autoloop CODER agent 가 본 프로젝트에서 작업할 때 따라야 하는 규칙·관례 모음. **모든 결정은 사용자가 사전에 lock-in 했음.** autoloop 빌드 중에는 AskUserQuestion 호출 금지 — 모호하면 본 문서 + TECH_SPEC.md 우선.

## 제1목표

**harness-maker 의 제1목표는 기본 품질을 지키면서 빠르고 효율적인 워크플로를 만드는 것이며, 복잡한 설계를 지양하고 단순하고 효율적인 쪽을 택한다. HOW 는 AI 가 최대한 가져가되 WHY·WHAT·트레이드오프는 사람이 소유하고, 작업이 끝나면 코드와 함께 사람의 시스템 이해도 갱신되게 한다.**

> 아래의 모든 원칙·게이트·에이전트는 이 목표에 종속된다. 어떤 장치가 품질을 지키는 것보다 워크플로를 느리고 복잡하게 만드는 데 더 기여한다면, 그 장치를 줄이거나 없애는 것이 옳은 방향이다.
>
> 대상은 1인 시니어 개발자다. 시니어에게 필요한 건 설명이 아니라 바뀐 가정과 위험을 드러내는 것이다. 그래서 학습·코칭 모드, 역량 평가, 팀 협업 기능은 만들지 않는다. 결정 주체 규칙과 지표는 `.claude/intent.yaml` 에 있다.

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

`harness.yaml.targets: list[Target]` — 사용자 하네스가 어느 IDE 에서 작동할지 결정하는 축. preset 과 직교.

- **값**: `claude-code` | `cursor` | `codex` (multi-select)
- **인터뷰 정책**: 명시 multi-select 강제. **auto-detect 금지** (`.cursor/` 디렉토리 존재 여부 등으로 추론하지 않음). 사용자 의도 확인 필수.
- **Default fallback**: 옛 harness.yaml 에 `targets` 키 없을 때만 `[claude-code]` silent fallback + 경고 로그. 신규 인터뷰는 항상 명시 선택.
- **Single source 원칙**: agents / skills / hooks / MCP 자산은 `.claude/` 한 곳에서 양쪽 IDE 가 공유 (Cursor 가 `.claude/agents/` 를 native 로 읽음, hooks schema 호환 — IDE 모드 인식은 Phase 1 manual 검증 결과 따름).
- **Cursor 추가 자산**: `targets` 에 `cursor` 포함 시에만 `.cursor/rules/harness.mdc` (`alwaysApply: true`), `.cursor/hooks.json`, `.cursor/mcp.json` 추가 렌더 (`synthesize._cursor_target_files`). 슬래시 명령은 Cursor 가 `.claude/commands/hm/` 를 native 로 읽으므로 별도 렌더 없음.
- **Cursor 사용자 모델 권장**: `harness.yaml.recommended_model: claude-opus-4-7` + agent frontmatter `model` 명시. user override 자유. prompt 자체는 model-agnostic 재작성 안 함 (`<thinking>` blocks 등 Claude-specific 표현 유지).
- **최소 지원 Cursor 버전**: 2.4 (subagents + skills + Claude Code hooks 호환 최초 도입). Cursor 3.0 이상 권장.
- **Codex dual role** (PLAN-codex-second-llm-integration ADR-009): `codex` 는 IDE asset 렌더링 (`.codex/`) 뿐 아니라 second-LLM provider 역할도 한다. 이 provider 축은 **`harness.yaml.second_opinion`** (PLAN-second-opinion-multi-model 이 옛 `codex_second_opinion` 을 대체) 로 제어된다 — `targets` 와 직교. 자세한 건 아래 **Cross-model second opinion (multi-model)**.
  - **Cross-model second opinion (multi-model)** — full rules: [`docs/reference/second-opinion.md`](docs/reference/second-opinion.md). Load-bearing rules:
    - `harness.yaml.second_opinion.models` (`codex`/`antigravity`, orthogonal to `targets`). Every CLI call goes through `harness_maker.second_opinion_invoke`; never inline a raw CLI in a recipe (four silent-skip bugs shipped that way).
    - k-of-N consensus with K=2 fixed; PIDA acceptance gate plus a vote freeze (one model call per `/hm:review`); every failure mode is warn-and-proceed.
    - Never hand-compute ledger rates. Use `hm verifier_discrimination report --ledger .claude/observability/second-opinion.jsonl`. It applies `.ledger-exclusions.json`; a hand count was 30× off.
    - A green `/hm:health` smoke proves the base path only, not the worktree path.

```
hm verifier_discrimination report --ledger .claude/observability/second-opinion.jsonl
```

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
- `hooks/hooks.json` (at the **plugin root**) — the plugin bundle's own hooks. This is a real, documented Claude Code hook location and it is why `sessionstart_drift` works. Do NOT confuse it with the rendered `.claude/hooks/hooks.json` (see below).
- **Hook schema diverges by design**: Cursor IDE reads `.cursor/hooks.json` (lowercase camelCase + `version: 1`); Codex reads `.codex/hooks.json`. Each IDE owns its own file with its own native schema. Verified empirically via kairos 0.5.7 metrics forensic 2026-05-08 (`tests/cursor-compat/results-2026-05-08.md`). Do NOT collapse to single source — Cursor 2.4+ hooks-compat docs apply to CLI only, IDE reads the dedicated `.cursor/` location.
  > **Cursor `sessionStart` (2026-08-16).** Cursor renders **one** hook on this event —
  > `autopilot_autoarm` — where Claude Code and Codex render two. The event is real, not
  > assumed: Cursor's extension host carries the hook-event enum (`sessionStart` sits beside
  > the four events already rendered) and an explicit Claude→Cursor mapping table
  > (`{PreToolUse: preToolUse, …, SessionStart: sessionStart, …}`). Before this, Cursor
  > rendered **no** session event at all, so `autopilot_persistent: true` armed on two
  > runtimes out of three and nothing reported the difference.
  > **`sessionid_envfile` is excluded on purpose** — it writes to `$CLAUDE_ENV_FILE`, which
  > does not exist in Cursor (zero occurrences in the same bundle), so its `main()` would take
  > the `env_file is None` early return every time. Adding it "for parity" ships a hook that
  > provably cannot act — the `.claude/hooks/hooks.json` mistake again. Cursor sessions are
  > therefore id-less **by design** and share `.hm-autopilot-degraded`. Gate:
  > `tests/unit/test_render_cursor_session_start.py`.
  > **⚠️ Corrected 2026-07-17.** This line used to say "**Claude Code reads `.claude/hooks/hooks.json`** (PascalCase + nested)". **False.** Claude Code reads project hooks **only** from settings files (`hooks.md`'s location table); `hooks/hooks.json` is a *plugin-bundle* path. Every hook harness-maker rendered to `.claude/hooks/hooks.json` was dead **in Claude Code** — Cursor and Codex were unaffected. The claim came from the 2026-05-08 forensic, which asked only "does Cursor read `.cursor/hooks.json`?" (yes) and never checked the Claude half; the untested half became this assertion. Refuted by controlled experiment on 2026-07-17 — see `[wiki:architecture] hooks-load-from-settings-not-hooksjson`. Claude hooks now render into `.claude/settings.json`'s `hooks` key (PLAN-permission-deny-and-hooks-wiring).
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
- `.claude/settings.json` — permissions + preset + **`hooks`** (Claude Code 가 프로젝트 hook 을 읽는 **유일한** 위치. harness-owned 이지만 deep-merge — 사용자 hook 보존)
- ~~`.claude/hooks/hooks.json`~~ — **더 이상 렌더되지 않음** (0.52.0 기준). Claude Code 가 읽지 않는다는 게 2026-07-17 실험으로 확정된 뒤 ADR-005 (PLAN-permission-deny-and-hooks-wiring) 가 렌더를 제거했다. 디스크에 남은 pristine 사본은 `cli._retire_stale_hooks_json` 이 은퇴시키고 (정확히 일치할 때만), 사용자가 손댄 사본은 `reconcile._SWEEP_NEVER_DELETE` 가 지킨다. 새 hook 은 `settings.json` 의 `hooks` 키로.
- `.claude/lib/`, `.claude/observability/`
- `.worktrees/` (gitignored)

**Cursor target 추가** (`targets` 에 `cursor` 포함 시):
- `.cursor/rules/harness.mdc` — 고정 템플릿 `templates/cursor/rules/harness.mdc.j2` 하나 (`alwaysApply: true`, `globs: []` — 경로 스코프 규칙 아님)
- `.cursor/hooks.json` — Cursor native camelCase hooks (위 "Hook schema diverges by design")
- `.cursor/mcp.json` — MCP server (Cursor 별도 위치)
- `.cursor/commands/` 는 **렌더되지 않는다** — Cursor 2.4+ 가 `.claude/commands/hm/*.md` 를 native 로 읽는다 (kairos 0.5.7 forensic, `tests/cursor-compat/results-2026-05-08.md`). `render.py` 의 `.cursor/commands/` dispatch 는 회귀 대비 예약 코드일 뿐 공급 템플릿이 없다.

**Codex target 추가** (`targets` 에 `codex` 포함 시):
- `.codex/config.toml` — Codex CLI 전역 설정 (features, mcp_servers)
- `.codex/hooks.json` — Codex hooks (PascalCase + PermissionRequest 이벤트)
- `.codex/agents/<name>.toml` — 에이전트 TOML (developer_instructions = agent body)
- `AGENTS.md` — 프로젝트 루트 instructions (block-merge markers 포함)
- `.agents/skills/<name>/SKILL.md` — 기존 skill 의 Codex 경로 dual-render (개수는 `templates/skills/` 가 소스; 고정 숫자를 여기 적으면 skill 하나 추가할 때마다 이 줄이 조용히 틀려진다)
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

Full text, including the 2026-06-02 enforcement correction: [`docs/reference/security-permissions.md`](docs/reference/security-permissions.md).
- Claude Code does **not** enforce agent frontmatter `permissions:`; it was removed in 0.40.0. The only real boundary is `tools:`. A reviewer has no Bash, so it cannot run anything. For an executor, "no writes outside `.worktrees/**`" is a prompt instruction, not an enforced rule.
- Main-session `settings.json` deny is opt-in (default OFF, `permissions.deny_dangerous`). `Write(<path>)` and `Bash(curl * | sh)` are dead syntax. `curl|sh` is caught by the `permission_gate` hook.
- Every generated file carries `generated_by + content_hash + source_template + harness_maker_version` in its frontmatter.

## Context Lint (v1.6)
- CLAUDE.md ≤ Side 200행 / Production 500행, **그리고** ≤ Side 16,000자 / Production 40,000자 (문자 예산 — 매 턴 로드되는 문서라 밀도가 비용이다; AGENTS.md 동일)
- agent prompt ≤ 300행 (양 preset 공통, 0.45.0 에서 150/200 → 300)
- skill SKILL.md ≤ 300행 (양 preset 공통, 0.45.0 에서 100/150 → 300)
- `.cursor/rules/*.mdc` ≤ 500행 (Cursor 권장. 분할 권장 임계 200행)
- 초과 시 renderer 가 warn

## 리뷰어 팬아웃은 언어 조건부다 — 기록만, 라우팅은 안 한다

Deliberately deferred; this has not been left unreviewed. Full reasoning: [`docs/reference/reviewer-fanout.md`](docs/reference/reviewer-fanout.md). `reviewers.enabled` does **not** reduce the fan-out, because `lens_dispatch` never reads it. Language routing without data is on hold.

## Step sensitivity classes (COMP / HOST / INV / TUNE)

`src/harness_maker/step_sensitivity.py` 가 렌더된 7 stage 의 모든 `Step|Phase|Check` 헤딩에
감도 클래스를 붙인다 (PLAN-workflow-steps-vs-model-capability). **COMP** = 모델 능력 보상 —
모델이 좋아질수록 줄여도 되는 산문. **HOST** = 호스트 하네스(Claude Code/Codex/Cursor)가 이제
네이티브로 하는 것. **INV** = 모델과 무관하게 유지 — 컨텍스트 창을 넘어 살아남는 상태, 결정적
oracle, 사람의 lock-in, 이종 모델. **TUNE** = 모델마다 값이 뒤집히는 것 (auto-fix cap, A.5,
plan-validator, fan-out) — `remeasure_on`/`measure_cmd` 필드가 재측정 트리거를 들고 있고, 측정
전엔 새 모델로 전이하지 않는다 (harness-bench "reversed between models").

- **강제**: `tests/structural/test_step_sensitivity_registry.py` — `ARMS` = preset 당 1개(기본
  strictness) 렌더의 모든 헤딩이 레지스트리에 있어야 하고(무분류 헤딩 = 테스트 실패), Side 기본값은 knob 을
  가진 어떤 엔트리(HOST 포함)에서도 Production 보다 공격적일 수 없다 (`knob`/`ordering`, 비공허 바닥 ≥3).
  렌더는 레지스트리를 읽지 않는다 — 검사이지 파생이 아니다 (ADR-005).
- **증거 등급**: `***`/`**`/`*` 는 harness-bench 관례, `unsourced: 32` 는 기준을 충족하는 근거가
  없는 항목 수 — RESEARCH 행 없이 이웃에서 상속했거나 (ADR-009), 조사했지만 찾지 못했다
  (`RESEARCH-source-plan-steps`). TUNE 수치는 전부 **Side-preset only, n=** 표기 —
  stage-agent ledger 에 Production 행이 0 이다. FAIL 율은 가치 증명이 아니다 (plan-validator 는
  40건 중 37건 MAJOR_REVISION — 변별력 미입증).
- **커버리지 한계** (ADR-007): `second_opinion.models`/`delegation`/`mechanical_checks` 토글로
  게이트된 헤딩은 `renders_when` 만 적고 커버리지 약속 밖이다 — toggle on-arm 추가는 후속.
- **모델 릴리스 시**: `grep TUNE src/harness_maker/step_sensitivity.py` 로 재측정 대상을 뽑고
  각 `measure_cmd` 를 돌린 뒤 등급/클래스를 갱신한다. 캡·산문 삭제는 그 결과로만.

## Workflow (autoloop CODER 가 알아야 할 점)
- **Atomic stage**: 7개 (research/spec/plan/execute/review/wrapup/verify)
- **Stage 연결** = `/hm:loop --per-iter-stages` 또는 autopilot. 융합 명령 축은 0.47.0 에서 제거됨 (PLAN-harness-diet ADR-001/002).
- Renderer 가 stage prompt fragment 들을 합성해 단일 명령 파일 생성

## Context discipline

도구가 반환한 것은 세션이 끝날 때까지 컨텍스트에 남아 매 턴 다시 읽힙니다. 측정 결과 메인 루프가 지출의 87.9%를 carry 70.0%로 나르고, 아래 두 습관이 그 무게의 약 20%입니다 (`work-docs/RESEARCH-context-carry-economics-2026-07-28.md`). 둘 다 피하는 데 비용이 들지 않습니다.

- **검색·조회 출력에 상한을 걸 것.** `rg` / `grep` / `find` / `ls` / `cat` / `head` 의 출력은 전량 컨텍스트로 들어옵니다 (16.0%). 호출 시점에 자릅니다 — Grep 도구의 `head_limit` 을 우선 쓰고, raw `rg` 는 `| head -50` 을 통과시킵니다. 상한을 늘리기 전에 패턴을 좁히십시오. 한 가지를 찾으려고 파일을 `cat` 하지 마십시오 — offset 을 준 Read 나 grep 을 쓰십시오.
- **컨텍스트가 이미 가진 파일을 다시 보내지 말 것.** 기존 파일에 대한 `Write` 는 사전 `Read` 를 요구하므로, 전체 재작성은 본문을 두 번 넣습니다 (3.8%). **이미 읽은** 파일의 수정에는 `Edit` 을 쓰고, `Write` 는 새 파일과 내용 대부분이 실제로 바뀌는 재작성에만 씁니다. PLAN/SPEC/REVIEW 같은 큰 문서에서 차이가 가장 큽니다 — 재작성 한 번이 수만 자를 복제합니다.

> 효과는 `uv run python -m harness_maker.economics composition --root .` 로 다시 재서 확인합니다. 이 지시는 hook 으로 강제되지 않으므로 그 재측정이 유일한 검증 수단입니다.

## 실행 주의
- Worktree base_dir 는 `.worktrees/` (Cursor 와 공유). 사용자 프로젝트의
  `.gitignore` 에 추가는 사용자 책임 — 본 repo 자체는 gitignore 됨.
- `.claude/.hm-loop-active` 은 자동 gitignore 추가 (worktree.create 시
  idempotent line-append; H3 round). marker 가 commit 되면 협업자 측에서
  존재하지 않는 worktree path 로 gate 가 블록 → 강제 footgun.
- 100% 로컬 telemetry — 외부 전송 금지

## Multi-session worktree (PLAN-worktree-cross-session-data-loss-defense + PLAN-multisession-worktree-concurrency)

Full specification (per-task model, 5-layer defense, loop-marker and per-session marker scoping): [`docs/reference/multi-session-worktree.md`](docs/reference/multi-session-worktree.md). **Read it before touching `worktree.py`, `loop_marker.py`, `autopilot.py` or `worktree_gate.py`.** Invariants that break most often:
- There is exactly one reader, `worktree.worktree_enabled(base)`, and exactly one writer, `cli._apply_worktree_enabled`. A true→false flip is refused while a task worktree, stash or loop marker is live.
- Flag ON: `task-create/preflight/refresh/land` on `hm/<slug>`. `/hm:wrapup` lands exactly one squash commit. Flag OFF (the `/hm:loop` `execute-<uuid>` worktree): the 5-layer defense stays active.
- `[finalize] stash-pop conflict`: never recommend `git stash drop` without first showing `git stash show -p <ref>`. Recover with `git reflog --all | grep "wip(execute)"` → cherry-pick.
- Queue-guard foreign counting is load-bearing; do not make it per-session.
- `HM_SESSION_ID` is a **shell variable**, never exported. A Python consumer must take it as an explicit argument, and a new marker content field must update **every** reader.
- Marker APIs take `session_id` as a required keyword argument, enforced by an import-graph test. Do not reuse the `.hm-loop-` prefix for task markers. `worktree_gate` fails open when the payload has no `session_id`.

## World model (Maker) (SPEC-world-model-name + SPEC-world-model-followups + SPEC-maker-front-door-improvements)

Maker (`templates/skills/world-model/SKILL.md.j2`, rendered at `skills/<handle>/`) is the one front door to the intent layer, project knowledge and task state. Full text: [`docs/reference/world-model.md`](docs/reference/world-model.md). Invariants that break most often:
- **Only entrance.** `intent-layer` / `project-knowledge` stay `disable-model-invocation: true` (Codex: `openai.yaml` `allow_implicit_invocation: false`); Maker Reads their SKILL.md before any write. Never make them model-invocable again or add another self-triggering entrance.
- `hm autopilot narrow` **never arms or widens**: it recomputes from `restore_pipeline` and is a no-op at `gated` / no marker / foreign marker. `restore_pipeline` is a marker field — every `.hm-autopilot*` reader must accept it.
- `hm world_model digest` stays ≤ 1,500 bytes and **always exits 0**. A new field must fit the trim order (`recent` → intents → tasks → timing → `latest_artifact`); `other_session` is never dropped.
- Always-loaded pointers: `## World model` ≤ 400 chars, `## Project knowledge` ≤ 300 chars per variant; Maker SKILL.md ≤ 4,500 chars.
- Maker `allowed-tools` stays scoped to `hm world_model:*` + `hm autopilot narrow:*` (plus `tail`/`grep`/`printf`). Never widen to `hm *` or `uv run:*`; the injected chain uses no `{ …; }` group, because a permission matcher that splits on `|`/`||` would see a piece starting with `{` (acceptance of the ungrouped chain is still unverified in a live session).

## Second Brain 승급 파이프라인 (PLAN-second-brain-promotion)

Local `.claude/memory/` feeds a promotion pipeline into the Obsidian Second Brain. Wrapup Step 5.6 must evaluate every time; only entries that pass the "cross-project durable?" check are promoted, via `second_brain promote` (idempotent). The vault is a separate repo. Full text: [`docs/reference/second-brain-promotion.md`](docs/reference/second-brain-promotion.md).

## Autoloop 빌드 중 모호함 발생 시
1. TECH_SPEC.md Section 4 의 phase task 우선
2. 본 CLAUDE.md 우선
3. `docs/reference/autoloop-pattern.md` 의 autonomous decision protocol (DD#8) 따름 — log 후 진행
4. **AskUserQuestion 호출 금지**

## 구현 패턴 (CODER 가 따라야 할 코드 관례)

**→ [`docs/reference/implementation-patterns.md`](docs/reference/implementation-patterns.md)**
에 전문이 있다. 담긴 것: atomic file write 강제 패턴 (`plain open(path,"w")` 금지),
LLM mock 픽스처 규약, worktree cleanup 정책 (`harness.yaml.worktree.cleanup` 은 존재하지 않는
키다), 렌더 컨텍스트 플래그를 출력 경로에서 파생시키는 규칙 (`is_codex`), snapshot 결정성,
외부 명령 호출 규약 (`shell=True` 금지 · timeout 필수), communication variant 정책.
**구현을 시작하기 전에 읽을 것** — 여기 요약은 목차이지 규칙이 아니다.

## 무언가를 고치거나 개선하기 전에 — 필수 체크리스트

**→ [`docs/reference/pre-change-checklist.md`](docs/reference/pre-change-checklist.md)**
에 8개 체크포인트 전문이 있다. 각각 "현실에서 한 번 깨졌던 사례 + 다음엔 어떻게 미리 잡을지"
형태: (1) 사용자 상태 보존 계약, (2) 외부 소비자 정합성 — parser 와 **전처리기** 양쪽,
(3) 설정 precedence, (4) CLI 와 slash 명령의 책임 분리, (5) fingerprint 기반 자동-업그레이드
분기, (6) 양방향 매퍼, (7) 테스트 결정성 + 환경 격리, (8) integration 경계 테스트.
**다음 fix/feature 시작 전에 반드시 읽고 통과시킬 것.**

## 사용자 voice
- 직접적 (no preamble, no flattery)
- 우려 먼저, 동의 나중
- 동의 시 WHY 설명
- 새 증거 없이 fold 하지 않음

---

*Cross-refs last verified: 2026-05-07 (0.5.x). TECH_SPEC.md §4 / docs/reference/autoloop-pattern.md DD#8 / tests/cursor-compat/MANUAL_CHECKLIST.md — 모두 유효.*
