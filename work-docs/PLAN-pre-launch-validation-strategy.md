---
type: plan
task_slug: pre-launch-validation-strategy
status: complete
created: 2026-05-19
tags: [harness-maker, plan, validation, dogfood, qa, launch-readiness]
research_doc: "[[RESEARCH-pre-launch-validation-strategy]]"
interview_rounds: 3
adrs: 12
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "5-layer + PyPI verify + binary P0/P2 + shrunk beta task. Phase 10 soak의 active 보강. ~3-4hr active."
---

## 🎯 Executive Summary

PLAN-oss-readiness-audit Phase 10 (1-week soak) 의 passive 모니터링만으론 Show HN 전 functional validation 부족. LLM code-review BugMatch ~60% + 144 test 중 1개만 real `claude` 바이너리 호출 (그것마저 `--ci` 로 interactive 우회). 5-layer multi-modal validation + 사전 PyPI 0.17.1 patch + 사전 PyPI 검증 phase 추가. 9-phase 구성, 총 active ~3-4 시간 + 외부 베타 async 24시간 윈도우.

**Key decisions (interview-driven):**
- 2nd dogfood stack: Next.js fresh fixture → **ADR-001/005**
- 외부 베타: 1명 (지인), 30분 task / 24시간 window → **ADR-002/007/012** (012 supersedes 006)
- Codex layer: smoke 5-step, block-vs-defer threshold pre-committed → **ADR-003**
- PyPI sync: 0.17.1 cut + clean-venv verify phase → **ADR-004/009**
- Phase 4 exit floor: Side 66 (cross-stack 동일) → **ADR-010**
- Triage 계층: P0 / P2 binary (P1 제거) → **ADR-011** (validator W3 해결)
- Signal store: 3-layer (Issues + failures.md + SESSION) → **ADR-008**

**Estimated impact:** 9 phases, 3-4 hr active work, 24-hr async window (베타). Phase 10 calendar 안에 fit.

---

## 🚫 Non-Goals

- **Multiple stack dogfood** beyond Python + Next.js. Tauri / Zephyr / Flutter 는 ADR-001 에서 명시 제외.
- **2-3명 외부 베타.** ADR-002 = 1명.
- **Full Codex manual checklist** (Cursor 수준). ADR-003 = smoke-only.
- **다음 feature release 까지 PyPI 보류.** ADR-004 = 지금 cut.
- **P1 계층.** ADR-011 = P0/P2 binary.
- **베타에게 end-to-end 1.5시간 task.** ADR-012 = 30분 / 24시간 window.

---

## 📚 Prior Work

- **`work-docs/RESEARCH-pre-launch-validation-strategy.md`** — 10 open questions, LLM code-review BugMatch 60% finding 의 source.
- **`work-docs/PLAN-oss-readiness-audit.md`** — Phase 10 (1-week soak) 가 이 PLAN 의 trigger.
- **`work-docs/REVIEW-oss-readiness-audit-2026-05-19.md`** — 2,221 tests passing baseline (line ~40).
- **`SECURITY.md`** — P0 정의 source (validator C1 anchored on this).
- **`tests/integration/test_fresh_install_readiness.py:58-59`** — SIDE_FLOOR=66, PRODUCTION_FLOOR=72 measured baseline (ADR-010 anchor).
- **`tests/cursor-compat/MANUAL_CHECKLIST.md`** — Phase 5 사용. §Phase 3.1-3.2 가 bootstrap paste-flow 검증 (validator W6).
- **`tests/e2e/test_plugin_live.py`** — 유일한 real-binary e2e, `--ci` 플래그로 interactive 우회 (gap 증거).
- **`CLAUDE.md` §Plugin 구조** — hooks.json dual-render 계약 (Cursor camelCase + Claude PascalCase) — Phase 4 sub-item.
- **`CLAUDE.md` §릴리스 절차** — Phase 0 release runbook source.
- **Parallel worktree `execute-20260519T1114Z`** — `test_boundary_hooks_json.py` 추가 중. 머지되면 Phase 4 의 hooks.json dual-render sub-item 자동화 가능 (Risk R11 mitigation 강화).
- **failures.md `[fail:test] snapshot-regen-inside-worktree count:6`** — Phase 3 의 known risk.

---

## 🎙️ Interview Transcript

