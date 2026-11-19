"""SPEC-stale-install-recovery AC-007: auto-tag decides from the four version files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker.documentation_contract import VERSION_FILES
from harness_maker.release_autotag import decide, main

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = json.loads((ROOT / "specs/SPEC-stale-install-recovery.golden.json").read_text("utf-8"))


@pytest.mark.parametrize(
    "row", GOLDEN["AC-007"], ids=[f"AC-007-{i}" for i in range(len(GOLDEN["AC-007"]))]
)
def test_ac_007_autotag_decision(row: dict[str, Any]) -> None:
    inp = row["input"]
    versions = dict(zip(VERSION_FILES, inp["versions"], strict=True))
    got = decide(versions, changed_in_push=inp["changed_in_push"], tag_exists=inp["tag_exists"])
    assert got == row["expected"]


# ── review round 1 (F2/F3/F10): main() against a real git history ───────────────


def _write(root: Path, manifest: str, rest: str) -> None:
    for rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        v = manifest if rel.startswith(".claude") else rest
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(json.dumps({"name": "harness-maker", "version": v}))
    (root / "pyproject.toml").write_text(f'[project]\nname = "harness-maker"\nversion = "{rest}"\n')
    (root / "src/harness_maker").mkdir(parents=True, exist_ok=True)
    (root / "src/harness_maker/__init__.py").write_text(f'__version__ = "{rest}"\n')


def _commit(root: Path, msg: str) -> str:
    def run(*a: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

    run("add", "-A")
    run("commit", "-q", "-m", msg)
    return run("rev-parse", "HEAD").stdout.strip()


def _decision(
    root: Path, before: str, monkeypatch: pytest.MonkeyPatch, tmp: Path
) -> tuple[int, str]:
    out = tmp / "gh_output"
    out.write_text("")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    rc = main(["--root", str(root), "--before", before])
    return rc, out.read_text()


def test_partial_bump_then_completion_tags_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, timeout=30)
    _write(root, "0.1.0", "0.1.0")
    c1 = _commit(root, "c1")
    _write(root, "0.2.0", "0.1.0")  # PR1 bumps only the manifest
    c2 = _commit(root, "c2")
    assert _decision(root, c1, monkeypatch, tmp_path) == (1, "")
    _write(root, "0.2.0", "0.2.0")  # PR2 completes the bump
    _commit(root, "c3")
    assert _decision(root, c2, monkeypatch, tmp_path) == (0, "tag=v0.2.0\n")
    assert _decision(root, "0" * 40, monkeypatch, tmp_path) == (0, "")
    subprocess.run(["git", "tag", "v0.2.0"], cwd=root, check=True, timeout=30)
    assert _decision(root, c2, monkeypatch, tmp_path) == (0, "")
    capsys.readouterr()
