"""Which validator critiques earn a follow-up round — the plan-stage analogue of the review loop.

`/hm:plan`'s cost is NOT its validator passes: those are capped at two and the cap holds. It is
the **follow-up interview rounds**, which the stage spends one-per-critique with no bound. Two
mechanisms from the review loop transfer, and one does not:

- **Progress invariant — transfers.** A critique that survives a revision unchanged is
  `unresolved`; answering it again is the round that produced nothing. Merge is by stable `id`,
  and the lattice is monotonic: nothing returns to `pending`.
- **Churn — transfers INVERTED.** In `/hm:review` a LOW churn ratio skips the re-review. That
  shape must not be copied here: `plan.md.j2` records 12 validator episodes, none ever clean,
  and one PLAN whose pass-2 criticals were *created by the pass-1 fixes* — so "small edit,
  skip the check" is the reading its own measurement refutes. What transfers is the other
  direction: once a revision has rewritten enough of the PLAN, the critiques still queued were
  raised against a document that no longer exists. They go `stale` and cost no round. Nothing is
  lost, because Step 4.5's terminal pass re-derives whatever still holds.
- **The lens axis — does NOT transfer.** `plan-validator` is a single agent, not a fan-out.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_maker import command_registry

#: Above this fraction of the PLAN rewritten since a critique was raised, the critique is stale.
#: Higher than the review gate's 0.20 on purpose: there the ratio decides whether to LOOK at a
#: repair, here it decides whether to DROP a question the validator already asked, so the bar to
#: discard is the higher one.
DEFAULT_STALE_RATIO = 0.50

STATUSES: tuple[str, ...] = ("pending", "resolved", "stale", "unresolved")

#: `pending` is the only status a critique may leave. Every other one is terminal for the pass —
#: the same monotonic rule the review loop needed after a reviewer's non-determinism alone was
#: enough to move a grade with no code change.
_TERMINAL: frozenset[str] = frozenset({"resolved", "stale", "unresolved"})

_WS = re.compile(r"\s+")


class PlanRoundsError(ValueError):
    """Input the round planner has no reading over."""


def critique_id(section: str, title: str) -> str:
    """Stable across passes, and computed HERE rather than asked of the model.

    The review loop learned this twice: an LLM-minted id changes every run, so merge-by-id
    silently degrades into "everything is new" and the progress invariant can never fire.
    Whitespace- and case-normalised so a re-worded indentation does not mint a second id for
    one critique.
    """
    key = f"{_WS.sub(' ', section).strip().lower()}\x00{_WS.sub(' ', title).strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Critique:
    id: str
    severity: str
    section: str
    title: str
    status: str = "pending"

    def as_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "section": self.section,
            "title": self.title,
            "status": self.status,
        }


def _coerce(raw: dict[str, Any]) -> Critique:
    section = str(raw.get("section", ""))
    title = str(raw.get("title", ""))
    if not title.strip():
        raise PlanRoundsError(f"critique has no title: {raw!r}")
    severity = str(raw.get("severity", "critical"))
    status = str(raw.get("status", "pending"))
    if status not in STATUSES:
        raise PlanRoundsError(f"unknown status {status!r}; expected one of {STATUSES}")
    return Critique(
        id=str(raw.get("id") or critique_id(section, title)),
        severity=severity,
        section=section,
        title=title,
        status=status,
    )


def stamp_ids(critiques: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_coerce(c).as_row() for c in critiques]


def merge_passes(
    previous: list[dict[str, Any]], current: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge pass N-1 into pass N by `id`, monotonically.

    A critique the earlier pass raised and this pass raised again was NOT resolved by the
    revision in between — it becomes `unresolved` and buys no further round. One that this pass
    no longer raises is `resolved`. Wholesale replacement would lose both facts and re-ask the
    same question every pass, which is the loop that does not converge.
    """
    prior = {c.id: c for c in (_coerce(x) for x in previous)}
    now = {c.id: c for c in (_coerce(x) for x in current)}

    merged: list[Critique] = []
    for cid, c in now.items():
        was = prior.get(cid)
        if was is None:
            merged.append(c)
            continue
        if was.status in _TERMINAL:
            # Already decided; a later pass restating it does not reopen it.
            merged.append(Critique(cid, c.severity, c.section, c.title, was.status))
            continue
        merged.append(Critique(cid, c.severity, c.section, c.title, "unresolved"))

    for cid, was in prior.items():
        if cid in now:
            continue
        status = was.status if was.status in _TERMINAL else "resolved"
        merged.append(Critique(cid, was.severity, was.section, was.title, status))

    return [c.as_row() for c in merged]


