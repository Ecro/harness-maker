"""SPEC-world-model-followups: router briefing/resume, help listing, pointer budget at
maximum lengths, interactive locale messages, modular-add refusal and name round-trips
(AC-007, AC-008, AC-010..AC-015).

Five tests pass before the implementation, by design — they pin behaviour the router
rewrite must KEEP (SPEC S6 "keeps the 8-line reply cap, the Never-Read rule and the routing
rows"; S11 body name, carried REVIEW 84a7f33d):
- `test_ac008_router_resume_fields[cap|what_next|never_read|record_first]`
- `test_ac_014_router_body_name`
Each goes red the moment the rewrite drops the phrase or hard-codes the name. Positive
sibling that forces the rewrite to happen: `test_ac_007_router_single_digest` (RED).
"""

from __future__ import annotations

import io
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner

from harness_maker import i18n
from harness_maker import interview as interview_mod
from harness_maker.cli import app
from harness_maker.io_utils import load_harness_yaml
from harness_maker.spec_machine import load_golden_table
from harness_maker.world_model import name_error

_REPO = Path(__file__).resolve().parents[2]
_SPEC_YAML = _REPO / "specs/SPEC-world-model-followups.machine.yaml"
_DIGEST = "hm world_model digest"
_OLD_BRIEFING = (
    "hm intent status",
    "hm autopilot status",
    "git worktree list",
    "stage-spans.jsonl",
)


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


def render_router(tmp: Path, *, name: str = "Maker", codex: bool) -> str:
    repo = _bootstrap(tmp, "--targets", "claude-code,codex", "--world-model-name", name)
    handle = load_harness_yaml(repo / ".claude/harness.yaml")["world_model"]["handle"]
    rel = f".agents/skills/{handle}/SKILL.md" if codex else f".claude/skills/{handle}/SKILL.md"
    return (repo / rel).read_text(encoding="utf-8")


def briefing_commands(text: str) -> list[str]:
    """Every line that runs a briefing source, classified by how it runs."""
    found: list[str] = []
    for line in text.splitlines():
        if _DIGEST in line:
            stripped = line.strip()
            if stripped.startswith("!") or "!`" in stripped:
                found.append("!digest")
            # SPEC-maker-front-door-improvements AC-010 (PLAN ADR-007 amendment): the Codex run
            # block is `uv run … | tail -n 1 | grep '^{.*}$' || printf …`; `{ uv run` is the earlier
            # grouped form, kept so an older render still classifies.
            elif stripped.startswith(("uv run", "hm ", "{ uv run")):
                found.append("bash:digest")
            else:
                found.append("fallback:digest")
        elif any(old in line for old in _OLD_BRIEFING):
            found.append(f"old:{line.strip()[:40]}")
    return found


def _pointer(text: str) -> str:
    rest = text[text.index("## World model") :]
    ends = [i for i in (rest.find("\n## ", 1), rest.find("\n<!--", 1)) if i != -1]
    return rest[: min(ends)].rstrip() if ends else rest.rstrip()


# ---------------------------------------------------------------------------
# AC-007 — router briefs from a single digest with a fallback
# ---------------------------------------------------------------------------


def test_ac_007_router_single_digest(tmp_path: Path) -> None:
    claude = render_router(tmp_path / "c", codex=False)
    codex = render_router(tmp_path / "x", codex=True)
    assert briefing_commands(claude) == ["!digest", "fallback:digest"]
    assert briefing_commands(codex) == ["bash:digest"]


# ---------------------------------------------------------------------------
# AC-008 — router resume acts on the digest fields
# ---------------------------------------------------------------------------

_AC008 = load_golden_table(_SPEC_YAML, "AC-008")


@pytest.mark.parametrize("row", _AC008, ids=[r.input["field"] for r in _AC008])
def test_ac008_router_resume_fields(row: Any, tmp_path: Path) -> None:
    for codex in (False, True):
        text = render_router(tmp_path / str(codex), codex=codex)
        assert row.expected["phrase"] in text, (codex, row.expected["phrase"])


def test_router_states_the_worktree_scope(tmp_path: Path) -> None:
    """Carried P3 130d174a: tasks come from `hm/<slug>` worktrees only — say so."""
    text = render_router(tmp_path, codex=False)
    assert "worktree.enabled" in text


# ---------------------------------------------------------------------------
# AC-010 — interactive name and handle errors follow locale
# ---------------------------------------------------------------------------


def _prompts(monkeypatch: pytest.MonkeyPatch, answers: list[str], locale: str) -> str:
    """Everything the operator sees: the question prompts AND the re-prompt messages."""
    it = iter(answers)
    shown: list[str] = []

    def fake_input(prompt: str = "") -> str:
        shown.append(prompt)
        return next(it, "")

    monkeypatch.setattr(interview_mod, "_input_or_empty", fake_input)
    buf = io.StringIO()
    with redirect_stdout(buf):
        interview_mod._ask_world_model(locale)
    return "\n".join(shown) + "\n" + buf.getvalue()


def test_ac_010_interactive_messages_follow_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    def ko_prompts(a: list[str]) -> str:
        return _prompts(monkeypatch, a, "ko")

    def en_prompts(a: list[str]) -> str:
        return _prompts(monkeypatch, a, "en")

    assert ko_prompts(["", "x" * 41, "Atlas"]) != en_prompts(["", "x" * 41, "Atlas"]) and i18n.t(  # noqa: PT018
        "world_model_handle_collision", "ko", handle="intent-layer"
    ) in ko_prompts(["비비", "intent-layer", "bibi"])


def test_ac010_name_error_is_localized(monkeypatch: pytest.MonkeyPatch) -> None:
    ko = _prompts(monkeypatch, ["x" * 41, "Atlas"], "ko")
    assert i18n.t("world_model_name_length", "ko", limit=40) in ko


