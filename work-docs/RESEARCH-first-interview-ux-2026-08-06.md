# RESEARCH — 첫 인터뷰(온보딩) 불친절 지점 전수 조사

- 날짜: 2026-08-06
- 범위: 신규 사용자가 처음 `/harness-maker:make` 를 실행했을 때 겪는 전 경로
- 벤치마크: Hermes Agent (NousResearch) CLI 온보딩
- 방법: 두 인터뷰 표면의 코드/템플릿 직접 독해 + Hermes 공식 문서 대조

---

## 1. 인터뷰 표면 지도 — 사용자가 실제로 만나는 건 하나뿐

| 표면 | 파일 | 실행 조건 | 실사용 |
|---|---|---|---|
| 슬래시 인터뷰 | `commands/make.md` (678줄) | `/harness-maker:make` | **이게 사실상 유일한 첫 인터뷰** |
| TTY 인터뷰 | `src/harness_maker/interview.py:139-181` | `harness-maker make . --reinterview` (실제 터미널) | 거의 안 쓰임 (슬래시에선 stdin 없음 → autoloop default 로 조용히 폴백) |

**중요**: 두 표면의 질문 집합이 다르다. TTY 는 `worktree` / `consensus` / `caching` 를 묻지만 슬래시는 안 묻고, 슬래시는 `focus` / `grade_threshold` / `mechanical_checks` / `domains` / `wrapup_docs` 를 묻지만 TTY 는 안 묻는다. 어느 쪽도 전체 축을 덮지 못한다.

슬래시 fresh-install 은 3갈래 (`make.md:208-221`):
- **Looks right** → 즉시 설치 (질문 0개)
- **Adjust a few things** → 10개 차원 중 골라서 수정
- **Full setup** → 14문항 순차

---

## 2. 발견 — 불친절 지점

### A. 커버리지 / 발견성

**F1 (P0). "Looks right" 는 14축 중 10축을 묻지도, 알려주지도 않고 확정한다.**
`make.md:180-207` 의 요약 화면이 보여주는 건 preset / reviewers / mechanical checks / grade / auto-fix **다섯 줄**뿐이다. 나머지는 화면에 뜨지 않은 채 default 로 굳는다:

| 축 | 조용히 정해지는 값 | 사용자에게 표시? |
|---|---|---|
| `second_opinion.models` | `[]` (꺼짐) | ✗ |
| `autonomy.level` | `gated` (꺼짐) | ✗ |
| `worktree.enabled` | preset 파생 (Production=on/Side=off) | ✗ |
| `targets` | `claude-code` | ✗ |
| `ref_folders` / `sibling_repos` | `[]` | ✗ |
| `second_brain` | 비활성 | ✗ |
| `wrapup_docs` | `[]` | ✗ |
| `dev_mode` | preset 파생 | ✗ |

가장 흔한 첫 경로가 **자기가 무엇을 안 골랐는지조차 알 수 없는** 경로다. 이게 "세컨오피니언 안 물어봤다"의 직접 원인이다.

**F2 (P0). 설치된 CLI 를 감지하지 않는다 — 그래서 제안할 수가 없다.**
- `profile()` (`src/harness_maker/profile.py:94`) 이 보는 건 stack / scale / lifecycle / mechanical checks 뿐. `codex`, `agy`, cursor 설치 여부는 스캔 대상이 아니다.
- `shutil.which` 는 코드베이스에 3곳뿐이고 (`cli.py:1464`, `interview.py:520`, `observability/spec_drift.py:159`), 온보딩에서 쓰이는 두 곳 모두 **"사용자가 이미 고른 뒤" 검증**용이다:
  - `cli.py:1461-1469` — 선택된 모델의 CLI 부재 시 경고
  - `interview.py:487-540` — antigravity 를 고른 뒤에만 `agy models` 조회
- 즉 **"있으니까 켤래요?" 라는 역방향 제안이 구조적으로 없다.**

