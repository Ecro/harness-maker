"""Token-bucket rate limiter with a rate written as 'N/DURATION'."""

from __future__ import annotations

import time
from collections.abc import Callable

from timeparse.parse import parse_duration

# Clock readings are decimal floats (0.1, 0.2, …); rounding the token count to 9 places makes
# a token due at t available at t instead of a few ulps later.
_PLACES = 9


class RateLimiter:
    """Continuous refill at `rate`, capacity `burst`, starting full."""

    def __init__(self, rate: str, burst: int, clock: Callable[[], float] = time.monotonic) -> None:
        count_text, sep, duration_text = rate.partition("/")
        if not sep or not count_text.isdigit():
            raise ValueError(f"invalid rate: {rate!r}")
        count = int(count_text)
        period = parse_duration(duration_text)
        if count <= 0 or period <= 0:
            raise ValueError(f"rate must be positive: {rate!r}")
        if isinstance(burst, bool) or not isinstance(burst, int) or burst < 1:
            raise ValueError("burst must be a positive integer")
        self._per_second = count / period
        self._burst = burst
        self._clock = clock
        self._tokens = float(burst)
        self._last = clock()

    def _check(self, n: int) -> None:
        if not 1 <= n <= self._burst:
            raise ValueError(f"n must be between 1 and {self._burst}")

    def _refill(self) -> None:
        now = self._clock()
        gained = round((now - self._last) * self._per_second, _PLACES)
        self._tokens = min(float(self._burst), round(self._tokens + gained, _PLACES))
        self._last = now

    def allow(self, n: int = 1) -> bool:
        self._check(n)
        self._refill()
        if self._tokens >= n:
            self._tokens = round(self._tokens - n, _PLACES)
            return True
        return False

    def retry_after(self, n: int = 1) -> float:
        self._check(n)
        self._refill()
        missing = n - self._tokens
        return 0.0 if missing <= 0 else missing / self._per_second
