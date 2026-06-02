"""Rendered .claude/schemas/*.json must REPLACE on re-render, never KEEP.

Pure-JSON schema files carry no provenance frontmatter (ADR-008 of
PLAN-codex-second-llm-integration), so the generic no-frontmatter branch would
KEEP them forever — a fixed rendered schema never reaches existing installs on
`/hm:make --update`. PLAN-reconcile-schemas-always-replace ADR-001 forces
REPLACE for this zero-user-content machine artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.models import Blueprint, FileEntry, HarnessConfig, ReconcileDecision
from harness_maker.reconcile import reconcile
from harness_maker.render import (
    DEFAULT_FREEZE_TIME,
    RENDER_MANIFEST_NAME,
    _is_schemas_json,
    render,
)

_SCHEMA_REL = "schemas/codex-finding.schema.json"
_SCHEMA_TEMPLATE = "schemas/codex-finding.schema.json"

# The pre-0.28.7 broken shape: confidence/file/line/evidence NOT in required.
_STALE_SCHEMA = (
    '{\n  "type": "object",\n  "additionalProperties": false,\n'
    '  "required": ["findings", "summary"],\n'
    '  "properties": {"summary": {"type": "string"}, "confidence": {"type": "number"}}\n}\n'
)


def _bp_with_schema() -> Blueprint:
    return Blueprint(
        config=HarnessConfig(),
        files=[FileEntry(path=Path(_SCHEMA_REL), template=_SCHEMA_TEMPLATE)],
    )


def test_reconcile_stale_schema_returns_replace(tmp_path: Path) -> None:
    """An existing frontmatter-less schema must reconcile to REPLACE, not KEEP."""
    schema_path = tmp_path / _SCHEMA_REL
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(_STALE_SCHEMA, encoding="utf-8")

    conflicts = reconcile(tmp_path, _bp_with_schema())

    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "schema-always-replace"


def test_reconcile_schema_fresh_install_returns_both(tmp_path: Path) -> None:
    """No existing schema on disk → BOTH (new-only); fresh install path unaffected."""
    conflicts = reconcile(tmp_path, _bp_with_schema())
    assert conflicts[0].decision == ReconcileDecision.BOTH
    assert conflicts[0].reason == "new-only"


def test_reconcile_schema_branch_scoped_to_json_under_schemas(tmp_path: Path) -> None:
    """REPLACE fires only for schemas/*.json — not non-json under schemas/, nor json elsewhere.

    Both negatives are frontmatter-less, so they must fall through to the
    generic no-frontmatter KEEP — proving the new branch is scoped exactly to
    render._is_schemas_json (the SHARED predicate, no second hand-rolled check).
    """
    # non-json under schemas/ → KEEP
    (tmp_path / "schemas").mkdir(parents=True, exist_ok=True)
    (tmp_path / "schemas" / "README.md").write_text("plain, no frontmatter\n", encoding="utf-8")
    # json OUTSIDE schemas/ → KEEP
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "foo.json").write_text('{"x": 1}\n', encoding="utf-8")

    bp = Blueprint(
        config=HarnessConfig(),
        files=[
            FileEntry(path=Path("schemas/README.md"), template="schemas/README.md"),
            FileEntry(path=Path("data/foo.json"), template="data/foo.json"),
        ],
    )
    by_path = {c.path: c for c in reconcile(tmp_path, bp)}
    assert by_path[Path("schemas/README.md")].decision == ReconcileDecision.KEEP
    assert by_path[Path("data/foo.json")].decision == ReconcileDecision.KEEP
    # sanity: the shared predicate agrees with this scoping
    assert _is_schemas_json(FileEntry(path=Path(_SCHEMA_REL), template="x")) is True
    assert _is_schemas_json(FileEntry(path=Path("schemas/README.md"), template="x")) is False
    assert _is_schemas_json(FileEntry(path=Path("data/foo.json"), template="x")) is False


def test_make_overwrites_stale_schema_on_disk(tmp_path: Path) -> None:
    """CLI-boundary: reconcile REPLACE -> cli keep-filter -> render -> disk overwrite.

    Mirrors cli.py:367-371 (`keep_paths` / `new_files`) with the REAL reconcile
    and REAL render — a reconcile-only unit test does not prove the file is
    actually re-written on disk (CLAUDE.md checkpoint 8).
    """
    target = tmp_path / ".claude"
    schema_path = target / _SCHEMA_REL
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(_STALE_SCHEMA, encoding="utf-8")

    bp = _bp_with_schema()

    # --- replicate cli.py post-reconcile filter, verbatim ---
    conflicts = reconcile(target, bp)
    keep_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.KEEP}
    new_files = [f for f in bp.files if f.path not in keep_paths]
    bp = bp.model_copy(update={"files": new_files})
    render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)

    # The fixed 0.28.7 template puts confidence in required + nullable optionals.
    on_disk = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "confidence" in on_disk["required"], on_disk["required"]
    item_required = on_disk["properties"]["findings"]["items"]["required"]
    assert {"evidence", "file", "line"} <= set(item_required), item_required

    # W2: render records the re-written schema in the render manifest, so the
    # orphan-sweep recognizes it as ours-clean (cannot delete it). Without the
    # REPLACE flip the schema is KEEP'd, excluded from render, never recorded.
    manifest = (target / RENDER_MANIFEST_NAME).read_text(encoding="utf-8")
    assert _SCHEMA_REL in manifest, manifest
