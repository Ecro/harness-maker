"""SPEC-world-model-name: the rendered `/<handle>` router skill, its always-loaded pointer, the
rename sweep and the slash-command onboarding surfaces (AC-001/002/004/005/007/009/010/011).

"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from harness_maker import models
from harness_maker.cli import app
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.spec_machine import load_golden_table
from harness_maker.synthesize import synthesize

_REPO = Path(__file__).resolve().parents[2]
_SPEC_YAML = _REPO / "specs/SPEC-world-model-name.machine.yaml"
_MAKE_MD = _REPO / "commands/make.md"
_POINTER_CAP = 200


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


def _bootstrap(root: Path, *args: str) -> Path:
    repo = root / "proj"
    repo.mkdir(parents=True)
    res = _cli(repo, *args)
    assert res.exit_code == 0, res.output
    return repo


def _read_yaml(repo: Path) -> dict[str, Any]:
    return load_harness_yaml(repo / ".claude" / "harness.yaml")


def _frontmatter(text: str) -> dict[str, Any]:
    """The skill's own frontmatter: the leading YAML document that carries `name`."""
    for doc in re.findall(r"^---\n(.*?)\n---\n", text, flags=re.S | re.M):
        data = yaml.safe_load(doc)
        if isinstance(data, dict) and "name" in data:
            return data
    raise AssertionError("no frontmatter with `name`")


def _pointer(text: str) -> str:
    rest = text[text.index("## World model") :]
    ends = [i for i in (rest.find("\n## ", 1), rest.find("\n<!--", 1)) if i != -1]
    return rest[: min(ends)].rstrip() if ends else rest.rstrip()


def _tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ---------------------------------------------------------------------------
# AC-002 — the router skill renders at the handle path with the display name
# ---------------------------------------------------------------------------

_AC002 = load_golden_table(_SPEC_YAML, "AC-002")


@pytest.mark.parametrize("row", _AC002, ids=[r.input["handle"] for r in _AC002])
def test_ac002_router_skill_rendered(row: Any, tmp_path: Path) -> None:
    inp = row.input
    repo = _bootstrap(
        tmp_path,
        "--targets",
        ",".join(inp["targets"]),
        "--world-model-name",
        inp["name"],
        "--world-model-handle",
        inp["handle"],
    )
    for rel in row.expected["expect_paths"]:
        fm = _frontmatter((repo / rel).read_text(encoding="utf-8"))
        assert fm["name"] == inp["handle"], rel
        assert inp["name"] in fm["description"], rel
    if "codex" not in inp["targets"]:
        assert not (repo / ".agents/skills" / inp["handle"]).exists()


@pytest.mark.parametrize(
    ("args", "name", "handle"),
    [((), "Maker", "maker"), (("--world-model-name", "Atlas"), "Atlas", "atlas")],
)
def test_s1_world_model_persisted_and_not_enabled_skill(
    args: tuple[str, ...], name: str, handle: str, tmp_path: Path
) -> None:
    """S1: the (default) choice is WRITTEN to harness.yaml, and the router skill renders
    outside `skills.enabled` (whose names must match a template dir)."""
    repo = _bootstrap(tmp_path, *args)
    data = _read_yaml(repo)
    assert data["world_model"] == {"name": name, "handle": handle}
    assert (repo / f".claude/skills/{handle}/SKILL.md").is_file()
    assert handle not in data["skills"]["enabled"]


