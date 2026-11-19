"""SPEC-stale-install-recovery AC-008: the auto-tag workflow dispatches the release on the tag."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows/autotag.yml"


def _load() -> dict[Any, Any]:
    data = yaml.safe_load(WF.read_text("utf-8"))
    assert isinstance(data, dict)
    return data


def test_ac_008_autotag_workflow_wiring() -> None:
    w = _load()
    on = w.get("on", w.get(True))  # PyYAML parses the bare key `on` as True
    assert on == {"push": {"branches": ["main"]}}
    assert w["permissions"] == {"contents": "write", "actions": "write"}
    assert "concurrency" in w
    text = WF.read_text("utf-8")
    assert "harness_maker.release_autotag" in text
    assert "github.event.before" in text
    assert "fetch-tags: true" in text or "git fetch --tags" in text
    assert "gh workflow run release.yml --ref" in text
    assert "git tag -a" in text


def test_ac_008_release_yml_publish_jobs_accept_a_dispatched_tag_ref() -> None:
    """The dispatch only publishes because every gated job keys on github.ref, not the event."""
    release = (ROOT / ".github/workflows/release.yml").read_text("utf-8")
    assert "github.event_name == 'push'" not in release
    assert release.count("startsWith(github.ref, 'refs/tags/v')") >= 4
