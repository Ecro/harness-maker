"""Phase 5 / ADR-005+006 — `upsert-failure` evicts stale one-off entries at write time.

`failures.md` had 156 entries / 266KB, 87% of them `count:1`, and no eviction mechanism
anywhere in the code. ADR-005 picks the predicate — `count:1` AND older than 90 days,
`count>=2` permanently exempt at any age — because the entries encode system invariants,
not model-capability workarounds, so age alone is the wrong test. ADR-006 puts the pass
inside `upsert-failure` rather than in a wrapup step: the growth point and the eviction
point become the same call, so a manual-commit workflow cannot skip it (the documented
failure mode of the Second Brain promotion step, which fires only as often as wrapup runs).

Archive, never delete — `.claude/memory/archive/failures-<YYYY>.md`.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker import memory_md
from harness_maker.memory_md import CLOSE_MARKER, OPEN_MARKER, upsert_failure

_TODAY = "2026-08-05"


def _days_ago(n: int) -> str:
    return (datetime(2026, 8, 5, tzinfo=UTC) - timedelta(days=n)).date().isoformat()


def _entry(slug: str, date: str, count: int, *, category: str = "design") -> str:
    return f"## [fail:{category}] {slug} | {date} | count:{count}\n- seeded body for {slug}\n"


def _seed(root: Path, *entries: str) -> Path:
    path = root / ".claude" / "memory" / "failures.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Failures Index\n\n" + OPEN_MARKER + "\n" + "".join(entries) + CLOSE_MARKER + "\n",
        encoding="utf-8",
    )
    return path


def _live(root: Path) -> str:
    return (root / ".claude" / "memory" / "failures.md").read_text(encoding="utf-8")


def _archive(root: Path, year: int = 2026) -> Path:
    return root / ".claude" / "memory" / "archive" / f"failures-{year}.md"


def _touch(root: Path, slug: str = "a-fresh-failure") -> None:
    """Any upsert triggers the pass — the pass is a side effect of writing, not a command."""
    upsert_failure(root, slug, "design", "body", occurrence_note="note", today=_TODAY)


def test_an_aged_single_occurrence_entry_is_moved_to_the_archive(tmp_path: Path) -> None:
    _seed(tmp_path, _entry("an-old-one-off", _days_ago(120), 1))
    _touch(tmp_path)
    assert "an-old-one-off" not in _live(tmp_path)
    assert "an-old-one-off" in _archive(tmp_path).read_text(encoding="utf-8")


def test_a_recurring_entry_is_exempt_at_any_age(tmp_path: Path) -> None:
    """ADR-005: `count>=2` is the recurrence signal — the whole reason the tier exists."""
    _seed(tmp_path, _entry("an-ancient-recurrence", _days_ago(3000), 2))
    _touch(tmp_path)
    assert "an-ancient-recurrence" in _live(tmp_path)
    assert not _archive(tmp_path).exists()


def test_a_recent_one_off_stays(tmp_path: Path) -> None:
    _seed(tmp_path, _entry("last-weeks-failure", _days_ago(7), 1))
    _touch(tmp_path)
    assert "last-weeks-failure" in _live(tmp_path)


@pytest.mark.parametrize(("age", "archived"), [(89, False), (90, False), (91, True)])
def test_the_ninety_day_boundary(tmp_path: Path, age: int, archived: bool) -> None:
    """`older than 90 days` is strict — exactly 90 stays, so the boundary is not a guess."""
    _seed(tmp_path, _entry("boundary-case", _days_ago(age), 1))
    _touch(tmp_path)
    assert ("boundary-case" not in _live(tmp_path)) is archived


def test_the_entry_just_written_is_never_archived(tmp_path: Path) -> None:
    _seed(tmp_path, _entry("unrelated-old", _days_ago(400), 1))
    _touch(tmp_path, "todays-new-failure")
    assert "todays-new-failure" in _live(tmp_path)


def test_a_calendar_invalid_date_is_preserved_and_warned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`2026-99-99` matches the heading SHAPE but is not a date.

    Preserve + warn, and never abort the pass for the entries after it — a single bad
    heading must not silently freeze eviction for the whole file.
    """
    _seed(
        tmp_path,
        _entry("bad-date-entry", "2026-99-99", 1),
        _entry("aged-after-the-bad-one", _days_ago(200), 1),
    )
    _touch(tmp_path)
    live = _live(tmp_path)
    assert "bad-date-entry" in live
    assert "aged-after-the-bad-one" not in live
    assert "bad-date-entry" in capsys.readouterr().err


