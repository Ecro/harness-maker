---
type: research
task_slug: personalization-depth-2026-05
status: complete
created: 2026-05-16
tags: [harness-maker, research, personalization, project-fit, profiling, adaptive-config, cross-project, migration]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://docs.cursor.com/context/rules
  - https://docs.continue.dev/customize/config
  - https://aider.chat/docs/config/aider_conf.html
  - https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot
  - https://www.builder.io/blog/cursor-rules
  - https://arxiv.org/abs/2602.20478
  - https://arxiv.org/abs/2601.21557
  - https://arxiv.org/abs/2603.09619
  - https://github.com/anthropics/claude-code/issues/41930
related_docs:
  - "[[RESEARCH-harness-gap-cot-2026-05]]"
  - "[[RESEARCH-harness-trends-2026-05]]"
  - "[[RESEARCH-user-workflow-opportunities-2026-05]]"
  - "[[PLAN-user-workflow-opportunities-2026-05]]"
  - "[[RESEARCH-make-ux-gaps-2026-05]]"
  - "[[RESEARCH-onboarding-ux-2026-05]]"
summary: "Detection→Recommendation pipeline depth + adaptive self-tuning > new axes. Personalization rubric next."
---

# Research: Per-Project Personalization Depth — what's missing, what's next

> 본 research 는 사용자의 "프로젝트마다 딱 맞는 하네스" 강화 의도에 대한 **메타-레벨 갭 분석**. 이미 존재하는 [[RESEARCH-harness-gap-cot-2026-05]] (vs 경쟁 하네스), [[RESEARCH-harness-trends-2026-05]] (arxiv 트렌드), [[RESEARCH-user-workflow-opportunities-2026-05]] (외부 컨텍스트 connector) 와 **중복하지 않음**. 그 세 문서가 다루지 않은 한 가지 축 — **"이 프로젝트에 얼마나 fit 한가"라는 personalization 자체의 depth** — 만 다룬다. `/hm:plan personalization-depth-2026-05` 가 Step 2 에서 frontmatter `research_doc:` 로 직접 read.

---

## 🎯 Recommended Direction

**"새 축 추가" 가 아니라 "기존 축의 Detect → Recommend → Confirm → Generate 파이프라인 깊이를 늘리는 것" 이 먼저.** 그 다음 단계가 **adaptive self-tuning** (하네스가 자기 사용 흐름을 관찰해 축을 재제안). 새 축 (team/privacy/code-style 등) 은 그 다음.

이유: 현재 `ProjectProfile` 은 5개 manifest 만 보고 stack 을 추론하고 (`profile.py:28-34`), 그 추론이 인터뷰의 *문구* 에는 노출되지만 (`"Detected: stack=..."`) **권장 reviewer / MCP / mechanical_checks / 모델 / 워크플로우** 로는 연결되지 않는다. 다시 말해 우리가 **알고 있는 정보** 와 **권유로 변환되는 정보** 사이에 큰 갭이 있다. 새 축을 더해도 같은 갭이 반복된다.

3-track 권장 순서:

1. **Track A — Detection Depth** (4-6 phase, low risk, immediate ROI): `ProjectProfile` 을 깊이 확장하고 그 신호를 인터뷰의 모든 후속 질문 default 로 흘려보낸다. 외부 AI config (Cursor rules / Continue / Aider / CLAUDE.md / AGENTS.md) 가 이미 있으면 import-suggest.
2. **Track B — Adaptive Personalization** (medium risk, 큰 lever): 하네스가 자기 사용을 관찰 — 어떤 reviewer 가 항상 PASS 하나, 어떤 permission 이 매번 prompt 되나, 사용자가 어떤 axis 를 자주 override 하나 → `/hm:personalization-audit` 명령으로 권유. annual review 형식.
3. **Track C — New Axes** (defer): team profile, privacy/regulated, code style, cross-project preferences, secret-tier. 각각 단독으로는 Tier B 보다 ROI 낮다 — Track A/B 의 인프라가 있어야 의미.

**Anti-pattern 회피**: persona/agent 양적 확장 (BMAD 21 role / wshobson 83 specialist 추격) 은 [[RESEARCH-harness-gap-cot-2026-05]] Approach C 에서 이미 defer. domain content 는 user author 원칙 ([[feedback_domain_content_ownership]]) 유지. 우리가 늘리는 것은 **detection + recommendation + adaptive loop**, content 가 아님.

이 권고는 *informational* — `/hm:plan` 인터뷰가 lock-in.

---

## 🔍 Refinement Decisions

- **Discovery lens** (Phase 0.75): User-workflow / product opportunity (primary) + Technical architecture / implementation (secondary). Academic/arXiv 은 [[RESEARCH-harness-trends-2026-05]] 가 이미 광범위 (15+ papers); 본 doc 은 외부 paper 보충 최소화.
- **중복 회피 결정**: 3개 선행 research 가 다룬 영역은 §Out-of-Scope 로 명시 후 *건드리지 않음*. 추가 가치 = "personalization 의 depth 자체" 메타 분석.
- **--deep 미사용**: 사용자 의도가 충분히 명확 ("프로젝트마다 딱 맞는 하네스 강화") → Phase 0/0.5 skip.

