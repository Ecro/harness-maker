"""SPEC-world-model-name: the `world_model {name, handle}` config, its handle rules and the
CLI / interview surfaces that set it (AC-001, AC-003, AC-006, AC-008, AC-009).

Production symbols are resolved at call time (`_wm()`), so each test goes RED for its own
reason instead of the whole module failing collection before the feature exists.
"""

from __future__ import annotations

import importlib
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from typer.testing import CliRunner

from harness_maker import i18n, models
from harness_maker import interview as interview_mod
from harness_maker.cli import app
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import InterviewAnswers, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.spec_machine import load_golden_table
from harness_maker.synthesize import _ALL_SKILLS, synthesize

_SPEC_YAML = Path(__file__).resolve().parents[2] / "specs/SPEC-world-model-name.machine.yaml"
# The Agent Skills spec `name` grammar (agentskills.io/specification) — external to this code.
_SKILL_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def _wm() -> ModuleType:
    return importlib.import_module("harness_maker.world_model")


def _config_cls() -> Any:
    return models.WorldModelConfig


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


@contextmanager
def _chdir(path: Path) -> Iterator[None]:
    before = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(before)


def _cli(repo: Path, *args: str) -> Any:
    with _chdir(repo):
        return CliRunner().invoke(app, ["make", str(repo), "--autoloop", *args])


def _read_yaml(repo: Path) -> dict[str, Any]:
    return load_harness_yaml(repo / ".claude" / "harness.yaml")


