# PLAN: Cursor target Implementation (Phase 2 myplan)

> **Status**: draft (Phase 1 manual 검증 결과 반영 후 §3 fork 적용)
> **Created**: 2026-05-06
> **Slug**: cursor-target-impl
> **Parent plan**: `PLAN-cursor-target-support.md`
> **Goal**: Phase 1 의 검증 가정 (A1–A4 PASS 또는 PARTIAL) 위에서 Cursor target 을 실 코드로 구현. 1차 릴리스부터 dual plugin (Claude Code + Cursor Marketplace).

---

## 0. 배경 한 줄

Phase 1 fixture + manual checklist 작성 완료, 검증은 사용자 IDE 에서 진행 중. Phase 2 는 그 검증 결과를 가정으로 받아 production code (`models.py`, `interview.py`, `synthesize.py`, `render.py`, `reconcile.py`) + Cursor 전용 templates + dual plugin manifest 를 구현. **A1–A4 모두 PASS 가정으로 작성**; 일부 fail 시 §3 분기 적용 후 본 plan 갱신.

---

## 1. 가정 (Phase 1 검증에서 받음)

| 가정 | PASS 가정 | fail 시 분기 |
|------|-----------|--------------|
| A1 (`.claude/agents/` Cursor native) | single source 유지 | §3 fork-A1 |
| A2 (hooks.json schema) | single source 유지 | §3 fork-A2 |
| A3 (SKILL.md 표준) | single source 유지 | §3 fork-A3 |
| A4 (slash + Q&A) | PASS 또는 PARTIAL with 자연어 fallback | §3 fork-A4 |
| recommended_model 정책 | claude-opus-4-7 권장 명시, prompt model-agnostic 재작성 X | (변경 없음) |
| .worktrees/ 공유 | prefix 매치 cleanup | (변경 없음) |

---

## 2. Phases (Phase 2.x = autoloop 단위 sub-phase)

> 모든 phase 의 commit message: `autoloop(harness-maker): phase 2.X - <name>`.
> 각 phase 완료 시 verify-before-completion 6 체크 통과 후 다음으로 이동.

### Phase 2.0 — Target enum + HarnessConfig 확장

**Files**:
- `src/harness_maker/models.py` — `Target(str, Enum)` 추가 (`CLAUDE_CODE = "claude-code"`, `CURSOR = "cursor"`)
- `src/harness_maker/models.py` — `HarnessConfig.targets: list[Target]` 필드 + Pydantic validator (multi-select 강제, 빈 list 거부, `recommended_model: str | None = None` 추가)
- `src/harness_maker/models.py` — schema gap fallback: 옛 yaml load 시 `targets` 키 부재 → `[Target.CLAUDE_CODE]` + `logger.warning`
- `tests/unit/test_models.py` — Target enum, multi-select validator, fallback, invalid 값 거부

**Acceptance**:
- `HarnessConfig(targets=[Target.CLAUDE_CODE])`, `[Target.CURSOR]`, `[Target.CLAUDE_CODE, Target.CURSOR]` 모두 valid
- `HarnessConfig(targets=[])` ValidationError
- 옛 yaml fixture (`tests/cursor-compat/fixture/.claude/harness.yaml`) load → `[Target.CLAUDE_CODE]` + 경고 로그
- 단위 테스트 green

---

### Phase 2.1 — Interview targets 질문

**Files**:
- `src/harness_maker/interview.py` — `locale` 다음 (preset 전) 위치에 `targets` 질문. `AskUserQuestion` multi-select with options `[claude-code, cursor]`. 빈 list 거부 (재질문)
- `src/harness_maker/interview.py` — `answers_from_harness_yaml` 의 schema gap 처리 (`targets` 없으면 `[claude-code]`)
- `tests/unit/test_interview.py` — targets 질문 (locale 다음 위치 검증), multi-select, fallback, reverse mapping

**Acceptance**:
- 인터뷰 순서: `locale → targets → preset → dev_mode → workflow → consensus → caching`
- 빈 targets 답변 시 재질문 (또는 default 거부)
- 옛 yaml + 재 인터뷰 시 targets 답변 silent 재사용 (B12)

---

