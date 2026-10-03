"""AC-013 — `hm memory_retrieve` is bounded and lexical-first (SPEC S9, PLAN ADR-004).

The eligible lexical set is fixed BY CONSTRUCTION, not read from the scorer: exactly the entries
the generator marks as eligible carry the topic tokens (`zqxtopic`, optionally `vwkmark`) in
their slug, and every other byte of the corpus is Hangul, digits or fixed ASCII words that share
no token with the topic. The score of each eligible entry is therefore known in advance (1.0 with
both tokens, 0.5 with one). "Newest" is the max parsed bullet date, and bullets are shuffled on
disk so the newest is not simply the last one.
"""

from __future__ import annotations

import contextlib
import io
import os
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker.memory_retrieve import main

settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=300, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

COUNT_FLOOR = 3  # PLAN ADR-004: the floor keeps its cap; it only fills free slots
K = 6
PRE_K = 30
CAP = 8192
TOPIC = "zqxtopic vwkmark"
FLOOR_MARK = "high-recurrence"
FENCE_CLOSE = "</memory_candidates>"

_HEADING = re.compile(r"^## \[(?P<tier>wiki|fail):(?P<cat>[^\]]+)\] (?P<slug>\S+) \|(?P<rest>.*)$")
_BULLET = re.compile(r"^- \[(\d{4}-\d{2}-\d{2})\]")
# Fixed vocabulary for non-eligible slugs/text — none stems to a topic token.
_WORDS = ("alpha", "bravo", "cargo", "delta", "ember", "fjord", "gamma", "harbor")
_CATS = ("arch", "test", "tooling", "design")


@dataclass
class Spec:
    tier: str
    cat: str
    slug: str
    date: str
    count: int | None
    para1: str
    para2: str | None
    bullets: list[tuple[str, str]] = field(default_factory=list)  # (date, text), on-disk order
    eligible: bool = False
    score: float = 0.0

    @property
    def newest(self) -> str | None:
        return max((d for d, _ in self.bullets), default=None)

    def text(self) -> str:
        count = f" | count:{self.count}" if self.count is not None else ""
        out = f"## [{self.tier}:{self.cat}] {self.slug} | {self.date}{count}\n{self.para1}\n"
        if self.para2 is not None:
            out += f"\n{self.para2}\n"
        for d, t in self.bullets:
            out += f"- [{d}] {t}\n"
        return out + "\n"


def _hangul(rng: random.Random, n: int) -> str:
    chars = [chr(rng.randint(0xAC00, 0xD7A3)) if rng.random() > 0.15 else " " for _ in range(n)]
    return "".join(chars).strip() or "가"


def _date(rng: random.Random) -> str:
    return f"20{rng.randint(20, 29)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def _build(seed: int, n_other: int, n_eligible: int, size_class: int) -> list[Spec]:
    rng = random.Random(seed)
    max_chars = (40, 300, 1000)[size_class]  # 1000 Hangul ≈ 3 KB
    specs: list[Spec] = []
    for i in range(n_other + n_eligible):
        eligible = i >= n_other
        tier = rng.choice(("wiki", "fail"))
        word = rng.choice(_WORDS)
        if eligible:
            both = rng.random() < 0.5
            slug = f"e{i}-zqxtopic-vwkmark-{word}" if both else f"e{i}-zqxtopic-{word}"
            score = 1.0 if both else 0.5
        else:
            slug, score = f"e{i}-{word}", 0.0
        n_bullets = rng.choice((0, 0, 1, rng.randint(2, 12)))
        dates: set[str] = set()
        while len(dates) < n_bullets:
            dates.add(_date(rng))
        bullets = [(d, f"note{i} " + _hangul(rng, rng.randint(1, max_chars))) for d in dates]
        rng.shuffle(bullets)
        undated_para2 = f"para2 {i} " + _hangul(rng, rng.randint(1, 80)) if not bullets else None
        specs.append(
            Spec(
                tier=tier,
                cat=rng.choice(_CATS),
                slug=slug,
                date=min(dates) if dates else _date(rng),
                count=rng.randint(1, 30) if tier == "fail" else None,
                para1=f"para1 {i} " + _hangul(rng, rng.randint(1, max_chars)),
                para2=undated_para2 if rng.random() < 0.6 else None,
                bullets=bullets,
                eligible=eligible,
                score=score,
            )
        )
    rng.shuffle(specs)
    return specs


