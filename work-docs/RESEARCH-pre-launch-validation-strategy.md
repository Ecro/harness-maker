---
type: research
task_slug: pre-launch-validation-strategy
status: complete
created: 2026-05-19
tags: [harness-maker, research, validation, dogfood, qa, launch-readiness]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://arxiv.org/html/2603.00539
  - https://arxiv.org/pdf/2508.12358
  - https://medium.com/@haseeb_sohail/how-i-evaluate-llm-code-quality-reviewing-ai-generated-code-at-scale-db8c4f150107
  - https://www.centercode.com/blog/dogfooding-101
  - https://www.testdevlab.com/blog/dogfooding-a-quick-guide-to-internal-beta-testing
  - https://blog.uxtweak.com/product-dogfooding/
  - https://www.productplan.com/learn/how-to-recruit-beta-testers
  - https://code.claude.com/docs/en/discover-plugins
  - https://www.agensi.io/learn/claude-code-plugin-marketplace-guide
  - https://buildtolaunch.substack.com/p/best-claude-code-plugins-tested-review
related_docs:
  - [[PLAN-oss-readiness-audit]]
  - [[RESEARCH-oss-readiness-audit]]
  - [[REVIEW-oss-readiness-audit-2026-05-19]]
  - [[tests/cursor-compat/MANUAL_CHECKLIST]]
  - [[tests/e2e/test_plugin_live.py]]
  - [[tests/integration/test_fresh_install_readiness.py]]
summary: "Layered validation (existing tests + 2-stack dogfood + Cursor checklist + Codex smoke) beats 'code review only' — LLM reviewers miss ~40% of real bugs."
---

## 🎯 Recommended Direction

**"코드 리뷰만" 은 NO. 실제 multi-place 테스트가 정답이지만 scoping 잘 해야 함.** 2026 LLM-code-review 연구가 합의: judge LLM 의 BugMatch ~60%, 즉 **실제 버그의 40% 가 reviewer 를 통과**. multi-reviewer consensus 도 hallucinated-requirement bias 를 증폭시킬 뿐 false-negative 본질은 못 잡음. harness-maker 의 surface 중 (a) IDE 통합 — Cursor + Codex, (b) PyPI/marketplace 설치, (c) 실제 interactive interview 흐름, (d) 12+ stack profiler 의 실제 stack 별 정확성 — 이 4가지는 mocked-test 와 LLM 리뷰 둘 다 못 보는 것. 추천: **5-layer 검증** (기존 test suite + 2-stack 자가 dogfood + Cursor 매뉴얼 + Codex 스모크 + 선택적 외부 베타 1명). 총 ~3-4 시간 budget. Phase 10 soak 가 passive 면 이 5-layer 는 active 보완.

## 🔍 Refinement Decisions

Discovery lens: **User-workflow / product opportunity** (실제 install 사용자 경험) + **Risk / compliance** (LLM 리뷰 한계 + 알려진 failure mode) + **Technical architecture** (현재 test surface gap 파악). arXiv lens 는 LLM-as-judge 정확도 1편만 사용.

## 🛠️ Approaches Found

### Approach A — Code review only (재실행)

| Field | Content |
|---|---|
| **Approach** | 추가 multi-reviewer cross-check (security/code/ux/concurrency/perf), 새 리뷰어 추가, 또는 같은 리뷰어 N차례 재실행 |
| **Assumption** | LLM judge 정확도가 N 차례 합의시 본질적 향상 |
| **Evidence** | arxiv 2603.00539: **detailed prompt + multiple judges = false-finding rate 증가** (the more careful the prompt, the more hallucinated requirements). BugMatch 절대값은 안 올라감. |
| **Trade-off** | 노이즈 ↑, signal ↑ 미미. 시간 1-2시간 / 회 |
| **Compatibility** | 이미 framework 있음 (security + code + ux consensus framework 작동 중) |
| **Risk** | 높음 — false confidence. "리뷰 4번 했으니 안전" 이라는 인지편향 |

### Approach B — 1-stack 자가 dogfood만

