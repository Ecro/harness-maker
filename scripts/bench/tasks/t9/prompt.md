Add a long output style to `format_duration` in `timeparse/format.py`, as
`format_duration(seconds, style="long")`.

- `style="compact"` is the default and gives exactly today's output.
- `style="long"` writes each non-zero unit as its count, a space and its name, joined by `", "`.
  The name is singular for a count of 1 and plural otherwise: `format_duration(5400,
  style="long")` returns `"1 hour, 30 minutes"` and `format_duration(90061, style="long")`
  returns `"1 day, 1 hour, 1 minute, 1 second"`.
- Zero is `"0 seconds"` in the long style.
- Any other `style` raises `ValueError`, and negative seconds still raise `ValueError` in both
  styles.
- The names live in one table, `UNIT_NAMES` in `timeparse/format.py`, which maps each unit letter
  to its singular and plural names, for example `"h": ("hour", "hours")`.
- Both styles must follow the one unit table, `UNITS` in `timeparse/parse.py`: adding a unit to
  `UNITS` (with its names in `UNIT_NAMES`) or removing one changes both styles, with no other
  edit.
- For example, with `"w": 604800` added first to `UNITS` and `"w": ("week", "weeks")` added to
  `UNIT_NAMES`, `format_duration(694861)` returns `"1w1d1h1m1s"` and `format_duration(694861,
  style="long")` returns `"1 week, 1 day, 1 hour, 1 minute, 1 second"`.
- With `"d"` removed from `UNITS`, `format_duration(90061)` returns `"25h1m1s"` and
  `format_duration(90061, style="long")` returns `"25 hours, 1 minute, 1 second"`.
