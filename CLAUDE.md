# CLAUDE.md — harness-maker

> 이 파일은 Claude / autoloop CODER agent 가 본 프로젝트에서 작업할 때 따라야 하는 규칙·관례 모음. **모든 결정은 사용자가 사전에 lock-in 했음.** autoloop 빌드 중에는 AskUserQuestion 호출 금지 — 모호하면 본 문서 + TECH_SPEC.md 우선.

## LLM 활용 원칙 (최우선)

harness-maker 는 Claude Code 의 플러그인으로, **LLM 판단력을 최대한 활용하여 품질을 극대화**한다.

- **규칙 기반 대신 LLM 판단**: 패턴 매칭·키워드 필터로 해결할 수 있는 것도, LLM 이 더 정확하게 판단할 수 있으면 LLM 에 위임
- **모호함 감지**: 답변이 충분히 actionable 한지 판정은 LLM 이 직접 수행 (regex 로 vague 판정 금지)
- **질문 생성**: 인터뷰 follow-up 질문은 LLM 이 컨텍스트를 읽고 동적으로 생성 (고정 스크립트 금지)
- **추출·요약**: 소스 문서에서 목적·불변조건·우선순위 등을 뽑는 작업은 LLM 이 전체 문서를 읽고 추출
- **수렴 판단**: stopping criteria 만족 여부는 LLM 이 현재 상태를 읽고 판단

템플릿(`.j2`)이 생성하는 슬래시 명령 안에서 Claude 가 직접 판단·추출·생성하도록 프롬프트를 설계할 것. Python 레이어는 타입 계약·저장·안전 레일만 담당.

## 프로젝트 정체성
- **이름**: harness-maker (Claude Code 플러그인)
- **단일 메타 명령**: `/harness-maker:make` (audit/add/remove/promote 플래그)
- **사용자 명령은 `/hm:` prefix** — `.claude/commands/hm/<name>.md` → `/hm:<name>`
- **언어**: English-default (locale=en 디폴트). interview 첫 질문이 locale (free-text). 한국어 등 다른 locale 도 입력 가능, unknown locale 은 en 으로 silent fallback

## 기술 결정 (변경 금지)

### Runtime / Tooling
- **언어**: **Python only** (Bash 사용 금지). Statusline 등 hook 도 `python -m harness_maker.<module>` 호출.
- **Python**: 3.12+
- **Package manager**: `uv` + `pyproject.toml` + `uv.lock`
- **Test**: `pytest`
- **Lint + Format**: `ruff check` + `ruff format`
- **Type**: `mypy --strict`
- **Template engine**: `Jinja2`
- **License**: MIT
- **Version 시작**: `0.1.0`
- **CI**: GitHub Actions (lint + test on PR)

### Plugin 구조 (Claude Code 공식 spec)
- `.claude-plugin/plugin.json` — manifest
- `skills/<name>/SKILL.md` — 공식 위치 (loose md 금지)
- `commands/<name>.md` — 슬래시 명령
- `hooks/hooks.json` — 단일 파일에 정의
- `lib/` — 내부 헬퍼
- `templates/` — 사용자 `.claude/` 로 렌더되는 자산

### 사용자 하네스 구조 (= 우리 templates/ 가 렌더하는 결과)
- `.claude/harness.yaml` — single source of truth
- `.claude/commands/hm/<name>.md` — 모든 생성 명령 (`/hm:` prefix)
- `.claude/skills/`, `.claude/agents/`, `.claude/hooks/hooks.json`, `.claude/lib/`, `.claude/observability/`
- `.worktrees/` (gitignored)

## 코드 스타일
- 파일 상단 docstring 1줄 (모듈 목적)
- 함수 docstring: WHY only (WHAT 은 코드가 말함)
- 주석 최소 — non-obvious 만
- 변수명은 영어. 사용자 출력은 locale 따름.
- 에러 메시지: locale 따라 분기 (en/ko 빌트인, 그 외 en fallback). system error 는 영어 그대로 + 현재 locale 요약

