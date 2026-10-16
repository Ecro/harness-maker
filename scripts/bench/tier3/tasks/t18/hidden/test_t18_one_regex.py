"""Hidden tests for t18: one full-match regex, the same behaviour, nothing else broken."""

import ast
import random
import re
import string
from collections.abc import Callable
from pathlib import Path

import pytest
import timeparse.parse
from timeparse import parse_duration

# parse_duration exactly as the start tree has it: the oracle for "must not change for any
# input". The DRI's default of 2026-10-15 keeps the corpus to ASCII.
_UNITS = {"d": 86400, "h": 3600, "m": 60, "s": 1}
_TOKEN = re.compile(r"(\d+)([a-z])")


def _original(text: str) -> int:
    cleaned = text.strip().lower()
    if not cleaned:
        raise ValueError("empty duration")
    total = 0
    pos = 0
    last_rank = -1
    for match in _TOKEN.finditer(cleaned):
        if match.start() != pos:
            raise ValueError(f"invalid duration: {text!r}")
        amount, unit = match.groups()
        if unit not in _UNITS:
            raise ValueError(f"unknown unit {unit!r} in {text!r}")
        rank = list(_UNITS).index(unit)
        if rank <= last_rank:
            raise ValueError(f"units out of order or repeated in {text!r}")
        last_rank = rank
        total += int(amount) * _UNITS[unit]
        pos = match.end()
    if pos != len(cleaned):
        raise ValueError(f"invalid duration: {text!r}")
    return total


def _outcome(parse: Callable[[str], int], text: str) -> tuple[str, int | None]:
    try:
        value = parse(text)
    except ValueError:
        return ("ValueError", None)
    return (type(value).__name__, value)


def _corpus(size: int = 5000, seed: int = 20261015) -> list[str]:
    """Random ASCII strings plus well-formed, reordered, repeated and padded durations."""
    rng = random.Random(seed)
    alphabet = string.digits + "dhmsDHMS" + "xwyz" + string.whitespace + ".+-:_,0"
    units = "dhms"
    texts = {"", " ", "0", "00s", "0d0h0m0s", "1h30m", " 1H30M ", "30m1h", "1h1h", "1h 30m", "h"}
    while len(texts) < size:
        kind = rng.randrange(4)
        if kind == 0:
            texts.add("".join(rng.choice(alphabet) for _ in range(rng.randrange(1, 9))))
            continue
        picked = [u for u in units if rng.random() < 0.6] or [rng.choice(units)]
        if kind == 2:
            rng.shuffle(picked)
        if kind == 3:
            picked.insert(rng.randrange(len(picked) + 1), rng.choice(units))
        parts = [f"{rng.randrange(0, 1000):0{rng.randrange(1, 4)}d}{u}" for u in picked]
        text = "".join(p.upper() if rng.random() < 0.2 else p for p in parts)
        pad = string.whitespace
        before, after = (rng.choice(["", " ", rng.choice(pad)]) for _ in range(2))
        texts.add(before + text + after)
    return sorted(texts)


def _calls(tree: ast.AST) -> set[str]:
    return {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }


def test_the_token_loop_is_replaced_by_one_full_match_regex() -> None:
    """Simplify `parse_duration`: replace the token loop with one full-match regex.

    Source: prompt
    """
    source = Path(timeparse.parse.__file__).read_text(encoding="utf-8")
    calls = _calls(ast.parse(source))
    assert "finditer" not in calls, "the token loop is still there"
    assert calls & {"fullmatch", "match"}, "no full-match regex"


def test_behaviour_is_unchanged_for_any_input() -> None:
    """Its behaviour must not change for any input, and nothing else in the package may break.

    Source: prompt
    """
    corpus = _corpus()
    assert len(corpus) >= 5000
    changed = [t for t in corpus if _outcome(parse_duration, t) != _outcome(_original, t)]
    assert not changed, f"{len(changed)} input(s) changed, e.g. {changed[:5]!r}"


def test_strict_durations_still_work() -> None:
    """Its behaviour must not change for any input, and nothing else in the package may break.

    Source: prompt
    """
    from timeparse.strict import is_canonical, parse_strict

    assert is_canonical("1h30m")
    for text in ("1h0m", " 1h", "1H", "01h", "", "30m1h", "1x"):
        assert not is_canonical(text), text
    assert parse_strict("1d1h1m1s") == 90061
    with pytest.raises(ValueError):
        parse_strict("1h0m")


def test_the_modules_that_read_parse_duration_still_work() -> None:
    """Its behaviour must not change for any input, and nothing else in the package may break.

    Source: prompt
    """
    from timeparse import config
    from timeparse.pack import pack, unpack
    from timeparse.schedule import normalize, split, total

    assert normalize("90m") == "1h30m"
    assert total(["1h", "30m"]) == "1h30m"
    assert split("1h", 4) == ["15m", "15m", "15m", "15m"]
    assert unpack(pack(90061)) == 90061
    assert config.load("idle = 45\nread = 2m\n") == {"idle": 2700, "read": 120}
    with pytest.raises(config.ConfigError) as info:
        config.load("timeout = 1h 30m\n")
    assert str(info.value) == "config line 1: bad duration '1h 30m'"
