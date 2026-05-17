"""Unit tests for harness_maker.io_utils."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from harness_maker.io_utils import atomic_write, denormalize_home_to_tilde, load_harness_yaml


def test_atomic_write_str_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    atomic_write(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_atomic_write_bytes_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    atomic_write(target, b"\x00\x01\x02hello")
    assert target.read_bytes() == b"\x00\x01\x02hello"


def test_atomic_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "out.txt"
    atomic_write(target, "ok")
    assert target.read_text(encoding="utf-8") == "ok"


def test_atomic_write_cleans_up_tempfile_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: tempfile must not leak when os.replace raises (WSL2/NTFS EXDEV)."""
    target = tmp_path / "out.txt"

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated EXDEV")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError, match="simulated EXDEV"):
        atomic_write(target, "hello")

    # NamedTemporaryFile defaults yield names starting with "tmp" inside tmp_path.
    # After the failed replace + cleanup, no tempfile entries should remain there,
    # and the target itself must not exist.
    leftovers = [p for p in tmp_path.iterdir() if p.is_file()]
    assert leftovers == [], f"orphaned tempfiles after replace failure: {leftovers}"
    assert not target.exists()


def test_atomic_write_bytes_cleans_up_tempfile_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: bytes path must also clean up tempfile on os.replace failure."""
    target = tmp_path / "out.bin"

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated EXDEV")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError, match="simulated EXDEV"):
        atomic_write(target, b"payload")

    leftovers = [p for p in tmp_path.iterdir() if p.is_file()]
    assert leftovers == [], f"orphaned tempfiles after replace failure: {leftovers}"
    assert not target.exists()


def test_denormalize_home_to_tilde_exact_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/alice")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/alice"))
    assert denormalize_home_to_tilde("/home/alice") == "~"


def test_denormalize_home_to_tilde_under_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/alice")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/alice"))
    assert denormalize_home_to_tilde("/home/alice/projects/x") == "~/projects/x"


def test_denormalize_home_to_tilde_outside_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/alice")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/alice"))
    assert denormalize_home_to_tilde("/etc/passwd") == "/etc/passwd"


# ---------------------------------------------------------------------------
# load_harness_yaml — provenance-frontmatter-aware loader
# ---------------------------------------------------------------------------


def _provenance_frontmatter() -> str:
    """Frontmatter shape injected by render.py for harness.yaml."""
    return (
        "---\n"
        "generated_by: harness-maker\n"
        "harness_maker_version: 0.13.0\n"
        "generated_at: '2026-01-01T00:00:00+00:00'\n"
        "source_template: harness-yaml/Production.yaml.j2\n"
        "provenance: official\n"
        "content_hash: 384fc6d5a53752ffef038282975540251278615efdf76059ac7a75f668eee136\n"
        "---\n"
    )


def test_load_harness_yaml_returns_body_when_frontmatter_present(tmp_path: Path) -> None:
    """The renderer injects a provenance frontmatter block; loader returns the body doc.

    Why: production harness.yaml always has frontmatter (render._format_frontmatter).
    Single-document yaml.safe_load rejects multi-doc streams — this is the exact bug
    being fixed for the Second Brain loader.
    """
    yaml_path = tmp_path / "harness.yaml"
    body = "preset: Production\nlocale: ko\nsecond_brain:\n  enabled: true\n"
    yaml_path.write_text(_provenance_frontmatter() + body, encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data["preset"] == "Production"
    assert data["locale"] == "ko"
    assert data["second_brain"]["enabled"] is True
    # Must NOT return the frontmatter doc — that contains generated_by/content_hash.
    assert "generated_by" not in data
    assert "content_hash" not in data


def test_load_harness_yaml_handles_bare_file_without_frontmatter(tmp_path: Path) -> None:
    """Hand-written or pre-render harness.yaml has no frontmatter; loader still works."""
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text("preset: Side\nlocale: en\n", encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data == {"preset": "Side", "locale": "en"}


def test_load_harness_yaml_returns_empty_dict_for_empty_file(tmp_path: Path) -> None:
    """An empty harness.yaml returns {} rather than None — callers expect dict.get()."""
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text("", encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data == {}


def test_load_harness_yaml_returns_last_nonempty_document(tmp_path: Path) -> None:
    """Multi-doc YAML: last non-empty doc is the canonical user-data block.

    Why: render.py prepends provenance frontmatter as the FIRST doc; the user
    body is the LAST doc. The loader must pick the last so user data wins.
    """
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text(
        "---\nfirst: 1\n---\nsecond: 2\n---\nthird: 3\n",
        encoding="utf-8",
    )

    data = load_harness_yaml(yaml_path)

    assert data == {"third": 3}


def test_load_harness_yaml_raises_for_missing_file(tmp_path: Path) -> None:
    """Missing file → FileNotFoundError (caller decides how to surface)."""
    with pytest.raises(FileNotFoundError):
        load_harness_yaml(tmp_path / "does-not-exist.yaml")


def test_load_harness_yaml_raises_for_malformed_yaml(tmp_path: Path) -> None:
    """Genuinely malformed YAML surfaces yaml.YAMLError to the caller."""
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text("preset: [unclosed\n  bracket\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        load_harness_yaml(yaml_path)


def test_load_harness_yaml_returns_empty_dict_for_top_level_sequence(
    tmp_path: Path,
) -> None:
    """Top-level sequence is invalid for harness.yaml → empty dict fallback.

    Why: harness.yaml is by contract a mapping; surfacing a list would crash
    callers deeper than necessary. Empty-dict gives a clean validation point.
    """
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text("- one\n- two\n", encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data == {}


def test_load_harness_yaml_skips_provenance_only_truncated_write(
    tmp_path: Path,
) -> None:
    """A file containing ONLY provenance (truncated write) returns {} not provenance.

    Regression: REVIEW-2026-05-17 P1 — earlier loader returned the provenance
    block as user data when the body had not yet been flushed (WSL2/NTFS
    partial-write scenario named in CLAUDE.md §실행 주의).
    """
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text(_provenance_frontmatter(), encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data == {}
    assert "generated_by" not in data
    assert "content_hash" not in data
