A user reports a bug in `parse_duration` in `timeparse/parse.py`: text after the last unit is
ignored instead of rejected. For example, `parse_duration("1h30m5")` returns 5400, but it must
raise `ValueError`.

Fix the bug. After the fix, each of these raises `ValueError`: `"1h30m5"`, `"1h30m!"`,
`"2d junk"` and `"45sx"`.

These documented behaviours must keep working exactly as they do now:

- Surrounding whitespace is ignored: `parse_duration(" 1h30m ")` returns 5400.
- Units are case-insensitive: `parse_duration("1H30M")` returns 5400.
- A zero amount is allowed: `parse_duration("0s")` returns 0.
- Large amounts are allowed: `parse_duration("100000s")` returns 100000.
- Text before or between the units still raises `ValueError`, as in `"x1h"` and `"1h 30m"`.
