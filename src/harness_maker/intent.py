"""`.claude/intent.yaml` — why the project exists: loader, validator, write-if-absent skeleton."""

from __future__ import annotations

import argparse
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from harness_maker.io_utils import atomic_write

#: The one schema major this build reads. Any other major — older or newer — is refused
#: (SPEC "Data versioning"): this file is long-lived, git-shared and hand-edited, and a silent
#: read of a foreign version corrupts approvals downstream.
KNOWN_MAJOR = 1

REQUIRED_FIELDS: frozenset[str] = frozenset({"schema_version", "mission", "outcomes"})
OPTIONAL_FIELDS: frozenset[str] = frozenset(
    {"vision", "non_negotiables", "non_scope", "unknowns", "owners"}
)
RECOGNISED_FIELDS: frozenset[str] = REQUIRED_FIELDS | OPTIONAL_FIELDS
LIST_FIELDS: frozenset[str] = frozenset({"outcomes", "non_negotiables", "non_scope", "unknowns"})
OWNER_ROLES = frozenset({"owner", "dri", "team"})
STRING_FIELDS: frozenset[str] = frozenset({"mission", "vision"})
OUTCOME_FIELDS: tuple[str, ...] = (
    "id",
    "description",
    "target",
    "higher_is_better",
    "how_measured",
    "measure",
)
#: `measure` is the one optional outcome field (SPEC-outcome-measure S1).
OPTIONAL_OUTCOME_FIELDS: frozenset[str] = frozenset({"measure"})
MEASURE_FIELDS: tuple[str, ...] = ("cmd", "select", "cwd", "timeout_s")
MEASURE_CWDS: tuple[str, ...] = ("base", "checkout")
SELECT_PREFIXES: tuple[str, ...] = ("json:", "regex:")
SELECT_LAST_NUMBER = "last-number"
DEFAULT_MEASURE_TIMEOUT_S = 300
_ID_RE = re.compile(r"^[a-z0-9_]+$")

SKELETON = """\
# .claude/intent.yaml — why this project exists. Human-written; nothing here is generated.
#
# Fill `purpose.statement` first. Until it and `metrics` are both filled,
# `hm intent status`
# reports `not_filled_in`. A file with metrics but no purpose statement is a validation error.
#
# Withdrawal criterion (SPEC-withdrawal-criterion-window): if 10 wrapups land with no signal
# from this layer — nothing measured, no intent created, approved or closed — and no
# `revisit_when` currently reads `candidate`, this layer is unused and is removed. The count
# runs from the last signal, or from the day the file was filled in when there has never been
# one. `hm intent status --json` measures it: `withdrawal.due` is true when the criterion holds.
schema_version: 1
purpose:
  statement: ""
  vision: ""
# metrics:
#   - id: dead_rendered_bytes          # [a-z0-9_]+, unique
#     description: share of rendered command bytes with zero recorded invocations
#     target: 10                       # a number; compared to the last recorded value
#     higher_is_better: false
#     how_measured: "hm economics stages + metrics invocation counts"
#     measure:                         # optional — lets `hm intent metric measure` record it
#       cmd: "uv run hm economics report --root ."   # argv (shlex), never a shell
#       select: "json:report.carry_ratio"  # json:<dotted.path> | regex:<one group> | last-number
#       cwd: base                        # base (default; observability lives there) | checkout
#       timeout_s: 300                   # optional, positive
metrics: []
rules: []
out_of_scope: []
open_questions: []
owners: {}
"""


@dataclass(frozen=True)
class IntentError:
    """One validation failure; `field` names the offending key (dotted / indexed for nesting)."""

    field: str
    message: str


class IntentInvalidError(ValueError):
    """Raised by `load_intent` when validation fails; carries every error."""

    def __init__(self, path: Path, errors: list[IntentError]) -> None:
        self.path = path
        self.errors = errors
        super().__init__(f"{path}: " + "; ".join(f"{e.field}: {e.message}" for e in errors))


@dataclass(frozen=True)
class Measure:
    """A machine-runnable measurement; edits stale history because the hash covers it."""

    cmd: str
    select: str
    cwd: str = "base"
    timeout_s: int = DEFAULT_MEASURE_TIMEOUT_S


@dataclass(frozen=True)
class Outcome:
    id: str
    description: str
    target: int | float
    higher_is_better: bool
    how_measured: str
    measure: Measure | None = None


@dataclass(frozen=True)
class Intent:
    schema_version: int
    mission: str
    vision: str
    outcomes: tuple[Outcome, ...]
    non_negotiables: tuple[str, ...]
    non_scope: tuple[str, ...]
    unknowns: tuple[str, ...]
    owners: dict[str, str]
    open_questions: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def purpose(self) -> dict[str, str]:
        return {"statement": self.mission, "vision": self.vision}

    @property
    def metrics(self) -> tuple[Outcome, ...]:
        return self.outcomes

    @property
    def rules(self) -> tuple[str, ...]:
        return self.non_negotiables

    @property
    def out_of_scope(self) -> tuple[str, ...]:
        return self.non_scope


