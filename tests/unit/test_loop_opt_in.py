"""SPEC-loop-opt-in: `loop.enabled` gates the /hm:loop family (AC-001..AC-011).

Production symbols (`LoopConfig`, the `loop` answers/config field) are resolved at call
time rather than imported at module level, so each test goes RED for its own reason
instead of the whole module failing collection.
"""

from __future__ import annotations

import json
import os
import posixpath
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner

from harness_maker import models
from harness_maker.cli import app
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REPO = Path(__file__).resolve().parents[2]
_BASE_COMMIT = "055cce85"
# The commit that made loop opt-in and regenerated the (loop-off) snapshots. A path whose
# off-render changed after it was changed by later, unrelated work, so the pre-change pin at
# _BASE_COMMIT no longer describes it; such a path is judged against the current snapshot instead.
_OPT_IN_COMMIT = "18714dd1"

# Loop-sensitive paths a LATER task moved, re-captured deliberately (append; never silently
# overwrite). Value: the loop-ON body hash per snapshot fixture.
# - 2026-10-02, `world-model-name`: CLAUDE.md gained the `## World model` pointer. Verified
#   before capture that the loop-ON vs loop-OFF render of CLAUDE.md differs ONLY in the opt-in
#   loop sentence, i.e. the new pointer is loop-independent.
# - 2026-10-02, `world-model-followups`: the `## World model` pointer text was shortened
#   (max-length budget). Re-verified the loop-ON/OFF CLAUDE.md diff is still only the loop
#   sentence before re-capturing.
#   `help.md` re-captured too: it gained the router row; its loop-ON/OFF diff is still only the
#   `/hm:loop` table row and the chaining sentence.
_LOOP_ON_RECAPTURES: dict[str, dict[str, str]] = {
    "commands/hm/help.md": {
        "side-python-cli": "7feb5335d127f43d9cf40c7ddeb00807d82822e6cf12cbd29effe06c6f03bbb2",
        "side-tauri-app": "7feb5335d127f43d9cf40c7ddeb00807d82822e6cf12cbd29effe06c6f03bbb2",
        "prod-tauri-app": "bda19830fef3ad2948b52d142aff1348d99c2a4a3c31f4501f455a8516f83c59",
        "prod-firmware": "bda19830fef3ad2948b52d142aff1348d99c2a4a3c31f4501f455a8516f83c59",
    },
    "../CLAUDE.md": {
        "side-python-cli": "e3606def5b85ea7d9ef10e5d4161ccf3456e1114d62a7e6cbf22983fdbdee76c",
        "side-tauri-app": "e3606def5b85ea7d9ef10e5d4161ccf3456e1114d62a7e6cbf22983fdbdee76c",
        "prod-tauri-app": "74a5b7efec5a49d6c97a6984268457567fb0280371bfae8cdf86410811e1e7ad",
        "prod-firmware": "74a5b7efec5a49d6c97a6984268457567fb0280371bfae8cdf86410811e1e7ad",
    },
}
# Loop-sensitive but never hash-compared below (`strip`), so a later key addition may move it.
_LOOP_SENSITIVE_HASH_EXEMPT = {"harness.yaml"}

LOOP_CLAUDE = {".claude/commands/hm/loop.md", ".claude/commands/hm/loop-p5-batch.md"}
LOOP_CODEX = {".agents/skills/hm-loop/SKILL.md", ".agents/skills/hm-loop-p5-batch/SKILL.md"}
LISTING_SURFACES = (
    ".claude/commands/hm/help.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".cursor/rules/harness.mdc",
    # The Codex rendering of help.md (review finding cd14c78815a4027d surfaced it once
    # AC-009 compared real rendered bodies).
    ".agents/skills/hm-help/SKILL.md",
)
ALLOWED_BODY_DIFFS = {".claude/harness.yaml", *LISTING_SURFACES}
ALL_TARGETS = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


def _norm(fe_path: Path) -> str:
    """Project-root-relative key, the same mapping reconcile._normalize_expected_path uses."""
    s = str(fe_path).replace("\\", "/")
    if s.startswith((".cursor/", ".codex/", ".agents/")) or s == "AGENTS.md":
        return s
    return posixpath.normpath(".claude/" + s)


def _answers(
    *,
    loop_enabled: bool,
    targets: list[Target] | None = None,
    preset: Preset | None = None,
    locale: str = "en",
) -> InterviewAnswers:
    a = interview(_profile(), autoloop_mode=True)
    update: dict[str, Any] = {
        "loop": models.LoopConfig(enabled=loop_enabled),
        "locale": locale,
    }
    if targets is not None:
        update["targets"] = targets
    if preset is not None:
        update["preset"] = preset
    return a.model_copy(update=update)


