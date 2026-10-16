"""SPEC-hm-overhaul-p1 AC-006: `hm check` on the 36 eval-3 hm trees reproduces the golden verdicts.

Each tree is rebuilt from committed bytes only (no network, no env flag):
1. the db19f023 bench fixture `scripts/bench/timeparse` plus the task's seed overlay, committed
   as "fixture" (`scripts/bench_light_lane.build_template` at db19f023);
2. a db19f023 harness render on top, committed as "harness" — pinned against the original
   harness commit through `harness_manifest.json` (normalised: provenance masked);
3. the run's `patch.diff` (its change against HEAD plus untracked, unignored files);
4. a `.venv` made with `python -m venv --system-site-packages`.

`expected.json` holds the verdicts recorded on 2026-10-15 (the AC-006 golden table in
`specs/SPEC-hm-overhaul-p1.machine.yaml`), not this implementation's output.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests._overhaul_p1_ref import HEAD_SRC, REF_SHA, REPO_ROOT, clean_env, normalise, ref_root

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "hm_check_eval3"
RUNS = sorted(p.name for p in FIXTURES.iterdir() if (p / "patch.diff").is_file())
_GIT = ["git", "-c", "user.name=hm-bench", "-c", "user.email=bench@localhost"]
_IGNORED = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
_LOCK = threading.Lock()
_TEMPLATES: dict[tuple[Path, str], Path] = {}


def _git(work: Path, *args: str, ok: tuple[int, ...] = (0,)) -> str:
    proc = subprocess.run(
        [*_GIT, *args], cwd=work, capture_output=True, text=True, timeout=120, check=False
    )
    assert proc.returncode in ok, (args, proc.stderr[-800:])
    return proc.stdout


def _bench(cache: Path) -> Path:
    out = cache / f"bench-{REF_SHA}"
    if not (out / "scripts" / "bench" / "timeparse" / "pyproject.toml").is_file():
        blob = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "archive", "--format=tar", REF_SHA, "scripts/bench"],
            check=True,
            capture_output=True,
            timeout=120,
        ).stdout
        out.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            tar.extractall(out, filter="data")
    return out / "scripts" / "bench"


def _task(run: str) -> str:
    return run.split("-", 1)[0]


_INSTALL_REF = re.compile(r"uv run --with (\S+) hm ")


def _install_ref(work: Path) -> str:
    """The checkout the render was installed from — machine provenance, not harness content."""
    text = subprocess.run(
        ["git", "show", "HEAD:.claude/commands/hm/execute.md"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    found = _INSTALL_REF.search(text)
    assert found, "no install ref in the rendered execute command"
    return found.group(1)


def harness_digest(work: Path) -> dict[str, str]:
    """sha256 of every file the "harness" commit (HEAD) adds or changes, provenance masked."""
    ref = _install_ref(work)
    names = _git(work, "diff", "--name-only", "HEAD~1", "HEAD").split()
    out: dict[str, str] = {}
    for name in names:
        raw = subprocess.run(
            ["git", "show", f"HEAD:{name}"], cwd=work, capture_output=True, timeout=60, check=True
        ).stdout
        try:
            text = normalise(raw.decode("utf-8")).replace(ref, "<REF>")
        except UnicodeDecodeError:
            text = raw.hex()
        out[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return out


def _template(cache: Path, task: str) -> Path:
    """The fixture + harness repo for one task, built once per process and copied per tree."""
    with _LOCK:
        key = (cache, task)
        if key in _TEMPLATES:
            return _TEMPLATES[key]
        bench = _bench(cache)
        dest = cache / f"template-{task}"
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(bench / "timeparse", dest, ignore=_IGNORED)
        seed = bench / "tasks" / task / "seed"
        if seed.is_dir():
            shutil.copytree(seed, dest, dirs_exist_ok=True, ignore=_IGNORED)
        _git(dest, "init", "-q")
        _git(dest, "add", "-A")
        _git(dest, "commit", "-q", "-m", "fixture")
        home = cache / "home"
        home.mkdir(exist_ok=True)
        proc = subprocess.run(
            [sys.executable, "-m", "harness_maker", "make", str(dest), "--autoloop"]
            + ["--preset", "Side", "--targets", "claude-code", "--autonomy-level", "auto_full"],
            cwd=dest,
            env=clean_env(home=home, src=ref_root(cache) / "src"),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr[-2000:]
        _git(dest, "add", "-A")
        _git(dest, "commit", "-q", "-m", "harness")
        _TEMPLATES[key] = dest
        return dest


def _venv(tree: Path) -> None:
    """`--system-site-packages` alone would see the base interpreter, not this suite's venv, so a
    `.pth` adds the running environment's site-packages (where pytest lives)."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "venv",
            "--system-site-packages",
            "--without-pip",
            str(tree / ".venv"),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    code = "import sysconfig; print(sysconfig.get_paths()['purelib'])"
    purelib = subprocess.run(
        [str(tree / ".venv" / "bin" / "python"), "-c", code],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()
    (Path(purelib) / "hm_suite_site.pth").write_text(
        sysconfig.get_paths()["purelib"] + "\n", encoding="utf-8"
    )


def rebuild(cache: Path, tmp: Path, run: str, *, harness_line: str | None = None) -> Path:
    template = _template(cache, _task(run))
    tree = tmp / run
    shutil.copytree(template, tree, symlinks=True)
    if harness_line is not None:
        reviewer = tree / ".claude" / "agents" / "code-reviewer.md"
        reviewer.write_text(reviewer.read_text(encoding="utf-8") + harness_line, encoding="utf-8")
        _git(tree, "commit", "-q", "-am", "harness line")
    _git(tree, "apply", "--binary", "--whitespace=nowarn", str(FIXTURES / run / "patch.diff"))
    _venv(tree)
    return tree


def hm_check(tree: Path, slug: str, home: Path) -> dict[str, Any]:
    home.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.check", "--slug", slug, "--root", str(tree)]
        + ["--offline"],
        cwd=tree,
        env=clean_env(home=home, src=HEAD_SRC),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1, (proc.stdout[-2000:], proc.stderr[-2000:])
    result: dict[str, Any] = json.loads(lines[0])
    assert result["exit"] == proc.returncode
    return result


def project(result: dict[str, Any]) -> dict[str, Any]:
    """The verdicts the golden records, and nothing this implementation adds beside them."""
    sec = result["sections"]
    out: dict[str, Any] = {
        "exit": result["exit"],
        "tree_changed": result["tree_changed"],
        "approval": {"state": sec["approval"]["state"], "ok": sec["approval"]["ok"]},
        "gates": {"ok": sec["gates"]["ok"]},
        "ac": {"ok": sec["ac"]["ok"]},
        "security": {"ok": sec["security"]["ok"], "gating": len(sec["security"]["findings"])},
    }
    if sec["ac"].get("reason") == "skip-path SPEC with a code change":
        out["ac"]["reason"] = sec["ac"]["reason"]
    return out


def _expected(run: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / run / "expected.json").read_text("utf-8"))
    return data


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    path = tmp_path_factory.mktemp("eval3-cache")
    yield path
    with _LOCK:
        for key in [k for k in _TEMPLATES if k[0] == path]:
            del _TEMPLATES[key]
    shutil.rmtree(path, ignore_errors=True)


