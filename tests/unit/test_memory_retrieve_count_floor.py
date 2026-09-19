"""Phase 2 — the count floor (SPEC-observed-harness-gaps S3/S4, AC-004/005/006 + P-6..P-9).

`top_candidates` drops every entry whose token-overlap score is exactly 0, before any
rerank, and `count` is parsed but never ranked on. A 239-entry failure corpus therefore
returned zero `[fail:*]` for a failure-shaped topic.

The floor admits the highest-`count` failure entries regardless of vocabulary, in a
SEPARATE labelled fence section with its OWN byte budget (ADR-001), so the lexical
section stays byte-identical — measured, not argued.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.memory_retrieve import (
    FLOOR_LABEL,
    FLOOR_SECTION_HEADER,
    MemoryEntry,
    floor_candidates,
    load_memory_dir,
    render_candidates_block,
    top_candidates,
)
from harness_maker.memory_retrieve import (
    _excerpt_recent_blocks as excerpt_recent_blocks,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_MEMORY_DIR = REPO_ROOT / ".claude" / "memory"
FENCE_CLOSE = "</memory_candidates>"


def _entry(
    slug: str,
    *,
    tier: str = "fail",
    count: int | None = None,
    body: str = "",
    date: str = "2026-01-01",
) -> MemoryEntry:
    return MemoryEntry(
        tier=tier,
        category="test",
        slug=slug,
        date=date,
        count=count,
        body=body or f"body of {slug}",
        source_path="x.md",
        line_offset=1,
    )


def _sections(rendered: str) -> tuple[str, str]:
    """Split the fence into (lexical body, floor body) on the floor section header."""
    inner = rendered.split(">\n", 1)[1].split(FENCE_CLOSE, 1)[0]
    head, sep, tail = inner.partition(FLOOR_SECTION_HEADER)
    return (head, sep + tail) if sep else (inner, "")


def _floor_slugs(rendered: str) -> list[str]:
    """Slugs whose heading carries the floor label."""
    return [
        m.group(1)
        for line in rendered.splitlines()
        if FLOOR_LABEL in line and (m := re.search(r"\] ([a-z0-9-]+) \|", line))
    ]


def _lexical_entry_bodies(rendered: str) -> str:
    """Everything inside the fence up to the floor section header — the AC-006 subject."""
    return _sections(rendered)[0]


# --------------------------------------------------------------------------------------
# AC-004 / AC-005 — a zero-overlap high-recurrence entry is admitted, and labelled
# --------------------------------------------------------------------------------------


def _zero_overlap_corpus() -> tuple[list[MemoryEntry], str]:
    """A high-count entry sharing no normalized token with the topic (fixture precondition)."""
    topic = "kangaroo zeppelin marmalade"
    entries = [
        _entry("quicksort-pivot-choice", count=13, body="- [2026-01-01] pivot text\n"),
        _entry("hash-collision-probe", count=8, body="- [2026-01-02] probe text\n"),
        _entry("kangaroo-zeppelin-hit", count=1, body="- [2026-01-03] lexical hit body\n"),
    ]
    return entries, topic


def test_count_floor_admits_zero_overlap_entry() -> None:
    """AC-004: the top-`count` entry appears even with zero lexical overlap."""
    from harness_maker.memory_retrieve import score_entry, topic_tokens

    entries, topic = _zero_overlap_corpus()
    high = entries[0]
    # Fixture precondition — makes the test non-vacuous.
    assert score_entry(high, topic_tokens(topic)) == 0.0

    ranked = top_candidates(entries, topic)
    out = render_candidates_block(ranked, topic, all_entries=entries)
    assert high.slug in out


def test_count_floor_entries_are_labelled() -> None:
    """AC-005: floor admissions carry a distinguishing label the rerank turn can act on."""
    entries, topic = _zero_overlap_corpus()
    ranked = top_candidates(entries, topic)
    out = render_candidates_block(ranked, topic, all_entries=entries)
    assert "quicksort-pivot-choice" in _floor_slugs(out)
    # The lexical hit must NOT be labelled as a floor admission.
    assert "kangaroo-zeppelin-hit" not in _floor_slugs(out)


def test_p6_floor_label_occurs_before_the_closing_fence() -> None:
    """P-6: the only composition preserving the old return string puts the floor OUTSIDE."""
    entries, topic = _zero_overlap_corpus()
    ranked = top_candidates(entries, topic)
    out = render_candidates_block(ranked, topic, all_entries=entries)
    assert FLOOR_LABEL in out
    assert out.index(FLOOR_LABEL) < out.index(FENCE_CLOSE)


# --------------------------------------------------------------------------------------
# AC-006 / P-1 — additivity under a cap that actually binds
# --------------------------------------------------------------------------------------


def _binding_cap_corpus(n: int = 30) -> tuple[list[MemoryEntry], str]:
    """Mirrors the measured 3-of-30 shape: many matching entries, bodies far over the cap."""
    topic = "worktree finalize stash merge"
    entries = [
        _entry(
            f"worktree-finalize-stash-{i}",
            tier="fail",
            count=(20 - i) if i < 5 else None,
            body=f"- [2026-01-{(i % 28) + 1:02d}] worktree finalize stash merge detail {i}. "
            + ("x" * 3000)
            + "\n",
            date=f"2026-01-{(i % 28) + 1:02d}",
        )
        for i in range(n)
    ]
    return entries, topic


def test_binding_cap_is_actually_binding_in_this_fixture() -> None:
    """Guard the guard: if the cap stopped binding, AC-006 below would be vacuous."""
    entries, topic = _binding_cap_corpus()
    ranked = top_candidates(entries, topic)
    off = render_candidates_block(ranked, topic, all_entries=entries, count_floor=0)
    assert off.count("## [fail:") < len(ranked), (
        "cap did not bind — fixture no longer models 3-of-30"
    )


def test_count_floor_is_additive_to_k() -> None:
    """AC-006: the lexical section is byte-identical with the floor on and off."""
    entries, topic = _binding_cap_corpus()
    ranked = top_candidates(entries, topic)
    off = render_candidates_block(ranked, topic, all_entries=entries, count_floor=0)
    on = render_candidates_block(ranked, topic, all_entries=entries, count_floor=3)
    assert _lexical_entry_bodies(on) == _lexical_entry_bodies(off)


def test_sections_are_capped_separately_not_as_a_sum() -> None:
    """W3: the sum form would go red on the pre-existing minimum-body clamp."""
    entries, topic = _binding_cap_corpus()
    ranked = top_candidates(entries, topic)
    on = render_candidates_block(
        ranked, topic, all_entries=entries, byte_cap=10240, count_floor=3, floor_entry_bytes=1000
    )
    lexical, floor = _sections(on)
    assert len(lexical.encode("utf-8")) <= 10240
    assert len(floor.encode("utf-8")) <= 3 * (1000 + 256)


# --------------------------------------------------------------------------------------
# P-7 — exactly N under a long topic
# --------------------------------------------------------------------------------------


def test_p7_exactly_n_admitted_under_a_long_topic() -> None:
    """C2: fence overhead must not come out of the floor budget and silently drop N to N-1."""
    long_topic = "an unusually long retrieval topic " * 12
    entries = [
        _entry(f"high-count-{i}", count=20 - i, body=f"- [2026-01-0{i + 1}] " + ("y" * 2000) + "\n")
        for i in range(5)
    ]
    out = render_candidates_block([], long_topic, all_entries=entries, count_floor=3)
    assert len(_floor_slugs(out)) == 3


# --------------------------------------------------------------------------------------
# P-8 — no inversion on the REAL corpus
# --------------------------------------------------------------------------------------


@pytest.mark.skipif(not (REAL_MEMORY_DIR / "failures.md").exists(), reason="no real corpus here")
def test_p8_real_corpus_excerpt_carries_the_closing_text_of_the_newest_block() -> None:
    """Head truncation would emit a SUPERSEDED entry's retracted guidance as authoritative.

    Stated as *closing text* because the newest block of the top entry is ~2.7 kB — "contains
    the whole block" is unsatisfiable at any sane budget. This assertion is false under both
    head truncation and a whole-blocks-only rule.
    """
    entries = load_memory_dir(REAL_MEMORY_DIR)
    top = floor_candidates(entries, exclude_slugs=set(), n=1)
    assert top, "no fail-tier entry carries a count: — the floor's source set is empty"
    newest_block = [
        b for b in re.split(r"(?m)^(?=- \[\d{4}-\d{2}-\d{2}\])", top[0].body) if b.strip()
    ][-1]
    excerpt, dropped = excerpt_recent_blocks(top[0].body, 1000)
    assert dropped > 0, "fixture assumption: the top entry's body exceeds the per-entry budget"
    assert newest_block.rstrip()[-200:] in excerpt, "the newest block's closing text was cut"


def test_excerpt_prefers_whole_blocks_but_never_drops_the_newest() -> None:
    """The rule ADR-002 was missing: a newest block over budget is tail-truncated, not dropped."""
    body = "head prose\n" + "- [2026-01-01] old\n" + "- [2026-02-02] " + ("z" * 4000) + "\n"
    excerpt, dropped = excerpt_recent_blocks(body, 500)
    assert excerpt.strip(), "whole-blocks-only would return nothing here — the degenerate case"
    assert excerpt.rstrip().endswith("z")
    assert dropped > 0


def test_excerpt_keeps_multiple_whole_blocks_when_they_fit() -> None:
    """The budget BINDS here (review 42e93551): the old 47-byte fixture under a 4000-byte cap
    returned on the early exit and never entered the whole-block selection loop."""
    a, b, c = (
        "- [2026-01-01] " + "a" * 900 + "\n",
        "- [2026-02-02] " + "b" * 900 + "\n",
        ("- [2026-03-03] " + "c" * 900 + "\n"),
    )
    body = "head prose\n" + a + b + c
    excerpt, dropped = excerpt_recent_blocks(body, 2000)
    assert len(body.encode("utf-8")) > 2000, "precondition: the cap must bind"
    assert excerpt == b + c, "the two newest blocks survive whole, in order"
    assert dropped == len(body.encode("utf-8")) - len(excerpt.encode("utf-8"))


@pytest.mark.parametrize("budget", [0, -2])
def test_excerpt_non_positive_budget_emits_nothing(budget: int) -> None:
    """Review 60a1e752: `[-0:]` is the WHOLE string, and a negative bound slices from the
    front — a zero or negative budget must yield an empty excerpt, never the full body."""
    body = "- [2026-01-01] abcdef\n"
    excerpt, dropped = excerpt_recent_blocks(body, budget)
    assert excerpt == ""
    assert dropped == len(body.encode("utf-8"))


# --------------------------------------------------------------------------------------
# P-9 — empty-lexical branch
# --------------------------------------------------------------------------------------


def test_p9_empty_lexical_with_a_populated_floor() -> None:
    """The shape the feature exists for: zero lexical hits, floor non-empty."""
    entries = [_entry("only-high-count", count=9, body="- [2026-01-01] text\n")]
    out = render_candidates_block(
        [], "no tokens shared here at all", all_entries=entries, count_floor=3
    )
    assert "(no lexical matches)" in out
    assert "(no entries matched)" not in out
    assert "only-high-count" in out


def test_both_sections_empty_keeps_the_legacy_sentinel() -> None:
    out = render_candidates_block([], "topic", all_entries=[], count_floor=3)
    assert "(no entries matched)" in out


# --------------------------------------------------------------------------------------
# ADR-002/003 — source set, tie-break, and the off switch
# --------------------------------------------------------------------------------------


def test_floor_source_set_is_fail_tier_with_a_count() -> None:
    """A wiki entry outranking a failure on count would wear a failure-specific label."""
    entries = [
        _entry("wiki-with-count", tier="wiki", count=99),
        _entry("fail-no-count", tier="fail", count=None),
        _entry("fail-with-count", tier="fail", count=2),
    ]
    picked = [e.slug for e in floor_candidates(entries, exclude_slugs=set(), n=5)]
    assert picked == ["fail-with-count"]


def test_floor_tie_break_is_count_then_date_desc_then_slug() -> None:
    entries = [
        _entry("bravo", count=8, date="2026-01-01"),
        _entry("alpha", count=8, date="2026-01-01"),
        _entry("charlie", count=8, date="2026-02-01"),
    ]
    picked = [e.slug for e in floor_candidates(entries, exclude_slugs=set(), n=3)]
    assert picked == ["charlie", "alpha", "bravo"]


def test_count_floor_zero_is_equivalent_to_off() -> None:
    entries, topic = _zero_overlap_corpus()
    ranked = top_candidates(entries, topic)
    zero = render_candidates_block(ranked, topic, all_entries=entries, count_floor=0)
    assert FLOOR_LABEL not in zero
    assert "quicksort-pivot-choice" not in zero


def test_dedup_is_against_the_emitted_lexical_set_not_the_pool() -> None:
    """W1: an entry pre-filtered in but popped by the cap stays eligible for the floor."""
    entries, topic = _binding_cap_corpus()
    ranked = top_candidates(entries, topic)
    on = render_candidates_block(ranked, topic, all_entries=entries, byte_cap=4096, count_floor=3)
    lexical, _floor = _sections(on)
    # Slug-set comparison, not substring: `...-stash-2` is a substring of `...-stash-27`.
    lexical_slugs = {m.group(1) for m in re.finditer(r"^## \[[^\]]+\] (\S+) \|", lexical, re.M)}
    assert set(_floor_slugs(on)).isdisjoint(lexical_slugs), (
        "a floor entry was also emitted lexically"
    )
    assert _floor_slugs(on), "nothing was admitted — the cap should have evicted eligible entries"
    # The point of the emitted-set rule: an entry the cap evicted IS still floor-eligible.
    assert len(lexical_slugs) < len(ranked), "cap did not evict anything — test is vacuous"
