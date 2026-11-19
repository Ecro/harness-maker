"""Splice dead harness-maker `--with` refs in a project's hook files to the live plugin cache."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness_maker.command_registry import MODULES
from harness_maker.io_utils import atomic_write
from harness_maker.render import _splice_install_ref

HEAL_FILES: tuple[str, ...] = (".claude/settings.json", ".codex/hooks.json")

_CACHE_PARTS = (".claude", "plugins", "cache")
_INVOKE = " python -m harness_maker."
_WITH_TOKEN = re.compile(r"--with\s+(\"[^\"]*\"|'[^']*'|\S+)")


@dataclass
class HealReport:
    healed: dict[str, int] = field(default_factory=dict)
    unhealable: list[str] = field(default_factory=list)


def _cache_parts(path: Path, home: Path) -> tuple[str, ...] | None:
    """`path`'s parts under `home` when it has the plugin-cache shape, else None.

    The unresolved form is tried first: a dotfiles setup that symlinks `~/.claude` out of home
    would otherwise never match once resolved.
    """
    for base, candidate in ((home, path), (home.resolve(), path.resolve())):
        try:
            parts = candidate.relative_to(base).parts
        except ValueError:
            continue
        if len(parts) == 6 and parts[:3] == _CACHE_PARTS and parts[4] == "harness-maker":
            return parts
    return None


def _plugin_cache_ref(plugin_root: str | None, home: Path) -> str | None:
    """`$HOME/...` form of `plugin_root`, only when it is a real plugin-cache install.

    A source checkout or `--plugin-dir` would otherwise become every project's gate code.
    """
    if not plugin_root:
        return None
    root = Path(plugin_root)
    parts = _cache_parts(root, home)
    if parts is None or not (root / "pyproject.toml").is_file():
        return None
    return "$HOME/" + "/".join(parts)


_HOME_PREFIX = re.compile(r"^(?:\$\{HOME\}|\$HOME|~)(?=$|[/\\])")


def _expand(raw: str, home: Path) -> Path | None:
    """The path `raw` names, or None when it is not a fully expandable local path."""
    raw = _HOME_PREFIX.sub(lambda _: str(home), raw, count=1).replace("\\", "/")
    if "$" in raw or "://" in raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else None


def _dead_token(cmd: str, home: Path) -> re.Match[str] | None:
    """The plugin-cache `--with` token of `cmd` whose directory is gone, if any.

    Only a plugin-cache-shaped ref is ours to repoint; a dev path, a URL, a bare package name
    or anything with an unexpanded variable is a hook the user chose and stays as written.
    """
    at = cmd.find(_INVOKE)
    if at < 0:
        return None
    for m in reversed(list(_WITH_TOKEN.finditer(cmd, 0, at))):
        raw = m.group(1)
        if raw[:1] in "\"'":
            raw = raw[1:-1]
        path = _expand(raw, home)
        if path is None or _cache_parts(path, home) is None:
            continue
        return None if path.is_dir() else m
    return None


def _module(cmd: str) -> str:
    tail = cmd[cmd.find(_INVOKE) + len(_INVOKE) :]
    return tail.split()[0] if tail.split() else ""


def _commands(node: Any) -> list[str]:  # noqa: ANN401 — heterogeneous JSON
    if isinstance(node, dict):
        found = [node["command"]] if isinstance(node.get("command"), str) else []
        return found + [c for v in node.values() for c in _commands(v)]
    if isinstance(node, list):
        return [c for v in node for c in _commands(v)]
    return []


def _note(report: HealReport, item: str) -> None:
    if item not in report.unhealable:
        report.unhealable.append(item)


def _current_bytes(path: Path) -> bytes:
    """Re-read seam for the compare-and-swap check."""
    return path.read_bytes()


def _heal_file(path: Path, token: str, home: Path, report: HealReport, rel: str) -> None:
    try:
        original = path.read_bytes()
        doc = json.loads(original.decode("utf-8"))
    except (OSError, ValueError):
        return
    text = original.decode("utf-8")
    count = 0
    for cmd in dict.fromkeys(_commands(doc)):
        m = _dead_token(cmd, home)
        if m is None:
            continue
        module = _module(cmd)
        if module not in MODULES:
            _note(report, module)
            continue
        new = cmd[: m.start()] + _splice_install_ref(cmd[m.start() :], f'--with "{token}"')
        for ascii_only in (False, True):
            old_enc = json.dumps(cmd, ensure_ascii=ascii_only)
            if old_enc in text:
                count += text.count(old_enc)
                text = text.replace(old_enc, json.dumps(new, ensure_ascii=ascii_only))
                break
        else:
            # Escaped on disk in a form we cannot splice byte-for-byte: say so, never stay silent.
            _note(report, f"{module} in {rel}")
    if not count or _current_bytes(path) != original:
        return
    target = path.resolve()  # a symlinked settings.json keeps being a symlink
    mode = stat.S_IMODE(target.stat().st_mode)
    atomic_write(target, text)
    os.chmod(target, mode)  # atomic_write's temp file would leave a committed 0644 as 0600
    report.healed[rel] = count


def heal_project(project: Path, *, plugin_root: str | None, home: Path | None = None) -> HealReport:
    """Repair hook refs a plugin update pruned, so the gates run again without a re-render."""
    report = HealReport()
    home = home if home is not None else Path.home()
    token = _plugin_cache_ref(plugin_root, home)
    if token is None or not (project / ".claude/harness.yaml").is_file():
        return report
    for rel in HEAL_FILES:
        path = project / rel
        if path.is_file():
            try:
                _heal_file(path, token, home, report, rel)
            except OSError as exc:  # one unwritable file must not cost the others their repair
                _note(report, f"{rel} ({type(exc).__name__})")
    return report


def describe(report: HealReport) -> str | None:
    """SessionStart text for a heal; None when nothing happened."""
    if not report.healed and not report.unhealable:
        return None
    lines = ["[harness-maker self-heal]"]
    if report.healed:
        done = ", ".join(f"{rel} ({n} hook command(s))" for rel, n in report.healed.items())
        lines.append(
            f"Repaired dead plugin-cache refs left by a plugin update: {done}. "
            "The hooks run again in this same session; no restart is needed (restart only if a "
            "hook still fails). The file now differs from git — commit it or re-render."
        )
    if report.unhealable:
        lines.append(
            "Not repaired: "
            + ", ".join(report.unhealable)
            + ". Run /hm:make --update to re-render."
        )
    lines.append("Tell the user what was repaired.")
    return "\n".join(lines)
