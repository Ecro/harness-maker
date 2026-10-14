"""A stage's text as the model meets it, with its on-demand reference files read in place.

Stage 2b (SPEC-hm-light-lane-s2b) moved the bodies of wrapup Steps 1-5.6, verify's checks,
review's auto-fix rounds and confirmation pass, and execute Phase A.5 out of the Claude commands
into `.claude/hm/*.md`. Most render tests assert on the text of one of those bodies, not on
where the Claude command keeps it, so they read the command through `stage_text`: each pointer
line is replaced by the block it points at. For review and execute that reproduces the pre-move
document order; the tests that ARE about the pointers read the command itself.
"""

from __future__ import annotations

import re
from pathlib import Path

#: The `.claude/hm/` files each stage command reads on demand for text it no longer carries.
STAGE_REFERENCE_FILES: dict[str, tuple[str, ...]] = {
    "wrapup": ("wrapup-steps",),
    "verify": ("verify-checks",),
    "review": ("review-autofix", "review-confirmation"),
    "execute": ("execute-a5",),
}
REF_START, REF_END = "<!-- @hm:ref:start -->\n", "<!-- @hm:ref:end -->"
_POINTER = re.compile(
    r"^Read `\.claude/hm/(?P<name>(?:wrapup-steps|verify-checks|review-autofix"
    r"|review-confirmation|execute-a5)\.md)` from the project root.*\n",
    re.M,
)
#: An INDENTED pointer is a reference, not the body's position (the wrapup receipt-mismatch bullet
#: sends the reader to the same file mid-list). It is checked against `ref_dir` but never expanded:
#: expanding it would put the block in Step 0.5, ahead of where the stage reads it.
_INLINE_POINTER = re.compile(
    r"^[ \t]+Read `\.claude/hm/(?P<name>(?:wrapup-steps|verify-checks|review-autofix"
    r"|review-confirmation|execute-a5)\.md)` from the project root.*$",
    re.M,
)


def expand_references(command: str, ref_dir: Path) -> str:
    """Replace each stage-body pointer line in `command` with the text it points at."""

    def block(m: re.Match[str]) -> str:
        ref = (ref_dir / m.group("name")).read_text(encoding="utf-8")
        i = ref.index(REF_START) + len(REF_START)
        return ref[i : ref.index(REF_END, i)]

    expanded, _ = _POINTER.subn(block, command)
    for m in _INLINE_POINTER.finditer(expanded):
        assert (ref_dir / m.group("name")).is_file(), f"{m.group('name')} did not render"
    # A pointer to a reference file this module does not know about would pass through unexpanded
    # and silently drop that file's text from every test that reads through here. The shared
    # auto-advance procedure is the one deliberate pointer left alone: tests read it directly.
    strays = [
        ln
        for ln in expanded.splitlines()
        if ln.lstrip().startswith("Read `.claude/hm/")
        and "autopilot-advance.md" not in ln
        and not _INLINE_POINTER.match(ln)
    ]
    assert not strays, f"a reference-file pointer matched nothing in _POINTER: {strays[0][:120]}"
    return expanded


def stage_text(claude_dir: Path, stage: str) -> str:
    """`<claude_dir>/commands/hm/<stage>.md` with its reference files expanded in place."""
    command = (claude_dir / "commands" / "hm" / f"{stage}.md").read_text(encoding="utf-8")
    return expand_references(command, claude_dir / "hm")
