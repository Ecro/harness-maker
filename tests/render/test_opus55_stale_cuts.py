"""SPEC-opus55-stale-cuts: the stale skill, the dead session hook and the CLAUDE.md stub lines."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker import interview, render, synthesize
from harness_maker.inert_keys import inert_key_warnings
from tests._overhaul_p1_ref import HEAD_SRC, clean_env, init_project, ref_root, run_make

#: main at 0.65.5, the last render that shipped what this SPEC retires.
REF_0655 = "735db8fdf6d588e8214b6b21363b6ab1120d85c4"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "opus55_stale_cuts"
PATHS_0655: dict[str, list[str]] = json.loads(
    (FIXTURE / "render_paths_0655.json").read_text(encoding="utf-8")
)
SESSION_README = ".claude/memory/session/README.md"
RETIRED_PATHS = frozenset(
    {
        ".claude/skills/worktree-isolator/SKILL.md",
        ".agents/skills/worktree-isolator/SKILL.md",
        ".agents/skills/worktree-isolator/agents/openai.yaml",
        SESSION_README,
    }
)
#: Paths a later SPEC removed from the render: SPEC-intent-lean deleted the workflow-feedback
#: reference of the intent-layer skill.
LATER_REMOVED = frozenset(
    {
        ".claude/skills/intent-layer/references/workflow-feedback.md",
        ".agents/skills/intent-layer/references/workflow-feedback.md",
    }
)
RUBRIC_SKILLS = ("agent-quality-rubric", "ai-readiness-rubric", "context-linter")
_PHASES = ("Phase 3 stub", "Phase 6", "Phase 9")
STUBS = {
    "en": (*_PHASES, "## Caching", "## Reviewers", "## Worktree", "## Memory"),
    "ko": (*_PHASES, "## 캐싱", "## 리뷰어", "## 자동 루프 / 워크트리", "## 메모리"),
}
KEPT_BY_LOCALE = {
    "en": ("## Workflow", "## Output Language"),
    "ko": ("## 워크플로우", "## 출력 언어"),
}
KEPT = (
    "## Context discipline",
    "## Project knowledge",
    "## World model",
    "<!-- @hm:user:project-rules -->",
    "<!-- @hm:user:extensions -->",
)
PRESETS = ("Side", "Production")
USER_HOOK = "echo my-own-hook"
#: A re-render's own records: the backup of what it replaced and its orphan log.
_RERENDER_STATE = (".git/", ".backup-", ".claude/.backup", ".claude/observability/orphans-")


def _args(preset: str, locale: str = "en") -> tuple[str, ...]:
    return ("--autoloop", "--targets", "claude-code,codex", "--locale", locale, "--preset", preset)


def _make(project: Path, home: Path, preset: str, *, src: Path, locale: str = "en") -> Path:
    proc = run_make(init_project(project), _args(preset, locale), src=src, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return project


def _paths(root: Path) -> set[str]:
    out: set[str] = set()
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not rel.startswith(_RERENDER_STATE):
            out.add(rel)
    return out


def _hook_commands(root: Path) -> dict[str, list[str]]:
    """Every hook command of a render, keyed `<file>:<event>`."""
    out: dict[str, list[str]] = {}
    for rel in (".claude/settings.json", ".codex/hooks.json"):
        hooks = json.loads((root / rel).read_text(encoding="utf-8")).get("hooks", {})
        for event, groups in hooks.items():
            out[f"{rel}:{event}"] = [h["command"] for g in groups for h in g["hooks"]]
    return out


@pytest.fixture(scope="module")
def fresh(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, str], Path]:
    """One HEAD render per preset and locale."""
    base = tmp_path_factory.mktemp("opus55-fresh")
    return {
        (preset, locale): _make(
            base / f"p-{preset}-{locale}",
            base / f"h-{preset}-{locale}",
            preset,
            src=HEAD_SRC,
            locale=locale,
        )
        for preset in PRESETS
        for locale in ("en", "ko")
    }


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("locale", ["en", "ko"])
def test_ac_001_claude_md_has_no_stub_lines(
    fresh: dict[tuple[str, str], Path], preset: str, locale: str
) -> None:
    md = (fresh[(preset, locale)] / "CLAUDE.md").read_text(encoding="utf-8")
    assert [s for s in STUBS[locale] if s in md] == []
    assert [k for k in (*KEPT_BY_LOCALE[locale], *KEPT) if k not in md] == []


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_002_fresh_render_is_the_0655_set_minus_the_retired_paths(
    fresh: dict[tuple[str, str], Path], preset: str
) -> None:
    # The recorded list holds the render's date-stamped orphan log; drop it on both sides.
    reference = {p for p in PATHS_0655[preset] if not p.startswith(_RERENDER_STATE)}
    assert reference >= RETIRED_PATHS
    assert _paths(fresh[(preset, "en")]) == reference - RETIRED_PATHS - LATER_REMOVED


def test_ac_003_worktree_isolator_is_a_retired_name() -> None:
    name = "worktree-isolator"
    assert name in synthesize.RETIRED_SKILLS
    assert name not in synthesize._ALL_SKILLS
    assert name not in interview._ALL_SKILLS
    assert not (Path(render.__file__).parent / "templates" / "skills" / name).exists()
    warnings = inert_key_warnings({"skills": {"enabled": [name, "intent-layer"]}})
    assert any(name in w and "retired" in w for w in warnings), warnings
    for rubric in RUBRIC_SKILLS:
        assert rubric in synthesize._ALL_SKILLS
        assert rubric in interview._ALL_SKILLS


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_004_no_session_hook_and_no_hot_tier(
    fresh: dict[tuple[str, str], Path], preset: str
) -> None:
    root = fresh[(preset, "en")]
    commands = _hook_commands(root)
    assert [k for k, cmds in commands.items() if any("flush_session" in c for c in cmds)] == []
    assert [k for k, cmds in commands.items() if not cmds] == []
    settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    groups = settings["hooks"]["PreCompact"]
    assert sorted(g["matcher"] for g in groups) == ["auto", "manual"]
    for group in groups:
        assert any("worktree span-end" in h["command"] for h in group["hooks"]), group
    for rel in (".claude/commands/hm/execute.md", ".agents/skills/hm-execute/SKILL.md"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "Hot tier" not in text, rel
        assert "memory/session" not in text, rel
        assert "hm memory_retrieve" in text, rel


def _ref_tree(
    tmp_path: Path, cache: Path, preset: str, *, user_hooks: bool = True
) -> tuple[Path, Path]:
    """A tree rendered by the 0.65.5 source, by default with a user hook beside each shipped one."""
    project, home = tmp_path / "proj", tmp_path / "home"
    _make(project, home, preset, src=ref_root(cache, REF_0655) / "src")
    assert _paths(project) >= RETIRED_PATHS
    if not user_hooks:
        return project, home
    for rel, event in ((".claude/settings.json", "PreCompact"), (".codex/hooks.json", "Stop")):
        path = project / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        assert any(
            "flush_session" in h["command"] for g in data["hooks"][event] for h in g["hooks"]
        )
        group = {"hooks": [{"type": "command", "command": USER_HOOK}]}
        if event == "PreCompact":
            group["matcher"] = "manual"  # type: ignore[assignment]
        data["hooks"][event].append(group)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return project, home


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_005_rerender_over_0655_retires_pristine_copies(
    fresh: dict[tuple[str, str], Path],
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    preset: str,
) -> None:
    project, home = _ref_tree(tmp_path, tmp_path_factory.getbasetemp() / "opus55-ref", preset)
    proc = run_make(project, _args(preset), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    # memory/ files carry no content hash, so the sweep keeps the README it cannot prove pristine.
    assert _paths(project) == _paths(fresh[(preset, "en")]) | {SESSION_README}
    commands = _hook_commands(project)
    assert [k for k, cmds in commands.items() if any("flush_session" in c for c in cmds)] == []
    assert USER_HOOK in commands[".claude/settings.json:PreCompact"]
    assert USER_HOOK in commands[".codex/hooks.json:Stop"]


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_005_a_pristine_rerender_leaves_no_empty_event(
    fresh: dict[tuple[str, str], Path],
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    preset: str,
) -> None:
    """The common upgrade: nothing of the user's in the hook files (REVIEW F-002)."""
    cache = tmp_path_factory.getbasetemp() / "opus55-ref"
    project, home = _ref_tree(tmp_path, cache, preset, user_hooks=False)
    proc = run_make(project, _args(preset), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    commands = _hook_commands(project)
    assert [k for k, cmds in commands.items() if not cmds] == []
    assert commands == _hook_commands(fresh[(preset, "en")])


def test_ac_005_a_user_command_inside_our_group_survives(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    project, home = _ref_tree(tmp_path, tmp_path_factory.getbasetemp() / "opus55-ref", "Side")
    mixed = "echo inside-our-group"
    for rel, event in ((".claude/settings.json", "PreCompact"), (".codex/hooks.json", "Stop")):
        path = project / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        ours = next(
            g
            for g in data["hooks"][event]
            if any("flush_session" in h["command"] for h in g["hooks"])
        )
        ours["hooks"].append({"type": "command", "command": mixed})
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    proc = run_make(project, _args("Side"), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    commands = _hook_commands(project)
    assert [k for k, cmds in commands.items() if any("flush_session" in c for c in cmds)] == []
    assert mixed in commands[".claude/settings.json:PreCompact"]
    assert mixed in commands[".codex/hooks.json:Stop"]


def test_ac_005_an_edited_retired_skill_is_kept(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    project, home = _ref_tree(tmp_path, tmp_path_factory.getbasetemp() / "opus55-ref", "Side")
    skill = project / ".claude" / "skills" / "worktree-isolator" / "SKILL.md"
    skill.write_bytes(skill.read_bytes() + b"x")
    edited = skill.read_bytes()
    proc = run_make(project, _args("Side"), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert skill.read_bytes() == edited
    assert not (project / ".agents" / "skills" / "worktree-isolator").exists()


def test_ac_005_an_edited_codex_copy_keeps_its_invocation_policy(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Deleting the pristine `openai.yaml` beside a kept SKILL.md would let the stale skill
    trigger itself in Codex (REVIEW F-001)."""
    project, home = _ref_tree(tmp_path, tmp_path_factory.getbasetemp() / "opus55-ref", "Side")
    codex = project / ".agents" / "skills" / "worktree-isolator"
    skill, policy = codex / "SKILL.md", codex / "agents" / "openai.yaml"
    skill.write_bytes(skill.read_bytes() + b"x")
    edited, shipped_policy = skill.read_bytes(), policy.read_bytes()
    assert b"allow_implicit_invocation: false" in shipped_policy
    proc = run_make(project, _args("Side"), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert skill.read_bytes() == edited
    assert policy.read_bytes() == shipped_policy
    assert not (project / ".claude" / "skills" / "worktree-isolator").exists()


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_ac_006_the_stub_survives_a_closed_stdin(tmp_path: Path) -> None:
    """fd 0 closed before exec leaves `sys.stdin` as `None` (REVIEW F-004, G-001)."""
    probe = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.stdin)"],
        preexec_fn=lambda: os.close(0),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert probe.stdout.strip() == "None", "the harness no longer reproduces a closed stdin"
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.flush_session"],
        cwd=tmp_path,
        env=clean_env(home=tmp_path / "home", src=HEAD_SRC),
        preexec_fn=lambda: os.close(0),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]


def test_ac_006_the_old_hook_command_is_a_stub(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    (project / ".claude" / "memory" / "session").mkdir(parents=True)
    (project / ".claude-progress.json").write_text('{"phase": 2}', encoding="utf-8")
    before = _tree_bytes(project)
    payload = {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(project)}
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.flush_session"],
        cwd=project,
        env=clean_env(home=tmp_path / "home", src=HEAD_SRC, CLAUDE_PROJECT_DIR=str(project)),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert proc.stdout == ""
    assert _tree_bytes(project) == before
    assert "<HM>:harness_maker.hooks.flush_session" in render._HARNESS_RETIRED_HOOK_INVOCATIONS
