"""SPEC-release-ui-tolerant: github-release must update a Release made in the web UI."""

from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]


def _release_step_script() -> str:
    workflow = yaml.safe_load((_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["github-release"]["steps"]
    matches = [step for step in steps if step.get("name") == "Create GitHub Release"]
    assert len(matches) == 1
    return str(matches[0]["run"])


def test_ac_001_github_release_updates_existing_release() -> None:
    script = _release_step_script()
    lines = [line.strip() for line in script.splitlines()]
    guard = [i for i, line in enumerate(lines) if line.startswith('if gh release view "$TAG"')]
    assert len(guard) == 1, "the step must branch on whether the Release already exists"
    start = guard[0]
    else_at = lines.index("else", start)
    fi_at = lines.index("fi", else_at)
    existing = " ".join(lines[start:else_at])
    fresh = " ".join(lines[else_at:fi_at])
    assert 'gh release upload "$TAG" dist/* --clobber' in existing
    assert 'gh release edit "$TAG" --title "$TAG" --notes-file "$NOTES_FILE"' in existing
    assert "gh release create" not in existing
    assert 'gh release create "$TAG" dist/*' in fresh
    assert '--notes-file "$NOTES_FILE"' in fresh
