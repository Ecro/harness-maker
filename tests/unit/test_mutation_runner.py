"""mutmut reads a mutant's fate from ONE exit code, and pytest has more than two.

`mutmut.tests_pass` is `return returncode != 1`, so every exit status except 1 means "the
tests passed" — i.e. **survived**. pytest exits 2 on a collection error and pytest-xdist
exits 2 when `-x` stops the session, so the mutants that break a module at import time, the
loudest ones there are, were recorded as survivors. Measured 2026-09-20 on
`spec_machine.py`: mutating `ACType = Literal["mechanical", ...]` to `"XXmechanicalXX"`
fails 8 tests at collection and mutmut called it survived.

That deflates every score this repo has ever reported, and it deflates it silently — a
lower number reads as a weaker test suite, which is exactly the thing the gate is supposed
to detect, so nothing about the output looks wrong.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_maker import mutation_runner
from harness_maker.spec_mutation import measure_baseline

_REAL_MUTMUT_TAIL = (
    "\N{PARTY POPPER} 42  \N{ALARM CLOCK} 0  \N{THINKING FACE} 0  "
    "\N{SLIGHTLY FROWNING FACE} 13  \N{SPEAKER WITH CANCELLATION STROKE} 0"
)


_ROOT = Path(__file__).resolve().parents[2]


def test_the_mutmut_verdict_cache_is_not_tracked() -> None:
    """The second half of the same fault: a measurement that reports a wrong number quietly.

    `mutmut run` re-runs every untested mutant IN `.mutmut-cache`, not only the ones under
    `--paths-to-mutate`. The cache was tracked from `bf65a1d1` (0.18.0) carrying 52
    `cache.py` mutants, so a run aimed at two other modules reported `16/1712` while mutating
    `cache.py` — the most plausible explanation for the execute-stage gate reporting zero
    mutants for a SPEC that named real paths. It is stale by construction too
    (`[wiki]` mutmut 2.5.1 keeps a mutant's old verdict after the tests change), so a
    committed cache spreads that staleness to every checkout.
    """
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", ".mutmut-cache"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode != 0, (
        "`.mutmut-cache` is tracked again — `mutmut run` will re-run the mutants it carries "
        "alongside the ones the SPEC asks for and report both as one score. Untrack it with "
        "`git rm --cached .mutmut-cache`; it is already in .gitignore."
    )
    ignored = {line.strip() for line in (_ROOT / ".gitignore").read_text(encoding="utf-8").split()}
    assert ".mutmut-cache" in ignored, "untracking alone: the next `git add -A` puts it back"


@pytest.mark.parametrize(
    ("inner_rc", "expected"),
    [
        (0, 0),  # tests passed → the mutant survived, and mutmut must see a non-1 code
        (1, 1),  # tests failed → killed
        (2, 1),  # collection error / xdist -x stop → killed, NOT survived
        (3, 1),  # internal error
        (4, 1),  # usage error
        (5, 1),  # no tests collected — a mutant that deletes the subject collects nothing
    ],
)
def test_every_failing_exit_code_reaches_mutmut_as_one(
    inner_rc: int, expected: int, tmp_path: Path
) -> None:
    script = tmp_path / "exit_with.py"
    script.write_text(f"raise SystemExit({inner_rc})\n", encoding="utf-8")
    assert mutation_runner.main([sys.executable, str(script)]) == expected


def test_an_empty_command_is_not_reported_as_a_passing_test_run() -> None:
    """Returning 0 here would mark the mutant survived on a wrapper misuse."""
    assert mutation_runner.main([]) == 1


def test_a_hanging_runner_is_killed_and_counted_against_the_mutant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mutant that hangs the suite is a detected mutant, not a surviving one."""

    def _hang(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1.0)

    monkeypatch.setattr(subprocess, "run", _hang)
    assert mutation_runner.main([sys.executable, "-c", "pass"]) == 1


def test_the_wrapper_is_what_measure_baseline_hands_to_mutmut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fix has to be at the injection point: every caller passes a bare pytest command."""
    seen: dict[str, list[str]] = {}

    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        seen["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout=_REAL_MUTMUT_TAIL, stderr="")

    monkeypatch.setattr("harness_maker.spec_mutation._detect_unsupported_mutmut", lambda cwd: None)
    monkeypatch.setattr(subprocess, "run", _fake_run)

    measure_baseline(["src/x.py"], cwd=Path("."), runner="python -m pytest -q tests/unit/test_x.py")
    passed = seen["args"][seen["args"].index("--runner") + 1]
    assert "harness_maker.mutation_runner" in passed, (
        "mutmut was handed the bare runner, so a collection-erroring mutant still reads as survived"
    )
    assert passed.endswith("-m pytest -q tests/unit/test_x.py"), "the caller's command was lost"


def test_a_runner_that_is_already_wrapped_is_not_wrapped_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SPEC may record the wrapped spelling; double-wrapping runs pytest under itself."""
    seen: dict[str, list[str]] = {}

    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        seen["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout=_REAL_MUTMUT_TAIL, stderr="")

    monkeypatch.setattr("harness_maker.spec_mutation._detect_unsupported_mutmut", lambda cwd: None)
    monkeypatch.setattr(subprocess, "run", _fake_run)

    already = f"{sys.executable} -m harness_maker.mutation_runner python -m pytest tests/unit"
    measure_baseline(["src/x.py"], cwd=Path("."), runner=already)
    passed = seen["args"][seen["args"].index("--runner") + 1]
    assert passed.count("harness_maker.mutation_runner") == 1
