"""Explicit migration: preflight all conflicts, replace destinations, then retire sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from harness_maker import intent, world
from harness_maker.frontmatter import split_frontmatter
from harness_maker.intent_vocabulary import (
    RECORD_ALIASES,
    canonical_project,
    canonical_question,
    translate,
)
from harness_maker.io_utils import atomic_write


def migrate(root: Path) -> dict[str, Any]:
    with world._mutation_lock(root):
        return _migrate_locked(root)


def _migrate_locked(root: Path) -> dict[str, Any]:
    project_path = world.intent_path(root)
    loaded = intent.load_intent(project_path)
    raw = yaml.safe_load(project_path.read_text())
    project = canonical_project(raw)
    writes: dict[Path, bytes] = {}
    retired: list[Path] = []
    questions = {q["id"]: q for q in project["open_questions"]}
    old_questions = root / ".claude/world/assumptions.yaml"
    if old_questions.exists():
        errors = world.validate_assumptions(old_questions)
        if errors:
            raise world.WorldError(errors[0].field, errors[0].message)
        for rec in yaml.safe_load(old_questions.read_text())["assumptions"]:
            question = canonical_question(rec)
            if question["id"] in questions and questions[question["id"]] != question:
                raise world.WorldError("conflict", f"question {question['id']}")
            questions[question["id"]] = question
        retired.append(old_questions)
    project["open_questions"] = list(questions.values())
    project_errors = intent._validate_raw(project_path, project)
    if project_errors:
        raise intent.IntentInvalidError(project_path, project_errors)

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
                raise world.WorldError("conflict", f"destination {path}")
        writes[path] = content

    old_metrics = root / ".claude/world/outcomes.yaml"
    if old_metrics.exists():
        errors = world.validate_outcomes(
            old_metrics, intent_outcomes={m.id: m for m in loaded.metrics}
        )
        if errors:
            raise world.WorldError(errors[0].field, errors[0].message)
        metrics = yaml.safe_load(old_metrics.read_text())
        metrics["values"] = [
            translate(r, {"metric_id": "outcome_id"}, canonical=True) for r in metrics["values"]
        ]
        destination(
            root / ".claude/intent/metrics.yaml",
            yaml.safe_dump(metrics, sort_keys=False, allow_unicode=True).encode(),
        )
        retired.append(old_metrics)
    for path in sorted((root / "work-docs").glob("INTENT-*.md")):
        record, body, err = world._read_intent(path)
        if err is not None:
            raise world.WorldError(err.field, err.message)
        errors = world._validate_objective_raw(
            path,
            record,
            intent_outcomes={m.id: m for m in loaded.metrics},
            assumption_ids=set(questions),
        )
        if errors:
            raise world.WorldError(errors[0].field, errors[0].message)
        record = translate(record, RECORD_ALIASES, canonical=True)
        content = (
            b"---\n"
            + yaml.safe_dump(record, sort_keys=False, allow_unicode=True).encode()
            + b"---\n"
            + body
        )
        destination(root / "intent" / f"{record['id']}.md", content)
        retired.append(path)
    # Existing canonical records must also be readable before any file is replaced.
    for path in sorted((root / "intent").glob("*.md")):
        record, _, err = world._read_intent(path)
        errors = (
            [err]
            if err
            else world._validate_objective_raw(
                path,
                record,
                intent_outcomes={m.id: m for m in loaded.metrics},
                assumption_ids=set(questions),
            )
        )
        if errors:
            raise world.WorldError("conflict", f"invalid destination {path}: {errors[0]}")
    canonical_metrics = root / ".claude/intent/metrics.yaml"
    if canonical_metrics.exists():
        errors = world.validate_outcomes(
            canonical_metrics, intent_outcomes={m.id: m for m in loaded.metrics}
        )
        if errors:
            raise world.WorldError(
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
