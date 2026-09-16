"""Shared builders for the `world` tests — a project root with intent, assumptions, INTENT records.

Test-side canonicalisers live here too (`canonical_hash`, `argmax_latest`), restated from the
SPEC Constraints rows rather than imported from `world`, so the oracle never reads the code.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

KNOWN_MAJOR = 1
GIT_NAME = "Fixture Approver"


def canonical_hash(payload: dict[str, Any]) -> str:
    """SPEC 'Approval hash payload' / 'Definition hash payload' rules, independently.

    This sorts unconditionally, and the subject's own payload literals are already alphabetical,
    so these hashes alone cannot tell a subject that dropped `sort_keys=True` from one that kept
    it. `test_ac_009_canonical_json_sorts_keys_it_was_not_handed_sorted` closes that gap by
    calling the subject's canonicaliser with an out-of-order dict.
    """
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def definition_hash(outcome: dict[str, Any]) -> str:
    return canonical_hash(
        {
            "higher_is_better": outcome["higher_is_better"],
            "how_measured": outcome["how_measured"],
            "target": outcome["target"],
        }
    )


def approval_hash(obj: dict[str, Any], target: float) -> str:
    return canonical_hash(
        {
            "hypothesis": obj["hypothesis"],
            "non_scope": list(obj.get("non_scope") or []),
            "outcome_id": obj["outcome_id"],
            "scope": list(obj["scope"]),
            "target": target,
        }
    )


def argmax_latest(records: list[dict[str, Any]]) -> int | None:
    """Greatest normalised instant; ties → later index (SPEC 'Gap' row)."""
    best: int | None = None
    best_ts: datetime | None = None
    for i, r in enumerate(records):
        ts = datetime.fromisoformat(r["observed_at"]).astimezone(UTC)
        if best_ts is None or ts >= best_ts:
            best, best_ts = i, ts
    return best


def outcome(oid: str = "onboarding_minutes", **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": oid,
        "description": f"{oid} description",
        "target": 10,
        "higher_is_better": False,
        "how_measured": "stopwatch",
    }
    base.update(over)
    return base


def intent_doc(
    *outcomes: dict[str, Any], mission: str = "ship it", unknowns: list[str] | None = None
) -> dict[str, Any]:
    return {
        "schema_version": KNOWN_MAJOR,
        "mission": mission,
        "vision": "",
        "outcomes": list(outcomes),
        "non_negotiables": [],
        "non_scope": [],
        "unknowns": unknowns or [],
        "owners": [],
    }


def assumption(
    aid: str = "log_location",
    *,
    claim: str = "logs live in /var/log",
    status: str = "known",
    evidence: list[dict[str, Any]] | None = None,
    history: list[str] | None = None,
    revisit_when: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": aid,
        "claim": claim,
        "status": status,
        "evidence": evidence
        if evidence is not None
        else [{"text": "E1", "observed_at": "2026-09-01T00:00:00Z", "relation": "confirms"}],
        "history": history or [],
        "revisit_when": revisit_when,
    }


def objective(
    oid: str = "OBJ-1",
    *,
    state: str = "proposed",
    outcome_id: str = "onboarding_minutes",
    depends_on: list[str] | None = None,
    approval: dict[str, Any] | None = None,
    rejected: list[str] | None = None,
    revisit_when: dict[str, Any] | None = None,
    observed: str | None = None,
    note: str | None = None,
    closed_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": KNOWN_MAJOR,
        "id": oid,
        "title": f"{oid} title",
        "hypothesis": "shorter onboarding keeps users",
        "scope": ["cut the interview to one round"],
        "non_scope": ["rewrite the renderer"],
        "rejected": rejected or [],
        "outcome_id": outcome_id,
        "depends_on": depends_on or [],
        "state": state,
        "approval": approval,
        "revisit_when": revisit_when,
        "observed": observed,
        "note": note,
        "created_at": "2026-09-01T00:00:00Z",
        "closed_at": closed_at,
    }


def approved(obj: dict[str, Any], target: float, *, by: str = GIT_NAME) -> dict[str, Any]:
    obj = dict(obj)
    obj["approval"] = {
        "content_hash": approval_hash(obj, target),
        "approved_by": by,
        "approved_at": "2026-09-02T00:00:00Z",
        "approved_target": target,
    }
    return obj


def load(path: Path) -> dict[str, Any]:
    """YAML files load whole; an INTENT document loads its frontmatter only (the record)."""
    data = path.read_bytes()
    if path.suffix == ".md":
        from harness_maker.frontmatter import split_frontmatter

        split = split_frontmatter(data)
        assert split.status == "ok", split
        assert split.mapping is not None
        return split.mapping
    return yaml.safe_load(data.decode("utf-8"))  # type: ignore[no-any-return]


def dump(path: Path, doc: dict[str, Any]) -> None:
    """Hand-edit an existing file: an INTENT document keeps its body, a YAML file is rewritten."""
    if path.suffix == ".md":
        body = FIXTURE_BODY
        if path.exists():
            from harness_maker.frontmatter import split_frontmatter

            split = split_frontmatter(path.read_bytes())
            if split.status == "ok":
                body = split.body
        dump_intent(path, doc, body)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")


def git_init(root: Path, *, name: str | None = GIT_NAME) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=30)
    if name is not None:
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", name], check=True, timeout=30
        )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"],
        check=True,
        timeout=30,
    )


def build_root(
    root: Path,
    *,
    intent: dict[str, Any] | None = None,
    assumptions: list[dict[str, Any]] | None = None,
    values: list[dict[str, Any]] | None = None,
    objectives: list[dict[str, Any]] | None = None,
    git: bool = True,
) -> Path:
    """A project root with the four state files. `git=True` initialises a repo with a user.name."""
    if git:
        git_init(root)
    claude = root / ".claude"
    dump(claude / "intent.yaml", intent if intent is not None else intent_doc(outcome()))
    dump(
        claude / "world" / "assumptions.yaml",
        {"schema_version": KNOWN_MAJOR, "assumptions": assumptions or []},
    )
    dump(
        claude / "world" / "outcomes.yaml", {"schema_version": KNOWN_MAJOR, "values": values or []}
    )
    for obj in objectives or []:
        dump_intent(objective_doc_path(root, obj["id"]), obj)
    return root


FIXTURE_BODY = b"## Problem\n\nfixture body\n"


def dump_intent(path: Path, doc: dict[str, Any], body: bytes = FIXTURE_BODY) -> None:
    """Independent of the subject's writer: frontmatter via yaml, fences, body bytes verbatim."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True).encode("utf-8")
    path.write_bytes(b"---\n" + fm + b"---\n" + body)


def objective_doc_path(root: Path, oid: str) -> Path:
    return root / "work-docs" / f"INTENT-{oid}.md"


def assumptions_path(root: Path) -> Path:
    return root / ".claude" / "world" / "assumptions.yaml"


def outcomes_path(root: Path) -> Path:
    return root / ".claude" / "world" / "outcomes.yaml"


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """The shipped entrypoint, as a subprocess — never the module function (seam rule)."""
    import sys

    return subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "world", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def stdout_json(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(proc.stdout.strip().splitlines()[-1])  # type: ignore[no-any-return]
