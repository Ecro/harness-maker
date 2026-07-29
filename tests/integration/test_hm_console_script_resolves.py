"""The one boundary the `hm` rewrite rests on, executed rather than asserted about.

REVIEW-workflow-step-audit-2026-07-29 P1-3. Every rendered `!` line now reads
`uv run --with <ref> hm <mod> …`, and the only thing that makes it resolvable is
`[project.scripts] hm` being installed into uv's `--with` overlay and exposed on PATH.

Nothing in the suite exercised that. `test_hm_entrypoint.py` runs
`python -m harness_maker.hm …` and `test_wrapup_brief_rendered_argv.py` deliberately
avoids the console script to dodge a PATH dependency — both reasonable in isolation, and
together they left the actual shipped invocation form with zero coverage. If resolution
ever fails (a `--with` ref pointing at a release older than the entry point, a stale ref
copied into a command), every mandated call in every stage dies with
`hm: command not found` and the whole suite stays green. That is CLAUDE.md checkpoint #2
verbatim: the disk content is right and only the executed content differs — a class of
defect no render-grep can reach.

`INTEGRATION=1`-guarded because it builds and installs the package into a uv overlay,
which is slow and needs a network-capable uv cache.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"), reason="INTEGRATION=1 required (builds a uv overlay)"
)


def _uv_run(*args: str) -> subprocess.CompletedProcess[str]:
    """Exactly the shape the templates render: `uv run --with <ref> <cmd…>`.

    `cwd` is a temp dir, not the repo: a rendered stage command runs from the user's
    project, and running from the repo root could let the local source tree satisfy the
    import even when the overlay does not carry the script.
    """
    uv = shutil.which("uv")
    assert uv, "uv is not on PATH — this test cannot make its claim"
    return subprocess.run(
        [uv, "run", "--with", str(_REPO_ROOT), *args],
        cwd="/tmp",
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_the_hm_console_script_resolves_under_uv_run_with() -> None:
    """The literal rendered form, end to end."""
    proc = _uv_run("hm", "--help")
    assert proc.returncode == 0, f"`hm` did not resolve:\n{proc.stderr[-2000:]}"
    assert "usage: hm <module>" in proc.stdout, proc.stdout[:400]


def test_a_dispatched_module_actually_runs_through_the_console_script() -> None:
    """`--help` alone would pass against a stub that never dispatches.

    `test_dep_map` is chosen because it succeeds with no repo state and prints parseable
    JSON, so a real dispatch is distinguishable from a no-op exit 0.
    """
    proc = _uv_run("hm", "test_dep_map", "--root", str(_REPO_ROOT), "--changed-file", "uv.lock")
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert '"mode": "full"' in proc.stdout, proc.stdout[:400]


def test_an_unknown_module_is_refused_through_the_console_script() -> None:
    """The allowlist must hold across the packaging boundary, not only in-process."""
    proc = _uv_run("hm", "os")
    assert proc.returncode == 2, (proc.returncode, proc.stderr[-500:])
    assert "unknown module" in proc.stderr
