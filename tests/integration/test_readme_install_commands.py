"""README install-command regression test (ADR-001 Q4 trigger — install-cmd-cifence).

This file is the canonical mechanical defense against the "README
overpromises IDE parity" failure class, which recurred 3 times in
4 days (2026-05-19 .. 2026-05-22) before this test landed:

1. ``[wiki:gotcha] readme-one-prompt-bash-not-slash`` (2026-05-19)
2. ``[wiki:gotcha] codex-marketplace-readme-overpromise`` (2026-05-22)
3. Codex first-run Skill-tool overpromise (2026-05-22)

Per ``work-docs/PLAN-readme-codex-truthification.md`` ADR-001's re-open
condition (3rd occurrence → P0 promote), this test now mechanically
verifies that:

1. The PyPI install path (``uv tool install harness-maker``) actually
   produces a working ``harness-maker`` binary. BLOCKING.
2. The Cursor git-clone install path lands the plugin manifest where
   Cursor expects to find it. BLOCKING.
3. Every ``Bash:`` install command in README.md / README.ko.md is in
   the explicit allowlist defined in ``_install_helpers.py``. BLOCKING.
   (Catches README drift: a new install command appearing without an
   allowlist update means the command is untested.)
4. ``codex plugin marketplace add`` + ``codex plugin add`` continues to
   FAIL as documented — if it ever starts passing, our README's
   "no native Codex marketplace install" claim has become stale.
   ADVISORY (xfail strict=False + shutil.which guard for missing
   codex CLI).

Gating policy per ``PLAN-install-cmd-cifence`` ADR-002 (Round 2 amend):
positive + lint = BLOCKING; negative = ADVISORY.

Opt-in via ``INSTALL_CMD_TEST=1`` env var; otherwise the BLOCKING tests
skip (CI sets the env in the install-cmd-regression job).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.integration._install_helpers import (
    EXPECTED_README_INSTALL_COMMANDS,
    build_local_wheel,
    extract_bash_install_commands,
    install_via_uv_tool,
    simulate_cursor_install,
)

INSTALL_CMD_GATE = pytest.mark.skipif(
    not os.getenv("INSTALL_CMD_TEST"),
    reason="install-cmd regression tests require INSTALL_CMD_TEST=1 "
    "(CI install-cmd-regression job sets this; locally opt-in to avoid "
    "the multi-second wheel build per pytest run)",
)


def _repo_root() -> Path:
    """Walk upward from this file to find the repo root (pyproject.toml).

    Why not hardcode: the repo lives in different locations depending on
    whether tests run from the main checkout or a worktree under
    ``.worktrees/<name>/``. Walking from ``__file__`` resolves to whichever
    checkout is currently active.
    """
    # Walk from `here.parent` upward — `here` itself is a file path, so
    # `here / 'pyproject.toml'` would be `.../file.py/pyproject.toml`, a
    # path that cannot exist (REVIEW code P2-1, 2026-05-23). Starting from
    # the containing directory makes the first iteration meaningful.
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"could not locate pyproject.toml from {here}")


# ──────────────────────────────────────────────────────────────────────────
# Positive BLOCKING tests
# ──────────────────────────────────────────────────────────────────────────


@INSTALL_CMD_GATE
def test_pypi_install_works(tmp_path: Path) -> None:
    """`uv tool install harness-maker` (against a local wheel) produces a
    working `harness-maker` CLI.

    Failure mode this catches: a refactor that breaks the package's
    entry point definition, or a `pyproject.toml` change that drops
    the ``[project.scripts]`` declaration. Either would silently break
    the PyPI install path README documents.
    """
    repo = _repo_root()
    wheel = build_local_wheel(repo, tmp_path / "dist")
    tool_dir = tmp_path / "tools"
    binary = install_via_uv_tool(wheel, tool_dir)
    # Verify the installed binary actually runs. The Typer CLI does NOT
    # expose `--version` (only --help, --install-completion, --show-completion),
    # so a smoke `--help` invocation is the universal "this binary is runnable"
    # check — exit 0 means uv tool install successfully wired the entry point.
    result = subprocess.run(  # noqa: S603 — argv fixed, no shell
        [str(binary), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    # --help must advertise the `make` subcommand. Typer/Rich emits ANSI
    # color codes into the captured stdout even when not on a TTY (verified
    # 2026-05-23 CI failure: `\x1b[1;36mmake` inside the Commands box). Strip
    # ANSI sequences first, then look for `make` as a command-list entry
    # (line starts with optional whitespace + box-drawing chars + `make`
    # followed by a space or end-of-word). Substring match (REVIEW code P2-2)
    # would false-positive on future help prose containing the word "make".
    import re

    ansi_re = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
    clean_stdout = ansi_re.sub("", result.stdout)
    assert re.search(r"(?m)^\s*[│|]?\s*make\b", clean_stdout), (
        f"`{binary} --help` did not advertise the `make` subcommand as a "
        f"command-list entry. cleaned stdout: {clean_stdout!r}\n"
        f"raw stderr: {result.stderr!r}"
    )


@INSTALL_CMD_GATE
def test_cursor_git_clone_path_structure(tmp_path: Path) -> None:
    """`git clone ~/.cursor/plugins/local/harness-maker` lands the
    `.cursor-plugin/plugin.json` manifest Cursor needs.

    Failure mode this catches: someone deletes or relocates
    ``.cursor-plugin/plugin.json`` (or its parent directory) without
    updating the README's Cursor branch. Without the manifest, Cursor
    cannot register the plugin after reload.
    """
    repo = _repo_root()
    install_path = simulate_cursor_install(repo, tmp_path / "harness-maker")
    manifest = install_path / ".cursor-plugin" / "plugin.json"
    assert manifest.is_file(), (
        f"Cursor manifest missing at {manifest}. "
        f"Contents of {install_path}: {list(install_path.iterdir())}"
    )
    # Verify the manifest parses + has the required name field.
    import json

    parsed = json.loads(manifest.read_text(encoding="utf-8"))
    assert parsed.get("name") == "harness-maker", (
        f"Cursor manifest at {manifest} has wrong name: {parsed.get('name')!r}"
    )


# ──────────────────────────────────────────────────────────────────────────
# README-lint BLOCKING test (ADR-002 Round 2 amend)
# ──────────────────────────────────────────────────────────────────────────


def test_readme_install_commands_in_allowlist() -> None:
    """Every `Bash:` install command in README.md / README.ko.md appears in
    `EXPECTED_README_INSTALL_COMMANDS`.

    Failure mode this catches: a new install command is added to README
    without a corresponding allowlist update — i.e., the install path
    is documented but not tested. ADR-002 Round 2 amend promoted this
    check from ADVISORY to BLOCKING: allowlist drift IS the regression
    class this PLAN defends against.

    Recovery: if the new command IS intended, add it to
    ``EXPECTED_README_INSTALL_COMMANDS`` in ``_install_helpers.py`` AND
    add a positive test for it. If unintended, remove it from README.

    NOT gated by INSTALL_CMD_TEST — this test is pure file-read + regex,
    so it must run on every PR CI to catch drift before merge.
    """
    repo = _repo_root()
    readmes = [repo / "README.md", repo / "README.ko.md"]
    found: set[str] = set()
    for readme in readmes:
        if not readme.is_file():
            continue
        commands = extract_bash_install_commands(readme.read_text(encoding="utf-8"))
        found.update(commands)
    extra = found - EXPECTED_README_INSTALL_COMMANDS
    assert not extra, (
        f"README contains Bash: install commands not in the test allowlist: "
        f"{sorted(extra)!r}\n"
        f"Add them to EXPECTED_README_INSTALL_COMMANDS in "
        f"tests/integration/_install_helpers.py AND author a positive test "
        f"that verifies each new command actually works."
    )


# ──────────────────────────────────────────────────────────────────────────
# Negative ADVISORY test
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.advisory
def test_codex_marketplace_add_fails_as_documented(tmp_path: Path) -> None:
    """`codex plugin marketplace add <repo>` + `codex plugin add <plugin>`
    continues to fail as documented.

    Per ADR-001 Round 1 + ADR-002 Round 2 amend, this test is ADVISORY:
    it's a normal positive-assertion test (assertions hold when the
    README claim is accurate; assertions break when codex behavior
    changes), and the ADVISORY nature is enforced at the CI workflow
    level via ``continue-on-error: true`` on the install-cmd-regression
    job's step that invokes this test. The custom ``@pytest.mark.advisory``
    is registered in ``pyproject.toml`` and lets CI run advisory vs
    blocking tests in separate steps (per ADR-002).

    The earlier ``xfail(strict=False)`` approach was rejected (validator
    P1-1 follow-up): xfail inverts the intuitive PASS/FAIL semantic —
    a test that asserts the documented-broken behavior would be marked
    XPASS (confusing) when assertions hold, and XFAIL (advisory pass)
    when codex behavior changes. The ``advisory`` mark + workflow
    continue-on-error keeps the test semantics straightforward.
    """
    codex_bin = shutil.which("codex")
    if codex_bin is None:
        pytest.skip(
            "codex CLI not installed — negative test cannot run. "
            "CI install-cmd-regression job installs codex via "
            "`npm install -g @openai/codex`; locally, install it the "
            "same way to exercise this test."
        )
    repo = _repo_root()
    # Use an isolated CODEX_HOME so the test does not pollute the developer's
    # ~/.codex/ state (marketplace registrations persist there).
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    # Step 1: register the repo as a Codex marketplace. This typically succeeds
    # — codex accepts any path/git URL as a marketplace root.
    subprocess.run(  # noqa: S603
        [codex_bin, "plugin", "marketplace", "add", str(repo)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    # Step 2: attempt to install the plugin from the registered marketplace.
    # This MUST fail (today) because the repo ships no Codex `marketplace.json`.
    result = subprocess.run(  # noqa: S603
        [codex_bin, "plugin", "add", "harness-maker@harness-maker"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    # Assert: nonzero exit AND stderr contains the documented error pattern.
    # If either condition flips (exit 0 OR stderr no longer matches), the
    # README's "no native Codex install" claim is stale.
    assert result.returncode != 0, (
        f"`codex plugin add` UNEXPECTEDLY SUCCEEDED — README needs re-truthification.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "not found in marketplace" in result.stderr.lower(), (
        f"`codex plugin add` failed but with a different error than documented. "
        f"README + ADR-001 may need update.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
