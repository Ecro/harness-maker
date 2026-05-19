"""Meta-test for the boundary-parse suite (PLAN-test-fidelity-gap Phase 4).

Three assertions that protect the layer from silent erosion:

1. The five boundary modules exist on disk. A future cleanup that
   accidentally deletes one is caught here.
2. Each boundary module has at least one ``@pytest.mark.boundary_negative``
   test (collected via ``pytest --collect-only -m boundary_negative``).
   Without this guard, a future refactor could remove the negatives — the
   exact failure mode of ``[fail:test] boundary-test-no-sentinel`` (2026-05-09)
   generalized to the whole suite.
3. CLAUDE.md ``## 릴리스 절차 (race-free)`` references the boundary test
   command. Source-of-truth-driven check: validates the runbook step's
   presence regardless of exact command syntax (matches the substring
   ``tests/integration/test_boundary``).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INT_DIR = _REPO_ROOT / "tests" / "integration"
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"

_EXPECTED_MODULES: tuple[str, ...] = (
    "test_boundary_hooks_json.py",
    "test_boundary_codex_toml.py",
    "test_boundary_harness_yaml.py",
    "test_boundary_cursor_mdc.py",
    "test_boundary_settings_json.py",
)


def test_meta_five_boundary_modules_exist() -> None:
    """Each of the five boundary test modules is present on disk.

    Caught failure mode: a global rename / delete drops one of the file-
    type modules silently. Phase 4 of PLAN-test-fidelity-gap pins the
    layer to exactly these five.
    """
    missing = [name for name in _EXPECTED_MODULES if not (_INT_DIR / name).is_file()]
    assert not missing, (
        f"boundary-parse modules missing from {_INT_DIR}: {missing}. "
        f"PLAN-test-fidelity-gap Phase 4 success criterion broken."
    )


@pytest.mark.parametrize("module_name", _EXPECTED_MODULES)
def test_meta_module_has_boundary_negative(module_name: str) -> None:
    """The module has ≥1 test collected with the ``boundary_negative`` marker.

    Uses ``pytest --collect-only -m boundary_negative`` rather than parsing
    the file directly — the marker IS the programmatic recognizer per
    PLAN-test-fidelity-gap §Testing Strategy (W6 resolution).
    """
    module_path = _INT_DIR / module_name
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "boundary_negative",
            "--collect-only",
            "-q",
            str(module_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"pytest collection failed for {module_name}: rc={proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    # ``-q --collect-only`` aggregates by file as ``<path>: <count>`` lines.
    # Parse the count for the target module and assert ≥ 1.
    count_match = re.search(
        rf"{re.escape(module_name)}:\s*(\d+)",
        proc.stdout,
    )
    assert count_match is not None, (
        f"could not parse collection count for {module_name} from pytest stdout:\n{proc.stdout}"
    )
    collected = int(count_match.group(1))
    assert collected >= 1, (
        f"{module_name} has no @pytest.mark.boundary_negative tests collected "
        f"(count={collected}).\npytest stdout:\n{proc.stdout}"
    )


def test_meta_claude_md_runbook_references_boundary_suite() -> None:
    """CLAUDE.md `릴리스 절차 (race-free)` section references the boundary command.

    Source-of-truth check: matches the substring ``tests/integration/test_boundary``
    inside the release-procedure section, NOT a fixed command string.
    If the maintainer changes ``pytest tests/integration/test_boundary_*.py``
    to ``pytest -m boundary`` later, this test stays green; if the entire
    paragraph is dropped, this fires red.
    """
    assert _CLAUDE_MD.is_file(), f"CLAUDE.md not found at {_CLAUDE_MD}"
    text = _CLAUDE_MD.read_text(encoding="utf-8")

    # Find the release-procedure heading. We accept either an exact match
    # on the Korean heading or the literal "릴리스 절차" substring.
    section_match = re.search(
        r"^##\s+릴리스 절차.*?$(?P<body>.*?)(?=^##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert section_match is not None, "Could not locate '## 릴리스 절차' section in CLAUDE.md"
    section_body = section_match.group("body")
    assert "tests/integration/test_boundary" in section_body, (
        "릴리스 절차 section does not reference the boundary-parse test "
        "command — PLAN-test-fidelity-gap ADR-004 runbook step missing. "
        "Restore the paragraph before tagging."
    )
