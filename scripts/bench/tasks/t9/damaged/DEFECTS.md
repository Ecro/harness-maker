# t9 damaged copy: the reference change with three planted defects

Kept out of `timeparse/`, so none of this reaches the judge's diff.

- Duplicated logic: the long style repeats the whole divmod loop over `UNITS` instead of sharing
  one helper with the compact style.
- Dead code: `_plural` is defined and never called.
- Misleading name: `names` holds the finished "count name" parts, not unit names.
