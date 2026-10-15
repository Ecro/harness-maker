Make `parse_duration` in `timeparse/parse.py` follow this input contract. Every input class it
accepts or rejects is listed below; any other input behaves as it does today.

- Surrounding spaces, tabs and newlines are ignored: `parse_duration(" 1h\t")` returns 3600 and
  `parse_duration("\n45s\n")` returns 45.
- Any other whitespace raises `ValueError`, also around the text: `"\u00a01h"` (a no-break
  space) and `"1h\u2003"` (an em space) raise `ValueError`.
- A sign raises `ValueError`: `"+1h"`, `"-1h"` and `"1h-30m"` raise `ValueError`.
- Only the ASCII digits 0 to 9 are digits: `"\u0661h"` (an Arabic-Indic one) and `"\uff11h"`
  (a fullwidth one) raise `ValueError`.
- Leading zeros are allowed: `parse_duration("007s")` returns 7.
- The largest accepted total is 9223372036854775807 seconds (2**63 - 1):
  `parse_duration("9223372036854775807s")` returns 9223372036854775807, while
  `"9223372036854775808s"`, `"106751991167301d"` and `"106751991167300d16h"` raise `ValueError`.
- An empty or all-whitespace string raises `ValueError`: `""` and `" \t\n"`.

(The strings above are written as Python literals: `\t` is a tab, `\n` a newline and `\u00a0` the
character with that code point.)
