---
type: plan
task_slug: workflow-optimization-2026-05
status: complete
created: 2026-05-17
tags: [harness-maker, plan, workflow, latency, prompt-caching, preset]
research_doc: "[[RESEARCH-workflow-optimization-2026-05]]"
interview_rounds: 5
adrs: 16
validator_outcome: APPROVED_AFTER_REVISION
summary: "11-phase plan: universal cache/skip wins + Side preset round-cap reductions, quality preserved (Layer C deferred)."
---

# PLAN — Workflow Stage Optimization (2026-05)

## 🎯 Executive Summary

**TL;DR**: harness-maker 의 workflow 가 stage 간 중복 호출 (full check suite 4× / drift gate 3-4× / LLM prompt 캐싱 누락) 과 Side preset 의 quality knob 미차등 으로 latency·token cost 가 과대. 본 plan 은 **Layer A universal quality-neutral 8개 + Layer B Side preset 한정 4개 = 12 optimization** 을 phase 별 PR 로 분리 적용. **Layer C (구조 리프트) 는 본 plan 제외 — 별도 PLAN-* 으로 분리.**

**What**:
- Universal cache 추가 (HTTP + LLM prompt) → token cost 60-80% 감소 (Anthropic ephemeral cache hit 율 가정)
- Fresh-skip 강제 (4 skill / 1 stage) → 동일 input 반복 호출 시 0 cost
- Drift gate cascade demote (review = single owner) → 3-4× → 1×
- Check-suite skip with sha+diff+tool+env invariant → 4× → 1-2×
- Pass 1.5 verifier 활성 + reviewer-count==1 시 Pass 1 redaction skip → reviewer LLM 호출 ↓
- Side preset 한정: harness.yaml field 신설로 interview round caps + review rounds 차등

**Why**: 사용자 직접 보고 — "각 workflow 의 단계 수가 너무 많아 하나의 workflow 가 길다, 품질은 양보 불가". RESEARCH 가 13 approach 정리, 그 중 12개 채택.

**Key decisions** (15 ADRs):
- 범위 = A+B (ADR-001), PR 분할 = phase별 (ADR-002), 캐시 = `~/.cache/harness-maker/` (ADR-003)
- preset 분기 정책 = harness.yaml field 신설 (CLAUDE.md "stage 내부 preset 분기 0" 원칙 유지, ADR-005)
- 측정 = baseline+after wall-clock+token (ADR-011)
- B2 = reviewer count==1 조건 (ADR-009), B3 Side default max_review_rounds=2 (ADR-010), B1+B6 Side=Gate 1 round+streak=1+main=5 (ADR-014)

**Estimated impact**:
- Wall-clock: `exec-rev-wrap-ver` 에서 2-3분 절감 (check suite 4×→1-2× 기준, 1885 test + mypy strict 가정)
- Token cost: relevance-filter / secscan Gate 5 batch 호출에서 prompt prefix 60-80% 절감 (Anthropic ephemeral cache hit)
- HTTP latency: research-crawler 24h cache hit 시 0 호출
- Side preset: interview 라운드 50-66% 단축 (Production 영향 0)

## 🚫 Non-Goals (본 plan 명시 제외)

- **Layer C 전체** (C1 atomic stage idempotent guard, C3 health batch, C4 `/hm:refresh` deprecation, C5 loop Gate 2 frequency) — 별도 PLAN-* 으로 분리
- **`--no-cache` flag** (research-crawler 의 escape hatch) — `HARNESS_MAKER_CACHE_DIR=/tmp/nonexistent` 가 충분한 escape (env override, ADR-003)
- **`xdg-base-dirs` 라이브러리 도입** — `Path.home() / ".cache"` 가 WSL2/Linux/macOS 충분, Windows native 는 본 프로젝트 대상 아님 (CLAUDE.md 환경: WSL2)
- **Cache GC (`~/.cache/harness-maker/verify/*.json` stale entry purge)** — 후속 plan. 본 plan 의 cache 는 monotonic append, disk pressure 시 사용자가 `rm -rf` 가능
- **Anthropic persistent cache (`cache_control: persistent`) 검토** — ephemeral 5분 TTL 이 batch 호출에 충분. persistent 는 별도 ROI 분석 필요
- **Cursor / Codex target 별 cache path 분기** — 모든 target 이 같은 `~/.cache/harness-maker/` 공유
- **prompt cache 1024-token threshold 사전 검증 자동화** — R12 에 risk 로 기록, 테스트로 detection (자동 fail-loud 미구현)

## 📚 Prior Work

| Doc | Relevance |
|-----|-----------|
| [[RESEARCH-workflow-optimization-2026-05]] | 본 plan 의 입력 — 13 approach 정리, 9 open questions |
| [[PLAN-health-consolidation]] | 0.13.0 `82eaddb` 가 audit 명령들 `/hm:health` 로 통합. `/hm:refresh` 는 0.11.5 partial (본 plan 미포함, Layer C 분리) |
| [[PLAN-deep-interview-llm-delegation]] | 3-Layer Gate LLM 위임 결정. B1+B6 의 cap 조정이 이 결정의 ROI 보존 |
| [[RESEARCH-loop-interview-intensity]] / [[PLAN-loop-interview-intensity]] | loop intensity tier 가 quality vs speed lever. B-Layer 의 settings 와 정합 |
| [[PLAN-llm-code-review-2026]] | Pass 1/1.5/2 redaction ADR-008 위치 (deferred). 본 plan Phase 9 (A8) 가 활성화 |
| ablation-results-2pass.md | 2-pass redaction 효과 측정 베이스. A8/B2 의 ROI 검증 참조 |
| `.claude/memory/failures.md`: `[fail:test] snapshot-regen-inside-worktree (count:4)` | Phase 6/7/8/9/10/11 모두 snapshot regen 필요 → 모두 worktree 밖 regen path 따름 |

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | → ADR |
|---|-------|-------|----------|--------|-------|
| 1 | 1 | Plan 범위 | Scope | Layer A + B (12 approach), C 제외 | ADR-001 |
| 2 | 1 | PR 분할 | Risk | Phase 별 1 PR (작고 자주) | ADR-002 |
| 3 | 1 | 캐시 디렉토리 | Dependencies | `~/.cache/harness-maker/` + `HARNESS_MAKER_CACHE_DIR` env override | ADR-003 |
| 4 | 2 | C2 (Preset.SIDE 버그) | Scope | 포함 (Phase 1 우선 해결) | ADR-004 |
| 5 | 2 | Preset 분기 정책 | Architecture | harness.yaml field 신설 (CLAUDE.md 원칙 유지) | ADR-005 |
| 6 | 2 | Drift cascade | Architecture | Demote (review = owner, wrapup/verify = verdict 확인) | ADR-006 |
| 7 | 2 | Check-suite skip-key | Contract | git sha + diff hash + tool versions + env hash | ADR-007 |
| 8 | 3 | A8 Pass 1.5 verifier | Architecture | 항상 활성 | ADR-008 |
| 9 | 3 | B2 Pass 1 skip 조건 | Architecture | reviewer count == 1 조건 (preset 무관) | ADR-009 |
| 10 | 3 | B3 max_review_rounds | Risk | Side default = 2 (Production = 3 유지) | ADR-010 |
| 11 | 3 | Success criteria | Testing | wall-clock + token baseline + after 비교 | ADR-011 |
| 12 | impl | A6 fresh-skip TTL | Failure handling | agent-quality 영속 / security 24h+lock-stable / verify session+sha | ADR-012 |
| 13 | impl | A3/A4 cache_control | Contract | `ephemeral` on system block | ADR-013 |
| 14 | 4 | B1+B6 Side caps | Risk | 3-Layer Gate 1 round + streak=1 + main loop max 5 | ADR-014 |
| 15 | 4 | A7 prefix scope | Architecture | Fused workflow 전용 preamble (atomic 단독은 그대로) | ADR-015 |
| 16 | 5 (validator follow-up C3) | Schema migration policy | Architecture | Preserve-old-on-upgrade (schema_version field, 기존 Side harness 는 옛 hardcoded 값 유지) | ADR-016 |
| 17 | 5 (validator follow-up W4+W5) | Baseline 도구 범위 | Testing | Phase 2 확장 — per-call-site metric 수집 | (Phase 2 scope 확장에 반영) |
| 18 | 5 (validator follow-up W6) | Drift verdict 부재/스테일 | Failure handling | FAIL with explicit message ('run /hm:review first') | (R7 보강 + Phase 6 exit 확장에 반영) |

