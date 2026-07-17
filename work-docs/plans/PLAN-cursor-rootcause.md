---
title: PLAN — Cursor IDE 호환 root-cause 진단 및 수리
created: 2026-05-06
status: in-progress
target_release: 0.5.3 (또는 진단 결과에 따라 0.6.0)
---

# Cursor IDE 호환 root-cause 진단 및 수리

## 배경

`~/kairos` 에서 사용자가 `/hm:loop` 을 Cursor IDE 에서 실행 중. 진단 결과:

- ✅ 0.5.2 설치 정상, `targets:[claude-code, cursor]`, `.cursor/rules/harness.mdc` 렌더됨
- ✅ 루프 활성 (~20분 진행, 95 파일 1741 라인 변경)
- 🔴 **PostToolUse 훅 fire 0회** — `metrics.jsonl` 미생성
- 🟡 **Worktree 비활성** — `.worktrees/` 없음, 95 파일 main 직접 편집
- 🟡 **메모리 템플릿 stale** — wiki.md/failures.md v0.4.7 frontmatter 잔존

세 이슈는 **모두 "Cursor IDE 가 우리 자산을 어떻게 소비하는가"** 라는 단일 가정 위에 서 있음. 0.5.0 릴리스 당시 `tests/cursor-compat/RESULTS.md` 가 비어있는 (TBD) 상태로 통과시킨 것이 화근. 본 PLAN 은 그 가정들을 실측으로 무너뜨리고, root cause 까지 들어가서 수리.

---

## 이슈 1 (P0) — Cursor 에서 hooks fire 안 함

### 증상
- `~/kairos/.claude/observability/metrics.jsonl` 부재 (PostToolUse 가 fire 됐다면 1줄 이상 append 됐어야 함)
- 사용자 루프 ~20분 (~수십~수백 tool call) 진행 후에도 동일

### Root cause — **3중 결함** (Cursor 공식 docs 기준 확정)

원천: <https://cursor.com/docs/hooks>, <https://cursor.com/changelog/2-4>

| # | 결함 | 증거 |
|---|------|------|
| **R1.A** | Cursor IDE 는 `.claude/hooks/hooks.json` 을 **안 읽음** — `.cursor/hooks.json` (또는 `~/.cursor/hooks.json`) 만 봄. 2.4 changelog 의 "Claude Code hooks 호환" 은 **CLI 한정**. | Cursor docs §"Hook Locations" + 2.4 changelog |
| **R1.B** | Cursor schema 는 **camelCase** (`preToolUse`, `postToolUse`, `preCompact`, `afterFileEdit` 등). 우리 PascalCase (`PreToolUse`) 는 silent ignore. | Cursor docs 모든 예시가 camelCase, options 도 camelCase (`failClosed`, `loop_limit`) |
| **R1.C** | Cursor stdin payload 는 **snake_case** (`tool_name`, `tool_input`, `tool_use_id`, `user_message`). 우리 `telemetry.py` 의 graceful read 덕에 즉시 깨지진 않지만, 향후 hook gate 가 PascalCase field 읽으면 깨짐. | Cursor docs §"Hook Input" |
| **R1.D** (잠재) | hook subprocess 의 PATH 에 `~/.local/bin/uv` 없을 가능성. Cursor docs 미명시. <https://forum.cursor.com/t/hooks-in-2-4-7-are-still-not-working-properly/149431> 같은 실사용자 사례 다수. | docs gap + forum |

즉 R1.A 만으로도 fire 0회 충분 설명 — 우리 hooks.json 을 Cursor 가 아예 안 읽음.

추가 확인된 사실:
- Cursor docs §"Hook Output" — Cursor Settings 에 **"Hooks" 디버그 탭** + Output 채널 "Hooks". 사용자가 진단 시 우선 볼 곳.
- Cursor 도 `CLAUDE_PROJECT_DIR` env var 를 호환 명목으로 노출 (+ `CURSOR_PROJECT_DIR`).
- `preCompact` 는 지원되나 `auto`/`manual` matcher 는 docs 미명시. dual-write 에서는 matcher 보존하되, fail 시 fallback 필요.

### Phase B 결정 — 단일 fix 는 불충분

확정 fix:

**R1.A fix (file location)**: `targets` 에 `cursor` 포함 시 `.cursor/hooks.json` 추가 렌더. `.claude/hooks/hooks.json` 은 Claude Code CLI 호환성 + 우리 single-source 원칙 유지로 그대로.

**R1.B fix (schema)**: 별도 Jinja 템플릿 `templates/cursor/hooks.json.j2` — camelCase 키 + PascalCase 와 **다른 dispatch 분기**. `synthesize.py` 의 `_cursor_target_files()` 에 추가.

