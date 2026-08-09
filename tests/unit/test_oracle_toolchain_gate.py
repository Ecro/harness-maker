"""Phase 2 of PLAN-second-opinion-oracle-polyglot — the extension gate and config dispatch.

Every assertion here is on an OBSERVABLE at the subprocess boundary — recorded argv, cwd, and
call count — not on a prose summary. Call-count is the only thing that proves ADR-001's "runs
nothing"; exact-argv is the only thing that proves ADR-004's sanitise-then-substitute ordering.

AC-002 is differential against an IMMUTABLE blob, never `HEAD~`: a moving ref points at the
pre-change module only until the next commit, after which the test compares the new `gather()`
against itself and passes vacuously forever — silently, on the one assertion protecting every
shipped Python harness.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from harness_maker import second_opinion_oracle as soo

# Pinned before Phase 2 touched the module. `git cat-file -p <sha>` resolves it forever.
BASELINE_BLOB = "d7b4ded0e067c904dde7a468be7516b1b321b029"

_PY_TC = {
    "name": "python",
    "extensions": [".py", ".pyi"],
    "commands": {
        "test": "uv run pytest -q {path}",
        "lint": "uv run ruff check {path}",
        "types": "uv run mypy {path}",
    },
}
_NODE_TC = {
    "name": "node",
    "extensions": [".ts", ".tsx"],
    "commands": {"test": "npx --no-install vitest run {path}", "types": "npx --no-install tsc"},
}


class _Recorder:
    """Captures every subprocess invocation instead of running it."""

    def __init__(self, returncode: int = 0, stdout: str = "ok") -> None:
        self.calls: list[dict[str, Any]] = []
        self._rc = returncode
        self._stdout = stdout

    def __call__(self, cmd: Any, **kw: Any) -> Any:
        self.calls.append({"cmd": list(cmd), "cwd": kw.get("cwd"), "shell": kw.get("shell", False)})
        return subprocess.CompletedProcess(cmd, self._rc, self._stdout, "")

    @property
    def argvs(self) -> list[list[str]]:
        return [c["cmd"] for c in self.calls]


@pytest.fixture
def rec(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    r = _Recorder()
    # NOTE: `soo.subprocess` IS the global subprocess module, so this patch is process-wide —
    # it would also intercept `resolve_base_root`'s git shell-out and make it return "ok" as
    # the repo root. Every test that uses this fixture therefore pins `_resolve_config_root`
    # explicitly rather than letting it resolve through the patched boundary.
    monkeypatch.setattr(soo.subprocess, "run", r)
    return r


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A root whose changed-file set and toolchains are both controllable.

    `_CHANGED` is reset here on purpose. It is module-level mutable state, so without this a
    test that forgets `_set_changed` inherits its predecessor's fixture and still passes —
    and `test_uncovered_extension_spawns_no_subprocess` asserts `rec.calls == []`, which is
    precisely the assertion that would pass vacuously on a stale empty changed-set.
    """
    _CHANGED[0] = set()
    monkeypatch.setattr(soo, "_changed_files", lambda _root: _CHANGED[0])
    return tmp_path


_CHANGED: list[set[str]] = [set()]


def _set_changed(*paths: str) -> None:
    _CHANGED[0] = set(paths)


def _with_toolchains(monkeypatch: pytest.MonkeyPatch, *entries: dict[str, Any]) -> None:
    from harness_maker.models import ToolchainConfig

    parsed = [ToolchainConfig.model_validate(e) for e in entries]
    monkeypatch.setattr(soo, "_load_toolchains", lambda _root: parsed)


def _finding(fid: str, path: str) -> dict[str, Any]:
    return {"id": fid, "file": path, "severity": "P1", "message": "x"}


# --- AC-001 / AC-005: the extension gate ------------------------------------------------


