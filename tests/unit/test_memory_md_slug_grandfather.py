"""Slug grandfathering — PLAN-second-opinion-invocation-and-slug-cap ADR-004.

``_SLUG_RE`` encoded two independent rules in one pattern: a kebab-case character
class and a 40-char length cap. The corpus violates both (45/123 failure and
49/185 wiki slugs exceed 40 chars; two live wiki slugs under the cap carry ``_``
or ``.``), so the writer refuses keys it wrote itself and ``count++`` is
unreachable for them.

The split: ``_SLUG_SAFE_RE`` (every slug — the characters that would actually
corrupt the tier file) and ``_SLUG_NEW_RE`` (new slugs only — the original
kebab-case + length rule). "Existing" means *present as an entry heading*, which
is why several tests below attack the cheaper wrong implementation `if slug in
text:`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker import memory_md

# The two real corpus violators — under the 40-char cap, outside `[a-z0-9-]`.
# Length grandfathering alone does not reach these, which is why a 65-char case
# cannot stand in for them.
REAL_UNDERSCORE_SLUG = "metrics-rotation-reader-via-_metrics_io"
REAL_DOTTED_SLUG = "adr-supersession-precedent-v0.22.3"

# The longest slug in the live failures corpus (65 chars).
REAL_LONG_SLUG = "task-land-squash-commits-whole-index-sweeps-concurrent-base-churn"


def _fresh_tier(path: Path, kind: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {kind} Index\n\n{memory_md.OPEN_MARKER}\n{memory_md.CLOSE_MARKER}\n",
        encoding="utf-8",
    )


def _seed_failure(path: Path, slug: str, *, date: str = "2026-01-01", count: int = 1) -> None:
    """Write a failures tier whose block already contains ``slug`` — bypassing the
    validator, exactly as the historical corpus was written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Failures Index\n\n"
        f"{memory_md.OPEN_MARKER}\n"
        f"## [fail:design] {slug} | {date} | count:{count}\n"
        "seeded body.\n"
        f"{memory_md.CLOSE_MARKER}\n",
        encoding="utf-8",
    )


def _seed_wiki(
    path: Path, slug: str, *, date: str = "2026-01-01", body: str = "seeded body."
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Wiki Index\n\n"
        f"{memory_md.OPEN_MARKER}\n"
        f"## [wiki:pattern] {slug} | {date}\n"
        f"{body}\n"
        f"{memory_md.CLOSE_MARKER}\n",
        encoding="utf-8",
    )


# ── (a) existing over-length failure slug receives count++ ────────────────────


def test_existing_65_char_failure_slug_receives_count_increment(tmp_path: Path) -> None:
    fail = tmp_path / ".claude" / "memory" / "failures.md"
    _seed_failure(fail, REAL_LONG_SLUG, count=2)
    assert len(REAL_LONG_SLUG) == 65

    memory_md.upsert_failure(
        tmp_path,
        REAL_LONG_SLUG,
        "design",
        "recurred again.",
        today="2026-07-25",
        occurrence_note="third sighting.",
    )

    text = fail.read_text("utf-8")
    # Pin the incremented VALUE, not merely that the call returned.
    assert "count:3" in text
    assert "count:2" not in text
    assert text.count(f"] {REAL_LONG_SLUG} ") == 1
    assert "2026-01-01" in text  # first-seen date preserved


# ── (b) existing over-length wiki slug is replaced in place ───────────────────


def test_existing_65_char_wiki_slug_is_replaced_in_place(tmp_path: Path) -> None:
    # The wiki path has no count++, so (a) cannot cover it — 26% of the live wiki
    # corpus is over the cap and was unwritable through the CLI.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _seed_wiki(wiki, REAL_LONG_SLUG, body="OLD BODY.")

    memory_md.upsert_wiki(tmp_path, REAL_LONG_SLUG, "pattern", "NEW BODY.", today="2026-07-25")

    text = wiki.read_text("utf-8")
    assert text.count(f"] {REAL_LONG_SLUG} ") == 1  # replaced, not duplicated
    assert "NEW BODY." in text
    assert "OLD BODY." not in text


# ── (c) the real character-class violators ────────────────────────────────────


@pytest.mark.parametrize(
    "slug",
    [REAL_UNDERSCORE_SLUG, REAL_DOTTED_SLUG],
    ids=["underscore", "dotted"],
)
def test_existing_character_class_violator_is_accepted(tmp_path: Path, slug: str) -> None:
    # Both sit UNDER the 40-char cap, so length grandfathering does not reach them.
    assert len(slug) <= 40
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _seed_wiki(wiki, slug, body="OLD.")

    memory_md.upsert_wiki(tmp_path, slug, "pattern", "REFRESHED.", today="2026-07-25")

    text = wiki.read_text("utf-8")
    assert text.count(f"] {slug} ") == 1
    assert "REFRESHED." in text