이벤트 매핑 (Cursor → Claude Code):
- `PreToolUse` → `preToolUse`
- `PostToolUse` → `postToolUse`
- `PreCompact` → `preCompact` (matcher 미지원 시 단일 hook 으로 평탄화)
- `SessionStart` → `sessionStart`
- `Stop` → `stop`

**R1.D fix (PATH 방어)**: 양쪽 hooks.json 의 command 를 `bash -lc 'PATH="$HOME/.local/bin:$PATH" uv run ...'` 로 wrap. 또는 `command_resolved_uv_path` 를 환경 detect 후 absolute path 박음 (renderer 단계). 보수적: 둘 다.

**R1.C 대비**: `harness_maker.telemetry` + `harness_maker.gates.permission_gate` 등 stdin reader 들이 PascalCase / snake_case 모두 받아들이도록 fallback 추가. 지금은 `data.get("usage")` 형태라 OK 지만 명시적 dual-key dict 처리.

### Phase C — 구현 계획

1. **새 템플릿**: `templates/cursor/hooks.json.j2` (camelCase + PATH wrap). `templates/hooks/hooks.json.j2` 는 그대로 유지 (Claude Code).
2. **synthesize.py**: `_cursor_target_files()` 에 hooks.json 추가.
3. **render.py**: `.cursor/hooks.json` 은 pure JSON (frontmatter 금지) — 기존 `_is_hooks_json` 분기 재사용 또는 신설.
4. **reconcile.py**: `.cursor/hooks.json` 도 hooks.json 처럼 무조건 REPLACE (사용자 manual 편집 가능성 낮음 + Cursor parser 가 strict).
5. **stdin reader**: `_get_field(data, *names)` helper 도입 — 입력 키 둘 다 받게.

### 검증
- 단위: `tests/unit/test_cursor_hooks_render.py` — camelCase 키 + bash -lc wrap 확인
- e2e: tests/cursor-compat/fixture 에 `.cursor/hooks.json` 추가 후 사용자에게 manual 검증 의뢰 (RESULTS.md A2 채움)

### 영향
- 0.5.3 minor patch (cursor-only 새 파일 1개 + dual-key reader). schema 분기 자체는 작음.
- 안티-회귀: 다음 릴리스마다 `.cursor/hooks.json` 의 camelCase 보존 snapshot test 필수.

---

## 이슈 2 (P1) — Worktree isolation 비활성

### 증상
- `.worktrees/` 디렉토리 없음
- 95 파일이 main 작업 트리에 직접 변경됨 (rollback / evidence 보존 불가)

### 검증된 사전 조건
- `harness.yaml.worktree.scope: [execute, plan]` ✅ Production preset 정상
- `worktree-isolator/SKILL.md` 가 정상 렌더 ✅
- `worktree-isolator` 가 `.claude/skills/` 에 존재 ✅

### Root cause — 새 발견 (Cursor docs 기준)

Cursor 2.4+ 는 `.claude/skills/` 를 **native 로 읽음**. <https://cursor.com/docs/skills> 명시: *"Cursor also loads skills from Claude and Codex directories: `.claude/skills/`, `.codex/skills/`..."* 그리고 description match 로 자동 dispatch. 즉 skill auto-discovery 자체는 작동 가능.

하지만 trigger 매칭은 LLM judgement — **deterministic 하지 않음**. worktree-isolator 의 description 은 *"Isolate /hm:execute changes inside a disposable git worktree..."*. Cursor 에서 사용자가 `/hm:loop` 을 호출하면 LLM 이 worktree-isolator 를 호출할 확률이 100% 가 아님.

**Root cause**: 안전성-치명적 (rollback 불가) 동작을 **확률적 LLM dispatch** 에 맡긴 설계 결함. Claude Code 에서도 같은 문제이지만, Cursor 에서 더 부각됨 (다른 skill priority 가중치).

추가 발견 (Cursor docs):
- *"Cursor may need a window reload to pick up new skills"* — install 직후 첫 세션에서 미작동 가능

### Fix — **명시 호출로 전환** (확률→결정성)

`worktree-isolator` skill 은 trigger 기반 자동 dispatch 에서 → `/hm:execute.md` 와 `/hm:loop.md` 가 직접 호출하는 결정적 단계로 격하.

