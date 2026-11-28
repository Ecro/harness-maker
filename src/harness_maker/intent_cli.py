"""`hm intent` runtime: goal records, metric values and measurement, open questions, status."""

from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from harness_maker import intent
from harness_maker.frontmatter import split_frontmatter
from harness_maker.intent import (
    MIGRATE_HINT,
    OBSERVED_VALUES,
    QUESTION_STATUSES,
    RELATIONS,
    Intent,
    IntentError,
    IntentInvalidError,
    Outcome,
)
from harness_maker.io_utils import atomic_write
from harness_maker.second_opinion_invoke import resolve_base_root
from harness_maker.second_opinion_oracle import BUDGET_PER_COMMAND, redact, truncate

#: States a record may carry on disk. `open|closed` are written; the rest are read (IRR-002).
RECORD_STATES: tuple[str, ...] = ("open", "closed", "proposed", "active", "dropped")
_OPEN_STATES = frozenset({"open", "proposed", "active"})
_RECORD_REQUIRED: tuple[str, ...] = (
    "id",
    "title",
    "statement",
    "scope",
    "metric_id",
    "state",
    "created_at",
    "schema_version",
)
#: Legacy keys (`rejected` … `revisit_when`) are accepted and kept, never written on new records.
_RECORD_OPTIONAL: tuple[str, ...] = (
    "out_of_scope",
    "observed",
    "note",
    "closed_at",
    "rejected",
    "depends_on",
    "approval",
    "revisit_when",
)
_RECORD_KEYS = frozenset(_RECORD_REQUIRED) | frozenset(_RECORD_OPTIONAL)
_RECORD_ID_RE = re.compile(r"^[A-Z0-9-]+$")
_QUESTION_ID_RE = re.compile(r"^[a-z0-9_]+$")
_ROW_KEYS: tuple[str, ...] = ("value", "observed_at", "evidence", "definition_hash", "metric_id")
_LOCK_TIMEOUT_S = 30.0
#: Resolve moves (ADR-005): a confirmed claim changes only through `observe` first.
_RESOLVABLE = {"open": {"confirmed", "wrong"}, "wrong": {"confirmed", "open"}}

RECORD_BODY = """\
## Problem



## Proposed outcome



## Constraints

"""


class IntentWriteError(ValueError):
    """A refused write or an unloadable record; `field` names what was wrong."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


# ── paths, layout, locks, timestamps ─────────────────────────────────────────


def intent_path(root: Path) -> Path:
    return root / ".claude" / "intent.yaml"


def metrics_path(root: Path) -> Path:
    return root / ".claude" / "intent" / "metrics.yaml"


def record_path(root: Path, record_id: str) -> Path:
    return root / "intent" / f"{record_id}.md"


def checkout_root(cwd: Path) -> Path:
    """The CURRENT checkout's root (the task worktree when run there), else `cwd` with a note."""
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
        print(f"[intent] git unavailable ({exc.__class__.__name__}); using {cwd}", file=sys.stderr)
        return Path(cwd)
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"[intent] {cwd} is not inside a git checkout; using it as the root", file=sys.stderr)
        return Path(cwd)
    return Path(proc.stdout.strip())


