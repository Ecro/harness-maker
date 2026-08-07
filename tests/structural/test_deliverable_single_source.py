"""One definition of "deliverable", three consumers, asserted to agree.

The same concept was spelled out separately in `.gitignore`'s negations, in
`worktree._DELIVERABLE_RE`, and in `wrapup.md.j2`'s staging flags — and the three had
already drifted apart: ten prefixes, four, and five. Each disagreement has its own symptom:

  * missing from `.gitignore`  -> the file is never committable
  * missing from the regex     -> the create-guard refuses to forgive it, blocking execute
  * missing from the manifest  -> **`wrapup_land` omits it while reporting success**

The third is the dangerous one, because the receipt says the work landed. It shipped:
ABLATION and MATRIX were committable and forgiven, and dropped by wrapup — two phases'
entire deliverables, saved only by passing `--optional` by hand.

`DELIVERABLE_PREFIXES` is now the single definition. This file is what keeps it single.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.worktree import DELIVERABLE_PREFIXES, _is_deliverable_path
from harness_maker.wrapup_land import derive_deliverable_globs

_REPO = Path(__file__).resolve().parents[2]
_GITIGNORE = _REPO / ".gitignore"
_NEGATION = re.compile(r"^!work-docs/([A-Z]+)-\*\.md$", re.MULTILINE)


def test_the_source_is_not_empty() -> None:
    """Positive control — every set comparison below holds vacuously over an empty tuple."""
    assert len(DELIVERABLE_PREFIXES) >= 4
    assert "PLAN" in DELIVERABLE_PREFIXES


def test_gitignore_negations_match_the_source() -> None:
    """A prefix the gitignore does not un-ignore produces a file nobody can commit."""
    ignored = set(_NEGATION.findall(_GITIGNORE.read_text(encoding="utf-8")))
    source = set(DELIVERABLE_PREFIXES)
    assert ignored == source, (
        f"gitignore-only: {sorted(ignored - source)}; source-only: {sorted(source - ignored)}"
        " — add the prefix to DELIVERABLE_PREFIXES and mirror the `!work-docs/<X>-*.md` line"
    )


@pytest.mark.parametrize("prefix", DELIVERABLE_PREFIXES)
def test_every_prefix_is_forgiven_by_the_create_guard(prefix: str) -> None:
    """A prefix the guard does not forgive blocks `worktree create`, so execute cannot start."""
    assert _is_deliverable_path(f"work-docs/{prefix}-some-task.md")


@pytest.mark.parametrize("prefix", DELIVERABLE_PREFIXES)
def test_every_prefix_is_staged_by_wrapup(prefix: str) -> None:
    """The dangerous arm: a prefix the manifest omits is dropped WITH a success receipt."""
    globs = derive_deliverable_globs("some-task")
    assert any(g.startswith(f"work-docs/{prefix}-") for g in globs), (
        f"{prefix} is committable and forgiven but wrapup_land would not stage it"
    )


def test_the_guard_still_rejects_non_deliverables() -> None:
    """Discrimination — a rule that forgives everything forgives the WIP it must block.

    The create-guard's whole job is to distinguish a deliverable from coexisting code work;
    widening the prefix set must not turn it into a pass-through.
    """
    for path in (
        "work-docs/random.md",
        "work-docs/PLAN-experiments/notes.md",
        "src/harness_maker/cli.py",
        "work-docs/PLANNING.md",
    ):
        assert not _is_deliverable_path(path), path


def test_the_rendered_wrapup_command_still_carries_its_own_paths() -> None:
    """The derivation ADDS to the caller's list; it must not have replaced it.

    A non-default `work_docs.dir` is not covered by the derivation (same accepted limit as
    `_DELIVERABLE_RE`), so the template's explicit paths are the fallback that keeps a
    customised layout working.
    """
    template = (
        _REPO / "src" / "harness_maker" / "templates" / "stages" / "wrapup.md.j2"
    ).read_text(encoding="utf-8")
    assert "--required" in template
    assert "--optional .claude/memory/" in template, "memory is not a deliverable glob"
