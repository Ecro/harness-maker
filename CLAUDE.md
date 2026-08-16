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
- **Codex dual role** (PLAN-codex-second-llm-integration ADR-009): `codex` 는 IDE asset 렌더링 (`.codex/`) 뿐 아니라 second-LLM provider 역할도 한다. 이 provider 축은 **`harness.yaml.second_opinion`** (PLAN-second-opinion-multi-model 이 옛 `codex_second_opinion` 을 대체) 로 제어된다 — `targets` 와 직교. 자세한 건 아래 **Cross-model second opinion (multi-model)**.
  - **Cross-model second opinion (multi-model)** (PLAN-second-opinion-multi-model, supersedes PLAN-codex-second-llm-integration + PLAN-crossmodel-codex-gaps): `harness.yaml.second_opinion.models: list[Literal["codex","antigravity"]]` — 활성 모델 집합 (빈 리스트=off). Codex CLI (`codex exec`) 와 Antigravity CLI (`agy --sandbox --print`, project-less) 를 각각 독립 second-opinion voter 로 붙일 수 있고 **둘 다 동시** 가능. **두 CLI 호출은 `harness_maker.second_opinion_invoke` 가 단독 소유한다** (PLAN-second-opinion-invocation-and-slug-cap ADR-001) — 렌더된 레시피는 `uv run … -m harness_maker.second_opinion_invoke --model <m> --prompt-file <f>` 한 줄로 축소됐고, `/hm:health` smoke 도 **같은 entrypoint** 를 호출한다 (ADR-005). 레시피에 raw CLI 를 다시 인라인하지 말 것: prose 레시피는 실행 표면이 없어 render 테스트가 텍스트 grep 밖에 못 하고, 그 형태로 silent-skip 버그가 4번 출하됐다. 옛 `codex_second_opinion.enabled=true` harness 는 `answers_from_harness_yaml` 의 1회성 silent migration (ADR-001, schema_version 2→3) 으로 `second_opinion.models=["codex"]` 로 자동 변환 (both-keys-present 면 new-key-wins + advisory 1회). 축은 `targets` 와 직교 — `targets` 에 `codex`/`agy` 없어도 활성 가능 (사용자 측 CLI + login 만 있으면 됨).
    - **k-of-N consensus, K=2 고정** (ADR-006): `/hm:review` Step 3.5 가 각 활성 모델을 **정식 투표권**으로 합류 (voter pool N = enabled reviewers + `len(models)`). `codex_adapter` 가 severity `critical→P0…` 매핑 + null-location symbol/message-similarity relaxation → Step 4 filter. threshold 는 모델을 더 켜도 **K=2 고정** (`conditional_router.scope_aware_consensus` 의 `len(reviewers)>=2` — Python 변경 0, prose 만 일반화). recall-favoring: 모델 추가는 consensus 를 *쉽게* 만든다.
    - **per-model config sub-block** (ADR-002): `second_opinion.{failure_policy, agents}` 는 공유 (agents = global allowlist, 모든 모델에 동일 적용); `second_opinion.codex.{hermetic, output_schema_path}` 와 `second_opinion.antigravity.{model}` 는 모델별. antigravity `model` 은 free-text 표시 이름 (`agy models` 가 안정적 machine ID 없음), **인터뷰 시점에만** live shell-out, **render 는 절대 shell-out 안 함** (ADR-007 결정성).
    - **mandatory 매트릭스** (ADR-003): Production = **모든 활성 모델**을 review+plan 마다 강제 / Side = high-diff 시에만. 활성 모델 균등 적용 (2x 비용 감수).
    - **graceful degrade** (ADR-011; 분기 정의는 PLAN-second-opinion-invocation-and-slug-cap ADR-008 이 supersede): CLI 미설치 / login 만료 / rate-limit·구독 초과 / timeout / 파싱 불가 — 전부 warn-and-proceed. **`exit 127` 은 더 이상 CLI 미설치의 신호가 아니다** — invoker 는 `shell=False` 로 돌기 때문에 127 을 만들어주던 쉘이 없고, 미설치는 `FileNotFoundError`, timeout 은 `TimeoutExpired`, 실행권한 없음은 `PermissionError` 로 **예외로 온다**. 7분기 매트릭스(예외 3 + non-zero exit + payload 획득 실패 + validate 실패 + 성공)가 이걸 전부 흡수하며, `resolve_base_root`/`load_config` 의 shell-out 도 같은 보호를 받는다 (git 부재 시 cwd fallback 후 **진행** — skip 아님). agy 는 hang 가능 → agy native `--print-timeout 240s` 를 계속 쓰고, process-level `AGY_TIMEOUT_S=300` 은 그보다 **위**에 있는 바깥 backstop 이다 (native 가 먼저 발화해 agy 자신의 진단이 남도록). 옛 "external `timeout` 래퍼 금지" 규칙의 근거는 allow-rule prefix 매칭이었고 ADR-001 이후 그 근거는 사라졌다 — `subprocess.run(timeout=)` 은 금지 대상이 아니다. Codex 는 `--output-schema` 로 JSON 강제; **antigravity 도 CLI-레벨 강제가 있다 — 플래그 이름이 다를 뿐이다** (`--output-format json --json-schema <path>`, 2026-08-08 probe. 옛 "CLI-레벨 강제 없음" 서술은 `--output-schema` 라는 철자만 찾아본 결과였고, 그 오기가 여섯 곳에 복제돼 파싱 실패 9건의 원인이 됐다 — PLAN-antigravity-second-opinion-timeout ADR-002/006). 단 **강제는 best-effort** 다: `status: SUCCESS` 응답에서도 `structured_output` 키가 없는 경우가 관측됐으므로 `codex_adapter.extract_antigravity_payload` fail-closed 경로는 **폐기가 아니라 필수 fallback** 으로 남는다 (4-case 표: 파싱불가→failed / status≠SUCCESS→skipped / structured_output dict→그대로 쓰되 validate 실패는 fail-closed / 부재→`response` 를 tolerant 추출). plan-validator 는 **PIDA** (KEEP/REFUTE → oracle 없으면 `unresolved` surface, never-block).
    - **output contract** (ADR-008): plan stage 는 `second_opinion_results: [{model, status: invoked|skipped|failed, reconciliation: [...]}]` 배열 (모델당 정확히 1 entry). 옛 scalar `codex_status`/`codex_reconciliation` 대체. review stage 는 persistent status field 없음 (findings 를 `source: "<model>"` 태그로 Step 4 에 fold).
    - **PIDA 수용 게이트 + vote freeze** (PLAN-second-opinion-acceptance-gate): review 경로에도 반박 게이트가 생겼다. `/hm:review` Step 3.4 가 **모든** finding (Claude 것 포함) 에 `codex_adapter.finding_id` 로 불변 `id` 를 찍고 (리뷰어는 `id` 를 내보내지 않는다 — LLM 이 만들면 매 실행 달라져 안정성이 깨짐), Step 3.6 이 분쟁 finding 이 지목한 경로에 targeted `pytest`/`ruff`/`mypy` 를 돌려 **예산 4000자 / 명령당 1500자 + 가시 절단마커 + `id` 연결 + 자격증명 라인 필터** 를 걸어 주입하고, Step 3.7 이 `code-verifier` **mode B** 로 ledger enum (`accepted`/`rejected`/`duplicate`/`unresolved`) 을 **직접** 판정한다 (KEEP/REFUTE 중간 어휘 없음 — 번역 단계가 있으면 그 매핑 실패로 행이 조용히 사라진다). `accepted` 만 Step 4 투표권을 얻고, `unresolved` 는 `manual-only` + `unverified_severe` 스캔의 **유일한 provenance 예외** (ADR-004 — 가시성 회귀를 수용한 의도된 선택). **Phase 0 mechanical checks 를 oracle 로 재사용하지 말 것** — `reviewers.mechanical_checks` 로 가드되어 이 repo 에선 렌더 자체가 안 되고, 렌더돼도 Round 1 위에서 1회만 돌며 stop-on-first-failure 라 살아남은 라운드에선 항상 all-green 이다. 모델은 `/hm:review` 당 **정확히 1회** 호출되고 rounds 2..N 은 REVIEW 의 `## 🧊 Cross-model findings (frozen @ round 1)` 섹션을 다시 읽는다. Auto-Fix Loop 은 **단조 격자**(`pending`→`resolved`/`stale` 만 progress; `→ pending` 은 절대 아님)와 **1회 무진전 라운드 종료**(단 **round ≥ 2** 에서만 평가 — round 1 은 fix 단계가 없어 progress 전이가 원리적으로 0이라 무조건 규칙이면 auto-fix 가 아예 안 돈다)를 갖고, 라운드별 voter state 는 **`id` 기준 merge** 다 (wholesale replacement 금지 — 리뷰어 비결정성만으로 corroborating voice 가 사라져 코드 변경 없이 등급이 움직인다). `resolved` 는 **verification 성공 후에만** — revert/skip 된 fix 는 `pending` 유지.
    - ledger `.claude/observability/second-opinion.jsonl` 는 **두 종류의 행**이 공존한다: `finding_ref == "n/a"` = **호출당 1행** (skip-rate 분모), `finding_ref != "n/a"` = **finding 당 disposition 1행** (accept-rate, `oracle_result` 에 capped PIDA 근거). **둘 다 `status: "invoked"` 이므로 `finding_ref` 가 유일한 판별자** — 필터 없이 집계하면 finding 마다 호출 1건으로 세어 skip-rate 가 조용히 오염된다. disposition 행은 `hm second_opinion_invoke --record-disposition --disposition-file <path>` 로만 쓴다 (argv JSON 금지 — quoting + `ARG_MAX`; `codex_ledger emit` 은 `Path.cwd()` 에 써서 worktree row-loss 재발). 실패는 exit 0 + `[second-opinion] disposition rows NOT recorded:` stderr 1행 (조용한 no-op 금지). `oracle_result` 는 `max_length=200` 이고 invoker 의 row emission 이 예외를 삼키므로 `codex_ledger.cap_oracle_result` 로 **검증 전에** 자른다 — 안 자르면 행 전체가 소실된다. invoker 가 **base repo root** 기준으로 쓴다 — 옛 `codex_ledger.main()` 의 `project_root=Path.cwd()` 는 worktree 안 gitignored 경로에 기록해 `task-land` 시 소실됐다. 행이 skip 전용에서 호출 전체로 바뀌었으므로 **분모가 바뀌었다**: **`(skipped + failed) / total` 을 모델별로** 계산하고 `stage: "health"` 행은 제외할 것 (smoke 는 base cwd + 사소한 프롬프트라 구조적으로 `invoked` 편향). **`failed` 를 빼거나 모델을 합치면 안 된다** — `failed` 는 CLI 가 돌았지만 Step 4 가 못 먹는 payload 라 그 모델 목소리가 없는 건 skip 과 동일하고, 건강한 모델이 고장난 모델을 희석한다. 2026-08-06 실측: 옛 `skipped/total` 이 10.3% 를 보고할 때 실제는 20.7% 였고 한 모델 손실 전량이 `failed` 행에 있었다 (집계 20.7% vs 모델별 2.4% / 37.8%). `stage` 는 `review|plan|health` (Python `Literal` 과 출하 JSON enum 양쪽 확장 — 이름만 비교하던 parity 테스트가 enum 값에 대해 불변이었다).
    - `/hm:health` 가 per-model positive smoke-test 로 silent-degradation 을 잡되, **base 에서만 돈다** (worktree preflight 없음). 초록 = "공유 호출 경로가 base 에서 동작". worktree 분기(base-root/config 해석)는 유닛 테스트와 수동 검증이 담당 — 초록 `/hm:health` 를 Production 경로의 증거로 읽지 말 것. 그 추론이 H1 을 수명 내내 가렸다.
    - antigravity sandbox 안전성 (`tests/manual/ANTIGRAVITY_SANDBOX_PROBE.md`, ADR-012): project-less `agy --sandbox --print` 는 file 도구 미노출 → working-tree mutation 불가. **2026-07-25 재검증 완료:** 옛 probe 는 `agy --print --sandbox …` 형태로 돌아 `--sandbox` 가 프롬프트 값으로 소비됐다 — 즉 sandbox 가 적용되지 **않은** 명령을 관찰하면서 "sandbox 가 안전하다"를 주장하고 있었다. 교정된 `agy --sandbox --print "<prompt>"` 로 `INTEGRATION=1 pytest tests/integration/test_antigravity_sandbox_probe.py` 재실행 → 통과 (명시적 파일 수정 지시에도 대상 파일 불변). 결론은 그대로지만, 이제 근거가 실제로 그 명령을 검증한다. loop 는 stage-level 이라 자동 상속.

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
- `.cursor/rules/<name>.mdc` — Cursor rules (CLAUDE.md 의 .mdc 변환본)
- `.cursor/commands/hm-<name>.md` — Cursor 위치의 슬래시 명령 (Phase 1 검증 결과 따라 `.claude/commands/` 만으로 가능할 수 있음)
- `.cursor/mcp.json` — MCP server (Cursor 별도 위치)

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