def skeleton_text() -> str:
    return SKELETON


def write_skeleton_if_absent(path: Path) -> bool:
    """Create the typed empty skeleton; never touch an existing file, empty or not.

    Existence is the whole test: a `touch`ed zero-byte file is a file the user owns.
    """
    if path.exists():
        return False
    atomic_write(path, SKELETON)
    return True


def _major_of(found: Any) -> int | None:
    """The one reading of `schema_version` (AC-008): an int, or the digits before the first dot
    of a string. The validator and the loader must agree, or `"1.0"` validates and then crashes."""
    if isinstance(found, int) and not isinstance(found, bool):
        return found
    if isinstance(found, str):
        head = found.split(".", 1)[0]
        return int(head) if head.isdigit() else None
    return None


def schema_version_error(
    path: Path, raw: Any, *, field: str = "schema_version"
) -> IntentError | None:
    """Shared with `world`: refuse a missing or foreign-major `schema_version`, naming the file.

    The message names the path, the found version and the known major, because the refusal
    is the only diagnostic a hand-editor gets.
    """
    if not isinstance(raw, dict) or field not in raw:
        return IntentError(
            field, f"{path}: schema_version missing (this build reads {KNOWN_MAJOR})"
        )
    found = raw[field]
    major = _major_of(found)
    if major != KNOWN_MAJOR:
        return IntentError(
            field,
            f"{path}: schema_version {found!r} is not readable by this build (known major "
            f"{KNOWN_MAJOR}); refusing rather than guessing",
        )
    return None


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate_select(prefix: str, select: Any, errors: list[IntentError]) -> None:
    if not isinstance(select, str) or not select:
        errors.append(IntentError(f"{prefix}.select", "must be a non-empty string"))
        return
    if select == SELECT_LAST_NUMBER:
        return
    if select.startswith("json:"):
        if not select[len("json:") :]:
            errors.append(IntentError(f"{prefix}.select", "json: needs a dotted path"))
        return
    if select.startswith("regex:"):
        try:
            groups = re.compile(select[len("regex:") :]).groups
        except re.error as exc:
            errors.append(IntentError(f"{prefix}.select", f"regex does not compile: {exc}"))
            return
        if groups != 1:
            errors.append(IntentError(f"{prefix}.select", "regex must have exactly one group"))
        return
    errors.append(
        IntentError(
            f"{prefix}.select",
            f"must be json:<path>, regex:<pattern> or exactly {SELECT_LAST_NUMBER!r}",
        )
    )


def _validate_measure(prefix: str, raw: Any, errors: list[IntentError]) -> None:
    """Refuse a bad block at load, before any subprocess exists (ADR-001)."""
    if not isinstance(raw, dict):
        errors.append(IntentError(prefix, "must be a mapping"))
        return
    for key in ("cmd", "select"):
        if key not in raw:
            errors.append(IntentError(f"{prefix}.{key}", "missing"))
    for key in raw:
        if key not in MEASURE_FIELDS:
            errors.append(IntentError(f"{prefix}.{key}", "unknown measure field"))
    if "cmd" in raw:
        cmd = raw["cmd"]
        argv: list[str] | None = None
        if isinstance(cmd, str):
            try:
                argv = shlex.split(cmd)
            except ValueError as exc:
                errors.append(IntentError(f"{prefix}.cmd", f"not a shell word list: {exc}"))
        if argv is not None or not isinstance(cmd, str):
            if not argv:
                errors.append(IntentError(f"{prefix}.cmd", "must be a non-empty argv string"))
            elif argv[0].startswith("-"):
                errors.append(
                    IntentError(f"{prefix}.cmd", "first token must be a program, not an option")
                )
    if "select" in raw:
        _validate_select(prefix, raw["select"], errors)
    if "cwd" in raw and raw["cwd"] not in MEASURE_CWDS:
        errors.append(IntentError(f"{prefix}.cwd", f"must be one of {'|'.join(MEASURE_CWDS)}"))
    if "timeout_s" in raw:
        t = raw["timeout_s"]
        if isinstance(t, bool) or not isinstance(t, int) or t <= 0:
            errors.append(IntentError(f"{prefix}.timeout_s", "must be a positive int"))