@pytest.mark.parametrize("path", ["src/App.tsx", "README.md", "Makefile", "src/lib.rs"])
def test_uncovered_extension_spawns_no_subprocess(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """ADR-001: zero subprocesses, and the finding is named in the no-oracle tail."""
    _set_changed(path)
    _with_toolchains(monkeypatch, _PY_TC)
    out = soo.gather([_finding("f-1", path)], repo)

    assert rec.calls == [], f"{path}: ran {len(rec.calls)} subprocess(es) for an uncovered path"
    assert "f-1" in out
    assert "no oracle" in out.lower()
    assert "### oracle for id(s)=f-1" not in out


@pytest.mark.parametrize(
    ("path", "covered"),
    [("src/mod.py", True), ("src/mod.pyi", True), ("src/App.tsx", False), ("README.md", False)],
)
def test_absent_key_defaults_by_extension(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch, path: str, covered: bool
) -> None:
    """ADR-006: no `toolchains` key → .py/.pyi keep the historical triple, everything else
    gets no oracle. This is what makes the change a no-op for every shipped harness."""
    _set_changed(path)
    monkeypatch.setattr(soo, "_load_toolchains", lambda _root: [])
    soo.gather([_finding("f-1", path)], repo)

    if covered:
        assert [a[:3] for a in rec.argvs] == [
            ["uv", "run", "pytest"],
            ["uv", "run", "ruff"],
            ["uv", "run", "mypy"],
        ]
    else:
        assert rec.calls == []


# --- AC-003 / AC-004: config-driven dispatch and the {path} contract ---------------------


def test_declared_commands_are_the_only_commands_run(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_changed("src/App.tsx")
    _with_toolchains(monkeypatch, _NODE_TC)
    soo.gather([_finding("f-1", "src/App.tsx")], repo)

    assert rec.argvs == [
        ["npx", "--no-install", "vitest", "run", "src/App.tsx"],
        ["npx", "--no-install", "tsc"],
    ]
    assert not any("pytest" in a or "mypy" in a for a in rec.argvs)


def test_path_placeholder_decides_per_path_vs_repo_wide(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `{path}` command runs once per path; a bare one runs exactly once per gather()."""
    _set_changed("a.ts", "b.ts")
    _with_toolchains(monkeypatch, _NODE_TC)
    soo.gather([_finding("f-1", "a.ts"), _finding("f-2", "b.ts")], repo)

    per_path = [a for a in rec.argvs if "vitest" in a]
    repo_wide = [a for a in rec.argvs if a[-1] == "tsc"]
    assert sorted(a[-1] for a in per_path) == ["a.ts", "b.ts"]
    assert len(repo_wide) == 1, f"repo-wide command ran {len(repo_wide)} times, must be exactly 1"


def test_repo_wide_block_carries_no_finding_id(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-008/AC-010: a repo-wide failure is not evidence for any individual finding.
    Unlabelled is how the EXISTING consumer rule neutralises it — no rubric change needed."""
    _set_changed("a.ts")
    _with_toolchains(monkeypatch, _NODE_TC)
    out = soo.gather([_finding("f-1", "a.ts")], repo)

    tsc_block = [b for b in out.split("###") if "tsc" in b]
    assert tsc_block, "repo-wide block missing"
    assert "f-1" not in tsc_block[0], "repo-wide block was labelled with a finding id"
    assert "project-wide" in tsc_block[0].lower()


# --- AC-009: no (template, path) pair crosses toolchain groups ---------------------------


def test_path_receives_only_its_own_toolchain_commands(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The P0 both second-opinion models found in the flat design. A single-language repo
    never reveals it, so the fixture must be mixed."""
    _set_changed("src/mod.py", "src/App.tsx")
    _with_toolchains(monkeypatch, _PY_TC, _NODE_TC)
    soo.gather([_finding("f-1", "src/mod.py"), _finding("f-2", "src/App.tsx")], repo)

    for argv in rec.argvs:
        tail = argv[-1]
        if tail.endswith(".py"):
            assert "npx" not in argv, f"node command ran on a .py path: {argv}"
        if tail.endswith(".tsx"):
            assert "uv" not in argv, f"python command ran on a .tsx path: {argv}"


# --- AC-006: sanitisation precedes substitution ------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "--basetemp=/tmp/x",
        "/etc/passwd",
        "../../secret.py",
        "a;rm -rf b.py",
        "not-in-diff.py",
    ],
)
def test_unsafe_file_value_never_reaches_argv(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    _set_changed("src/mod.py")
    _with_toolchains(monkeypatch, _PY_TC)
    soo.gather([_finding("f-1", bad)], repo)
    for argv in rec.argvs:
        assert bad not in argv, f"tainted value reached argv: {argv}"


def test_recorded_cwd_is_the_worktree_root(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-005: config comes from the base root, but the CHECKS run in the worktree.
    Running them at base would check unmodified files — a clean-looking run."""
    _set_changed("src/mod.py")
    _with_toolchains(monkeypatch, _PY_TC)
    soo.gather([_finding("f-1", "src/mod.py")], repo)
    assert rec.calls
    for call in rec.calls:
        assert call["cwd"] == str(repo)
        assert call["shell"] is False


def test_space_containing_path_stays_one_argv_element(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_UNSAFE_CHARS` does not reject a space, so substituting into the raw string before
    tokenising would split one path into two arguments."""
    _set_changed("src/my file.py")
    _with_toolchains(monkeypatch, _PY_TC)
    soo.gather([_finding("f-1", "src/my file.py")], repo)
    assert rec.calls
    for argv in rec.argvs:
        assert "src/my file.py" in argv


def test_repeated_and_embedded_placeholders_substitute_without_resplit(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_changed("a.py")
    tc = {
        "name": "python",
        "extensions": [".py"],
        "commands": {"test": "pytest --file={path} --snap={path}.snap {path}"},
    }
    _with_toolchains(monkeypatch, tc)
    soo.gather([_finding("f-1", "a.py")], repo)
    assert rec.argvs == [["pytest", "--file=a.py", "--snap=a.py.snap", "a.py"]]


# --- AC-011 / AC-012: visibility and degradation -----------------------------------------


def test_zero_labelled_block_emits_exactly_one_stderr_warning(
    repo: Path,
    rec: _Recorder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_changed("src/App.tsx")
    _with_toolchains(monkeypatch, _PY_TC)
    soo.gather([_finding("f-1", "src/App.tsx")], repo)
    lines = [ln for ln in capsys.readouterr().err.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected exactly one warning line, got {lines}"
    assert "oracle" in lines[0].lower()


def test_all_repo_wide_config_still_warns(
    repo: Path,
    rec: _Recorder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The seeded-Rust shape: coverage is non-zero and the command set is non-empty, yet
    every block is unlabelled. A config-shaped trigger misses this entirely."""
    _set_changed("src/lib.rs")
    rust = {"name": "rust", "extensions": [".rs"], "commands": {"test": "cargo test"}}
    _with_toolchains(monkeypatch, rust)
    soo.gather([_finding("f-1", "src/lib.rs")], repo)
    lines = [ln for ln in capsys.readouterr().err.splitlines() if ln.strip()]
    assert len(lines) == 1, f"all-repo-wide run must warn exactly once, got {lines}"


def test_full_coverage_emits_no_warning(
    repo: Path,
    rec: _Recorder,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_changed("src/mod.py")
    _with_toolchains(monkeypatch, _PY_TC)
    soo.gather([_finding("f-1", "src/mod.py")], repo)
    assert capsys.readouterr().err.strip() == ""


@pytest.mark.parametrize(
    "broken",
    [
        "toolchains: not-a-list",
        "toolchains:\n  - name: x\n    extensions: [.py]\n    commands: {}\n",
        "toolchains:\n  - name: x\n    extensions: []\n    commands: {test: 't {path}'}\n",
        "toolchains:\n  - name: a\n    extensions: ['.py']\n    commands: {test: 'a {path}'}\n"
        "  - name: b\n    extensions: ['.py']\n    commands: {test: 'b {path}'}\n",
        "toolchains:\n  - 42\n",
        "toolchains: [\n",  # unparseable YAML
    ],
)
def test_malformed_toolchains_degrades_without_raising(
    tmp_path: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    """AC-012. `main()` guards only the findings-file parse, so the guard must live in
    `gather()` — and cover any exception TYPE, not just ValidationError."""
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text(
        "---\ngenerated_by: harness-maker\n---\npreset: Side\n" + broken, encoding="utf-8"
    )
    monkeypatch.setattr(soo, "_changed_files", lambda _root: {"src/mod.py"})
    monkeypatch.setattr(soo, "_resolve_config_root", lambda _root: tmp_path)

    out = soo.gather([_finding("f-1", "src/mod.py")], tmp_path)
    assert isinstance(out, str)
    assert "### oracle for id(s)=f-1" not in out


def test_base_root_resolution_failure_degrades(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_p: Path) -> Path:
        raise OSError("git is gone")

    monkeypatch.setattr(soo, "_resolve_config_root", _boom)
    monkeypatch.setattr(soo, "_changed_files", lambda _root: {"src/mod.py"})
    out = soo.gather([_finding("f-1", "src/mod.py")], repo)
    assert isinstance(out, str)


# --- the REAL loader: absent-key is the widest-blast-radius branch --------------------------


@pytest.mark.parametrize("yaml_body", [None, "preset: Side\n", "preset: Side\ntoolchains: []\n"])
def test_real_loader_maps_absent_key_to_empty_list(
    tmp_path: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch, yaml_body: str | None
) -> None:
    """Every other test patches `_load_toolchains`, so the `[]`-on-absent branch — the one
    that makes "no shipped harness is affected" true — had no coverage at all. If either
    early return regressed to `None`, the entire installed base would lose its oracle and the
    suite would stay green, because the assertions that would notice are all downstream of a
    monkeypatch hardcoding the correct answer.
    """
    if yaml_body is not None:
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "harness.yaml").write_text(
            "---\ngenerated_by: harness-maker\n---\n" + yaml_body, encoding="utf-8"
        )
    monkeypatch.setattr(soo, "_changed_files", lambda _root: {"src/mod.py"})
    monkeypatch.setattr(soo, "_resolve_config_root", lambda _root: tmp_path)

    assert soo._load_toolchains(tmp_path) == [], "absent/empty key must be [], never None"
    soo.gather([_finding("f-1", "src/mod.py")], tmp_path)
    assert [a[:3] for a in rec.argvs] == [
        ["uv", "run", "pytest"],
        ["uv", "run", "ruff"],
        ["uv", "run", "mypy"],
    ]


# --- runner allowlist: argv[0] is config-derived now ----------------------------------------


@pytest.mark.parametrize("prog", ["curl", "sh", "bash", "/bin/sh", "rm", "nc"])
def test_disallowed_runner_never_executes(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch, prog: str
) -> None:
    """`argv[0]` used to be one of three hardcoded literals; it now comes from a file that is
    an explicitly permitted write target, behind a pre-approved Bash prefix rule. Without the
    allowlist a single config write is unprompted arbitrary execution — no `shell=True`
    needed, because argv[0] IS the program."""
    _set_changed("a.py")
    _with_toolchains(
        monkeypatch,
        {"name": "x", "extensions": [".py"], "commands": {"test": f"{prog} {{path}}"}},
    )
    out = soo.gather([_finding("f-1", "a.py")], repo)
    assert rec.calls == [], f"{prog} was executed"
    assert "unrunnable command template" in out, "the skip must be visible, not silent"


def test_unrunnable_template_is_reported_not_dropped(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A silently dropped role is the worst outcome: a sibling role succeeds, the block looks
    healthy, `labelled` stays non-zero so the coverage warning never fires, and a configured
    check simply never ran."""
    _set_changed("a.py")
    _with_toolchains(
        monkeypatch,
        {
            "name": "x",
            "extensions": [".py"],
            "commands": {"test": 'uv run pytest "{path}', "lint": "uv run ruff check {path}"},
        },
    )
    out = soo.gather([_finding("f-1", "a.py")], repo)
    assert len(rec.calls) == 1, "the well-formed sibling role should still run"
    assert "NOT RUN" in out
    assert "unrunnable command template" in out


# --- budget: the stated total must actually hold --------------------------------------------


def test_long_no_oracle_tail_cannot_exceed_the_total_budget(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`room` was floored at 800 while the tail grew one entry per uncovered finding, so the
    return could be 800 + an arbitrarily long tail — the comment claiming "≤ BUDGET_TOTAL is
    actually true of the output" was false for exactly the inputs that matter."""
    _set_changed(*[f"f{i}.tsx" for i in range(200)])
    _with_toolchains(monkeypatch, _PY_TC)
    out = soo.gather([_finding(f"f-{i}", f"f{i}.tsx") for i in range(200)], repo)
    assert len(out) <= soo.BUDGET_TOTAL, f"output was {len(out)} chars, budget {soo.BUDGET_TOTAL}"


def test_repo_wide_commands_are_charged_against_the_budget(
    repo: Path, rec: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """They used to run after the per-path `break`, so a budget-exhausted run still spawned a
    300 s subprocess per repo-wide template whose output was then discarded."""
    _set_changed(*[f"f{i}.ts" for i in range(80)])
    big = _Recorder(stdout="x" * 4000)
    monkeypatch.setattr(soo.subprocess, "run", big)
    _with_toolchains(monkeypatch, _NODE_TC)
    soo.gather([_finding(f"f-{i}", f"f{i}.ts") for i in range(80)], repo)
    assert not any(a[-1] == "tsc" for a in big.argvs), (
        "repo-wide command ran after the budget was exhausted"
    )


# --- AC-002: differential against the pinned baseline -------------------------------------


def _load_baseline_module(root: Path) -> types.ModuleType:
    proc = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-p", BASELINE_BLOB],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"baseline blob {BASELINE_BLOB} does not resolve ({proc.stderr.strip()}). "
            "This is a HARD failure, not a skip: a vacuous AC-002 is exactly the silent "
            "degradation it exists to prevent."
        )
    spec = importlib.util.spec_from_loader("_soo_baseline", loader=None)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_soo_baseline"] = mod
    exec(compile(proc.stdout, "<baseline>", "exec"), mod.__dict__)  # noqa: S102
    return mod


def test_python_path_output_unchanged_from_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No behaviour change for any harness with no `toolchains` key on a .py path."""
    root = Path(__file__).parents[2]
    baseline = _load_baseline_module(root)

    findings = [_finding("f-1", "src/mod.py")]
    changed = {"src/mod.py"}

    def _run(cmd: Any, **kw: Any) -> Any:
        return subprocess.CompletedProcess(cmd, 0, f"out for {' '.join(cmd[:3])}", "")

    monkeypatch.setattr(baseline.subprocess, "run", _run)
    monkeypatch.setattr(baseline, "_changed_files", lambda _r: changed)
    expected = baseline.gather(findings, tmp_path)

    monkeypatch.setattr(soo.subprocess, "run", _run)
    monkeypatch.setattr(soo, "_changed_files", lambda _r: changed)
    monkeypatch.setattr(soo, "_load_toolchains", lambda _r: [])
    actual = soo.gather(findings, tmp_path)

    assert actual == expected
