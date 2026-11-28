"""Explicit migration: preflight all conflicts, replace destinations, then retire sources.

The only module that still reads the pre-0.58 vocabulary (`mission`, `outcomes`, `hypothesis`,
`known|assumed|unknown|conflict`, `.claude/world/`, `work-docs/INTENT-*.md`): it translates
everything to the canonical form, then validates that form with the runtime's own validators.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import yaml

from harness_maker import intent
from harness_maker.frontmatter import split_frontmatter
from harness_maker.intent_cli import (
    IntentWriteError,
    intent_path,
    metrics_errors,
    read_record,
    record_errors,
    write_lock,
)
from harness_maker.io_utils import atomic_write

PROJECT_ALIASES = {"metrics": "outcomes", "rules": "non_negotiables", "out_of_scope": "non_scope"}
RECORD_ALIASES = {"statement": "hypothesis", "metric_id": "outcome_id", "out_of_scope": "non_scope"}
QUESTION_STATES = {"known": "confirmed", "assumed": "open", "unknown": "open", "conflict": "wrong"}


def translate(raw: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    """Legacy keys → canonical keys; a key present under both names must agree."""
    result = copy.deepcopy(raw)
    for new, old in aliases.items():
        if old in result:
            if new in result and result[new] != result[old]:
                raise IntentWriteError("conflict", f"between {old} and {new}")
            result[new] = result.pop(old)
    if isinstance(result.get("revisit_when"), dict):
        cond = translate(result["revisit_when"], {"metric": "outcome", "question": "assumption"})
        if isinstance(cond.get("status"), str):
            cond["status"] = QUESTION_STATES.get(cond["status"], cond["status"])
        result["revisit_when"] = cond
    return result


def canonical_question(question: dict[str, Any]) -> dict[str, Any]:
    result = translate(question, {})
    if not isinstance(result.get("status"), str):
        raise IntentWriteError("status", "question status must be a string")
    result["status"] = QUESTION_STATES.get(result["status"], result["status"])
    return result


def canonical_project(raw: Any) -> dict[str, Any]:
    """`mission`/`vision` → `purpose`, `unknowns[]` → open questions with stable hashed ids."""
    if not isinstance(raw, dict):
        raise IntentWriteError("file", "intent.yaml: top level must be a mapping")
    result = translate(raw, PROJECT_ALIASES)
    questions = [canonical_question(q) for q in result.pop("open_questions", None) or []]
    seen = {q.get("id") for q in questions}
    mission, vision = result.pop("mission", None), result.pop("vision", None)
    if "purpose" not in result:
        result["purpose"] = {"statement": mission or "", "vision": vision or ""}
    occurrences: dict[str, int] = {}
    for claim in result.pop("unknowns", None) or []:
        if not isinstance(claim, str):
            raise IntentWriteError("unknowns", "must be a list of strings")
        n = occurrences.get(claim, 0)
        occurrences[claim] = n + 1
        qid = "q_" + hashlib.sha256(f"{n}:{claim}".encode()).hexdigest()[:16]
        if qid not in seen:
            questions.append(
                {"id": qid, "claim": claim, "status": "open", "evidence": [], "history": []}
            )
            seen.add(qid)
    result["open_questions"] = questions
    result.setdefault("rules", [])
    result.setdefault("out_of_scope", [])
    owners = result.get("owners", {})
    result["owners"] = (
        {"team": ", ".join(owners)} if isinstance(owners, list) and owners else owners or {}
    )
    return result


def migrate(root: Path) -> dict[str, Any]:
    with write_lock(root):
        return _migrate_locked(root)


def _migrate_locked(root: Path) -> dict[str, Any]:
    project_path = intent_path(root)
    raw = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    project = canonical_project(raw)
    writes: dict[Path, bytes] = {}
    retired: list[Path] = []
    questions = {q["id"]: q for q in project["open_questions"]}
    old_questions = root / ".claude/world/assumptions.yaml"
    if old_questions.exists():
        doc = yaml.safe_load(old_questions.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("assumptions"), list):
            raise IntentWriteError("assumptions", f"{old_questions}: needs an assumptions list")
        for rec in doc["assumptions"]:
            if not isinstance(rec, dict):
                raise IntentWriteError("assumptions", "entries must be mappings")
            question = canonical_question(rec)
            if question["id"] in questions and questions[question["id"]] != question:
                raise IntentWriteError("conflict", f"question {question['id']}")
            questions[question["id"]] = question
        retired.append(old_questions)
    project["open_questions"] = list(questions.values())
    loaded = intent.intent_from_raw(project_path, project)
    metric_ids = {m.id for m in loaded.metrics}

    def destination(path: Path, content: bytes, *, compare: bool = True) -> None:
        if path.exists():
            if path.read_bytes() == content:
                return
            if compare:
                if path.suffix == ".md":
                    before = split_frontmatter(path.read_bytes())
                    after = split_frontmatter(content)
                    if (
                        before.status == after.status == "ok"
                        and before.mapping == after.mapping
                        and before.body == after.body
                    ):
                        return
                else:
                    try:
                        if yaml.safe_load(path.read_bytes()) == yaml.safe_load(content):
                            return
                    except yaml.YAMLError:
                        pass
                raise IntentWriteError("conflict", f"destination {path}")
        writes[path] = content

    old_metrics = root / ".claude/world/outcomes.yaml"
    if old_metrics.exists():
        metrics = yaml.safe_load(old_metrics.read_text(encoding="utf-8"))
        if isinstance(metrics, dict) and isinstance(metrics.get("values"), list):
            metrics["values"] = [
                translate(r, {"metric_id": "outcome_id"}) if isinstance(r, dict) else r
                for r in metrics["values"]
            ]
        errors, _ = metrics_errors(old_metrics, metrics, metric_ids)
        if errors:
            raise IntentWriteError(errors[0].field, errors[0].message)
        destination(
            root / ".claude/intent/metrics.yaml",
            yaml.safe_dump(metrics, sort_keys=False, allow_unicode=True).encode(),
        )
        retired.append(old_metrics)
    for path in sorted((root / "work-docs").glob("INTENT-*.md")):
        record, body = read_record(path)
        record = translate(record, RECORD_ALIASES)
        dest = root / "intent" / f"{path.stem.removeprefix('INTENT-')}.md"
        errors = record_errors(dest, record, metric_ids)
        if errors:
            raise IntentWriteError(errors[0].field, f"{path}: {errors[0].message}")
        content = (
            b"---\n"
            + yaml.safe_dump(record, sort_keys=False, allow_unicode=True).encode()
            + b"---\n"
            + body
        )
        destination(dest, content)
        retired.append(path)
    # Existing canonical records must also be readable before any file is replaced.
    for path in sorted((root / "intent").glob("*.md")):
        if path in writes:
            continue
        try:
            record, _ = read_record(path)
        except IntentWriteError as exc:
            raise IntentWriteError("conflict", f"invalid destination {path}: {exc}") from exc
        errors = record_errors(path, record, metric_ids)
        if errors:
            raise IntentWriteError("conflict", f"invalid destination {path}: {errors[0]}")
    canonical_metrics = root / ".claude/intent/metrics.yaml"
    if canonical_metrics.exists() and canonical_metrics not in writes:
        errors, _ = metrics_errors(
            canonical_metrics,
            yaml.safe_load(canonical_metrics.read_text(encoding="utf-8")),
            metric_ids,
        )
        if errors:
            raise IntentWriteError(
                "conflict", f"invalid destination {canonical_metrics}: {errors[0]}"
            )
    # Preserve already canonical bytes (comments/key order included) on a no-op migration.
    if project != raw:
        destination(
            project_path,
            yaml.safe_dump(project, sort_keys=False, allow_unicode=True).encode(),
            compare=False,
        )
    for path, content in writes.items():
        atomic_write(path, content)
    for path in retired:
        path.unlink()
    return {
        "changed": [str(p.relative_to(root)) for p in writes],
        "retired": [str(p.relative_to(root)) for p in retired],
    }
