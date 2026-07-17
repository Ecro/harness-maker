# PLAN: Content Depth Uplift (harness-maker)

> **Status**: draft (review before autoloop)
> **Created**: 2026-05-03
> **Slug**: content-depth-uplift
> **Goal**: neuroTerm 비교에서 드러난 콘텐츠 깊이·enforcement 격차를, harness-maker 의 메타-제너레이터 정체성을 회귀시키지 않으면서 메운다.

---

## 0. 배경 한 줄

neuroTerm = 1년 운영하며 손으로 채운 prompt 자산. harness-maker = 그걸 자동 합성·갱신하는 골조. 비교 결과 enforcement(0개) + reviewer agent prompt(텅 빔) + locale 정책 + dev_mode 축이 격차의 본진. 콘텐츠를 stage 에 박는 건 neuroTerm 회귀 — agent partial 에 박고, 도메인 표준은 user 가 author 한다.

---

## 1. Locked 결정

### 1.1 Architecture
- **Hook 배달**: `python -m harness_maker.gates.<gate>` — user 프로젝트가 harness-maker 를 dev dep 로 설치. CLAUDE.md 의 hook 정책과 일치.
- **도메인 모델**: **Model C** — user-authored 팩 + 우리가 sample 1개 (`python.md`). 콘텐츠 유지 책임은 user.
- **Anti-rot**: `/hm:refresh` 가 sample 도메인 팩 + reviewer partial 둘 다 frontmatter 의 `last_reviewed_at` 기준 stale 검출.
- **preset × dev_mode = 4 cross 다 허용** (Side+spec, Side+task, Production+spec, Production+task).

### 1.2 harness.yaml 새 키
```yaml
locale: en              # default; interview 첫 질문, free-text
dev_mode: spec-driven   # spec-driven | task-driven
project:
  domains: []           # ["python", "tauri", ...] — _standards/<x>.md auto include
spec:
  dir: specs/
reviewers:
  verbosity: standard   # terse | standard | full
```

### 1.3 Locale UX
- Interview **첫 질문**. preset 도 dev_mode 도 그 다음.
- Free-text. AskUserQuestion preview 에 `en (built-in)`, `ko (built-in)` 제시. 다른 값 (예: `ja`) 도 수용.
- harness-maker 가 i18n 메시지 없는 locale 이면 en 으로 silent fallback.

### 1.4 dev_mode 의미
- `spec-driven`: SPEC + test 강제. spec-gate hook 설치. verify 게이트가 SPEC 충족 검사.
- `task-driven`: SPEC 강제 X. spec-gate hook **미설치** (배달 자체 안 함). verify 는 회귀 + health 만.

### 1.5 spec-gate 심각도 (spec-driven 일 때만)
- preset = Side → `warn` / preset = Production → `block`.
- harness.yaml `security.gates.spec_gate: warn|block` 키로 노출, 위 기본값.

---

## 2. Phases (autoloop 순차)

> 모든 phase 의 commit message: `autoloop(harness-maker): phase N - <name>` (CLAUDE.md 규약).
> 모든 phase 가 verify-before-completion 6 체크 통과 후 다음으로 이동.

### Phase 0 — Interview 재구성 (locale-first + dev_mode 축)

**Files**
- `src/harness_maker/interview.py` — locale 첫 질문 추가, dev_mode 질문 추가.
- `src/harness_maker/models.py` — `InterviewAnswers`, `HarnessConfig` 에 `locale: str`, `dev_mode: Literal["spec-driven","task-driven"]` 추가.
- `src/harness_maker/i18n.py`, `i18n_messages.py` — en 을 baseline 으로, ko 를 overlay 로 재정렬. unknown locale → en silent fallback.
- `templates/harness-yaml/{Production,Side}.yaml.j2` — `locale`, `dev_mode` 키 추가.
- `tests/unit/test_interview.py` — locale 첫 질문 / dev_mode 질문 / 4 cross 조합 / unknown locale fallback.

**Acceptance**
- Interview 순서: **locale → preset → dev_mode → workflow → consensus → caching**.
- harness.yaml 에 `locale`, `dev_mode` 두 키 모두 출력.
- `tests/unit/test_interview.py` green.

---

### Phase 1 — spec-gate Python hook

**Files**
- `src/harness_maker/gates/__init__.py` (신설)
- `src/harness_maker/gates/spec_gate.py` (신설) — Claude Code PreToolUse 입력을 stdin 으로 받아 JSON 응답.
- `tests/unit/test_spec_gate.py` — test path 검출 / SPEC 매칭 / warn vs block / Korean+English 메시지.
- `templates/hooks/hooks.json.j2` — `{% if dev_mode == 'spec-driven' %}` 가드로 PreToolUse 에 spec-gate 등록.

