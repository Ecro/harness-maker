# Design decisions

One entry per decision, newest last. An entry is never edited after it is accepted; a later
entry supersedes it and says so. Issue threads link here with "Resolved per D-n".

## D-1: Units and their order

Accepted 2024-03-02.

timeparse knows four units: `d` (86400 seconds), `h` (3600), `m` (60) and `s` (1). They live in
one table, `UNITS` in `timeparse/parse.py`, largest first. A duration lists each unit at most
once, largest first, so `1h30m` is valid and `30m1h` and `1h1h` are not. The table order is also
the order `format_duration` writes units in.

## D-2: A bare number means minutes

Accepted 2024-03-02.

A duration written as a bare number, with no unit at all, means that many minutes wherever
timeparse accepts one. The config format inherited this from the cron-era files it replaced,
and `config.load` applies it today. A number without a unit after other units, as in `1h30`, is
never accepted.

## D-3: Whole seconds

Accepted 2024-03-09.

Durations are whole seconds end to end: every function takes and returns an `int`. An input
that does not come to a whole number of seconds is rejected with `ValueError`, never rounded or
truncated. Should decimal amounts ever be accepted, a decimal is written `<digits>.<digits>`:
no exponent, no sign and no bare leading or trailing point.

## D-4: Case and whitespace

Accepted 2024-03-09.

Units are case-insensitive (`1H` is `1h`) and surrounding whitespace is ignored. Whitespace
inside a duration is an error: `1h 30m` is not a duration. This keeps `parse_duration` strict
enough that a typo in a config file fails loudly instead of being read as something else.

## D-5: The CLI's exit codes

Accepted 2024-04-11, superseded in part by D-8.

`python -m timeparse.cli` prints one line of seconds per argument and exits 0. On the first
invalid argument it prints `error: invalid duration: '<arg>'` on stderr and exits 2, printing
nothing on stdout. Exit code 1 is reserved for internal errors.

## D-6: Compact output is a wire format

Accepted 2024-05-20.

The compact output of `format_duration` (`1d1h1m1s`, `0s`) is a stable wire format: the
scheduler stores `schedule.normalize` results and `config.save` writes it into config files that
other tools read back, so the default output stays exactly as it is. Readability comes from an
opt-in separator instead: `format_duration(seconds, sep=" ")` puts one space between units, so
`format_duration(90061, sep=" ")` returns `"1d 1h 1m 1s"`. `sep` may only be `""` (the default)
or `" "`; any other value raises `ValueError`.

## D-7: No third-party dependencies

Accepted 2024-05-20.

timeparse uses the standard library only. It is vendored into tools that cannot take on a
dependency tree, so a helper that would need a package is written out instead, and tests use
pytest only.

## D-8: Python versions

Accepted 2024-09-30. Supersedes the Python note of D-5.

timeparse supports the Python versions that are not end of life, today 3.11 and later. Code may
use `match`, `X | Y` unions and `datetime.UTC`. The CLI behaviour of D-5 is otherwise unchanged.

## D-9: Negative durations

Accepted 2024-11-04.

A duration is never negative. Formatting or packing a negative number of seconds raises
`ValueError`, and no input string can mean a negative duration: a leading `-` or `+` is
rejected like any other unexpected character.

## D-10: Release notes

Accepted 2025-01-15.

Every user-visible change gets a line in `CHANGELOG.md` under "Unreleased", in the past tense,
naming the function it changes. Internal refactors that change no behaviour get no line.
