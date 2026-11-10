"""SPEC-hm-cost-p4 AC-004..AC-007: the rendered execute and spec stages, and three stale texts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from harness_maker import io_utils
from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]


def _render(path: str, *, is_codex: bool = False, **cfg_edits: Any) -> str:
    cfg: dict[str, Any] = HarnessConfig().model_dump(mode="json")
    cfg.update(cfg_edits)
    return (
        _make_env()
        .get_template(path)
        .render(
            stage=path.rsplit("/", 1)[-1].split(".")[0], workflow_context="", project_name="",
            feature="", config=cfg, harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
            is_codex=is_codex, communication_variant="reframe",
        )
    )  # fmt: skip


def _step(text: str, number: str) -> str:
    head = f"## Step {number} "
    assert head in text, f"no {head!r}"
    return text.split(head, 1)[1].split("\n## ", 1)[0]


@pytest.mark.parametrize("is_codex", [False, True])
def test_ac_004_phase_a_names_tests(is_codex: bool) -> None:
    text = _render("stages/execute.md.j2", is_codex=is_codex)
    assert "AC-NNN-<i>" in text
    assert "never copy the implementation" in text
    assert "Put each test's node id in its AC's `test_ids`" not in text
    assert "spec_machine validate" not in text


@pytest.mark.parametrize("is_codex", [False, True])
def test_ac_005_no_same_session_reread(is_codex: bool) -> None:
    text = _render("stages/execute.md.j2", is_codex=is_codex)
    assert "Read it back" not in text
    assert "Read it and any RESEARCH doc it names" not in text
    assert "only on Resume or when this session did not write them" in _step(text, "1")


@pytest.mark.parametrize("is_codex", [False, True])
def test_ac_006_unchanged_rows_from_unchanged_code(is_codex: bool) -> None:
    spec = _render("stages/spec.md.j2", is_codex=is_codex)
    assert "computed at spec time by running the unchanged code" in spec
    assert "never regenerated" in spec
    assert "never regenerate" in _render("stages/execute.md.j2", is_codex=is_codex)


def test_ac_007_stale_texts(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    retired = sorted(io_utils.RETIRED_TOP_LEVEL_KEYS)[0]
    with caplog.at_level(logging.WARNING):
        io_utils.strip_retired_keys({retired: True}, source=tmp_path / "harness.yaml")
    advisory = caplog.text
    assert retired in advisory
    assert "/hm:loop" not in advisory
    assert "autopilot" not in advisory
    arch = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "research|spec|execute|wrapup" in arch
    assert "loop.md" not in arch
    so = {"models": ["codex"]}
    for is_codex in (False, True):
        execute = _render("stages/execute.md.j2", is_codex=is_codex, second_opinion=so)
        assert "consensus-arbiter" in execute
        assert "resolves conflicting severities" not in execute
    arbiter = _render("agents/consensus-arbiter.md.j2", second_opinion=so)
    assert "disagree on a finding's severity" not in arbiter
    assert "severity resolution" not in arbiter