**Layer 2 probes used (one per round, no repeat)**: PERF (round 3, success criteria) · STAKEHOLDER (round 4, harness-maker maintainer + plan-validator).

**3-Layer Gate**: 0.929 (round 4 final) ✅ PASS · streak 2/2.

## 📐 Architecture Decision Records

### ADR-001: Plan 범위 = Layer A + B (Layer C 제외)
**Status:** Accepted (2026-05-17, via /hm:plan interview)
**Context:** RESEARCH 가 13 approach 를 4 Layer 로 정리. 1 plan 에 모두 담으면 PR 크기 폭발 + 회귀 위험.
**Decision:** Layer A (universal 8개) + Layer B (Side-only 5개 중 4개, B5 적용불가 결론으로 제외) + C2 만 (개별 ADR-004). Layer C 나머지 (C1·C3·C4·C5) 는 별도 PLAN-* 으로 분리.
**Consequences:**
- ✅ PR 11개로 분할 가능, 회귀 추적 명확
- ⚠️ Layer C 의 잠재적 절감 (loop Gate 2 frequency 등) 본 plan 에서 미실현
**Rejected alternatives:**
- "Layer A+B+C 전체" — bundled PR risk 가 phase-per-PR 정책과 충돌
- "Quick-win 만 (A3+A4+A5+C2)" — Side preset 차등 미실현, 사용자 명시 요구 ("ALL optimizations")
**Source:** Interview #1

### ADR-002: PR 분할 = Phase 별 1 PR
**Status:** Accepted (2026-05-17)
**Context:** 12개 approach 의 코드 영향 영역이 다양. 한 PR 로 묶으면 review fatigue + 회귀 origin 식별 곤란.
**Decision:** 11 phase, 각 1 PR. 같은 파일을 만지는 approach 만 묶음 (예: B2+A8 는 둘 다 review.md.j2 → 분리 phase 이지만 sequential).
**Consequences:** ✅ review 부담 분산, ⚠️ wrap cost (PR description, branch hygiene) 11회
**Rejected:** "1 bundled PR" (cognitive load), "Layer 별 PR" (Layer A 8개를 1 PR 도 큼)
**Source:** Interview #2

### ADR-003: Cache 디렉토리 = `~/.cache/harness-maker/` + env override
**Status:** Accepted (2026-05-17)
**Context:** A3/A4/A5 모두 캐시 도입. CLAUDE.md L: "GitHub API 는 unauthenticated (60/h) + `~/.cache/harness-maker/` 캐시 공유" 약속.
**Decision:** XDG 표준 경로 `~/.cache/harness-maker/<source>/<key>.json` (`Path.home() / ".cache" / "harness-maker"`). `HARNESS_MAKER_CACHE_DIR` env var 가 모든 캐시 경로 override. **xdg-base-dirs 라이브러리 도입 안 함 (Non-Goal)** — `Path.home() / ".cache"` 가 WSL2/Linux/macOS 충분.
**Consequences:** ✅ XDG 표준 정합, 사용자 간 공유, ✅ test 시 tmp dir override 가능, ⚠️ Windows native 경로 미대응 (Non-Goal — CLAUDE.md 환경: WSL2)
**Rejected:** `.claude/cache/` (project-local, CLAUDE.md 약속 미이행), "둘 다" (사용자가 옵션 A 선택), "xdg-base-dirs 도입" (Non-Goal, 의존성 추가 ROI 낮음)
**Source:** Interview #3

### ADR-004: C2 (verify Preset.SIDE 하드코딩 버그) 본 plan 포함, Phase 1 우선
**Status:** Accepted (2026-05-17)
**Context:** RESEARCH 에서 Layer C 분류였으나 정의상 correctness bug — `templates/skills/verify-before-completion/SKILL.md.j2:65` 의 `compute_readiness(Path('.'), Preset.SIDE)` 가 Production 사용자에게도 Side baseline 적용.
**Decision:** Phase 1 으로 포함. 단일 파일 변경 + unit test.
**Consequences:** ✅ Production harness 의 verify baseline 정확화, ✅ 다른 phase 의존성 0 (immediate ship), ⚠️ Layer C 분리 원칙의 작은 예외
**Rejected:** "별도 plan" (paper-cut 을 늦추는 비용 > 분리 이익), "wontfix" (Production false-positive 감소 이익 존재)
**Source:** Interview #4

### ADR-005: Preset 분기 정책 = harness.yaml field 신설 (Jinja preset 분기 금지)
**Status:** Accepted (2026-05-17)
**Context:** B1/B3/B6 는 Side preset 한정 차등. CLAUDE.md "stage 내부 preset 분기 0" 의도된 단순성 원칙.
**Decision:** **모든 Side/Production 차등은 `harness.yaml` 의 새/기존 field 값 차이로 표현**. interview.py 의 `_preset_extras` 가 preset 에 따라 다른 default 값 주입. Stage template 은 `{% if preset == 'Side' %}` 사용 금지 — 대신 `{{ config.interview.deep_gate.max_rounds }}` 같은 config 값 참조.
**Consequences:** ✅ stage template 의 preset-invariance 보존, ✅ 사용자 override 자유 (Side 인데 strict 인터뷰 원하면 field 만 변경), ⚠️ harness.yaml schema 확장 (3-4 새 field), ⚠️ migration: 기존 Side harness 들은 `/hm:make --update` 로 새 default 받음 (사용자 override 보존)
**Rejected:** "Jinja `{% if preset %}` 분기" (CLAUDE.md 원칙 위반, 유지보수 부담 ↑), "둘 다 혼용" (정합성 ↓)
**Source:** Interview #5

### ADR-006: Drift cascade = demote (review = owner, wrapup/verify = verdict 확인)
**Status:** Accepted (2026-05-17)
**Context:** Drift gate 가 execute Step 4 / review Step 2 / wrapup Step 3 / verify Check 1 에서 3-4× 반복. LLM-heavy.
**Decision:** **review Step 2 가 단독 owner**. review report 에 `drift_verdict: {result, scope_violations, scenario_misses}` 명시. wrapup Step 3 / verify Check 1 은 record 만 확인 (LLM 재호출 X). execute Step 4 는 cleanliness check (drift 아니라 worktree 상태) → 그대로 유지.
**Consequences:** ✅ LLM drift 진단 1회만, ✅ wrapup/verify 의 phase 간소화, ⚠️ wrapup 전 ad-hoc edit 으로 생긴 drift 는 못 잡음 — mitigation: wrapup advisory 메시지 유지 ("review 이후 추가 변경 시 /hm:review 재실행 권장")
**Rejected:** "Remove (wrapup/verify drift 체크 완전 제거)" (ad-hoc edit 미감지), "Skip-when-fresh sha 기준" (구현 복잡도 증가)
**Source:** Interview #6

