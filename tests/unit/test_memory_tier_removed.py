"""SPEC-sdlc-three-loops-gap AC-001..005 — dead memory tier gone, fact/question boundary rendered.

AC-002 and AC-003 are preservation guards: they pass before the change by construction and go
red only if the removal also strips the live lock or the legacy churn entries. Their RED sibling
is ``test_dead_tier_not_importable``, which forces the deletion that could take them along.
"""

from __future__ import annotations

import ast
import re
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import cache
from importlib.util import find_spec
from pathlib import Path

import pytest
import yaml

from harness_maker import memory_md
from harness_maker.memory import _locking
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from harness_maker.worktree import _HARNESS_CHURN_DIRS

REPO = Path(__file__).parents[2]
SELF_TEST = Path(__file__).resolve()
REMOVED_MODULES = ("episodic", "semantic", "profile", "retrieval")
REMOVED_NAMES = frozenset({"EpisodicStore", "SemanticStore", "ProfileStore", "MemoryRetriever"})
BOUNDARY_RULE = (
    "A claim that bears on an intent's metric or decision is an intent question "
    "(`hm intent question`, open → confirmed or wrong); any other domain fact is a "
    "`[wiki:fact]`. Record each claim in one place only and link to it from the other."
)
SKILL_PATHS = {
    Target.CLAUDE_CODE: ".claude/skills/{}/SKILL.md",
    Target.CODEX: ".agents/skills/{}/SKILL.md",
}
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def ast_uses(names: frozenset[str], *, exclude: Path) -> list[str]:
    """Import or identifier uses of the removed tier; prose and string literals do not count."""
    hits: list[str] = []
    for root in (REPO / "src", REPO / "tests"):
        for path in root.rglob("*.py"):
            if path.resolve() == exclude:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                where = f"{path.relative_to(REPO)}:{getattr(node, 'lineno', 0)}"
                if isinstance(node, ast.ImportFrom) and node.module:
                    from_removed = any(
                        node.module == f"harness_maker.memory.{m}" for m in REMOVED_MODULES
                    )
                    names_removed = node.module == "harness_maker.memory" and any(
                        a.name in names or a.name in REMOVED_MODULES for a in node.names
                    )
                    if from_removed or names_removed:
                        hits.append(where)
                elif isinstance(node, ast.Import):
                    if any(
                        a.name == f"harness_maker.memory.{m}"
                        for a in node.names
                        for m in REMOVED_MODULES
                    ):
                        hits.append(where)
                elif (isinstance(node, ast.Name) and node.id in names) or (
                    isinstance(node, ast.Attribute) and node.attr in names
                ):
                    hits.append(where)
    return hits


# ── AC-001 ───────────────────────────────────────────────────────────────────


def test_dead_tier_not_importable() -> None:
    assert all(find_spec(f"harness_maker.memory.{m}") is None for m in REMOVED_MODULES), [
        m for m in REMOVED_MODULES if find_spec(f"harness_maker.memory.{m}") is not None
    ]


def test_no_imports_remain() -> None:
    uses = ast_uses(REMOVED_NAMES, exclude=SELF_TEST)
    assert not uses, uses


# ── AC-002 ───────────────────────────────────────────────────────────────────


def test_memory_md_writes_take_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: Counter[str] = Counter()
    current = {"path": ""}
    real_lock = _locking.exclusive_lock

    @contextmanager
    def counting_lock(lock_path: Path) -> Iterator[None]:
        calls[current["path"]] += 1
        with real_lock(lock_path):
            yield

    monkeypatch.setattr(memory_md, "exclusive_lock", counting_lock)
    writes: dict[str, Callable[[], object]] = {
        "upsert_wiki": lambda: memory_md.upsert_wiki(tmp_path, "s", "fact", "body"),
        "append_failure": lambda: memory_md.upsert_failure(tmp_path, "s", "code", "body"),
        "append_session": lambda: memory_md.append_session(tmp_path, "body"),
    }
    for name, write in writes.items():
        current["path"] = name
        write()
    lock_calls = dict(calls)
    assert all(
        lock_calls.get(path, 0) >= 1 for path in ("upsert_wiki", "append_failure", "append_session")
    ), lock_calls


