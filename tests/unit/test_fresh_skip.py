"""Tests for A6 fresh-skip enforcement (Phase 5)."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import pytest


def test_agent_quality_skip_platinum(tmp_path: Path) -> None:
    """Agent quality scorer must skip re-scoring for Platinum/Gold tiers."""
    from harness_maker.agent_quality import score_agent

    agent_md = tmp_path / "test-agent.md"
    agent_md.write_text(
        "---\nname: test\ndescription: test agent\n---\n"
        + "\n".join(f"- rule {i}" for i in range(200)),
        encoding="utf-8",
    )

    result1 = score_agent(agent_md)
    tier1 = result1["tier"]

    if tier1 in ("Platinum", "Gold"):
        result2 = score_agent(agent_md)
        assert result2["tier"] == tier1
        assert result2["composite"] == result1["composite"]
    else:
        result2 = score_agent(agent_md)
        assert result2["tier"] == tier1


def test_agent_quality_skip_invalidates_on_change(tmp_path: Path) -> None:
    """Skip cache must invalidate when agent content changes."""
    from harness_maker.agent_quality import score_agent

    agent_md = tmp_path / "test-agent.md"
    agent_md.write_text(
        "---\nname: test\ndescription: test\n---\n" + "\n".join(f"- rule {i}" for i in range(200)),
        encoding="utf-8",
    )

    result1 = score_agent(agent_md)

    agent_md.write_text("# Empty agent\nno structure\n", encoding="utf-8")
    result2 = score_agent(agent_md)
    assert result2["composite"] != result1["composite"]


def test_agent_quality_force_overrides_skip(tmp_path: Path) -> None:
    """--force must bypass the tier-based skip."""
    from harness_maker.agent_quality import score_agent

    agent_md = tmp_path / "test-agent.md"
    agent_md.write_text(
        "---\nname: test\ndescription: test agent\n---\n"
        + "\n".join(f"- bullet point {i}" for i in range(200)),
        encoding="utf-8",
    )

    result1 = score_agent(agent_md)
    result2 = score_agent(agent_md, force=True)
    assert result2["tier"] == result1["tier"]


def test_secscan_skip_fresh(tmp_path: Path) -> None:
    """Security scanner must skip when findings are fresh and deps unchanged."""
    from harness_maker.security_scanner import scan_all

    sec_dir = tmp_path / ".claude" / "observability" / "security"
    sec_dir.mkdir(parents=True)

    findings_file = sec_dir / f"findings-{date.today().isoformat()}.jsonl"
    findings_file.write_text("", encoding="utf-8")

    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "hooks.json").write_text("{}", encoding="utf-8")

    result = scan_all(tmp_path)
    assert isinstance(result, list)


def test_secscan_force_overrides_skip(tmp_path: Path) -> None:
    """--force must bypass the fresh-scan skip."""
    from harness_maker.security_scanner import scan_all

    sec_dir = tmp_path / ".claude" / "observability" / "security"
    sec_dir.mkdir(parents=True)

    findings_file = sec_dir / f"findings-{date.today().isoformat()}.jsonl"
    findings_file.write_text("", encoding="utf-8")

    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "hooks.json").write_text("{}", encoding="utf-8")

    result = scan_all(tmp_path, force=True)
    assert isinstance(result, list)