### ADR-007: Check-suite skip-key = sha + diff + tool versions + env (inverted-allowlist) + project_root_hash
**Status:** Accepted (2026-05-17, revised after validator critique W8/R13 + C1 env scope)
**Context:** A1 의 핵심 — 같은 input 에 대해 lint+mypy+test 결과는 결정적 → 첫 PASS 이후 skip. Validator C1: env whitelist 가 LANG/LC_*/TZ/CC/RUSTC/CARGO_HOME/SOURCE_DATE_EPOCH 누락 → silent false-positive. Validator W8 R13: 두 프로젝트가 같은 sha/diff 시 cache key 충돌.
**Decision:** Skip-key 구성 (**inverted env policy + project_root 포함**):
```python
key = sha256(
    project_root_absolute_path_hash    # NEW (R13): 두 repo 의 같은 sha 충돌 방지
    + git_head_sha
    + diff_hash(staged + worktree)     # 0 if clean
    + uv_lock_hash
    + pyproject_toml_hash
    + tool_versions_json               # mypy, ruff, pytest, python interpreter semver
    + relevant_env_hash                # INVERTED: env-allowlist 외 변경 시 invalidate
)

# Inverted env policy:
# Build sorted hash of ALL os.environ EXCEPT a known-safe ignore set:
ENV_IGNORE = {
    "PWD", "OLDPWD", "_", "SHLVL", "TERM", "TERM_PROGRAM",
    "DISPLAY", "WAYLAND_DISPLAY", "SSH_*",  # interactive shell
    "EDITOR", "VISUAL", "PAGER",
    "COLORFGBG", "COLORTERM",
    "WSL_*", "WT_*",  # WSL2 noise
    "CLAUDE_CODE_*",  # harness session vars
}
# Everything else (LANG, LC_*, TZ, PATH, PYTHONPATH, VIRTUAL_ENV,
# CC, CXX, RUSTC, CARGO_HOME, SOURCE_DATE_EPOCH, NODE_ENV, CI, ...)
# is included in hash → invalidates skip on change.
```
저장 위치: `~/.cache/harness-maker/verify/<key>.json` (ADR-003). 내용: `{passed_at: ISO, checks: [lint, mypy, pytest], project_root: path, env_snapshot: {...}}`.
**Consequences:** ✅ tool version drift 자동 invalidate, ✅ locale/TZ drift 잡힘 (mypy/pytest 출력 정렬 변경 감지), ✅ project_root 다름 = key 다름 (cross-project 충돌 0), ✅ inverted policy: 알려진 noise 만 ignore, 나머지는 모두 invariant. ⚠️ ENV_IGNORE 가 너무 좁으면 false-negative (skip 못함) — 안전 방향. ⚠️ cache GC 없음 — Non-Goal, 후속 plan
**Rejected:** "sha 만" (kairos 0.5.7 forensic 위험), "sha + lock 만" (env drift 미감지), "allowlist-in 정책" (validator C1: 누락 위험), "A1 자체 드롭" (사용자가 Recommended 선택)
**Source:** Interview #7 + validator follow-up C1 + W8 R13

### ADR-008: A8 Pass 1.5 code-verifier 항상 활성
**Status:** Accepted (2026-05-17)
**Context:** review.md.j2 의 Pass 1.5 verifier 가 ADR-008 으로 deferred. Pass 1 findings reduce-only KEEP/DROP/DEMOTE → Pass 2 의 findings 수 감소.
**Decision:** Pass 1.5 verifier 항상 활성. 단, B2 (ADR-009) 가 발동 (reviewer count==1) 하면 Pass 1 자체가 없으므로 verifier 도 자동 skip — 별도 조건 불필요.
**Consequences:** ✅ Pass 2 의 LLM 입력 토큰 감소 (false positives reduce), ⚠️ verifier 자체가 LLM 호출 1회 추가 — 하지만 reduce-only 라 cheap (KEEP/DROP/DEMOTE label only)
**Rejected:** "Pass 1 findings N≥5 시만 활성" (cutoff 결정 자의적), "deferred 유지" (ROI 측정 안된 상태로 무한 deferred)
**Source:** Interview #8

### ADR-009: B2 Pass 1 redaction skip 조건 = reviewer count == 1
**Status:** Accepted (2026-05-17)
**Context:** Pass 1 redaction 의 목적 = cross-reviewer cargo-cult 합의 차단. Reviewer 1 명이면 bias source 없음.
**Decision:** review.md.j2 에 conditional 추가: `{% if config.reviewers.enabled|length + ad_hoc_reviewers|length == 1 %}skip Pass 1{% endif %}`. **preset 분기 아님** (ADR-005 원칙). Side+Production 둘 다 reviewer 1명 시 발동.
**Consequences:** ✅ Side default (1 reviewer) 에서 자동 적용, ✅ Production 도 사용자가 reviewer 1개로 설정 시 적용, ⚠️ `--with-reviewers=` ad-hoc 추가 시 count 증가 → 자동 보호
**Rejected:** "Side preset 시 항상 skip" (Side+ad-hoc 조합 시 bias source 있음), "항상 skip" (Production multi-reviewer 의 bias mitigation 손실)
**Source:** Interview #9

### ADR-010: B3 Side default `max_review_rounds = 2`
**Status:** Accepted (2026-05-17)
**Context:** 현재 모든 preset default = 3. Side velocity 우선 정책 + grade target B (vs Prod A).
**Decision:** `interview.py` 의 `_preset_extras` 에 Side default `reviewers.max_review_rounds: 2`. Production 은 3 유지. 사용자 override 자유 (`/hm:configure`).
**Consequences:** ✅ Side auto-fix loop 33% 단축, ⚠️ 잔여 issue 가 `human_review_needed` flag 로 노출 (CHANGES_REQUESTED) — 이게 의도
**Rejected:** "1" (auto-fix 실효성 ↓), "3 유지" (B3 효과 0)
**Source:** Interview #10

### ADR-011: Success measurement = baseline + after wall-clock + token cost
**Status:** Accepted (2026-05-17)
**Context:** "품질 양보 불가" 정책 하에서 최적화 효과 검증 필요. RESEARCH 의 "60-80% 절감" 추정값 정량 확인.
**Decision:**
- Phase 2 에서 baseline script `scripts/measure_workflow_baseline.py` 추가 → JSON 출력 `{pytest_seconds, mypy_seconds, ruff_seconds, /hm:health_seconds, /hm:review_token_estimate}`
- 각 PR 의 exit criterion 에 "baseline 대비 delta % 첨부 (description 의 표)"
- final wrap PR 11 후 비교 sweep
**Consequences:** ✅ "60-80% 절감" 가설 검증 가능, ⚠️ baseline 측정 자체가 1회 cost (분 단위), ⚠️ wall-clock 은 머신 성능 의존 — token cost 가 더 안정적 metric
**Rejected:** "테스트 통과만" (정량 비교 불가), "PR 별 micro-benchmark" (작성 cost ↑↑)
**Source:** Interview #11

### ADR-012: A6 fresh-skip TTL defaults
**Status:** Accepted (2026-05-17, implementation default)
**Context:** SKILL.md 들이 약속한 skip 헬리스틱이 미시행. RESEARCH 의 open question.
**Decision:**
- `agent-quality-rubric`: skip if `tier in {Platinum, Gold}` (content-based, TTL 무관)
- `security-scanner`: skip if `last_scan < 24h ago` AND `uv.lock` + `pyproject.toml` + `.claude/**` 변경 없음
- `verify-before-completion`: skip if `last_PASS in same session` AND `git diff` 빈상태 AND `git sha unchanged`
- 모두 `--force` flag 로 override 가능
**Consequences:** ✅ 반복 호출 시 0 cost, ⚠️ TTL 24h 는 CVE 신규 등록 시 stale — `security-scanner --force` 가 mitigation
**Rejected:** "12h TTL" (cycle 보다 짧으면 hit 안됨), "never-skip" (전체 plan 의 cost saving 가설 무력화), "TTL 1주" (CVE 0-day disclosure 시 위험), "agent-quality 도 TTL 기반" (tier 가 더 안정적 fingerprint)
**Source:** Implementation default (Interview Round 3+)

