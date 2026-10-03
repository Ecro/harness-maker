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
    _excerpt_newest as excerpt_newest,
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


def _few_hits_plus_loud_failures() -> tuple[list[MemoryEntry], str]:
    """3 lexical hits (< k) with ~3 kB newest blocks, plus 4 zero-overlap high-count failures."""
    entries, topic = _binding_cap_corpus(3)
    entries += [
        _entry(f"unrelated-loud-{i}", count=50 - i, body="- [2026-02-01] " + ("q" * 2000) + "\n")
        for i in range(4)
    ]
    return entries, topic


def test_count_floor_is_additive_to_k() -> None:
    """The floor never evicts a lexical hit: the lexical section is identical on and off.

    PLAN-maker-front-door-improvements ADR-004 / SPEC IRR-006: was "byte-identical because the
    floor has its own budget"; under one cap it holds because overflow drops floor entries
    first. Name kept for the node id. With k or more hits there is no free slot at all.
    """
    entries, topic = _few_hits_plus_loud_failures()
    ranked = top_candidates(entries, topic)
    assert 0 < len(ranked) < 6, "precondition: fewer hits than k, so the floor has free slots"
    off = render_candidates_block(ranked, topic, all_entries=entries, count_floor=0)
    on = render_candidates_block(ranked, topic, all_entries=entries, count_floor=3)
    assert _lexical_entry_bodies(on) == _lexical_entry_bodies(off)

    many, many_topic = _binding_cap_corpus()
    many_ranked = top_candidates(many, many_topic)
    full = render_candidates_block(many_ranked, many_topic, all_entries=many, count_floor=3)
    assert _floor_slugs(full) == [], "the floor took a slot although lexical hits >= k"


def test_sections_are_capped_separately_not_as_a_sum() -> None:
    """One cap bounds the whole output, and the floor section is the first to give way.

    PLAN-maker-front-door-improvements ADR-004 / SPEC IRR-006: was "each section has its own
    cap"; the sum of the two was unbounded by design. Name kept for the node id.
    """
    entries, topic = _few_hits_plus_loud_failures()
    ranked = top_candidates(entries, topic)
    on = render_candidates_block(ranked, topic, all_entries=entries, byte_cap=8192, count_floor=3)
    assert len(on.encode("utf-8")) <= 8192
    lexical, floor = _sections(on)
    shown = re.findall(r"^## \[[^\]]+\] (\S+) \|", lexical, re.M)
    assert len(shown) < len(ranked), "precondition: the cap must bind on the lexical hits"
    assert floor == "", "a floor entry survived while a lexical hit was dropped"

    roomy = render_candidates_block(
        ranked[:1], topic, all_entries=entries, byte_cap=8192, count_floor=3
    )
    assert len(roomy.encode("utf-8")) <= 8192
    assert _floor_slugs(roomy), "with room to spare the floor should fill free slots"


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
    """On the real corpus the top entry shows its newest block — whole — and nothing older.

    PLAN-maker-front-door-improvements ADR-004 / SPEC IRR-006: was "the closing text of the
    newest block survives a 1000-byte tail excerpt". Newest is now the max parsed date, and the
    block fits the 8192-byte cap whole, so the assertion tightens to the full block.
    """
    entries = load_memory_dir(REAL_MEMORY_DIR)
    top = floor_candidates(entries, exclude_slugs=set(), n=1)
    assert top, "no fail-tier entry carries a count: — the floor's source set is empty"
    blocks = [b for b in re.split(r"(?m)^(?=- \[\d{4}-\d{2}-\d{2}\])", top[0].body) if b.strip()]
    dated = [(m.group(1), i) for i, b in enumerate(blocks) if (m := re.match(r"- \[(.{10})\]", b))]
    assert len(dated) > 1, "fixture assumption: the top entry has more than one dated block"
    newest_block = blocks[max(dated)[1]].rstrip()
    excerpt, dropped = excerpt_newest(top[0].body, 8192)
    assert dropped > 0, "older blocks must not be shown"
    assert excerpt == newest_block, "the newest block was cut or another block was shown"


