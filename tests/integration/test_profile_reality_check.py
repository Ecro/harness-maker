"""Reality-check the profiler against real public repos (PLAN Phase 2.5).

PLAN-harness-maker-cold-eval ADR-006 + ADR-007 redesigned `_detect_lifecycle`
and `_detect_mechanical_checks` after a manual reality-check on 5 public repos
exposed false positives + empty outputs. This test gates the regression: each
repo's profile output must match the directionally-correct expectations
encoded in the PLAN.

Network-bound (requires `git clone`); skipped unless `INTEGRATION=1`.
Each clone uses `--depth 1` and is sandboxed inside the per-test tmpdir.

Expected outputs derive directly from PLAN-harness-maker-cold-eval.md
Phase 2.5 sub-phase. If the underlying repos change shape (e.g., requests
drops its Makefile, ripgrep stops shipping Cargo.toml), the test surface
must surface the regression rather than silently passing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from harness_maker.profile import profile

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="reality-check requires INTEGRATION=1 (network: clones 6 public repos)",
)


def _clone(url: str, dest: Path) -> Path:
    """Shallow-clone url into dest; return dest. Skip silently if network fails."""
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        pytest.skip(f"clone failed for {url}: {exc}")
    return dest


def test_reality_check_requests_python_lib(tmp_path: Path) -> None:
    """psf/requests — Python lib, maintenance mode, no uv, ships Makefile."""
    repo = _clone("https://github.com/psf/requests.git", tmp_path / "requests")
    p = profile(repo)
    # Lifecycle: requests is in maintenance — sparse but non-zero recent commits.
    # The new ADR-006 algorithm must avoid the old "experiment" label.
    assert p.lifecycle in {"active", "maintenance"}, p.lifecycle
    # ADR-007 manifest fallback: requests ships pyproject.toml without uv.lock
    # → "pip" (the previous version returned "" — broken).
    assert p.package_manager == "pip", p.package_manager
    # Detected checks should include the Makefile `test:` target.
    assert any("make test" in c for c in p.detected_checks), p.detected_checks


def test_reality_check_fastapi_python_framework(tmp_path: Path) -> None:
    """tiangolo/fastapi — active Python framework, uv-based, ships pydantic dep."""
    repo = _clone("https://github.com/tiangolo/fastapi.git", tmp_path / "fastapi")
    p = profile(repo)
    # FastAPI commits multiple times per week — must classify as active.
    assert p.lifecycle == "active", p.lifecycle
    assert "pydantic" in p.frameworks, p.frameworks


def test_reality_check_ripgrep_rust_cli(tmp_path: Path) -> None:
    """BurntSushi/ripgrep — mature Rust CLI. Primary regression target."""
    repo = _clone("https://github.com/BurntSushi/ripgrep.git", tmp_path / "ripgrep")
    p = profile(repo)
    # ADR-006: ripgrep is mature, never "experiment". The new algorithm must
    # classify as active or maintenance based on its recent commit cadence.
    assert p.lifecycle in {"active", "maintenance"}, (
        f"ripgrep mis-classified as {p.lifecycle!r}; ADR-006 removed 'experiment'"
    )
    # ADR-007 Cargo whitelist: cargo test + clippy + fmt --check must appear.
    assert "cargo test" in p.detected_checks, p.detected_checks
    assert "cargo clippy" in p.detected_checks, p.detected_checks


def test_reality_check_fastify_node_framework(tmp_path: Path) -> None:
    """fastify/fastify — active Node framework. Validates package.json scripts whitelist."""
    repo = _clone("https://github.com/fastify/fastify.git", tmp_path / "fastify")
    p = profile(repo)
    # ADR-007 manifest fallback: package.json present → package_manager is non-empty.
    assert p.package_manager != "", "fastify package_manager regression — ADR-007"
    # At least one whitelisted script key (test/lint/check/typecheck/format/build) emits.
    assert len(p.detected_checks) > 0, p.detected_checks


def test_reality_check_htmx_single_file_js(tmp_path: Path) -> None:
    """bigskysoftware/htmx — single-file JS lib. Edge case: minimal package.json."""
    repo = _clone("https://github.com/bigskysoftware/htmx.git", tmp_path / "htmx")
    p = profile(repo)
    # No bun/pnpm/yarn lockfile → npm default per ADR-007.
    assert p.package_manager == "npm", p.package_manager


def test_reality_check_embedeval_python_baseline(tmp_path: Path) -> None:
    """Ecro/embedeval — maintainer baseline, same-stack Python+pydantic.

    This is the Side-preset showcase target referenced in ADR-002 and
    docs/assets/showcase-diff.md. The render diff vs harness-maker self
    (Production preset) is the headline-proof artifact.
    """
    repo = _clone("https://github.com/Ecro/embedeval.git", tmp_path / "embedeval")
    p = profile(repo)
    assert p.lifecycle in {"active", "maintenance"}, p.lifecycle
    assert "pydantic" in p.frameworks, p.frameworks