### ADR-013: A3/A4 cache_control = `ephemeral` on system block
**Status:** Accepted (2026-05-17, implementation default)
**Context:** RESEARCH open question. Anthropic prompt cache placement.
**Decision:** `relevance.py` 의 `_build_relevance_system_prompt` 및 `security_scanner.py` 의 prompt-injection rubric 둘 다, Anthropic API call 의 `system=[{"type": "text", "text": ..., "cache_control": {"type": "ephemeral"}}]` 형태로 변경. `llm_judge.py:79` / `foreign_config.py:308` 의 기존 패턴 재사용.
**Consequences:** ✅ N items batch 시 hit 률 90%+ (project context 동일), ✅ 5분 TTL → batch 안에서 안전, ⚠️ user pause 5분+ 시 cache miss (full cost) — 통상 batch 호출 안에서 발생 가능성 낮음, ⚠️ system prompt < 1024 tokens 시 cache 무효 (Anthropic minimum) — R12 risk 로 기록, Phase 3 test 가 길이 assert
**Rejected:** "cache_control on messages content block" (per-message 변경 시 cache invalidate, less stable), "persistent cache type" (별도 ROI 평가 필요, 본 plan Non-Goal), "cache_control 미적용" (60-80% prefix token 절감 손실)
**Source:** Implementation default

### ADR-014: B1+B6 Side caps = Gate 1 round + streak=1 + main loop max 5
**Status:** Accepted (2026-05-17)
**Context:** Side preset 의 interview 단축. 새 harness.yaml field (ADR-005 따름).
**Decision:** harness.yaml 신규 fields (Side default vs Prod default):
- `interview.deep_gate.max_rounds`: Side=1, Prod=3
- `interview.deep_gate.streak_target`: Side=1, Prod=2
- `interview.main_loop.max_rounds`: Side=5, Prod=null (unlimited 유지)

Stage template (research/spec/plan) 의 gate 로직이 이 config 읽음.
**Consequences:** ✅ Side interview 50-66% 단축, ✅ Production 영향 0, ⚠️ gate 1 round + streak 1 은 robustness 약간 ↓ — Side 정책상 수용
**Rejected:** "Gate skip + main 3" (gate 완전 제거 시 ADR 부실 위험), "Gate 2 rounds + main 8" (Production 과 거의 동일)
**Source:** Interview #14

### ADR-016: Schema migration policy = preserve-old-on-upgrade (schema_version field)
**Status:** Accepted (2026-05-17, validator follow-up C3)
**Context:** Validator C3 critical: Phase 11 의 새 fields (`interview.deep_gate.*`, `interview.main_loop.*`) 가 기존 Side harness 에 없음 → `answers_from_harness_yaml` 가 reverse-map 할 키 없음 → 기존 사용자가 silent 하게 Side 새 default (1/1/5) 받음.
**Decision:** `harness.yaml` 에 `schema_version: <N>` field 도입. interview.py:
- `schema_version` 없거나 `< 2` AND preset=Side → 새 fields 의 default 를 **옛 hardcoded 값** (`deep_gate.max_rounds=3, streak_target=2, main_loop.max_rounds=null`) 으로 주입
- `schema_version >= 2` OR 새 harness 생성 → Side 새 default (`1, 1, 5`)
- `/hm:make --update` 시 schema_version 낮은 harness 감지 → advisory 메시지: "Side default 가 변경됐습니다 (max_rounds 3→1). opt-in 하려면 `interview.deep_gate.max_rounds: 1` 명시 또는 `schema_version: 2` 로 업데이트". 자동 silent migration 없음.
**Consequences:** ✅ 기존 Side 사용자 무중단, ✅ 새 사용자 즉시 새 default 적용, ✅ opt-in path 명확, ⚠️ migration code 추가 (interview.py 분기 + advisory 메시지 + 새 test), ⚠️ schema_version field 가 harness.yaml schema 영구 추가
**Rejected:** "Aggressive migration (모두 새 default + advisory)" (validator W4 silent downshift 문제 그대로), "Opt-in flag (default 는 옛 값)" (B-Layer 명시 적용 원칙 일부 손실), "Migration 안함 (옛 사용자는 영원히 옛 default)" (Side 신규 사용자와 default 분기 누적, 유지보수 부담)
**Source:** Validator follow-up Interview Round 5 Q1

### ADR-015: A7 memory tier preamble scope = fused-workflow only (atomic 단독은 그대로)
**Status:** Accepted (2026-05-17)
**Context:** RESEARCH open question. Memory tier reload 가 fused workflow 안에서 2-3× 발생.
**Decision:** `templates/commands/hm/workflow_command.md.j2` (fused workflow 마스터 템플릿) 의 헤더 직후에 memory load preamble block 삽입. Atomic stage template (`templates/stages/*.md.j2`) 변경 없음 — atomic 단독 호출 시 기존대로 메모리 로드.
**Consequences:** ✅ atomic stage 호환성 100%, ✅ fused workflow 의 token cost 감소 (prompt cache 흡수 외 추가), ⚠️ stage 가 fused 안에서 호출됐는지 모름 — but prompt cache hit 이라 두 번째 load 도 cheap
**Rejected:** "모든 stage 에 idempotent guard" (리팩토링 범위 ↑↑), "A7 deferred" (사용자가 Recommended 선택)
**Source:** Interview #15

## 🏗️ Technical Design

### Current State

- **Atomic stages** (7): research / spec / plan / execute / review / wrapup / verify. `templates/stages/*.md.j2`.
- **Fused workflows** (4): exec-rev / exec-rev-wrap / exec-rev-wrap-ver / res-spec-plan. Stage prompt 들의 concatenation.
- **Skills** (11): `templates/skills/*/SKILL.md.j2` + 해당 Python module.
- **Preset divergence**: 11곳 (interview.py × 4 fields · context_lint.py thresholds · readiness.py weights · template select · stub prose). Stage template 자체에는 0.

### Affected Components

| Phase | 영향 파일 |
|------|----------|
| 1 (C2) | `templates/skills/verify-before-completion/SKILL.md.j2` |
| 2 (baseline) | NEW `scripts/measure_workflow_baseline.py` |
| 3 (A3+A4) | `src/harness_maker/relevance.py`, `src/harness_maker/security_scanner.py` |
| 4 (A5) | NEW `src/harness_maker/cache.py`, `src/harness_maker/crawler/{anthropic_blog,github_releases,arxiv,osv_dev}.py` |
| 5 (A6) | `src/harness_maker/agent_quality.py`, `src/harness_maker/security_scanner.py`, `templates/skills/verify-before-completion/SKILL.md.j2` |
| 6 (A2 drift) | `templates/stages/wrapup.md.j2`, `templates/stages/verify.md.j2`, `templates/stages/review.md.j2` (drift_verdict 출력 형식 명시) |
| 7 (A7 prefix) | `templates/commands/hm/workflow_command.md.j2` |
| 8 (A1 check-suite) | NEW `src/harness_maker/observability/verification_cache.py`, `templates/stages/wrapup.md.j2`, `templates/stages/verify.md.j2` |
| 9 (A8 verifier) | `templates/stages/review.md.j2`, `templates/agents/code-verifier.md.j2` (이미 정의됨, 활성화 마커 제거) |
| 10 (B2 Pass 1 skip) | `templates/stages/review.md.j2` |
| 11 (B1+B3+B6) | `templates/harness-yaml/{Side,Production}.yaml.j2`, `src/harness_maker/interview.py` (`_preset_extras`), `templates/stages/{research,spec,plan}.md.j2` (gate config 참조) |

### Dependencies

- 신규 helper module: `harness_maker.cache` (HTTP cache + TTL + ETag), `harness_maker.observability.verification_cache` (skip-key + marker IO)
- 외부 lib: 없음 (stdlib `hashlib`, `httpx` 기존, `tomllib` 기존). `xdg-base-dirs` 검토 OPEN 但 not adopted in this plan.
- snapshot tests: `tests/snapshot/test_render*.py` 가 Phase 6/7/8/9/10/11 마다 regen 필요 — worktree 밖에서 (`failures.md` `snapshot-regen-inside-worktree` count=4 회피)

### Architecture diagram (data flow for A1/A2/A3/A5/A6)

