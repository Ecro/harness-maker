"""The retired antigravity model default must not survive at any shipped site."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The tier retired by PLAN-antigravity-second-opinion-timeout ADR-001. Measured
# 2026-08-08: 4m04s -> timeout with zero output bytes on a 41KB prompt, against a
# 240s budget. Eight ledger rows were lost to it.
_RETIRED = re.compile(r"Gemini 3\.1 Pro \(High\)")

# Scan roots are the SHIPPED surface only. Deliberately excluded, and why:
#   tests/            - fixtures pin a NON-default value on purpose (see below)
#   CHANGELOG.md      - historical record
#   work-docs/        - PLAN/RESEARCH documents describing the retirement
#   .claude/          - this repo's own harness config; Phase 6 owns it
# There is no allowlist parameter here: an allowlist naming paths outside these
# roots would be dead text, since a scan of `src/` and `README.md` can never
# emit one.
_SCAN_ROOTS = ("src", "README.md")


def _shipped_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        target = _REPO_ROOT / root
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(p for p in target.rglob("*") if p.is_file() and _is_text(p))
    return sorted(files)


def _is_text(path: Path) -> bool:
    return path.suffix in {".py", ".j2", ".md", ".json", ".yaml", ".yml", ".toml"}


def test_retired_antigravity_default_absent_from_shipped_surface() -> None:
    hits: list[str] = []
    for path in _shipped_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # pragma: no cover - defensive
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _RETIRED.search(line):
                hits.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}")
    assert not hits, (
        "retired antigravity default 'Gemini 3.1 Pro (High)' still present at: "
        f"{hits}. ADR-001/ADR-003 retire it at every shipped site; the two "
        "harness-yaml render fallbacks are the fresh-install path, so leaving "
        "them pins every NEW harness to the timing-out tier."
    )


def test_scan_actually_covers_the_known_default_sites() -> None:
    """Guard the guard: an empty or mis-rooted scan would pass vacuously."""
    scanned = {str(p.relative_to(_REPO_ROOT)) for p in _shipped_files()}
    for required in (
        "src/harness_maker/models.py",
        "src/harness_maker/second_opinion_invoke.py",
        "src/harness_maker/templates/harness-yaml/Production.yaml.j2",
        "src/harness_maker/templates/harness-yaml/Side.yaml.j2",
        "src/harness_maker/templates/agents/_partials/second_opinion_antigravity.md.j2",
        "README.md",
    ):
        assert required in scanned, f"scan root regression: {required} not scanned"


def test_nondefault_pro_low_fixtures_are_left_alone() -> None:
    """`Gemini 3.1 Pro (Low)` proves config plumbing reads the USER's value.

    Those fixtures deliberately differ from the shipped default; rewriting them
    to the new default would silently delete that coverage. This test fails if
    they are "cleaned up" along with the retirement.

    A membership check (``"..." in text``) is NOT enough here and the mutation gate
    proved it: deleting one of the six occurrences in ``test_second_opinion_invoke.py``
    left the other five, so the assertion stayed green through a real coverage
    deletion — ``[fail:test] assertion-invariant-over-named-dimension`` exactly. The
    floor counts are what make a single deletion turn this red. They may rise if more
    plumbing coverage is added; they may never silently fall.
    """
    floors = {
        _REPO_ROOT / "tests" / "unit" / "test_second_opinion_invoke.py": 6,
        _REPO_ROOT / "tests" / "integration" / "test_antigravity_sandbox_probe.py": 1,
    }
    for path, floor in floors.items():
        found = path.read_text(encoding="utf-8").count("Gemini 3.1 Pro (Low)")
        assert found >= floor, (
            f"{path.name} has {found} non-default model fixtures, expected at least "
            f"{floor}. That value is the only proof the CONFIGURED model reaches the "
            "argv rather than a hardcoded default; losing one silently deletes a "
            "plumbing assertion."
        )
