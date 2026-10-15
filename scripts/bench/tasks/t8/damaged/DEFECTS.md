# t8 damaged copy: the reference change with three planted defects

Kept out of `timeparse/`, so none of this reaches the judge's diff.

- Duplicated logic: the loop re-checks that each amount is ASCII digits (the `[0-9]` token
  pattern already guarantees it) and repeats the `MAX_SECONDS` limit as a literal
  `9223372036854775807` inside the loop, beside the check after it.
- Dead code: `_ASCII_DIGITS` is defined and never used.
- Misleading name: `count` holds the parse position in the string, not a count.
