"""SPEC-hm-overhaul-p1 PR-C: the Cursor target leaves the render and the code (AC-001, AC-002)."""

from __future__ import annotations

import difflib
import hashlib
import inspect
import itertools
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest

from harness_maker import hook_host, models, presets, readiness, reconcile, render, synthesize
from harness_maker.io_utils import load_harness_yaml
from tests._overhaul_p1_ref import (
    HEAD_SRC,
    REPO_ROOT,
    init_project,
    ref_root,
    run_make,
    tree_files,
)

TEMPLATES = HEAD_SRC / "harness_maker" / "templates"
_WORKERS = 6


@pytest.fixture(scope="module")
def ref_src(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return ref_root(tmp_path_factory.mktemp("overhaul-ref")) / "src"


# ── AC-001: differential render ──────────────────────────────────────────────

_TARGETS: tuple[tuple[str, ...], ...] = (
    ("claude-code", "cursor"),
    ("claude-code", "cursor", "codex"),
    ("cursor",),
    ("claude-code",),
    ("claude-code", "codex"),
)
_PRESETS = ("Side", "Production")
_WORKTREE = (False, True)


def _minus_cursor(targets: tuple[str, ...]) -> tuple[str, ...]:
    kept = tuple(t for t in targets if t != "cursor")
    return kept or ("claude-code",)


def _make_args(targets: tuple[str, ...], preset: str, worktree: bool) -> list[str]:
    return [
        "--autoloop",
        "--preset",
        preset,
        "--targets",
        ",".join(targets),
        "--worktree" if worktree else "--no-worktree",
    ]


def _render(
    base: Path, name: str, args: list[str], src: Path, *, agent_models: str | None = None
) -> dict[str, str]:
    """One render; with `agent_models`, appended to harness.yaml and re-rendered by `--update`."""
    project = init_project(base / name / "project")
    r = run_make(project, args, src=src, home=base / name / "home")
    assert r.returncode == 0, (name, args, r.stdout[-2000:], r.stderr[-2000:])
    if agent_models is not None:
        yaml_path = project / ".claude" / "harness.yaml"
        yaml_path.write_text(yaml_path.read_text(encoding="utf-8") + agent_models, encoding="utf-8")
        r = run_make(project, ["--update"], src=src, home=base / name / "home")
        assert r.returncode == 0, (name, "--update", r.stdout[-2000:], r.stderr[-2000:])
    return tree_files(project)


def _is_cursor_deletion(old: str, new: str) -> bool:
    """`new` is `old` with only characters deleted, and what was deleted names Cursor.

    Character-level: nothing inserted or substituted, so the line cannot have gained or
    reworded anything. The deleted runs together must mention Cursor; a qualifier that only
    existed to contrast with Cursor (`in Claude Code` beside `in Cursor`) may go with it.
    """
    if old == new:
        return False
    ops = difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
    if any(tag in ("insert", "replace") for tag, *_ in ops):
        return False
    deleted = "".join(old[i1:i2] for tag, i1, i2, _, _ in ops if tag == "delete")
    return "cursor" in deleted.lower()


def _hunk_violation(old: list[str], new: list[str]) -> bool:
    """Every new line is an old line with Cursor deleted; every unpaired old line names Cursor."""
    i = 0
    for line in new:
        while i < len(old) and not _is_cursor_deletion(old[i], line):
            if "cursor" not in old[i].lower():
                return True
            i += 1
        if i == len(old):
            return True
        i += 1
    return any("cursor" not in rest.lower() for rest in old[i:] if rest.strip())


def _violations(ref: dict[str, str], head: dict[str, str]) -> list[str]:
    """The AC-001 relation: equal file sets; every hunk only deletes Cursor lines or Cursor text.

    A pure delete may take blank lines with it; a replace pairs each new line with an old one
    it is a Cursor deletion of; an insert is never Cursor removal.
    """
    out: list[str] = []
    if set(ref) != set(head):
        out.append(
            f"file sets differ: only at db19f023 {sorted(set(ref) - set(head))}, "
            f"only at HEAD {sorted(set(head) - set(ref))}"
        )
    for path in sorted(set(ref) & set(head)):
        old, new = ref[path].splitlines(), head[path].splitlines()
        if old == new:
            continue
        matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            if tag == "insert" or _hunk_violation(old[i1:i2], new[j1:j2]):
                out.append(f"{path} -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1}: {new[j1:j2][:3]!r}")
    return out


def test_ac001_relation_rejects_what_is_not_cursor_removal() -> None:
    """Negative control for `_violations`: each of these must be reported."""
    ref = {"a.md": "keep\n| targets | `claude-code, cursor` |\nkeep\n"}
    ok = {"a.md": "keep\n| targets | `claude-code` |\nkeep\n"}
    assert _violations(ref, ok) == []
    assert _violations({"a.md": "x\nCursor note\n\ny\n"}, {"a.md": "x\ny\n"}) == []
    bad = (
        "keep\n| targets | `claude-code, codex` |\nkeep\n",  # reworded, not deleted
        "keep\n| targets | `claude-code` | extra\nkeep\n",  # gained text
        "keep\nkeep\n",  # a whole line went, but ...
        "keep\n| targets | `claude-code` |\nnew line\nkeep\n",  # an inserted line
    )
    for text in bad[:2] + bad[3:]:
        assert _violations(ref, {"a.md": text}), text
    assert _violations({"a.md": "keep\nplain line\nkeep\n"}, {"a.md": bad[2]})
    assert _violations(ref, {"a.md": ok["a.md"], "b.md": ""})


#: Side-preset `agent_models` cells (review round 1): a 0.62 override must render the same
#: Claude model whether it set `claude:`, only `cursor:`, or both.
_AGENT_MODELS = {
    "claude-only": "agent_models:\n  code-reviewer:\n    claude: haiku\n",
    "cursor-only": "agent_models:\n  code-reviewer:\n    cursor: haiku\n",
    "both": "agent_models:\n  code-reviewer:\n    claude: opus\n    cursor: haiku\n",
}


def test_ac001_render_equals_reference_without_cursor(tmp_path: Path, ref_src: Path) -> None:
    cells: list[tuple[tuple[str, ...], str, bool, str | None]] = [
        (t, p, w, None) for t, p, w in itertools.product(_TARGETS, _PRESETS, _WORKTREE)
    ]
    cells += [(("claude-code", "cursor"), "Side", False, "ko")]
    cells += [(("claude-code", "cursor"), "Side", False, f"am:{k}") for k in _AGENT_MODELS]
    refs = sorted({(_minus_cursor(t), p, w, x) for t, p, w, x in cells}, key=repr)

    def job(
        src: Path, tag: str, cell: tuple[tuple[str, ...], str, bool, str | None]
    ) -> dict[str, str]:
        t, p, w, extra = cell
        args = _make_args(t, p, w)
        agent_models = None
        if extra == "ko":
            args += ["--locale", "ko"]
        elif extra is not None:
            agent_models = _AGENT_MODELS[extra.removeprefix("am:")]
        name = f"{tag}-{'+'.join(t)}-{p}-{w}-{extra}"
        return _render(tmp_path, name, args, src, agent_models=agent_models)

    with ThreadPoolExecutor(_WORKERS) as pool:
        ref_trees = dict(zip(refs, pool.map(lambda c: job(ref_src, "ref", c), refs), strict=True))
        head_trees = dict(
            zip(cells, pool.map(lambda c: job(HEAD_SRC, "head", c), cells), strict=True)
        )

    failures: list[str] = []
    for (t, p, w, x), head in head_trees.items():
        for v in _violations(ref_trees[(_minus_cursor(t), p, w, x)], head):
            failures.append(f"targets={','.join(t)} preset={p} worktree={w} extra={x}: {v}")
    assert not failures, "\n".join(failures[:40])
    # The cells are not vacuous: the overrides really reach the agent file.
    reviewer = ".claude/agents/code-reviewer.md"
    for key, model in (("claude-only", "haiku"), ("cursor-only", "haiku"), ("both", "opus")):
        tree = head_trees[(("claude-code", "cursor"), "Side", False, f"am:{key}")]
        assert f"\nmodel: {model}\n" in tree[reviewer], key


def test_ac001_cursor_only_paths_absent() -> None:
    removed: dict[str, bool] = {
        "templates/cursor/": (TEMPLATES / "cursor").exists(),
        ".cursor-plugin/plugin.json": (REPO_ROOT / ".cursor-plugin" / "plugin.json").exists(),
        "Target.CURSOR": "cursor" in {t.value for t in models.Target},
        "render._is_cursor_mdc": hasattr(render, "_is_cursor_mdc"),
        "render._is_cursor_command": hasattr(render, "_is_cursor_command"),
        "render._is_cursor_mcp_json": hasattr(render, "_is_cursor_mcp_json"),
        ".cursor/ in _SIBLING_TREE_PREFIXES": ".cursor/" in render._SIBLING_TREE_PREFIXES,
        ".cursor/ in resolve_output_path": render.resolve_output_path(
            Path("/p/.claude"), Path(".cursor/x")
        )
        == Path("/p/.cursor/x"),
        "synthesize._cursor_target_files": hasattr(synthesize, "_cursor_target_files"),
        "cursor_model context": "cursor_model" in inspect.getsource(synthesize),
        "_alias_by_cursor_id": "_alias_by_cursor_id" in inspect.getsource(synthesize),
        "presets.CURSOR_MODEL_IDS": hasattr(presets, "CURSOR_MODEL_IDS"),
        "readiness Cursor advisory": "cursor_alias_vs_concrete_id" in inspect.getsource(readiness),
    }
    for fn in (
        render._entry_identity,
        render._strip_shipped_commands,
        render._refresh_ref,
        render._merge_hooks_json,
        render._render_hooks_json_merged,
    ):
        removed[f"flat schema in render.{fn.__name__}"] = '"flat"' in inspect.getsource(fn)
    for rel in ("commands/hm/help.en.md.j2", "commands/hm/help.ko.md.j2", "commands/hm/make.md.j2"):
        removed[f"cursor branch in {rel}"] = "cursor" in (TEMPLATES / rel).read_text().lower()
    plugin_make = (REPO_ROOT / "commands" / "make.md").read_text(encoding="utf-8")
    removed["cursor branch in plugin commands/make.md"] = "cursor" in plugin_make.lower()
    still_present = sorted(k for k, present in removed.items() if present)
    assert not still_present, f"Cursor-only code still present: {still_present}"

    kept = {
        "hook_host.is_claude_copy_in_cursor": callable(
            getattr(hook_host, "is_claude_copy_in_cursor", None)
        ),
        "tests/unit/test_hook_host.py": (REPO_ROOT / "tests/unit/test_hook_host.py").is_file(),
        ".cursor sweep root": ".cursor" in reconcile._SWEEP_ROOTS,
        ".cursor backup": '".cursor"' in inspect.getsource(reconcile.backup),
        ".cursor/hooks.json never swept": ".cursor/hooks.json" in reconcile._SWEEP_NEVER_DELETE,
        "AgentModelSpec.cursor parseable": "cursor" in models.AgentModelSpec.model_fields,
    }
    missing = sorted(k for k, ok in kept.items() if not ok)
    assert not missing, f"kept Cursor support is gone: {missing}"


# ── AC-002: the brownfield golden table ──────────────────────────────────────

_KEPT_TEXT = (
    "kept `{path}`: you edited it, so it was not deleted. harness-maker no longer maintains it "
    "and it will not be updated. Its hook commands point at this plugin version's cache path "
    "and stop working once that cache is pruned. Remove it when you are done with it."
)
_CURSOR_FILES = (".cursor/rules/harness.mdc", ".cursor/mcp.json", ".cursor/hooks.json")
_FULL = "claude-code,cursor,codex"


@dataclass
class _Row:
    name: str
    targets: str | None  # the 0.62 tree's targets; None = no 0.62 tree (fresh HEAD render)
    mutate: Callable[[Path, Path, Path], None]  # (project, ref_src, home)
    head_args: list[str]
    check: Callable[[Path, str, dict[str, bytes]], list[str]]  # (project, output, before)
    head_runs: int = 1  # the check reads the LAST run's output


def _no_mutation(project: Path, ref_src: Path, home: Path) -> None:
    del project, ref_src, home


def _edit_mdc(project: Path, ref_src: Path, home: Path) -> None:
    del ref_src, home
    p = project / ".cursor/rules/harness.mdc"
    data = bytearray(p.read_bytes())
    data[-2] = ord("X") if data[-2] != ord("X") else ord("Y")
    p.write_bytes(bytes(data))


def _edit_mcp(project: Path, ref_src: Path, home: Path) -> None:
    del ref_src, home
    p = project / ".cursor/mcp.json"
    p.write_text(json.dumps({"mcpServers": {"mine": {"command": "my-server"}}}), encoding="utf-8")


def _merge_user_hook(project: Path, ref_src: Path, home: Path) -> None:
    """A user entry folded into `.cursor/hooks.json` by a 0.62 `make --update`."""
    p = project / ".cursor/hooks.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["hooks"].setdefault("stop", []).append({"command": "echo my-own-stop-hook"})
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    r = run_make(project, ["--update"], src=ref_src, home=home)
    assert r.returncode == 0, r.stderr[-2000:]
    merged = p.read_text(encoding="utf-8")
    assert "my-own-stop-hook" in merged, "precondition: 0.62 merge kept the user entry"
    digest = hashlib.sha256(merged.encode("utf-8")).hexdigest()
    manifest = (project / ".claude/.hm-render-manifest.jsonl").read_text(encoding="utf-8")
    assert digest in manifest, "precondition: the merged hash is recorded in the manifest"


def _add_cursor_agent_model(project: Path, ref_src: Path, home: Path) -> None:
    del ref_src, home
    p = project / ".claude/harness.yaml"
    p.write_text(
        p.read_text(encoding="utf-8") + "agent_models:\n  code-reviewer:\n    cursor: opus\n",
        encoding="utf-8",
    )


def _plant_hooks(text: str) -> Callable[[Path, Path, Path], None]:
    """A `.cursor/hooks.json` the manifest never recorded (hand-made, or a pre-manifest 0.5x)."""

    def plant(project: Path, ref_src: Path, home: Path) -> None:
        del ref_src, home
        (project / ".cursor").mkdir(parents=True, exist_ok=True)
        (project / ".cursor/hooks.json").write_text(text, encoding="utf-8")

    return plant


_HAND_MADE_HOOKS = json.dumps({"version": 1, "hooks": {"stop": [{"command": "echo mine"}]}})
#: The 0.5x shape: flat Cursor schema, no `HM_HOOK_HOST` marker, no `sessionStart`.
_PRE_MARKER_05X_HOOKS = json.dumps(
    {
        "version": 1,
        "hooks": {
            "stop": [
                {
                    "command": 'uv run --with "$HOME/.claude/plugins/cache/harness-maker/0.5.7" '
                    "python -m harness_maker.telemetry"
                }
            ]
        },
    },
    indent=2,
)


def _expect_unrecorded_hooks_untouched(
    project: Path, output: str, before: dict[str, bytes]
) -> list[str]:
    """No manifest record: the file is left alone and never told "you edited it"."""
    errs: list[str] = []
    rel = ".cursor/hooks.json"
    if (project / rel).read_bytes() != before[rel]:
        errs.append(f"{rel} not kept byte-identical")
    if "you edited it" in output:
        errs.append("the KEPT edited-file text was printed for a file the harness never wrote")
    other = [w for w in _cursor_warnings(output) if "orphan-sweep KEPT .cursor/hooks.json" not in w]
    if other:
        errs.append(f"unexpected cursor warnings: {other}")
    if len(_cursor_warnings(output)) > 1:
        errs.append(f"{len(_cursor_warnings(output))} lines about {rel}")
    return errs


def _cursor_warnings(output: str) -> list[str]:
    return [
        line
        for line in output.splitlines()
        if line.lstrip().startswith("WARN") and "cursor" in line.lower()
    ]


def _removed_warnings(output: str) -> list[str]:
    return [line for line in _cursor_warnings(output) if "cursor target removed" in line]


def _kept_warnings(output: str, path: str) -> list[str]:
    text = _KEPT_TEXT.format(path=path)
    return [line for line in _cursor_warnings(output) if text in line]


def _targets(project: Path) -> list[str]:
    return [str(t) for t in load_harness_yaml(project / ".claude/harness.yaml")["targets"]]


def _expect(
    *,
    removed_warnings: int,
    kept: tuple[str, ...] = (),
    targets: list[str],
    extra_warning: str | None = None,
    yaml_contains: str | None = None,
) -> Callable[[Path, str, dict[str, bytes]], list[str]]:
    def check(project: Path, output: str, before: dict[str, bytes]) -> list[str]:
        errs: list[str] = []
        if len(_removed_warnings(output)) != removed_warnings:
            errs.append(f"'cursor target removed' x{len(_removed_warnings(output))}")
        for rel in _CURSOR_FILES:
            path = project / rel
            if rel in kept:
                if not path.is_file() or path.read_bytes() != before.get(rel):
                    errs.append(f"{rel} not kept byte-identical")
                if len(_kept_warnings(output, rel)) != 1:
                    errs.append(f"{rel}: KEPT warning x{len(_kept_warnings(output, rel))}")
            elif path.exists():
                errs.append(f"{rel} not deleted")
        if not kept and (project / ".cursor").exists():
            errs.append(".cursor/ not removed")
        expected = removed_warnings + len(kept) + (1 if extra_warning else 0)
        if len(_cursor_warnings(output)) != expected:
            errs.append(f"{len(_cursor_warnings(output))} cursor warnings, expected {expected}")
        if extra_warning and not any(extra_warning in w for w in _cursor_warnings(output)):
            errs.append(f"no warning naming {extra_warning}")
        if _targets(project) != targets:
            errs.append(f"targets {_targets(project)} != {targets}")
        harness_yaml = (project / ".claude/harness.yaml").read_text(encoding="utf-8")
        if yaml_contains and yaml_contains not in harness_yaml:
            errs.append(f"harness.yaml lost {yaml_contains!r}")
        return errs

    return check


_ROWS = (
    _Row(
        "pristine",
        _FULL,
        _no_mutation,
        ["--update"],
        _expect(removed_warnings=1, targets=["claude-code", "codex"]),
    ),
    _Row(
        "mdc-edited",
        _FULL,
        _edit_mdc,
        ["--update"],
        _expect(
            removed_warnings=1,
            kept=(".cursor/rules/harness.mdc",),
            targets=["claude-code", "codex"],
        ),
    ),
    _Row(
        "hooks-merged-user-entry",
        _FULL,
        _merge_user_hook,
        ["--update"],
        _expect(removed_warnings=1, kept=(".cursor/hooks.json",), targets=["claude-code", "codex"]),
    ),
    _Row(
        "mcp-edited",
        _FULL,
        _edit_mcp,
        ["--update"],
        _expect(removed_warnings=1, kept=(".cursor/mcp.json",), targets=["claude-code", "codex"]),
    ),
    _Row(
        "cursor-only",
        "cursor",
        _no_mutation,
        ["--update"],
        _expect(removed_warnings=1, targets=["claude-code"]),
    ),
    _Row(
        "agent-models-cursor",
        "claude-code",
        _add_cursor_agent_model,
        ["--update"],
        _expect(
            removed_warnings=0,
            targets=["claude-code"],
            extra_warning="agent_models.code-reviewer.cursor",
            yaml_contains="    cursor: opus\n",
        ),
    ),
    _Row(
        "hooks-kept-again-on-second-update",
        _FULL,
        _merge_user_hook,
        ["--update"],
        _expect(removed_warnings=0, kept=(".cursor/hooks.json",), targets=["claude-code", "codex"]),
        head_runs=2,
    ),
    _Row(
        "hooks-never-rendered",
        None,
        _plant_hooks(_HAND_MADE_HOOKS),
        ["--autoloop", "--preset", "Side", "--targets", "claude-code,codex"],
        _expect_unrecorded_hooks_untouched,
    ),
    _Row(
        "hooks-pre-marker-05x",
        None,
        _plant_hooks(_PRE_MARKER_05X_HOOKS),
        ["--autoloop", "--preset", "Side", "--targets", "claude-code,codex"],
        _expect_unrecorded_hooks_untouched,
    ),
    _Row(
        "fresh-targets-flag",
        None,
        _no_mutation,
        ["--autoloop", "--preset", "Side", "--targets", "claude-code,cursor"],
        _expect(removed_warnings=1, targets=["claude-code"]),
    ),
    _Row(
        "fresh-no-cursor",
        None,
        _no_mutation,
        ["--autoloop", "--preset", "Side", "--targets", "claude-code,codex"],
        _expect(removed_warnings=0, targets=["claude-code", "codex"]),
    ),
)


def test_ac002_cursor_brownfield_table(tmp_path: Path, ref_src: Path) -> None:
    def run_row(row: _Row) -> list[str]:
        project = init_project(tmp_path / row.name / "project")
        home = tmp_path / row.name / "home"
        if row.targets is not None:
            r = run_make(
                project,
                ["--autoloop", "--preset", "Side", "--targets", row.targets],
                src=ref_src,
                home=home,
            )
            assert r.returncode == 0, (row.name, r.stderr[-2000:])
        row.mutate(project, ref_src, home)
        before = {
            rel: (project / rel).read_bytes() for rel in _CURSOR_FILES if (project / rel).is_file()
        }
        for _ in range(row.head_runs):
            r = run_make(project, row.head_args, src=HEAD_SRC, home=home)
            if r.returncode != 0:
                return [f"{row.name}: make exited {r.returncode}: {r.stderr[-1500:]}"]
        return [f"{row.name}: {e}" for e in row.check(project, r.stdout + r.stderr, before)]

    with ThreadPoolExecutor(_WORKERS) as pool:
        failures = [e for errs in pool.map(run_row, _ROWS) for e in errs]
    assert not failures, "\n".join(failures)
