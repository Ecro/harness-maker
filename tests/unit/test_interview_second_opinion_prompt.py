"""The second-opinion prompt after PLAN-onboarding-interview-ux Phase 4 (P1-7, P1-4).

Two defects are pinned here:

* The prompt was bare free text with no indication of which CLI is actually present, and a
  typo was dropped with a `logger.warning` the user never saw — so "I typed antigravty and
  it silently did nothing" was indistinguishable from "I declined".
* `consensus` and `caching` were asked with no explanation of their valid values or meaning,
  and neither changes any behaviour (ADR-003). They are gone from the interview; the fields
  keep their preset defaults.

These tests dispatch on the prompt TEXT rather than on a positional list of blanks, because
a positional list silently re-points at a different question the moment a prompt is added or
removed — which is exactly what this phase does to every other test in this directory.
"""

from __future__ import annotations

import shutil

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


def _answering(
    monkeypatch: pytest.MonkeyPatch,
    answers: dict[str, str],
    *,
    installed: set[str] = frozenset(),  # type: ignore[assignment]
) -> list[str]:
    """Drive the interview by prompt substring; return every prompt+printed line seen."""

    seen: list[str] = []

    def _which(cmd: str) -> str | None:
        return f"/usr/bin/{cmd}" if cmd in installed else None

    monkeypatch.setattr(shutil, "which", _which)
    monkeypatch.setattr("harness_maker.interview._fetch_agy_models", lambda: [])

    def _input(prompt: str) -> str:
        seen.append(prompt)
        for needle, answer in answers.items():
            if needle.lower() in prompt.lower():
                return answer
        return ""

    monkeypatch.setattr("builtins.input", _input)
    monkeypatch.setattr("builtins.print", lambda *a, **_k: seen.append(" ".join(map(str, a))))
    return seen


def test_the_prompt_reports_which_cli_is_actually_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _answering(monkeypatch, {}, installed={"codex"})
    interview(_profile(), autoloop_mode=False)
    blob = "\n".join(seen)
    assert "codex" in blob
    assert "antigravity" in blob
    # The present one and the absent one must be distinguishable, not both listed flatly.
    assert "not installed" in blob


def test_the_prompt_never_claims_a_detected_cli_is_authenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`shutil.which` proves a binary exists, nothing more.

    If the prompt implies readiness, a user enables a model whose first real call degrades
    to a skip, and the harness looks broken rather than unauthenticated.
    """
    seen = _answering(monkeypatch, {}, installed={"codex", "agy"})
    interview(_profile(), autoloop_mode=False)
    blob = "\n".join(seen).lower()
    assert "authentication not verified" in blob or "not verified" in blob


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("", []),
        ("1", ["codex"]),
        ("2", ["antigravity"]),
        ("3", ["codex", "antigravity"]),
        ("4", []),
        ("codex", ["codex"]),
        ("codex,antigravity", ["codex", "antigravity"]),
        ("antigravity", ["antigravity"]),
    ],
    ids=[
        "blank-is-none",
        "numbered-codex",
        "numbered-antigravity",
        "numbered-both",
        "numbered-none",
        "legacy-name",
        "legacy-comma-list",
        "legacy-antigravity",
    ],
)
def test_numbered_and_legacy_name_entry_both_select(
    monkeypatch: pytest.MonkeyPatch, answer: str, expected: list[str]
) -> None:
    """Numbered entry is added; the comma list keeps working (it is documented in make.md)."""
    _answering(monkeypatch, {"Enable which models": answer})
    result = interview(_profile(), autoloop_mode=False)
    assert result.second_opinion.models == expected
    assert result.second_opinion.enabled is bool(expected)


def test_an_unrecognised_answer_is_re_asked_not_silently_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The old code logged a warning and returned []; the user saw a silent decline."""
    replies = iter(["antigravty", "codex"])  # typo, then a correction
    seen: list[str] = []

    monkeypatch.setattr(shutil, "which", lambda _c: None)
    monkeypatch.setattr("harness_maker.interview._fetch_agy_models", lambda: [])

    def _input(prompt: str) -> str:
        seen.append(prompt)
        if "enable which models" in prompt.lower():
            return next(replies, "")
        return ""

    monkeypatch.setattr("builtins.input", _input)
    result = interview(_profile(), autoloop_mode=False)

    asked = [p for p in seen if "enable which models" in p.lower()]
    assert len(asked) == 2, asked
    assert result.second_opinion.models == ["codex"]


def test_a_persistently_bad_answer_terminates_instead_of_looping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-prompting must be bounded — an unattended stdin must not spin forever."""

    monkeypatch.setattr(shutil, "which", lambda _c: None)
    monkeypatch.setattr("harness_maker.interview._fetch_agy_models", lambda: [])
    asked: list[str] = []

    def _input(prompt: str) -> str:
        if "enable which models" in prompt.lower():
            asked.append(prompt)
            return "nonsense"
        return ""

    monkeypatch.setattr("builtins.input", _input)
    result = interview(_profile(), autoloop_mode=False)
    assert 1 < len(asked) <= 4, len(asked)
    assert result.second_opinion.models == []


def test_the_interview_no_longer_asks_about_consensus_or_caching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-003. Neither value changes any behaviour, so asking was pure friction.

    Asserted over prompts only — `consensus-arbiter` legitimately appears in printed
    explanatory text and in the reviewer allow-list, so a whole-output scan would be a
    false positive.
    """
    seen = _answering(monkeypatch, {})
    interview(_profile(), autoloop_mode=False)
    # Match on the UN-stripped string: `rstrip()` first would delete the trailing space of
    # `"... [Y/n] "`, so three of the four arms could never fire and `_ask_worktree`'s
    # prompt was silently outside the filter — the gate would miss a `consensus` question
    # re-introduced in that style.
    prompts = [p for p in seen if p.endswith((": ", ":", "] ", ") "))]
    assert prompts, "no prompts captured — the filter would pass vacuously"
    assert any("[y/n]" in p.lower() for p in prompts), (
        "the `[Y/n]`-style prompt is not being captured; the filter is too narrow again"
    )
    offenders = [p for p in prompts if "consensus" in p.lower() or "caching" in p.lower()]
    assert offenders == [], offenders


def test_consensus_and_caching_still_carry_their_preset_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-003 keeps the fields and the harness.yaml keys — only the questions go."""
    _answering(monkeypatch, {})
    side = interview(_profile(), autoloop_mode=False)
    assert side.preset == Preset.SIDE
    assert side.consensus == "single"
    assert side.caching == "agent-aware"

    _answering(monkeypatch, {"preset": "Production"})
    prod = interview(_profile(), autoloop_mode=False)
    assert prod.preset == Preset.PRODUCTION
    assert prod.consensus == "cross-check"
