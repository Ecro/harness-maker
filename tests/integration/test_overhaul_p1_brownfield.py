"""SPEC-hm-overhaul-p1 AC-007: upgrading a 0.62 tree sweeps only pristine retired files.

Fixtures, from committed bytes only: db19f023 renders for `[claude-code]` and
`[claude-code,codex]` x {Side, Production} x worktree {off, on}, and the 36 eval-3 hm trees
(the db19f023 harness on the bench fixture, plus each run's patch). Each is upgraded with
`make --update` at HEAD. The expected sets are AC-004's list and the db19f023 render listing,
both fixed before the implementation.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import reconcile
from harness_maker.interview import answers_from_harness_yaml
from tests._overhaul_p1_ref import HEAD_SRC, init_project, ref_root, run_make
from tests.integration import test_overhaul_p1_eval3_replay as eval3

STAGES = ("research", "spec", "execute", "wrapup")
COMMANDS = {*STAGES, "health", "help", "make", "metrics", "uninstall"}
BASE_AGENTS = {"code-reviewer", "judgment-reviewer", "spec-validator"}
LENSES = (
    "security-reviewer",
    "concurrency-reviewer",
    "test-reviewer",
    "performance-reviewer",
    "ux-reviewer",
)
KEPT_SKILLS = {
    "agent-quality-rubric",
    "ai-readiness-rubric",
    "context-linter",
    "intent-layer",
    "maker",
    "project-knowledge",
    "worktree-isolator",
}
RETIRED_HOOKS = (
    "harness_maker.telemetry",
    "harness_maker.hooks.post_write_reminder",
    "harness_maker.hooks.autopilot_autoarm",
)
#: Never touched by an upgrade: the user's own records.
UNTOUCHED = ("specs/", "work-docs/", ".claude/memory/", ".claude/observability/")
_KEPT = re.compile(r"orphan-sweep KEPT (\S+)")

_CELLS = [
    (targets, preset, wt)
    for targets in ("claude-code", "claude-code,codex")
    for preset in ("Side", "Production")
    for wt in (False, True)
]
_WORKERS = 6


def _cell_name(cell: tuple[str, str, bool]) -> str:
    targets, preset, wt = cell
    return f"{preset}-{targets.replace(',', '+')}-{'wt' if wt else 'nowt'}"


def _listing(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if (
            not p.is_file()
            or rel.parts[0] in (".git", ".venv")
            or rel.parts[0].startswith(".backup-")
        ):
            continue
        out[rel.as_posix()] = p.read_bytes()
    return out


def _harness_paths(listing: dict[str, bytes]) -> set[str]:
    """The paths a render owns: the five render locations (`reconcile.sweep_orphans`)."""
    return {
        p
        for p in listing
        if p.startswith((".claude/", ".codex/", ".agents/")) or p in ("AGENTS.md", "CLAUDE.md")
    }


def _upgrade(
    project: Path, home: Path, extra: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[str]:
    r = run_make(project, ["--update", *extra], src=HEAD_SRC, home=home)
    assert r.returncode == 0, (project.name, r.stdout[-2000:], r.stderr[-2000:])
    return r


def _render62(base: Path, name: str, cell: tuple[str, str, bool], src: Path) -> Path:
    targets, preset, wt = cell
    project = init_project(base / name / "project")
    args = ["--autoloop", "--preset", preset, "--targets", targets]
    args.append("--worktree" if wt else "--no-worktree")
    r = run_make(project, args, src=src, home=base / name / "home")
    assert r.returncode == 0, (name, r.stdout[-2000:], r.stderr[-2000:])
    return project


@pytest.fixture(scope="module")
def ref_src(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return ref_root(tmp_path_factory.mktemp("ac007-ref")) / "src"


@pytest.fixture(scope="module")
def pristine(tmp_path_factory: pytest.TempPathFactory, ref_src: Path) -> dict[str, Path]:
    """The eight db19f023 renders, kept pristine; tests upgrade copies."""
    base = tmp_path_factory.mktemp("ac007-62")
    with ThreadPoolExecutor(_WORKERS) as pool:
        futures = {
            _cell_name(c): pool.submit(_render62, base, _cell_name(c), c, ref_src) for c in _CELLS
        }
        return {n: f.result() for n, f in futures.items()}


def _copy(src: Path, dest: Path) -> Path:
    shutil.copytree(src, dest, symlinks=True)
    return dest


def _eval3_tree(cache: Path, dest: Path, run: str) -> Path:
    """One eval-3 hm tree as the run left it: the db19f023 harness commit plus the run's patch."""
    tree = _copy(eval3._template(cache, eval3._task(run)), dest / run)
    subprocess.run(
        [
            "git",
            "apply",
            "--binary",
            "--whitespace=nowarn",
            str(eval3.FIXTURES / run / "patch.diff"),
        ],
        cwd=tree,
        check=True,
        capture_output=True,
        timeout=120,
    )
    return tree


