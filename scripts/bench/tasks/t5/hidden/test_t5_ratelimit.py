"""Hidden tests for t5: token-bucket RateLimiter."""

import pytest
from timeparse.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _limiter(rate: str, burst: int) -> tuple[RateLimiter, FakeClock]:
    clock = FakeClock()
    return RateLimiter(rate, burst, clock=clock), clock


def test_starts_full() -> None:
    limiter, _ = _limiter("1/1m", 3)
    assert [limiter.allow() for _ in range(4)] == [True, True, True, False]


def test_tenth_second_steps_are_exact() -> None:
    limiter, clock = _limiter("10/1s", 1)
    results = []
    for i in range(11):
        clock.now = i / 10
        results.append(limiter.allow())
    assert results == [True] * 11


def test_tenth_second_steps_with_literals() -> None:
    limiter, clock = _limiter("10/1s", 1)
    for now in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        clock.now = now
        assert limiter.allow(), now


def test_early_call_is_refused() -> None:
    limiter, clock = _limiter("10/1s", 1)
    assert limiter.allow()
    clock.now = 0.05
    assert not limiter.allow()
    clock.now = 0.1
    assert limiter.allow()


def test_refused_call_takes_nothing() -> None:
    limiter, clock = _limiter("1/1s", 2)
    assert limiter.allow(2)
    clock.now = 1.0
    assert not limiter.allow(2)
    assert limiter.allow(1)


def test_never_above_burst() -> None:
    limiter, clock = _limiter("1/1s", 2)
    clock.now = 1000.0
    assert limiter.allow(2)
    assert not limiter.allow()


def test_retry_after() -> None:
    limiter, clock = _limiter("2/1s", 2)
    assert limiter.retry_after() == 0.0
    assert limiter.allow(2)
    assert limiter.retry_after() == pytest.approx(0.5)
    assert limiter.retry_after(2) == pytest.approx(1.0)
    clock.now = 0.25
    assert limiter.retry_after() == pytest.approx(0.25)
    clock.now = 0.5
    assert limiter.retry_after() == 0.0


def test_retry_after_takes_nothing() -> None:
    limiter, _ = _limiter("1/1h", 1)
    limiter.retry_after()
    assert limiter.allow()


def test_minute_and_compound_rates() -> None:
    limiter, clock = _limiter("5/1m", 1)
    assert limiter.allow()
    clock.now = 11.9
    assert not limiter.allow()
    clock.now = 12.0
    assert limiter.allow()
    slow, slow_clock = _limiter("3/1h30m", 1)
    assert slow.allow()
    slow_clock.now = 1800.0
    assert slow.allow()


@pytest.mark.parametrize(
    ("rate", "burst"),
    [
        ("0/1s", 1),
        ("-1/1s", 1),
        ("10", 1),
        ("10/", 1),
        ("x/1s", 1),
        ("10/1x", 1),
        ("10/0s", 1),
        ("1.5/1s", 1),
        ("10/1s", 0),
        ("10/1s", -2),
    ],
)
def test_invalid_construction(rate: str, burst: int) -> None:
    with pytest.raises(ValueError):
        RateLimiter(rate, burst, clock=FakeClock())


@pytest.mark.parametrize("n", [0, -1, 4])
def test_invalid_n(n: int) -> None:
    limiter, _ = _limiter("1/1s", 3)
    with pytest.raises(ValueError):
        limiter.allow(n)
    with pytest.raises(ValueError):
        limiter.retry_after(n)


def test_default_clock_is_monotonic() -> None:
    limiter = RateLimiter("1/1h", 1)
    assert limiter.allow()
    assert not limiter.allow()
