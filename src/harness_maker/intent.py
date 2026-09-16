"""`.claude/intent.yaml` — why the project exists: loader, validator, write-if-absent skeleton."""

from __future__ import annotations

import re
from dataclasses import dataclass
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
LIST_FIELDS: frozenset[str] = frozenset(
    {"outcomes", "non_negotiables", "non_scope", "unknowns", "owners"}
)
STRING_FIELDS: frozenset[str] = frozenset({"mission", "vision"})
OUTCOME_FIELDS: tuple[str, ...] = (
    "id",
    "description",
    "target",
    "higher_is_better",
    "how_measured",
)
_ID_RE = re.compile(r"^[a-z0-9_]+$")

SKELETON = """\
# .claude/intent.yaml — why this project exists. Human-written; nothing here is generated.
#
# Fill `mission` first. Until `mission` and `outcomes` are both filled, `hm world status`
# reports `not_filled_in`. A file with outcomes but no mission is a validation error.
#
# Withdrawal criterion (SPEC): if after 10 wrapups no objective carries `observed:` and no
# `revisit_when` has evaluated `candidate`, this layer is unused and is removed.
schema_version: 1
mission: ""
vision: ""
# outcomes:
#   - id: dead_rendered_bytes          # [a-z0-9_]+, unique
#     description: share of rendered command bytes with zero recorded invocations
#     target: 10                       # a number; compared to the last recorded value
#     higher_is_better: false
#     how_measured: "hm economics stages + metrics invocation counts"
outcomes: []
non_negotiables: []
non_scope: []
unknowns: []
owners: []
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
class Outcome:
    id: str
    description: str
    target: int | float
    higher_is_better: bool
    how_measured: str


@dataclass(frozen=True)
class Intent:
    schema_version: int
    mission: str
    vision: str
    outcomes: tuple[Outcome, ...]
    non_negotiables: tuple[str, ...]
    non_scope: tuple[str, ...]
    unknowns: tuple[str, ...]
    owners: tuple[str, ...]


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
    major = found if isinstance(found, int) and not isinstance(found, bool) else None
    if major is None and isinstance(found, str):
        head = found.split(".", 1)[0]
        major = int(head) if head.isdigit() else None
    if major != KNOWN_MAJOR:
        return IntentError(
            field,
            f"{path}: schema_version {found!r} is not readable by this build (known major "
            f"{KNOWN_MAJOR}); refusing rather than guessing",
        )
    return None


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate_outcome(i: int, raw: Any, seen: set[str], errors: list[IntentError]) -> None:
    prefix = f"outcomes[{i}]"
    if not isinstance(raw, dict):
        errors.append(IntentError(prefix, "must be a mapping"))
        return
    for key in OUTCOME_FIELDS:
        if key not in raw:
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


def _validate_raw(path: Path, raw: Any) -> list[IntentError]:
    errors: list[IntentError] = []
    if not isinstance(raw, dict):
        return [IntentError("file", f"{path}: top level must be a mapping")]
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
    errors = [err] if err is not None else _validate_raw(path, raw)
    if errors:
        raise IntentInvalidError(path, errors)
    assert isinstance(raw, dict)
    return Intent(
        schema_version=int(raw["schema_version"]),
        mission=raw["mission"],
        vision=raw.get("vision") or "",
        outcomes=tuple(
            Outcome(
                id=o["id"],
                description=o["description"],
                target=o["target"],
                higher_is_better=o["higher_is_better"],
                how_measured=o["how_measured"],
            )
            for o in raw["outcomes"]
        ),
        non_negotiables=_strs(raw, "non_negotiables"),
        non_scope=_strs(raw, "non_scope"),
        unknowns=_strs(raw, "unknowns"),
        owners=_strs(raw, "owners"),
    )


def is_not_filled_in(intent: Intent) -> bool:
    """The skeleton state: mission empty AND no outcomes — the one state where that is legal."""
    return not intent.mission.strip() and not intent.outcomes