### Phase 2.2 — Render dispatch 확장

**Files**:
- `src/harness_maker/render.py` — `_is_cursor_mdc(fe)`, `_is_cursor_command(fe)`, `_is_cursor_mcp_json(fe)` predicate
- `src/harness_maker/render.py` — `_render_cursor_mdc()` (frontmatter `description / globs / alwaysApply` 만, 우리 `content_hash` 등은 sidecar `.hm-meta.yaml` 또는 본문 HTML comment 결정 — Phase 1 검증 결과 따라)
- `src/harness_maker/render.py` — `_render_cursor_mcp()` (pure JSON), `_render_cursor_command()` (plain markdown)
- `src/harness_maker/synthesize.py` — `Blueprint.entries` 가 target 정보 포함. `targets` 가 cursor 미포함이면 cursor entry skip
- `tests/unit/test_render.py` — 각 predicate / render 함수 단위

**Acceptance**:
- `targets=[claude-code]`: 기존 출력과 byte-identical (regression 0, 기존 snapshot test 그대로)
- `targets=[cursor]`: `.cursor/rules/`, `.cursor/commands/`, `.cursor/mcp.json` 추가 + `.claude/` 공유 자산 출력
- `targets=[claude-code, cursor]`: 양쪽 모두 출력
- snapshot test 결정성 (`freeze_time` + `content_hash` 마스크)

---

### Phase 2.3 — Cursor templates 작성

**Files**:
- `src/harness_maker/templates/cursor/rules/harness.mdc.j2` (신규) — CLAUDE.md 의 .mdc 변환본 (1차 단일 mdc, frontmatter: `description, alwaysApply: true, globs: []`)
- `src/harness_maker/templates/cursor/commands/hm-<name>.md.j2` (신규) — 기존 `commands/hm/<name>.md.j2` 의 위치 변형. 본문은 동일하지만 prefix 가 다를 수 있음 (Phase 1 A4 결과: `.claude/commands/` 만으로 가능하면 이 디렉토리 자체 skip 결정)
- `src/harness_maker/templates/cursor/mcp.json.j2` (신규) — `templates/settings/<preset>.json.j2` 의 mcpServers 부분 추출
- `src/harness_maker/templates/cursor/agents/` — **만들지 않음** (single source `.claude/agents/`)
- `src/harness_maker/templates/cursor/skills/` — **만들지 않음** (single source `.claude/skills/`)
- `src/harness_maker/templates/cursor/hooks.json.j2` — Phase 1 A2 PASS 시 만들지 않음, FAIL 시 신설 (camelCase + `version: 1` 변환)

**Acceptance**:
- `harness.mdc` frontmatter valid Cursor schema
- 각 cursor command 가 production claude command 와 본문 동일 (content_hash 일치 검증 단위 테스트)
- mcp.json valid pure JSON
- Production CLAUDE.md ≤ 500행 정책에 맞춰 .mdc 도 ≤ 500행 (Context Lint)

---

### Phase 2.4 — Reconcile 확장

**Files**:
- `src/harness_maker/reconcile.py` — `.cursor/` 디렉토리도 enumerate (기존 `.claude/` 만 처리)
- `src/harness_maker/reconcile.py` — `.mdc` 파일은 frontmatter 가지므로 기존 hash 패턴 적용 가능 → KEEP/REPLACE/MERGE_BLOCK 정상 작동
- `src/harness_maker/reconcile.py` — `backup()` 가 `.cursor/` 도 포함 (디렉토리 리스트 확장)
- `tests/integration/test_reconcile_cursor.py` (신규) — `.cursor/` enumerate, backup, KEEP/REPLACE 결정 (B13)

**Acceptance**:
- 옛 `.claude/` + 신규 `.cursor/` reconcile 시 두 디렉토리 모두 backup
- `.mdc` hash mismatch 시 KEEP (사용자 추가 보존)
- B13 자동화 테스트 PASS — Phase 1 acceptance 의 deferred 항목 closed

---

### Phase 2.5 — harness-maker 자체 dual plugin manifest