def follow_up_plan(
    critiques: list[dict[str, Any]],
    *,
    churn_ratio: float | None = None,
    threshold: float = DEFAULT_STALE_RATIO,
) -> dict[str, Any]:
    """The rounds to actually run, and the reason for every one not run.

    `churn_ratio` is how much of the PLAN changed since these critiques were raised. **`None`
    means unmeasured, and unmeasured runs every round** — the opposite default would let a
    missing measurement silently cancel the stage's entire revision step, which is this repo's
    most-recurring failure class.
    """
    rows = [_coerce(c) for c in critiques]
    stale = churn_ratio is not None and churn_ratio >= threshold

    rounds: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for c in rows:
        if c.status in _TERMINAL:
            skipped.append({**c.as_row(), "reason": f"status={c.status}"})
            continue
        if stale:
            skipped.append(
                {
                    **Critique(c.id, c.severity, c.section, c.title, "stale").as_row(),
                    "reason": (
                        f"plan churned {churn_ratio:.2f} >= {threshold:.2f} since it was raised; "
                        "the terminal pass re-derives it if it still holds"
                    ),
                }
            )
            continue
        rounds.append(c.as_row())

    # Critical before warning, then stable by id so two runs over one input agree.
    rounds.sort(key=lambda r: (0 if r["severity"] == "critical" else 1, r["id"]))
    return {
        "rounds": rounds,
        "skipped": skipped,
        "churn_ratio": churn_ratio,
        "threshold": threshold,
    }


def pass_outcome(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, Any]:
    """Whether the pass in between changed anything, in the loop's own vocabulary.

    `no-progress` and `cap-exhausted` are different endings and the PLAN's reader acts on them
    differently: the first says the revision step is not working on this document, the second
    says it ran out of passes while still moving. Reporting the cap for both — which a bare
    two-pass limit does — hides the first entirely.
    """
    merged = merge_passes(previous, current)
    resolved = [c for c in merged if c["status"] == "resolved"]
    unresolved = [c for c in merged if c["status"] == "unresolved"]
    fresh = [c for c in merged if c["status"] == "pending"]
    progressed = bool(resolved) or bool(fresh)
    return {
        "outcome": "progress" if progressed else "no-progress",
        "resolved_n": len(resolved),
        "unresolved_n": len(unresolved),
        "new_n": len(fresh),
        "critiques": merged,
    }


def _load(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PlanRoundsError(f"cannot read {path}: {exc}") from exc
    except ValueError as exc:
        raise PlanRoundsError(f"{path} is not valid JSON: {exc}") from exc
    if isinstance(data, dict):
        inner = data.get("critiques")
        if not isinstance(inner, list):
            raise PlanRoundsError(f"{path} is an object without a `critiques` list")
        return [x for x in inner if isinstance(x, dict)]
    if not isinstance(data, list):
        raise PlanRoundsError(f"{path} must be a list or an object with `critiques`")
    return [x for x in data if isinstance(x, dict)]


_USAGE = (
    "usage: hm plan_rounds plan --file <critiques.json> [--previous <prior.json>]\n"
    "                          [--churn-ratio <r>] [--threshold <t>]\n"
    "       hm plan_rounds outcome --file <critiques.json> --previous <prior.json>\n"
    "\n"
    "  plan     which critiques earn a follow-up round, and why each other one does not.\n"
    "  outcome  progress | no-progress between two validator passes.\n"
    "Reads only; prints one JSON payload. Never writes.\n"
)


def main(argv: list[str] | None = None) -> int:
    guard = command_registry.guard_or_none("plan_rounds", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(prog="hm plan_rounds", add_help=False)
    parser.add_argument("verb", choices=["plan", "outcome"])
    parser.add_argument("--file", dest="file", required=True, type=Path)
    parser.add_argument("--previous", dest="previous", type=Path)
    parser.add_argument("--churn-ratio", dest="churn_ratio", type=float)
    parser.add_argument("--threshold", dest="threshold", type=float, default=DEFAULT_STALE_RATIO)
    try:
        opts = parser.parse_args(argv if argv is not None else sys.argv[1:])
    except SystemExit:
        sys.stderr.write(_USAGE)
        return 2

    try:
        current = _load(opts.file)
        previous = _load(opts.previous) if opts.previous else []
        if opts.verb == "outcome":
            if not opts.previous:
                sys.stderr.write("outcome needs --previous\n")
                return 2
            payload: dict[str, Any] = pass_outcome(previous, current)
        else:
            merged = merge_passes(previous, current) if previous else stamp_ids(current)
            payload = follow_up_plan(merged, churn_ratio=opts.churn_ratio, threshold=opts.threshold)
    except PlanRoundsError as exc:
        sys.stderr.write(f"[plan_rounds] {exc}\n")
        return 2

    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
