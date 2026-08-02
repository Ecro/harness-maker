"""Phase 3 of PLAN-sessionid-env-propagation — the root env pin, proved by absence.

An in-process `assert os.environ.get("CLAUDECODE") is None` is worthless here: it passes
vacuously in CI, under `env -u CLAUDECODE`, and in any non-Claude shell, with no root
conftest at all. Composite-equality is no better — after Phase 1 both tri-state signals are
weight-0 and non-gating, so the composites coincide whether or not this phase exists.

So the check runs an INNER pytest in a subprocess with all three variables deliberately set
and asserts the inner run is green. Delete `tests/conftest.py` and this goes red, in CI and
locally, which is the only property that makes it a gate rather than a decoration.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Deliberately NOT `INTEGRATION=1`-gated, unlike its neighbours in this directory. That
# guard exists for tests that hit an external service (CLAUDE.md test policy); this one
# only shells out to pytest. Gating it would have made the module's own claim — "delete
# `tests/conftest.py` and this goes red, in CI and locally" — false in the half that
# matters, since PR CI does not set INTEGRATION. A gate that never runs is a decoration.

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _probe_dir(tag: str) -> Path:
    """A probe dir INSIDE the repo — `tmp_path` would miss the rootdir conftest under test —
    but unique per process and per test.

    A fixed shared name survives a hard-killed run, and a leftover is not inert here: the
    repo's own unclassified-test-directory gate (`test_test_dep_map_select`) walks `tests/`
    at RUN time, so it reads the filesystem and `.gitignore` cannot hide a leftover from it.
    The pid suffix stops concurrent runs colliding; `_sweep_stale_probes` below covers the
    SIGKILL case, which the suffix alone cannot.
    """
    return _REPO_ROOT / "tests" / f"_env_isolation_probe_{os.getpid()}_{tag}"


def _sweep_stale_probes() -> None:
    """Reap probe dirs a hard-killed earlier run left behind.

    Runs at IMPORT time, i.e. during collection — before any test body executes, so the
    directory gate that walks `tests/` at run time never sees a leftover. Best-effort by
    design: a sweep failure must not be the thing that fails the suite.
    """
    for stale in (_REPO_ROOT / "tests").glob("_env_isolation_probe_*"):
        shutil.rmtree(stale, ignore_errors=True)


_sweep_stale_probes()


_POISON = {
    "CLAUDECODE": "1",
    "CLAUDE_ENV_FILE": "/tmp/hm-env-isolation-probe",
    "HM_SESSION_ID": "probe-session-id",
}

_INNER = """
import os

def test_the_root_conftest_pinned_the_session_env():
    leaked = {k: v for k, v in os.environ.items()
              if k in ("CLAUDECODE", "CLAUDE_ENV_FILE", "HM_SESSION_ID")}
    assert not leaked, f"root conftest did not pin the session env: {leaked}"
"""


def _run_inner(*, poisoned: bool) -> subprocess.CompletedProcess[str]:
    """Run a one-test pytest inside the repo's rootdir so `tests/conftest.py` applies."""
    inner_dir = _probe_dir("pin")
    env = {**os.environ}
    env.pop("PYTEST_CURRENT_TEST", None)
    if poisoned:
        env.update(_POISON)
    else:
        for key in _POISON:
            env.pop(key, None)
    # mkdir/write_text INSIDE the try: an OSError there would otherwise leak the dir past
    # the `finally`, which is the one failure path the cleanup exists for.
    try:
        inner_dir.mkdir(parents=True, exist_ok=True)
        (inner_dir / "test_probe.py").write_text(_INNER, encoding="utf-8")
        probe = inner_dir / "test_probe.py"
        return subprocess.run(
            [sys.executable, "-m", "pytest", str(probe), "-q", "-p", "no:cacheprovider"],
            cwd=str(_REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    finally:
        # rmtree, not rmdir: pytest leaves a __pycache__ behind, and a surviving
        # `tests/_env_isolation_probe/` trips the repo's own unclassified-test-directory
        # gate — the same 'a new test directory inherits nothing' rule this PLAN's
        # Phase 3 exists to satisfy.
        shutil.rmtree(inner_dir, ignore_errors=True)


def test_session_env_is_pinned_even_when_the_caller_sets_it() -> None:
    """The gate. Fails deterministically if `tests/conftest.py` is missing or stops
    covering a directory — which is exactly how the previous pin (unit-only) let
    `tests/integration/` read the developer's live Claude session."""
    result = _run_inner(poisoned=True)
    assert result.returncode == 0, (
        "the root conftest did not neutralise a poisoned session env\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def test_the_probe_itself_can_fail() -> None:
    """Meta-check: prove the probe has teeth.

    Run the same inner test with the root conftest's pin defeated. If this passes, the
    gate above is green for the wrong reason and would stay green after a regression —
    the failure mode this whole PLAN is about.
    """
    inner_dir = _probe_dir("teeth")
    try:
        inner_dir.mkdir(parents=True, exist_ok=True)
        probe = inner_dir / "test_probe.py"
        probe.write_text(_INNER, encoding="utf-8")
        # A LOCAL conftest that re-sets the variables AFTER the root autouse fixture ran,
        # simulating "the pin is not in effect for this directory".
        (inner_dir / "conftest.py").write_text(
            "import pytest\n\n"
            "@pytest.fixture(autouse=True)\n"
            "def _undo_the_pin(monkeypatch):\n"
            "    monkeypatch.setenv('CLAUDECODE', '1')\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(probe), "-q", "-p", "no:cacheprovider"],
            cwd=str(_REPO_ROOT),
            env={**os.environ},
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        assert result.returncode != 0, (
            "the probe passed with the pin defeated — it cannot detect a regression\n"
            f"--- stdout ---\n{result.stdout}"
        )
    finally:
        shutil.rmtree(inner_dir, ignore_errors=True)


def test_fresh_install_composite_is_identical_under_both_env_states() -> None:
    """What isolation actually guarantees: the score does not depend on WHERE it ran.

    The 66/72 floors are satisfied by Phase 1 alone, so they prove nothing about this
    phase. Equality does.
    """
    from harness_maker.models import Preset
    from harness_maker.readiness import compute_readiness

    saved = {k: os.environ.get(k) for k in _POISON}
    try:
        for key in _POISON:
            os.environ.pop(key, None)
        clean = compute_readiness(_REPO_ROOT, Preset.PRODUCTION).composite
        os.environ.update(_POISON)
        poisoned = compute_readiness(_REPO_ROOT, Preset.PRODUCTION).composite
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert clean == poisoned, (
        f"composite depends on the ambient session env: {clean} clean vs {poisoned} poisoned"
    )