# ── AC-003 ───────────────────────────────────────────────────────────────────


def test_churn_dirs_retained() -> None:
    assert {
        ".claude/memory/semantic/",
        ".claude/memory/episodic/",
        ".claude/memory/profile/",
    } <= set(_HARNESS_CHURN_DIRS)


# ── AC-004 / AC-005 ──────────────────────────────────────────────────────────


@cache
def _render(target: Target) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(), InterviewAnswers(preset=Preset.PRODUCTION, targets=[target])
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        return {
            str(p.relative_to(root)): p.read_text(encoding="utf-8") for p in root.rglob("SKILL.md")
        }


def _skill(target: Target, name: str) -> str:
    return _render(target)[SKILL_PATHS[target].format(name)]


def _description(skill: str) -> str:
    match = _FRONTMATTER.search(skill)
    assert match, "no frontmatter"
    meta = yaml.safe_load(match.group(1))
    return str(meta["description"])


def _procedure(skill: str) -> str:
    start = skill.index("## Procedure")
    end = skill.find("\n## ", start + 1)
    return skill[start:] if end == -1 else skill[start:end]


@pytest.mark.parametrize("target", list(SKILL_PATHS), ids=["claude", "codex"])
def test_boundary_rule_in_both_skills(target: Target) -> None:
    project_knowledge_md = _skill(target, "project-knowledge")
    intent_layer_md = _skill(target, "intent-layer")
    # AC-004 predicate, one conjunct per assert so a failure names the missing piece.
    assert BOUNDARY_RULE in project_knowledge_md
    assert BOUNDARY_RULE in intent_layer_md
    assert "intent-layer" in project_knowledge_md
    assert "project-knowledge" in intent_layer_md


@pytest.mark.parametrize("target", list(SKILL_PATHS), ids=["claude", "codex"])
def test_project_knowledge_routes_intent_claims(target: Target) -> None:
    project_knowledge_md = _skill(target, "project-knowledge")
    pk_description = _description(project_knowledge_md)
    pk_procedure = _procedure(project_knowledge_md)
    # AC-005 predicate, one conjunct per assert.
    assert "intent-layer" in pk_description
    assert "intent-layer" in pk_procedure
    assert "--locator .claude/memory/wiki.md" in project_knowledge_md
    assert "name that question's id in the body" in pk_procedure
    # The hand-off must precede the wiki write, or the unconditional upsert still runs first.
    assert pk_procedure.index("intent-layer") < pk_procedure.index("upsert-wiki")


# ── REVIEW sdlc-three-loops-gap: wrapup 5.7 inline values stay inert ─────────

_INTENT_WRITE_CALLS = ("hm intent question add", "hm intent question observe", "hm intent close")


@cache
def _wrapup(target: Target) -> str:
    blueprint = synthesize(
        ProjectProfile(), InterviewAnswers(preset=Preset.PRODUCTION, targets=[target])
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        if target is Target.CODEX:
            return (root / ".agents/skills/hm-wrapup/SKILL.md").read_text(encoding="utf-8")
        return (root / ".claude/commands/hm/wrapup.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("target", list(SKILL_PATHS), ids=["claude", "codex"])
def test_wrapup_intent_writes_single_quote_inline_values(target: Target) -> None:
    # Superseded by SPEC-intent-file-inputs: text reaches these calls through `-file` paths, so
    # no quoting of any kind is left on the line. Kept as a guard that the inline forms stay out.
    lines = [ln for ln in _wrapup(target).splitlines() if any(c in ln for c in _INTENT_WRITE_CALLS)]
    assert lines, "no intent write call rendered in wrapup"
    for flag in ("--claim", "--text", "--note"):
        assert not [ln for ln in lines if f"{flag} '" in ln or f'{flag} "' in ln], flag
    assert any("--claim-file" in ln for ln in lines)
    assert any("--text-file" in ln for ln in lines)
    assert any("--note-file" in ln for ln in lines)