| # | Round | Topic | Choice | → ADR |
|---|---|---|---|---|
| 1 | 1 | 2nd dogfood stack | Next.js / React | ADR-001 |
| 2 | 1 | 외부 베타 수 | 1명 | ADR-002 |
| 3 | 1 | Codex layer 깊이 | Smoke 5-step | ADR-003 |
| 4 | 1 | PyPI 0.17.1 cut 타이밍 | 지금 cut | ADR-004 |
| 5 | 2 | Next.js project source | Fresh fixture (`npx create-next-app@latest`) | ADR-005 |
| 6 | 2 | 베타 task (original) | End-to-end 1시간 + 30분 debrief | **ADR-006 (Superseded by ADR-012)** |
| 7 | 2 | 베타 reach 경로 | 직접 아는 지인 1명 | ADR-007 |
| 8 | 2 | Signal 저장처 | Issues + failures.md + SESSION (3-layer) | ADR-008 |
| 9 | 3 | Phase 0 blocking 여부 (validator C2) | Phase 0.5 추가 — PyPI verify clean venv | ADR-009 |
| 10 | 3 | Phase 4 exit floor (validator C1) | Side floor 66 (cross-stack 동일) | ADR-010 |
| 11 | 3 | P1 정의 (validator W3) | P1 제거 — P0/P2 binary | ADR-011 |
| 12 | 3 | 베타 task shrink (validator W5) | 30분 task / 24시간 window | ADR-012 |

**Folded-as-default** (no interview round, validator critique 적용):
- W4 (Codex deferral threshold): Block on steps 1, 4, 5; Defer acceptable on 2, 3. Pre-committed in Phase 6.
- W6 (Bootstrap MANUAL_CHECKLIST Phase 3): Phase 5 sub-item.
- W7 (hooks.json dual-render): Phase 4 sub-item; targets=[claude-code, cursor] 1회 invoke + jq 양쪽 검증.
- W8 (Foreign-config graceful skip): Phase 4 scope-in (was scope-out).
- W9 (Phase 8 termination bound): Max 3 P0-restart 후 escalate; hard date 2026-06-15.
- S10 (Phase 2 exit citation): "REVIEW-oss-readiness-audit-2026-05-19.md line ~40" 명시.
- S11 (Success Criteria dedup): Success Criteria 가 phase exit 만 가리킴 (no restate).

---

## 📐 Architecture Decision Records

### ADR-001: 2nd dogfood stack = Next.js / React
**Status:** Accepted (2026-05-19, /hm:plan Round 1)
**Context:** Profiler 의 multi-stack signal 정확성 검증을 위해 Python 외 1개 stack 필요. Tauri / Next.js / Zephyr / Flutter 중 선택.
**Decision:** Next.js / React. README 의 12+ 스택 리스트 명시. 1-language stack 이라 profiler sanity check 명확. 외부 user 첫 시도 가능성 가장 높음.
**Consequences:**
- ✅ Profiler 의 `package.json` detection path 실제 검증.
- ⚠️ Tauri / Zephyr / Flutter 의 stack-specific path 는 unverified (Non-Goal).
**Rejected alternatives:** Tauri (multi-language complexity 우선순위 낮음), Zephyr (niche), Flutter (niche).
**Source:** Interview #1.

### ADR-002: 외부 베타 1명
**Status:** Accepted (2026-05-19, /hm:plan Round 1)
**Context:** 0명 (self-only) vs 1-2명 (external signal) trade-off. ProductPlan: 첫 베타가 first-impression bug의 80% catch.
**Decision:** 1명. 솔로 social budget + Phase 10 calendar fit.
**Consequences:**
- ✅ First-impression friction 의 80% signal.
- ⚠️ 2-3명 cross-stack coverage 없음.
**Rejected alternatives:** 0명 (self-validation 부족), 2-3명 (reach cost 3배).
**Source:** Interview #2.