```
                    [stage prompt]
                          │
                          ▼
            ┌─ existing flow ─┐
            │                  │
   ┌────────┴──────────┐    ┌──┴──────────────────┐
   │ has skip-marker?  │NO  │ has fresh-skip key? │NO
   │ (A1)              │───▶│ (A6)                │───▶ normal LLM/Bash call
   └────────┬──────────┘    └──┬──────────────────┘                 │
        YES │                  │ YES                                │
            ▼                  ▼                              ┌─────┴────┐
        return marker      return cached              has cache_control? (A3/A4)
                                                              │ YES
                                                              ▼
                                                       Anthropic API
                                                       (cache hit → 0.1× cost)


   research-crawler HTTP (A5)
        │
        ▼
   ~/.cache/harness-maker/<source>/<date>.json (TTL per source)
        │ miss
        ▼
   normal httpx call → atomic_write
```

### API changes

`harness.yaml` 새 fields (default 만 추가, 기존 key 변경 없음):

```yaml
interview:
  deep_gate:
    max_rounds: 1   # Prod default 3
    streak_target: 1   # Prod default 2
  main_loop:
    max_rounds: 5   # Prod default null
reviewers:
  max_review_rounds: 2   # Prod default 3 (existing field, default 만 변경)
```

기존 사용자 override 보존: `/hm:make --update` 가 `answers_from_harness_yaml` (CLAUDE.md item 6) 으로 기존 값 재사용.

## 📝 Implementation Plan

### Phase 1 — C2 verify Preset.SIDE 버그픽스

- **Scope**:
  - **In**: `templates/skills/verify-before-completion/SKILL.md.j2:65` (`compute_readiness(Path('.'), Preset.SIDE)` → `_read_preset()` 사용)
  - **Out**: 다른 skill, 다른 phase
- **Exit criterion**: `uv run pytest tests/unit/test_verify_skill.py::test_preset_dynamic -x` PASS (신규 test); 기존 1885 test 통과; mypy --strict + ruff clean. Snapshot regen: SKILL.md.j2 변경 → `tests/snapshot/test_render_verify_skill.py` regen 필요 (worktree 밖).
- **Risk**: low
- **Rollback**: Phase 0 (현재 main) — single file revert.

### Phase 2 — Baseline 측정 인프라 (validator W4+W5 확장)

- **Scope**:
  - **In**: NEW `scripts/measure_workflow_baseline.py` 가 **per-call-site metric** 모두 수집:
    - `pytest_seconds`, `mypy_seconds`, `ruff_seconds` (전체 suite)
    - `wrapup_step2_seconds`, `verify_check2_seconds` (Phase 8 wall-clock delta 측정용)
    - `drift_call_count` per `exec-rev-wrap-ver` (Phase 6 의 "3-4×→1×" 검증용 — **Phase 2 시점은 rendered template 정적 스캔만**, runtime hook 카운터는 Phase 6 가 같이 deliver 후 후속 측정에서 union)
    - `review_pass1_input_tokens`, `review_pass2_input_tokens` per fixture review run (Phase 3/9/10 의 token delta 측정용)
    - `health_seconds`, `crawler_http_call_count` (Phase 4 cache delta 측정용)
    - machine fingerprint (OS, CPU, RAM, python interpreter version) baseline.json 에 기록 → R11 mitigation
  - 출력: `~/.cache/harness-maker/baseline.json` (XDG 따름, ADR-003)
  - **Out**: 본격 optimization code 변경 X (관측 인프라만)
- **Exit criterion**: `uv run python scripts/measure_workflow_baseline.py` 실행 → JSON 출력 검증 (모든 axis 존재); 새 unit test `test_baseline_collects_all_axes` (mock subprocess + mock rendered template, all keys present); baseline.json 이 Phase 3+ 의 PR description 의 delta 비교 base 가 됨; 후속 PR description template (CLAUDE.md item 7 에 정합) 에 `**Delta vs baseline.json**:` 표 포함.
- **Risk**: low — 측정 인프라 작성 cost (W4 가 명시한 +0.5-1일 추가)
- **Rollback**: Phase 1 — 측정 인프라 제거, optimization 영향 0.

### Phase 3 — A3 + A4 prompt cache_control 추가

- **Scope**:
  - **In**: `src/harness_maker/relevance.py` (`score_item` 의 Anthropic call), `src/harness_maker/security_scanner.py` (prompt-injection LLM second pass)
  - **Out**: HTTP cache (A5 는 Phase 4), 다른 LLM call site (이미 `llm_judge.py` 경유로 캐시 됨)
- **Exit criterion**: 신규 unit test `test_relevance_cache_control` + `test_secscan_pi_cache_control` — Anthropic mock 검증 (system block 에 `cache_control` 존재 확인); baseline 대비 N=10 mock items batch 처리 시 input token 추정값 90%+ 절감 (PR description 첨부).
- **Risk**: low
- **Rollback**: Phase 2 — 두 함수 의 system kwarg 만 revert.

### Phase 4 — A5 HTTP cache helper + research-crawler 통합

- **Scope**:
  - **In**:
    - NEW `src/harness_maker/cache.py`: `class HttpCache(base_dir=Path.home() / ".cache" / "harness-maker", ttl=...)` with `get_or_fetch(key, fetcher_callable, ttl)`. `HARNESS_MAKER_CACHE_DIR` env override 우선.
    - `src/harness_maker/crawler/__init__.py` (공통 wrapping)
    - `crawler/anthropic_blog.py` (TTL 24h), `crawler/github_releases.py` (TTL 1h), `crawler/arxiv.py` (TTL 24h), `crawler/osv_dev.py` (TTL 1h)
  - **Out**: relevance.py / secscan.py 의 LLM cache (Phase 3)
- **Exit criterion**: 신규 unit tests `test_http_cache_ttl`, `test_http_cache_env_override`, `test_crawler_cache_hit_zero_http`; `/hm:health` 1차 실행 = miss → HTTP, 2차 실행 = hit → 0 HTTP (verbose 로그 확인); `INTEGRATION=1 uv run pytest tests/integration/test_crawler_cache.py` (선택, INTEGRATION env 시만).
- **Risk**: medium (CVE data freshness — OSV 1h TTL 도 0-day disclosure 시 길 수 있음. `--no-cache` flag 후속 plan 검토)
- **Rollback**: Phase 3 — `cache.py` 삭제, crawler 들 직접 httpx 호출 복원.

### Phase 5 — A6 fresh-skip enforcement (3 sites)

- **Scope**:
  - **In**:
    - `src/harness_maker/agent_quality.py`: `judge_file()` 진입 시 `if tier in {Platinum, Gold}: return cached_score`
    - `src/harness_maker/security_scanner.py`: `scan()` 진입 시 `if _last_scan_fresh(): return cached_findings`. Helper `_last_scan_fresh()` 는 `findings-<latest>.jsonl` mtime 24h + `uv.lock`/`.claude/` mtime 비교.
    - `templates/skills/verify-before-completion/SKILL.md.j2`: bash heredoc 첫줄에 `if session_marker_fresh && git_diff_empty: emit "PASS (cached)" && exit 0`
  - **Out**: 다른 skill (context-linter 는 이미 cheap)
- **Exit criterion**: 각 site 의 신규 test (`test_agent_quality_skip_platinum`, `test_secscan_skip_fresh`, `test_verify_skip_fresh_session`); `--force` flag override 동작 (`uv run python -m harness_maker.security_scanner --force` 가 무조건 재실행); baseline 대비 동일 input 2회 호출 시 2회차 cost ~0 확인 (PR description).
- **Risk**: low
- **Rollback**: Phase 4 — 3개 진입 guard 만 revert.

### Phase 6 — A2 drift gate cascade demote (validator W6 보강: missing/stale verdict → FAIL)

