# Phase 1 Manual Checklist — Codex CLI smoke (5-step)

> 이 체크리스트는 PLAN-pre-launch-validation-strategy Phase 6 (L5) 의 산출물. ADR-003 = smoke-only (Cursor MANUAL_CHECKLIST.md 의 full-coverage 수준 아님). harness-maker 가 Codex CLI 에 install / dispatch / render 까지 도달하는 핵심 약속만 검증.

**예상 소요**: 30-60 분 (install 변동성에 따라).

**필요 준비물**:
- Codex CLI (`codex` 바이너리 PATH 에 있음)
- 깨끗한 임시 디렉토리 (`/tmp/codex-dogfood-$(date +%Y%m%d-%H%M)/`)

---

## Step-별 BLOCK vs DEFER threshold (사전 commit, ADR-003 + plan-validator W4)

| Step | Threshold | 이유 |
|---|---|---|
| **1. install** | **BLOCK** — fail = P0, Show HN 차단 | README 에 명시된 install path. fail 시 약속 깨짐 |
| **2. discovery (`/plugins` 노출)** | DEFER acceptable — fail = P2 + README disclaimer | UX detail; ADR-003 = "discovery 가 살짝 어려워도 install 자체는 OK" |
| **3. interactive interview** | DEFER acceptable — fail = P2 + README disclaimer | Cursor 의 manual checklist 수준 fully verified 까지는 아님 (smoke-only) |
| **4. AGENTS.md absorption** | **BLOCK** — fail = P0, Show HN 차단 | README 명시 + block-merge marker 의 핵심 약속 |
| **5. `.codex/*` render** | **BLOCK** — fail = P0, Show HN 차단 | Codex target 의 가장 visible 산출물. hooks.json PascalCase 포함 |

---

## 사전 준비

1. 터미널에서:
   ```bash
   FRESH_DIR="/tmp/codex-dogfood-$(date +%Y%m%d-%H%M)"
   mkdir -p "$FRESH_DIR" && cd "$FRESH_DIR"
   git init . && git commit --allow-empty -m "initial"
   echo "Working in: $FRESH_DIR"
   ```
2. `codex --version` 으로 Codex 버전 기록 (results-*.md 의 환경 섹션에 명시).

---

## Step 1 — Install via Codex plugin marketplace [BLOCK]

```bash
codex plugin marketplace add Ecro/harness-maker
```

**기대 결과**: 명령 exit 0, "marketplace added" 류 메시지.

**Verify**:
- `codex plugin marketplace list` 의 출력에 `Ecro/harness-maker` 노출.

**PASS 조건**: exit 0 + list 에 노출.
**FAIL = P0**. README 의 "Codex: `codex plugin marketplace add Ecro/harness-maker`" 약속 거짓. 즉시 Phase 0 redux (patch + 0.17.2 cut) 또는 README 의 Codex install path 를 제거.

---

## Step 2 — Discovery [DEFER acceptable]

Codex CLI 안에서:

```
/plugins
```

**기대 결과**: harness-maker 가 enabled / available 상태로 보임.

**Verify**:
- 보이지 않으면 `codex` 재시작 후 다시 시도.
- 여전히 안 보이면 DEFER — README 에 "Codex 의 `/plugins` 탐색은 restart 가 필요할 수 있음" 명시 추가.

**PASS 조건**: enabled 상태 노출 (재시작 후라도).
**FAIL = P2 + README disclaimer 추가** (BLOCK 아님 per ADR-003).

---

## Step 3 — Trigger /harness-maker:make [DEFER acceptable]

Codex CLI 안에서:

```
/harness-maker:make
```

**기대 결과**: Interactive interview 시작 (locale 질문이 첫 step).

**Verify**:
- Interview 가 시작하면 PASS.
- AskUserQuestion 류가 작동 안 하면 — Codex 의 question dispatch 방식이 다를 가능성. README disclaimer "Codex 의 interactive flow 는 Cursor / Claude Code 와 다소 다를 수 있음" 으로 처리.

