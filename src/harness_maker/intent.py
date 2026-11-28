"""`.claude/intent.yaml` — why the project exists: loader, validator, write-if-absent skeleton."""

from __future__ import annotations

import argparse
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from harness_maker.io_utils import atomic_write

#: The one schema major this build reads. Any other major — older or newer — is refused
#: (SPEC "Data versioning"): this file is long-lived, git-shared and hand-edited, and a silent
#: read of a foreign version corrupts approvals downstream.
KNOWN_MAJOR = 1

REQUIRED_FIELDS: frozenset[str] = frozenset({"schema_version", "purpose", "metrics"})
OPTIONAL_FIELDS: frozenset[str] = frozenset({"rules", "out_of_scope", "open_questions", "owners"})
RECOGNISED_FIELDS: frozenset[str] = REQUIRED_FIELDS | OPTIONAL_FIELDS
#: Pre-0.58 top-level keys: a file carrying any of them has not been migrated.
LEGACY_FIELDS: frozenset[str] = frozenset(
    {"mission", "vision", "outcomes", "non_negotiables", "non_scope", "unknowns"}
)
STRING_LIST_FIELDS: frozenset[str] = frozenset({"rules", "out_of_scope"})
OWNER_ROLES = frozenset({"owner", "dri", "team"})
QUESTION_STATUSES: tuple[str, ...] = ("open", "confirmed", "wrong")
RELATIONS: tuple[str, ...] = ("confirms", "supersedes", "contradicts")
_QUESTION_KEYS: frozenset[str] = frozenset(
    {"id", "claim", "status", "evidence", "history", "revisit_when"}
)
MIGRATE_HINT = "legacy intent layout: run `hm intent migrate` first"
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
    purpose: dict[str, str]
    metrics: tuple[Outcome, ...]
    rules: tuple[str, ...] = ()
    out_of_scope: tuple[str, ...] = ()
    owners: dict[str, str] = field(default_factory=dict)
    open_questions: tuple[dict[str, Any], ...] = ()


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
    """Shared with records and migrate: refuse a missing or foreign-major `schema_version`.

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
    prefix = f"metrics[{i}]"
    if not isinstance(raw, dict):
        errors.append(IntentError(prefix, "must be a mapping"))
        return
    for key in OUTCOME_FIELDS:
        if key not in raw and key not in OPTIONAL_OUTCOME_FIELDS:
            errors.append(IntentError(f"{prefix}.{key}", "missing"))
    for key in raw:
        if key not in OUTCOME_FIELDS:
            errors.append(IntentError(f"{prefix}.{key}", "unknown metric field"))
    oid = raw.get("id")
    if "id" in raw:
        if not isinstance(oid, str) or not _ID_RE.match(oid):
            errors.append(IntentError(f"{prefix}.id", "must match [a-z0-9_]+"))
        elif oid in seen:
            errors.append(IntentError("metrics[].id", f"duplicate id {oid!r}"))
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


def _validate_question(i: int, raw: Any, seen: set[str], errors: list[IntentError]) -> None:
    """Shape only: evidence keys beyond text/observed_at/relation (an old `locator`) are kept."""
    prefix = f"open_questions[{i}]"
    if not isinstance(raw, dict):
        errors.append(IntentError(prefix, "must be a mapping"))
        return
    for key in raw:
        if key not in _QUESTION_KEYS:
            errors.append(IntentError(f"{prefix}.{key}", "unknown key"))
    qid = raw.get("id")
    if not isinstance(qid, str) or not _ID_RE.match(qid):
        errors.append(IntentError(f"{prefix}.id", "must match [a-z0-9_]+"))
    elif qid in seen:
        errors.append(IntentError("open_questions[].id", f"duplicate id {qid!r}"))
    else:
        seen.add(qid)
    if not isinstance(raw.get("claim"), str) or not raw["claim"].strip():
        errors.append(IntentError(f"{prefix}.claim", "must be a non-empty string"))
    if raw.get("status") not in QUESTION_STATUSES:
        errors.append(IntentError(f"{prefix}.status", f"must be one of {QUESTION_STATUSES}"))
    evidence = raw.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append(IntentError(f"{prefix}.evidence", "must be a list"))
    else:
        for j, ev in enumerate(evidence):
            ep = f"{prefix}.evidence[{j}]"
            if not isinstance(ev, dict):
                errors.append(IntentError(ep, "must be a mapping"))
                continue
            if not isinstance(ev.get("text"), str) or not ev["text"].strip():
                errors.append(IntentError(f"{ep}.text", "must be a non-empty string"))
            if ev.get("relation") not in RELATIONS:
                errors.append(IntentError(f"{ep}.relation", f"must be one of {RELATIONS}"))
            if "observed_at" not in ev and "locator" not in ev:
                errors.append(IntentError(f"{ep}.observed_at", "missing"))
    history = raw.get("history", [])
    if not isinstance(history, list) or not all(isinstance(h, str) for h in history):
        errors.append(IntentError(f"{prefix}.history", "must be a list of strings"))


def _validate_raw(path: Path, raw: Any) -> list[IntentError]:
    if not isinstance(raw, dict):
        return [IntentError("file", f"{path}: top level must be a mapping")]
    if set(raw) & LEGACY_FIELDS:
        return [IntentError("layout", f"{path}: {MIGRATE_HINT}")]
    errors: list[IntentError] = []
    sv = schema_version_error(path, raw)
    if sv is not None:
        errors.append(sv)
    for key in raw:
        if key not in RECOGNISED_FIELDS:
            errors.append(IntentError(str(key), "unknown top-level key"))
    for key in sorted(REQUIRED_FIELDS - {"schema_version"}):
        if key not in raw:
            errors.append(IntentError(key, "missing required key"))
    purpose = raw.get("purpose")
    if "purpose" in raw and (
        not isinstance(purpose, dict)
        or set(purpose) != {"statement", "vision"}
        or not all(isinstance(v, str) for v in purpose.values())
    ):
        errors.append(IntentError("purpose", "must be {statement: str, vision: str}"))
    if "owners" in raw:
        owners = raw["owners"]
        if isinstance(owners, dict):
            for role, person in owners.items():
                if role not in OWNER_ROLES:
                    errors.append(IntentError(f"owners.{role}", "unknown role"))
                elif not isinstance(person, str):
                    errors.append(IntentError(f"owners.{role}", "must be a string"))
        elif isinstance(owners, list):
            errors.extend(
                IntentError(f"owners[{i}]", "must be a string")
                for i, person in enumerate(owners)
                if not isinstance(person, str)
            )
        else:
            errors.append(IntentError("owners", "must be a role map"))
    for key in STRING_LIST_FIELDS:
        val = raw.get(key, [])
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            errors.append(IntentError(key, "must be a list of strings"))
    questions = raw.get("open_questions", [])
    if not isinstance(questions, list):
        errors.append(IntentError("open_questions", "must be a list"))
    else:
        seen_q: set[str] = set()
        for i, q in enumerate(questions):
            _validate_question(i, q, seen_q, errors)
    metrics = raw.get("metrics")
    if "metrics" in raw and not isinstance(metrics, list):
        errors.append(IntentError("metrics", "must be a list"))
    elif isinstance(metrics, list):
        seen: set[str] = set()
        for i, item in enumerate(metrics):
            _validate_outcome(i, item, seen, errors)
        # The non-empty statement rule is waived ONLY when metrics is empty too: a half-filled
        # file must not hide as a skeleton.
        statement = purpose.get("statement") if isinstance(purpose, dict) else None
        if isinstance(statement, str) and not statement.strip() and metrics:
            errors.append(IntentError("purpose.statement", "must be non-empty once metrics exist"))
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
    errors = _validate_raw(path, raw)
    if errors:
        raise IntentInvalidError(path, errors)
    assert isinstance(raw, dict)
    major = _major_of(raw["schema_version"])
    assert major is not None  # validated above
    return Intent(
        schema_version=major,
        purpose=dict(raw["purpose"]),
        metrics=tuple(
            Outcome(
                id=o["id"],
                description=o["description"],
                target=o["target"],
                higher_is_better=o["higher_is_better"],
                how_measured=o["how_measured"],
                measure=_measure_of(o.get("measure")),
            )
            for o in raw["metrics"]
        ),
        rules=_strs(raw, "rules"),
        out_of_scope=_strs(raw, "out_of_scope"),
        owners=_owners(raw.get("owners")),
        open_questions=tuple(raw.get("open_questions") or []),
    )


def _owners(raw: Any) -> dict[str, str]:
    """A legacy list of names reads as the team role; the file is never rewritten for it."""
    if isinstance(raw, list):
        return {"team": ", ".join(raw)} if raw else {}
    return dict(raw or {})


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
    """The skeleton state: empty statement AND no metrics — the one state where that is legal."""
    return not intent.purpose.get("statement", "").strip() and not intent.metrics


#: Every free-text argument of the write verbs and its file twin: (dest, file dest, flag, multi).
#: Rendered recipes pass the file form so operator text never lands on a shell command line.
FILE_TWINS: tuple[tuple[str, str, str, bool], ...] = (
    ("claim", "claim_file", "--claim", False),
    ("text", "text_file", "--text", False),
    ("evidence", "evidence_file", "--evidence", False),
    ("note", "note_file", "--note", False),
    ("title", "title_file", "--title", False),
    ("statement", "statement_file", "--statement", False),
    ("scope", "scope_file", "--scope", True),
    ("out_of_scope", "out_of_scope_file", "--out-of-scope", True),
)

OBSERVED_VALUES: tuple[str, ...] = ("met", "missed", "no_data")

#: Verbs SPEC-intent-lean removed (IRR-001): each stays a subcommand that names its replacement
#: and exits 2, so a stale script or recipe fails loudly instead of being guessed at.
REMOVED_VERBS: dict[str, str] = {
    "approve": "a new goal is open from the start, no step needed",
    "activate": "a new goal is open from the start, no step needed",
    "reopen": "no step needed to keep working; for a closed goal, record a new one with "
    "`hm intent new`",
    "drop": "use `hm intent close <id> --observed no_data --note-file <f>`",
}


def _pair(
    parser: argparse.ArgumentParser,
    flag: str,
    *,
    dest: str,
    required: bool,
    multi: bool = False,
) -> None:
    """An inline flag and its `-file` twin: exactly one when required, at most one otherwise.

    Refuses a pair FILE_TWINS does not list: `resolve_file_args` reads only that table, so an
    unlisted twin would parse and then reach its handler as None.
    """
    if (dest, f"{dest}_file", flag, multi) not in FILE_TWINS:
        raise ValueError(
            f"{flag}: add ({dest!r}, {dest + '_file'!r}, {flag!r}, {multi}) to FILE_TWINS"
        )
    group = parser.add_mutually_exclusive_group(required=required)
    if multi:
        group.add_argument(flag, action="append", default=None, dest=dest)
    else:
        group.add_argument(flag, default=None, dest=dest)
    group.add_argument(f"{flag}-file", default=None, dest=f"{dest}_file", metavar="PATH")


def _read_text_file(parser: argparse.ArgumentParser, flag: str, raw: str) -> str:
    if raw == "-":
        stream = getattr(sys.stdin, "buffer", None)
        if stream is None:
            parser.error(f"argument {flag}-file: '-' needs piped stdin, and none is attached")
        if sys.stdin.isatty():
            parser.error(f"argument {flag}-file: '-' needs piped stdin, not a terminal")
        try:
            raw_bytes: bytes = stream.read()
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            parser.error(f"argument {flag}-file: stdin is not UTF-8 text")
    try:
        data = Path(raw).read_bytes().decode("utf-8")
    except OSError as exc:
        parser.error(f"argument {flag}-file: cannot read {raw}: {exc.strerror or exc}")
    except UnicodeDecodeError:
        parser.error(f"argument {flag}-file: {raw} is not UTF-8 text")
    return data


def resolve_file_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Replace every given `-file` twin with its value before any handler runs.

    Single values drop only trailing newlines; list values take one item per non-empty
    stripped line. An empty result is refused. Inline values are never touched. `-` reads
    stdin, which can feed only one value, so a second `-` is refused before anything is read.
    """
    from_stdin = [
        f"{flag}-file" for _d, fd, flag, _m in FILE_TWINS if getattr(args, fd, None) == "-"
    ]
    if len(from_stdin) > 1:
        parser.error(f"only one -file value may read stdin (got {', '.join(from_stdin)})")
    for dest, file_dest, flag, multi in FILE_TWINS:
        raw = getattr(args, file_dest, None)
        if raw is None:
            continue
        data = _read_text_file(parser, flag, raw)
        if multi:
            items = [line.strip() for line in data.splitlines() if line.strip()]
            if not items:
                parser.error(f"argument {flag}-file: {raw} holds no items (one per line)")
            setattr(args, dest, items)
        else:
            value = data.rstrip("\n")
            if not value:
                parser.error(f"argument {flag}-file: {raw} is empty")
            setattr(args, dest, value)


