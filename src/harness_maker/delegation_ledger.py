"""One row per delegation invocation, at the BASE repo — the denominator nobody had."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from . import command_registry
from .io_utils import append_atomic_line

LEDGER_FILENAME = "delegation.jsonl"

# The atomic helper raises above PIPE_BUF (4096) BYTES. `reason` carries `verdict.reason`,
# the only caller-supplied field with no natural bound, so it is the one that gets shrunk.
_MAX_ROW_BYTES = 4096
_TRUNCATION_MARK = "…[truncated]"

# The health signal reads the most recent N `brief`/`ok` rows and the dispatch rows at or
# after the oldest of them. Bounded by BRIEF rows rather than by total rows so a burst of
# dispatch rows cannot push the briefs they are measured against out of the window.
WINDOW_BRIEFS = 10

Kind = Literal["brief", "dispatch"]
# `mismatch` / `unparseable` mean the subagent WAS dispatched and its reply did not
# reconcile — a different problem from never dispatching, and conflating them blames the
# user for the wrong thing. `unavailable` means this IDE has no dispatch tool at all.
_DISPATCH_HAPPENED = frozenset({"dispatched", "mismatch", "unparseable"})
_SELF_SKIP = "unavailable"
DISPATCH_STATUSES = (*sorted(_DISPATCH_HAPPENED), _SELF_SKIP)
BRIEF_STATUSES = ("ok", "degraded")

# Sort position for a row whose `ts` cannot be parsed. See `_when`.
_EPOCH = datetime.min.replace(tzinfo=UTC)


def ledger_path(base: Path) -> Path:
    """Always the BASE repo's observability dir.

    `codex_ledger` shipped with `project_root=Path.cwd()`, which under the task-worktree
    model wrote into a gitignored path inside the worktree and vanished at `task-land`.
    Callers resolve the base themselves and pass it here.
    """
    return base / ".claude" / "observability" / LEDGER_FILENAME


def _fit(row: dict[str, Any]) -> str:
    """Serialise the row, shrinking `reason` until the ENCODED line fits PIPE_BUF.

    Measured, not estimated: the loop re-encodes after each cut, so it is correct for any
    encoding width instead of assuming one byte per character.
    """
    line = json.dumps(row, ensure_ascii=False)
    if len(line.encode("utf-8")) + 1 <= _MAX_ROW_BYTES:
        return line
    reason = row.get("reason")
    if not isinstance(reason, str):
        return line  # nothing shrinkable; the caller's except handles the raise
    keep = len(reason)
    while keep > 0:
        keep //= 2
        row = {**row, "reason": reason[:keep] + _TRUNCATION_MARK}
        line = json.dumps(row, ensure_ascii=False)
        if len(line.encode("utf-8")) + 1 <= _MAX_ROW_BYTES:
            return line
    return json.dumps({**row, "reason": _TRUNCATION_MARK}, ensure_ascii=False)


def append(
    base: Path,
    *,
    stage: str,
    slug: str,
    kind: Kind,
    status: str,
    reason: str | None = None,
    now: datetime | None = None,
) -> None:
    """Append-only, and never raises: observability must not break the thing it observes.

    The write goes through `io_utils.append_atomic_line` — the repo's existing
    O_APPEND + `os.write` + `fsync` helper — rather than a buffered `open("a")`. This
    ledger is deliberately shared: `ledger_path` forces every session to the same base-repo
    file, and this project supports 10–20 parallel sessions. A buffered write can be split
    across syscalls and interleave with a peer's row, and `read_rows` drops the resulting
    torn line silently — which pushes `dispatch_verdict` toward `no-dispatch`/`no-rows`,
    i.e. the failing arm, reached through unevaluability rather than through evidence.

    The row is shrunk against the helper's PIPE_BUF ceiling by **measuring the encoded
    bytes**, not by capping a field's character count. A character cap is the wrong unit
    twice over: the ceiling is 4096 bytes over the WHOLE row, and this project's default
    locale is Korean, where one `reason` character costs three bytes — so a
    "safely truncated" reason could still overflow and the row would be dropped in the
    `except` below. Silently losing a row moves `dispatch_verdict` toward its failing arm
    through unevaluability rather than evidence, which is what this module must not do.
    """
    row = {
        "ts": (now or datetime.now(UTC)).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "stage": stage,
        "slug": slug,
        "kind": kind,
        "status": status,
        "reason": reason,
    }
    path = ledger_path(base)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        append_atomic_line(path, _fit(row))
    except (OSError, ValueError):
        # ValueError is the helper's over-PIPE_BUF guard. `_fit` shrinks only `reason`, so
        # a caller passing a pathological `stage`/`slug` can still trip it; that loses one
        # observability row and never the wrapup being observed.
        return


def read_rows(base: Path) -> list[dict[str, Any]]:
    """Absent ledger is empty, not an error — that is the state every harness ships in.

    A corrupt line is skipped rather than fatal: a truncated write in a gitignored churn
    directory must not make the health signal unevaluable, because "unevaluable" would
    surface as "no invocations", which is the failing arm.
    """
    path = ledger_path(base)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _when(row: dict[str, Any]) -> datetime:
    """Parsed `ts`; an unreadable one returns the `_EPOCH` sentinel.

    Callers must treat `_EPOCH` as "not placeable in time", not merely as "very old". In
    the DISPATCH position sorting it oldest is enough — `_EPOCH >= floor` is false, so the
    row drops out. In the BRIEF position it is not: an epoch-sorted brief that survives the
    window slice becomes the floor and admits every dispatch in the file. `dispatch_verdict`
    therefore filters it out rather than relying on the ordering.

    Identity (`is _EPOCH`) is the safe test, not equality: a `ts` that legitimately parses
    to `0001-01-01T00:00:00+00:00` would compare equal while being perfectly readable.
    """
    raw = row.get("ts")
    if not isinstance(raw, str):
        return _EPOCH
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return _EPOCH
    # A writer that stamped a naive timestamp is read as UTC rather than crashing the
    # comparison; every shipped writer stamps UTC.
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def dispatch_verdict(rows: list[dict[str, Any]], *, stage: str) -> str:
    """`no-rows` | `brief-degrading` | `no-dispatch` | `unavailable-only` | `ok`.

    Lifetime existence is the wrong question. The ledger is append-only, so "has a
    dispatch ever succeeded" goes green on the first success and stays green through every
    later regression — this defect's own blind spot, rebuilt one layer in.

    **The window is anchored on ALL brief rows, not only the `ok` ones.** Anchoring on
    `ok` briefs alone re-opened that same blind spot one condition deeper: when the brief
    starts degrading, no new `ok` row is ever appended, so the floor stays pinned to the
    last healthy era whose dispatch rows are still inside it — and the verdict reads `ok`
    forever, through any number of non-dispatching runs. That is precisely the regression
    this signal exists to catch, so the arm that catches it cannot depend on the thing
    that stops happening.

    Ordering is by PARSED timestamp, not by file order. File order and timestamp order
    diverge under late writes, interleaved concurrent sessions, and a backward clock; the
    slice and the comparison must therefore agree on one notion of "recent". Sorting is
    stable, so rows sharing a timestamp keep file order.

    **The ledger is shared across stages, so the window is stage-scoped.** Both writers
    stamp `stage`; reading it is not optional once every brief row became load-bearing.
    `verify` is also a delegatable stage and its rendered line carries no `--slug`, so its
    briefs degrade structurally — unfiltered, a handful of verify runs would push a
    correctly-dispatching wrapup to `brief-degrading`, and a verify dispatch row would
    vouch for a wrapup that never dispatched.

    **A brief whose timestamp will not parse is excluded from the window entirely**, not
    merely sorted first. Sorting it first was fail-OPEN in this position: it survives the
    slice whenever the ledger holds few enough briefs, lands at index 0, and sets the floor
    to the epoch — which admits every dispatch row in the file and restores exactly the
    lifetime-existence semantics this function exists to remove. A row that cannot be
    placed in time has no place in a recency window.
    """
    briefs = [r for r in rows if r.get("kind") == "brief" and r.get("stage") == stage]
    datable = [b for b in briefs if _when(b) is not _EPOCH]
    if not datable:
        # Either nothing has run, or nothing that ran left a readable timestamp. Both are
        # "no usable invocation record", and both are remedied by producing fresh rows.
        return "no-rows"
    window = sorted(datable, key=_when)[-WINDOW_BRIEFS:]
    floor = _when(window[0])
    recent = [
        r
        for r in rows
        if r.get("kind") == "dispatch" and r.get("stage") == stage and _when(r) >= floor
    ]

    if not recent:
        # No dispatch in the window. WHY it is missing decides the remedy, and the two
        # causes need different ones: a brief that cannot be derived means Step 0.5 never
        # reaches the dispatch at all, so telling the user to "check that the dispatch is
        # issued" points at the wrong half of the seam.
        if all(str(r.get("status")) != "ok" for r in window):
            return "brief-degrading"
        return "no-dispatch"

    if any(str(r.get("status")) in _DISPATCH_HAPPENED for r in recent):
        return "ok"
    # `unavailable-only` is a PASS, so it must be reached only by explicit evidence that
    # every recent dispatch was a self-skip. An earlier version returned it for ANY row
    # not in `_DISPATCH_HAPPENED` — a typo, a corrupt row, or a status some future writer
    # adds would all have read as "this IDE has no subagent tool" and turned the signal
    # green. That is fail-OPEN on unevaluable input, which is the failure shape this
    # signal exists to eliminate.
    if all(str(r.get("status")) == _SELF_SKIP for r in recent):
        return "unavailable-only"
    return "no-dispatch"


# ------------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    """The third writer: a rendered prose branch, which has no Python entry point of its own.

    `stages/wrapup.md.j2` self-skips the subagent in IDEs with no dispatch tool. Without a
    row, those harnesses are indistinguishable from a harness whose dispatch is simply
    never firing — the failing arm, on an action their user cannot satisfy.

    A malformed invocation still exits non-zero through argparse; that is a template bug a
    render test catches, not a runtime condition. The *recording* itself never raises.
    """
    # The uniform misroute hook, wired when this module was registered in
    # `command_registry.MODULES`. Without it a verb owned by another module (`record`
    # vs. e.g. `emit`) reaches argparse and dies with "invalid choice", which reads as a
    # template typo rather than as a call routed to the wrong module.
    guard = command_registry.guard_or_none("delegation_ledger", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(prog="hm delegation_ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record", help="append one row at the base repo's ledger")
    record.add_argument("--root", default=".", help="any path inside the repo; base is resolved")
    record.add_argument("--stage", required=True)
    record.add_argument("--slug", default="")
    record.add_argument("--kind", required=True, choices=("brief", "dispatch"))
    # `choices` at the WRITER, so a template typo fails loudly at the call site instead of
    # writing a status the verdict cannot interpret. Validated against `--kind` below:
    # `DISPATCH_STATUSES` alone would reject every legal brief status, and a brief row
    # carrying a dispatch status reads as `degrading` — the inverse of the strictness the
    # dispatch side deliberately has.
    record.add_argument("--status", required=True, choices=(*DISPATCH_STATUSES, *BRIEF_STATUSES))
    record.add_argument("--reason", default=None)
    ns = parser.parse_args(argv if argv is not None else sys.argv[1:])
    allowed = DISPATCH_STATUSES if ns.kind == "dispatch" else BRIEF_STATUSES
    if ns.status not in allowed:
        parser.error(f"--status {ns.status!r} is not valid for --kind {ns.kind}: {allowed}")

    # Imported here, not at module scope: `readiness` reads this ledger, and hoisting the
    # invoker's import would drag a subprocess-heavy module into the health path for a
    # function only the CLI uses.
    from .second_opinion_invoke import resolve_base_root

    append(
        resolve_base_root(Path(ns.root).resolve()),
        stage=ns.stage,
        slug=ns.slug,
        kind=ns.kind,
        status=ns.status,
        reason=ns.reason,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
