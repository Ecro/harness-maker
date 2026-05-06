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
- `HarnessConfig(targets=[])` ValidationError (`min_length=1`)
- 옛 yaml fixture (`tests/cursor-compat/fixture/.claude/harness.yaml`) load → `default_factory` 가 `[Target.CLAUDE_CODE]` 박음. **경고 로그는 Phase 2.1 의 yaml-aware loader 책임으로 이전** — model 단은 default_factory 만으로 처리 (Pydantic `mode="before"` validator 가 default 호출에서도 fire 하는 동작 회피, 구현 중 발견)
- 단위 테스트 green (회귀 0)

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
- `answers_from_harness_yaml` 또는 yaml loader wrapper 가 옛 yaml (`targets` 키 부재) 검출 시 `[claude-code]` fallback **+ 경고 로그** (Phase 2.0 에서 이전된 책임)

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
- `src/harness_maker/render.py` — `resolve_output_path(target_dir, fe_path)` helper 신규
  (구현 중 발견된 critical bug fix: CLI 가 target_dir = `.claude/` 로 호출하는데
  cursor 자산은 그 sibling 위치라 기존 `target_dir / fe.path` 가 `.claude/.cursor/...`
  로 잘못된 경로 만듦)
- `src/harness_maker/render.py` — 4 callers 갱신 (`out = target_dir / fe.path` →
  `out = resolve_output_path(target_dir, fe.path)`)
- `src/harness_maker/reconcile.py` — `resolve_output_path` import 후 동일 helper 사용
  (`existing_path = resolve_output_path(existing_dir, fe.path)`)
- `src/harness_maker/reconcile.py` — `backup()` layout 변경: backup directory 가
  project root 의 mirror (`<bdir>/.claude/<files>` + `<bdir>/.cursor/<files>`).
  Pre-2.4 layout (flat `<bdir>/<files>`) 은 manual restore 필요 — README 명시.
- `tests/unit/test_reconcile.py` — cursor section 추가 (3 tests: first-render-BOTH /
  second-render-KEEP / backup-cursor-modifications) + backup test 갱신 (`bdir / '.claude' / 'f.txt'`).
  integration 디렉토리 미존재로 unit 으로 통합.
- `tests/unit/test_render.py` — cursor test 3개 갱신 (`target_dir = tmp_path` →
  `target_dir = tmp_path / '.claude'` 의 실제 CLI 패턴)

**Acceptance**:
- ✅ 옛 `.claude/` + 신규 `.cursor/` reconcile 시 두 디렉토리 모두 backup
  (`test_backup_includes_cursor_directory`, `test_backup_after_full_render_preserves_cursor_user_modifications`)
- ✅ `.mdc` 가 우리 `content_hash` 메타 박지 않으므로 (Cursor strict-reject 회피)
  reconcile 의 'no-frontmatter' rule 자동 KEEP. 사용자 수정 보존 ✅; 우리
  template update 는 사용자가 수동 delete + re-render 필요 — README 명시 +
  Phase 2.4+ 에 sidecar 메타 (`.hm-meta.yaml`) 도입 시 변경 가능
  (`test_reconcile_cursor_mdc_keeps_after_render`)
- ⚠️ **Reconcile KEEP rule 의 일반 trade-off**: hash-가진 자산 (`harness.yaml`,
  `CLAUDE.md`, agents/skills/commands) 도 옛 hash != 새 hash 시 KEEP rule 적용.
  template 갱신 (예: Phase 2.7 의 `targets`/`recommended_model` 키 추가) 이
  자동 propagation 안 됨 — 사용자가 수정 안 했어도 옛 yaml 그대로 보존.
  Workaround: 사용자가 `harness.yaml` 수동 delete + `/harness-maker:make`
  재실행 (또는 직접 yaml 편집). 1차 release 는 README/onboarding 가이드에
  명시. Phase 2.4+ 의 sidecar 메타 도입 또는 yaml 의 special-case
  (settings.json 같이 always-REPLACE) 로 향후 개선 가능.
- ✅ B13 자동화 테스트 PASS — Phase 1 acceptance 의 deferred 항목 closed
  (`test_reconcile_cursor_first_render_returns_both`)
- ✅ Path resolution critical bug fix (CLI 가 `.claude/` 를 target_dir 로 호출 시
  cursor 자산이 정확한 경로에 박힘)

---

### Phase 2.5 — harness-maker 자체 dual plugin manifest

**Files**:
- `.cursor-plugin/plugin.json` (신규) — `.claude-plugin/plugin.json` 거의 동일.
  description 에 dual-IDE 명시 + keywords 에 `cursor` 추가. `commands`
  path 를 explicit 로 박음 (`"./commands"`) — Cursor docs "explicit >
  implicit" 권고 (auto-discovery 결과는 동일하나 spec 변경 시 break 회피).
  현재 plugin 은 `/harness-maker:make` 명령 하나만 노출; agents/skills 는
  사용자 하네스의 렌더 결과로 들어가고 plugin 자체에는 포함 안 됨.
- `tests/unit/test_version_sync.py` (신규) — 4-way version 일치 + manifest
  metadata 일치 + Cursor explicit commands path 검증 (8 tests).

**Acceptance**:
- ✅ 두 manifest version 일치 (`test_*_versions_match`,
  `test_all_four_version_sources_agree`)