def test_an_archive_write_failure_never_loses_the_upsert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-006's hard constraint: the pass is a side effect and must not fail the write.

    On an archive failure the aged entries stay in `failures.md` — the eviction is skipped,
    never half-applied, so no entry can exist in neither file.
    """
    _seed(tmp_path, _entry("aged-but-unarchivable", _days_ago(200), 1))

    def _boom(*_a: object, **_kw: object) -> None:
        raise OSError("archive volume is read-only")

    monkeypatch.setattr(memory_md, "_append_archive", _boom)
    _touch(tmp_path, "the-write-that-must-survive")
    live = _live(tmp_path)
    assert "the-write-that-must-survive" in live
    assert "aged-but-unarchivable" in live


def test_one_years_archive_failing_does_not_strand_or_duplicate_another_year(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The multi-year partial-failure case, unasserted until three reviewers named it.

    The original loop archived every year and only then returned the pruned lines, so a
    failure on the SECOND year unwound past the first year's already-durable write. The
    caller kept the unpruned text, leaving those entries in BOTH files — and since they stay
    `count:1` and aged, the next upsert archived them again. A persistent fault on one year
    made unbounded duplication the steady state, not a one-shot crash artifact.
    """
    _seed(
        tmp_path,
        _entry("from-2024", "2024-03-04", 1),
        _entry("from-2025", "2025-03-04", 1),
    )
    real = memory_md._append_archive

    def _fail_2025(root: object, year: int, entry_lines: list[str]) -> None:
        if year == 2025:
            raise OSError("simulated failure on this year only")
        real(root, year, entry_lines)  # type: ignore[arg-type]

    monkeypatch.setattr(memory_md, "_append_archive", _fail_2025)
    _touch(tmp_path, "first-trigger")
    live = _live(tmp_path)
    # The year that landed is gone from the live file...
    assert "from-2024" not in live
    # ...and the year that failed is still there, not lost.
    assert "from-2025" in live

    # Now the second pass, with the fault cleared: 2024 must NOT be archived twice.
    monkeypatch.setattr(memory_md, "_append_archive", real)
    _touch(tmp_path, "second-trigger")
    text = _archive(tmp_path, 2024).read_text(encoding="utf-8")
    assert sum(1 for ln in text.splitlines() if ln.startswith("## [fail:")) == 1
    assert "from-2025" in _archive(tmp_path, 2025).read_text(encoding="utf-8")


def test_a_corrupt_marker_block_fails_closed_on_read(tmp_path: Path) -> None:
    """Fail-closed on a corrupt INPUT file, asserted so the archive pass cannot mask it.

    Scope, stated honestly: this exercises the pre-existing `_locate_block` at the top of
    `_upsert`, NOT the second one the archive pass added. Verified by moving that second
    check back inside the swallowing `try` — this test still passed, so it does not cover it.

    The second check was hoisted out of the `except Exception` anyway (a marker duplicated by
    a future splice bug is corruption, not an archive I/O problem, and must not be reported
    as "archive pass skipped"). That hoist is forward defense with **no reachable failing
    input today**: `_upsert` already rejects a body or occurrence note containing a marker
    string, and rejects heading-shaped body lines, so the spliced text cannot gain a marker
    the input did not have. Recorded rather than covered — a test that passed for the wrong
    reason would imply a guard that does not exist.
    """
    path = tmp_path / ".claude" / "memory" / "failures.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Failures Index\n\n"
        + OPEN_MARKER
        + "\n"
        + _entry("existing", _days_ago(2), 1)
        + CLOSE_MARKER
        + "\n"
        + CLOSE_MARKER
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(memory_md.MemoryBlockError):
        _touch(tmp_path, "any-slug")