def _harness_commit_paths(tree: Path) -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        cwd=tree,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    return set(out.split())


def _expected_violations(root: Path, codex: bool) -> list[str]:
    """Where the upgraded tree differs from AC-004's set (no opt-in is on in a default 0.62)."""
    claude = root / ".claude"
    out: list[str] = []

    def names(d: Path, suffix: str) -> set[str]:
        return {p.name.removesuffix(suffix) for p in d.glob(f"*{suffix}")} if d.is_dir() else set()

    def dirs(d: Path) -> set[str]:
        return {p.name for p in d.iterdir() if p.is_dir()} if d.is_dir() else set()

    checks: list[tuple[str, set[str], set[str]]] = [
        ("commands", names(claude / "commands" / "hm", ".md"), COMMANDS),
        ("agents", names(claude / "agents", ".md"), BASE_AGENTS),
        ("skills", dirs(claude / "skills"), KEPT_SKILLS),
    ]
    if codex:
        checks += [
            (
                "codex skills",
                dirs(root / ".agents" / "skills"),
                {f"hm-{s}" for s in (*STAGES, "help")} | KEPT_SKILLS,
            ),
            ("codex agents", names(root / ".codex" / "agents", ".toml"), BASE_AGENTS),
        ]
    for label, got, want in checks:
        if got != want:
            out.append(f"{label}: extra {sorted(got - want)}, missing {sorted(want - got)}")
    for absent in (claude / "stages", claude / "hm", root / ".cursor"):
        if absent.exists():
            out.append(f"{absent.relative_to(root)} still exists")
    return out


def _settings_commands(root: Path) -> list[str]:
    data = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    return [
        h["command"]
        for groups in data.get("hooks", {}).values()
        for g in groups
        for h in g.get("hooks", [])
    ]


#: The sweep's own KEPT log: an upgrade appends to it, never rewrites it.
_APPEND_ONLY = re.compile(r"\.claude/observability/orphans-[\d-]+\.jsonl$")


_STAMP = re.compile(rb"\A(---\n(?:.*\n)*?)harness_maker_version: [^\n]*\n")


def _stamp_masked(data: bytes) -> bytes:
    """Memory seed files carry no `content_hash` (they are append targets), so an upgrade only
    re-stamps their frontmatter version; the body, which is the user's record, must not move."""
    return _STAMP.sub(rb"\1harness_maker_version: <V>\n", data, count=1)


def _pristine_render(data: bytes) -> bool:
    """A file the 0.62 render seeded and nobody has edited since: its frontmatter `content_hash`
    still matches its body (pre-change-checklist item 1). An upgrade may re-render it — that is
    harness state, not the user's record; every other file under `UNTOUCHED` is the user's."""
    text = data.decode("utf-8", errors="replace")
    end = text.find("\n---\n", 4)
    if not text.startswith("---\n") or end == -1:
        return False
    try:
        fm = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return False
    body = text[end + 5 :].encode("utf-8")
    return isinstance(fm, dict) and fm.get("content_hash") == reconcile.compute_body_hash(body)


