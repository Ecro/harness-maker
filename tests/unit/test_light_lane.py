"""SPEC-hm-light-lane-s3a AC-001, AC-002, AC-010, AC-012 — the light lane's one reader.

AC-001 and AC-002's rows come from the machine SPEC's golden tables (each `case` string is
mapped to a fixture below). AC-012's rows other than the first are the e7dd6648 digest's own
output on the same fixtures (`digest_e7dd6648.json`, captured before the edit).
"""

from __future__ import annotations

import json
import re
import tempfile
from datetime import UTC, datetime
from fnmatch import fnmatch
from functools import cache
from pathlib import Path

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


@pytest.mark.parametrize("wt_on", [True, False], ids=["wt-on", "wt-off"])
@pytest.mark.parametrize("spec_requirement", ["pass", "warn", "n-a"])
def test_record_satisfies_wrapup_and_verify(
    tmp_path: Path, wt_on: bool, spec_requirement: str
) -> None:
    text = _light_check_reference(wt_on)
    record_path_line = next(
        ln for ln in text.splitlines() if "REVIEW-{slug}-{date}.md" in ln and "Write" in ln
    )
    assert RECORD_DIR[wt_on] in record_path_line
    example = (
        _record_example(text)
        .replace("{slug}", SLUG)
        .replace("{YYYY-MM-DD}", fx.RECORD_DATE)
        .replace("<ISO timestamp>", datetime.now(UTC).isoformat())
        .replace("pass | warn | n-a", spec_requirement)
        .replace("pass | n-a", "pass")
    )
    fm = yaml.safe_load(example.strip().strip("-"))
    assert fm["drift_verdict"]["task_slug"] == SLUG
    assert fm["drift_verdict"]["result"] == "clean"
    assert "computed_at" in fm["drift_verdict"]
    assert fm["review_kind"] == "light-check"
    assert fm["status"] == "PASSED"
    assert fm["checks"]["spec_requirement"] in {"pass", "warn", "n-a"}
    assert fm["checks"]["structural"] == "not-run"
    base = tmp_path / "repo"
    fx.init_repo(base)
    fx.write_spec(base, "light")
    docs = base / "work-docs"
    docs.mkdir()
    record = docs / f"REVIEW-{SLUG}-{fx.RECORD_DATE}.md"
    record.write_text(example if example.startswith("---") else f"---\n{example}---\n")
    fx.mark_fresh(base)
    assert light_lane.light_check_passed(base, SLUG)
    assert fnmatch(record.name, "REVIEW-" + SLUG + "-*.md")
    assert world_model_digest._reviews(docs, SLUG) == [record]


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
