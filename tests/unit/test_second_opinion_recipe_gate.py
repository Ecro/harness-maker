"""Producer gate: the retired second-opinion invocation shapes cannot come back.

Prose can be re-broken by an edit, and only a producer gate notices. Four distinct
silent-skip bugs shipped through rendered recipes; two of them are pinned here.

Scope note — what this file can and cannot do. The `agy` shapes ARE greppable in
rendered output, so they are gated here. The `--output-schema` absoluteness is NOT:
under the current design that flag never appears in rendered output at all, so a
"no relative --output-schema" grep would pass unconditionally even while the Python
built a relative path — an assertion invariant over the dimension it names. That
half lives on the constructed argv in `test_second_opinion_invoke.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.models import (
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionConfig,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

# `agy --print <anything>` consumes the next token as the PROMPT VALUE. Any rendered
# command of that shape is broken by construction, whatever follows.
_AGY_PRINT_THEN_FLAG = re.compile(r"agy\s+--print\s+--")
# `agy` never reads stdin in print mode, so a redirect into it is always dead.
_AGY_STDIN_REDIRECT = re.compile(r"agy\b[^\n|]*<\s*[\"$]")


def _command_lines(text: str) -> str:
    """Only the lines a reader would EXECUTE: fenced code blocks and `!`-prefixed lines.

    Scoped deliberately. The partials now *document* the retired shapes — explaining why
    `agy --print --sandbox … < file` never worked is the most useful thing in that file,
    and a gate that forbids naming the bug would delete its own rationale. What must
    never come back is a runnable line, so that is what this reads.
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or stripped.startswith("!"):
            out.append(line)
    return "\n".join(out)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> list[tuple[Path, str]]:
    out = tmp_path_factory.mktemp("rendered")
    ans = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
        second_opinion=SecondOpinionConfig(models=["codex", "antigravity"]),
    )
    render(synthesize(ProjectProfile(), ans), out, freeze_time=DEFAULT_FREEZE_TIME)
    return [
        (p, _command_lines(p.read_text(encoding="utf-8", errors="replace")))
        for p in out.rglob("*")
        if p.is_file()
    ]


def test_no_rendered_artifact_puts_a_flag_after_agy_print(
    rendered: list[tuple[Path, str]],
) -> None:
    offenders = [str(p) for p, text in rendered if _AGY_PRINT_THEN_FLAG.search(text)]
    assert offenders == [], (
        "`agy --print` takes the prompt as its VALUE — a flag after it becomes the "
        f"prompt and the vote is vacuous at exit 0: {offenders}"
    )


def test_no_rendered_artifact_feeds_agy_on_stdin(rendered: list[tuple[Path, str]]) -> None:
    offenders = [str(p) for p, text in rendered if _AGY_STDIN_REDIRECT.search(text)]
    assert offenders == [], f"`agy` does not read stdin in print mode: {offenders}"


def test_the_gate_would_actually_fire(rendered: list[tuple[Path, str]]) -> None:
    # A producer gate that cannot fail is worse than none — it certifies coverage it
    # does not have. Prove both patterns match the exact strings that shipped.
    assert _AGY_PRINT_THEN_FLAG.search('agy --print --sandbox --print-timeout 240s --model "X"')
    assert _AGY_STDIN_REDIRECT.search('agy --print --sandbox --model "X" < "$prompt_tmp"')
    # …and do not fire on the corrected shape.
    assert not _AGY_PRINT_THEN_FLAG.search(
        'agy --sandbox --print "the prompt" --print-timeout 240s'
    )
    assert not _AGY_STDIN_REDIRECT.search('agy --sandbox --print "the prompt"')


def test_command_line_extractor_ignores_prose_but_keeps_commands() -> None:
    # The extractor is the gate's blast radius: if it silently returned nothing, every
    # assertion above would pass vacuously over an empty string.
    doc = (
        "> It used to be `agy --print --sandbox` and that never worked.\n"
        "\n"
        "```bash\n"
        'agy --sandbox --print "p"\n'
        "```\n"
        "!echo hi\n"
    )
    extracted = _command_lines(doc)
    assert "agy --sandbox --print" in extracted
    assert "!echo hi" in extracted
    assert "It used to be" not in extracted


def test_settings_allow_rule_matches_the_real_argv_grammar(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    # An allow-rule prefix is a contract with the tool's argv grammar, not just a
    # string. The old rule pre-approved a command shape that could not work, which is
    # what froze the bug in place for its whole lifetime. Read the raw file here —
    # settings.json has no fences, so the command-line extractor would empty it.
    out = tmp_path_factory.mktemp("settings")
    ans = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
        second_opinion=SecondOpinionConfig(models=["codex", "antigravity"]),
    )
    render(synthesize(ProjectProfile(), ans), out, freeze_time=DEFAULT_FREEZE_TIME)
    settings = (out / "settings.json").read_text(encoding="utf-8")
    assert "Bash(agy --sandbox --print:*)" in settings
    assert "Bash(agy --print --sandbox:*)" not in settings
