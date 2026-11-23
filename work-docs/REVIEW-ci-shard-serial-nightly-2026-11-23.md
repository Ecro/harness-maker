---
type: review
task_slug: ci-shard-serial-nightly
created: 2026-11-23
spec: "[[SPEC-ci-shard-serial-nightly]]"
plan: "[[PLAN-ci-shard-serial-nightly]]"
rounds: 2
summary: "Two review rounds; 8 findings, 7 fixed, 1 rejected as the SPEC's accepted cost. Second opinion (codex) skipped: CLI not installed."
---

# REVIEW — ci-shard-serial-nightly

Reviewer: `code-reviewer` (rounds 1 and 2). Second opinion: `codex` skipped (CLI not installed),
warn-and-proceed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1-1 | P1 | tests/conftest.py:86 | `ruff format --check` fails (one blank line before the `#:` block) | accepted | fixed: `ruff format` |
| R1-2 | P1 | tests/unit/test_ci_shard_serial_nightly.py:192 | `mypy --strict` fails on `doc.get(True)` and `in` on an optional `Any` | accepted | fixed: `_workflow` returns `dict[Any, Any]`, triggers typed |
| R1-3 | P3 | tests/conftest.py:67 | a bad `HM_TEST_SHARD` under xdist becomes opaque INTERNALERRORs | accepted | fixed: validated in `pytest_configure`; AC-001 test covers `-n 2` |
| R1-4 | P3 | .github/workflows/ci.yml:27 | default `fail-fast: true` hides the other shards' failures | accepted | fixed: `fail-fast: false` in ci.yml and release.yml |
| R1-5 | P3 | .github/workflows/ci.yml:70 | `if: always()` leaves a red `quality-gate` on a superseded, cancelled run | accepted | fixed: `if: ${{ !cancelled() }}` |
| R1-6 | P3 | tests/conftest.py:50 | shards uneven by test count (+21% on one shard) | rejected | SPEC Refinement Decisions (hash split accepted; real times read from this PR's CI) |
| R2-1 | P2 | tests/conftest.py:50 | multi-paragraph docstrings on `shard_of` / `pytest_configure` | accepted | fixed: one WHY line each, detail as a comment |
| R2-2 | P3 | .github/workflows/ci.yml:74 | a hand-cancelled run leaves the summary skipped, which a required check counts as passing | accepted | fixed: comment names the trade and when to switch back |