| Field | Content |
|---|---|
| **Approach** | harness-maker 자체 repo (Python 만) 에서 fresh `/hm:make` → `/hm:health` → 본인 voice 로 끝까지 확인 |
| **Assumption** | "내 stack 에서 되면 다른 stack 도 비슷할 것" |
| **Evidence** | Centercode dogfood guide: 다양한 role/stack 노출이 dogfood 의 정의. 1개만 noise vs signal 안 됨. |
| **Trade-off** | 30-60분. profiler 의 stack-conditional logic / 12+ 신호 정확성 검증 불가 |
| **Compatibility** | 그 동안 진행해온 패턴 (dogfood-only) — 새 코드 path 없음 |
| **Risk** | 중간 — Python-stack 만 검증. Tauri/Next.js/Flutter/Zephyr 등은 0.17.0 release notes 에 언급되지만 실제 호출은 unclear |

### Approach C — **5-layer 다중 검증** (추천)

| Field | Content |
|---|---|
| **Approach** | 기존 144 test 통과 확인 + 2 stack 자가 dogfood + Cursor 매뉴얼 checklist + Codex 스모크 + 외부 베타 1명 선택적 |
| **Assumption** | 각 layer 가 잡는 bug class 가 다름. Pareto-optimal: ~3-4시간 / launch 신뢰도 dramatic ↑ |
| **Evidence** | uxtweak dogfood guide: 다양한 stack/IDE 노출이 핵심. arxiv 2508.12358: LLM verification 의 systematic failure 는 specification-vs-implementation mismatch — 실제 실행만이 catch. ProductPlan beta guide: 2-3 명 외부 베타가 first-impression bug 의 80% catch |
| **Trade-off** | 3-4시간 + 선택적 1명 외부 reach. 일주일 soak 안에 충분 |
| **Compatibility** | Phase 10 (passive 1주 soak) 안 깨고 active 보강 |
| **Risk** | 낮음 — 각 layer 가 독립적이라 한 layer 실패해도 나머지가 보완. 시간만 들이면 됨 |

### Approach D — External beta only

| Field | Content |
|---|---|
| **Approach** | 2-3명 트위터/디스코드/지인에게 install 요청, 코드 리뷰 + 자가 dogfood 안 함 |
| **Assumption** | "real user" 가 모든 bug class 를 catch |
| **Evidence** | ProductPlan: beta 추천 patterns 은 strong but recruit 시간 + 답신 latency 큼 |
| **Trade-off** | 사람 시간 (남의) — 2-3명 reach 시간 + 답신 1-3일 + 답신 quality 변동성 큼. 첫인상 망치면 social cost |
| **Compatibility** | 솔로 + just-launched 의 "PRs at your own risk" 톤과 충돌 가능 ("미완성품에 시간 쓰라고 한다") |
| **Risk** | 중간 — 외부 의존, deterministic 아님. 자가 검증 없이 외부 노출은 reputational risk |

### Synthesis

C 추천 이유 명확:
- **A 의 효과 한계** = arxiv 합의 (LLM judge 의 BugMatch 절대값은 reviewer 수 추가로 못 올라감)
- **B 만 으로는 stack 다양성 0** = profiler/conditional rendering 가 핵심 가치인데 1-stack 만 dogfood 면 그 가치 검증 자체가 빠짐
- **D 만 으로는 selvalidation 부재** = 외부 사용자가 첫 30초에 시간 망치면 social cost. self-dogfood 후 베타로 가는 게 정상
- **C 가 가장 비용대비 효율** — 각 layer 가 서로 다른 bug class catch + 시간 3-4 시간이면 일주일 soak 안에 충분히 들어감

## ⚠️ Pitfalls

1. **"테스트 다 pass 했으니 OK" 함정** — 현재 144 test 중 unit 123 + integration 9 + e2e 7. **e2e 중 실제 `claude` 바이너리 호출하는 건 `test_plugin_live.py` 하나뿐**이고, 그것마저 `--ci` 플래그 사용 → AskUserQuestion-driven interactive interview 는 e2e CI 에서 단 한번도 실행되지 않음. arxiv 2508.12358 ("Uncovering Systematic Failures of LLMs in Verifying Code Against Natural Language Specifications") 가 정확히 이 gap 을 paper 로 만듦.

2. **Cursor IDE 통합은 Phase 1 manual 검증 결과 따름이라고 CLAUDE.md 가 명시** — 즉, 실제 Cursor 에서 agent dispatch / skill auto-load / hook fire 가 작동하는지는 자동화 안 됨. `tests/cursor-compat/MANUAL_CHECKLIST.md` 가 30분 가이드로 존재 — 안 돌리면 Cursor target 의 모든 약속이 unverified 인 상태로 launch.

