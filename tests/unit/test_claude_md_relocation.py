"""SPEC-top-issues-2026-09 S8 / AC-016: CLAUDE.md sections were relocated, not cut.

Differential against the blob at the task's base commit, which predates the relocation edit and
is independent of it. Only the RELOCATED sections are checked — CLAUDE.md stays free to evolve;
the moved text lives in `docs/reference/*.md` files CLAUDE.md links to, as the recorded *why*.

Skips when the base commit is not in the object store (a shallow CI clone). Delete this test,
rather than editing the list, when a relocated reference doc is deliberately rewritten.

Phase A.4 justified passes: `test_relocated_sections_survive` and
`test_pinned_sections_stay_in_claude_md`
are negative invariants, vacuously true before anything moves; they go red the moment a relocation
drops a line or a pinned section. The RED positive siblings that force the relocation are
`test_relocated_docs_are_linked_from_claude_md` here and
`test_context_lint_chars.py::test_repo_claude_md_within_char_budget`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).parents[2]
_BASE = "3b718d91"

#: Headings (verbatim, from the base blob) whose bodies moved to docs/reference/.
RELOCATED_SECTIONS = (
    "## 보안 / 권한 (v1.6, REVIEW-2026-05-08 개정)",
    "## 리뷰어 팬아웃은 언어 조건부다 — 기록만, 라우팅은 안 한다",
    "## Multi-session worktree (PLAN-worktree-cross-session-data-loss-defense"
    " + PLAN-multisession-worktree-concurrency)",
    "## Second Brain 승급 파이프라인 (PLAN-second-brain-promotion)",
)
#: The second-opinion block is a nested bullet list inside "Targets 정책", not a heading.
RELOCATED_BULLET_PREFIX = "  - **Cross-model second opinion (multi-model)**"

#: Sections other tests pin — they must stay in CLAUDE.md.
PINNED_IN_CLAUDE_MD = ("## 릴리스 절차", "## Context discipline", "## Step sensitivity classes")


def _base_blob() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(_REPO), "show", f"{_BASE}:CLAUDE.md"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(f"base commit {_BASE} not available (shallow clone)")


def _section_lines(text: str, heading: str) -> list[str]:
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    start = lines.index(heading)
    out: list[str] = []
    for ln in lines[start:]:
        m = re.match(r"^(#+) ", ln)
        if out and m and len(m.group(1)) <= level:
            break
        out.append(ln)
    return out


def _bullet_block(text: str, prefix: str) -> list[str]:
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(prefix))
    out: list[str] = []
    for ln in lines[start:]:
        if out and ln.startswith("## "):
            break
        out.append(ln)
    return out


def _linked_reference_docs() -> list[Path]:
    """The `docs/reference/*.md` files CLAUDE.md actually links to — SPEC S8's corpus.

    Derived from the links, not from a filename convention: a relocation into any linked
    reference doc satisfies the SPEC, and an unlinked doc does not count however it is named.
    """
    claude = (_REPO / "CLAUDE.md").read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"docs/reference/([A-Za-z0-9._-]+\.md)", claude)))
    return [_REPO / "docs/reference" / n for n in names if (_REPO / "docs/reference" / n).is_file()]


def _current_corpus() -> set[str]:
    texts = [(_REPO / "CLAUDE.md").read_text(encoding="utf-8")]
    texts += [p.read_text(encoding="utf-8") for p in _linked_reference_docs()]
    return {ln.strip() for t in texts for ln in t.splitlines() if ln.strip()}


def test_relocated_sections_survive() -> None:
    base = _base_blob()
    corpus = _current_corpus()
    moved: list[str] = []
    for heading in RELOCATED_SECTIONS:
        moved += _section_lines(base, heading)
    moved += _bullet_block(base, RELOCATED_BULLET_PREFIX)
    missing = [ln for ln in moved if ln.strip() and ln.strip() not in corpus]
    assert not missing, f"{len(missing)} relocated line(s) lost, first: {missing[:3]}"


def test_relocated_docs_are_linked_from_claude_md() -> None:
    """Every relocated section has a destination CLAUDE.md links to — not merely a file on disk.

    The line check above would pass if the moved text sat in CLAUDE.md itself; this one requires
    that each relocated heading resolves to a LINKED reference doc, which is what S8 promises.
    """
    linked = _linked_reference_docs()
    headings = [h.lstrip("#").strip() for h in RELOCATED_SECTIONS]
    headings.append("Cross-model second opinion (multi-model)")
    for heading in headings:
        assert any(heading in p.read_text(encoding="utf-8") for p in linked), heading


def test_pinned_sections_stay_in_claude_md() -> None:
    claude = (_REPO / "CLAUDE.md").read_text(encoding="utf-8")
    for heading in PINNED_IN_CLAUDE_MD:
        assert any(ln.startswith(heading) for ln in claude.splitlines()), heading


def test_relocated_snapshots_are_classified_historical() -> None:
    """A relocated snapshot is exempt from the living-doc contract ONLY by explicit listing.

    Each doc carrying the relocation header must be in `HISTORICAL_DOC_FILES`, so moving one to
    living status (and back under the contract) is a deliberate edit, not an accident.
    """
    from harness_maker.documentation_contract import is_historical_doc

    snapshots = [
        p
        for p in _linked_reference_docs()
        if "Relocated verbatim from `CLAUDE.md`" in p.read_text(encoding="utf-8")
    ]
    assert len(snapshots) == 5
    for p in snapshots:
        assert is_historical_doc(p.relative_to(_REPO)), p.name