부수 효과로 `targets` 도 같은 문제다. CLAUDE.md 의 targets 정책은 *암묵 추론*(디렉토리 존재 → 자동 켬)을 금지하는 것이지, **"Cursor 감지됨, 포함할까요?" 라고 묻는 것**을 금지하지 않는다. 그런데 현재는 묻지도 않고 `claude-code` default(`make.md:173`) — 같은 정책이 요구하는 "명시 multi-select 강제"와도 어긋난다.

**F3 (P1). 설치 때 안 물은 축은 나중에 켤 UI 경로가 없다.**
`/hm:configure` (`templates/commands/hm/configure.md.j2:28-75`) 메뉴에 **없는** 항목: `second_opinion`, `autonomy(autopilot)`, `locale`, `focus`, `consensus`, `caching`, `permissions.deny_dangerous`. 남은 방법은 `harness.yaml` 직접 편집 또는 실제 터미널에서 `--reinterview` 뿐이다. F1 로 조용히 꺼진 축이 F3 때문에 영구히 꺼진 채 남는다.

**F4 (P1). `/hm:health` 는 이미 켜진 축만 점검한다.**
`health.md.j2:61` 이 `{% if config.second_opinion.models %}` 로 가드돼 있어, **"codex 는 설치돼 있는데 second_opinion 은 꺼짐"** 이라는 가장 흔한 상태에 대해 영원히 침묵한다. Hermes 의 `doctor` 는 미설정 항목을 지적하는 쪽인데 우리는 반대다.

### B. 질문 자체의 친절도

**F5 (P1). TTY 인터뷰의 `consensus` / `caching` 은 설명 0의 생짜 free-text.**
`interview.py:161-162` → `_ask_with_default("consensus", "cross-check")`. 화면에 뜨는 건 `consensus (cross-check):` 한 줄이 전부다. 유효값도, 의미도, 트레이드오프도 없다. 이 두 축은 슬래시 인터뷰에는 아예 없다.

**F6 (P1). second_opinion 질문이 free-text 다.**
`interview.py:499` — `Enable which models? [codex,antigravity or blank for none]:`. 번호 선택 없음, 설치 여부 표시 없음, 비용(리뷰당 추가 호출)·속도 영향 설명 없음. 오타는 `logger.warning` 후 조용히 무시(`interview.py:505`)라 사용자는 자기 입력이 버려진 걸 모를 수 있다.

**F7 (P2). `ref_folders` 문법이 외워야 하는 형태다.**
`make.md:250-252` / `470-474` — `::` 는 항목 구분, `;` 는 경로/glob 구분. 슬래시 UI 에선 이걸 한 줄 free-text 로 정확히 타이핑해야 한다. 아이러니하게 TTY 쪽(`interview.py:347-373`)이 **한 줄에 하나씩 받는 더 친절한 형태**인데, 실사용 표면이 더 나쁘다.

**F8 (P2). Full setup 이 14회 왕복이다.**
`make.md:223-281`. `AskUserQuestion` 은 호출당 최대 4문항을 지원하는데 전부 1문항씩 쪼개져 있다. 4~5회로 묶을 수 있다.

**F9 (P2). 되돌리기·유예 선택지가 없다.**
"Adjust a few things" 에서 잘못 고르면 되돌아갈 수단이 없고, 어느 질문에도 "지금은 건너뛰고 나중에 `/hm:configure` 에서" 라는 명시적 선택지가 없다. (F3 때문에 실제로 나중에 못 하는 축도 있으니 이 선택지를 만들려면 F3 부터 고쳐야 한다.)

**F10 (P2). 용어 설명이 축마다 들쭉날쭉하다.**
preset / dev_mode / grade 는 한 줄 trade-off 가 붙어 있지만(좋음), `autopilot` 의 `auto_safe` vs `full` 차이(`make.md:277-281`), `consensus`, `caching` 은 설명이 없다.

### C. 사실 오류 — 첫인상에서 바로 깨지는 것

