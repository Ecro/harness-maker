"""Static structural checks for README one-prompt section.

PLAN-readme-one-prompt-autoinstall Phase 3a.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATHS = [REPO_ROOT / "README.md", REPO_ROOT / "README.ko.md"]


def _extract_one_prompt_block(readme_path: Path) -> str:
    """Body of the first triple-fenced code block under 'Universal Bootstrap Prompt'."""
    text = readme_path.read_text(encoding="utf-8")
    start = re.search(r"Universal Bootstrap Prompt", text)
    if start is None:
        pytest.fail(f"{readme_path.name}: 'Universal Bootstrap Prompt' heading missing")
    fence_open = text.find("```", start.end())
    if fence_open == -1:
        pytest.fail(f"{readme_path.name}: no opening code fence after Universal Bootstrap Prompt")
    body_start = text.find("\n", fence_open) + 1
    fence_close = text.find("\n```", body_start)
    if fence_close == -1:
        pytest.fail(f"{readme_path.name}: no closing code fence")
    return text[body_start:fence_close]


def _section_between_markers(block: str, ide: str) -> str:
    """Return substring scoped to the given IDE branch inside the prompt body."""
    markers = {
        "claude": r"IF Claude Code:",
        "cursor": r"IF Cursor",
        "codex": r"IF Codex CLI:",
    }
    pat = markers[ide]
    m = re.search(pat, block)
    if m is None:
        pytest.fail(f"branch marker {pat!r} missing inside one-prompt body")
    rest = block[m.end() :]
    end = re.search(r"\n\s*IF (Claude Code|Cursor|Codex CLI|you can't)", rest)
    return rest[: end.start()] if end else rest


@pytest.fixture(params=README_PATHS, ids=lambda p: p.name)
def readme(request: pytest.FixtureRequest) -> Path:
    path: Path = request.param
    if not path.exists():
        pytest.fail(f"{path} does not exist")
    return path


def test_no_user_directed_slash_commands_in_prompt(readme: Path) -> None:
    block = _extract_one_prompt_block(readme)
    forbidden_patterns = [
        r"^\s*/plugin marketplace add\b",
        r"^\s*/plugin install\b",
        r"^\s*/harness-maker:make\b",
    ]
    offenders: list[str] = []
    for ln in block.splitlines():
        for pat in forbidden_patterns:
            if re.search(pat, ln):
                offenders.append(f"  {ln.rstrip()}")
    assert not offenders, (
        f"{readme.name}: one-prompt body still tells the user to type slash commands:\n"
        + "\n".join(offenders)
    )


def test_claude_code_branch_uses_bash_install(readme: Path) -> None:
    sub = _section_between_markers(_extract_one_prompt_block(readme), "claude")
    bash_lines = [ln for ln in sub.splitlines() if re.match(r"^\s*Bash:", ln)]
    assert len(bash_lines) >= 2, (
        f"{readme.name}: Claude Code branch expects ≥2 'Bash:' lines "
        f"(marketplace add + install); found {len(bash_lines)}:\n" + "\n".join(bash_lines)
    )
    joined = " ".join(bash_lines)
    assert "claude plugin marketplace add" in joined, (
        f"{readme.name}: Claude Code branch missing 'claude plugin marketplace add' Bash line"
    )
    assert "claude plugin install" in joined, (
        f"{readme.name}: Claude Code branch missing 'claude plugin install' Bash line"
    )


def test_cursor_branch_uses_bash_git_clone(readme: Path) -> None:
    sub = _section_between_markers(_extract_one_prompt_block(readme), "cursor")
    bash_lines = [ln for ln in sub.splitlines() if re.match(r"^\s*Bash:", ln)]
    assert len(bash_lines) >= 1, (
        f"{readme.name}: Cursor branch expects ≥1 'Bash:' line; found {len(bash_lines)}"
    )
    assert "git clone" in " ".join(bash_lines), (
        f"{readme.name}: Cursor branch missing 'git clone' Bash line. "
        f"Got:\n" + "\n".join(bash_lines)
    )


def test_codex_branch_uses_bash_marketplace_add(readme: Path) -> None:
    sub = _section_between_markers(_extract_one_prompt_block(readme), "codex")
    bash_lines = [ln for ln in sub.splitlines() if re.match(r"^\s*Bash:", ln)]
    assert len(bash_lines) >= 1, (
        f"{readme.name}: Codex branch expects ≥1 'Bash:' line; found {len(bash_lines)}"
    )
    assert "codex plugin marketplace add" in " ".join(bash_lines), (
        f"{readme.name}: Codex branch missing 'codex plugin marketplace add' Bash line"
    )


def test_per_ide_step_budget_table_present(readme: Path) -> None:
    """A markdown table listing per-IDE user actions must precede the one-prompt code fence."""
    text = readme.read_text(encoding="utf-8")
    heading = re.search(r"Universal Bootstrap Prompt", text)
    assert heading is not None
    fence_open = text.find("```", heading.end())
    pre_fence_section = text[heading.end() : fence_open]
    for ide in ("Claude Code", "Cursor", "Codex"):
        assert ide in pre_fence_section, (
            f"{readme.name}: per-IDE step budget section before prompt is missing '{ide}'"
        )
    table_row = re.search(r"^\s*\|.*\|.*\|", pre_fence_section, re.M)
    assert table_row is not None, (
        f"{readme.name}: per-IDE step budget markdown table (rows with `|`) "
        f"missing between 'Universal Bootstrap Prompt' heading and the prompt code fence"
    )