- **Agent frontmatter `permissions:` 블록은 0.40.0 에서 전부 삭제됨** (Phase 7, ADR-002). subagent frontmatter 에 `permissions` 필드가 없어 Claude Code 가 silent-ignore 했고, 집행 0 인데 보안 경계처럼 읽혀 incoming brief 작성자를 오도했다. 진짜 경계는 `tools:` 뿐 (도구 부재 = 사용 불가). Reviewer agent 는 `tools:` 에 Bash 미포함 → `python -c`/`sh -c` 우회 자체가 불가 (이건 집행됨). Executor 는 `tools:` 에 Write/Edit/Bash 포함 → frontmatter deny 유무와 무관하게 경로 제한 없음. `.worktrees/**` 밖 write 금지는 **프롬프트 지시**이지 런타임 강제가 아니다 (executor_body.md.j2 의 "Scope — instruction, not enforcement").
- **Main-session `settings.json` deny (opt-in, default OFF — 2026-05-31):** 위 reviewer/executor *agent* deny 와 별개로, 사용자 메인 세션의 `settings.json.permissions.deny` 는 **기본 빈 리스트**다 (`rm`/`curl|sh`/`/etc`/`~/.ssh` write 미차단 — 솔로 작업 효율). 전체 destructive baseline 은 `harness.yaml.permissions.deny_dangerous: true` 로 opt-in → `["Bash(rm:*)", "Edit(/etc/**)", "Edit(~/.ssh/**)", "Edit(~/.aws/**)"]` 렌더 (0.40.0, Phase 5). **옛 리스트 `["Bash(rm:*)", "Bash(curl * | sh)", "Write(/etc/**)", "Write(~/.ssh/**)"]` 은 4개 중 3개가 죽은 문법** — `Write(<path>)` 는 file-permission check 가 Edit/Read 만 보므로 미집행, `Bash(curl * | sh)` 는 `|` 가 separator 라 subcommand 분할 후 매치 불가 (silent). `curl|sh` 탐지는 settings 규칙이 아니라 `permission_gate` PreToolUse hook 의 몫 (ADR-003). 재렌더 시 `_HARNESS_SHIPPED_DENY_LITERALS` 가 harness 가 실제 발행한 **죽은** literal 만 prune (live `Bash(rm:*)`/`Bash(curl:*)` 은 대체 hook 배선 전까지 보류 — `is_matchable_rule` 이 안전 불변식, `test_permission_syntax.py` 가 회귀 차단). **Why**: 솔로 프로젝트에서 `Bash(rm:*)` 기본 차단이 비효율적이라는 사용자 피드백. **Reviewer agents 는 `tools:` 에 Bash 부재로 rm 자체 불가** (read-only). `readiness.py` 의 `permissions_deny_present` / `deny_covers_dangerous` 두 signal 은 opt-out 시 N-A (passed=True, no penalty) — 의도된 config 선택은 finding 이 아님. 스키마: `models.PermissionsConfig.deny_dangerous` (default False), 양 `settings/*.json.j2` 가 `config.permissions.deny_dangerous` 로 분기.
- 모든 generated 파일은 frontmatter 에 `generated_by + content_hash + source_template + harness_maker_version`