**F11 (P0). quick-start 첫 줄이 존재하지 않는 명령을 권한다.**
`make.md:601` — `Run /hm:ai-readiness to see your project's AI-readiness score`. 렌더되는 명령 템플릿은 `atomic_command / configure / health / help / loop / loop-p5-batch / make / metrics / uninstall` 뿐이다(`templates/commands/hm/`). `/hm:ai-readiness` 는 0.x 초기에 `/hm:health` 로 흡수됐고(`docs/adr/0006-three-layer-health-audit.md`), quick-start 만 갱신이 안 됐다. **설치 직후 사용자가 가장 먼저 치는 명령이 "없는 명령"이다.**

**F12 (P1). 설치가 실제로 작동하는지 확인시키는 단계가 없다.**
quick-start 는 "이걸 해보세요" 4줄로 끝나고, 성공 판정 기준이 없다. Hermes 는 첫 채팅 실행 + 성공 기준 4개(모델 배너 표시 / 응답 / 툴 호출 / 멀티턴)를 명시한다. 우리는 `/hm:health` 라는 좋은 검증 명령이 있는데도 quick-start 에 넣지 않았다.

---

## 3. Hermes 대조표

| Hermes | harness-maker 현재 | 판정 |
|---|---|---|
| `hermes setup` 위저드 + `[model\|tts\|terminal\|gateway\|tools\|agent]` 섹션 점프 | `/hm:configure` 존재하나 second_opinion/autopilot/locale 누락 | 부분 (F3) |
| 3-path 온보딩: Portal(빠름) / Full / Blank slate | 3-path: Looks right / Adjust / Full setup | **동등** ✅ |
| 설치 시 OS 감지 + 요구사항 검증(모델 컨텍스트 ≥64k) | 프로젝트 프로파일만 감지, 도구 설치 여부 감지 0 | 격차 (F2) |
| 40+ 프로바이더 중 **선택지 제시** | second_opinion 은 free-text | 격차 (F6) |
| `--quick` (이미 설정된 항목 건너뜀), `--reconfigure`, `--non-interactive` | `Update` / `Full reconfigure` / `--ci`·`--autoloop` | **동등** ✅ |
| 재실행 시 현재값이 default, Enter 로 유지 | 재렌더 메뉴가 현재 설정 표시 (`make.md:104-107`) | **동등** ✅ |
| `hermes doctor [--fix]` — 미설정/문제 진단 | `/hm:health` — 켜진 축만 점검, `--fix` 없음 | 부분 (F4) |
| `hermes status` / `hermes dump` (지원용 요약) | `/hm:health` 일부 + `Audit only` | 부분 |
| `hermes config get/set <key>` 단일 값 변경 | 없음 (yaml 직접 편집) | 격차 |
| 첫 실행 검증 + 성공 기준 명시 | 없음 | 격차 (F12) |

핵심 시사점 하나: Hermes 는 **"검증 → 제안 → 확인"** 이 기본 흐름이다 (모델 컨텍스트를 재고 부족하면 막고, OS 를 보고 설치 방법을 고른다). 우리는 **"사용자가 고른 뒤 검증"** 이라 제안이 원천적으로 불가능하다. F2 가 그 구조적 근원이다.

---

## 4. 권고 (우선순위)

### P0 — 첫인상을 직접 깨는 것

1. **`make.md:601` 의 `/hm:ai-readiness` → `/hm:health` 로 수정.** 1줄. 즉시.
2. **환경 감지를 `profile` 에 추가.** `profile --json` 출력에 `available_tools: {codex: bool, agy: bool, cursor: bool, obsidian_vault: path|null}` 필드 신설. `shutil.which` 3회 + 홈 디렉토리 1회 스캔이면 끝. 결정성 유지를 위해 렌더 경로가 아니라 **인터뷰 시점에만** 호출 (ADR-007 의 antigravity 선례와 동일 규칙).
3. **감지 결과를 "Looks right" 요약 화면에 반영.** 감지된 도구가 있으면 요약에 한 줄 추가 + **그 축만 조건부로 1문항 질문**:
   > 감지: `codex` CLI 설치됨. 리뷰/플랜에 교차모델 세컨오피니언 투표를 붙일까요? (리뷰 1회당 CLI 호출 1회 추가 / 미인증·레이트리밋 시 자동 스킵)
   > → 켜기(codex) / 켜기(codex+antigravity) / 끄기

   감지된 게 없으면 질문 0개 유지 — "Looks right 는 빠르다"는 성질을 깨지 않는다.