3. **Codex CLI 는 manual checklist 자체가 없음** — `tests/codex-compat/` 에 fixture (`hook_*.json`, `test_worktree_create.md`) 만 있고 매뉴얼 가이드 부재. README + plugin.json + agents/ 매니페스트 다 ship 되어 있지만 실제 Codex 가 이를 어떻게 dispatch 하는지 검증된 적 없음. 가장 risk 높은 IDE.

4. **PyPI 설치 path 가 main branch 변경과 sync 안 됨** — `release.yml` 의 tag-time smoke (`uv pip install harness-maker --python /tmp/testpypi-venv/bin/python && harness-maker --help`) 가 마지막 검증. 이후 main 에 변경 누적 (8 commits 이번 세션). PyPI 0.17.0 release 와 현재 main 의 결정적 차이 (가령 `tests/unit/test_synthesize.py` 의 format 차이) 는 다음 PyPI release (0.17.1+) 에야 반영. **즉 PyPI 사용자는 0.17.0 을 받고**, GitHub clone 사용자는 main 상태 (post-launch readiness) 를 받음. Two-version problem — 어떤 surface 를 검증할지 명확해야.

5. **Bootstrap prompt 검증 부재** — README hero 의 "Try in 30 seconds" 가 실제 Claude Code / Cursor / Codex 에서 detection branch → Bash install → Skill 호출 까지 흐름이 작동하는지 자가 검증 없음. CLAUDE.md "8 checkpoints" §8 ("Integration boundary one-liner test") 의 원칙에 위배. 가장 visible 한 user-facing path 가 hand-test 부재.

6. **LLM judge bias of detailed prompts** (arxiv 2603.00539) — 우리가 reviewer 에게 더 구체적 지시를 주면 hallucinated-requirement rate 가 더 높아짐. exec-rev 의 verifier (Pass 1.5) 가 이를 일부 mitigate 하지만 본질적으로는 self-fulfilling — 같은 LLM family 의 verifier 가 같은 family 의 reviewer 의 hallucination 를 catch 한다는 가정이 위태로움. 외부 dogfood 만이 model-independent signal.

7. **"베타 1명 = 안 함"** — solo + just-launched 의 ergonomic trap. 1명 external user 의 "30초 install 실패" 가 코드 review 10시간보다 더 많은 정보를 줌. ProductPlan: 첫 베타가 first-impression bug 의 80% catch. 그러나 "PRs at your own risk" 톤과의 conflict 는 베타에게 진실되게 말하면 (= "이 stage 에서의 베타는 risk 동의 후 진행") 해결됨.

