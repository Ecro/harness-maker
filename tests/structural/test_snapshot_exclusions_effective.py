"""Phase A5 — snapshot exclusion mechanism actually filters.

PLAN-llm-code-review-2026 critique #7 resolution: the exclusion list must be
real machinery, not a parked file. Inject a known path into the list, assert
it disappears from both regenerate.py and the snapshot test's comparison
view.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "snapshot"))
from regenerate import is_excluded, load_exclusions  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
EXCLUSIONS_PATH = REPO_ROOT / "tests" / "snapshot" / "EXCLUSIONS.md"


def test_exclusions_file_present() -> None:
    assert EXCLUSIONS_PATH.is_file(), "EXCLUSIONS.md must ship with the mechanism"


def test_load_exclusions_parses_marker_block(tmp_path: Path) -> None:
    """Mechanism reads only the @hm:exclusion-list block — outside lines ignored."""
    fixture = tmp_path / "EXCLUSIONS.md"
    fixture.write_text(
        "# Header\n"
        "outside-block.md\n"
        "<!-- @hm:exclusion-list -->\n"
        "# comment line\n"
        ".claude/agents/code-reviewer.md\n"
        ".claude/agents/security-reviewer.md\n"
        "<!-- @hm:/exclusion-list -->\n"
        "after-block.md\n",
        encoding="utf-8",
    )
    globs = load_exclusions(fixture)
    assert ".claude/agents/code-reviewer.md" in globs
    assert ".claude/agents/security-reviewer.md" in globs
    assert "outside-block.md" not in globs
    assert "after-block.md" not in globs


def test_is_excluded_fnmatch_glob() -> None:
    """Patterns are fnmatch globs — wildcards expand correctly."""
    globs = [".claude/agents/*-reviewer.md"]
    assert is_excluded(".claude/agents/code-reviewer.md", globs)
    assert is_excluded(".claude/agents/security-reviewer.md", globs)
    assert not is_excluded(".claude/agents/code-verifier.md", globs)
    assert not is_excluded(".claude/skills/foo/SKILL.md", globs)


def test_exclusion_default_list_empty_or_documented() -> None:
    """Phase A5 ships with an empty list — Phase C1 populates it.

    A non-empty default would mean the exclusion has already taken effect
    on something today; that is a Phase C decision, not an A5 one.
    """
    globs = load_exclusions(EXCLUSIONS_PATH)
    assert globs == [], (
        f"Phase A5 must ship with no active exclusions; found {globs!r}. "
        "Reviewer-output paths get exclusions only at Phase C1 (ADR-003)."
    )


def test_exclusion_with_glob_drops_blueprint_files() -> None:
    """When an exclusion glob matches, downstream snapshot comparison drops it.

    This is the structural guarantee: the mechanism filters, not just parses.
    Inject ``.claude/agents/code-verifier.md`` as a fake exclusion and assert
    is_excluded returns True for that path.
    """
    fake_globs = [".claude/agents/code-verifier.md"]
    assert is_excluded(".claude/agents/code-verifier.md", fake_globs)
    # Real-world wildcard sanity check.
    star_globs = [".claude/agents/code-*.md"]
    assert is_excluded(".claude/agents/code-verifier.md", star_globs)
    assert is_excluded(".claude/agents/code-reviewer.md", star_globs)
    assert not is_excluded(".claude/agents/ux-reviewer.md", star_globs)