- ✅ Cursor 의 commands path explicit (`test_cursor_plugin_explicit_commands_path`,
  `test_cursor_plugin_commands_path_resolves_to_existing_directory`)
- ✅ Required metadata 일치 (name, author, license, repository, homepage) —
  `test_two_manifests_share_required_metadata`
- ✅ Cursor 키워드 포함 — `test_cursor_plugin_manifest_has_cursor_keyword`

**의식적 omit (1차 release scope 외)**:
- `scripts/bump_version.py` (선택, 4-파일 동시 bump helper) — manual bump +
  `test_version_sync` 회귀 검증으로 충분. 미래 release 시 cycle 빈도가
  높아지면 도입.

---

### Phase 2.6 — B11 / B13 자동화 검증

**Files**:
- `tests/unit/test_answers_from_harness_yaml.py` 에 `test_phase1_fixture_yaml_falls_back_with_warning` 추가
  — Phase 1 fixture 직접 사용 (B11). integration 디렉토리 미존재로 unit 통합.
- `tests/unit/test_reconcile.py` — Phase 2.4 에 추가된 cursor reconcile 섹션
  + backup 의 `.cursor/` 처리 (B13).

**Acceptance**:
- ✅ B11 PASS — Phase 1 fixture (`tests/cursor-compat/fixture/.claude/harness.yaml`)
  를 production code (`answers_from_harness_yaml`) 가 read 시 `[claude-code]`
  fallback + `falling back` 경고 로그 emit. Phase 1 fixture 가 dead asset 가
  아니라 회귀 방지 자산으로 자동화에 통합됨.
- ✅ B13 PASS — Phase 2.4 의 5 cursor reconcile/backup tests:
  `test_reconcile_cursor_first_render_returns_both`,
  `test_reconcile_cursor_mdc_keeps_after_render`,
  `test_backup_includes_cursor_directory`,
  `test_backup_after_full_render_preserves_cursor_user_modifications`,
  `test_backup_creates_dir` (Phase 2.4 layout).
- ✅ `PLAN-cursor-target-support.md` §5 Phase 1 acceptance 의 deferred 부분
  closed (parent plan 의 Phase 1 acceptance 표시 갱신 필요).

---

### Phase 2.7 — Snapshot tests + critical bug fix

**Files**:
- `src/harness_maker/templates/harness-yaml/Side.yaml.j2` +
  `Production.yaml.j2`: **critical bug fix** — `targets` 와
  `recommended_model` 키가 yaml output 에 박지 않던 누락 (Phase 2.0/2.1 의
  buf 가 Phase 2.7 진행 중 발견). 사용자가 cursor 선택해도 yaml 에 박지
  않으면 next render 시 옛 yaml 으로 인식되어 silent fallback
  `[claude-code]`. fix 후 yaml 에 `targets: [claude-code, cursor]` +
  `recommended_model: claude-opus-4-7` 명시.
- `tests/snapshot/*.expected.yaml` × 8: 모두 regenerate.py 로 갱신
  (file_count 동일, body_sha256 만 변화 — yaml template 의 새 키 추가 반영).
- `tests/unit/test_render.py`: cursor target snapshot section 추가 (3 tests):
  - `test_render_cursor_target_byte_identical_across_runs`
  - `test_render_both_targets_byte_identical_across_runs`
  - `test_render_cursor_target_writes_targets_to_harness_yaml`

**Acceptance**:
- ✅ snapshot 결정성 — `freeze_time=DEFAULT_FREEZE_TIME` 으로 두 번 render 시
  byte-identical (cursor only / both targets 모두).
- ✅ regression 0 — 기존 8 snapshot 들의 file_count 동일, body_sha256 만
  template 변경에 따라 갱신 (path / template / file_count 변화 없음).
- ✅ harness.yaml 의 `targets` / `recommended_model` 키가 실제 박힘 — re-render
  시 옛 yaml fallback 회피, 사용자 선택 보존
  (`test_render_cursor_target_writes_targets_to_harness_yaml`).
- ✅ End-to-end round-trip 보장 — `synthesize → render → answers_from_harness_yaml`
  이 `targets` 를 정확히 복원 (CLAUDE.md 체크리스트 #6, 양방향 매퍼)
  (`test_round_trip_targets_via_render_and_reverse`,
   `test_round_trip_cursor_only_targets`).

---

### Phase 2.8 — Production hook 작동 검증 (manual)

**Files**:
- ✅ `tests/cursor-compat/MANUAL_CHECKLIST.md` 끝에 "Phase 2.8 — Production
  hook 작동 검증" 섹션 추가. 4 검증 항목 (`Phase2.8.fire`, `.uv-resolves`,
  `.module-loads`, `.exit-clean`) + 각 항목별 fail-시-분기 명시 (스키마 변환
  layer / uv 의존성 명시 / dev dep 등록 / graceful exit 정책).
- ✅ `tests/cursor-compat/RESULTS.md` 끝에 Phase 2.8 결과 표 추가
  (4 rows × `Cursor 결과` / `Claude Code 결과`).

**Acceptance**:
- Production hook command (`uv run --with <path> python -m
  harness_maker.gates.X`) 가 Cursor IDE 에서 fire + module 로드 + clean exit
  되는지 manual 검증 절차 정의 (1차 release 의 dogfooding 시점에 사용자가
  실 IDE 에서 따라가서 RESULTS.md row 채움).
- Phase 1 acceptance 의 A1–A4 와 함께 dogfooding manual 검증으로 통합.

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
