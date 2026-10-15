"""SPEC-bench-cli-provenance: the hm arm runs the CLI the checkout holds, or the bench refuses."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "bench_light_lane.py"


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_light_lane", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module
    spec.loader.exec_module(module)
    return module


def _package(root: Path, files: dict[str, str]) -> Path:
    pkg = root / "src" / "harness_maker"
    for rel, text in files.items():
        (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
        (pkg / rel).write_text(text)
    return pkg


def _template(tmp_path: Path, src_root: Path) -> Path:
    template = tmp_path / "template"
    command = template / ".claude" / "commands" / "hm" / "spec.md"
    command.parent.mkdir(parents=True)
    command.write_text(f"!uv run --with {src_root} hm spec_machine approve --yaml x\n")
    return template


_FILES = {"__init__.py": "", "cli.py": "X = 1\n", "templates/stages/spec.md.j2": "body\n"}


# --- AC-001 -----------------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not on PATH")
def test_cache_keys_rebuild_a_with_install_after_a_source_edit(tmp_path: Path) -> None:
    copy = tmp_path / "checkout"
    copy.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        if (_ROOT / name).exists():
            shutil.copy2(_ROOT / name, copy / name)
    shutil.copytree(
        _ROOT / "src", copy / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    probe = (
        "import harness_maker, harness_maker.spec_machine as s, pathlib; "
        "t = pathlib.Path(harness_maker.__file__).parent / 'templates/stages/spec.md.j2'; "
        "print(getattr(s, 'PROBE_MARKER', 'absent'), t.read_text().endswith('# probe\\n'))"
    )

    def run() -> subprocess.CompletedProcess[str]:
        argv = ["uv", "run", "--no-project", "--with", str(copy), "python", "-c", probe]
        return subprocess.run(argv, cwd=tmp_path, capture_output=True, text=True, timeout=600)

    first = run()
    if first.returncode != 0:  # the first build resolves dependencies from the index
        pytest.skip(f"uv could not build the copy (offline?): {first.stderr.strip()[-200:]}")
    assert first.stdout.strip().splitlines()[-1] == "absent False"
    with (copy / "src" / "harness_maker" / "spec_machine.py").open("a") as handle:
        handle.write('\nPROBE_MARKER = "edited"\n')
    with (copy / "src" / "harness_maker" / "templates" / "stages" / "spec.md.j2").open("a") as h:
        h.write("# probe\n")
    second = run()
    assert second.returncode == 0, second.stderr
    probe_after_edit, template_edited = second.stdout.strip().splitlines()[-1].split()
    assert probe_after_edit == "edited"
    assert template_edited == "True"


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not on PATH")
def test_a_real_uv_install_digests_like_its_source(bench: ModuleType, tmp_path: Path) -> None:
    try:
        installed = bench._installed_package_dir(str(_ROOT), tmp_path, bench.agent_env())
    except bench.CliProvenanceError as exc:
        pytest.skip(f"uv could not build the checkout (offline?): {exc}")
    assert bench.package_digest(installed) == bench.package_digest(_ROOT / "src" / "harness_maker")


# --- AC-002 -----------------------------------------------------------------------------------


def test_check_refuses_a_stale_install(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src_root = tmp_path / "checkout"
    _package(src_root, _FILES)
    stale = _package(tmp_path / "cache", {**_FILES, "cli.py": "X = 0\n"})
    template = _template(tmp_path, src_root)
    seen: list[tuple[str, Path]] = []

    def fake(src: str, cwd: Path, env: dict[str, str]) -> Path:
        seen.append((src, cwd))
        assert env == bench.agent_env()
        return stale

    monkeypatch.setattr(bench, "_installed_package_dir", fake)
    with pytest.raises(bench.CliProvenanceError) as caught:
        bench.check_cli_fresh(template)
    assert seen == [(str(src_root), template)]
    message = str(caught.value)
    assert bench.package_digest(stale) in message
    assert bench.package_digest(src_root / "src" / "harness_maker") in message
    assert "uv cache clean harness-maker" in message


def test_a_template_change_alone_is_stale(bench: ModuleType, tmp_path: Path) -> None:
    fresh = _package(tmp_path / "a", _FILES)
    edited = _package(tmp_path / "b", {**_FILES, "templates/stages/spec.md.j2": "edited\n"})
    assert bench.package_digest(fresh) != bench.package_digest(edited)


def test_pycache_does_not_count(bench: ModuleType, tmp_path: Path) -> None:
    fresh = _package(tmp_path / "a", _FILES)
    noisy = _package(tmp_path / "b", {**_FILES, "__pycache__/cli.cpython-312.pyc": "junk"})
    assert bench.package_digest(fresh) == bench.package_digest(noisy)


def test_runtime_data_outside_templates_counts(bench: ModuleType, tmp_path: Path) -> None:
    fresh = _package(tmp_path / "a", {**_FILES, "rubrics/r.yaml": "a: 1\n"})
    edited = _package(tmp_path / "b", {**_FILES, "rubrics/r.yaml": "a: 2\n"})
    assert bench.package_digest(fresh) != bench.package_digest(edited)


def test_a_home_relative_prefix_is_expanded_like_the_agent_shell(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    _package(home / "checkout", _FILES)
    same = _package(tmp_path / "cache", _FILES)
    template = _template(tmp_path, Path("$HOME/checkout"))
    monkeypatch.setenv("HOME", str(home))
    seen: list[str] = []

    def fake(src: str, cwd: Path, env: dict[str, str]) -> Path:
        seen.append(src)
        return same

    monkeypatch.setattr(bench, "_installed_package_dir", fake)
    assert bench.check_cli_fresh(template) is None
    assert seen == [str(home / "checkout")]


def test_a_missing_source_tree_is_not_a_digest(bench: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(bench.CliProvenanceError, match="not a package directory"):
        bench.package_digest(tmp_path / "nowhere")


def test_a_non_path_install_is_named_as_such(bench: ModuleType, tmp_path: Path) -> None:
    template = _template(tmp_path, tmp_path)
    (template / ".claude" / "commands" / "hm" / "spec.md").write_text(
        "!uv run --with harness-maker==0.62.0 hm spec_machine approve\n"
    )
    with pytest.raises(bench.CliProvenanceError, match="not a checkout path"):
        bench.check_cli_fresh(template)


def test_a_command_without_the_prefix_is_refused(bench: ModuleType, tmp_path: Path) -> None:
    template = _template(tmp_path, tmp_path / "checkout")
    (template / ".claude" / "commands" / "hm" / "spec.md").write_text("no prefix here\n")
    with pytest.raises(bench.CliProvenanceError, match="uv run --with"):
        bench.check_cli_fresh(template)


def _live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTEGRATION", "1")
    monkeypatch.setenv("IS_SANDBOX", "1")
    monkeypatch.setenv("HM_BENCH_TEST", "1")


def test_run_refuses_before_any_cell_when_the_cli_is_stale(
    bench: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    _live_env(monkeypatch)
    stale = _package(tmp_path / "cache", _FILES)
    monkeypatch.setattr(bench, "_installed_package_dir", lambda src, cwd, env: stale)
    argv = ["run", "--out", str(out), "--guard-top", str(tmp_path), "--claude-bin", "unused",
            "--arms", "hm", "--tasks", "t1", "--runs", "1"]  # fmt: skip
    exit_code = bench.main(argv)
    results_written = (out / "results.jsonl").exists()
    runs_started = any((out / "runs").iterdir()) if (out / "runs").exists() else False
    assert exit_code == 2
    assert not results_written
    assert not runs_started
    err = capsys.readouterr().err
    assert "stale CLI" in err
    assert bench.package_digest(_ROOT / "src" / "harness_maker") in err


# --- AC-003 -----------------------------------------------------------------------------------


def test_check_proceeds_on_a_matching_install(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src_root = tmp_path / "checkout"
    _package(src_root, _FILES)
    same = _package(tmp_path / "cache", _FILES)
    template = _template(tmp_path, src_root)
    monkeypatch.setattr(bench, "_installed_package_dir", lambda src, cwd, env: same)
    assert bench.check_cli_fresh(template) is None


def test_run_checks_once_and_only_an_hm_template(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    _live_env(monkeypatch)
    calls: list[Path] = []

    def refuse(template: Path, pass_env: tuple[str, ...] = ()) -> None:
        calls.append(template)
        raise bench.CliProvenanceError("stale CLI (test)")

    monkeypatch.setattr(bench, "check_cli_fresh", refuse)
    argv = ["run", "--out", str(out), "--guard-top", str(tmp_path), "--claude-bin", "unused",
            "--arms", "plain,hm", "--tasks", "t1,t2", "--runs", "1"]  # fmt: skip
    assert bench.main(argv) == 2
    assert len(calls) == 1
    assert calls[0].name.startswith("hm")
    assert not (out / "results.jsonl").exists()
