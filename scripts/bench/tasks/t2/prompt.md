Add a new module `timeparse/store.py` that saves and loads named durations as a JSON file.

- `save_durations(path, mapping)`: `path` is a `str` or `pathlib.Path`; `mapping` must be a
  `dict` of name to duration string (for example `{"tea": "3m", "lunch": "1h"}`), otherwise raise
  `TypeError`. Every value is parsed with `parse_duration` before the file is touched; if any
  value is invalid, raise `ValueError` naming the bad key and leave the file exactly as it was.
  The file holds a JSON object of name to seconds, e.g. `{"tea": 180, "lunch": 3600}`.
- The write is atomic: write to a temporary file in the same directory, then replace the target.
  If writing or replacing fails, the original file is left unchanged and no temporary file is
  left behind; the error propagates.
- `load_durations(path) -> dict[str, int]` returns that mapping; a missing file returns `{}`.
