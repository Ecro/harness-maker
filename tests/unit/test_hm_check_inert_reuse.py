"""SPEC-hm-check-docs-only-reuse: gate-only reuse under DRI-declared inert globs."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from harness_maker import check, check_reuse
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.models import CheckConfig, HarnessConfig, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.spec_machine import approve
from harness_maker.synthesize import synthesize
from tests.hm_cost_p2_fixture import init_project, mech_ac, write_spec

GOLDEN = json.loads(
    (Path(__file__).parents[2] / "specs" / "SPEC-hm-check-docs-only-reuse.golden.json").read_text(
        encoding="utf-8"
    )
)
D = ["CHANGELOG.md", "work-docs/**"]
BASE_FILES = {
    "CHANGELOG.md": "# log\n",
    "README.md": "# readme\n",
    "NOTES.md": "notes\n",
    "docs/nested.md": "nested\n",
    "work-docs/PLAN-x.md": "plan\n",
    "work-docs/a.md": "a\n",
    "work-docs/data.md": "data\n",
    "work-docs/other.md": "other\n",
    "work-docs/sub/keep.md": "keep\n",
    "work-docs/tool.py": "X = 1\n",
    "work-docs/tests/fixture.md": "fixture\n",
    "src/a.py": "A = 1\n",
    "pyproject.toml": '[project]\nname = "fixture"\nversion = "0.0.0"\n',
    "tests/test_ok.py": "def test_ok():\n    assert 1 + 1 == 2\n",
    "gate.py": (
        "import os, sys\n"
        "open(os.environ['HM_FIX_MARKER'], 'a').write('x\\n')\n"
        "sys.exit(1 if os.path.exists(os.environ['HM_FIX_FAIL']) else 0)\n"
    ),
    "gate_tests/conftest.py": (
        "import os\n\n\ndef pytest_sessionstart(session):\n"
        "    if not hasattr(session.config, 'workerinput'):\n"
        "        open(os.environ['HM_FIX_MARKER'], 'a').write('p\\n')\n"
    ),
    "gate_tests/test_g.py": "def test_g():\n    assert True\n",
}
OPENS = {
    "work-docs/data.md": (
        "import os\nfrom pathlib import Path\n\n\ndef test_g():\n"
        "    assert open(Path(__file__).resolve().parents[1] / 'work-docs' / 'data.md').read()\n"
    ),
    "work-docs/data.md (in a worker)": (
        "import os\nfrom pathlib import Path\n\n\ndef test_g():\n"
        "    assert os.environ.get('PYTEST_XDIST_WORKER')\n"
        "    assert open(Path(__file__).resolve().parents[1] / 'work-docs' / 'data.md').read()\n"
    ),
    "relative Path('work-docs/data.md')": (
        "from pathlib import Path\n\n\ndef test_g():\n"
        "    assert Path('work-docs/data.md').read_text()\n"
    ),
    "chdir work-docs/sub then ../data.md": (
        "import os\n\n\ndef test_g(monkeypatch):\n"
        "    monkeypatch.chdir('work-docs/sub')\n"
        "    assert open('../data.md').read()\n"
    ),
    "link.md -> work-docs/data.md": ("def test_g():\n    assert open('link.md').read()\n"),
}


@dataclass
class Proj:
    root: Path
    marker: Path
    fail_flag: Path
    marker_cmd: str

    def gate_runs(self) -> int:
        return len(self.marker.read_text().splitlines()) if self.marker.exists() else 0

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True, timeout=30)

    def commit(self, msg: str = "c") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)

    def record(self) -> dict[str, Any] | None:
        path = check.verdict_path(self.root)
        assert path is not None
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def edit_record(self, **fields: Any) -> None:
        path = check.verdict_path(self.root)
        assert path is not None
        rec = json.loads(path.read_text(encoding="utf-8"))
        rec.update(fields)
        for k in [k for k, v in fields.items() if v is _DROP]:
            del rec[k]
        path.write_text(json.dumps(rec), encoding="utf-8")


_DROP = object()


def _write_cfg(
    root: Path, decl: Any, level: str = "auto_full", mechanical: list[str] | None = None
) -> None:
    cfg: dict[str, Any] = {"autonomy": {"level": level}}
    if mechanical:
        cfg["reviewers"] = {"mechanical_checks": mechanical}
    if decl is not None and decl != []:
        cfg["check"] = {"reuse_inert": decl}
    (root / ".claude" / "harness.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")


def _project(
    tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    decl: Any = None,
    gates: str = "both",
    opens: str | None = None,
    xdist: bool = False,
    level: str = "auto_full",
) -> Proj:
    root = init_project(tmp / "p")
    marker, fail_flag = tmp / "gate-runs.log", tmp / "gate-fails"
    monkeypatch.setenv("HM_FIX_MARKER", str(marker))
    monkeypatch.setenv("HM_FIX_FAIL", str(fail_flag))
    for rel, body in BASE_FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body, encoding="utf-8")
    if opens is not None:
        (root / "gate_tests" / "test_g.py").write_text(OPENS[opens], encoding="utf-8")
        if opens.startswith("link.md"):
            os.symlink("work-docs/data.md", root / "link.md")
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    for name, body in (
        ("python", f'exec "{sys.executable}" "$@"'),
        ("pytest", f'exec "{sys.executable}" -m pytest "$@"'),
        ("ruff", "exit 0"),  # a recognised CI tool name for the non-pytest-only gate list
    ):
        (venv_bin / name).write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        (venv_bin / name).chmod(0o755)
    (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    marker_cmd = f"{sys.executable} gate.py"
    pytest_cmd = ".venv/bin/pytest -q -p no:cacheprovider gate_tests"
    if xdist:
        pytest_cmd += " -n 2"
    ci = {"both": [pytest_cmd], "pytest": [pytest_cmd], "marker": [".venv/bin/ruff check"]}
    mechanical = {"both": [marker_cmd], "pytest": [], "marker": [marker_cmd]}
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    body = "on: [push]\njobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n"
    for i, cmd in enumerate(ci[gates]):
        body += f"      - name: g{i}\n        run: {json.dumps(cmd)}\n"
    (wf / "ci.yml").write_text(body, encoding="utf-8")
    write_spec(
        root, [mech_ac("AC-001", pending_test=False, test_ids=["tests/test_ok.py::test_ok"])]
    )
    _write_cfg(root, decl, level, mechanical[gates])
    p = Proj(root, marker, fail_flag, marker_cmd)
    p.commit("base")
    return p


def _run(p: Proj, *, reuse: bool = True) -> dict[str, Any]:
    opts = check.Options(slug="demo", root=p.root, offline=True)
    return check.run(opts, reuse=reuse, cve_query=lambda *a, **k: [])


def _seed_pass(p: Proj) -> None:
    result = _run(p, reuse=False)
    assert result["exit"] == 0, result
    assert p.record() is not None, "a passing run wrote no record"


def _rows(ac: str) -> list[dict[str, Any]]:
    return list(GOLDEN[ac])


def _rid(row: dict[str, Any]) -> str:
    return re.sub(r"[^A-Za-z0-9*.]+", "-", "-".join(map(str, row["input"].values())))[:80]


def _append(p: Proj, rel: str) -> None:
    with (p.root / rel).open("a", encoding="utf-8") as f:
        f.write("edited\n")


def _apply(p: Proj, change: str) -> None:
    if change == "none":
        return
    m = re.fullmatch(r"modify (\S+)(?: and (\S+))?", change)
    if m:
        for rel in m.groups():
            if rel:
                _append(p, rel)
        return
    m = re.fullmatch(r"add (\S+)", change)
    if m:
        (p.root / m.group(1)).write_text("new\n", encoding="utf-8")
        return
    m = re.fullmatch(r"remove (\S+)", change)
    if m:
        p.git("rm", "-q", m.group(1))
        return
    if change.startswith("plain rm "):
        (p.root / change.split()[2]).unlink()
        return
    if change == "work-docs/a.md replaced by symlink to src/a.py":
        (p.root / "work-docs" / "a.md").unlink()
        os.symlink("../src/a.py", p.root / "work-docs" / "a.md")
        return
    raise AssertionError(f"unknown change {change!r}")


def _observe(p: Proj, before: int, result: dict[str, Any]) -> dict[str, Any]:
    reuse = result.get("reuse") or {}
    miss = result.get("reuse_miss") or {}
    return {
        "gates_ran": p.gate_runs() > before,
        "rule": reuse.get("rule"),
        "miss": miss.get("reason"),
        "paths": miss.get("paths"),
        "read_set": reuse.get("read_set"),
        "unobserved": reuse.get("unobserved"),
    }


# ── AC-001 ─────────────────────────────────────────────────────────────────────

_REVIEW = "work-docs/REVIEW-demo-2026-11-02.md"


def _review(p: Proj, disposition: str) -> None:
    (p.root / _REVIEW).write_text(
        "# REVIEW\n\n## Findings\n\n"
        "| id | severity | file:line | finding | disposition | authority |\n"
        f"|---|---|---|---|---|---|\n| F1 | minor | a.py:1 | x | {disposition} | dri |\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("row", _rows("AC-001"), ids=_rid)
def test_ac_001_section_split(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: dict[str, Any]
) -> None:
    inp, exp = row["input"], row["expected"]
    level = "gated" if "approval" in inp["change"] else "auto_full"
    p = _project(tmp_path, monkeypatch, decl=inp["decl"], level=level)
    _review(p, "accepted")
    y = p.root / "specs" / "SPEC-demo.machine.yaml"
    if level == "gated":
        approve(y)
    p.commit("review")
    _seed_pass(p)
    before = p.gate_runs()
    change = inp["change"]
    observed: dict[str, Any] = {}
    if inp.get("gate_fails_on_fresh_run"):
        p.fail_flag.touch()
        result = _run(p, reuse=False)
    elif change == "remove the SPEC approval stamp":
        doc = yaml.safe_load(y.read_text(encoding="utf-8"))
        doc.pop("approval", None)
        y.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        result = _run(p)
        observed["approval_ok"] = result["sections"]["approval"]["ok"]
    else:
        _review(p, "unresolved")
        result = _run(p)
        if change.endswith("then fixed"):
            assert result["sections"]["review"]["ok"] is False
            _review(p, "accepted")
            result = _run(p)
    observed["gates_ran"] = p.gate_runs() > before
    if "review_ok" in exp:
        observed["review_ok"] = result["sections"]["review"]["ok"]
    if "exit" in exp:
        observed["exit"] = result["exit"]
    if "exit_nonzero" in exp:
        observed["exit_nonzero"] = result["exit"] != 0
    if "record_kept" in exp:
        observed["record_kept"] = p.record() is not None
    assert observed == exp


# ── AC-002 ─────────────────────────────────────────────────────────────────────


def _seed_record(p: Proj, record: str) -> None:
    if record == "pass":
        _seed_pass(p)
    elif record == "none":
        return
    elif record.startswith("legacy"):
        _seed_pass(p)
        p.edit_record(files=_DROP)
    elif record.startswith("none written"):
        locked = p.root / "locked.txt"
        locked.write_text("x\n")
        p.commit("locked")
        locked.chmod(0)
        _run(p, reuse=False)
        assert p.record() is None
    else:
        raise AssertionError(record)


@pytest.mark.parametrize("row", _rows("AC-002"), ids=_rid)
def test_ac_002_rule_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: dict[str, Any]
) -> None:
    inp, exp = row["input"], row["expected"]
    if inp["record"].startswith("none written") and os.geteuid() == 0:
        pytest.skip("root reads unreadable files")
    decl: Any = inp["decl"]
    added_later = decl == "declaration added after the pass"
    if isinstance(decl, str) and not added_later:
        decl = decl.split(" ")[0]  # the bare-string row: "work-docs/** (bare string, ...)"
    p = _project(tmp_path, monkeypatch, decl=None if added_later else decl)
    try:
        _seed_record(p, inp["record"])
        if added_later:
            _write_cfg(p.root, ["CHANGELOG.md"])
        _apply(p, inp["change"])
        if inp["head"] == "moved":
            p.git("commit", "-q", "--allow-empty", "-m", "move")
        before = p.gate_runs()
        result = _run(p)
    finally:
        if (p.root / "locked.txt").exists():
            (p.root / "locked.txt").chmod(0o644)
    observed = {k: v for k, v in _observe(p, before, result).items() if k in exp}
    assert observed == exp, result.get("reuse_miss") or result.get("reuse")


# ── AC-003 ─────────────────────────────────────────────────────────────────────

_POOL = [
    "CHANGELOG.md", "README.md", "docs/a.md", "docs/sub/b.md", "work-docs/PLAN-x.md",
    "work-docs/tests/f.md", "src/a.py", "src/a.sql", "pyproject.toml", "sub/setup.cfg",
    "tests/data.json", "NOTES.txt", "x/pytest.ini",
]  # fmt: skip
_GLOBS = [
    "CHANGELOG.md", "*.md", "docs/**", "work-docs/**", "**", "**/*.md", "docs/*.md",
    "src/*", "*", "docs/?.md", "**/b.md",
]  # fmt: skip
_SHAS = ["a" * 64, "b" * 64, "c" * 64]
_DIGESTS = st.sampled_from([*_SHAS, "absent", "link:elsewhere", "unreadable:PermissionError"])
_SHA = re.compile(r"[0-9a-f]{64}")
_RUNNER = {"pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"}


def _oracle_match(pattern: str, path: str) -> bool:
    """Segment-wise recursive matcher, written apart from the module's regex translator."""

    def seg(p: str, s: str) -> bool:
        if not p:
            return not s
        if p[0] == "*":
            return any(seg(p[1:], s[i:]) for i in range(len(s) + 1))
        if not s:
            return False
        return (p[0] == "?" or p[0] == s[0]) and seg(p[1:], s[1:])

    def walk(ps: list[str], ss: list[str]) -> bool:
        if not ps:
            return not ss
        if ps[0] == "**":
            return any(walk(ps[1:], ss[i:]) for i in range(len(ss) + 1))
        return bool(ss) and seg(ps[0], ss[0]) and walk(ps[1:], ss[1:])

    return walk(pattern.split("/"), path.split("/"))