def _write(mem: Path, specs: list[Spec]) -> None:
    mem.mkdir(parents=True, exist_ok=True)
    for tier, name in (("wiki", "wiki.md"), ("fail", "failures.md")):
        entries = "".join(s.text() for s in specs if s.tier == tier)
        (mem / name).write_text(
            f"# {name}\n\n<!-- @hm:user:entries -->\n{entries}<!-- @hm:/user:entries -->\n",
            encoding="utf-8",
        )


def _run_inprocess(mem: Path) -> str:
    out, err = io.StringIO(), io.StringIO()
    argv = ["--topic", TOPIC, "--k", str(K), "--pre-k", str(PRE_K), "--memory-dir", str(mem)]
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        assert main(argv) == 0
    return out.getvalue()


@dataclass
class Rendered:
    slug: str
    floor: bool
    body: str


def _parse(out: str) -> list[Rendered]:
    inner = out.split(">\n", 1)[1].split(FENCE_CLOSE, 1)[0]
    items: list[Rendered] = []
    cur: tuple[str, bool] | None = None
    body: list[str] = []
    for line in inner.splitlines():
        m = _HEADING.match(line)
        if m:
            if cur is not None:
                items.append(Rendered(cur[0], cur[1], "\n".join(body)))
            cur, body = (m.group("slug"), FLOOR_MARK in m.group("rest")), []
        elif cur is not None and not line.startswith("### "):
            body.append(line)
    if cur is not None:
        items.append(Rendered(cur[0], cur[1], "\n".join(body)))
    return items


def _shown_size(s: Spec) -> int:
    """Conservative rendered size of one entry under the new rule (newest bullet / para 1)."""
    shown = f"- [{s.newest}] " + dict(s.bullets)[s.newest] if s.newest else s.para1
    return len(s.slug.encode()) + len(shown.encode("utf-8")) + 128


def _check(out: str, specs: list[Spec]) -> None:
    raw = out.encode("utf-8")  # strict: a lone surrogate from a mid-codepoint cut raises here
    assert len(raw) <= CAP, f"output is {len(raw)} bytes > {CAP}"
    assert raw.decode("utf-8") == out

    by_slug = {s.slug: s for s in specs}
    eligible = [s for s in specs if s.eligible]
    want = min(K, len(eligible))
    rendered = _parse(out)
    lex = [r for r in rendered if not r.floor]
    floor = [r for r in rendered if r.floor]

    assert len({r.slug for r in rendered}) == len(rendered), "an entry was rendered twice"
    for r in lex:
        assert by_slug[r.slug].eligible, f"non-floor entry {r.slug} is not a lexical hit"
    for r in floor:
        s = by_slug[r.slug]
        assert not s.eligible, f"lexical hit {r.slug} re-admitted under the floor label"
        assert s.tier == "fail", r.slug
        assert s.count is not None, r.slug

    # Lexical first: no floor entry precedes a lexical entry.
    if lex and floor:
        assert rendered.index(lex[-1]) < rendered.index(floor[0]), "floor rendered before lexical"
    assert all(not r.floor for r in rendered[:want]), "first min(k, eligible) not all lexical"
    # Floor fills only the slots lexical hits leave.
    if floor:
        assert len(eligible) < K, f"{len(floor)} floor entries admitted with {len(eligible)} hits"
        assert len(floor) <= min(K - len(eligible), COUNT_FLOOR), (
            "floor exceeded its remainder or cap"
        )
    # Cap drops floor first, then the lowest-scored lexical entries.
    if len(lex) < want:
        assert not floor, "a lexical hit was dropped while a floor entry survived"
    shown = {r.slug for r in lex}
    dropped = [s for s in eligible if s.slug not in shown]
    if lex and dropped:
        assert min(by_slug[r.slug].score for r in lex) >= max(s.score for s in dropped)
    # When every eligible entry's new-rule rendering fits, none may be missing from the first k.
    if sum(_shown_size(s) for s in eligible) + 1024 <= CAP:
        assert len(lex) >= want, f"{len(lex)} lexical shown, {want} expected (fits the cap)"
    # Lower bound on the floor: when everything that could be shown fits, the remainder is filled.
    pool = [s for s in specs if s.tier == "fail" and s.count is not None and not s.eligible]
    if len(eligible) < K:
        n_floor = min(K - len(eligible), COUNT_FLOOR, len(pool))
        biggest = sorted((_shown_size(s) for s in pool), reverse=True)[:n_floor]
        if sum(_shown_size(s) for s in eligible) + sum(biggest) + 1024 <= CAP:
            assert len(floor) == n_floor, f"{len(floor)} floor entries, expected {n_floor}"

    for r in rendered:
        s = by_slug[r.slug]
        dates = [m.group(1) for line in r.body.splitlines() if (m := _BULLET.match(line))]
        if s.newest is not None:
            assert dates == [s.newest], f"{r.slug}: shown bullets {dates}, newest {s.newest}"
        else:
            assert s.para1 in r.body, f"undated {r.slug} lost its first paragraph"
            if s.para2 is not None:
                assert s.para2 not in r.body, f"undated {r.slug} rendered past paragraph one"


