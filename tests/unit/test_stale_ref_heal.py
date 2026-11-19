"""SPEC-stale-install-recovery AC-001..004: SessionStart heals dead harness-maker hook refs."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker import stale_ref_heal
from harness_maker.hooks import sessionstart_drift

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = json.loads((ROOT / "specs/SPEC-stale-install-recovery.golden.json").read_text("utf-8"))

CACHE = ".claude/plugins/cache/harness-maker/harness-maker"
LIVE_VER = "0.66.0"
NEW_TOKEN = f'--with "$HOME/{CACHE}/{LIVE_VER}"'


def _home(tmp: Path, name: str = "home dir") -> tuple[Path, Path]:
    """A tmp HOME holding the live plugin cache, and that cache dir."""
    home = tmp / name
    plugin = home / CACHE / LIVE_VER
    plugin.mkdir(parents=True)
    (plugin / "pyproject.toml").write_text("[project]\nname = 'harness-maker'\n")
    (home / CACHE / "0.65.9-live").mkdir(parents=True)
    return home, plugin


def _hm(ref: str, quote: str, module: str = "gates.permission_gate", args: str = "") -> str:
    token = {"dq": f'"{ref}"', "sq": f"'{ref}'", "bare": ref}[quote]
    tail = f" {args}" if args else ""
    return f"uv run --no-project --with {token} python -m harness_maker.{module}{tail}"


DEAD_REF = f"$HOME/{CACHE}/0.65.2"
DEAD_BACKSLASH_REF = "$HOME\\.claude\\plugins\\cache\\harness-maker\\harness-maker\\0.64.0"
LIVE_REF = f"$HOME/{CACHE}/0.65.9-live"
USER_DEAD = 'uv run --with "$HOME/gone-tool" python -m mytool.check'


def _settings_text(commands: list[str], *, indent: int = 2, newline: bool = True) -> str:
    doc: dict[str, Any] = {
        "permissions": {"allow": ["Bash(ls:*)"], "설명": "사용자 메모"},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": c, "timeout": 10} for c in commands],
                }
            ]
        },
        "preset": "Side",
    }
    return json.dumps(doc, indent=indent, ensure_ascii=False) + ("\n" if newline else "")


def _project(
    tmp: Path, text: str, *, harness: bool = True, rel: str = ".claude/settings.json"
) -> Path:
    project = tmp / "proj"
    target = project / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    if harness:
        (project / ".claude").mkdir(exist_ok=True)
        (project / ".claude/harness.yaml").write_text("---\nharness_maker_version: 0.65.2\n---\n")
    return project


def _expected_new(old: str) -> str:
    """Independent oracle: the harness-maker `--with` token becomes NEW_TOKEN; nothing else."""
    head, sep, tail = old.partition(" python -m harness_maker.")
    words = head.split(" --with ")
    assert len(words) == 2, old
    return f"{words[0]} {NEW_TOKEN}{sep}{tail}"


def _expand(arg: str, home: Path) -> Path:
    return Path(arg.replace("$HOME", str(home)))


# ── AC-001 ─────────────────────────────────────────────────────────────────────

_ENTRY = st.sampled_from(["dead_hm", "dead_backslash_hm", "live_hm", "dead_user"])
_QUOTE = st.sampled_from(["dq", "sq", "bare"])


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    entries=st.lists(st.tuples(_ENTRY, _QUOTE), min_size=1, max_size=6),
    indent=st.sampled_from([2, 4]),
    newline=st.booleans(),
)
def test_ac_001_dead_hm_refs_spliced_rest_byte_identical(
    tmp_path_factory: pytest.TempPathFactory,
    entries: list[tuple[str, str]],
    indent: int,
    newline: bool,
) -> None:
    tmp = tmp_path_factory.mktemp("ac001")
    home, plugin = _home(tmp)
    commands: list[str] = []
    for kind, quote in entries:
        if kind == "dead_hm":
            commands.append(_hm(DEAD_REF, quote, args="--subordinate-to-deny-dangerous"))
        elif kind == "dead_backslash_hm":
            commands.append(_hm(DEAD_BACKSLASH_REF, "dq" if quote == "bare" else quote))
        elif kind == "live_hm":
            commands.append(_hm(LIVE_REF, quote, module="gates.worktree_gate"))
        else:
            commands.append(USER_DEAD)
    original = _settings_text(commands, indent=indent, newline=newline)
    project = _project(tmp, original)

    stale_ref_heal.heal_project(project, plugin_root=str(plugin), home=home)

    expected = original
    for kind, cmd in zip((k for k, _ in entries), commands, strict=True):
        if kind in ("dead_hm", "dead_backslash_hm"):
            new = _expected_new(cmd)
            expected = expected.replace(
                json.dumps(cmd, ensure_ascii=False), json.dumps(new, ensure_ascii=False)
            )
    healed = (project / ".claude/settings.json").read_text(encoding="utf-8")
    assert healed == expected
    for hook in json.loads(healed)["hooks"]["PreToolUse"][0]["hooks"]:
        argv = shlex.split(hook["command"])
        if "harness_maker.gates.permission_gate" in argv:
            assert _expand(argv[argv.index("--with") + 1], home).is_dir()


# ── AC-002 ─────────────────────────────────────────────────────────────────────


def _case(case: str, tmp: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str | None]:
    home, plugin = _home(tmp)
    root: str | None = str(plugin)
    dead = _hm(DEAD_REF, "dq")
    text = _settings_text([dead])
    harness = True
    if case == "all_live":
        text = _settings_text([_hm(LIVE_REF, "dq")])
    elif case == "dead_user_hook_only":
        text = _settings_text([USER_DEAD])
    elif case == "no_harness_yaml":
        harness = False
    elif case == "malformed_json":
        text = text[: len(text) // 2]
    elif case == "running_ref_not_directory":
        root = str(home / CACHE / "9.9.9")
    elif case == "running_ref_is_source_checkout":
        src = home / "SIDE/harness-maker"
        src.mkdir(parents=True)
        (src / "pyproject.toml").write_text("[project]\nname = 'harness-maker'\n")
        root = str(src)
    elif case == "claude_plugin_root_unset":
        root = None
    elif case == "module_not_in_registry_only":
        text = _settings_text([_hm(DEAD_REF, "dq", module="hooks.retired_session_hook")])
    project = _project(tmp, text, harness=harness)
    if case == "file_changed_between_read_and_write":
        real = stale_ref_heal._current_bytes

        def racing(path: Path) -> bytes:
            path.write_text(path.read_text("utf-8").replace('"Side"', '"Production"'), "utf-8")
            return real(path)

        monkeypatch.setattr(stale_ref_heal, "_current_bytes", racing)
    return project, home, root


@pytest.mark.parametrize(
    "row", GOLDEN["AC-002"], ids=[f"AC-002-{i}" for i in range(len(GOLDEN["AC-002"]))]
)
def test_ac_002_no_write_when_nothing_safe_to_heal(
    row: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = row["input"]["case"]
    assert row["expected"] == "no_write"
    project, home, root = _case(case, tmp_path, monkeypatch)
    path = project / ".claude/settings.json"
    if case == "file_changed_between_read_and_write":
        stale_ref_heal.heal_project(project, plugin_root=root, home=home)
        after = path.read_text("utf-8")
        assert '"Production"' in after, "the concurrent edit was overwritten"
        assert DEAD_REF in after
        return
    before = path.read_bytes()
    mtime = path.stat().st_mtime_ns
    report = stale_ref_heal.heal_project(project, plugin_root=root, home=home)
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == mtime
    assert not report.healed
    if case == "module_not_in_registry_only":
        assert report.unhealable == ["hooks.retired_session_hook"]


# ── AC-003 ─────────────────────────────────────────────────────────────────────


def _codex_text(command: str) -> str:
    doc = {
        "hooks": {
            "PermissionRequest": [{"hooks": [{"command": command, "type": "command"}]}],
            "PostToolUse": [],
            "PreToolUse": [{"hooks": [{"command": command, "type": "command"}], "matcher": "Bash"}],
        }
    }
    return json.dumps(doc, indent=2) + "\n"


@pytest.mark.parametrize(
    "row", GOLDEN["AC-003"], ids=[f"AC-003-{i}" for i in range(len(GOLDEN["AC-003"]))]
)
def test_ac_003_codex_hooks_json_same_rule(row: dict[str, Any], tmp_path: Path) -> None:
    home, plugin = _home(tmp_path)
    old = _hm(DEAD_REF if row["input"]["ref"] == "dead" else LIVE_REF, "dq")
    original = _codex_text(old)
    project = _project(tmp_path, original, rel=row["input"]["file"])
    path = project / row["input"]["file"]
    mtime = path.stat().st_mtime_ns
    report = stale_ref_heal.heal_project(project, plugin_root=str(plugin), home=home)
    if row["expected"] == "spliced":
        assert path.read_text("utf-8") == original.replace(
            json.dumps(old), json.dumps(_expected_new(old))
        )
        assert report.healed == {".codex/hooks.json": 2}
    else:
        assert path.read_text("utf-8") == original
        assert path.stat().st_mtime_ns == mtime


# ── AC-004 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "row", GOLDEN["AC-004"], ids=[f"AC-004-{i}" for i in range(len(GOLDEN["AC-004"]))]
)
def test_ac_004_sessionstart_reports_heal_and_stays_safe(
    row: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inp, exp = row["input"], row["expected"]
    home, plugin = _home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    dead = [_hm(DEAD_REF, "dq")] * int(inp.get("healed", 0))
    project = _project(tmp_path, _settings_text(dead or [_hm(LIVE_REF, "dq")]))
    stamped = "0.0.1" if inp["drift"] else "0.5.5"
    (project / ".claude/harness.yaml").write_text(
        f"---\nharness_maker_version: {stamped}\n---\nadaptive:\n  disable_telemetry: true\n"
    )
    monkeypatch.setattr(sessionstart_drift, "latest_installed_version", lambda: "0.5.5")
    monkeypatch.setattr(sessionstart_drift, "_personalization_hint", lambda _cwd: None)
    if inp.get("heal_raises"):

        def boom(*_a: object, **_k: object) -> object:
            raise RuntimeError("heal exploded")

        monkeypatch.setattr(stale_ref_heal, "heal_project", boom)

    rc = sessionstart_drift.run(cwd=project, plugin_root=str(plugin))
    out = capsys.readouterr().out
    assert rc == exp["exit"]
    if "stdout" in exp:
        assert out == ""
        return
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    for word in exp["context_mentions"]:
        assert word in ctx.lower() or word in ctx
    if inp.get("healed"):
        assert f".claude/settings.json ({inp['healed']} hook command(s))" in ctx


def test_ac_004_main_reads_plugin_root_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        sessionstart_drift,
        "run",
        lambda cwd=None, plugin_root=None: seen.update(r=plugin_root) or 0,
    )
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setattr("sys.argv", ["x", "--plugin-root", "/p/root"])
    assert sessionstart_drift.main() == 0
    assert seen["r"] == "/p/root"
    hooks = json.loads((ROOT / "hooks/hooks.json").read_text())
    cmd = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert cmd.endswith("--plugin-root ${CLAUDE_PLUGIN_ROOT}")


# ── review round 1 (REVIEW-stale-install-recovery F1/F6/F7/F8) ──────────────────


@pytest.mark.parametrize(
    "ref",
    [
        "$CLAUDE_PROJECT_DIR/../harness-maker",
        "git+https://github.com/Ecro/harness-maker",
        "harness-maker",
        "$HOMEDIR/.claude/plugins/cache/harness-maker/harness-maker/0.65.2",
        "/opt/src/harness-maker",
    ],
)
def test_user_chosen_refs_are_never_repointed(ref: str, tmp_path: Path) -> None:
    home, plugin = _home(tmp_path)
    original = _settings_text([_hm(ref, "dq")])
    project = _project(tmp_path, original)
    report = stale_ref_heal.heal_project(project, plugin_root=str(plugin), home=home)
    assert (project / ".claude/settings.json").read_text("utf-8") == original
    assert not report.healed


def test_symlinked_claude_dir_still_heals(tmp_path: Path) -> None:
    home = tmp_path / "home"
    real = tmp_path / "dotfiles/claude"
    plugin = real / "plugins/cache/harness-maker/harness-maker" / LIVE_VER
    plugin.mkdir(parents=True)
    (plugin / "pyproject.toml").write_text("[project]\nname = 'harness-maker'\n")
    home.mkdir()
    (home / ".claude").symlink_to(real)
    project = _project(tmp_path, _settings_text([_hm(DEAD_REF, "dq")]))
    report = stale_ref_heal.heal_project(
        project, plugin_root=str(home / CACHE / LIVE_VER), home=home
    )
    assert report.healed == {".claude/settings.json": 1}


def test_heal_keeps_file_mode_and_symlink(tmp_path: Path) -> None:
    home, plugin = _home(tmp_path)
    project = _project(tmp_path, "{}")
    real = tmp_path / "shared-settings.json"
    real.write_text(_settings_text([_hm(DEAD_REF, "dq")]), "utf-8")
    real.chmod(0o644)
    link = project / ".claude/settings.json"
    link.unlink()
    link.symlink_to(real)
    stale_ref_heal.heal_project(project, plugin_root=str(plugin), home=home)
    assert link.is_symlink()
    assert (real.stat().st_mode & 0o777) == 0o644
    assert NEW_TOKEN.replace('"', '\\"') in real.read_text("utf-8")


def test_unspliceable_escape_and_unwritable_file_are_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review round 2 N1/N2: a dead ref we cannot repair is reported, and one failing file
    does not stop the other from being healed."""
    home, plugin = _home(tmp_path)
    dead = _hm(DEAD_REF, "dq")
    escaped = _settings_text([dead]).replace("/", "\\u002f")
    project = _project(tmp_path, escaped)
    codex = project / ".codex/hooks.json"
    codex.parent.mkdir(parents=True)
    codex.write_text(_codex_text(dead), "utf-8")
    report = stale_ref_heal.heal_project(project, plugin_root=str(plugin), home=home)
    assert report.healed == {".codex/hooks.json": 2}
    assert report.unhealable == ["gates.permission_gate in .claude/settings.json"]

    codex.write_text(_codex_text(dead), "utf-8")
    from harness_maker.io_utils import atomic_write as real

    def flaky(path: Path, content: str) -> None:
        if path.name == "settings.json":
            raise PermissionError("read-only")
        real(path, content)

    monkeypatch.setattr("harness_maker.stale_ref_heal.atomic_write", flaky)
    (project / ".claude/settings.json").write_text(_settings_text([dead]), "utf-8")
    report = stale_ref_heal.heal_project(project, plugin_root=str(plugin), home=home)
    assert report.healed == {".codex/hooks.json": 2}
    assert report.unhealable == [".claude/settings.json (PermissionError)"]
    msg = stale_ref_heal.describe(report)
    assert msg is not None
    assert "Not repaired" in msg
