"""Tests for the project Profiler."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness_maker import detection_cache
from harness_maker.models import Confidence
from harness_maker.profile import profile


def test_profile_python_cli_with_git(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / ".git").mkdir()
    p = profile(tmp_path)
    assert "python" in p.stack
    # No git binary available or empty repo → experiment
    assert p.lifecycle == "dormant"
    assert p.existing_dotclaude is False
    assert p.vault_member is False


def test_profile_no_manifests_returns_unknown(tmp_path: Path) -> None:
    p = profile(tmp_path)
    assert p.stack == ["unknown"]


def test_profile_no_git_lifecycle_experiment(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    p = profile(tmp_path)
    assert p.lifecycle == "dormant"
    assert "node" in p.stack


def test_profile_vault_member(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "obsidian.json").write_text("{}")
    p = profile(tmp_path)
    assert p.vault_member is True
    assert p.existing_dotclaude is True


def test_profile_existing_dotclaude_without_obsidian(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    p = profile(tmp_path)
    assert p.existing_dotclaude is True
    assert p.vault_member is False


def test_profile_scale_small_boundary(tmp_path: Path) -> None:
    # 49 files → small (< 50)
    for i in range(49):
        (tmp_path / f"f{i}.txt").touch()
    p = profile(tmp_path)
    assert p.scale == "small"


def test_profile_scale_medium_boundary(tmp_path: Path) -> None:
    # 50 files → medium (>= 50, <= 500)
    for i in range(50):
        (tmp_path / f"f{i}.txt").touch()
    p = profile(tmp_path)
    assert p.scale == "medium"


def test_profile_multi_stack_tauri(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\n")
    p = profile(tmp_path)
    assert "node" in p.stack
    assert "rust" in p.stack


def test_profile_cmake_stack(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("project(x)\n")
    p = profile(tmp_path)
    assert "cmake" in p.stack


def test_profile_go_stack(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module x\n")
    p = profile(tmp_path)
    assert "go" in p.stack


def test_profile_spec_only_true(tmp_path: Path) -> None:
    (tmp_path / "TECH_SPEC.md").write_text("# spec\n")
    p = profile(tmp_path)
    assert p.spec_only is True


def test_profile_spec_only_false_when_many_files(tmp_path: Path) -> None:
    (tmp_path / "TECH_SPEC.md").write_text("# spec\n")
    for i in range(10):
        (tmp_path / f"f{i}.txt").touch()
    p = profile(tmp_path)
    assert p.spec_only is False


def test_profile_ignores_node_modules(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    nm = tmp_path / "node_modules"
    nm.mkdir()
    for i in range(100):
        (nm / f"f{i}.txt").touch()
    p = profile(tmp_path)
    # node_modules should be ignored → only package.json (1 file) → small
    assert p.scale == "small"


# ---------------------------------------------------------------------------
# Phase 3: mechanical_checks detection
# ---------------------------------------------------------------------------


def test_detect_checks_pyproject_ruff(tmp_path: Path) -> None:
    """pyproject.toml with [tool.ruff] → detected_checks includes ruff."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    p = profile(tmp_path)
    assert any("ruff" in c for c in p.detected_checks)