## 테스트 정책
- 모든 LLM 호출은 **subscription 통해 실제 호출 가능** (Anthropic API 결제 X — Claude Code 환경)
- 단위 테스트는 mock 우선 (속도)
- Integration / e2e 는 실제 호출 가능 (test fixture 안에서)
- 외부 API (arxiv, GitHub, OSV.dev) 는 mock + 캐시. 실제 호출은 `INTEGRATION=1` env 시만.
- GitHub API 는 unauthenticated (60/h) + `~/.cache/harness-maker/` 캐시 공유

## Git 정책
- 커밋 메시지: `<type>: <short subject>` 또는 autoloop 자동 형식 `autoloop(harness-maker): phase N - <name>`
- type: `feat | fix | chore | ci | test | docs | refactor`
- **Remote**: `git@github.com-personal:Ecro/harness-maker.git` (private). push 허용 — backup 용도.
  - 사용자가 명시적으로 요청해야 push (자동 push 금지).
  - public 공개 시점·조건은 별도 결정 (현재는 private 유지).
- 로컬 author: `Ecro <e839638@gmail.com>` (project-scoped git config).
- 모든 phase 완료 시 자동 commit (autoloop wrapup stage). push 는 별도.

## 버전업 정책

버전 번호는 **세 파일을 동시에** 수정해야 한다. 하나라도 빠지면 `/plugin update` 가 잘못된 버전을 보고함:

| 파일 | 역할 |
|------|------|
| `.claude-plugin/plugin.json` | `/plugin update` 가 읽는 기준 버전 |
| `pyproject.toml` | Python 패키지 버전 |
| `src/harness_maker/__init__.py` | `__version__` 런타임 값 |

> **왜:** Claude Code 의 `/plugin update` 는 `plugin.json` 의 `version` 필드를 기준으로 최신 여부를 판단한다. `pyproject.toml` 을 올려도 `plugin.json` 이 구버전이면 "already at latest" 로 오보한다. (0.4.9 릴리스 시 발견)

## 보안 / 권한 (v1.6)
- Reviewer agent (code, security, perf, ux, concurrency) — `permissions.allow: [Read(*), Grep(*), Bash(git diff:*), Bash(git log:*)]`, `deny: [Write(*), Edit(*), Bash(rm:*), Bash(curl:*), Bash(npm:*)]`
- Executor agent — `allow: [Write(.worktrees/**), Edit(.worktrees/**), Bash(<test commands>:*)]`, `deny: [Write(/etc/**), Write(~/.ssh/**), Bash(curl * | sh), Bash(eval *)]`
- 모든 generated 파일은 frontmatter 에 `generated_by + content_hash + source_template + harness_maker_version`

## Context Lint (v1.6)
- CLAUDE.md ≤ Side 200행 / Production 500행
- agent prompt ≤ Side 100행 / Production 200행
- skill SKILL.md ≤ Side 50행 / Production 150행
- 초과 시 renderer 가 warn

## Workflow (autoloop CODER 가 알아야 할 점)
- **Atomic stage**: 7개 (research/spec/plan/execute/review/wrapup/verify)
- **Workflow** = 사용자 명명 fused stage 시퀀스 → 1 명령 1 turn
- Renderer 가 stage prompt fragment 들을 합성해 단일 명령 파일 생성

## 실행 주의
- WSL2 NTFS 환경 인지 (vault 경로). Edit 대신 Write 강제 시점 있음.
- Worktree base_dir 는 `.worktrees/` (.gitignore 자동 추가)
- 100% 로컬 telemetry — 외부 전송 금지

