"""Living documentation must stay synchronized with executable source contracts.

The real-tree assertion is intentionally paired with synthetic negative controls. A parser
that returns an empty inventory, reads detached markers, or silently accepts one of the defects
observed in v0.59.0 must fail here even if the checkout prose happens to look correct.
"""

from __future__ import annotations

import ast
import inspect
import re
import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harness_maker.documentation_contract import (
    CONTRACT_DOCS,
    CORE_DOCS,
    ContractError,
    SourceContract,
    current_changelog,
    default_source_contract,
    discover_preset_fallbacks,
    is_historical_doc,
    validate_documents,
    validate_preset_fallbacks,
    validate_repository,
)

_ROOT = Path(__file__).resolve().parents[2]

_EXPECTED_CORE_DOCS = (
    "README.md",
    "README.ko.md",
    "TECH_SPEC.md",
    "docs/ARCHITECTURE.md",
    "docs/HOW-IT-WORKS.md",
    "docs/HOW-IT-WORKS.ko.md",
    "docs/CONTRIBUTING.md",
    "docs/release-checklist.md",
)
_EXPECTED_VERSION_FILES = (
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "pyproject.toml",
    "src/harness_maker/__init__.py",
)
_EXPECTED_PRESET_FILES = (
    "src/harness_maker/templates/harness-yaml/Production.yaml.j2",
    "src/harness_maker/templates/harness-yaml/Side.yaml.j2",
)


def _visible_docs(source: SourceContract) -> dict[str, str]:
    pipeline = " → ".join(f"`{stage}`" for stage in source.pipeline)
    agents = ", ".join(f"`{name}`" for name in sorted(source.agents))
    skills = ", ".join(f"`{name}`" for name in sorted(source.skills))
    mechanisms = ", ".join(source.mechanisms)
    version_files = ", ".join(f"`{path}`" for path in source.version_files)
    body = f"""# Living guide

> **Version**: {source.version}

<!-- hm-doc-contract:pipeline:start -->
**Current pipeline:** {pipeline}
<!-- hm-doc-contract:pipeline:end -->

<!-- hm-doc-contract:agents:start -->
**Current agents:** {agents}
<!-- hm-doc-contract:agents:end -->

<!-- hm-doc-contract:skills:start -->
**Current skills:** {skills}
<!-- hm-doc-contract:skills:end -->

<!-- hm-doc-contract:mechanisms:start -->
**Current mechanisms:** {mechanisms}
<!-- hm-doc-contract:mechanisms:end -->

<!-- hm-doc-contract:version-files:start -->
**Release version files:** {version_files}
<!-- hm-doc-contract:version-files:end -->
"""
    return dict.fromkeys(CORE_DOCS, body)


def _keys(errors: list[ContractError]) -> set[str]:
    return {error.key for error in errors}