def test_detect_checks_pyproject_mypy(tmp_path: Path) -> None:
    """pyproject.toml mentioning mypy → detected_checks includes mypy."""
    (tmp_path / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n")
    p = profile(tmp_path)
    assert any("mypy" in c for c in p.detected_checks)


def test_detect_checks_pyproject_pytest(tmp_path: Path) -> None:
    """pyproject.toml with [tool.pytest.*] block → detected_checks includes pytest.

    ADR-007 (v0.22.0): bare dependency listing does NOT trigger detection — the
    [tool.pytest.ini_options] block must be present. The pre-v0.22.0 behavior
    (string-match on "pytest") produced false positives on dep-listed-but-
    unconfigured repos (psf/requests reality-check).
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1"\n\n[tool.pytest.ini_options]\nminversion = "7"\n'
    )
    p = profile(tmp_path)
    assert any("pytest" in c for c in p.detected_checks)


def test_detect_checks_makefile_targets(tmp_path: Path) -> None:
    """Makefile with lint:/test: targets → detected_checks includes make lint/test."""
    (tmp_path / "Makefile").write_text("lint:\n\truff check .\ntest:\n\tpytest\n")
    p = profile(tmp_path)
    assert any("make lint" in c for c in p.detected_checks)
    assert any("make test" in c for c in p.detected_checks)


def test_detect_checks_empty_project(tmp_path: Path) -> None:
    """Project with no pyproject.toml or Makefile → empty detected_checks."""
    (tmp_path / "README.md").write_text("hello")
    p = profile(tmp_path)
    assert p.detected_checks == []


def test_detect_checks_cap_at_6(tmp_path: Path) -> None:
    """detected_checks is capped at 6 (ADR-007 v0.22.0, raised from 4 because the
    whitelist now spans Python + Rust + Node + Makefile and a polyglot repo
    can legitimately want more than 4 distinct check commands)."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 100\n"
        "[tool.mypy]\nstrict = true\n"
        "[tool.pytest.ini_options]\nminversion = '7'\n"
    )
    (tmp_path / "Makefile").write_text(
        "lint:\n\truff .\n"
        "test:\n\tpytest\n"
        "typecheck:\n\tmypy .\n"
        "check:\n\tall\n"
        "format:\n\truff format\n"
        "build:\n\tpython -m build\n"
    )
    p = profile(tmp_path)
    assert len(p.detected_checks) <= 6


# ---------------------------------------------------------------------------
# Phase 3 — stack granularity expansion (12+ stacks)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stack_name", "manifest_files"),
    [
        ("java", [("pom.xml", "<project/>")]),
        ("java", [("build.gradle", "// gradle")]),
        ("swift", [("Package.swift", "// swift package")]),
        ("dart", [("pubspec.yaml", "name: x\n")]),
        ("ruby", [("Gemfile", "source 'rubygems'\n")]),
        ("php", [("composer.json", "{}")]),
        ("elixir", [("mix.exs", "defmodule X do end")]),
        ("scala", [("build.sbt", 'name := "x"\n')]),
        ("zig", [("build.zig", "// zig build\n")]),
    ],
)
def test_profile_stack_detection_concrete_manifest(
    tmp_path: Path, stack_name: str, manifest_files: list[tuple[str, str]]
) -> None:
    """Concrete-filename manifests each map to their named stack."""
    for fname, body in manifest_files:
        (tmp_path / fname).write_text(body)
    p = profile(tmp_path)
    assert stack_name in p.stack


def test_profile_stack_kotlin_via_gradle_kts(tmp_path: Path) -> None:
    """build.gradle.kts triggers BOTH java and kotlin (PLAN: no precedence enforcement)."""
    (tmp_path / "build.gradle.kts").write_text("// kts build")
    p = profile(tmp_path)
    assert "kotlin" in p.stack
    assert "java" in p.stack


def test_profile_stack_csharp_via_csproj_glob(tmp_path: Path) -> None:
    """*.csproj glob match yields the `csharp` stack."""
    (tmp_path / "MyApp.csproj").write_text("<Project/>")
    p = profile(tmp_path)
    assert "csharp" in p.stack


def test_profile_stack_csharp_via_sln_glob(tmp_path: Path) -> None:
    """*.sln glob match yields the `csharp` stack."""
    (tmp_path / "MyApp.sln").write_text("Microsoft Visual Studio Solution File")
    p = profile(tmp_path)
    assert "csharp" in p.stack


def test_profile_stack_haskell_via_cabal_glob(tmp_path: Path) -> None:
    """*.cabal glob match yields the `haskell` stack."""
    (tmp_path / "myproj.cabal").write_text("name: myproj\n")
    p = profile(tmp_path)
    assert "haskell" in p.stack


def test_profile_stack_haskell_via_stack_yaml(tmp_path: Path) -> None:
    """stack.yaml yields the `haskell` stack."""
    (tmp_path / "stack.yaml").write_text("resolver: lts-22.0\n")
    p = profile(tmp_path)
    assert "haskell" in p.stack


