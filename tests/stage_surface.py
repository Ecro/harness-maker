"""A stage's text as the model meets it, with its on-demand reference files read in place.

Stage 2b (SPEC-hm-light-lane-s2b) moved the bodies of wrapup Steps 1-5.6, verify's checks,
review's auto-fix rounds and confirmation pass, and execute Phase A.5 out of the Claude commands
into `.claude/hm/*.md`. Most render tests assert on the text of one of those bodies, not on
where the Claude command keeps it, so they read the command through `stage_text`: each pointer
line is replaced by the block it points at. For review and execute that reproduces the pre-move
document order; the tests that ARE about the pointers read the command itself.

Stage 3c (SPEC-hm-light-lane-s3c) moved three more: every stage's preamble
(`stage-preamble.md`), execute's full PLAN text (`execute-plan.md`, read in two parts, the second
at Step 0.3) and spec's full machine.yaml schema (`spec-machine-full.md`). Each pointer is
replaced the same way, so the pre-move order comes back, apart from the light-lane text 3c added.
"""

from __future__ import annotations

import re
from pathlib import Path

#: The `.claude/hm/` files each stage command reads on demand for text it no longer carries.
STAGE_REFERENCE_FILES: dict[str, tuple[str, ...]] = {
    "research": ("stage-preamble",),
    "spec": ("stage-preamble", "spec-machine-full"),
    "wrapup": ("stage-preamble", "wrapup-steps"),
    "verify": ("stage-preamble", "verify-checks"),
    "review": ("stage-preamble", "review-autofix", "review-confirmation"),
    "execute": ("stage-preamble", "execute-plan", "execute-a5", "execute-light-check"),
}
REF_START, REF_END = "<!-- @hm:ref:start -->\n", "<!-- @hm:ref:end -->"
_NAMES = (
    r"(?P<name>(?:wrapup-steps|verify-checks|review-autofix|review-confirmation|execute-a5"
    r"|execute-light-check|stage-preamble|execute-plan|spec-machine-full)\.md)"
)
_POINTER = re.compile(rf"^Read `\.claude/hm/{_NAMES}` from the project root.*\n", re.M)
#: execute-plan.md's second part belongs at the command's Step 0.3, where this sentence stands.
_STEP03_SENTENCE = re.compile(
    r"^Light PLAN: run the light read-back from Step 0's light block\. Any other PLAN: apply the "
    r"Step 0\.3 part of `\.claude/hm/execute-plan\.md`\.\n\n",
    re.M,
)
_PLAN_PART_SEPARATOR = re.compile(r"<!-- @hm:ref:step-0\.3 -->.*\n\n")
#: The preamble pointer and the two markers the command keeps for `/hm:health`: the whole span
#: between the frontmatter and `# Stage:`, which the preamble text filled before 3c.
_PREAMBLE_SPAN = re.compile(
    r"^Read `\.claude/hm/stage-preamble\.md` from the project root.*\n\n"
    r"<!-- @hm:banner:start -->\n<!-- @hm:output_language -->\n\n",
    re.M,
)
#: An INDENTED pointer is a reference, not the body's position (the wrapup receipt-mismatch bullet
#: sends the reader to the same file mid-list). It is checked against `ref_dir` but never expanded:
#: expanding it would put the block in Step 0.5, ahead of where the stage reads it.
_INLINE_POINTER = re.compile(rf"^[ \t]+Read `\.claude/hm/{_NAMES}` from the project root.*$", re.M)


def expand_references(command: str, ref_dir: Path) -> str:
    """Replace each stage-body pointer line in `command` with the text it points at."""

    def body(name: str) -> str:
        ref = (ref_dir / name).read_text(encoding="utf-8")
        i = ref.index(REF_START) + len(REF_START)
        return ref[i : ref.index(REF_END, i)]

    def block(m: re.Match[str]) -> str:
        text = body(m.group("name"))
        return (
            _PLAN_PART_SEPARATOR.split(text, 1)[0] if m.group("name") == "execute-plan.md" else text
        )

    expanded = _PREAMBLE_SPAN.sub(lambda _m: body("stage-preamble.md"), command, count=1)
    expanded, _ = _POINTER.subn(block, expanded)
    if _STEP03_SENTENCE.search(expanded):
        part2 = _PLAN_PART_SEPARATOR.split(body("execute-plan.md"), 1)[1]
        expanded = _STEP03_SENTENCE.sub(lambda _m: part2, expanded, count=1)
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
