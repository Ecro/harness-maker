# CLAUDE.md — harness-maker

> 이 파일은 Claude / autoloop CODER agent 가 본 프로젝트에서 작업할 때 따라야 하는 규칙·관례 모음. **모든 결정은 사용자가 사전에 lock-in 했음.** autoloop 빌드 중에는 AskUserQuestion 호출 금지 — 모호하면 본 문서 + TECH_SPEC.md 우선.

## 프로젝트 정체성
- **이름**: harness-maker (Claude Code 플러그인)
- **단일 메타 명령**: `/harness-maker:make` (audit/add/remove/promote 플래그)
- **사용자 명령은 `/hm:` prefix** — `.claude/commands/hm/<name>.md` → `/hm:<name>`
- **언어**: Korean-first (locale=ko 디폴트), English 지원

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
- 에러 메시지: locale=ko 일 때 한국어 (system error 는 영어 그대로 + 한국어 요약)

## 테스트 정책
- 모든 LLM 호출은 **subscription 통해 실제 호출 가능** (Anthropic API 결제 X — Claude Code 환경)
- 단위 테스트는 mock 우선 (속도)
- Integration / e2e 는 실제 호출 가능 (test fixture 안에서)
- 외부 API (arxiv, GitHub, OSV.dev) 는 mock + 캐시. 실제 호출은 `INTEGRATION=1` env 시만.
- GitHub API 는 unauthenticated (60/h) + `~/.cache/harness-maker/` 캐시 공유

## Git 정책
- 커밋 메시지: `<type>: <short subject>` 또는 autoloop 자동 형식 `autoloop(harness-maker): phase N - <name>`
- type: `feat | fix | chore | ci | test | docs | refactor`
- **No remote** (local commits only). push 금지.
- 모든 phase 완료 시 자동 commit (autoloop wrapup stage)

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

## 사용자 voice
- 직접적 (no preamble, no flattery)
- 우려 먼저, 동의 나중
- 동의 시 WHY 설명
- 새 증거 없이 fold 하지 않음