def test_archiving_twice_does_not_duplicate(tmp_path: Path) -> None:
    _seed(tmp_path, _entry("archived-once", _days_ago(200), 1))
    _touch(tmp_path, "first-trigger")
    _touch(tmp_path, "second-trigger")
    # Count HEADINGS, not slug occurrences — the slug also appears in the entry body.
    text = _archive(tmp_path).read_text(encoding="utf-8")
    assert sum(1 for ln in text.splitlines() if ln.startswith("## [fail:")) == 1


def test_entries_are_filed_under_their_own_year(tmp_path: Path) -> None:
    _seed(tmp_path, _entry("from-two-years-back", "2024-03-04", 1))
    _touch(tmp_path)
    assert "from-two-years-back" in _archive(tmp_path, 2024).read_text(encoding="utf-8")


def test_the_surviving_file_is_still_upsertable(tmp_path: Path) -> None:
    """Non-vacuity of the whole feature: the pruned file must round-trip through the writer.

    An archive pass that corrupted the marker block would pass every assertion above and
    break the next wrapup.
    """
    _seed(tmp_path, _entry("aged", _days_ago(200), 1), _entry("kept", _days_ago(2), 1))
    _touch(tmp_path, "trigger-one")
    upsert_failure(tmp_path, "kept", "design", "b", occurrence_note="again", today=_TODAY)
    assert "count:2" in _live(tmp_path)


def test_the_archive_is_a_deliverable_not_user_dirt() -> None:
    """ADR-015: the archive must land in the squash like `failures.md` itself."""
    from harness_maker.worktree import _is_create_guard_harness_artifact, _path_owner

    assert _path_owner(".claude/memory/archive/failures-2026.md") == "deliverable"
    # Anchored on the directory, not a substring — a user's `notes/claude/memory/archive`
    # must not be swept into harness ownership.
    assert _path_owner("notes/.claude/memory/archive/failures-2026.md") == "user"
    # The create-guard side: an uncommitted archive file must not block `worktree create`.
    assert _is_create_guard_harness_artifact("?? .claude/memory/archive/failures-2026.md")


def test_the_archive_is_folded_into_the_base_memory_commit() -> None:
    """The eviction is only an archive if the archive reaches git.

    On the `feature_branch_workflow` path (the Production default, and this repo's own
    setting) wrapup amends base-side memory into the squash via `commit_base_memory`, which
    stages only paths passing `_is_human_memory_tier_path`. Without `archive/` there, an
    eviction commits `failures.md` MINUS the entries and leaves the archive as untracked
    base dirt — a delete from git, which inverts ADR-005's "archive, never delete".

    `test_wrapup_memory_fold`'s correspondence test cannot catch this: it derives the
    expected set by scanning the rendered wrapup TEMPLATE, and this writer is invoked from
    Python inside `upsert-failure`, so it never appears in that text.
    """
    from harness_maker.worktree import _is_human_memory_tier_path

    assert _is_human_memory_tier_path(".claude/memory/archive/failures-2026.md")
    # Still scoped: a non-.md file and a sibling directory must not ride along.
    assert not _is_human_memory_tier_path(".claude/memory/archive/notes.txt")
    assert not _is_human_memory_tier_path(".claude/memory/semantic/x.md")


def test_the_archive_path_is_not_gitignored() -> None:
    """Assert, do not assume — ADR-005 requires the archive to be COMMITTED alongside.

    `.gitignore` re-includes `!.claude/memory/` then re-ignores only semantic/, episodic/,
    profile/ and *.lock. The file's own header records a past regression where new memory
    files were silently dropped from `git add`, so this is checked against real git.
    """
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        ["git", "check-ignore", "-v", ".claude/memory/archive/failures-2026.md"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.stdout.strip() == "", proc.stdout
    # Positive control: a path that IS ignored, so a broken invocation cannot pass silently.
    ignored = subprocess.run(
        ["git", "check-ignore", "-v", ".claude/memory/semantic/x.md"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert ignored.stdout.strip() != ""