@given(
    seed=st.integers(0, 2**32 - 1),
    n_other=st.integers(0, 50),
    n_eligible=st.integers(0, 10),
    size_class=st.integers(0, 2),
)
def test_ac013_memory_retrieve_bounded(
    seed: int, n_other: int, n_eligible: int, size_class: int
) -> None:
    specs = _build(seed, n_other, n_eligible, size_class)
    with tempfile.TemporaryDirectory() as d:
        mem = Path(d) / "memory"
        _write(mem, specs)
        _check(_run_inprocess(mem), specs)


def _small(slug: str, tier: str, count: int | None, i: int) -> Spec:
    return Spec(
        tier=tier,
        cat="test",
        slug=slug,
        date="2026-01-01",
        count=count,
        para1=f"para1 {i} 짧은 본문",
        para2=None,
        bullets=[("2026-02-01", f"old {i} 이전"), ("2026-03-01", f"new {i} 최신")],
        eligible="zqxtopic" in slug,
        score=0.5,
    )


def test_ac013_k_lexical_hits_admit_no_floor(tmp_path: Path) -> None:
    """(a) 6 lexical hits + 20 high-count unrelated failures → zero floor entries."""
    specs = [_small(f"hit{i}-zqxtopic", "wiki", None, i) for i in range(6)]
    specs += [_small(f"loud{i}-{_WORDS[i % 8]}", "fail", 20 + i % 10, 100 + i) for i in range(20)]
    _write(tmp_path / "memory", specs)
    out = _run_inprocess(tmp_path / "memory")
    rendered = _parse(out)
    assert [r for r in rendered if r.floor] == [], "floor admitted although lexical hits == k"
    assert sorted(r.slug for r in rendered if not r.floor) == sorted(s.slug for s in specs[:6])
    _check(out, specs)


def test_ac013_zero_lexical_hits_floor_fills_to_k(tmp_path: Path) -> None:
    """(b) 0 lexical hits → the floor fills the free slots up to its cap of 3 (PLAN ADR-004).

    Name kept for the machine-SPEC-independent node id; the count asserts min(k, COUNT_FLOOR).
    """
    specs = [_small(f"loud{i}-{_WORDS[i % 8]}", "fail", 10 + i, i) for i in range(10)]
    _write(tmp_path / "memory", specs)
    out = _run_inprocess(tmp_path / "memory")
    floor = [r for r in _parse(out) if r.floor]
    assert len(floor) == min(K, COUNT_FLOOR), f"{len(floor)} floor entries with 0 lexical hits"
    _check(out, specs)


@pytest.mark.parametrize("hits", [1, 2, 3, 4, 5])
def test_ac013_partial_lexical_floor_fills_remainder(tmp_path: Path, hits: int) -> None:
    """Floor fills exactly min(K − hits, COUNT_FLOOR); undated floor entries show paragraph one."""
    specs = [_small(f"hit{i}-zqxtopic", "wiki", None, i) for i in range(hits)]
    loud = [_small(f"loud{i}-{_WORDS[i % 8]}", "fail", 10 + i, 100 + i) for i in range(6)]
    for i, s in enumerate(loud[-2:]):  # the two highest counts are undated
        s.bullets = []
        s.para2 = f"para2 undated{i} 둘째 문단"
    specs += loud
    _write(tmp_path / "memory", specs)
    out = _run_inprocess(tmp_path / "memory")
    rendered = _parse(out)
    lex = [r for r in rendered if not r.floor]
    floor = [r for r in rendered if r.floor]
    want = min(K - hits, COUNT_FLOOR)
    assert len(floor) == want, f"{len(floor)} floor entries with {hits} hits, expected {want}"
    assert len(lex) == hits
    assert rendered[: len(lex)] == lex, "a floor entry precedes a lexical entry"
    by_slug = {s.slug: s for s in specs}
    for r in floor:
        s = by_slug[r.slug]
        if not s.bullets:
            assert s.para1 in r.body, f"undated floor {r.slug} lost its first paragraph"
            assert s.para2 is not None
            assert s.para2 not in r.body, f"undated floor {r.slug} rendered past paragraph one"
    _check(out, specs)