def _manifest() -> dict[str, str]:
    """One digest for every task: the 36 original harness commits are identical once masked."""
    data: dict[str, str] = json.loads((FIXTURES / "harness_manifest.json").read_text("utf-8"))
    return data


def test_ac006_fixture_set_is_the_36_hm_runs() -> None:
    assert len(RUNS) == 36
    assert {_task(r) for r in RUNS} == {f"t{i}" for i in range(1, 13)}
    assert all(json.loads((FIXTURES / r / "expected.json").read_text("utf-8")) for r in RUNS)


@pytest.mark.parametrize("run", RUNS)
def test_ac006_section_verdicts_match_golden(run: str, cache: Path, tmp_path: Path) -> None:
    tree = rebuild(cache, tmp_path, run)
    try:
        # Precondition: the regenerated harness commit is the run's original one.
        assert harness_digest(tree) == _manifest()
        expected = _expected(run)
        assert project(hm_check(tree, expected["slug"], tmp_path / "home")) == expected["verdicts"]
    finally:
        shutil.rmtree(tree, ignore_errors=True)


CONTROL_RUN = "t1-hm-1"
CONTROL_SRC = "timeparse/format.py"


def _secret_line() -> str:
    return "# " + "AKIA" + "Q" * 16 + "\n"  # built at runtime: the repo must not hold one


def test_ac006_negative_controls(cache: Path, tmp_path: Path) -> None:
    expected = _expected(CONTROL_RUN)
    base = expected["verdicts"]
    slug = expected["slug"]
    home = tmp_path / "home"

    # 1. A secret-shaped line in the change's own source file flips security, and only it.
    tree = rebuild(cache, tmp_path / "secret", CONTROL_RUN)
    try:
        src = tree / CONTROL_SRC
        src.write_text(src.read_text(encoding="utf-8") + _secret_line(), encoding="utf-8")
        got = project(hm_check(tree, slug, home))
        assert got["security"]["ok"] is False
        assert got["security"]["gating"] >= 1
        assert {k: v for k, v in got.items() if k != "security"} == {
            k: v for k, v in base.items() if k != "security"
        }
    finally:
        shutil.rmtree(tree, ignore_errors=True)

    # 2. The same line in a committed, untouched harness file is out of scope.
    tree = rebuild(cache, tmp_path / "harness", CONTROL_RUN, harness_line=_secret_line())
    try:
        result = hm_check(tree, slug, home)
        assert project(result) == base
        assert result["sections"]["security"]["out_of_scope"] >= 1
    finally:
        shutil.rmtree(tree, ignore_errors=True)

    # 3. Reverting the source change while keeping its tests flips gates, and only it.
    tree = rebuild(cache, tmp_path / "revert", CONTROL_RUN)
    try:
        _git(tree, "checkout", "HEAD", "--", CONTROL_SRC)
        got = project(hm_check(tree, slug, home))
        assert got["gates"]["ok"] is False
        assert {k: v for k, v in got.items() if k != "gates"} == {
            k: v for k, v in base.items() if k != "gates"
        }
    finally:
        shutil.rmtree(tree, ignore_errors=True)
