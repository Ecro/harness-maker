"""Host invocation contracts from SPEC-codex-stage-invocation.

Preservation and retired-stage negative invariants already pass before the fix;
RED positive siblings (dollar spelling, full body, update) force the formatter
into the production path. Preservation fixtures must reject blanket replacement.
"""

from __future__ import annotations

import os
import re
import tempfile
from functools import cache
from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from harness_maker.template_globals import TEMPLATE_GLOBALS, stage_invocation


@cache
def _rendered(preset: Preset, locale: str = "en") -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=preset, locale=locale, targets=[Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
        ),
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
    assert stage_invocation("`/hm:execute {slug}` (STOP)", True) == "`$hm-execute {slug}` (STOP)"
    assert stage_invocation("`/hm:execute {slug}` (STOP)", False) == "`/hm:execute {slug}` (STOP)"


def test_rewrites_every_command_in_one_string() -> None:
    """`/hm:review`'s banner names two stages; rewriting only the first is a silent half-fix."""
    got = stage_invocation("re-review, or `/hm:wrapup` and `/hm:verify`", True)
    assert "$hm-wrapup" in got
    assert "$hm-verify" in got
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


@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_codex_guidance_uses_dollar_mentions(preset: Preset, locale: str) -> None:
    files = _rendered(preset, locale)
    research = files[".agents/skills/hm-research/SKILL.md"]
    assert "Invoke via `$hm-research <topic>" in research
    assert "Y → run `$hm-spec {slug}`" in research
    assert "**Next:** `$hm-spec {slug}`" in research
    assert "`$hm-execute task-slug`" in files["AGENTS.md"]
    for path, body in files.items():
        if path == "AGENTS.md" or path.startswith(".agents/skills/"):
            assert "@hm-" not in body, path
    help_body = files[".agents/skills/hm-help/SKILL.md"]
    assert "`$hm-research`" in help_body
    assert "`$intent-layer`" in help_body
    assert "`$project-knowledge`" in help_body
    for skill in ("hm-verify", "hm-wrapup", "verify-before-completion"):
        recovery = files[f".agents/skills/{skill}/SKILL.md"]
        assert "— run $hm-review first" in recovery
    common = files[".agents/skills/targeted-test-selection/SKILL.md"]
    assert "Followed by $hm-review" in common


def test_preserves_executable_and_non_codex_content() -> None:
    # These are shell payloads, not prompts. Expanding $hm would corrupt them.
    protected = [
        '```bash\necho "run /hm:spec"\nhm span-end --stage hm:spec\n```\n',
        '```\nBash("echo /hm:spec")\n```\n',
        '~~~python\ncommand = "/hm:spec"\n~~~\n',
        '`echo "run /hm:spec"` and `.claude/commands/hm/spec.md`',
        "`--stage hm:spec` and `/tmp/hm:spec`",
        "<!-- @hm:user:extensions -->\nUse /hm:spec and @hm-spec here.\n"
        "<!-- @hm:/user:extensions -->",
    ]
    for text in protected:
        assert stage_invocation(text, True) == text
    assert stage_invocation("```text\n/hm:spec topic\n```", True) == "```text\n$hm-spec topic\n```"
    text = "Run `/hm:spec x`, `@hm-execute x`, then `/hm:review x`."
    assert stage_invocation(text, False) == text
    files = _rendered(Preset.SIDE)
    assert "Y → run `/hm:spec {slug}`" in files[".claude/commands/hm/research.md"]
    assert "/hm:" in files[".cursor/rules/harness.mdc"]


@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_recommendations_resolve_to_skills(preset: Preset, locale: str) -> None:
    files = _rendered(preset, locale)
    names = {p.split("/")[2] for p in files if p.startswith(".agents/skills/")}
    assert {
        "hm-research",
        "hm-spec",
        "hm-execute",
        "hm-review",
        "hm-verify",
        "hm-wrapup",
        "hm-loop",
        "hm-help",
    } <= names
    assert "hm-plan" not in names
    for path, body in files.items():
        if path.startswith(".agents/skills/hm-"):
            for line in _next_lines(body):
                for name in re.findall(r"(?:\$hm-|@hm-|/hm:)([a-z][a-z-]+)", line):
                    assert f"hm-{name}" in names, (path, line)
    help_body = files[".agents/skills/hm-help/SKILL.md"]
    advertised = {
        f"hm-{name}" for name in re.findall(r"`(?:\$hm-|@hm-|/hm:)([a-z][a-z-]+)`", help_body)
    }
    assert {
        "hm-research",
        "hm-spec",
        "hm-execute",
        "hm-review",
        "hm-verify",
        "hm-wrapup",
        "hm-loop",
        "hm-help",
    } <= advertised
    assert advertised <= names


def test_update_repairs_guidance(tmp_path: Path) -> None:
    blueprint = synthesize(ProjectProfile(), InterviewAnswers(targets=[Target.CODEX]))
    target = tmp_path / ".claude"
    render(blueprint, target, freeze_time=DEFAULT_FREEZE_TIME)
    rel = Path(".agents/skills/hm-research/SKILL.md")
    path = tmp_path / rel
    old = path.read_text().replace("$hm-", "@hm-")
    old = old.replace("Y → run `@hm-spec {slug}`", "Y → run `/hm:spec {slug}`")
    assert "Invoke via `@hm-research <topic>" in old
    assert "Y → run `/hm:spec {slug}`" in old
    marker = "<!-- @hm:user:extensions -->"
    agents_path = tmp_path / "AGENTS.md"
    extension = "\nKeep my literal /hm:spec and @hm-spec.\n"
    agents_path.write_text(agents_path.read_text().replace(marker, marker + extension))
    path.write_text(old)
    render(
        blueprint,
        target,
        freeze_time=DEFAULT_FREEZE_TIME,
        merge_paths={rel, Path("AGENTS.md")},
        merge_reports={},
    )
    result = path.read_text()
    assert "Invoke via `$hm-research <topic>" in result
    assert "Y → run `$hm-spec {slug}`" in result
    agents_result = agents_path.read_text()
    assert extension in agents_result
    render(
        blueprint,
        target,
        freeze_time=DEFAULT_FREEZE_TIME,
        merge_paths={rel, Path("AGENTS.md")},
        merge_reports={},
    )
    assert path.read_text() == result
    assert agents_path.read_text() == agents_result
