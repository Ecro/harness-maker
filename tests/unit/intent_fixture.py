"""Shared builders for the `hm intent` tests — a canonical project root (SPEC-intent-lean).

Test-side canonicalisers live here too (`canonical_hash`, `argmax_latest`), restated from the
SPEC Constraints rows rather than imported from the runtime, so the oracle never reads the code.
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
    """SPEC-outcome-measure Constraints 'Hash': the `measure` key joins the payload only when a
    block is present (with its `cwd: base` / `timeout_s: 300` defaults filled in), so a
    block-less outcome hashes exactly as it did before the block existed."""
    payload: dict[str, Any] = {
        "higher_is_better": outcome["higher_is_better"],
        "how_measured": outcome["how_measured"],
        "target": outcome["target"],
    }
    block = outcome.get("measure")
    if block is not None:
        payload["measure"] = {
            "cmd": block["cmd"],
            "cwd": block.get("cwd", "base"),
            "select": block["select"],
            "timeout_s": block.get("timeout_s", 300),
        }
    return canonical_hash(payload)


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
    *metrics: dict[str, Any],
    statement: str = "ship it",
    questions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": KNOWN_MAJOR,
        "purpose": {"statement": statement, "vision": ""},
        "metrics": list(metrics),
        "rules": [],
        "out_of_scope": [],
        "open_questions": questions or [],
        "owners": {},
    }


def question(
    qid: str = "log_location",
    *,
    claim: str = "logs live in /var/log",
    status: str = "confirmed",
    evidence: list[dict[str, Any]] | None = None,
    history: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": qid,
        "claim": claim,
        "status": status,
        "evidence": evidence
        if evidence is not None
        else [{"text": "E1", "observed_at": "2026-09-01T00:00:00Z", "relation": "confirms"}],
        "history": history or [],
    }


def record(
    rid: str = "OBJ-1",
    *,
    state: str = "open",
    metric_id: str = "onboarding_minutes",
    observed: str | None = None,
    note: str | None = None,
    closed_at: str | None = None,
) -> dict[str, Any]:
    return {
        "id": rid,
        "title": f"{rid} title",
        "statement": "shorter onboarding keeps users",
        "metric_id": metric_id,
        "scope": ["cut the interview to one round"],
        "out_of_scope": ["rewrite the renderer"],
        "state": state,
        "created_at": "2026-09-01T00:00:00Z",
        "schema_version": KNOWN_MAJOR,
        "observed": observed,
        "note": note,
        "closed_at": closed_at,
    }


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
    values: list[dict[str, Any]] | None = None,
    records: list[dict[str, Any]] | None = None,
    git: bool = True,
) -> Path:
    """A canonical project root. `git=True` initialises a repo with a user.name."""
    if git:
        git_init(root)
    dump(root / ".claude" / "intent.yaml", intent if intent is not None else intent_doc(outcome()))
    dump(metrics_path(root), {"schema_version": KNOWN_MAJOR, "values": values or []})
    for rec in records or []:
        dump_intent(record_path(root, rec["id"]), rec)
    return root


FIXTURE_BODY = b"## Problem\n\nfixture body\n"


def dump_intent(path: Path, doc: dict[str, Any], body: bytes = FIXTURE_BODY) -> None:
    """Independent of the subject's writer: frontmatter via yaml, fences, body bytes verbatim."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True).encode("utf-8")
    path.write_bytes(b"---\n" + fm + b"---\n" + body)


def record_path(root: Path, rid: str) -> Path:
    return root / "intent" / f"{rid}.md"


def metrics_path(root: Path) -> Path:
    return root / ".claude" / "intent" / "metrics.yaml"


def row(metric_id: str, value: float, observed_at: str, *, definition: str = "") -> dict[str, Any]:
    return {
        "value": value,
        "observed_at": observed_at,
        "evidence": "fixture",
        "definition_hash": definition,
        "metric_id": metric_id,
    }


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """The shipped entrypoint, as a subprocess — never the module function (seam rule)."""
    import sys

    return subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "intent", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def stdout_json(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(proc.stdout.strip().splitlines()[-1])  # type: ignore[no-any-return]
