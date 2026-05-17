"""Phase 7 — ADR-013: `--update` rejects cwd inside .worktrees/.

Turns `[fail:snapshot-regen-inside-worktree]` (count:4 documented footgun)
into enforced prevention.
"""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from harness_maker.cli import app


def test_update_rejects_cwd_inside_worktrees(
    tmp_path: Path, monkeypatch: object
) -> None:
    """cwd inside `.worktrees/<branch>/` → CLI exits 1 with actionable error.

    Conftest autouse bypass is removed here so the guard actually fires.
    """
    monkeypatch.delenv("HARNESS_MAKER_BYPASS_WORKTREE_GUARD", raising=False)  # type: ignore[attr-defined]
    fake_repo = tmp_path / "fake-repo"
    fake_worktree = fake_repo / ".worktrees" / "execute-fake"
    fake_worktree.mkdir(parents=True)

    runner = CliRunner()
    cwd_before = os.getcwd()
    try:
        os.chdir(fake_worktree)
        result = runner.invoke(
            app,
            ["make", str(fake_worktree), "--autoloop", "--update"],
        )
    finally:
        os.chdir(cwd_before)

    assert result.exit_code == 1, (
        f"expected exit 1, got {result.exit_code}; output: {result.output}"
    )
    assert ".worktrees" in result.output
    assert "main repo root" in result.output or "cd " in result.output


def test_update_bypass_env_var_skips_guard(tmp_path: Path, monkeypatch: object) -> None:
    """ADR-013 amendment: HARNESS_MAKER_BYPASS_WORKTREE_GUARD=1 lets CI /
    programmatic regen bypass the guard (needed for harness-maker's own
    dogfood sandbox regen when tests/e2e/sandbox lives inside .worktrees/)."""
    fake_repo = tmp_path / "fake-repo"
    fake_worktree = fake_repo / ".worktrees" / "execute-fake"
    fake_worktree.mkdir(parents=True)
    # Bootstrap so --update has something to update
    runner = CliRunner()
    monkeypatch.setenv("HARNESS_MAKER_BYPASS_WORKTREE_GUARD", "1")  # type: ignore[attr-defined]
    cwd_before = os.getcwd()
    try:
        os.chdir(fake_worktree)
        bootstrap = runner.invoke(app, ["make", str(fake_worktree), "--autoloop"])
        assert bootstrap.exit_code == 0, bootstrap.output
        # Even though cwd is inside .worktrees/, bypass env var lets --update proceed
        result = runner.invoke(
            app, ["make", str(fake_worktree), "--autoloop", "--update"]
        )
        assert result.exit_code == 0, result.output
        assert "Snapshot regen invoked from inside" not in result.output
    finally:
        os.chdir(cwd_before)


def test_update_proceeds_when_cwd_outside_worktrees(tmp_path: Path) -> None:
    """cwd at a normal repo path (no .worktrees/ ancestor) → CLI proceeds.

    Two-step (bootstrap then update) because the guard fires before the
    "no harness.yaml" check, but the test must verify the guard does NOT
    fire on a clean cwd. The `--update` path needs an existing harness.yaml,
    so we bootstrap first.
    """
    fake_repo = tmp_path / "fake-repo"
    fake_repo.mkdir()
    runner = CliRunner()
    cwd_before = os.getcwd()
    try:
        os.chdir(fake_repo)
        # Bootstrap
        result1 = runner.invoke(app, ["make", str(fake_repo), "--autoloop"])
        assert result1.exit_code == 0, result1.output
        # Re-render with --update — guard should NOT fire (cwd has no .worktrees/ ancestor).
        result2 = runner.invoke(
            app, ["make", str(fake_repo), "--autoloop", "--update"]
        )
        assert result2.exit_code == 0, result2.output
        assert "Snapshot regen invoked from inside" not in result2.output
    finally:
        os.chdir(cwd_before)
