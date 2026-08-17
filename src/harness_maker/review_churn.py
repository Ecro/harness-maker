"""Per-round fix churn: config resolution plus measurement over pinned endpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_maker import command_registry, freeze

DEFAULT_CHURN_RATIO = 0.30
"""Fraction of a touched file's LOC above which a repair round re-reviews.

Was 0.20, from the source experiment on a 156-line Python module in another
codebase. That value was always meant to be recalibrated from the ratios the
loop records — and on 2026-08-17 an audit of four repositories found the loop
records **none**: `churn_ratio` is a declared `ReviewTelemetryRecord` field that
only a prose instruction ever populated, and all 123 rows have it absent. So
0.30 is NOT the recalibration this docstring asked for; it is a second estimate,
raised because the yield data that *does* exist argues for fewer repair rounds —
of 22 multi-round slugs, 16 (73%) got zero consensus findings out of every round
after the first. Wiring the four `churn_*` keys to a producer that cannot skip
them is the prerequisite for ever setting this number from evidence.
"""


def default_churn_ratio() -> float:
    """Callable, not the bare float: Jinja globals are callables by contract here.

    The gate branch renders the threshold it promises, and `resolve_churn_threshold` applies
    the one it resolves. Both read this, so a template literal cannot drift from the CLI.
    """
    return DEFAULT_CHURN_RATIO


_RATIO_KEY = "rereview_churn_ratio"
_GATE_KEY = "rereview_churn_gate"


class ChurnConfigError(ValueError):
    """A present-but-malformed churn setting.

    Fail loudly rather than falling back to the default: a silent fallback makes
    a typo indistinguishable from a deliberate value, and the gate it feeds
    decides whether a review happens at all.
    """


def resolve_churn_threshold(reviewers: dict[str, Any]) -> float:
    """Absent key -> the documented default; present key -> validated.

    The absent case is the one that actually ships: harnesses rendered before
    this key existed have no `reviewers.rereview_churn_ratio`, and a feature that
    no-ops for them would never fire for the data that motivated it
    (CLAUDE.md learned correction 2026-06-08).
    """
    if _RATIO_KEY not in reviewers:
        return DEFAULT_CHURN_RATIO

    raw = reviewers[_RATIO_KEY]
    if isinstance(raw, bool):  # bool is an int subclass — reject before the numeric path
        raise ChurnConfigError(f"{_RATIO_KEY} must be a number in [0, 1], got a bool: {raw!r}")
    try:
        value = float(raw)
    except (TypeError, ValueError) as e:
        raise ChurnConfigError(f"{_RATIO_KEY} must be a number in [0, 1], got {raw!r}") from e

    if not (0.0 <= value <= 1.0):
        raise ChurnConfigError(f"{_RATIO_KEY} must be within [0, 1], got {value!r}")
    return value


def churn_gate_enabled(reviewers: dict[str, Any]) -> bool:
    """Absent key -> on.

    The gate defaults on so the ratios accrue; a harness that regresses turns it
    off in one line rather than pinning an old plugin version (ADR-004).
    """
    if _GATE_KEY not in reviewers:
        return True

    raw = reviewers[_GATE_KEY]
    if not isinstance(raw, bool):
        raise ChurnConfigError(f"{_GATE_KEY} must be a bool, got {raw!r}")
    return raw


# ── measurement (Phase 5 — record only; the gate is Phase 6) ────────────────

BINARY = "binary"
DELETED = "deleted"
CREATED = "created"
MODIFIED = "modified"
RENAMED = "renamed"

EXCLUDED_BINARY = "binary"
EXCLUDED_DELETED = "deleted"
EXCLUDED_EMPTY_POST = "empty-post-tree"


class ChurnMeasurementError(ValueError):
    """A file record the ratio has no reading over.

    Distinct from `ChurnConfigError`: that one is a user's typo, this one is the
    adapter handing the pure layer something it cannot have produced.
    """


@dataclass(frozen=True)
class FileChurn:
    """One touched file at the pinned endpoints.

    `post_loc` is the line count in the **post** tree, which is what makes
    "a small file rewritten whole" and "a small edit to a large file" separable;
    a pre-tree denominator would rank a whole-file deletion-and-rewrite by its
    old size instead.
    """

    path: str
    kind: str
    added: int | None
    deleted: int | None
    post_loc: int | None


@dataclass(frozen=True)
class ChurnMeasurement:
    """The aggregate plus the audit trail of what did not count toward it.

    `excluded` is carried, not dropped: a round whose whole diff was binary
    reports `ratio=None` with a reason, which a bare `0.0` would have made
    indistinguishable from a round that genuinely changed nothing.
    """

    ratio: float | None
    max_path: str | None
    measured: tuple[tuple[str, float], ...]
    excluded: tuple[tuple[str, str], ...]

    def as_record(self) -> dict[str, Any]:
        """The telemetry subset — exactly the four `ReviewTelemetryRecord` churn keys.

        Deliberately excludes the per-file detail: the telemetry row forbids extra
        keys and is capped at PIPE_BUF, so a caller splatting the detail into it
        would fail validation on a large diff and nowhere else.
        """
        return {
            "churn_ratio": self.ratio,
            "churn_max_path": self.max_path,
            "churn_measured_n": len(self.measured),
            "churn_excluded_n": len(self.excluded),
        }

    def as_detail(self) -> dict[str, Any]:
        """The full audit shape for the REVIEW iteration record."""
        return {
            **self.as_record(),
            "measured": [{"path": p, "ratio": r} for p, r in self.measured],
            "excluded": [{"path": p, "reason": r} for p, r in self.excluded],
        }


def file_ratio(entry: FileChurn) -> tuple[float | None, str | None]:
    """`(ratio, exclusion_reason)` — exactly one of the two is set.

    Returning the reason alongside the value is what keeps an exclusion
    *recorded* rather than silently folded into "no churn" (AC-013).
    """
    if entry.kind == BINARY:
        return None, EXCLUDED_BINARY
    if entry.kind == DELETED:
        return None, EXCLUDED_DELETED
    if entry.added is None or entry.deleted is None:
        raise ChurnMeasurementError(
            f"{entry.path}: kind={entry.kind!r} needs numeric added/deleted "
            f"(got {entry.added!r}/{entry.deleted!r}); only {BINARY!r} may omit them"
        )
    if entry.post_loc is None or entry.post_loc <= 0:
        return None, EXCLUDED_EMPTY_POST

    # Clamped at 1.0: a file whose every line was replaced has churned wholly, and
    # `(added + deleted) / post_loc` exceeds 1 for that case. Leaving it unclamped
    # would let one rewritten 30-line file outrank another purely by edit style.
    return min(1.0, (entry.added + entry.deleted) / entry.post_loc), None


def measure(files: list[FileChurn]) -> ChurnMeasurement:
    """Aggregate by **maximum**, not mean.

    S12's rule: averaging let a one-line edit to a 5000-line file mask a 30-line
    file rewritten whole, which is the case the gate exists to catch.
    """
    measured: list[tuple[str, float]] = []
    excluded: list[tuple[str, str]] = []
    for entry in files:
        ratio, reason = file_ratio(entry)
        if ratio is None:
            excluded.append((entry.path, reason or EXCLUDED_EMPTY_POST))
        else:
            measured.append((entry.path, ratio))

    if not measured:
        return ChurnMeasurement(None, None, (), tuple(excluded))

    # `max` keeps the first maximum, so pre-sorting by path breaks ties on path —
    # two runs over the same diff then name the same file.
    top = max(sorted(measured), key=lambda pair: pair[1])
    return ChurnMeasurement(top[1], top[0], tuple(measured), tuple(excluded))


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(  # noqa: S603 — fixed argv, shell=False
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout


def _parse_name_status(raw: str) -> dict[str, str]:
    """post-path -> kind, from `--name-status -z -M` records."""
    fields = [f for f in raw.split("\0") if f != ""]
    kinds: dict[str, str] = {}
    i = 0
    while i < len(fields):
        status = fields[i]
        if status[0] in {"R", "C"}:  # status, old-path, new-path
            if i + 2 >= len(fields):
                break
            kinds[fields[i + 2]] = RENAMED
            i += 3
            continue
        if i + 1 >= len(fields):
            break
        path = fields[i + 1]
        kinds[path] = {"A": CREATED, "D": DELETED}.get(status[0], MODIFIED)
        i += 2
    return kinds


def _parse_numstat(raw: str) -> list[tuple[str, int | None, int | None]]:
    """(post-path, added, deleted) — `None` counts mark git's binary `-`."""
    fields = [f for f in raw.split("\0") if f != ""]
    out: list[tuple[str, int | None, int | None]] = []
    i = 0
    while i < len(fields):
        head = fields[i]
        parts = head.split("\t")
        if len(parts) < 2:
            i += 1
            continue
        added = None if parts[0] == "-" else int(parts[0])
        deleted = None if parts[1] == "-" else int(parts[1])
        if len(parts) >= 3 and parts[2] != "":
            out.append((parts[2], added, deleted))
            i += 1
            continue
        # Rename: the trailing tab is empty and old/new paths follow as records.
        if i + 2 >= len(fields):
            break
        out.append((fields[i + 2], added, deleted))
        i += 3
    return out