### Out of Scope (이미 다른 research 가 담당)

| 영역 | 담당 research | 본 doc 에서 다루지 않는 이유 |
|------|---------------|----------------------------|
| Reliability Stack (drift score / hallucination gate / episodic memory) | harness-gap-cot-2026-05 | 7개 Primary 이미 정의됨 — 본 doc 의 Track B (adaptive) 와 인프라 일부 공유하나 메타-축이 다름 |
| Harness synthesis / longitudinal CI eval | harness-trends-2026-05 | meta-harness 자동 진화는 personalization-depth 의 *최상위 형태* 이나 별도 트랙 — Track B 가 그 전단계 |
| External context connectors (Issue intake / Evidence loop) | user-workflow-opportunities-2026-05 | Second Brain 완료, 나머지 2개 별도 plan 으로 진행 중 |
| Onboarding UX flow | onboarding-ux-2026-05 | 인터뷰 전체 흐름은 별도 |
| Make UX gaps (CLI commands, lifecycle) | make-ux-gaps-2026-05 | 명령 표면은 별도 |

본 doc 의 *unique contribution* = 위 5개 트랙이 모두 가정하는 "프로젝트 신호" 의 **detection / recommendation / adaptation depth** 그 자체.

---

## 🧠 Chain-of-Thought 분석

### Step 1 — 현재 personalization axis 인벤토리

`HarnessConfig` 가 정의하는 축 (models.py:322-397):

| 축 | 현재 표현력 | 사용자 입력 방식 | 자동 detection 연결 |
|----|-----------|----------------|--------------------|
| `locale` | en/ko + 자유 텍스트 | 인터뷰 첫 질문 | 없음 |
| `targets` | claude-code / cursor / codex multi-select | 명시 multi-select | 명시 거부 (memory: [[project_targets_axis]]) |
| `recommended_model` | 자유 텍스트 (default claude-opus-4-7) | 인터뷰 default + 자유 입력 | 없음 |
| `preset` | Side / Production | 인터뷰 + recommendation | profile.scale/lifecycle → `_recommend_preset` (interview.py:271) ✅ |
| `dev_mode` | spec-driven / task-driven | 인터뷰 + recommendation | preset 기반 (`_recommend_dev_mode`) — *transitive* |
| `workflows` (fused) | dict[name, list[stage]] | 인터뷰 starter or 커스텀 | preset 기반 starter — *transitive* |
| `mechanical_checks` | list[str] (shell cmd) | **수동 yaml 편집** | profile.detected_checks ✅ (그러나 인터뷰에서 안 묻고 흘리기만) |
| `wrapup_docs` | list[str] (paths) | CLI flag / interview | 없음 (CHANGELOG.md / TODO.md 존재 여부 미감지) |
| `ref_folders` | list[RefFolder] | 인터뷰 | 없음 (sibling docs/, design-docs/ 미감지) |
| `sibling_repos` | list[str] | 인터뷰 | 없음 (monorepo / workspace 미감지) |
| `second_brain` | typed config | 인터뷰 + 수동 | profile.vault_member ✅ (그러나 vault_path 추천은 없음) |
| `mcp_servers` | dict[name, cmd] | **수동 yaml 편집만** | 없음 — 가장 큰 갭 |
| `domains` (project.domains) | list[str] (user-authored agent names) | `/harness-maker make --add-domain` | 없음 |
| `reviewers` (installed/enabled) | dict[list, list] | 인터뷰 | preset 기반 default — *transitive* |
| `skills` (installed/enabled) | dict[list, list] | 인터뷰 | preset 기반 default — *transitive* |
| `consensus` / `auto_fix` / `grade_threshold` / `max_review_rounds` | single/cross-check/k-of-n + bool + A/B/C + int | 인터뷰 | 없음 |
| `caching` / `hooks` / `memory` / `autoloop` / `anti_rot` / `dashboard` / `models` / `worktree` / `security` / `context_lint` | dict[str, Any] | 인터뷰 + 수동 | 없음 |

**관찰**: ✅ 표시한 4개 (`preset`, `mechanical_checks`, `second_brain`, `dev_mode-transitive`) 만 자동 detection 이 인터뷰에 흐른다. **나머지 17개 축은 detection 신호 없이 default 또는 사용자 자유 입력**.

### Step 2 — detection 깊이 진단

`profile.py:28-34` STACK_MANIFESTS:

```python
STACK_MANIFESTS = {
    "python": ["pyproject.toml", "requirements.txt", "setup.py"],
    "node": ["package.json"],
    "rust": ["Cargo.toml"],
    "cmake": ["CMakeLists.txt"],
    "go": ["go.mod"],
}
```