def _blueprint(**kw: Any) -> models.Blueprint:
    return synthesize(_profile(), _answers(**kw))


def normalized_paths(*, loop_enabled: bool, targets: list[str] | None = None) -> set[str]:
    tgt = [Target.CLAUDE_CODE] + [Target(t) for t in (targets or [])]
    return {_norm(f.path) for f in _blueprint(loop_enabled=loop_enabled, targets=tgt).files}


def _render_tree(root: Path, answers: InterviewAnswers) -> models.Blueprint:
    bp = synthesize(_profile(), answers)
    render(bp, root / ".claude", dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    return bp


def _rendered_body_hashes(root: Path, **kw: Any) -> dict[str, str]:
    """Post-render body hashes. `synthesize()` leaves `body_sha256` None until `render()`."""
    bp = _render_tree(root, _answers(**kw))
    hashes = {_norm(f.path): f.body_sha256 for f in bp.files}
    assert all(h for h in hashes.values()), "render() did not stamp every body hash"
    return {p: str(h) for p, h in hashes.items()}


def _read_yaml(root: Path) -> dict[str, Any]:
    """The user-data body; the rendered file carries a provenance document first."""
    return load_harness_yaml(root / ".claude" / "harness.yaml")


def _git_show(rev: str, rel: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(_REPO), "show", f"{rev}:{rel}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"base commit {rev} not reachable in this checkout: {proc.stderr.strip()}")
    return proc.stdout


def _legacy_yaml_variants() -> dict[str, dict[str, Any]]:
    """Pre-feature harness.yaml (this repo's own, at the base commit) in four shapes."""
    docs = list(yaml.safe_load_all(_git_show(_BASE_COMMIT, ".claude/harness.yaml")))
    base = [d for d in docs if isinstance(d, dict) and d.get("generated_by") != "harness-maker"][-1]
    assert "loop" not in base
    no_version = {k: v for k, v in base.items() if k != "schema_version"}
    v5 = {**base, "schema_version": 5}
    v6_no_key = {**base, "schema_version": 6}
    empty_block = {**base, "loop": {}}
    return {
        "no_version": no_version,
        "v5": v5,
        "v6_no_key": v6_no_key,
        "empty_loop_block": empty_block,
    }


@contextmanager
def _chdir(path: Path) -> Iterator[None]:
    before = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(before)


def _cli(repo: Path, *args: str) -> Any:
    with _chdir(repo):
        return CliRunner().invoke(app, ["make", str(repo), "--autoloop", *args])


def _bootstrap(tmp_path: Path, *extra: str) -> Path:
    repo = tmp_path / "proj"
    repo.mkdir(parents=True)
    res = _cli(repo, *extra)
    assert res.exit_code == 0, res.output
    return repo


def _write_yaml(repo: Path, data: dict[str, Any]) -> None:
    (repo / ".claude" / "harness.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def _tree(repo: Path) -> dict[str, bytes]:
    return {
        p.relative_to(repo).as_posix(): p.read_bytes()
        for p in sorted(repo.rglob("*"))
        if p.is_file()
    }


# ---------------------------------------------------------------------------
# AC-001 / AC-002
# ---------------------------------------------------------------------------


def test_ac001_disabled_renders_no_claude_loop_commands() -> None:
    assert not (LOOP_CLAUDE & normalized_paths(loop_enabled=False))
    assert normalized_paths(loop_enabled=True) >= LOOP_CLAUDE


def test_ac002_disabled_renders_no_codex_loop_skills() -> None:
    assert not (LOOP_CODEX & normalized_paths(loop_enabled=False, targets=["codex"]))
    assert normalized_paths(loop_enabled=True, targets=["codex"]) >= LOOP_CODEX


# ---------------------------------------------------------------------------
# AC-003 — enabled render == pre-change snapshot (reference read from git)
# ---------------------------------------------------------------------------

_SNAPSHOT_FIXTURES = ("side-python-cli", "side-tauri-app", "prod-tauri-app", "prod-firmware")


@pytest.fixture
def _isolate_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = tmp_path_factory.mktemp("hm-home")
    monkeypatch.setattr(Path, "home", lambda: fake_home)


@pytest.mark.usefixtures("_isolate_home")
@pytest.mark.parametrize("fixture", _SNAPSHOT_FIXTURES)
def test_ac003_enabled_matches_pre_change_snapshots(fixture: str, tmp_path: Path) -> None:
    sys.path.insert(0, str(_REPO / "tests" / "snapshot"))
    from regenerate import is_excluded, load_exclusions

    snapshot = f"tests/snapshot/{fixture}.expected.yaml"
    reference = yaml.safe_load(_git_show(_BASE_COMMIT, snapshot))
    base = {r["path"]: r["body_sha256"] for r in reference["files"]}
    at_opt_in = {
        r["path"]: r["body_sha256"]
        for r in yaml.safe_load(_git_show(_OPT_IN_COMMIT, snapshot))["files"]
    }
    now_rows = {
        r["path"]: r
        for r in yaml.safe_load((_REPO / snapshot).read_text(encoding="utf-8"))["files"]
    }
    now = {path: r["body_sha256"] for path, r in now_rows.items()}
    moved = {path for path in at_opt_in.keys() | now.keys() if at_opt_in.get(path) != now.get(path)}
    # Paths whose render depends on loop.enabled are the ones the opt-in commit itself changed.
    loop_sensitive = {
        path for path in base.keys() | at_opt_in.keys() if base.get(path) != at_opt_in.get(path)
    }
    # A moved loop-insensitive path renders the same with the loop on or off, so its loop-ON
    # expectation is today's loop-OFF snapshot. A moved loop-SENSITIVE path has no committed
    # loop-ON expectation at all: fail here so it is handled deliberately, never dropped silently.
    unhandled = (moved & loop_sensitive) - _LOOP_ON_RECAPTURES.keys() - _LOOP_SENSITIVE_HASH_EXEMPT
    assert not unhandled, sorted(unhandled)
    p = profile(_REPO / "tests" / "fixtures" / fixture)
    a = interview(p, autoloop_mode=True).model_copy(
        update={"loop": models.LoopConfig(enabled=True)}
    )
    bp = synthesize(p, a)
    render(bp, tmp_path, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    exclusions = load_exclusions()
    actual = sorted(
        (
            {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
            for f in bp.files
            if not is_excluded(str(f.path), exclusions)
        ),
        key=lambda x: x["path"] or "",
    )
    expected = sorted(
        (
            now_rows[r["path"]] if r["path"] in moved else r
            for r in reference["files"]
            if not (r["path"] in moved and r["path"] not in now_rows)
        ),
        key=lambda x: x["path"] or "",
    )
    expected += [now_rows[path] for path in sorted(moved - base.keys()) if path in now_rows]
    expected = [
        {**r, "body_sha256": _LOOP_ON_RECAPTURES[r["path"]][fixture]}
        if r["path"] in _LOOP_ON_RECAPTURES
        else r
        for r in expected
    ]
    expected.sort(key=lambda x: x["path"] or "")

    def strip(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in rows if r["path"] != "harness.yaml"]

    assert [r["path"] for r in actual] == [r["path"] for r in expected]
    assert strip(actual) == strip(expected)


# ---------------------------------------------------------------------------
# AC-004 — listing surfaces carry no loop advertisement, exactly one enable hint
# ---------------------------------------------------------------------------


def _enable_hint_count(text: str) -> int:
    """Lines naming the key and the re-render command in the host's spelling.

    The Codex render rewrites `/hm:<name>` to `$hm-<name>` (AGENTS.md), and Codex's
    re-render skill really is `hm-make`, so both spellings name the same command.
    """
    return sum(
        1
        for line in text.splitlines()
        if "loop.enabled: true" in line and ("/hm:make" in line or "$hm-make" in line)
    )


@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
@pytest.mark.parametrize("locale", ["en", "ko"])
def test_ac004_disabled_leaves_no_loop_advertisement(
    tmp_path: Path, preset: Preset, locale: str
) -> None:
    _render_tree(
        tmp_path,
        _answers(loop_enabled=False, targets=ALL_TARGETS, preset=preset, locale=locale),
    )
    for rel in LISTING_SURFACES:
        path = tmp_path / rel
        assert path.is_file(), f"{rel} was not rendered"
        text = path.read_text(encoding="utf-8")
        offenders = [
            line
            for line in text.splitlines()
            if ("hm:loop" in line or "hm-loop" in line) and "loop.enabled" not in line
        ]
        assert offenders == [], f"{rel} still advertises the loop: {offenders}"
        assert _enable_hint_count(text) == 1, f"{rel} must carry exactly one enable hint"


# ---------------------------------------------------------------------------
# AC-005 — an existing harness.yaml without the key keeps the loop
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", ["no_version", "v5", "v6_no_key", "empty_loop_block"])
def test_ac005_existing_absent_key_keeps_loop(tmp_path: Path, variant: str) -> None:
    data = _legacy_yaml_variants()[variant]
    src = tmp_path / "harness.yaml"
    src.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    answers = answers_from_harness_yaml(src)
    assert answers is not None
    assert answers.loop.enabled is True

    out = tmp_path / "out"
    bp = _render_tree(out, answers)
    assert _read_yaml(out)["loop"]["enabled"] is True
    assert {_norm(f.path) for f in bp.files} >= LOOP_CLAUDE


# ---------------------------------------------------------------------------
# AC-006 — no harness.yaml on disk → loop off, schema_version 6, disclosure row
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("preset_flag", ["Side", "Production"])
def test_ac006_no_harness_yaml_writes_loop_off(tmp_path: Path, preset_flag: str) -> None:
    repo = tmp_path / "proj"
    repo.mkdir()
    assert not (repo / ".claude" / "harness.yaml").exists()
    res = _cli(repo, "--preset", preset_flag)
    assert res.exit_code == 0, res.output
    data = _read_yaml(repo)
    assert data["loop"]["enabled"] is False
    assert data["schema_version"] == 6
    assert not (repo / ".claude" / "commands" / "hm" / "loop.md").exists()

    make_md = (_REPO / "commands" / "make.md").read_text(encoding="utf-8")
    disclosure = make_md.split("**Set for you", 1)[1].split("**Safety receipt preview", 1)[0]
    assert "| `loop.enabled` |" in disclosure


# ---------------------------------------------------------------------------
# AC-007 — turning the loop off sweeps pristine files, keeps edited ones
# ---------------------------------------------------------------------------


def test_ac007_disable_sweeps_pristine_keeps_edited(tmp_path: Path) -> None:
    repo = _bootstrap(tmp_path, "--targets", "claude-code,codex")
    data = _read_yaml(repo)
    data["loop"] = {"enabled": True}
    _write_yaml(repo, data)
    res = _cli(repo, "--update")
    assert res.exit_code == 0, res.output

    pristine = [".claude/commands/hm/loop.md", ".agents/skills/hm-loop/SKILL.md"]
    edited = [".claude/commands/hm/loop-p5-batch.md", ".agents/skills/hm-loop-p5-batch/SKILL.md"]
    for rel in pristine + edited:
        assert (repo / rel).is_file(), f"precondition: {rel} rendered while enabled"
    before: dict[str, bytes] = {}
    for rel in edited:
        path = repo / rel
        path.write_text(path.read_text(encoding="utf-8") + "\nuser note\n", encoding="utf-8")
        before[rel] = path.read_bytes()

    data = _read_yaml(repo)
    data["loop"] = {"enabled": False}
    _write_yaml(repo, data)
    res = _cli(repo, "--update")
    assert res.exit_code == 0, res.output

    assert not any((repo / rel).exists() for rel in pristine)
    assert all((repo / rel).read_bytes() == before[rel] for rel in edited)
    assert "orphan(s) kept" in res.output
    kept_rows = [
        json.loads(line)
        for log in (repo / ".claude" / "observability").glob("orphans-*.jsonl")
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    kept = {row["path"]: row["classification"] for row in kept_rows}
    for rel in edited:
        assert kept.get(rel) == "ours-modified", f"{rel} keep warning missing: {kept}"


# ---------------------------------------------------------------------------
# AC-008 — an explicit value survives re-render (property)
# ---------------------------------------------------------------------------


@settings(max_examples=8, derandomize=True, deadline=None)
@given(enabled=st.booleans(), preset=st.sampled_from([Preset.SIDE, Preset.PRODUCTION]))
def test_ac008_explicit_value_round_trips(enabled: bool, preset: Preset) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        first = Path(d) / "first"
        _render_tree(first, _answers(loop_enabled=enabled, preset=preset))
        assert _read_yaml(first)["loop"]["enabled"] is enabled
        reloaded = answers_from_harness_yaml(first / ".claude" / "harness.yaml")
        assert reloaded is not None
        second = Path(d) / "second"
        _render_tree(second, reloaded)
        assert _read_yaml(second)["loop"]["enabled"] is enabled


# ---------------------------------------------------------------------------
# AC-009 — disabling removes only the loop files
# ---------------------------------------------------------------------------


def test_ac009_disable_removes_only_loop_files(tmp_path: Path) -> None:
    enabled = _rendered_body_hashes(tmp_path / "on", loop_enabled=True, targets=ALL_TARGETS)
    disabled = _rendered_body_hashes(tmp_path / "off", loop_enabled=False, targets=ALL_TARGETS)
    assert set(enabled) - set(disabled) == LOOP_CLAUDE | LOOP_CODEX
    assert not (set(disabled) - set(enabled))
    changed = {p for p in disabled if disabled[p] != enabled[p]}
    assert changed <= ALLOWED_BODY_DIFFS, f"unexpected body changes: {changed - ALLOWED_BODY_DIFFS}"
    for p in disabled:
        if p in ALLOWED_BODY_DIFFS:
            continue
        if p.startswith(
            (".claude/agents/", ".claude/skills/", ".agents/skills/", ".codex/")
        ) or p in {
            ".claude/settings.json",
            ".cursor/hooks.json",
        }:
            assert disabled[p] == enabled[p], f"{p} changed"


# ---------------------------------------------------------------------------
# AC-010 — an existing harness.yaml keeps the loop on every re-render path
# ---------------------------------------------------------------------------


def test_ac010_preset_switch_keeps_existing_loop(tmp_path: Path) -> None:
    """Review finding f5610f47309c7a63: the `--preset` rebuild takes a field allowlist."""
    for preset_from, preset_to in (("Side", "Production"), ("Production", "Side")):
        for enabled in (True, False):
            repo = _bootstrap(tmp_path / f"{preset_from}-{enabled}", "--preset", preset_from)
            data = _read_yaml(repo)
            data["loop"] = {"enabled": enabled}
            _write_yaml(repo, data)
            res = _cli(repo, "--update", "--preset", preset_to)
            assert res.exit_code == 0, res.output
            assert _read_yaml(repo)["preset"] == preset_to
            assert _read_yaml(repo)["loop"]["enabled"] is enabled
            assert (repo / ".claude/commands/hm/loop.md").is_file() is enabled


def test_ac010_existing_yaml_keeps_loop_on_every_path(tmp_path: Path) -> None:
    loop_md = Path(".claude/commands/hm/loop.md")

    repo = _bootstrap(tmp_path / "reinterview")
    data = _read_yaml(repo)
    data.pop("loop", None)
    data["schema_version"] = 5
    _write_yaml(repo, data)
    res = _cli(repo, "--reinterview")
    assert res.exit_code == 0, res.output
    assert _read_yaml(repo)["loop"]["enabled"] is True
    assert (repo / loop_md).is_file()

    repo = _bootstrap(tmp_path / "fallback")
    data = _read_yaml(repo)
    data.pop("loop", None)
    data["preset"] = "NotAPreset"  # answers_from_harness_yaml returns None → interview()
    _write_yaml(repo, data)
    res = _cli(repo, "--update")
    assert res.exit_code == 0, res.output
    assert _read_yaml(repo)["loop"]["enabled"] is True
    assert (repo / loop_md).is_file()

    repo = _bootstrap(tmp_path / "undecodable")
    (repo / ".claude" / "harness.yaml").write_bytes(b"preset: Side\nlocale: \xff\xfe\n")
    res = _cli(repo, "--update")
    assert res.exit_code == 0, res.output
    assert _read_yaml(repo)["loop"]["enabled"] is True
    assert (repo / loop_md).is_file()

    repo = _bootstrap(tmp_path / "explicit-false")
    data = _read_yaml(repo)
    data["loop"] = {"enabled": False}
    _write_yaml(repo, data)
    res = _cli(repo, "--reinterview")
    assert res.exit_code == 0, res.output
    assert _read_yaml(repo)["loop"]["enabled"] is False


# ---------------------------------------------------------------------------
# AC-011 — a malformed loop value fails the render, nothing written or deleted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {"enabled": None},
        {"enabled": "false"},
        {"enabled": True, "extra": 1},
        {1: True},
        {"enabled": True, 1: False, "extra": False},
    ],
    ids=[
        "loop_null",
        "enabled_null",
        "enabled_str_false",
        "unknown_key",
        "int_key",
        "mixed_keys",
    ],
)
def test_ac011_malformed_loop_value_fails_render(tmp_path: Path, bad: object) -> None:
    repo = _bootstrap(tmp_path)
    data = _read_yaml(repo)
    data["loop"] = bad
    _write_yaml(repo, data)
    before = _tree(repo)
    res = _cli(repo, "--update")
    assert res.exit_code != 0
    assert "loop" in res.output
    assert _tree(repo) == before