- **Scope**:
  - **In**:
    - `templates/stages/review.md.j2`: Step 2 결과를 review report 의 frontmatter 에 `drift_verdict: {result: clean|scope_violation|scenario_miss, details: [...], task_slug: <slug>, computed_at: ISO}` 명시
    - `templates/stages/wrapup.md.j2`: Step 3 → "read REVIEW frontmatter drift_verdict, **task_slug match 확인**, **존재 + slug 일치 시 advisory**, **부재 또는 slug 불일치 → FAIL with explicit '`/hm:review` 를 먼저 실행하세요' 메시지**" (LLM 호출 없음)
    - `templates/stages/verify.md.j2`: Check 1 → 동일 FAIL-on-missing/stale 패턴 (Check 6 의 worktree cleanliness 와 일관)
  - **Out**: execute.md.j2 Step 4 (cleanliness 체크 — drift 와 무관)
- **Exit criterion**: Snapshot regen 후 rendered `wrapup.md` / `verify.md` 가 LLM drift instruction 미포함; 신규 unit tests:
  - `test_review_emits_drift_verdict` — review.md.j2 의 output schema 검증
  - `test_wrapup_blocks_on_missing_review` — review report 없는 상태에서 wrapup 호출 → FAIL exit code + 명시 메시지
  - `test_verify_blocks_on_stale_review_slug` — REVIEW-other-slug.md 존재하나 본 task_slug 와 불일치 → FAIL
  - `test_wrapup_passes_on_matching_verdict` — verdict clean + slug match → 정상 진행
- **Risk**: medium (template snapshot regen workflow 함정 — `failures.md`: `snapshot-regen-inside-worktree` count=4). Mitigation: regen 명확히 worktree 밖에서, PR description 에 명시.
- **Rollback**: Phase 5 — 3개 template 의 변경 revert.

### Phase 7 — A7 fused-workflow memory preamble

- **Scope**:
  - **In**: `templates/commands/hm/workflow_command.md.j2` 의 stage 진입 직전에 `## Shared Session Context` 블록 (hot/warm/wiki memory + harness.yaml 요약 1회)
  - **Out**: atomic stage template 들 (변경 없음 — atomic 단독 호출 호환성)
- **Exit criterion**: snapshot regen 후 `exec-rev-wrap-ver.md` 가 `## Shared Session Context` 1회만 포함; `research.md` (atomic) 은 기존대로; 신규 unit test `test_workflow_preamble_present` / `test_atomic_no_preamble`.
- **Risk**: low
- **Rollback**: Phase 6 — workflow_command.md.j2 의 preamble block 만 revert.

### Phase 8 — A1 check-suite skip with inverted-env-allowlist invariant (validator C1/W8 보강)

- **Scope**:
  - **In**:
    - NEW `src/harness_maker/observability/verification_cache.py`:
      - `class VerificationCache` — skip-key 계산 + read/write marker
      - ADR-007 의 inverted env policy 적용 (ENV_IGNORE set + 나머지 모두 invariant)
      - project_root_absolute_path_hash 포함 (R13 mitigation)
      - 키 저장 위치: `~/.cache/harness-maker/verify/<key>.json` (ADR-003)
    - `templates/stages/wrapup.md.j2` Step 2: 진입 직전 `verification_cache.is_fresh(key)` 호출, fresh 면 "PASS (cached at <time>)" message + skip
    - `templates/stages/verify.md.j2` Check 2: 동일 패턴
  - **Out**: execute.md.j2 Phase D (per-PLAN-phase exit criterion 은 LLM-driven, invariant 다름); cache GC (Non-Goal — 후속 plan); cache size 제한 (Non-Goal)
- **Exit criterion**: 신규 unit test 8개:
  - `test_verification_key_includes_sha` / `test_verification_key_includes_uv_lock` / `test_verification_key_includes_tool_versions`
  - `test_verification_key_includes_project_root` (R13 — 두 가짜 project_root 가 같은 sha 라도 다른 key)
  - `test_verification_key_invalidates_on_lang_change` (C1 — LANG=C 변경 시 key 다름)
  - `test_verification_key_invalidates_on_tz_change`
  - `test_verification_key_ignores_pwd` (ENV_IGNORE 정상 동작)
  - `test_verification_skip_hit_only_when_all_match`
  - fused workflow 2회차 실행 시 wrapup Step 2 + verify Check 2 wall-clock 60%+ 절감 (Phase 2 baseline 의 `wrapup_step2_seconds` + `verify_check2_seconds` axis 와 비교, PR description 표 첨부)
- **Risk**: medium-high (silent regression — 잘못 skip 시 mypy 가 새 type 에러 못 잡고 통과). Mitigation: inverted env policy (ENV_IGNORE 가 좁아 false-negative 안전 방향); `--force` flag (verify 이미 존재) 가 escape hatch; project_root_hash 로 cross-project 충돌 방지
- **Follow-up debt**: cache GC (`>30일 entry purge on miss`) 별도 plan. 본 plan 의 cache 는 monotonic append.
- **Rollback**: Phase 7 — verification_cache 모듈 및 2개 template 의 skip gate 만 revert.

### Phase 9 — A8 Pass 1.5 code-verifier 활성화

- **Scope**:
  - **In**:
    - `templates/stages/review.md.j2`: Pass 1.5 verifier 호출 활성화 (현재 "documented as deferred" 마커 제거 + Task 호출 활성)
    - `templates/agents/code-verifier.md.j2`: 정의 이미 존재, 검증
  - **Out**: 다른 Pass
- **Exit criterion**: snapshot regen 후 review.md 가 Pass 1.5 verifier Task call 포함; 신규 integration test `test_review_pass_15_active` (mock review run → verifier called between Pass 1 and Pass 2, findings reduced); ablation 결과 (ablation-results-2pass.md 패턴) Pass 2 input token 감소 확인.
- **Risk**: medium (verifier 가 잘못 DROP 시 false-negative, Pass 2 가 final say 라 mitigation 됨)
- **Rollback**: Phase 8 — review.md.j2 의 Pass 1.5 활성 라인 revert.

### Phase 10 — B2 Pass 1 + Pass 1.5 verifier skip when reviewer count == 1 (validator C2 보강)

- **Scope**:
  - **In**: `templates/stages/review.md.j2`:
    - Pass 1 호출 block 을 `{% if (config.reviewers.enabled|length + ad_hoc_count) > 1 %}` 으로 wrapping
    - **Pass 1.5 verifier block (Phase 9 에서 활성화) 도 같은 conditional 로 wrapping** (validator C2 critical: verifier 가 Pass 1 부재 시 빈 artifact 읽고 wasted call 또는 error 발생)
    - 결과: single reviewer 시 Pass 1 + Pass 1.5 둘 다 skip → Pass 2 만 실행
  - **Out**: 다른 stage
- **Exit criterion**: snapshot regen — Side preset rendered review.md 는 Pass 1 block + verifier block 둘 다 미포함, Production multi-reviewer rendered 는 둘 다 포함; 신규 unit tests:
  - `test_review_skips_pass1_when_single_reviewer`
  - `test_review_includes_pass1_when_multi`
  - `test_review_skips_verifier_when_single_reviewer` (C2)
  - `test_review_includes_verifier_when_multi_and_a8_active` (C2)
  - baseline 대비 Side review input token cost 50%+ 감소 (Phase 2 baseline 의 `review_pass1_input_tokens` axis 와 비교, PR description)
- **Risk**: low
- **Rollback**: Phase 9 — review.md.j2 의 두 conditional 만 revert.

### Phase 11 — B3 + B1 + B6 harness.yaml schema + Side defaults + schema_version migration (validator C3 보강)