# ---------------------------------------------------------------------------
# AC-004 — an absent world_model key renders identically to the explicit default
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("preset", [models.Preset.SIDE, models.Preset.PRODUCTION])
def test_ac004_absent_key_matches_explicit_default(preset: models.Preset, tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    a = interview(_profile(), autoloop_mode=True).model_copy(update={"preset": preset})
    render(
        synthesize(_profile(), a), seed / ".claude", dry_run=False, freeze_time=DEFAULT_FREEZE_TIME
    )
    data = load_harness_yaml(seed / ".claude" / "harness.yaml")

    trees = []
    for label, world in (("absent", None), ("explicit", {"name": "Maker", "handle": "maker"})):
        variant = {k: v for k, v in data.items() if k != "world_model"}
        if world is not None:
            variant["world_model"] = world
        src = tmp_path / f"{label}.yaml"
        src.write_text(yaml.safe_dump(variant, sort_keys=False), encoding="utf-8")
        answers = answers_from_harness_yaml(src)
        assert answers is not None
        out = tmp_path / label
        render(
            synthesize(_profile(), answers),
            out / ".claude",
            dry_run=False,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
        trees.append(_tree(out))
    assert trees[0] == trees[1]
    assert any(k.endswith("skills/maker/SKILL.md") for k in trees[0])


# ---------------------------------------------------------------------------
# AC-005 — renaming removes the pristine old router skill and keeps an edited one
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("edited_tree", [None, ".claude", ".agents"])
def test_ac005_rename_sweeps_pristine_keeps_edited(edited_tree: str | None, tmp_path: Path) -> None:
    repo = _bootstrap(tmp_path, "--targets", "claude-code,codex")
    old = {
        ".claude": repo / ".claude/skills/maker/SKILL.md",
        ".agents": repo / ".agents/skills/maker/SKILL.md",
    }
    assert all(p.is_file() for p in old.values())
    before = b""
    if edited_tree is not None:
        p = old[edited_tree]
        p.write_text(p.read_text(encoding="utf-8") + "\nuser note\n", encoding="utf-8")
        before = p.read_bytes()

    res = _cli(repo, "--update", "--world-model-name", "Atlas")
    assert res.exit_code == 0, res.output

    assert (repo / ".claude/skills/atlas/SKILL.md").is_file()
    assert (repo / ".agents/skills/atlas/SKILL.md").is_file()
    for tree, p in old.items():
        if tree == edited_tree:
            assert p.read_bytes() == before, f"{tree} edited router skill must be kept"
        else:
            assert not p.exists(), f"{tree} pristine router skill must be swept"
            assert not p.parent.exists(), f"{tree} emptied skill dir must be removed"


def test_user_owned_skill_dir_is_not_overwritten(tmp_path: Path) -> None:
    """A pre-existing, un-provenanced `.claude/skills/maker/SKILL.md` belongs to the user."""
    repo = tmp_path / "proj"
    own = repo / ".claude/skills/maker/SKILL.md"
    own.parent.mkdir(parents=True)
    own.write_text("---\nname: maker\ndescription: mine\n---\n\nmine\n", encoding="utf-8")
    before = own.read_bytes()
    res = _cli(repo)
    assert res.exit_code == 0, res.output
    assert own.read_bytes() == before
    # the rest of the harness still rendered around the kept file
    assert (repo / ".claude/skills/project-knowledge/SKILL.md").is_file()
    assert _read_yaml(repo)["world_model"]["handle"] == "maker"


# ---------------------------------------------------------------------------
# AC-007 — every always-loaded file names the world model and its handle within budget
# ---------------------------------------------------------------------------

_AC007 = load_golden_table(_SPEC_YAML, "AC-007")


@pytest.mark.parametrize("preset", ["Side", "Production"])
@pytest.mark.parametrize("locale", ["en", "ko"])
def test_ac007_pointer_in_every_always_loaded_variant(
    preset: str, locale: str, tmp_path: Path
) -> None:
    repo = _bootstrap(
        tmp_path, "--preset", preset, "--locale", locale, "--targets", "claude-code,cursor,codex"
    )
    for row in _AC007:
        section = _pointer((repo / row.input["file"]).read_text(encoding="utf-8"))
        for token in row.expected["expect"]:
            assert token in section, (row.input["file"], token)
        assert len(section) <= _POINTER_CAP, (row.input["file"], len(section))


def test_ac007_pointer_follows_rename(tmp_path: Path) -> None:
    repo = _bootstrap(
        tmp_path,
        "--targets",
        "claude-code,cursor,codex",
        "--world-model-name",
        "비비",
        "--world-model-handle",
        "bibi",
    )
    expect = {"CLAUDE.md": "/bibi", "AGENTS.md": "$bibi", ".cursor/rules/harness.mdc": "/bibi"}
    for rel, token in expect.items():
        section = _pointer((repo / rel).read_text(encoding="utf-8"))
        assert "비비" in section, rel
        assert token in section, rel
        assert "maker" not in section.lower(), rel
        assert len(section) <= _POINTER_CAP, (rel, len(section))
    assert (repo / ".claude/skills/bibi/SKILL.md").is_file()
    assert (repo / ".agents/skills/bibi/SKILL.md").is_file()


# ---------------------------------------------------------------------------
# AC-010 support — the router routes to surfaces that exist in the same render
# ---------------------------------------------------------------------------


def test_router_routes_resolve_to_rendered_surfaces(tmp_path: Path) -> None:
    repo = _bootstrap(tmp_path, "--targets", "claude-code,codex")
    claude = (repo / ".claude/skills/maker/SKILL.md").read_text(encoding="utf-8")
    codex = (repo / ".agents/skills/maker/SKILL.md").read_text(encoding="utf-8")

    commands = set(re.findall(r"/hm:([a-z-]+)", claude))
    assert {"research", "spec"} <= commands
    for c in commands:
        assert (repo / f".claude/commands/hm/{c}.md").is_file(), f"/hm:{c} not rendered"
    skills = set(re.findall(r"`([a-z]+(?:-[a-z]+)+)` skill", claude))
    assert {"project-knowledge", "intent-layer"} <= skills
    for s in skills:
        assert (repo / f".claude/skills/{s}/SKILL.md").is_file(), s

    assert "/hm:" not in codex, "Codex cannot run /hm: commands"
    codex_skills = set(re.findall(r"\$(hm-[a-z-]+)", codex))
    assert {"hm-research", "hm-spec"} <= codex_skills
    for s in codex_skills:
        assert (repo / f".agents/skills/{s}/SKILL.md").is_file(), f"${s} not rendered"
    # SPEC-world-model-followups S6: the briefing is the digest, not the composed commands
    assert "hm world_model digest" in claude


def test_router_description_requires_the_name(tmp_path: Path) -> None:
    repo = _bootstrap(tmp_path, "--world-model-name", "Atlas")
    text = (repo / ".claude/skills/atlas/SKILL.md").read_text(encoding="utf-8")
    desc = _frontmatter(text)["description"]
    assert "Atlas" in desc
    assert "/atlas" in desc
    assert re.search(r"\bnot\b.*\bmake\b", desc), "description must exclude bare make/build/fix"


# ---------------------------------------------------------------------------
# AC-001 / AC-009 slash halves — commands/make.md
# ---------------------------------------------------------------------------


def _make_md() -> str:
    return _MAKE_MD.read_text(encoding="utf-8")


def test_ac001_make_md_asks_name_right_after_locale() -> None:
    text = _make_md()
    headings = re.findall(r"^### (.+)$", text, flags=re.M)
    i = next(n for n, h in enumerate(headings) if "Choose live locale" in h)
    assert "world model" in headings[i + 1].lower()
    body = text[text.index(headings[i + 1]) : text.index(headings[i + 2])]
    assert "Maker" in body


def test_ac009_make_md_ci_parses_world_model_params() -> None:
    section0 = _make_md().split("### 1.", 1)[0]
    assert "world_model_name=" in section0
    assert "world_model_handle=" in section0


def test_ac009_every_dispatch_forwards_world_model_flags() -> None:
    blocks = re.findall(r"```bash\n(.*?)```", _make_md(), flags=re.S)
    # Selected by the CLI invocation itself, not by a co-occurring flag (REVIEW 3749a9d7).
    dispatch = [
        b for b in blocks if re.search(r'(harness_maker\.cli|harness-maker) make "\$\(pwd\)"', b)
    ]
    assert len(dispatch) >= 6, f"expected every make dispatch block, found {len(dispatch)}"
    for b in dispatch:
        assert "--world-model-name" in b, b[:200]
        assert "--world-model-handle" in b, b[:200]


# ---------------------------------------------------------------------------
# AC-011 — configure offers the world model name as a dimension
# ---------------------------------------------------------------------------


def render_configure_command(tmp_path: Path) -> str:
    repo = _bootstrap(tmp_path)
    return (repo / ".claude/commands/hm/configure.md").read_text(encoding="utf-8")


def test_ac_011_configure_dimension(tmp_path: Path) -> None:
    text = render_configure_command(tmp_path)
    assert "World model name" in text
    section = text[text.index("### 4. Dispatch") :]
    nxt = section.find("\n### ", 1)
    section = section if nxt == -1 else section[:nxt]
    assert "--world-model-name" in section
    assert "--world-model-handle" in section


def test_handle_taken_by_user_skill_is_named(tmp_path: Path) -> None:
    """confirm-1 P1: a user-owned skill at the handle path is kept, so the router is NOT
    installed there — the run must say so instead of leaving the front door silently missing."""
    repo = _bootstrap(tmp_path)
    own = repo / ".claude/skills/deploy/SKILL.md"
    own.parent.mkdir(parents=True)
    own.write_text("---\nname: deploy\ndescription: mine\n---\n\nmine\n", encoding="utf-8")
    before = own.read_bytes()
    res = _cli(repo, "--update", "--world-model-handle", "deploy")
    assert res.exit_code == 0, res.output
    assert own.read_bytes() == before
    assert ".claude/skills/deploy/SKILL.md" in res.output
    assert "NOT installed at /deploy" in res.output
    # a generated router at the handle path is ours, not a collision
    assert "NOT installed" not in _cli(repo, "--update", "--world-model-handle", "maker").output
