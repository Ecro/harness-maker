"""SPEC-retired-text AC-001, 002, 004: renders describe what runs now, not retired machinery.

AC-003 (the `flush_session` status message on re-render) and the worktree-isolator and hook rows
of AC-001/AC-002 were superseded when SPEC-opus55-stale-cuts retired that skill and hook.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

PRESETS = ("Side", "Production")
RETIRED = re.compile(r"autoloop|autopilot|executor agent", re.I)
_ARGS = (
    "--autoloop",
    "--targets",
    "claude-code,codex",
    "--locale",
    "en",
    "--second-opinion-models",
    "codex",
)

#: Rendered from a touched template, per SPEC AC-001 (and their Codex copies).
TOUCHED = (
    ".claude/agents/consensus-arbiter.md",
    ".claude/agents/code-verifier.md",
    ".codex/agents/consensus-arbiter.toml",
    ".codex/agents/code-verifier.toml",
    ".claude/commands/hm/health.md",
    ".claude/skills/intent-layer/SKILL.md",
    ".agents/skills/intent-layer/SKILL.md",
    ".claude/skills/maker/SKILL.md",
    ".agents/skills/maker/SKILL.md",
    ".claude/settings.json",
    ".codex/hooks.json",
)
REPLACEMENTS = (
    (
        ".claude/agents/consensus-arbiter.md",
        # SPEC-hm-cost-p4 AC-007: the trigger no longer promises a severity resolution.
        "Invoked by the review step of `/hm:execute` to merge the second-opinion voters' findings",
    ),
    (
        ".claude/agents/code-verifier.md",
        "Findings are proposals; the main session applies them.",
    ),
    (".claude/commands/hm/health.md", "## Non-interactive behavior"),
    (
        ".claude/skills/intent-layer/SKILL.md",
        "`hm intent status` reports the approval you record",
    ),
)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def get(preset: str) -> Path:
        if preset not in cache:
            base = tmp_path_factory.mktemp(f"retired-{preset}")
            project = init_project(base / "proj")
            proc = run_make(project, (*_ARGS, "--preset", preset), src=HEAD_SRC, home=base / "home")
            assert proc.returncode == 0, proc.stderr[-2000:]
            cache[preset] = project
        return cache[preset]

    return get


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_001_touched_renders_have_no_retired_token(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    hits = {}
    for rel in TOUCHED:
        path = root / rel
        assert path.is_file(), f"{rel} not rendered"
        # The rendered install path is the checkout's, and a task worktree's name can
        # contain a retired token.
        text = path.read_text("utf-8").replace(str(HEAD_SRC.parent), "")
        found = sorted({m.group(0).lower() for m in RETIRED.finditer(text)})
        if found:
            hits[rel] = found
    assert hits == {}


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_002_replaced_texts_say_what_runs_now(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    for rel, text in REPLACEMENTS:
        assert text in (root / rel).read_text("utf-8"), rel


def _allowed_tools(text: str) -> list[str]:
    fm = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    return [t.strip() for t in re.split(r",\s*(?=Bash\()", fm["allowed-tools"])]


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("rel", [".claude/skills/maker/SKILL.md", ".agents/skills/maker/SKILL.md"])
def test_ac_004_maker_grants_and_runs_nothing_of_autopilot(
    preset: str, rel: str, rendered: Callable[[str], Path]
) -> None:
    text = (rendered(preset) / rel).read_text("utf-8")
    hm = re.search(r"`hm` below means `([^`]+)`", text)
    assert hm, "no hm prefix line"
    want = [
        t.format(hm=hm.group(1))
        for t in ("Bash({hm} world_model:*)", "Bash(tail:*)", "Bash(grep:*)", "Bash(printf:*)")
    ]
    frontmatter = text.split("\n---\n", 1)[0]
    if "allowed-tools" in frontmatter or rel.startswith(".claude/"):
        assert _allowed_tools(text) == want
    assert "autopilot" not in text.replace(str(HEAD_SRC.parent), "").lower()
