"""The runner table — and the two things about it that are easy to get backwards.

1. **More workers is not faster.** The cap is the feature; a test that only asserted
   `workers <= cores` would pass for `cores - 1`, which is the setting that makes the suite
   compete with the session waiting for it.
2. **Most runners are already parallel.** "Add `-n auto`" is pytest advice, and applying it to
   `cargo`/`go`/`vitest` either does nothing or nests a pool inside a pool.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.test_runners import (
    DEFAULT_CORE_FRACTION,
    MAX_CORE_FRACTION,
    RUNNERS,
    RunnerConfigError,
    detect_runners,
    main,
    recipe,
    resolve_fraction,
    worker_count,
)

# ── the cap ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("cores", "expected"),
    [(1, 1), (2, 1), (4, 2), (8, 4), (14, 7), (16, 8), (64, 32)],
)
def test_the_worker_count_is_half_the_cores_not_all_of_them(cores: int, expected: int) -> None:
    assert worker_count(cores) == expected


def test_a_single_core_machine_still_gets_one_worker() -> None:
    """Zero workers means no tests ran, which is reported as a pass."""
    assert worker_count(1) == 1


def test_the_reservation_holds_even_at_the_ceiling_fraction() -> None:
    """At 0.7 of 2 cores the arithmetic gives 1; at 0.7 of 3 it gives 2, never 3.

    The `cores - 1` floor is what keeps the machine answering. Without it a small box hands
    every core to the suite and the session that launched it stops responding.
    """
    assert worker_count(2, fraction=MAX_CORE_FRACTION) == 1
    assert worker_count(3, fraction=MAX_CORE_FRACTION) == 2
    assert worker_count(10, fraction=MAX_CORE_FRACTION) == 7


def test_more_cores_never_yields_fewer_workers() -> None:
    counts = [worker_count(c) for c in range(1, 65)]
    assert counts == sorted(counts)


def test_a_fraction_above_the_ceiling_is_refused_not_clamped() -> None:
    """A silent clamp makes `1.0` read as accepted while behaving as 0.7.

    Someone measuring the difference would then find none and conclude the knob is inert.
    """
    with pytest.raises(RunnerConfigError, match="within"):
        resolve_fraction(1.0)
    with pytest.raises(RunnerConfigError):
        resolve_fraction(0)
    with pytest.raises(RunnerConfigError):
        resolve_fraction(-0.5)


def test_an_absent_fraction_is_the_default_not_an_error() -> None:
    assert resolve_fraction(None) == DEFAULT_CORE_FRACTION
    assert resolve_fraction("0.7") == MAX_CORE_FRACTION


def test_a_bool_fraction_is_refused_before_the_numeric_path() -> None:
    """`True` is an int subclass and would resolve to a fraction of 1.0."""
    with pytest.raises(RunnerConfigError):
        resolve_fraction(True)


# ── the table ────────────────────────────────────────────────────────────────


def test_pytest_is_the_only_common_runner_that_is_serial_by_default() -> None:
    """The fact the whole recipe turns on.

    If this stops being true the advice inverts, and the table is where that would be noticed.
    """
    assert RUNNERS["pytest"].parallel_default is False
    for already in ("cargo", "go", "vitest", "jest", "flutter"):
        assert RUNNERS[already].parallel_default is True, already


def test_a_runner_that_is_already_parallel_says_so_in_its_recipe() -> None:
    """`parallel_is_default: true` is the signal not to paste the flag.

    For `cargo` the flag LOWERS concurrency and for `go` it oversubscribes packages; either
    way "add the parallel flag" is wrong advice, so the recipe has to carry the distinction
    rather than just a command string.
    """
    plan = recipe("go", cores=8)
    assert plan["parallel_is_default"] is True
    assert plan["workers"] == 4
    assert "-p 4" in plan["parallel"]


def test_every_parallel_template_resolves_its_worker_placeholder() -> None:
    """A leftover `{n}` would be pasted into a shell as a brace expansion."""
    for runner_id in RUNNERS:
        plan = recipe(runner_id, cores=8)
        assert "{n}" not in (plan["parallel"] or "")


def test_a_runner_needing_an_install_says_which_one() -> None:
    """`-n` on a pytest without xdist is `error: unrecognized arguments`, nothing more."""
    assert recipe("pytest", cores=8)["parallel_requires"] == "pytest-xdist"
    assert recipe("ctest", cores=8)["parallel_requires"] is None


def test_an_unknown_runner_is_refused_by_name() -> None:
    with pytest.raises(RunnerConfigError, match="unknown runner"):
        recipe("maven", cores=4)


# ── detection ────────────────────────────────────────────────────────────────


def test_detection_reads_markers_and_reports_every_match(tmp_path: Path) -> None:
    """A repo may genuinely hold two runners; reporting one hides the other's suite."""
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "go.mod").write_text("", encoding="utf-8")
    assert set(detect_runners(tmp_path)) == {"pytest", "go"}


def test_detection_of_nothing_is_not_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unrecognised project is the NORMAL case for a table of ten runners.

    Exiting non-zero here would make the stage treat "I do not know this toolchain" as a
    failure and skip the step that runs the tests.
    """
    assert main(["plan", "--root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runner"] is None
    assert payload["workers"] >= 1
    assert "project's own test command" in payload["reason"]


def test_the_cli_refuses_an_over_ceiling_fraction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert main(["plan", "--root", str(tmp_path), "--fraction", "0.95"]) == 2
    assert "within" in capsys.readouterr().err


def test_the_cli_plans_for_the_named_runner_over_detection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert main(["plan", "--root", str(tmp_path), "--runner", "jest", "--cores", "8"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runner"] == "jest"
    assert payload["workers"] == 4


def test_the_cli_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    before = sorted(p.name for p in tmp_path.iterdir())
    assert main(["plan", "--root", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == before
