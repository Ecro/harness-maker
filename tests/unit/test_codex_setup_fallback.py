"""SPEC-stale-install-recovery AC-005/006: Codex bootstrap falls back to the plugin source."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker.codex_setup import setup

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = json.loads((ROOT / "specs/SPEC-stale-install-recovery.golden.json").read_text("utf-8"))
VERSION = "0.58.0"

# Captured live on 2026-11-19 from `uv run --with harness-maker==0.65.6 …` (version swapped).
UV_UNRESOLVABLE = (
    "  × No solution found when resolving `--with` dependencies:\n"
    f"  ╰─▶ Because there is no version of harness-maker=={VERSION} and you require "
    f"harness-maker=={VERSION}, we can conclude that your requirements are unsatisfiable.\n"
)


def _plugin(root: Path, *, pyproject: bool) -> Path:
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "harness-maker", "version": VERSION})
    )
    if pyproject:
        (root / "pyproject.toml").write_text("[project]\nname = 'harness-maker'\n")
    return root


class Engine:
    """Fake runner: only the engine launch is exercised (action `make`)."""

    def __init__(self, *, pypi: bool, engine_error: bool = False, fallback_fails: bool = False):
        self.pypi = pypi
        self.engine_error = engine_error
        self.fallback_fails = fallback_fails
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        ref = argv[argv.index("--with") + 1]
        pinned = ref.startswith("harness-maker==")
        if (pinned and not self.pypi) or (not pinned and self.fallback_fails):
            return subprocess.CompletedProcess(argv, 1, "", UV_UNRESOLVABLE)
        receipt: dict[str, Any] = {"engine": VERSION, "project": VERSION, "codex_assets": True}
        if self.engine_error:
            receipt["error"] = "engine_mismatch"
            return subprocess.CompletedProcess(argv, 1, json.dumps(receipt), "")
        return subprocess.CompletedProcess(argv, 0, json.dumps(receipt), "")


@pytest.mark.parametrize(
    "row", GOLDEN["AC-005"], ids=[f"AC-005-{i}" for i in range(len(GOLDEN["AC-005"]))]
)
def test_ac_005_fallback_to_plugin_root(row: dict[str, Any], tmp_path: Path) -> None:
    inp, exp = row["input"], row["expected"]
    plugin_root = _plugin(tmp_path / "plugin", pyproject=inp.get("plugin_pyproject", True))
    engine = Engine(
        pypi=inp["pypi_resolves"],
        engine_error=inp.get("engine_error", False),
        fallback_fails=inp.get("fallback_fails", False),
    )
    result = setup("make", tmp_path / "proj", plugin_root=plugin_root, runner=engine)
    assert len(engine.calls) == exp["runs"]
    if "engine_source" in exp:
        assert result["engine_source"] == exp["engine_source"]
    if exp.get("engine_source") == "plugin_root":
        assert engine.calls[-1][engine.calls[-1].index("--with") + 1] == str(plugin_root)
    if "state_not" in exp:
        assert result["state"] != exp["state_not"]
    else:
        assert result["state"] == "complete"


@pytest.mark.parametrize(
    "row", GOLDEN["AC-006"], ids=[f"AC-006-{i}" for i in range(len(GOLDEN["AC-006"]))]
)
def test_ac_006_make_honours_update(row: dict[str, Any], tmp_path: Path) -> None:
    inp = row["input"]
    plugin_root = _plugin(tmp_path / "plugin", pyproject=True)
    engine = Engine(pypi=True)
    setup(
        inp["action"],
        tmp_path / "proj",
        plugin_root=plugin_root,
        runner=engine,
        update=inp["update"],
    )
    has = "--update" in engine.calls[-1]
    assert has is (row["expected"] == "engine_argv_has_update")


def test_ac_006_cli_flag_and_skill_doc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from harness_maker import codex_setup

    seen: dict[str, Any] = {}

    def fake_setup(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {"state": "complete"}

    monkeypatch.setattr(codex_setup, "setup", fake_setup)
    monkeypatch.setattr("sys.argv", ["codex_setup.py", "make", str(tmp_path), "--update"])
    assert codex_setup.main(tmp_path) == 0
    assert seen["update"] is True
    skill = (ROOT / "skills/hm-make/SKILL.md").read_text("utf-8")
    assert "--update" in skill


def test_engine_crash_without_receipt_is_not_retried(tmp_path: Path) -> None:
    """Review F4: a traceback means the engine ran; only a uv-level failure falls back."""
    plugin_root = _plugin(tmp_path / "plugin", pyproject=True)
    calls: list[list[str]] = []

    def crash(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        tb = 'Traceback (most recent call last):\n  File "codex_engine.py"\nKeyError: x\n'
        return subprocess.CompletedProcess(argv, 1, "", tb)

    result = setup("make", tmp_path / "proj", plugin_root=plugin_root, runner=crash)
    assert len(calls) == 1
    assert result["state"] != "complete"
