Add a token-bucket rate limiter in a new module `timeparse/ratelimit.py`.

- `RateLimiter(rate, burst, clock=time.monotonic)`. `rate` is a string `"N/DURATION"`: `N` tokens
  per duration, where `N` is a positive integer and `DURATION` is anything `parse_duration`
  accepts with a positive value (for example `"10/1s"`, `"5/1m"`, `"3/1h30m"`). `burst` is a
  positive integer, the bucket's capacity. Anything else raises `ValueError`. `clock` returns the
  current time in seconds as a float.
- The bucket starts full and refills continuously at the rate, never above `burst`.
- `allow(n=1) -> bool`: if `n` tokens are available, take them and return `True`; otherwise
  return `False` and take nothing.
- `retry_after(n=1) -> float`: seconds until `n` tokens will be available (`0.0` if they are
  available now). Does not take tokens.
- `n` must be between 1 and `burst` for both methods, otherwise `ValueError`.
- A token is available exactly when it is due: with `rate="10/1s"` and `burst=1`, calls to
  `allow()` at clock readings 0.0, 0.1, 0.2, 0.3 … 1.0 must all return `True`, and a call at
  0.05 after the one at 0.0 returns `False`.
