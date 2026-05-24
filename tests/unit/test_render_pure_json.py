"""Tests for the _is_schemas_json predicate + dispatch routing.

Phase 1 of PLAN-codex-second-llm-integration. ADR-008 P-W3 correction:
_render_pure_json is NOT new (exists at render.py:512); the new code is the
_is_schemas_json predicate + the dispatch wire-up routing .claude/schemas/*.json
to the existing _render_pure_json renderer.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import Blueprint, FileEntry
from harness_maker.render import DEFAULT_FREEZE_TIME, _is_schemas_json, render


def test_is_schemas_json_predicate_matches_dot_claude_schemas() -> None:
    fe = FileEntry(
        path=Path("schemas/codex-finding.schema.json"),
        template="schemas/codex-finding.schema.json",
    )
    assert _is_schemas_json(fe) is True


def test_is_schemas_json_predicate_excludes_other_json_paths() -> None:
    for path in [
        "hooks/hooks.json",
        ".cursor/mcp.json",
        ".codex/hooks.json",
        "settings.json",
    ]:
        fe = FileEntry(path=Path(path), template=path)
        assert _is_schemas_json(fe) is False, f"unexpected match for {path}"


def test_is_schemas_json_predicate_excludes_non_json_under_schemas() -> None:
    fe = FileEntry(path=Path("schemas/README.md"), template="schemas/README.md")
    assert _is_schemas_json(fe) is False


def test_dispatch_routes_schemas_to_pure_json(tmp_path: Path) -> None:
    """Schema files at .claude/schemas/*.json MUST render as pure JSON.

    Contract: output starts with `{` (no YAML `---` frontmatter prefix) and
    does NOT contain `content_hash:` (per ADR-008 — schemas have no provenance
    block because the external consumer is `codex exec --output-schema`, which
    expects pure JSON Schema). Validates the dispatch wire-up — if the predicate
    is added but the dispatch chain still routes via `_render_text_file`,
    this test fails (frontmatter prefix appears).
    """
    fe = FileEntry(
        path=Path("schemas/codex-finding.schema.json"),
        template="schemas/codex-finding.schema.json",
    )
    bp = Blueprint(files=[fe])
    written = render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    assert len(written) == 1
    body = written[0].read_text(encoding="utf-8")
    assert body.startswith("{"), f"schema file must be pure JSON; got: {body[:50]!r}"
    assert "content_hash" not in body, "schema file must NOT contain content_hash"
    assert "generated_by" not in body, "schema file must NOT contain frontmatter"
