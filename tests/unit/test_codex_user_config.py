"""Tests for codex_user_config.bootstrap_user_codex_profiles."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.codex_user_config import bootstrap_user_codex_profiles


def test_fresh_install_creates_file_with_both_profiles(tmp_path: Path) -> None:
    """No prior ~/.codex/config.toml → file created with cheap + deep blocks
    and an ADR-008 header explaining why they live at user level."""
    result = bootstrap_user_codex_profiles(home=tmp_path)
    assert result.changed
    assert result.installed == ["cheap", "deep"]
    body = result.path.read_text(encoding="utf-8")
    assert "[profiles.cheap]" in body
    assert "[profiles.deep]" in body
    assert 'model_reasoning_effort = "minimal"' in body
    assert 'model_reasoning_effort = "high"' in body
    assert "ADR-008" in body


def test_idempotent_when_both_already_present(tmp_path: Path) -> None:
    """File already has both blocks → no-op, no write, empty `installed`.

    Critical: re-running `harness-maker make` MUST NOT keep appending
    duplicate blocks each time (the user would end up with a polluted
    config and Codex would error on duplicate-key parse).
    """
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    pre = (
        "# user's own header\n"
        "[profiles.cheap]\n"
        'model_reasoning_effort = "minimal"\n'
        "\n"
        "[profiles.deep]\n"
        'model_reasoning_effort = "high"\n'
    )
    cfg.write_text(pre, encoding="utf-8")
    result = bootstrap_user_codex_profiles(home=tmp_path)
    assert not result.changed
    assert result.installed == []
    assert cfg.read_text(encoding="utf-8") == pre


def test_only_missing_block_is_added(tmp_path: Path) -> None:
    """User has cheap but not deep → only deep is appended; cheap is left alone."""
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    pre = '[profiles.cheap]\nmodel_reasoning_effort = "low"   # user customized to low\n'
    cfg.write_text(pre, encoding="utf-8")
    result = bootstrap_user_codex_profiles(home=tmp_path)
    assert result.changed
    assert result.installed == ["deep"]
    body = cfg.read_text(encoding="utf-8")
    # User's cheap block (including their custom value + comment) survives.
    assert 'model_reasoning_effort = "low"   # user customized to low' in body
    # New deep block appended.
    assert "[profiles.deep]" in body
    assert 'model_reasoning_effort = "high"' in body


def test_preserves_unrelated_user_content(tmp_path: Path) -> None:
    """User's [mcp_servers] / [agents] / other blocks must survive untouched."""
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    pre = (
        '[mcp_servers.custom]\ncommand = "/usr/local/bin/my-mcp"\n'
        "\n"
        "[features]\n"
        "experimental_skills = true\n"
    )
    cfg.write_text(pre, encoding="utf-8")
    result = bootstrap_user_codex_profiles(home=tmp_path)
    assert result.changed
    body = cfg.read_text(encoding="utf-8")
    assert '[mcp_servers.custom]\ncommand = "/usr/local/bin/my-mcp"' in body
    assert "experimental_skills = true" in body
    assert "[profiles.cheap]" in body
    assert "[profiles.deep]" in body


def test_creates_codex_dir_when_missing(tmp_path: Path) -> None:
    """~/.codex/ directory may not exist on first install — bootstrap creates
    it. mkdir is parents=True / exist_ok=True, so this is also safe when
    a partial install left an empty dir behind."""
    # tmp_path itself has no .codex subdir.
    assert not (tmp_path / ".codex").exists()
    result = bootstrap_user_codex_profiles(home=tmp_path)
    assert result.changed
    assert result.path == tmp_path / ".codex" / "config.toml"
    assert result.path.exists()


def test_trailing_newline_appended_if_missing(tmp_path: Path) -> None:
    """User's file without trailing newline gets one inserted before our
    addition so the merged file stays valid TOML (otherwise the next line
    would concatenate onto the user's last value)."""
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("[features]\nhooks = true", encoding="utf-8")  # no \n
    result = bootstrap_user_codex_profiles(home=tmp_path)
    assert result.changed
    body = cfg.read_text(encoding="utf-8")
    # User's `hooks = true` line must end with \n before our additions.
    assert "hooks = true\n" in body
    assert "[profiles.cheap]" in body


