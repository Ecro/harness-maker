"""AC-004/005/009 — execute the lines the TEMPLATE renders, against a real git worktree.

The defect these cover is not a logic bug. `wrapup_brief` was correct; the rendered `!`
line invoked it from the base repo with `--root .`, and `!` lines execute at the base, so
the gate reported `degraded` on every Production wrapup for four months while every unit
test stayed green. A test that constructs its own argv reproduces the bug it is meant to
detect, and a test that mocks git lets the base-cwd resolution pass. So: the argv is
**extracted from a hermetic render**, and the repository is real.

Only the interpreter prefix is substituted. `uv run --with $HOME/harness-maker python` is
not runnable here (the pin is a literal, unexpanded string), so the prefix is matched
exactly — a drift in it fails the match — and `sys.executable` is put in its place. Every
flag downstream of the module name is used verbatim.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from harness_maker.models import (
    DelegationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from ..render.conftest import pin_install_ref

SLUG_TOKEN = "<slug>"

# The module name is part of the match, so the brief line cannot be silently satisfied by
# the adjacent `wrapup_receipt` line, which has the same prefix and a similar tail.
_PREFIX = re.compile(r"^uv run --with (?P<ref>\S+) hm (?P<module>[\w.]+)\s*(?P<rest>.*)$")


def _rendered_wrapup_command() -> str:
    """A hermetic render, NOT this repo's committed `.claude/commands/hm/wrapup.md`.

    The AC is about the template. Reading the dogfood copy would test whatever the last
    `--update` happened to leave on disk, which drifts independently of the source.

    `delegation.stages` MUST name wrapup: the Step 0.5 block is behind a Jinja guard on
    exactly that key, so the default config renders no `!` line at all and the extraction
    below would find nothing to assert about.
    """
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / ".claude"
        out.mkdir()
        with pytest.MonkeyPatch.context() as mp:
            pin_install_ref(mp)
            render(
                synthesize(
                    ProjectProfile(),
                    InterviewAnswers(
                        preset=Preset.PRODUCTION,
                        targets=[Target.CLAUDE_CODE],
                        locale="en",
                        delegation=DelegationConfig(stages=["wrapup"]),
                    ),
                ),
                out,
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        return (out / "commands" / "hm" / "wrapup.md").read_text(encoding="utf-8")


def _bang_line(module: str, *, containing: str = "") -> str:
    """`containing` keys the extraction on the BRANCH, not just on the module.

    Keying on the module name alone would abort on a correct implementation the day a
    second ledger invocation is rendered elsewhere in the stage. That direction is a false
    RED rather than a false GREEN, but a gate that fires on correct code gets loosened.
    """
    body = _rendered_wrapup_command()
    hits = [
        line[1:].strip()
        for line in body.splitlines()
        if line.startswith("!") and f" hm {module} " in line and containing in line
    ]
    assert len(hits) == 1, f"expected exactly one rendered `!` line for {module}, got {hits}"
    return hits[0]


def _argv(line: str, module: str) -> list[str]:
    match = _PREFIX.match(line)
    assert match is not None, f"rendered line is not the expected invoker shape: {line!r}"
    assert match.group("module") == module
    # Executed through the DISPATCHER (`harness_maker.hm`), not through
    # `harness_maker.<module>` directly and not through the `hm` console script. The
    # dispatcher is the code path the rendered line actually takes, and reaching it via
    # `-m` avoids depending on the script being on PATH in the test environment.
    return [sys.executable, "-m", "harness_maker.hm", module, *shlex.split(match.group("rest"))]


def _sub_slug(argv: list[str], slug: str) -> list[str]:
    assert SLUG_TOKEN in argv, f"rendered argv carries no {SLUG_TOKEN} token: {argv}"
    return [slug if part == SLUG_TOKEN else part for part in argv]


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60, check=True)


@pytest.fixture
def base_repo(tmp_path: Path) -> Path:
    """A real repository on `main`, with no task worktree yet."""
    base = (tmp_path / "base").resolve()
    base.mkdir()
    _git(["init", "-b", "main"], base)
    _git(["config", "user.email", "t@example.com"], base)
    _git(["config", "user.name", "t"], base)
    (base / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "-A"], base)
    _git(["commit", "-m", "init"], base)
    return base


def _add_task_worktree(base: Path, slug: str) -> Path:
    """Exactly where `validate_brief` requires it — `<base>/.worktrees/<slug>` on `hm/<slug>`."""
    wt = base / ".worktrees" / slug
    _git(["worktree", "add", "-b", f"hm/{slug}", str(wt)], base)
    return wt.resolve()


# ------------------------------------------------------------------------ AC-004


def test_ac_004_rendered_brief_argv_resolves_the_task_worktree_from_the_base(
    base_repo: Path,
) -> None:
    slug = "demo-task"
    _add_task_worktree(base_repo, slug)
    argv = _argv(_bang_line("wrapup_brief"), "wrapup_brief")

    # Asserted BEFORE substitution: a template that resolved the seam by pointing `--root`
    # at the worktree would pass the status check below while re-introducing the very
    # cwd-dependence this AC exists to pin. The seam is that `!` runs at the base.
    assert "--root" in argv
    assert argv[argv.index("--root") + 1] == "."

    proc = _run(_sub_slug(argv, slug), cwd=base_repo)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok", payload["verdict"]
    assert payload["brief"]["slug"] == slug
    assert payload["brief"]["worktree_root"] == str(base_repo / ".worktrees" / slug)


# ------------------------------------------------------------------------ AC-005


@pytest.mark.parametrize("shape", ["slug-names-nothing", "slug-absent"])
def test_ac_005_no_task_branch_degrades_gracefully(base_repo: Path, shape: str) -> None:
    """Both standalone shapes. The supported recovery path must not become a failure.

    A fix that made every cwd resolve to *something* would turn this degrade into a
    confident wrong answer, so `missing` is asserted by name rather than by truthiness.
    """
    argv = _argv(_bang_line("wrapup_brief"), "wrapup_brief")
    if shape == "slug-names-nothing":
        argv = _sub_slug(argv, "absent-task")
    else:
        i = argv.index("--slug")
        argv = argv[:i] + argv[i + 2 :]

    proc = _run(argv, cwd=base_repo)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "degraded"
    assert payload["brief"] is None
    assert "slug" in payload["verdict"]["missing"]
    assert payload["verdict"]["reason"].strip()


# ------------------------------------------------------------------------ AC-009


def test_ac_009_rendered_self_skip_line_writes_an_unavailable_row(base_repo: Path) -> None:
    """The branch claims to record something. Executing it is the only way to know.

    A fixture-built ledger proves the reader works and says nothing about whether the
    prose branch ever writes a row — which is the shape of the defect being fixed.
    """
    line = _bang_line("delegation_ledger", containing="--status unavailable")
    argv = _argv(line, "delegation_ledger")
    proc = _run(_sub_slug(argv, "demo-task"), cwd=base_repo)
    assert proc.returncode == 0, proc.stderr

    ledger = base_repo / ".claude" / "observability" / "delegation.jsonl"
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    unavailable = [r for r in rows if r["kind"] == "dispatch" and r["status"] == "unavailable"]
    assert len(unavailable) == 1, rows
    assert unavailable[0]["stage"] == "wrapup"
    assert unavailable[0]["slug"] == "demo-task"


def test_the_self_skip_row_lands_at_the_base_even_when_run_from_the_worktree(
    base_repo: Path,
) -> None:
    """The row must survive `task-land`, which deletes the worktree.

    AC-009 runs from the base, so it cannot tell `resolve_base_root` from a plain
    `Path.cwd()` — and `Path.cwd()` is precisely what `codex_ledger` shipped with, writing
    into a gitignored worktree path that vanished when the task landed. Running the same
    rendered argv from inside the worktree is the only cwd that separates them.
    """
    slug = "demo-task"
    worktree = _add_task_worktree(base_repo, slug)
    line = _bang_line("delegation_ledger", containing="--status unavailable")
    proc = _run(_sub_slug(_argv(line, "delegation_ledger"), slug), cwd=worktree)
    assert proc.returncode == 0, proc.stderr

    assert (base_repo / ".claude" / "observability" / "delegation.jsonl").is_file()
    assert not (worktree / ".claude" / "observability" / "delegation.jsonl").exists()