4. **묻지 않은 축의 default 를 요약 화면에 전부 표시** (F1 표 그대로 8줄). 질문을 늘리지 않고 침묵만 없앤다. 가장 싸고 효과가 큰 개선.

### P1 — 복구 경로

5. **`/hm:configure` 메뉴에 `second_opinion` / `autopilot` / `locale` 항목 추가.** CLI 플래그는 이미 있다 (`--second-opinion-models`, `--autonomy-level`, `--locale`) — 템플릿 메뉴 항목과 dispatch 분기만 추가하면 된다. 이게 있어야 F9 의 "나중에 정할래" 선택지가 정직해진다.
6. **`/hm:health` 에 역방향 advisory 추가.** `second_opinion.models` 가 비었더라도 `codex`/`agy` 가 PATH 에 있으면 1줄 안내(`/hm:configure` 로 켜는 법). autopilot 도 동일.
7. **second_opinion 질문을 선택지형으로.** TTY 쪽 `_ask_second_opinion` 을 번호 선택 + 설치 여부 표시(`codex ✓ 설치됨` / `antigravity ✗ 미설치 — 켜면 스킵됨`)로. 오타 입력은 조용한 무시 대신 재질문.
8. **`consensus` / `caching` 에 설명 부여**하거나, 설명할 가치가 없으면 **인터뷰에서 제거**하고 preset 파생으로 내린다. 지금은 "설명 없이 묻는" 최악의 중간 상태다.
9. **quick-start 에 검증 단계 추가.** `/hm:health` 를 첫 줄로 올리고 "초록이면 설치 성공" 성공 기준을 명시.

### P2 — 마찰 줄이기

10. Full setup 14문항 → `AskUserQuestion` 다문항 묶음 4~5회로 재편 (기본축 / 리뷰축 / 경로축 / 고급축).
11. `ref_folders` / `sibling_repos` / `wrapup_docs` 를 free-text 구분자 대신 **감지된 후보의 다중 선택**으로. `ls ..` 제안은 이미 문서에 있으니(`make.md:258`), 이를 실제 선택지로 승격.
12. 각 질문에 "지금은 건너뛰기 — `/hm:configure` 로 나중에" 선택지 명시 (권고 5 이후에만 정직해짐).

---

## 5. 열린 질문

- **Q1.** `consensus` / `caching` 축은 살릴 가치가 있나? 살린다면 어떤 값이 유효하고 무엇이 달라지는가 (문서에 정의를 못 찾음). 제거가 낫다고 보이나 사용자 판단 필요.
- **Q2.** P0-3 의 조건부 질문을 second_opinion 외에 어디까지 확장할까? 후보: Cursor 설치 감지 → `targets` 확인, Obsidian vault 감지 → Second Brain 확인. 감지된 도구 수만큼 질문이 늘어나므로 상한(최대 2문항?)이 필요.
- **Q3.** `hermes config get/set` 등가물(`harness-maker config set second_opinion.models codex`)을 만들 가치가 있나, 아니면 `/hm:configure` 확장으로 충분한가?

## 6. 출처

- [Hermes Agent — CLI Commands Reference](https://hermes-agent.nousresearch.com/docs/reference/cli-commands)
- [Hermes Agent — Quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)
- [Hermes Agent — Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)
- [NousResearch/hermes-agent (GitHub)](https://github.com/nousresearch/hermes-agent)
