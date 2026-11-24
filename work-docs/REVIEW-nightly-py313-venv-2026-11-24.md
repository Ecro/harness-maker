---
type: review
task_slug: nightly-py313-venv
created: 2026-11-24
spec: "[[SPEC-nightly-py313-venv]]"
rounds: 1
summary: "One review round; 4 findings (1 P2, 3 P3), 3 fixed, 1 rejected. Second opinion skipped: not configured in this container."
---

# REVIEW — nightly-py313-venv

Reviewer: `code-reviewer` (round 1, read-only). Second opinion: skipped (CLI not installed),
warn-and-proceed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1-1 | P2 | tests/unit/test_nightly_py313_venv.py:97 | AC-002 can only run in nightly py313 (PR CI has no 3.13); if the runner image loses 3.12 it would silently skip there | accepted | fixed: `pytest.fail` instead of skip when `GITHUB_ACTIONS` is set and `UV_PYTHON=3.13` |
| R1-2 | P3 | tests/_uv_env.py:9 | an explicit key list still misses other uv settings (`UV_CACHE_DIR`, `UV_PYTHON_PREFERENCE`, ...) | accepted | fixed: forward every `UV_*` variable; AC-001 and SPEC updated |
| R1-3 | P3 | tests/unit/test_nightly_py313_venv.py:98 | the `uv python find` probe ran at the repo root and could find the project venv's interpreter | accepted | fixed: `--no-project`, `cwd=tmp_path` |
| R1-4 | P3 | tests/e2e/test_verify_health_dashboard.py:39 | `sys.executable` instead of `uv run` would remove the venv-rebuild path entirely | rejected | out of scope: the tests deliberately drive the CLI through `uv run`; the helper fixes the cause |

No P1. The reviewer also grepped every other `uv run` / `uv sync` at the repo root in `tests/`:
the rest inherit the full `os.environ` (so `UV_PYTHON` passes) or run `sys.executable` / a fake uv.