**PASS 조건**: interview 가 첫 질문까지 도달.
**FAIL = P2 + README disclaimer 추가** (BLOCK 아님 per ADR-003).

---

## Step 4 — AGENTS.md absorption + block-merge marker [BLOCK]

Interview 완료 후 (또는 step 3 가 DEFER 면 별도로 `harness-maker make .` CLI 사용):

```bash
# Project root 에 AGENTS.md 생성/업데이트 됐는지
test -f AGENTS.md && echo "AGENTS.md exists ✓" || echo "MISSING — P0"
```

**Verify**:
- `AGENTS.md` 가 project root 에 존재.
- 내용에 block-merge marker (`<!-- @hm:user:* -->` 류) 포함.
- 사용자 추가 영역 (e.g., `<!-- @hm:user:extensions -->` 내부) 명확 분리.

**검증 명령**:
```bash
grep -c "@hm:user:" AGENTS.md  # 1 이상 나와야 함
grep -c "@hm:/user:" AGENTS.md # closing marker 도 동수
```

**PASS 조건**: AGENTS.md 존재 + block-merge marker 양쪽 (open + close) 동수.
**FAIL = P0**. README + Codex target 약속 (`AGENTS.md` rendering + block-merge preservation) 거짓.

---

## Step 5 — `.codex/*` render + hooks.json PascalCase 검증 [BLOCK]

```bash
# 4 파일 모두 존재해야 함
test -f .codex/config.toml && echo "config.toml ✓"
test -f .codex/hooks.json  && echo "hooks.json ✓"
ls .codex/agents/*.toml | head -3
ls .agents/skills/*/SKILL.md | head -3
```

**hooks.json 의 PascalCase 검증** (CLAUDE.md §Plugin 구조 명시 contract):

```bash
# Codex 는 PascalCase + PermissionRequest 이벤트 사용 (Cursor 의 camelCase 와 분리)
jq -r '.hooks | keys[]' .codex/hooks.json
# 기대 출력: PreToolUse, PostToolUse, Stop, PermissionRequest, ...
# (camelCase 인 preToolUse, postToolUse 가 나오면 FAIL — schema 가 Cursor side 로 잘못 갔다는 뜻)
```

**TOML 검증** (config.toml):
```bash
python3 -c "import tomllib; tomllib.load(open('.codex/config.toml', 'rb'))"
# exit 0 이면 valid TOML
```

**PASS 조건**:
- 4 파일 모두 존재.
- `jq` 가 PascalCase key 만 emit (camelCase 없음).
- `tomllib.load` exit 0.

**FAIL = P0**. Codex target 의 핵심 약속 (PascalCase + .codex/* 4 파일 모두 render) 거짓.

---

## Results 기록

위 5 step 의 결과를 `tests/codex-compat/results-YYYY-MM-DD.md` 에 기록. Format:

```markdown
# Codex CLI smoke results — YYYY-MM-DD

**Codex 버전**: <output of `codex --version`>
**Test directory**: `/tmp/codex-dogfood-YYYY-MM-DD-HHMM/`
**harness-maker 버전**: <pip show harness-maker | grep Version>

| Step | Status | Notes |
|---|---|---|
| 1. Install | PASS / FAIL | |
| 2. Discovery | PASS / FAIL / DEFERRED | |
| 3. Interactive interview | PASS / FAIL / DEFERRED | |
| 4. AGENTS.md + block-merge | PASS / FAIL | |
| 5. .codex/* + hooks.json PascalCase | PASS / FAIL | |

**Overall**:
- BLOCK steps (1, 4, 5) 모두 PASS? → Phase 11 (Show HN) Go.
- BLOCK steps 중 하나라도 FAIL? → P0, Phase 0 redux (patch + new tag).
- DEFER steps (2, 3) FAIL? → README disclaimer 추가 commit + 진행.

**Findings**:
- ...
```

---

## Cleanup

```bash
rm -rf /tmp/codex-dogfood-*
codex plugin marketplace remove Ecro/harness-maker  # optional, 다음 검증 위해 깨끗히
```
