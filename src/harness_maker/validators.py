"""Cross-module input validators (Phase 6+).

Per Phase 6 amendment §F, workflow names have a reserved set:
- atomic stage names: research, spec, plan, execute, review, wrapup, verify
- meta verbs: make, audit, add, remove, promote, monitor, refresh, loop

Preset-seeded names (dev, quick, careful, audit, ship) are EXEMPT because
they're harness-author-supplied. The router treats them as ordinary names.

Note that `audit` appears in both lists. Per amendment §F it's exempt as a
preset seed, so the validator's job is only to block USER-CHOSEN names that
collide with the reserved set when typed via the interactive override path.
"""

from __future__ import annotations

import re

# Reserved set per amendment §F (atomic stages + meta verbs).
RESERVED_WORKFLOW_NAMES: frozenset[str] = frozenset(
    {
        # Atomic stages
        "research",
        "spec",
        "plan",
        "execute",
        "review",
        "wrapup",
        "verify",
        # Meta verbs
        "make",
        "audit",
        "add",
        "remove",
        "promote",
        "monitor",
        "refresh",
        "loop",
    },
)

# Preset-seeded names — exempt from the reserved-word check (amendment §F).
EXEMPT_PRESET_SEEDS: frozenset[str] = frozenset(
    {"dev", "quick", "careful", "audit", "ship"},
)

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def validate_workflow_name(name: str, *, exempt: bool = False) -> None:
    """Raise ValueError if `name` is invalid as a workflow name.

    Args:
        name: candidate name
        exempt: when True, skip the reserved-word check (used for
                preset-seeded names which are author-supplied, not user-typed)
    """
    if not _NAME_RE.match(name):
        msg = (
            f"Invalid workflow name {name!r}: must match ^[a-z][a-z0-9-]*$ "
            f"(lowercase letter, then lowercase letters/digits/hyphens)."
        )
        raise ValueError(msg)
    if exempt:
        return
    if name in RESERVED_WORKFLOW_NAMES:
        msg = (
            f"Workflow name {name!r} is reserved (atomic stages + meta verbs). "
            f"Pick a different name. "
            f"Reserved: {sorted(RESERVED_WORKFLOW_NAMES)}"
        )
        raise ValueError(msg)


def validate_workflow_names(names: list[str]) -> None:
    """Validate a list of user-typed workflow names; raise on the first invalid one."""
    for n in names:
        # Preset-seeded names are exempt from the reserved-word check.
        exempt = n in EXEMPT_PRESET_SEEDS
        validate_workflow_name(n, exempt=exempt)
