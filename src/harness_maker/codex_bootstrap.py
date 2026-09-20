"""Pure package/engine identity helpers for the future Codex bootstrap.

No filesystem, installation, or stage dispatch occurs here. Package cachebusters
identify local plugin builds, not published Python distributions.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

_RELEASE = re.compile(
    r"(?P<release>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))"
    r"(?:\+codex\.[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?"
)


def _engine_version(version: object) -> str:
    if not isinstance(version, str) or (match := _RELEASE.fullmatch(version)) is None:
        raise ValueError("unsupported release: expected x.y.z with optional +codex suffix")
    return match.group("release")


def engine_requirement(manifest: Mapping[str, object]) -> str:
    """Resolve only a known stable engine release; never guess from arbitrary metadata."""
    if manifest.get("name") != "harness-maker":
        raise ValueError("package name must be harness-maker")
    return f"harness-maker=={_engine_version(manifest.get('version'))}"


@dataclass(frozen=True)
class UpdateStatus:
    """An observation, not proof that any command was run or succeeded."""

    state: Literal["pending", "partial", "complete"]
    pending: tuple[str, ...]


def update_status(
    target: str, *, plugin: str | None, engine: str | None, project: str | None
) -> UpdateStatus:
    """Compare exact package identity and stable engine/project release independently.

    Missing, old, or unsupported observed identities are pending. The caller must
    obtain these observations after operations; no success is inferred from intent.
    """
    release = _engine_version(target)
    expected = (
        ("plugin", plugin, target),
        ("engine", engine, release),
        ("project", project, release),
    )
    pending = tuple(name for name, observed, required in expected if observed != required)
    state: Literal["pending", "partial", "complete"]
    if not pending:
        state = "complete"
    elif len(pending) == len(expected):
        state = "pending"
    else:
        state = "partial"
    return UpdateStatus(state, pending)
