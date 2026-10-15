Make the command line in `timeparse/cli.py` report every invalid argument instead of stopping at
the first one.

- When one or more arguments are invalid, `main` prints one line `error: invalid duration: '<text>'`
  to stderr for each invalid argument, in argument order, prints nothing to stdout and returns 2:
  `main(["1h", "nope", "2x", "30s"])` prints the lines for `'nope'` and `'2x'` and returns 2.
- The same holds with `--total`: `main(["--total", "1h", "nope", "2x"])` prints the two error lines,
  prints no total and returns 2.
- Valid arguments behave as today: `main(["1h", "30s"])` prints `3600` and `30`, and
  `main(["--total", "1h", "30s"])` prints `3630`; both return 0.
- Change only the function `main` in `timeparse/cli.py`: leave the other functions, the imports,
  the module docstring and every other file under `timeparse/` as they are. You may add or change
  tests under `tests/`.
