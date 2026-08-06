"""PLAN-worktree-side-defaults ADR-006 — the interactive migration prompt, over a real pty.

Everything else about this migration is covered by mocking `_input_or_empty`. That
proves the branch computes the right value; it does not prove the branch is REACHABLE,
and reachability is where this one nearly shipped broken:

* Piping stdin does not work. `make` auto-flips to `autoloop_mode` when stdin is not a
  tty, so `printf 'n\\n' | make … --reinterview` answers nothing and silently takes the
  non-interactive default. A first manual attempt did exactly that and read as "the
  prompt never fires".
* `--reinterview` does not reach it either. The interview asks `_ask_worktree` itself,
  so `_apply_worktree_enabled` skips the migration branch (`asked=True`) rather than
  asking twice. The prompt is reachable ONLY from a plain `make <dir>` — reused answers
  — on a tty.

So the test spawns the CLI under a pty. It is deliberately NOT `INTEGRATION`-gated: CI
runs the default suite only, and gating this would leave the human path unverified in
exactly the release where it breaks.

One driver detail is load-bearing. An earlier version wrote `\\n` on every select
timeout; the spare newlines sat in the tty buffer and were consumed by the NEXT prompt,
so an explicit `n` produced `enabled: true` and looked like a product bug. The driver
below writes ONLY in response to a detected prompt, exactly once.
"""

from __future__ import annotations

import os
import pty
import re
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="pty is POSIX-only")

_REPO = Path(__file__).resolve().parents[2]
# "…? [Y/n] " or "…: " — the two shapes `_input_or_empty` produces.
_PROMPT = re.compile(rb"(\[[^\]\n]*\]\s*|:\s*)$")
_MIGRATION_PROMPT = b"Keep isolation?"


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _legacy_scope_only_harness(tmp_path: Path) -> Path:
    """The one shape ADR-006 calls genuinely lossy: `scope` with no explicit flag.

    The old axis expressed *execute-only* isolation here; the new boolean cannot, so
    this is the case that must ASK rather than guess.
    """
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@e.com"], root)
    _git(["config", "user.name", "T"], root)
    (root / "README.md").write_text("x\n", encoding="utf-8")
    (root / ".claude" / "harness.yaml").write_text(
        "preset: Side\ndev_mode: task-driven\n"
        "worktree:\n  scope: [execute]\n  branch_prefix: hm-\n",
        encoding="utf-8",
    )
    _git(["add", "-A"], root)
    _git(["commit", "-m", "init"], root)
    return root


def _run_under_pty(target: Path, *, migration_answer: bytes, budget_s: float = 120.0) -> str:
    """Drive `make <target>` on a pty, answering the migration prompt once.

    Every other prompt takes its default (a bare newline). Returns the transcript.
    """
    master, slave = pty.openpty()
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "harness_maker.cli", "make", str(target)],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=str(_REPO),
        close_fds=True,
    )
    os.close(slave)
    pending, chunks = b"", []
    deadline = time.time() + budget_s
    try:
        while time.time() < deadline and proc.poll() is None:
            readable, _, _ = select.select([master], [], [], 1.0)
            if not readable:
                # Deliberately no write here — see the module docstring.
                continue
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            pending += chunk
            if _PROMPT.search(pending.replace(b"\r", b"")):
                reply = migration_answer if _MIGRATION_PROMPT in pending else b""
                os.write(master, reply + b"\n")
                pending = b""
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            proc.kill()
            pytest.fail("make did not exit under the pty within budget")
    finally:
        os.close(master)
    assert proc.returncode == 0, b"".join(chunks).decode("utf-8", "replace")[-2000:]
    return b"".join(chunks).decode("utf-8", "replace")


def _enabled(root: Path) -> object:
    from harness_maker.io_utils import load_harness_yaml

    block = load_harness_yaml(root / ".claude" / "harness.yaml").get("worktree")
    assert isinstance(block, dict), block
    return block.get("enabled")


@pytest.mark.parametrize(
    ("answer", "expected"),
    [(b"", True), (b"y", True), (b"n", False)],
    ids=["enter-keeps-isolation", "yes", "no"],
)
def test_the_migration_prompt_fires_and_honours_the_answer(
    tmp_path: Path, answer: bytes, expected: bool
) -> None:
    """Enter must PRESERVE. A migration that changes behavior when the operator just
    presses through is the failure this default exists to avoid."""
    root = _legacy_scope_only_harness(tmp_path)
    transcript = _run_under_pty(root, migration_answer=answer)
    assert "Keep isolation?" in transcript, (
        "the interactive migration prompt never fired — it is reachable only from a "
        "plain `make <dir>` on a tty, not from --reinterview and not from a pipe"
    )
    assert "retired `worktree.scope` key" in transcript
    assert _enabled(root) is expected


def test_the_prompt_defaults_to_the_current_isolation_state(tmp_path: Path) -> None:
    """`[Y/n]` — capital Y — because this fixture's legacy `scope: [execute]` means
    isolation is currently ON. The bracket hint is the only signal an operator gets
    about which way Enter goes, so it must track the live state rather than be a
    constant."""
    root = _legacy_scope_only_harness(tmp_path)
    transcript = _run_under_pty(root, migration_answer=b"")
    assert "isolation is on for /hm:execute only" in transcript
    assert "Keep isolation? [Y/n]" in transcript
