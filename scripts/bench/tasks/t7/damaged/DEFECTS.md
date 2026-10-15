# t7 damaged copy: the reference change with three planted defects

Kept out of `timeparse/`, so none of this reaches the judge's diff.

- Duplicated logic: `format_duration` splits off weeks with its own `WEEK` constant and skips
  `w` in the loop, although `UNITS` already holds the week and the loop would handle it.
- Dead code: `DAYS_PER_WEEK` is defined and never used.
- Misleading name: `days_left` holds the remaining seconds, not days.
