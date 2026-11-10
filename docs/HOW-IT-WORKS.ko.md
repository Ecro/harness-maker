[🇺🇸 English](HOW-IT-WORKS.md)

# harness-maker 동작 원리

> **대상 독자**: harness-maker 를 쓰면서 각 stage 가 무엇을 하고, 무엇을 쓰고, 어디서 사람을
> 기다리는지 알고 싶은 개발자.
> **Version**: 0.65.4
>
> 이 문서는 현재 릴리스만 설명한다. 릴리스 간 변경은 [CHANGELOG.md](../CHANGELOG.md), 설계
> 기록은 [ARCHITECTURE.md](ARCHITECTURE.md) 에 있다.

> 현재 릴리스 계약(소스에서 자동 검증):
>
> <!-- hm-doc-contract:pipeline:start -->
> **Current pipeline:** `research` → `spec` → `execute` → `wrapup`
> <!-- hm-doc-contract:pipeline:end -->
>
> <!-- hm-doc-contract:agents:start -->
> **Current agents:** `code-reviewer`, `code-verifier`, `concurrency-reviewer`, `consensus-arbiter`, `judgment-reviewer`, `performance-reviewer`, `security-reviewer`, `spec-validator`, `stage-delegate`, `test-reviewer`, `trajectory-monitor`, `ux-reviewer`
> <!-- hm-doc-contract:agents:end -->
>
> <!-- hm-doc-contract:skills:start -->
> **Current skills:** `agent-quality-rubric`, `ai-readiness-rubric`, `context-linter`, `intent-layer`, `project-knowledge`, `second-opinion-gate`, `trajectory-monitor`, `worktree-isolator`, `world-model`
> <!-- hm-doc-contract:skills:end -->
>
> <!-- hm-doc-contract:mechanisms:start -->
> **Current mechanisms:** M1, M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12, M13, M14, M15, M16, M17, M18, M19
> <!-- hm-doc-contract:mechanisms:end -->
>
> <!-- hm-doc-contract:version-files:start -->
> **Release version files:** `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`
> <!-- hm-doc-contract:version-files:end -->
>
> 위 목록은 소스 트리의 모든 템플릿이다. 모든 프로젝트에 다 렌더되지는 않는다. 언제 렌더되는지는
> [에이전트](#에이전트)와 [스킬](#스킬) 절에 있다.

---

## 목차

1. [harness-maker 란](#1-harness-maker-란)
2. [렌더 파이프라인](#렌더-파이프라인)
3. [네 개의 stage](#3-네-개의-stage)
4. [`hm check`](#4-hm-check)
5. [Maker — 정문](#5-maker--정문)
6. [태스크별 worktree](#6-태스크별-worktree)
7. [에이전트](#에이전트)
8. [스킬](#스킬)
9. [Hook](#9-hook)
10. [메모리, intent, Second Brain](#10-메모리-intent-second-brain)
11. [교차 모델 second opinion](#11-교차-모델-second-opinion)
12. [그 밖의 명령](#12-그-밖의-명령)
13. [주요 `harness.yaml` 설정](#13-주요-harnessyaml-설정)
14. [0.64.0 에서 은퇴한 것](#14-0640-에서-은퇴한-것)

---

## 1. harness-maker 란

harness-maker 는 Claude Code 와 Codex 플러그인이다. `/harness-maker:make` 한 번으로 프로젝트에
대해 한 번 인터뷰하고, 그 프로젝트에 **하네스**를 렌더한다: stage 명령, 몇 개의 에이전트와
스킬, hook, 그리고 단일 진실 원천인 설정 파일 `.claude/harness.yaml`. `make` 를 다시 돌리면 그
파일에서 다시 렌더하고 사용자 편집은 보존한다.

하네스는 계속 유지보수되는 프로덕션 코드를 위한 것이다. 유능한 모델이 아직 스스로 하지 않는
것만 남기고, 이미 잘하는 것은 뺀다:

- **컨텍스트 창을 넘어 살아남는 상태**: SPEC, PLAN, REVIEW, 메모리, intent 가 파일이라 다음
  세션이 요약이 아니라 그 파일에서 시작한다.
- **사람의 lock-in**: SPEC 은 사람이 승인하고, 되돌리기 어려운 결정(스키마, 공개 API, 데이터
  마이그레이션, 보안 경계, 새 외부 의존성)은 모두 사람을 기다린다.
- **결정적 게이트**: 테스트를 먼저 쓰고 실제 이유로 실패해야 하며(RED), 무엇이든 착지하기 전에
  `hm check` 가 프로젝트의 lint·타입·테스트 명령과 AC 테스트를 돌린다.
- **이해 델타**: 커밋마다 어떤 가정이 바뀌었는지로 끝나서, 사람의 시스템 이해가 코드와 함께
  갱신된다.

명령은 Claude Code 에서 `/hm:<name>`, Codex 에서 `$hm-<name>` 스킬이다. 텔레메트리는 전부
로컬에 남는다.

## 렌더 파이프라인

`/harness-maker:make` (및 렌더된 `/hm:make`)는 `harness.yaml`을 디스크 위 하네스로 만든 뒤,
git 결정까지 끝까지 가이드한다. 이 흐름은 의도적으로 git worktree 안에서 돌지 **않는다** —
`make`는 실제 `.claude/`에 쓰고, 안전성은 backup + reconcile + 읽기 전용 미리보기에서 오며,
이는 비-git 프로젝트도 작동하게 한다.

**1. 해석 + 미리보기 (재렌더 한정).** `.claude/`가 이미 있고 비어있지 않으면 make는 먼저
`--dry-run`을 돌려 NEW / REPLACE / KEEP / MERGE 카운트(KEEP = 내 편집이 그대로 보존되는 파일;
MERGE = `@hm:user:*` 블록이 새 템플릿에 block-merge됨)를 보여주고, 쓰기 전에 확인을 받는다.
신규 설치는 미리보기를 건너뛰고 바로 적용. 덮어쓰기 전에 기존 생성물은 `.backup-<ts>/`
(자동 gitignore)로 복사된다.

**2. 적용 + 설명.** 파일이 쓰여지고, CLI가 안정적인 `render-summary:` 라인
(`files= keep= merge= targets=`)을 내보내면 슬래시 명령이 이를 사용자 locale의 평이한 설명으로
바꾼다 — 무엇이 바뀌고, 무엇이 보존되고, 현재 버전. structural-health 스캔은 **깨끗하면
조용**하고 **실제 P0/P1이 있을 때만 loud**하다 (전체 스캔은 언제든 `/hm:health`).

**3. git 처분 — 마지막 한 걸음.** 파일이 의도대로 git에 들어가기 전까지 렌더는 "끝"이 아니다.
`harness-maker git-status`가 선택된 모든 target root(`.claude/`, 그리고 Codex 면 `.codex/`,
`.agents/`, `AGENTS.md`)에 걸쳐 렌더 manifest를 — 운영 churn은 제외하고 — 검사해 다음 중
하나를 보고한다:

| 상태 | make의 동작 |
|------|------------|
| git 저장소 아님 | 알려줌; 추적을 원하면 `git init` 제안; git 명령 실행 안 함 |
| 미결정 (tracked도 ignored도 아님) | **중립적으로** 질문 — *commit*(팀과 공유) 또는 *gitignore*(로컬 유지). 권장 옵션 없음. |
| 이미 commit됨 | 없음 — 단, 재렌더가 새 파일을 추가했으면 그것만 staging 제안 (전체 재질문 아님) |
| 이미 gitignore됨 | 없음 |

결정은 **매 실행마다 git 상태에서 추론, 저장 안 함**이라 재렌더가 다시 묻지 않는다. churn
(`observability/`, `.backup-*`)이 이미 gitignore되어 commit이 깨끗하고; `git-ignore-roots`는
target root 전체를 ignore하며 쓰기가 적용되지 않으면 **loud하게 실패**하므로 슬래시 명령이 거짓
성공을 보고할 수 없다.

**인터뷰가 묻는 것.** 사람이 소유한 것만: locale, 대상 IDE(Claude Code, Codex, 또는 둘 다;
자동 감지 안 함), preset(사이드 프로젝트는 `Side`, 출시된 제품은 `Production`), 몇 가지 프로젝트
사실. 나머지는 preset 기본값을 쓰고, 요약에 "대신 정한 것" 으로 보여준다.

**렌더되는 것.** `.claude/harness.yaml`, `.claude/commands/hm/*.md`, `.claude/agents/*.md`,
`.claude/skills/*/SKILL.md`, `.claude/settings.json` 의 `hooks` 와 `permissions` 키(deep-merge 라
사용자 hook 은 남는다), `CLAUDE.md` 의 포인터 절. Codex 를 고르면 `.codex/config.toml`,
`.codex/hooks.json`, `.codex/agents/*.toml`, `AGENTS.md`, `.agents/skills/`. 생성 파일마다
frontmatter 에 `generated_by`, `content_hash`, `source_template`, `harness_maker_version` 이 있어,
재렌더가 사용자 편집과 자기 출력을 구별한다.

## 3. 네 개의 stage

태스크 하나는 최대 네 stage 를 순서대로 지난다: `/hm:research` (선택) → `/hm:spec` →
`/hm:execute` → `/hm:wrapup`. 각 stage 는 자기완결적이고, 이전 stage 의 파일을 읽고, 사람이
필요한 지점에서 멈춘다. 다음 stage 는 직접 치거나, Maker 가 한 세션에서 이어 간다
([§5](#5-maker--정문)). 요청하지 않으면 push 하지 않는다.

| stage | 쓰는 것 | 사람을 기다리는 때 |
|---|---|---|
| `/hm:research <topic>` | `work-docs/RESEARCH-<slug>.md` | `--deep` 이면 먼저 범위 질문 3–5개 |
| `/hm:spec <slug>` | `specs/SPEC-<slug>.md`, `specs/SPEC-<slug>.machine.yaml` | 인터뷰, SPEC 승인 |
| `/hm:execute <slug>` | `work-docs/PLAN-<slug>.md`, 테스트, 코드, `work-docs/REVIEW-<slug>-<date>.md` | 미승인 SPEC, 새 비가역 결정, unresolved 로 남은 finding |
| `/hm:wrapup <slug>` | 메모리 항목, 커밋 하나 | 보류된 비가역 결정, exempt SPEC 아래의 intent 쓰기 |

### 3.1 `/hm:research` — 선택

SPEC 에 필요한 것을 모은다: 코드베이스, 프로젝트 자체 기록(메모리, 이전 SPEC·PLAN·REVIEW),
최신 라이브러리 문서, 웹. 모든 주장에 `file:line` 이나 URL 과 그 근거 스니펫이 붙는다. 접근마다
가정·근거·트레이드오프·적합성·위험을 분석하고 방향을 추천하지만, 결정은 SPEC 이 한다. 어떤
stage 도 이것을 요구하지 않는다.

### 3.2 `/hm:spec` — 무엇을, 왜, 어떻게 검증할지

유일한 인터뷰. `worktree.enabled` 면 태스크별 worktree 에서 돈다([§6](#6-태스크별-worktree)).

1. **건너뛰기 판정.** 파일 하나, 범위가 뻔하고, 되돌릴 수 있고, API·포맷 변경이 없으면 인터뷰
   없이 테스트 가능한 AC 하나짜리 최소 SPEC 을 쓰고 exempt 로 찍는다.
2. **Intent.** 프로젝트에 활성 intent 가 있으면 이 태스크가 어느 것을 위한 것인지 묻는다.
3. **인터뷰.** 사람이 소유한 것만 묻는다: 왜 지금인지, "끝" 이 어떻게 보이는지, 시나리오,
   비목표, 그리고 모든 비가역 결정. 라운드당 최대 3문항. 제약·검증·각 AC 의 oracle 은 직접 정하고
   **Refinement Decisions** 로 보여줘서 사람이 거부할 수 있게 한다.
4. **SPEC + machine.yaml.** 각 AC 는 검사 대상 코드와 독립인 oracle(golden, differential,
   property, rubric, consensus)을 갖는다. "테스트가 확인한다" 는 순환이라 거부된다.
5. **검사.** `hm spec_machine check` 가 두 파일을 검증하고 품질을 채점한다.
   `spec.strictness: block` 이면 blocked 점수에서 멈추고, `warn` 이면 경고만 한다. `spec-validator` 에이전트가 SPEC 을 한 번 비평한다(권고만; live AC 가 8개 이하면
   기본 생략, "Approve after spec-validator" 를 고르면 실행).
6. **승인.** 사람이 명시적으로 "Approve this SPEC" 을 골라야만 찍힌다(`hm spec_machine
   approve`). 침묵은 승인이 아니다. `--exempt` 는 건너뛰기 경로, 또는 `autonomy.level: auto_full`
   에서 비가역 결정이 없는 SPEC 에만 쓴다.

### 3.3 `/hm:execute` — 테스트 먼저, 그다음 코드, 그다음 리뷰 한 번

커밋하지 않는다.

1. **SPEC 게이트.** `hm spec_machine approval-status` 가 `approved` 또는 `exempt` 여야 한다.
2. **PLAN.** `work-docs/PLAN-<slug>.md` 를 쓴다: phase 마다 `scope`, `exit` 명령, `risk`,
   `rollback`, 그리고 이 태스크가 건드리면 안 되는 경로의 `### Do not change` 목록.
3. **테스트 먼저 (RED).** 코드보다 먼저 테스트 가능한 AC 마다 `test_ac_NNN_<short>` 테스트.
   `hm check --red` 가 각각 실제 이유로 실패함을 보여야 한다. 동작이 이미 있는 AC 는
   `--green-ok AC-NNN` 으로 면제할 수 있고, 리뷰어가 그 면제를 본다.
4. **구현.** phase 별로, 그 테스트를 green 으로 만드는 가장 작은 변경. 비가역 범주의 새 선택은
   SPEC 에 추가되고(승인 무효화) stage 가 사람을 기다린다.
5. **바인딩과 게이트.** `hm spec_machine mark-tested` 가 테스트를 AC 에 묶고 `hm check` 가 모든
   게이트를 돌린다. diff 에 `Do not change` 경로가 있으면 멈춘다.
6. **리뷰.** `code-reviewer` 하나가 SPEC, PLAN, diff, 테스트를 함께 읽어 약해진 테스트도 잡는다.
   finding 마다 처분: `accepted`, `rejected`(근거 필수), `duplicate`, `unresolved`. accepted 는
   고치고 다시 리뷰, 최대 `reviewers.max_review_rounds`(3) 라운드. REVIEW 문서는 루프가 끝난 뒤
   쓰므로, 그 존재가 execute 완료 표시다.

### 3.4 `/hm:wrapup` — 게이트, 메모리, 커밋 하나

1. **게이트.** `hm check --reuse --require-review`: REVIEW 기록 없는 코드 변경은 실패(exempt SPEC
   제외). `--reuse` 는 execute 이후 바뀐 게 없으면 재실행을 건너뛴다.
2. **Judgment AC.** `type: judgment` AC 는 `judgment-reviewer` 가 rubric 으로 판정한다.
3. **PLAN** 을 complete 로 표시한다.
4. **메모리.** 오래 갈 교훈은 위키와 실패 로그에(`hm memory_md`). 세 번 반복된 실패는
   `.claude/memory/pending-proposals.md` 의 제안이 된다. 승인된 SPEC 아래에서는 intent 관찰과
   지표 기록을 묻지 않고 쓴다.
5. **커밋.** 메시지에 이유, RED 요약, `Understanding:` 블록(`<가정>: <전> -> <후>`,
   `unknown: …`, `agent-decided: ADR-…`)이 들어간 커밋 하나. `hm wrapup_land` 가 태스크 파일만
   정확히 stage 하고, 보류된 비가역 결정은 착지 전에 사람에게 보여준다.
6. **Squash-land.** worktree 를 켜면 `hm worktree task-land` 가 `hm/<slug>` 를 사용자 브랜치에
   커밋 하나로 squash 하고 worktree 를 지운다.

push 하지 않는다.

## 4. `hm check`

`hm check --slug <slug>` 는 태스크의 결정적 게이트를 돌리고 게이트별 섹션이 담긴 JSON 한 줄을
출력한다:

| 섹션 | 검사 |
|---|---|
| `approval` | SPEC 이 승인·exempt 이거나, `auto_full` 이 미승인을 허용 |
| `gates` | CI 설정의 lint·타입·테스트 명령; CI 파일이 없으면 `pyproject.toml` 에서 도출한 ruff·mypy·pytest; 여기에 `reviewers.mechanical_checks` |
| `ac` | 테스트 가능한 AC 마다 바인딩된 테스트가 있고 통과 |
| `review` | `--require-review` 면 코드 변경에 REVIEW 기록이 있음 |
| `contract` | 바뀐 경로가 PLAN 의 `Do not change` 에 없음 |
| `security` | 바뀐 파일에 비밀이나 hook injection 이 없음 |
| `cve` | OSV 로 의존성 취약점 (`--offline` 은 건너뛰고 그렇다고 말함) |

종료 코드: `0` ok, `1` 게이트 실패, `2` 사용법, `3` degraded(게이트를 못 돌림; 통과가 아니다),
`4` 실행 중 트리 변경, `5` 승인 누락·무효. `--red` 는 RED 단계용으로 AC 게이트를 뒤집고,
`--mutation` 은 선택형 mutation 게이트를 더한다. AC 러너는 pytest 전용이다. pytest 가 없는
프로젝트에서는 조용히 통과하지 않고 그렇다고 말한다.

## 5. Maker — 정문

Maker 는 스킬이다(인터뷰 때 이름을 정하며 기본은 `Maker`, `/maker` 로 친다). 프로젝트 상태로
들어가는 유일한 입구로, 현재 상황 브리핑, 태스크 시작·재개, 프로젝트 사실 기록, 목표와 지표
관리를 한다. 저장소를 다시 읽는 대신 `hm world_model digest`(최대 1,500 바이트, 항상 exit 0)를
읽는다.

**범위는 요청을 따른다.** "research X" 는 research 에서, "spec X" 는 spec 에서 끝나고, "build X"
나 "fix X" 는 전체 파이프라인을 돈다.

**Advance 규칙.** 전체 파이프라인 시작·재개일 때 Maker 는 spec → execute → wrapup 을 같은
세션에서 이어 가고, 사람이 필요한 지점(인터뷰, SPEC 승인, 비가역 결정, unresolved finding),
마지막 `hm check` 가 0 이 아닐 때, 태스크에 `## Queued asks` 가 있을 때 멈춘다. push 하지
않는다. stage 를 직접 쳐도 언제나 된다.

`intent-layer` 와 `project-knowledge` 는 Maker 를 통해서만 쓰이고, 스스로 발동하지 않는다.

## 6. 태스크별 worktree

`worktree.enabled: true` 면 태스크마다 `.worktrees/<slug>/` 의 `hm/<slug>` 브랜치에서 일하고,
모든 stage 가 그것을 공유한다:

- `hm worktree task-preflight` 가 만들거나 다시 들어가고, 다른 활성 세션이 있으면 경고한다.
- `hm worktree task-refresh` 가 사용자 브랜치 위로 rebase 한다(dirty 트리는 거부, 충돌이면
  중단하고 브랜치는 그대로).
- `/hm:wrapup` 이 `hm worktree task-land` 로 정확히 squash 커밋 하나로 착지시킨다.

같은 저장소의 두 세션은 각자 worktree 를 가진다. `worktree_gate` hook 은 태스크 worktree 가
활성인 동안 base 체크아웃 편집을 막는다. 전체 규칙은
[multi-session-worktree.md](reference/multi-session-worktree.md).

## 에이전트

에이전트는 stage 가 띄우는 sub-agent 다. 실제로 강제되는 경계는 `tools:` 뿐이고, 리뷰어에게는
Bash 도 쓰기 도구도 없다.

| 에이전트 | 렌더 조건 | 쓰이는 곳 |
|---|---|---|
| `code-reviewer` | 항상 | `/hm:execute` 리뷰 |
| `spec-validator` | 항상 | `/hm:spec` 권고 비평 |
| `judgment-reviewer` | 항상 | `/hm:wrapup` judgment AC |
| `security-reviewer`, `concurrency-reviewer`, `test-reviewer`, `performance-reviewer`, `ux-reviewer` | `reviewers.fanout: true` 이고 `reviewers.installed` 에 있을 때 | `code-reviewer` 옆에서 함께 실행; finding 은 투표가 아니라 합집합 |
| `code-verifier`, `consensus-arbiter` | `second_opinion.models` 가 비어 있지 않을 때 | 교차 모델 수용 게이트 |
| `stage-delegate` | `delegation.stages` 에 `wrapup` 이 있을 때 | wrapup Step 1–5 를 대신 돌리고 receipt 를 돌려줌 |
| `trajectory-monitor` | 렌더 안 됨 (템플릿만 남음) | — |

## 스킬

| 스킬 | 렌더 조건 | 하는 일 |
|---|---|---|
| `world-model` | 항상, 정한 handle 위치에 | Maker (§5) |
| `intent-layer` | 항상 | intent 생성·관찰·측정·종료; Maker 를 통해서 |
| `project-knowledge` | 항상 | 코드에 없는 프로젝트 사실 기록; Maker 를 통해서 |
| `context-linter` | 항상 | CLAUDE.md·에이전트·스킬 파일이 preset 한도를 넘는지 |
| `agent-quality-rubric` | 항상 | 에이전트 파일 등급(Platinum–Bronze) |
| `ai-readiness-rubric` | 항상 | 저장소의 AI 작업 준비도 채점 |
| `worktree-isolator` | 항상 | stage 가 따르는 worktree 절차 |
| `second-opinion-gate` | `second_opinion.models` 가 비어 있지 않을 때 | 리뷰 루프의 라운드 상태·수용 절차 |
| `trajectory-monitor` | 렌더 안 됨 (템플릿만 남음) | — |

## 9. Hook

Claude Code 는 프로젝트 hook 을 `.claude/settings.json` 의 `hooks` 키에서만 읽고, Codex 는
`.codex/hooks.json` 을 읽는다. 둘 다 재렌더 때 병합되어 사용자 hook 은 남는다.

| 이벤트 | 명령 | 호스트 | 하는 일 |
|---|---|---|---|
| `SessionStart` | `hooks.sessionid_envfile` | 둘 다 | 세션 id 를 stage 의 셸 명령에 노출 |
| `SessionStart` | `hooks.sessionstart_drift` | Codex (Claude 는 플러그인 자체의 `hooks/hooks.json`) | 렌더된 하네스가 템플릿에서 어긋나면 경고 |
| `PreToolUse` (Bash) | `gates.permission_gate` | 둘 다 | `curl … \| sh` 같은 위험 명령 차단 |
| `PreToolUse` (Write/Edit) | `gates.worktree_gate` | Claude | 태스크 worktree 활성 중 base 체크아웃 편집 차단 |
| `PreToolUse` (Write/Edit; Codex 는 `apply_patch`) | `gates.spec_gate` | 둘 다 | `spec.strictness: block` 에서 어떤 SPEC 도 언급하지 않는 테스트 파일 쓰기 차단 |
| `PreCompact` | `hooks.flush_session`, `worktree span-end` | Claude | 컴팩션 전에 진행 상황 스냅샷 |
| `Stop` | `worktree span-end` (Codex 는 `hooks.flush_session`) | 둘 다 | 세션 span 종료 (Codex 는 진행 상황 스냅샷) |

## 10. 메모리, intent, Second Brain

- **메모리** (`.claude/memory/`): 오래 갈 프로젝트 사실의 위키와 발생 횟수가 붙은 실패 로그.
  stage 는 `hm memory_retrieve --topic …` 으로 읽고, wrapup 이 `hm memory_md` 로 쓴다.
  `.claude/memory/session/<date>.md` 의 컴팩션 체크포인트로 중단된 stage 를 재개한다.
- **Intent** (`hm intent`): 열린 질문과 지표를 가진 목표. wrapup 이 태스크 증거로 관찰
  (`confirms` / `contradicts`)과 지표 측정을 기록한다.
- **Second Brain** (선택, `second_brain.enabled`): 프로젝트들이 공유하는 Obsidian vault.
  research 와 execute 가 검색하고, wrapup 은 프로젝트를 넘어 오래 갈 것만 승급한다.

## 11. 교차 모델 second opinion

`second_opinion.models`(`codex`, `antigravity`)를 설정하면 execute 리뷰가 `hm
second_opinion_invoke` 로 다른 모델에게도 묻는다. 두 voter 가 낸 finding 은 수용되고(k-of-N,
K=2), 한 voter 만 낸 finding 은 `code-verifier` 가 판정해 수용할 수도 있다. 리뷰당 한 번 호출
후 투표가 고정된다. 모든 실패(CLI 없음, 타임아웃, 잘못된 출력)는
경고 후 진행한다. 비율은 손으로 세지 않고
`hm verifier_discrimination report --ledger .claude/observability/second-opinion.jsonl` 로 낸다.
자세한 건 [second-opinion.md](reference/second-opinion.md).

## 12. 그 밖의 명령

| 명령 | 하는 일 |
|---|---|
| `/hm:make` | `harness.yaml` 에서 재렌더 (`/harness-maker:make` 와 같음) |
| `/hm:health` | 구조 무결성과 개인화 drift 감사 |
| `/hm:metrics` | 로컬 git 과 transcript 에서 변경 실패율, 머지 후 churn, 토큰 지출 |
| `/hm:help` | 사용자 locale 의 명령 목록 |
| `/hm:uninstall` | 지울 것을 보여주고 확인받은 뒤 생성 파일 삭제 |

## 13. 주요 `harness.yaml` 설정

| 키 | 효과 |
|---|---|
| `preset` | `Side` 또는 `Production`: strictness, 한도, 리뷰 깊이의 기본값 |
| `locale` | stage 가 사람과 대화하는 언어; 문서는 영어 유지 |
| `targets` | `claude-code`, `codex` |
| `spec.strictness` | `block` 또는 `warn`: SPEC 품질 blocked 점수가 `/hm:spec` 을 멈추는지, `spec_gate` 가 어떤 SPEC 도 언급하지 않는 테스트 파일을 막는지 |
| `worktree.enabled` | 태스크별 worktree (§6) |
| `reviewers.max_review_rounds`, `reviewers.fanout`, `reviewers.installed` | 리뷰 루프와 lens 리뷰어 |
| `autonomy.level` | `ask`, `gated`, `auto_safe`, `auto_full`; `auto_full` 만이 묻지 않고 spec stage 가 SPEC 을 찍고, execute 와 `hm check` 가 미승인 SPEC 으로 진행하게 한다 |
| `second_opinion.models` | §11 |
| `delegation.stages` | `[wrapup]` 이면 wrapup Step 1–5 를 `stage-delegate` 에게 |
| `second_brain` | §10 |
| `wrapup_docs` | 변경마다 wrapup 이 갱신하는 문서 |

은퇴한 기능의 키(`loop.*`, `autonomy.autopilot_persistent`, `autonomy.pipeline`, step·time cap)는
스키마에 남고 재렌더 때 값도 유지되지만 아무것도 읽지 않는다. `loop.enabled` 와
`autonomy.autopilot_persistent` 는 `make` 마다 한 번 경고한다.

## 14. 0.64.0 에서 은퇴한 것

워크플로가 일곱 stage 에서 넷으로 줄었다. 은퇴:

- **명령**: `hm:review`(execute 의 리뷰 단계로), `hm:verify`(`hm check` 로), `hm:loop` 과
  `hm:loop-p5-batch`(호스트의 `/loop` 사용), `hm:configure`.
- **Autopilot** 자동 진행(Maker 의 Advance 규칙이 대체). `harness-maker autopilot` 과 `verify`
  CLI 명령은 옛 스크립트를 위해 여전히 돌지만 도움말에서는 숨겨졌다.
- **에이전트**: `stuck`, `security-auditor`, `executor`, `autoloop-coder`.
- **스킬**: `security-scanner`, `verify-before-completion`, `targeted-test-selection`,
  `conditional-router`, `autoloop-driver`, `refdocs-search`.
- **Cursor** 대상(0.63.0). 남은 `.cursor/` 파일은 손대지 않았을 때만 지운다.

재렌더는 자신이 실었던 은퇴 파일을 지우고, 사용자가 편집한 것은 남긴다.
