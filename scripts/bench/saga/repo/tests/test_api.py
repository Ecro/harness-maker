from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from remind import api


def test_add_and_upcoming(save_file: Path) -> None:
    later = api.add("later", datetime(2026, 1, 9, 9, 0, tzinfo=UTC))
    sooner = api.add("sooner", datetime(2026, 1, 5, 9, 0, tzinfo=UTC))
    assert [ident for _due, _text, ident in api.upcoming()] == [sooner.id, later.id]


def test_done_hides_reminder(save_file: Path) -> None:
    reminder = api.add("x", datetime(2026, 1, 5, 9, 0, tzinfo=UTC))
    api.done(reminder.id)
    assert api.upcoming() == []


def test_empty_text_rejected(save_file: Path) -> None:
    with pytest.raises(ValueError):
        api.add("  ", datetime(2026, 1, 5, 9, 0, tzinfo=UTC))
