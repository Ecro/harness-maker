"""Tests for memory_md.consolidate — exact-slug duplicate merge (PLAN-failures-consolidate-cli).

Merges exact-slug duplicate entries under the flock: count=sum, earliest body
canonical, later bodies fold to dated occurrence bullets, earliest first-seen date
preserved, all-or-nothing on a marker-string fold. Wiki dups concatenate bodies
(no bullet convention). The no-dup case is a byte-identical no-op.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import memory_md


def _write(tmp_path: Path, name: str, entries_md: str) -> Path:
    d = tmp_path / ".claude" / "memory"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(
        f"# {'Failures' if name == 'failures.md' else 'Wiki'} Index\n\n"
        f"{memory_md.OPEN_MARKER}\n{entries_md.strip(chr(10))}\n{memory_md.CLOSE_MARKER}\n",
        encoding="utf-8",
    )
    return f


_DUP_FAILURES = """\
## [fail:test] dupe | 2026-05-19 | count:7
Body of the LATER entry.

## [fail:test] dupe | 2026-05-15 | count:4
Body of the EARLIER entry.

## [fail:render] solo | 2026-05-10 | count:1
Solo body stays untouched.
"""


def test_exact_dup_merges_count_sum_earliest_canonical(tmp_path: Path) -> None:
    f = _write(tmp_path, "failures.md", _DUP_FAILURES)
    groups = memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    text = f.read_text(encoding="utf-8")

    # exactly one heading for the dup slug now
    assert text.count("] dupe |") == 1
    # count summed, earliest first-seen date kept, canonical = earliest body
    assert "## [fail:test] dupe | 2026-05-15 | count:11" in text
    assert "Body of the EARLIER entry." in text
    # later body folded as a dated occurrence bullet (not lost)
    assert "- [2026-05-19] Body of the LATER entry." in text
    # consolidation provenance note, dated today
    assert "- [2026-07-04]" in text
    assert "consolidated" in text
    # solo untouched
    assert "## [fail:render] solo | 2026-05-10 | count:1" in text
    assert "Solo body stays untouched." in text
    # report
    assert len(groups) == 1
    g = groups[0]
    assert g.slug == "dupe"
    assert g.n_entries == 2
    assert g.merged_count == 11
    assert g.first_seen == "2026-05-15"


def test_merged_entry_is_upsertable_again(tmp_path: Path) -> None:
    _write(tmp_path, "failures.md", _DUP_FAILURES)
    memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    # the matches>1 crash is gone → a normal count++ now works
    memory_md.upsert_failure(
        tmp_path, "dupe", "test", "", today="2026-07-05", occurrence_note="happened again"
    )
    text = (tmp_path / ".claude" / "memory" / "failures.md").read_text(encoding="utf-8")
    assert "## [fail:test] dupe | 2026-05-15 | count:12" in text
    assert "- [2026-07-05] happened again" in text


def test_no_dup_is_byte_identical_noop(tmp_path: Path) -> None:
    entries = (
        "## [fail:test] alpha | 2026-05-01 | count:1\nAlpha body.\n\n"
        "## [fail:render] beta | 2026-05-02 | count:2\nBeta body.\n- [2026-05-03] again\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    before = f.read_text(encoding="utf-8")
    groups = memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    assert groups == []
    assert f.read_text(encoding="utf-8") == before


def test_dry_run_writes_nothing_but_reports(tmp_path: Path) -> None:
    f = _write(tmp_path, "failures.md", _DUP_FAILURES)
    before = f.read_text(encoding="utf-8")
    groups = memory_md.consolidate(tmp_path, which="failures", today="2026-07-04", dry_run=True)
    assert f.read_text(encoding="utf-8") == before  # untouched
    assert len(groups) == 1
    assert groups[0].merged_count == 11


def test_markers_preserved_single(tmp_path: Path) -> None:
    f = _write(tmp_path, "failures.md", _DUP_FAILURES)
    memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    assert text.count(memory_md.OPEN_MARKER) == 1
    assert text.count(memory_md.CLOSE_MARKER) == 1


def test_body_with_dash_list_line_not_reordered(tmp_path: Path) -> None:
    # a body line that is an ordinary markdown list ("- foo", NOT "- [date] ...")
    # must stay verbatim in the canonical body, never treated as an occurrence bullet.
    entries = (
        "## [fail:test] dupe | 2026-05-19 | count:2\nLater body.\n\n"
        "## [fail:test] dupe | 2026-05-15 | count:1\n"
        "Earlier body has a list:\n- first item\n- second item\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    # the plain list lines survive in order, right under the canonical body
    assert "Earlier body has a list:\n- first item\n- second item" in text
    assert "count:3" in text


def test_three_member_group(tmp_path: Path) -> None:
    entries = (
        "## [fail:test] trip | 2026-05-03 | count:2\nThird body.\n\n"
        "## [fail:test] trip | 2026-05-01 | count:5\nFirst body.\n\n"
        "## [fail:test] trip | 2026-05-02 | count:3\nSecond body.\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    groups = memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    assert text.count("] trip |") == 1
    assert "## [fail:test] trip | 2026-05-01 | count:10" in text  # 2+5+3, earliest date
    assert groups[0].n_entries == 3
    assert groups[0].merged_count == 10


def test_singleton_dup_singleton_ordering_preserved(tmp_path: Path) -> None:
    entries = (
        "## [fail:test] aaa | 2026-05-01 | count:1\nA.\n\n"
        "## [fail:test] dup | 2026-05-02 | count:1\nDup1.\n\n"
        "## [fail:test] zzz | 2026-05-03 | count:1\nZ.\n\n"
        "## [fail:test] dup | 2026-05-04 | count:1\nDup2.\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    # order: aaa, dup(merged at first pos), zzz
    ai = text.index("] aaa |")
    di = text.index("] dup |")
    zi = text.index("] zzz |")
    assert ai < di < zi
    assert text.count("] dup |") == 1


def test_category_mismatch_keeps_canonical_and_notes(tmp_path: Path) -> None:
    entries = (
        "## [fail:render] mixed | 2026-05-02 | count:1\nLater.\n\n"
        "## [fail:test] mixed | 2026-05-01 | count:1\nEarlier.\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    # canonical (earliest) category kept + the exact mismatch note (pins detection AND kept-cat)
    assert "## [fail:test] mixed | 2026-05-01 | count:2" in text
    assert "mixed categories ['render', 'test'], kept 'test'" in text


def test_collapse_note_marker_abort_is_byte_identical(tmp_path: Path) -> None:
    # a later-body containing a marker string must abort the whole run with no write.
    entries = (
        f"## [fail:test] bad | 2026-05-02 | count:1\ncontains {memory_md.OPEN_MARKER} marker.\n\n"
        "## [fail:test] bad | 2026-05-01 | count:1\nEarlier ok body.\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    before = f.read_text(encoding="utf-8")
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    assert f.read_text(encoding="utf-8") == before  # untouched


def test_wiki_dup_concatenates_bodies(tmp_path: Path) -> None:
    entries = (
        "## [wiki:pattern] w | 2026-05-02\nLater wiki body.\n\n"
        "## [wiki:pattern] w | 2026-05-01\nEarlier wiki body.\n"
    )
    f = _write(tmp_path, "wiki.md", entries)
    groups = memory_md.consolidate(tmp_path, which="wiki", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    assert text.count("] w |") == 1
    assert "## [wiki:pattern] w | 2026-05-01" in text  # earliest date
    # both bodies survive (concatenated — no bullet convention for wiki)
    assert "Earlier wiki body." in text
    assert "Later wiki body." in text
    assert groups[0].merged_count is None  # wiki has no count


def test_wiki_dup_preserves_trailing_dated_body_line(tmp_path: Path) -> None:
    # P0 REGRESSION: a wiki body ending with a `- [date]` line must survive the merge.
    # Wiki has no occurrence-bullet convention, so that line is BODY, not a droppable bullet.
    entries = (
        "## [wiki:pattern] w | 2026-05-02\nLater body.\n- [2026-06-08] see MEMORY.md\n\n"
        "## [wiki:pattern] w | 2026-05-01\nEarlier body.\n- [2026-05-09] earlier ref\n"
    )
    f = _write(tmp_path, "wiki.md", entries)
    memory_md.consolidate(tmp_path, which="wiki", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    assert text.count("] w |") == 1
    # BOTH trailing dated lines survive (they are body, not dropped bullets)
    assert "- [2026-06-08] see MEMORY.md" in text
    assert "- [2026-05-09] earlier ref" in text


def test_wiki_dateless_dup_member_no_dangling_pipe(tmp_path: Path) -> None:
    # a wiki dup with an undated member must not render a `## [wiki:cat] slug | ` trailer.
    entries = (
        "## [wiki:pattern] w\nUndated member.\n\n## [wiki:pattern] w | 2026-05-01\nDated member.\n"
    )
    f = _write(tmp_path, "wiki.md", entries)
    memory_md.consolidate(tmp_path, which="wiki", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    assert text.count("] w") == 1
    assert "## [wiki:pattern] w | \n" not in text  # no dangling pipe-space
    assert "## [wiki:pattern] w | 2026-05-01" in text  # earliest real date wins


def test_dup_member_unparseable_meta_raises_byte_identical(tmp_path: Path) -> None:
    # fail-closed rail: a dup-group member whose failure heading fails _FAILURE_META_RE
    # (legacy `| previous_count:N`) must raise BEFORE any write.
    entries = (
        "## [fail:test] dupe | 2026-05-02 | previous_count:3\nLegacy-format member.\n\n"
        "## [fail:test] dupe | 2026-05-01 | count:2\nClean member.\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    before = f.read_text(encoding="utf-8")
    with pytest.raises(memory_md.MemoryBlockError, match="unparseable failure heading"):
        memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    assert f.read_text(encoding="utf-8") == before


def test_legacy_singleton_tolerated_alongside_real_dup(tmp_path: Path) -> None:
    # the 'kept' half: a SINGLETON with legacy meta survives verbatim while a real dup merges.
    entries = (
        "## [fail:test] legacy | 2026-05-01 | count:9 | previous_count:8\nLegacy singleton.\n\n"
        "## [fail:test] dupe | 2026-05-03 | count:2\nLater.\n\n"
        "## [fail:test] dupe | 2026-05-02 | count:1\nEarlier.\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    # legacy singleton line survives byte-for-byte
    assert "## [fail:test] legacy | 2026-05-01 | count:9 | previous_count:8" in text
    # the real dup still merged
    assert "## [fail:test] dupe | 2026-05-02 | count:3" in text
    assert text.count("] dupe |") == 1


def test_bullets_merged_in_chronological_order(tmp_path: Path) -> None:
    # dup members that ALREADY have occurrence bullets with INTERLEAVING dates → merged & sorted.
    entries = (
        "## [fail:test] b | 2026-05-04 | count:3\nBodyA.\n- [2026-05-10] a1\n- [2026-05-20] a2\n\n"
        "## [fail:test] b | 2026-05-01 | count:2\nBodyB.\n- [2026-05-05] b1\n- [2026-05-15] b2\n"
    )
    f = _write(tmp_path, "failures.md", entries)
    memory_md.consolidate(tmp_path, which="failures", today="2026-07-04")
    text = f.read_text(encoding="utf-8")
    order = [
        text.index(d)
        for d in ("[2026-05-05]", "[2026-05-10]", "[2026-05-15]", "[2026-05-20]", "[2026-07-04]")
    ]
    assert order == sorted(order)  # strictly ascending → chronological + today-note last


def test_which_both_aggregates_across_files(tmp_path: Path) -> None:
    _write(tmp_path, "failures.md", _DUP_FAILURES)
    _write(
        tmp_path,
        "wiki.md",
        "## [wiki:pattern] w | 2026-05-02\nLater.\n\n## [wiki:pattern] w | 2026-05-01\nEarlier.\n",
    )
    groups = memory_md.consolidate(tmp_path, which="both", today="2026-07-04")
    assert len(groups) == 2
    assert groups[0].file == "failures"
    assert groups[0].merged_count == 11
    assert groups[1].file == "wiki"
    assert groups[1].merged_count is None


def test_cli_real_merge_reports_and_mutates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = _write(tmp_path, "failures.md", _DUP_FAILURES)
    rc = memory_md.main(
        ["consolidate", "--root", str(tmp_path), "--file", "failures", "--today", "2026-07-04"]
    )
    assert rc == 0
    assert "count:11" in f.read_text(encoding="utf-8")  # really mutated
    out = capsys.readouterr().out
    assert "failures snapshot-regen" not in out  # slug is 'dupe' here
    assert "failures dupe: 2 entries -> count:11, first-seen 2026-05-15" in out
    assert "consolidate: 1 group(s), 1 entries collapsed" in out


def test_default_date_uses_utcnow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    monkeypatch.setattr(memory_md, "_utcnow", lambda: datetime(2026, 9, 9, tzinfo=UTC))
    _write(tmp_path, "failures.md", _DUP_FAILURES)
    memory_md.consolidate(tmp_path, which="failures")  # no today= → default path
    text = (tmp_path / ".claude" / "memory" / "failures.md").read_text(encoding="utf-8")
    assert "- [2026-09-09] consolidated" in text


def test_noop_on_missing_and_markerless_files(tmp_path: Path) -> None:
    # missing failures.md → [] (no crash)
    assert memory_md.consolidate(tmp_path, which="failures", today="2026-07-04") == []
    # content but no markers → [] and untouched (consolidate's lock already made the dir)
    d = tmp_path / ".claude" / "memory"
    d.mkdir(parents=True, exist_ok=True)
    mk = d / "failures.md"
    mk.write_text("# Failures\n\nno markers here\n", encoding="utf-8")
    before = mk.read_text(encoding="utf-8")
    assert memory_md.consolidate(tmp_path, which="failures", today="2026-07-04") == []
    assert mk.read_text(encoding="utf-8") == before


def test_cli_consolidate_dry_run(tmp_path: Path) -> None:
    f = _write(tmp_path, "failures.md", _DUP_FAILURES)
    before = f.read_text(encoding="utf-8")
    rc = memory_md.main(
        [
            "consolidate",
            "--root",
            str(tmp_path),
            "--file",
            "failures",
            "--today",
            "2026-07-04",
            "--dry-run",
        ]
    )
    assert rc == 0
    assert f.read_text(encoding="utf-8") == before