def _validate_outcome(i: int, raw: Any, seen: set[str], errors: list[IntentError]) -> None:
    prefix = f"outcomes[{i}]"
    if not isinstance(raw, dict):
        errors.append(IntentError(prefix, "must be a mapping"))
        return
    for key in OUTCOME_FIELDS:
        if key not in raw and key not in OPTIONAL_OUTCOME_FIELDS:
            errors.append(IntentError(f"{prefix}.{key}", "missing"))
    for key in raw:
        if key not in OUTCOME_FIELDS:
            errors.append(IntentError(f"{prefix}.{key}", "unknown outcome field"))
    oid = raw.get("id")
    if "id" in raw:
        if not isinstance(oid, str) or not _ID_RE.match(oid):
            errors.append(IntentError(f"{prefix}.id", "must match [a-z0-9_]+"))
        elif oid in seen:
            errors.append(IntentError("outcomes[].id", f"duplicate id {oid!r}"))
        else:
            seen.add(oid)
    if "description" in raw and not isinstance(raw["description"], str):
        errors.append(IntentError(f"{prefix}.description", "must be a string"))
    if "target" in raw and not _is_number(raw["target"]):
        errors.append(IntentError(f"{prefix}.target", "must be a number"))
    if "higher_is_better" in raw and not isinstance(raw["higher_is_better"], bool):
        errors.append(IntentError(f"{prefix}.higher_is_better", "must be a bool"))
    if "how_measured" in raw and not isinstance(raw["how_measured"], str):
        errors.append(IntentError(f"{prefix}.how_measured", "must be a string"))
    if "measure" in raw and raw["measure"] is not None:
        _validate_measure(f"{prefix}.measure", raw["measure"], errors)


def _validate_raw(path: Path, raw: Any) -> list[IntentError]:
    errors: list[IntentError] = []
    if not isinstance(raw, dict):
        return [IntentError("file", f"{path}: top level must be a mapping")]
    from harness_maker.intent_vocabulary import legacy_project

    try:
        raw = legacy_project(raw)
    except ValueError as exc:
        return [IntentError("file", str(exc))]
    sv = schema_version_error(path, raw)
    if sv is not None:
        errors.append(sv)
    for key in raw:
        if key not in RECOGNISED_FIELDS:
            errors.append(IntentError(str(key), "unknown top-level key"))
    for key in sorted(REQUIRED_FIELDS - {"schema_version"}):
        if key not in raw:
            errors.append(IntentError(key, "missing required key"))
    for key in STRING_FIELDS:
        if key in raw and not isinstance(raw[key], str):
            errors.append(IntentError(key, "must be a string"))
    if "owners" in raw:
        owners = raw["owners"]
        if isinstance(owners, dict):
            for role, person in owners.items():
                if role not in OWNER_ROLES:
                    errors.append(IntentError(f"owners.{role}", "unknown role"))
                elif not isinstance(person, str):
                    errors.append(IntentError(f"owners.{role}", "must be a string"))
        elif isinstance(owners, list):
            for j, person in enumerate(owners):
                if not isinstance(person, str):
                    errors.append(IntentError(f"owners[{j}]", "must be a string"))
        else:
            errors.append(IntentError("owners", "must be a role map or legacy list of strings"))
    for key in LIST_FIELDS:
        if key in raw and not isinstance(raw[key], list):
            errors.append(IntentError(key, "must be a list"))
    for key in LIST_FIELDS - {"outcomes"}:
        if isinstance(raw.get(key), list):
            for j, item in enumerate(raw[key]):
                if not isinstance(item, str):
                    errors.append(IntentError(f"{key}[{j}]", "must be a string"))
    outcomes = raw.get("outcomes")
    if isinstance(outcomes, list):
        seen: set[str] = set()
        for i, item in enumerate(outcomes):
            _validate_outcome(i, item, seen, errors)
        # Skeleton-validity row: the non-empty mission rule is waived ONLY when outcomes is
        # empty too. A half-filled file must not hide as a skeleton.
        if isinstance(raw.get("mission"), str) and not raw["mission"].strip() and outcomes:
            errors.append(IntentError("mission", "must be non-empty once outcomes exist"))
    return errors