**R2 fix**:
1. `harness_maker.worktree` 모듈을 CLI 진입점으로 노출 (`python -m harness_maker.worktree create/finalize/cleanup`)
2. `templates/commands/hm/execute.md.j2` 의 head 에 worktree enter / 끝에 finalize 블록 inline
3. `templates/commands/hm/loop.md.j2` 의 iter 단위 안에서 동일
4. `worktree-isolator/SKILL.md` 는 "documentation skill" 로 격하 — 더 이상 trigger 안 됨, 사용자가 worktree 동작 이해를 돕는 reference 로 유지

```bash
# /hm:execute.md template snippet
!if grep -q '"execute"' .claude/harness.yaml | head -1; then  # scope 검사
  WT=$(uv run --directory "$plugin_dir" python -m harness_maker.worktree create execute "$(pwd)")
  cd "$WT" || exit 1
fi
# ... 사용자 작업 ...
!uv run --directory "$plugin_dir" python -m harness_maker.worktree finalize "$WT" "$STATUS"
```

### 영향
- 모든 Production preset 사용자 (Cursor + Claude Code 양쪽)
- ~/kairos 의 현재 isolation 없는 95 파일 변경 상태는 본 fix 로는 **소급 적용 불가** — 사용자가 일단 commit/stash 해야 함
- 0.5.3 patch (issue 1 과 동시)

---

## 이슈 3 (P2) — 메모리 템플릿 stale (legacy frontmatter)

### 증상
- `~/kairos/.claude/memory/wiki.md` 와 `failures.md` 가 v0.4.7 frontmatter 로 남음 (현재 0.5.2 임에도)
- body 가 v0.4.7 의 placeholder ("(아직 기록된 항목 없음)") + "Side preset" 명시 — 사용자의 실제 preset 인 Production 과 불일치

### Root cause (확정)

`reconcile.py:104` 의 KEEP 분기:
```python
fm, body = parse_frontmatter(existing_path)
if fm is None or "content_hash" not in fm:
    conflicts.append(ConflictItem(path=fe.path, decision=KEEP, reason="no-frontmatter"))
    continue
```

v0.4.7 시점의 메모리 템플릿은 frontmatter 에 `content_hash` 필드가 **없었음** (`generated_by/version/at/source_template/provenance` 만). 현재 reconcile 은 `content_hash` 부재 = "사용자 작성 파일" 로 단정 → KEEP. 하지만 다른 frontmatter 필드 (`generated_by: harness-maker`) 가 명백히 우리 출처임을 알려줌.

즉 **legacy 우리 파일을 사용자 파일로 오판**하는 false-positive. 영향:
- v0.4.7 → 0.5.2 업그레이드 후에도 메모리 파일 영원히 v0.4.7 상태
- 더 나쁜 점: Production preset 으로 전환했어도 "Side preset" 헤더 잔존

### Phase B — Fix design

**R3.1 (legacy backfill)**: reconcile.py 의 분기 보강:

```python
fm, body = parse_frontmatter(existing_path)
if fm is None:
    # 진짜 사용자 파일 — KEEP
    decision = KEEP, reason = "no-frontmatter"
elif "content_hash" not in fm:
    # 우리가 생성했지만 옛 버전 (content_hash 도입 전) — 안전 REPLACE
    if fm.get("generated_by") == "harness-maker":
        decision = REPLACE, reason = "legacy-no-hash-but-ours"
    else:
        decision = KEEP, reason = "no-frontmatter"
else:
    # 정상 흐름 (hash 비교)
    ...
```

**안전성 검토**:
- v0.4.7 사용자가 메모리 파일 body 를 직접 편집했을 수 있음 → REPLACE 시 user content lost
- 완화: 옛 파일은 `.backup-<ts>/` 로 자동 backup 됨 (이미 reconcile 시 backup() 호출). 사용자가 복구 가능.
- 추가 완화: REPLACE 결정 시 stderr 로 경고 ("legacy file replaced — original at .backup-...")

대안 **R3.2 (block-merge 마커 도입)**: 메모리 템플릿 자체를 `@hm:user:wiki-entries` 블록으로 감싸 사용자 추가는 보존. 이건 더 큰 변경. 후속 작업으로 분리.

### Phase C — Implementation
- `reconcile.py` 분기 추가
- 단위 테스트: `tests/unit/test_reconcile.py` 에 "legacy frontmatter without content_hash" 케이스 추가
- 회귀 테스트: 진짜 user-authored 파일 (frontmatter 없음 또는 generated_by 없음) 은 KEEP 그대로

### 영향
- 모든 v0.4.7 이전 install 한 사용자 (~/kairos 포함) 의 다음 `/harness-maker:make` 시 메모리 파일 자동 갱신
- 0.5.3 patch

---