**Files**:
- `.cursor-plugin/plugin.json` (신규) — `.claude-plugin/plugin.json` schema 거의 동일. 컴포넌트 path: `commands: "./commands"`, `agents: "./agents"`, `skills: "./skills"`, `hooks: "./hooks/hooks.json"`, `mcpServers: "./mcp.json"` (모두 `.claude-plugin` 과 같은 디렉토리 가리킴)
- `tests/unit/test_version_sync.py` (신규) — 4 파일 version 일치 검증 (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `pyproject.toml`, `__init__.py`)
- `scripts/bump_version.py` (선택) — 4 파일 동시 bump helper

**Acceptance**:
- 두 manifest version 일치
- 컴포넌트 path 가 같은 디렉토리 가리킴 (single source)
- `test_version_sync` PASS

---

### Phase 2.6 — B11 / B13 자동화 검증

**Files**:
- `tests/integration/test_targets_fallback.py` (신규) — `tests/cursor-compat/fixture/.claude/harness.yaml` 로 render → `[claude-code]` fallback + 경고 로그 확인 (B11)
- `tests/integration/test_reconcile_cursor.py` — Phase 2.4 의 일부, B13

**Acceptance**:
- B11 PASS: 옛 yaml 로 render → 경고 로그 + targets default
- B13 PASS: `.cursor/` 도 reconcile / backup 범위 포함
- `PLAN-cursor-target-support.md` §5 Phase 1 acceptance 의 deferred 부분 closed (해당 plan 갱신 필요)

---

### Phase 2.7 — Snapshot tests

**Files**:
- `tests/snapshots/cursor_target/` (신규) — `targets=[cursor]` render 결과 snapshot
- `tests/snapshots/both_target/` (신규) — `targets=[claude-code, cursor]` render 결과 snapshot
- `tests/integration/test_render_snapshots.py` 확장 — Cursor target 케이스 추가 (`freeze_time` + `normalize_for_snapshot`)
- `tests/unit/test_render_determinism.py` — 같은 input 으로 두 번 render 시 byte-identical

**Acceptance**:
- 모든 snapshot 결정성 (`generated_at` 마스크 외 모든 필드 frozen)
- regression 0 (`targets=[claude-code]` snapshot 이 기존과 동일)

---

### Phase 2.8 — Production hook 작동 검증 (manual)

**Files**:
- `tests/cursor-compat/MANUAL_CHECKLIST.md` 의 Phase 2 검증 step 추가 — production-style hook command (`uv run --with ... python -m harness_maker.gates.spec_gate`) 가 Cursor IDE 에서 실제 작동
- `tests/cursor-compat/RESULTS.md` 의 메타 표에 "Phase 2 production hook" 행 추가

**Acceptance**:
- production hook command 가 Cursor IDE 에서 fire + 정상 종료 확인 (manual)
- 결과 RESULTS.md 에 기록

---

## 3. 검증 결과 분기 (Phase 1 fail 시)

> **이 섹션은 RESULTS.md 채워진 후 본 plan §1 / §2 를 갱신할 때 적용**.

### fork-A1 (`A1.list` / `A1.dispatch` / `A1.frontmatter` 중 하나라도 FAIL)

- Phase 2.2 의 dispatch 에 `_is_cursor_agent(fe)` predicate + `_render_cursor_agent()` 추가
- Phase 2.3 에 `templates/cursor/agents/<name>.md.j2` 신설 (production agents 의 cursor 변형)
- single source 가정 무효 → `templates/cursor/skills/` 도 동시에 검토 (frontmatter 만 다른 변형)

### fork-A2 (`A2.fire` FAIL or `A2.case` FAIL)

- Phase 2.3 의 `templates/cursor/hooks.json.j2` 신설 (camelCase + `version: 1`)
- Phase 2.2 의 dispatch 에 `_is_cursor_hooks_json(fe)` 분기 추가
- A2.case FAIL 만일 때 (key 표기만 차이): 변환 layer (`render.py` 의 hook key 매핑 dict) 만으로 처리 가능

### fork-A3 (`A3.auto-discover` / `A3.user-invocable` / `A3.frontmatter` 중 FAIL)

