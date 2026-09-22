"""Release identity is enforced at local prepublish and remote postpublish boundaries."""

from __future__ import annotations

import builtins
import importlib
import json
import sys
import time
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker.release_identity import (
    RemoteStatus,
    classify_remote_versions,
    fetch_remote_identity,
    prepublish_identity,
)
from harness_maker.spec_machine import GoldenRow, load_golden_table

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = _ROOT / "specs/SPEC-docs-release-sync.machine.yaml"
_REMOTE_ROWS = load_golden_table(_SPEC, "AC-008")
_VERSION_PATHS = (
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "pyproject.toml",
    "src/harness_maker/__init__.py",
)
_DOCUMENT_PATHS = (
    "README.md",
    "README.ko.md",
    "docs/HOW-IT-WORKS.md",
    "docs/HOW-IT-WORKS.ko.md",
)
_GITHUB_URL = "https://api.github.com/repos/Ecro/harness-maker/releases/tags/v1.2.3"
_PYPI_URL = "https://pypi.org/pypi/harness-maker/1.2.3/json"


def _release_tree(tmp_path: Path, version: str = "1.2.3") -> Path:
    for relative in _VERSION_PATHS[:3]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": version}), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "fixture"\nversion = "{version}"\n', encoding="utf-8"
    )
    runtime = tmp_path / "src/harness_maker/__init__.py"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    for relative in _DOCUMENT_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"> **Version**: {version}\n", encoding="utf-8")
    return tmp_path


def _replace_version(root: Path, relative: str, version: str) -> None:
    path = root / relative
    if relative.endswith("plugin.json"):
        path.write_text(json.dumps({"version": version}), encoding="utf-8")
    elif relative == "pyproject.toml":
        path.write_text(f'[project]\nname = "fixture"\nversion = "{version}"\n', encoding="utf-8")
    elif relative == "src/harness_maker/__init__.py":
        path.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    else:
        path.write_text(f"> **Version**: {version}\n", encoding="utf-8")


@pytest.mark.parametrize("mismatch_path", ["tag", *_VERSION_PATHS, *_DOCUMENT_PATHS])
def test_s3_ac_004_prepublish_identity_is_local_and_blocking(
    tmp_path: Path, mismatch_path: str
) -> None:
    root = _release_tree(tmp_path)
    result = prepublish_identity("v1.2.3", root)
    assert result.ok
    assert result.exit_code == 0
    assert tuple(result.source_versions) == _VERSION_PATHS
    assert tuple(result.document_versions) == _DOCUMENT_PATHS

    if mismatch_path == "tag":
        mismatch = prepublish_identity("v1.2.2", root)
        assert set(mismatch.mismatches) == {*_VERSION_PATHS, *_DOCUMENT_PATHS}
    else:
        _replace_version(root, mismatch_path, "1.2.2")
        mismatch = prepublish_identity("v1.2.3", root)
        assert mismatch.mismatches == {mismatch_path: "1.2.2"}
    assert not mismatch.ok
    assert mismatch.exit_code != 0


def test_s3_ac_003_prepublish_identity_imports_no_network_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals_: Mapping[str, object] | None = None,
        locals_: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> Any:
        if name.split(".", 1)[0] in {"httpx", "requests", "socket", "urllib"}:
            raise AssertionError(f"prepublish imported network dependency {name}")
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop("harness_maker.release_identity", None)
    isolated = importlib.import_module("harness_maker.release_identity")
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert isolated.prepublish_identity(f"v{project['project']['version']}", _ROOT).ok


@pytest.mark.parametrize(
    "row",
    _REMOTE_ROWS,
    ids=[f"remote-{index}" for index, _ in enumerate(_REMOTE_ROWS)],
)
def test_s3_ac_008_remote_identity_classifies_golden_cases(row: GoldenRow) -> None:
    inputs = row.input
    result = classify_remote_versions(
        tagged_source=str(inputs["tagged_source"]),
        github=str(inputs["github"]),
        pypi=str(inputs["pypi"]),
    )
    assert result.status is RemoteStatus(str(row.expected))
    assert result.exit_code == (0 if row.expected == "match" else 1)


def test_s3_ac_008_remote_identity_rejects_github_only_mismatch() -> None:
    result = classify_remote_versions(tagged_source="1.2.3", github="1.2.2", pypi="1.2.3")
    assert result.status is RemoteStatus.MISMATCH
    assert result.exit_code != 0


