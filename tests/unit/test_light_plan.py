"""SPEC-hm-light-lane-s3c AC-012..014 — the short light PLAN and the minimal light machine.yaml.

AC-012/013: the fixture is derived from the light template the render ships, filled mechanically
from the SPEC's S9 value table (bench t1, written before the template existed), then given Step
0.1's real `spec_need frontmatter-upsert`. The readers run on it are a7403f2f code, unchanged:
`autopilot_caps._plan_link`, `wrapup_land.stage_manifest` (the PLAN `--required` path) and the
admitted-form grammar of `test_contract_boundaries_section`. The prose readers (wrapup, verify,
review, the verify-before-completion skill) are represented by the keys the SPEC's reader table
says each one reads.

AC-014: minimal light machine.yamls holding only the keys the SPEC's Outcomes list, written from
the SPEC text, run through the real `check --all`, `approve`, `approval-status` and `mark-tested`.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.unit import light_lane_s3a_fixture as s3a
from tests.unit import light_lane_s3c_fixture as fx

LIGHT_OPEN, LIGHT_CLOSE = "<!-- @hm:light-plan -->", "<!-- @hm:/light-plan -->"
SLUG = "format-max-units"
#: The SPEC's S9 value table.
T1_SCALARS = {
    "{slug}": SLUG,
    "{YYYY-MM-DD}": "2026-10-14",
    "<id>": "TIMEPARSE-UNITS",
    "{M}": "2",
    "{summary}": "format_duration gains max_units to cap the number of emitted units",
}
T1_PHASES = (
    (
        "max_units parameter",
        "`timeparse/format.py`, `tests/test_format.py`",
        "pytest tests/test_format.py -q",
        "low",
        "revert",
    ),
    (
        "CLI flag",
        "`timeparse/cli.py`, `tests/test_cli.py`",
        "pytest tests/test_cli.py -q",
        "low",
        "revert",
    ),
)
T1_BOUNDARIES = (("timeparse/parse.py", "parsing grammar is out of scope"),)
T1_ADRS = (
    ("truncate, never round, the dropped units", "user (source: SPEC S2)"),
    ("max_units=None keeps today's output", "agent"),
)
T1_SPEC_NEED = ("add", "SPEC-format-max-units")
PLAN_REL = f"work-docs/PLAN-{SLUG}.md"


@cache
def _execute_renders() -> tuple[str, str]:
    files = fx.render_files(fx._answers(lambda _b: {}))
    claude, codex = files["commands/hm/execute.md"], files["skills/hm-execute"]
    assert claude is not None
    assert codex is not None
    return claude, codex


def _light_span(text: str) -> str:
    i = text.index(LIGHT_OPEN)
    return text[i : text.index(LIGHT_CLOSE, i) + len(LIGHT_CLOSE)]


def extract_fenced_template(span: str) -> str:
    i = span.index("```markdown\n") + len("```markdown\n")
    return span[i : span.index("\n```", i) + 1]


def fill(template: str) -> str:
    """Substitute the S9 values; repeat the phase, boundary and ADR lines once per row."""
    out: list[str] = []
    for line in template.splitlines():
        if line.startswith("research_doc:"):
            continue  # no RESEARCH ran for t1
        rows: list[str]
        if "{N}" in line:
            rows = [
                line.replace("{N}", str(n))
                .replace("{name}", name)
                .replace("{files}", files)
                .replace("{command}", command)
                .replace("{risk}", risk)
                .replace("{rollback}", rollback)
                for n, (name, files, command, risk, rollback) in enumerate(T1_PHASES, 1)
            ]
        elif "{path}" in line:
            rows = [line.replace("{path}", p).replace("{why}", w) for p, w in T1_BOUNDARIES]
        elif "{NNN}" in line:
            rows = [
                line.replace("{NNN}", f"{n:03d}")
                .replace("{decision}", d)
                .replace("{provenance}", p)
                for n, (d, p) in enumerate(T1_ADRS, 1)
            ]
        else:
            rows = [line]
        for row in rows:
            for k, v in T1_SCALARS.items():
                row = row.replace(k, v)
            out.append(row)
    return "\n".join(out) + "\n"


def _upsert(checkout: Path) -> dict[str, Any]:
    from harness_maker import spec_need

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = spec_need.main(
            [
                "frontmatter-upsert",
                "--plan",
                str(checkout / PLAN_REL),
                "--root",
                str(checkout),
                "--verdict",
                T1_SPEC_NEED[0],
                "--target",
                T1_SPEC_NEED[1],
            ]
        )
    assert rc == 0, buf.getvalue()
    doc: dict[str, Any] = json.loads(buf.getvalue())
    return doc


@pytest.fixture
def light_plan(tmp_path: Path) -> tuple[Path, str]:
    """LIGHT_PLAN_FIXTURE in a committed checkout, after the real Step 0.1 upsert."""
    claude, codex = _execute_renders()
    assert _light_span(claude) == _light_span(codex), "one source for both arms"
    filled = fill(extract_fenced_template(_light_span(claude)))
    assert not re.search(r"\{[A-Za-z-]+\}|<id>", filled), filled
    checkout = tmp_path / "checkout"
    s3a.init_repo(checkout)
    (checkout / "work-docs").mkdir()
    (checkout / PLAN_REL).write_text(filled, encoding="utf-8")
    assert _upsert(checkout)["wrote"] is True
    return checkout, (checkout / PLAN_REL).read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, Any]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m is not None, text[:80]
    doc: dict[str, Any] = yaml.safe_load(m.group(1))
    return doc


def _section(text: str, heading: str) -> str:
    i = text.index(heading + "\n") + len(heading) + 1
    nxt = re.search(r"^## ", text[i:], re.M)
    return text[i : i + nxt.start()] if nxt else text[i:]


# ── AC-014: the minimal light machine.yaml ────────────────────────────────────

RUBRIC = "light-rubric"
EVIDENCE = (
    "rows written by hand from the SPEC table before the code exists, compared against a golden "
    "captured from the reference implementation"
)
MD_TEMPLATE = """---
type: spec
task_slug: {slug}
status: approved
tier: {tier}
lane: light
test_framework: pytest
---

