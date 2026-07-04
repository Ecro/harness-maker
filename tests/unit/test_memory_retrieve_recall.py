"""Recall/precision tests for memory_retrieve's conservative stemmer.

PLAN-memory-retrieve-lexical-recall Phase 1+2. Proves the stemmer raises recall
on inflectional wording variants (snapshots↔snapshot, skips↔skip) via a raw
baseline (1 surfaces raw → 2 surface stemmed), and that its conservatism holds
the precision line (no -er / -tion collapse, min-stem-length guard). No new
dependency: pure-Python, single-signal normalized overlap (PLAN ADR-001/002/003).
"""

from __future__ import annotations


def _make_entry(
    *,
    slug: str,
    body: str = "",
    date: str = "2026-05-20",
    tier: str = "fail",
    category: str = "lint",
):
    from harness_maker.memory_retrieve import MemoryEntry

    return MemoryEntry(
        tier=tier,
        category=category,
        slug=slug,
        date=date,
        count=None,
        body=body,
        source_path="/x.md",
        line_offset=1,
    )


class TestStemBranches:
    """Pinned _stem semantics: first-match-wins, min-stem-length guard, no cascade."""

    def test_stem_strips_plural_s(self) -> None:
        from harness_maker.memory_retrieve import _stem

        assert _stem("snapshots") == "snapshot"
        assert _stem("skips") == "skip"

    def test_stem_strips_es_after_sibilant(self) -> None:
        from harness_maker.memory_retrieve import _stem

        # -es fires as a plural only after a sibilant: "misses" -> "miss" (strip 2,
        # not "misse"), because the stem "miss" ends in a sibilant.
        assert _stem("misses") == "miss"
        assert _stem("dishes") == "dish"
        assert _stem("matches") == "match"

    def test_stem_strips_ing(self) -> None:
        from harness_maker.memory_retrieve import _stem

        assert _stem("rendering") == "render"

    def test_stem_strips_ed(self) -> None:
        from harness_maker.memory_retrieve import _stem

        assert _stem("rendered") == "render"

    def test_stem_guard_blocks_short_stem_returns_unchanged(self) -> None:
        from harness_maker.memory_retrieve import _stem

        # -es matches but stem "go" (<4) -> unchanged.
        assert _stem("goes") == "goes"
        # -s matches but stem "ga" (<4) -> unchanged.
        assert _stem("gas") == "gas"

    def test_stem_first_match_wins_no_cascade(self) -> None:
        from harness_maker.memory_retrieve import _stem

        # "uses": -es matches FIRST -> stem "us" (<4) blocked -> returns "uses".
        # Must NOT fall through to -s and yield "use".
        assert _stem("uses") == "uses"

    def test_stem_no_suffix_match_returns_unchanged(self) -> None:
        from harness_maker.memory_retrieve import _stem

        assert _stem("boundary") == "boundary"

    def test_stem_non_sibilant_es_falls_through_to_s(self) -> None:
        """`<stem>e`+`s` plurals bridge to the singular via the -s rule, not -es.

        Cross-model REVIEW fix (Codex + code-reviewer, 2026-07-04): the trailing
        `e` is part of the stem, so only the `s` is inflectional.
        """
        from harness_maker.memory_retrieve import _stem

        assert _stem("files") == "file"
        assert _stem("updates") == "update"
        assert _stem("states") == "state"
        assert _stem("nodes") == "node"
        assert _stem("codes") == "code"
        assert _stem("types") == "type"
        assert _stem("values") == "value"
        # -th/-ph/-gh are NOT sibilants: `bathes` falls through to -s → `bathe`,
        # not the over-stem `bath` a bare trailing-`h` guard would produce.
        assert _stem("bathes") == "bathe"
        # symmetry: the singular is a fixed point, so plural↔singular actually meet.
        for singular in ("file", "update", "state", "node", "code", "type", "value"):
            assert _stem(singular) == singular

    def test_stem_sibilant_es_below_guard_stays_unchanged(self) -> None:
        """`boxes` -> `-es` after sibilant `x` -> stem `box` (<4) blocked -> unchanged.

        No cascade to `-s` (which would give `boxe`), preserving the min-stem guard.
        """
        from harness_maker.memory_retrieve import _stem

        assert _stem("boxes") == "boxes"


class TestStemPrecisionGate:
    """ADR-003 enumerated forbidden collapses: -er / -tion must never strip."""

    def test_stem_does_not_strip_er(self) -> None:
        from harness_maker.memory_retrieve import _stem

        for word in ("user", "server", "cover"):
            assert _stem(word) == word

    def test_stem_does_not_merge_er_pairs(self) -> None:
        from harness_maker.memory_retrieve import _stem

        assert _stem("user") != _stem("use")
        assert _stem("server") != _stem("serv")
        assert _stem("cover") != _stem("cove")

    def test_stem_does_not_strip_tion(self) -> None:
        from harness_maker.memory_retrieve import _stem

        for word in ("action", "function"):
            assert _stem(word) == word

    def test_stem_does_not_merge_tion_pairs(self) -> None:
        from harness_maker.memory_retrieve import _stem

        assert _stem("action") != _stem("act")
        assert _stem("function") != _stem("funct")


