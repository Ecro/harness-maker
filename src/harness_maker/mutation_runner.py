"""Normalise a mutmut runner's exit code — mutmut reads a mutant's fate from one integer.

``mutmut.tests_pass`` is ``return returncode != 1``: only exit 1 means "the tests failed",
i.e. killed. pytest exits 2 on a collection error and pytest-xdist exits 2 when ``-x`` stops
the session, so a mutant that breaks the module at import time — the loudest kind — was
recorded as **survived**. The resulting score is too low, and a too-low mutation score reads
as a weak test suite, which is the finding the gate exists to report. Nothing looks wrong.

mutmut runs the runner through ``shlex.split`` with no shell (POSIX branch of
``popen_streaming_output``), so ``cmd || exit 1`` is not available: the normalisation has to
be a process. This module is that process.
"""

from __future__ import annotations

import os
import subprocess
import sys

#: mutmut applies its own per-mutant timeout (``baseline_time_elapsed * 10``) and kills the
#: process it spawned — this one. That kill does not reach the pytest grandchild, so the
#: wrapper carries a backstop of its own; CLAUDE.md requires a timeout on every external
#: call for the same reason.
_TIMEOUT_ENV = "HM_MUTATION_RUNNER_TIMEOUT"
_DEFAULT_TIMEOUT_S = 900.0


def _timeout() -> float:
    raw = os.environ.get(_TIMEOUT_ENV, "")
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_TIMEOUT_S
    return value if value > 0 else _DEFAULT_TIMEOUT_S


def main(argv: list[str] | None = None) -> int:
    """Run the command and report 0 only when it exited 0.

    Every other outcome is 1, including the misuse and timeout paths: a wrapper that cannot
    run the tests has not observed the mutant surviving, and 0 is the one answer that would
    claim it had.
    """
    cmd = list(sys.argv[1:] if argv is None else argv)
    if not cmd:
        print(
            "usage: python -m harness_maker.mutation_runner <command> [args…]",
            file=sys.stderr,
        )
        return 1
    try:
        completed = subprocess.run(cmd, check=False, timeout=_timeout())
    except subprocess.TimeoutExpired:
        print(f"[mutation-runner] timed out after {_timeout():.0f}s: {cmd[0]}", file=sys.stderr)
        return 1
    except OSError as exc:  # unrunnable command — not evidence that the mutant survived
        print(f"[mutation-runner] could not run {cmd[0]}: {exc}", file=sys.stderr)
        return 1
    return 0 if completed.returncode == 0 else 1


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
