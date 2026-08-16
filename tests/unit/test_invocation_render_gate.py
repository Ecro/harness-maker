"""ADR-002 — producer gate: every executable harness_maker invocation must use the
full self-contained launcher `uv run --with {{ harness_maker_src_path }} python -m
harness_maker…`.

Two broken forms fail on consumer plugin-cache installs: bare `python -m
harness_maker` (no `python` alias / no pip console script) and `uv run python -m
harness_maker` (no `--with` → consumer venv lacks `harness_maker`). The console form
`harness-maker <subcmd>` is the third. This gate renders the whole tree and fails if
ANY executable context (a `!` slash line, a `Bash("…")` call, or a fenced ```bash
block) reintroduces a broken form (Codex HIGH-1, MED-4 + plan-validator W2/W4).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import InterviewAnswers, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_PY_INVOKE = re.compile(r"python -m harness_maker")
# the src_path renders to a slash path with no spaces, so \S+ is safe
_FULL_LAUNCHER = re.compile(r"uv run --with \S+ python -m harness_maker")
# console form: `harness-maker <subcmd>` — the path `harness-maker/harness-maker/…`
# never has a space after `harness-maker`, so a word-boundary subcmd can't false-match
_CONSOLE = re.compile(
    r"\bharness-maker (autopilot|make|on|off|audit|render|loop|health|worktree|drain|prune)\b"
)


def _line_is_broken(line: str) -> bool:
    """Used by the negative-fixture tests: a line carries a broken invocation if it
    uses the console form (flagged anywhere) OR a `python -m harness_maker` that is
    not the full launcher (callers gate this on executable context)."""
    if _CONSOLE.search(line):
        return True
    return bool(_PY_INVOKE.search(line) and not _FULL_LAUNCHER.search(line))


def _executable_broken_lines(text: str) -> list[str]:
    """Return offending lines. The console form (`harness-maker <subcmd>`) is flagged
    ANYWHERE — no template has a legitimate use of it. A bare/`--with`-less `python -m
    harness_maker` is flagged ONLY in an executable context (a `!`-slash line, a
    `Bash("…")` call, or a fenced ```bash block) so explanatory prose ("the contract
    `python -m …` enforces") and doc-table cells are not false-positives."""
    out: list[str] = []
    in_fence = False
    fence_is_bash = False
    in_bash_call = False  # a Bash( … ) whose parens span multiple lines (REVIEW P3)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                fence_is_bash = stripped[3:].strip().lower() in ("bash", "sh", "shell", "")
            else:
                in_fence = False
                fence_is_bash = False
            continue
        # A `#`-comment line is not executable, in any of the asset languages this walks:
        # TOML comments, shell comments inside a bash fence, and markdown headings all start
        # this way and none of them runs. This became load-bearing when the Codex `.toml`
        # tree entered scope — `.codex/agents/*.toml` carry block-marker comments that mention
        # `harness-maker make` in prose, and the old docstring's premise ("no template has a
        # legitimate use of the console form") was only true while those files were invisible.
        if stripped.startswith("#"):
            continue
        if _CONSOLE.search(line):
            out.append(stripped)
            continue
        is_table_row = bool(re.match(r"^\s*\|.*\|\s*$", line))
        bash_open = "Bash(" in line
        is_exec = not is_table_row and (
            (in_fence and fence_is_bash) or stripped.startswith("!") or bash_open or in_bash_call
        )
        # track an unbalanced Bash( … ) so the invocation line of a multi-line Bash call
        # (which alone carries no `Bash(`) is still seen as executable (REVIEW P3, #6b)
        if bash_open and line.count("(") > line.count(")"):
            in_bash_call = True
        elif in_bash_call and line.count(")") > line.count("("):
            in_bash_call = False
        # count-based, NOT boolean: a compound line `… --with X python -m a && python -m b`
        # carries a full launcher AND a trailing bare invocation — flag when the bare
        # `python -m harness_maker` count exceeds the full-launcher count (REVIEW P3, #6a)
        if is_exec and len(_PY_INVOKE.findall(line)) > len(_FULL_LAUNCHER.findall(line)):
            out.append(stripped)
    return out


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("rendered-invocation-gate")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    render(synthesize(p, interview(p, autoloop_mode=True)), out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def test_no_broken_invocation_in_rendered_output(rendered: Path) -> None:
    offenders: dict[str, list[str]] = {}
    for f in rendered.rglob("*.md"):
        bad = _executable_broken_lines(f.read_text(encoding="utf-8"))
        if bad:
            offenders[str(f.relative_to(rendered))] = bad
    assert not offenders, (
        "executable harness_maker invocations must use the full "
        "`uv run --with {{ harness_maker_src_path }} python -m harness_maker` launcher:\n"
        + "\n".join(f"  {k}: {v}" for k, v in offenders.items())
    )


@pytest.fixture(scope="module")
def rendered_cursor_codex(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The migration touched dual-rendered partials, so the gate must also cover the
    Cursor (`.mdc`) and Codex (`.toml`/`.md`) asset trees, not just claude-code `.md`
    (REVIEW P2: code-reviewer + codex)."""
    # `render()`'s target_dir is the `.claude` DIRECTORY; Codex outputs (`.codex/`, `.agents/`,
    # `AGENTS.md`) are written to its PARENT. Passing the scan root itself as target_dir put the
    # entire Codex tree in pytest's basetemp — OUTSIDE the tree this test then walks — so the
    # docstring's claim to cover the Codex asset tree was never true and any broken launcher
    # living only in a Codex body passed. Root the render one level down and walk the parent.
    # (Found by the security lens while reviewing PLAN-codex-lens-dispatch, which fixes the
    # identical mistake two files over.)
    out = tmp_path_factory.mktemp("rendered-invocation-gate-multi")
    blueprint = synthesize(
        ProjectProfile(stack=["python"]),
        InterviewAnswers(targets=[Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]),
    )
    render(blueprint, out / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return out


def test_no_broken_invocation_in_cursor_codex_targets(rendered_cursor_codex: Path) -> None:
    offenders: dict[str, list[str]] = {}
    scanned: list[str] = []
    for pattern in ("*.md", "*.mdc", "*.toml"):
        for f in rendered_cursor_codex.rglob(pattern):
            rel = str(f.relative_to(rendered_cursor_codex))
            scanned.append(rel)
            bad = _executable_broken_lines(f.read_text(encoding="utf-8"))
            if bad:
                offenders[rel] = bad
    # NON-EMPTY PRECONDITION. Until 2026-08-17 this fixture rendered the Codex tree to
    # `target_dir.parent` — outside the directory it then walked — so it scanned ZERO Codex
    # files while its docstring claimed to cover them, and reported clean for years. Asserting
    # the surface exists is what makes the re-rooting durable: without it the same mistake
    # reads as a pass again. `not offenders` alone is also true of nothing at all.
    codex_seen = [p for p in scanned if p.startswith((".codex/", ".agents/")) or p == "AGENTS.md"]
    assert codex_seen, (
        "no Codex-destined asset was scanned — this gate is vacuous. Either the render root "
        "moved back above the walked tree, or the `targets` axis stopped producing them."
    )
    assert not offenders, (
        "broken executable harness_maker invocations in cursor/codex assets:\n"
        + "\n".join(f"  {k}: {v}" for k, v in offenders.items())
    )


# --- negative fixtures: the gate MUST trip on each broken form (W2/W4) ---


@pytest.mark.parametrize(
    "fixture",
    [
        "!python -m harness_maker.autopilot_caps boundary --root .",  # bare
        "!uv run python -m harness_maker.memory_retrieve --topic x",  # --with-less
        "```bash\npython -m harness_maker.codex_adapter adapt\n```",  # fenced bash
        # multi-line continuation inside a fence
        "```bash\nuv run python -m harness_maker.spec_machine mark-tested \\\n  --yaml x\n```",
        "> `harness-maker autopilot on --level auto_safe`",  # console form
        # compound line: a valid launcher MASKING a trailing bare invocation (#6a)
        "!uv run --with /c python -m harness_maker.a && python -m harness_maker.b",
        # multi-line Bash(...) — invocation line alone carries no `Bash(` (#6b)
        'Bash(\n    "python -m harness_maker.codex_adapter adapt"\n)',
    ],
)
def test_gate_trips_on_broken_fixture(fixture: str) -> None:
    # console form is detected even outside a fence (it appears in `>`-blockquote
    # picker instructions), so check the predicate directly for that one.
    if "harness-maker autopilot" in fixture:
        assert _line_is_broken(fixture)
    else:
        assert _executable_broken_lines(fixture), f"gate failed to trip on: {fixture!r}"


def test_gate_passes_canonical_and_prose() -> None:
    good = (
        "!uv run --with /cache/0.33.0 python -m harness_maker.autopilot_caps boundary\n"
        "the contract `python -m harness_maker.spec_machine validate` enforces\n"
        "| a. schema | `python -m harness_maker.spec_machine validate {y}` | exit 0 |\n"
    )
    assert not _executable_broken_lines(good)


# --- source-grep: runtime remediation strings must not prescribe the bare console form (W3) ---


@pytest.mark.parametrize("module", ["autopilot_caps.py"])
def test_no_bare_console_remediation_in_runtime_source(module: str) -> None:
    src = Path(__file__).parents[2] / "src" / "harness_maker" / module
    text = src.read_text(encoding="utf-8")
    assert not _CONSOLE.search(text), (
        f"{module}: a user-facing runtime string prescribes the bare `harness-maker "
        f"<subcmd>` form, which fails on consumer plugin-cache installs (W3)"
    )
