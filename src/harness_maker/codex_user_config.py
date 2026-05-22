"""Bootstrap `[profiles.*]` blocks into the user-level Codex config.

Why this module exists: Codex CLI v0.130+ enforces a strict whitelist for
project-local ``.codex/config.toml`` (features/agents/mcp_servers/hooks).
``[profiles.*]`` is rejected there with a "Ignored unsupported
project-local config keys ... profiles" warning at every session start.
ADR-008 (PLAN-model-routing-multi-ide) needs ``profiles.cheap`` /
``profiles.deep`` to function (the ``codex -p cheap`` / ``codex -p deep``
cost-lever shortcuts), so the only valid location is the user-level
``~/.codex/config.toml``.

This module installs those two blocks idempotently. It MUST NOT overwrite
or rearrange existing user content — it only appends blocks that aren't
already declared. Detection is intentionally lexical — a regex that
tolerates TOML's whitespace-in-brackets rule — rather than a full TOML
round-trip so we never reformat the user's file or strip their inline
comments. The regex also intentionally matches commented-out headers
(``# [profiles.cheap]``); if a user deliberately disabled the block, we
should not re-add it on their behalf.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from harness_maker.io_utils import atomic_write

_HEADER = (
    "# harness-maker (ADR-008): per-loop invocation profiles. Codex CLI\n"
    "# rejects [profiles.*] in project-local .codex/config.toml, so they\n"
    "# live here at the user level. Safe to edit or remove — `harness-maker\n"
    "# make` only adds blocks that are absent; it never overwrites yours.\n"
)

_CHEAP_BLOCK = '[profiles.cheap]\nmodel_reasoning_effort = "minimal"\n'
_DEEP_BLOCK = '[profiles.deep]\nmodel_reasoning_effort = "high"\n'

# TOML spec §4.5 allows whitespace inside bracketed table headers
# (`[ profiles.cheap ]` ≡ `[profiles.cheap]`). The lexical guard must
# match every spelling a TOML formatter might emit, otherwise we'd
# duplicate the block and Codex would reject the file on next parse.
# The regex is multiline-aware and matches anywhere on a line (so
# `# [profiles.cheap]` — a user-disabled block — also counts as
# present; we respect intentional disablement).
_CHEAP_HEADER_RE = re.compile(r"\[\s*profiles\.cheap\s*\]")
_DEEP_HEADER_RE = re.compile(r"\[\s*profiles\.deep\s*\]")


@dataclass(frozen=True)
class BootstrapResult:
    """What was changed in ``~/.codex/config.toml``.

    ``installed`` lists the profile names we appended this run (subset of
    ``{"cheap", "deep"}``). Empty list means the file already had both
    blocks — no write happened. Callers print a one-line notice keyed on
    this list so a no-op is silent.
    """

    path: Path
    installed: list[str]

    @property
    def changed(self) -> bool:
        return bool(self.installed)


def bootstrap_user_codex_profiles(home: Path | None = None) -> BootstrapResult:
    """Append `[profiles.cheap]` / `[profiles.deep]` to ``~/.codex/config.toml``.

    Idempotent: each block is only added if the corresponding marker
    (``[profiles.cheap]`` / ``[profiles.deep]``) is not already present
    somewhere in the file. Comment lines and whitespace are preserved.

    ``home`` is injectable for tests so we don't have to monkeypatch
    ``Path.home()`` at every call site.
    """
    home = home or Path.home()
    path = home / ".codex" / "config.toml"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    additions: list[tuple[str, str]] = []
    if not _CHEAP_HEADER_RE.search(existing):
        additions.append(("cheap", _CHEAP_BLOCK))
    if not _DEEP_HEADER_RE.search(existing):
        additions.append(("deep", _DEEP_BLOCK))
    if not additions:
        return BootstrapResult(path=path, installed=[])
    path.parent.mkdir(parents=True, exist_ok=True)
    # _HEADER explains the ADR-008 reasoning. Show it once, on fresh-file
    # creation. If the file already exists (partial install — e.g. user
    # had `cheap` but not `deep` from an earlier run), skip the header
    # so we don't re-prepend the same explanation block every time.
    body_parts: list[str] = []
    if not existing:
        body_parts.append(_HEADER)
    body_parts.extend(block for _name, block in additions)
    addition = "\n".join(body_parts)
    if existing and not existing.endswith("\n"):
        existing = existing + "\n"
    new_content = (existing + "\n" + addition) if existing else addition
    atomic_write(path, new_content)
    return BootstrapResult(path=path, installed=[name for name, _ in additions])
