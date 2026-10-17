"""SPEC-hm-overhaul-p1 AC-004: the rendered surface per target holds the kept set within budget.

Every arm is a real `harness-maker make` in a fresh git repo, so `.claude/intent.yaml` and the
other make-time files are in the tree. Config axes the CLI has no flag for (the lens fan-out,
delegation) are set by editing harness.yaml and re-rendering with `--update`. Budgets are measured
with the install ref replaced by `$HOME/harness-maker`, the same pin the structural ratchets use,
so a number does not depend on where the suite runs.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests._overhaul_p1_ref import HEAD_SRC, REF_SHA, REPO_ROOT, init_project, ref_root, run_make

PIN = "$HOME/harness-maker"
LENSES = (
    "security-reviewer",
    "concurrency-reviewer",
    "test-reviewer",
    "performance-reviewer",
    "ux-reviewer",
)
KEPT_SKILLS = (
    "agent-quality-rubric",
    "ai-readiness-rubric",
    "context-linter",
    "intent-layer",
    "maker",
    "project-knowledge",
    "worktree-isolator",
)
BASE_AGENTS = ("code-reviewer", "judgment-reviewer", "spec-validator")
COMMANDS = (
    "execute",
    "health",
    "help",
    "make",
    "metrics",
    "research",
    "spec",
    "uninstall",
    "wrapup",
)
STAGES = ("research", "spec", "execute", "wrapup")
REMOVED_COMMAND = re.compile(r"(?:/hm:|\$hm-)(?:review|verify|configure|loop)\b")
_INSTALL_REF = re.compile(r"uv run --with (\S+) hm ")


@dataclass(frozen=True)
class Arm:
    preset: str
    targets: str
    worktree: bool
    extra: tuple[str, ...] = ()
    #: harness.yaml edits applied before a `make --update` (dotted key -> value).
    edits: dict[str, Any] = field(default_factory=dict)


ARMS: dict[str, Arm] = {
    "side": Arm("Side", "claude-code", False),
    "prod": Arm("Production", "claude-code", False),
    "side-block": Arm("Side", "claude-code", False, ("--strictness", "block")),
    "side-codex-wt": Arm("Side", "claude-code,codex", True),
    "prod-codex": Arm("Production", "claude-code,codex", False),
    "prod-codex-wt": Arm("Production", "claude-code,codex", True),
    "side-deep": Arm("Side", "claude-code", False, ("--comprehension-depth", "deep")),
    "side-deep-wt": Arm("Side", "claude-code", True, ("--comprehension-depth", "deep")),
    "lenses-installed": Arm(
        "Side",
        "claude-code,codex",
        False,
        edits={"reviewers.installed": ["code-reviewer", *LENSES]},
    ),
    "fanout": Arm(
        "Side",
        "claude-code,codex",
        False,
        edits={
            "reviewers.fanout": True,
            "reviewers.installed": ["code-reviewer", "security-reviewer", "ux-reviewer"],
        },
    ),
    "opt-ins": Arm(
        "Side",
        "claude-code,codex",
        True,
        ("--second-opinion-models", "codex"),
        edits={"delegation.stages": ["wrapup"]},
    ),
}


def _set(data: dict[str, Any], dotted: str, value: object) -> None:
    *head, last = dotted.split(".")
    node = data
    for part in head:
        node = node.setdefault(part, {})
    node[last] = value


def _edit_yaml(path: Path, edits: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    data = yaml.safe_load(body)
    for key, value in edits.items():
        _set(data, key, value)
    path.write_text(f"---\n{front}---\n{yaml.safe_dump(data, sort_keys=False)}", encoding="utf-8")


def _make(base: Path, name: str, arm: Arm, src: Path) -> Path:
    project = init_project(base / name / "project")
    home = base / name / "home"
    args = [
        "--autoloop",
        "--preset",
        arm.preset,
        "--targets",
        arm.targets,
        "--worktree" if arm.worktree else "--no-worktree",
        *arm.extra,
    ]
    r = run_make(project, args, src=src, home=home)
    assert r.returncode == 0, (name, r.stdout[-2000:], r.stderr[-2000:])
    if arm.edits:
        _edit_yaml(project / ".claude" / "harness.yaml", arm.edits)
        r = run_make(project, ["--update"], src=src, home=home)
        assert r.returncode == 0, (name, "--update", r.stdout[-2000:], r.stderr[-2000:])
    return project


@pytest.fixture(scope="module")
def trees(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    base = tmp_path_factory.mktemp("ac004")
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {n: pool.submit(_make, base, n, a, HEAD_SRC) for n, a in ARMS.items()}
        return {n: f.result() for n, f in futures.items()}


@pytest.fixture(scope="module")
def ref_trees(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """db19f023 renders, for the rows whose budget is "<= the db19f023 size"."""
    base = tmp_path_factory.mktemp("ac004-ref")
    src = ref_root(base / "cache") / "src"
    arms = {
        f"{p}-{wt}": Arm(p, "claude-code,codex", wt)
        for p in ("Side", "Production")
        for wt in (False, True)
    }
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {n: pool.submit(_make, base, n, a, src) for n, a in arms.items()}
        return {n: f.result() for n, f in futures.items()}


def _size(project: Path, rel: str) -> int:
    text = (project / rel).read_text(encoding="utf-8")
    execute = (project / ".claude/commands/hm/execute.md").read_text(encoding="utf-8")
    m = _INSTALL_REF.search(execute)
    assert m, "execute.md lost its CLI prefix"
    return len(text.replace(m.group(1), PIN))


def _names(directory: Path, suffix: str) -> set[str]:
    return (
        {p.name.removesuffix(suffix) for p in directory.glob(f"*{suffix}")}
        if directory.is_dir()
        else set()
    )


def _dirs(directory: Path) -> set[str]:
    return {p.name for p in directory.iterdir() if p.is_dir()} if directory.is_dir() else set()


def _expected_agents(arm: Arm) -> set[str]:
    names = set(BASE_AGENTS)
    if arm.edits.get("reviewers.fanout"):
        names |= {n for n in arm.edits["reviewers.installed"] if n in LENSES}
    if "--second-opinion-models" in arm.extra:
        names |= {"code-verifier", "consensus-arbiter"}
    if arm.edits.get("delegation.stages"):
        names.add("stage-delegate")
    return names


def _expected_skills(arm: Arm) -> set[str]:
    return set(KEPT_SKILLS) | (
        {"second-opinion-gate"} if "--second-opinion-models" in arm.extra else set()
    )


# ── file set ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", list(ARMS))
def test_ac004_file_set_per_target(trees: dict[str, Path], name: str) -> None:
    arm, root = ARMS[name], trees[name]
    claude = root / ".claude"
    assert _names(claude / "commands" / "hm", ".md") == set(COMMANDS)
    assert _names(claude / "agents", ".md") == _expected_agents(arm)
    assert _dirs(claude / "skills") == _expected_skills(arm)
    for rel in ("settings.json", "harness.yaml", "intent.yaml", "observability/dashboard.md"):
        assert (claude / rel).is_file(), rel
    assert any((claude / "memory").iterdir())
    assert any((claude / "rubrics").iterdir())
    assert (root / "CLAUDE.md").is_file()
    for absent in (claude / "stages", claude / "hm", root / ".cursor"):
        assert not absent.exists(), absent
    if "codex" in arm.targets:
        stage_skills = {f"hm-{s}" for s in (*STAGES, "help")}
        assert _dirs(root / ".agents" / "skills") == stage_skills | _expected_skills(arm)
        agents = _expected_agents(arm)
        assert _names(root / ".codex" / "agents", ".toml") == agents
        config = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
        assert set(re.findall(r"^\[agents\.([\w-]+)\]", config, re.M)) == agents
        assert (root / ".codex" / "hooks.json").is_file()
        assert (root / "AGENTS.md").is_file()
    else:
        assert not (root / ".agents").exists()
        assert not (root / ".codex").exists()


def test_ac004_file_set_negative_control(trees: dict[str, Path], tmp_path: Path) -> None:
    """A stray retired file is caught: the comparison is set equality, not a subset check."""
    import shutil

    copy = tmp_path / "copy"
    shutil.copytree(trees["side"] / ".claude", copy)
    (copy / "commands" / "hm" / "review.md").write_text("x", encoding="utf-8")
    assert _names(copy / "commands" / "hm", ".md") != set(COMMANDS)


# ── budgets ─────────────────────────────────────────────────────────────────

#: (stage, base, + worktree on, + depth deep) from the AC-004 table.
_STAGE_BUDGET = {"spec": (6500, 1500, 800), "execute": (7000, 1500, 0), "wrapup": (3800, 2800, 0)}
_OPT_IN = 1500


def _stage_budget(arm: Arm, stage: str) -> int:
    if stage == "research":
        return 8000
    base, wt, deep = _STAGE_BUDGET[stage]
    extra = 0
    if arm.edits.get("reviewers.fanout") and stage == "execute":
        extra += _OPT_IN
    if "--second-opinion-models" in arm.extra and stage == "execute":
        extra += _OPT_IN
    if arm.edits.get("delegation.stages") and stage == "wrapup":
        extra += _OPT_IN
    return base + (wt if arm.worktree else 0) + (deep if "deep" in arm.extra else 0) + extra


@pytest.mark.parametrize("name", list(ARMS))
def test_ac004_char_budgets(trees: dict[str, Path], ref_trees: dict[str, Path], name: str) -> None:
    arm, root = ARMS[name], trees[name]
    over: list[str] = []

    def check(rel: str, budget: int) -> None:
        size = _size(root, rel)
        if size > budget:
            over.append(f"{rel}: {size} > {budget}")

    for stage in STAGES:
        budget = _stage_budget(arm, stage)
        check(f".claude/commands/hm/{stage}.md", budget)
        if "codex" in arm.targets:
            check(f".agents/skills/hm-{stage}/SKILL.md", int(budget * 1.03))
    check(".claude/commands/hm/metrics.md", 3000)
    check(".claude/agents/code-reviewer.md", 3000)
    # "<= the db19f023 size" rows compare like with like: same preset and worktree, no opt-in
    # (a second-opinion block in health.md is outside the base, as it is for the stages).
    if "--second-opinion-models" not in arm.extra:
        ref = ref_trees[f"{arm.preset}-{arm.worktree}"]
        for rel in (
            *(f".claude/commands/hm/{c}.md" for c in ("make", "help", "health", "uninstall")),
            ".claude/agents/spec-validator.md",
            ".claude/agents/judgment-reviewer.md",
            *(
                f".claude/agents/{n}.md"
                for n in LENSES
                if (root / f".claude/agents/{n}.md").is_file()
            ),
        ):
            check(rel, _size(ref, rel))
        if "codex" in arm.targets:
            check(
                ".agents/skills/hm-help/SKILL.md",
                int(_size(ref, ".agents/skills/hm-help/SKILL.md") * 1.03),
            )
    assert not over, over


def test_ac004_budget_negative_control(trees: dict[str, Path], tmp_path: Path) -> None:
    """The measurement sees growth: one more line pushes a file over a budget it met."""
    root = trees["side"]
    size = _size(root, ".claude/commands/hm/wrapup.md")
    assert size <= 3800
    padded = tmp_path / "p"
    (padded / ".claude/commands/hm").mkdir(parents=True)
    for stage in ("execute", "wrapup"):
        text = (root / f".claude/commands/hm/{stage}.md").read_text(encoding="utf-8")
        if stage == "wrapup":
            text += "x" * (3801 - size)
        (padded / f".claude/commands/hm/{stage}.md").write_text(text, encoding="utf-8")
    assert _size(padded, ".claude/commands/hm/wrapup.md") > 3800


# ── hooks ───────────────────────────────────────────────────────────────────

_HM = re.compile(r"python -m harness_maker\.(.+)$")


def _hook_rows(path: Path) -> set[tuple[str, str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: set[tuple[str, str, str]] = set()
    for event, groups in data["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                m = _HM.search(hook["command"])
                assert m, hook["command"]
                rows.add((event, group.get("matcher", ""), m.group(1)))
    return rows


def _strict_block(root: Path) -> bool:
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.strictness import resolve_strictness

    return resolve_strictness(load_harness_yaml(root / ".claude" / "harness.yaml")) == "block"


@pytest.mark.parametrize("name", ["side", "prod", "side-block", "side-codex-wt", "prod-codex"])
def test_ac004_hook_commands_per_file(trees: dict[str, Path], name: str) -> None:
    root = trees[name]
    block = _strict_block(root)
    assert block == (name in ("prod", "side-block", "prod-codex")), "strictness arm mislabelled"
    edit = "Write|Edit|MultiEdit"
    claude = {
        ("PreToolUse", "Bash", "gates.permission_gate --subordinate-to-deny-dangerous"),
        ("PreToolUse", edit, "gates.worktree_gate"),
        ("PreCompact", "auto", "hooks.flush_session"),
        ("PreCompact", "auto", "worktree span-end"),
        ("PreCompact", "manual", "hooks.flush_session"),
        ("PreCompact", "manual", "worktree span-end"),
        ("Stop", "", "hooks.loop_gate --mode stop-hook"),
        ("Stop", "", "worktree span-end"),
        ("SessionStart", "", "hooks.sessionid_envfile"),
    } | ({("PreToolUse", edit, "gates.spec_gate")} if block else set())
    assert _hook_rows(root / ".claude" / "settings.json") == claude
    if (root / ".codex").is_dir():
        codex = {
            ("PermissionRequest", "", "gates.permission_gate"),
            ("PreToolUse", "Bash", "gates.permission_gate"),
            ("SessionStart", "", "hooks.sessionstart_drift"),
            ("SessionStart", "", "hooks.sessionid_envfile"),
            ("Stop", "", "hooks.loop_gate --mode stop-hook"),
            ("Stop", "", "hooks.flush_session"),
        } | ({("PreToolUse", "apply_patch", "gates.spec_gate")} if block else set())
        assert _hook_rows(root / ".codex" / "hooks.json") == codex


def test_ac004_plugin_hooks_unchanged() -> None:
    ref = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{REF_SHA}:hooks/hooks.json"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout
    assert (REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8") == ref


# ── stage content ───────────────────────────────────────────────────────────


def _text(root: Path, stage: str) -> str:
    return (root / ".claude" / "commands" / "hm" / f"{stage}.md").read_text(encoding="utf-8")


#: (arms, stage, predicate over the stage text, what the row asserts)
_ROWS: list[tuple[tuple[str, ...], str, Callable[[str], bool], str]] = [
    (
        ("side-codex-wt", "prod-codex-wt", "side-deep-wt"),
        "*",
        lambda t: "hm worktree task-preflight" in t,
        "task-preflight (worktree on)",
    ),
    (
        ("side", "prod"),
        "*",
        lambda t: "task-preflight" not in t,
        "no task-preflight (worktree off)",
    ),
    (
        tuple(ARMS),
        "*",
        lambda t: bool(re.search(r"uv run --with \S+ hm ", t)),
        "the `uv run --with <path> hm` prefix",
    ),
    (tuple(ARMS), "*", lambda t: "@hm:user:extensions" in t, "the user extensions block"),
    (
        tuple(ARMS),
        "*",
        lambda t: ".claude/hm/" not in t and ".claude/stages/" not in t,
        "self-contained",
    ),
    (
        tuple(ARMS),
        "spec",
        lambda t: all(
            c in t
            for c in (
                "**Intent**",
                "**Outcomes**",
                "**In-scope scenarios**",
                "**Non-goals**",
                "**Constraints**",
                "**Verification**",
            )
        ),
        "the six categories",
    ),
    (
        tuple(ARMS),
        "spec",
        lambda t: t.count("Approve this SPEC and end interview") >= 2,
        "the approval option and its stop rule",
    ),
    (
        tuple(ARMS),
        "spec",
        lambda t: "interview.main_loop.max_rounds" in t,
        "the round cap as the stop rule",
    ),
    (
        tuple(ARMS),
        "spec",
        lambda t: "oracle_source" in t and "irreversible_decisions" in t,
        "oracle and IRR",
    ),
    (
        tuple(ARMS),
        "spec",
        lambda t: "@hm:comprehension:brief" in t and "@hm:comprehension:round_state" in t,
        "brief and round state",
    ),
    (
        ("side-deep", "side-deep-wt"),
        "spec",
        lambda t: "Per-question envelope" in t and "Closing readback" in t,
        "deep blocks",
    ),
    (
        ("side", "prod"),
        "spec",
        lambda t: "Per-question envelope" not in t,
        "no deep block at standard",
    ),
    (
        tuple(ARMS),
        "spec",
        lambda t: "spec_machine check --all" in t and "spec_machine approve" in t,
        "check and approve",
    ),
    (
        tuple(ARMS),
        "spec",
        lambda t: 'subagent_type="spec-validator"' in t,
        "the spec-validator dispatch",
    ),
    (tuple(ARMS), "spec", lambda t: re.search(r"\blane", t.lower()) is None, "no lanes"),
    (
        tuple(ARMS),
        "spec",
        lambda t: (
            re.search(
                r"--exempt` only when `irreversible_decisions: \[\]`, Step 4 passed, "
                r"`status: approved`, and the DRI was not asked",
                t,
            )
            is not None
        ),
        "the exempt rule",
    ),
    (
        tuple(ARMS),
        "spec",
        lambda t: "Only a non-code change may write `ac: []`" in t,
        "the skip path's ac rule",
    ),
    (
        tuple(ARMS),
        "execute",
        lambda t: "checkpoint:compaction" in t and ".claude-progress.json" in t,
        "the hot tier",
    ),
    (
        tuple(ARMS),
        "execute",
        lambda t: t.index("hm check --red") < t.index("hm check --slug"),
        "--red then the gate",
    ),
    (tuple(ARMS), "execute", lambda t: "spec_machine mark-tested" in t, "mark-tested"),
    (
        tuple(ARMS),
        "execute",
        lambda t: 'subagent_type="code-reviewer"' in t and "reviewers.max_review_rounds" in t,
        "one reviewer, capped",
    ),
    (
        tuple(a for a in ARMS if a != "fanout"),
        "execute",
        lambda t: not any(n in t for n in LENSES),
        "no lens without fan-out",
    ),
    (
        ("fanout",),
        "execute",
        lambda t: (
            "`security-reviewer`, `ux-reviewer`" in t
            and not any(
                n in t for n in ("concurrency-reviewer", "test-reviewer", "performance-reviewer")
            )
            and "union, not a vote" in t
        ),
        "the two named lenses, merged",
    ),
    (
        tuple(ARMS),
        "execute",
        lambda t: (
            [ln for ln in t.splitlines() if "--no-tdd" in ln]
            == [ln for ln in t.splitlines() if "--no-tdd is retired" in ln]
        ),
        "--no-tdd only in its notice",
    ),
    (tuple(ARMS), "execute", lambda t: "spec_mutation" not in t, "no mutation"),
    (tuple(ARMS), "*", lambda t: "second_brain" not in t, "Second Brain off by default"),
    (
        tuple(ARMS),
        "wrapup",
        lambda t: (
            "hm check" in t and "memory_md upsert-wiki" in t and "memory_md upsert-failure" in t
        ),
        "gate and memory",
    ),
    (
        tuple(ARMS),
        "wrapup",
        lambda t: "find-unjudged" in t and "mark-judged" in t and "wrapup_land" in t,
        "judgment and land",
    ),
    (
        ("side-codex-wt", "prod-codex-wt"),
        "wrapup",
        lambda t: "task-land" in t and "commit-base-memory" in t,
        "squash-land (worktree on)",
    ),
    (("opt-ins",), "wrapup", lambda t: "stage-delegate" in t, "delegation block"),
    (("opt-ins",), "execute", lambda t: "hm second_opinion_invoke" in t, "second-opinion block"),
    (tuple(ARMS), "research", lambda t: "optional" in t, "research is optional"),
    # The install path is the checkout's, not template text; a worktree named for a task can
    # contain the word.
    (tuple(ARMS), "*", lambda t: "autopilot" not in _INSTALL_REF.sub("", t), "no auto-advance"),
]


def _row_id(row: tuple[tuple[str, ...], str, object, str]) -> str:
    return f"{row[1]}:{row[3]}"


@pytest.mark.parametrize("row", _ROWS, ids=[_row_id(r) for r in _ROWS])
def test_ac004_stage_content_substrings(
    trees: dict[str, Path], row: tuple[tuple[str, ...], str, Callable[[str], bool], str]
) -> None:
    arms, stage, predicate, _what = row
    failed = [
        (a, s)
        for a in arms
        for s in (STAGES if stage == "*" else (stage,))
        if not predicate(_text(trees[a], s))
    ]
    assert not failed, failed


def test_ac004_second_brain_promote_only_when_enabled(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    on = Arm(
        "Side",
        "claude-code",
        False,
        ("--second-brain-vault-path", str(vault), "--second-brain-project-id", "demo"),
    )
    root = _make(tmp_path, "sb", on, HEAD_SRC)
    assert "second_brain promote" in _text(root, "wrapup")
    assert "second_brain search" in _text(root, "execute")
    assert "second_brain search" in _text(root, "research")


# ── no removed command ──────────────────────────────────────────────────────


def _removed_command_lines(root: Path) -> list[str]:
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or rel.parts[0] in (".git",) or rel.parts[0].startswith(".backup-"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        out += [
            f"{rel}: {ln.strip()[:140]}"
            for ln in text.splitlines()
            if REMOVED_COMMAND.search(ln) and "retired" not in ln.lower()
        ]
    return out


@pytest.mark.parametrize("name", list(ARMS))
def test_ac004_no_removed_command_named(trees: dict[str, Path], name: str) -> None:
    assert _removed_command_lines(trees[name]) == []


def test_ac004_removed_command_scan_negative_control(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "run /hm:review next\n$hm-loop\n/hm:loop is retired\n", encoding="utf-8"
    )
    assert len(_removed_command_lines(tmp_path)) == 2