def _sweep_violations(
    before: dict[str, bytes], root: Path, codex: bool, owned: set[str]
) -> list[str]:
    after = _listing(root)
    out = _expected_violations(root, codex)
    removed = set(before) - set(after)
    out += [f"removed a path no 0.62 render owned: {p}" for p in sorted(removed - owned)]
    for path, data in before.items():
        if not path.startswith(UNTOUCHED) or _pristine_render(data):
            continue
        new = after.get(path)
        if _APPEND_ONLY.match(path) and new is not None and new.startswith(data):
            continue
        if new is None or _stamp_masked(new) != _stamp_masked(data):
            out.append(f"{path} changed")
    commands = _settings_commands(root)
    out += [
        f"retired hook still wired: {m}" for m in RETIRED_HOOKS if any(m in c for c in commands)
    ]
    return out


def test_ac007_pristine_trees_sweep_to_the_ac004_set(
    pristine: dict[str, Path], tmp_path_factory: pytest.TempPathFactory
) -> None:
    base = tmp_path_factory.mktemp("ac007-up")
    jobs: list[tuple[str, Path, bool, set[str]]] = []
    for cell in _CELLS:
        name = _cell_name(cell)
        tree = _copy(pristine[name], base / name)
        jobs.append((name, tree, "codex" in cell[0], _harness_paths(_listing(tree))))

    cache = base / "eval3-cache"
    for run in eval3.RUNS:
        tree = _eval3_tree(cache, base / "eval3", run)
        jobs.append((run, tree, False, _harness_commit_paths(tree)))

    def one(job: tuple[str, Path, bool, set[str]]) -> list[str]:
        name, tree, codex, owned = job
        before = _listing(tree)
        _upgrade(tree, base / "home" / name)
        return [f"{name}: {v}" for v in _sweep_violations(before, tree, codex, owned)]

    with ThreadPoolExecutor(_WORKERS) as pool:
        failures = [v for vs in pool.map(one, jobs) for v in vs]
    shutil.rmtree(cache, ignore_errors=True)
    assert len(jobs) == len(_CELLS) + 36, len(jobs)
    assert not failures, "\n".join(failures[:40])


def test_ac007_sweep_relation_rejects_a_kept_retired_file(
    pristine: dict[str, Path], tmp_path: Path
) -> None:
    """Negative control: a retired file left in place is a violation."""
    tree = _copy(pristine["Side-claude-code-nowt"], tmp_path / "t")
    before = _listing(tree)
    _upgrade(tree, tmp_path / "home")
    assert _sweep_violations(before, tree, False, _harness_paths(before)) == []
    (tree / ".claude" / "commands" / "hm" / "review.md").write_text("x", encoding="utf-8")
    assert _sweep_violations(before, tree, False, _harness_paths(before))


def _retired_paths(pristine_tree: Path, tmp: Path) -> list[str]:
    """The paths a pristine upgrade removes: every file the mutation run below edits."""
    tree = _copy(pristine_tree, tmp / "probe")
    before = set(_listing(tree))
    _upgrade(tree, tmp / "probe-home")
    return sorted(p for p in before - set(_listing(tree)) if not p.startswith(".claude/.backup"))


def test_ac007_one_byte_edit_is_kept(pristine: dict[str, Path], tmp_path: Path) -> None:
    """One mutation per run, over every retired path: the edited file stays byte-identical and
    gets exactly one KEPT warning."""
    source = pristine["Production-claude-code+codex-wt"]
    retired = _retired_paths(source, tmp_path)
    assert len(retired) >= 20, retired

    def one(item: tuple[int, str]) -> list[str]:
        i, rel = item
        tree = _copy(source, tmp_path / f"m{i}")
        path = tree / rel
        path.write_bytes(path.read_bytes() + b"x")
        edited = path.read_bytes()
        r = _upgrade(tree, tmp_path / f"h{i}")
        out: list[str] = []
        if not path.is_file() or path.read_bytes() != edited:
            out.append(f"{rel}: the edited file was not kept byte-identical")
        kept = [m for m in _KEPT.findall(r.stdout + r.stderr) if m == rel]
        if len(kept) != 1:
            out.append(f"{rel}: {len(kept)} KEPT warnings, expected 1")
        return out

    with ThreadPoolExecutor(_WORKERS) as pool:
        failures = [v for vs in pool.map(one, enumerate(retired)) for v in vs]
    assert not failures, "\n".join(failures[:40])


