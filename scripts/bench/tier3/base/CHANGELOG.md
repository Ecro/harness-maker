# Changelog

All user-visible changes, newest first (D-10).

## Unreleased

- Nothing yet.

## 0.3.0 (2025-02-03)

- Added `strict.is_canonical` and `strict.parse_strict` for the scheduler's API.
- `schedule.normalize` documents that its output must parse back to the same seconds.

## 0.2.3 (2024-07-09)

- Fixed `pack.unpack` typing under `mypy --strict` (#18).

## 0.2.2 (2024-06-01)

- Added `schedule.split`.
- Added `pack.pack` and `pack.unpack`; packed strings are a frozen storage format.

## 0.2.1 (2024-05-12)

- Added `schedule.total` (#15).
- Added `config.load` and `config.save`.

## 0.2.0 (2024-04-11)

- The CLI takes several durations and exits 2 on the first invalid one (#3, D-5).

## 0.1.0 (2024-03-09)

- First release: `parse_duration` and `format_duration`.
