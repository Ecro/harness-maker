"""SPEC-hm-light-lane-s3a AC-001, AC-002, AC-010, AC-012 — the light lane's one reader.

AC-001 and AC-002's rows come from the machine SPEC's golden tables (each `case` string is
mapped to a fixture below). AC-012's rows other than the first are the e7dd6648 digest's own
output on the same fixtures (`digest_e7dd6648.json`, captured before the edit).
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from fnmatch import fnmatch
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import light_lane, world_model_digest
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import ProjectProfile
from harness_maker.observability import verification_cache
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.spec_machine import load
from harness_maker.synthesize import synthesize
from tests.structural._surface_baseline import HARNESS_YAML, pinned_install_ref
from tests.unit import light_lane_s3a_fixture as fx

REPO = Path(__file__).parents[2]
SPEC_YAML = REPO / "specs" / "SPEC-hm-light-lane-s3a.machine.yaml"
DIGEST = json.loads(
    (REPO / "tests/fixtures/light_lane_s3a/digest_e7dd6648.json").read_text(encoding="utf-8")
)
SLUG = fx.SLUG
IRR = [{"id": "IRR-001", "decision": "d", "category": "c", "rationale": "r", "source": "spec"}]


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HARNESS_MAKER_CACHE_DIR", str(home / "cache"))
    monkeypatch.setattr(verification_cache, "_tool_versions", lambda root: {})


def _golden_cases(ac_id: str) -> list[str]:
    machine = load(SPEC_YAML)
    ac = next(a for a in machine.ac if a.id == ac_id)
    return [str(row.input["case"]) for row in ac.golden_table]


# ── AC-001 ─────────────────────────────────────────────────────────────────

#: AC-001 case → [(lane kind, irreversible list, slug argument, put the SPEC in the worktree)].
LANE_FIXTURES: dict[str, list[tuple[str, list[dict[str, str]] | None, str | None, bool]]] = {
    "lane light, approval_state approved, irreversible_decisions []": [
        ("light", None, SLUG, False)
    ],
    "lane light, approval_state exempt, irreversible_decisions []": [("exempt", None, SLUG, False)],
    "lane light, approval_state missing (no approval written, e.g. auto_full)": [
        ("untrusted", None, SLUG, False)
    ],
    "lane light, approval_state invalid (edited after approval)": [("invalid", None, SLUG, False)],
    "lane light, approval_state approved, irreversible_decisions [IRR-001]": [
        ("light", IRR, SLUG, False)
    ],
    "lane light, schema_version 2 without irreversible_decisions (state legacy)": [
        ("legacy", None, SLUG, False)
    ],
    "lane light, SPEC-<slug>.md without a machine yaml (state malformed)": [
        ("md_only", None, SLUG, False)
    ],
    "lane full, approved, no irreversible decisions": [("full", None, SLUG, False)],
    "no lane key, approved, no irreversible decisions": [("absent", None, SLUG, False)],
    "lane Light, lane 'light ' or lane true, approved": [
        ("Light", None, SLUG, False),
        ("light_space", None, SLUG, False),
        ("light_true", None, SLUG, False),
    ],
    "unparseable SPEC-<slug>.md frontmatter": [("unparseable", None, SLUG, False)],
    "no SPEC-<slug>.md, or slug None, '..' or containing '/'": [
        ("none", None, SLUG, False),
        ("light", None, None, False),
        ("light", None, "..", False),
        ("light", None, "a/b", False),
    ],
    "approved light SPEC only in the per-task worktree checkout, not the base": [
        ("light", None, SLUG, True)
    ],
}
LANE_EXPECTED = {
    str(row.input["case"]): row.expected
    for row in next(a for a in load(SPEC_YAML).ac if a.id == "AC-001").golden_table
}


def test_lane_table_covers_the_spec() -> None:
    assert set(LANE_FIXTURES) == set(_golden_cases("AC-001"))


@pytest.mark.parametrize("case", list(LANE_FIXTURES))
def test_lane_of(tmp_path: Path, case: str) -> None:
    for i, (lane, irreversible, slug, in_worktree) in enumerate(LANE_FIXTURES[case]):
        base = tmp_path / f"base{i}"
        fx.init_repo(base)
        checkout = base / ".worktrees" / SLUG if in_worktree else base
        if in_worktree:
            fx.init_repo(checkout)
        fx.write_spec(checkout, lane, irreversible=irreversible)
        assert light_lane.lane_of(base, slug) == LANE_EXPECTED[case], (lane, slug)


# ── AC-002 ─────────────────────────────────────────────────────────────────

#: AC-002 case → [(lane kind, record kind, where: base | worktree | base-with-worktree)].
RECORD_FIXTURES: dict[str, list[tuple[str, str, str]]] = {
    "trusted light lane, newest REVIEW-<slug>-<date>.md is review_kind light-check, status PASSED,"
    " task_slug <slug>": [("light", "passed", "base")],
    "same record, lane full or untrusted (approval missing)": [
        ("full", "passed", "base"),
        ("untrusted", "passed", "base"),
    ],
    "newest record is a real review (no review_kind)": [("light", "real_newest", "base")],
    "newest record is a PASSED light-check, an older-dated real review exists for the slug": [
        ("light", "real_beside", "base")
    ],
    "light-check record with status FAILED or no status": [
        ("light", "failed", "base"),
        ("light", "no_status", "base"),
    ],
    "light-check record whose task_slug is another slug": [("light", "other_slug", "base")],
    "REVIEW-<slug>-extra-<date>.md for a hyphen-prefix sibling slug only": [
        ("light", "sibling_only", "base")
    ],
    "no REVIEW record, or unparseable record frontmatter": [
        ("light", "none", "base"),
        ("light", "unparseable", "base"),
    ],
    "PASSED record and approved light SPEC exist only in the per-task worktree <WT>/work-docs/": [
        ("light", "passed", "worktree")
    ],
    "PASSED record only in the base checkout while a per-task worktree for the slug exists": [
        ("light", "passed", "base-with-worktree")
    ],
}
RECORD_EXPECTED = {
    str(row.input["case"]): row.expected
    for row in next(a for a in load(SPEC_YAML).ac if a.id == "AC-002").golden_table
}


def test_record_table_covers_the_spec() -> None:
    assert set(RECORD_FIXTURES) == set(_golden_cases("AC-002"))


@pytest.mark.parametrize("case", list(RECORD_FIXTURES))
def test_light_check_passed(tmp_path: Path, case: str) -> None:
    created = datetime.now(UTC)
    for i, (lane, record, where) in enumerate(RECORD_FIXTURES[case]):
        base = tmp_path / f"base{i}"
        fx.init_repo(base)
        if where == "worktree":
            checkout = base / ".worktrees" / SLUG
            fx.init_repo(checkout)
            fx.write_spec(checkout, lane)
            fx.write_record(checkout, record, marker_created=created)
        else:
            checkout = base
            fx.write_spec(base, lane)
            fx.write_record(base, record, marker_created=created)
            if where == "base-with-worktree":
                wt = base / ".worktrees" / SLUG
                fx.init_repo(wt)
                fx.write_spec(wt, lane)
                fx.mark_fresh(wt)
        fx.mark_fresh(checkout)
        assert light_lane.light_check_passed(base, SLUG) is RECORD_EXPECTED[case], (lane, record)


def test_review_records_moved_from_the_digest(tmp_path: Path) -> None:
    docs = tmp_path / "work-docs"
    docs.mkdir()
    for name in ("REVIEW-demo-2026-10-15.md", "REVIEW-demo-extra-2026-10-15.md", "REVIEW-demo.md"):
        (docs / name).write_text("---\n---\n")
    assert light_lane.review_records(docs, "demo") == [docs / "REVIEW-demo-2026-10-15.md"]
    assert world_model_digest._reviews(docs, "demo") == light_lane.review_records(docs, "demo")


# ── AC-010 ─────────────────────────────────────────────────────────────────


@cache
def _light_check_reference(wt_on: bool) -> str:
    base = answers_from_harness_yaml(HARNESS_YAML)
    assert base is not None
    answers = base.model_copy(update={"worktree": {**base.worktree, "enabled": wt_on}})
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with pinned_install_ref():
            render(
                synthesize(ProjectProfile(), answers),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        text: str = (root / ".claude/hm/execute-light-check.md").read_text(encoding="utf-8")
        return text


def _record_example(text: str) -> str:
    blocks: list[str] = re.findall(r"```yaml\n(.*?)```", text, re.S)
    return next(b for b in blocks if "review_kind: light-check" in b)


RECORD_DIR = {True: "<WT>/work-docs/", False: "./work-docs/"}
RENDERS = json.loads(
    (REPO / "tests/fixtures/light_lane_s3a/renders_e7dd6648.json").read_text(encoding="utf-8")
)
#: A backticked frontmatter path in a reader's text: `drift_verdict`, `drift_verdict.task_slug`.
READ_FIELD = re.compile(r"`((?:drift_verdict|task_slug)(?:\.\w+)*)`")


def _readers(wt_on: bool) -> list[str]:
    """wrapup Step 3 and verify Check 1 at e7dd6648, for every config with this worktree arm."""
    texts: list[str] = []
    for key, cfg in RENDERS["configs"].items():
        if ("/wt-on/" in key) is wt_on:
            for readers in cfg["record_readers"].values():
                texts += [RENDERS["texts"][sha] for sha in readers.values()]
    return texts


def _lookup(fm: dict[str, Any], path: str) -> Any:
    node: Any = fm
    for part in path.split("."):
        assert isinstance(node, dict), path
        assert part in node, path
        node = node[part]
    return node




# ── AC-012 ─────────────────────────────────────────────────────────────────

DIGEST_EXPECTED = {
    name: ("wrapup" if i == 0 else DIGEST["cases"][name])
    for i, (name, *_rest) in enumerate(fx.DIGEST_CASES)
}


@pytest.mark.parametrize(("name", "lane", "record", "fresh"), fx.DIGEST_CASES)
def test_digest_routes_checked_light_task_to_wrapup(
    tmp_path: Path, name: str, lane: str, record: str, fresh: bool
) -> None:
    root = tmp_path / "repo"
    fx.build_digest(root, lane, record, fresh)
    assert world_model_digest.next_stage(root, SLUG, root) == DIGEST_EXPECTED[name]


def test_digest_rows_match_the_spec_table() -> None:
    expected = [
        row.expected for row in next(a for a in load(SPEC_YAML).ac if a.id == "AC-012").golden_table
    ]
    assert list(DIGEST_EXPECTED.values()) == expected


# ── AC-015: the light lane is bound to the lane the SPEC was accepted on ───────────────


def _flip(checkout: Path, lane: str) -> None:
    md = checkout / "specs" / f"SPEC-{SLUG}.md"
    md.write_text(md.read_text(encoding="utf-8").replace("lane: light\n", f"lane: {lane}\n"))


def _flip_full_to_light(checkout: Path) -> None:
    md = checkout / "specs" / f"SPEC-{SLUG}.md"
    md.write_text(md.read_text(encoding="utf-8").replace("lane: full\n", "lane: light\n"))


def _strip_stamp_lane(checkout: Path) -> None:
    yml = checkout / "specs" / f"SPEC-{SLUG}.machine.yaml"
    raw = yaml.safe_load(yml.read_text(encoding="utf-8"))
    raw["approval"].pop("lane", None)
    yml.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _exempt_full(checkout: Path) -> None:
    from harness_maker import spec_machine

    fx.write_spec(checkout, "untrusted")
    md = checkout / "specs" / f"SPEC-{SLUG}.md"
    md.write_text(md.read_text(encoding="utf-8").replace("lane: light\n", "lane: full\n"))
    spec_machine.approve(checkout / "specs" / f"SPEC-{SLUG}.machine.yaml", exempt=True)


def _full_then_light(c: Path) -> None:
    fx.write_spec(c, "full")
    _flip_full_to_light(c)


def _exempt_full_then_light(c: Path) -> None:
    _exempt_full(c)
    _flip_full_to_light(c)


def _old_stamp(c: Path) -> None:
    fx.write_spec(c, "light")
    _strip_stamp_lane(c)


def _light_then_full(c: Path) -> None:
    fx.write_spec(c, "light")
    _flip(c, "full")


#: AC-015 case → (build the SPEC, expected lane, expected stamp lane).
BINDING_FIXTURES: dict[str, tuple[Callable[[Path], None], str, str | None]] = {
    "lane full approved, then the .md flipped to light": (_full_then_light, "full", "full"),
    "lane full stamped exempt, then the .md flipped to light": (
        _exempt_full_then_light,
        "full",
        "full",
    ),
    "lane light approved by a stamp written before the lane field (no approval.lane)": (
        _old_stamp,
        "full",
        None,
    ),
    "lane light approved, then the .md flipped to full": (_light_then_full, "full", "light"),
    "lane light approved": (lambda c: fx.write_spec(c, "light"), "light", "light"),
    "lane light stamped exempt": (lambda c: fx.write_spec(c, "exempt"), "light", "light"),
}
BINDING_EXPECTED = {
    str(row.input["case"]): row.expected
    for row in next(a for a in load(SPEC_YAML).ac if a.id == "AC-015").golden_table
}


def test_binding_table_covers_the_spec() -> None:
    assert set(BINDING_FIXTURES) == set(BINDING_EXPECTED)


@pytest.mark.parametrize("case", list(BINDING_FIXTURES))
def test_lane_is_bound_to_the_approved_lane(
    tmp_path: Path, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_maker import spec_machine

    build, lane, stamp_lane = BINDING_FIXTURES[case]
    base = tmp_path / "repo"
    fx.init_repo(base)
    build(base)
    approval = load(base / "specs" / f"SPEC-{SLUG}.machine.yaml").approval
    assert approval is not None
    assert approval.lane == stamp_lane
    assert light_lane.lane_of(base, SLUG) == lane == BINDING_EXPECTED[case]
    # Execute Step 4.2 gates on the same predicate through `approval-status` (2026-10-15,
    # confirmation pass item 1): its additive `trusted_lane` is `lane_of`'s answer.
    capsys.readouterr()
    assert spec_machine.main(["approval-status", "--root", str(base), "--slug", SLUG]) == 0
    status = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert status["trusted_lane"] == lane


def test_the_stamp_lane_releases_no_stamp_and_keeps_the_cli_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`approval` is outside the content hash, so the field moves no stamp; an old stamp written
    back stays without it; the CLI keeps its four keys (IRR-005 is a disk-format extension)."""
    from harness_maker import spec_machine

    base = tmp_path / "repo"
    fx.init_repo(base)
    fx.write_spec(base, "light")
    yml = base / "specs" / f"SPEC-{SLUG}.machine.yaml"
    assert spec_machine.approval_state(base, SLUG).state == "approved"
    _strip_stamp_lane(base)
    assert spec_machine.approval_state(base, SLUG).state == "approved"
    spec_machine._dump_machine_yaml(yml, load(yml))
    assert "lane" not in yaml.safe_load(yml.read_text(encoding="utf-8"))["approval"]
    capsys.readouterr()
    assert spec_machine.main(["approve", "--yaml", str(yml), "--exempt"]) == 0
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert set(printed) == {"kind", "content_hash", "approved_by", "approved_at"}
    stamp = load(yml).approval
    assert stamp is not None
    assert stamp.lane == "light"


