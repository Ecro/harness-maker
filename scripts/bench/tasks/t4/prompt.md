Extend the CLI in `timeparse/cli.py` (`main(argv) -> int`).

- `--sum`: print only the total number of seconds of all durations, as one line.
- A duration argument of `-` means "read durations from standard input", one per line;
  surrounding whitespace is stripped and blank lines are ignored. `-` may be mixed with normal
  arguments and the inputs keep their order.
- Invalid input: check every input first and report **every** invalid one on stderr, one line
  each, as `error: invalid duration: '<text>'` (the text after stripping). If any input is invalid,
  print nothing on stdout and return 2.
- Without `--sum`, valid input prints one line of seconds per duration, as today.

Examples: `main(["--sum", "1h", "30m"])` prints `5400`. With stdin `"1m\n\n2m\n"`,
`main(["-", "--sum"])` prints `180`. `main(["1h", "x", "2q"])` prints two error lines and
returns 2.