def test_profile_stack_c_cpp_via_makefile(tmp_path: Path) -> None:
    """Makefile yields the `c-cpp` stack."""
    (tmp_path / "Makefile").write_text("all:\n\tgcc -o x x.c\n")
    p = profile(tmp_path)
    assert "c-cpp" in p.stack


def test_profile_stack_c_cpp_via_meson(tmp_path: Path) -> None:
    """meson.build yields the `c-cpp` stack."""
    (tmp_path / "meson.build").write_text("project('x', 'c')\n")
    p = profile(tmp_path)
    assert "c-cpp" in p.stack


def test_profile_stack_cmake_and_c_cpp_coexist(tmp_path: Path) -> None:
    """CMakeLists.txt triggers BOTH cmake (existing) and c-cpp (new) — same-file collision OK."""
    (tmp_path / "CMakeLists.txt").write_text("project(x)\n")
    p = profile(tmp_path)
    assert "cmake" in p.stack
    assert "c-cpp" in p.stack


# ---------------------------------------------------------------------------
# Phase 3 — framework detection via dep parsing
# ---------------------------------------------------------------------------


def test_python_frameworks_detected_from_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["fastapi>=0.100", "pydantic~=2.0"]\n'
    )
    p = profile(tmp_path)
    assert "fastapi" in p.frameworks
    assert "pydantic" in p.frameworks


def test_python_frameworks_detected_from_poetry_table(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "x"\n\n'
        "[tool.poetry.dependencies]\n"
        'python = "^3.12"\n'
        'django = "^5.0"\n'
        'httpx = "^0.27"\n'
    )
    p = profile(tmp_path)
    assert "django" in p.frameworks
    assert "httpx" in p.frameworks


def test_python_framework_with_extras_stripped(tmp_path: Path) -> None:
    """`fastapi[all]==0.111` must still match `fastapi`."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["fastapi[all]==0.111"]\n'
    )
    p = profile(tmp_path)
    assert "fastapi" in p.frameworks


def test_node_frameworks_detected_from_package_json(tmp_path: Path) -> None:
    pkg = {
        "name": "x",
        "dependencies": {"react": "^18.0.0", "vite": "^5.0.0"},
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    p = profile(tmp_path)
    assert "react" in p.frameworks
    assert "vite" in p.frameworks


def test_node_frameworks_detected_from_dev_dependencies(tmp_path: Path) -> None:
    pkg = {"name": "x", "devDependencies": {"vite": "^5.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    p = profile(tmp_path)
    assert "vite" in p.frameworks


def test_node_scoped_packages_detected(tmp_path: Path) -> None:
    """Real-world npm scoped packages (@nestjs/core, @remix-run/node) match."""
    pkg = tmp_path / "package.json"
    pkg.write_text(
        json.dumps(
            {
                "dependencies": {
                    "@nestjs/core": "^10.0.0",
                    "@nestjs/common": "^10.0.0",
                    "@remix-run/node": "^2.0.0",
                    "@remix-run/react": "^2.0.0",
                }
            }
        )
    )
    p = profile(tmp_path)
    assert "nestjs" in p.frameworks
    assert "remix" in p.frameworks


def test_node_unscoped_lookalike_does_not_match_scoped_framework(tmp_path: Path) -> None:
    """`nestjs-helper-unrelated` (no @ prefix) must NOT false-match `nestjs`.

    Scope-prefix guard requires the leading `@` — bare hyphen-prefixed names
    are unrelated user packages.
    """
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"dependencies": {"nestjs-helper-unrelated": "^1.0.0"}}))
    p = profile(tmp_path)
    assert "nestjs" not in p.frameworks


def test_rust_frameworks_detected_from_cargo_toml(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "x"\nversion = "0.1.0"\n\n'
        "[dependencies]\n"
        'tokio = { version = "1", features = ["full"] }\n'
        'axum = "0.7"\n'
    )
    p = profile(tmp_path)
    assert "tokio" in p.frameworks
    assert "axum" in p.frameworks


def test_frameworks_empty_when_no_deps(tmp_path: Path) -> None:
    """Manifest exists but no recognized deps → empty frameworks list."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = []\n')
    p = profile(tmp_path)
    assert p.frameworks == []


