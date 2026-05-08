"""Tests for AST hallucination gate (Phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.secscan.hallucination import scan_directory, scan_file


def _write_py(path: Path, code: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    return path


def test_detects_nonexistent_import(tmp_path: Path) -> None:
    f = _write_py(tmp_path / "bad.py", "from nonexistent_pkg import FakeClass\n")
    findings = scan_file(f)
    assert len(findings) >= 1
    assert any("nonexistent_pkg" in f.evidence for f in findings)
    assert findings[0].severity == "P0"
    assert findings[0].category == "hallucination"


def test_allows_stdlib_import(tmp_path: Path) -> None:
    f = _write_py(tmp_path / "good.py", "import os\nimport json\nimport sys\n")
    findings = scan_file(f)
    assert findings == []


def test_allows_installed_package(tmp_path: Path) -> None:
    f = _write_py(tmp_path / "good.py", "import pytest\nfrom pydantic import BaseModel\n")
    findings = scan_file(f)
    assert findings == []


def test_allows_future_import(tmp_path: Path) -> None:
    f = _write_py(tmp_path / "good.py", "from __future__ import annotations\n")
    findings = scan_file(f)
    assert findings == []


def test_guarded_import_gets_p2(tmp_path: Path) -> None:
    code = """\
try:
    from totally_fake_optional_pkg import Something
except ImportError:
    Something = None
"""
    f = _write_py(tmp_path / "optional.py", code)
    findings = scan_file(f)
    assert len(findings) >= 1
    guarded = [f for f in findings if "totally_fake_optional_pkg" in f.evidence]
    assert guarded[0].severity == "P2"


def test_multiple_hallucinated_imports(tmp_path: Path) -> None:
    code = """\
from imaginary_lib import FooBar
import another_fake_module
from yet_another_nonexistent import helper
"""
    f = _write_py(tmp_path / "multi.py", code)
    findings = scan_file(f)
    assert len(findings) == 3


def test_scan_directory_skips_venv(tmp_path: Path) -> None:
    _write_py(tmp_path / ".venv" / "lib" / "bad.py", "from nonexistent_pkg import X\n")
    _write_py(tmp_path / "src" / "good.py", "import os\n")
    findings = scan_directory(tmp_path)
    assert findings == []


def test_scan_directory_finds_across_files(tmp_path: Path) -> None:
    _write_py(tmp_path / "a.py", "from fake_pkg_a import A\n")
    _write_py(tmp_path / "sub" / "b.py", "from fake_pkg_b import B\n")
    findings = scan_directory(tmp_path)
    assert len(findings) == 2


def test_syntax_error_file_no_crash(tmp_path: Path) -> None:
    f = _write_py(tmp_path / "broken.py", "def f(\n")
    findings = scan_file(f)
    assert findings == []


def test_empty_file_no_findings(tmp_path: Path) -> None:
    f = _write_py(tmp_path / "empty.py", "")
    findings = scan_file(f)
    assert findings == []


def test_relative_import_ignored(tmp_path: Path) -> None:
    f = _write_py(tmp_path / "rel.py", "from . import sibling\nfrom .sub import helper\n")
    findings = scan_file(f)
    assert findings == []


def test_finding_has_fix_suggestion(tmp_path: Path) -> None:
    f = _write_py(tmp_path / "bad.py", "import nonexistent_pkg\n")
    findings = scan_file(f)
    assert len(findings) == 1
    assert "Verify" in findings[0].fix


# 0.7.1 ADR-105: pure-filesystem check (no import side effects).
def test_hallucination_no_import_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drop a fake package directory + .pth on sys.path with side-effect
    code in __init__.py. ``_is_available`` must NOT execute it — the gate
    is meant to scan LLM-generated code, never run it."""
    from harness_maker.secscan.hallucination import _is_available

    # Clear lru_cache so prior tests' lookups don't poison this one.
    _is_available.cache_clear()

    fake_root = tmp_path / "fake-root"
    fake_root.mkdir()
    (fake_root / "side_effect_pkg").mkdir()
    sentinel = tmp_path / "side_effect_fired.txt"
    (fake_root / "side_effect_pkg" / "__init__.py").write_text(
        f"import pathlib\npathlib.Path({sentinel!r}).write_text('fired')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(fake_root))

    found = _is_available("side_effect_pkg")
    assert found is True  # dir exists → filesystem check passes
    assert not sentinel.exists(), (
        "_is_available executed __init__.py — pure filesystem check is broken"
    )


# 0.7.1 Code F7: guarded except handlers also tag P2.
def test_guarded_import_in_except_handler(tmp_path: Path) -> None:
    """``except ImportError: import alt`` is a guarded fallback — the
    fallback import inside the handler must be tagged P2 (guarded), not
    P0 (hallucinated)."""
    f = _write_py(
        tmp_path / "guarded.py",
        "try:\n"
        "    import primary_nonexistent_pkg\n"
        "except ImportError:\n"
        "    import fallback_nonexistent_pkg\n",
    )
    findings = scan_file(f)
    by_pkg = {fnd.evidence: fnd for fnd in findings}
    fallback = next(
        (f for f in findings if "fallback_nonexistent_pkg" in f.evidence),
        None,
    )
    assert fallback is not None, f"missing finding for fallback import: {by_pkg}"
    assert fallback.severity == "P2", (
        f"expected guarded P2 for fallback import, got {fallback.severity}"
    )
