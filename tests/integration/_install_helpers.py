"""Helpers for the README install-command regression test (ADR-001 Q4 trigger).

Background: the "README overpromises IDE parity" failure class hit its 3rd
occurrence in 4 days (2026-05-19 .. 2026-05-22). Per
``work-docs/PLAN-readme-codex-truthification.md`` ADR-001's re-open
condition, the deferred Q4 test promoted to P0. This module owns the
positive-install simulation primitives + the README-extracted command
allowlist; the test functions live in
``test_readme_install_commands.py``.

The leading underscore is intentional — pytest does not collect this
module as a test file (the project convention; see ``_boundary_helpers.py``).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────
# Allowlist — the EXACT set of `Bash:` install commands documented in README
# ──────────────────────────────────────────────────────────────────────────

EXPECTED_README_INSTALL_COMMANDS: frozenset[str] = frozenset(
    {
        # Claude Code marketplace install (canonical path)
        "claude plugin marketplace add Ecro/harness-maker",
        "claude plugin install harness-maker@harness-maker",
        # Cursor local-clone install (community pattern)
        "git clone --depth 1 https://github.com/Ecro/harness-maker.git "
        "~/.cursor/plugins/local/harness-maker",
        # Codex CLI PyPI fallback (when `claude` CLI is not present)
        "uv tool install harness-maker",
        # Codex CLI first-run Skill-tool fallback (ADR-001 / install-cmd-cifence)
        "harness-maker make",
    }
)


# The Codex CLI version the advisory install test's expectation was actually
# verified against. CI must install exactly this version, and
# `test_ci_codex_pin_matches_the_verified_version` (BLOCKING, ordinary suite) enforces
# that — because the two silently diverged for 10 days: the test flipped from
# "…_fails_as_documented" to "…_succeeds_as_documented" on 2026-07-15 when codex
# 0.144.4 started cloning the repo, while CI kept installing 0.133.0 from 2026-05-23,
# where `plugin add` still errors "not found in marketplace". The step is
# `continue-on-error: true` by design (ADR-002 — external CLI behaviour must not block
# CI), so the mismatch surfaced only as a workflow annotation nobody opened.
#
# The external behaviour check stays advisory; this internal consistency check does
# not. Re-verifying the test against a newer codex means bumping BOTH this constant
# and the `npm install -g @openai/codex@…` pin in `.github/workflows/ci.yml`.
CODEX_CLI_PINNED_VERSION = "0.144.4"


# ──────────────────────────────────────────────────────────────────────────
# Wheel build + uv-tool install simulation
# ──────────────────────────────────────────────────────────────────────────


def build_local_wheel(repo_root: Path, dest_dir: Path) -> Path:
    """Build the project wheel into ``dest_dir`` and return its path.

    Why a local wheel: the PyPI install assertion in
    ``test_pypi_install_works`` must exercise the same install path a
    real user takes (``uv tool install harness-maker``), but pulling
    from PyPI in CI is slow + couples to network state. A local
    ``uv build`` against the current commit produces a wheel we can
    feed to ``uv tool install <wheel>``, simulating the user flow
    deterministically.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["uv", "build", "--wheel", "--out-dir", str(dest_dir)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    wheels = sorted(dest_dir.glob("harness_maker-*.whl"))
    if not wheels:
        raise RuntimeError(
            f"uv build produced no harness_maker-*.whl in {dest_dir}. "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
    return wheels[-1]


def install_via_uv_tool(wheel: Path, tool_dir: Path) -> Path:
    """Install ``wheel`` into an isolated ``tool_dir`` via uv-tool.

    Returns the path to the installed ``harness-maker`` executable.

    Why an isolated install dir: tests must not pollute the developer's
    real ``~/.local/share/uv/tools/`` install. We set ``UV_TOOL_DIR``
    (and ``UV_TOOL_BIN_DIR``) to point inside ``tool_dir`` and rely on
    uv's documented opt-in behavior.
    """
    bin_dir = tool_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["UV_TOOL_DIR"] = str(tool_dir / "tools")
    env["UV_TOOL_BIN_DIR"] = str(bin_dir)
    subprocess.run(  # noqa: S603
        ["uv", "tool", "install", "--force", str(wheel)],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    binary = bin_dir / "harness-maker"
    if not binary.exists():
        raise RuntimeError(
            f"`uv tool install {wheel}` did not produce {binary}; "
            f"contents of {bin_dir}: {list(bin_dir.iterdir())}"
        )
    return binary


# ──────────────────────────────────────────────────────────────────────────
# Cursor local-clone install simulation
# ──────────────────────────────────────────────────────────────────────────


def simulate_cursor_install(repo_root: Path, target_dir: Path) -> Path:
    """Simulate the README's ``git clone ~/.cursor/plugins/local/harness-maker``
    by copying the repo into ``target_dir``. Returns the install path.

    Why ``copytree`` instead of a real ``git clone``: the network path is
    out of scope for a unit-like integration test; what we care about
    structurally is that the resulting directory contains
    ``.cursor-plugin/plugin.json``, the manifest Cursor needs to register
    the plugin. ``copytree`` exactly reproduces the on-disk state
    ``git clone --depth 1`` would leave, minus the ``.git`` dir.
    """
    if target_dir.exists():
        shutil.rmtree(target_dir)
    # `symlinks=True` is REQUIRED security hardening (REVIEW security P1-3,
    # 2026-05-23): with the default `symlinks=False`, copytree follows each
    # symlink and copies the TARGET file. A PR adding e.g. a symlink at
    # `src/harness_maker/secrets -> /etc/shadow` would cause this helper to
    # read arbitrary host files during the test. With `symlinks=True`, the
    # symlinks are preserved AS symlinks — Cursor users typically wouldn't
    # have any in this tree, but the safety property must hold defensively.
    shutil.copytree(
        src=repo_root,
        dst=target_dir,
        symlinks=True,
        ignore=shutil.ignore_patterns(
            ".git",
            ".worktrees",
            ".venv",
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
        ),
    )
    return target_dir


# ──────────────────────────────────────────────────────────────────────────
# README install-command extraction
# ──────────────────────────────────────────────────────────────────────────


# Match lines of the form `    Bash: <command>` OR `    Bash  <command>` —
# both shapes appear in the README's prompt block. Protection (REVIEW code
# P2-3): requires `Bash` to start the line after whitespace, AND to be
# followed by `:` or 2+ spaces. Prose like `Bash tool` (single space) and
# `> **Bash approval:**` (no leading whitespace before `>`) do NOT match.
_BASH_LINE_RE = re.compile(
    r"^\s*Bash(?:\s*:\s*|\s{2,})(?P<cmd>\S.*?)\s*$",
    re.MULTILINE,
)


def extract_bash_install_commands(readme_text: str) -> list[str]:
    """Return the list of `Bash: <command>` lines from a README's prompt block.

    Why a narrow regex: false positives from prose mentions of the word
    "Bash" must not pollute the allowlist comparison. We anchor on the
    ``Bash`` token followed by either ``:`` or two-or-more spaces, both
    of which are conventions our prompt blocks use to introduce a Bash
    invocation. Pure prose like "the Bash approval" never matches.
    """
    commands: list[str] = []
    for match in _BASH_LINE_RE.finditer(readme_text):
        cmd = match.group("cmd").strip()
        # Skip backtick-quoted prose mentions like `Bash: claude plugin install …`
        # that appear in the Bash-approval note (ellipsis is a giveaway).
        if "…" in cmd or "..." in cmd:
            continue
        commands.append(cmd)
    return commands