> **Cursor target 의 권한 매핑** (Phase 1 검증 결과 채움):
> Cursor 의 `permissionMode`, `sandbox.json` 등가물이 위 allow/deny 정책을 어떻게 강제하는지 미정의. Phase 1 검증 fixture 로 확인 후 본 섹션 갱신.

## Context Lint (v1.6)
- CLAUDE.md ≤ Side 200행 / Production 500행
- agent prompt ≤ 300행 (양 preset 공통, 0.45.0 에서 150/200 → 300)
- skill SKILL.md ≤ 300행 (양 preset 공통, 0.45.0 에서 100/150 → 300)
- `.cursor/rules/*.mdc` ≤ 500행 (Cursor 권장. 분할 권장 임계 200행)
- 초과 시 renderer 가 warn

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

두 모델이 **`harness.yaml worktree.enabled`** 플래그로 직교 공존한다 (default **True**=Production / **False**=Side). 옛 `feature_branch_workflow` / `scope` / `branch_prefix` 는 **0.48.0 에서 은퇴**됐다 (PLAN-worktree-side-defaults ADR-001/007) — 4개 노브 중 3개가 런타임 효과 0 이었고, `scope`/`branch_prefix` 는 템플릿 리터럴이라 손편집이 재렌더마다 조용히 되돌려졌다.