def _write_repository(root: Path, source: SourceContract, *, changelog: str | None = None) -> None:
    for relative, body in _visible_docs(source).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    if changelog is not None:
        (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")


_MUTATIONS = [
    ("stage-count", "pipeline"),
    ("retired-stage", "retired-stage"),
    ("pipeline-order", "pipeline"),
    ("validator-name", "retired-validator"),
    ("missing-agent", "agents"),
    ("extra-agent", "agents"),
    ("missing-skill", "skills"),
    ("extra-skill", "skills"),
    ("mechanism-count", "mechanisms"),
    ("four-version-files", "version-files"),
    ("version", "version"),
    ("detached-marker", "retired-stage"),
    ("legacy-sequence", "retired-stage"),
    ("seven-workflow-stages", "pipeline"),
    ("hidden-marker-content", "pipeline"),
]


def test_ac_001_living_docs_match_source_contracts(tmp_path: Path) -> None:
    source = default_source_contract(_ROOT)
    assert source.pipeline == ("research", "spec", "execute", "review", "verify", "wrapup")
    assert source.agents
    assert source.skills
    assert source.mechanisms == tuple(f"M{i}" for i in range(1, 20))
    assert validate_repository(_ROOT) == []

    _write_repository(tmp_path, source)
    assert validate_repository(tmp_path, source=source) == []
    readme = tmp_path / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nThe live `plan` stage runs.\n")
    errors = validate_repository(tmp_path, source=source)
    assert any(error.path == "README.md" and error.key == "retired-stage" for error in errors)


@pytest.mark.parametrize(
    ("mutation", "expected_key"),
    _MUTATIONS,
)
def test_ac_002_doc_contract_rejects_representative_mutations(
    mutation: str, expected_key: str
) -> None:
    source = default_source_contract(_ROOT)
    docs = _visible_docs(source)
    assert validate_documents(docs, source) == []
    target = "docs/HOW-IT-WORKS.md"
    text = docs[target]

    if mutation == "stage-count":
        text += "\nThere are exactly seven atomic stages.\n"
    elif mutation == "retired-stage":
        text += "\nThe live `plan` stage writes the plan.\n"
    elif mutation == "pipeline-order":
        text = text.replace("`review` → `verify` → `wrapup`", "`review` → `wrapup` → `verify`")
    elif mutation == "validator-name":
        text += "\nThe current `plan-validator` checks the plan.\n"
    elif mutation == "missing-agent":
        text = text.replace(f"`{sorted(source.agents)[0]}`, ", "", 1)
    elif mutation == "extra-agent":
        text = text.replace("**Current agents:**", "**Current agents:** `ghost-agent`,")
    elif mutation == "missing-skill":
        text = text.replace(f"`{sorted(source.skills)[0]}`, ", "", 1)
    elif mutation == "extra-skill":
        text = text.replace("**Current skills:**", "**Current skills:** `ghost-skill`,")
    elif mutation == "mechanism-count":
        text = text.replace(", M19", "", 1)
    elif mutation == "four-version-files":
        text = text.replace(f", `{source.version_files[-1]}`", "", 1)
    elif mutation == "version":
        text = text.replace(source.version, "0.0.0", 1)
    elif mutation == "detached-marker":
        text += "\nSeven atomic stages include the current `plan` stage.\n"
    elif mutation == "legacy-sequence":
        text += "\nresearch → spec → plan → execute → review → verify → wrapup\n"
    elif mutation == "seven-workflow-stages":
        text += "\n## The 7 Atomic Workflow Stages\n"
    elif mutation == "hidden-marker-content":
        pipeline = " → ".join(f"`{stage}`" for stage in source.pipeline)
        text = text.replace(
            f"**Current pipeline:** {pipeline}",
            f"<!-- **Current pipeline:** {pipeline} -->",
        )
    docs[target] = text

    errors = validate_documents(docs, source)
    assert any(error.path == target and error.key == expected_key for error in errors), errors


def test_ac_002_contract_and_mutation_inventories_are_nonempty() -> None:
    source = default_source_contract(_ROOT)
    assert tuple(CORE_DOCS) == _EXPECTED_CORE_DOCS
    assert source.agents
    assert source.skills
    assert len(source.mechanisms) == 19
    assert source.version_files == _EXPECTED_VERSION_FILES
    required_mutations = {
        "stage-count",
        "retired-stage",
        "pipeline-order",
        "validator-name",
        "missing-agent",
        "extra-agent",
        "missing-skill",
        "extra-skill",
        "mechanism-count",
        "four-version-files",
        "version",
        "detached-marker",
        "legacy-sequence",
        "seven-workflow-stages",
        "hidden-marker-content",
    }
    assert {name for name, _ in _MUTATIONS} == required_mutations


@pytest.mark.parametrize(
    ("relative", "old", "stale", "expected_key"),
    [
        (
            "README.md",
            "`/hm:review` → `/hm:verify` → `/hm:wrapup`",
            "`/hm:review` → `/hm:wrapup` → `/hm:verify`",
            "pipeline",
        ),
        (
            "docs/CONTRIBUTING.md",
            "all **5 files** updated",
            "all **4 files** updated",
            "version-files",
        ),
        (
            "docs/HOW-IT-WORKS.md",
            "`spec-validator` performs one conditional",
            "`plan-validator` performs one conditional",
            "retired-validator",
        ),
    ],
)
def test_ac_002_real_operational_prose_cannot_contradict_marker_contracts(
    relative: str, old: str, stale: str, expected_key: str
) -> None:
    source = default_source_contract(_ROOT)
    original = (_ROOT / relative).read_text(encoding="utf-8")
    assert old in original
    mutated = original.replace(old, stale, 1)
    assert mutated != original

    errors = validate_documents({relative: mutated}, source)

    assert any(error.path == relative and error.key == expected_key for error in errors), errors


def test_ac_003_branch_check_is_hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = default_source_contract(_ROOT)
    _write_repository(tmp_path, source)

    def unexpected_network_or_process(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"branch documentation check attempted external I/O: {args!r}")

    monkeypatch.setattr(socket, "create_connection", unexpected_network_or_process)
    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network_or_process)
    monkeypatch.setattr(subprocess, "run", unexpected_network_or_process)
    monkeypatch.setattr(subprocess, "Popen", unexpected_network_or_process)
    assert validate_repository(tmp_path, source=source) == []

    module_path = Path(inspect.getfile(validate_repository))
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert imported_roots.isdisjoint({"httpx", "requests", "socket", "urllib"})


