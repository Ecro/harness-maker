"""The one reader of `.ledger-exclusions.json`, shared by every ledger aggregate (ADR-007)."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Filename, unchanged from the single-ledger era so no file has to move.
EXCLUSIONS_FILE = ".ledger-exclusions.json"

#: The fields an entry may key on. `run_id` is what the legacy map meant; `slug` is what the
#: second-opinion ledger actually carries (`codex_ledger.SecondOpinionRecord` is
#: `extra="forbid"` and has no `run_id` at all, which is why the promotion was needed).
KEYS: frozenset[str] = frozenset({"run_id", "slug", "stage"})


@dataclass(frozen=True)
class Exclusion:
    """One predicate: rows whose ``key`` field equals ``value`` do not enter any aggregate."""

    key: str
    value: str
    reason: str


def _warn(message: str) -> None:
    sys.stderr.write(f"[ledger] {message}\n")


def load(observability_dir: Path) -> list[Exclusion]:
    """Read both the promoted list form and the legacy map. Absent file → nothing excluded.

    **The legacy map is READ, never rewritten.** Nothing on disk changes, so reverting this
    change leaves the previous reader looking at the file it has always understood. A
    migration that rewrote in place would hand a rolled-back reader a JSON list, whose
    ``"x" in [...]`` membership test silently matches nothing — the precise "excluding
    nothing looks identical to having nothing to exclude" failure this file exists to stop.

    **Malformed input fails OPEN, loudly.** ADR-007's draft said "fail loudly, not fail
    open"; the behaviour it was written against already reasoned the other way and said so
    in its own test — *a torn exclusions file must not silently empty the report*. Failing
    closed would exclude everything and empty the aggregate, a worse and quieter outcome than
    reporting unfiltered rows beside a stderr line. What the ADR forbids is silence, and the
    shout supplies it.
    """
    path = observability_dir / EXCLUSIONS_FILE
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _warn(f"{path} unreadable ({exc}) — NO rows excluded")
        return []

    if isinstance(payload, dict):
        # A dict is the LEGACY map — unless it looks like one new-schema entry that forgot its
        # surrounding list. That is the likeliest authoring mistake for the promoted vocabulary,
        # and reading it as a legacy map turns `{"key": "slug", "value": "s"}` into three
        # run_id exclusions matching nothing: a file that looks configured and is inert, which
        # is the exact condition this mechanism exists to end.
        if "key" in payload:
            _warn(
                f"{path} looks like ONE predicate entry rather than the legacy run-id map. "
                f"Wrap it in a list: [{{...}}] — NO rows excluded"
            )
            return []
        return [Exclusion(key="run_id", value=str(k), reason=str(v)) for k, v in payload.items()]

    if not isinstance(payload, list):
        _warn(f"{path} is neither a list nor an object — NO rows excluded")
        return []

    entries: list[Exclusion] = []
    for raw in payload:
        if not isinstance(raw, dict):
            _warn(f"{path}: entry {raw!r} is not an object — skipped")
            continue
        key = str(raw.get("key", ""))
        if key not in KEYS:
            # Loud, and the rest survive. A typo that silently excluded nothing would leave
            # the file looking configured while doing nothing.
            _warn(f"{path}: unknown key {key!r} (expected one of {sorted(KEYS)}) — entry skipped")
            continue
        # `value` gets the same loudness as `key`. Absent coerces to `""` and an explicit null
        # to the literal `"None"`; both are predicates that match almost nothing, produced
        # without a diagnostic, while the neighbouring branch shouts. That asymmetry was the
        # defect — not the coercion itself.
        raw_value = raw.get("value")
        if not isinstance(raw_value, str | int) or str(raw_value) == "":
            _warn(f"{path}: entry for key {key!r} has no usable 'value' — entry skipped")
            continue
        raw_reason = raw.get("reason")
        if not raw_reason:
            # Not fatal: an unexplained exclusion still excludes. But ADR-007 requires every
            # entry to carry an auditable reason, so its absence must not be silent.
            _warn(f"{path}: entry {key}={raw_value!r} has no 'reason' — kept, but unauditable")
        entries.append(Exclusion(key=key, value=str(raw_value), reason=str(raw_reason or "")))
    return entries


def is_excluded(row: Mapping[str, Any], exclusions: Sequence[Exclusion]) -> bool:
    """Does any entry match this row, on the field its own ``key`` names?

    The ``key`` is the whole point of the schema. A matcher that compared the value against
    every field would drop a legitimate row whose ``stage`` happened to equal an excluded
    slug — silent under-counting in the aggregate this mechanism exists to make honest.

    An **absent** field is not a match. ``str(row.get("run_id"))`` yields the literal
    ``"None"``, so a value of ``"None"`` would otherwise sweep up every row lacking the field.
    """
    for entry in exclusions:
        if entry.key not in row:
            continue
        value = row[entry.key]
        if value is None:
            continue
        if str(value) == entry.value:
            return True
    return False