def legacy_layout(root: Path) -> str | None:
    """The first pre-0.58 file found, or None. Only `migrate` reads those files."""
    try:
        raw = yaml.safe_load(intent_path(root).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        raw = None
    if isinstance(raw, dict) and (set(raw) & intent.LEGACY_FIELDS or "purpose" not in raw):
        return ".claude/intent.yaml"
    for rel in (".claude/world/assumptions.yaml", ".claude/world/outcomes.yaml"):
        if (root / rel).exists():
            return rel
    legacy = sorted((root / "work-docs").glob("INTENT-*.md"))
    return legacy[0].relative_to(root).as_posix() if legacy else None


@contextmanager
def write_lock(root: Path) -> Iterator[None]:
    """One writer per checkout: flock on the checkout directory, which creates no file."""
    try:
        import fcntl
    except ImportError:  # pragma: no cover - non-POSIX keeps the unlocked fallback
        yield
        return
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    deadline = time.monotonic() + _LOCK_TIMEOUT_S
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    raise IntentWriteError(
                        "lock", "intent storage is locked by another writer"
                    ) from exc
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


@contextmanager
def _writing(root: Path) -> Iterator[None]:
    with write_lock(root):
        legacy = legacy_layout(root)
        if legacy is not None:
            raise IntentWriteError("layout", f"{legacy}: {MIGRATE_HINT}")
        yield


def normalise_timestamp(raw: Any, field_name: str) -> str:
    """Timezone-aware ISO-8601 in → UTC `Z` form out; naive or unparseable is refused by name."""
    if not isinstance(raw, str) or not raw.strip():
        raise IntentWriteError(field_name, "missing or not a string")
    text = raw.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00") if text.endswith("Z") else text)
    except ValueError as exc:
        raise IntentWriteError(field_name, f"not ISO-8601: {text!r} ({exc})") from exc
    if parsed.tzinfo is None:
        raise IntentWriteError(field_name, f"naive timestamp {text!r}: a timezone is required")
    utc = parsed.astimezone(UTC)
    if utc.microsecond:
        return utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _json_number(value: Any) -> int | float:
    """A CLI float that is integral is stored as its int (`--value 17` → 17, not 17.0)."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value  # type: ignore[no-any-return]


def _dump_yaml(path: Path, doc: dict[str, Any]) -> None:
    atomic_write(path, yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


# ── metric definitions and values ────────────────────────────────────────────


def definition_hash(outcome: Outcome) -> str:
    """Binds a row to the definition it was measured under; a changed target stales history."""
    payload: dict[str, Any] = {
        "higher_is_better": outcome.higher_is_better,
        "how_measured": outcome.how_measured,
        "target": outcome.target,
    }
    if outcome.measure is not None:
        m = outcome.measure
        payload["measure"] = {
            "cmd": m.cmd,
            "cwd": m.cwd,
            "select": m.select,
            "timeout_s": m.timeout_s,
        }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def metrics_errors(
    path: Path, doc: Any, metric_ids: set[str]
) -> tuple[list[IntentError], set[int]]:
    """Envelope errors, and the indexes of rows a reader must skip."""
    if not isinstance(doc, dict):
        return [IntentError("file", f"{path}: top level must be a mapping")], set()
    errors: list[IntentError] = []
    sv = intent.schema_version_error(path, doc)
    if sv is not None:
        errors.append(sv)
    for key in doc:
        if key not in ("schema_version", "values"):
            errors.append(IntentError(str(key), "unknown envelope key"))
    values = doc.get("values")
    if not isinstance(values, list):
        return [*errors, IntentError("values", "must be a list")], set()
    bad: set[int] = set()
    for i, row in enumerate(values):
        prefix = f"values[{i}]"
        if not isinstance(row, dict):
            errors.append(IntentError(prefix, "must be a mapping"))
            bad.add(i)
            continue
        for key in _ROW_KEYS:
            if key not in row:
                errors.append(IntentError(f"{prefix}.{key}", "missing"))
                bad.add(i)
        if "metric_id" in row and row["metric_id"] not in metric_ids:
            errors.append(IntentError(f"{prefix}.metric_id", f"{row['metric_id']!r} is no metric"))
            bad.add(i)
        if "value" in row and not _is_number(row["value"]):
            errors.append(IntentError(f"{prefix}.value", "must be a number"))
            bad.add(i)
    return errors, bad


@dataclass(frozen=True)
class LastValue:
    value: int | float
    observed_at: str
    stale_definition: bool


def last_value(outcome: Outcome, values: list[dict[str, Any]]) -> LastValue | None:
    """Greatest normalised instant wins; ties → the later row."""
    best: dict[str, Any] | None = None
    best_ts: datetime | None = None
    for row in values:
        if row.get("metric_id") != outcome.id or not isinstance(row.get("observed_at"), str):
            continue
        try:
            ts = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            continue
        if best_ts is None or ts >= best_ts:
            best, best_ts = row, ts
    if best is None:
        return None
    return LastValue(
        value=best["value"],
        observed_at=best["observed_at"],
        stale_definition=best.get("definition_hash") != definition_hash(outcome),
    )


def gap(outcome: Outcome, lv: LastValue | None) -> str:
    if lv is None or lv.stale_definition:
        return "unevaluable"
    if outcome.higher_is_better:
        return "at_or_better" if lv.value >= outcome.target else "below_target"
    return "at_or_better" if lv.value <= outcome.target else "above_target"


def _find_metric(loaded: Intent, metric_id: str) -> Outcome:
    found = next((m for m in loaded.metrics if m.id == metric_id), None)
    if found is None:
        raise IntentWriteError("metric_id", f"{metric_id!r} is not a metric in intent.yaml")
    return found


def _append_value(
    root: Path, loaded: Intent, metric: Outcome, *, value: Any, observed_at: Any, evidence: Any
) -> dict[str, Any]:
    """The definition hashed is the one the caller loaded (and, for measure, actually ran)."""
    if not _is_number(value):
        raise IntentWriteError("value", "must be a number")
    stamp = normalise_timestamp(observed_at, "observed_at")
    if not isinstance(evidence, str) or not evidence.strip():
        raise IntentWriteError("evidence", "must be a non-empty string")
    row = {
        "value": value,
        "observed_at": stamp,
        "evidence": evidence,
        "definition_hash": definition_hash(metric),
        "metric_id": metric.id,
    }
    path = metrics_path(root)
    with _writing(root):
        if path.exists():
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            errors, _ = metrics_errors(path, doc, {m.id for m in loaded.metrics})
            if errors:
                raise IntentWriteError(errors[0].field, errors[0].message)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            doc = {"schema_version": intent.KNOWN_MAJOR, "values": []}
        doc["values"].append(row)
        _dump_yaml(path, doc)
    return row


def record_value(
    root: Path, metric_id: str, *, value: Any, observed_at: Any, evidence: Any
) -> dict[str, Any]:
    loaded = intent.load_intent(intent_path(root))
    return _append_value(
        root,
        loaded,
        _find_metric(loaded, metric_id),
        value=value,
        observed_at=observed_at,
        evidence=evidence,
    )


# ── metric measure: the harness records the number, the human never types it ─

_NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _shape(value: Any) -> str:
    """What a refused selection WAS, without what it SAID: stdout never reaches a message."""
    return f"{type(value).__name__} of length {len(str(value))}"


def _finite_number(value: Any) -> int | float:
    """A bool is no number and a NaN row would make every gap comparison False forever."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IntentWriteError("select", f"not a number: {_shape(value)}")
    if isinstance(value, float) and not math.isfinite(value):
        raise IntentWriteError("select", "not a finite number")
    if isinstance(value, int):
        try:
            float(value)
        except OverflowError as exc:
            raise IntentWriteError("select", "integer too large to compare with a target") from exc
    return _json_number(value)


def select_number(text: str, select: str) -> int | float:
    """Exactly one number out of stdout, by the selector the metric declared."""
    if select == intent.SELECT_LAST_NUMBER:
        found = _NUMBER_RE.findall(text)
        if not found:
            raise IntentWriteError("select", "no number in stdout")
        return _finite_number(float(found[-1]))
    if select.startswith("json:"):
        try:
            node: Any = json.loads(text)
        except ValueError as exc:
            raise IntentWriteError("select", f"stdout is not JSON: {exc}") from exc
        for part in select[len("json:") :].split("."):
            if isinstance(node, list) and part.lstrip("-").isdigit():
                idx = int(part)
                if not -len(node) <= idx < len(node):
                    raise IntentWriteError("select", f"index {part} out of range")
                node = node[idx]
            elif isinstance(node, dict) and part in node:
                node = node[part]
            else:
                raise IntentWriteError("select", f"path segment {part!r} not found")
        return _finite_number(node)
    if select.startswith("regex:"):
        m = re.search(select[len("regex:") :], text)
        if m is None:
            raise IntentWriteError("select", "regex did not match stdout")
        captured = m.group(1)
        if captured is None:
            raise IntentWriteError("select", "the regex group did not participate in the match")
        try:
            return _finite_number(float(captured))
        except ValueError as exc:
            raise IntentWriteError("select", f"group is not a number: {_shape(captured)}") from exc
    raise IntentWriteError("select", f"unknown selector {select!r}")


def _short_sha(cwd: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "nogit"
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "nogit"


def run_measure(metric: Outcome, root: Path) -> tuple[int | float, str]:
    """Run `measure` as argv (never a shell) within its timeout; stdout is only selected from,
    stderr reaches the message redacted and truncated. `cwd: base` runs at the base root."""
    measure = metric.measure
    if measure is None:
        raise IntentWriteError("measure", f"metric {metric.id!r} has no measure block (manual)")
    argv = shlex.split(measure.cmd)
    cwd = resolve_base_root(root) if measure.cwd == "base" else root
    try:
        # Own session so a timeout kills the whole process group, not just the direct child.
        with subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        ) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=measure.timeout_s)
            except subprocess.TimeoutExpired as exc:
                with suppress(OSError):
                    os.killpg(proc.pid, signal.SIGKILL)
                with suppress(OSError):
                    proc.kill()
                proc.wait()
                raise IntentWriteError(
                    "timeout", f"{argv[0]} exceeded {measure.timeout_s}s"
                ) from exc
    except OSError as exc:
        raise IntentWriteError("exit", f"{argv[0]} did not run: {exc}") from exc
    if proc.returncode != 0:
        diag = truncate(redact(stderr or ""), BUDGET_PER_COMMAND)
        raise IntentWriteError("exit", f"exit={proc.returncode}: {diag}".rstrip(": "))
    value = select_number(stdout or "", measure.select)
    ref = definition_hash(metric)[:12]
    return value, f"auto: measure#{ref} @ {_short_sha(cwd)} exit=0 cwd={measure.cwd}"


