"""Token-presence snapshot for `harness-maker locate --help` and `make --help`.

Locks the load-bearing help-text tokens so silent removal during refactors
surfaces as a test failure. Mandated by PLAN-locate-cli-version-gate
§Testing Strategy + REVIEW-2026-05-21 finding F4 (drift gate).
"""

from __future__ import annotations

import re

from typer.testing import CliRunner

from harness_maker.cli import app

# `mix_stderr=False` so stderr (where Rich often emits ANSI under FORCE_COLOR)
# stays out of `result.stdout`. CI runners (GitHub Actions) set FORCE_COLOR=1
# which makes Click 8.2 / Typer 0.16+ render `--help` through Rich with ANSI
# escapes + width-driven line wraps, breaking naive substring matches; passing
# `color=False` to `.invoke()` defuses that on a per-call basis. ANSI-strip
# regex is a belt-and-suspenders fallback for cases where `color=False` does
# not fully suppress (e.g. Rich's panel borders).
runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")


def _help_text(*args: str) -> str:
    """Invoke the CLI with color disabled and ANSI-strip the resulting output.

    Returns a single string (stdout) safe for substring assertions across
    both local terminals and CI runners with FORCE_COLOR=1.
    """
    result = runner.invoke(app, list(args), color=False)
    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output!r}"
    return _ANSI_RE.sub("", result.stdout)


def test_locate_help_mentions_constraint_and_exit_codes() -> None:
    """locate --help must document `>=X.Y` semantics and exit codes 0/2/3."""
    out = _help_text("locate", "--help")
    assert ">=X.Y" in out, f"missing >=X.Y constraint: {out!r}"
    assert "--plain" in out
    assert "--require-version" in out
    # Each exit code mentioned in docstring "Exit codes: 0 found+ok,
    # 2 version mismatch, 3 no install found."
    for code in ("0", "2", "3"):
        assert code in out, f"exit code {code} not surfaced in --help: {out!r}"


def test_make_help_exposes_require_version_with_constraint_hint() -> None:
    """make --help must expose --require-version and mention >=X.Y."""
    out = _help_text("make", "--help")
    assert "--require-version" in out, f"flag missing from make --help: {out!r}"
    assert ">=X.Y" in out
    # cross-reference to locate
    assert "locate" in out, "make --help should cross-ref locate for resolution rules"


def test_locate_help_mentions_priority_rules() -> None:
    """locate --help (via the command docstring) describes the resolver priority."""
    out = _help_text("locate", "--help").lower()
    # Either prose explanation or pointer to docs/BOOTSTRAP.md is acceptable.
    assert "resolver" in out or "resolve" in out or "priority" in out or "tier" in out
