"""Phase 5b test: .codex/hooks.json must reference the current harness-maker version.

RED: hooks.json rendered from template with development path (no version in path)
GREEN: hooks.json rendered with installed plugin cache path containing __version__
"""

from __future__ import annotations

import json

from harness_maker import __version__
from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env


def _render_codex_hooks_json(src_path: str) -> str:
    env = _make_env()
    cfg = HarnessConfig().model_dump(mode="json")
    return env.get_template("codex/hooks.json.j2").render(
        harness_maker_src_path=src_path,
        config=cfg,
        preset="Production",
        is_codex=False,
        skills={},
        stack=[],
        scale="",
        lifecycle="",
    )


def test_codex_hooks_reference_current_version() -> None:
    """All .codex/hooks.json hook commands must reference the current harness-maker version."""
    versioned_path = (
        f"/home/noel/.claude/plugins/cache/harness-maker-local/harness-maker/{__version__}"
    )
    rendered = _render_codex_hooks_json(versioned_path)
    data = json.loads(rendered)
    commands = [
        h["command"] for event in data["hooks"].values() for block in event for h in block["hooks"]
    ]
    for cmd in commands:
        assert __version__ in cmd, (
            f"Hook command references old version — expected {__version__!r}: {cmd}"
        )


def test_codex_hooks_json_is_valid_json() -> None:
    """codex/hooks.json.j2 must render valid JSON."""
    rendered = _render_codex_hooks_json("/some/path/0.0.0")
    data = json.loads(rendered)
    assert "hooks" in data, "hooks.json must have top-level 'hooks' key"


def test_codex_hooks_json_has_required_events() -> None:
    """codex/hooks.json must define PostToolUse and PreToolUse hooks."""
    rendered = _render_codex_hooks_json("/some/path/0.0.0")
    data = json.loads(rendered)
    assert "PostToolUse" in data["hooks"], "hooks.json missing PostToolUse"
    assert "PreToolUse" in data["hooks"] or "PermissionRequest" in data["hooks"], (
        "hooks.json missing PreToolUse or PermissionRequest"
    )


def test_codex_hooks_json_has_no_unknown_top_level_keys() -> None:
    """Codex's parser accepts only `description` and `hooks` at the top level.

    Regression: harness-maker shipped a `preset` provenance stamp here through
    0.51.1, and Codex rejected the whole file — "unknown field `preset`, expected
    `description` or `hooks`" — leaving every hook in it dead.
    """
    rendered = _render_codex_hooks_json("/some/path/0.0.0")
    data = json.loads(rendered)
    unknown = sorted(set(data) - {"description", "hooks"})
    assert not unknown, f"unknown top-level key(s) in .codex/hooks.json: {unknown}"
