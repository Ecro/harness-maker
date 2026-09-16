"""`.claude/world/` — assumptions, human-recorded outcome values, objectives; `hm world` CLI.

Everything a human writes or approves lives in three YAML files plus one file per objective;
`approval_valid` and `needs_revalidation` are DERIVED at read time and never stored, so every
mutation touches exactly one file and terminal records can stay immutable. No LLM client is
imported here — `hm world status` is the deterministic, free read path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from harness_maker import autopilot_ledger, command_registry
from harness_maker import intent as intent_mod
from harness_maker.frontmatter import split_frontmatter
from harness_maker.intent import Intent, IntentError, IntentInvalidError, schema_version_error
from harness_maker.io_utils import atomic_write
from harness_maker.second_opinion_invoke import resolve_base_root

KNOWN_MAJOR = intent_mod.KNOWN_MAJOR
STATUSES: tuple[str, ...] = ("known", "assumed", "unknown", "conflict")
RESOLVE_TARGETS: tuple[str, ...] = ("known", "assumed", "unknown")
RELATIONS: tuple[str, ...] = ("confirms", "supersedes", "contradicts")
OBJECTIVE_STATES: tuple[str, ...] = ("proposed", "active", "closed", "dropped")
TERMINAL_STATES: frozenset[str] = frozenset({"closed", "dropped"})
OBSERVED_VALUES: tuple[str, ...] = ("met", "missed", "no_data")
REVISIT_OPS: tuple[str, ...] = ("<", "<=", ">", ">=", "==")
SUBCOMMANDS: tuple[str, ...] = ("status", "assume", "outcome", "objective")

#: SPEC "Transitions": every other pair over the four states is refused. `dropped→proposed`
#: is the reopen, which clears the approval block; `proposed→active` needs a valid approval.
LEGAL_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("proposed", "active"),
        ("active", "closed"),
        ("proposed", "dropped"),
        ("active", "dropped"),
        ("dropped", "proposed"),
    }
)
#: The approval hash covers exactly these objective fields (plus the outcome's target).
HASHED_FIELDS: tuple[str, ...] = ("hypothesis", "non_scope", "outcome_id", "scope")

_ASSUMPTION_ID_RE = re.compile(r"^[a-z0-9_]+$")
_OBJECTIVE_ID_RE = re.compile(r"^[A-Z0-9-]+$")
_ASSUMPTION_KEYS: frozenset[str] = frozenset(
    {"id", "claim", "status", "evidence", "history", "revisit_when"}
)
_EVIDENCE_KEYS: frozenset[str] = frozenset({"text", "observed_at", "relation"})
_OBJECTIVE_REQUIRED: tuple[str, ...] = (
    "id",
    "title",
    "hypothesis",
    "scope",
    "outcome_id",
    "state",
    "created_at",
    "schema_version",
)
#: Ordered on purpose (ADR-011): this tuple is both the membership set and the frontmatter key
#: order every writer emits, so a repeated no-op write is byte-identical.
_OBJECTIVE_OPTIONAL: tuple[str, ...] = (
    "non_scope",
    "rejected",
    "depends_on",
    "approval",
    "revisit_when",
    "observed",
    "note",
    "closed_at",
)
_OBJECTIVE_KEYS: frozenset[str] = frozenset(_OBJECTIVE_REQUIRED) | frozenset(_OBJECTIVE_OPTIONAL)
_INTENT_PREFIX = "INTENT-"
_APPROVAL_KEYS: frozenset[str] = frozenset(
    {"content_hash", "approved_by", "approved_at", "approved_target"}
)


class WorldError(ValueError):
    """A refused write or an unloadable record; `field` names what was wrong."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


# ── paths, canonical forms, timestamps ───────────────────────────────────────


def checkout_root(cwd: Path) -> Path:
    """The CURRENT checkout's root — the task worktree when run there (SPEC two-root rule).

    Versioned files (PLAN, intent, world) are read here, never at the base root: a linked
    worktree's PLAN is the one the gate must see. Falls back to `cwd` with a stderr line when
    git is absent or `cwd` is outside a repo; never a silent `Path.cwd()`.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as exc:
        print(f"[world] git unavailable ({exc.__class__.__name__}); using {cwd}", file=sys.stderr)
        return Path(cwd)
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"[world] {cwd} is not inside a git checkout; using it as the root", file=sys.stderr)
        return Path(cwd)
    return Path(proc.stdout.strip())


def intent_path(root: Path) -> Path:
    return root / ".claude" / "intent.yaml"


def assumptions_path(root: Path) -> Path:
    return root / ".claude" / "world" / "assumptions.yaml"


def outcomes_path(root: Path) -> Path:
    return root / ".claude" / "world" / "outcomes.yaml"


def legacy_objectives_dir(root: Path) -> Path:
    """The pre-0.57 record location; anything found here is diagnosed, never loaded (ADR-006)."""
    return root / ".claude" / "world" / "objectives"


def intents_dir(root: Path) -> Path:
    return root / "work-docs"


def objective_doc_path(root: Path, objective_id: str) -> Path:
    """`work-docs/INTENT-<ID>.md` — the record IS the deliverable (ADR-001)."""
    return intents_dir(root) / f"{_INTENT_PREFIX}{objective_id}.md"


def _id_from_stem(path: Path) -> str | None:
    """The one id-extraction rule (ADR-003): the stem after `INTENT-`, else not a record."""
    stem = path.stem
    if not stem.startswith(_INTENT_PREFIX):
        return None
    return stem[len(_INTENT_PREFIX) :]


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def definition_hash(target: int | float, how_measured: str, higher_is_better: bool) -> str:
    return _sha256(
        canonical_json(
            {"higher_is_better": higher_is_better, "how_measured": how_measured, "target": target}
        )
    )


def approval_hash(record: dict[str, Any], target: int | float) -> str:
    return _sha256(
        canonical_json(
            {
                "hypothesis": record.get("hypothesis"),
                "non_scope": list(record.get("non_scope") or []),
                "outcome_id": record.get("outcome_id"),
                "scope": list(record.get("scope") or []),
                "target": target,
            }
        )
    )


def _json_number(value: Any) -> int | float:
    """A CLI float that is integral is stored as its int (`--value 17` → 17, not 17.0)."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value  # type: ignore[no-any-return]


