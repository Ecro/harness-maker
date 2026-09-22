"""Two-boundary release identity checks.

``prepublish`` is filesystem-only. Network imports are local to the postpublication opener so
ordinary branch and tag-quality checks remain hermetic.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from harness_maker.documentation_contract import VERSION_FILES

DOCUMENT_VERSION_FILES = (
    "README.md",
    "README.ko.md",
    "docs/HOW-IT-WORKS.md",
    "docs/HOW-IT-WORKS.ko.md",
)
DEFAULT_REPOSITORY = "Ecro/harness-maker"
DEFAULT_PACKAGE = "harness-maker"


@dataclass(frozen=True)
class PrepublishResult:
    tag_version: str
    source_versions: dict[str, str]
    document_versions: dict[str, str]
    mismatches: dict[str, str]

    @property
    def ok(self) -> bool:
        return not self.mismatches

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1


class RemoteStatus(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RemoteResult:
    status: RemoteStatus
    tagged_source: str
    github: str | None
    pypi: str | None
    detail: str = ""

    @property
    def exit_code(self) -> int:
        return 0 if self.status is RemoteStatus.MATCH else 1


JsonOpener = Callable[[str, float], Mapping[str, object]]


def _normalize_version(value: str) -> str:
    normalized = value.strip()
    return normalized[1:] if normalized.startswith("v") else normalized


def _source_versions(root: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for relative in VERSION_FILES[:3]:
        payload = json.loads((root / relative).read_text(encoding="utf-8"))
        versions[relative] = str(payload["version"])
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    versions["pyproject.toml"] = str(pyproject["project"]["version"])
    runtime = (root / "src/harness_maker/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', runtime, re.MULTILINE)
    if match is None:
        raise ValueError("src/harness_maker/__init__.py has no __version__")
    versions["src/harness_maker/__init__.py"] = match.group(1)
    return versions


def _document_versions(root: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    pattern = re.compile(r"^> \*\*Version\*\*:\s*([^\s]+)", re.MULTILINE)
    for relative in DOCUMENT_VERSION_FILES:
        text = (root / relative).read_text(encoding="utf-8")
        match = pattern.search(text)
        if match is None:
            raise ValueError(f"{relative} has no visible Version declaration")
        versions[relative] = match.group(1)
    return versions


def prepublish_identity(tag_version: str, root: Path) -> PrepublishResult:
    """Compare a tag with all local source and visible document identities."""

    expected = _normalize_version(tag_version)
    source_versions = _source_versions(root)
    document_versions = _document_versions(root)
    mismatches = {
        path: version
        for path, version in (*source_versions.items(), *document_versions.items())
        if _normalize_version(version) != expected
    }
    return PrepublishResult(expected, source_versions, document_versions, mismatches)


def classify_remote_versions(*, tagged_source: str, github: str, pypi: str) -> RemoteResult:
    """Classify already-observed remote identities against the validated tag."""

    expected = _normalize_version(tagged_source)
    unavailable = {"", "timeout", "unavailable"}
    if github.lower() in unavailable or pypi.lower() in unavailable:
        return RemoteResult(RemoteStatus.UNAVAILABLE, expected, github, pypi)
    github_version = _normalize_version(github)
    pypi_version = _normalize_version(pypi)
    status = (
        RemoteStatus.MATCH if github_version == expected == pypi_version else RemoteStatus.MISMATCH
    )
    return RemoteResult(status, expected, github_version, pypi_version)


def _default_opener(url: str, timeout: float) -> Mapping[str, object]:
    import urllib.request

    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload: object = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("remote payload is not an object")
    return payload


def _fetch_json(
    url: str, *, opener: JsonOpener, retries: int, timeout: float
) -> Mapping[str, object] | None:
    if retries < 1:
        raise ValueError("retries must be at least 1")
    if not 0 < timeout <= 10:
        raise ValueError("timeout must be between 0 and 10 seconds")
    for attempt in range(retries):
        try:
            return opener(url, timeout)
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
            if attempt + 1 < retries:
                time.sleep(min(2**attempt, timeout))
    return None


def fetch_remote_identity(
    tagged_source: str,
    *,
    repository: str = DEFAULT_REPOSITORY,
    package: str = DEFAULT_PACKAGE,
    opener: JsonOpener = _default_opener,
    retries: int = 3,
    timeout: float = 5,
) -> RemoteResult:
    """Fetch fixed GitHub/PyPI endpoints and classify publication identity."""

    expected = _normalize_version(tagged_source)
    github_url = f"https://api.github.com/repos/{repository}/releases/tags/v{expected}"
    github_payload = _fetch_json(github_url, opener=opener, retries=retries, timeout=timeout)
    if github_payload is None or not isinstance(github_payload.get("tag_name"), str):
        return RemoteResult(
            RemoteStatus.UNAVAILABLE, expected, None, None, "GitHub release evidence unavailable"
        )
    github_version = str(github_payload["tag_name"])

    pypi_url = f"https://pypi.org/pypi/{package}/{expected}/json"
    pypi_payload = _fetch_json(pypi_url, opener=opener, retries=retries, timeout=timeout)
    pypi_info = pypi_payload.get("info") if pypi_payload is not None else None
    if not isinstance(pypi_info, Mapping) or not isinstance(pypi_info.get("version"), str):
        return RemoteResult(
            RemoteStatus.UNAVAILABLE,
            expected,
            _normalize_version(github_version),
            None,
            "PyPI release evidence unavailable",
        )
    return classify_remote_versions(
        tagged_source=expected,
        github=github_version,
        pypi=str(pypi_info["version"]),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify harness-maker release identity")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepublish = subparsers.add_parser("prepublish")
    prepublish.add_argument("--tag", required=True)
    prepublish.add_argument("--root", type=Path, default=Path("."))
    postpublish = subparsers.add_parser("postpublish")
    postpublish.add_argument("--tag", required=True)
    postpublish.add_argument("--repository", default=DEFAULT_REPOSITORY)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepublish":
        prepublish_result = prepublish_identity(args.tag, args.root)
        payload: dict[str, Any] = {
            "status": "match" if prepublish_result.ok else "mismatch",
            "tagged_source": prepublish_result.tag_version,
            "mismatches": prepublish_result.mismatches,
        }
        exit_code = prepublish_result.exit_code
    else:
        remote_result = fetch_remote_identity(args.tag, repository=args.repository)
        payload = {
            "status": remote_result.status.value,
            "tagged_source": remote_result.tagged_source,
            "github": remote_result.github,
            "pypi": remote_result.pypi,
            "detail": remote_result.detail,
        }
        exit_code = remote_result.exit_code
    print(json.dumps(payload, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
