"""Structural tests for onboarding UX copy contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_make_command_asks_locale_before_state_or_profile() -> None:
    text = _read("commands/make.md")
    hm_make = _read("src/harness_maker/templates/commands/hm/make.md.j2")

    locale_pos = text.index("### 1. Choose live locale")
    detect_pos = text.index("### 2. Detect state")
    profile_pos = text.index("#### 4.1 Run profile scan")

    assert locale_pos < detect_pos < profile_pos
    assert "Default is `en`" in text
    assert "subsequent live onboarding prose" in text
    assert "--ci" in text
    assert "asks locale first" in hm_make


def test_make_command_explains_receipt_safety_boundaries() -> None:
    text = _read("commands/make.md")
    required = [
        ".claude/",
        ".codex/",
        ".agents/skills/",
        "AGENTS.md",
        ".backup-<timestamp>",
        "@hm:user:*",
        "KEEP",
        "MERGE_BLOCK",
        "REPLACE",
        "Dropping a target does not delete",
        "trade-off",
        "without predicting exact review time",
        "hand-edit `.claude/harness.yaml`",  # hm:configure retired in 0.64.0
        # Phase 6 (PLAN-onboarding-backup-friction): preservation matrix +
        # prune-backups CLI mentioned in the safety receipt prose.
        "docs/reference/preservation-matrix.md",
        "harness-maker prune-backups",
    ]
    for needle in required:
        assert needle in text




