---
type: plan
task_slug: interview-tool-cursor-compat
status: complete
created: 2026-05-12
tags: [harness-maker, plan, python, jinja2, cursor, codex, interview, tool-compat]
research_doc: "[[RESEARCH-interview-tool-cursor-compat]]"
interview_rounds: 3
adrs: 2
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Tri-IDE structured question tool support via dual-name + request_user_input"
---

## 🎯 Executive Summary

**What:** 3개 IDE (Claude Code, Cursor, Codex) 모두에서 인터뷰 시 구조화된 객관식 UI가 표시되도록 stage/command 템플릿을 수정한다.

**Why:** 현재 템플릿은 Claude Code의 `AskUserQuestion`만 명시. Cursor는 `AskQuestion` (다른 이름/다른 스키마), Codex는 `request_user_input`을 사용하는데 둘 다 참조되지 않아, 모델이 plain text로 질문을 던지고 사용자는 typing으로 답해야 하는 상태.

**Key Decisions:**
- ADR-001: `.claude/commands/hm/*.md`에 dual name mention — "Use `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code)" → single-source 유지
- ADR-002: Codex 템플릿을 "Ask in your response"에서 `request_user_input` 으로 전환 + `default_mode_request_user_input=true` flag 문서화

**Impact:** interview가 있는 모든 stage (spec, plan, research) + command (loop, configure, make, refresh, ai-readiness) + docs 업데이트. Silent upgrade on next `/hm:make --update`.

**Non-Goals (out of scope):**
- `.cursor/commands/` mirror 추가 금지 (ADR-001 rejected alternative)
- hook wiring / MCP 변경 없음
- 새로운 custom tool 개발 없음 (각 IDE의 기존 tool 활용만)
- tool schema를 템플릿에 inject 하지 않음 (모델이 자기 tool 정의 참조)

## 📚 Prior Work

