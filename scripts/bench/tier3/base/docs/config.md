# Config files

`timeparse.config` reads and writes the timeout files our services load at start-up.

## Format

One timeout per line, `name = duration`:

```
# timeouts.conf
connect = 30s
read = 2m
retry_window = 1h30m
idle = 45
```

- A name starts with a lower-case letter and holds only lower-case letters, digits and `_`.
- A duration is anything `parse_duration` accepts, plus a bare number, which is minutes (D-2):
  `idle = 45` is 45 minutes.
- Blank lines and everything after a `#` are ignored.
- A name may appear once.

`config.load(text)` returns `{name: seconds}`, and `config.save(values)` writes the same format
back, one line per name in sorted order, each duration in compact form (D-6). `save` then `load`
gives back the same values.

## Errors

`load` raises `ConfigError` (a `ValueError`) on the first bad line, with a message that names
the line. The services print that message as it is, and their operators grep the logs for it.

| Line | Message |
|---|---|
| `read 2m` (no `=`) | `config line 1: expected 'name = duration'` |
| `Read = 2m` (bad name) | `config line 1: expected 'name = duration'` |
| `read = 2m` twice | `config line 2: read is set twice` |
| `timeout = 1h 30m` | `config line 1: bad duration '1h 30m'` |

For example:

```
>>> config.load("connect = 30s\ntimeout = 1h 30m\n")
Traceback (most recent call last):
  ...
timeparse.config.ConfigError: config line 2: bad duration '1h 30m'
```

A duration that is malformed shows its text in the message, so an operator can find it.
