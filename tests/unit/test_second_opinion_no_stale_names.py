"""Phase 7 staleness gate (PLAN-second-opinion-multi-model S1).

Asserts the codex_second_opinion → second_opinion rename left no stale identifier in the
shipped source tree (src/ + commands/ + CLAUDE.md), except the small, deliberate set of
migration / back-compat references that MUST keep naming the legacy key to read old files.
A regression here means a rename was missed and would ship a broken reference.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

# Stale identifiers that must not appear in shipped source outside the allowlist.
_STALE = [
    "codex_second_opinion",
    "codex_status",
    "codex_reconciliation",
    "codex-second-opinion.jsonl",
    "codex-finding.schema.json",
    "codex_exec_mainloop",
    "CodexSecondOpinionConfig",
    "CodexSecondOpinionRecord",
    "map_codex_severity",
]

# Files allowed to mention a legacy name — the migration/back-compat code that reads old
# harness.yaml / old ledger files, plus this test itself.
_ALLOWLIST = {
    "src/harness_maker/interview.py",  # _load_second_opinion legacy migration (ADR-001)
    "src/harness_maker/codex_ledger.py",  # legacy ledger forward-copy (ADR-005)
    "src/harness_maker/models.py",  # doc comments explaining the supersede
    "CLAUDE.md",  # migration prose: "second_opinion supersedes codex_second_opinion"
    "tests/unit/test_second_opinion_no_stale_names.py",
}

_SCAN_ROOTS = ["src/harness_maker", "commands", "CLAUDE.md"]


def _iter_files():  # type: ignore[no-untyped-def]
    for root in _SCAN_ROOTS:
        p = _REPO / root
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and f.suffix in {".py", ".j2", ".md", ".json", ".toml"}:
                    yield f


def test_no_stale_second_opinion_names() -> None:
    pattern = re.compile("|".join(re.escape(s) for s in _STALE))
    offenders: dict[str, list[str]] = {}
    for f in _iter_files():
        rel = f.relative_to(_REPO).as_posix()
        if rel in _ALLOWLIST:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        hits = sorted({m.group(0) for m in pattern.finditer(text)})
        if hits:
            offenders[rel] = hits
    assert not offenders, f"stale codex second-opinion identifiers found: {offenders}"