## 종합 implementation order (root cause 확정 후 갱신)

```
Phase A — 완료 (Cursor docs research)
  └─ Cursor 가 .claude/hooks.json 안 읽음 + camelCase + snake_case stdin

Phase C — 구현 (의존성 순)
  ├─ C1. Issue 3 fix (reconcile.py legacy backfill)             ← 가장 작고 안전. 단독 PR 가능.
  │      위험: ~v0.4.7 사용자가 메모리 body 직접 편집했다면 .backup-*/ 로 자동 보존
  ├─ C2. Issue 1 fix — 3중 결함 한 번에:
  │      a) templates/cursor/hooks.json.j2 신설 (camelCase + bash -lc PATH wrap)
  │      b) synthesize._cursor_target_files() 에 hooks.json 추가
  │      c) render.py: .cursor/hooks.json pure-JSON 분기
  │      d) reconcile.py: .cursor/hooks.json REPLACE 분기
  │      e) telemetry.py + permission_gate.py stdin reader 가 dual-key (Pascal/snake)
  └─ C3. Issue 2 fix — worktree 명시 inline:
         a) harness_maker.worktree CLI 노출 (이미 있는지 확인 필요)
         b) templates/commands/hm/execute.md.j2 + loop.md.j2 head/tail 에 worktree blocks
         c) worktree-isolator skill 은 documentation only 로 격하

Phase D — 검증
  ├─ unit + snapshot test 추가
  ├─ tests/cursor-compat/MANUAL_CHECKLIST.md 의 A2/Phase 2.8 재실행 + RESULTS.md 채우기
  ├─ ~/kairos 에 0.5.3 install + 한 iter 돌려서 metrics.jsonl 생성 확인
  └─ tests/cursor-compat/fixture 에 cursor hooks 검증 케이스 추가

Release: 0.5.3 patch (3개 fix bundle)
```

## 사용자 협조 필요 (선택)

본 fix 는 docs 기반으로 root cause 확정됐으므로 진단용 협조는 불필요. 다만 검증 단계 (Phase D) 에서:

- [ ] **현재 ~/kairos 루프 처리**: fix 적용 전 95 파일 working tree 정리 필요. 옵션 (사용자 결정):
   - (a) 현재 루프 wrapup 까지 진행 → commit → 그 위에 0.5.3 적용
   - (b) `git stash` → 0.5.3 적용 → 새 루프 시작 (이전 것 폐기)
   - (c) 그대로 두고 0.5.3 적용 + worktree 부터 새로 시작 (95 파일은 main 에 잔존)
- [ ] **Cursor IDE 버전 확인**: Help → About. <2.4 면 사용자 업그레이드 필요 (우리 0.5.3 이 fix 하더라도 hook 자체 미지원).
- [ ] 0.5.3 install 후 짧은 task 한 번 — `metrics.jsonl` 1줄 이상 쌓이는지 확인.

## 발견된 부수 이슈 (별도 추적)

본 root cause 진단 중 부수적으로 확인된 것 — 0.5.3 에 동봉할지 별도 plan 으로 분리할지 결정 필요:

- **Slash command 위치 미문서화**: Cursor docs 가 `.claude/commands/` 호환 명시 X. 사용자가 `/hm:loop` 호출 성공 = 운 좋게 작동 중. 보수적으로 `.cursor/commands/hm-<name>.md` 추가 렌더 권장. → 별도 plan 추천.
- **`.cursor/rules/*.mdc` strict-reject 미문서화**: `description / globs / alwaysApply` 외 frontmatter 필드 처리 미정. 우리 `content_hash` 추가 시 reject 가능성 → CLAUDE.md §2 의 sidecar `.hm-meta.yaml` 도입 결정 시급. → 별도 plan.
- **Cursor "Hooks" 디버그 탭 + Output 채널 안내**: README troubleshooting 섹션 추가 — 0.5.3 docs 동봉.

## 참고

- Cursor docs (검증된 권위): <https://cursor.com/docs/hooks>, <https://cursor.com/docs/skills>, <https://cursor.com/docs/agent/subagents>, <https://cursor.com/docs/context/rules>
- 2.4 changelog: <https://cursor.com/changelog/2-4>
- Forum 사례: <https://forum.cursor.com/t/hooks-in-2-4-7-are-still-not-working-properly/149431>
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — Phase D 검증 backbone
- 0.5.0 릴리스 당시 RESULTS.md 빈 채로 통과시킨 것 = 본 사고의 직접 원인. 0.5.3 릴리스 시 RESULTS.md 의 A2/Phase 2.8 PASS/FAIL 채워야 회귀 방지.
