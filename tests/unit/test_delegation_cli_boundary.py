"""The two delegation CLIs as the rendered command actually invokes them.

`test_wrapup_brief.py` and `test_wrapup_receipt.py` between them hold 68 tests and
neither one calls `main()`. That gap is this project's most-repeated defect shape —
"unit boundary green, shipped entry point wrong" — and it has now produced at least
six instances, including a P0 where `run_classify.main` forgot to `.resolve()` its
`--root` and reported zero boundaries while the library layer reported 392.

The delegation path is unusually exposed to it, because the rendered wrapup command
does something no unit test does: it derives the brief **inside the task worktree**,
then reconciles the receipt **from the base repo**, passing the worktree back across
that boundary as `--worktree '<brief.worktree_root>'`. Every test that calls
`reconcile()` directly supplies that argument from a Python variable, so a defect in
how the CLI parses, resolves, or confines it is invisible to all of them.

These tests drive `main(argv)` and nothing else.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from harness_maker import wrapup_brief, wrapup_receipt


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=60
    ).stdout


@pytest.fixture
def task_repo(tmp_path: Path) -> tuple[Path, Path]:
    """(base, worktree) — a repo with one task worktree on `hm/<slug>`."""
    base = tmp_path / "repo"
    base.mkdir()
    _git(["init", "-b", "main"], base)
    _git(["config", "user.email", "t@e.com"], base)
    _git(["config", "user.name", "T"], base)
    (base / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (base / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "."], base)
    _git(["commit", "-m", "init"], base)

    wt = base / ".worktrees" / "demo"
    _git(["worktree", "add", "-b", "hm/demo", str(wt)], base)
    (wt / "work-docs").mkdir(parents=True)
    (wt / "work-docs/PLAN-demo.md").write_text("# plan\n", encoding="utf-8")
    (wt / "src.py").write_text("print(1)\n", encoding="utf-8")
    return base, wt


def _run(
    mod: object, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    rc = mod.main(argv)  # type: ignore[attr-defined]
    return rc, json.loads(capsys.readouterr().out)


def test_brief_cli_emits_an_absolute_worktree_root(
    task_repo: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`worktree_root` is substituted into a shell line that runs somewhere ELSE.

    The reconciler resolves `--worktree` against the BASE repo's cwd, so a relative
    value here would silently resolve to the wrong directory and every truthful run
    would report `document-missing`. Driving the CLI with a relative `--root` is the
    only way to see it: `derive_brief` is always called with an absolute path in the
    existing tests.
    """
    _base, wt = task_repo
    monkeypatch.chdir(wt)

    rc, payload = _run(wrapup_brief, ["--root", "."], capsys)

    assert rc == 0
    assert payload["status"] == "ok", payload["verdict"]
    brief = payload["brief"]
    assert isinstance(brief, dict)
    root = brief["worktree_root"]
    assert Path(root).is_absolute(), f"relative worktree_root {root!r} breaks the reconciler"
    assert Path(root).resolve() == wt.resolve()


