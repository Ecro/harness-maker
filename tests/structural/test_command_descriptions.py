"""Phase 4 / ADR-016 — every rendered `/hm:` command carries a frontmatter `description:`.

Without one, Claude Code and Cursor fall back to the command's first body line, and 14 of
the 15 commands present the identical string in the tool listing.

ADR-016 requires the per-target parser question to be ANSWERED before the field ships,
not assumed. The answer, established by rendering all three targets rather than by reading
the code: **commands render to exactly one file family**, `.claude/commands/hm/*.md`, which
Claude Code and Cursor both read natively and for which `description` is a documented
frontmatter key. Neither the Codex TOML path (`.codex/agents/*.toml`, agents only) nor
`_render_cursor_mdc` (`.cursor/rules/*.mdc`) receives a command, so no target-conditional
rendering is needed. `test_no_target_renders_a_command_outside_the_claude_path` pins that
premise — if a future release adds `.codex/commands/`, this file fails and the parser
question is re-opened rather than silently answered wrong.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_ALL_TARGETS = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]


def _blueprint(preset: Preset = Preset.PRODUCTION) -> Any:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True).model_copy(update={"targets": _ALL_TARGETS})
    return synthesize(profile, answers, preset=preset)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("desc")
    render(_blueprint(), out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    end = text.index("\n---\n", 4)
    parsed = yaml.safe_load(text[4:end])
    assert isinstance(parsed, dict)
    return parsed


def _command_paths(root: Path) -> list[Path]:
    return sorted((root / "commands" / "hm").glob("*.md"))


def test_every_rendered_command_has_a_non_empty_description(rendered: Path) -> None:
    paths = _command_paths(rendered)
    # Non-vacuity: a mistyped glob would make an all-pass loop over zero files.
    assert len(paths) >= 15, [p.name for p in paths]
    missing = [p.name for p in paths if not str(_frontmatter(p).get("description", "")).strip()]
    assert missing == []


def test_descriptions_are_single_line_and_bounded(rendered: Path) -> None:
    """A tool listing shows one line — a paragraph there is worse than the fallback."""
    for path in _command_paths(rendered):
        desc = str(_frontmatter(path)["description"])
        assert "\n" not in desc, path.name
        assert len(desc) <= 120, (path.name, len(desc))


def test_descriptions_are_distinguishable(rendered: Path) -> None:
    """Uniqueness is ADVISORY per ADR-016 — asserted here, but as the whole point.

    ADR-016 declined to make uniqueness a *build* gate for a cosmetic collision. This test
    is the advisory made visible: the entire reason the field exists is that 14 commands
    were indistinguishable, so a duplicate should be seen, not silently shipped.
    """
    descs = [str(_frontmatter(p)["description"]) for p in _command_paths(rendered)]
    dupes = {d for d in descs if descs.count(d) > 1}
    assert dupes == set()


def test_no_target_renders_a_command_outside_the_claude_path() -> None:
    """The premise ADR-016's parser answer rests on. See this module's docstring."""
    paths = [str(f.path) for f in _blueprint().files]
    assert len(paths) > 50  # non-vacuity
    stray = [p for p in paths if "commands/" in p and not p.startswith("commands/hm/")]
    assert stray == []


def test_the_description_survives_into_a_side_preset_render(tmp_path: Path) -> None:
    """The other preset renders a different command set; both must carry the field."""
    render(_blueprint(Preset.SIDE), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    paths = _command_paths(tmp_path)
    assert len(paths) >= 15
    assert all(str(_frontmatter(p).get("description", "")).strip() for p in paths)