**결손 stack** (그러나 사용자가 실제로 가질 수 있는 것):
- java/kotlin (`pom.xml`, `build.gradle`, `build.gradle.kts`)
- swift (`Package.swift`, `*.xcodeproj`)
- dart/flutter (`pubspec.yaml`)
- ruby (`Gemfile`)
- php (`composer.json`)
- c# / dotnet (`*.csproj`, `*.sln`)
- c/cpp (헤더만 — manifest 없음; 별도 휴리스틱 필요)
- elixir (`mix.exs`)
- zig (`build.zig`)
- haskell (`*.cabal`, `stack.yaml`)
- scala (`build.sbt`)
- 다중-stack monorepo (`pnpm-workspace.yaml`, `turbo.json`, `nx.json`, `lerna.json`)

**결손 framework-level detection** (같은 stack 안에서도 다른 페르소나 필요):
- Python: Django / FastAPI / Flask / Streamlit / Jupyter / Zephyr (firmware)
- Node: React / Vue / Svelte / Next.js / Remix / Astro / Express / NestJS / Fastify
- Rust: Tauri / Axum / Tokio / bevy / embedded
- Mobile: react-native / flutter / native iOS / native android

**결손 비-stack 신호**:
- 패키지 매니저 (npm/pnpm/yarn/bun, pip/uv/poetry/pipenv) — wrapup 의 install 명령에 영향
- CI provider (GitHub Actions / GitLab CI / CircleCI / Jenkins) — wrapup status check 의 위치
- 커밋 메시지 컨벤션 (`git log` 최근 50건 분석 — conventional commits / gitmoji / 자유) — wrapup commit message 형식
- 기존 docstring 컨벤션 (Python 모듈 import + AST 으로 NumPy / Google / Sphinx 식별)
- 기존 AI assistant config 존재 (`.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`, `.github/copilot-instructions.md`) — **현재 우리가 만들면 충돌 / 사용자 작업 손실 위험**
- README/CONTRIBUTING 첫 50 줄 LLM 요약 — 프로젝트 의도 / 컨벤션 추론
- LICENSE / SECURITY.md / CODE_OF_CONDUCT.md 존재 → open source signal
- `.devcontainer/` 존재 → 컨테이너-first workflow
- `.gitignore` 패턴 → 어떤 데이터가 민감한지

### Step 3 — recommendation 깊이 진단

`_recommend_preset` (interview.py:271-275):

```python
def _recommend_preset(profile: ProjectProfile) -> Preset:
    if profile.scale == "small" and profile.lifecycle in {"experiment", "maintenance"}:
        return Preset.SIDE
    return Preset.PRODUCTION
```

→ 단 한 줄 휴리스틱. detection 이 늘어도 이 함수가 안 늘면 의미 없다. **17개 축 각각에 recommend\_<axis>(profile) 같은 일관된 인터페이스 필요**.

`_recommend_dev_mode(preset)` 는 preset 만 보고 결정 — 다시 transitive. 결과적으로 사용자가 보는 dev_mode 권유는 *프로젝트 자체* 가 아니라 *우리가 preset 으로 단순화한 것* 의 함수.

### Step 4 — 외부 비교: 동급 도구의 personalization 깊이

| 도구 | 프로젝트 신호 detection | 권유 메커니즘 | adaptive 학습 |
|------|----------------------|-------------|---------------|
| Cursor `rules/` `.mdc` | 없음 (full manual) | rule 매칭 | 없음 |
| Continue.dev `config.json` | 없음 (full manual) | 없음 | 없음 (user manually edits) |
| Aider `.aider.conf.yml` | git tree 읽기 | 모델/언어 자동 fallback | 없음 |
| GitHub Copilot custom instructions | `.github/copilot-instructions.md` 단일 파일 | repo-level 만 | 없음 |
| spec-kit | `/speckit.constitution` 사용자 작성 | 없음 | 없음 |
| BMAD-METHOD | 페르소나 사용자 선택 | 없음 | 없음 |
| agent-os | `standards/` 사용자 작성 | 없음 | 없음 |
| claude-flow (ruflo) | 없음 | 54 agents 자동 routing | 없음 |
| **harness-maker (현재)** | **5 manifest + scale + lifecycle + checks + vault** | **preset + dev_mode + check list** | **없음** |
| **harness-maker (목표)** | **stack + framework + pkg + CI + commit-style + foreign-AI-config + README LLM 요약** | **17 축 모두에 recommend_x(profile)** | **`/hm:personalization-audit` annual review + 자동 axis 재제안** |

**시사점**: 현재 우리는 동급 도구 대비 *이미 detection 이 가장 깊다* (5개 영역). 그러나 그 신호가 **권유** 로 변환되는 비율이 25% 미만 (4/21 축). 갭 메우면 동급 대비 격차 크게 벌어진다.

### Step 5 — adaptive layer 예측

다음 12-18개월의 prediction (low confidence, but directionally important):

