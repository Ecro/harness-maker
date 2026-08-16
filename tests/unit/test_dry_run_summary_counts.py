"""`make --dry-run` must count what the render will actually do.

Two defects, both of which made the preview overstate the change on every re-render of an
unchanged harness:

1. Existence was decided by walking `.claude/` and comparing blueprint keys against it. But
   `.cursor/`, `.codex/`, `.agents/`, `AGENTS.md` and the root `CLAUDE.md` are written
   OUTSIDE `.claude/`, so none of them could ever match — every one was reported NEW,
   forever. Measured on this repo's own harness (claude-code + cursor + codex, nothing
   changed): the preview said `NEW: 43` when the true answer was 0, because 42 of those live
   in sibling trees and the 43rd was the root `CLAUDE.md`.
2. KEEP and MERGE are reconcile decisions about files that EXIST, so each was also counted
   in REPLACE — reported once honestly and once as an overwrite that will not happen.

The user-facing cost is specific: a preview is shown precisely so someone can decide whether
to proceed, and "43 new files" invites a Cancel on a re-render that changes nothing. Both
counts now come from `resolve_output_path`, the resolver `render` and `reconcile` already
share, so the three cannot disagree about where a file lives.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.cli import _emit_dry_run_summary
from harness_maker.models import Blueprint, FileEntry, HarnessConfig


def _blueprint(paths: list[str]) -> Blueprint:
    return Blueprint(
        config=HarnessConfig(),
        files=[FileEntry(path=Path(p), template="x.j2", context={}) for p in paths],
    )


def _counts(out: str) -> dict[str, int]:
    got: dict[str, int] = {}
    for line in out.splitlines():
        for key in ("NEW:", "REPLACE:", "KEEP:", "MERGE:", "Total:"):
            if line.strip().startswith(key):
                got[key.rstrip(":")] = int(line.split()[1])
    return got


@pytest.fixture
def harness(tmp_path: Path) -> Path:
    """A project whose harness is fully rendered — sibling trees included."""
    dotclaude = tmp_path / ".claude"
    for rel in ("commands/hm/plan.md", "agents/code-reviewer.md"):
        p = dotclaude / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    for rel in (".cursor/hooks.json", ".codex/config.toml", ".agents/skills/hm-plan/SKILL.md"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("x", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    return dotclaude


_ALL = [
    "commands/hm/plan.md",
    "agents/code-reviewer.md",
    ".cursor/hooks.json",
    ".codex/config.toml",
    ".agents/skills/hm-plan/SKILL.md",
    "AGENTS.md",
    "../CLAUDE.md",
]


def test_files_outside_dotclaude_are_not_reported_as_new(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole defect, in one assertion: nothing here is new — all seven are on disk."""
    _emit_dry_run_summary(_blueprint(_ALL), harness)

    counts = _counts(capsys.readouterr().out)
    assert counts["NEW"] == 0, (
        f"{counts['NEW']} of 7 existing files reported as NEW. Sibling trees (.cursor/, "
        ".codex/, .agents/, AGENTS.md) and the root CLAUDE.md are written outside .claude/, "
        "so an existence check scoped to .claude/ can never see them."
    )
    assert counts["REPLACE"] == 7


def test_a_genuinely_absent_file_is_still_reported_as_new(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative control. Without it, `return 0` for NEW would pass the test above."""
    _emit_dry_run_summary(_blueprint([*_ALL, ".cursor/rules/harness.mdc"]), harness)

    counts = _counts(capsys.readouterr().out)
    assert counts["NEW"] == 1, "a sibling-tree file that is NOT on disk must count as NEW"
    assert counts["REPLACE"] == 7


def test_kept_and_merged_files_are_not_also_counted_as_replaced(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A KEEP is a file that will NOT be overwritten — reporting it under REPLACE is false."""
    _emit_dry_run_summary(
        _blueprint(_ALL),
        harness,
        keep_paths=frozenset({Path("../CLAUDE.md")}),
        merge_paths=frozenset({Path("AGENTS.md"), Path(".codex/config.toml")}),
    )

    counts = _counts(capsys.readouterr().out)
    assert counts["KEEP"] == 1
    assert counts["MERGE"] == 2
    assert counts["REPLACE"] == 4, "kept/merged files must be excluded from REPLACE"


def test_the_four_buckets_partition_the_blueprint(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`Total` is printed as the blueprint size, so the buckets have to add up to it.

    They did not before: KEEP and MERGE overlapped REPLACE, so a reader summing the column
    got more files than the harness contains.
    """
    _emit_dry_run_summary(
        _blueprint([*_ALL, ".cursor/rules/harness.mdc"]),
        harness,
        keep_paths=frozenset({Path("../CLAUDE.md")}),
        merge_paths=frozenset({Path("AGENTS.md")}),
    )

    c = _counts(capsys.readouterr().out)
    assert c["NEW"] + c["REPLACE"] + c["KEEP"] + c["MERGE"] == c["Total"] == 8
