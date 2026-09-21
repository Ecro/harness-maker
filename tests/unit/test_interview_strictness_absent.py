"""AC-009 (SPEC-dev-mode-removal): onboarding asks no strictness question.

Two interviews exist and both are checked. The Python `interview()` is the CLI fallback; the
plugin's `/harness-maker:make` command is the onboarding a real user sees, and it passed the
answer to `harness-maker make --dev-mode`, so leaving its question in place would both keep
the question and break the command.

The pre-change count, measured on this tree before any edit, is 15 prompts on the all-defaults
path; the dev_mode prompt was one of them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.models import ProjectProfile, Target

ROOT = Path(__file__).resolve().parents[2]
_PRE_CHANGE_PROMPT_COUNT = 15
_AXIS = re.compile(r"dev_mode|dev-mode|strictness|spec-driven|task-driven", re.IGNORECASE)


def interview_questions(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from harness_maker import interview as iv

    prompts: list[str] = []

    def record(prompt: str = "") -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(iv, "_input_or_empty", record)
    monkeypatch.setattr("builtins.input", record)
    iv.interview(ProjectProfile())
    return prompts


def configure_editable_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    from harness_maker.interview import _build_answers
    from harness_maker.models import Preset
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    from ..structural.conftest import pin_install_ref

    pin_install_ref(monkeypatch)
    answers = _build_answers(locale="en", targets=[Target.CLAUDE_CODE], preset=Preset.SIDE)
    render(
        synthesize(ProjectProfile(), answers, preset=Preset.SIDE),
        tmp_path,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return (tmp_path / "commands" / "hm" / "configure.md").read_text(encoding="utf-8")


def test_ac_009_onboarding_asks_no_strictness_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = interview_questions(monkeypatch)
    assert not [p for p in prompts if _AXIS.search(p)], prompts
    assert len(prompts) < _PRE_CHANGE_PROMPT_COUNT

    assert "spec.strictness" in configure_editable_keys(tmp_path, monkeypatch)

    make_cmd = (ROOT / "commands" / "make.md").read_text(encoding="utf-8")
    assert not re.search(r"dev_mode|dev-mode", make_cmd), (
        "/harness-maker:make still asks or passes dev_mode"
    )