def _parser() -> argparse.ArgumentParser:
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
    ob.add_argument("--relation", required=True, choices=RELATIONS)
    _pair(ob, "--text", dest="text", required=True)
    ob.add_argument("--observed-at", default=None, dest="observed_at")
    _pair(ob, "--claim", dest="claim", required=False)
    ob.add_argument("--json", action="store_true")
    ad = asub.add_parser("add")
    ad.add_argument("id")
    _pair(ad, "--claim", dest="claim", required=True)
    ad.add_argument("--status", required=True, choices=QUESTION_STATUSES)
    _pair(ad, "--text", dest="text", required=False)
    ad.add_argument("--observed-at", default=None, dest="observed_at")
    ad.add_argument("--json", action="store_true")
    rs = asub.add_parser("resolve")
    rs.add_argument("id")
    rs.add_argument("--status", required=True, choices=QUESTION_STATUSES)
    _pair(rs, "--claim", dest="claim", required=True)
    rs.add_argument("--json", action="store_true")

    o = sub.add_parser("metric")
    osub = o.add_subparsers(dest="verb", required=True)
    rc = osub.add_parser("record")
    rc.add_argument("id")
    rc.add_argument("--value", required=True, type=float)
    rc.add_argument("--observed-at", default=None, dest="observed_at")
    _pair(rc, "--evidence", dest="evidence", required=True)
    rc.add_argument("--json", action="store_true")
    ms = osub.add_parser("measure")
    ms.add_argument("id", nargs="?", default=None)
    ms.add_argument("--all", action="store_true", dest="all_metrics")
    ms.add_argument("--dry-run", action="store_true", dest="dry_run")
    ms.add_argument("--json", action="store_true")

    # Literal `add_parser` names on purpose: the command-surface gate reads them by AST and
    # the registry must list every one, so a loop over a tuple would hide verbs from it.
    nw = sub.add_parser("new")
    nw.add_argument("id")
    _pair(nw, "--title", dest="title", required=True)
    _pair(nw, "--statement", dest="statement", required=True)
    nw.add_argument("--metric", required=True, dest="metric_id")
    _pair(nw, "--scope", dest="scope", required=False, multi=True)
    _pair(nw, "--out-of-scope", dest="out_of_scope", required=False, multi=True)
    nw.add_argument("--json", action="store_true")
    sh = sub.add_parser("show")
    sh.add_argument("id")
    sh.add_argument("--json", action="store_true")
    cl = sub.add_parser("close")
    cl.add_argument("id")
    cl.add_argument("--observed", required=True, choices=OBSERVED_VALUES)
    _pair(cl, "--note", dest="note", required=True)
    cl.add_argument("--json", action="store_true")
    removed = (
        sub.add_parser("approve", add_help=False),
        sub.add_parser("activate", add_help=False),
        sub.add_parser("drop", add_help=False),
        sub.add_parser("reopen", add_help=False),
    )
    for p in removed:
        p.add_argument("rest", nargs=argparse.REMAINDER)
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
