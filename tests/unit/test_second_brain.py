"""Tests for the Obsidian Second Brain filesystem backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from harness_maker.models import SecondBrainConfig, SecondBrainFolder, SecondBrainNoteType
from harness_maker.second_brain import (
    SecondBrainError,
    append_note,
    parse_frontmatter,
    patch_note,
    read_note,
    search_notes,
    validate_note,
    write_note,
)


def _harness_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".claude").mkdir(parents=True)
    return root


def _write_harness_yaml(root: Path, cfg: SecondBrainConfig) -> None:
    payload = {
        "preset": "Side",
        "second_brain": cfg.model_dump(mode="json"),
    }
    (root / ".claude" / "harness.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


def _enabled_config(root: Path) -> SecondBrainConfig:
    vault = root.parent / "vault"
    return SecondBrainConfig(
        enabled=True,
        project_id="harness-maker",
        vault_path=str(vault),
        folders=[
            SecondBrainFolder(
                path="Projects/harness-maker",
                read=True,
                write=True,
                note_types=[
                    SecondBrainNoteType.DECISION,
                    SecondBrainNoteType.FAILURE,
                    SecondBrainNoteType.JOURNAL,
                ],
            )
        ],
    )


def _frontmatter(note_type: str = "decision") -> dict[str, object]:
    return {
        "type": note_type,
        "created": "2026-05-11",
        "updated": "2026-05-11",
        "tags": ["hm/second-brain", f"hm/type/{note_type}"],
        "links": ["[[Project Harness Maker]]"],
    }


def test_parse_frontmatter_extracts_body_and_metadata() -> None:
    text = "---\ntype: decision\ntags: [hm/second-brain]\n---\n# Title\nBody"
    fm, body = parse_frontmatter(text)
    assert fm["type"] == "decision"
    assert fm["tags"] == ["hm/second-brain"]
    assert body == "# Title\nBody"


def test_validate_note_requires_core_frontmatter() -> None:
    with pytest.raises(SecondBrainError, match="missing required frontmatter"):
        validate_note({"type": "decision"}, "Body")


def test_validate_note_warns_for_missing_recommended_fields() -> None:
    warnings = validate_note(_frontmatter("failure"), "Body")
    assert any("recommended frontmatter missing" in w for w in warnings)


def test_validate_note_rejects_unknown_type() -> None:
    fm = _frontmatter("unknown")
    with pytest.raises(SecondBrainError, match="unknown note type"):
        validate_note(fm, "Body")


def test_write_and_read_note_inside_allowlist(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    cfg = _enabled_config(root)
    _write_harness_yaml(root, cfg)
    result = write_note(
        root,
        "Projects/harness-maker/Decisions/Second Brain.md",
        _frontmatter("decision"),
        "# Second Brain\nLinks to [[Project Harness Maker]].\n",
    )
    assert result.path.is_file()
    assert "recommended frontmatter missing" in "\n".join(result.warnings)
    text = read_note(root, "Projects/harness-maker/Decisions/Second Brain.md")
    assert "type: decision" in text
    assert "[[Project Harness Maker]]" in text


def test_write_note_rejects_outside_allowlist(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    with pytest.raises(SecondBrainError, match="not under a configured write folder"):
        write_note(root, "Private/secret.md", _frontmatter("decision"), "Body")


def test_write_note_rejects_path_traversal(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    with pytest.raises(SecondBrainError, match="not under a configured write folder"):
        write_note(root, "Projects/harness-maker/../../outside.md", _frontmatter(), "Body")


def test_write_note_rejects_non_markdown(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    with pytest.raises(SecondBrainError, match="Markdown files"):
        write_note(root, "Projects/harness-maker/data.json", _frontmatter(), "{}")


def test_write_note_rejects_disallowed_note_type(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    vault = root.parent / "vault"
    cfg = SecondBrainConfig(
        enabled=True,
        project_id="harness-maker",
        vault_path=str(vault),
        folders=[
            SecondBrainFolder(
                path="Projects/harness-maker",
                read=True,
                write=True,
                note_types=[SecondBrainNoteType.DECISION],
            )
        ],
    )
    _write_harness_yaml(root, cfg)
    with pytest.raises(SecondBrainError, match="not allowed in folder"):
        write_note(root, "Projects/harness-maker/Failures/fail.md", _frontmatter("failure"), "Body")


def test_append_and_exact_patch_note(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    rel = "Projects/harness-maker/Journal/today.md"
    write_note(root, rel, _frontmatter("journal"), "# Today\n")
    append_note(root, rel, "\n- Worked on [[Second Brain]].\n")
    patch_note(root, rel, "Worked on", "Implemented")
    text = read_note(root, rel)
    assert "Implemented [[Second Brain]]" in text


def test_patch_note_requires_existing_text(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    rel = "Projects/harness-maker/Journal/today.md"
    write_note(root, rel, _frontmatter("journal"), "# Today\n")
    with pytest.raises(SecondBrainError, match="old text not found"):
        patch_note(root, rel, "missing", "new")


def test_search_notes_filters_by_type_and_tag(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    write_note(
        root,
        "Projects/harness-maker/Decisions/Second Brain.md",
        _frontmatter("decision"),
        "# Second Brain\nUse [[Project Harness Maker]].\n",
    )
    write_note(
        root,
        "Projects/harness-maker/Failures/Bad Path.md",
        _frontmatter("failure"),
        "# Bad Path\nPath traversal failed.\n",
    )
    results = search_notes(root, "Second Brain", note_type="decision", tag="hm/type/decision")
    assert [r.relpath for r in results] == ["Projects/harness-maker/Decisions/Second Brain.md"]
    assert results[0].links == ["[[Project Harness Maker]]"]


def test_search_notes_skips_folder_disallowed_note_type(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    vault = root.parent / "vault"
    cfg = SecondBrainConfig(
        enabled=True,
        project_id="harness-maker",
        vault_path=str(vault),
        folders=[
            SecondBrainFolder(
                path="Projects/harness-maker",
                read=True,
                write=True,
                note_types=[SecondBrainNoteType.DECISION],
            )
        ],
    )
    _write_harness_yaml(root, cfg)
    note = vault / "Projects" / "harness-maker" / "Failures" / "fail.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntype: failure\ncreated: 2026-05-11\nupdated: 2026-05-11\n"
        "tags: [hm/second-brain, hm/type/failure]\nlinks: []\n---\n# Failure\n",
        encoding="utf-8",
    )
    assert search_notes(root, "Failure") == []


def test_validate_note_warns_for_missing_harness_tags() -> None:
    fm = _frontmatter("decision")
    fm["tags"] = ["custom"]
    warnings = validate_note(fm, "Body [[Project]]")
    assert any("hm/second-brain" in w for w in warnings)


def test_write_note_warns_when_project_namespace_missing(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    fm = _frontmatter("decision")
    result = write_note(root, "Projects/harness-maker/Decisions/no-project.md", fm, "Body")
    assert any("project namespace missing" in w for w in result.warnings)


def test_write_note_accepts_matching_project_namespace(tmp_path: Path) -> None:
    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    fm = _frontmatter("decision")
    fm["project_id"] = "harness-maker"
    result = write_note(root, "Projects/harness-maker/Decisions/project.md", fm, "Body")
    assert not any("project namespace missing" in w for w in result.warnings)


def test_cli_write_and_read(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from harness_maker.second_brain import _cli

    root = _harness_root(tmp_path)
    _write_harness_yaml(root, _enabled_config(root))
    body = tmp_path / "body.md"
    body.write_text("# CLI\n", encoding="utf-8")
    code = _cli(
        [
            "--root",
            str(root),
            "write",
            "Projects/harness-maker/Decisions/CLI.md",
            "--frontmatter-json",
            json.dumps(_frontmatter("decision")),
            "--body-file",
            str(body),
        ]
    )
    assert code == 0
    code = _cli(["--root", str(root), "read", "Projects/harness-maker/Decisions/CLI.md"])
    assert code == 0
    assert "# CLI" in capsys.readouterr().out
