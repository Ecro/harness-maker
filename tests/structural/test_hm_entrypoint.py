"""`hm` is the same call as `python -m harness_maker.<module>`, only shorter.

That equivalence is the entire safety argument for rewriting 390 call sites across the
shipped surface, so it is asserted rather than assumed — by exit-code parity against the
real `python -m` form, and by a coverage gate proving no rendered template can call a
module the dispatcher refuses.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker.hm import _DISPATCHABLE, main

from ._surface_baseline import render_surface

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_CALL = re.compile(r"python -m harness_maker\.([\w.]+)")
_HM_CALL = re.compile(r"(?<![\w./-])hm ([a-z][\w.]*)")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


# ── the equivalence the rewrite rests on ───────────────────────────────────────


@pytest.mark.parametrize("module", ["worktree", "iter_receipts", "spec_machine"])
def test_hm_and_python_dash_m_agree_on_exit_code_and_stderr(module: str) -> None:
    """Same code path (`runpy.run_module(run_name="__main__")`), so a divergence here
    would mean the dispatcher grew behaviour of its own — the thing it must not do."""
    direct = _run(["-m", f"harness_maker.{module}", "--definitely-not-a-flag"])
    viahm = _run(["-m", "harness_maker.hm", module, "--definitely-not-a-flag"])
    assert direct.returncode == viahm.returncode, (direct.returncode, viahm.returncode)


def test_hm_propagates_a_successful_exit_code() -> None:
    direct = _run(["-m", "harness_maker.hm", "test_dep_map", "--root", str(_REPO_ROOT)])
    assert direct.returncode == 0, direct.stderr[-800:]
    assert '"mode"' in direct.stdout


# ── the dispatcher refuses what it does not know ──────────────────────────────


def test_an_unknown_module_is_refused_not_imported() -> None:
    """`hm os` must not become `runpy.run_module("harness_maker.os")` or anything else —
    an allowlist is the difference between a dispatcher and an arbitrary-module runner."""
    assert main(["os"]) == 2
    assert main(["subprocess"]) == 2
    assert main(["definitely_not_a_module"]) == 2


def test_help_lists_the_dispatchable_set(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    for name in _DISPATCHABLE:
        assert name in out, name


def test_no_argument_is_an_error_not_a_silent_success(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2


# ── the allowlist covers what the templates actually call ─────────────────────


@pytest.fixture(scope="module")
def rendered() -> dict[str, dict[str, str]]:
    return render_surface()


def test_every_module_the_rendered_surface_calls_is_dispatchable(
    rendered: dict[str, dict[str, str]],
) -> None:
    """The failure this prevents is a template shipping a call nothing can run.

    Covers BOTH spellings: the legacy `python -m harness_maker.X` form and the short
    `hm X` form, so the gate keeps binding while the rewrite is partial and after it is
    complete.
    """
    called: set[str] = set()
    for commands in rendered.values():
        for text in commands.values():
            called.update(_MODULE_CALL.findall(text))
            called.update(_HM_CALL.findall(text))
    assert called, "found no harness_maker calls at all — the extraction broke, not the set"
    missing = called - set(_DISPATCHABLE)
    assert not missing, (
        f"rendered commands call modules `hm` will refuse: {sorted(missing)} — add them to "
        f"_DISPATCHABLE in src/harness_maker/hm.py"
    )


def test_the_allowlist_names_only_real_modules() -> None:
    """A stale entry is an invitation to keep a dead call site in a template."""
    src = _REPO_ROOT / "src" / "harness_maker"
    for name in _DISPATCHABLE:
        rel = Path(*name.split("."))
        assert (src / rel).with_suffix(".py").is_file(), name
