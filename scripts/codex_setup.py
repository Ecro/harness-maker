"""Resolve the bootstrap from this installed package, independent of cwd."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from harness_maker.codex_setup import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(_ROOT))