8. **Stack 다양성 — Python-bias risk** — harness-maker 자체가 Python 이므로 dogfood 가 Python-bias. 12+ stack signal 검증 (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pubspec.yaml`) 의 실제 fixture 가 stack 별로 있긴 하지만 (`tests/e2e/sandbox`, `tests/e2e/sandbox-plugin-test`), JS/Rust/Go/Flutter 의 real-world `/hm:make` 실행 결과는 unknown.

9. **Snapshot regen drift** — `[fail:test] snapshot-regen-inside-worktree count:6` 이 이번 세션에 또 발생. 이는 test 가 일관되게 통과하는지 자체가 환경 의존적임을 보여줌. dogfood 시 같은 함정이 user 머신에서 재현될 수 있음.

10. **현재 main 의 d6d522b commit 은 자동 검증 안 됨** — locale fix (synthesize/workflow_fuse) 는 prior session 의 uncommitted 작업이었고 wrapup 의 verify pass 에서 통과는 했지만 (테스트 2,221 green), 실제 `harness.yaml.locale: ko` 시 한국어 interview 가 작동하는지 manual 검증 부재. 솔로 사용자 본인이 `ko` locale 로 검증하면 30분에 catch 가능.

## ❓ Open Questions (plan 단계에서 정해야)

1. **Layer 6 (외부 베타) include? exclude?** — 1명 부르면 Phase 11 (Show HN) 전에 catch 신호 ×10. 0명이면 깨끗한 self-validation 만. 외부 채널 친한 사람 있는가? r/ClaudeAI / 디스코드 등 reach 가능한가?
2. **2-stack dogfood 의 두 번째 stack 선택** — 후보: Tauri (Rust+TypeScript, dual-language 케이스), Next.js / React (가장 흔한 web stack), Zephyr (firmware — niche but harness-maker README 에 명시됨), FastAPI (Python 다른 framework). 사용자가 access 가능한 본인 프로젝트 기준이 최우선.
3. **Codex 매뉴얼 checklist 새로 design 할지, 또는 Codex target 비고로 후속 처리할지** — Codex 가 가장 risk 높지만 launch 시 "Codex target untested" 만 명시하고 deferred 가능. 매뉴얼 만들 시 30-60분 추가.
4. **PyPI 시멘틱 — main 과 sync 강제 여부** — 다음 patch release (0.17.1) 를 이번 세션 변경 사항 반영용으로 cut? 또는 main 만 update 하고 PyPI 는 다음 feature release 때 합쳐서? 후자가 conventional 이지만 user 들이 PyPI 0.17.0 + GitHub main 의 차이로 혼란 가능.
5. **Bootstrap prompt 자체의 LLM-IDE-detection branch 검증** — Claude Code 의 `$CLAUDE_CODE`, Cursor 의 `$CURSOR_SESSION`, Codex 의 `$CODEX_SESSION` env var 가 실제로 set 되는지 unverified. 각 IDE 에서 echo 한 번이면 catch.
6. **Phase 10 soak 와의 관계** — 5-layer validation 을 Phase 10 안에 끼우는지, Phase 10 끝나고 Phase 10.5 로 추가하는지. 전자가 calendar 효율, 후자가 분리된 책임.
7. **Layer 별 fail 처리 분기** — Layer 3 (2-stack dogfood) 에서 P0 발견 시 patch + 새 tag + Phase 10 reset, P2 발견 시 issue 로 defer 하고 진행. P1 의 처리 정책은? (validator 가 자주 흐릿한 영역)
8. **"checklist" vs "free-form dogfood"** — Cursor 매뉴얼처럼 step-by-step 체크리스트가 reproducibility 높지만 LLM-가이드 free-form dogfood 가 unknown-unknown 더 잘 catch. 두 mode 다 쓸지, 하나만 쓸지.
9. **만약 외부 베타 1명 가능하면 그 사람의 task 정의** — "install 만", "30분 자유 실행", "특정 시나리오 (`/hm:make` end-to-end)", "본인 프로젝트에 깔아보기"? 시간 명시 + 기대 결과 명시가 베타의 ROI 좌우.
10. **수집된 신호의 저장처** — 5-layer 동안 발견한 issue 들 `.claude/memory/failures.md` 에 추가? GitHub Issues 자체로? work-docs/ 의 새 doc? deferral / followup 의 단일 source-of-truth 필요.

## 📊 Layer 별 catch 하는 bug class (요약 표)

| Layer | 시간 | What it catches | What it misses |
|---|---|---|---|
| **L1: Static code review (already done)** | 2-3 시간 (exec-rev) | SHA pin, doc-vs-code drift, naming inconsistencies, obvious logic, security policy file content | Live runtime, IDE integration, real LLM tool-call shape, multi-step interactive flows, stack-conditional rendering |
| **L2: Existing test suite** (`pytest -x`) | 4 분 | Logic regressions on mocked services, schema drift (e.g., PRIVACY.md AST-walk test) | Anything mocked — all anthropic/GitHub/arxiv/OSV calls, real file-system races, real IDE behavior |
| **L3: 2-stack self-dogfood** (fresh `/hm:make` on Python + 1 other) | 60-90 분 | Stack profiler accuracy on real `pyproject.toml`/`package.json`/`Cargo.toml`, conditional reviewer routing, real render output, foreign-config absorption (`.cursor/rules`, `AGENTS.md`, `.aider.conf.yml`) | Other stacks, other IDEs, multi-step interview surprises that the 2 chosen stacks don't hit |
| **L4: Cursor manual checklist** (`tests/cursor-compat/MANUAL_CHECKLIST.md`) | 30 분 | Cursor agent dispatch, skill auto-load, hook fire schema, fixture-state preservation | Other IDEs, real user workflows beyond fixture |
| **L5: Codex CLI smoke** (new — 5-10 step checklist) | 30-60 분 (design + run) | Codex plugin marketplace add, hook permission flow (PermissionRequest event), AGENTS.md absorption, `.codex/config.toml` recognition | Long-running flows, multi-stack |
| **L6: 1 external beta** (optional) | 15-30분 reach + 1-3일 latency + 15-30분 debrief | First-impression friction (install → first run → "what now?"), tone-mismatch in docs, dialect/locale issues | Stack-specific issues outside beta's project, slow-build cumulative failures |

## 🧭 시간 budget 권장 (Phase 10 1주 안에)

| 일차 | 작업 | 시간 |
|---|---|---|
| **D-7 (today)** | L1+L2 — already done in exec-rev + wrapup | 0 (이미 함) |
| **D-7 evening or D-6** | L3 — 2-stack self-dogfood, P0 면 patch release | 60-90 분 |
| **D-5** | L4 — Cursor manual checklist | 30 분 |
| **D-4** | L5 design — Codex smoke checklist 새로 만들기 (10 steps) | 30 분 |
| **D-3** | L5 run — Codex smoke 실행 | 30 분 |
| **D-3 / D-2** | (선택) L6 — 외부 베타 1명 reach, brief, async wait | reach 30분 |
| **D-1** | L6 debrief + 모든 layer 의 issue triage + Phase 11 Go/NoGo 결정 | 30-60 분 |
| **D-0** | Show HN 게시 (Phase 11) | 30 분 |

총 active 시간 **3-4 시간** (외부 베타 제외) 또는 **4-5 시간** (베타 포함). 일주일 soak 안에 충분히 들어감.

## 📚 Sources

- [arXiv: Are LLMs Reliable Code Reviewers? Systematic Overcorrection in Requirement Conformance Judgement](https://arxiv.org/html/2603.00539) — BugMatch ~60%, false-negative 54%, detailed prompts increase hallucination
- [arXiv: Uncovering Systematic Failures of LLMs in Verifying Code Against Natural Language Specifications](https://arxiv.org/pdf/2508.12358)
- [Medium: How I Evaluate LLM Code Quality (Apr 2026)](https://medium.com/@haseeb_sohail/how-i-evaluate-llm-code-quality-reviewing-ai-generated-code-at-scale-db8c4f150107)
- [Centercode: Dogfooding 101 — A Quick Guide to Internal Beta Testing](https://www.centercode.com/blog/dogfooding-101)
- [TestDevLab: Dogfooding Guide](https://www.testdevlab.com/blog/dogfooding-a-quick-guide-to-internal-beta-testing)
- [UXtweak: Product Dogfooding](https://blog.uxtweak.com/product-dogfooding/)
- [ProductPlan: 9 Ways to Recruit Beta Testers](https://www.productplan.com/learn/how-to-recruit-beta-testers)
- [Claude Code Docs: Discover and install prebuilt plugins through marketplaces](https://code.claude.com/docs/en/discover-plugins)
- [Agensi: Claude Code Plugin Marketplace Guide (2026)](https://www.agensi.io/learn/claude-code-plugin-marketplace-guide)
- [Build to Launch: Best Claude Code Plugins (2026) — 10 Tested, 4 Worth Keeping](https://buildtolaunch.substack.com/p/best-claude-code-plugins-tested-review) — referenced for plugin-validation rigor expected by 2026 reviewers

## 🔗 Related Internal Docs

- [[PLAN-oss-readiness-audit]] — Phase 10 (1-week soak) — passive 관찰만, active 검증 부재. 이 RESEARCH 는 그 빈자리 채움
- [[RESEARCH-oss-readiness-audit]] — 직전 connection: launch readiness 의 3-layer (trust / positioning / discovery). 본 doc 은 그 위의 4번째 — quality
- [[REVIEW-oss-readiness-audit-2026-05-19]] — exec-rev 의 reviewer 가 catch 한 것 / 못 한 것 — bugMatch 60% 가 실제 적용된 결과
- [[tests/cursor-compat/MANUAL_CHECKLIST]] — Layer 4 의 source-of-truth
- [[tests/e2e/test_plugin_live.py]] — 유일한 real-binary e2e. `--ci` 플래그로 인터뷰 우회 — gap 의 증거
- [[tests/integration/test_fresh_install_readiness.py]] — Side+Production 의 rubric 통과 검증. CliRunner 이라 IDE 동작 모름
- [[CLAUDE.md#무언가를-고치거나-개선하기-전에--필수-체크리스트]] — §8 "Integration boundary one-liner test" 가 이 RESEARCH 의 핵심 동기
