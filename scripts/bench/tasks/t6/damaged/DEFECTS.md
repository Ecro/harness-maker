# t6 damaged copy: the reference fix with three planted defects

Kept out of `timeparse/`, so none of this reaches the judge's diff.

- Duplicated logic: `_has_units` scans the string with `_TOKEN` a second time to find the end of
  the last token, which the main loop already tracks in `pos`.
- Dead code: `seen_units` is filled in the loop and never read.
- Misleading name: `_has_units` returns True when text is left over after the units.