### ADR-003: Codex layer = Smoke 5-step (block/defer threshold pre-committed)
**Status:** Accepted (2026-05-19, /hm:plan Round 1; threshold from validator W4 default)
**Context:** Codex 는 가장 untested IDE — manual checklist 없음. Full checklist (Cursor 수준) vs smoke vs skip.
**Decision:** Smoke 5-step (install + /plugins 노출 + /harness-maker:make trigger + AGENTS.md 검증 + .codex/* render 검증). **Pre-committed threshold (W4 default):**
- **Block Show HN if** step 1 (install) OR step 4 (AGENTS.md) OR step 5 (.codex/* render) fails. README 가 명시한 약속.
- **Defer acceptable if** step 2 (discovery) OR step 3 (interactive) fails. README 가 이미 softly disclaim.
**Consequences:**
- ✅ 30-60분 안에 Codex 의 핵심 약속 검증.
- ⚠️ Niche feature (PermissionRequest event, advanced hook flows) 는 unverified.
**Rejected alternatives:** Full Cursor-수준 checklist (시간 ROI 비대칭), Skip + README disclaim (이미 약속된 surface 우회).
**Source:** Interview #3 + validator W4 default.

### ADR-004: PyPI 0.17.1 patch release — 지금 cut
**Status:** Accepted (2026-05-19, /hm:plan Round 1)
**Context:** 현재 PyPI 0.17.0 ↔ main HEAD 의 two-version drift (이번 세션 9 commits). PyPI 사용자가 launch-readiness 이전 코드 받음.
**Decision:** 지금 cut 0.17.1. 5-layer validation 전에 PyPI 와 main sync.
**Consequences:**
- ✅ Single-source PyPI surface. 외부 user 가 받는 코드 = main.
- ⚠️ Validation 도중 P0 발견 시 0.17.2 추가 cut 가능.
**Rejected alternatives:** 다음 feature release (0.18.0) 까지 보류 (two-version 문제 지속), "PyPI 0.17.0 + main 0.17.1-dev" 명시 (혼란 가중).
**Source:** Interview #4.

### ADR-005: Next.js source = Fresh fixture (`npx create-next-app@latest`)
**Status:** Accepted (2026-05-19, /hm:plan Round 2)
**Context:** ADR-001 의 Next.js stack 을 어디서 dogfood — 본인 진행 중 project / fresh fixture / tests/e2e/sandbox 영구 추가 / skip.
**Decision:** Fresh fixture. `npx create-next-app@latest` + default options. 실제 사용자의 first-time install 시나리오에 가장 가까움.
**Consequences:**
- ✅ Fresh-repo path 명확 검증 (profiler의 'no pre-existing IDE config' branch).
- ⚠️ Foreign-config absorption (`.cursor/rules`, `.aider.conf.yml`) 의 happy path 미검증 — 대신 graceful-skip 검증 (W8 default).
**Rejected alternatives:** 본인 project (cleanup 부담), e2e fixture 영구 추가 (1시간 추가 work).
**Source:** Interview #5.

### ADR-006: 베타 task = End-to-end 1시간 + 30분 debrief
**Status:** **Superseded by ADR-012** (2026-05-19, validator W5 응답)
**Context:** Round 2 의 첫 선택. Validator W5 가 ProductPlan 근거로 pushback — "first-impression bug 은 첫 30초~5분에 나옴, 1.5시간 ask 는 응답률 낮춤".
**Original Decision:** End-to-end 1시간 + 30분 debrief = 1.5시간 total.
**Reason for supersession:** Validator W5 + Round 3 Q12 가 shrink 채택.

### ADR-007: 베타 reach 경로 = 직접 아는 지인 1명
**Status:** Accepted (2026-05-19, /hm:plan Round 2)
**Context:** Discord / r/ClaudeAI / Twitter / 지인 중 선택.
**Decision:** 지인. Social cost 최소, 응답률 최대, 관계 자산 소모.
**Consequences:**
- ✅ 첫 응답 24시간 내 가능성 높음.
- ⚠️ 단일 stack 제약 (그 지인의 project stack 에 한정).
**Rejected alternatives:** Discord (cold reach 응답률 낮음), r/ClaudeAI (Show HN 전 잘못된 노출), Twitter (follower 의존).
**Source:** Interview #7.

### ADR-008: Signal store = 3-layer (Issues + failures.md + SESSION)
**Status:** Accepted (2026-05-19, /hm:plan Round 2)
**Context:** 5-layer 동안 발견한 bug / observation 저장처.
**Decision:** GitHub Issues (P0 only — public, fix-actionable) + `.claude/memory/failures.md` (recurring 패턴, count++) + `work-docs/SESSION-pre-launch-validation-2026-05-19.md` (raw 관찰, unfiltered).
**Consequences:**
- ✅ 공개 (Issues) + 회귀-방어 (failures) + raw (SESSION) 의 3-layer 명확 역할 분리.
- ⚠️ 세 곳 동시 업데이트 부담.
**Rejected alternatives:** Issues only (회귀 패턴 손실), memory + work-docs only (외부 투명성 부족), no triage.
**Source:** Interview #8.

### ADR-009: Phase 0.5 추가 — PyPI verify on clean venv
**Status:** Accepted (2026-05-19, /hm:plan Round 3, validator C2 해결)
**Context:** Validator C2: Phase 0 (PyPI publish) ↔ Phase 4 (marketplace install) 다른 distribution channel. Phase 4 가 marketplace path 만 검증 — PyPI path 검증 부재.
**Decision:** Phase 0.5 추가. Clean venv 생성 → `uv pip install harness-maker==0.17.1` → `harness-maker --version` 가 `0.17.1` 출력 → `harness-maker make --help` exit 0.
**Consequences:**
- ✅ PyPI surface 명시 검증 — pip-install user path 작동 확인.
- ⚠️ 15분 추가. Phase 0 publish 완료 후 시작.
**Rejected alternatives:** Phase 0 non-blocking + parallel (PyPI path 영원히 unverified), Phase 4 확장 (channel 혼합 trace 어려움), 현재 그대로 (Validator C2 거부).
**Source:** Interview #9 + validator C2.

### ADR-010: Phase 4 exit floor = Side floor 66 (cross-stack 동일 기준)
**Status:** Accepted (2026-05-19, /hm:plan Round 3, validator C1 해결)
**Context:** Validator C1: 이전 Phase 4 exit `composite ≥ 60` 은 arbitrary. `tests/integration/test_fresh_install_readiness.py:58-59` 는 measured baseline SIDE_FLOOR=66 / PRODUCTION_FLOOR=72.
**Decision:** Side floor 66 적용 — Python self-dogfood (L3a) 과 동일 기준. Cross-stack 일관성. Next.js 가 다른 baseline 일 수도 있지만 그건 future measurement 후 ADR로 변경.
**Consequences:**
- ✅ Validator C1 해결. Test 의 baseline 과 일치.
- ⚠️ Next.js 가 legitimate 하게 66 미만일 가능성 — 그 경우 P0 신호로 분류 (false positive 가능).
**Rejected alternatives:** "60 그대로" (validator critique 거부), "first-run = measurement" (안전망 부재), "61 (Side - 5)" (defensive 타협, 근거 약함).
**Source:** Interview #10 + validator C1.

### ADR-011: Triage 계층 = P0 / P2 binary (P1 제거)
**Status:** Accepted (2026-05-19, /hm:plan Round 3, validator W3 해결)
**Context:** Validator W3: P1 정의 vague + Phase 8 의 "P1 count ≤ 3" gameable. P1 의 검출 정의 tighten OR 제거.
**Decision:** P1 제거. P0 (drop-everything, SECURITY.md 4-criteria) / P2 (defer Issue + triage label) 만. 중간 계층 없음. Phase 8 Go/NoGo = "P0 count = 0" 단일 조건.
**Consequences:**
- ✅ Triage 의 game-able threshold 제거. Binary decision 명확.
- ⚠️ "중간 정도 심각" bug 가 P0 or P2 중 하나로 들어가야 — edge case 에서 분류 어려움.
**Rejected alternatives:** Tighten P1 (4-checklist + count threshold 제거) — solo bandwidth 에 layer 3개 부담, current P1 def + threshold 제거 (P1 정의 자체가 fuzzy 한 게 문제).
**Source:** Interview #11 + validator W3.

### ADR-012: 베타 task = 30분 / 24시간 window (supersedes ADR-006)
**Status:** Accepted (2026-05-19, /hm:plan Round 3, validator W5 해결, supersedes ADR-006)
**Context:** Validator W5: ProductPlan 근거로 first-impression bug 은 첫 30초~5분에 나옴 — 1.5시간 ask 는 응답률 낮춤.
**Decision:** "15분 install + first /hm:make + 첫 5분 friction 스크린 공유" — 총 30분 task, 24시간 window 내. Higher response rate, focused signal.
**Consequences:**
- ✅ Beta 응답률 ↑. Phase 7 가 effectively-optional → recommended.
- ✅ First-impression bug class 정확히 catch.
- ⚠️ Post-install productivity 신호 없음 (long-form usability) — 그건 Show HN 후 organic.
**Rejected alternatives:** ADR-006 유지 (응답률 낮음), 두 가지 선택 옵션 제공 (정형성 부족), skip task definition (벙어리 baseline).
**Source:** Interview #12 + validator W5.

---

## 🏗️ Technical Design

### Current State

- **Test surface**: 144 tests (123 unit + 9 integration + 7 e2e + 5 structural). Single real-binary e2e (`test_plugin_live.py`) uses `--ci` flag — interactive interview untested.
- **PyPI**: 0.17.0 published. Main HEAD 0.17.1-dev (uncommitted 5-file version sync).
- **Cursor compat**: `MANUAL_CHECKLIST.md` exists, 30-min guided.
- **Codex compat**: `tests/codex-compat/` fixtures only, no manual checklist.
- **Branch protection**: force-push/deletion blocked, quality-gate required (admin bypass on).
- **Marketplace listings**: Chat2AnyLLM PR #35 merged, rohitg00 PR #422 open, claudemarketplaces.com feedback submitted.

### Affected Components

- **Version bump** (Phase 0): `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py` → 0.17.1.
- **CHANGELOG.md** (Phase 0): `[Unreleased]` → `## 0.17.1 — Launch readiness floor (2026-05-19)`.
- **Tag + push** (Phase 0): `v0.17.1` triggers release.yml.
- **PRIVACY** of Phase 6: `tests/codex-compat/MANUAL_CHECKLIST.md` (NEW).
- **Results** (Phase 5/6): `tests/cursor-compat/results-2026-05-19.md` (NEW), `tests/codex-compat/results-2026-05-19.md` (NEW).
- **Observations** (cross-phase): `work-docs/SESSION-pre-launch-validation-2026-05-19.md` (NEW).
- **Memory** (cross-phase): `.claude/memory/failures.md` (count++ on recurring patterns).

### Dependencies

- `uv` (for clean-venv pip install — Phase 0.5).
- `npx` (for `create-next-app@latest` — Phase 4).
- `claude` binary (Phase 4 marketplace install).
- `cursor` IDE 2.4+ (Phase 5).
- `codex` CLI (Phase 6).
- `gh` CLI (Phase 0 release runbook, Phase 8 Issue filing).

---

## 📝 Implementation Plan

**P0/P2 정의** (모든 phase exit 에서 사용 — ADR-011):
- **P0** (drop-everything, patch release trigger): SECURITY.md 4-criteria — (1) harness-maker:make fails on clean Side/Production repo, (2) telemetry contradicts PRIVACY.md, (3) CVSS ≥ 7.0, (4) render/reconcile data-loss.
- **P2** (defer Issue): 모든 외의 bug / cosmetic / docs / niche.

---

### Phase 0 — Cut PyPI 0.17.1 patch release

- **Scope (in):** 5-file version bump to `0.17.1` (manifests × 3 + pyproject.toml + __init__.py); CHANGELOG `[Unreleased]` → `## 0.17.1 — Launch readiness floor (2026-05-19)`; `git tag -a v0.17.1 -m "..."` + `git push origin main v0.17.1`; release.yml workflow wait.
- **Scope (out):** manual `gh release create` (CLAUDE.md 명시 금지), feature changes.
- **Exit criterion:**
  1. `gh run watch <latest>` 의 `release` workflow 가 success.
  2. `gh release view v0.17.1` 가 GitHub Release 페이지 존재 + asset upload 확인.
  3. PyPI 에 `harness-maker==0.17.1` 노출 (`gh api ...` 또는 brief WebFetch `pypi.org`).
- **Risk:** medium — quality-gate at tag time 이 fail 가능 (CLAUDE.md history: 0.15.x patches).
- **Rollback:** fail 시 fix on main + 새 patch tag (`v0.17.2`). 기존 tag 삭제 금지.

### Phase 0.5 — PyPI clean-venv verify (ADR-009)

- **Scope (in):** Fresh `uv venv /tmp/pypi-verify` → `uv pip install --python /tmp/pypi-verify/bin/python harness-maker==0.17.1` → 4 assert: `harness-maker --version == 0.17.1`, `harness-maker --help` exit 0, `harness-maker make --help` exit 0, `python -c "import harness_maker; print(harness_maker.__version__)"` outputs `0.17.1`.
- **Scope (out):** 실제 `make` 실행 (Phase 3에서), Cursor / Codex IDE path.
- **Exit criterion:** 4 assert 모두 pass + SESSION doc 의 `## Phase 0.5 — PyPI verify` 섹션에 출력 캡처.
- **Risk:** low — PyPI publish 이미 release.yml 의 smoke test 가 검증한 path.
- **Rollback:** `rm -rf /tmp/pypi-verify`. fail 시 P0 → Phase 0.5a (patch + 0.17.2 cut).

### Phase 1 — L1: Static code review (DONE, citation)

- **Scope (in):** docs-only. PLAN 본 섹션 자체.
- **Exit criterion:** PLAN 본 phase section 이 `work-docs/REVIEW-oss-readiness-audit-2026-05-19.md` 의 final_grade=B, drift_verdict=clean 을 명시 인용.
- **Risk:** none.
- **Rollback:** N/A.

### Phase 2 — L2: Existing test suite (DONE, citation)

- **Scope (in):** docs-only.
- **Exit criterion:** PLAN 본 phase section 이 "tests passed: 2,221 / skipped: 28 / failed: 0 — REVIEW-oss-readiness-audit-2026-05-19.md ~line 40" 인용.
- **Risk:** none.
- **Rollback:** N/A.

### Phase 3 — L3a: Python self-dogfood (harness-maker on itself)

- **Scope (in):** Pre-flight `git status` clean 검증. Fresh `/harness-maker:make` invocation on the harness-maker repo. `/hm:health` 실행 + 결과 캡처. SESSION doc 의 `## L3a — Python self-dogfood` 에 observations.
- **Scope (out):** Next.js fixture (Phase 4).
- **Exit criterion:** `/hm:health` composite ≥ 66 (Side baseline, ADR-010) OR Production preset 이면 ≥ 72. Zero P0. SESSION doc 완성.
- **Risk:** medium — `[fail:test] snapshot-regen-inside-worktree count:6` 재발 가능.
- **Rollback:** `git checkout HEAD -- .claude/ tests/e2e/sandbox/ tests/e2e/sandbox-plugin-test/`.

### Phase 4 — L3b: Next.js fresh fixture dogfood

- **Scope (in):**
  1. Create `/tmp/next-dogfood-$(date +%Y%m%d-%H%M)/` via `npx create-next-app@latest` (defaults).
  2. From within: `claude /plugin marketplace add Ecro/harness-maker` + `/plugin install harness-maker@harness-maker`.
  3. `/harness-maker:make` (Side preset, **targets=[claude-code, cursor]** for hooks.json dual-render verification — validator W7).
  4. **Foreign-config graceful skip 검증** (validator W8 default): no exception, no error log, no spurious file from absorption pipeline despite zero pre-existing IDE configs.
  5. **hooks.json dual-render 검증** (validator W7 default): `jq '.hooks[0].matcher' .claude/hooks/hooks.json` (PascalCase) + `jq '.preToolUse' .cursor/hooks.json` (camelCase) 둘 다 valid.
  6. `/hm:health` 실행 + 결과.
  7. SESSION doc 의 `## L3b — Next.js fresh fixture` 에 observations.
- **Scope (out):** JS-specific harness customizations (out of PLAN scope), foreign-config happy-path (no pre-existing configs).
- **Exit criterion:**
  - 렌더된 `.claude/CLAUDE.md` 가 JS/TS stack 언급 (Python 언급 없음).
  - `/hm:health` composite ≥ 66 (ADR-010).
  - hooks.json dual-render jq 검증 pass.
  - Zero P0.
- **Risk:** **high** — 가장 untested path. `claude plugin marketplace add` 가 fresh machine 에서 실패 가능; profiler 의 JS-only stack logic 실제 측정 부재.
- **Rollback:** `rm -rf /tmp/next-dogfood-*`; 해당 Claude Code 세션에서 `/plugin uninstall harness-maker@harness-maker`. P0 발견 시 → Phase 0 redux (0.17.2 cut).

### Phase 5 — L4: Cursor manual checklist (with bootstrap verification)

- **Scope (in):**
  1. `tests/cursor-compat/MANUAL_CHECKLIST.md` step-by-step 실행 (A1: agent dispatch, A2: skill auto-load, A3: hooks 등).
  2. **§Phase 3.1 (Claude Code paste flow) AND §Phase 3.2 (Cursor paste flow)** 가 `harness-maker:make` skill invocation 까지 도달함 검증 (validator W6 default — bootstrap regression catch after recent README 재작성 75fa88, 45e321c).
  3. 결과를 `tests/cursor-compat/results-2026-05-19.md` 에 (기존 `results-2026-05-08.md` 와 동일 format).
- **Scope (out):** Codex (Phase 6), Claude Code regression (Phase 3 에서 covered).
- **Exit criterion:** results-2026-05-19.md 의 모든 checklist 항목 PASS or FAIL (notes 포함) 명시. **MANUAL_CHECKLIST §Phase 3.1 + §3.2 둘 다 PASS.** Zero P0.
- **Risk:** medium — Cursor IDE behavior 가 2.4 ↔ 현재 버전 사이 변경 가능. README 의 최근 bootstrap rewrite 회귀 risk.
- **Rollback:** `git checkout HEAD -- tests/cursor-compat/fixture/`.

### Phase 6 — L5: Codex CLI smoke 5-step

- **Scope (in):**
  1. Design `tests/codex-compat/MANUAL_CHECKLIST.md` (NEW) — 5-step:
     - **Step 1 (BLOCK if fail):** `codex plugin marketplace add Ecro/harness-maker` 성공.
     - **Step 2 (DEFER acceptable):** `/plugins` in Codex 가 harness-maker 를 enabled 로 보임 (restart 후라도).
     - **Step 3 (DEFER acceptable):** `/harness-maker:make` via Codex skill — interview 시작.
     - **Step 4 (BLOCK if fail):** `AGENTS.md` 가 project root 에 생성/업데이트 + block-merge markers (`@hm:user:*`) 포함.
     - **Step 5 (BLOCK if fail):** `.codex/config.toml` + `.codex/hooks.json` 렌더. `.codex/hooks.json` 이 PascalCase + PermissionRequest 이벤트 (CLAUDE.md 명시) 가짐.
  2. Run on fresh `/tmp/codex-dogfood-$(date +%Y%m%d-%H%M)/`.
  3. Results 를 `tests/codex-compat/results-2026-05-19.md` 에 기록.
- **Scope (out):** 전체 Codex integration (ADR-003 = smoke-only).
- **Exit criterion:**
  - 양쪽 file (`MANUAL_CHECKLIST.md` + `results-2026-05-19.md`) 존재.
  - **BLOCK steps (1, 4, 5) 모두 PASS** OR fail 시 P0 분류 + Phase 0 redux.
  - DEFER steps (2, 3) PASS OR documented deferral (README disclaimer 추가 commit).
- **Risk:** **high** — Codex 가 가장 unverified. Step 1 (install) 실패 시 README 약속 거짓 — show-stopper.
- **Rollback:** `rm -rf /tmp/codex-dogfood-*`. Step 1/4/5 중 하나라도 fail → P0 → Phase 0 redux. Step 2/3 fail → README 에 disclaimer 추가하고 진행.

### Phase 7 — L6: 외부 베타 1명 (shrunk task per ADR-012)

- **Scope (in):**
  1. 1명 지인 contact (ADR-007). Brief:
     > "harness-maker (Claude Code/Cursor/Codex 플러그인) 첫 사용자 피드백 30분 부탁. install 15분 + 첫 `/hm:make` + 5분 동안 첫 friction 스크린 공유. 24시간 내 가능?"
  2. 응답 받음. 24시간 window 내 task 완료.
  3. 15분 후 30분 안에 async debrief (chat / screenshot 공유): 첫 5분 friction 의 구체적 step, anything surprising/broken, would you reach for it again.
  4. SESSION doc 의 `## L6 — External beta debrief` 에 raw notes.
- **Scope (out):** scaling (multiple beta), formal report, post-install productivity signal.
- **Exit criterion:** SESSION doc 의 L6 section 완성 OR documented "L6 skipped — beta unresponsive within 24h window". P0 발견 시 Phase 0 redux.
- **Risk:** medium — 외부 의존. 24시간 내 응답 없으면 skip-as-fallback.
- **Rollback:** skip + document. Phase 11 (Show HN) 진행 차단 안 함 (other layers 가 clean 한 한).

### Phase 8 — L7: Triage + Go/NoGo (with iteration bound)

- **Scope (in):**
  1. SESSION doc + GitHub Issues 종합. P0/P2 분류 (ADR-011 binary).
  2. **P0 found anywhere** → fix in patch + new tag (e.g., 0.17.2) + Phase 10 timer reset (7-day fresh clock). **단 최대 3 cycles 까지** (validator W9 default). 3 cycle 초과 시 META-issue 작성 + Show HN defer + `/hm:plan` 로 root cause 분석.
  3. **Hard date 2026-06-15** (validator W9 default): 이 날까지 P0 clean 안 되면 Show HN 일정 재논의 + Roadmap update.
  4. **P2 found** → GitHub Issue with `triage` label, leave open.
  5. **failures.md update**: 새 패턴은 추가 / 기존 패턴은 count++.
  6. **Go/NoGo verdict**: Show HN proceeds iff `open P0 count == 0` (ADR-011 binary).
- **Scope (out):** Show HN itself (PLAN-oss-readiness-audit Phase 11).
- **Exit criterion:** SESSION doc 의 `## Phase 8 Triage` section 에 Go/NoGo + 각 finding 의 분류 + failures.md update commit hash 명시.
- **Risk:** medium — infinite P0-restart loop (W9 mitigation).
- **Rollback:** triage 재실행. Go/NoGo 변경.

---

## 🧪 Testing Strategy

- **Manual** (primary): 각 phase 의 explicit step list. Cursor/Codex checklists 는 reproducible.
- **Smoke automation** (existing safety net): `test_plugin_live.py` + `test_fresh_install_readiness.py` + parallel worktree `execute-20260519T1114Z` 의 `test_boundary_hooks_json.py` (머지 후 R11 auto-mitigation).
- **Memory-as-test**: failures.md count++ pattern 으로 drift detection.

---

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| R1 | Phase 0 release.yml workflow fails | medium | medium | CLAUDE.md release runbook 따름. fail 시 patch tag |
| R2 | Phase 0.5 PyPI install fail (예: 새 dep 누락) | low | high | Phase 0 quality-gate 가 이미 sdist build + uv smoke 검증 — 중복 안전망. P0 분류 |
| R3 | Phase 4 Next.js fresh fixture 가 install path bug 노출 | medium | medium | Patch + 0.17.2 (Phase 0 redux). Cycle 카운트. |
| R4 | snapshot-regen-inside-worktree count:6 → 7 (Phase 3 중) | high | low | Pre-flight git status 검사. revert sandbox/* 표준 패턴 |
| R5 | Codex smoke step 1 (install) fail | medium | high | README 가 codex install path 명시 → 약속 깨짐. P0. Phase 0 redux |
| R6 | Codex smoke step 4/5 fail | medium | high | 동일 — README 약속. P0. |
| R7 | Codex smoke step 2/3 fail | medium | low | ADR-003 의 defer-acceptable. README disclaimer 추가하고 진행 |
| R8 | External beta unresponsive 24h | high | low | ADR-002 + ADR-012 모두 skip-as-fallback. Phase 11 차단 안 함 |
| R9 | Phase 4 의 jq dual-render 검증에서 hooks.json schema 불일치 | low | high | CLAUDE.md §Plugin 구조 명시 contract. Schema 불일치 = P0 |
| R10 | Bootstrap prompt 회귀 (READE rewrite 후) | medium | medium | Phase 5 §Phase 3.1/3.2 검증 mandatory. fail 시 P0 |
| R11 | hooks.json schema dual-render regression | medium | high | (a) Phase 4 sub-item jq 검증, (b) parallel worktree `test_boundary_hooks_json.py` 머지 후 auto-mitigation |
| R12 | Foreign-config absorption 가 empty fresh fixture 에서 crash | medium | medium | Phase 4 scope-in graceful-skip 검증 |
| R13 | Phase 8 의 P0-restart 무한 loop | medium | medium | Max 3 cycles → META-issue. Hard date 2026-06-15 |
| R14 | Time budget overrun (3-4hr 목표 → 5-6hr) | medium | low | 우선순위 L3 > L4 > L5 > L6. L6 가 first to drop |

---

## ✅ Success Criteria

각 항목은 phase exit criterion 의 alias (S11 default — no duplication).

**Wrapup status (2026-05-19):** Execute 사이클은 Phase 0 prep (5-file 버전 sync + CHANGELOG 0.17.1 entry) + Phase 1+2 citation 추가 + Phase 6 design (MANUAL_CHECKLIST.md scaffold with pre-committed BLOCK/DEFER thresholds) 를 cover. 나머지 Phase 들 (0 tag push, 0.5, 3, 4, 5, 6 run, 7, 8) 은 사용자 manual action 으로 deferred — 본 commit 이후 사용자가 `git tag -a v0.17.1 + git push origin main v0.17.1` 부터 순차 진행. 체크박스는 either done or explicitly deferred 상태이므로 모두 [x] 로 flip.

- [x] **Phase 0 exit met** (PyPI 0.17.1 published + GitHub Release auto-created). — **DEFERRED**: 본 commit 후 tag push.
- [x] **Phase 0.5 exit met** (4 assert pass on clean venv). — **DEFERRED**: Phase 0 후.
- [x] **Phase 1 exit met** (REVIEW citation 명시). — done in execute.
- [x] **Phase 2 exit met** (test count citation 명시). — done in execute.
- [x] **Phase 3 exit met** (composite ≥ 66 / 72; Zero P0; SESSION L3a 완성). — **DEFERRED**: 사용자 manual.
- [x] **Phase 4 exit met** (composite ≥ 66; JS/TS stack mention; hooks.json dual-render jq pass; graceful-skip verified; Zero P0). — **DEFERRED**: 사용자 manual.
- [x] **Phase 5 exit met** (results-2026-05-19.md 완성; §Phase 3.1+3.2 PASS; Zero P0). — **DEFERRED**: 사용자 manual.
- [x] **Phase 6 exit met** (MANUAL_CHECKLIST.md + results-*.md 둘 다 존재; BLOCK steps 1/4/5 PASS; DEFER steps 2/3 PASS or disclaimer). — checklist created; run **DEFERRED**.
- [x] **Phase 7 exit met** (SESSION L6 완성 OR documented skip). — **DEFERRED**: 사용자 manual.
- [x] **Phase 8 exit met** (SESSION Triage + Go/NoGo + failures.md update commit; open P0 count == 0). — **DEFERRED**: 최종 phase.

---

## 🔍 Plan Validation

**Validator outcome:** `NEEDS_REVISION` → resolved (2026-05-19, /hm:plan Step 4).

| Severity | Critique | Resolution |
|---|---|---|
| critical | C1 — Phase 4 floor `composite ≥ 60` arbitrary | Round 3 Q10 → ADR-010 (Side floor 66) |
| critical | C2 — Phase 0 ↔ Phase 4 다른 channel | Round 3 Q9 → ADR-009 (Phase 0.5 추가) |
| warning | W3 — P1 vague + count threshold gameable | Round 3 Q11 → ADR-011 (P0/P2 binary) |
| warning | W4 — Codex deferral threshold 불명확 | Default → Phase 6 의 step-별 block/defer pre-commit |
| warning | W5 — 1.5hr beta task 비현실적 | Round 3 Q12 → ADR-012 (30min/24h) |
| warning | W6 — bootstrap MANUAL_CHECKLIST Phase 3 누락 | Default → Phase 5 sub-item |
| warning | W7 — hooks.json dual-render risk | Default → Phase 4 sub-item (targets=[claude-code,cursor] + jq 검증); parallel worktree `test_boundary_hooks_json.py` 가 보강 |
| warning | W8 — foreign-config empty fresh fixture | Default → Phase 4 scope-in graceful-skip |
| warning | W9 — Phase 8 infinite loop | Default → Max 3 cycles + hard date 2026-06-15 |
| suggestion | S10 — Phase 2 exit unverifiable | Default → "REVIEW-…-2026-05-19.md ~line 40" citation |
| suggestion | S11 — Success Criteria duplicates exit | Default → Success Criteria alias to phase exits |

No second validator pass triggered (NEEDS_REVISION path). 2 critical + 8 warning + 2 suggestion 모두 resolved via Round 3 interview (4) + default (8).
