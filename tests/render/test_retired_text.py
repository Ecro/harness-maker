"""SPEC-retired-text AC-001..004: 0.64.0 renders describe what runs now, not retired machinery."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests._overhaul_p1_ref import HEAD_SRC, init_project, ref_root, run_make

PRESETS = ("Side", "Production")
#: SPEC Intent: the 0.64.0 render (main 79b16a99) these phrases were found in.
OLD_RENDER_SHA = "79b16a99"
RETIRED = re.compile(r"autoloop|autopilot|executor agent", re.I)
NEW_STATUS = "Snapshotting session progress..."
USER_CMD = "python3 -m my_precompact_hook"
_ARGS = (
    "--autoloop",
    "--targets",
    "claude-code,codex",
    "--locale",
    "en",
    "--second-opinion-models",
    "codex",
)

#: Rendered from a touched template, per SPEC AC-001 (and their Codex copies).
TOUCHED = (
    ".claude/agents/consensus-arbiter.md",
    ".claude/agents/code-verifier.md",
    ".codex/agents/consensus-arbiter.toml",
    ".codex/agents/code-verifier.toml",
    ".claude/commands/hm/health.md",
    ".claude/skills/worktree-isolator/SKILL.md",
    ".agents/skills/worktree-isolator/SKILL.md",
    ".claude/skills/intent-layer/SKILL.md",
    ".agents/skills/intent-layer/SKILL.md",
    ".claude/skills/maker/SKILL.md",
    ".agents/skills/maker/SKILL.md",
    ".claude/settings.json",
    ".codex/hooks.json",
)
REPLACEMENTS = (
    (
        ".claude/agents/consensus-arbiter.md",
        "Invoked by the review step of `/hm:execute` when second-opinion voters disagree on "
        "a finding's severity",
    ),
    (
        ".claude/agents/code-verifier.md",
        "Findings are proposals; the main session applies them.",
    ),
    (".claude/commands/hm/health.md", "## Non-interactive behavior"),
    (".claude/skills/worktree-isolator/SKILL.md", "issued in the task worktree"),
    (
        ".claude/skills/intent-layer/SKILL.md",
        "`hm intent status` reports the approval you record",
    ),
)
HOOK_FILES = (".claude/settings.json", ".codex/hooks.json")
#: The event each file runs `flush_session` on (SPEC AC-003).
FLUSH_EVENT = {".claude/settings.json": "PreCompact", ".codex/hooks.json": "Stop"}


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def get(preset: str) -> Path:
        if preset not in cache:
            base = tmp_path_factory.mktemp(f"retired-{preset}")
            project = init_project(base / "proj")
            proc = run_make(project, (*_ARGS, "--preset", preset), src=HEAD_SRC, home=base / "home")
            assert proc.returncode == 0, proc.stderr[-2000:]
            cache[preset] = project
        return cache[preset]

    return get


def _split(text: str) -> tuple[str, str]:
    """A provenance frontmatter head (if any) and the JSON body after it."""
    if text.startswith("---\n"):
        cut = text.index("\n---\n", 4) + 5
        return text[:cut], text[cut:]
    return "", text


def _hooks(path: Path) -> dict[str, Any]:
    hooks = json.loads(_split(path.read_text(encoding="utf-8"))[1])["hooks"]
    assert isinstance(hooks, dict)
    return hooks


def _flush_entries(hooks: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        h
        for groups in hooks.values()
        for g in groups
        for h in g["hooks"]
        if "flush_session" in h.get("command", "")
    ]


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_001_touched_renders_have_no_retired_token(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    hits = {}
    for rel in TOUCHED:
        path = root / rel
        assert path.is_file(), f"{rel} not rendered"
        found = sorted({m.group(0).lower() for m in RETIRED.finditer(path.read_text("utf-8"))})
        if found:
            hits[rel] = found
    assert hits == {}


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_002_replaced_texts_say_what_runs_now(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    for rel, text in REPLACEMENTS:
        assert text in (root / rel).read_text("utf-8"), rel
    for rel in HOOK_FILES:
        entries = _flush_entries(_hooks(root / rel))
        assert entries, rel
        assert {e.get("statusMessage") for e in entries} == {NEW_STATUS}, rel


def _user_group(rel: str) -> dict[str, Any]:
    group: dict[str, Any] = {"hooks": [{"type": "command", "command": USER_CMD}]}
    if FLUSH_EVENT[rel] == "PreCompact":
        group["matcher"] = "auto"
    return group


def _write_hooks(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    head, body = _split(path.read_text(encoding="utf-8"))
    data = json.loads(body)
    mutate(data["hooks"])
    path.write_text(head + json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _flush_groups(hooks: dict[str, Any], event: str) -> list[dict[str, Any]]:
    return [
        g
        for g in hooks.get(event, [])
        if any("flush_session" in h.get("command", "") for h in g["hooks"])
    ]


@pytest.fixture
def old_project(tmp_path: Path) -> Callable[[str], Path]:
    """A project rendered by the 0.64.0 templates, before this change."""

    def make(name: str) -> Path:
        project = init_project(tmp_path / name)
        old_src = ref_root(tmp_path / "ref", OLD_RENDER_SHA) / "src"
        proc = run_make(
            project, (*_ARGS, "--preset", "Production"), src=old_src, home=tmp_path / "home"
        )
        assert proc.returncode == 0, proc.stderr[-2000:]
        for rel in HOOK_FILES:
            olds = {e.get("statusMessage") for e in _flush_entries(_hooks(project / rel))}
            assert olds == {"Snapshotting autoloop progress..."}, (rel, olds)
        return project

    return make


def _rerender(project: Path, home: Path) -> None:
    proc = run_make(project, (*_ARGS, "--preset", "Production"), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]


def test_ac_003_rerender_replaces_status_in_owned_groups(
    old_project: Callable[[str], Path], tmp_path: Path
) -> None:
    project = old_project("own-group")
    shipped = {
        rel: len(_flush_groups(_hooks(project / rel), FLUSH_EVENT[rel])) for rel in HOOK_FILES
    }
    for rel in HOOK_FILES:

        def add(h: dict[str, Any], rel: str = rel) -> None:
            h.setdefault(FLUSH_EVENT[rel], []).append(_user_group(rel))

        _write_hooks(project / rel, add)
    _rerender(project, tmp_path / "home")
    for rel in HOOK_FILES:
        hooks = _hooks(project / rel)
        groups = _flush_groups(hooks, FLUSH_EVENT[rel])
        assert len(groups) == shipped[rel], (rel, groups)
        for g in groups:
            flush = [h for h in g["hooks"] if "flush_session" in h["command"]]
            assert len(flush) == 1, (rel, g)
            assert flush[0].get("statusMessage") == NEW_STATUS, (rel, g)
        assert hooks[FLUSH_EVENT[rel]].count(_user_group(rel)) == 1, rel


def test_ac_003_rerender_keeps_a_user_extended_group(
    old_project: Callable[[str], Path], tmp_path: Path
) -> None:
    project = old_project("mixed-group")
    before: dict[str, dict[str, Any]] = {}
    for rel in HOOK_FILES:

        def extend(h: dict[str, Any], rel: str = rel) -> None:
            group = _flush_groups(h, FLUSH_EVENT[rel])[0]
            group["hooks"].append({"type": "command", "command": USER_CMD})
            before[rel] = json.loads(json.dumps(group))

        _write_hooks(project / rel, extend)
    _rerender(project, tmp_path / "home")
    for rel in HOOK_FILES:
        groups = _hooks(project / rel)[FLUSH_EVENT[rel]]
        assert before[rel] in groups, (rel, groups)


def _allowed_tools(text: str) -> list[str]:
    fm = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    return [t.strip() for t in re.split(r",\s*(?=Bash\()", fm["allowed-tools"])]


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("rel", [".claude/skills/maker/SKILL.md", ".agents/skills/maker/SKILL.md"])
def test_ac_004_maker_grants_and_runs_nothing_of_autopilot(
    preset: str, rel: str, rendered: Callable[[str], Path]
) -> None:
    text = (rendered(preset) / rel).read_text("utf-8")
    hm = re.search(r"`hm` below means `([^`]+)`", text)
    assert hm, "no hm prefix line"
    want = [
        t.format(hm=hm.group(1))
        for t in ("Bash({hm} world_model:*)", "Bash(tail:*)", "Bash(grep:*)", "Bash(printf:*)")
    ]
    frontmatter = text.split("\n---\n", 1)[0]
    if "allowed-tools" in frontmatter or rel.startswith(".claude/"):
        assert _allowed_tools(text) == want
    assert "autopilot" not in text.lower()
