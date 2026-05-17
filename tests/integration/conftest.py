"""Shared fixtures for tests/integration/ — minimal real-shaped project trees.

Other integration tests can import ``build_min_fixture`` to get a
deterministic project directory that exercises real signal computation
without depending on the harness-maker repo itself.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

# Per-run telemetry shard date. Dynamic (always "yesterday in UTC") so the
# fixture stays within _candidate_files(obs, days=365)'s file-count cap
# regardless of when the test runs. A hardcoded ISO date would silently
# rot once it fell outside the most-recent 365 dated shards observed by
# the rotation reader, surfacing as a spurious "fixture floor not cleared"
# failure pointing the developer at signal weights instead of the date.
# (Flagged by security-reviewer P1 in REVIEW-health-plugin-bugs-2026-05-17.)
_FIXTURE_METRICS_DATE = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

# Number of telemetry entries written into the fixture's dated file.
# Must clear the ``metrics_has_samples`` threshold (>= 5) so the
# observability_setup dimension scores fully — keeping the floor stable
# against future signal additions.
_FIXTURE_TELEMETRY_LINES = 6


def build_min_fixture(tmp_path: Path) -> Path:
    """Seed a minimal project tree that clears MIN_FIXTURE_SCORE=30 on Side.

    Composition (ADR-002 in PLAN-health-plugin-bugs-2026-05):
      - ``.claude/harness.yaml`` with ``preset: Side``
      - ``CLAUDE.md`` with the basic required sections
      - ``.claude/observability/`` with a rotated metrics file + dashboard.md
      - ``.claude/settings.json`` with the 4 dangerous-pattern deny entries
      - ``.claude/memory/`` with failures.md + wiki.md
      - ``tests/`` with one trivial test
      - ``.github/workflows/ci.yml`` invoking pytest

    These five seeded signal groups deterministically clear the 30-point floor;
    additions to ``_dim_*`` functions can only raise the score, not lower it
    below the floor. If a future rubric change demotes one of these signals
    enough to drop below 30, the integration test will fail with a clear
    "fixture floor not cleared" message — the fix is to seed one more signal,
    not to lower the floor.
    """
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n## Tech Stack\nPython\n\n## Conventions\n- ruff\n- mypy\n",
        encoding="utf-8",
    )

    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    (claude / "settings.json").write_text(
        '{"permissions": {"deny": ['
        '"Bash(rm:*)", "Bash(curl * | sh)", '
        '"Write(/etc/**)", "Write(~/.ssh/**)"'
        "]}}\n",
        encoding="utf-8",
    )

    obs = claude / "observability"
    obs.mkdir()
    (obs / f"metrics-{_FIXTURE_METRICS_DATE}.jsonl").write_text(
        "\n".join("{}" for _ in range(_FIXTURE_TELEMETRY_LINES)) + "\n",
        encoding="utf-8",
    )
    (obs / "dashboard.md").write_text("# dashboard\n", encoding="utf-8")

    memory = claude / "memory"
    memory.mkdir()
    (memory / "failures.md").write_text("# Failures\n", encoding="utf-8")
    (memory / "wiki.md").write_text("# Wiki\n", encoding="utf-8")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_x() -> None:\n    assert True\n", encoding="utf-8")

    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "name: ci\n"
        "on: [push, pull_request]\n"
        "jobs:\n"
        "  t:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - run: pytest\n",
        encoding="utf-8",
    )

    return tmp_path
