"""The replay corpus must be COMMITTED, and the churn around it must not be.

ADR-006 part 2's detection check was declared unimplementable three times, the last time
because no per-reviewer finding payload had ever been persisted. Persisting it into a
gitignored path would repeat that in a quieter form: a corpus that exists only on the
machine that produced it cannot verify anyone else's pipeline change, nor one made after a
fresh clone. It shipped that way, and this file is the gate that keeps the fix.

The fragile part is not the negation — it is that `worktree._HARNESS_CHURN_DIRS` contains
the literal `.claude/observability/`, and `_ensure_gitignore_entries` appends any pattern it
does not find as an exact line. Appended text lands at EOF, after the negation, and git
resolves by last-match, so an implicit-only exclusion would be re-added on the next
`worktree create` and would silently re-ignore the corpus. `test_the_churn_appender_does_not
_shadow_the_negation` runs the real appender and asserts it stays skipped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_CORPUS = ".claude/observability/review-payloads/some-slug/run-round1-merged.json"
_CHURN = ".claude/observability/review-2026-01-01.jsonl"


def _ignored(rel: str) -> bool:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", rel], cwd=_REPO, capture_output=True, timeout=30, check=False
    )
    return proc.returncode == 0


def test_the_replay_corpus_is_committable() -> None:
    """A gitignored corpus is a scratch file, not an artifact."""
    assert not _ignored(_CORPUS), (
        "the replay corpus is gitignored — it cannot verify a pipeline change on any "
        "machine but the one that produced it, which is the gap ADR-006 part 2 exists to close"
    )


def test_the_surrounding_observability_churn_stays_ignored() -> None:
    """The other direction, and the one an over-broad negation would break.

    `review-*.jsonl`, receipts and ledgers are per-run churn; committing them would put the
    base repo back in the state the churn set was introduced to fix.
    """
    assert _ignored(_CHURN), "observability churn became committable — the negation is too broad"


def test_the_churn_appender_does_not_shadow_the_negation() -> None:
    """Run the REAL appender and assert `.gitignore` is unchanged.

    Asserting the literal line is present would only prove today's spelling. This proves the
    property that matters: the appender finds its pattern and skips, so nothing lands at EOF
    to win the last-match race against the negation.
    """
    from harness_maker.worktree import _ensure_harness_gitignore

    gitignore = _REPO / ".gitignore"
    before = gitignore.read_text(encoding="utf-8")
    _ensure_harness_gitignore(_REPO)
    assert gitignore.read_text(encoding="utf-8") == before, (
        "the churn appender rewrote .gitignore — an appended `.claude/observability/` lands "
        "after the negation and git's last-match rule then re-ignores the corpus"
    )
    assert not _ignored(_CORPUS), "the corpus became ignored after the appender ran"