@given(
    st.sampled_from(
        ["adr/x.md", "migration/x.md", "observability/x.md", "followups/x.md", "assets/x.md"]
    )
)
def test_ac_005_historical_directories_are_excluded(relative: str) -> None:
    assert is_historical_doc(Path("docs") / relative)


def test_ac_005_core_and_current_doc_discovery_policy() -> None:
    assert not is_historical_doc(Path("README.md"))
    assert not is_historical_doc(Path("docs/HOW-IT-WORKS.md"))
    assert is_historical_doc(Path("docs/reference/pre-change-checklist.md"))
    assert is_historical_doc(Path("work-docs/PLAN-old.md"))


def test_ac_005_repository_recursively_discovers_additional_current_docs(tmp_path: Path) -> None:
    source = default_source_contract(_ROOT)
    _write_repository(tmp_path, source)
    nested = tmp_path / "docs/guides/current.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("The live `plan` stage runs.\n", encoding="utf-8")

    errors = validate_repository(tmp_path, source=source)

    assert any(
        error.path == "docs/guides/current.md" and error.key == "retired-stage" for error in errors
    ), errors


@pytest.mark.parametrize("key", ["mechanisms", "version-files"])
@pytest.mark.parametrize("relative", sorted(CONTRACT_DOCS))
def test_ac_001_each_visible_contract_section_is_required(
    tmp_path: Path, relative: str, key: str
) -> None:
    source = default_source_contract(_ROOT)
    _write_repository(tmp_path, source)
    path = tmp_path / relative
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        rf"\n?<!-- hm-doc-contract:{re.escape(key)}:start -->.*?"
        rf"<!-- hm-doc-contract:{re.escape(key)}:end -->\n?",
        "\n",
        text,
        flags=re.DOTALL,
    )
    path.write_text(text, encoding="utf-8")

    errors = validate_repository(tmp_path, source=source)
    assert any(error.path == relative and error.key == key for error in errors), errors


@pytest.mark.parametrize("missing", _EXPECTED_CORE_DOCS)
def test_ac_005_each_core_document_is_mandatory(tmp_path: Path, missing: str) -> None:
    source = default_source_contract(_ROOT)
    _write_repository(tmp_path, source)
    (tmp_path / missing).unlink()

    errors = validate_repository(tmp_path, source=source)
    assert any(error.path == missing and error.key == "missing-doc" for error in errors), errors


@pytest.mark.parametrize(
    "historical",
    [
        "docs/adr/x.md",
        "docs/migration/x.md",
        "docs/observability/x.md",
        "docs/followups/x.md",
        "docs/assets/x.md",
        "docs/reference/pre-change-checklist.md",
        "work-docs/PLAN-old.md",
    ],
)
def test_ac_005_same_claim_fails_in_current_docs_but_not_history(historical: str) -> None:
    source = default_source_contract(_ROOT)
    clean = _visible_docs(source)
    claim = "The live `plan` stage runs."

    current = dict(clean)
    current["docs/current-guide.md"] = claim
    current_errors = validate_documents(current, source)
    assert any(
        error.path == "docs/current-guide.md" and error.key == "retired-stage"
        for error in current_errors
    )

    archived = dict(clean)
    archived[historical] = claim
    assert validate_documents(archived, source) == []