# ---------------------------------------------------------------------------
# AC-011 — modular add of the world-model skill is refused
# ---------------------------------------------------------------------------


class _Run:
    def __init__(self, res: Any, root: Path) -> None:
        self.exit_code = res.exit_code
        self.output = res.output
        self.root = root


def run_make_add(component: str, tmp: Path, flag: str = "--add") -> _Run:
    repo = _bootstrap(tmp)
    with _chdir(repo):
        res = CliRunner().invoke(app, ["make", str(repo), flag, component])
    return _Run(res, repo)


def test_ac_011_modular_add_refused(tmp_path: Path) -> None:
    r = run_make_add("skill:world-model", tmp_path)
    assert (  # noqa: PT018
        r.exit_code != 0
        and "/hm:configure" in r.output
        and not (r.root / ".claude/skills/world-model").exists()
    )
    assert (
        "world-model" not in load_harness_yaml(r.root / ".claude/harness.yaml")["skills"]["enabled"]
    )


@pytest.mark.parametrize("component", ["skill:world-model", "skill:maker"])
def test_ac011_modular_remove_of_router_refused(component: str, tmp_path: Path) -> None:
    r = run_make_add(component, tmp_path, flag="--remove")
    assert r.exit_code != 0, r.output
    assert "/hm:configure" in r.output
    assert (r.root / ".claude/skills/maker/SKILL.md").is_file()


# ---------------------------------------------------------------------------
# AC-012 — accepted names round-trip and noncharacters are rejected (property)
# ---------------------------------------------------------------------------

_NAMES = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs", "Zl", "Zp")), min_size=1, max_size=40
).filter(lambda s: s.strip() == s and name_error(s) is None)


@settings(
    max_examples=8,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(name=st.one_of(_NAMES, st.sampled_from(["Maker 🚀", "비비✨", "𝔐aker"])))
def test_ac012_names_round_trip(name: str, tmp_path_factory: pytest.TempPathFactory) -> None:
    tmp = tmp_path_factory.mktemp("rt")
    repo = _bootstrap(tmp, "--world-model-name", name, "--world-model-handle", "atlas")
    assert load_harness_yaml(repo / ".claude/harness.yaml")["world_model"]["name"] == name
    text = (repo / ".claude/skills/atlas/SKILL.md").read_text(encoding="utf-8")
    fm = next(
        d
        for d in (
            yaml.safe_load(b) for b in re.findall(r"^---\n(.*?)\n---\n", text, flags=re.S | re.M)
        )
        if isinstance(d, dict) and "name" in d
    )
    assert name in fm["description"]


@pytest.mark.parametrize("bad", ["a￾", "￿b"])
def test_ac012_noncharacters_rejected(bad: str) -> None:
    assert name_error(bad) is not None


# ---------------------------------------------------------------------------
# AC-013 — pointer within its cap, full tokens (200 → 400: SPEC-maker-front-door-improvements)
# ---------------------------------------------------------------------------

_AC013 = load_golden_table(_SPEC_YAML, "AC-013")
_POINTER_CAP_SUPERSEDED = 400


@pytest.mark.parametrize("row", _AC013, ids=[r.input["locale"] for r in _AC013])
def test_ac013_pointer_cap_full_tokens(row: Any, tmp_path: Path) -> None:
    name, handle = row.input["name"], row.input["handle"]
    repo = _bootstrap(
        tmp_path,
        "--locale",
        row.input["locale"],
        "--targets",
        "claude-code,cursor,codex",
        "--world-model-name",
        name,
        "--world-model-handle",
        handle,
    )
    for rel, token in (
        ("CLAUDE.md", f"/{handle}"),
        ("AGENTS.md", f"${handle}"),
        (".cursor/rules/harness.mdc", f"/{handle}"),
    ):
        section = _pointer((repo / rel).read_text(encoding="utf-8"))
        # The golden row's 200 is the approved SPEC-world-model-followups AC-013 value; the
        # SPEC-maker-front-door-improvements Constraints supersede it with 400 (the pointer now
        # carries routing, decision capture and the aside protocol). The SPEC is left untouched.
        assert row.expected["max_chars"] == 200
        assert len(section) <= _POINTER_CAP_SUPERSEDED, (rel, len(section))
        assert name in section and token in section, rel  # noqa: PT018


# ---------------------------------------------------------------------------
# AC-014 — router body carries the display name and the Codex token
# ---------------------------------------------------------------------------


def test_ac_014_router_body_name(tmp_path: Path) -> None:
    claude = render_router(tmp_path / "c", name="Atlas", codex=False)
    codex = render_router(tmp_path / "x", name="Atlas", codex=True)
    assert "# Atlas" in claude and "Atlas —" in claude and "$atlas" in codex  # noqa: PT018
    assert "Maker" not in claude.split("---", 2)[-1]
    assert "/atlas" not in codex


# ---------------------------------------------------------------------------
# AC-015 — help lists the router under its handle
# ---------------------------------------------------------------------------

_AC015 = load_golden_table(_SPEC_YAML, "AC-015")


@pytest.mark.parametrize("locale", ["en", "ko"])
def test_ac015_help_lists_router(locale: str, tmp_path: Path) -> None:
    repo = _bootstrap(
        tmp_path,
        "--locale",
        locale,
        "--targets",
        "claude-code,codex",
        "--world-model-name",
        "Atlas",
    )
    files = {"claude": ".claude/commands/hm/help.md", "codex": ".agents/skills/hm-help/SKILL.md"}
    for row in _AC015:
        text = (repo / files[row.input["runtime"]]).read_text(encoding="utf-8")
        assert row.expected["token"] in text, (locale, row.input)
