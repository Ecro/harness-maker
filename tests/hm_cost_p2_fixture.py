"""Fixture projects for SPEC-hm-cost-p2: a minimal machine SPEC whose rows are written by hand."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_YAML = REPO_ROOT / "specs" / "SPEC-hm-cost-p2.machine.yaml"
SLUG = "demo"


def param_ac(ac_id: str, rows: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "id": ac_id,
        "title": f"title {ac_id}",
        "type": "parametric",
        "golden_table": rows,
        "pending_test": True,
        "oracle_source": "golden",
        "oracle_evidence": "rows written by hand in the fixture",
        **extra,
    }


def mech_ac(ac_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": ac_id,
        "title": f"title {ac_id}",
        "type": "mechanical",
        "executable_predicate": "True",
        "pending_test": True,
        "oracle_source": "golden",
        "oracle_evidence": "rows written by hand in the fixture",
        **extra,
    }


def spec_doc(acs: list[dict[str, Any]], slug: str = SLUG) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "spec_slug": slug,
        "verification_tier": 1,
        "irreversible_decisions": [],
        "ac": acs,
    }


def write_spec(root: Path, acs: list[dict[str, Any]], slug: str = SLUG) -> Path:
    specs = root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    path = specs / f"SPEC-{slug}.machine.yaml"
    path.write_text(yaml.safe_dump(spec_doc(acs, slug), sort_keys=False), encoding="utf-8")
    return path


def write_golden(root: Path, payload: dict[str, Any], slug: str = SLUG) -> Path:
    path = root / "specs" / f"SPEC-{slug}.golden.json"
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def init_project(root: Path, *, level: str = "auto_full") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    claude = root / ".claude"
    claude.mkdir(exist_ok=True)
    (claude / "harness.yaml").write_text(
        yaml.safe_dump({"autonomy": {"level": level}}), encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=30)
    # wrapup_land commits here too; CI runners have no global git identity.
    for key, value in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(root), "config", key, value], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "commit",
         "-q", "--allow-empty", "-m", "init"],
        check=True, timeout=30,
    )  # fmt: skip
    return root