def _read_raw(path: Path) -> tuple[Any, IntentError | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, IntentError("file", f"{path}: {exc}")
    try:
        return yaml.safe_load(text), None
    except yaml.YAMLError as exc:
        return None, IntentError("file", f"{path}: not valid YAML: {exc}")


def validate_intent(path: Path) -> list[IntentError]:
    raw, err = _read_raw(path)
    if err is not None:
        return [err]
    return _validate_raw(path, raw)


def _strs(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    return tuple(str(x) for x in raw.get(key) or [])


def load_intent(path: Path) -> Intent:
    raw, err = _read_raw(path)
    if err is not None:
        raise IntentInvalidError(path, [err])
    return intent_from_raw(path, raw)


def intent_from_raw(path: Path, raw: Any) -> Intent:
    """The one construction rule, shared with readers of historical blobs (`world` withdrawal)."""
    errors = _validate_raw(path, raw)
    if errors:
        raise IntentInvalidError(path, errors)
    assert isinstance(raw, dict)
    from harness_maker.intent_vocabulary import legacy_project, project_questions

    questions = project_questions(raw)
    raw = legacy_project(raw)
    major = _major_of(raw["schema_version"])
    assert major is not None  # validated above
    return Intent(
        schema_version=major,
        open_questions=tuple(questions),
        mission=raw["mission"],
        vision=raw.get("vision") or "",
        outcomes=tuple(
            Outcome(
                id=o["id"],
                description=o["description"],
                target=o["target"],
                higher_is_better=o["higher_is_better"],
                how_measured=o["how_measured"],
                measure=_measure_of(o.get("measure")),
            )
            for o in raw["outcomes"]
        ),
        non_negotiables=_strs(raw, "non_negotiables"),
        non_scope=_strs(raw, "non_scope"),
        unknowns=_strs(raw, "unknowns"),
        owners=(
            dict(raw["owners"])
            if isinstance(raw.get("owners"), dict)
            else {"team": ", ".join(raw["owners"])}
            if raw.get("owners")
            else {}
        ),
    )


def _measure_of(raw: Any) -> Measure | None:
    if raw is None:
        return None
    return Measure(
        cmd=raw["cmd"],
        select=raw["select"],
        cwd=raw.get("cwd", "base"),
        timeout_s=raw.get("timeout_s", DEFAULT_MEASURE_TIMEOUT_S),
    )


def is_not_filled_in(intent: Intent) -> bool:
    """The skeleton state: mission empty AND no outcomes — the one state where that is legal."""
    return not intent.mission.strip() and not intent.outcomes


def _parser() -> argparse.ArgumentParser:
    from harness_maker import world

    parser = argparse.ArgumentParser(prog="hm intent")
    parser.add_argument("--root", default=None, help="checkout root (default: git toplevel of cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    mg = sub.add_parser("migrate")
    mg.add_argument("--json", action="store_true")

    a = sub.add_parser("question")
    asub = a.add_subparsers(dest="verb", required=True)
    ob = asub.add_parser("observe")
    ob.add_argument("id")
    ob.add_argument("--relation", required=True, choices=world.RELATIONS)
    ob.add_argument("--text", required=True)
    ob.add_argument("--observed-at", required=True, dest="observed_at")
    ob.add_argument("--claim", default=None)
    ob.add_argument("--locator", default=None)
    ob.add_argument("--json", action="store_true")
    ad = asub.add_parser("add")
    ad.add_argument("id")
    ad.add_argument("--claim", required=True)
    ad.add_argument("--status", required=True, choices=("open", "confirmed", "wrong"))
    ad.add_argument("--text", default=None)
    ad.add_argument("--observed-at", default=None, dest="observed_at")
    ad.add_argument("--locator", default=None)
    ad.add_argument("--json", action="store_true")
    rs = asub.add_parser("resolve")
    rs.add_argument("id")
    rs.add_argument("--status", required=True, choices=("open", "confirmed", "wrong"))
    rs.add_argument("--claim", required=True)
    rs.add_argument("--json", action="store_true")

    o = sub.add_parser("metric")
    osub = o.add_subparsers(dest="verb", required=True)
    rc = osub.add_parser("record")
    rc.add_argument("id")
    rc.add_argument("--value", required=True, type=float)
    rc.add_argument("--observed-at", required=True, dest="observed_at")
    rc.add_argument("--evidence", required=True)
    rc.add_argument("--json", action="store_true")
    ms = osub.add_parser("measure")
    ms.add_argument("id", nargs="?", default=None)
    ms.add_argument("--all", action="store_true", dest="all_outcomes")
    ms.add_argument("--dry-run", action="store_true", dest="dry_run")
    ms.add_argument("--json", action="store_true")

    jsub = sub
    # Literal `add_parser` names on purpose: the command-surface gate reads them by AST and
    # the registry must list every one, so a loop over a tuple would hide six verbs from it.
    nw = jsub.add_parser("new")
    nw.add_argument("id")
    nw.add_argument("--title", required=True)
    nw.add_argument("--statement", required=True, dest="hypothesis")
    nw.add_argument("--scope", action="append", required=True)
    nw.add_argument("--metric", required=True, dest="outcome_id")
    nw.add_argument("--out-of-scope", action="append", default=None, dest="non_scope")
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
    for p in (ap, ac, dr, ro, sh):
        p.add_argument("id")
        p.add_argument("--json", action="store_true")
    cl = jsub.add_parser("close")
    cl.add_argument("id")
    cl.add_argument("--observed", required=True, choices=world.OBSERVED_VALUES)
    cl.add_argument("--note", required=True)
    cl.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Lazy bridge: execution as __main__ must use the imported schema exception class."""
    from harness_maker import command_registry
    from harness_maker.intent_cli import main as cli_main

    guard = command_registry.guard_or_none("intent", argv)
    if guard is not None:
        return guard

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
