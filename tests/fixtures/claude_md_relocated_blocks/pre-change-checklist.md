## 무언가를 고치거나 개선하기 전에 — 필수 체크리스트

> **이 섹션은 다음 fix/feature 시작 전에 반드시 읽고 통과시킬 것.**
> 0.1.0 → 0.3.5 patch 5번을 거치며 같은 패턴의 실수가 반복됨. 매번
> 회귀 테스트가 잡아주는 게 아니라 **구현 전에 8개 체크포인트를
> 통과**해야 다음에 같은 함정 안 밟음.

각 체크포인트는 "현실에서 한 번 깨졌던 사례 + 그래서 다음엔 어떻게
미리 잡을지" 형태. 새 PR 의 description 에 **각 항목 OK/N-A 표기 권장**.

### 1. 사용자 상태 보존 계약을 먼저 그려라
사용자 디스크에 쓸 때마다 묻는다: **"이 write 가 사용자가 손댄 무엇을
지울 수 있나?"** 답이 "있다" 면 보존 정책 설계 필수.
- 0.3.0: block-merge marker (`@hm:user:*` 안의 사용자 추가가 템플릿
  업그레이드를 견디게)
- 0.3.1: `settings.json` shallow merge (Claude Code 가 쓴 `enabledPlugins`
  보존)
- 0.3.2: `answers_from_harness_yaml` (재렌더 시 인터뷰 답변 silent 재사용)
패턴: **policy flag (default = preserve user) + slash 명령에서
`AskUserQuestion` 으로 의도 묻기**.

### 2. 외부 소비자 정합성 확인 — 전처리 + parser
우리가 렌더하는 파일은 우리가 아니라 **다른 도구가 읽음**. 그 도구의
parser 가 받아들이는 형식을 따라야 하고, **parser 앞단에서 내용을 바꾸는
전처리기가 있는지도** 확인해야 한다.

> **두 층은 탐지 방법이 다르다.** parser 문제는 파일을 읽으면 잡힌다
> (`settings.json` 에 frontmatter 가 박혀 있다 — 보면 안다). **전처리 문제는
> 파일을 읽어서는 절대 안 잡힌다** — 디스크의 내용은 옳고, 실행되는 내용만
> 다르다. render-grep 테스트는 전부 통과한다. **실제 호출의 결과값을
> 대조해야만** 보인다.
- `settings.json` → Claude Code 가 pure JSON 으로 기대 (YAML frontmatter
  prefix 박으면 permissions 무시됨, 0.3.1 fix)
- `hooks/hooks.json` → jq-parseable pure JSON
- `lib/*.sh` → bash 가 `---` 를 명령으로 해석, frontmatter 금지
  (`_render_pure_text`)
- `.cursor/rules/*.mdc` → Cursor 가 frontmatter 로 `description`, `globs`,
  `alwaysApply` 만 인식. 우리 `content_hash` 등 추가 필드를 strict-reject
  하는지는 Phase 1 검증 결과 따름. reject 시 `_render_cursor_mdc()`
  분기에서 우리 메타는 별도 sidecar (`.hm-meta.yaml`) 로 분리 고려.
- `.cursor/mcp.json` → Cursor pure JSON, frontmatter 금지
- `.cursor-plugin/plugin.json` / `.claude-plugin/plugin.json` → 두
  marketplace 가 schema 검증. 알 수 없는 필드는 일반적으로 무시되나
  manifest 표준 외 키 추가 금지.
- `.claude/harness.yaml` → 렌더러가 **provenance YAML frontmatter** 를
  prefix 로 박는다 (`generated_by`, `content_hash`, …). 결과 파일은
  multi-document YAML stream 이므로 단일 `yaml.safe_load` 는 거부한다.
  새 reader 는 `harness_maker.io_utils.load_harness_yaml()` 헬퍼를 쓰거나,
  `safe_load_all` 의 마지막 non-empty mapping 을 사용해야 한다.
  Reverse mapper: `interview.answers_from_harness_yaml`.

- **슬래시 명령 본문** (렌더된 `.claude/commands/hm/*.md` **와** 플러그인 자신의
  `commands/*.md` 양쪽) → Claude Code 가 모델에게 넘기기 **전에** 인자를 치환한다.
  `$0`–`$9` 는 인자로 대체되므로 셸/awk 의 위치 매개변수를 쓸 수 없다
  (`$ARGUMENTS` 가 지원되는 방식). **2026-07-26 실측**: `/hm:make --update` 에서
  디스크의 `awk '{print $NF, $0}'` 가 호출 시 `awk '{print $NF, --update}'` 가 되어
  `HM=-8` → `uv run --with "-8"` 실패 → **하드코딩된 구버전 pin 으로 fallback**.
  그 줄의 존재 이유가 정확히 그 stale-pin 함정을 피하는 것이었다. 같은 함정이
  `/hm:review`·`/hm:plan` 의 `awk '{s+=$1}'` 에도 있었고, 그 값은
  `high_diff classify --added-lines` 로 가서 **second-opinion 발동 여부**를
  결정한다. 그리고 플러그인 자신의 `commands/make.md` — **신규 설치의 진입점** —
  에도 같은 줄이 있었는데, 렌더된 명령만 스캔하던 첫 게이트가 놓쳤다.
  게이트: `tests/structural/test_no_positional_params_in_commands.py`
  (렌더 산출물 + 플러그인 자체 표면 양쪽).