# ── AC-016: a record counts only for the tree it checked, with its own checks passing ──

#: AC-016 case → [(record kind, run marker writer)]; every fixture is a trusted light lane, a
#: run marker for the current tree, and `since` = the marker time the records are built around.
READER_FIXTURES: dict[str, list[tuple[str, str | None]]] = {
    "PASSED record, verification_key = the current relevant key, computed_at after since": [
        ("passed", "run")
    ],
    "computed_at exactly equal to since": [("at_since", "run")],
    "computed_at one second before since": [("second_before", "run")],
    "computed_at without a zone, or a date only": [
        ("naive_computed_at", "run"),
        ("date_only", "run"),
    ],
    "verification_key missing, or not the current relevant key": [
        ("no_key", "run"),
        ("other_key", "run"),
    ],
    "the cache marker was written by mark-pass, not run": [("passed", None)],
    "checks.regression or checks.security not pass": [
        ("regression_fail", "run"),
        ("security_fail", "run"),
    ],
    "checks.mechanical not pass/n-a, or checks.spec_requirement not pass/warn/n-a": [
        ("mechanical_fail", "run"),
        ("spec_requirement_fail", "run"),
    ],
    "drift_verdict.result scope_violation or scenario_miss": [
        ("drift_scope", "run"),
        ("drift_scenario", "run"),
    ],
    "drift_verdict.task_slug another slug, the top-level task_slug this one": [
        ("nested_slug", "run")
    ],
}
READER_EXPECTED = {
    str(row.input["case"]): row.expected
    for row in next(a for a in load(SPEC_YAML).ac if a.id == "AC-016").golden_table
}


def test_reader_table_covers_the_spec() -> None:
    assert set(READER_FIXTURES) == set(READER_EXPECTED)


@pytest.mark.parametrize("case", list(READER_FIXTURES))
def test_record_is_bound_to_the_checked_tree(tmp_path: Path, case: str) -> None:
    since = datetime.now(UTC).replace(microsecond=0)
    for i, (record, writer) in enumerate(READER_FIXTURES[case]):
        base = tmp_path / f"base{i}"
        fx.init_repo(base)
        fx.write_spec(base, "light")
        fx.write_record(base, record, marker_created=since)
        fx.mark_fresh(base, writer=writer)
        got = light_lane.light_check_passed(base, SLUG, since=since.isoformat())
        assert got is READER_EXPECTED[case], record
