"""Phase 1 of PLAN-second-opinion-oracle-polyglot — the `toolchains` config contract.

The four assertions here map to the PLAN's Phase 1 exit criterion (a)-(d). (b) and (c) are
the load-bearing ones: a single-preset round-trip passes while the other preset never emits
the key at all, and `--preset` rebuilds answers from a seven-field allowlist that silently
drops any root field it does not name.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import (
    HarnessConfig,
    InterviewAnswers,
    Preset,
    ToolchainConfig,
)

_PY = {
    "name": "python",
    "extensions": [".py", ".pyi"],
    "commands": {"test": "uv run pytest -q {path}", "lint": "uv run ruff check {path}"},
}
_NODE = {
    "name": "node",
    "extensions": [".ts", ".tsx"],
    "commands": {"test": "npx --no-install vitest run {path}"},
}


# --- (a) per-entry inert rules + model-level disjointness -------------------------------


def test_entry_with_empty_extensions_is_inert() -> None:
    """An entry that matches nothing must be representable but never claim a path."""
    entry = ToolchainConfig.model_validate(
        {"name": "x", "extensions": [], "commands": {"test": "t {path}"}}
    )
    assert entry.is_inert is True


def test_entry_with_empty_commands_is_inert() -> None:
    """Covered-but-commandless is the false-`accepted` shape: a labelled block with no evidence."""
    entry = ToolchainConfig.model_validate({"name": "x", "extensions": [".py"], "commands": {}})
    assert entry.is_inert is True


def test_populated_entry_is_not_inert() -> None:
    assert ToolchainConfig.model_validate(_PY).is_inert is False


def test_overlapping_extensions_across_entries_are_rejected() -> None:
    """Disjointness is a property of the LIST, not of one entry — a per-entry model
    structurally cannot see its siblings, so the validator must live on the container."""
    overlap = dict(_NODE, extensions=[".py", ".ts"])
    with pytest.raises(ValidationError, match="overlap"):
        HarnessConfig(
            toolchains=[
                ToolchainConfig.model_validate(_PY),
                ToolchainConfig.model_validate(overlap),
            ]
        )


def test_disjoint_extensions_across_entries_are_accepted() -> None:
    cfg = HarnessConfig(
        toolchains=[ToolchainConfig.model_validate(_PY), ToolchainConfig.model_validate(_NODE)]
    )
    assert [t.name for t in cfg.toolchains] == ["python", "node"]


def test_absent_key_defaults_to_empty_list() -> None:
    """Empty list = off, same convention as reviewers.mechanical_checks."""
    assert HarnessConfig().toolchains == []
    assert InterviewAnswers().toolchains == []


# --- (b) round-trip through BOTH presets ------------------------------------------------


@pytest.mark.parametrize("preset", ["Production", "Side"])
def test_toolchains_round_trip_under_both_presets(tmp_path: Path, preset: str) -> None:
    """A single-preset assertion can pass while the other preset never emits the key,
    which silently returns the ADR-006 Python default for half the install base.
    """
    from harness_maker.models import ProjectProfile
    from harness_maker.render import render
    from harness_maker.synthesize import synthesize

    answers = InterviewAnswers(
        preset=Preset(preset),
        toolchains=[ToolchainConfig.model_validate(_PY), ToolchainConfig.model_validate(_NODE)],
    )
    render(synthesize(ProjectProfile(), answers), tmp_path)

    path = tmp_path / "harness.yaml"
    assert path.exists(), f"{preset}: renderer produced no harness.yaml"
    restored = answers_from_harness_yaml(path)
    assert restored is not None
    assert [t.name for t in restored.toolchains] == ["python", "node"], (
        f"{preset} preset did not emit toolchains"
    )
    assert [t.extensions for t in restored.toolchains] == [[".py", ".pyi"], [".ts", ".tsx"]]
    assert restored.toolchains[0].commands.test == "uv run pytest -q {path}"
    assert restored.toolchains[1].commands.test == "npx --no-install vitest run {path}"


# --- (c) survives every answers-reconstruction path --------------------------------------


def test_toolchains_survive_preset_switch() -> None:
    """`_build_answers` takes a seven-field allowlist; any root field absent from it AND
    from `update` is lost on `--preset`. The comment above cli.py:1402 already records
    this loss class for `autonomy`.
    """
    from harness_maker import cli

    answers = InterviewAnswers(
        preset=Preset.SIDE,
        toolchains=[ToolchainConfig.model_validate(_PY)],
    )
    result = cli._apply_dimension_overrides(
        answers,
        preset_override="Production",
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
    )
    assert result.preset is Preset.PRODUCTION
    assert [t.name for t in result.toolchains] == ["python"], (
        "toolchains was dropped by the preset-switch rebuild"
    )


def test_toolchains_survive_second_opinion_models_override() -> None:
    from harness_maker import cli

    answers = InterviewAnswers(toolchains=[ToolchainConfig.model_validate(_PY)])
    result = cli._apply_dimension_overrides(
        answers,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
        second_opinion_models_override="codex",
    )
    assert [t.name for t in result.toolchains] == ["python"]


# --- (d) structural: no construction site may omit a field -------------------------------


def _interview_answers_call_sites() -> list[tuple[Path, ast.Call]]:
    """Discover, don't enumerate. A hand-list of reconstruction functions has gone stale
    three times in this repo ([fail:design] new-marker-content-field-must-update-every-reader,
    count:3); the guard has to find the sites itself.
    """
    src = Path(__file__).parents[2] / "src" / "harness_maker"
    out: list[tuple[Path, ast.Call]] = []
    for py in src.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "InterviewAnswers"
                and node.keywords
            ):
                out.append((py, node))
    return out


def test_every_answers_construction_site_carries_toolchains() -> None:
    """A construction site that rebuilds answers from a field allowlist must name every
    root field, or the omitted one resets silently. Sites that build a FRESH answers object
    (no `existing` to preserve) are exempt — they are identified by taking no argument
    derived from another InterviewAnswers.
    """
    sites = _interview_answers_call_sites()
    assert sites, "discovery found zero InterviewAnswers construction sites — the scan is broken"

    offenders: list[str] = []
    for path, call in sites:
        kwargs = {k.arg for k in call.keywords if k.arg}
        # A rebuild is a site that forwards other fields off an existing answers object.
        forwards_existing = any(
            isinstance(k.value, ast.Attribute)
            and isinstance(k.value.value, ast.Name)
            and k.value.value.id == "answers"
            for k in call.keywords
        )
        if forwards_existing and "toolchains" not in kwargs:
            offenders.append(f"{path.name}:{call.lineno}")
    assert not offenders, f"answers rebuild drops `toolchains`: {offenders}"
