"""End-to-end acceptance for the onboarding paths (PLAN-onboarding-interview-ux Phase 7).

Every arm below drives the REAL CLI against a REAL temporary project and reads the resulting
`harness.yaml`. That boundary is the point: the unit tests prove the flag parsers work and
the render tests prove the prose says the right thing, but neither proves that answering the
fresh-install question actually lands the axis in the file the harness reads afterwards.

Scenarios 1-3 (does an LLM ask exactly one question when a CLI is detected, and none when it
is not) cannot be settled here — they are the model executing prose. `tests/manual/
ONBOARDING_ACCEPTANCE.md` owns those, and this file's docstring is the pointer to it.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness_maker.cli import app
from harness_maker.io_utils import load_harness_yaml

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='p'\nversion='0'\n", encoding="utf-8")
    return root


def _make(root: Path, *flags: str) -> None:
    result = runner.invoke(app, ["make", str(root), "--autoloop", *flags])
    assert result.exit_code == 0, result.output


def _config(root: Path) -> dict[str, object]:
    return load_harness_yaml(root / ".claude" / "harness.yaml")


def _fake_which(present: set[str]) -> object:
    def _which(cmd: str) -> str | None:
        return f"/usr/bin/{cmd}" if cmd in present else None

    return _which


# ── Scenario 6 — detect-tools degrades rather than gating ──────────────────────


def test_detect_tools_reports_absence_rather_than_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing installed is a normal answer, not an error.

    If this ever exits non-zero, the fresh-install flow acquires a failure mode in the one
    place a first-time user is least equipped to diagnose.
    """
    monkeypatch.setattr(shutil, "which", _fake_which(set()))
    result = runner.invoke(app, ["detect-tools", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert all(v == {"installed": False} for v in payload.values()), payload


# ── Scenario 2/3 — the answer reaches harness.yaml ────────────────────────────


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("codex", ["codex"]),
        ("antigravity", ["antigravity"]),
        ("codex,antigravity", ["codex", "antigravity"]),
    ],
    ids=["codex-only", "agy-only", "both"],
)
def test_the_fresh_install_answer_lands_in_harness_yaml(
    tmp_path: Path, answer: str, expected: list[str]
) -> None:
    root = _project(tmp_path)
    _make(root, "--second-opinion-models", answer)
    assert _config(root)["second_opinion"]["models"] == expected  # type: ignore[index]


def test_declining_leaves_the_axis_off(tmp_path: Path) -> None:
    """The decline branch must produce an empty list, not a partially-configured block."""
    root = _project(tmp_path)
    _make(root)
    assert _config(root)["second_opinion"]["models"] == []  # type: ignore[index]


# ── Scenario 4 — /hm:configure's flags round-trip ─────────────────────────────


def test_configure_can_enable_then_disable_the_second_opinion(tmp_path: Path) -> None:
    """The recovery path, exercised as the CLI call `/hm:configure` dispatches.

    Disabling is the half most likely to rot: an empty string must CLEAR rather than be
    read as "unspecified, preserve".
    """
    root = _project(tmp_path)
    _make(root)
    _make(root, "--second-opinion-models", "codex")
    assert _config(root)["second_opinion"]["models"] == ["codex"]  # type: ignore[index]

    _make(root, "--second-opinion-models", "")
    assert _config(root)["second_opinion"]["models"] == []  # type: ignore[index]


def test_omitting_the_flag_preserves_the_current_value(tmp_path: Path) -> None:
    """The other half of the same boundary — a neighbouring edit must not clobber it."""
    root = _project(tmp_path)
    _make(root, "--second-opinion-models", "codex")
    _make(root, "--locale", "ko")
    cfg = _config(root)
    assert cfg["second_opinion"]["models"] == ["codex"]  # type: ignore[index]
    assert cfg["locale"] == "ko"


def test_configure_can_change_autonomy_and_locale(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _make(root)
    _make(root, "--autonomy-level", "auto_safe", "--locale", "ko")
    cfg = _config(root)
    assert cfg["autonomy"]["level"] == "auto_safe"  # type: ignore[index]
    assert cfg["locale"] == "ko"


def test_per_model_sub_blocks_survive_a_models_list_change(tmp_path: Path) -> None:
    """ADR-002's per-model config must not be collateral damage of toggling the list."""
    root = _project(tmp_path)
    _make(root, "--second-opinion-models", "codex,antigravity")
    before = _config(root)["second_opinion"]
    _make(root, "--second-opinion-models", "codex")
    after = _config(root)["second_opinion"]
    assert isinstance(after, dict)
    assert isinstance(before, dict)
    assert after["codex"] == before["codex"]
    assert after["antigravity"] == before["antigravity"]