## Autoloop 빌드 중 모호함 발생 시
1. TECH_SPEC.md Section 4 의 phase task 우선
2. 본 CLAUDE.md 우선
3. `docs/reference/autoloop-pattern.md` 의 autonomous decision protocol (DD#8) 따름 — log 후 진행
4. **AskUserQuestion 호출 금지**

## 구현 패턴 (CODER 가 따라야 할 코드 관례)

### Atomic file write (디스크 corrupt 방지)
모든 파일 write 는 atomic 패턴 강제:
```python
import os, tempfile
from pathlib import Path

def atomic_write(path: Path, content: str) -> None:
    """tempfile + os.rename — 인터럽트 시 corrupt 0."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)  # atomic on POSIX + Windows
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
```
plain `open(path, "w")` 사용 금지 (단, 명백히 임시 디렉토리 안에서만 OK).

### LLM mock 패턴 (테스트 결정성)
사용자 정책: 실제 호출은 Claude Code subscription 통해 가능하지만, **단위 테스트는 mock 우선** (속도·결정성).

```python
# tests/unit/conftest.py
import pytest
from anthropic.types import Message, TextBlock, Usage

@pytest.fixture
def mock_anthropic_client(monkeypatch):
    """Claude SDK 호출을 deterministic mock 으로 대체."""
    class _MockClient:
        def __init__(self, *_a, **_kw): ...
        @property
        def messages(self):
            return self
        def create(self, *_a, **_kw):
            return Message(
                id="msg_test",
                type="message",
                role="assistant",
                model="claude-opus-4-7",
                content=[TextBlock(type="text", text='{"applicability_score": 0.85, "risk": "low"}')],
                stop_reason="end_turn",
                stop_sequence=None,
                usage=Usage(input_tokens=10, output_tokens=20),
            )
    monkeypatch.setattr("anthropic.Anthropic", _MockClient)
    return _MockClient
```
Integration test 는 `tests/integration/` 에 두고 `pytest.mark.skipif(not os.getenv("INTEGRATION"))` 가드.

### Worktree cleanup 정책
- 정상 종료: `harness.yaml.worktree.cleanup` 따름 (default `on_success`)
- **autoloop iter / phase blocker 발생 시 강제 cleanup**: `worktree.cleanup_all(force=True)` 호출 → halt 전 모든 `.worktrees/*` 제거 (디스크 누적 방지). 단, `--debug-worktree` 플래그 시 보존.
- weekly cleanup hook: `/hm:refresh` 와 동시 실행되는 별도 함수가 24h 이상 stale worktree 청소.

### Snapshot test 결정성
Renderer 의 `freeze_time` 인자 적극 활용. snapshot 비교 시 `generated_at` 필드 마스크:
```python
def normalize_for_snapshot(text: str) -> str:
    """frontmatter 의 generated_at 만 마스크 (다른 필드는 결정적)."""
    return re.sub(r'^generated_at:.*$', 'generated_at: <FROZEN>', text, flags=re.M)
```

### 외부 명령 호출
- `subprocess.run(..., check=True, capture_output=True, text=True, timeout=N)` — timeout 필수
- shell=True 금지 (security_scanner 의 hook injection 검사가 자기 코드도 잡으면 안 됨)
- 외부 명령 실패 시 graceful fallback (예: GitHub API rate limit → empty result + 경고 로그)

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

### 2. 외부 소비자의 파서 정합성 확인
우리가 렌더하는 파일은 우리가 아니라 **다른 도구가 읽음**. 그 도구의
parser 가 받아들이는 형식을 따라야 함.
- `settings.json` → Claude Code 가 pure JSON 으로 기대 (YAML frontmatter
  prefix 박으면 permissions 무시됨, 0.3.1 fix)
- `hooks/hooks.json` → jq-parseable pure JSON
- `lib/*.sh` → bash 가 `---` 를 명령으로 해석, frontmatter 금지
  (`_render_pure_text`)

새 파일 종류 추가 시: 그 파일을 누가 읽는지 + 그 reader 가 frontmatter
허용하는지 먼저 확인. 안 되면 `_is_pure_text` / `_is_hooks_json` 같은
디스패치 분기 추가.

### 3. 설정 precedence 의식
Claude Code 는 `~/.claude/settings.json` (user) → `<project>/.claude/settings.json`
(project) → `<project>/.claude/settings.local.json` 순으로 우선 적용. **하위
레벨에 키를 쓰면 상위가 가려짐**.
- 같은 패턴: `permissions`, `env` 도 project 가 user-global 을 가림

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

새 사용자-경계 코드 (CLI 명령, 슬래시 명령, hook) 는 **bash 또는
subprocess 로 실제 실행하는 e2e 한 케이스** 라도 추가.

---

## 사용자 voice
- 직접적 (no preamble, no flattery)
- 우려 먼저, 동의 나중
- 동의 시 WHY 설명
- 새 증거 없이 fold 하지 않음
