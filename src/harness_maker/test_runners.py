"""How to run a project's tests fast, without assuming the project is Python.

Three levers, and which of them exist depends entirely on the runner:

- **parallelism** — every runner below has it, but **most already do it by default**. `pytest`
  is the outlier that is serial unless a plugin is installed, which is why "add `-n auto`" is
  the wrong universal advice: for `cargo`, `go`, `vitest` and `jest` it is either redundant or
  actively harmful (nested pools).
- **change-based selection** — only some runners can map a changed file to its tests.
- **re-run only what failed** — only some runners persist a last-failed set.

The table is a table because the alternative is prose telling an LLM to "use the project's
parallel flag", and the flag differs per runner in name, in units, and in whether it counts
workers or threads. A wrong flag is not a slow suite; it is a suite that does not run.

**Worker count is capped well below the core count on purpose** (see `worker_count`).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness_maker import command_registry

#: Fraction of visible cores to hand the test runner by default.
#:
#: Half, not all. Oversubscription makes a suite SLOWER, and three things stack here that a
#: bare core count does not see: the runner's workers are not the only processes (this repo's
#: tests shell out to `git` constantly, so N workers means roughly 2N runnable processes), the
#: machine is also running the editor and the agent that launched the suite, and several
#: runners below are ALREADY parallel internally — asking for N workers there requests N × M.
DEFAULT_CORE_FRACTION = 0.5

#: Hard ceiling on the configurable fraction. Above this the suite competes with the session
#: that is waiting for it, which is the case a user tuning for speed is least likely to notice:
#: the number goes up, the wall clock does not.
MAX_CORE_FRACTION = 0.7


class RunnerConfigError(ValueError):
    """A runner id or a core fraction with no reading."""


def visible_cores() -> int:
    """Cores this process may actually use — never the machine's total.

    `os.cpu_count()` reports the host's cores even inside a container limited to two of them,
    and CI is the place this matters most. `sched_getaffinity` is the number the scheduler
    will honour; it is Linux-only, hence the fallback.
    """
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:  # pragma: no cover — macOS / Windows
        return max(1, os.cpu_count() or 1)


def resolve_fraction(raw: object | None) -> float:
    """Absent → the default. Present → validated against the ceiling, never clamped silently.

    A silent clamp would let `1.0` read as accepted and behave as `0.7`, so a user measuring
    the difference would find none and conclude the setting does nothing.
    """
    if raw is None:
        return DEFAULT_CORE_FRACTION
    if isinstance(raw, bool):
        raise RunnerConfigError(f"core fraction must be a number in (0, {MAX_CORE_FRACTION}]")
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise RunnerConfigError(f"core fraction must be a number, got {raw!r}") from exc
    if not (0.0 < value <= MAX_CORE_FRACTION):
        raise RunnerConfigError(
            f"core fraction must be within (0, {MAX_CORE_FRACTION}], got {value!r}. "
            "Above that the suite competes with the session waiting for it."
        )
    return value


def worker_count(cores: int, *, fraction: float = DEFAULT_CORE_FRACTION) -> int:
    """`floor(cores × fraction)`, never below 1 and never above `cores - 1` on a real machine.

    The `cores - 1` reservation is what keeps the machine answering while the suite runs. On a
    single-core box it degrades to 1 rather than 0 — a worker count of 0 means "no tests ran",
    reported as a pass.
    """
    if cores < 1:
        raise RunnerConfigError(f"cores must be >= 1, got {cores}")
    if cores == 1:
        return 1
    return max(1, min(cores - 1, int(cores * fraction)))


@dataclass(frozen=True)
class Runner:
    """One test runner's three levers, plus what it cannot do.

    `parallel_default` is the field that keeps this table from being a list of flags to paste:
    when it is true, adding a worker flag is at best redundant.
    """

    id: str
    detect: tuple[str, ...]
    full: str
    parallel_default: bool
    #: `{n}` is substituted with the resolved worker count. Empty when the runner is already
    #: parallel and exposes no useful override.
    parallel: str = ""
    #: Extra install step the parallel flag needs. Empty when it is built in.
    parallel_requires: str = ""
    select_changed: str = ""
    rerun_failed: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)


RUNNERS: dict[str, Runner] = {
    "pytest": Runner(
        id="pytest",
        detect=("pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg"),
        full="pytest",
        parallel_default=False,
        parallel="pytest -n {n} --dist loadfile",
        parallel_requires="pytest-xdist",
        rerun_failed="pytest --lf",
        notes=(
            "The only common runner that is SERIAL by default — the one place `-n` is the "
            "whole win rather than a tweak.",
            "`--dist loadfile` keeps one file's tests on one worker. Drop it only if no test "
            "in the suite touches process-external state (cwd, temp paths, git refs); "
            "`--dist load` spreads them and those tests then race each other.",
            "Do NOT put `-n` in `addopts`. A suite that is only ever run in parallel hides "
            "order- and isolation-dependent failures from the serial run CI may still do.",
        ),
    ),
    "cargo-nextest": Runner(
        id="cargo-nextest",
        detect=("Cargo.toml",),
        full="cargo nextest run",
        parallel_default=True,
        parallel="cargo nextest run -j {n}",
        rerun_failed="cargo nextest run --failed",
        notes=("Process-per-test, so a crashing test is reported rather than killing the run.",),
    ),
    "cargo": Runner(
        id="cargo",
        detect=("Cargo.toml",),
        full="cargo test",
        parallel_default=True,
        parallel="cargo test -- --test-threads={n}",
        notes=(
            "Already threads tests within a binary. `--test-threads` LOWERS that; it is a cap, "
            "not an accelerator.",
        ),
    ),
    "go": Runner(
        id="go",
        detect=("go.mod",),
        full="go test ./...",
        parallel_default=True,
        parallel="go test -p {n} ./...",
        notes=(
            "`-p` bounds parallel PACKAGES and defaults to GOMAXPROCS; `-parallel` bounds "
            "tests within a package. They are different knobs and `-p` is the one that "
            "oversubscribes a machine.",
        ),
    ),
    "vitest": Runner(
        id="vitest",
        detect=("vitest.config.ts", "vitest.config.js"),
        full="vitest run",
        parallel_default=True,
        parallel="vitest run --maxWorkers={n}",
        select_changed="vitest run --changed",
        notes=("Worker pool is on by default; `--maxWorkers` caps it.",),
    ),
    "jest": Runner(
        id="jest",
        detect=("jest.config.js", "jest.config.ts"),
        full="jest",
        parallel_default=True,
        parallel="jest --maxWorkers={n}",
        select_changed="jest --findRelatedTests <changed files>",
        rerun_failed="jest --onlyFailures",
        notes=("`--findRelatedTests` is a real dep map — the closest analogue to the Python one.",),
    ),
    "ctest": Runner(
        id="ctest",
        detect=("CMakeLists.txt",),
        full="ctest",
        parallel_default=False,
        parallel="ctest -j {n}",
        rerun_failed="ctest --rerun-failed",
    ),
    "bats": Runner(
        id="bats",
        detect=("*.bats",),
        full="bats .",
        parallel_default=False,
        parallel="bats --jobs {n} .",
        parallel_requires="GNU parallel",
    ),
    "flutter": Runner(
        id="flutter",
        detect=("pubspec.yaml",),
        full="flutter test",
        parallel_default=True,
        parallel="flutter test -j {n}",
    ),
    "dotnet": Runner(
        id="dotnet",
        detect=("*.csproj", "*.sln"),
        full="dotnet test",
        parallel_default=True,
        notes=("Parallelises across assemblies; per-collection behaviour is set in code.",),
    ),
    "gradle": Runner(
        id="gradle",
        detect=("build.gradle", "build.gradle.kts"),
        full="gradle test",
        parallel_default=False,
        parallel="gradle test --max-workers={n}",
    ),
}


def detect_runners(root: Path) -> list[str]:
    """Every runner whose marker is present — a repo may legitimately have several."""
    found: list[str] = []
    for runner in RUNNERS.values():
        for marker in runner.detect:
            hits = list(root.glob(marker)) if "*" in marker else [root / marker]
            if any(p.exists() for p in hits):
                found.append(runner.id)
                break
    return found


def recipe(
    runner_id: str, *, cores: int | None = None, fraction: float = DEFAULT_CORE_FRACTION
) -> dict[str, Any]:
    """The three commands for one runner, with the worker count already resolved.

    `parallel` is `None` when the runner is already parallel and its flag would only cap it —
    stating "no change needed" beats handing over a flag that makes the suite slower.
    """
    runner = RUNNERS.get(runner_id)
    if runner is None:
        raise RunnerConfigError(f"unknown runner {runner_id!r}; known: {sorted(RUNNERS)}")
    total = visible_cores() if cores is None else cores
    workers = worker_count(total, fraction=fraction)
    parallel = runner.parallel.replace("{n}", str(workers)) if runner.parallel else ""
    return {
        "runner": runner.id,
        "cores_visible": total,
        "workers": workers,
        "fraction": fraction,
        "full": runner.full,
        "parallel": parallel or None,
        "parallel_is_default": runner.parallel_default,
        "parallel_requires": runner.parallel_requires or None,
        "select_changed": runner.select_changed or None,
        "rerun_failed": runner.rerun_failed or None,
        "notes": list(runner.notes),
    }


_USAGE = (
    "usage: hm test_runners plan [--root <dir>] [--runner <id>] [--fraction <f>] "
    "[--cores <n>]\n"
    "       hm test_runners list\n"
    "\n"
    "  plan  the parallel / changed-selection / rerun-failed commands for this project.\n"
    f"  --fraction defaults to {DEFAULT_CORE_FRACTION} and may not exceed {MAX_CORE_FRACTION}.\n"
)


def main(argv: list[str] | None = None) -> int:
    guard = command_registry.guard_or_none("test_runners", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(prog="hm test_runners", add_help=False)
    parser.add_argument("verb", choices=["plan", "list"])
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--runner")
    parser.add_argument("--fraction")
    parser.add_argument("--cores", type=int)
    try:
        opts = parser.parse_args(argv if argv is not None else sys.argv[1:])
    except SystemExit:
        sys.stderr.write(_USAGE)
        return 2

    if opts.verb == "list":
        sys.stdout.write(json.dumps(sorted(RUNNERS), sort_keys=True) + "\n")
        return 0

    try:
        fraction = resolve_fraction(opts.fraction)
        ids = [opts.runner] if opts.runner else detect_runners(opts.root)
        if not ids:
            # Not an error: an unknown runner is the normal case for a project this table has
            # never heard of. Say so and let the stage fall back to the project's own command.
            sys.stdout.write(
                json.dumps(
                    {
                        "runner": None,
                        "detected": [],
                        "cores_visible": opts.cores or visible_cores(),
                        "workers": worker_count(opts.cores or visible_cores(), fraction=fraction),
                        "fraction": fraction,
                        "reason": "no known runner detected; use the project's own test command",
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            return 0
        plans = [recipe(r, cores=opts.cores, fraction=fraction) for r in ids]
    except RunnerConfigError as exc:
        sys.stderr.write(f"[test_runners] {exc}\n")
        return 2

    sys.stdout.write(
        json.dumps(
            {"detected": ids, "plans": plans} if len(plans) > 1 else plans[0], sort_keys=True
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
