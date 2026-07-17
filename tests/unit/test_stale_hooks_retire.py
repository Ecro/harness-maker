"""ADR-005 pristine-exact-match retirement of `.claude/hooks/hooks.json`.

PLAN-permission-deny-and-hooks-wiring Phase 4: the file is no longer rendered,
but a stale copy on disk must be retired ONLY when it is byte-identical to what
the current template renders (⇒ zero user content). A file holding hand-wired
hooks is preserved with a one-time warning.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.cli import _retire_stale_hooks_json
from harness_maker.interview import interview
from harness_maker.models import Blueprint, ProjectProfile
from harness_maker.render import render_stale_hooks_json_bytes
from harness_maker.synthesize import synthesize


def _blueprint() -> Blueprint:
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)
    return synthesize(p, a)


def _shared_context(bp: Blueprint) -> dict[str, object]:
    for fe in bp.files:
        if "harness_maker_src_path" in fe.context:
            return fe.context
    raise AssertionError("no FileEntry carries the shared render context")


def test_pristine_hooks_json_is_deleted(tmp_path: Path) -> None:
    """A byte-pristine stale hooks.json (== current template render) is deleted."""
    bp = _blueprint()
    hooks_json = tmp_path / ".claude" / "hooks" / "hooks.json"
    hooks_json.parent.mkdir(parents=True)
    pristine = render_stale_hooks_json_bytes(_shared_context(bp))
    hooks_json.write_bytes(pristine)

    _retire_stale_hooks_json(tmp_path, bp)

    assert not hooks_json.exists(), "pristine hooks.json must be deleted"


def test_user_content_hooks_json_is_preserved(tmp_path: Path) -> None:
    """A hooks.json whose bytes differ from the template render (hand-wired
    hook) is preserved — the pristine-exact-match path must not touch it."""
    bp = _blueprint()
    hooks_json = tmp_path / ".claude" / "hooks" / "hooks.json"
    hooks_json.parent.mkdir(parents=True)
    pristine = render_stale_hooks_json_bytes(_shared_context(bp))
    # Splice a user hook in — bytes now differ from the template render.
    tampered = pristine.replace(b'"preset"', b'"USER_HOOK": "hand-wired", "preset"', 1)
    assert tampered != pristine
    hooks_json.write_bytes(tampered)

    _retire_stale_hooks_json(tmp_path, bp)

    assert hooks_json.exists(), "hooks.json with user content must be preserved"
    assert b"USER_HOOK" in hooks_json.read_bytes()


def test_retire_is_noop_when_file_absent(tmp_path: Path) -> None:
    """No stale file → nothing to do, no crash."""
    bp = _blueprint()
    _retire_stale_hooks_json(tmp_path, bp)  # must not raise


def test_pristine_bytes_match_the_canonical_render_pipeline() -> None:
    """De-circularize the delete test: the pristine oracle must equal what the
    real render pipeline (`_format_settings_json(json.loads(template.render))`)
    produced for the historical FileSpec. Without this, a future refactor that
    changed `render_stale_hooks_json_bytes` (e.g. dropped `_format_settings_json`)
    would silently stop retiring real on-disk files while the self-consistent
    delete test stayed green.
    """
    import json

    from harness_maker.render import (
        _STALE_HOOKS_JSON_TEMPLATE,
        _format_settings_json,
        _make_env,
    )

    ctx = _shared_context(_blueprint())
    independent = _format_settings_json(
        json.loads(_make_env().get_template(_STALE_HOOKS_JSON_TEMPLATE).render(**ctx))
    )
    assert render_stale_hooks_json_bytes(ctx) == independent