- **단일 리더**: `worktree.worktree_enabled(base)` 하나뿐. 3세대 fallback (`enabled` → 레거시 `feature_branch_workflow` → 레거시 `scope` 에 `execute` 포함 → 부재=False+경고 1회), first-key-present-wins. **present-but-malformed 는 fail-closed 로 체인을 종료**한다 (하위 stale 키로 fall-through 하면 `enabled: "false"` 옆의 `feature_branch_workflow: true` 가 격리를 *켜버린다*). `tests/unit/test_worktree_reader_singleton.py` 가 두 번째 리더 추가를 구조적으로 차단한다 — `/hm:health` 가 실제 실행 모드와 다른 걸 보고하는 게 그 실패 모드다.
- **단일 writer**: `cli._apply_worktree_enabled` 가 유일하게 `answers.worktree["enabled"]` 를 쓴다. preset flip / `--worktree`·`--no-worktree` / 인터뷰 답변 / `/hm:configure` / 마이그레이션 — 다섯 producer 가 전부 여기로 수렴한다. **true→false 전환은 `disable_preflight` 가 살아있는 task worktree·pending stash·loop marker 를 발견하면 거부**한다 (ADR-003). ADR-005 가 OFF 렌더에서 finalize/stash 복구 지침을 지우므로, 가드 없는 disable 은 복구 경로가 없는 고아 상태를 만든다.
- **마이그레이션** (ADR-006): 명시 `feature_branch_workflow` bool 은 **정확히 보존** (scripted `--update` 가 레거시 Production 을 조용히 끄는 걸 막는다); `scope`-only 는 표현 불가라 대화형이면 묻고 아니면 `false`+큰 소리 공지; `scope` 있는데 `execute` 없으면 (`scope: []` = 사용자가 disable 하려던 손편집) `false`.
- **OFF 의 의미** (ADR-005): 어떤 스테이지도 worktree 를 만들지 않는다. `execute.md` 의 Step 0·Step 5, `worktree-isolator` 스킬이 미렌더. **알려진 이탈**: `loop.md`/`loop-p5-batch.md` 는 OFF 에서 prose 가 남는다 (런타임은 이미 no-op — `create` 가 빈 줄을 출력하고 템플릿이 그걸 "cwd 에서 진행"으로 명시). `<WT>` 를 반복 본문 전체에서 걷어내는 건 autoloop 회귀 위험이 큰 별개 작업.
- **OFF 의 비용** (ADR-004): PLAN/RESEARCH/SPEC/REVIEW 가 wrapup 이 커밋할 때까지 현재 브랜치에 uncommitted 로 쌓인다. 자동 커밋은 의도적으로 안 한다 — 공유 base 커밋은 count:3 오염 클래스다.

### Per-task feature-branch model (flag ON, ADR-001~010 LOCKED)

세션마다 stash 를 쌓는 대신 **task 당 영속 브랜치 + 워크트리**를 쓴다 — 동시 세션이 서로의 커밋을 오염시킬 경로가 구조적으로 없음.

- **Lifecycle CLI** (`python -m harness_maker.worktree …`): `task-create <slug>` → 영속 `.worktrees/<slug>/` 를 브랜치 `hm/<slug>` (base HEAD 기준) 에 멱등 생성; `task-preflight <slug>` → registry claim + warm-branch drift 경고 + 죽은 row reclaim; `task-refresh <slug>` → drift 난 task 브랜치를 base HEAD 로 rebase (commit 손실 0, conflict→abort); `task-land <slug>` → `hm/<slug>` 를 main 으로 squash-land (full merge fence) 후 registry row drop + 브랜치+워크트리 삭제. 모든 `/hm:` stage 가 flag-on 시 preflight 를 거쳐 `<WT>` 안에서 실행 (Phase 5 partial).
- **Session registry** `.claude/.hm-sessions.json` — flock+O_EXCL 직렬화, **전용 락** `index.lock-hm-registry` (30s, 360s finalize fence 와 분리 — registry mutate 가 fence 와 경쟁 안 함). `session_uuid` primary identity, pid 는 liveness-hint. **live mismatched-UUID row 는 절대 삭제 안 함.** registry 는 operational churn → gitignore + dirt/preserve 결정에서 제외.
- **wrapup auto squash-land** (ADR-003, wrapup.md.j2 Step 7.7 — flag-on task worktree only): `/hm:wrapup` 이 `hm/<slug>` 워크트리 안에서 돌면 base 에서 `task-land <slug>` 를 호출 → task 당 main 에 **정확히 1 squash 커밋** + 브랜치/워크트리/registry row/marker 정리 (idempotent, dirty-base self-abort). `hm/*` 브랜치가 아니면 skip — `/hm:loop` 의 `execute-<uuid>` 워크트리는 loop-close `finalize` 의 legacy squash 가 land 를 소유 (double-land 없음). 렌더 검증: `test_render_worktree_preflight.test_wrapup_lands_task_branch_when_flag_on`.
- **Make-time migration** (ADR-008, `enablement_preflight`): `/harness-maker:make` 가 기존 harness 의 플래그를 **clean live-state probe 통과 시에만** flip — primary **와 모든 sibling** base 에 pending `.hm-finalize-stash-*` / live `.hm-loop-*` / in-flight `.worktrees/<owned>-*` / uncommitted user dirt 가 없어야 함 (sibling 도 git-dirt probe full parity — Phase 7 AC4). 하나라도 있으면 old-model 유지 + loud warn. **config + re-render only, git mutation 0.**
- **Drain/prune**: `worktree drain` + create-time `prune_stale` 가 landed 브랜치를 `refs/hm-landed/v1/*` marker(tip SHA) 로 reap; `prune-branches [--force]` 가 legacy `execute-*` backlog 정리 (`--force` 전 per-branch `git log -p` 힌트, reflog `wip` 커밋은 gc 윈도우까지 생존).

### Old-model 5-layer defense (flag OFF — 여전히 활성)

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
- Recovery procedure when stash conflict happens: `git reflog --all | grep "wip(execute)"` → cherry-pick chronological → resolve sandbox conflicts with `--ours`. Documented in `src/harness_maker/templates/stages/wrapup.md.j2` Step 7.5 with `<!-- @hm:drop-policy:user-confirmed -->` marker block. (Corrected 2026-07-29 — this said `templates/commands/hm/wrapup.md.j2`, which does not exist. That directory does, so following the old path would have created a new inert file rather than erroring.)

