"""Package artifact regression tests — wheel and sdist must ship runtime templates.

Gated by ``INTEGRATION=1`` per CLAUDE.md §테스트 정책. The ``uv build``
subprocess costs ~3 minutes and pulls dependencies from the registry, so
this lives in the integration tier rather than the unit suite — the regular
``pytest`` invocation stays fast and offline.
"""

from __future__ import annotations

import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

_INTEGRATION_ENABLED = os.environ.get("INTEGRATION") == "1"

# Representative runtime assets that must reach the published wheel/sdist.
# Each entry is a substring match against the archive member names — the build
# backend prefixes wheel members with the package directory
# (``harness_maker/templates/...``) and sdist members with the project-version
# directory (``harness_maker-<X.Y.Z>/src/harness_maker/templates/...``).
_REQUIRED_TEMPLATE_PATHS = (
    "harness_maker/templates/agents/code-reviewer.md.j2",
    "harness_maker/templates/stages/plan.md.j2",
    "harness_maker/templates/rubrics/agent_prompt.yaml.j2",
    "harness_maker/templates/skills/verify-before-completion/SKILL.md.j2",
    "harness_maker/templates/commands/hm/configure.md.j2",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not _INTEGRATION_ENABLED,
    reason="INTEGRATION=1 required — uv build is slow + network-dependent",
)


def _build_dists(out_dir: Path) -> tuple[Path, Path]:
    """Build wheel and sdist into ``out_dir`` via ``uv build``."""
    subprocess.run(
        ["uv", "build", "--out-dir", str(out_dir)],
        cwd=str(_REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    wheels = list(out_dir.glob("*.whl"))
    sdists = list(out_dir.glob("*.tar.gz"))
    assert len(wheels) == 1, f"expected exactly one wheel in {out_dir}, got {wheels}"
    assert len(sdists) == 1, f"expected exactly one sdist in {out_dir}, got {sdists}"
    return wheels[0], sdists[0]


@pytest.fixture(scope="session")
def built_artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build wheel + sdist once per session — the artifacts are read-only.

    Session scope keeps the 3-minute ``uv build`` from re-running if a future
    artifact-test module imports the same fixture via ``conftest.py``.
    """
    out = tmp_path_factory.mktemp("dist")
    return _build_dists(out)


@pytest.mark.parametrize("template_path", _REQUIRED_TEMPLATE_PATHS)
def test_wheel_includes_template(built_artifacts: tuple[Path, Path], template_path: str) -> None:
    """Each runtime template must be inside the wheel — installs depend on them."""
    wheel, _ = built_artifacts
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert any(template_path in n for n in names), (
        f"wheel {wheel.name} missing template {template_path!r}\nsample members: {names[:10]}"
    )


def test_wheel_excludes_pycache(built_artifacts: tuple[Path, Path]) -> None:
    """``__pycache__`` directories must never reach the wheel."""
    wheel, _ = built_artifacts
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    leaked = [n for n in names if "__pycache__" in n]
    assert not leaked, f"wheel leaked __pycache__ entries: {leaked[:5]}"


@pytest.mark.parametrize("template_path", _REQUIRED_TEMPLATE_PATHS)
def test_sdist_includes_template(built_artifacts: tuple[Path, Path], template_path: str) -> None:
    """Sdist mirrors the wheel — required so source rebuilds reproduce the package."""
    _, sdist = built_artifacts
    # Sdist paths are prefixed by the project name + version, e.g. ``harness_maker-0.13.1/src/...``.
    needle = f"src/{template_path}"
    with tarfile.open(sdist, "r:gz") as tf:
        names = tf.getnames()
    assert any(needle in n for n in names), (
        f"sdist {sdist.name} missing template {needle!r}\nsample members: {names[:10]}"
    )


def test_sdist_excludes_pycache(built_artifacts: tuple[Path, Path]) -> None:
    """Same ``__pycache__`` ban applies to sdist."""
    _, sdist = built_artifacts
    with tarfile.open(sdist, "r:gz") as tf:
        names = tf.getnames()
    leaked = [n for n in names if "__pycache__" in n]
    assert not leaked, f"sdist leaked __pycache__ entries: {leaked[:5]}"