def _edit_yaml(path: Path, edits: dict[str, object]) -> None:
    text = path.read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    data = yaml.safe_load(body)
    for key, value in edits.items():
        _setdeep(data, key, value)
    path.write_text(f"---\n{front}---\n{yaml.safe_dump(data, sort_keys=False)}", encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8").split("---\n", 2)[2])
    return data


def _setdeep(data: dict[str, Any], dotted: str, value: object) -> None:
    *head, last = dotted.split(".")
    node = data
    for part in head:
        node = node.setdefault(part, {})
    node[last] = value


def _getdeep(data: dict[str, Any], dotted: str) -> object:
    node: Any = data
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


#: (label, edits, the inert key one warning must name, a key no warning may name). A 0.62 file
#: already names lens reviewers in `installed` and sets `autopilot_persistent: true`, so the
#: unedited tree's own warnings are the baseline the "gives none" rows compare against.
#: Each row's 5th field is extra `make` flags. A `forbid` of "" means no inert warning at all.
_Row = tuple[str, dict[str, object], str | None, str | None, tuple[str, ...]]
_LENS_FANOUT = {"reviewers.fanout": True, "reviewers.installed": ["code-reviewer", *LENSES]}
_RETIRED_AGENT_MODEL_ROWS: list[_Row] = [
    (
        f"agent-model-{n}",
        {f"agent_models.{n}": {"claude": "tier-small"}},
        f"agent_models.{n}",
        None,
        (),
    )
    for n in ("stuck", "security-auditor", "executor", "autoloop-coder")
]
_KEY_ROWS: list[_Row] = [
    ("loop", {"loop.enabled": True}, "loop.enabled", None, ()),
    ("deleg-review", {"delegation.stages": ["review", "execute"]}, "delegation.stages", None, ()),
    ("deleg-verify", {"delegation.stages": ["verify"]}, "delegation.stages", None, ()),
    ("rounds", {"reviewers.max_review_rounds": 4}, None, "max_review_rounds", ()),
    # The 0.62 file names every lens in `installed`, so each lens row first narrows it to
    # code-reviewer; otherwise the row would pass on the unedited file's own warning.
    (
        "lens-no-fanout",
        {
            "reviewers.installed": ["code-reviewer"],
            "reviewers.enabled": ["code-reviewer", "security-reviewer"],
        },
        "reviewers.installed/enabled",
        None,
        (),
    ),
    (
        "lens-none",
        {"reviewers.installed": ["code-reviewer"], "reviewers.enabled": ["code-reviewer"]},
        None,
        "reviewers.installed/enabled",
        (),
    ),
    ("fanout", _LENS_FANOUT, None, "reviewers.", ()),
    # A `--preset` switch rebuilds the answers from an allowlist; the fan-out must survive it.
    ("fanout-preset", _LENS_FANOUT, None, "reviewers.", ("--preset", "Production")),
    (
        "fanout-empty",
        {"reviewers.fanout": True, "reviewers.installed": ["code-reviewer"]},
        "reviewers.fanout",
        None,
        (),
    ),
    (
        "skill",
        {"skills.enabled": ["context-linter", "conditional-router"]},
        "skills.enabled",
        None,
        (),
    ),
    (
        "agent-model",
        {"agent_models.test-reviewer": {"claude": "tier-small"}},
        "agent_models.test-reviewer",
        None,
        (),
    ),
    *_RETIRED_AGENT_MODEL_ROWS,
    (
        "autopilot",
        {"autonomy.autopilot_persistent": True},
        "autonomy.autopilot_persistent",
        None,
        (),
    ),
    (
        "autopilot-off",
        {"autonomy.autopilot_persistent": False},
        None,
        "autonomy.autopilot_persistent",
        (),
    ),
    (
        "none",
        {
            "loop.enabled": False,
            "delegation.stages": [],
            "reviewers.installed": ["code-reviewer"],
            "reviewers.enabled": ["code-reviewer"],
            "skills.enabled": ["context-linter"],
            "agent_models": {},
            "instrumentation.stage_agent_ledger": False,
            "autonomy.autopilot_persistent": False,
        },
        None,
        "",
        (),
    ),
]


def _inert_warnings(r: subprocess.CompletedProcess[str]) -> list[str]:
    return [ln for ln in r.stderr.splitlines() if ln.startswith("warn: inert key")]


def test_ac007_user_blocks_and_hooks_survive(pristine: dict[str, Path], tmp_path: Path) -> None:
    source = pristine["Side-claude-code+codex-nowt"]
    tree = _copy(source, tmp_path / "blocks")
    marker = "USER-BLOCK-TEXT-ac007"
    wrapup = tree / ".claude" / "commands" / "hm" / "wrapup.md"
    close = "<!-- @hm:/user:extensions -->"
    text = wrapup.read_text(encoding="utf-8")
    assert close in text
    wrapup.write_text(text.replace(close, f"{marker}\n{close}", 1), encoding="utf-8")
    settings = tree / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    bash = next(g for g in data["hooks"]["PreToolUse"] if g.get("matcher") == "Bash")
    bash["hooks"].append({"type": "command", "command": "echo user-hook-in-harness-group"})
    data["hooks"].setdefault("PostToolUse", []).append(
        {"matcher": "Read", "hooks": [{"type": "command", "command": "echo user-hook-own-group"}]}
    )
    settings.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Twice: a block-merged file records its merged hash, and the second upgrade once read that
    # as pristine and replaced it (PLAN ADR-043; `reconcile._user_blocks_edited`).
    _upgrade(tree, tmp_path / "home-blocks")
    _upgrade(tree, tmp_path / "home-blocks")

    failures: list[str] = []
    new_wrapup = wrapup.read_text(encoding="utf-8")
    if marker not in new_wrapup:
        failures.append("the user-block text left wrapup.md")
    if "## Step 5 — Memory" not in new_wrapup:
        failures.append("wrapup.md is not the 0.64 stage")
    commands = _settings_commands(tree)
    for hook in ("echo user-hook-in-harness-group", "echo user-hook-own-group"):
        if hook not in commands:
            failures.append(f"user hook lost: {hook}")
    failures += [
        f"retired hook still wired: {m}" for m in RETIRED_HOOKS if any(m in c for c in commands)
    ]

    base_tree = _copy(source, tmp_path / "k-baseline")
    baseline = set(_inert_warnings(_upgrade(base_tree, tmp_path / "kh-baseline")))

    def one(row: _Row) -> list[str]:
        label, edits, key, forbid, flags = row
        t = _copy(source, tmp_path / f"k-{label}")
        yaml_path = t / ".claude" / "harness.yaml"
        _edit_yaml(yaml_path, edits)
        out: list[str] = []
        for run in (1, 2):  # the warning repeats per `make`; the value survives both re-renders
            warnings = _inert_warnings(_upgrade(t, tmp_path / f"kh-{label}", flags))
            if key is not None and len([w for w in warnings if f" {key}:" in w]) != 1:
                out.append(f"{label} run {run}: expected one warning naming {key}, got {warnings}")
            if forbid is not None:
                extra = [w for w in warnings if forbid in w or (forbid and w not in baseline)]
                if extra:
                    out.append(f"{label} run {run}: unexpected {extra}")
            after = _load_yaml(yaml_path)
            for k, v in edits.items():
                if _getdeep(after, k) != v:
                    out.append(f"{label} run {run}: {k} became {_getdeep(after, k)!r}")
            if answers_from_harness_yaml(yaml_path) is None:
                out.append(f"{label} run {run}: harness.yaml no longer parses")
            execute = (t / ".claude" / "commands" / "hm" / "execute.md").read_text(encoding="utf-8")
            if label == "rounds" and "(4) rounds" not in execute:
                out.append("reviewers.max_review_rounds is no longer read by execute.md")
            if label in ("fanout", "fanout-preset"):
                agents = {p.stem for p in (t / ".claude" / "agents").glob("*.md")}
                if not set(LENSES) <= agents:
                    out.append(f"{label} run {run}: lens agents missing, have {sorted(agents)}")
        return out

    with ThreadPoolExecutor(_WORKERS) as pool:
        failures += [v for vs in pool.map(one, _KEY_ROWS) for v in vs]
    assert not failures, "\n".join(failures)