def normalise_timestamp(raw: Any, field_name: str) -> str:
    """Timezone-aware ISO-8601 in → UTC `Z` form out; naive or unparseable is refused by name."""
    if not isinstance(raw, str) or not raw.strip():
        raise WorldError(field_name, "missing or not a string")
    text = raw.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00") if text.endswith("Z") else text)
    except ValueError as exc:
        raise WorldError(field_name, f"not ISO-8601: {text!r} ({exc})") from exc
    if parsed.tzinfo is None:
        raise WorldError(field_name, f"naive timestamp {text!r}: a timezone is required")
    utc = parsed.astimezone(UTC)
    if utc.microsecond:
        return utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_yaml(path: Path) -> tuple[Any, IntentError | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, IntentError("file", f"{path}: {exc}")
    try:
        return yaml.safe_load(text), None
    except yaml.YAMLError as exc:
        return None, IntentError("file", f"{path}: not valid YAML: {exc}")


def _dump_yaml(path: Path, doc: dict[str, Any]) -> None:
    atomic_write(path, yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def _read_intent(path: Path) -> tuple[dict[str, Any], bytes, IntentError | None]:
    """S1's three shapes: no/unterminated/invalid/non-mapping frontmatter is ONE `file` error; an
    empty mapping is a record with every required key missing (the rule set reports those)."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {}, b"", IntentError("file", f"{path}: {exc}")
    split = split_frontmatter(data)
    if split.status != "ok" or split.mapping is None:
        return {}, data, IntentError("file", f"{path}: {split.error}")
    return split.mapping, split.body, None


def _dump_intent(path: Path, record: dict[str, Any], body: bytes) -> None:
    """Frontmatter in declared key order, then the body bytes verbatim (ADR-002).

    An unknown key is refused rather than dropped: a key the order does not name would otherwise
    vanish silently on the next write.
    """
    unknown = sorted(set(record) - _OBJECTIVE_KEYS)
    if unknown:
        raise WorldError(unknown[0], "not an objective field; refusing to write")
    ordered = {k: record[k] for k in (*_OBJECTIVE_REQUIRED, *_OBJECTIVE_OPTIONAL) if k in record}
    fm = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True).encode("utf-8")
    atomic_write(path, b"---\n" + fm + b"---\n" + body)


def _write_record(world: World, root: Path, objective_id: str, record: dict[str, Any]) -> None:
    """Every writer's single exit; a missing body is refused, never replaced by an empty one."""
    body = world.bodies.get(objective_id)
    if body is None:
        raise WorldError("body", f"{objective_id!r} has no loaded body; refusing to write")
    _dump_intent(objective_doc_path(root, objective_id), record, body)


# ── validation ────────────────────────────────────────────────────────────────


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate_revisit_when(prefix: str, raw: Any, errors: list[IntentError]) -> None:
    if raw is None:
        return
    if not isinstance(raw, dict):
        errors.append(IntentError(prefix, "must be a mapping or null"))
        return
    keys = set(raw)
    if keys == {"outcome", "op", "value"}:
        if not isinstance(raw["outcome"], str):
            errors.append(IntentError(f"{prefix}.outcome", "must be a string"))
        if raw["op"] not in REVISIT_OPS:
            errors.append(IntentError(f"{prefix}.op", f"must be one of {REVISIT_OPS}"))
        if not _is_number(raw["value"]):
            errors.append(IntentError(f"{prefix}.value", "must be a number"))
    elif keys == {"assumption", "status"}:
        if not isinstance(raw["assumption"], str):
            errors.append(IntentError(f"{prefix}.assumption", "must be a string"))
        if raw["status"] not in RESOLVE_TARGETS:
            errors.append(
                IntentError(
                    f"{prefix}.status", f"must be one of {RESOLVE_TARGETS} (never conflict)"
                )
            )
    else:
        errors.append(
            IntentError(prefix, "must be {outcome, op, value} or {assumption, status} exactly")
        )


def _validate_assumption_record(
    i: int, raw: Any, seen: set[str], errors: list[IntentError]
) -> None:
    prefix = f"assumptions[{i}]"
    if not isinstance(raw, dict):
        errors.append(IntentError(prefix, "must be a mapping"))
        return
    for key in raw:
        if key not in _ASSUMPTION_KEYS:
            errors.append(IntentError(f"{prefix}.{key}", "unknown key"))
    aid = raw.get("id")
    if not isinstance(aid, str) or not _ASSUMPTION_ID_RE.match(aid):
        errors.append(IntentError(f"{prefix}.id", "must match [a-z0-9_]+"))
    elif aid in seen:
        errors.append(IntentError("assumptions[].id", f"duplicate id {aid!r}"))
    else:
        seen.add(aid)
    claim = raw.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        errors.append(IntentError(f"{prefix}.claim", "must be a non-empty string"))
    if raw.get("status") not in STATUSES:
        errors.append(IntentError(f"{prefix}.status", f"must be one of {STATUSES}"))
    evidence = raw.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append(IntentError(f"{prefix}.evidence", "must be a list"))
    else:
        for j, ev in enumerate(evidence):
            ep = f"{prefix}.evidence[{j}]"
            if not isinstance(ev, dict):
                errors.append(IntentError(ep, "must be a mapping"))
                continue
            for key in _EVIDENCE_KEYS:
                if key not in ev:
                    errors.append(IntentError(f"{ep}.{key}", "missing"))
            if "text" in ev and (not isinstance(ev["text"], str) or not ev["text"].strip()):
                errors.append(IntentError(f"{ep}.text", "must be a non-empty string"))
            if "relation" in ev and ev["relation"] not in RELATIONS:
                errors.append(IntentError(f"{ep}.relation", f"must be one of {RELATIONS}"))
    history = raw.get("history", [])
    if not isinstance(history, list):
        errors.append(IntentError(f"{prefix}.history", "must be a list"))
    else:
        for j, h in enumerate(history):
            if not isinstance(h, str):
                errors.append(IntentError(f"{prefix}.history[{j}]", "must be a string"))
    _validate_revisit_when(f"{prefix}.revisit_when", raw.get("revisit_when"), errors)


def validate_assumptions(path: Path) -> list[IntentError]:
    raw, err = _read_yaml(path)
    if err is not None:
        return [err]
    if not isinstance(raw, dict):
        return [IntentError("file", f"{path}: top level must be a mapping")]
    errors: list[IntentError] = []
    sv = schema_version_error(path, raw)
    if sv is not None:
        errors.append(sv)
    for key in raw:
        if key not in ("schema_version", "assumptions"):
            errors.append(IntentError(str(key), "unknown envelope key"))
    if "assumptions" not in raw:
        errors.append(IntentError("assumptions", "missing envelope key"))
    elif not isinstance(raw["assumptions"], list):
        errors.append(IntentError("assumptions", "must be a list"))
    else:
        seen: set[str] = set()
        for i, rec in enumerate(raw["assumptions"]):
            _validate_assumption_record(i, rec, seen, errors)
    return errors


def validate_outcomes(path: Path, *, intent_outcomes: dict[str, Any]) -> list[IntentError]:
    raw, err = _read_yaml(path)
    if err is not None:
        return [err]
    if not isinstance(raw, dict):
        return [IntentError("file", f"{path}: top level must be a mapping")]
    errors: list[IntentError] = []
    sv = schema_version_error(path, raw)
    if sv is not None:
        errors.append(sv)
    for key in raw:
        if key not in ("schema_version", "values"):
            errors.append(IntentError(str(key), "unknown envelope key"))
    if "values" not in raw:
        errors.append(IntentError("values", "missing envelope key"))
    elif not isinstance(raw["values"], list):
        errors.append(IntentError("values", "must be a list"))
    else:
        for i, rec in enumerate(raw["values"]):
            prefix = f"values[{i}]"
            if not isinstance(rec, dict):
                errors.append(IntentError(prefix, "must be a mapping"))
                continue
            for key in ("outcome_id", "value", "observed_at", "evidence", "definition_hash"):
                if key not in rec:
                    errors.append(IntentError(f"{prefix}.{key}", "missing"))
            if "outcome_id" in rec and rec["outcome_id"] not in intent_outcomes:
                errors.append(
                    IntentError(
                        f"{prefix}.outcome_id", f"{rec['outcome_id']!r} is not an intent outcome"
                    )
                )
            if "value" in rec and not _is_number(rec["value"]):
                errors.append(IntentError(f"{prefix}.value", "must be a number"))
    return errors


def validate_objective(
    path: Path, *, intent_outcomes: dict[str, Any], assumption_ids: set[str]
) -> list[IntentError]:
    """The disk validator for one INTENT document; `load_world` runs the same rule set."""
    raw, _body, err = _read_intent(path)
    if err is not None:
        return [err]
    return _validate_objective_raw(
        path, raw, intent_outcomes=intent_outcomes, assumption_ids=assumption_ids
    )


def _validate_objective_raw(
    path: Path, raw: Any, *, intent_outcomes: dict[str, Any], assumption_ids: set[str]
) -> list[IntentError]:
    """The one rule set for an objective record — the disk and in-memory validators share it.

    `path` is only the identity the record must match (the stem) and the name in messages;
    nothing here reads it.
    """
    if not isinstance(raw, dict):
        return [IntentError("file", f"{path}: top level must be a mapping")]
    errors: list[IntentError] = []
    sv = schema_version_error(path, raw)
    if sv is not None:
        errors.append(sv)
    for key in raw:
        if key not in _OBJECTIVE_KEYS:
            errors.append(IntentError(str(key), "unknown key"))
    for key in _OBJECTIVE_REQUIRED:
        if key not in raw:
            errors.append(IntentError(key, "missing required key"))
    oid = raw.get("id")
    if isinstance(oid, str):
        if not _OBJECTIVE_ID_RE.match(oid):
            errors.append(IntentError("id", "must match [A-Z0-9-]+"))
        elif oid != _id_from_stem(path):
            errors.append(
                IntentError("id", f"{oid!r} does not equal the stem after INTENT- ({path.name})")
            )
    elif "id" in raw:
        errors.append(IntentError("id", "must be a string"))
    for key in ("title", "hypothesis", "created_at"):
        if key in raw and (not isinstance(raw[key], str) or not raw[key].strip()):
            errors.append(IntentError(key, "must be a non-empty string"))
    scope = raw.get("scope")
    if "scope" in raw and (
        not isinstance(scope, list) or not scope or not all(isinstance(s, str) for s in scope)
    ):
        errors.append(IntentError("scope", "must be a non-empty list of strings"))
    for key in ("non_scope", "rejected"):
        val = raw.get(key)
        if val is not None and (
            not isinstance(val, list) or not all(isinstance(s, str) for s in val)
        ):
            errors.append(IntentError(key, "must be a list of strings"))
    if "outcome_id" in raw and raw["outcome_id"] not in intent_outcomes:
        errors.append(IntentError("outcome_id", f"{raw['outcome_id']!r} is not an intent outcome"))
    deps = raw.get("depends_on")
    if deps is not None:
        if not isinstance(deps, list):
            errors.append(IntentError("depends_on", "must be a list"))
        else:
            for j, dep in enumerate(deps):
                if not isinstance(dep, str) or dep not in assumption_ids:
                    errors.append(
                        IntentError(f"depends_on[{j}]", f"{dep!r} is not an assumption id")
                    )
    state = raw.get("state")
    if "state" in raw and state not in OBJECTIVE_STATES:
        errors.append(IntentError("state", f"must be one of {OBJECTIVE_STATES}"))
    approval = raw.get("approval")
    if approval is not None and (not isinstance(approval, dict) or set(approval) != _APPROVAL_KEYS):
        errors.append(IntentError("approval", f"must be null or exactly {sorted(_APPROVAL_KEYS)}"))
    _validate_revisit_when("revisit_when", raw.get("revisit_when"), errors)
    if state == "closed":
        if raw.get("observed") not in OBSERVED_VALUES:
            errors.append(
                IntentError("observed", f"a closed objective needs one of {OBSERVED_VALUES}")
            )
        if not isinstance(raw.get("note"), str) or not raw["note"].strip():
            errors.append(IntentError("note", "a closed objective needs a non-empty note"))
        if not isinstance(raw.get("closed_at"), str):
            errors.append(IntentError("closed_at", "a closed objective needs closed_at"))
    elif raw.get("observed") is not None:
        errors.append(IntentError("observed", "only a closed objective carries observed"))
    return errors


# ── the loaded world ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Derived:
    """Read-time state; `approval_valid` is None for terminal objectives (n/a)."""

    approval_valid: bool | None
    needs_revalidation: bool


@dataclass
class World:
    root: Path
    intent: Intent
    assumptions: dict[str, dict[str, Any]] = field(default_factory=dict)
    values: list[dict[str, Any]] = field(default_factory=list)
    objectives: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: The prose after the frontmatter fence, as bytes, carried opaque so a writer can put it
    #: back untouched (ADR-002). Present exactly for the ids in `objectives`.
    bodies: dict[str, bytes] = field(default_factory=dict)
    broken: dict[str, list[IntentError]] = field(default_factory=dict)
    errors: list[IntentError] = field(default_factory=list)

    @property
    def outcome_by_id(self) -> dict[str, Any]:
        return {o.id: o for o in self.intent.outcomes}


def load_world(root: Path) -> World:
    """Load everything; referential breakage is REPORTED (`errors` / `broken`), never raised.

    `intent.yaml` itself must validate — without it nothing downstream has a meaning — so an
    invalid intent raises `IntentInvalidError` for the caller to render.
    """
    loaded_intent = intent_mod.load_intent(intent_path(root))
    world = World(root=root, intent=loaded_intent)
    outcomes = world.outcome_by_id
    apath = assumptions_path(root)
    if apath.exists():
        a_errors = validate_assumptions(apath)
        if a_errors:
            world.errors.extend(IntentError(f"{apath.name}:{e.field}", e.message) for e in a_errors)
        else:
            raw, _ = _read_yaml(apath)
            for rec in raw["assumptions"]:
                world.assumptions[rec["id"]] = rec
    opath = outcomes_path(root)
    if opath.exists():
        o_errors = validate_outcomes(opath, intent_outcomes=outcomes)
        if o_errors:
            world.errors.extend(IntentError(f"{opath.name}:{e.field}", e.message) for e in o_errors)
        raw, _ = _read_yaml(opath)
        if isinstance(raw, dict) and isinstance(raw.get("values"), list):
            # AC-009: a row the validator refused stays out of `values` (its error stays in
            # `errors`) — `last_value` reads `value` unguarded and must never see that row.
            refused = {
                int(m.group(1))
                for e in o_errors
                if (m := re.match(r"values\[(\d+)\]", e.field)) is not None
            }
            world.values = [
                v
                for i, v in enumerate(raw["values"])
                if i not in refused and isinstance(v, dict) and v.get("outcome_id") in outcomes
            ]
    idir = intents_dir(root)
    if idir.is_dir():
        for p in sorted(idir.glob(f"{_INTENT_PREFIX}*.md")):
            oid = _id_from_stem(p)
            if not oid:
                continue
            raw, body, err = _read_intent(p)
            if err is not None:
                world.broken[oid] = [err]
                continue
            errs = _validate_objective_raw(
                p, raw, intent_outcomes=outcomes, assumption_ids=set(world.assumptions)
            )
            if errs:
                world.broken[oid] = errs
                continue
            world.objectives[oid] = raw
            world.bodies[oid] = body
    ldir = legacy_objectives_dir(root)
    if ldir.is_dir():
        for p in sorted(ldir.glob("*.yaml")):
            rel = p.relative_to(root).as_posix()
            world.errors.append(
                IntentError(
                    "objectives",
                    f"{rel}: the objective record moved; move this file to "
                    f"work-docs/{_INTENT_PREFIX}{p.stem}.md (frontmatter = the YAML, body = prose)",
                )
            )
    return world


def derive(world: World, objective_id: str) -> Derived:
    """`approval_valid` and `needs_revalidation`, computed — never read from a file."""
    rec = world.objectives.get(objective_id)
    if rec is None:
        raise WorldError("objective", f"{objective_id!r} is not a loadable objective")
    state = rec.get("state")
    if state in TERMINAL_STATES:
        return Derived(approval_valid=None, needs_revalidation=False)
    approval = rec.get("approval")
    valid = False
    if isinstance(approval, dict):
        outcome = world.outcome_by_id.get(str(rec.get("outcome_id")))
        if outcome is not None:
            valid = approval.get("content_hash") == approval_hash(rec, outcome.target)
    needs = any(
        world.assumptions.get(dep, {}).get("status") == "conflict"
        for dep in rec.get("depends_on") or []
    )
    return Derived(approval_valid=valid, needs_revalidation=needs)


@dataclass(frozen=True)
class LastValue:
    value: int | float
    observed_at: str
    stale_definition: bool


def last_value(world: World, outcome_id: str) -> LastValue | None:
    """Greatest normalised instant wins; ties → the later row (SPEC 'Gap' row)."""
    outcome = world.outcome_by_id.get(outcome_id)
    if outcome is None:
        return None
    best: dict[str, Any] | None = None
    best_ts: datetime | None = None
    for row in world.values:
        if row.get("outcome_id") != outcome_id or not isinstance(row.get("observed_at"), str):
            continue
        try:
            ts = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            continue
        if best_ts is None or ts >= best_ts:
            best, best_ts = row, ts
    if best is None:
        return None
    current = definition_hash(outcome.target, outcome.how_measured, outcome.higher_is_better)
    return LastValue(
        value=best["value"],
        observed_at=best["observed_at"],
        stale_definition=best.get("definition_hash") != current,
    )


def gap(world: World, outcome_id: str) -> str:
    lv = last_value(world, outcome_id)
    outcome = world.outcome_by_id[outcome_id]
    if lv is None or lv.stale_definition:
        return "unevaluable"
    if outcome.higher_is_better:
        return "at_or_better" if lv.value >= outcome.target else "below_target"
    return "at_or_better" if lv.value <= outcome.target else "above_target"


_OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
}


def revisit(world: World, objective_id: str) -> dict[str, Any]:
    """`candidate | not_met | unevaluable`, never blocking; prints what it evaluated against."""
    rec = world.objectives.get(objective_id)
    if rec is None:
        raise WorldError("objective", f"{objective_id!r} is not a loadable objective")
    cond = rec.get("revisit_when")
    out: dict[str, Any] = {
        "objective": objective_id,
        "title": rec.get("title"),
        "condition": cond,
        "last_value": None,
        "result": "unevaluable",
        "blocked": False,
    }
    if not isinstance(cond, dict):
        return out
    if "outcome" in cond:
        lv = last_value(world, cond["outcome"])
        if lv is None or lv.stale_definition:
            return out
        out["last_value"] = lv.value
        out["result"] = "candidate" if _OPS[cond["op"]](lv.value, cond["value"]) else "not_met"
        return out
    assumption = world.assumptions.get(str(cond.get("assumption")))
    if assumption is None or assumption.get("status") == "conflict":
        return out
    out["last_value"] = assumption["status"]
    out["result"] = "candidate" if assumption["status"] == cond["status"] else "not_met"
    return out


def _invalid_payload(exc: IntentInvalidError) -> dict[str, Any]:
    first = exc.errors[0]
    return {
        "state": "invalid",
        "error": {"field": first.field, "message": first.message},
        "errors": [{"field": e.field, "message": e.message} for e in exc.errors],
    }


def status_report(root: Path) -> dict[str, Any]:
    """The `hm world status` payload — read-only, LLM-free."""
    try:
        world = load_world(root)
    except IntentInvalidError as exc:
        return _invalid_payload(exc)
    return _status_payload(world)


def _status_payload(world: World) -> dict[str, Any]:
    """`status_report` over an already-loaded World — one snapshot, shared with `gap_report`."""
    report: dict[str, Any] = {
        "state": "not_filled_in" if intent_mod.is_not_filled_in(world.intent) else "ok",
        "mission": world.intent.mission,
        "outcomes": {},
        "active": {},
        "proposed": [],
        "unknowns": list(world.intent.unknowns),
        "conflicts": sorted(
            a for a, rec in world.assumptions.items() if rec.get("status") == "conflict"
        ),
        "fired_revisits": [],
        "broken_references": [
            *(f"{oid}: {errs[0].field}: {errs[0].message}" for oid, errs in world.broken.items()),
            *(f"{e.field}: {e.message}" for e in world.errors),
        ],
    }
    for outcome in world.intent.outcomes:
        lv = last_value(world, outcome.id)
        report["outcomes"][outcome.id] = {
            "last": lv.value if lv else None,
            "target": outcome.target,
            "observed_at": lv.observed_at if lv else None,
            "gap": gap(world, outcome.id),
            "stale_definition": bool(lv.stale_definition) if lv else False,
        }
    for oid, rec in sorted(world.objectives.items()):
        state = rec.get("state")
        if state == "active":
            d = derive(world, oid)
            report["active"][oid] = {
                "approval_valid": d.approval_valid,
                "needs_revalidation": d.needs_revalidation,
            }
        elif state == "proposed":
            report["proposed"].append(oid)
        if state in ("active", "proposed") and revisit(world, oid)["result"] == "candidate":
            report["fired_revisits"].append(oid)
    return report


def _measurement_reason(lv: LastValue | None) -> str:
    if lv is None:
        return "never_measured"
    return "stale_definition" if lv.stale_definition else "measured"


_GAP_OBJECTIVE_KEYS: tuple[str, ...] = (
    "state",
    "title",
    "hypothesis",
    "outcome_id",
    "observed",
    "rejected",
    "scope",
    "non_scope",
)


def gap_report(root: Path) -> dict[str, Any]:
    """The `hm world gap` payload — the proposer's read, LLM-free (ADR-001).

    A sibling of `status_report`, not an extension: `status` is what the gate-adjacent prose
    reads and stays frozen, while a proposer needs what `status` deliberately omits — closed and
    dropped records with their `rejected[]` (so rejected work is not re-proposed) and WHY an
    outcome cannot be judged (`never_measured` vs `stale_definition`, which `gap` folds into one
    `unevaluable`). The invalid world returns `status_report`'s payload verbatim: one shape.
    One `load_world` feeds both halves, so a row can never mix two disk snapshots.
    """
    try:
        world = load_world(root)
    except IntentInvalidError as exc:
        return _invalid_payload(exc)
    status = _status_payload(world)
    report: dict[str, Any] = {
        "state": status["state"],
        "mission": status["mission"],
        "outcomes": {},
        "objectives": {},
        "conflicts": status["conflicts"],
        "unknowns": status["unknowns"],
        "fired_revisits": status["fired_revisits"],
        "broken_references": status["broken_references"],
    }
    for outcome in world.intent.outcomes:
        lv = last_value(world, outcome.id)
        report["outcomes"][outcome.id] = {
            **status["outcomes"][outcome.id],
            "reason": _measurement_reason(lv),
            "how_measured": outcome.how_measured,
            "higher_is_better": outcome.higher_is_better,
        }
    for oid, rec in sorted(world.objectives.items()):
        report["objectives"][oid] = {key: rec.get(key) for key in _GAP_OBJECTIVE_KEYS}
    return report


# ── writers: each touches exactly one file ───────────────────────────────────


def _load_assumptions_doc(root: Path) -> dict[str, Any]:
    path = assumptions_path(root)
    if not path.exists():
        return {"schema_version": KNOWN_MAJOR, "assumptions": []}
    errors = validate_assumptions(path)
    if errors:
        raise WorldError(errors[0].field, errors[0].message)
    raw, _ = _read_yaml(path)
    return raw  # type: ignore[no-any-return]


def _find(doc: dict[str, Any], aid: str) -> dict[str, Any]:
    for rec in doc["assumptions"]:
        if rec["id"] == aid:
            return rec  # type: ignore[no-any-return]
    raise WorldError("id", f"no assumption {aid!r}")


def observe(
    root: Path,
    assumption_id: str,
    *,
    text: str,
    observed_at: str,
    relation: str,
    claim: str | None = None,
) -> dict[str, Any]:
    """File an observation by relation; `contradicts` → conflict with both sides kept."""
    if relation not in RELATIONS:
        raise WorldError("relation", f"must be one of {RELATIONS}")
    if not isinstance(text, str) or not text.strip():
        raise WorldError("text", "must be a non-empty string")
    stamp = normalise_timestamp(observed_at, "observed_at")
    if relation == "supersedes" and (not isinstance(claim, str) or not claim.strip()):
        raise WorldError("claim", "supersedes needs the new claim")
    doc = _load_assumptions_doc(root)
    rec = _find(doc, assumption_id)
    rec.setdefault("evidence", []).append(
        {"text": text, "observed_at": stamp, "relation": relation}
    )
    if relation == "contradicts":
        rec["status"] = "conflict"
    elif relation == "supersedes":
        rec.setdefault("history", []).append(rec["claim"])
        rec["claim"] = claim
    _dump_yaml(assumptions_path(root), doc)
    return rec


def resolve(root: Path, assumption_id: str, *, status: str, claim: str) -> dict[str, Any]:
    """The only exit from `conflict`; refused from any other status or to `conflict`."""
    if status not in RESOLVE_TARGETS:
        raise WorldError("status", f"must be one of {RESOLVE_TARGETS}")
    if not isinstance(claim, str) or not claim.strip():
        raise WorldError("claim", "must be a non-empty string")
    doc = _load_assumptions_doc(root)
    rec = _find(doc, assumption_id)
    if rec.get("status") != "conflict":
        raise WorldError("status", f"{assumption_id!r} is {rec.get('status')!r}, not in conflict")
    rec.setdefault("history", []).append(rec["claim"])
    rec["claim"] = claim
    rec["status"] = status
    _dump_yaml(assumptions_path(root), doc)
    return rec


def record_value(
    root: Path, *, outcome_id: str, value: Any, observed_at: Any, evidence: Any
) -> dict[str, Any]:
    """A human-recorded outcome value with provenance; every defect is refused by field name."""
    loaded = intent_mod.load_intent(intent_path(root))
    outcome = next((o for o in loaded.outcomes if o.id == outcome_id), None)
    if outcome is None:
        raise WorldError("outcome_id", f"{outcome_id!r} is not an intent outcome")
    if not _is_number(value):
        raise WorldError("value", "must be a number")
    stamp = normalise_timestamp(observed_at, "observed_at")
    if not isinstance(evidence, str) or not evidence.strip():
        raise WorldError("evidence", "must be a non-empty string")
    path = outcomes_path(root)
    doc: dict[str, Any]
    if path.exists():
        errors = validate_outcomes(path, intent_outcomes={o.id: o for o in loaded.outcomes})
        if errors:
            raise WorldError(errors[0].field, errors[0].message)
        doc, _ = _read_yaml(path)
    else:
        doc = {"schema_version": KNOWN_MAJOR, "values": []}
    row = {
        "outcome_id": outcome_id,
        "value": value,
        "observed_at": stamp,
        "evidence": evidence,
        "definition_hash": definition_hash(
            outcome.target, outcome.how_measured, outcome.higher_is_better
        ),
    }
    doc["values"].append(row)
    _dump_yaml(path, doc)
    return row


def _load_objective(root: Path, objective_id: str) -> tuple[World, dict[str, Any]]:
    world = load_world(root)
    if objective_id in world.broken:
        first = world.broken[objective_id][0]
        raise WorldError(first.field, first.message)
    rec = world.objectives.get(objective_id)
    if rec is None:
        raise WorldError("objective", f"no objective {objective_id!r}")
    return world, rec


def _git_user_name(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "config", "user.name"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def approve(root: Path, objective_id: str) -> dict[str, Any]:
    """Bind an approval to the canonical payload with git provenance; terminal records refuse."""
    world, rec = _load_objective(root, objective_id)
    if rec["state"] in TERMINAL_STATES:
        raise WorldError(
            "state", f"{objective_id!r} is {rec['state']}; a terminal record is not re-approved"
        )
    # SPEC 'Approval provenance': the name is read at the BASE root, not the checkout the record
    # lives in — a task worktree may carry a per-worktree config that is not the approver.
    name = _git_user_name(resolve_base_root(root))
    if not name:
        raise WorldError("approved_by", "git config user.name is empty; set it before approving")
    target = world.outcome_by_id[rec["outcome_id"]].target
    rec["approval"] = {
        "content_hash": approval_hash(rec, target),
        "approved_by": name,
        "approved_at": _now_iso(),
        "approved_target": target,
    }
    _write_record(world, root, objective_id, rec)
    return rec


def transition(
    root: Path,
    objective_id: str,
    target_state: str,
    *,
    observed: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Apply one table transition; everything outside the table is refused and writes nothing."""
    if target_state not in OBJECTIVE_STATES:
        raise WorldError("state", f"must be one of {OBJECTIVE_STATES}")
    world, rec = _load_objective(root, objective_id)
    src = rec["state"]
    if (src, target_state) not in LEGAL_TRANSITIONS:
        raise WorldError("state", f"{src}→{target_state} is not a legal transition")
    if target_state == "active" and derive(world, objective_id).approval_valid is not True:
        raise WorldError("approval", "activation needs a valid approval")
    if target_state == "closed":
        if observed not in OBSERVED_VALUES:
            raise WorldError("observed", f"must be one of {OBSERVED_VALUES}")
        if not isinstance(note, str) or not note.strip():
            raise WorldError("note", "must be a non-empty string")
        rec["observed"] = observed
        rec["note"] = note
        rec["closed_at"] = _now_iso()
    if target_state == "proposed":
        rec["approval"] = None
    rec["state"] = target_state
    _write_record(world, root, objective_id, rec)
    return rec


@dataclass(frozen=True)
class CapWarning:
    count: int
    cap: int


@dataclass(frozen=True)
class ActivateResult:
    activated: bool
    warning: CapWarning | None


def activate(root: Path, objective_id: str, *, cap: int = 1) -> ActivateResult:
    """Activate, and on the SAME call warn when the active count exceeds the cap (never lock)."""
    transition(root, objective_id, "active")
    world = load_world(root)
    count = sum(1 for r in world.objectives.values() if r.get("state") == "active")
    return ActivateResult(activated=True, warning=CapWarning(count, cap) if count > cap else None)


def close(
    root: Path, objective_id: str, *, observed: str | None, note: str | None
) -> dict[str, Any]:
    return transition(root, objective_id, "closed", observed=observed, note=note)


def edit_objective(root: Path, objective_id: str, **fields: Any) -> dict[str, Any]:
    """Edit non-state fields of a proposed/active record; terminal records refuse every edit."""
    world, rec = _load_objective(root, objective_id)
    if rec["state"] in TERMINAL_STATES:
        raise WorldError(
            "state", f"{objective_id!r} is {rec['state']}; terminal records are immutable"
        )
    for key, value in fields.items():
        if key not in _OBJECTIVE_KEYS or key in ("id", "state", "schema_version", "approval"):
            raise WorldError(key, "not an editable field")
        rec[key] = value
    errs = validate_objective_record(root, world, rec, objective_id)
    if errs:
        raise WorldError(errs[0].field, errs[0].message)
    _write_record(world, root, objective_id, rec)
    return rec


PLAYBOOK_BODY = """\
## Problem



## Proposed outcome



## Affected users and systems



## Constraints



## Open questions

"""


def new_objective(
    root: Path,
    objective_id: str,
    *,
    title: str,
    hypothesis: str,
    scope: list[str],
    outcome_id: str,
    non_scope: list[str] | None = None,
    from_proposal: bool = False,
    candidates: int | None = None,
    declined: list[str] | None = None,
) -> dict[str, Any]:
    """Write the INTENT skeleton the operator then fills in prose (ADR-004).

    Every refusal happens before the filesystem is touched: a hand-written frontmatter is the
    class of error that produces `broken` records, so the verb owns the machine half and leaves
    the five Playbook headings empty for the human.

    `from_proposal` is the proposer's path (PLAN-objective-gap-proposal ADR-003): the declined
    candidates of the same turn pre-fill `rejected[]` — the only provenance a declined candidate
    gets, so the next gap pass does not re-propose it — and exactly one `objective_proposed`
    ledger row is appended AFTER the record write. `candidates`/`declined` are proposal-only;
    accepting them without the flag would let a wrong combination pass silently.
    """
    if not _OBJECTIVE_ID_RE.match(objective_id):
        raise WorldError("id", f"{objective_id!r} must match [A-Z0-9-]+")
    declined_titles = list(declined or [])
    if not from_proposal and (candidates is not None or declined_titles):
        raise WorldError(
            "from_proposal", "--candidates/--declined are proposal-only; pass --from-proposal"
        )
    if from_proposal:
        if candidates is None:
            raise WorldError("candidates", "--from-proposal requires --candidates <N>")
        if candidates < len(declined_titles) + 1:
            raise WorldError(
                "candidates",
                f"--candidates must be at least the declined count + 1 "
                f"({len(declined_titles) + 1}), got {candidates}",
            )
    path = objective_doc_path(root, objective_id)
    if path.exists():
        raise WorldError("id", f"{objective_id!r} already exists at {path}; refusing to overwrite")
    world = load_world(root)
    if outcome_id not in world.outcome_by_id:
        raise WorldError("outcome_id", f"{outcome_id!r} is not an outcome in intent.yaml")
    rec: dict[str, Any] = {
        "id": objective_id,
        "title": title,
        "hypothesis": hypothesis,
        "scope": list(scope),
        "outcome_id": outcome_id,
        "state": "proposed",
        "created_at": _now_iso(),
        "schema_version": intent_mod.KNOWN_MAJOR,
        "non_scope": list(non_scope or []),
        "rejected": declined_titles,
        "depends_on": [],
        "approval": None,
        "revisit_when": None,
        "observed": None,
        "note": None,
        "closed_at": None,
    }
    errs = _validate_objective_raw(
        path, rec, intent_outcomes=world.outcome_by_id, assumption_ids=set(world.assumptions)
    )
    if errs:
        raise WorldError(errs[0].field, errs[0].message)
    _dump_intent(path, rec, PLAYBOOK_BODY.encode("utf-8"))
    if from_proposal:
        assert candidates is not None  # guarded above
        _record_proposal(root, objective_id, candidates=candidates)
    return rec


def _record_proposal(root: Path, objective_id: str, *, candidates: int) -> None:
    """The adoption row, at the BASE root's ledger — a worktree's ledger dies with `task-land`.

    A failed append is a warning, not a retry: the record already exists and `new_objective`
    refuses to overwrite, so retrying would fail on the id. Exit 0 keeps the verb's contract
    ("the record stands"); the stderr line is what makes the missing row visible.
    """
    base = resolve_base_root(root)
    try:
        autopilot_ledger.append_event(
            base,
            event="objective_proposed",
            fields={"objective": objective_id, "candidates": candidates, "accepted": 1},
            observability_dir=base / ".claude" / "observability",
        )
    except (OSError, ValueError) as exc:
        print(f"[world] objective_proposed NOT recorded: {exc}", file=sys.stderr)


def validate_objective_record(
    root: Path, world: World, rec: dict[str, Any], objective_id: str
) -> list[IntentError]:
    """Run the on-disk rule set over an in-memory record; writes nothing.

    Same function as the file validator, so a record this accepts is one `load_world` accepts —
    an edit can never persist a record the next read reports as broken.
    """
    return _validate_objective_raw(
        objective_doc_path(root, objective_id),
        rec,
        intent_outcomes=world.outcome_by_id,
        assumption_ids=set(world.assumptions),
    )


# ── CLI ──────────────────────────────────────────────────────────────────────


def _emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip())


def _changed_path(root: Path, objective_id: str) -> str:
    """The `changed:` line the skill shows the operator — the INTENT document, never the
    retired `objectives/<id>.yaml` literal (review findings ec50e469 / a30ea560)."""
    return objective_doc_path(root, objective_id).relative_to(root).as_posix()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hm world")
    parser.add_argument("--root", default=None, help="checkout root (default: git toplevel of cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    g = sub.add_parser("gap")
    g.add_argument("--json", action="store_true")

    a = sub.add_parser("assume")
    asub = a.add_subparsers(dest="verb", required=True)
    ob = asub.add_parser("observe")
    ob.add_argument("id")
    ob.add_argument("--relation", required=True, choices=RELATIONS)
    ob.add_argument("--text", required=True)
    ob.add_argument("--observed-at", required=True, dest="observed_at")
    ob.add_argument("--claim", default=None)
    ob.add_argument("--json", action="store_true")
    rs = asub.add_parser("resolve")
    rs.add_argument("id")
    rs.add_argument("--status", required=True, choices=RESOLVE_TARGETS)
    rs.add_argument("--claim", required=True)
    rs.add_argument("--json", action="store_true")

    o = sub.add_parser("outcome")
    osub = o.add_subparsers(dest="verb", required=True)
    rc = osub.add_parser("record")
    rc.add_argument("id")
    rc.add_argument("--value", required=True, type=float)
    rc.add_argument("--observed-at", required=True, dest="observed_at")
    rc.add_argument("--evidence", required=True)
    rc.add_argument("--json", action="store_true")

    j = sub.add_parser("objective")
    jsub = j.add_subparsers(dest="verb", required=True)
    # Literal `add_parser` names on purpose: the command-surface gate reads them by AST and
    # the registry must list every one, so a loop over a tuple would hide six verbs from it.
    nw = jsub.add_parser("new")
    nw.add_argument("id")
    nw.add_argument("--title", required=True)
    nw.add_argument("--hypothesis", required=True)
    nw.add_argument("--scope", action="append", required=True)
    nw.add_argument("--outcome", required=True, dest="outcome_id")
    nw.add_argument("--non-scope", action="append", default=None, dest="non_scope")
    nw.add_argument("--from-proposal", action="store_true", dest="from_proposal")
    nw.add_argument("--candidates", type=int, default=None)
    nw.add_argument("--declined", action="append", default=None)
    nw.add_argument("--json", action="store_true")
    ap = jsub.add_parser("approve")
    ac = jsub.add_parser("activate")
    ac.add_argument("--cap", type=int, default=1)
    dr = jsub.add_parser("drop")
    ro = jsub.add_parser("reopen")
    sh = jsub.add_parser("show")
    rv = jsub.add_parser("revisit")
    for p in (ap, ac, dr, ro, sh, rv):
        p.add_argument("id")
        p.add_argument("--json", action="store_true")
    cl = jsub.add_parser("close")
    cl.add_argument("id")
    cl.add_argument("--observed", required=True, choices=OBSERVED_VALUES)
    cl.add_argument("--note", required=True)
    cl.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Registry-driven misroute guard (PLAN-command-surface-registry ADR-004), as every
    # subparser module carries: `hm world on` → the module that owns `on`, not a traceback.
    guard = command_registry.guard_or_none("world", argv)
    if guard is not None:
        return guard
    args = _parser().parse_args(argv)
    root = Path(args.root) if args.root else checkout_root(Path.cwd())
    as_json = bool(getattr(args, "json", False))
    try:
        if args.cmd == "status":
            _emit(status_report(root), as_json=as_json)
            return 0
        if args.cmd == "gap":
            _emit(gap_report(root), as_json=as_json)
            return 0
        if args.cmd == "assume":
            if args.verb == "observe":
                rec = observe(
                    root,
                    args.id,
                    text=args.text,
                    observed_at=args.observed_at,
                    relation=args.relation,
                    claim=args.claim,
                )
            else:
                rec = resolve(root, args.id, status=args.status, claim=args.claim)
            _emit({"changed": "assumptions.yaml", "assumption": rec}, as_json=as_json)
            return 0
        if args.cmd == "outcome":
            value = _json_number(args.value)
            row = record_value(
                root,
                outcome_id=args.id,
                value=value,
                observed_at=args.observed_at,
                evidence=args.evidence,
            )
            _emit({"changed": "outcomes.yaml", "value": row}, as_json=as_json)
            return 0
        # objective verbs
        if args.verb == "new":
            rec = new_objective(
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
            _emit({"changed": _changed_path(root, args.id), "record": rec}, as_json=as_json)
            return 0
        if args.verb == "show":
            _, rec = _load_objective(root, args.id)
            _emit(rec, as_json=as_json)
            return 0
        if args.verb == "revisit":
            _emit(revisit(load_world(root), args.id), as_json=as_json)
            return 0
        if args.verb == "approve":
            rec = approve(root, args.id)
        elif args.verb == "activate":
            result = activate(root, args.id, cap=args.cap)
            payload: dict[str, Any] = {"changed": _changed_path(root, args.id), "activated": True}
            if result.warning is not None:
                payload["warning"] = {
                    "active_count": result.warning.count,
                    "cap": result.warning.cap,
                    "message": "active objectives exceed the cap; proceeding (warn, never lock)",
                }
            _emit(payload, as_json=as_json)
            return 0
        elif args.verb == "drop":
            rec = transition(root, args.id, "dropped")
        elif args.verb == "reopen":
            rec = transition(root, args.id, "proposed")
        else:
            rec = close(root, args.id, observed=args.observed, note=args.note)
        _emit({"changed": _changed_path(root, args.id), "objective": rec}, as_json=as_json)
        return 0
    except (WorldError, IntentInvalidError) as exc:
        if isinstance(exc, WorldError):
            err = {"field": exc.field, "message": exc.message}
        else:
            err = {"field": exc.errors[0].field, "message": exc.errors[0].message}
        _emit({"error": err}, as_json=as_json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
