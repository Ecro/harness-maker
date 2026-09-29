"""SPEC-top-issues-2026-09 S7/S8: a character budget beside the line budget for CLAUDE.md/AGENTS.md.

The line unit is blind to density: this repo's CLAUDE.md passed 429/500 lines at 65,108 bytes
(~18k tokens, carried on every turn). Every test here is written so that deleting the character
check makes it fail — a fixture over the LINE budget as well would pass on the line check alone.

Phase A.4 justified passes: the four `ok` rows of AC-011 and
`test_readiness_within_both_budgets_passes`
assert the ABSENCE of a character warning, so they pass while no character check exists. They go red
if the budget is set too low. Their RED positive siblings are the `warn` rows and
`test_readiness_char_overflow_fails`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness_maker.context_lint import CHAR_THRESHOLDS, THRESHOLDS, lint
from harness_maker.models import Preset
from harness_maker.readiness import _dim_context_quality
from harness_maker.spec_machine import GoldenRow, load_golden_table

_REPO = Path(__file__).parents[2]
_ROWS = load_golden_table(_REPO / "specs/SPEC-top-issues-2026-09.machine.yaml", "AC-011")


def _body(lines: int, chars: int) -> str:
    width = max(1, chars // lines - 1)
    return "\n".join("x" * width for _ in range(lines)) + "\n"


def _char_warnings(warnings: list[str]) -> list[str]:
    return [w for w in warnings if "characters" in w]


@pytest.mark.parametrize(
    "row",
    _ROWS,
    ids=[f"{r.input['asset']}-{r.input['preset']}-{r.input['chars']}" for r in _ROWS],
)
def test_char_budget_warns_under_line_budget(tmp_path: Path, row: GoldenRow) -> None:
    spec = row.input
    preset = Preset(spec["preset"])
    path = tmp_path / spec["asset"]
    path.write_text(_body(spec["lines"], spec["chars"]), encoding="utf-8")
    got = _char_warnings(lint(path, spec["asset"], preset))
    if row.expected == "warn":
        assert len(got) == 1
        assert str(CHAR_THRESHOLDS[(spec["asset"], preset.value)]) in got[0].replace(",", "")
    else:
        assert got == []


def test_char_budget_fires_where_the_line_budget_cannot(tmp_path: Path) -> None:
    """The discriminating case: under the line budget, over the character budget → exactly one
    warning, and it is the character one. Removing the char check turns this red."""
    path = tmp_path / "CLAUDE.md"
    path.write_text(_body(300, 50_000), encoding="utf-8")
    assert THRESHOLDS[("CLAUDE.md", Preset.PRODUCTION.value)] >= 300
    warnings = lint(path, "CLAUDE.md", Preset.PRODUCTION)
    assert len(warnings) == 1
    assert "characters" in warnings[0]


def test_char_budget_values_match_spec() -> None:
    assert CHAR_THRESHOLDS[("CLAUDE.md", "Production")] == 40_000
    assert CHAR_THRESHOLDS[("CLAUDE.md", "Side")] == 16_000
    assert CHAR_THRESHOLDS[("AGENTS.md", "Production")] == 40_000
    assert CHAR_THRESHOLDS[("AGENTS.md", "Side")] == 16_000


def test_budget_counts_characters_not_bytes(tmp_path: Path) -> None:
    """Korean text is ~3 bytes per character — the file that motivated this is 65,108 bytes.

    Both directions are pinned: 30,000 Hangul characters (~90,000 bytes) must NOT warn, and a
    count taken in bytes would; 45,000 characters must warn.
    """
    under = tmp_path / "under" / "CLAUDE.md"
    under.parent.mkdir()
    under.write_text(("가" * 99 + "\n") * 300, encoding="utf-8")
    assert len(under.read_bytes()) > 40_000
    assert _char_warnings(lint(under, "CLAUDE.md", Preset.PRODUCTION)) == []
    assert _signal(under.parent, Preset.PRODUCTION, "claude_md_within_limit").passed is True

    over = tmp_path / "over" / "CLAUDE.md"
    over.parent.mkdir()
    over.write_text(("가" * 149 + "\n") * 300, encoding="utf-8")
    assert len(_char_warnings(lint(over, "CLAUDE.md", Preset.PRODUCTION))) == 1
    assert _signal(over.parent, Preset.PRODUCTION, "claude_md_within_limit").passed is False


# ── AC-012 ───────────────────────────────────────────────────────────────────


def _signal(project: Path, preset: Preset, sid: str) -> Any:
    dim = _dim_context_quality(project, preset)
    return next(s for s in dim.signals if s.id == sid)


def test_readiness_char_overflow_fails(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(_body(300, 50_000), encoding="utf-8")
    sig = _signal(tmp_path, Preset.PRODUCTION, "claude_md_within_limit")
    assert sig.passed is False
    assert "characters" in sig.evidence


def test_readiness_within_both_budgets_passes(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(_body(300, 30_000), encoding="utf-8")
    assert _signal(tmp_path, Preset.PRODUCTION, "claude_md_within_limit").passed is True


# ── AC-013 ───────────────────────────────────────────────────────────────────


def test_repo_claude_md_within_char_budget() -> None:
    from harness_maker.context_lint import _strip_frontmatter

    body = _strip_frontmatter((_REPO / "CLAUDE.md").read_text(encoding="utf-8"))
    assert len(body) <= 40000
