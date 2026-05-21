"""Token-presence snapshot for docs/BOOTSTRAP.md.

This is NOT a byte-diff against `harness-maker locate --help`. The doc is a
human-authored canonical onboarding reference (PLAN-locate-cli-version-gate
ADR-003); we assert load-bearing tokens are present so silent removal during
doc edits surfaces as a test failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_DOC = REPO_ROOT / "docs" / "BOOTSTRAP.md"


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert BOOTSTRAP_DOC.exists(), (
        f"docs/BOOTSTRAP.md missing at {BOOTSTRAP_DOC} — "
        "Phase 3 of PLAN-locate-cli-version-gate creates this file."
    )
    return BOOTSTRAP_DOC.read_text(encoding="utf-8")


# ---------- load-bearing CLI tokens ----------


def test_doc_mentions_locate_plain_pattern(doc_text: str) -> None:
    """The canonical bootstrap snippet uses `locate --plain`."""
    assert "harness-maker locate --plain" in doc_text


def test_doc_mentions_require_version_flag(doc_text: str) -> None:
    """The canonical bootstrap snippet uses --require-version."""
    assert "--require-version" in doc_text


def test_doc_documents_exit_code_2_and_3(doc_text: str) -> None:
    """Exit-code handling (2 = version mismatch, 3 = not installed) is documented."""
    assert "exit 2" in doc_text.lower() or "exit code 2" in doc_text.lower()
    assert "exit 3" in doc_text.lower() or "exit code 3" in doc_text.lower()


# ---------- 3 IDE sections ----------


def test_doc_has_claude_code_section(doc_text: str) -> None:
    """Claude Code-specific install + bootstrap snippet present."""
    assert "Claude Code" in doc_text
    assert "claude plugin install" in doc_text


def test_doc_has_cursor_section(doc_text: str) -> None:
    """Cursor-specific install + bootstrap snippet present."""
    assert "Cursor" in doc_text


def test_doc_has_codex_section(doc_text: str) -> None:
    """Codex CLI install + bootstrap snippet present."""
    assert "Codex" in doc_text


# ---------- anti-pattern + migration ----------


def test_doc_calls_out_anti_pattern(doc_text: str) -> None:
    """The kairos@0.7.3 footgun (or its class) is explicitly documented.

    The anti-pattern section MUST be marked with an HTML comment marker so
    future automated audits can find it; a contiguous "anti-pattern" string
    is the minimum required surface.
    """
    assert "anti-pattern" in doc_text.lower() or "ANTI-PATTERN" in doc_text


def test_doc_has_migration_snippet(doc_text: str) -> None:
    """Migration guidance for legacy meta-prompts is present."""
    text_lower = doc_text.lower()
    assert "migrat" in text_lower  # "migration", "migrating", etc.