def _oracle_never(path: str) -> bool:
    parts = path.split("/")
    return (
        Path(path).suffix.lower() in check.CODE_SUFFIXES
        or any(x in ("tests", "test") for x in parts)
        or parts[-1] in _RUNNER
    )


@settings(max_examples=400, derandomize=True, deadline=None)
@given(
    recorded=st.dictionaries(st.sampled_from(_POOL), _DIGESTS, max_size=8),
    edits=st.dictionaries(st.sampled_from(_POOL), st.one_of(st.none(), _DIGESTS), max_size=4),
    decl=st.lists(st.sampled_from(_GLOBS), max_size=3),
    head_moved=st.booleans(),
    read_set=st.one_of(st.none(), st.lists(st.sampled_from(_POOL), max_size=3)),
    has_pytest=st.booleans(),
    key_same=st.booleans(),
)
def test_ac_003_never_unsafe(
    recorded: dict[str, str],
    edits: dict[str, str | None],
    decl: list[str],
    head_moved: bool,
    read_set: list[str] | None,
    has_pytest: bool,
    key_same: bool,
) -> None:
    current = dict(recorded)
    for path, digest in edits.items():
        if digest is None:
            current.pop(path, None)
        else:
            current[path] = digest
    key = {"slug": "s", "fingerprint": "f", "harness_maker_version": "v", "options": {}}
    record = {
        **key,
        "fingerprint": "f" if key_same else "other",
        "head": "h0",
        "files": recorded,
        "read_set": read_set,
        "gates": {"ok": True},
        "line": {"exit": 0},
    }
    got = check_reuse.decide(
        record,
        key=key,
        files=current,
        declaration=decl,
        head="h1" if head_moved else "h0",
        has_pytest_gate=has_pytest,
    )
    if not got.reuse:
        return
    delta = sorted(p for p in set(recorded) | set(current) if recorded.get(p) != current.get(p))
    identical = key_same and not head_moved and not delta
    inert = (
        bool(decl)
        and key_same
        and all(
            _SHA.fullmatch(recorded.get(p, "")) and _SHA.fullmatch(current.get(p, ""))
            for p in delta
        )
        and all(any(_oracle_match(g, p) for g in decl) for p in delta)
        and not any(_oracle_never(p) for p in delta)
        and not set(delta) & set(read_set or [])
        and (read_set is not None or not has_pytest)
    )
    assert identical or inert, (got, delta)