새 파일 종류 추가 시 두 가지를 확인한다:
1. **누가 읽는지** + 그 reader 가 frontmatter 를 허용하는지. 안 되면
   `_is_pure_text` / `_is_hooks_json` 같은 디스패치 분기 추가.
2. **그 소비자가 읽기 전에 내용을 바꾸는지.** 바꾼다면 디스크의 파일을 검사하는
   테스트로는 절대 잡을 수 없다 — 실제 호출을 한 번 돌려 결과값을 대조하는
   테스트가 있어야 한다. 게이트를 만들 때는 **자기가 고치던 산출물에만 범위를
   맞추지 말 것** — 같은 결함이 자기 수정을 피해 살아남는다 (위 `commands/make.md`).

### 3. 설정 precedence 의식
Claude Code 는 `~/.claude/settings.json` (user) → `<project>/.claude/settings.json`
(project) → `<project>/.claude/settings.local.json` 순으로 우선 적용. **하위
레벨에 키를 쓰면 상위가 가려짐**.
- 같은 패턴: `permissions`, `env` 도 project 가 user-global 을 가림
- Cursor 도 동일 패턴: enterprise → team → project (`<root>/.cursor/`) → user (`~/.cursor/`)

새 키 쓰기 전에 상위 레벨에 같은 키 있는지 확인. 있으면 keep / combine /
overwrite 분기 줄지 결정.

### 4. CLI 와 slash 명령의 책임 분리
- **CLI** (`harness_maker.cli`) = flag-driven, no stdin/AskUserQuestion.
  테스트 가능, CI 안전, 슬래시 명령에서 호출 가능
- **Slash 명령** (`commands/*.md`, `templates/commands/hm/*.md.j2`) = 사용자
  intent 수집 (`AskUserQuestion`) → CLI 에 적절한 flag 조합으로 dispatch

CLI 에 `input()` / `AskUserQuestion` 박지 말 것 — 슬래시 명령 컨텍스트에는
stdin 이 안 통해 hang. 0.3.2 의 non-tty fallback 도 같은 원리.

### 5. 자동-업그레이드 vs 보존 분기 (fingerprint 기반)
사용자 파일에 박힌 값을 만질 때: **이게 우리가 박은 거냐 사용자가 박은
거냐** 를 fingerprint 로 판정.
- `content_hash` 비교: frontmatter hash 가 일치하면 "ours" → 자동 업그레이드.
  다르면 "theirs" → KEEP.
- explicit policy 가 있으면 자동-업그레이드 무시 + policy 우선.

같은 fingerprint 패턴이 필요할 만한 곳: 사용자 hooks.json, 사용자 추가
agent/skill 파일. 그 위치에 우리 출력 박을 때 fingerprint set 만들어두면
나중에 업그레이드 깔끔.

### 6. 양방향 매퍼 (write 한 건 read 도 가능해야)
디스크에 persist 하는 모든 포맷은 **reverse mapper** 가 있어야 추후
재사용 가능.
- `synthesize.py` → `harness.yaml` 쓰기
- `interview.answers_from_harness_yaml` → `harness.yaml` 읽어서 InterviewAnswers
  복원 (0.3.2)
- `render.py` → frontmatter 에 `content_hash`
- `reconcile.py` → 같은 hash 로 KEEP/REPLACE 결정

새 persist 포맷 도입 시 "이걸 다음 번에 누가 읽을까?" 답이 있어야 함.
Schema gap (옛 버전 파일에 새 키 없음) 은 default fallback 으로 처리.
예: `targets` 키 없는 옛 harness.yaml → `[claude-code]` silent fallback +
경고 로그.

### 7. 테스트 결정성 + 환경 격리
사용자 환경 (HOME, env vars, 시계) 을 읽는 코드는 **테스트에서 격리** 필수.
안 그러면 개발자 머신 의존 + CI 비결정적.
- `freeze_time` (0.1.x): `generated_at` 결정적
- `Path.home()` mocking (0.3.5): test 가 개발자의 `~/.claude/settings.json`
  에 의존하지 않게
- `regenerate.py` 도 HOME pin: snapshot 결정성
- LLM mock: `mock_anthropic_client` fixture
- 외부 API: `INTEGRATION=1` 가드

새 코드가 환경 변수 / HOME / 외부 API / 시계 읽으면 **autouse fixture 또는
명시 monkeypatch** 추가가 PR 의 일부.

### 8. Integration 경계 한 줄 테스트
unit test 다 통과해도 **integration 경계** (CLI 실행, 외부 도구 호출,
파일 시스템 효과) 가 깨질 수 있음.
- 예: 모듈 import 는 통과해도 `uv run` 으로 다른 cwd 에서 실행하면 실패.
  unit 으론 못 잡음 → `tests/e2e/test_plugin_live.py` 로 실제 claude 바이너리
  호출해서 검증.
- **Cursor target 추가 시**: 사용자는 Cursor IDE 사용 (CLI 사용 X). e2e
  자동화는 IDE 기반이라 어렵고 **manual 검증이 default**. CI 에서는
  unit + snapshot test 로 디스크 산출물 (frontmatter 형식, parser 정합성,
  render 결정성) 을 최대한 잡음. IDE 인식 여부 (slash 명령 표시,
  agent dispatch, hook fire, skill auto-load) 는 manual 체크리스트로
  README 또는 `tests/cursor-compat/MANUAL_CHECKLIST.md` 에 명시.

새 사용자-경계 코드 (CLI 명령, 슬래시 명령, hook) 는 **bash 또는
subprocess 로 실제 실행하는 e2e 한 케이스** 라도 추가.
