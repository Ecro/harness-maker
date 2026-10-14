Add an optional `max_units` parameter to `format_duration` in `timeparse/format.py`.

- `format_duration(seconds, max_units=None)`. With `None` the output is exactly what it is today.
- With an integer `max_units` of 1 or more, the output keeps at most that many unit positions,
  counted from the largest non-zero unit downward through d, h, m, s. A zero unit inside that
  window still uses up a position and is left out of the string, as today.
- Everything below the smallest kept position is rounded half-up into it, and the carry
  propagates upward (60s becomes 1m, 60m becomes 1h, 24h becomes 1d).
- `max_units` below 1 raises `ValueError`.

Examples:

- `format_duration(5430, max_units=1) == "2h"` (1h30m30s rounds up)
- `format_duration(5399, max_units=2) == "1h30m"`
- `format_duration(3601, max_units=2) == "1h"`
- `format_duration(86399, max_units=2) == "1d"`
- `format_duration(90, max_units=1) == "2m"` and `format_duration(89, max_units=1) == "1m"`
- `format_duration(0, max_units=1) == "0s"`