**Acceptance**
- `Write`/`Edit` tool 이 `tests/**/*test*.py` 또는 `**/*_test.py` 경로면, `{spec.dir}/SPEC-*.md` 의 frontmatter 또는 본문에 해당 test path 가 참조되는지 확인.
  - 매칭 → allow.
  - 미매칭 + Side → warn (allow + log).
  - 미매칭 + Production → block.
- `dev_mode == "task-driven"` 일 때 hooks.json 에 등록 안 됨.
- WSL2 호환 (`shell=True` 금지, jq 의존 0).
- 메시지 locale 따름 (en/ko 둘 다 fixture).

---

### Phase 2 — permission_gate Python hook

**Files**
- `src/harness_maker/gates/permission_gate.py` (신설) — `Bash` tool input 의 command 를 검사.
- `tests/unit/test_permission_gate.py`
- `templates/hooks/hooks.json.j2` — PreToolUse 에 permission-gate 등록 (모든 dev_mode).
- `src/harness_maker/security_scanner.py` 의 위험 패턴 룰을 import 해서 재사용 (DRY).

**Acceptance**
- `curl * | sh`, `wget * | bash`, `eval $(*)`, `rm -rf /*` 패턴 → block + 한국어/영어 메시지.
- 모든 preset/dev_mode 조합에서 설치.
- 룰 추가는 `security_scanner` 한 곳만 고치면 됨 (테스트로 일관성 검증).

---

### Phase 3 — Reviewer agent partials

**Files (모두 신설)**
- `templates/agents/_partials/rubric.md.j2` — P0/P1/P2/P3 severity. verbosity 별 (terse=P0/P1만, standard=P0~P2, full=P0~P3+rationale).
- `templates/agents/_partials/reasoning.md.j2` — Observe→Trace→Infer→Conclude. terse 시 omit.
- `templates/agents/_partials/hard_rules.md.j2` — no fabrication / evidence with file:line / no rubber-stamp / fixes-not-just-descriptions.
- `templates/agents/_partials/finding_schema.md.j2` — 정확 JSON shape + 1 worked example.

**Files (수정)**
- `templates/agents/code-reviewer.md.j2`
- `templates/agents/security-reviewer.md.j2`
- `templates/agents/performance-reviewer.md.j2`
- `templates/agents/concurrency-reviewer.md.j2`
- `templates/agents/ux-reviewer.md.j2`
- 5개 모두 `{% include "agents/_partials/rubric.md.j2" %}` 등 4종 partial 끌어다 씀.

**Acceptance**
- 5개 reviewer × 3 verbosity = 15 snapshot fixture 결정적 byte 일치.
- verbosity=terse 시 reasoning partial 제외, finding_schema 압축 (rationale 필드 빠짐).
- 각 reviewer agent 본문 ≤ 80줄 (partial include 후 합성 시 100~150줄, Side context-lint 통과).

---

### Phase 4 — 도메인 메커니즘 + sample python 팩 + --add-domain 플래그

**Files (신설)**
- `templates/agents/_standards/_template.md.j2` — skeleton:
  ```yaml
  ---
  name: {domain}
  source: ""
  fetched_at: ""
  last_reviewed_at: ""
  ---
  # {domain} standards
  > 이 파일은 user 가 채운다. /hm:refresh 가 last_reviewed_at 기준 stale 알림.
  ```
- `templates/agents/_standards/python.md.j2` — useful sample (50줄 내외):
  - atomic_write 강제 (CLAUDE.md "구현 패턴" 그대로).
  - `subprocess.run(..., timeout=N, check=True)` 필수 / `shell=True` 금지.
  - ruff format + ruff check + mypy --strict.
  - docstring: WHY only.
  - frontmatter `last_reviewed_at: 2026-05-03`.

**Files (수정)**
- `src/harness_maker/cli.py` — `/harness-maker:make` 가 `--add-domain=<name>` 플래그 받음. 동작:
  1. `templates/agents/_standards/_template.md.j2` 를 `{harness_dir}/.claude/agents/_standards/<name>.md` 로 렌더 (frontmatter 만 채움, body 는 placeholder).
  2. `harness.yaml project.domains` 에 `<name>` 추가 (atomic_write).
