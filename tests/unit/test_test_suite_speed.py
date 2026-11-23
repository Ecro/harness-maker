"""SPEC-test-suite-speed AC-001..003 — faster local suite, same assertions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path, PurePath

import pytest

from tests.unit import test_memory_tier_removed as tier

REPO = Path(__file__).resolve().parents[2]
GOLDEN = json.loads(
    (REPO / "specs" / "SPEC-test-suite-speed.golden.json").read_text(encoding="utf-8")
)

_SEEDED_A = """from harness_maker.memory.episodic import X
from harness_maker.memory import semantic
from harness_maker.memory import EpisodicStore, _locking
from harness_maker.memory import _locking as lk
import harness_maker.memory.profile
import harness_maker.memory
s = "EpisodicStore"
# EpisodicStore in a comment
x = SemanticStore()
y = mod.MemoryRetriever
z = SemanticStore.MemoryRetriever
"""
_SEEDED_B = "def f():\n    return ProfileStore\n"


@pytest.fixture
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "pkg" / "a.py").write_text(_SEEDED_A, encoding="utf-8")
    (tmp_path / "tests" / "b.py").write_text(_SEEDED_B, encoding="utf-8")
    (tmp_path / "tests" / "excluded.py").write_text(_SEEDED_A, encoding="utf-8")
    monkeypatch.setattr(tier, "REPO", tmp_path)
    return tmp_path


def _uses(root: Path) -> list[str]:
    return tier.ast_uses(tier.REMOVED_NAMES, exclude=(root / "tests" / "excluded.py").resolve())


@pytest.mark.parametrize(
    "row", GOLDEN["AC-001"], ids=lambda r: f"AC-001-{json.dumps(r['input'], sort_keys=True)}"
)
def test_ac_001_ast_uses_golden(seeded: Path, row: dict[str, object]) -> None:
    assert sorted(_uses(seeded)) == row["expected"]


def test_ac_002_location_formatted_only_on_hit(
    seeded: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = PurePath.relative_to
    calls = 0

    def counting(self: PurePath, other: str | os.PathLike[str]) -> PurePath:
        nonlocal calls
        if str(self).startswith(str(seeded)):
            calls += 1
        return real(self, other)

    monkeypatch.setattr(PurePath, "relative_to", counting)
    hits = _uses(seeded)
    monkeypatch.undo()
    assert calls == len(hits), (calls, len(hits))


_FAKE_CLAUDE = """#!{python}
import os, sys
from pathlib import Path

prompt = sys.argv[sys.argv.index("-p") + 1]
args = dict(p.split("=", 1) for p in prompt.split() if "=" in p)
with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as log:
    log.write(prompt + "\\n")
claude = Path.cwd() / ".claude"
claude.mkdir(exist_ok=True)
(claude / "harness.yaml").write_text(
    "---\\ngenerated_by: fake\\n---\\npreset: " + args["preset"] + "\\n", encoding="utf-8"
)
for i in range(30):
    (claude / f"f{{i}}.md").write_text("x", encoding="utf-8")
"""


def test_ac_003_live_make_runs_once_per_args(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(_FAKE_CLAUDE.format(python=sys.executable), encoding="utf-8")
    fake.chmod(0o755)
    log = tmp_path / "launches.log"
    log.touch()
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["FAKE_CLAUDE_LOG"] = str(log)
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/e2e/test_plugin_live.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    rc = cp.returncode
    launches = len(log.read_text(encoding="utf-8").splitlines())
    detail = (rc, launches, cp.stdout[-1500:], cp.stderr[-800:])
    assert rc == 0, detail
    assert launches == 2, detail