@pytest.mark.parametrize("preexisting", ["cheap", "deep"])
def test_partial_addition_does_not_duplicate(tmp_path: Path, preexisting: str) -> None:
    """Cross-check: whichever block IS present is never appended again."""
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        f'[profiles.{preexisting}]\nmodel_reasoning_effort = "medium"\n',
        encoding="utf-8",
    )
    result = bootstrap_user_codex_profiles(home=tmp_path)
    body = cfg.read_text(encoding="utf-8")
    # Exactly one occurrence of the preexisting block header.
    assert body.count(f"[profiles.{preexisting}]") == 1
    assert preexisting not in result.installed


@pytest.mark.parametrize(
    "header",
    [
        "[profiles.cheap]",
        "[ profiles.cheap]",
        "[profiles.cheap ]",
        "[ profiles.cheap ]",
        "[  profiles.cheap  ]",
    ],
)
def test_whitespace_variant_headers_are_detected(tmp_path: Path, header: str) -> None:
    """TOML §4.5 whitespace-padded headers must count as present (REVIEW P2-1).

    Substring `"[profiles.cheap]" not in existing` would miss `[ profiles.cheap ]`
    and re-append the block, producing duplicate-key TOML that Codex rejects
    on parse. The regex must accept any whitespace inside the brackets.
    """
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        f'{header}\nmodel_reasoning_effort = "minimal"\n'
        '[profiles.deep]\nmodel_reasoning_effort = "high"\n',
        encoding="utf-8",
    )
    result = bootstrap_user_codex_profiles(home=tmp_path)
    # Both blocks detected — nothing to add.
    assert not result.changed, (
        f"header {header!r} should count as present but bootstrap re-added blocks"
    )


def test_commented_out_block_is_respected(tmp_path: Path) -> None:
    """A user-disabled `# [profiles.cheap]` line counts as present.

    Rationale: if the user explicitly commented out a profile we previously
    installed, they intended to disable it. Silently re-adding the block
    would override their decision. The lexical regex matches commented
    lines too, which is the documented intentional behavior.
    """
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "# user disabled the cheap profile after a bad experience\n"
        "# [profiles.cheap]\n"
        '# model_reasoning_effort = "minimal"\n'
        "\n"
        '[profiles.deep]\nmodel_reasoning_effort = "high"\n',
        encoding="utf-8",
    )
    result = bootstrap_user_codex_profiles(home=tmp_path)
    assert not result.changed
    # User's commented-out block was not stomped.
    body = cfg.read_text(encoding="utf-8")
    assert "# [profiles.cheap]" in body


def test_header_comment_not_duplicated_on_partial_install(tmp_path: Path) -> None:
    """REVIEW P2-4: the ADR-008 explanatory header must appear once.

    Scenario: user previously ran bootstrap, which created the file with
    `_HEADER` + both blocks. User later deleted `[profiles.deep]` (perhaps
    to redefine it). Next bootstrap run should append the missing deep
    block WITHOUT re-prepending the ADR-008 comment header — the file
    already has one and a second copy is confusing.
    """
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "# harness-maker (ADR-008): per-loop invocation profiles. Codex CLI\n"
        "# rejects [profiles.*] in project-local .codex/config.toml, so they\n"
        "# live here at the user level.\n"
        "\n"
        '[profiles.cheap]\nmodel_reasoning_effort = "minimal"\n',
        encoding="utf-8",
    )
    result = bootstrap_user_codex_profiles(home=tmp_path)
    assert result.installed == ["deep"]
    body = cfg.read_text(encoding="utf-8")
    # Header line appears once, not twice.
    assert body.count("harness-maker (ADR-008): per-loop invocation profiles") == 1