- **Scope**:
  - **In**:
    - `templates/harness-yaml/{Side,Production}.yaml.j2`: 새 keys (`interview.deep_gate.*`, `interview.main_loop.*`); 또한 `schema_version: 2` 추가 (ADR-016)
    - `src/harness_maker/interview.py` `_preset_extras`: **schema_version 분기**:
      - `schema_version >= 2` AND preset=Side → 새 default `{deep_gate.max_rounds: 1, streak_target: 1, main_loop.max_rounds: 5, reviewers.max_review_rounds: 2}`
      - `schema_version < 2` OR missing AND preset=Side → **옛 default** `{deep_gate.max_rounds: 3, streak_target: 2, main_loop.max_rounds: null, reviewers.max_review_rounds: 3}` + advisory log: "Side default 변경: opt-in 하려면 schema_version: 2 또는 새 fields 명시"
      - Production: `{3, 2, null, 3}` 일관 (변경 없음)
    - `src/harness_maker/models.py`: pydantic schema 확장 + `schema_version: int = 1` (default 1 = 기존 harness 호환)
    - `templates/stages/research.md.j2` Phase 0.5: hardcoded `Max 3 rounds` / `2 consecutive` → `{{ config.interview.deep_gate.max_rounds }}` / `{{ config.interview.deep_gate.streak_target }}`. spec/plan 동일
    - `templates/stages/plan.md.j2` Step 3: `unlimited rounds` → `up to {{ config.interview.main_loop.max_rounds or 'unlimited' }} rounds`
    - `/hm:make --update` 에 advisory: "Side default 변경 감지" (schema_version < 2 + preset=Side 인 경우만)
  - **Out**: 다른 phase, 다른 skill
- **Exit criterion**: 신규 unit test 10개:
  - `test_side_defaults_new_fields_schema_v2`
  - `test_side_defaults_old_fields_schema_v1_or_missing` (C3 — 기존 harness silent downshift 방지)
  - `test_prod_defaults_unchanged_across_schema_versions`
  - `test_interview_py_injects_side_v2`
  - `test_interview_py_preserves_side_v1_old_defaults` (C3)
  - `test_existing_side_harness_no_silent_downshift` (C3 — fixture: 옛 harness.yaml + `/hm:make --update` → 새 fields 가 옛 hardcoded 값으로 렌더)
  - `test_schema_version_field_present_in_models`
  - `test_make_update_emits_advisory_for_v1_side`
  - `test_make_update_preserves_user_override` (CLAUDE.md item 5 fingerprint)
  - `test_stage_template_reads_config_not_hardcoded` (snapshot diff)
  - snapshot regen — Side rendered research.md 는 schema_version 따라 분기, Production 은 일관
- **Risk**: medium-high (schema migration + 사용자 override 보존). Mitigation: 기존 `_preset_extras` 및 `answers_from_harness_yaml` 패턴 재사용; schema_version 가 binary switch 라 dual-write 위험 낮음; advisory message → 사용자가 명시 인지.
- **Rollback**: Phase 10 — 새 fields 제거, stage template 의 hardcoded 값 복구, `_preset_extras` revert, `schema_version` field 제거.

### Phase 12 (closing) — Final wrapup: baseline 비교 sweep

- **Scope**:
  - **In**: `scripts/measure_workflow_baseline.py --compare baseline.json` 실행 → 종합 delta report; `work-docs/CLOSE-workflow-optimization-2026-05.md` 작성 (각 PR 의 delta 합산, 가설 검증)
  - **Out**: 코드 변경 0 (관측 산출물만)
- **Exit criterion**: CLOSE 문서가 ADR-001 의 "estimated impact" 가설 (wall-clock 2-3분 절감, token 60-80% 절감) 검증 또는 반박; `/hm:wrapup` 호출 가능 상태.
- **Risk**: very low
- **Rollback**: Phase 11 — CLOSE 문서 삭제, 코드 영향 0.

## 🧪 Testing Strategy

| Layer | Coverage |
|------|---------|
| **Unit** | 각 Phase 신규 단위 테스트 (15-20 신규 test 예상). LLM 호출은 `mock_anthropic_client` fixture (CLAUDE.md 패턴). HTTP 는 `httpx.MockTransport`. |
| **Snapshot** | Phase 1, 6, 7, 8, 9, 10, 11 모두 snapshot regen 필요 — **worktree 밖에서** (`failures.md` count=4 회피). `tests/snapshot/test_render_*.py` 의 결정성 보장. |
| **Integration** | Phase 4 (HTTP cache): `INTEGRATION=1 pytest` 시 실제 OSV/GitHub/arxiv hit + cache 동작. Phase 11 (harness migration): fixture 기반 `/hm:make --update` 시뮬레이션. |
| **E2E** | Phase 8 (check-suite skip): `tests/e2e/test_plugin_live.py` 의 wrapup→verify 흐름이 2회차 실행 시 skip 발동. |
| **Baseline + delta** | Phase 2 가 baseline.json 생성, 각 PR description 에 delta 표 첨부 (wall-clock seconds · token estimate). Final Phase 12 가 합산. |

## ⚠️ Risks & Mitigation

| ID | Risk | Severity | Phase | Mitigation |
|----|------|----------|-------|-----------|
| R1 | Snapshot regen inside worktree fails (`failures.md` count=4) | high | 1, 6, 7, 8, 9, 10, 11 | 각 PR description 의 PR checklist: "snapshot regen 은 worktree 밖에서 수행됨". CLAUDE.md item 8 (e2e 경계 테스트) 패턴 따름 |
| R2 | A1 skip-key env 정책 미흡 → silent regression | medium-high | 8 | ADR-007 inverted env policy 적용 (ENV_IGNORE set: `PWD/OLDPWD/SHLVL/TERM/SSH_*/WSL_*/CLAUDE_CODE_*` 등 알려진 noise 만 ignore, **나머지 모두 invalidate**); verify --force escape hatch 유지 |
| R3 | A5 OSV cache 가 0-day disclosure 시점에 stale | medium | 4 | OSV TTL 1h (다른 source 24h 보다 짧음); `--no-cache` flag 후속 plan 검토 (본 plan 미포함, 별도 PLAN) |
| R4 | Phase 11 의 schema migration 이 기존 user override 덮어쓰기 | medium-high | 11 | `answers_from_harness_yaml` (CLAUDE.md item 6) 재사용. fingerprint hash 비교 (CLAUDE.md item 5) 로 user-modified 감지. Migration 테스트 fixture 필수. |
| R5 | A8 verifier 가 잘못 DROP → false-negative review | medium | 9 | Pass 2 가 final say (verifier 는 reduce-only, Pass 2 가 verifier 의 DROP 을 무시 가능); ablation 비교 (현재 vs A8) 로 false-negative 검증 |
| R6 | A6 fresh-skip 의 session marker 가 다른 worker 의 PASS 를 잘못 신뢰 | low | 5 | session marker = git sha + diff hash + pid (cross-worker invalidate); `--force` override |
| R7 | A2 drift demote 가 wrapup 전 ad-hoc edit 으로 생긴 drift 미감지 | medium | 6 | wrapup advisory 메시지 유지 ("review 이후 추가 변경 시 /hm:review 재실행 권장"); UI affordance 명확 |
| R8 | A3/A4 prompt cache 5분 TTL → user pause 시 cache miss | low | 3 | batch 호출 안에서 발생 → 일반적으로 hit. user-driven pause 는 첫 호출 cost 흡수 (regression 0) |
| R9 | A7 preamble 의 conversation context 부풀음 | low | 7 | Anthropic prompt cache 가 prefix 흡수 → token cost ≈ 0; wall-clock 영향 없음 |
| R10 | Plan-validator agent 가 11 phase plan 을 MAJOR_REVISION 판정 | medium | (validation) | Step 4 validator 호출, MAJOR_REVISION 시 follow-up round + 1회 재호출 (template 정책) |
| R11 | Wall-clock baseline 측정이 머신 의존 → 다른 머신에서 검증 불가 | low | 2, 12 | token cost 가 primary metric (deterministic); wall-clock 은 secondary; baseline.json 에 머신 fingerprint (OS, CPU, RAM) 기록 |
| R12 | A3/A4 ephemeral cache_control 이 system prompt < 1024 token 시 silent no-op (Anthropic API minimum) | medium | 3 | Phase 3 의 unit test 가 `assert len(system_prompt_estimated_tokens) >= 1024` 명시 (CLAUDE.md/README excerpt + rubric content 합산 추정); 실제 호출 시 cache hit metric 모니터링 |
| R13 | A1 verification_cache key 가 두 프로젝트 (같은 sha/diff) 충돌 | medium | 8 | ADR-007 의 key 에 `project_root_absolute_path_hash` 포함; 신규 test `test_verification_key_includes_project_root` (두 가짜 root, 같은 sha → 다른 key) |
| R14 | Phase 6 의 missing/stale drift_verdict → silent pass | medium-high | 6 | wrapup/verify 가 task_slug match + verdict 존재 검증 후 부재 시 FAIL with explicit message (Round 5 Q3 결정); 신규 tests `test_wrapup_blocks_on_missing_review`, `test_verify_blocks_on_stale_review_slug` |
| R15 | Phase 11 schema migration 이 기존 Side harness 의 silent downshift | medium-high | 11 | ADR-016 schema_version 분기; 옛 schema → 옛 default 유지 + advisory; 신규 test `test_existing_side_harness_no_silent_downshift` (C3) |
| R16 | A1 cache GC 부재 → `~/.cache/harness-maker/verify/*.json` 무한 누적 | low | 8 (follow-up) | Non-Goal — 후속 plan 으로 분리. 본 plan 의 cache 는 monotonic append. 사용자가 `rm -rf ~/.cache/harness-maker/` 가능. baseline.json 도 같은 디렉토리 — wipe 시 baseline 재측정 필요 |