- Phase 2.2 의 dispatch 에 `_is_cursor_skill(fe)` 분기
- Phase 2.3 에 `templates/cursor/skills/<name>/SKILL.md.j2` 신설 (frontmatter 변환)
- `A3.user-invocable` FAIL 만일 때: `user-invocable: true` 키만 strip 한 변형으로 충분

### fork-A4 (`A4.command-discover` FAIL or `A4.agent-mode` FAIL)

- `A4.command-discover` FAIL: Phase 2.3 의 `templates/cursor/commands/` 활성 (이미 plan 에 있음, skip 안 함). prefix 매핑 결정
- `A4.agent-mode` FAIL: 인터뷰 자연어 chat 다운그레이드 + Cursor 사용자 onboarding 문서에 Plan Mode 강제 진입 가이드 추가

---

## 4. 위험 / 모니터링

- **D1**: Phase 1 가정 위에서 Phase 2 진행 중 검증 결과 fail 시 phase 추가 → 일정 ↑. **mitigate**: 본 plan §3 분기 명시 → 각 fork 의 작업이 1–2 phase 추가에 그치도록 설계.
- **D2**: 4 파일 version sync drift. **mitigate**: Phase 2.5 의 `test_version_sync` + `scripts/bump_version.py`.
- **D3**: snapshot 비결정성. **mitigate**: `freeze_time` + `normalize_for_snapshot` + `content_hash` 마스크.
- **D4**: `.mdc` frontmatter 의 우리 `content_hash` 키를 Cursor 가 strict-reject 시 reconcile 패턴 깨짐. **mitigate**: Phase 1 A1.frontmatter 결과 → strict-reject 시 sidecar `.hm-meta.yaml` 또는 HTML comment fallback.
- **D5**: production CLAUDE.md ≤ 500행 정책을 .mdc 변환 시 위반. **mitigate**: 1차 단일 mdc, 초과 시 분할 (PLAN parent §1.5 의 phased 분할).

---

## 5. 다음 액션

### Phase 1 검증 종료 후

1. RESULTS.md 결과 → §3 fork 적용 여부 결정
2. 본 plan §1 가정 표 갱신 (실제 PASS/FAIL 반영)
3. fork 적용 시 §2 의 phase 항목 추가 / 변경

### Phase 2 진입 (실 구현)

순차 진행 (autoloop 단위):
- Phase 2.0 → 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → 2.8

각 phase commit: `autoloop(harness-maker): phase 2.X - <name>`.
모든 phase 완료 시 → Phase 3 (`/execute` 또는 `/wrapup`) 진입.

---

## 6. Acceptance (myplan 완료 시점)

- ✅ §1 가정 표 의 PASS/FAIL 갱신 완료 (Phase 1 RESULTS.md 반영)
- ✅ §2 의 phase 8개 모두 acceptance 충족
- ✅ B11 / B13 자동화 검증 통과 (Phase 1 의 deferred 항목 closed)
- ✅ 4 파일 version sync 검증 자동화
- ✅ Cursor target snapshot test 결정성
- ✅ production hook command Cursor IDE 작동 manual 검증 완료
- ✅ Phase 3 (execute) 진입 준비

---

## 7. 참조

- Parent plan: `work-docs/plans/PLAN-cursor-target-support.md`
- Phase 1 fixture / 결과: `tests/cursor-compat/`
- 메모리 결정:
  - `project_targets_axis.md` — targets 축
  - `project_dual_plugin_manifest.md` — dual plugin + 4파일 sync
  - `project_cursor_model_policy.md` — Anthropic 모델 권장
  - `project_worktree_share_policy.md` — `.worktrees/` 공유
- production code 의존:
  - `src/harness_maker/models.py` (HarnessConfig, AtomicStage)
  - `src/harness_maker/interview.py` (`answers_from_harness_yaml`)
  - `src/harness_maker/synthesize.py` (Blueprint, FileEntry)
  - `src/harness_maker/render.py` (dispatch predicates)
  - `src/harness_maker/reconcile.py` (hash-driven decision matrix)
  - `src/harness_maker/templates/` (cursor/ 신설 위치)
- Cursor 공식 spec:
  - https://github.com/cursor/plugins
  - https://cursor.com/docs/subagents
  - https://cursor.com/docs/hooks
  - https://cursor.com/docs/agent/plan-mode