class TestNormalizeSymmetry:
    """Both token producers must normalize, or the overlap never matches."""

    def test_normalize_maps_stem_over_set(self) -> None:
        from harness_maker.memory_retrieve import _normalize

        assert _normalize(["snapshots", "skips", "boundary"]) == frozenset(
            {"snapshot", "skip", "boundary"}
        )

    def test_topic_tokens_are_stemmed(self) -> None:
        from harness_maker.memory_retrieve import topic_tokens

        tt = topic_tokens("snapshots")
        assert "snapshot" in tt
        assert "snapshots" not in tt

    def test_entry_token_set_is_stemmed(self) -> None:
        from harness_maker.memory_retrieve import _entry_token_set

        e = _make_entry(slug="skips-check", body="body skips")
        toks = _entry_token_set(e)
        assert "skip" in toks
        assert "skips" not in toks


class TestRecallStemBridge:
    """The recall win: a stem bridges wording the raw overlap missed."""

    def test_stem_is_sole_bridge_one_raw_two_stemmed(self) -> None:
        """Raw baseline: only entry A (shares a raw token) surfaces; stemming ON
        surfaces entry B too (shares a token only after -s strip). 1 raw → 2 stemmed."""
        from harness_maker.memory_retrieve import WORD_RE, top_candidates

        topic = "snapshots"
        entry_a = _make_entry(slug="snapshots-baseline", body="raw overlap here")
        entry_b = _make_entry(slug="snapshot-regen-inside-worktree", body="singular only")

        # --- raw baseline (stemming OFF, mirrors the pre-change formula) ---
        topic_raw = {t.lower() for t in WORD_RE.findall(topic)}

        def _raw_tokens(e) -> set[str]:
            text = " ".join([e.tier, e.category, e.slug, e.date, e.body]).lower()
            return set(WORD_RE.findall(text))

        def _raw_score(e) -> float:
            return len(topic_raw & _raw_tokens(e)) / len(topic_raw)

        assert _raw_score(entry_a) > 0.0  # A shares "snapshots" raw
        assert _raw_score(entry_b) == 0.0  # B shares nothing raw (it has "snapshot")

        # --- stemming ON (real module) ---
        surfaced = {e.slug for e in top_candidates([entry_a, entry_b], topic, pre_k=10)}
        assert entry_a.slug in surfaced
        assert entry_b.slug in surfaced  # recall win: B now surfaces
        assert len(surfaced) == 2

    def test_regenerating_snapshots_surfaces_singular_entry(self) -> None:
        """Phase 1 exit: topic 'regenerating snapshots' surfaces the singular
        'snapshot-...' entry, carried by snapshots→snapshot ALONE — the
        conservative rules do NOT produce regenerating→regen."""
        from harness_maker.memory_retrieve import _stem, top_candidates, topic_tokens

        topic = "regenerating snapshots"
        entry = _make_entry(slug="snapshot-regen-inside-worktree", body="worktree regen body")

        assert _stem("snapshots") == "snapshot"  # the bridge token
        assert _stem("regenerating") != "regen"  # regen is NOT the bridge

        tt = topic_tokens(topic)
        assert "snapshot" in tt  # bridge present
        assert "regen" not in tt  # not how we reach the entry

        surfaced = {e.slug for e in top_candidates([entry], topic, pre_k=10)}
        assert entry.slug in surfaced


class TestPrecisionInvariant:
    """ADR-003: single-signal s>0 filter holds automatically under stemming."""

    def test_zero_normalized_overlap_entry_filtered(self) -> None:
        from harness_maker.memory_retrieve import top_candidates

        match = _make_entry(slug="snapshot-baseline", body="snapshots drift")
        # -er / -tion words: none normalize toward "snapshot".
        nomatch = _make_entry(slug="user-server-action", body="cover function")
        surfaced = {e.slug for e in top_candidates([match, nomatch], "snapshots", pre_k=10)}
        assert "snapshot-baseline" in surfaced
        assert "user-server-action" not in surfaced

    def test_deterministic_candidate_order(self) -> None:
        from harness_maker.memory_retrieve import top_candidates

        entries = [
            _make_entry(slug="snapshot-a", body="snapshots"),
            _make_entry(slug="snapshot-b", body="snapshots"),
            _make_entry(slug="skip-c", body="skips snapshots"),
        ]
        r1 = [e.slug for e in top_candidates(entries, "snapshots skips", pre_k=10)]
        r2 = [e.slug for e in top_candidates(entries, "snapshots skips", pre_k=10)]
        assert r1 == r2
        assert len(r1) == 3