**Recovery from accidental drop** (precedent: 2026-05-23 morning's 4 dropped stashes recovered via `git reflog --all` cherry-pick — see session log 21:30 UTC). The finalize logic creates `wip(execute): capture uncommitted work` commits on the per-worktree branch BEFORE attempting cleanup; even if the stash is dropped, the WIP commit on the branch ref survives until gc.

**Keep-base-clean (PLAN-worktree-base-artifact-pollution)** — the 5 layers above stop *contamination*; this work stops the layers from *firing on the harness's own churn* (the real cause of constant stash warnings + blocked parallel `create`). One shared source of truth, `worktree._HARNESS_CHURN_PREFIXES`, drives three things:
- **gitignore** (`_ensure_harness_gitignore`, ADR-002) — appended at make time (`cli.py`) AND every `worktree create` (idempotent, subsumption-safe). Covers `.claude/observability/`, `.claude/.hm-iter-receipts/`, `.claude/loop-specs/`, `.claude/.hm-session-uuid`, `.claude/.hm-render-manifest.jsonl`, `.claude/memory/{semantic,episodic,profile}/`, `work-docs/loop-context/`, `work-docs/p5-batch-state.yaml`. Deliverables (PLAN/REVIEW/RESEARCH/SPEC, human memory tiers) are deliberately NOT ignored — wrapup commits them.
- **both dirt-filters** (ADR-003) — `_is_harness_artifact` (finalize) recognizes the churn set as a UNION with the legacy 3 prefixes; `_is_create_guard_harness_artifact` (create) inherits it via delegation, so committed-then-modified `work-docs/` churn no longer blocks `create`. Still a strict subset — genuine user `.claude/agents`/`skills`/`harness.yaml` edits remain "dirt" the finalize stash preserves (narrow-filter invariant).
- **create-guard deliverable exemption** (PLAN-worktree-deliverable-blocks-create ADR-001) — `/hm:plan` writes `work-docs/{PLAN,RESEARCH,SPEC,REVIEW}-*.md` (and `specs/SPEC-*.md`) that `/hm:execute` depends on, and deliverables are deliberately NOT in the churn set (wrapup commits them), so they were ALWAYS uncommitted at `worktree create` time → every plan→execute self-blocked. `_is_create_guard_harness_artifact` now forgives these via the anchored full-match `_is_deliverable_path` **per-line** (coexisting code WIP still blocks; the abort lists only the code WIP). The finalize filter `_is_harness_artifact` is UNCHANGED — deliverables stay user-dirt there and are stash-PRESERVED. The guard helpers use `git status --porcelain -uall` so a fresh project's first PLAN (fully-untracked `work-docs/`, which git collapses to one line) is seen as the individual file. **Accepted limitation**: a non-default `work_docs.dir` is not covered (pure porcelain predicate, no harness.yaml access — same as the churn-filter).
- **wrapup deliverable commit** (ADR-004) — `git add` now also stages RESEARCH + SPEC, so they stop lingering as untracked dirt.
- **accepted limitation**: a user who already *committed* `.claude/` churn keeps a cosmetic `M .claude/observability/...` in `git status` (gitignore can't untrack; we never auto-`git rm --cached` — CLAUDE.md git policy). It neither blocks nor stashes. Opt-in manual cleanup: `git rm -r --cached .claude/observability .claude/.hm-iter-receipts` then commit.

### Loop-marker session-scoping (PLAN-loop-marker-session-scoping)

`/hm:loop` is parallel-safe across concurrent Claude sessions — N loops + idle sessions coexist with zero interference on the normal path. The mechanism (shared helper `loop_marker.py`):
- The Claude `session_id` is recorded in the per-session marker **content** header (`claude_session_id:`); the **filename** stays worktree-keyed so `_owned_session_uuids` (filename-suffix) and the 5-layer defense are untouched.
- A SessionStart hook `sessionid_envfile` writes a sanitized `HM_SESSION_ID` to `$CLAUDE_ENV_FILE` (the only way slash-command Bash can read its own session_id). The Stop-hook (`loop_gate`) and the `worktree loop-mode-active` CLI block/detect **only on a content-match against the caller's own `session_id`**.
- **ONLY `loop.md.j2` passes `--claude-session-id`** to `worktree create`. A standalone `/hm:execute` worktree has an empty header → never trips the Stop-hook. Empty-vs-set header is the sole loop-vs-worktree signal (both write a `.hm-loop-*` marker).
- **All four** marker-content readers (`_read_active_worktrees` ×2, `_marker_referenced_paths`, `_session_worktrees`) drop the header via the shared `parse_marker_paths` (`startswith("/")` rule — never existence). Adding any field to this format = update every reader (regression: `_session_worktrees` once ingested the header as a phantom path).
- **`HM_SESSION_ID` is a SHELL variable, never exported** (PLAN-sessionid-env-propagation ADR-001, verified by live probe): `echo "$HM_SESSION_ID"` works in slash-command Bash, `os.environ.get("HM_SESSION_ID")` is `None` in **every** subprocess on **every** platform. That is not a WSL2 quirk — it is how `$CLAUDE_ENV_FILE` sourcing works. So the two consumer classes diverge: `"$HM_SESSION_ID"` interpolated into a command **works**; any Python that reads the env **cannot**. Python entry points therefore take the id as an explicit argument (`readiness`/`ai_readiness`/`cli health --session-id`, `autopilot`/`autopilot_caps --session-id`), with the env read kept only as a fallback for a host that does export it. **Adding a new consumer means wiring the argument** — the env read will silently never fire.
- **Degraded fallback** (`$HM_SESSION_ID` empty **in the shell** — a genuine SessionStart-hook failure / Cursor / Codex / no-isolation; NOT the unexported-to-Python case above): the session-blind legacy global `.hm-loop-active` is honored **only when the caller has no id of its own** (`not sid`) — a valid-id session is never blocked/mis-detected by a peer's global. Two both-id-less loops still share the global (structurally unavoidable — no per-session key). The loud `[loop] degraded` warning + the `/hm:health` `sessionid_envfile_registered` smoke surface this.
- `/hm:health` (`readiness._dim_guardrails`) fails the `sessionid_envfile_registered` signal when a rendered `hooks.json` lost the SessionStart hook (stale render → silent degradation).
- **Degraded symptom is per-IDE, not "peers block each other"** (PLAN-fleet-10-20-parallel-safety Phase-0 spike, `tests/fixtures/stop_payload_wsl2.json`): in **Claude Code** with `HM_SESSION_ID` empty **in the shell** (a genuine SessionStart-hook failure — not the unexported-to-Python fact above) the Stop-hook still has the real `session_id` from stdin, so it cannot content-match the empty marker and **the loop self-stops after iteration 1** — peers are NOT affected. The "peers block each other" case needs an id-less *stdin* (Cursor/Codex). A **Stop-hook self-heal is impossible**: the Stop `cwd` is the project root (not the worktree; subshell `cd` is invisible) and no payload field identifies the worktree, so a degraded empty-header marker cannot be attributed to the stopping session. The agreed fix is the **loud floor only** — `loop.md.j2` (loop-start, `CLAUDECODE`-branched) and `readiness.sessionid_envfile_live` both describe the accurate self-stop symptom + remedy. `loop_gate.py`/marker format are unchanged.
- **Queue-guard foreign-counting is LOAD-BEARING — do NOT make it per-session** (PLAN-fleet-10-20-parallel-safety C3, **reverted** after k-of-3 review found a P0). The "fleet false-block" where sessions A+B's live finalize-stashes block session C's `worktree create` *looks* like pure friction, but it is the operative gate compensating for a documented-vulnerable Layer 3: `post-commit-pop`'s ownership set (`_owned_session_uuids` → `HM_OWNED_SESSION_UUIDS`) reads **all** sessions' `.hm-loop-*` markers (shared FS state), so C's `post-commit-pop` will restore a PEER's deferred stash — the exact 3×-recurring `worktree-finalize-pulls-orphan-wip-into-main` contamination. Excluding foreign stashes from `_count_pending_stashes` lets C proceed into that path. Cross-model note: Codex (reading the implementation + the vulnerability comment) caught this; two Claude reviewers trusted the `_owned_session_uuids` "owned by THIS process" docstring and missed it.
- **Layer 3 is now per-session** (PLAN-layer3-per-session-ownership, the C3-unblocking follow-up). `post-commit-pop` no longer sources `HM_OWNED_SESSION_UUIDS` from the all-markers `owned-uuids`; the templates source it from a **slug-keyed crumb** (`.claude/.hm-owned-uuids-<slug>`, written by execute's finalize via `owned-crumb-add`, read at wrapup by `owned-crumb-read "$(pwd)" <slug>` — machine-derived, works on a standalone/recovered wrapup). The `:3224` guard dropped the `owned_uuids and` short-circuit so an **empty owned-set fail-safe-SKIPs** a `session_uuid`-bearing ref (never the old marker-present pop); legacy no-uuid refs keep the bounded marker accept (the writer always stamps a uuid from the dirname — proven by test). `wt-uuid <path>` parses the uuid; `owned-uuids` is loud-deprecated (diagnostic only). **Safety is producer-gated** — a render-grep test (`test_owned_uuids_render_gate`) fails if any rendered command re-sources from `owned-uuids`; an un-re-rendered user harness keeps the old behavior until `/harness-maker:make --update`. **C3 (per-session queue-guard exclusion) is now the unblocked fast-follow** — a foreign stash is no longer restorable by a peer's post-commit-pop, so excluding it from `_count_pending_stashes` is safe once that follow-up ships. (Until C3 ships, `_count_pending_stashes` still counts every live-marker stash; `--allow-stash-queue` bypasses.)

### Per-session marker scoping (PLAN-multisession-marker-scoping)

두 세션이 한 프로젝트에 있는 건 **정상 케이스**다. 그런데 harness-maker 는 정반대 두 방향으로 적대적이었다 — autopilot 은 marker 가 단일 파일이라 두 번 arm 할 수 없었고, write gate 는 무시해야 할 peer 를 막으면서 정작 실제로 쓰이는 worktree 모델엔 아무 강제도 없었다. 둘 다 marker-scoping 결함이고, 해법은 **per-session marker 파일을 세션 정체성의 단일 저장소로 만들고 gate 가 그걸 보게 하는 것**이다.

- **autopilot marker 는 세션당 1파일** (ADR-001): `.claude/.hm-autopilot-<sanitized-id>`. id 없는 caller (Cursor/Codex/SessionStart hook 실패) 는 `.claude/.hm-autopilot-degraded` 공유 (ADR-002 — 레거시 `.hm-autopilot` 과 **다른 이름**이어야 한다. ADR-003 이 레거시를 unlink 하므로 같은 이름이면 살아있는 degraded 세션 marker 를 지운다). 레거시 단일 파일은 **1회 takeover 후 CAS 로 unlink** (ADR-003). GC 는 **자기 키만** (ADR-013) — glob GC 는 모든 세션을 모든 peer marker 의 unlink 권한자로 만들어 ADR-001 의 격리를 GC 문으로 되돌린다.
  - `marker_path` / `load` / `clear` / `gc_stale_marker` 의 `session_id` 는 **required keyword-only**. default 를 두면 놓친 reader 가 조용히 degraded 파일을 읽고 = "autopilot off", 진단 없음 — `[fail:design] new-marker-content-field-must-update-every-reader` (count:3) 의 정확한 모양이다. 진짜 가드는 이 문서의 목록이 아니라 **import-graph 테스트** (`tests/structural/test_autopilot_marker_api_session_key.py`): `harness_maker.autopilot` 를 import 하는 모든 모듈을 AST 로 **발견**해 marker API 호출마다 session key 를 넘기는지 본다. 이 클래스는 지금까지 세 번 "더 나은 손목록"으로 고쳤고 세 목록 다 틀렸다.
  - ADR-011: `.claude/.hm-autopilot` 은 exact-match `_HARNESS_CHURN_FILES` 에서 **prefix `_HARNESS_ARTIFACT_PREFIXES`** 로 이동 + gitignore glob `.claude/.hm-autopilot*` (하이픈 없이 — `.hm-autopilot-*` 이면 레거시 bare 이름이 gitignore 에서 빠진다). **finalize dirt-filter 는 prefix 튜플만 읽고 glob 은 절대 안 읽는다** — prefix 없이 glob 만 넣으면 살아있는 marker 가 전부 user dirt 가 되어 `worktree finalize` 가 stash 로 쓸어담고 autopilot 이 조용히 해제된다.
- **task worktree 도 per-session marker 를 갖는다** (ADR-008/010): `.claude/.hm-task-<worktree-name>`, 세션 id 는 **content header**. **`.hm-loop-` prefix 재사용 금지** — `loop_gate` 가 content-match 로 Stop 을 막으므로 모든 `/hm:plan`·`/hm:execute` 세션이 멈출 수 없게 되고, `_owned_session_uuids`·queue-guard·`_session_worktrees` 가 task worktree 를 loop worktree 로 삼킨다. 파일명을 **세션이 아니라 worktree** 로 키잉하는 이유: 한 세션이 slug 두 개(plan/execute)를 동시에 들면 세션-키잉은 두 worktree 를 한 파일로 접어 `task-land`/`cleanup_all` 이 공유(때론 peer 소유) 파일을 line-edit 해야 한다. worktree 키잉이면 모든 전이가 whole-file create/unlink.
  - id 없으면 **marker 를 아예 안 쓴다** (공유 fallback 아님) — 귀속 불가 task marker 는 false peer-block 만 만든다.
  - registry 는 enforcement 경로에서 **빠졌다**: `pid=os.getpid()` 는 종료된 CLI 서브프로세스라 row 가 거의 즉시 non-live.
  - 복구는 **expiry 가 아니라 takeover** — task marker content 엔 timestamp 자체가 없다. `task-preflight` 가 claim 하면서 header 를 재작성한다. orphan 은 `prune_stale` 의 **별도 `.hm-task-*` sweep** (`_is_orphan_task_marker`; `_is_orphan_marker` 재사용 금지 — 그건 stash 개념을 물어본다).
- **worktree_gate 는 자기를 가두지 않고 peer 를 보호한다** (ADR-004): target 이 **다른 살아있는 세션의 worktree 안**일 때만 block. base repo·`/tmp`·repo 밖 전부 허용. marker 3분류 — mine / peer(비어있지 않은 다른 id) / **unattributable(빈 header → 완전 무시)**. 세 번째 버킷이 load-bearing: `loop.md.j2` 만 `--claude-session-id` 를 넘기므로 standalone `/hm:execute` worktree marker 는 header 가 비어 있고, 2분류면 그 세션들이 **자기 worktree 에서** 차단된다. **own membership wins** — 같은 경로가 내 것과 peer 것 양쪽에 있으면 block 하지 않는다 (재시작 직후의 일상적 상황).
  - **fail-open 은 절대적** (ADR-006): payload 에 `session_id` 없으면 marker 를 읽기 **전에** 허용. 여기 강제는 원래 prompt-level 이었으므로 이건 없던 바닥이 생긴 것이지 벽이 사라진 게 아니다.
  - `session_id` 는 **PreToolUse payload** 에서 온다 (ADR-005, live probe 로 확인 — `tests/fixtures/pretooluse_payload_write.json`). `HM_SESSION_ID` 는 export 되지 않아 hook 서브프로세스의 `os.environ` 엔 없다. payload 에 `workspace` 키는 **없다**.
  - **base root 를 먼저 해석**한다. `/hm:` stage 의 `cwd` 는 worktree 이고 거기서 rooting 하면 `.claude/` marker 를 하나도 못 찾아 **조용히 아무것도 강제하지 않는다**. gate 는 `_strip_worktree` 로 로컬 구현한다 (모든 Write/Edit 마다 도는 hook 에 pydantic + 5k줄 `worktree` import 를 얹지 않으려고) — drift 방지는 `tests/structural/test_gate_base_root_parity.py`.
  - **수용된 비용**: drifting agent 는 더 이상 자기 worktree 에 갇히지 않는다. gate 의 원래 목적(= `<WT>` 치환의 기술적 강제층)은 부분적으로 포기됐다. self-confinement 는 나중에 opt-in 으로 복구 가능.

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
- 정상 종료: cleanup 은 **설정이 아니라 finalize 의 status 인자**가 결정한다. `cleanup(wt, on_success=True)` 는 force 제거(작업 복사본 무조건 삭제), `on_success=False` 는 non-force 제거(dirty 면 git 이 거부 — 의도된 안전망). **`harness.yaml.worktree.cleanup` 이라는 키는 존재하지 않는다** — 어떤 preset 템플릿도 렌더한 적 없고 어떤 코드도 읽지 않는다. 이 문서가 `(default on_success)` 라고 적어 설정 가능한 것처럼 읽히게 했던 것이 오류다 (PLAN-worktree-side-defaults 에서 확인).
- **autoloop iter / phase blocker 발생 시 강제 cleanup**: `worktree.cleanup_all(force=True)` 호출 → halt 전 모든 `.worktrees/*` 제거 (디스크 누적 방지). 단, `--debug-worktree` 플래그 시 보존.
- stale-artifact janitor: `prune_stale(base)` 가 **`worktree create` 시점에만** 실행된다 (`_cli_create`, `--debug-worktree` 시 skip). orphan `.hm-loop-*` 마커, dangling `.worktrees/*`, 그리고 finalize-stash ref 를 정리한다. ref drain 정책: stash object 가 이미 사라진(gc/drop) ref 는 즉시 제거(복원할 내용 없음), 살아있지만 내용이 HEAD 에 없는 ref 는 preserve+warn (PLAN-worktree-base-artifact-pollution ADR-005). **24h/주기 기반 hook 은 없다** — 예전 문서의 "weekly `/hm:health` cleanup" 주장은 코드에 존재한 적 없는 오류였다.
- orphan-branch sweep + **landed-marker** (PLAN-worktree-deliverable-blocks-create ADR-003/004): finalize 성공 시 `refs/hm-landed/v1/<branch>` 에 worktree 브랜치 tip SHA 를 기록한다 (`_write_landed_marker`, cleanup 직전·clean/dirty base 양쪽). `prune_stale` 의 브랜치 sweep 은 marker SHA == 현재 tip 이면 (worktree dir 부재 시) **content 재비교 없이** 삭제 — 후속 HEAD 편집에도 안전하고, 이름 충돌로 재생성된 동명 브랜치는 tip 이 달라 marker 불일치 → preserve-biased content-gate 로 빠진다. marker 없는 legacy 브랜치는 기존 `_branch_content_in_head` fallback. **모든 삭제 경로(marker-sweep, content-gate, `--force`)가 같은 op 에서 marker ref 도 삭제**하고, branch 없는 orphan `refs/hm-landed/v1/*` 는 prune 시 reap → ref 누적 0. create 시 preserved-branch 경고 벽은 **1줄 요약**으로 collapse (`_print_prune_warnings`).
- `prune-branches [--force]` CLI (ADR-004): 누적된 legacy `execute-*` 브랜치 backlog 를 정리. flag 없으면 `prune_stale` 와 동일 gate (marker/content 검증된 것만 sweep, 나머지는 `git log -p <branch>` 힌트와 함께 preserve). `--force` 는 markerless/diverged 브랜치까지 삭제하되 삭제 전 per-branch recovery 힌트를 출력 (reflog `wip(execute)` 커밋은 gc 윈도우까지 생존). `--force` 는 명시 파싱 (substring 검사 아님).
- **Cursor 와 공유 시 주의**: prefix 매치로 자기 것만 cleanup (`execute-*`, `plan-*`, `phase-*`, `autoloop-*`). Cursor 가 만든 worktree (다른 prefix) 는 건드리지 않음.

### 렌더 컨텍스트 플래그는 **출력 경로에서 파생**시킬 것 (`is_codex`, 2026-08-16)

`synthesize` 의 컨텍스트 빌더가 모든 파일에 `is_codex: False` 를 하드코딩하고 있었다. 근거는
"Codex 본문은 `_codex_stage_skills()` 가 미리 렌더한다" 였고, 절반만 맞았다 — 미리 렌더되는 건
**stage body** 뿐이고 그걸 감싸는 **wrapper** (`codex/stage_skill.md.j2` + 그것이 include 하는
partial) 는 빌더가 렌더한다. 그래서 **디스크의 Codex 파일 전부가 `is_codex=False` 로 생성**됐고,
wrapper-level partial 의 `{% if is_codex %}` 는 템플릿 소스만 보면 Codex 를 인식하는 것처럼 읽히면서
실제로는 항상 Claude 가지를 탔다. 실측 결과: autopilot picker 의 `not is_codex` 게이트는 한 번도
발화한 적이 없고, `stage_end_summary` 의 auto-advance 억제 게이트도 마찬가지여서 Codex stage skill 이
실행할 수 없는 `Skill` 자동 전환 블록을 싣고 나갔다.

교훈은 두 가지다. (a) **런타임 플래그는 손목록이 아니라 출력 경로에서 파생**시킨다
(`_is_codex_output` — `.codex/` · `.agents/` · `AGENTS.md`). 새 Codex 출력이 플래그를 조용히
놓치는 경로가 없어진다. (b) **이 결함은 render-grep 으로 절대 안 잡힌다** — 템플릿도 산출물도 모두
"정상"으로 읽히고, 틀린 건 컨텍스트뿐이다. 게이트는 blueprint 의 `FileEntry.context` 를 직접 보는
`tests/structural/test_is_codex_matches_output_path.py` 다.

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

### 2. 외부 소비자 정합성 확인 — 전처리 + parser
우리가 렌더하는 파일은 우리가 아니라 **다른 도구가 읽음**. 그 도구의
parser 가 받아들이는 형식을 따라야 하고, **parser 앞단에서 내용을 바꾸는
전처리기가 있는지도** 확인해야 한다.

> **두 층은 탐지 방법이 다르다.** parser 문제는 파일을 읽으면 잡힌다
> (`settings.json` 에 frontmatter 가 박혀 있다 — 보면 안다). **전처리 문제는
> 파일을 읽어서는 절대 안 잡힌다** — 디스크의 내용은 옳고, 실행되는 내용만
> 다르다. render-grep 테스트는 전부 통과한다. **실제 호출의 결과값을
> 대조해야만** 보인다.
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

- **슬래시 명령 본문** (렌더된 `.claude/commands/hm/*.md` **와** 플러그인 자신의
  `commands/*.md` 양쪽) → Claude Code 가 모델에게 넘기기 **전에** 인자를 치환한다.
  `$0`–`$9` 는 인자로 대체되므로 셸/awk 의 위치 매개변수를 쓸 수 없다
  (`$ARGUMENTS` 가 지원되는 방식). **2026-07-26 실측**: `/hm:make --update` 에서
  디스크의 `awk '{print $NF, $0}'` 가 호출 시 `awk '{print $NF, --update}'` 가 되어
  `HM=-8` → `uv run --with "-8"` 실패 → **하드코딩된 구버전 pin 으로 fallback**.
  그 줄의 존재 이유가 정확히 그 stale-pin 함정을 피하는 것이었다. 같은 함정이
  `/hm:review`·`/hm:plan` 의 `awk '{s+=$1}'` 에도 있었고, 그 값은
  `high_diff classify --added-lines` 로 가서 **second-opinion 발동 여부**를
  결정한다. 그리고 플러그인 자신의 `commands/make.md` — **신규 설치의 진입점** —
  에도 같은 줄이 있었는데, 렌더된 명령만 스캔하던 첫 게이트가 놓쳤다.
  게이트: `tests/structural/test_no_positional_params_in_commands.py`
  (렌더 산출물 + 플러그인 자체 표면 양쪽).

새 파일 종류 추가 시 두 가지를 확인한다:
1. **누가 읽는지** + 그 reader 가 frontmatter 를 허용하는지. 안 되면
   `_is_pure_text` / `_is_hooks_json` 같은 디스패치 분기 추가.
2. **그 소비자가 읽기 전에 내용을 바꾸는지.** 바꾼다면 디스크의 파일을 검사하는
   테스트로는 절대 잡을 수 없다 — 실제 호출을 한 번 돌려 결과값을 대조하는
   테스트가 있어야 한다. 게이트를 만들 때는 **자기가 고치던 산출물에만 범위를
   맞추지 말 것** — 같은 결함이 자기 수정을 피해 살아남는다 (위 `commands/make.md`).

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
