Make `parse_duration` in `timeparse/parse.py` reject a zero duration, which is always a mistake in
a timeout.

- `parse_duration` raises `ValueError` when the total is zero: `parse_duration("0s")`,
  `parse_duration("0h0m")` and `parse_duration(" 0D ")` all raise.
- A zero unit inside a non-zero duration is still accepted: `parse_duration("0h1m")` returns 60
  and `parse_duration("1h0m")` returns 3600.
- Apart from rejecting a zero duration, existing behaviour of the package must not change.
