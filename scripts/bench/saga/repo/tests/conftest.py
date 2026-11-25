from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def save_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "reminders.json"
    monkeypatch.setenv("REMIND_FILE", str(path))
    monkeypatch.chdir(tmp_path)
    return path
