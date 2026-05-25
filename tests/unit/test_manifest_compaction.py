from __future__ import annotations

import json
from pathlib import Path

from harness_maker.reconcile import _load_render_manifest
from harness_maker.render import RENDER_MANIFEST_NAME, _manifest_key_for, compact_render_manifest


def test_manifest_compaction_preserves_unique_path_hash_pairs(tmp_path: Path) -> None:
    manifest = tmp_path / RENDER_MANIFEST_NAME
    records = [
        {"path": ".claude/a.md", "content_hash": "h1", "timestamp": "2026-01-01T00:00:00+00:00"},
        {"path": ".claude/a.md", "content_hash": "h1", "timestamp": "2026-01-02T00:00:00+00:00"},
        {"path": ".claude/a.md", "content_hash": "h2", "timestamp": "2026-01-01T00:00:00+00:00"},
        {
            "path": ".codex/config.toml",
            "content_hash": "h3",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
    ]
    manifest.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records),
        encoding="utf-8",
    )

    before = _load_render_manifest(tmp_path)
    assert compact_render_manifest(tmp_path, line_threshold=1) is True
    after = _load_render_manifest(tmp_path)

    assert after == before
    compacted = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert len(compacted) == 3
    latest_a_h1 = [
        r for r in compacted if r["path"] == ".claude/a.md" and r["content_hash"] == "h1"
    ][0]
    assert latest_a_h1["timestamp"] == "2026-01-02T00:00:00+00:00"


def test_manifest_compaction_key_matches_manifest_key_for() -> None:
    assert _manifest_key_for(Path("commands/hm/execute.md")) == ".claude/commands/hm/execute.md"
    assert _manifest_key_for(Path(".codex/agents/hm.toml")) == ".codex/agents/hm.toml"
