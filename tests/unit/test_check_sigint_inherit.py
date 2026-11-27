"""SPEC-spec-owner-boundary AC-003: a gate command gets SIGINT back even when hm check lost it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

#: Started with SIGINT set to `sys.argv[2]` (a background job of a non-interactive shell starts
#: with it ignored), call `check._run` on a child that reports its own SIGINT handler.
_DRIVER = """
import os, signal, sys
from pathlib import Path
start = signal.SIG_IGN if sys.argv[2] == "ignore" else signal.SIG_DFL
signal.signal(signal.SIGINT, start)
from harness_maker import check
probe = "import signal; print(signal.getsignal(signal.SIGINT) is signal.default_int_handler)"
code, out = check._run([sys.executable, "-c", probe], Path(sys.argv[1]), dict(os.environ))
print(code, out.strip(), signal.getsignal(signal.SIGINT) is start)
"""


@pytest.mark.parametrize("start", ["ignore", "default"])
def test_ac_003_gate_child_has_default_sigint(tmp_path: Path, start: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(tmp_path), start],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    # child exit 0, child has Python's KeyboardInterrupt handler, hm check's own is untouched
    assert proc.stdout.split() == ["0", "True", "True"]