def test_excerpt_prefers_whole_blocks_but_never_drops_the_newest() -> None:
    """A newest block over budget is head-cut at a codepoint boundary, never dropped.

    PLAN-maker-front-door-improvements ADR-004 / SPEC IRR-006: was tail-truncation of the
    newest block; head-cut keeps its `- [date]` line, and Hangul pins the codepoint boundary.
    """
    body = "head prose\n" + "- [2026-01-01] old\n" + "- [2026-02-02] " + ("가" * 4000) + "\n"
    excerpt, dropped = excerpt_newest(body, 500)
    assert excerpt.startswith("- [2026-02-02] 가"), "the newest block was dropped or tail-cut"
    assert len(excerpt.encode("utf-8")) <= 500
    assert excerpt.encode("utf-8").decode("utf-8") == excerpt
    assert "old" not in excerpt
    assert dropped == len(body.encode("utf-8")) - len(excerpt.encode("utf-8"))


def test_excerpt_keeps_multiple_whole_blocks_when_they_fit() -> None:
    """Only the newest block is shown even when older ones would fit; newest is by date.

    PLAN-maker-front-door-improvements ADR-004 / SPEC IRR-006: was "the two newest whole blocks
    survive in order". Name kept for the node id. The newest block sits FIRST on disk here, so
    a position-based rule (last block wins) fails.
    """
    a, b, c = (
        "- [2026-01-01] " + "a" * 900 + "\n",
        "- [2026-02-02] " + "b" * 900 + "\n",
        ("- [2026-03-03] " + "c" * 900 + "\n"),
    )
    body = "head prose\n" + c + a + b
    excerpt, dropped = excerpt_newest(body, 8192)
    assert excerpt == c.rstrip(), "only the max-date block is shown, whole"
    assert dropped == len(body.encode("utf-8")) - len(excerpt.encode("utf-8"))

    undated = "first paragraph line one\nline two\n\nsecond paragraph\n"
    assert excerpt_newest(undated, 8192)[0] == "first paragraph line one\nline two"


@pytest.mark.parametrize("budget", [0, -2])
def test_excerpt_non_positive_budget_emits_nothing(budget: int) -> None:
    """Review 60a1e752: `[-0:]` is the WHOLE string, and a negative bound slices from the
    front — a zero or negative budget must yield an empty excerpt, never the full body."""
    body = "- [2026-01-01] abcdef\n"
    excerpt, dropped = excerpt_newest(body, budget)
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
    """A lexical hit is never re-admitted under the floor label — dedup runs against the POOL.

    PLAN-maker-front-door-improvements ADR-004 / SPEC IRR-006: inverted from W1's emitted-set
    rule, which let a cap-dropped hit return labelled `high-recurrence`. Name kept for the node
    id. Under one cap a dropped hit and a surviving floor entry cannot coexist (floor goes
    first), so the non-vacuous case is the hit ranked out by `pre_k`: it has the highest
    `count`, so an emitted-set rule would pick it first.
    """
    entries, topic = _binding_cap_corpus(3)  # 3 hits, counts 20/19/18
    entries.append(_entry("unrelated-quiet", count=2, body="- [2026-02-01] other words\n"))
    capped = render_candidates_block(
        top_candidates(entries, topic), topic, all_entries=entries, byte_cap=4096, count_floor=3
    )
    lexical, _floor = _sections(capped)
    # Slug-set comparison, not substring: `...-stash-2` is a substring of `...-stash-27`.
    lexical_slugs = {m.group(1) for m in re.finditer(r"^## \[[^\]]+\] (\S+) \|", lexical, re.M)}
    assert len(lexical_slugs) < 3, "cap did not evict anything — test is vacuous"
    assert _floor_slugs(capped) == [], "a cap-dropped hit or a floor entry outlived a hit"

    ranked = top_candidates(entries, topic, pre_k=1)
    out = render_candidates_block(ranked, topic, all_entries=entries, byte_cap=8192, count_floor=3)
    assert _floor_slugs(out) == ["unrelated-quiet"], "a lexical hit wore the floor label"