@pytest.mark.parametrize(
    "slug",
    [REAL_UNDERSCORE_SLUG, REAL_DOTTED_SLUG],
    ids=["underscore", "dotted"],
)
def test_same_string_as_a_new_slug_is_rejected(tmp_path: Path, slug: str) -> None:
    # The identical string must be refused when it is NOT already in the file —
    # grandfathering is keyed on presence, never on the string itself.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")

    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_wiki(tmp_path, slug, "pattern", "body.", today="2026-07-25")
    assert "new slug" in str(exc.value)


# ── (d) over-length NEW slug is rejected, naming the length rule ──────────────


def test_new_65_char_slug_is_rejected_with_length_message(tmp_path: Path) -> None:
    fail = tmp_path / ".claude" / "memory" / "failures.md"
    _fresh_tier(fail, "Failures")

    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_failure(tmp_path, REAL_LONG_SLUG, "design", "body.", today="2026-07-25")
    msg = str(exc.value)
    assert "new slug" in msg
    assert "40" in msg


# ── (e) new-slug length boundary, as a PAIR ───────────────────────────────────


def test_new_slug_length_boundary_pair(tmp_path: Path) -> None:
    # A single-sided assertion cannot distinguish a cap of 40 from a cap of 80.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")

    at_cap = "a" * 40
    over_cap = "a" * 41

    memory_md.upsert_wiki(tmp_path, at_cap, "pattern", "ok.", today="2026-07-25")
    assert f"] {at_cap} " in wiki.read_text("utf-8")

    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_wiki(tmp_path, over_cap, "pattern", "nope.", today="2026-07-25")
    assert "new slug" in str(exc.value)


# ── (f) file-corrupting characters are refused even for an EXISTING slug ──────


@pytest.mark.parametrize(
    "slug",
    ["foo|bar", "foo]bar", "deps-drift$(id)", "a`id`b", "x;rm-rf", "p&q"],
    ids=["pipe", "bracket", "cmdsub", "backtick", "semicolon", "ampersand"],
)
def test_corrupting_character_rejected_even_when_already_present(tmp_path: Path, slug: str) -> None:
    # `_SLUG_SAFE_RE` is the correctness floor, not a style rule. Two distinct reasons:
    # `|` collides with the `| date | count:N` meta field and `]` breaks the
    # `[tier:category]` bracket (reparse); `$(…)`, backticks, `;` and `&` reach an
    # UNQUOTED `--slug` in a rendered `!uv run …` Bash line via `wrapup.md.j2`, and
    # `failures.md` is a committed deliverable — so a poisoned heading would be
    # grandfathered here and executed there on the next recurrence.
    #
    # Both round-trip through `_entry_headings`: `(?P<cat>[^\]]+)` stops at the first
    # `]`, then `(?P<slug>\S+)` captures `foo|bar` / `foo]bar` intact. So the slug IS
    # in the existing-heading set, and the wrong implementation
    # `if present: skip all checks` accepts it — which is what these params reject.
    # A whitespace slug canNOT be seeded this way (see the sibling test below).
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _seed_wiki(wiki, slug, body="OLD.")

    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_wiki(tmp_path, slug, "pattern", "body.", today="2026-07-25")
    msg = str(exc.value)
    assert "new slug" not in msg  # distinct diagnosis from the length/kebab rule
    assert "character" in msg.lower()


def test_every_live_corpus_slug_still_passes_the_floor() -> None:
    # The floor was tightened from a deny-3-characters rule to an allowlist. That is
    # only free if the existing corpus clears it — otherwise the tightening reopens
    # H3 for whatever it excludes. Pin the property against the real tier files.
    repo_root = Path(__file__).resolve().parents[2]
    heading = re.compile(r"^##\s+\[[^:\]]+:[^\]]+\]\s+(\S+)")
    checked = 0
    for tier in ("wiki.md", "failures.md"):
        path = repo_root / ".claude" / "memory" / tier
        if not path.exists():  # a fresh clone has no memory tiers yet
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            m = heading.match(line)
            if m:
                checked += 1
                assert memory_md._SLUG_SAFE_RE.fullmatch(m.group(1)), (
                    f"{tier}: existing slug {m.group(1)!r} fails the tightened floor"
                )
    assert checked > 0, "no headings found — the assertion above never ran"


def test_whitespace_slug_rejected_as_a_new_slug(tmp_path: Path) -> None:
    # A whitespace slug is NOT seedable as "existing": `_HEADING_RE`'s `(?P<slug>\S+)`
    # truncates `foo bar` to `foo`, so it can never enter the existing-heading set —
    # which is itself the reason `_SLUG_SAFE_RE` must reject it. Asserting it under
    # the "already present" name would be invariant over that dimension.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _seed_wiki(wiki, "foo bar", body="OLD.")

    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_wiki(tmp_path, "foo bar", "pattern", "body.", today="2026-07-25")
    msg = str(exc.value)
    assert "corrupt" in msg.lower() or "character" in msg.lower()


