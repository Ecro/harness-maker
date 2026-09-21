"""Canonical intent command surface over the compatibility-preserving domain operations."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from harness_maker import intent, world
from harness_maker.intent_migrate import migrate
from harness_maker.intent_vocabulary import RECORD_ALIASES, canonical_question, condition, translate


def status_report(root: Path) -> dict[str, Any]:
    try:
        loaded = world.load_world(root)
    except intent.IntentInvalidError as exc:
        return world._invalid_payload(exc)
    report = world._gap_payload(loaded, root)
    status = world._status_payload(loaded)
    report.pop("mission", None)
    report["purpose"] = loaded.intent.purpose
    report["metrics"] = report.pop("outcomes")
    report["intents"] = {
        key: translate(value, RECORD_ALIASES, canonical=True)
        for key, value in report.pop("objectives").items()
    }
    report.pop("unknowns", None)
    report.pop("assumptions", None)
    questions = {q["id"]: q for q in loaded.intent.open_questions}
    for raw in loaded.assumptions.values():
        question = canonical_question(raw)
        if question["id"] in questions and question != questions[question["id"]]:
            report["broken_references"].append(f"conflict: question {question['id']}")
        else:
            questions[question["id"]] = question
    report["open_questions"] = list(questions.values())
    report["revisits"] = {key: world.revisit(loaded, key) for key in loaded.objectives}
    for item in report["revisits"].values():
        item["intent"] = item.pop("objective")
        item["condition"] = condition(item["condition"], canonical=True)
        if isinstance(item["condition"], dict) and "question" in item["condition"]:
            item["last_value"] = {
                "known": "confirmed",
                "unknown": "open",
                "assumed": "open",
                "conflict": "wrong",
            }.get(item["last_value"], item["last_value"])
    report["active"] = status["active"]
    report["proposed"] = status["proposed"]
    return report


def _metric_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = translate(payload, {"metric": "outcome", "metric_id": "outcome_id"}, canonical=True)
    if isinstance(result.get("row"), dict):
        result["row"] = _metric_payload(result["row"])
    if isinstance(result.get("results"), list):
        result["results"] = [_metric_payload(row) for row in result["results"]]
    return result


def main(argv: list[str] | None = None) -> int:
    args = intent._parser().parse_args(sys.argv[1:] if argv is None else argv)
    migration = args.cmd == "migrate"
    if args.cmd in {"new", "approve", "activate", "drop", "reopen", "close", "show"}:
        args.verb = args.cmd
        args.cmd = "objective"
    if args.cmd == "question":
        args.cmd = "assume"
    elif args.cmd == "metric":
        args.cmd = "outcome"
    root = Path(args.root) if args.root else world.checkout_root(Path.cwd())
    as_json = bool(getattr(args, "json", False))
    try:
        reading = args.cmd == "status" or (args.cmd == "objective" and args.verb == "show")
        dry_run = bool(getattr(args, "dry_run", False))
        if not migration and not reading and not dry_run and not world._canonical_project(root):
            raise world.WorldError("migration", "run hm intent migrate before making changes")
        if migration:
            payload = migrate(root)
        elif args.cmd == "status":
            payload = status_report(root)
        elif args.cmd == "outcome":
            if args.verb == "record":
                row = world.record_value(
                    root,
                    outcome_id=args.id,
                    value=world._json_number(args.value),
                    observed_at=args.observed_at,
                    evidence=args.evidence,
                )
                payload = {"value": translate(row, {"metric_id": "outcome_id"}, canonical=True)}
            elif bool(args.id) == bool(args.all_outcomes):
                raise world.WorldError("id", "give exactly one of <id> or --all")
            else:
                payload = (
                    world.measure_all(root, dry_run=args.dry_run)
                    if args.all_outcomes
                    else world.measure_outcome(root, args.id, dry_run=args.dry_run)
                )
        elif args.cmd == "assume":
            if not world._canonical_project(root):
                raise world.WorldError(
                    "migration", "run hm intent migrate before editing questions"
                )
            if args.verb == "add":
                rec = world.add_assumption(
                    root,
                    args.id,
                    claim=args.claim,
                    status={"open": "unknown", "confirmed": "known", "wrong": "conflict"}[
                        args.status
                    ],
                    text=args.text,
                    observed_at=args.observed_at,
                    locator=args.locator,
                )
            elif args.verb == "observe":
                rec = world.observe(
                    root,
                    args.id,
                    relation=args.relation,
                    text=args.text,
                    observed_at=args.observed_at,
                    claim=args.claim,
                    locator=args.locator,
                )
            else:
                if not args.claim.strip():
                    raise world.WorldError("claim", "must be a non-empty string")
                with world._mutation_lock(root):
                    world._require_writable_layout(root)
                    with world._rmw_lock(world.intent_path(root)):
                        doc = world._load_assumptions_doc(root)
                        rec = world._find(doc, args.id)
                        rec.setdefault("history", []).append(rec["claim"])
                        rec["claim"] = args.claim
                        rec["status"] = {
                            "open": "unknown",
                            "confirmed": "known",
                            "wrong": "conflict",
                        }[args.status]
                        world._dump_assumptions(root, doc)
            payload = {"question": canonical_question(rec)}
        elif args.verb == "new":
            rec = world.new_objective(
                root,
                args.id,
                title=args.title,
                hypothesis=args.hypothesis,
                scope=args.scope,
                outcome_id=args.outcome_id,
                non_scope=args.non_scope,
                from_proposal=args.from_proposal,
                candidates=args.candidates,
                declined=args.declined,
            )
            payload = {"record": translate(rec, RECORD_ALIASES, canonical=True)}
        elif args.verb == "show":
            _, rec = world._load_objective(root, args.id)
            payload = translate(rec, RECORD_ALIASES, canonical=True)
        elif args.verb == "activate":
            result = world.activate(root, args.id, cap=args.cap)
            payload = {"activated": True}
            if result.warning:
                payload["warning"] = {
                    "active_count": result.warning.count,
                    "cap": result.warning.cap,
                }
        else:
            if args.verb == "approve":
                rec = world.approve(root, args.id)
            elif args.verb == "close":
                rec = world.close(root, args.id, observed=args.observed, note=args.note)
            else:
                rec = world.transition(
                    root, args.id, "dropped" if args.verb == "drop" else "proposed"
                )
            payload = {"intent": translate(rec, RECORD_ALIASES, canonical=True)}
        if not migration and not reading:
            if args.cmd == "outcome":
                payload = _metric_payload(payload)
                payload["changed"] = None if dry_run else ".claude/intent/metrics.yaml"
            elif args.cmd == "assume":
                payload["changed"] = ".claude/intent.yaml"
            else:
                payload["changed"] = world._changed_path(root, args.id)
        world._emit(payload, as_json=as_json)
        return 1 if payload.get("failed") else 0
    except (world.WorldError, intent.IntentInvalidError, ValueError, OSError) as exc:
        world._emit({"error": str(exc)}, as_json=as_json)
        return 1
