"""Every `harness-maker <subcommand>` a shipped doc tells a user to run must actually exist.

Motivation, from this repo's own history rather than a hypothetical: the 0.47.0 CHANGELOG
and README each acquired a migration instruction naming `harness-maker configure`, which is
not a registered command — and it was written *while rewriting the paragraph that had just
been corrected for a different wrong migration instruction*. Typer exits with "No such
command", so the documented adoption path fails outright for anyone who follows it.

Docs are not covered by lint, mypy, or any test that runs the CLI, so a wrong command name
in prose is invisible to every gate this project has. This is that gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


# Discovered, not enumerated. A fixed tuple missed `docs/BOOTSTRAP.md` — 11 invocations,
# and the file a new user is pointed at. `docs/adr/**` is excluded on the same reasoning as
# the CHANGELOG's older sections: an ADR records what was decided at the time, and a command
# it names may since have been retired.
def _shipped_docs() -> list[Path]:
    docs = [_ROOT / "README.md", _ROOT / "README.ko.md", _ROOT / "CHANGELOG.md"]
    docs += sorted(
        d for d in (_ROOT / "docs").rglob("*.md") if "adr" not in d.relative_to(_ROOT).parts
    )
    return [d for d in docs if d.is_file()]


_DOCS = tuple(str(d.relative_to(_ROOT)) for d in _shipped_docs())

# Only invocations inside a code span (`...`) or a fenced block count. Prose like
# "harness-maker itself reads ..." is not an instruction to run anything, and matching it
# produced a dozen false positives ("itself", "would", "reads") on the first run.
# Inline spans and shell-tagged fences are runnable wholesale.
_CODE_SPAN = re.compile(r"`([^`\n]+)`|```(?:bash|sh|shell|console)\n(.*?)```", re.S)

# UNTAGGED fences are the hard case, and excluding them wholesale was a false negative on the
# highest-stakes surface in the repo: README's paste-into-Claude bootstrap — the documented
# entry point for a NEW install — is an untagged fence, and the line inside it reads
# `Bash  harness-maker make`. An agent executes that verbatim. Scanning those fences as prose
# flagged `as`/`via`/`for`; skipping them let the install command go unchecked.
#
# This is the exact scoping mistake CLAUDE.md records for `commands/make.md`: a gate aimed at
# the artifact being fixed let the identical defect survive in the install entry point.
#
# So: inside an untagged fence, count a line ONLY when it is shaped like an explicit run
# instruction — optionally prefixed with `Bash`/`Run`/`$`/`>` — rather than mentioning the
# tool mid-sentence.
_UNTAGGED_FENCE = re.compile(r"```[ \t]*\n(.*?)```", re.S)
# The run marker is REQUIRED, not optional. Made optional, this matched prose lines that
# merely START with the tool name ("harness-maker generates ..."), which are descriptions,
# not orders. A `Bash`/`Run`/`Shell` label or a `$`/`>` prompt is what makes a line inside a
# prose fence an instruction to execute.
_RUN_INSTRUCTION = re.compile(
    r"""(?:(?:Bash|Run|Shell)[:\s]|[$>][ \t]*)[ \t]*"""
    r"""(?<![\w/"'-])harness-maker[ \t]+([a-z][a-z0-9-]*)(?![=\w])""",
)
# `[ \t]+`, NOT `\s+`: a fenced block is many lines, and `\s` crosses newlines, so a line
# ending in `harness-maker` matched the FIRST WORD of the next line (`cd`, `git`, `uv`).
# `harness-maker` must be in COMMAND position. Three real false positives from docs/:
#   `echo "harness-maker not installed"`            → preceded by a quote (prose in a string)
#   `#   harness-maker installed=0.7.3 required=…`  → the word is followed by `=` (a message)
#   `git -C ~/.cursor/plugins/local/harness-maker pull` → preceded by `/` (a PATH component,
#                                                          and `pull` is git's subcommand)
_INVOCATION = re.compile(r"""(?<![\w/"'-])harness-maker[ \t]+([a-z][a-z0-9-]*)(?![=\w])""")


def _documented_subcommands(markdown: str) -> set[str]:
    """Every subcommand a reader is told to RUN, from both fence kinds."""
    runnable = "\n".join(m.group(1) or m.group(2) or "" for m in _CODE_SPAN.finditer(markdown))
    found = set(_INVOCATION.findall(runnable))
    for fence in _UNTAGGED_FENCE.finditer(markdown):
        found.update(_RUN_INSTRUCTION.findall(fence.group(1)))
    return found


def _current_release_section(markdown: str) -> str:
    """CHANGELOG only: the topmost `## [x]` section.

    A changelog is a HISTORICAL record — older entries legitimately name commands that
    existed at the time and have since been removed (`health-finalize`). Gating those would
    force rewriting history to satisfy a test. Only the release being shipped is a live
    instruction to the reader.
    """
    parts = re.split(r"^## ", markdown, flags=re.M)[1:]
    if not parts:
        return markdown
    # `[Unreleased]` plus the first real release. Taking only the topmost section drops the
    # shipped release from coverage the moment development resumes and an `[Unreleased]`
    # heading is added above it.
    return "\n## ".join(parts[:2])


def _registered_commands() -> set[str]:
    """The names Typer will actually accept, read from the live app rather than a list."""
    from harness_maker.cli import app

    names: set[str] = set()
    for info in app.registered_commands:
        # Typer derives the CLI name from the callback's __name__ when `name` is unset,
        # replacing underscores with hyphens.
        name = info.name or (info.callback.__name__.replace("_", "-") if info.callback else None)
        if name:
            names.add(name)
    return names


# ── Slash-command surface ──────────────────────────────────────────────────────
#
# The arm above covers `harness-maker <subcommand>` in docs. It covers neither of the two
# axes on which `/hm:ai-readiness` survived in `commands/make.md:601` — the quick-start line
# a user reads FIRST after a fresh install, naming a command retired into `/hm:health` by
# docs/adr/0006. It is a slash name, not a Typer subcommand, and it lives in `commands/`,
# which `_shipped_docs()` never looks at.
#
# That is this file's own recorded failure class, repeated: a gate scoped to the artifact
# being fixed lets the identical defect survive next door. So this arm reads the plugin's
# live command surface and both spellings — `/hm:<name>` (Claude Code, Cursor) and
# `@hm-<name>` (Codex), which the templates emit from one `{% if is_codex %}` branch.
#
# SCOPE, deliberate: `commands/**/*.md` only, NOT `_shipped_docs()`. Measured 2026-08-06,
# the docs surface carries 12+ names that no longer render — the retired fused workflows
# (`exec-rev*`, `plan-exec-rev*`, `res-spec-plan`) plus `audit`, `bootstrap`, `refresh`,
# `trends`, `personalization-audit`. Gating those is a docs-cleanup project; folding it in
# here would make this arm un-greenable for reasons unrelated to the surface that executes.
# `commands/` is where an agent reads its instructions, which is why it is gated first.
_HM_SLASH = re.compile(r"(?:/hm:|@hm-)([a-z][a-z0-9-]*)")


def _rendered_hm_commands() -> set[str]:
    """Names that actually render, from the template registry — not from a checkout.

    NOT `.claude/commands/**`: that is a generated artifact whose contents depend on the
    local harness.yaml (targets, preset), so a test reading it measures this machine.
    """
    from harness_maker.models import AtomicStage

    names = {s.value for s in AtomicStage}
    templates = _ROOT / "src" / "harness_maker" / "templates" / "commands" / "hm"
    for path in templates.glob("*.md.j2"):
        stem = path.name.removesuffix(".md.j2")
        if stem == "atomic_command":
            continue  # the generator for the AtomicStage names already added above
        names.add(stem.split(".", 1)[0])  # help.en / help.ko both spell `help`
    return names


def _plugin_command_docs() -> list[Path]:
    """`commands/**` plus the READMEs — the two surfaces a user is pointed at to RUN things.

    `docs/**` is deliberately still out. Measured 2026-08-06 it carries ~40 references to
    retired commands, and `docs/HOW-IT-WORKS.md` gives three of them (`hm:refresh`,
    `hm:ai-readiness`, `hm:personalization-audit`) whole numbered sections. Resolving those
    is a documentation rewrite that has to decide what replaced each capability, not a
    rename — so folding it in here would make this arm un-greenable for reasons unrelated to
    the surfaces that execute. Tracked as a follow-up in
    `work-docs/PLAN-onboarding-interview-ux.md` Phase 8.
    """
    docs = sorted((_ROOT / "commands").rglob("*.md"))
    docs += [p for p in (_ROOT / "README.md", _ROOT / "README.ko.md") if p.is_file()]
    return docs


def test_the_rendered_command_list_is_non_empty() -> None:
    """Non-vacuity, mirroring `test_the_command_list_is_non_empty` for the slash arm.

    An empty set makes the assertion below accept every name, including the one this arm
    exists to reject.
    """
    commands = _rendered_hm_commands()
    assert len(commands) >= 10, commands
    for expected in ("health", "configure", "execute", "wrapup"):
        assert expected in commands, (expected, sorted(commands))


def test_the_slash_scanner_rejects_a_name_that_does_not_render() -> None:
    """Negative control: the scanner must reject, not merely observe.

    Without this, a scanner that silently found nothing would pass every real assertion.
    """
    registered = _rendered_hm_commands()
    found = set(_HM_SLASH.findall("see `/hm:health` and `@hm-wrapup` and `/hm:does-not-exist`"))
    assert {"health", "wrapup"} <= found, found
    assert sorted(w for w in found if w not in registered) == ["does-not-exist"]


def test_every_hm_command_named_in_the_plugin_surface_renders() -> None:
    docs = _plugin_command_docs()
    assert docs, "no plugin command markdown found — the scanner would be vacuous"
    registered = _rendered_hm_commands()
    bad: dict[str, list[str]] = {}
    for path in docs:
        text = path.read_text(encoding="utf-8")
        missing = sorted({w for w in _HM_SLASH.findall(text) if w not in registered})
        if missing:
            bad[str(path.relative_to(_ROOT))] = missing
    assert bad == {}, (
        f"plugin command surface names commands that do not render: {bad}. "
        f"Rendered: {sorted(registered)}"
    )


def test_the_command_list_is_non_empty() -> None:
    """Non-vacuity: if the introspection breaks, every assertion below passes on an empty set.

    Guarding the guard — an empty `registered_commands` would make the real test below
    silently accept any command name at all.
    """
    commands = _registered_commands()
    assert len(commands) >= 5, commands
    assert "make" in commands


@pytest.mark.parametrize("doc", _DOCS)
def test_every_documented_subcommand_is_registered(doc: str) -> None:
    path = _ROOT / doc
    if not path.is_file():
        pytest.skip(f"{doc} not present")
    text = path.read_text(encoding="utf-8")
    if doc == "CHANGELOG.md":
        text = _current_release_section(text)
    registered = _registered_commands()
    bad = sorted({w for w in _documented_subcommands(text) if w not in registered})
    assert bad == [], (
        f"{doc} tells users to run `harness-maker {bad}`, which Typer does not accept. "
        f"Registered: {sorted(registered)}"
    )