@pytest.mark.parametrize(
    ("github_payload", "pypi_payload", "expected_urls"),
    [
        ({}, {"info": {"version": "1.2.3"}}, [_GITHUB_URL]),
        ({"tag_name": "v1.2.3"}, {"info": {}}, [_GITHUB_URL, _PYPI_URL]),
    ],
)
def test_s3_ac_008_remote_identity_rejects_malformed_payloads(
    github_payload: dict[str, object],
    pypi_payload: dict[str, object],
    expected_urls: list[str],
) -> None:
    responses = iter([github_payload, pypi_payload])
    seen: list[tuple[str, float]] = []

    def opener(url: str, timeout: float) -> dict[str, object]:
        seen.append((url, timeout))
        return next(responses)

    result = fetch_remote_identity("1.2.3", opener=opener, retries=1, timeout=5)
    assert seen == [(url, 5) for url in expected_urls]
    assert result.status is RemoteStatus.UNAVAILABLE
    assert result.exit_code != 0


def test_s3_ac_008_remote_identity_classifies_request_failure_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    sleeps: list[float] = []

    def opener(url: str, timeout: float) -> dict[str, object]:
        calls.append(url)
        raise TimeoutError("fixture timeout")

    monkeypatch.setattr(time, "sleep", sleeps.append)
    result = fetch_remote_identity("1.2.3", opener=opener, retries=2, timeout=5)
    assert calls == [_GITHUB_URL, _GITHUB_URL]
    assert sleeps == [1]
    assert result.status is RemoteStatus.UNAVAILABLE
    assert result.exit_code != 0


def test_s3_cli_propagates_prepublish_mismatch_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import harness_maker.release_identity as release_identity

    root = _release_tree(tmp_path)
    assert release_identity.main(["prepublish", "--tag", "v1.2.2", "--root", str(root)]) != 0
    assert json.loads(capsys.readouterr().out)["status"] == "mismatch"


def test_s3_cli_propagates_postpublish_unavailable_exit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import harness_maker.release_identity as release_identity

    unavailable = release_identity.RemoteResult(
        release_identity.RemoteStatus.UNAVAILABLE,
        "1.2.3",
        None,
        None,
        "fixture unavailable",
    )
    monkeypatch.setattr(
        release_identity, "fetch_remote_identity", lambda *args, **kwargs: unavailable
    )
    assert release_identity.main(["postpublish", "--tag", "v1.2.3"]) != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unavailable"
    assert payload["detail"] == "fixture unavailable"


def test_s3_release_workflow_enforces_both_identity_boundaries() -> None:
    workflow = yaml.safe_load((_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    quality_steps = jobs["quality-gate"]["steps"]
    local = [step for step in quality_steps if step.get("name") == "Verify local release identity"]
    assert len(local) == 1
    assert local[0]["run"] == (
        "uv run python -m harness_maker.release_identity prepublish "
        '--tag "$GITHUB_REF_NAME" --root .'
    )
    assert local[0]["if"] == "startsWith(github.ref, 'refs/tags/v')"
    assert local[0].get("continue-on-error") is not True
    assert jobs["quality-gate"].get("continue-on-error") is not True
    assert jobs["build"]["needs"] == ["quality-gate"]
    assert jobs["publish-testpypi"]["needs"] == ["build"]
    assert jobs["publish-pypi"]["needs"] == ["publish-testpypi"]
    assert jobs["github-release"]["needs"] == ["publish-pypi"]

    remote = jobs["release-identity"]
    assert remote["needs"] == ["github-release"]
    assert remote.get("continue-on-error") is not True
    assert remote["if"] == "startsWith(github.ref, 'refs/tags/v')"
    remote_steps = [
        step for step in remote["steps"] if step.get("name") == "Verify published release identity"
    ]
    assert len(remote_steps) == 1
    assert remote_steps[0]["run"] == (
        "uv run python -m harness_maker.release_identity postpublish "
        '--tag "$GITHUB_REF_NAME" --repository "$GITHUB_REPOSITORY"'
    )
    assert remote_steps[0].get("continue-on-error") is not True
    assert all(step.get("continue-on-error") is not True for step in remote["steps"])
