"""Lossless v1 vocabulary adapters. Reads never persist the translated mapping."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

PROJECT_ALIASES = {"metrics": "outcomes", "rules": "non_negotiables", "out_of_scope": "non_scope"}
RECORD_ALIASES = {"statement": "hypothesis", "metric_id": "outcome_id", "out_of_scope": "non_scope"}
QUESTION_STATES = {"known": "confirmed", "assumed": "open", "unknown": "open", "conflict": "wrong"}


def translate(raw: dict[str, Any], aliases: dict[str, str], *, canonical: bool) -> dict[str, Any]:
    result = copy.deepcopy(raw)
    for new, old in aliases.items():
        source, destination = (old, new) if canonical else (new, old)
        if source in result:
            if destination in result and result[destination] != result[source]:
                raise ValueError(f"conflict between {source} and {destination}")
            result[destination] = result.pop(source)
    if "revisit_when" in result:
        result["revisit_when"] = condition(result["revisit_when"], canonical=canonical)
    return result


def condition(raw: Any, *, canonical: bool) -> Any:
    if not isinstance(raw, dict):
        return raw
    result = translate(raw, {"metric": "outcome", "question": "assumption"}, canonical=canonical)
    if isinstance(result.get("status"), str):
        states = (
            QUESTION_STATES
            if canonical
            else {"confirmed": "known", "open": "unknown", "wrong": "conflict"}
        )
        result["status"] = states.get(result["status"], result["status"])
    return result


def project_questions(raw: dict[str, Any]) -> list[dict[str, Any]]:
    questions = copy.deepcopy(raw.get("open_questions", []))
    if not isinstance(questions, list):
        raise ValueError("open_questions must be a list")
    seen: set[str] = set()
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("open_questions entries must be mappings")
        allowed = {"id", "claim", "status", "evidence", "history", "revisit_when"}
        if set(question) - allowed:
            raise ValueError("unknown open_questions field")
        if not isinstance(question.get("id"), str) or question["id"] in seen:
            raise ValueError("question id must be a unique string")
        seen.add(question["id"])
        if not isinstance(question.get("claim"), str):
            raise ValueError("question claim must be a string")
        if question.get("status") not in ("open", "confirmed", "wrong"):
            raise ValueError("question status must be open, confirmed or wrong")
        for key in ("evidence", "history"):
            if not isinstance(question.get(key, []), list):
                raise ValueError(f"question {key} must be a list")
    from harness_maker import world
    from harness_maker.intent import IntentError

    errors: list[IntentError] = []
    validated: set[str] = set()
    for i, question in enumerate(questions):
        world._validate_assumption_record(i, legacy_question(question), validated, errors)
    if errors:
        raise ValueError("; ".join(f"{e.field}: {e.message}" for e in errors))
    unknowns = raw.get("unknowns", [])
    if "open_questions" in raw and (
        not isinstance(unknowns, list) or any(not isinstance(item, str) for item in unknowns)
    ):
        raise ValueError("unknowns must be a list of strings")
    if isinstance(unknowns, list):
        occurrences: dict[str, int] = {}
        for claim in unknowns:
            if not isinstance(claim, str):
                continue  # legacy validator names the original malformed field
            occurrence = occurrences.get(claim, 0)
            occurrences[claim] = occurrence + 1
            qid = "q_" + hashlib.sha256(f"{occurrence}:{claim}".encode()).hexdigest()[:16]
            question = {"id": qid, "claim": claim, "status": "open", "evidence": [], "history": []}
            if qid in seen:
                if next(q for q in questions if q["id"] == qid) != question:
                    raise ValueError(f"conflict for question {qid}")
            else:
                questions.append(question)
                seen.add(qid)
    return questions


def legacy_project(raw: dict[str, Any]) -> dict[str, Any]:
    result = translate(raw, PROJECT_ALIASES, canonical=False)
    if "purpose" in result:
        purpose = result.pop("purpose")
        if not isinstance(purpose, dict) or set(purpose) != {"statement", "vision"}:
            raise ValueError("purpose must contain statement and vision")
        for new, old in (("statement", "mission"), ("vision", "vision")):
            if not isinstance(purpose[new], str):
                raise ValueError(f"purpose.{new} must be a string")
            if old in result and result[old] != purpose[new]:
                raise ValueError(f"conflict between purpose.{new} and {old}")
            result[old] = purpose[new]
    if "open_questions" in result:
        questions = project_questions(result)
        result.pop("open_questions")
        result["unknowns"] = [q["claim"] for q in questions if q["status"] == "open"]
    return result


def canonical_project(raw: dict[str, Any]) -> dict[str, Any]:
    questions = project_questions(raw)
    result = translate(legacy_project(raw), PROJECT_ALIASES, canonical=True)
    result["purpose"] = {"statement": result.pop("mission"), "vision": result.pop("vision", "")}
    result.pop("unknowns", None)
    result["open_questions"] = questions
    result.setdefault("rules", [])
    result.setdefault("out_of_scope", [])
    owners = result.get("owners", {})
    result["owners"] = (
        {"team": ", ".join(owners)} if isinstance(owners, list) and owners else owners or {}
    )
    return result


def legacy_question(question: dict[str, Any]) -> dict[str, Any]:
    result = translate(question, {}, canonical=False)
    if not isinstance(result.get("status"), str):
        raise ValueError("question status must be a string")
    result["status"] = {"confirmed": "known", "open": "unknown", "wrong": "conflict"}.get(
        result["status"], result["status"]
    )
    return result


def canonical_question(question: dict[str, Any]) -> dict[str, Any]:
    result = translate(question, {}, canonical=True)
    if not isinstance(result.get("status"), str):
        raise ValueError("question status must be a string")
    result["status"] = QUESTION_STATES.get(result["status"], result["status"])
    return result
