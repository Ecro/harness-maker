"""No `$0`–`$9` anywhere in a rendered slash command — the host substitutes them.

Claude Code expands a slash command's arguments into the command body BEFORE the model
sees it, and that expansion replaces `$0`, `$1`, … . The file on disk is therefore not
what runs: a shell or awk snippet that uses a positional parameter is silently rewritten
at invocation time, and every render-grep test still passes because they read the file.

Measured on 2026-07-26 with `/hm:make --update`:

    on disk   : ... | awk -F/ '{print $NF, $0}'   | sort -V | ...   -> .../0.43.2
    as invoked: ... | awk -F/ '{print $NF, --update}' | sort -V | ...   -> -8

`HM` became `-8`, `uv run --with "-8"` failed, and the line fell through to its
hardcoded fallback pin — which is the *stale-pin bootstrap trap that very line exists to
escape*. Two more instances were in `/hm:review` and `/hm:plan`
(`awk '{s+=$1} END{print s+0}'`), where the clobbered value feeds
`high_diff classify --added-lines` and therefore decides whether the Side preset invokes
its second opinion at all.

This is one layer outside CLAUDE.md checkpoint 2: the source is right and the rendered
artifact is right; the CONSUMER's own preprocessing is what breaks it. `$ARGUMENTS` is
the supported way to reach the arguments, and it is deliberately not matched here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

# `$0`..`$9`, but not `$$` (PID) and not `${...}` (parameter expansion of a NAME).
_POSITIONAL = re.compile(r"(?<![$\\])\$[0-9]")


@pytest.fixture(scope="module")
def rendered_commands(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    out = tmp_path_factory.mktemp("cmd-render")
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(
                preset=Preset.PRODUCTION,
                targets=[Target.CLAUDE_CODE],
                worktree={"feature_branch_workflow": True},
            ),
        ),
        out,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    root = out / "commands" / "hm"
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.md"))}


def test_the_fixture_actually_rendered_commands(rendered_commands: dict[str, str]) -> None:
    """Positive control: an empty mapping would make every check below vacuous."""
    assert len(rendered_commands) >= 10, sorted(rendered_commands)


def test_no_rendered_command_uses_a_positional_parameter(
    rendered_commands: dict[str, str],
) -> None:
    offenders: dict[str, list[str]] = {}
    for name, body in rendered_commands.items():
        hits = [line.strip() for line in body.splitlines() if _POSITIONAL.search(line)]
        if hits:
            offenders[name] = hits

    assert not offenders, (
        "rendered slash commands contain `$0`-`$9`, which the host replaces with the "
        "command's arguments before the model reads the file — the line that runs is "
        f"not the line on disk:\n{offenders}"
    )


def test_the_plugins_own_commands_use_no_positional_parameter() -> None:
    """The plugin's OWN `commands/` are slash commands too — and the first version of
    this gate scanned only the RENDERED ones, so it missed
    `/harness-maker:make`, which is the entry point for a fresh install and takes
    arguments (`--ci preset=…`). Scoping a gate to the artifact you happened to be
    fixing is how the same defect survives its own fix.
    """
    root = Path(__file__).resolve().parents[2]
    offenders: dict[str, list[str]] = {}
    for directory in ("commands", "skills", "agents", "hooks"):
        for path in sorted((root / directory).rglob("*.md")):
            hits = [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if _POSITIONAL.search(line)
            ]
            if hits:
                offenders[str(path.relative_to(root))] = hits

    assert not offenders, (
        "the plugin's own slash commands contain `$0`-`$9`, which the host replaces "
        f"with the command's arguments before the model reads them:\n{offenders}"
    )


def test_the_make_bootstrap_resolves_a_version_not_a_positional(
    rendered_commands: dict[str, str],
) -> None:
    """The specific line the defect was found on, pinned by intent rather than by shape.

    Asserting `"$0" not in body` alone would pass the moment someone rewrote the
    resolution using `$1`; asserting the *mechanism* keeps it honest.
    """
    body = rendered_commands["make.md"]

    assert "harness_maker.cli locate --plain" in body, (
        "the bootstrap must still disambiguate installs via `locate`"
    )
    assert "${p##*/}" in body, (
        "the version sort must derive the basename with shell parameter expansion — "
        "awk's `$NF`/`$0` form is what the host clobbers"
    )
