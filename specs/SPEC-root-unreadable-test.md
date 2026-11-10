---
type: spec
task_slug: root-unreadable-test
status: approved
created: 2026-11-10
tags: [harness-maker, spec, test]
test_framework: pytest
interview_rounds: 0
summary: "The [unreadable] row of test_land_hold's subject-hash test keeps its coverage when the suite runs as root, where a mode-000 file is still readable."
---

# SPEC — root-unreadable-test

## Intent

`tests/unit/test_land_hold.py::test_ac_011_the_subject_hash_refuses_an_oversized_subject[unreadable]`
makes a file unreadable with `chmod 000`. Root reads it anyway, so the row fails ("DID NOT RAISE")
whenever the suite runs as root, as in this project's cloud containers. Because `hm check` runs
pytest with `-x`, that one row stops the whole gate there (NT-010).

## Outcomes

- **O1.** The `[unreadable]` row passes as root and as a normal user, still asserting
  `SubjectHashError`.
- **O2.** `hm check`'s pytest gate in this container is no longer stopped by this row.

## In-Scope Scenarios

- **S1.** Given the suite runs as root, when the `[unreadable]` row runs, then reading the
  mode-000 file still fails with `PermissionError` and `compute_subject_hash` raises
  `SubjectHashError`; as a non-root user the row runs exactly as before.

## Non-Goals

- No change to `spec_machine.compute_subject_hash` or any other source file.
- No change to the other rows of the test, or to any other test.
- No skip marker: the row keeps running everywhere.

## Constraints

| Constraint | Value |
|---|---|
| Test framework | pytest (mandatory) |
| Scope | `tests/unit/test_land_hold.py`, the `unreadable` branch only |

## Irreversible Decisions

None.

## Acceptance Criteria

### AC-001: The unreadable row holds as root and as a normal user
When the process can still read the mode-000 file (`os.access(path, os.R_OK)`), the row makes
`Path.read_bytes` raise `PermissionError` for that one path only; otherwise it relies on the real
permission. In both cases `compute_subject_hash` raises `SubjectHashError` naming the file.
- oracle_source: golden. The expected error is `SubjectHashError`, from SPEC-ai-native-sdlc-vs-intent-world AC-011's unreadable row.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit, run as root here and as a normal user in CI | test_ac_011_…[unreadable] |

## Open Questions

None.

## Refinement Decisions

- **Skip check:** one test file, acceptance plain from the title, no API, schema or format change,
  reversible in minutes, so the interview is skipped and the SPEC is stamped `--exempt`.
- **Default — simulate, do not skip:** a skip would leave root runs with no coverage of the
  unreadable branch; patching the read for the one path keeps the branch exercised.