- `templates/agents/{code,security,performance,concurrency,ux}-reviewer.md.j2` 에 슬롯:
  ```jinja
  {% for d in domains %}
  {% include "agents/_standards/" + d + ".md.j2" ignore missing %}
  {% endfor %}
  ```
  (sample 만 templates/ 에, user 가 추가한 팩은 `.claude/agents/_standards/` 에서 별도 loader.)

**Files (수정 — render.py)**
- `src/harness_maker/render.py` — `_make_env()` 의 FileSystemLoader 가 user `.claude/agents/_standards/` 도 search path 로 추가.

**Acceptance**
- `harness.yaml project.domains: [python]` 일 때 5개 reviewer 모두 python.md 표준 본문 include.
- `/harness-maker:make --add-domain=tauri` 호출 시:
  - `.claude/agents/_standards/tauri.md` 생성 (frontmatter 채워짐, body 는 placeholder).
  - `harness.yaml project.domains` 에 `tauri` 추가.
- snapshot fixture: domains=[]/[python] 두 가지.

---

### Phase 5 — /hm:refresh 확장 (anti-rot)

**Files (수정)**
- `templates/commands/hm/refresh.md.j2` — 갱신 대상에 `_partials/*.j2` + `agents/_standards/*.md` 추가. stale 기준: `last_reviewed_at` 가 90일 이전.
- `src/harness_maker/relevance.py` — `detect_stale_assets(now: datetime, threshold_days: int) -> list[Path]` 추가.
- `templates/agents/_partials/*.j2` 4개 frontmatter 에 `last_reviewed_at` 추가.

**Files (신설)**
- `tests/unit/test_relevance_stale.py`

**Acceptance**
- `/hm:refresh` 실행 시 stale partial / domain pack 발견 → AskUserQuestion 으로 갱신 제안 (accept / reject / defer).
- accept 시 `last_reviewed_at` 만 새 timestamp 로 갱신 (body 는 user 책임).
- autoloop 모드에서는 step 3 (proposed-<date>.md 작성) 까지만 진행.

---

## 3. Done 기준

verify-before-completion 6 체크에 추가로:
- **snapshot test 전부 green** (freeze_time fixture 아래 결정적 byte 일치).
- 4 cross 조합 (Side+spec, Side+task, Production+spec, Production+task) 모두 render 성공.
- spec-gate 가 task-driven 일 때 hooks.json 에 등록 **안 되는** 걸 fixture 로 입증.
- locale=ja (= unknown) 일 때 en silent fallback 동작.

---

## 4. 위험 / 미결

| 위험 | 영향 | 대응 |
|---|---|---|
| Python 외 toolchain 프로젝트 (Rust/Node only) 에서 hook 작동 안 함 | hook 배달 model A 의 비용 | README 에 "harness-maker 는 user 프로젝트에 Python+uv 가 있어야 함" 명시. 향후 self-contained binary 검토. |
| dev_mode 축 추가로 기존 snapshot fixture 4개 → 8개 재생성 | 기존 테스트 깨짐 | Phase 0 에서 fixture 일괄 갱신. CI 도 8개 matrix. |
| `_partials/` 의 last_reviewed_at 갱신을 user 가 안 누르면 stale 누적 | anti-rot 효과성 | `/hm:refresh` 가 stale 90일 + 누적 카운트 표시. 180일 넘으면 강한 경고. |
| Sample python 팩이 너무 opinionated → user 거부감 | dogfood 가치 손실 | "이 sample 은 harness-maker 자체가 쓰는 규칙. 자기 프로젝트에 맞게 자유롭게 수정." 헤더 주석 강제. |

---

## 5. 다음 단계

1. **Plan 검토** (user 가 본 문서 읽고 의견).
2. 의견 반영 (필요 시 본 문서 수정).
3. **autoloop 시작 명령 제안** — 예시:
   ```
   /harness-maker:autoloop --plan work-docs/plans/PLAN-content-depth-uplift.md
   ```
   각 phase 가 자체 SPEC + tests + snapshot 으로 마감하고 commit. 5번 phase 끝나면 verify-before-completion 통과 시 plan 종료.

---

## 6. 부록 — 본 plan 이 *하지 않는* 것

- **stage fragment 비대화** — neuroTerm /review.md 712줄 같은 모놀리식 stage 안 만듦. 깊이는 agent partial 에.
- **22 reviewer 직접 운영** — 5 reviewer × 4 partial × N 도메인 슬롯의 합성으로 동급 깊이 달성.
- **commands/ 디렉토리 추가** — 새 사용자 명령 0개. `--add-domain` 은 기존 `/harness-maker:make` 의 플래그.
- **Bash hook 도입** — Python only 정책 유지.
