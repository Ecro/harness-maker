"""The stage-end `Next:` banner names an invocation the calling runtime can actually make.

Codex has no slash command for a stage and no tool that runs a skill. A stage there is a skill
under `.agents/skills/`, started only by mentioning it — live-probed against Codex CLI 0.147.0:
*"SKILL-running tools: none … A skill in `.agents/skills/` is invoked by mentioning its skill
name (e.g. `@hm-execute`)."* So `➡️ Next: /hm:execute` on that target names a call the runtime
cannot make. Same defect class as rendering `Task(` into a Codex skill — an instruction that
reads fine and cannot be followed.

`summary_next` is the single seam: each stage sets it as a literal and
`agents/_partials/stage_end_summary.md.j2` renders it once, so one rewrite covers all seven.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from harness_maker.template_globals import TEMPLATE_GLOBALS, stage_invocation


def _rendered(preset: Preset) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=preset, targets=[Target.CLAUDE_CODE, Target.CODEX]),
    )
    with tempfile.TemporaryDirectory() as td:
        # `target_dir` is the `.claude` directory; Codex outputs land in its PARENT. Rooting
        # the render at a bare tmpdir writes `.codex/` and `AGENTS.md` into the tmpdir's parent
        # (the real `/tmp`) and the scan then reads as "no Codex output" instead of "did not look".
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        out: dict[str, str] = {}
        for walk_root, _dirs, names in os.walk(root):
            for name in names:
                f = Path(walk_root) / name
                out[str(f.relative_to(root))] = f.read_text(encoding="utf-8", errors="replace")
        return out


def _next_lines(body: str) -> list[str]:
    return [line.strip() for line in body.splitlines() if "**Next:**" in line]


def test_rewrites_only_for_codex() -> None:
    assert stage_invocation("`/hm:execute {slug}` (STOP)", True) == "`@hm-execute {slug}` (STOP)"
    assert stage_invocation("`/hm:execute {slug}` (STOP)", False) == "`/hm:execute {slug}` (STOP)"


def test_rewrites_every_command_in_one_string() -> None:
    """`/hm:review`'s banner names two stages; rewriting only the first is a silent half-fix."""
    got = stage_invocation("re-review, or `/hm:wrapup` and `/hm:verify`", True)
    assert "@hm-wrapup" in got
    assert "@hm-verify" in got
    assert "/hm:" not in got


def test_leaves_non_command_text_alone() -> None:
    assert stage_invocation("STOP — task complete", True) == "STOP — task complete"


def test_is_registered_as_a_template_global() -> None:
    """Every Environment in the package installs these; a local registration would render in
    one code path and raise UndefinedError in another."""
    assert TEMPLATE_GLOBALS["stage_invocation"] is stage_invocation


def test_rendered_codex_banner_uses_mention_form() -> None:
    files = _rendered(Preset.SIDE)
    codex = {p: b for p, b in files.items() if p.startswith(".agents/skills/hm-")}
    assert codex, "no Codex stage skills rendered — the scan looked in the wrong place"
    seen = 0
    for path, body in codex.items():
        for line in _next_lines(body):
            seen += 1
            assert "/hm:" not in line, f"{path}: Codex banner names an uncallable slash command"
    assert seen, "no Next: banner found in any Codex stage skill"


def test_rendered_claude_banner_keeps_slash_form() -> None:
    files = _rendered(Preset.SIDE)
    claude = {p: b for p, b in files.items() if p.startswith(".claude/commands/hm/")}
    assert claude
    assert any("/hm:" in line for body in claude.values() for line in _next_lines(body)), (
        "the Claude arm lost its slash-command form"
    )
