"""AC-007: public configuration, generated dispatch, actual provider and ledger.

The legacy-provider regression is intentionally GREEN before this feature: it
forbids replacing the existing provider set, while the RED Claude render/CLI
siblings require the additive new provider to exist.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness_maker import second_opinion_invoke as invoker
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import (
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionConfig,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

FINDING = {
    "severity": "high",
    "file": "demo.py",
    "line": 9,
    "message": "Missing boundary check",
    "evidence": "index can equal size",
}


def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, invalid: bool = False) -> None:
    cli = tmp_path / "claude"
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "structured_output": {"summary": "Review", "findings": [FINDING], "confidence": None},
    }
    raw = "secret-SENTINEL invalid" if invalid else json.dumps([payload])
    cli.write_text(
        f"#!{sys.executable}\nimport sys\n"
        "if '--help' in sys.argv:\n"
        " print('--print --safe-mode --tools --no-session-persistence "
        "--output-format --json-schema')\n"
        "else:\n"
        " sys.stdin.read()\n"
        f" print({raw!r})\n"
    )
    cli.chmod(0o700)
    agy = tmp_path / "agy"
    agy.write_text(f"#!{sys.executable}\nraise SystemExit(1)\n")
    agy.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])


@pytest.mark.parametrize("stage", ["review", "spec"])
@pytest.mark.parametrize("invalid", [False, True])
def test_ac_007_real_transport_to_provider_and_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, invalid: bool
) -> None:
    fake_claude(tmp_path, monkeypatch, invalid=invalid)
    result = invoker.invoke(
        model="claude", prompt="Synthetic review", slug="test", stage=stage, base_root=tmp_path
    )
    expected = "failed" if invalid else "invoked"
    assert result["status"] == expected
    assert result["model"] == "claude"
    if invalid:
        assert result["findings"] == []
        assert "secret-SENTINEL" not in json.dumps(result)
    else:
        assert len(result["findings"]) == 1
        finding = result["findings"][0]
        assert finding["source"] == "claude"
        assert finding["severity"] == "P1"
        assert finding["file"] == "demo.py"
        assert finding["line"] == 9
        assert finding["summary"] == FINDING["message"]
        assert finding["evidence"] == FINDING["evidence"]
        assert finding["id"]
    rows = [
        json.loads(line)
        for line in (tmp_path / ".claude/observability/second-opinion.jsonl")
        .read_text()
        .splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["model"] == "claude"
    assert rows[0]["status"] == expected
    assert rows[0]["stage"] == stage


def test_ac_007_public_cli_accepts_claude_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_claude(tmp_path, monkeypatch)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=30)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Synthetic specification review")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.second_opinion_invoke",
            "--model",
            "claude",
            "--stage",
            "spec",
            "--slug",
            "test",
            "--prompt-file",
            str(prompt),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "invoked"


def test_ac_007_config_render_roundtrip_preserves_claude(tmp_path: Path) -> None:
    opinion = SecondOpinionConfig.model_validate(
        {"models": ["claude", "codex"], "claude": {"model": "sonnet", "timeout": 45.0}}
    )
    answers = InterviewAnswers(targets=[Target.CODEX], second_opinion=opinion)
    render(
        synthesize(ProjectProfile(), answers), tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME
    )
    restored = answers_from_harness_yaml(tmp_path / ".claude/harness.yaml")
    assert restored is not None
    assert restored.second_opinion.models == ["claude", "codex"]
    assert restored.second_opinion.model_dump()["claude"] == {"model": "sonnet", "timeout": 45.0}
    review = (tmp_path / ".agents/skills/hm-review/SKILL.md").read_text()
    assert "hm second_opinion_invoke --model claude" in review
    assert "--stage review" in review
    assert "--safe-mode" in review
    assert "--dangerously-skip-permissions" not in review


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_ac_007_invalid_provider_deadline_rejected(timeout: float) -> None:
    SecondOpinionConfig.model_validate({"models": ["claude"], "claude": {"timeout": 10.0}})
    with pytest.raises(ValueError, match="timeout"):
        SecondOpinionConfig.model_validate({"models": ["claude"], "claude": {"timeout": timeout}})


def test_ac_007_legacy_provider_config_still_valid() -> None:
    config = SecondOpinionConfig.model_validate({"models": ["codex", "antigravity"]})
    assert config.models == ["codex", "antigravity"]
    assert SecondOpinionConfig().models == []


def test_ac_007_spec_dispatch_partial_supports_absorbed_stage() -> None:
    from harness_maker.render import _make_env

    template = _make_env().get_template("agents/_partials/second_opinion_dispatch.md.j2")
    text = template.render(
        config={"second_opinion": {"models": ["claude"]}},
        second_opinion_stage="spec",
        is_codex=True,
        harness_maker_src_path="harness-maker==0.58.0",
    )
    assert "hm second_opinion_invoke --model claude" in text
    assert "--stage spec" in text
    assert "--dangerously-skip-permissions" not in text


def test_ac_007_saved_nondefault_model_reaches_actual_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_claude(tmp_path, monkeypatch)
    config = tmp_path / ".claude/harness.yaml"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "second_opinion": {
                    "models": ["claude"],
                    "claude": {"model": "configured-model-identity", "timeout": 2.0},
                }
            }
        )
    )
    capture = tmp_path / "argv.json"
    cli = tmp_path / "claude"
    cli.write_text(
        cli.read_text()
        .replace("import sys", "import sys, json")
        .replace("--output-format --json-schema", "--output-format --json-schema --model")
        .replace(
            " sys.stdin.read()",
            f" json.dump(sys.argv[1:], open({str(capture)!r}, 'w'))\n sys.stdin.read()",
        )
    )
    result = invoker.invoke(
        model="claude",
        prompt="Synthetic review",
        slug="configured",
        stage="review",
        base_root=tmp_path,
    )
    assert result["status"] == "invoked"
    argv = json.loads(capture.read_text())
    assert argv[argv.index("--model") + 1] == "configured-model-identity"


def test_ac_007_saved_short_deadline_limits_actual_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_claude(tmp_path, monkeypatch)
    config = tmp_path / ".claude/harness.yaml"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "second_opinion": {
                    "models": ["claude"],
                    "claude": {"timeout": 1.0},
                }
            }
        )
    )
    capture = tmp_path / "started"
    cli = tmp_path / "claude"
    cli.write_text(
        cli.read_text()
        .replace("import sys", "import sys, time")
        .replace(
            " sys.stdin.read()",
            f" open({str(capture)!r}, 'w').write('invoked')\n time.sleep(4)\n sys.stdin.read()",
        )
    )
    started = time.monotonic()
    result = invoker.invoke(
        model="claude",
        prompt="Synthetic review",
        slug="deadline",
        stage="spec",
        base_root=tmp_path,
    )
    assert capture.read_text() == "invoked"
    assert result["status"] == "skipped"
    assert result["reason"] == "timeout"
    assert time.monotonic() - started < 3


@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
def test_ac_007_disabled_claude_preserves_saved_model_and_timeout(
    tmp_path: Path, preset: Preset
) -> None:
    opinion = SecondOpinionConfig.model_validate(
        {
            "models": [],
            "claude": {"model": "saved-when-disabled", "timeout": 17.0},
        }
    )
    answers = InterviewAnswers(targets=[Target.CODEX], second_opinion=opinion, preset=preset)
    render(
        synthesize(ProjectProfile(), answers), tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME
    )
    restored = answers_from_harness_yaml(tmp_path / ".claude/harness.yaml")
    assert restored is not None
    assert restored.second_opinion.models == []
    assert restored.second_opinion.claude.model == "saved-when-disabled"
    assert restored.second_opinion.claude.timeout == 17.0