1. **Per-project AI config 자체가 *유저 자산* 으로 인식되기 시작.** Cursor rules 가 dotfiles 처럼 공유되고, GitHub `awesome-cursorrules` repo 가 활성. → 우리도 *exportable harness preset* (사용자 A 의 `harness.yaml` 을 사용자 B 가 `--from-preset URL` 로 import).
2. **Telemetry-driven self-tune** 이 differentiator 가 됨. SWE-PRM (2509.02360) / AgentTrace (2602.10133) / Agentic Harness Engineering (2604.25850) 가 *agent 가 자기 trajectory 를 관찰* 하는 패턴을 보임 — harness 도 같은 길.
3. **Foreign AI config migration** 이 onboarding 의 default. 이미 `.cursor/rules/` 가 있으면 *덮어쓰지 말고 import-suggest*. 현재 우리 reconcile.py 는 *우리 출력물* 의 KEEP/REPLACE 만 보고, 외부 AI 도구의 파일은 *touch 안 함* — 그런데 사용자는 "Cursor rules 도 harness 가 알아서 통합해줘" 를 기대하기 시작.
4. **Personalization rubric** 등장. ai-readiness rubric 처럼 "이 하네스는 프로젝트에 X% 맞춰져 있다" 점수. Bronze (default-heavy) / Silver (preset+detect) / Gold (recommend 70%+) / Platinum (adaptive loop on).
5. **Cross-project preference inheritance**. 사용자가 5개 프로젝트에 모두 `consensus=cross-check, auto_fix=false` 를 쓴다면, 6번째 프로젝트의 default 가 자동으로 그 값 — **per-user defaults file** (`~/.harness-maker/user-defaults.yaml`).
6. **Regulated/privacy axis** 가 enterprise adoption 의 entry barrier. HIPAA/PCI/GDPR 프로젝트는 *LLM 에 못 보내는 파일* 글로벌 deny 필요 — `.gitignore` 와 다른 차원.
7. **Per-developer override in shared harness**. 같은 repo 의 5명 개발자가 각자 `~/.claude/<repo-id>/overlay.yaml` 로 자기 preference 만 다르게 — git 공유 베이스 + per-user overlay 패턴. (Cursor `User Rules` vs `Project Rules` 가 비슷한 분리.)

---

## 🛠️ Approaches Found

### Track A — Detection Depth (PRIMARY, 우선 권장)

| 필드 | 내용 |
|------|------|
| Approach | `ProjectProfile` 확장 (stack 12+ / framework / pkg-mgr / CI / commit-style / foreign-AI-config / README LLM 요약) + `recommend_<axis>(profile)` 일관 인터페이스 17개 |
| Assumption | **이미 알고 있는 신호를 권유로 변환하지 못하면 새 신호를 추가해도 같은 갭 반복.** 현재 detection→recommend 변환률 ~25% 가 핵심 병목 |
| Evidence | 본 doc Step 1 인벤토리 (21축 중 4축만 transitive 권유); profile.py:28-34 STACK_MANIFESTS 5개 한정; interview.py:271-275 단일-규칙 _recommend_preset; [[RESEARCH-make-ux-gaps-2026-05]] 의 `vault_member` 패턴이 detection→권유 변환 정상 작동 사례 |
| Trade-off | profile.py 깊이 ×3-4 (단일 stack → framework / pkg / CI / commit-style / foreign-AI / LLM-summary). LLM 호출 1-2회 (README 요약, foreign-AI-config 의도 추론) 추가 — `/hm:configure` 첫 실행 latency 5-10초 추가. False positive (e.g. `requirements.txt` 만 있고 실제로는 java 프로젝트) 시 사용자가 reject 한 번 누르면 끝 — recoverable |
| Compatibility | 매우 높음. 기존 `profile()` 함수 시그니처 유지 + 필드 추가. 인터뷰는 default value 만 바꿈. backward compatible. answers_from_harness_yaml 호환 |
| Risk | low |

**구체 sub-track** (priority 순):

A1. **Stack/framework granularity**: STACK_MANIFESTS 확장 (12+ stack) + framework 식별 (package.json scripts/deps / pyproject 의 fastapi/django dep / Cargo.toml workspace 등). Output: `ProjectProfile.frameworks: list[str]`.

A2. **Foreign AI config import-suggest**: `.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`, `.github/copilot-instructions.md` 감지 → 인터뷰에서 "기존 X 가 있습니다. import-suggest? [Y/n]" → LLM 이 외부 config 읽고 우리 harness.yaml 의 어떤 axis 와 매핑되는지 추론 + 사용자 confirm. **이 한 기능이 onboarding-ux-2026-05 의 brownfield 시나리오 전부 커버 가능**.

A3. **Commit-style detection**: `git log --pretty=format:%s -n 50` → conventional commits / gitmoji / 자유. wrapup 의 commit message 템플릿 default 가 바뀜.

A4. **Package manager + CI provider**: `pnpm-lock.yaml` vs `package-lock.json` vs `bun.lockb`; `.github/workflows/` vs `.gitlab-ci.yml` 등. mechanical_checks 와 wrapup 의 status check 위치에 영향.