def _write_yaml(repo: Path, data: dict[str, Any]) -> None:
    (repo / ".claude" / "harness.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# AC-001 — onboarding asks the name right after locale and defaults to Maker
# ---------------------------------------------------------------------------


def interview_with_empty_answers() -> InterviewAnswers:
    return interview(_profile(), autoloop_mode=False)


def test_ac_001_interview_default_maker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(interview_mod, "_input_or_empty", lambda _prompt="": "")
    assert interview_with_empty_answers().world_model.name == "Maker"
    assert interview_with_empty_answers().world_model.handle == "maker"


def test_ac001_name_is_asked_right_after_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    monkeypatch.setattr(interview_mod, "_input_or_empty", lambda _prompt="": "")
    real_locale = interview_mod._ask_locale
    real_targets = interview_mod._ask_targets
    real_wm = interview_mod._ask_world_model

    def locale() -> str:
        order.append("locale")
        return real_locale()

    def wm(*a: Any, **k: Any) -> Any:
        order.append("world_model")
        return real_wm(*a, **k)

    def targets(*a: Any, **k: Any) -> Any:
        order.append("targets")
        return real_targets(*a, **k)

    monkeypatch.setattr(interview_mod, "_ask_locale", locale)
    monkeypatch.setattr(interview_mod, "_ask_world_model", wm)
    monkeypatch.setattr(interview_mod, "_ask_targets", targets)
    interview(_profile(), autoloop_mode=False)
    assert order[:3] == ["locale", "world_model", "targets"]


def test_ac001_non_ascii_asks_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []
    answers = iter(["비비", "bibi"])

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(interview_mod, "_input_or_empty", fake_input)
    got = interview_mod._ask_world_model()
    assert (got.name, got.handle) == ("비비", "bibi")
    assert len(prompts) == 2, "a handle question must follow an underivable name"


def test_s2_interview_carries_non_ascii_name_into_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S2 through the public interview(): locale, then the name, then the handle, then defaults."""
    answers = iter(["ko", "비비", "bibi"])
    monkeypatch.setattr(interview_mod, "_input_or_empty", lambda _p="": next(answers, ""))
    got = interview(_profile(), autoloop_mode=False)
    assert (got.locale, got.world_model.name, got.world_model.handle) == ("ko", "비비", "bibi")


def test_ac001_ascii_name_asks_no_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return "Atlas"

    monkeypatch.setattr(interview_mod, "_input_or_empty", fake_input)
    got = interview_mod._ask_world_model()
    assert (got.name, got.handle) == ("Atlas", "atlas")
    assert len(prompts) == 1


def test_ac001_invalid_handle_answer_is_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["비비", "intent-layer", "bibi"])
    monkeypatch.setattr(interview_mod, "_input_or_empty", lambda _p="": next(answers))
    got = interview_mod._ask_world_model()
    assert got.handle == "bibi"


def test_ac001_autoloop_defaults_to_maker() -> None:
    a = interview(_profile(), autoloop_mode=True)
    assert (a.world_model.name, a.world_model.handle) == ("Maker", "maker")


# ---------------------------------------------------------------------------
# AC-003 — derived handles always satisfy the skill name rule (property)
# ---------------------------------------------------------------------------


@settings(max_examples=300, derandomize=True, deadline=None)
@given(
    name=st.one_of(
        st.text(max_size=200),
        st.sampled_from(
            ["비비", "메이커", "Maker", "My Bot!", "-x-", "Intent Layer", "hm research"]
        ),
    )
)
def test_ac003_handle_derivation_property(name: str) -> None:
    h = _wm().derive_handle(name)
    assert h is None or (
        _SKILL_NAME.fullmatch(h) is not None and len(h) <= 64 and h not in _wm().RESERVED_HANDLES
    )
    assert h is None or not h.startswith("hm-")


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Maker", "maker"), ("My Bot!", "my-bot"), ("비비", None), ("Intent Layer", None)],
)
def test_ac003_derivation_examples(name: str, expected: str | None) -> None:
    assert _wm().derive_handle(name) == expected


def test_reserved_covers_every_shipped_skill() -> None:
    """ADR-002 drift guard: a new shipped skill must never become a legal handle."""
    assert set(_ALL_SKILLS) <= set(_wm().RESERVED_HANDLES)
    for stage in ("research", "spec", "execute", "review", "verify", "wrapup", "loop", "help"):
        assert _wm().handle_error(f"hm-{stage}") is not None


# ---------------------------------------------------------------------------
# AC-006 — invalid or colliding handles are rejected without touching harness.yaml
# ---------------------------------------------------------------------------

_AC006 = load_golden_table(_SPEC_YAML, "AC-006")


def _materialise(handle: str) -> str:
    return "a" * 65 if handle == "65 x a" else handle


@pytest.mark.parametrize("row", _AC006, ids=[r.input["handle"] for r in _AC006])
def test_ac006_invalid_handle_rejected(row: Any, tmp_path: Path) -> None:
    handle = _materialise(row.input["handle"])
    rejected = row.expected["rejected"]
    # handle_error returns the rule class the golden table names (None = accepted)
    assert _wm().handle_error(handle) == row.expected["reason"]
    if rejected:
        with pytest.raises(ValidationError):
            _config_cls()(name="Atlas", handle=handle)

    repo = tmp_path / "proj"
    repo.mkdir()
    assert _cli(repo).exit_code == 0
    before = (repo / ".claude" / "harness.yaml").read_bytes()
    res = _cli(repo, "--update", "--world-model-name", "Atlas", "--world-model-handle", handle)
    if rejected:
        assert res.exit_code != 0, res.output
        assert (
            i18n.t(f"world_model_handle_{row.expected['reason']}", "en", handle=handle)
            in res.output
        )
        assert (repo / ".claude" / "harness.yaml").read_bytes() == before
    else:
        assert res.exit_code == 0, res.output
        assert _read_yaml(repo)["world_model"]["handle"] == handle


def test_ac006_rejection_message_follows_locale(tmp_path: Path) -> None:
    repo = tmp_path / "proj"
    repo.mkdir()
    assert _cli(repo, "--locale", "ko").exit_code == 0
    res = _cli(repo, "--update", "--world-model-handle", "intent-layer")
    assert res.exit_code != 0
    ko = i18n.t("world_model_handle_collision", "ko", handle="intent-layer")
    assert ko != i18n.t("world_model_handle_collision", "en", handle="intent-layer")
    assert ko in res.output


@pytest.mark.parametrize("name", ["", "   ", "two\nlines", "tab\there", "x" * 41])
def test_ac006_invalid_display_name_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        _config_cls()(name=name, handle="maker")


def test_ac006_hand_edited_reserved_handle_fails_load(tmp_path: Path) -> None:
    """Critical #1: the rule is a load-time invariant, not only an input-prompt check."""
    repo = tmp_path / "proj"
    repo.mkdir()
    assert _cli(repo).exit_code == 0
    data = _read_yaml(repo)
    data["world_model"] = {"name": "PK", "handle": "project-knowledge"}
    _write_yaml(repo, data)
    skill = repo / ".claude/skills/project-knowledge/SKILL.md"
    before = skill.read_bytes()
    res = _cli(repo, "--update")
    assert res.exit_code != 0, res.output
    assert skill.read_bytes() == before


def test_partial_key_derives_handle_from_name() -> None:
    cfg = _config_cls().model_validate({"name": "Atlas"})
    assert cfg.handle == "atlas"
    assert _config_cls().model_validate({"name": "비비"}).handle == "maker"
    assert _config_cls().model_validate({}).name == "Maker"


# ---------------------------------------------------------------------------
# AC-008 — world_model survives load and re-render unchanged (property)
# ---------------------------------------------------------------------------

_HANDLES = st.from_regex(r"[a-z][a-z0-9]{0,8}(-[a-z0-9]{1,6}){0,2}", fullmatch=True).filter(
    lambda h: not h.startswith("hm-") and h not in _ALL_SKILLS
)
_NAMES = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs", "Zl", "Zp")), min_size=1, max_size=40
).filter(lambda s: s.strip() == s and s != "")


