"""SPEC-review-effect-measurement — the /hm:metrics step, the registry measure_cmd and the doc."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.step_sensitivity import REGISTRY
from harness_maker.synthesize import synthesize

_REPO = Path(__file__).resolve().parents[2]

RULE_1_SENTENCE = (
    "**Rule 1.** With at least 20 counted reviews (status parsed or none, deduped, after "
    "exclusions), if the 95% upper bound of marginal yield is below 25% and the 95% upper bound "
    "of seeded recall is below 50%, register a candidate task that makes review opt-in."
)
RULE_2_SENTENCE = (
    "**Rule 2.** With at least 20 counted reviews, if the 95% lower bound of the escape miss rate "
    "is above 50%, register a candidate task that reconsiders the lens fan-out default."
)


@pytest.fixture(scope="module")
def rendered_metrics_variants(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    root = tmp_path_factory.mktemp("metrics")
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE, Target.CODEX]),
    )
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    found = []
    for f in sorted(root.rglob("*.md")):
        text = f.read_text(encoding="utf-8")
        if "delivery_metrics candidates" in text:
            found.append(text)
    return found


def test_ac_010_metrics_renders_escape_step(rendered_metrics_variants: list[str]) -> None:
    # Guards the guard: the Claude command must have been found (Codex renders no metrics).
    assert len(rendered_metrics_variants) >= 1
    for t in rendered_metrics_variants:
        assert "review_effect escape-candidates" in t
        assert "review_effect escape " in t


def _entry(stage: str, ordinal: str):  # type: ignore[no-untyped-def]
    return next(e for e in REGISTRY if e.key == (stage, ordinal))


def test_ac_011_step6_measure_cmd_runs(tmp_path: Path) -> None:
    e = _entry("execute", "Step 6")
    assert e.remeasure_on == ("model_release",)
    assert e.measure_cmd.startswith("harness-maker: hm review_effect report")
    _repo, _, cmd = e.measure_cmd.partition(": ")
    argv = shlex.split(cmd)
    assert argv[0] == "hm"
    (tmp_path / ".git").mkdir()
    r = subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", *argv[1:]],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr


def test_ac_012_reference_doc_rule() -> None:
    doc = (_REPO / "docs" / "reference" / "review-effect.md").read_text(encoding="utf-8")
    for s in (
        RULE_1_SENTENCE,
        RULE_2_SENTENCE,
        "This rule is never reinterpreted after it fires.",
        "review_effect seed",
        "code-reviewer",
        "review_effect score",
        "--record",
        "scratch worktree",
    ):
        assert s in doc, s