def test_ac013_huge_hangul_body_stays_under_cap_and_decodes(tmp_path: Path) -> None:
    """(c) one ~30 KB Hangul body → raw stdout ≤ 8192 bytes and valid UTF-8 (subprocess bytes)."""
    rng = random.Random(13)
    spec = Spec(
        tier="fail",
        cat="test",
        slug="huge-zqxtopic",
        date="2026-01-01",
        count=4,
        para1="para1 " + _hangul(rng, 10_000),
        para2=None,
        eligible=True,
        score=0.5,
    )
    _write(tmp_path / "memory", [spec])
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.memory_retrieve", "--topic", TOPIC, "--k", str(K)]
        + ["--pre-k", str(PRE_K), "--memory-dir", str(tmp_path / "memory")],
        capture_output=True,
        timeout=60,
        check=True,
    )
    assert len(proc.stdout) <= CAP, f"stdout is {len(proc.stdout)} bytes > {CAP}"
    text = proc.stdout.decode("utf-8")  # strict — raises on a mid-codepoint cut
    assert "�" not in text, "replacement character in output — a lossy decode upstream"
    shown = [r for r in _parse(text) if r.slug == spec.slug]
    assert shown, "the only lexical hit was dropped instead of bounded"
    assert not shown[0].floor, "the lexical hit was re-admitted under the floor label"
    body = shown[0].body
    run = 200
    assert any(spec.para1[i : i + run] in body for i in range(len(spec.para1) - run + 1)), (
        f"shown body carries no {run}-char run of the entry's text"
    )


_FENCE_HEAD = re.compile(r'^<memory_candidates topic="(?P<topic>[^"]*)" k="\d+" pre_k="\d+">$')
_ENTITY = re.compile(r"&(?:\w+|#\d+|#x[0-9A-Fa-f]+);")


def _run_topic(mem: Path, topic: str) -> str:
    out, err = io.StringIO(), io.StringIO()
    argv = ["--topic", topic, "--k", str(K), "--pre-k", str(PRE_K), "--memory-dir", str(mem)]
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        assert main(argv) == 0
    return out.getvalue()


@pytest.mark.parametrize("with_entries", [False, True], ids=["no-entries", "some-entries"])
@pytest.mark.parametrize("filler", ["가", '"<>'], ids=["hangul", "escaped"])
def test_ac013_huge_topic_stays_under_cap(tmp_path: Path, with_entries: bool, filler: str) -> None:
    """REVIEW codex 406f3bc1: a ~20 KB topic is echoed clipped, on every path incl. empty."""
    topic = "zqxtopic " + filler * (20_000 // len(filler.encode("utf-8")))
    assert len(topic.encode("utf-8")) >= 20_000
    mem = tmp_path / "memory"
    specs: list[Spec] = []
    if with_entries:
        specs = [_small(f"hit{i}-zqxtopic", "wiki", None, i) for i in range(2)]
        specs += [_small(f"loud{i}-{_WORDS[i]}", "fail", 10 + i, 100 + i) for i in range(4)]
    _write(mem, specs)
    out = _run_topic(mem, topic)
    assert len(out.encode("utf-8")) <= CAP, len(out.encode("utf-8"))
    head = out.splitlines()[0]
    assert head.startswith('<memory_candidates topic="zqxtopic '), head[:80]
    assert "…" in head, "a clipped topic must be marked"
    # REVIEW confirm-1: the clip happens before escaping, so the attribute closes right after the
    # marker and no entity is cut in half (`&quo…` would be a dangling fragment).
    m = _FENCE_HEAD.match(head)
    assert m is not None, head[-120:]
    attr = m.group("topic")
    assert attr.endswith("…"), attr[-40:]
    assert '"' not in attr, attr[-40:]
    assert "<" not in attr, attr[-40:]
    assert all(_ENTITY.match(attr, i) for i, c in enumerate(attr) if c == "&"), attr[-60:]
    assert FENCE_CLOSE in out
    if with_entries:
        assert {r.slug for r in _parse(out)} >= {s.slug for s in specs[:2]}
    else:
        assert "(no entries matched)" in out