def _post_loc(root: Path, post_ref: str, path: str) -> int | None:
    """Line count in the pinned post tree; `None` when the blob is absent."""
    try:
        blob = subprocess.run(  # noqa: S603 — fixed argv, shell=False
            ["git", "-C", str(root), "show", f"{post_ref}:{path}"],
            check=True,
            capture_output=True,
            timeout=60,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    if not blob:
        return 0
    return blob.count(b"\n") + (0 if blob.endswith(b"\n") else 1)


def collect(root: Path, pre_ref: str, post_ref: str) -> list[FileChurn]:
    """Read the two **pinned** endpoints — never the working tree.

    The endpoints are refs on purpose (S12): measuring the cumulative working
    diff would attribute an earlier round's edits to this one, so the ratio
    would grow monotonically and the gate would stop skipping anything.
    """
    kinds = _parse_name_status(_git(root, "diff", "--name-status", "-z", "-M", pre_ref, post_ref))
    entries: list[FileChurn] = []
    for path, added, deleted in _parse_numstat(
        _git(root, "diff", "--numstat", "-z", "-M", pre_ref, post_ref)
    ):
        kind = kinds.get(path, MODIFIED)
        if added is None or deleted is None:
            kind = BINARY
        post = None if kind == DELETED else _post_loc(root, post_ref, path)
        entries.append(FileChurn(path=path, kind=kind, added=added, deleted=deleted, post_loc=post))
    return entries


def measure_refs(root: Path, pre_ref: str, post_ref: str) -> ChurnMeasurement:
    return measure(collect(root, pre_ref, post_ref))


def pin_ref(slug: str, label: str) -> str:
    if not label or "/" in label or label.startswith("-"):
        raise ChurnMeasurementError(f"pin label must be a bare name, got {label!r}")
    return f"refs/hm-churn/v1/{slug}-{label}"


def pin(root: Path, slug: str, label: str) -> str:
    """Snapshot the working tree into a ref and return its commit.

    The fixes a round makes are uncommitted (wrapup owns commits), so `HEAD` is the
    wrong endpoint — it would measure zero churn no matter what the round changed.
    Parentless on purpose: these are measurement endpoints, not history.
    """
    ref = pin_ref(slug, label)
    tree = freeze.snapshot_working_tree(root)
    commit = _git(root, "commit-tree", tree, "-m", f"hm churn pin: {slug} {label}").strip()
    _git(root, "update-ref", ref, commit)
    return commit


# ── oscillation (Phase 7 — report only; it can never block a grade) ─────────

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@ ?(.*)$")


@dataclass(frozen=True)
class HunkRecord:
    """One changed hunk as of one round.

    Keyed on `(path, content_hash, symbol)` — the symbol is not decoration. Identical text
    in two functions is two hunks; without the symbol, a removal in one and an addition of
    the same line in the other reads as a restoration and raises a spec_gap against code
    that never oscillated.
    """

    round: int
    path: str
    content_hash: str
    symbol: str
    present: bool


@dataclass(frozen=True)
class Oscillation:
    """A hunk one round removed and a later round put back.

    `tag` is fixed at `manual-only` and is not a parameter. Two rounds disagreeing about the
    same code is a gap in the SPEC, not a defect in the diff; if it could join the voting set
    it would make grade A unreachable for a review whose only real problem is that nobody
    wrote down which behaviour was wanted.
    """

    path: str
    symbol: str
    content_hash: str
    rounds: tuple[int, ...]
    tag: str = "manual-only"
    category: str = "spec_gap"
    severity: str = "P1"

    def as_row(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "symbol": self.symbol,
            "content_hash": self.content_hash,
            "rounds": list(self.rounds),
            "tag": self.tag,
            "category": self.category,
            "severity": self.severity,
        }


def normalize_hunk_body(lines: list[str]) -> str:
    """Changed lines only, sign- and indentation-blind.

    Sign-blind because a removal and its later restoration must hash the SAME — that identity
    is what makes the pair detectable. Indentation-blind because a restoration that lands at a
    different nesting level is still the same decision being reversed, and hashing raw text
    would let a re-indent hide it.
    """
    parts = [ln[1:].strip() for ln in lines if ln[:1] in {"+", "-"}]
    return "\n".join(p for p in parts if p)


def parse_hunks(diff_text: str, round_no: int) -> list[HunkRecord]:
    """Read hunks from a unified diff, taking the enclosing symbol from git's own header.

    Git already prints the enclosing function on the `@@` line, so no language parser is
    needed and none is added — a wrong symbol from a hand-rolled parser would silently
    re-key hunks and lose the very pairs this looks for.
    """
    records: list[HunkRecord] = []
    path = ""
    symbol = ""
    body: list[str] = []
    started = False

    def flush() -> None:
        if not started:
            return
        content = normalize_hunk_body(body)
        if not content:
            return
        added = sum(1 for ln in body if ln.startswith("+"))
        removed = sum(1 for ln in body if ln.startswith("-"))
        records.append(
            HunkRecord(
                round=round_no,
                path=path,
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
                symbol=symbol,
                present=added >= removed,
            )
        )

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            flush()
            started = False
            body = []
            path = line[4:].strip()
            path = path[2:] if path.startswith(("a/", "b/")) else path
            continue
        header = _HUNK_HEADER.match(line)
        if header:
            flush()
            started = True
            body = []
            symbol = header.group(1).strip()
            continue
        if started and line[:1] in {"+", "-", " "} and not line.startswith(("+++", "---")):
            body.append(line)
    flush()
    return records


def detect_oscillation(records: list[HunkRecord]) -> list[Oscillation]:
    """A hunk one round REMOVED that a later round put back — a removal followed by a return.

    Only the removal→return pair, in that order. Three near-misses this deliberately excludes:
    "touched in two rounds" matches every ordinary repair round, so the report would be noise
    from its first run; a removal left removed is a fix; and an addition that is only ever
    added is ordinary forward work. A leading presence is NOT required — the common real shape
    is a guard removed in round 2 and restored in round 3, which never appears before its own
    removal.
    """
    grouped: dict[tuple[str, str, str], list[HunkRecord]] = {}
    for rec in records:
        grouped.setdefault((rec.path, rec.content_hash, rec.symbol), []).append(rec)

    found: list[Oscillation] = []
    for (path, content_hash, symbol), group in grouped.items():
        ordered = sorted(group, key=lambda r: r.round)
        seen_removal = False
        oscillates = False
        for rec in ordered:
            if not rec.present:
                seen_removal = True
            elif seen_removal:
                oscillates = True
                break
        if oscillates:
            found.append(
                Oscillation(
                    path=path,
                    symbol=symbol,
                    content_hash=content_hash,
                    rounds=tuple(r.round for r in ordered),
                )
            )
    return sorted(found, key=lambda o: (o.path, o.symbol, o.content_hash))


def scan_rounds(root: Path, slug: str, rounds: list[int]) -> list[HunkRecord]:
    """Re-read every repair round from the endpoint refs Phase 5 already pinned.

    No per-round accumulation file: the pins ARE the record, so a review that crashed
    mid-loop can still be scanned afterwards, and there is no second store to fall out of
    step with the first.
    """
    records: list[HunkRecord] = []
    for round_no in sorted(set(rounds)):
        try:
            diff = _git(
                root,
                "diff",
                pin_ref(slug, f"r{round_no}-pre"),
                pin_ref(slug, f"r{round_no}-post"),
            )
        except subprocess.CalledProcessError:
            # A round whose pins are missing is skipped, not fatal: the report is advisory
            # and a partial scan is worth more than no scan. It is also visible — the
            # round simply contributes no hunks, so it cannot fake a restoration.
            continue
        records.extend(parse_hunks(diff, round_no))
    return records


def oscillation_path(root: Path, slug: str) -> Path:
    return root / ".claude" / "observability" / f"review-oscillation-{slug}.jsonl"


def record_oscillations(root: Path, slug: str, findings: list[Oscillation]) -> Path:
    """Append one row per oscillation; write NOTHING when there are none.

    An empty file would read, later, as "the report ran and found nothing" for a review
    where it never ran at all.
    """
    path = oscillation_path(root, slug)
    if not findings:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(f.as_row(), sort_keys=True) + "\n" for f in findings)
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        view = memoryview(payload.encode("utf-8"))
        written = 0
        while written < len(view):
            n = os.write(fd, view[written:])
            if n == 0:
                raise OSError("os.write returned 0 appending the oscillation report")
            written += n
    finally:
        os.close(fd)
    return path


