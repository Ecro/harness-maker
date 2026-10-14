"""Codex hook trust notice after `make` (Codex skips untrusted project hooks silently)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.cli import _emit_codex_hook_trust_notice


def _write_hooks(root: Path, payload: object) -> None:
    (root / ".codex").mkdir()
    (root / ".codex" / "hooks.json").write_text(json.dumps(payload), encoding="utf-8")


def test_notice_counts_every_rendered_handler(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_hooks(
        tmp_path,
        {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "*", "hooks": [{"type": "command", "command": "a"}]},
                    {"matcher": "Write", "hooks": [{"type": "command", "command": "b"}]},
                ],
                "SessionStart": [
                    {
                        "hooks": [
                            {"type": "command", "command": "c"},
                            {"type": "command", "command": "d"},
                        ]
                    }
                ],
            }
        },
    )
    _emit_codex_hook_trust_notice(tmp_path)
    out = capsys.readouterr().out
    assert "4 handler(s)" in out
    assert "/hooks" in out
    assert "Re-trust" in out


def test_notice_silent_without_hooks_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _emit_codex_hook_trust_notice(tmp_path)
    assert capsys.readouterr().out == ""


def test_notice_never_raises_on_malformed_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "hooks.json").write_text("{not json", encoding="utf-8")
    _emit_codex_hook_trust_notice(tmp_path)
    assert capsys.readouterr().out == ""


def test_notice_matches_the_shipped_template(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The count must come from what Codex will actually load, not a hard-coded number."""
    from harness_maker.models import HarnessConfig
    from harness_maker.render import _make_env

    rendered = (
        _make_env()
        .get_template("codex/hooks.json.j2")
        .render(config=HarnessConfig().model_dump(mode="json"), harness_maker_src_path="/x")
    )
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "hooks.json").write_text(rendered, encoding="utf-8")
    _emit_codex_hook_trust_notice(tmp_path)
    out = capsys.readouterr().out
    assert "handler(s) in .codex/hooks.json will not run until trusted" in out
