"""Token-presence snapshot for `harness-maker locate --help` and `make --help`.

Locks the load-bearing help-text tokens so silent removal during refactors
surfaces as a test failure. Mandated by PLAN-locate-cli-version-gate
§Testing Strategy + REVIEW-2026-05-21 finding F4 (drift gate).
"""

from __future__ import annotations

from typer.testing import CliRunner

from harness_maker.cli import app

runner = CliRunner()


def test_locate_help_mentions_constraint_and_exit_codes() -> None:
    """locate --help must document `>=X.Y` semantics and exit codes 0/2/3."""
    result = runner.invoke(app, ["locate", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert ">=X.Y" in out, f"missing >=X.Y constraint: {out!r}"
    assert "--plain" in out
    assert "--require-version" in out
    # Each exit code mentioned in docstring "Exit codes: 0 found+ok,
    # 2 version mismatch, 3 no install found."
    for code in ("0", "2", "3"):
        assert code in out, f"exit code {code} not surfaced in --help: {out!r}"


def test_make_help_exposes_require_version_with_constraint_hint() -> None:
    """make --help must expose --require-version and mention >=X.Y."""
    result = runner.invoke(app, ["make", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "--require-version" in out, f"flag missing from make --help: {out!r}"
    assert ">=X.Y" in out
    # cross-reference to locate
    assert "locate" in out, "make --help should cross-ref locate for resolution rules"


def test_locate_help_mentions_priority_rules() -> None:
    """locate --help (via the command docstring) describes the resolver priority."""
    result = runner.invoke(app, ["locate", "--help"])
    assert result.exit_code == 0
    out = result.stdout.lower()
    # Either prose explanation or pointer to docs/BOOTSTRAP.md is acceptable.
    assert "resolver" in out or "resolve" in out or "priority" in out or "tier" in out