@settings(max_examples=12, derandomize=True, deadline=None)
@given(name=_NAMES, handle=_HANDLES)
def test_ac008_world_model_roundtrip_property(name: str, handle: str) -> None:
    import tempfile

    original = _config_cls()(name=name, handle=handle)
    a = interview(_profile(), autoloop_mode=True).model_copy(update={"world_model": original})
    with tempfile.TemporaryDirectory() as d:
        first = Path(d) / "first"
        render(
            synthesize(_profile(), a),
            first / ".claude",
            dry_run=False,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
        reloaded = answers_from_harness_yaml(first / ".claude" / "harness.yaml")
        assert reloaded is not None
        assert reloaded.world_model == original
        second = Path(d) / "second"
        render(
            synthesize(_profile(), reloaded),
            second / ".claude",
            dry_run=False,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
        again = answers_from_harness_yaml(second / ".claude" / "harness.yaml")
        assert again is not None
        assert again.world_model == original


def test_ac008_preset_switch_keeps_world_model(tmp_path: Path) -> None:
    for preset_from, preset_to in (("Side", "Production"), ("Production", "Side")):
        repo = tmp_path / preset_from / "proj"
        repo.mkdir(parents=True)
        assert _cli(repo, "--preset", preset_from, "--world-model-name", "Atlas").exit_code == 0
        res = _cli(repo, "--update", "--preset", preset_to)
        assert res.exit_code == 0, res.output
        assert _read_yaml(repo)["world_model"] == {"name": "Atlas", "handle": "atlas"}
        assert (repo / ".claude/skills/atlas/SKILL.md").is_file()


# ---------------------------------------------------------------------------
# AC-009 — ci flags set the world model name and handle
# ---------------------------------------------------------------------------


def run_ci(tmp: Path, **flags: str) -> Path:
    repo = tmp / "proj"
    repo.mkdir(parents=True, exist_ok=True)
    args: list[str] = []
    if "world_model_name" in flags:
        args += ["--world-model-name", flags["world_model_name"]]
    if "world_model_handle" in flags:
        args += ["--world-model-handle", flags["world_model_handle"]]
    res = _cli(repo, *args)
    assert res.exit_code == 0, res.output
    return repo


def test_ac_009_ci_flags_set_world_model(tmp_path: Path) -> None:
    def load_config(repo: Path) -> Any:
        return _config_cls().model_validate(_read_yaml(repo)["world_model"])

    repo = run_ci(tmp_path, world_model_name="Atlas")
    assert load_config(repo).handle == "atlas"
    assert (repo / ".claude/skills/atlas/SKILL.md").is_file()


def test_ac009_explicit_handle_wins(tmp_path: Path) -> None:
    repo = run_ci(tmp_path, world_model_name="비비", world_model_handle="bibi")
    assert _read_yaml(repo)["world_model"] == {"name": "비비", "handle": "bibi"}


def test_ac009_underivable_name_without_handle_exits_nonzero(tmp_path: Path) -> None:
    repo = tmp_path / "proj"
    repo.mkdir()
    res = _cli(repo, "--world-model-name", "비비")
    assert res.exit_code != 0
    assert "--world-model-handle" in res.output
    assert not (repo / ".claude" / "harness.yaml").exists()
