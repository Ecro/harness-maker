Add weeks to `timeparse`. The new unit `w` is 7 days, that is 604800 seconds.

- `format_duration` uses weeks as its largest unit: `format_duration(604800)` returns `"1w"`,
  `format_duration(1209600)` returns `"2w"` and `format_duration(694861)` returns
  `"1w1d1h1m1s"`.
- Values below one week are formatted exactly as today: `format_duration(604799)` returns
  `"6d23h59m59s"`.
- `parse_duration` accepts `w` with the same rules as the other units: `parse_duration("1w")`
  returns 604800, `parse_duration("2w3d")` returns 1468800 and `parse_duration("1W")` returns
  604800.
- `w` comes before `d` in the unit order, so `"1d1w"` and `"1w1w"` raise `ValueError`.
- The round-trip invariant must keep holding: for every integer `s` from 0 to 10000000,
  `parse_duration(format_duration(s)) == s`.
