"""SPEC-hm-overhaul-p1 AC-003: every 0.62 stage heading is disposed of according to its class.

The classes come from db19f023's own `step_sensitivity.REGISTRY`, loaded from `git show`, and the
dispositions from the SPEC's cut ledger table. A registry key the ledger does not name must still
render, with its ordinal, in the same stage at HEAD.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from harness_maker import step_sensitivity as ss
from harness_maker import synthesize
from harness_maker.interview import _build_answers
from harness_maker.models import DelegationConfig, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from tests._overhaul_p1_ref import REF_SHA, REPO_ROOT

SPEC = REPO_ROOT / "specs" / "SPEC-hm-overhaul-p1.md"
_HEADING = re.compile(r"^#{2,4} (.+)$", re.M)
_KEYWORD = {"Step": "Step", "Steps": "Step", "Phase": "Phase", "Phases": "Phase", "Check": "Check"}
_KEYWORD["Checks"] = "Check"


def _ref_registry(tmp: Path) -> ModuleType:
    source = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{REF_SHA}:src/harness_maker/step_sensitivity.py"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout
    path = tmp / "ref_step_sensitivity.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("ref_step_sensitivity", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ref_step_sensitivity"] = module
    spec.loader.exec_module(module)
    return module


def _expand(item: str) -> list[str]:
    """`2/4/6`, `1–4`, `4a–4d`, `C1–C3` → their members; anything else is itself."""
    if "/" in item:
        return item.split("/")
    m = re.fullmatch(r"([A-Z]?)(\d+)([a-z]?)–\1?(\d+)([a-z]?)", item)
    if m is None:
        return [item]
    prefix, lo, lo_l, hi, hi_l = m.groups()
    if lo_l and hi_l:
        return [f"{prefix}{lo}{chr(c)}" for c in range(ord(lo_l), ord(hi_l) + 1)]
    return [f"{prefix}{n}" for n in range(int(lo), int(hi) + 1)]


def parse_keys(cell: str) -> list[tuple[str, str]]:
    """`execute Phase D, Step 4.2, Checks 2/4/6` → registry keys. Non-ordinal rows give []."""
    if "(not ordinal)" in cell:
        return []
    cell = re.sub(r"\s*\(.*\)$", "", cell.strip())
    stage, _, rest = cell.partition(" ")
    keys: list[tuple[str, str]] = []
    keyword = ""
    for raw in rest.split(", "):
        words = raw.split(" ", 1)
        if words[0] in _KEYWORD:
            keyword = _KEYWORD[words[0]]
            raw = words[1]
        keys += [(stage, f"{keyword} {member}") for member in _expand(raw)]
    return keys


def ledger_rows(text: str) -> list[tuple[list[tuple[str, str]], str, str]]:
    body = text[text.index("## Cut ledger (AC-003)") :]
    body = body[: body.index("**Items that are not headings**")]
    out = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("Stage / heading", "---"):
            continue
        out.append((parse_keys(cells[0]), cells[1], cells[2]))
    return out


@pytest.fixture(scope="module")
def ref(tmp_path_factory: pytest.TempPathFactory) -> ModuleType:
    return _ref_registry(tmp_path_factory.mktemp("ref-ss"))


@pytest.fixture(scope="module")
def ledger() -> list[tuple[list[tuple[str, str]], str, str]]:
    return ledger_rows(SPEC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> set[tuple[str, str]]:
    """Ordinals HEAD renders over default Side and Production, plus every opt-in that adds one."""
    keys: set[tuple[str, str]] = set()
    for i, preset in enumerate(Preset):
        for extra in ({}, {"worktree_enabled": True}):
            answers = _build_answers(
                locale="en", targets=[Target.CLAUDE_CODE], preset=preset, **extra
            ).model_copy(update={"delegation": DelegationConfig(stages=["wrapup"])})
            out = tmp_path_factory.mktemp(f"arm{i}{len(extra)}")
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(synthesize, "_compute_install_ref", lambda: "$HOME/harness-maker")
                render(
                    synthesize.synthesize(ProjectProfile(), answers, preset=preset),
                    out,
                    freeze_time=DEFAULT_FREEZE_TIME,
                )
            for stage in ss.STAGES:
                text = (out / "commands" / "hm" / f"{stage}.md").read_text(encoding="utf-8")
                headings = [h.strip() for h in _HEADING.findall(text)]
                keys |= {(stage, o) for o in ss.ordinals_from_headings(headings)}
    return keys


def test_ledger_parser_reads_ranges_and_lists() -> None:
    assert parse_keys("review Steps C1–C3") == [("review", f"Step C{n}") for n in (1, 2, 3)]
    assert parse_keys("execute Phase D, Step 4.2, Checks 2/4/6") == [
        ("execute", "Phase D"),
        ("execute", "Step 4.2"),
        ("execute", "Check 2"),
        ("execute", "Check 4"),
        ("execute", "Check 6"),
    ]
    assert parse_keys("review Steps 3.5, 3.6, 4, 4a–4d")[-1] == ("review", "Step 4d")
    assert parse_keys("spec Step 2 (the `lane: light` one-round mode)") == [("spec", "Step 2")]
    assert parse_keys("execute Session Context Loading (not ordinal)") == []


def test_ac003_ledger_covers_db19f023_registry(
    ref: ModuleType,
    ledger: list[tuple[list[tuple[str, str]], str, str]],
    rendered: set[tuple[str, str]],
) -> None:
    ref_keys = {e.key for e in ref.REGISTRY}
    in_ledger = {k for keys, _, _ in ledger for k in keys}
    assert in_ledger <= ref_keys, sorted(in_ledger - ref_keys)
    unlisted_missing = sorted(k for k in ref_keys - in_ledger if k not in rendered)
    assert unlisted_missing == [], (
        f"not in the ledger, so KEPT, yet not rendered: {unlisted_missing}"
    )
    classes = {e.key: e.cls for e in ref.REGISTRY}
    bad: list[str] = []
    for keys, _cls, disposition in ledger:
        for key in keys:
            cls = classes[key]
            if disposition.startswith("CUT-COMP") and cls != "COMP":
                bad.append(f"{key}: CUT-COMP on {cls}")
            if disposition.startswith("CUT-HOST") and cls != "HOST":
                bad.append(f"{key}: CUT-HOST on {cls}")
            if cls == "TUNE" and "TUNE-M" not in disposition and "DRI" not in disposition:
                bad.append(f"{key}: TUNE without a measurement or DRI")
            if disposition.startswith("VACUOUS") and ":" not in disposition:
                bad.append(f"{key}: VACUOUS names no cause")
            if disposition.startswith("KEPT") and key not in rendered:
                bad.append(f"{key}: KEPT but not rendered")
    assert bad == []


def _moved_owner_holds(disposition: str, texts: dict[str, str]) -> bool:
    if "`hm check --red`" in disposition:
        return "hm check --red" in texts["execute"]
    if "`hm check`" in disposition:
        return "hm check --slug" in texts["execute"] and "hm check --slug" in texts["wrapup"]
    if "execute's review step" in disposition:
        return "## Step 6 — Review" in texts["execute"] and "disposition" in texts["execute"]
    if "MOVED to execute" in disposition:
        return "mark-tested" in texts["execute"]
    return False


def test_ac003_no_inv_heading_is_cut(
    ref: ModuleType,
    ledger: list[tuple[list[tuple[str, str]], str, str]],
    rendered: set[tuple[str, str]],
    tmp_path: Path,
) -> None:
    classes = {e.key: e.cls for e in ref.REGISTRY}
    answers = _build_answers(locale="en", targets=[Target.CLAUDE_CODE], preset=Preset.SIDE)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(synthesize, "_compute_install_ref", lambda: "$HOME/harness-maker")
        render(
            synthesize.synthesize(ProjectProfile(), answers, preset=Preset.SIDE),
            tmp_path,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
    texts = {
        s: (tmp_path / "commands" / "hm" / f"{s}.md").read_text(encoding="utf-8") for s in ss.STAGES
    }
    bad: list[str] = []
    for keys, _cls, disposition in ledger:
        for key in keys:
            if classes[key] != "INV":
                continue
            if not re.match(r"(KEPT|MOVED|VACUOUS|DRI)\b", disposition):
                bad.append(f"{key}: {disposition[:40]}")
            if disposition.startswith("MOVED") and not _moved_owner_holds(disposition, texts):
                bad.append(f"{key}: the new owner lacks the moved function")
    for key, cls in classes.items():
        listed = any(key in keys for keys, _, _ in ledger)
        if cls == "INV" and not listed and key not in rendered:
            bad.append(f"{key}: INV, unlisted and gone")
    assert bad == []


def test_ac003_negative_control_cut_inv_is_flagged() -> None:
    """A CUT disposition on an INV key fails the pattern the test applies."""
    assert re.match(r"(KEPT|MOVED|VACUOUS|DRI)\b", "CUT-COMP") is None
    assert not _moved_owner_holds("MOVED to `hm check`", {"execute": "", "wrapup": ""})