A5. **README LLM summary**: `README.md` + `CONTRIBUTING.md` 첫 80줄 → LLM 한 줄 요약 → `harness.yaml.summary` 필드 default. 트래젝토리 드리프트 baseline (harness-gap-cot Open Q #4) 으로도 활용 가능.

A6. **Wrapup-doc auto-detect**: `CHANGELOG.md / TODO.md / docs/ADR-*.md` 존재 여부 → `wrapup_docs` default 채움.

A7. **MCP suggestion engine**: framework 기반 추천 — frontend (React/Vue) → playwright MCP suggest; firmware → 추천 없음; data science → jupyter MCP. **결정 X — 단지 인터뷰에서 *추천 카드* 표시**, 사용자가 yes/no.

### Track B — Adaptive Self-Tuning (SECONDARY, Track A 이후)

| 필드 | 내용 |
|------|------|
| Approach | 하네스가 자기 사용을 관찰 → 정기적으로 axis 재제안. `/hm:personalization-audit` 명령 + monthly `SessionStart` hint |
| Assumption | 사용자는 한 번 configure 후 거의 다시 안 만짐 (실제 git log: `/hm:configure` 후 `harness.yaml` 직접 수정이 압도적). 신호는 *자동 캡처* + *명시적 재제안 시점* 필요 |
| Evidence | [[RESEARCH-harness-trends-2026-05]] Top-1 Harness Synthesis (AutoHarness, AgentFlow); MCE (2601.21557) skill/context co-evolution 16.9% 상대 개선; [[RESEARCH-harness-gap-cot-2026-05]] Pitfall #6 self-correction loop class cap (logical error 45%); 우리 자체 telemetry (review_telemetry.py, telemetry.py) 가 이미 jsonl 으로 누적 중 — 활용 안 함 |
| Trade-off | 데이터 모으는 데 시간 (최소 30 sessions or 90 days). 너무 일찍 권유 → noisy; 너무 늦으면 무의미. observer effect (telemetry 가 user 행동 바꿈) 회피 위해 **read-only audit** 형태로 시작 |
| Compatibility | 높음. telemetry.py, review_telemetry.py 가 이미 존재. SessionStart hook 이 이미 drift 를 surface (recent commit `64bf5b9`) — 같은 surface 재활용 |
| Risk | medium — false-recommendation (잘못된 패턴 권유) 가 user trust 깎음. 권유는 *suggestion-only*, 절대 자동 적용 X |

**구체 sub-track**:

B1. **Override telemetry**: 사용자가 `harness.yaml` 의 어떤 키를 manual 편집했는지 git diff 추적 → "사용자가 `consensus` 를 4번 직접 바꿨네요. default 를 cross-check 으로 바꿀까요?"

B2. **Permission prompt frequency**: hook log 분석 → 매번 prompt 되는 permission → "이 permission 을 default allow 로?" (단, **deny pattern 은 더 엄격 유지**, allow 만 자동 권유)

B3. **Reviewer signal**: review_telemetry.py 의 N session 동안 *항상 PASS / 항상 같은 finding* 패턴 → 해당 reviewer 제거 권유 (PASS) 또는 mechanical_check 으로 전환 권유 (같은 finding 반복).

B4. **`/hm:personalization-audit`**: 위 모든 신호 + 3-layer rubric (Bronze/Silver/Gold/Platinum) → 단일 명령 출력. ai-readiness rubric 의 패턴 재사용 (rubric_loader.py 가 이미 framework).

B5. **Session drift surface**: 30 session 마다 SessionStart 에서 "your harness has 8 axis recommendations queued. /hm:personalization-audit to review" — 사용자가 끄지 않는 한 정기 nudge.

### Track C — New Axes (DEFER until Track A/B basics land)

| 필드 | 내용 |
|------|------|
| Approach | team-profile (solo/small/large), privacy-tier (none/sensitive/regulated), code-style (docstring / naming), cross-project preference 5개 추가 axis |
| Assumption | Track A 의 detection→recommend 인프라 + Track B 의 adaptive loop 가 있으면 이 axis 들이 *자동으로 권유* 됨. 없으면 그냥 default 로 묻히는 또 하나의 yaml 키 |
| Evidence | enterprise adoption 의 entry barrier (HIPAA/PCI/GDPR) + Cursor User Rules vs Project Rules 의 2-tier 분리가 이미 사용자 mental model — 우리는 단일 tier (project 만) |
| Trade-off | axis 7→12 으로 늘면 InterviewAnswers 가 무거워짐. context_lint 부담 증가. backward compat 부담 (옛 yaml 의 missing field fallback 5개 추가) |
| Compatibility | medium. 각 axis 가 독립이라 phase 분할 가능. 다만 모든 axis 가 reviewer/permission/skill 어딘가에 영향을 주어야 *권유* 가 의미 있다 — Track A/B 없으면 dead config |
| Risk | medium |

**구체 sub-track** (각각 별도 phase 가능):

C1. **Team profile** (solo / small-team / large-team): consensus default, review intensity, commit message format, PR vs direct commit. 1-2명 dev = `consensus=single, auto_fix=true`; 5+ dev = `consensus=cross-check, mandatory PR`.

C2. **Privacy/regulated tier** (`security.tier: none|sensitive|regulated`): regulated → file-level deny patterns (e.g. `db/migrations/*sensitive*.sql` never read by LLM), MCP 통과 데이터 redaction, 외부 web search disable.

C3. **Code-style detection** (docstring/naming): NumPy/Google/Sphinx 식별 → execute stage prompt 의 "write docstrings as X style" 자동. naming convention (snake_case / camelCase / PascalCase) AST 분석 → 마찬가지.

C4. **Cross-project preferences** (`~/.harness-maker/user-defaults.yaml`): 5 프로젝트 모두에서 같은 axis 를 같은 값으로 쓰면 자동 user-default 로 승격. 6번째 프로젝트의 default 가 user-default. Track B 가 데이터 공급원.

C5. **Per-developer overlay** (`~/.claude/<repo-id>/overlay.yaml`): 공유 harness 위에 dev 별 override. Cursor User Rules 와 동치 패턴. multi-dev team 의 friction 해소.

### Track D — Foreign AI Config Migration (Track A 의 sub-track 으로 통합 가능)

| 필드 | 내용 |
|------|------|
| Approach | `.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`, `.github/copilot-instructions.md` 자동 감지 + LLM-driven import suggest |
| Assumption | 신규 사용자 대다수가 *이미 AI 코딩 도구를 쓰고 있고* 그 설정이 disk 에 있음. greenfield 보다 brownfield 가 default |
| Evidence | Cursor / Continue / Aider / Copilot / Codex 동시 사용은 GitHub 검색 결과 흔함. [[RESEARCH-onboarding-ux-2026-05]] brownfield 시나리오; 우리 reconcile.py 는 *우리 출력* 의 KEEP/REPLACE 만 보고 외부 AI config 는 touch 안 함 — 그런데 사용자는 통합 기대 |
| Trade-off | LLM 호출 (외부 config 읽고 의도 추론) — 한 번만, idempotent. False mapping 위험은 *사용자 confirm step* 으로 완화. import 후 원본 파일은 보존 (덮어쓰지 X) |
| Compatibility | 매우 높음. import 후에는 우리 harness.yaml 로 single source 됨. 외부 AI 도구 와 병행 운영 시에는 *우리가 그 외부 파일 도 generate* (현재 .cursor/rules 는 이미 generate) |
| Risk | low-medium — false mapping 이 사용자 친화 메시지로 surface 되면 user trust 유지 |

**구체 sub-track**:

D1. **Detection layer**: 6개 known config 파일 존재 여부.
D2. **LLM 매핑**: 각 config 의 내용 → 우리 axis 매핑 제안 (e.g. Cursor `.mdc` 의 `globs:` → 우리 conditional-router 의 path-rule).
D3. **Confirm UI**: 인터뷰에서 매핑 표 + accept/reject 토글.
D4. **Idempotent re-import**: `/hm:configure --reimport-foreign` 으로 외부 config 변경 시 다시 swing.

---

## ⚠️ Pitfalls (personalization-depth 특유)

1. **"Domain content owner = user" 원칙 깨기 쉽다.** detection 이 깊어지면 "이 프로젝트는 React 야" → 자동으로 React-best-practice agent prompt 박는 유혹 — 해선 안 됨 ([[feedback_domain_content_ownership]]). detection 의 출력은 *어떤 페르소나 슬롯을 추천* 까지, 페르소나 *content* 는 user. 모든 Track A sub-track 의 PR description 에 "domain content 추가 X" 확인 필수.

2. **Recommendation 권한 인플레이션.** 한 번에 17개 축 권유하면 인터뷰가 끝없어짐. UI 패턴: **Top-3 가장 confident 한 권유만 explicit 질문, 나머지는 silent default** (사용자가 yaml 열어 보면 보임 + comment 에 reasoning).

3. **False-positive detection 의 trust cost.** `requirements.txt` 만 있고 실제로는 java 프로젝트 (CI 가 java) 인 케이스 — 사용자가 한 번이라도 보면 "이 도구 못 믿겠다" 신뢰 깎임. 모든 detection 결과는 *confidence score* 표시 + 낮으면 그냥 "unknown — please specify".

4. **Adaptive loop 의 observer effect.** B1 (override telemetry) 가 *사용자 행동 데이터 수집* 으로 보이면 unease. 해결: 100% 로컬 (이미 CLAUDE.md 정책), 매월 audit 결과를 *사용자에게 보여줌* (transparency), opt-out 명령 (`hooks.disable-personalization-telemetry`).

5. **Cross-project federation 의 충돌 정책.** Track C4 (user-defaults) 가 *5개 프로젝트 모두에서 같은 값* 을 자동 승격하면, 6번째 프로젝트가 *legitimately different* (e.g. firmware vs web) 일 때 잘못된 default. 해결: user-default 승격 시 *stack-aware* — "python+pytest 프로젝트에서만 적용" 같은 scope 추가.

6. **Personalization rubric 이 score-Goodharting 의 새 surface 됨.** Bronze→Platinum 추격이 *실제 fit* 보다 *rubric 점수* 최적화 압박 → 의미 없는 axis 채우기. 해결: rubric 의 모든 level 은 *trade-off 명시* — Platinum 이 항상 좋은 게 아님 (adaptive loop 가 high-cost 환경 / 단일-세션 시나리오에서 부담).

7. **Foreign AI config import 의 ownership 모호.** D2 가 Cursor rule 을 import → 우리 axis 로 변환 → 사용자가 cursor 를 계속 쓰면서 cursor rule 을 *직접 편집* → 우리 axis 와 drift. 해결: import 시 *single source* 강제 — "이제부터는 우리가 .cursor/rules 도 generate 합니다" 명시 + 외부 도구의 user 편집은 *block-merge marker* 와 같은 방식으로 보존.

8. **Privacy axis (C2) 와 LLM 호출 자체의 충돌.** regulated tier 가 *모든 외부 LLM 호출 금지* 라면 우리 core (`anthropic` 의존) 자체가 작동 X. 해결: regulated tier 는 *file-level deny + redaction* 까지만; *zero-LLM* 은 별도 enterprise tier 로 표기.

9. **Detection 의 git-history 부담.** A3 (commit-style) 의 `git log -n 50` 은 cheap 하나, A5 (README LLM 요약) + D2 (foreign config LLM 매핑) 가 누적되면 `/hm:configure` 가 30초+ 걸림. 해결: detection 결과 캐싱 (`~/.cache/harness-maker/profile-<repo-hash>.json`, 24h TTL).

10. **Per-developer overlay (C5) 의 git-share 위험.** dev A 의 overlay 가 실수로 commit → dev B 가 dev A 의 preference 받음. 해결: overlay 는 `~/.claude/` 절대 경로 (project repo 밖) + 우리가 `.gitignore` 검증.

---

## ❓ Open Questions (`/hm:plan personalization-depth-2026-05` 인터뷰가 lock-in)

1. **Track 우선 순위**: Track A (detection depth) 먼저인가 Track B (adaptive) 먼저인가? 권장: A — 데이터 없는 adaptive 는 cold-start.
2. **Track A 의 sub-track scope**: A1-A7 중 첫 릴리스에 몇 개? (A) 전부 (B) A1+A2+A6 (stack+foreign+wrapup-docs) (C) A2 만 (foreign-AI config import — 가장 즉각적 user value).
3. **LLM 호출 budget for detection**: A5 (README 요약) + D2 (foreign config 매핑) 가 LLM 호출. configure 한 번에 몇 번 까지 OK? 권장: max 3 호출 + cache.
4. **Recommendation 표시 UI**: AskUserQuestion 으로 *모든* recommendation 질문 vs *Top-3 만* 명시 + 나머지 silent default + comment 에 이유?
5. **Adaptive opt-in vs opt-out**: Track B 가 default-on 인가 default-off? 권장: default-on (read-only audit, suggestion-only — actual 적용은 user confirm).
6. **Personalization rubric 의 도입**: 별도 명령 `/hm:personalization-audit` vs 기존 `/hm:ai-readiness` 의 layer 4 로? 권장: 별도 명령 (다른 audience — ai-readiness 는 외부 사용자 onboard, personalization 은 maintainer self-review).
7. **Foreign AI config import 의 backward 정책**: import 후 외부 파일 (`.cursor/rules/`) 을 우리가 *re-generate* 하는가 *touch 안 함* 인가? 권장: re-generate (single source 보장), 단 user 편집은 block-marker.
8. **Per-developer overlay (C5)** 도입 시점: 0.12.x 에 포함 vs defer? Track B 의 데이터 (override telemetry) 가 *single-dev 가정* 으로 작성되면 multi-dev 변경 시 schema 흔들림 — 처음부터 multi-dev 가정이 안전.
9. **Cross-project user-defaults (C4)** 의 저장 위치: `~/.harness-maker/user-defaults.yaml` 단일 vs `~/.harness-maker/by-stack/<stack>.yaml` 다중? scope 충돌 (Pitfall #5) 회피하려면 후자.
10. **Privacy/regulated tier (C2)** 의 layer: harness-maker 자체 LLM 호출 (anthropic 의존) 도 disable 가능해야 하나? *full-zero-LLM enterprise tier* 는 본 doc scope 밖 / 별도 research 권장.

---

## 📊 Predicted Impact Matrix

| Track | 구현 비용 | user-visible value | 경쟁 차별화 | 위험 | 권장 순서 |
|-------|----------|-------------------|------------|------|----------|
| A (Detection Depth) | medium (3-5 phase) | high — 인터뷰 default 정확도 ↑↑ | high — 동급 대비 격차 벌리는 직접 경로 | low | **1순위** |
| B (Adaptive Tuning) | high (4-6 phase + telemetry schema) | medium-high — 누적 효과 | very high — 어떤 도구도 미보유 | medium (observer effect) | **2순위** (A 후 3-6개월) |
| C (New Axes) | medium-high (각 1-2 phase × 5) | medium — 정해진 use case 만 | low — Cursor/Continue 도 일부 있음 | medium | **3순위** (A/B 후 cherry-pick) |
| D (Foreign AI Migration) | medium (2-3 phase) | very high — onboarding friction 해소 | very high — 시장의 brownfield 지배 가정 인정 | low-medium | **1순위와 병행** (A 의 sub-track 으로) |

---

## 📚 Sources

### External (minimal — 본 doc 은 내부 분석 위주)

- [Cursor — Rules docs](https://docs.cursor.com/context/rules) — Project Rules (`.cursor/rules/*.mdc`) vs User Rules 2-tier 패턴; globs / alwaysApply / description-driven matching.
- [Continue.dev — config docs](https://docs.continue.dev/customize/config) — `config.json` per-project, model/embedding/context provider 등 manual 명시.
- [Aider — config docs](https://aider.chat/docs/config/aider_conf.html) — `.aider.conf.yml`, project default 모델/언어/auto-commit.
- [GitHub Copilot — custom instructions](https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot) — `.github/copilot-instructions.md` repo-level.
- [Builder.io — Cursor rules guide](https://www.builder.io/blog/cursor-rules) — 커뮤니티 best practice; awesome-cursorrules 생태계 신호.
- [Codified Context 2602.20478](https://arxiv.org/abs/2602.20478) — persistent context 가 cross-session 일관성 유지; adaptive loop 의 이론적 근거.
- [Meta Context Engineering 2601.21557](https://arxiv.org/abs/2601.21557) — skill/context co-evolution 16.9% 상대 개선 (Track B 근거).
- [Context Engineering taxonomy 2603.09619](https://arxiv.org/abs/2603.09619) — relevance/sufficiency/isolation/economy/provenance — 본 doc 의 detection→recommend pipeline 정합.
- [CC #41930 — quota drain](https://github.com/anthropics/claude-code/issues/41930) — adaptive tuning 의 cost 부담 우려 prior art.

### Internal (재인용 — 본 doc 은 prior research 위에 쌓는다)

- [[RESEARCH-harness-gap-cot-2026-05]] — Reliability Stack 7 features, persona library defer 결정, multi-CLI defer 결정. 본 doc 의 anti-pattern 회피 근거.
- [[RESEARCH-harness-trends-2026-05]] — harness synthesis / longitudinal CI / agentic verification. 본 doc Track B 의 상위 형태.
- [[RESEARCH-user-workflow-opportunities-2026-05]] — Second Brain (DONE), Issue intake, Evidence loop. 본 doc 과 직교; user-facing external context 가 그쪽, project-fit 이 본 doc.
- [[PLAN-user-workflow-opportunities-2026-05]] — Second Brain 7 phase 완료 — Track A 의 second_brain 자동-detection 패턴 모델.
- [[RESEARCH-make-ux-gaps-2026-05]] — `vault_member` detection→권유 변환의 정상 작동 사례.
- [[RESEARCH-onboarding-ux-2026-05]] — brownfield 시나리오 — Track D 의 동기.

---

## 🔗 Related Internal Docs

- [[feedback_domain_content_ownership]] — domain content owner = user. Track A 의 모든 sub-track 의 boundary line.
- [[project_targets_axis]] — targets 명시 multi-select 강제, auto-detect 금지. detection→recommend 의 *반례* (사용자 의도 확인이 더 중요한 axis 도 있다) — 본 doc 의 *모든* detection 이 권유에 그치고 강제 X 원칙의 근거.
- [[project_dev_mode_axis]] — preset 과 직교 axis. transitive recommendation 의 사례 (preset → dev_mode 권유).
- [[project_review_grade_gate]] — review auto-fix loop. Track B 의 reviewer signal 데이터 공급원.
- [[project_docs_search_design]] — ref_folders detection 의 minimal yaml index 정책. Track A 의 detection cache (Pitfall #9) 와 동치.
- [[project_multi_repo_mgmt_progress]] — sibling_repos 진행 상황. Track A4 (monorepo manager detection) 와 인접.
- 2026-05-08 session [[decision:review-cross-check-with-disjoint-specialists]] — consensus axis 의 운영 함정. Track B3 (reviewer signal) 의 caution.
- 2026-05-08 session [[decision:cursor-compat-dual-render-kept]] — schema divergence 비용. Track D (foreign config import) 의 *반대 방향* 사례 — single source 강제의 cost.

---

*본 research 는 Phase 4 validation 후 `/hm:plan personalization-depth-2026-05` 진입.*
