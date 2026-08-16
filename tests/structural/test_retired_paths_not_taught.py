"""A path this project retired must not be taught, in any shipped doc, as a live one.

Every gate this repo has checks that something it SAYS exists does exist. Nothing checked the
opposite direction — that something it says works still works — and that is the direction the
expensive errors ran. `.claude/hooks/hooks.json` was described as "the Claude Code hooks
schema" across four docs and this project's own CLAUDE.md. It was refuted by controlled
experiment on 2026-07-17 and the render was removed; the sentences teaching it survived,
because a doc sentence is not reachable from lint, mypy, or any test that runs the CLI.

The three assertions are deliberately different in kind, and the middle one is the one that
keeps this file from decaying into an allowlist:

1. the retired path is genuinely not rendered — if someone re-adds it, this fires, and the
   right fix is to delete the entry rather than to silence the test;
2. the REPLACEMENT is rendered — so the forward pointer these docs give a reader is live,
   and moving the replacement breaks this rather than stranding the docs;
3. a doc naming the retired path also names the replacement — wording-agnostic, because
   pattern-matching disclaimer prose ("no longer", "deprecated") is exactly the kind of
   heuristic that passes on a sentence which then says the opposite.

**Scope, stated plainly:** this catches retired PATHS. It does not catch a wrong claim about
behaviour — three of the four corrections made on 2026-08-15 (two-pass review described as
diff preprocessing, the reviewer axis, the auto-fix exit conditions) are prose semantics with
no mechanical referent, and no test in this file would have found them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile, Target
from harness_maker.synthesize import synthesize

_ROOT = Path(__file__).resolve().parents[2]

# retired path -> the path that replaced it. Both halves are asserted against the renderer,
# so neither can quietly become fiction.
_RETIRED: dict[str, str] = {
    ".claude/hooks/hooks.json": ".claude/settings.json",
}


# CHANGELOG and ADRs record what was true when written; naming a since-retired path there is
# correct, not a defect. Same exclusion, same reasoning, as `test_documented_commands_exist`.
def _shipped_docs() -> list[Path]:
    docs = [_ROOT / "README.md", _ROOT / "README.ko.md", _ROOT / "CLAUDE.md"]
    docs += sorted(
        d for d in (_ROOT / "docs").rglob("*.md") if "adr" not in d.relative_to(_ROOT).parts
    )
    return [d for d in docs if d.is_file()]


def _rendered_paths() -> set[str]:
    """Every path a full three-target render puts on disk, normalised to project-relative.

    Blueprint paths are relative to `.claude/` except for the Codex/Cursor roots, which the
    renderer writes as siblings of it. Note that "has no slash" is NOT the sibling test:
    `settings.json` and `harness.yaml` are both bare names *inside* `.claude/`, while
    `AGENTS.md` is the one bare name at the repo root.
    """
    profile = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    out: set[str] = set()
    for entry in synthesize(profile, answers).files:
        raw = str(entry.path)
        sibling = raw.startswith((".codex/", ".agents/", ".cursor/")) or raw == "AGENTS.md"
        out.add(raw if sibling else f".claude/{raw}")
    return out


@pytest.fixture(scope="module")
def rendered() -> set[str]:
    return _rendered_paths()


def test_the_render_probe_is_not_vacuous(rendered: set[str]) -> None:
    """A silently-empty blueprint would make assertion 1 pass for every conceivable path."""
    assert len(rendered) > 50, f"only {len(rendered)} rendered paths — probe is broken"


@pytest.mark.parametrize("retired", sorted(_RETIRED))
def test_a_retired_path_is_not_rendered(retired: str, rendered: set[str]) -> None:
    assert retired not in rendered, (
        f"{retired} is listed as retired but the renderer still emits it. Either the "
        "retirement was reverted (drop the entry here, and fix the docs that call it dead) "
        "or the render came back by accident."
    )


@pytest.mark.parametrize("retired", sorted(_RETIRED))
def test_the_replacement_is_rendered(retired: str, rendered: set[str]) -> None:
    replacement = _RETIRED[retired]
    assert replacement in rendered, (
        f"docs point readers from {retired} to {replacement}, which the renderer does not "
        "emit. The forward pointer is dead — update both the docs and this mapping."
    )


def _mentions(retired: str) -> list[tuple[Path, str]]:
    """(doc, text) for every shipped doc naming `retired`, boundary-matched.

    The negative lookarounds keep `.claude/hooks/hooks.json` from matching inside a longer
    path — without them the plugin-bundle `hooks/hooks.json`, which is a REAL and live
    location, would be read as a mention of the retired one.
    """
    pattern = re.compile(rf"(?<![\w./]){re.escape(retired)}(?![\w])")
    hits = []
    for doc in _shipped_docs():
        text = doc.read_text(encoding="utf-8")
        if pattern.search(text):
            hits.append((doc, text))
    return hits


@pytest.mark.parametrize("retired", sorted(_RETIRED))
def test_some_doc_still_names_the_retired_path(retired: str) -> None:
    """Non-vacuity for the assertion below — with zero mentions it proves nothing.

    If this fails, every shipped doc has stopped naming the path. That is a fine end state,
    but it means the pairing check is no longer testing anything: retire the entry.
    """
    assert _mentions(retired), (
        f"no shipped doc names {retired} any more, so the pairing assertion below is "
        "vacuous — drop this entry from _RETIRED rather than leaving a test that cannot fail"
    )


@pytest.mark.parametrize("retired", sorted(_RETIRED))
def test_no_doc_names_a_retired_path_without_its_replacement(retired: str) -> None:
    replacement = _RETIRED[retired]
    offenders = [
        str(doc.relative_to(_ROOT)) for doc, text in _mentions(retired) if replacement not in text
    ]
    assert not offenders, (
        f"{offenders} name {retired} without ever naming {replacement}. A reader who lands "
        "there is taught a path that does nothing, with no pointer to the live one."
    )
