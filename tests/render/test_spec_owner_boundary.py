"""SPEC-spec-owner-boundary: /hm:spec asks the owner-only scope boundary and skips less."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

_ARGS = ("--autoloop", "--targets", "claude-code,codex", "--locale", "en")
_PATHS = {"claude": ".claude/commands/hm/spec.md", "codex": ".agents/skills/hm-spec/SKILL.md"}
ARMS = {
    "side": ("--preset", "Side"),
    "prod": ("--preset", "Production"),
    "side-minimal": ("--preset", "Side", "--comprehension-depth", "minimal"),
    "side-deep": ("--preset", "Side", "--comprehension-depth", "deep"),
}

#: SPEC AC-001, verbatim.
SKIP_RULE = (
    "Skip the interview only when all five hold: one file or config (docs count, tests do not); "
    "acceptance obvious from the title; no API, IPC, schema, file-format, CLI-output or "
    "user-facing message change; reversible within an hour with no user impact; no open "
    "**Boundary** (Step 2). A detailed ask is not a small one; when unsure, interview."
)
#: SPEC AC-002, verbatim.
BOUNDARY_RULE = (
    "**Boundary.** Before the SPEC, read the code the ask touches: which inputs take the new "
    "behaviour, which keep the old, and which existing behaviour must stay? If neither the ask "
    "nor the code settles that, ask the DRI in round 1: one question, recommendation first."
)

Renders = Callable[[str], Path]


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Renders:
    cache: dict[str, Path] = {}

    def get(arm: str) -> Path:
        if arm not in cache:
            base = tmp_path_factory.mktemp(f"owner-boundary-{arm}")
            project = init_project(base / "proj")
            proc = run_make(project, (*_ARGS, *ARMS[arm]), src=HEAD_SRC, home=base / "home")
            assert proc.returncode == 0, proc.stderr[-2000:]
            cache[arm] = project
        return cache[arm]

    return get


def _step(text: str, heading: str) -> str:
    start = text.index(f"## {heading}")
    nxt = text.find("\n## ", start + 1)
    return text[start : nxt if nxt != -1 else len(text)]


@pytest.mark.parametrize("runtime", list(_PATHS))
@pytest.mark.parametrize("arm", list(ARMS))
def test_ac_001_skip_check_has_five_conditions(arm: str, runtime: str, rendered: Renders) -> None:
    text = (rendered(arm) / _PATHS[runtime]).read_text(encoding="utf-8")
    step0 = _step(text, "Step 0")
    assert step0.count(SKIP_RULE) == 1
    assert "all four hold" not in text
    assert step0.index(SKIP_RULE) < step0.index("--exempt")


@pytest.mark.parametrize("runtime", list(_PATHS))
@pytest.mark.parametrize("arm", list(ARMS))
def test_ac_002_boundary_before_the_interview(arm: str, runtime: str, rendered: Renders) -> None:
    text = (rendered(arm) / _PATHS[runtime]).read_text(encoding="utf-8")
    assert text.count(BOUNDARY_RULE) == 1
    interview = _step(text, "Step 2")
    assert BOUNDARY_RULE in interview
    assert interview.index(BOUNDARY_RULE) < interview.index("Ask only what the DRI owns")