def measure_metric(root: Path, metric_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    loaded = intent.load_intent(intent_path(root))
    metric = _find_metric(loaded, metric_id)
    value, evidence = run_measure(metric, root)
    if dry_run:
        return {"metric": metric_id, "status": "would_record", "value": value, "evidence": evidence}
    row = _append_value(
        root, loaded, metric, value=value, observed_at=_now_iso(), evidence=evidence
    )
    return {"metric": metric_id, "status": "recorded", "value": row["value"], "row": row}


def measure_all(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Every metric in order; a failure is reported and never aborts the rest."""
    loaded = intent.load_intent(intent_path(root))
    results: list[dict[str, Any]] = []
    for metric in loaded.metrics:
        if metric.measure is None:
            results.append({"metric": metric.id, "status": "manual"})
            continue
        try:
            results.append(measure_metric(root, metric.id, dry_run=dry_run))
        except IntentWriteError as exc:
            failed = {"status": "failed", "cause": exc.field, "message": exc.message}
            results.append({"metric": metric.id, **failed})
    return {"results": results, "failed": sum(1 for r in results if r["status"] == "failed")}


# ── open questions (in `.claude/intent.yaml`) ────────────────────────────────


@contextmanager
def _questions(root: Path) -> Iterator[list[dict[str, Any]]]:
    """Read-modify-write of `open_questions`; the whole file is validated before it is written."""
    path = intent_path(root)
    with _writing(root):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        intent.intent_from_raw(path, raw)
        questions: list[dict[str, Any]] = raw.setdefault("open_questions", [])
        yield questions
        intent.intent_from_raw(path, raw)
        _dump_yaml(path, raw)


def _find_question(questions: list[dict[str, Any]], qid: str) -> dict[str, Any]:
    for q in questions:
        if q.get("id") == qid:
            return q
    raise IntentWriteError("id", f"no question {qid!r}")


def _non_empty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntentWriteError(name, "must be a non-empty string")
    return value


def add_question(
    root: Path,
    qid: str,
    *,
    claim: str,
    status: str,
    text: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    if not _QUESTION_ID_RE.fullmatch(qid):
        raise IntentWriteError("id", "must match [a-z0-9_]+")
    _non_empty(claim, "claim")
    if status not in QUESTION_STATUSES:
        raise IntentWriteError("status", f"must be one of {QUESTION_STATUSES}")
    evidence: list[dict[str, Any]] = []
    if text is not None:
        _non_empty(text, "text")
        stamp = normalise_timestamp(observed_at, "observed_at")
        evidence.append({"text": text, "observed_at": stamp, "relation": "confirms"})
    elif observed_at is not None:
        raise IntentWriteError("text", "--observed-at needs --text")
    rec: dict[str, Any] = {
        "id": qid,
        "claim": claim,
        "status": status,
        "evidence": evidence,
        "history": [],
    }
    with _questions(root) as questions:
        if any(q.get("id") == qid for q in questions):
            raise IntentWriteError("id", f"question {qid!r} already exists; use observe")
        questions.append(rec)
    return rec


def observe_question(
    root: Path,
    qid: str,
    *,
    relation: str,
    text: str,
    observed_at: str,
    claim: str | None = None,
) -> dict[str, Any]:
    """`contradicts` marks the claim wrong; `supersedes` replaces it and keeps the old one."""
    if relation not in RELATIONS:
        raise IntentWriteError("relation", f"must be one of {RELATIONS}")
    _non_empty(text, "text")
    stamp = normalise_timestamp(observed_at, "observed_at")
    if relation == "supersedes":
        _non_empty(claim, "claim")
    with _questions(root) as questions:
        rec = _find_question(questions, qid)
        rec.setdefault("evidence", []).append(
            {"text": text, "observed_at": stamp, "relation": relation}
        )
        if relation == "contradicts":
            rec["status"] = "wrong"
        elif relation == "supersedes":
            rec.setdefault("history", []).append(rec["claim"])
            rec["claim"] = claim
    return rec


def resolve_question(root: Path, qid: str, *, status: str, claim: str) -> dict[str, Any]:
    _non_empty(claim, "claim")
    with _questions(root) as questions:
        rec = _find_question(questions, qid)
        if status not in _RESOLVABLE.get(str(rec.get("status")), set()):
            raise IntentWriteError(
                "status",
                f"{qid!r} is {rec.get('status')!r}; resolve settles an open question "
                "(to confirmed|wrong) or leaves wrong (to confirmed|open) — "
                "record an observation first with observe --relation",
            )
        rec.setdefault("history", []).append(rec["claim"])
        rec["claim"] = claim
        rec["status"] = status
    return rec


# ── goal records (`intent/<ID>.md`) ──────────────────────────────────────────


def record_errors(path: Path, raw: Any, metric_ids: set[str]) -> list[IntentError]:
    if not isinstance(raw, dict):
        return [IntentError("file", f"{path}: frontmatter must be a mapping")]
    errors: list[IntentError] = []
    sv = intent.schema_version_error(path, raw)
    if sv is not None:
        errors.append(sv)
    errors.extend(IntentError(str(k), "unknown key") for k in raw if k not in _RECORD_KEYS)
    errors.extend(IntentError(k, "missing required key") for k in _RECORD_REQUIRED if k not in raw)
    rid = raw.get("id")
    if "id" in raw and (not isinstance(rid, str) or not _RECORD_ID_RE.match(rid)):
        errors.append(IntentError("id", "must match [A-Z0-9-]+"))
    elif "id" in raw and rid != path.stem:
        errors.append(IntentError("id", f"{rid!r} does not equal the file name ({path.name})"))
    for key in ("title", "statement", "created_at"):
        if key in raw and (not isinstance(raw[key], str) or not raw[key].strip()):
            errors.append(IntentError(key, "must be a non-empty string"))
    for key in ("scope", "out_of_scope", "rejected"):
        val = raw.get(key)
        if val is not None and (
            not isinstance(val, list) or not all(isinstance(s, str) for s in val)
        ):
            errors.append(IntentError(key, "must be a list of strings"))
    if "metric_id" in raw and raw["metric_id"] not in metric_ids:
        errors.append(IntentError("metric_id", f"{raw['metric_id']!r} is not a metric"))
    state = raw.get("state")
    if "state" in raw and state not in RECORD_STATES:
        errors.append(IntentError("state", f"must be one of {RECORD_STATES}"))
    if state == "closed":
        if raw.get("observed") not in OBSERVED_VALUES:
            errors.append(IntentError("observed", f"a closed goal needs one of {OBSERVED_VALUES}"))
        if not isinstance(raw.get("note"), str) or not raw["note"].strip():
            errors.append(IntentError("note", "a closed goal needs a non-empty note"))
        if not isinstance(raw.get("closed_at"), str):
            errors.append(IntentError("closed_at", "a closed goal needs closed_at"))
    elif raw.get("observed") is not None:
        errors.append(IntentError("observed", "only a closed goal carries observed"))
    return errors


def read_record(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise IntentWriteError("file", f"{path}: {exc}") from exc
    split = split_frontmatter(data)
    if split.status != "ok" or split.mapping is None:
        raise IntentWriteError("file", f"{path}: {split.error}")
    return dict(split.mapping), split.body


def state_of(rec: dict[str, Any]) -> str:
    return "open" if rec.get("state") in _OPEN_STATES else "closed"


def observed_of(rec: dict[str, Any]) -> str | None:
    observed = rec.get("observed")
    if observed is None and rec.get("state") == "dropped":
        return "no_data"
    return observed if isinstance(observed, str) else None


@dataclass
class Snapshot:
    """One read of everything, so a status line never mixes two disk states."""

    intent: Intent
    values: list[dict[str, Any]] = field(default_factory=list)
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    bodies: dict[str, bytes] = field(default_factory=dict)
    broken: dict[str, str] = field(default_factory=dict)


def load(root: Path) -> Snapshot:
    """Raises `IntentInvalidError` for an invalid or unmigrated `intent.yaml`; a broken record
    or metrics row is reported, never raised."""
    path = intent_path(root)
    legacy = legacy_layout(root)
    if legacy is not None:
        raise IntentInvalidError(path, [IntentError("layout", f"{legacy}: {MIGRATE_HINT}")])
    snap = Snapshot(intent=intent.load_intent(path))
    metric_ids = {m.id for m in snap.intent.metrics}
    mpath = metrics_path(root)
    if mpath.exists():
        try:
            doc = yaml.safe_load(mpath.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            doc = None
        _, bad = metrics_errors(mpath, doc, metric_ids)
        if isinstance(doc, dict) and isinstance(doc.get("values"), list):
            snap.values = [r for i, r in enumerate(doc["values"]) if i not in bad]
    for rpath in sorted((root / "intent").glob("*.md")):
        try:
            rec, body = read_record(rpath)
        except IntentWriteError as exc:
            snap.broken[rpath.stem] = exc.message
            continue
        errors = record_errors(rpath, rec, metric_ids)
        if errors:
            snap.broken[rpath.stem] = f"{errors[0].field}: {errors[0].message}"
            continue
        snap.records[rpath.stem] = rec
        snap.bodies[rpath.stem] = body
    return snap


def _dump_record(path: Path, rec: dict[str, Any], body: bytes) -> None:
    fm = yaml.safe_dump(rec, sort_keys=False, allow_unicode=True).encode("utf-8")
    atomic_write(path, b"---\n" + fm + b"---\n" + body)


def new_record(
    root: Path,
    record_id: str,
    *,
    title: str,
    statement: str,
    metric_id: str,
    scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> dict[str, Any]:
    if not _RECORD_ID_RE.match(record_id):
        raise IntentWriteError("id", f"{record_id!r} must match [A-Z0-9-]+")
    path = record_path(root, record_id)
    loaded = intent.load_intent(intent_path(root))
    rec: dict[str, Any] = {
        "id": record_id,
        "title": title,
        "statement": statement,
        "metric_id": metric_id,
        "scope": list(scope or []),
        "out_of_scope": list(out_of_scope or []),
        "state": "open",
        "created_at": _now_iso(),
        "schema_version": intent.KNOWN_MAJOR,
    }
    errors = record_errors(path, rec, {m.id for m in loaded.metrics})
    if errors:
        raise IntentWriteError(errors[0].field, errors[0].message)
    with _writing(root):
        if path.exists():
            raise IntentWriteError("id", f"{record_id!r} already exists at {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        _dump_record(path, rec, RECORD_BODY.encode("utf-8"))
    return rec


def close_record(root: Path, record_id: str, *, observed: str, note: str) -> dict[str, Any]:
    """The only rewrite of a goal record; every key it carries, legacy ones included, stays."""
    if observed not in OBSERVED_VALUES:
        raise IntentWriteError("observed", f"must be one of {OBSERVED_VALUES}")
    _non_empty(note, "note")
    with _writing(root):
        rec, body = _loaded_record(root, record_id)
        if state_of(rec) != "open":
            raise IntentWriteError("state", f"{record_id!r} is already closed")
        rec["state"] = "closed"
        rec["observed"] = observed
        rec["note"] = note
        rec["closed_at"] = _now_iso()
        _dump_record(record_path(root, record_id), rec, body)
    return rec


def _loaded_record(root: Path, record_id: str) -> tuple[dict[str, Any], bytes]:
    snap = load(root)
    if record_id in snap.broken:
        raise IntentWriteError("record", f"{record_id}: {snap.broken[record_id]}")
    if record_id not in snap.records:
        raise IntentWriteError("id", f"no goal {record_id!r} under intent/")
    return snap.records[record_id], snap.bodies[record_id]


def show_record(root: Path, record_id: str) -> dict[str, Any]:
    rec, _ = _loaded_record(root, record_id)
    return {**rec, "state": state_of(rec), "observed": observed_of(rec)}


# ── status ───────────────────────────────────────────────────────────────────


def _invalid_payload(exc: IntentInvalidError) -> dict[str, Any]:
    first = exc.errors[0]
    return {
        "state": "invalid",
        "error": {"field": first.field, "message": first.message},
        "errors": [{"field": e.field, "message": e.message} for e in exc.errors],
    }


def _reason(lv: LastValue | None) -> str:
    if lv is None:
        return "never_measured"
    return "stale_definition" if lv.stale_definition else "measured"


def status_report(root: Path) -> dict[str, Any]:
    """Read-only and LLM-free: goals, metrics with their gaps, and open questions."""
    try:
        snap = load(root)
    except IntentInvalidError as exc:
        return _invalid_payload(exc)
    metrics: dict[str, Any] = {}
    for m in snap.intent.metrics:
        lv = last_value(m, snap.values)
        metrics[m.id] = {
            "last": lv.value if lv else None,
            "target": m.target,
            "gap": gap(m, lv),
            "observed_at": lv.observed_at if lv else None,
            "reason": _reason(lv),
            "how_measured": m.how_measured,
            "higher_is_better": m.higher_is_better,
            "measure": m.measure is not None,
        }
    intents: dict[str, Any] = {
        rid: {
            "state": state_of(rec),
            "title": rec.get("title"),
            "metric_id": rec.get("metric_id"),
            "observed": observed_of(rec),
        }
        for rid, rec in sorted(snap.records.items())
    }
    for rid, message in sorted(snap.broken.items()):
        intents[rid] = {"state": "broken", "title": message, "metric_id": None, "observed": None}
    return {
        "state": "not_filled_in" if intent.is_not_filled_in(snap.intent) else "ok",
        "purpose": snap.intent.purpose,
        "metrics": metrics,
        "intents": intents,
        "open_questions": list(snap.intent.open_questions),
        "open": [rid for rid, v in intents.items() if v["state"] == "open"],
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def _emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip())


def _writes_observation(args: Any) -> bool:
    """`question add` without text records no evidence, so it is not stamped either."""
    verb = getattr(args, "verb", None)
    if args.cmd == "question":
        return verb == "observe" or (verb == "add" and getattr(args, "text", None) is not None)
    return args.cmd == "metric" and verb == "record"


def _dispatch(args: Any, root: Path) -> dict[str, Any]:
    cmd, verb = args.cmd, getattr(args, "verb", None)
    if cmd == "migrate":
        from harness_maker.intent_migrate import migrate

        return migrate(root)
    if cmd == "status":
        return status_report(root)
    if cmd == "show":
        return show_record(root, args.id)
    if cmd == "metric":
        if verb == "record":
            row = record_value(
                root,
                args.id,
                value=_json_number(args.value),
                observed_at=args.observed_at,
                evidence=args.evidence,
            )
            return {"value": row, "changed": ".claude/intent/metrics.yaml"}
        if bool(args.id) == bool(args.all_metrics):
            raise IntentWriteError("id", "give exactly one of <id> or --all")
        payload = (
            measure_all(root, dry_run=args.dry_run)
            if args.all_metrics
            else measure_metric(root, args.id, dry_run=args.dry_run)
        )
        payload["changed"] = None if args.dry_run else ".claude/intent/metrics.yaml"
        return payload
    if cmd == "question":
        if verb == "add":
            rec = add_question(
                root,
                args.id,
                claim=args.claim,
                status=args.status,
                text=args.text,
                observed_at=args.observed_at,
            )
        elif verb == "observe":
            rec = observe_question(
                root,
                args.id,
                relation=args.relation,
                text=args.text,
                observed_at=args.observed_at,
                claim=args.claim,
            )
        else:
            rec = resolve_question(root, args.id, status=args.status, claim=args.claim)
        return {"question": rec, "changed": ".claude/intent.yaml"}
    if cmd == "new":
        rec = new_record(
            root,
            args.id,
            title=args.title,
            statement=args.statement,
            metric_id=args.metric_id,
            scope=args.scope,
            out_of_scope=args.out_of_scope,
        )
    else:
        rec = close_record(root, args.id, observed=args.observed, note=args.note)
    return {"intent": rec, "changed": f"intent/{args.id}.md"}


def main(argv: list[str] | None = None) -> int:
    parser = intent._parser()
    # parse_known_args so a removed verb followed by any flag still names its replacement.
    args, extra = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    if args.cmd in intent.REMOVED_VERBS:
        print(
            f"hm intent {args.cmd} was removed: {intent.REMOVED_VERBS[args.cmd]}.",
            file=sys.stderr,
        )
        return 2
    if extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    intent.resolve_file_args(parser, args)
    if getattr(args, "observed_at", "") is None and _writes_observation(args):
        args.observed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    root = Path(args.root) if args.root else checkout_root(Path.cwd())
    as_json = bool(getattr(args, "json", False))
    try:
        payload = _dispatch(args, root)
    except IntentWriteError as exc:
        _emit({"error": {"field": exc.field, "message": exc.message}}, as_json=as_json)
        return 1
    except IntentInvalidError as exc:
        first = exc.errors[0]
        _emit({"error": {"field": first.field, "message": str(exc)}}, as_json=as_json)
        return 1
    except (ValueError, OSError) as exc:
        _emit({"error": {"field": type(exc).__name__, "message": str(exc)}}, as_json=as_json)
        return 1
    _emit(payload, as_json=as_json)
    return 1 if payload.get("failed") else 0
