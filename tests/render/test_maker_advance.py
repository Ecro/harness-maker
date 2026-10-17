"""SPEC-maker-advance AC-001..004: Maker chains spec → execute → wrapup; stages never advance."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

PRESETS = ("Side", "Production")
_ARGS = ("--autoloop", "--targets", "claude-code,codex", "--locale", "en")
MAKER = {"claude": ".claude/skills/maker/SKILL.md", "codex": ".agents/skills/maker/SKILL.md"}
STAGE = {"claude": ".claude/commands/hm/{}.md", "codex": ".agents/skills/hm-{}/SKILL.md"}
_INVOKE = {"claude": "`/hm:{}`", "codex": "`$hm-{}`"}


def advance_rule(runtime: str) -> str:
    """SPEC AC-001, verbatim."""
    ex, wr = (_INVOKE[runtime].format(s) for s in ("execute", "wrapup"))
    return (
        "## Advance\n\n"
        "After a full-pipeline Start or Resume, when a stage reaches its final STOP, enter the "
        f"next,\nsame `<slug>`: {ex} after spec, {wr} after execute. Stop and report if it\n"
        "stopped earlier, an ask is unanswered, spec's status is not `approved`, the last "
        "`hm check` was\nnot 0, a finding is `unresolved`, or `## Queued asks` has entries. "
        "Never push.\n"
    )


def hand_off(runtime: str, nxt: str) -> str:
    """SPEC AC-003: the stage still names the next command."""
    cmd = _INVOKE[runtime].format(nxt)[:-1]
    return (
        f"{cmd} <slug>` is the user's call; if the world model began this run, enter it now "
        "unless its Advance rule stops."
    )


AGENTS_LINE = "the next one is the user's call, or the world model's under its Advance rule."


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def get(preset: str) -> Path:
        if preset not in cache:
            base = tmp_path_factory.mktemp(f"advance-{preset}")
            project = init_project(base / "proj")
            proc = run_make(project, (*_ARGS, "--preset", preset), src=HEAD_SRC, home=base / "home")
            assert proc.returncode == 0, proc.stderr[-2000:]
            cache[preset] = project
        return cache[preset]

    return get


def _makers(root: Path) -> Iterator[tuple[str, str]]:
    for runtime, rel in MAKER.items():
        yield runtime, (root / rel).read_text("utf-8")


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_001_maker_carries_the_advance_rule(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    counts = {rt: text.count(advance_rule(rt)) for rt, text in _makers(rendered(preset))}
    assert counts == {"claude": 1, "codex": 1}


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_002_resume_does_not_reserve_wrapup(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    for runtime, text in _makers(rendered(preset)):
        assert "`next_stage: wrapup` → ready to land." in text, runtime
        assert "the operator runs wrapup" not in text, runtime


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_003_hand_offs_name_next_command_and_world_model(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    for runtime, pattern in STAGE.items():
        for stage, nxt in (("spec", "execute"), ("execute", "wrapup")):
            text = (root / pattern.format(stage)).read_text("utf-8")
            assert hand_off(runtime, nxt) in text, (runtime, stage)
            old = _INVOKE[runtime].format(nxt)[:-1] + " <slug>` is the user's call."
            assert old not in text, (runtime, stage)
    assert AGENTS_LINE in (root / "AGENTS.md").read_text("utf-8")


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_004_choices_rule_single_blank_line(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    for runtime, text in _makers(rendered(preset)):
        assert "\n\n**Choices.**" in text, runtime
        assert "\n\n\n**Choices.**" not in text, runtime