# ── presence is derived from headings, NOT from a substring scan ──────────────


def test_slug_quoted_in_another_entrys_body_is_not_grandfathered(tmp_path: Path) -> None:
    # Memory bodies routinely quote other entries' slugs. Under the wrong
    # implementation `if slug in text:` an over-cap slug merely MENTIONED in a body
    # would be treated as existing, and a brand-new over-cap entry would be written —
    # reintroducing the corpus drift ADR-004 exists to stop.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _seed_wiki(wiki, "real-entry", body=f"see also {REAL_LONG_SLUG} for context.")
    assert REAL_LONG_SLUG in wiki.read_text("utf-8")  # present as TEXT, not as a heading

    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_wiki(tmp_path, REAL_LONG_SLUG, "pattern", "body.", today="2026-07-25")
    assert "new slug" in str(exc.value)


def test_presence_does_not_leak_across_tiers(tmp_path: Path) -> None:
    # Grandfathering is per-tier-file: a slug present in wiki.md must not license a
    # brand-new over-cap entry in failures.md.
    _seed_wiki(tmp_path / ".claude" / "memory" / "wiki.md", REAL_LONG_SLUG)
    _fresh_tier(tmp_path / ".claude" / "memory" / "failures.md", "Failures")

    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_failure(tmp_path, REAL_LONG_SLUG, "design", "body.", today="2026-07-25")
    assert "new slug" in str(exc.value)


# ── validation order: the length rule runs AFTER the file is parsed ───────────


def test_new_slug_length_check_runs_after_block_parsing(tmp_path: Path) -> None:
    # ADR-004 moves validation inside the lock, after the read. The observable: when
    # the tier file is structurally corrupt AND the slug is a new over-cap one, the
    # caller must learn about the corruption first — `_locate_block` raises before the
    # length rule is reached. Today the slug check fires at module top and wins, so
    # this pins the ordering rather than merely restating it.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(
        "# Wiki Index\n\n"
        f"{memory_md.OPEN_MARKER}\n"
        f"{memory_md.OPEN_MARKER}\n"
        f"{memory_md.CLOSE_MARKER}\n",
        encoding="utf-8",
    )

    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_wiki(tmp_path, REAL_LONG_SLUG, "pattern", "body.", today="2026-07-25")
    msg = str(exc.value)
    assert "marker" in msg.lower()
    assert "new slug" not in msg


def test_new_slug_validated_on_the_marker_absent_create_branch(tmp_path: Path) -> None:
    # `_upsert`'s `located is None` branch creates the block from scratch. Every other
    # test here seeds a file that already HAS markers, so that branch is never taken —
    # and it is the one place where the existing-heading set is empty by construction,
    # making it the easiest spot to forget the new-slug rule entirely.
    with pytest.raises(memory_md.MemoryBlockError) as exc:
        memory_md.upsert_wiki(tmp_path, REAL_LONG_SLUG, "pattern", "body.", today="2026-07-25")
    assert "new slug" in str(exc.value)
    assert not (tmp_path / ".claude" / "memory" / "wiki.md").exists()


# ── (g) the real CLI path, not just `_upsert` ─────────────────────────────────


def test_grandfathered_slug_through_the_cli_main(tmp_path: Path) -> None:
    # H3's observed symptom is a non-zero CLI exit; a test that never runs the CLI
    # cannot see a future parser-layer constraint. `--occurrence-note` is mutually
    # exclusive with `--body/--body-file`, and for upsert-failure it IS the payload.
    fail = tmp_path / ".claude" / "memory" / "failures.md"
    _seed_failure(fail, REAL_LONG_SLUG, count=1)

    rc = memory_md.main(
        [
            "upsert-failure",
            "--root",
            str(tmp_path),
            "--slug",
            REAL_LONG_SLUG,
            "--category",
            "design",
            "--occurrence-note",
            "cli sighting.",
            "--today",
            "2026-07-25",
        ]
    )

    assert rc == 0
    text = fail.read_text("utf-8")
    assert "count:2" in text


def test_new_over_length_slug_through_the_cli_main_names_the_new_slug_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `rc != 0` alone cannot distinguish "rejected because NEW and over-length" from
    # "rejected because the un-split rule refuses every over-40 slug, present or not"
    # — the exact wrong implementation ADR-004 removes. Pin the diagnosis.
    _fresh_tier(tmp_path / ".claude" / "memory" / "failures.md", "Failures")

    rc = memory_md.main(
        [
            "upsert-failure",
            "--root",
            str(tmp_path),
            "--slug",
            REAL_LONG_SLUG,
            "--category",
            "design",
            "--occurrence-note",
            "first sighting.",
            "--today",
            "2026-07-25",
        ]
    )

    assert rc != 0
    assert "new slug" in capsys.readouterr().err