def test_frameworks_unreadable_pyproject_graceful(tmp_path: Path) -> None:
    """Malformed pyproject.toml does not raise — empty frameworks."""
    (tmp_path / "pyproject.toml").write_text("this is not toml [[[ bad\n")
    p = profile(tmp_path)
    assert p.frameworks == []
    assert "python" in p.stack  # still detected via existence


def test_frameworks_malformed_package_json_graceful(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{not json")
    p = profile(tmp_path)
    assert p.frameworks == []
    assert "node" in p.stack


# ---------------------------------------------------------------------------
# Phase 3 — package_manager detection
# ---------------------------------------------------------------------------


def test_package_manager_detected_python_uv(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "uv.lock").write_text("# lock")
    p = profile(tmp_path)
    assert p.package_manager == "uv"


def test_package_manager_detected_python_poetry(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='x'\n")
    (tmp_path / "poetry.lock").write_text("# lock")
    p = profile(tmp_path)
    assert p.package_manager == "poetry"


def test_package_manager_detected_python_pip(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("pytest\n")
    p = profile(tmp_path)
    assert p.package_manager == "pip"


def test_package_manager_detected_node_pnpm(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 6.0\n")
    p = profile(tmp_path)
    assert p.package_manager == "pnpm"


def test_package_manager_node_precedence_bun_over_pnpm(tmp_path: Path) -> None:
    """bun > pnpm > yarn > npm."""
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "bun.lockb").write_text("")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    p = profile(tmp_path)
    assert p.package_manager == "bun"


def test_package_manager_detected_bun_text_format(tmp_path: Path) -> None:
    """Bun 1.1+ uses bun.lock (TOML text format) instead of bun.lockb."""
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "bun.lock").write_text("# bun lockfile")
    p = profile(tmp_path)
    assert p.package_manager == "bun"


def test_package_manager_detected_rust_cargo(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\nversion='0.1.0'\n")
    (tmp_path / "Cargo.lock").write_text("# cargo lock")
    p = profile(tmp_path)
    assert p.package_manager == "cargo"


def test_package_manager_monorepo_python_wins_over_node(tmp_path: Path) -> None:
    """Cross-stack precedence: python > node > rust > other."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    p = profile(tmp_path)
    assert p.package_manager == "uv"


def test_package_manager_manifest_fallback_pip(tmp_path: Path) -> None:
    """ADR-007 manifest-fallback exception (v0.22.0): pyproject.toml without
    [tool.uv]/[tool.poetry] and no lockfile → "pip" default. Pre-v0.22.0 this
    returned "" but reality-check on psf/requests showed users wanted *some*
    package_manager signal for documentation hint rather than empty string."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    p = profile(tmp_path)
    assert p.package_manager == "pip"


def test_package_manager_empty_when_no_manifest(tmp_path: Path) -> None:
    """Empty repo (no pyproject.toml, no package.json, no Cargo.toml) → "".

    The empty-string return is still valid when there is genuinely no manifest
    signal. ADR-007 manifest-fallback only kicks in when a manifest IS present.
    """
    p = profile(tmp_path)
    assert p.package_manager == ""


# ---------------------------------------------------------------------------
# Phase 3 — ci_provider detection
# ---------------------------------------------------------------------------


def test_ci_provider_github_actions(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: ci\n")
    p = profile(tmp_path)
    assert p.ci_provider == "github-actions"


def test_ci_provider_github_actions_yaml_suffix(tmp_path: Path) -> None:
    """Either .yml or .yaml suffix counts."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yaml").write_text("name: ci\n")
    p = profile(tmp_path)
    assert p.ci_provider == "github-actions"


def test_ci_provider_github_actions_empty_dir_does_not_match(tmp_path: Path) -> None:
    """Empty .github/workflows/ should NOT count as github-actions."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    p = profile(tmp_path)
    assert p.ci_provider == ""


def test_ci_provider_gitlab_ci(tmp_path: Path) -> None:
    (tmp_path / ".gitlab-ci.yml").write_text("stages: []\n")
    p = profile(tmp_path)
    assert p.ci_provider == "gitlab-ci"


def test_ci_provider_circleci(tmp_path: Path) -> None:
    cc = tmp_path / ".circleci"
    cc.mkdir()
    (cc / "config.yml").write_text("version: 2.1\n")
    p = profile(tmp_path)
    assert p.ci_provider == "circleci"


def test_ci_provider_jenkins(tmp_path: Path) -> None:
    (tmp_path / "Jenkinsfile").write_text("pipeline {}\n")
    p = profile(tmp_path)
    assert p.ci_provider == "jenkins"


def test_ci_provider_travis(tmp_path: Path) -> None:
    (tmp_path / ".travis.yml").write_text("language: python\n")
    p = profile(tmp_path)
    assert p.ci_provider == "travis"


def test_ci_provider_empty_when_no_signal(tmp_path: Path) -> None:
    p = profile(tmp_path)
    assert p.ci_provider == ""


# ---------------------------------------------------------------------------
# Phase 3 — detection_confidence per signal
# ---------------------------------------------------------------------------


def test_detection_confidence_high_when_manifest_match(tmp_path: Path) -> None:
    """A real manifest → stack=HIGH and other matched signals HIGH too."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = ["fastapi"]\n')
    (tmp_path / "uv.lock").write_text("")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: ci\n")

    p = profile(tmp_path)
    assert p.detection_confidence["stack"] == Confidence.HIGH
    assert p.detection_confidence["frameworks"] == Confidence.HIGH
    assert p.detection_confidence["package_manager"] == Confidence.HIGH
    assert p.detection_confidence["ci_provider"] == Confidence.HIGH


def test_detection_confidence_low_when_no_manifest(tmp_path: Path) -> None:
    """Empty project — all four signals LOW."""
    p = profile(tmp_path)
    assert p.detection_confidence["stack"] == Confidence.LOW
    assert p.detection_confidence["frameworks"] == Confidence.LOW
    assert p.detection_confidence["package_manager"] == Confidence.LOW
    assert p.detection_confidence["ci_provider"] == Confidence.LOW


def test_foreign_ai_configs_always_empty_in_phase_3(tmp_path: Path) -> None:
    """Phase 5 owns foreign-AI-config detection; Phase 3 must leave it empty."""
    (tmp_path / "AGENTS.md").write_text("# agents\n")
    (tmp_path / "CLAUDE.md").write_text("# claude\n")
    p = profile(tmp_path)
    assert p.foreign_ai_configs == []


# ---------------------------------------------------------------------------
# Phase 3 — detection_cache wiring
# ---------------------------------------------------------------------------


def test_profile_uses_cache_on_second_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second call with no manifest mtime change returns cached profile."""
    cache_dir = tmp_path / "cache"
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n")

    p1 = profile(repo, cache_dir=cache_dir)
    assert "python" in p1.stack

    # Sentinel: replace the inner detector to ensure a cache hit short-circuits.
    sentinel_calls = {"count": 0}

    def _boom(*_a: object, **_kw: object) -> list[str]:
        sentinel_calls["count"] += 1
        return []

    monkeypatch.setattr("harness_maker.profile._detect_frameworks", _boom)
    p2 = profile(repo, cache_dir=cache_dir)
    assert sentinel_calls["count"] == 0  # framework detection NEVER ran
    assert p2.stack == p1.stack


def test_profile_cache_invalidated_on_manifest_mtime_bump(tmp_path: Path) -> None:
    """Touching the manifest later than the cache file forces a fresh detection."""
    cache_dir = tmp_path / "cache"
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = repo / "pyproject.toml"
    manifest.write_text('[project]\nname = "x"\ndependencies = []\n')

    p1 = profile(repo, cache_dir=cache_dir)
    assert p1.frameworks == []

    # Rewrite with a framework dep and bump mtime past the cache.
    manifest.write_text('[project]\nname = "x"\ndependencies = ["fastapi"]\n')
    cache_file = cache_dir / f"profile-{detection_cache._repo_hash(repo)}.json"
    future = cache_file.stat().st_mtime + 100.0
    os.utime(manifest, (future, future))

    p2 = profile(repo, cache_dir=cache_dir)
    assert "fastapi" in p2.frameworks


# ---------------------------------------------------------------------------
# Phase 3 — legacy backward compatibility
# ---------------------------------------------------------------------------


def test_profile_legacy_signals_unchanged(tmp_path: Path) -> None:
    """Reproduce the baseline `test_profile_python_cli_with_git` fixture exactly.

    Phase 3 must not alter the seven pre-existing signals. Any change here
    means the legacy contract drifted and downstream callers may break.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / ".git").mkdir()
    p = profile(tmp_path)
    assert "python" in p.stack
    assert p.lifecycle == "dormant"
    assert p.existing_dotclaude is False
    assert p.vault_member is False
    assert p.spec_only is False
    assert p.scale == "small"


# ---------------------------------------------------------------------------
# Phase 3 — dogfood: profile() on the harness-maker repo itself
# ---------------------------------------------------------------------------


def _find_repo_root(start: Path) -> Path | None:
    """Walk up looking for a directory that contains both pyproject.toml and src/harness_maker/."""
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").exists() and (
            candidate / "src" / "harness_maker"
        ).is_dir():
            return candidate
    return None


def test_profile_dogfood_on_harness_maker_repo(tmp_path: Path) -> None:
    """Run profile() on the harness-maker repo itself and check core signals.

    Skips when the expected env is missing (e.g. an installed wheel rather
    than a source checkout). When present, asserts the pieces of the
    expected env that ARE present — `.github/workflows/` was deliberately
    removed from this repo (see commit 565d7ce), so ci_provider is only
    asserted when the directory exists.
    """
    repo_root = _find_repo_root(Path(__file__).resolve())
    if repo_root is None:
        pytest.skip("not running inside a harness-maker source checkout")
    if not (repo_root / "uv.lock").exists():
        pytest.skip("uv.lock missing — not the expected dev env")

    p = profile(repo_root, cache_dir=tmp_path / "dogfood-cache")

    assert "python" in p.stack, f"expected python in stack, got {p.stack}"
    assert p.package_manager == "uv", f"expected uv, got {p.package_manager!r}"

    gh_workflows = repo_root / ".github" / "workflows"
    has_workflow_files = gh_workflows.is_dir() and any(
        entry.is_file() and entry.suffix in {".yml", ".yaml"} for entry in gh_workflows.iterdir()
    )
    if has_workflow_files:
        assert p.ci_provider == "github-actions"
    else:
        # The harness-maker repo currently has no .github/workflows/ (commit
        # 565d7ce). Detector must report empty — never fabricate.
        assert p.ci_provider == ""


# ─────────────────────────────────────────────────────────────────────────────
# ADR-006 / ADR-007 (v0.22.0) — lifecycle 3-tier + detect_checks whitelist
# ─────────────────────────────────────────────────────────────────────────────


def test_lifecycle_no_git_returns_dormant(tmp_path: Path) -> None:
    """No .git → dormant (was "experiment" pre-v0.22.0, ADR-006)."""
    from harness_maker.profile import _detect_lifecycle

    assert _detect_lifecycle(tmp_path) == "dormant"


def test_lifecycle_active_for_ten_or_more_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """≥10 commits in last 30d → active. ADR-006 threshold."""
    import subprocess

    from harness_maker import profile as profile_mod

    (tmp_path / ".git").mkdir()

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        # 12 commits worth of oneline output
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="x\n" * 12, stderr="")

    monkeypatch.setattr(profile_mod.subprocess, "run", fake_run)
    assert profile_mod._detect_lifecycle(tmp_path) == "active"


def test_lifecycle_maintenance_for_partial_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """1-9 commits in last 30d → maintenance."""
    import subprocess

    from harness_maker import profile as profile_mod

    (tmp_path / ".git").mkdir()

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="x\n" * 5, stderr="")

    monkeypatch.setattr(profile_mod.subprocess, "run", fake_run)
    assert profile_mod._detect_lifecycle(tmp_path) == "maintenance"


def test_lifecycle_dormant_for_zero_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """0 commits in last 30d → dormant (was "experiment" pre-v0.22.0)."""
    import subprocess

    from harness_maker import profile as profile_mod

    (tmp_path / ".git").mkdir()

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(profile_mod.subprocess, "run", fake_run)
    assert profile_mod._detect_lifecycle(tmp_path) == "dormant"


def test_lifecycle_subprocess_failure_returns_dormant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subprocess error → dormant (most conservative fallback, ADR-006)."""
    import subprocess

    from harness_maker import profile as profile_mod

    (tmp_path / ".git").mkdir()

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.SubprocessError("git timed out")

    monkeypatch.setattr(profile_mod.subprocess, "run", fake_run)
    assert profile_mod._detect_lifecycle(tmp_path) == "dormant"


def test_detected_checks_rust_cargo_whitelist(tmp_path: Path) -> None:
    """Cargo.toml present → cargo test + clippy + fmt --check. ADR-007 whitelist."""
    from harness_maker.profile import _detect_mechanical_checks

    (tmp_path / "Cargo.toml").write_text('[package]\nname = "x"\nversion = "0.1.0"\n')
    checks = _detect_mechanical_checks(tmp_path)
    assert "cargo test" in checks
    assert "cargo clippy" in checks
    assert "cargo fmt --check" in checks


def test_detected_checks_node_scripts_whitelist(tmp_path: Path) -> None:
    """package.json scripts → npm run <whitelisted-key>. ADR-007."""
    from harness_maker.profile import _detect_mechanical_checks

    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "jest", "lint": "eslint .", "irrelevant": "echo skip"}}'
    )
    checks = _detect_mechanical_checks(tmp_path)
    assert "npm run test" in checks
    assert "npm run lint" in checks
    assert "npm run irrelevant" not in checks  # not in whitelist


def test_detected_checks_node_pnpm_runner(tmp_path: Path) -> None:
    """pnpm-lock.yaml present → runner is pnpm."""
    from harness_maker.profile import _detect_mechanical_checks

    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    (tmp_path / "pnpm-lock.yaml").write_text("")
    checks = _detect_mechanical_checks(tmp_path)
    assert "pnpm run test" in checks
    assert "npm run test" not in checks


def test_detected_checks_python_no_false_positive_on_dep_listing(tmp_path: Path) -> None:
    """ADR-007: bare "mypy"/"pytest" in deps must NOT trigger detection.

    Pre-v0.22.0 had bare-string `"mypy" in content` / `"pytest" in content`
    matching, which emitted false positives on dep-listed-but-unconfigured
    tools. v0.22.0 requires [tool.X] block explicitly.
    """
    from harness_maker.profile import _detect_mechanical_checks

    # Has only dep mentions, no [tool.X] blocks
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1"\ndependencies = ["mypy", "pytest", "ruff"]\n'
    )
    checks = _detect_mechanical_checks(tmp_path)
    assert "uv run ruff check ." not in checks
    assert "uv run mypy ." not in checks
    assert "uv run pytest --tb=short -q" not in checks


def test_detected_checks_python_strict_block_match_positive(tmp_path: Path) -> None:
    """[tool.ruff] / [tool.mypy] / [tool.pytest.*] blocks → respective check emitted."""
    from harness_maker.profile import _detect_mechanical_checks

    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 100\n\n"
        "[tool.mypy]\nstrict = true\n\n"
        '[tool.pytest.ini_options]\nminversion = "7"\n'
    )
    checks = _detect_mechanical_checks(tmp_path)
    assert "uv run ruff check ." in checks
    assert "uv run mypy ." in checks
    assert "uv run pytest --tb=short -q" in checks


def test_package_manager_python_manifest_fallback(tmp_path: Path) -> None:
    """pyproject.toml without lockfile → infer from header (ADR-007 exception)."""
    from harness_maker.profile import _python_package_manager

    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n")
    assert _python_package_manager(tmp_path) == "uv"


def test_package_manager_node_manifest_fallback(tmp_path: Path) -> None:
    """package.json without lockfile → "npm" default (ADR-007 exception)."""
    from harness_maker.profile import _node_package_manager

    (tmp_path / "package.json").write_text("{}")
    assert _node_package_manager(tmp_path) == "npm"


def test_package_manager_python_default_pip_when_no_uv_or_poetry_block(tmp_path: Path) -> None:
    """pyproject.toml without [tool.uv]/[tool.poetry] → "pip" fallback."""
    from harness_maker.profile import _python_package_manager

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert _python_package_manager(tmp_path) == "pip"