def test_ac_003_run_routes_through_decide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A refusing `decide` must make `run()` run the gate: no shortcut outside the function."""
    p = _project(tmp_path, monkeypatch, decl=D, gates="marker")
    _seed_pass(p)
    calls: list[Any] = []

    def refuse(*a: Any, **k: Any) -> check_reuse.Decision:
        calls.append(a)
        return check_reuse.Decision(reuse=False, reason="key")

    monkeypatch.setattr(check_reuse, "decide", refuse)
    before = p.gate_runs()
    _run(p)
    assert calls
    assert p.gate_runs() > before


# ── AC-004 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("row", _rows("AC-004"), ids=_rid)
def test_ac_004_voided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: dict[str, Any]
) -> None:
    inp, exp = row["input"], row["expected"]
    gate = inp["gate"]
    gates = {"pytest": "pytest", "pytest -n 2": "pytest", "non-pytest only": "marker"}.get(
        gate, "both"
    )
    p = _project(
        tmp_path,
        monkeypatch,
        decl=inp["decl"],
        gates=gates,
        opens=inp.get("test_opens"),
        xdist=gate == "pytest -n 2",
    )
    _seed_pass(p)
    if inp.get("test_opens"):
        recorded = p.record()
        assert recorded is not None
        assert "work-docs/data.md" in (recorded["read_set"] or [])
    if inp.get("read_set_missing"):
        p.edit_record(read_set=None)
    _apply(p, inp["change"])
    before = p.gate_runs()
    result = _run(p)
    observed = {k: v for k, v in _observe(p, before, result).items() if k in exp}
    if exp.get("unobserved") == ["<the non-pytest command>"]:
        exp = {**exp, "unobserved": [p.marker_cmd]}
    assert observed == exp, result.get("reuse_miss") or result.get("reuse")


# ── AC-005 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("row", _rows("AC-005"), ids=_rid)
def test_ac_005_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: dict[str, Any]
) -> None:
    inp, exp = row["input"], row["expected"]
    p = _project(tmp_path, monkeypatch, decl=inp.get("decl"), gates="pytest")
    _seed_pass(p)
    if "read-set null" in inp["case"]:
        p.edit_record(read_set=None)
    _apply(p, inp["change"])
    result = _run(p, reuse=not inp["case"].startswith("fresh run without"))
    if "has_reuse_miss" in exp:
        assert ("reuse_miss" in result) is exp["has_reuse_miss"]
        return
    if "reused" in exp:
        assert result.get("reused") is exp["reused"]
    for name in ("reuse", "reuse_miss"):
        if name in exp:
            got = result.get(name) or {}
            assert {k: got.get(k) for k in exp[name]} == exp[name], got


# ── AC-006 ─────────────────────────────────────────────────────────────────────


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


def _parse_row_yaml(text: str) -> dict[str, Any]:
    if text == "no check key":
        return {}
    parsed = yaml.safe_load(text)
    assert isinstance(parsed, dict)
    return parsed


@pytest.mark.parametrize("row", _rows("AC-006"), ids=_rid)
def test_ac_006_config(row: dict[str, Any]) -> None:
    inp, exp = row["input"], row["expected"]
    data = _parse_row_yaml(inp["yaml"])
    if inp.get("path", "").startswith("/hm:make"):
        a = interview(_profile(), autoloop_mode=True).model_copy(
            update={"check": CheckConfig.model_validate(data["check"])}
        )
        with tempfile.TemporaryDirectory() as d:
            first = Path(d) / "first" / ".claude"
            render(synthesize(_profile(), a), first, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
            reloaded = answers_from_harness_yaml(first / "harness.yaml")
            assert reloaded is not None
            second = Path(d) / "second" / ".claude"
            render(
                synthesize(_profile(), reloaded), second, dry_run=False,
                freeze_time=DEFAULT_FREEZE_TIME,
            )  # fmt: skip
            again = answers_from_harness_yaml(second / "harness.yaml")
            assert again is not None
            assert again.check.reuse_inert == exp["reuse_inert"]
        return
    if exp.get("rejected"):
        with pytest.raises(ValidationError):
            CheckConfig.model_validate(data["check"])
        assert check_reuse.parse_declaration(data) is None
        return
    cfg = CheckConfig.model_validate(data.get("check", {}))
    assert cfg.reuse_inert == exp["reuse_inert"]
    assert check_reuse.parse_declaration(data) == exp["reuse_inert"]
    if exp.get("round_trip_equal"):
        dumped = cfg.model_dump(mode="json")
        assert CheckConfig.model_validate(dumped) == cfg
        assert "check" in HarnessConfig.model_fields


def test_ac_006_default_render_has_no_check_key(tmp_path: Path) -> None:
    """A ≤0.65.2 reader rejects `check:`, so a default render must not emit it (ADR-005)."""
    a = interview(_profile(), autoloop_mode=True)
    render(synthesize(_profile(), a), tmp_path / ".claude", dry_run=False,
           freeze_time=DEFAULT_FREEZE_TIME)  # fmt: skip
    text = (tmp_path / ".claude" / "harness.yaml").read_text(encoding="utf-8")
    assert not re.search(r"^check:", text, re.M)


# ── review round 1 (REVIEW-hm-check-docs-only-reuse) ───────────────────────────


_LATE = {
    "dotdot": (
        "..notes.md",
        "def test_g():\n    assert open('..notes.md').read()\n",
        None,
    ),
    "unconfigure": (
        "work-docs/data.md",
        "def test_g():\n    assert True\n",
        "\n\ndef pytest_unconfigure(config):\n    open('work-docs/data.md').read()\n",
    ),
}


@pytest.mark.parametrize("case", sorted(_LATE))
def test_ac_004_late_and_dotdot_reads_are_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """A `..`-prefixed in-repo name and a read in a later hook both void the declaration."""
    target, test_body, conftest_extra = _LATE[case]
    p = _project(tmp_path, monkeypatch, decl=[target], gates="pytest")
    (p.root / "..notes.md").write_text("notes\n", encoding="utf-8")
    (p.root / "gate_tests" / "test_g.py").write_text(test_body, encoding="utf-8")
    if conftest_extra:
        with (p.root / "gate_tests" / "conftest.py").open("a", encoding="utf-8") as f:
            f.write(conftest_extra)
    p.commit("late")
    _seed_pass(p)
    recorded = p.record()
    assert recorded is not None
    assert target in (recorded["read_set"] or [])
    _append(p, target)
    before = p.gate_runs()
    result = _run(p)
    assert p.gate_runs() > before
    assert result["reuse_miss"] == {"reason": "voided", "paths": [target]}


def test_ac_005_identical_reprint_carries_no_reuse_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh run that missed under --reuse records a line an identical hit later reprints."""
    p = _project(tmp_path, monkeypatch, gates="pytest")
    first = _run(p)
    assert first["exit"] == 0
    assert first["reuse_miss"]["reason"] == "no-record"
    again = _run(p)
    assert again.get("reused") is True
    assert again["reuse"]["rule"] == "identical"
    assert "reuse_miss" not in again


def test_ac_006_preset_switch_keeps_check(tmp_path: Path) -> None:
    """`make --update --preset X` rebuilds answers from an allowlist; `check` must be on it."""
    from typer.testing import CliRunner

    from harness_maker.cli import app
    from harness_maker.io_utils import load_harness_yaml

    def make(repo: Path, *args: str) -> Any:
        before = os.getcwd()
        os.chdir(repo)
        try:
            return CliRunner().invoke(app, ["make", str(repo), "--autoloop", *args])
        finally:
            os.chdir(before)

    for preset_from, preset_to in (("Side", "Production"), ("Production", "Side")):
        repo = tmp_path / preset_from / "proj"
        repo.mkdir(parents=True)
        assert make(repo, "--preset", preset_from).exit_code == 0
        yml = repo / ".claude" / "harness.yaml"
        yml.write_text(
            yml.read_text(encoding="utf-8") + "check:\n  reuse_inert: [CHANGELOG.md]\n",
            encoding="utf-8",
        )
        res = make(repo, "--update", "--preset", preset_to)
        assert res.exit_code == 0, res.output
        assert load_harness_yaml(yml)["check"] == {"reuse_inert": ["CHANGELOG.md"]}