## ✅ Success Criteria

(SPEC 없으므로 ADR-011 기반. 각 항목 `[closed by Phase N]` 또는 `[closed by Phase 12 sweep]` 태그 부착)

- [x] **Quality preservation** [closed by 각 Phase PR + Phase 12 sweep]: Phase 11 완료 후 1885 기존 test + 신규 30+ test (Phase별 5-10) 모두 PASS, ruff clean, mypy --strict clean
- [x] **Token cost delta** [closed by Phase 3 PR]: relevance-filter / secscan Gate 5 batch 호출 시 input token estimate 60%+ 절감 (Phase 2 baseline 의 `review_pass1_input_tokens` 등 axis 와 비교, harness-maker repo 위 측정)
- [x] **Wall-clock delta** [closed by Phase 8 PR]: harness-maker repo 위에서 `exec-rev-wrap-ver` 2회차 (cache hit) 실행 시 wrapup Step 2 + verify Check 2 wall-clock 합산 **60%+ 절감 (absolute)** 또는 절감 가능 floor 의 **90%+ 도달**. Phase 2 baseline 의 머신 fingerprint 와 동일 환경에서 측정. (Validator W5 — fixed-overhead floor 가 absolute % 막으면 명시 fallback)
- [x] **HTTP delta** [closed by Phase 4 PR]: `/hm:health` 2회차 (cache hit) 실행 시 crawler HTTP 호출 0회 (Phase 2 baseline 의 `crawler_http_call_count`)
- [x] **Side preset interview** [closed by Phase 11 PR]: schema_version=2 Side rendered research/spec/plan 의 gate max_rounds 명시값 = 1; schema_version=1 또는 missing Side 는 = 3 (C3 backward compat)
- [x] **Reviewer optimization** [closed by Phase 10 PR]: Side single-reviewer rendered review.md 에 Pass 1 block + Pass 1.5 verifier block 둘 다 부재 (validator C2)
- [x] **Drift unification** [closed by Phase 6 PR]: rendered `exec-rev-wrap-ver` 의 LLM drift 진단 instance 가 1개 (Phase 2 baseline 의 `drift_call_count` axis 비교)
- [x] **Drift safety** [closed by Phase 6 PR]: missing/stale drift_verdict 상태에서 wrapup/verify 호출 → FAIL with explicit message (validator W6)
- [x] **Bug fix** [closed by Phase 1 PR]: Production preset 의 verify Check 3 가 Production baseline 사용 (Phase 1 test)
- [x] **Backward compat** [closed by Phase 11 PR + Phase 12 sweep]: 기존 Production harness 가 `/hm:make --update` 후 동작 변경 없음 (defaults 만 추가); 기존 Side harness 는 schema_version=1 으로 옛 default 유지 (R15 mitigation)
- [x] **Migration safety** [closed by Phase 11 PR]: `/hm:make --update` 가 사용자 override 덮어쓰지 않음 (CLAUDE.md item 5 fingerprint 패턴, ADR-016)
- [x] **CLOSE 문서** [closed by Phase 12 sweep]: 비교 sweep 가 ADR-001 estimated impact (wall-clock 2-3분, token 60-80%) 검증 또는 반박, 머신 fingerprint 명시

## 🔍 Plan Validation

**Round 1 outcome**: `NEEDS_REVISION` (2026-05-17, plan-validator agent). 12 findings: 3 critical + 7 warn + 2 info.

**Resolution table**:

| Finding | Severity | Resolution | Where applied |
|---------|----------|-----------|---------------|
| C1 — Skip-key env whitelist 누락 (LANG/LC_*/TZ/CC/RUSTC...) | critical | A. Revise — ADR-007 inverted env policy (allowlist-out, invalidate-by-default) | ADR-007 (수정) |
| C2 — Phase 10 conditional 이 Pass 1.5 verifier 미포함 | critical | A. Revise — Phase 10 scope 가 Pass 1 + verifier 둘 다 wrap | Phase 10 scope (수정) |
| C3 — Phase 11 schema migration silent downshift | critical | A. Revise — Round 5 Q1: preserve-old-on-upgrade + schema_version (ADR-016 신설) | ADR-016 (신설), Phase 11 scope (수정) |
| W4 — Phase 2 baseline 이 per-call-site axis 누락 | warn | A. Revise — Round 5 Q2: Phase 2 확장 (drift_call_count, wrapup_step2_seconds, review_pass1_input_tokens) | Phase 2 scope (수정) |
| W5 — Success criteria "80% wall-clock" aspirational | warn | A. Revise — 60% absolute OR 90% of floor 명시, 머신 fingerprint pin | Success Criteria (수정) |
| W6 — Phase 6 missing/stale verdict silent pass | warn | A. Revise — Round 5 Q3: FAIL with explicit message | Phase 6 scope (수정), R14 신설 |
| W7 — A1 cache GC 부재 | warn | B. Accept as risk — Non-Goal, R16 + 후속 plan 명시 | Non-Goals 섹션 + R16 |
| W8.1 — A3/A4 1024 token threshold silent no-op | warn | A. Revise — R12 신설 + Phase 3 test 가 길이 assert | R12 신설, Phase 3 (이미 test 명시) |
| W8.2 — A1 cache key cross-project 충돌 | warn | A. Revise — ADR-007 에 project_root_hash 포함, R13 신설 | ADR-007 (수정), R13 신설 |
| W9 — Non-Goals 섹션 부재 | warn | A. Revise — `## 🚫 Non-Goals` 신설 (7개 항목) | Non-Goals 섹션 (신설) |
| W10 — Deferred-question 패턴 (xdg-base-dirs / --no-cache / env whitelist policy) | warn | A. Revise — ADR-003 / Phase 4 / ADR-007 안에서 NO 결정 | ADR-003 / ADR-007 / Non-Goals (수정) |
| I1 — ADR-012/013 Rejected alternatives 부재 | info | A. Revise — 1줄 Rejected 추가 | ADR-012 / ADR-013 (수정) |
| I2 — Success criteria 항목별 closing phase 미명시 | info | A. Revise — `[closed by Phase N]` 태그 부착 | Success Criteria (수정) |

**Re-validation Round 2 outcome**: **APPROVED** (2026-05-17, plan-validator agent). 12 findings 모두 genuinely resolved 로 검증. 2개 non-blocking suggestions 추가 — 둘 다 wording 수정으로 즉시 반영:
- (suggestion) R2 mitigation 의 옛 whitelist-in 문구 → ADR-007 의 inverted (ENV_IGNORE) 정책으로 wording 정정
- (suggestion) Phase 2 의 `drift_call_count` axis: 정적 스캔만 deliver, runtime hook 은 Phase 6 가 같이 deliver — 명시

**Final ADRs (16)**: 1-15 (Round 1-4) + ADR-016 (Round 5, schema migration policy).
