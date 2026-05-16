"""Phase A5 — telemetry numerics must not leak into snapshot-tested templates.

PLAN-llm-code-review-2026 risk #9: if any `.j2` interpolates ``wall_time_ms``
(or similar per-run varying field) into a rendered surface, the snapshot
suite flakes the moment Phase A4 lands. Grep-based lint catches the
regression at PR time before snapshots even run.

Allowed sites: prose mentions in stage / agent docs (NOT Jinja2 expressions),
the dedicated emit-CLI block, and structural tests asserting the absence.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "src" / "harness_maker" / "templates"

# Forbidden Jinja2-injection pattern: `{{ ... wall_time_ms ... }}` or
# `{% ... wall_time_ms ... %}`. Plain prose mentions in body text are fine.
_JINJA_INJECT = re.compile(r"\{\{[^}]*wall_time_ms[^}]*\}\}|\{%[^%]*wall_time_ms[^%]*%\}")


def _scan_template_for_jinja_leak(path: Path) -> list[tuple[int, str]]:
    leaks: list[tuple[int, str]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _JINJA_INJECT.search(line):
            leaks.append((i, line))
    return leaks


def test_no_jinja_injection_of_wall_time_ms_in_templates() -> None:
    """No `.j2` template may interpolate wall_time_ms via Jinja2.

    Plain mentions in markdown prose are fine. Interpolations that surface
    a per-run number into a snapshot-hashed output are not.
    """
    offenders: list[str] = []
    for j2 in TEMPLATES.rglob("*.j2"):
        rel = j2.relative_to(REPO_ROOT)
        for lineno, line in _scan_template_for_jinja_leak(j2):
            offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        "telemetry numeric field leaked into Jinja2 interpolation in templates:\n"
        + "\n".join(offenders)
    )


_OBSERVABILITY_ALLOWLIST: frozenset[str] = frozenset(
    {
        "src/harness_maker/templates/stages/review.md.j2",  # Phase A4 emitter
        "src/harness_maker/templates/stages/verify.md.j2",  # pre-existing
        "src/harness_maker/templates/commands/hm/refresh.md.j2",  # pre-existing
        "src/harness_maker/templates/commands/hm/ai-readiness.md.j2",  # pre-existing
        # Phase 10 — reads override telemetry log
        "src/harness_maker/templates/commands/hm/personalization-audit.md.j2",
    }
)


def test_observability_dir_referenced_only_in_allowlist() -> None:
    """`.claude/observability/` path is mentioned only in known templates.

    Stray new references signal that telemetry shape is leaking — add to the
    allowlist deliberately, don't let it accumulate by accident.
    """
    candidates: list[str] = []
    for j2 in TEMPLATES.rglob("*.j2"):
        rel = str(j2.relative_to(REPO_ROOT))
        text = j2.read_text(encoding="utf-8")
        if ".claude/observability" not in text:
            continue
        if rel in _OBSERVABILITY_ALLOWLIST:
            continue
        # Skills / memory / lib subtrees may reference the dir for their own
        # observability needs; not part of this leak concern.
        if "/skills/" in rel or "/memory/" in rel or "/lib/" in rel:
            continue
        candidates.append(rel)
    assert not candidates, (
        ".claude/observability/ referenced in unexpected templates "
        "(add to allowlist if intentional):\n" + "\n".join(candidates)
    )
