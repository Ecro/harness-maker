"""SPEC-retired-wiring: the retired loop's hook, Codex profiles, dead partials and progress file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker import render
from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

TEMPLATES = Path(render.__file__).parent / "templates"
_ARGS = ("--autoloop", "--targets", "claude-code,codex", "--locale", "en")
OLD_STOP = (
    'uv run --no-project --with "{src}" python -m harness_maker.hooks.loop_gate --mode stop-hook'
)
SPAN_END = 'uv run --no-project --with "{src}" python -m harness_maker.worktree span-end'
FLUSH = 'uv run --no-project --with "{src}" python -m harness_maker.hooks.flush_session'
USER_HOOK = "echo my-own-stop-hook"
PARTIALS = (
    "step_manifest", "stage_end_summary", "gate0_receipt", "comprehension_block",
    "worktree_preflight", "codex_autopilot_advance",
)  # fmt: skip


def _make(tmp_path: Path, preset: str) -> tuple[Path, Path]:
    project = init_project(tmp_path / "proj")
    home = tmp_path / "home"
    proc = run_make(project, (*_ARGS, "--preset", preset), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return project, home


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_ac_001_fresh_render_has_no_loop_gate(tmp_path: Path, preset: str) -> None:
    project, _ = _make(tmp_path, preset)
    settings = (project / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "loop_gate" not in settings
    assert "loop_gate" not in (project / ".codex" / "hooks.json").read_text(encoding="utf-8")
    stop = json.loads(settings)["hooks"]["Stop"]
    assert any("worktree span-end" in h["command"] for g in stop for h in g["hooks"])


def test_ac_001_loop_gate_is_retired() -> None:
    assert (
        "<HM>:harness_maker.hooks.loop_gate --mode stop-hook"
        in render._HARNESS_RETIRED_HOOK_INVOCATIONS
    )


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_ac_001_rerender_retires_the_old_stop_group(tmp_path: Path, preset: str) -> None:
    project, home = _make(tmp_path, preset)
    path = project / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    src = str(HEAD_SRC.parent)
    data["hooks"]["Stop"] = [
        {
            "hooks": [
                {"type": "command", "command": OLD_STOP.format(src=src), "timeout": 10},
                {"type": "command", "command": SPAN_END.format(src=src), "timeout": 10},
            ]
        },
        {"hooks": [{"type": "command", "command": USER_HOOK}]},
    ]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    proc = run_make(project, (*_ARGS, "--preset", preset), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    stop = json.loads(path.read_text(encoding="utf-8"))["hooks"]["Stop"]
    commands = [h["command"] for g in stop for h in g["hooks"]]
    assert not any("loop_gate" in c for c in commands), commands
    assert sum("worktree span-end" in c for c in commands) == 1, commands
    assert USER_HOOK in commands


def test_ac_001_rerender_retires_the_old_codex_stop_group(tmp_path: Path) -> None:
    project, home = _make(tmp_path, "Side")
    path = project / ".codex" / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    src = "/old/cache/harness-maker"  # the normaliser ignores the --with path
    data["hooks"]["Stop"] = [
        {"hooks": [{"type": "command", "command": OLD_STOP.format(src=src), "timeout": 5}]},
        {"hooks": [{"type": "command", "command": FLUSH.format(src=src), "timeout": 10}]},
        {"hooks": [{"type": "command", "command": USER_HOOK}]},
    ]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    proc = run_make(project, (*_ARGS, "--preset", "Side"), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    stop = json.loads(path.read_text(encoding="utf-8"))["hooks"]["Stop"]
    commands = [h["command"] for g in stop for h in g["hooks"]]
    assert not any("loop_gate" in c for c in commands), commands
    assert sum("hooks.flush_session" in c for c in commands) == 1, commands
    assert USER_HOOK in commands


def test_ac_002_make_leaves_the_home_codex_config_alone(tmp_path: Path) -> None:
    project, home = _make(tmp_path, "Side")
    assert not (home / ".codex" / "config.toml").exists()
    assert "profiles" not in (project / ".codex" / "config.toml").read_text(encoding="utf-8")


def test_ac_003_partials_are_gone() -> None:
    for name in PARTIALS:
        assert not list(TEMPLATES.rglob(f"{name}.md.j2")), name
    for template in TEMPLATES.rglob("*.j2"):
        text = template.read_text(encoding="utf-8")
        for name in PARTIALS:
            assert f"{name}.md.j2" not in text, (template, name)


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_ac_004_no_progress_file_pointer(tmp_path: Path, preset: str) -> None:
    project, _ = _make(tmp_path, preset)
    paths = [project / "AGENTS.md", *(project / ".codex").rglob("*.toml")]
    for tree in (".claude", ".agents"):
        paths += (project / tree).rglob("*.md")
    for path in paths:
        assert ".claude-progress.json" not in path.read_text(encoding="utf-8"), path