def test_brief_cli_never_exits_non_zero_off_a_task_branch(
    task_repo: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-006's degraded path is a supported outcome, not a halt — asserted at the
    exit code, which is what the rendered `!` line reacts to."""
    base, _wt = task_repo
    monkeypatch.chdir(base)

    rc, payload = _run(wrapup_brief, ["--root", "."], capsys)

    assert rc == 0
    assert payload["status"] == "degraded"
    assert payload["brief"] is None


def _receipt(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": wrapup_receipt.SCHEMA_VERSION,
        "stage": "wrapup",
    }
    body.update(overrides)
    return body


def test_reconcile_cli_resolves_worktree_from_the_base_cwd(
    task_repo: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real invocation: cwd is the BASE, the claim is a path in the WORKTREE.

    Omitting `--worktree` was shipped once and made every honest receipt report
    `document-missing`; passing it is what the rendered command does, so that is what
    is asserted here — from the base cwd, exactly as the `!` line runs.

    The path passed is ABSOLUTE, because that is the contract: `worktree_root` comes
    out of the brief already resolved (pinned by
    `test_brief_cli_emits_an_absolute_worktree_root`). This test therefore covers the
    cross-directory HAND-OFF, not relative-path resolution — the discriminating half
    is the companion test below, which drops the flag and must fail.
    """
    base, wt = task_repo
    monkeypatch.chdir(base)
    receipt = base / "r.json"
    receipt.write_text(
        json.dumps(_receipt(documents_updated=["work-docs/PLAN-demo.md"])), encoding="utf-8"
    )

    rc, payload = _run(
        wrapup_receipt,
        ["--root", ".", "--stage", "wrapup", "--worktree", str(wt), "--receipt-file", str(receipt)],
        capsys,
    )

    assert rc == 0, payload
    assert payload["status"] == "ok"


def test_reconcile_cli_without_worktree_cannot_see_the_delegates_files(
    task_repo: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the failure the `--worktree is not optional` note warns about.

    Without this, a future edit could drop the flag from the template and every test
    would still pass — the reconciler would simply start vouching for nothing.
    """
    base, _wt = task_repo
    monkeypatch.chdir(base)
    receipt = base / "r.json"
    receipt.write_text(
        json.dumps(_receipt(documents_updated=["work-docs/PLAN-demo.md"])), encoding="utf-8"
    )

    rc, payload = _run(
        wrapup_receipt,
        ["--root", ".", "--stage", "wrapup", "--receipt-file", str(receipt)],
        capsys,
    )

    assert rc == 1
    assert payload["status"] == "mismatch"


def test_reconcile_cli_rejects_a_worktree_outside_the_base(
    task_repo: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--worktree` is model-substituted text, so it is an untrusted confinement root.

    `--worktree /` would let `documents_updated: ["etc/hostname"]` resolve a real file
    and reconcile clean. The guard lives in `main`, so only a CLI-level test sees it.

    Assert the exact exit code and message, not `rc != 0`. With the guard deleted the
    run returns 1/`mismatch` on any host where `/etc/hostname` is absent (macOS), so a
    relation assertion passes in the world the guard does not exist in — and `rc != 0`
    cannot separate "guard fired" from "the claimed document was simply missing".
    """
    base, _wt = task_repo
    monkeypatch.chdir(base)
    receipt = base / "r.json"
    receipt.write_text(json.dumps(_receipt(documents_updated=["etc/hostname"])), encoding="utf-8")

    rc, payload = _run(
        wrapup_receipt,
        ["--root", ".", "--stage", "wrapup", "--worktree", "/", "--receipt-file", str(receipt)],
        capsys,
    )

    assert rc == 2, payload
    assert payload["status"] == "unparseable"
    assert "neither the base repo" in str(payload["error"])


def test_reconcile_cli_flags_a_stage_mismatch(
    task_repo: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verify receipt must not be accepted as a wrapup one — the two stages have
    different `--stage` values in their rendered lines and nothing else separates them."""
    base, wt = task_repo
    monkeypatch.chdir(base)
    receipt = base / "r.json"
    receipt.write_text(json.dumps(_receipt(stage="verify")), encoding="utf-8")

    rc, payload = _run(
        wrapup_receipt,
        ["--root", ".", "--stage", "wrapup", "--worktree", str(wt), "--receipt-file", str(receipt)],
        capsys,
    )

    assert rc == 1
    assert payload["status"] == "mismatch"


def test_reconcile_cli_exits_2_on_an_unreadable_receipt(
    task_repo: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit 2 is what routes the stage to its inline body; exit 1 would instead tell
    the main loop to go fix mismatches that do not exist."""
    base, wt = task_repo
    monkeypatch.chdir(base)

    rc, payload = _run(
        wrapup_receipt,
        [
            "--root",
            ".",
            "--stage",
            "wrapup",
            "--worktree",
            str(wt),
            "--receipt-file",
            str(base / "absent.json"),
        ],
        capsys,
    )

    assert rc == 2
    assert payload["status"] == "unparseable"


def _rendered_reconcile_line() -> str:
    """The `wrapup_receipt` invocation exactly as the wrapup command ships it."""
    import tempfile

    from harness_maker.models import DelegationConfig, InterviewAnswers, Preset, ProjectProfile
    from harness_maker.models import Target as _Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    out = Path(tempfile.mkdtemp())
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(
                preset=Preset.PRODUCTION,
                targets=[_Target.CLAUDE_CODE],
                worktree={"feature_branch_workflow": True},
                delegation=DelegationConfig(stages=["wrapup"]),
            ),
        ),
        out,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    body = (out / "commands" / "hm" / "wrapup.md").read_text(encoding="utf-8")
    lines = [ln for ln in body.splitlines() if "hm wrapup_receipt" in ln]
    assert len(lines) == 1, f"expected exactly one reconcile invocation, got {lines}"
    return lines[0]


def test_every_flag_the_template_passes_is_one_the_cli_accepts(
    task_repo: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Close the seam between the two halves that are each already tested.

    `test_render_wrapup_delegation` greps the rendered line for literal flag text, and
    the tests above drive `main(argv)` with hand-written literals. Neither notices
    DRIFT: rename a flag in the parser, or add one to the template, and both stay green
    while the shipped `!` line dies at argparse with exit 2 — which the stage reads as
    "unparseable receipt" and silently routes to the inline body.

    So extract the flags from the RENDERED line and feed exactly those to the parser.

    Known blind spot, found while mutation-checking this test: argparse accepts
    unambiguous prefixes, so renaming `--stage` to `--stage-name` keeps the rendered
    line working and this test green. It catches renames that are not prefixes
    (`--stage` → `--phase` kills it) and flags added on either side. Stated rather than
    papered over — a gate whose limits are undocumented reads as covering more than it
    does, which is the failure this whole module exists to answer.
    """
    base, wt = task_repo
    monkeypatch.chdir(base)
    receipt = base / "r.json"
    receipt.write_text(json.dumps(_receipt()), encoding="utf-8")

    # Scope to the text AFTER the module name: everything before it belongs to `uv`
    # (`uv run --with <path> python -m …`), and its flags are not this parser's.
    line = _rendered_reconcile_line()
    _, sep, tail = line.partition(" hm wrapup_receipt")
    assert sep, f"reconcile line does not invoke the module by name: {line}"
    flags = re.findall(r"(?<!\w)--[a-z][a-z-]*", tail)
    assert flags, f"no flags found after the module name in: {line}"

    values = {
        "--root": ".",
        "--stage": "wrapup",
        "--worktree": str(wt),
        "--receipt-file": str(receipt),
        "--vault": str(base / "vault"),
    }
    unknown = [f for f in flags if f not in values]
    assert not unknown, (
        f"the rendered command passes {unknown}, which this test does not know how to "
        "supply — either the CLI gained a flag or the template did; reconcile them"
    )

    argv: list[str] = []
    for f in flags:
        argv += [f, values[f]]

    # argparse exits 2 via SystemExit on an unknown flag; any normal verdict is fine.
    rc = wrapup_receipt.main(argv)
    capsys.readouterr()
    assert rc in (0, 1, 2), rc
