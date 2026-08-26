# Implementation patterns (CODER conventions)

> Relocated verbatim out of `CLAUDE.md` (2026-08-26, PLAN-render-observability-audit ADR-004) to bring that file
> under its 500-line Production ceiling. Nothing was compressed or dropped — these are binding
> conventions, not background reading.

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
- 정상 종료: cleanup 은 **설정이 아니라 finalize 의 status 인자**가 결정한다. `cleanup(wt, on_success=True)` 는 force 제거(작업 복사본 무조건 삭제), `on_success=False` 는 non-force 제거(dirty 면 git 이 거부 — 의도된 안전망). **`harness.yaml.worktree.cleanup` 이라는 키는 존재하지 않는다** — 어떤 preset 템플릿도 렌더한 적 없고 어떤 코드도 읽지 않는다. 이 문서가 `(default on_success)` 라고 적어 설정 가능한 것처럼 읽히게 했던 것이 오류다 (PLAN-worktree-side-defaults 에서 확인).
- **autoloop iter / phase blocker 발생 시 강제 cleanup**: `worktree.cleanup_all(force=True)` 호출 → halt 전 모든 `.worktrees/*` 제거 (디스크 누적 방지). 단, `--debug-worktree` 플래그 시 보존.
- stale-artifact janitor: `prune_stale(base)` 가 **`worktree create` 시점에만** 실행된다 (`_cli_create`, `--debug-worktree` 시 skip). orphan `.hm-loop-*` 마커, dangling `.worktrees/*`, 그리고 finalize-stash ref 를 정리한다. ref drain 정책: stash object 가 이미 사라진(gc/drop) ref 는 즉시 제거(복원할 내용 없음), 살아있지만 내용이 HEAD 에 없는 ref 는 preserve+warn (PLAN-worktree-base-artifact-pollution ADR-005). **24h/주기 기반 hook 은 없다** — 예전 문서의 "weekly `/hm:health` cleanup" 주장은 코드에 존재한 적 없는 오류였다.
- orphan-branch sweep + **landed-marker** (PLAN-worktree-deliverable-blocks-create ADR-003/004): finalize 성공 시 `refs/hm-landed/v1/<branch>` 에 worktree 브랜치 tip SHA 를 기록한다 (`_write_landed_marker`, cleanup 직전·clean/dirty base 양쪽). `prune_stale` 의 브랜치 sweep 은 marker SHA == 현재 tip 이면 (worktree dir 부재 시) **content 재비교 없이** 삭제 — 후속 HEAD 편집에도 안전하고, 이름 충돌로 재생성된 동명 브랜치는 tip 이 달라 marker 불일치 → preserve-biased content-gate 로 빠진다. marker 없는 legacy 브랜치는 기존 `_branch_content_in_head` fallback. **모든 삭제 경로(marker-sweep, content-gate, `--force`)가 같은 op 에서 marker ref 도 삭제**하고, branch 없는 orphan `refs/hm-landed/v1/*` 는 prune 시 reap → ref 누적 0. create 시 preserved-branch 경고 벽은 **1줄 요약**으로 collapse (`_print_prune_warnings`).
- `prune-branches [--force]` CLI (ADR-004): 누적된 legacy `execute-*` 브랜치 backlog 를 정리. flag 없으면 `prune_stale` 와 동일 gate (marker/content 검증된 것만 sweep, 나머지는 `git log -p <branch>` 힌트와 함께 preserve). `--force` 는 markerless/diverged 브랜치까지 삭제하되 삭제 전 per-branch recovery 힌트를 출력 (reflog `wip(execute)` 커밋은 gc 윈도우까지 생존). `--force` 는 명시 파싱 (substring 검사 아님).
- **Cursor 와 공유 시 주의**: prefix 매치로 자기 것만 cleanup (`execute-*`, `plan-*`, `phase-*`, `autoloop-*`). Cursor 가 만든 worktree (다른 prefix) 는 건드리지 않음.

### 렌더 컨텍스트 플래그는 **출력 경로에서 파생**시킬 것 (`is_codex`, 2026-08-16)

`synthesize` 의 컨텍스트 빌더가 모든 파일에 `is_codex: False` 를 하드코딩하고 있었다. 근거는
"Codex 본문은 `_codex_stage_skills()` 가 미리 렌더한다" 였고, 절반만 맞았다 — 미리 렌더되는 건
**stage body** 뿐이고 그걸 감싸는 **wrapper** (`codex/stage_skill.md.j2` + 그것이 include 하는
partial) 는 빌더가 렌더한다. 그래서 **디스크의 Codex 파일 전부가 `is_codex=False` 로 생성**됐고,
wrapper-level partial 의 `{% if is_codex %}` 는 템플릿 소스만 보면 Codex 를 인식하는 것처럼 읽히면서
실제로는 항상 Claude 가지를 탔다. 실측 결과: autopilot picker 의 `not is_codex` 게이트는 한 번도
발화한 적이 없고, `stage_end_summary` 의 auto-advance 억제 게이트도 마찬가지여서 Codex stage skill 이
실행할 수 없는 `Skill` 자동 전환 블록을 싣고 나갔다.

교훈은 두 가지다. (a) **런타임 플래그는 손목록이 아니라 출력 경로에서 파생**시킨다
(`_is_codex_output` — `.codex/` · `.agents/` · `AGENTS.md`). 새 Codex 출력이 플래그를 조용히
놓치는 경로가 없어진다. (b) **이 결함은 render-grep 으로 절대 안 잡힌다** — 템플릿도 산출물도 모두
"정상"으로 읽히고, 틀린 건 컨텍스트뿐이다. 게이트는 blueprint 의 `FileEntry.context` 를 직접 보는
`tests/structural/test_is_codex_matches_output_path.py` 다.

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

### Communication variant policy (PLAN-antisycophancy-2026-05)

- 새 agent dispatcher template 추가 시 source frontmatter 에 `communication_variant: full|reframe|soft` **필수**. 누락 시 render 시 Jinja `UndefinedError` + `/hm:health` Layer 1 `communication_protocol` sub-check 가 actionable item 으로 surface (silent-miss = R4 canonical failure mode).
- 분류:
  - **FULL** — 일반 executor 형 (autoloop-coder, executor, stuck, trajectory-monitor — JSON output, REFRAME inapplicable).
  - **REFRAME** — reviewer / evaluator 형 (10 reviewer agents). FULL + "Input Processing" 섹션 (confirmation bias 완화).
  - **SOFT** — idea / brainstorm 형. 현재 consumer 없음 (dormant ship).
- Output frontmatter / TOML metadata 에는 키 노출 X — body 안 HTML comment 마커 `<!-- @hm:communication_variant: X -->` 로만 식별. Cursor `.mdc` / Codex TOML strict parser 호환 (ADR-004).
- Skill 도 동일 패턴, **4 LLM-judgment skill 만 적용** — agent-quality-rubric, ai-readiness-rubric, security-scanner, refdocs-search (ADR-005, reduced from 5 in 0.22.3 per ADR-0007). 7 procedural skill 제외.
- Render path: `render._extract_source_communication_variant` 가 pre-render 단계에서 source frontmatter 에서 regex 로 추출 (yaml.safe_load 는 `{{ name }}` 같은 Jinja expression 에 fail). Codex 는 dispatcher source 우회하므로 `synthesize._COMMUNICATION_VARIANT` table 명시.
- 변경 후 `/hm:health` 실행하여 silent-miss + source ↔ output drift 확인.
