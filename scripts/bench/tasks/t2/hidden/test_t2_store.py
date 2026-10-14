"""Hidden tests for t2: atomic timeparse/store.py."""

import json
import os
from pathlib import Path

import pytest
from timeparse import store


def _files(directory: Path) -> set[str]:
    return {p.name for p in directory.iterdir()}


def test_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    store.save_durations(target, {"tea": "3m", "lunch": "1h"})
    assert store.load_durations(target) == {"tea": 180, "lunch": 3600}
    assert json.loads(target.read_text()) == {"tea": 180, "lunch": 3600}


def test_accepts_str_path(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    store.save_durations(str(target), {"a": "1s"})
    assert store.load_durations(str(target)) == {"a": 1}


def test_values_are_ints(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    store.save_durations(target, {"a": "1d1s"})
    loaded = store.load_durations(target)
    assert loaded == {"a": 86401}
    assert all(type(v) is int for v in loaded.values())


def test_missing_file_loads_empty(tmp_path: Path) -> None:
    assert store.load_durations(tmp_path / "absent.json") == {}


def test_empty_mapping(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    store.save_durations(target, {})
    assert store.load_durations(target) == {}


def test_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    store.save_durations(target, {"a": "1m"})
    store.save_durations(target, {"b": "2m"})
    assert store.load_durations(target) == {"b": 120}


def test_non_dict_is_type_error(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        store.save_durations(tmp_path / "d.json", [("a", "1m")])  # type: ignore[arg-type]


def test_invalid_value_leaves_file_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    store.save_durations(target, {"a": "1m"})
    before = target.read_bytes()
    with pytest.raises(ValueError, match="bad"):
        store.save_durations(target, {"ok": "2m", "bad": "nope"})
    assert target.read_bytes() == before
    assert _files(tmp_path) == {"d.json"}


def test_invalid_value_creates_nothing(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    with pytest.raises(ValueError):
        store.save_durations(target, {"bad": "1x"})
    assert _files(tmp_path) == set()


@pytest.fixture
def broken_replace(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    monkeypatch.setattr(os, "rename", boom)


@pytest.mark.usefixtures("broken_replace")
def test_failed_replace_keeps_original(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    target.write_text('{"a": 60}')
    with pytest.raises(OSError):
        store.save_durations(target, {"b": "2m"})
    assert target.read_text() == '{"a": 60}'
    assert _files(tmp_path) == {"d.json"}


@pytest.mark.usefixtures("broken_replace")
def test_failed_replace_without_original_leaves_nothing(tmp_path: Path) -> None:
    target = tmp_path / "d.json"
    with pytest.raises(OSError):
        store.save_durations(target, {"b": "2m"})
    assert _files(tmp_path) == set()


def test_existing_cli_unaffected() -> None:
    from timeparse.cli import main

    assert main(["1m"]) == 0