# SPEC — {slug}

## Intent

The feature caps the emitted units; the requirement and the constraint are stated below.

## In-Scope Scenarios

### S1: the cap holds
**Given** a duration **When** it is formatted **Then** the observable output has at most N units

## Non-Goals

- Out-of-scope: the parsing grammar. The scope boundary is the formatter; edge case: zero.

## Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_one` (pytest assert) |

### AC-001: the formatter caps the units
### AC-002: the cap table holds
### AC-003: the help text reads clearly
### AC-004: formatting twice is idempotent
"""


def _minimal(tier: int, slug: str) -> dict[str, Any]:
    """Only the keys SPEC Outcomes C lists for a light Step 3.5."""
    doc: dict[str, Any] = {
        "schema_version": 3,
        "spec_slug": slug,
        "verification_tier": tier,
        "irreversible_decisions": [],
    }
    if tier == 1:
        doc["mutation_threshold"] = 85
        doc["paths_to_mutate"] = ["src/app.py"]
    common = {"oracle_source": "golden", "oracle_evidence": EVIDENCE}
    doc["ac"] = [
        {
            "id": "AC-001",
            "title": "the formatter caps the units",
            "type": "mechanical",
            "executable_predicate": "len(format_duration(3700, max_units=1).split()) == 1",
            "pending_test": True,
            **common,
        },
        {
            "id": "AC-002",
            "title": "the cap table holds",
            "type": "parametric",
            "golden_table": [
                {"input": {"seconds": 3700, "max_units": 1}, "expected": "1h"},
                {"input": {"seconds": 3700, "max_units": 2}, "expected": "1h 1m"},
            ],
            "pending_test": True,
            **common,
        },
        {
            "id": "AC-003",
            "title": "the help text reads clearly",
            "type": "judgment",
            "rubric_id": RUBRIC,
            "judgment_subject_paths": ["src/app.py"],
            **{**common, "oracle_source": "rubric"},
        },
        {
            "id": "AC-004",
            "title": "formatting twice is idempotent",
            "type": "property",
            "input_domain": "non-negative integer seconds",
            "transformation": "format then parse then format",
            "expected_relation": "format(parse(format(x))) == format(x)",
            "observable_output": "str",
            "pending_test": True,
            **{**common, "oracle_source": "property"},
        },
    ]
    return doc


TEST_IDS = {
    "AC-001": "tests/test_app.py::test_one",
    "AC-002": "tests/test_app.py::test_two",
    "AC-004": "tests/test_app.py::test_four",
}


def _spec_checkout(root: Path, tier: int) -> tuple[Path, Path, str]:
    slug = f"light-t{tier}"
    s3a.init_repo(root)
    specs = root / "specs"
    specs.mkdir()
    (root / ".claude" / "rubrics").mkdir(parents=True)
    (root / ".claude" / "rubrics" / f"{RUBRIC}.yaml").write_text("name: x\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text(
        "def test_one():\n    pass\n\n\ndef test_two():\n    pass\n\n\ndef test_four():\n"
        "    pass\n",
        encoding="utf-8",
    )
    yml = specs / f"SPEC-{slug}.machine.yaml"
    md = specs / f"SPEC-{slug}.md"
    yml.write_text(yaml.safe_dump(_minimal(tier, slug), sort_keys=False), encoding="utf-8")
    md.write_text(MD_TEMPLATE.format(slug=slug, tier=tier), encoding="utf-8")
    return yml, md, slug


def _main(argv: list[str]) -> tuple[int, str]:
    from harness_maker import spec_machine

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = spec_machine.main(argv)
    return rc, buf.getvalue()


def _status(root: Path, slug: str) -> dict[str, Any]:
    rc, out = _main(["approval-status", "--root", str(root), "--slug", slug])
    assert rc == 0, out
    doc: dict[str, Any] = json.loads(out)
    return doc


def _mark_tested(yml: Path, md: Path) -> int:
    argv = ["mark-tested", "--yaml", str(yml), "--md", str(md)]
    for ac, tid in TEST_IDS.items():
        argv += ["--ac", ac, "--test-id", f"{ac}={tid}"]
    rc, _out = _main(argv)
    return rc


TIERS = (1, 2, 3)


@pytest.mark.parametrize("tier", TIERS)
def test_minimal_machine_yaml_validates_and_approves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tier: int
) -> None:
    root = tmp_path / "repo"
    yml, md, slug = _spec_checkout(root, tier)
    authored = set(_minimal(tier, slug))
    assert authored <= {
        "schema_version",
        "spec_slug",
        "verification_tier",
        "irreversible_decisions",
        "ac",
        "mutation_threshold",
        "paths_to_mutate",
    }
    monkeypatch.chdir(root)
    rc, out = _main(
        ["check", "--all", "--yaml", str(yml), "--md", str(md), "--strictness", "block"]
    )
    payload = json.loads(out)
    assert rc == 0, out
    assert payload["ok"] is True, out
    assert not payload.get("quality", {}).get("blocked", False), out
    if tier != 1:
        # The mutation dimension is omitted, not zeroed (no weak or low dimension names it).
        assert "mutation_coverage_set" not in json.dumps(payload), out
    rc, out = _main(["approve", "--yaml", str(yml), "--exempt"])
    assert rc == 0, out
    status = _status(root, slug)
    assert status["state"] == "exempt", status
    assert status["trusted_lane"] == "light", status


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("kind", ["exempt", "human"])
def test_mark_tested_write_back_keeps_the_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tier: int, kind: str
) -> None:
    root = tmp_path / "repo"
    yml, md, slug = _spec_checkout(root, tier)
    monkeypatch.chdir(root)
    argv = ["approve", "--yaml", str(yml)] + (["--exempt"] if kind == "exempt" else [])
    rc, out = _main(argv)
    assert rc == 0, out
    state = "exempt" if kind == "exempt" else "approved"
    assert _status(root, slug)["state"] == state
    assert _mark_tested(yml, md) == 0
    written = yaml.safe_load(yml.read_text(encoding="utf-8"))
    for ac in written["ac"]:
        if ac["id"] in TEST_IDS:
            assert ac["test_ids"] == [TEST_IDS[ac["id"]]], ac
    status = _status(root, slug)
    assert status["state"] == state, status
    assert status["trusted_lane"] == "light", status