- [[RESEARCH-interview-tool-cursor-compat]] — root cause 분석: `is_codex` 이진 플래그만 존재, Cursor 분기 없음
- [[PLAN-install-without-claude-code]] — IDE-agnostic bootstrap (인접 관심사)
- `[wiki:pattern] codex-is-codex-flag` — 기존 Codex 적응 패턴 (3가지: `$ARGUMENTS`, `!uv run`, `AskUserQuestion` → response-based)
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — A4.plan-mode-askquestion (TBD, 미실행)
- Codex `request_user_input` — Plan mode default, Code mode with `default_mode_request_user_input=true` flag (GitHub issue #9926, #11536, #18224)

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|-------|-------|----------|-------------------|---------|--------|------|-------|
| 1 | 1 | Single-source command conflict | Contract | .claude/commands/ 에서 tool name 차이 해결법 | A~E | B: Dual name mention | CC+Cursor 한 파일에 양쪽 명시 | ADR-001 |
| 2 | 1 | Codex tool 처리 | Architecture | Codex request_user_input 채택 여부 | A~D | B: 사용 + flag 안내 | Plan mode 기본, Code mode flag | ADR-002 |
| 3 | 1 | Schema hint | Contract | 템플릿에 schema 예시 포함 여부 | A~D | A: 생략 | 모델이 tool 정의에서 참조 | no |
| 4 | 2 | 변경 범위 | Scope | 어떤 템플릿을 수정할까 | A~D | C: stages + commands + docs 전체 | — | no |
| 5 | 2 | Flag mechanism | Architecture | Jinja2에서 3개 IDE 분기 방법 | A~D | A: is_codex + is_cursor 2개 flag | commands에서는 dual name | no |
| 6 | 2 | Backward compat | Risk | 기존 사용자 harness 업데이트 전략 | A~D | A: Silent update | 행동 개선이므로 breaking change 아님 | no |
| 7 | V | Phase 5 exit criterion | Validator | 측정 가능한 검증 방법 | A~D | A: allowlist 파일 비교 | — | no |
| 8 | V | Non-Goals | Validator | 범위 제한 항목 | A~E | E: 모두 포함 | mirror, hook, tool, schema 모두 제외 | no |

## 📐 Architecture Decision Records

### ADR-001: Dual tool name in shared commands
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** `.claude/commands/hm/*.md`는 CC와 Cursor가 공유하는 single-source (kairos 0.5.7 forensic verified). CC의 tool name은 `AskUserQuestion`, Cursor는 `AskQuestion`으로 다르다. 한 파일에 한 tool name만 쓰면 다른 IDE에서 구조화 UI가 작동하지 않음.
**Decision:** `is_codex=False` 경로(commands + stages)의 렌더 출력에 "Use `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code) to present structured options to the user"로 양쪽 tool name을 명시. 모델이 자기가 가진 tool로 매핑.
**Consequences:**
- ✅ Single-source `.claude/commands/` 유지 — kairos forensic 결과 존중
- ✅ 양쪽 IDE에서 구조화 UI 기대 가능
- ⚠️ 프롬프트 텍스트가 약간 verbose (dual name)
**Rejected alternatives:**
- Target-aware render (is_cursor flag 기반 per-target render) — 렌더 시점에 어느 IDE가 읽을지 모름 (targets=[claude-code, cursor] 일 때 commands는 한 번만 렌더)
- `.cursor/commands/` mirror — single-source 원칙 파괴, kairos forensic 무효화
**Source:** Interview #1

### ADR-002: Codex `request_user_input` 채택
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Codex CLI에 `request_user_input` 구조화 질문 tool이 존재하지만 (Plan mode 기본, Code mode는 feature flag 필요), 현재 템플릿(`is_codex=True` 경로)은 "Ask in your response"로 downgrade 중. 기존 `codex-is-codex-flag` 패턴이 "Codex에는 tool UI 없음"을 전제로 했으나 이는 outdated.
**Decision:** `is_codex=True` 경로에서 "Ask in your response"를 "Use the `request_user_input` tool to present structured options"로 전환. README/onboarding에 `default_mode_request_user_input = true` config 안내 추가.
**Consequences:**
- ✅ Codex Plan mode에서 즉시 구조화 UI 사용 가능
- ✅ Code mode 사용자도 flag 설정으로 사용 가능
- ⚠️ Code mode에서 flag 미설정 시 tool 호출 실패 가능 → fallback 문구 필요
**Rejected alternatives:**
- 현행 유지 ("Ask in your response") — 사용 가능한 tool 역량 낭비
**Source:** Interview #2

## 🏗️ Technical Design

### Current State

Templates use binary `is_codex` flag:
```jinja2
{% if is_codex %}Ask in your response{% else %}...AskUserQuestion...{% endif %}
```

- `is_codex=False` (CC + Cursor via commands) → `AskUserQuestion` (Cursor에서 미인식)
- `is_codex=True` (Codex via skills) → "Ask in your response" (tool 활용 안 함)

### Target State

Tri-state rendering:

**Commands/Stages (`is_codex=False`):**
```jinja2
{% if is_codex %}Use the `request_user_input` tool to present structured options to the user{% else %}Use `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code) to present structured options to the user{% endif %}
```

**Codex skills (`is_codex=True`):**
```
Use the `request_user_input` tool to present structured options to the user
```

### Affected Components

| Component | Files | Change Type |
|-----------|-------|-------------|
| Stage templates | `templates/stages/{plan,spec,research}.md.j2` | Pattern replacement |
| Command templates | `templates/commands/hm/{loop,configure}.md.j2` | Pattern replacement |
| Plugin command | `commands/make.md` | Direct edit (no Jinja2) |
| Codex stage skills | `synthesize.py` (via `is_codex=True` render) | Auto-propagated |
| Tests | `test_codex_stage_procedures.py` | Assertion updates |
| Docs | `HOW-IT-WORKS.md`, `HOW-IT-WORKS.ko.md`, `ARCHITECTURE.md`, `autoloop-pattern.md` | Text replacement |
| README | `README.md` | Codex flag documentation |

### Design Decisions

1. **`is_cursor` flag는 현재 불필요** — ADR-001에 의해 commands에서는 dual name으로 해결. `is_cursor` flag는 `render.py`/`synthesize.py`에 이미 `_is_cursor_*` 판별 함수가 있으므로 향후 필요 시 추가 가능하나, 이 PLAN에서는 추가하지 않음. 기존 `is_codex` flag만으로 2-way 분기 충분.

2. **Fallback clause for Codex** — `request_user_input` 호출 실패 시를 위해 Codex 템플릿에 "If the tool is unavailable, ask the same questions in your response text" 한 줄 추가.

3. **`commands/make.md` 특수 처리** — Jinja2가 아닌 raw markdown이므로 직접 텍스트 편집. `AskUserQuestion` → dual name으로 전환.

### Data Flow

```
synthesize.py
  ├─ stages/*.md.j2 (is_codex=False) → .claude/commands/hm/*.md (CC + Cursor 공용)
  │   └─ "AskQuestion (Cursor) or AskUserQuestion (CC)"
  ├─ stages/*.md.j2 (is_codex=True) → .agents/skills/hm-*/SKILL.md (Codex 전용)
  │   └─ "request_user_input"
  └─ commands/hm/*.md.j2 (is_codex=False) → .claude/commands/hm/*.md
      └─ "AskQuestion (Cursor) or AskUserQuestion (CC)"
```

## 📝 Implementation Plan

### Phase 1: Stage template pattern replacement
**Scope:** `src/harness_maker/templates/stages/{plan,spec,research}.md.j2` (interview가 있는 3개). execute/review/wrapup/verify는 AskUserQuestion 참조 없으면 skip.
**What:**
- `{% if is_codex %}Ask in your response{% else %}...AskUserQuestion...{% endif %}` →
- `{% if is_codex %}Use the \`request_user_input\` tool to present structured options to the user. If the tool is unavailable, ask the same questions in your response text.{% else %}Use \`AskQuestion\` (Cursor) or \`AskUserQuestion\` (Claude Code) to present structured options to the user{% endif %}`
- 모든 `AskUserQuestion` 단독 언급도 dual-name으로 전환
**Exit criterion:** `rg 'AskUserQuestion' src/harness_maker/templates/stages/ | rg -v 'AskQuestion.*or.*AskUserQuestion|AskUserQuestion.*or.*AskQuestion'` returns 0 lines
**Risk:** low
**Rollback:** git revert Phase 1 commits

### Phase 2: Command template pattern replacement
**Scope:** `src/harness_maker/templates/commands/hm/{loop,configure,refresh,ai-readiness,make}.md.j2` + `commands/make.md`
**What:** Same pattern as Phase 1. `commands/make.md`는 raw markdown이므로 직접 편집.
**Exit criterion:** `rg 'AskUserQuestion' src/harness_maker/templates/commands/ | rg -v 'AskQuestion.*or.*AskUserQuestion|AskUserQuestion.*or.*AskQuestion'` returns 0 lines. `commands/make.md`에서도 동일 검증.
**Risk:** low
**Rollback:** Phase 1

### Phase 3: Test updates
**Scope:** `tests/unit/test_codex_stage_procedures.py`
**What:**
- `test_codex_stage_render_no_ask_user_question` → `request_user_input` 포함 확인으로 전환
- `test_loop_codex_render_no_ask_user_question` → 동일
- `test_loop_cc_render_preserves_cc_constructs` → dual-name 패턴 확인으로 전환
- 신규: `test_cc_render_has_dual_name_pattern` — `is_codex=False` 렌더에 "AskQuestion" AND "AskUserQuestion" 양쪽 존재 확인
**Exit criterion:** `pytest tests/unit/test_codex_stage_procedures.py -v` all green
**Risk:** medium (assertion 세밀 조정 필요)
**Rollback:** Phase 1

### Phase 4: Codex flag documentation + README
**Scope:** `README.md`
**What:** Codex 섹션에 `default_mode_request_user_input = true` flag 안내 추가. interview가 Code mode에서도 작동하려면 필요하다는 설명.
**Exit criterion:** `rg 'default_mode_request_user_input' README.md` returns ≥1 match
**Risk:** low
**Rollback:** Phase 2

### Phase 5: Documentation updates
**Scope:** `docs/HOW-IT-WORKS.md`, `docs/HOW-IT-WORKS.ko.md`, `docs/ARCHITECTURE.md`, `docs/reference/autoloop-pattern.md`
**What:** bare `AskUserQuestion` 참조를 설명적 문맥으로 전환. 예: "Claude Code의 `AskUserQuestion`" → "IDE의 구조화 질문 도구 (`AskQuestion` in Cursor, `AskUserQuestion` in Claude Code, `request_user_input` in Codex)"
**Exit criterion:** `rg 'AskUserQuestion' docs/` 결과를 `tests/allowlists/askuserquestion-docs.txt`와 비교. 허용된 패턴(설명적 문맥)만 남아야 함. Allowlist 파일이 없으면 0건이어야 함.
**Risk:** low
**Rollback:** Phase 4

### Phase 6: Snapshot regeneration + full test
**Scope:** `tests/snapshot/`, sandbox fixtures
**What:** main repo root에서 `python tests/snapshot/regenerate.py` 실행 (per [fail:test] snapshot-regen-inside-worktree). `pytest` 전체.
**Exit criterion:** `pytest` all green
**Risk:** medium (hash 변경 예상)
**Rollback:** Phase 5

## 🧪 Testing Strategy

**Unit:**
- `test_codex_stage_procedures.py` — Codex renders contain `request_user_input`, CC renders contain dual-name
- Snapshot tests — rendered output hash 갱신

**Manual (Cursor):**
- `/hm:plan` 실행 → `AskQuestion` structured UI 표시 확인
- `/hm:spec` 실행 → 동일

**Manual (Codex):**
- `@hm-plan` skill 호출 (Plan mode) → `request_user_input` UI 표시 확인
- Code mode + flag → 동일

**Regression (CC):**
- `/hm:plan` 실행 → `AskUserQuestion` 정상 작동 확인

## ⚠️ Risks & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Model ignores dual-name, asks plain text | UX unchanged (no regression) | medium | Manual test; if persistent, add schema hint in Phase 7 |
| Codex `request_user_input` renamed/removed | Codex interview breaks | low | Fallback clause in template + pin to known version |
| Snapshot hashes change | CI red | certain | Phase 6 handles explicitly |
| `commands/make.md` missed | Plugin Cursor users get wrong tool | low | Phase 2 covers explicitly |
| Dual-name prompt confuses model | Wrong tool called or no tool | low | Both names are real tools; model picks its available one |

## ✅ Success Criteria

- [x] Cursor: `/hm:plan` shows `AskQuestion` structured UI
- [x] Claude Code: `/hm:plan` shows `AskUserQuestion` structured UI (regression)
- [x] Codex: `@hm-plan` in Plan mode shows `request_user_input` structured UI
- [x] `rg 'AskUserQuestion' src/harness_maker/templates/` returns only dual-name patterns
- [x] `pytest` all green including updated snapshots
- [x] README documents `default_mode_request_user_input = true` for Codex Code mode

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION → RESOLVED

| # | Critique | Severity | Resolution |
|---|----------|----------|------------|
| 1 | Phase 5 exit criterion not objectively checkable | warning | Changed to allowlist file comparison (Interview #7) |
| 2 | No explicit non-goals | warning | Added Non-Goals section (Interview #8) |
| 3 | Missing interview transcript | warning | Added compact transcript table |
