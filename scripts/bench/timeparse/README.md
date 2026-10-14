# timeparse

Parse and format human durations such as `1h30m` or `45s`.

```
python -m timeparse.cli 1h30m 45s
5400
45
```

## Layout

- `timeparse/parse.py` — `parse_duration(text) -> int` seconds.
- `timeparse/format.py` — `format_duration(seconds) -> str`.
- `timeparse/cli.py` — command line entry point (`main(argv) -> int`).
- `tests/` — run with `python -m pytest`.

Units are `d`, `h`, `m`, `s`, written largest first, each at most once. Errors raise `ValueError`;
the CLI turns them into exit code 2 with a message on stderr.