_USAGE = (
    "usage: hm review_churn measure --pre <ref> --post <ref> [--root <dir>]\n"
    "       hm review_churn pin --slug <slug> --label <name> [--root <dir>]\n"
    "       hm review_churn oscillation --slug <slug> --rounds 2,3,4 [--root <dir>]\n"
)


def main(argv: list[str] | None = None) -> int:
    guard = command_registry.guard_or_none("review_churn", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(prog="hm review_churn", add_help=True)
    parser.add_argument("verb", choices=["measure", "pin", "oscillation"])
    parser.add_argument("--pre")
    parser.add_argument("--post")
    parser.add_argument("--slug")
    parser.add_argument("--label")
    parser.add_argument("--rounds")
    parser.add_argument("--root", default=".")
    try:
        opts = parser.parse_args(argv if argv is not None else sys.argv[1:])
    except SystemExit:
        sys.stderr.write(_USAGE)
        raise

    try:
        if opts.verb == "pin":
            if not opts.slug or not opts.label:
                sys.stderr.write(_USAGE)
                return 2
            sys.stdout.write(pin(Path(opts.root), opts.slug, opts.label) + "\n")
            return 0
        if opts.verb == "oscillation":
            if not opts.slug or not opts.rounds:
                sys.stderr.write(_USAGE)
                return 2
            try:
                rounds = [int(part) for part in opts.rounds.split(",") if part.strip()]
            except ValueError:
                sys.stderr.write("--rounds takes comma-separated integers, e.g. 2,3,4\n")
                return 2
            root = Path(opts.root)
            findings = detect_oscillation(scan_rounds(root, opts.slug, rounds))
            record_oscillations(root, opts.slug, findings)
            sys.stdout.write(json.dumps([f.as_row() for f in findings], sort_keys=True) + "\n")
            return 0
        if not opts.pre or not opts.post:
            sys.stderr.write(_USAGE)
            return 2
        result = measure_refs(Path(opts.root), opts.pre, opts.post)
    except (subprocess.CalledProcessError, ChurnMeasurementError) as e:
        sys.stderr.write(f"[churn] measurement failed: {e}\n")
        return 1
    sys.stdout.write(json.dumps(result.as_detail(), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
