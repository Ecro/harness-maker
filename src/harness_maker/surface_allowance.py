"""Per-PLAN, expiring headroom above the frozen shipped-surface ratchet."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)

#: A PLAN only holds headroom while it is in flight. On completion the growth is folded
#: into the baseline once, with its BASELINE-DELTA attribution — that is the legitimate
#: re-freeze moment, and it is what stops allowances accumulating into no ratchet at all.
#:
#: `blocked` counts as in-flight. `plan.md.j2`'s halt path writes it when an iteration hits a
#: decision needing an ADR — the PLAN is then maximally mid-work, and expiring its headroom there
#: fails the ratchet gate with a message telling the author to regenerate `surface_baseline.json`,
#: which is precisely the destructive act the allowance exists to remove. Only `wrapup` writes the
#: terminal `complete`.
_ACTIVE_STATUSES = frozenset({"planning", "blocked"})


class AllowanceError(ValueError):
    """A malformed `surface_allowance` block.

    Fail loudly. A silently-ignored allowance reads as "the budget got tighter" at a
    moment when someone is actively trying to spend it, and the reader would go looking
    in the wrong place — the ratchet, not their own frontmatter.
    """


@dataclass(frozen=True)
class Allowance:
    """One in-flight PLAN's headroom."""

    slug: str
    chars: int
    reason: str
    delta_doc: str
    commands: dict[str, int] = field(default_factory=dict)
    round_trips: dict[str, int] = field(default_factory=dict)


def _require(block: dict[str, object], key: str, path: Path) -> object:
    if key not in block:
        raise AllowanceError(f"{path.name}: surface_allowance is missing required key {key!r}")
    return block[key]


def _parse(block: object, path: Path) -> Allowance:
    if not isinstance(block, dict):
        raise AllowanceError(
            f"{path.name}: surface_allowance must be a mapping, got {type(block).__name__}"
        )

    chars = _require(block, "chars", path)
    if isinstance(chars, bool) or not isinstance(chars, int) or chars <= 0:
        raise AllowanceError(
            f"{path.name}: surface_allowance.chars must be a positive int, got {chars!r}"
        )

    reason = _require(block, "reason", path)
    delta_doc = _require(block, "delta_doc", path)
    for name, value in (("reason", reason), ("delta_doc", delta_doc)):
        if not isinstance(value, str) or not value.strip():
            raise AllowanceError(
                f"{path.name}: surface_allowance.{name} must be a non-empty string"
            )

    # An allowance with no attribution document is the thing this mechanism exists to
    # replace — an unexplained number that makes the budget bigger.
    if not (path.parent / str(delta_doc)).is_file():
        raise AllowanceError(
            f"{path.name}: surface_allowance.delta_doc {delta_doc!r} "
            "does not exist next to the PLAN"
        )

    def _positive_int_map(key: str) -> dict[str, int]:
        raw = block.get(key, {})
        if not isinstance(raw, dict):
            raise AllowanceError(f"{path.name}: surface_allowance.{key} must be a mapping")
        out: dict[str, int] = {}
        for name, value in raw.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise AllowanceError(
                    f"{path.name}: surface_allowance.{key}[{name!r}] "
                    f"must be a positive int, got {value!r}"
                )
            out[str(name)] = value
        return out

    slug = str(block.get("slug") or path.stem.removeprefix("PLAN-"))
    return Allowance(
        slug=slug,
        chars=chars,
        reason=str(reason),
        delta_doc=str(delta_doc),
        commands=_positive_int_map("commands"),
        round_trips=_positive_int_map("round_trips"),
    )


def load_active_allowances(root: Path) -> list[Allowance]:
    """Every in-flight PLAN's allowance, in slug order.

    A PLAN with no `surface_allowance` contributes nothing; a completed PLAN's allowance
    is ignored even when the block is still present, so the headroom disappears the moment
    the work lands rather than needing a separate cleanup step nobody would run.
    """
    work_docs = root / "work-docs"
    if not work_docs.is_dir():
        return []

    found: list[Allowance] = []
    for path in sorted(work_docs.glob("PLAN-*.md")):
        match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if match is None:
            continue
        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        if not isinstance(meta, dict) or "surface_allowance" not in meta:
            continue
        if str(meta.get("status", "")).strip() not in _ACTIVE_STATUSES:
            continue
        found.append(_parse(meta["surface_allowance"], path))
    return found


def _sole_active(root: Path) -> list[Allowance]:
    """The active allowances, refusing to SUM across two in-flight PLANs.

    Headroom has no ownership key: the gates pass only the repo root, so summing means every
    in-flight PLAN's declared growth funds every other's. Session B, whose change earned zero
    headroom, would pass the ratchet on session A's budget — and the failure message reports only
    the total, so nothing says whose. This repo runs N concurrent sessions by default, which is
    the case that makes it fail OPEN rather than the exotic one.

    Refusing is the honest control: a real second concurrent allowance is rare, and when it
    happens the author must fold the completed PLAN's growth into the baseline (the legitimate
    re-freeze) rather than silently borrowing.
    """
    active = load_active_allowances(root)
    if len(active) > 1:
        slugs = ", ".join(a.slug for a in active)
        raise AllowanceError(
            f"{len(active)} in-flight PLANs declare a surface_allowance ({slugs}). Headroom is "
            "not attributable across PLANs — one PLAN's growth would be funded by another's "
            "budget. Fold the completed PLAN's growth into surface_baseline.json with its "
            "delta doc, or set its status away from planning/blocked."
        )
    return active


def aggregate_headroom(root: Path) -> int:
    """Total characters the aggregate ratchet may exceed its frozen baseline by."""
    return sum(a.chars for a in _sole_active(root))


def command_headroom(root: Path, command: str) -> int:
    """Characters a single rendered command may exceed its per-command ceiling by."""
    return sum(a.commands.get(command, 0) for a in _sole_active(root))


def round_trip_headroom(root: Path, command: str) -> int:
    """Extra mandated calls an in-flight PLAN may add to one command.

    Round trips are compared **exactly** rather than ratcheted — a mandated call is added or
    removed on purpose, never "improved" — so an in-flight PLAN that deliberately adds dispatches
    has to declare how many, in the same frontmatter block that funds its characters. Without
    this the only way to go green is regenerating `surface_baseline.json`, which rewrites the
    frozen `chars` in the same file and destroys the ratchet as a side effect of a description
    update.

    The key is the baseline's own command name, **per variant** (`review` and `hm-review` are
    separate declarations). They are not interchangeable: the counting rule differs by variant —
    `^!` lines for claude, `Bash(` call sites for codex — and the template branches on `is_codex`,
    so one edit legitimately adds a different number of calls to each. Folding them onto one key
    would let a real drift in one variant hide behind the other's declaration.
    """
    return sum(a.round_trips.get(command, 0) for a in _sole_active(root))
