# remind

A small reminder list kept in one JSON file.

```
python -m remind.cli add "Call the bank" --when "2026-01-05 09:00"
python -m remind.cli list
python -m remind.cli done <id>
```

## Layout

- `remind/api.py` — public Python API: `add`, `upcoming`, `done`, `parse_when`.
- `remind/store.py` — reads and writes the save file (format v1, see its docstring).
- `remind/migrate.py` — converts pre-v1 save files. Frozen, see below.
- `remind/config.py` — settings from `remind.cfg`; `REMIND_FILE` overrides the save file path.
- `remind/fmt.py` — human-readable output.
- `remind/cli.py` — command line (`main(argv) -> int`; errors exit with code 2).
- `tests/` — run with `python -m pytest`.

## Goals

- No new runtime dependencies: `remind` runs on the standard library only.
- The save file stays in format v1.

## Frozen files

- `remind/migrate.py` — installed copies already migrated their files with this exact code.
  Do not edit it.
