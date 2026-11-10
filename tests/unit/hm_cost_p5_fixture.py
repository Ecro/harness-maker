"""SPEC-hm-cost-p5 fixtures: SPECs of a chosen AC count, and `check --all` run on them."""

from __future__ import annotations

import contextlib
import io
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from harness_maker import spec_machine

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "fe6fada6"
BEFORE = REPO_ROOT / "tests" / "fixtures" / "hm_cost_p5" / "check_before.json"
YAML_NAME = "SPEC-x.machine.yaml"
MD_NAME = "SPEC-x.md"

#: name -> (live ACs, break the md title of AC-001, write an unloadable yaml)
CASES: dict[str, tuple[int, bool, bool]] = {
    "valid_3ac": (3, False, False),
    "valid_9ac": (9, False, False),
    "failing_gate_9ac": (9, True, False),
    "unloadable": (3, False, True),
}


def _ac(i: int, *, superseded_by: str | None = None) -> dict[str, Any]:
    ac: dict[str, Any] = {
        "id": f"AC-{i:03d}",
        "title": f"behaviour {i} holds",
        "type": "mechanical",
        "pending_test": True,
        "executable_predicate": f"f({i}) == {i}",
        "oracle_source": "differential",
        "oracle_evidence": "compared against the reference captured before the edit",
    }
    if superseded_by:
        ac["superseded_by"] = superseded_by
    return ac


def machine(live: int, superseded: int = 0, irreversible: int = 0) -> dict[str, Any]:
    acs = [_ac(i) for i in range(1, live + 1)]
    acs += [_ac(live + i, superseded_by="other") for i in range(1, superseded + 1)]
    return {
        "schema_version": 3,
        "spec_slug": "x",
        "verification_tier": 1,
        "irreversible_decisions": [
            {
                "id": f"IRR-{i:03d}",
                "decision": f"decision {i}",
                "category": "public API/CLI contract",
                "rationale": "a consumer reads it",
                "source": "spec",
            }
            for i in range(1, irreversible + 1)
        ],
        "ac": acs,
    }


def model(live: int, superseded: int = 0, irreversible: int = 0) -> spec_machine.SpecMachine:
    return spec_machine.SpecMachine.model_validate(machine(live, superseded, irreversible))


def write_case(root: Path, name: str) -> None:
    live, break_title, unloadable = CASES[name]
    doc = machine(live)
    lines = [
        "---",
        "type: spec",
        "task_slug: x",
        "tier: 1",
        "test_framework: pytest",
        "---",
        "",
        "# SPEC — x",
        "",
        "## In-Scope Scenarios",
        "",
        "### S1: behaviour 1 holds",
        "**Given** an input **When** f runs **Then** it returns the input.",
        "",
        "## Verification Criteria",
        "",
        "| Scenario | Verification mode | Test name / manual step |",
        "|---|---|---|",
        "| S1 | unit | `test_s1` |",
        "",
    ]
    for ac in doc["ac"]:
        title = "a different title" if break_title and ac["id"] == "AC-001" else ac["title"]
        lines.append(f"### {ac['id']}: {title}")
    root.mkdir(parents=True, exist_ok=True)
    (root / MD_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    text = "ac: [unclosed\n" if unloadable else yaml.safe_dump(doc, sort_keys=False)
    (root / YAML_NAME).write_text(text, encoding="utf-8")


@contextlib.contextmanager
def _cwd(path: Path) -> Iterator[None]:
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def run_case(root: Path, name: str) -> tuple[int, dict[str, Any], str]:
    """Exit code, parsed payload without the volatile `approval` key, and raw stdout."""
    work = root / name
    write_case(work, name)
    buf = io.StringIO()
    with _cwd(work), contextlib.redirect_stdout(buf):
        rc = spec_machine.main(
            ["check", "--all", "--yaml", YAML_NAME, "--md", MD_NAME, "--strictness", "warn"]
        )
    out = buf.getvalue()
    payload = json.loads(out)
    payload.pop("approval", None)
    return rc, payload, out
