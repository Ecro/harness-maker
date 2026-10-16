"""A stage's text as the model meets it.

Until 0.63.0 the stage commands read part of their text on demand from `.claude/hm/*.md`, and this
module expanded those pointers in place. SPEC-hm-overhaul-p1 folded every helper back into its stage
(`.claude/hm/` no longer renders), so a stage's text is its command file. The helpers keep their
signatures so the tests that read a stage through here need no edit.
"""

from __future__ import annotations

from pathlib import Path

#: No stage reads a reference file since 0.64.0.
STAGE_REFERENCE_FILES: dict[str, tuple[str, ...]] = {}


def expand_references(command: str, ref_dir: Path) -> str:
    """The command unchanged; a leftover `.claude/hm/` pointer is a render bug, so it fails."""
    del ref_dir
    strays = [ln for ln in command.splitlines() if "`.claude/hm/" in ln]
    assert not strays, f"a stage still points at .claude/hm/: {strays[0][:120]}"
    return command


def stage_text(claude_dir: Path, stage: str) -> str:
    """`<claude_dir>/commands/hm/<stage>.md`."""
    command = (claude_dir / "commands" / "hm" / f"{stage}.md").read_text(encoding="utf-8")
    return expand_references(command, claude_dir / "hm")
