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
_ACTIVE_STATUSES = frozenset({"planning"})


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

    raw_commands = block.get("commands", {})
    if not isinstance(raw_commands, dict):
        raise AllowanceError(f"{path.name}: surface_allowance.commands must be a mapping")
    commands: dict[str, int] = {}
    for name, value in raw_commands.items():
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise AllowanceError(
                f"{path.name}: surface_allowance.commands[{name!r}] "
                f"must be a positive int, got {value!r}"
            )
        commands[str(name)] = value

    slug = str(block.get("slug") or path.stem.removeprefix("PLAN-"))
    return Allowance(
        slug=slug, chars=chars, reason=str(reason), delta_doc=str(delta_doc), commands=commands
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


def aggregate_headroom(root: Path) -> int:
    """Total characters the aggregate ratchet may exceed its frozen baseline by."""
    return sum(a.chars for a in load_active_allowances(root))


def command_headroom(root: Path, command: str) -> int:
    """Characters a single rendered command may exceed its per-command ceiling by."""
    return sum(a.commands.get(command, 0) for a in load_active_allowances(root))
