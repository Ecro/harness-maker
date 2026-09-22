"""Executable contracts for release-facing living documentation.

The branch checker is deliberately filesystem-only. Publication-time remote identity lives in
``release_identity`` so ordinary CI can validate an unreleased checkout without network access.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from harness_maker.models import AutonomyConfig

CORE_DOCS: Final[tuple[str, ...]] = (
    "README.md",
    "README.ko.md",
    "TECH_SPEC.md",
    "docs/ARCHITECTURE.md",
    "docs/HOW-IT-WORKS.md",
    "docs/HOW-IT-WORKS.ko.md",
    "docs/CONTRIBUTING.md",
    "docs/release-checklist.md",
)
VERSION_FILES: Final[tuple[str, ...]] = (
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "pyproject.toml",
    "src/harness_maker/__init__.py",
)
PRESET_FILES: Final[tuple[str, ...]] = (
    "src/harness_maker/templates/harness-yaml/Production.yaml.j2",
    "src/harness_maker/templates/harness-yaml/Side.yaml.j2",
)
HISTORICAL_DOC_DIRS: Final[frozenset[str]] = frozenset(
    {"adr", "migration", "observability", "followups", "assets"}
)
HISTORICAL_DOC_FILES: Final[frozenset[str]] = frozenset({"docs/reference/pre-change-checklist.md"})
CONTRACT_DOCS: Final[frozenset[str]] = frozenset(
    {"README.md", "README.ko.md", "docs/HOW-IT-WORKS.md", "docs/HOW-IT-WORKS.ko.md"}
)
MECHANISM_FIXTURE: Final[str] = "tests/fixtures/documentation_mechanisms.json"


@dataclass(frozen=True)
class SourceContract:
    """Source-derived values against which visible documentation is checked."""

    version: str
    pipeline: tuple[str, ...]
    agents: tuple[str, ...]
    skills: tuple[str, ...]
    mechanisms: tuple[str, ...]
    version_files: tuple[str, ...]


@dataclass(frozen=True)
class ContractError:
    """One path-sensitive documentation contract mismatch."""

    path: str
    key: str
    message: str


def _version_values(root: Path) -> dict[str, str]:
    manifests = VERSION_FILES[:3]
    values = {
        path: str(json.loads((root / path).read_text(encoding="utf-8"))["version"])
        for path in manifests
    }
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    values["pyproject.toml"] = str(pyproject["project"]["version"])
    runtime = (root / "src/harness_maker/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', runtime, re.MULTILINE)
    if match is None:
        raise ValueError("src/harness_maker/__init__.py has no __version__")
    values["src/harness_maker/__init__.py"] = match.group(1)
    return values


def default_source_contract(root: Path) -> SourceContract:
    """Build the contract from live enums/templates and the reviewed mechanism fixture."""

    versions = _version_values(root)
    agents = tuple(
        sorted(
            path.name.removesuffix(".md.j2")
            for path in (root / "src/harness_maker/templates/agents").glob("*.md.j2")
            if not path.name.endswith("_body.md.j2")
        )
    )
    skills = tuple(
        sorted(
            path.name
            for path in (root / "src/harness_maker/templates/skills").iterdir()
            if path.is_dir() and (path / "SKILL.md.j2").is_file()
        )
    )
    mechanism_data = json.loads((root / MECHANISM_FIXTURE).read_text(encoding="utf-8"))
    return SourceContract(
        version=versions["pyproject.toml"],
        pipeline=tuple(stage.value for stage in AutonomyConfig().pipeline),
        agents=agents,
        skills=skills,
        mechanisms=tuple(str(item) for item in mechanism_data["ids"]),
        version_files=VERSION_FILES,
    )


def _marker_values(text: str, key: str) -> tuple[str, ...] | None:
    pattern = re.compile(
        rf"<!-- hm-doc-contract:{re.escape(key)}:start -->(.*?)"
        rf"<!-- hm-doc-contract:{re.escape(key)}:end -->",
        re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return None
    visible = re.sub(r"<!--.*?-->", "", match.group(1), flags=re.DOTALL)
    if key == "mechanisms":
        return tuple(re.findall(r"\bM\d+\b", visible))
    return tuple(re.findall(r"`([^`]+)`", visible))


def _append_mismatch(
    errors: list[ContractError], path: str, key: str, actual: object, expected: object
) -> None:
    if actual != expected:
        errors.append(ContractError(path, key, f"expected {expected!r}; found {actual!r}"))


def validate_documents(docs: dict[str, str], source: SourceContract) -> list[ContractError]:
    """Validate visible contract sections and current-tense retired claims."""

    errors: list[ContractError] = []
    expected = {
        "pipeline": source.pipeline,
        "agents": tuple(sorted(source.agents)),
        "skills": tuple(sorted(source.skills)),
        "mechanisms": source.mechanisms,
        "version-files": source.version_files,
    }
    for path, text in docs.items():
        relative = Path(path)
        if is_historical_doc(relative):
            continue
        for key, wanted in expected.items():
            actual = _marker_values(text, key)
            if actual is not None:
                _append_mismatch(errors, path, key, actual, wanted)

        version_match = re.search(
            r"^> \*\*Version\*\*:\s*([^\s.]+(?:\.[^\s.]+){2})", text, re.MULTILINE
        )
        if version_match is not None:
            _append_mismatch(errors, path, "version", version_match.group(1), source.version)

        lowered = text.lower()
        retired_stage_patterns = (
            r"\b(?:the\s+)?live\s+`plan`\s+stage\b",
            r"\b(?:the\s+)?current\s+`plan`\s+stage\b",
            r"\bresearch\s*(?:→|->)\s*spec\s*(?:→|->)\s*plan\s*(?:→|->)\s*execute\b",
        )
        if any(re.search(pattern, lowered) for pattern in retired_stage_patterns):
            errors.append(
                ContractError(path, "retired-stage", "retired plan stage stated as current")
            )
        if re.search(r"\b(?:seven|7)\s+atomic\s+stages\b", lowered):
            errors.append(ContractError(path, "pipeline", "atomic-stage count is not canonical"))
        if re.search(r"\b(?:seven|7)\s+atomic\s+workflow\s+stages\b", lowered):
            errors.append(ContractError(path, "pipeline", "atomic-stage count is not canonical"))
        if re.search(r"\b(?:the\s+)?current\s+`?plan-validator`?\b", lowered):
            errors.append(
                ContractError(path, "retired-validator", "retired plan-validator stated as current")
            )

        for line in text.splitlines():
            lowered_line = line.lower()
            if re.search(
                r"\b(?:recommended|sequence|in order)\b|(?:권장|시퀀스|순서)", lowered_line
            ):
                stages = tuple(
                    re.findall(
                        r"/(?:hm:|hm-)(research|spec|plan|execute|review|verify|wrapup)\b",
                        lowered_line,
                    )
                )
                if len(stages) >= len(source.pipeline):
                    _append_mismatch(
                        errors,
                        path,
                        "pipeline",
                        stages[: len(source.pipeline)],
                        source.pipeline,
                    )

            version_count = re.search(r"\ball\s+\*\*(\d+)\s+files\*\*\s+updated\b", lowered_line)
            if version_count is not None:
                _append_mismatch(
                    errors,
                    path,
                    "version-files",
                    int(version_count.group(1)),
                    len(source.version_files),
                )

            if "plan-validator" in lowered_line and re.search(
                r"\b(?:performs?|validates?|checks?|runs?|reads?)\b|(?:실행|검증|읽기)",
                lowered_line,
            ):
                errors.append(
                    ContractError(
                        path,
                        "retired-validator",
                        "retired plan-validator described as operational",
                    )
                )

        for match in re.finditer(r"\*\*(\d+) mechanisms\*\*", text):
            _append_mismatch(
                errors, path, "mechanisms", int(match.group(1)), len(source.mechanisms)
            )
    return errors


def is_historical_doc(path: Path) -> bool:
    """Return whether a repository-relative Markdown path is excluded from living checks."""

    normalized = path.as_posix().lstrip("./")
    if normalized.startswith("work-docs/"):
        return True
    if normalized in HISTORICAL_DOC_FILES:
        return True
    parts = Path(normalized).parts
    return len(parts) >= 2 and parts[0] == "docs" and parts[1] in HISTORICAL_DOC_DIRS


def current_changelog(text: str) -> str:
    """Select exactly Unreleased plus the first real release section."""

    headings = list(re.finditer(r"^##\s+\[([^\]]+)\].*$", text, re.MULTILINE))
    unreleased = [heading for heading in headings if heading.group(1).casefold() == "unreleased"]
    if len(unreleased) != 1 or not headings or headings[0] is not unreleased[0]:
        return ""
    releases = [heading for heading in headings[1:] if heading.group(1).casefold() != "unreleased"]
    if not releases or headings[1] is not releases[0]:
        return ""
    end = headings[2].start() if len(headings) > 2 else len(text)
    return text[headings[0].start() : end]


def _living_documents(root: Path) -> tuple[dict[str, str], list[ContractError]]:
    docs: dict[str, str] = {}
    errors: list[ContractError] = []
    for relative in CORE_DOCS:
        path = root / relative
        if not path.is_file():
            errors.append(
                ContractError(relative, "missing-doc", "mandatory living document missing")
            )
        else:
            docs[relative] = path.read_text(encoding="utf-8")
    docs_root = root / "docs"
    if docs_root.is_dir():
        for path in docs_root.rglob("*.md"):
            relative = path.relative_to(root).as_posix()
            if relative not in docs and not is_historical_doc(Path(relative)):
                docs[relative] = path.read_text(encoding="utf-8")
    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        changelog_text = changelog.read_text(encoding="utf-8")
        selected = current_changelog(changelog_text)
        if selected:
            docs["CHANGELOG.md"] = selected
        else:
            errors.append(
                ContractError(
                    "CHANGELOG.md",
                    "changelog-boundary",
                    "expected one leading [Unreleased] section followed by a release",
                )
            )
    return docs, errors


def _required_contract_sections(
    docs: dict[str, str], source: SourceContract
) -> list[ContractError]:
    errors: list[ContractError] = []
    for path in CONTRACT_DOCS:
        text = docs.get(path)
        if text is None:
            continue
        for key in ("pipeline", "agents", "skills", "mechanisms", "version-files"):
            if _marker_values(text, key) is None:
                errors.append(ContractError(path, key, "required visible contract section missing"))
    architecture = docs.get("docs/ARCHITECTURE.md")
    if architecture is not None:
        headings = tuple(re.findall(r"^###\s+(M\d+)\b", architecture, re.MULTILINE))
        if headings:
            _append_mismatch(
                errors, "docs/ARCHITECTURE.md", "mechanisms", headings, source.mechanisms
            )
    return errors


def validate_repository(root: Path, *, source: SourceContract | None = None) -> list[ContractError]:
    """Validate the complete local living-document surface without external I/O."""

    errors: list[ContractError] = []
    if source is None:
        try:
            source = default_source_contract(root)
        except (FileNotFoundError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
            return [ContractError("repository", "source-contract", str(exc))]
        versions = _version_values(root)
        for path, version in versions.items():
            _append_mismatch(errors, path, "version", version, source.version)
    docs, discovery_errors = _living_documents(root)
    errors.extend(discovery_errors)
    errors.extend(_required_contract_sections(docs, source))
    errors.extend(validate_documents(docs, source))
    if (root / "src/harness_maker/templates/harness-yaml").is_dir():
        errors.extend(validate_preset_fallbacks(root))
    return errors


def discover_preset_fallbacks(root: Path) -> dict[str, tuple[str, ...]]:
    """Read the fallback pipeline encoded by every shipped preset template."""

    fallbacks: dict[str, tuple[str, ...]] = {}
    for relative in PRESET_FILES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(r"autonomy\.pipeline if config\.autonomy else \[([^\]]+)\]", text)
        if match is not None:
            fallbacks[relative] = tuple(re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)))
    return fallbacks


def validate_preset_fallbacks(
    root: Path, *, fallbacks: dict[str, tuple[str, ...]] | None = None
) -> list[ContractError]:
    """Compare every preset fallback with the canonical autonomy pipeline."""

    actual = discover_preset_fallbacks(root) if fallbacks is None else fallbacks
    expected = tuple(stage.value for stage in AutonomyConfig().pipeline)
    errors: list[ContractError] = []
    for relative in PRESET_FILES:
        if relative not in actual:
            errors.append(ContractError(relative, "pipeline", "preset fallback missing"))
        else:
            _append_mismatch(errors, relative, "pipeline", actual[relative], expected)
    return errors