@pytest.mark.parametrize(
    ("section", "must_fail"),
    [("unreleased", True), ("first-release", True), ("second-release", False)],
)
def test_ac_005_changelog_boundary_is_enforced_by_repository_validation(
    tmp_path: Path, section: str, must_fail: bool
) -> None:
    source = default_source_contract(_ROOT)
    claim = "The live `plan` stage runs."
    bodies = {"unreleased": "current", "first-release": "first", "second-release": "history"}
    bodies[section] = claim
    changelog = f"""# Changelog
## [Unreleased]
{bodies["unreleased"]}
## [2.0.0]
{bodies["first-release"]}
## [1.0.0]
{bodies["second-release"]}
"""
    _write_repository(tmp_path, source, changelog=changelog)

    selected = current_changelog(changelog)
    assert (claim in selected) is must_fail
    errors = validate_repository(tmp_path, source=source)
    matched = any(error.path == "CHANGELOG.md" and error.key == "retired-stage" for error in errors)
    assert matched is must_fail, errors


@pytest.mark.parametrize(
    "changelog",
    [
        "# Changelog\n## [2.0.0]\nrelease\n## [1.0.0]\nhistory\n",
        "# Changelog\n## [2.0.0]\nrelease\n## [Unreleased]\ncurrent\n",
        "# Changelog\n## [Unreleased]\ncurrent\n## [Unreleased]\nduplicate\n## [2.0.0]\nrelease\n",
        "# Changelog\n## [Unreleased]\ncurrent only\n",
    ],
)
def test_ac_005_changelog_requires_canonical_unreleased_boundary(
    tmp_path: Path, changelog: str
) -> None:
    source = default_source_contract(_ROOT)
    _write_repository(tmp_path, source, changelog=changelog)

    errors = validate_repository(tmp_path, source=source)

    assert any(
        error.path == "CHANGELOG.md" and error.key == "changelog-boundary" for error in errors
    ), errors


@given(st.integers())
def test_ac_006_localized_contracts_ignore_unrelated_prose(note_id: int) -> None:
    source = default_source_contract(_ROOT)
    docs = _visible_docs(source)
    docs["README.md"] += f"\nUnrelated localization note {note_id}.\n"
    docs["README.ko.md"] += "\n한국어 설명은 달라도 됩니다.\n"
    assert validate_documents(docs, source) == []


@pytest.mark.parametrize("relative", sorted(CONTRACT_DOCS))
@pytest.mark.parametrize("catalog", ["agents", "skills"])
@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_ac_006_each_locale_must_match_the_complete_source_inventory(
    relative: str, catalog: str, mutation: str
) -> None:
    source = default_source_contract(_ROOT)
    docs = _visible_docs(source)
    inventory = sorted(getattr(source, catalog))
    if mutation == "missing":
        docs[relative] = docs[relative].replace(f"`{inventory[0]}`, ", "", 1)
    else:
        docs[relative] = docs[relative].replace(
            f"**Current {catalog}:**", f"**Current {catalog}:** `ghost-{catalog[:-1]}`,"
        )
    errors = validate_documents(docs, source)
    assert any(error.path == relative and error.key == catalog for error in errors), errors


def test_ac_007_preset_fallbacks_use_the_canonical_six_stage_pipeline() -> None:
    source = default_source_contract(_ROOT)
    fallbacks = discover_preset_fallbacks(_ROOT)
    assert tuple(sorted(fallbacks)) == _EXPECTED_PRESET_FILES
    assert validate_preset_fallbacks(_ROOT, fallbacks=fallbacks) == []

    broken = dict(fallbacks)
    preset = sorted(broken)[0]
    broken[preset] = source.pipeline[:2] + ("plan",) + source.pipeline[2:]
    errors = validate_preset_fallbacks(_ROOT, fallbacks=broken)
    assert any(error.path == preset and error.key == "pipeline" for error in errors)


def test_wrong_source_inventory_cannot_be_hidden_by_locale_parity() -> None:
    source = default_source_contract(_ROOT)
    docs = _visible_docs(source)
    missing = sorted(source.skills)[0]
    for path in ("docs/HOW-IT-WORKS.md", "docs/HOW-IT-WORKS.ko.md"):
        docs[path] = docs[path].replace(f"`{missing}`, ", "", 1)
    assert "skills" in _keys(validate_documents(docs, source))


def test_pipeline_oracle_is_not_derived_from_document_text() -> None:
    source = default_source_contract(_ROOT)
    wrong = replace(source, pipeline=("research", "spec", "execute", "review", "wrapup", "verify"))
    docs = _visible_docs(source)
    assert "pipeline" in _keys(validate_documents(docs, wrong))
