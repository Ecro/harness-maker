"""Statusline — `python -m harness_maker.statusline` (per amendments §C/§D/§E/§I).

Reads JSON from stdin (Claude Code statusLine spec). Writes one-line summary to stdout:
    <project> | <preset> | 🪙<eff>% | 🎯<health> | 🔄<fresh>d

NEVER crash on missing files (eff=0, fresh=999, health=0).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from harness_maker.models import Preset
from harness_maker.readiness import compute_health


def _read_stdin_json() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_cwd(data: dict[str, Any]) -> Path:
    raw_workspace = data.get("workspace")
    workspace: dict[str, Any] = raw_workspace if isinstance(raw_workspace, dict) else {}
    candidate = workspace.get("current_dir") or data.get("cwd")
    if candidate:
        try:
            return Path(candidate)
        except (TypeError, ValueError):
            pass
    return Path.cwd()


def _read_preset(claude_dir: Path) -> Preset:
    """Read preset from harness.yaml. Returns Preset.SIDE on any failure."""
    yml = claude_dir / "harness.yaml"
    try:
        text = yml.read_text(encoding="utf-8")
    except OSError:
        return Preset.SIDE
    # Strip leading YAML frontmatter doc separator if multi-doc
    docs: list[Any] = []
    try:
        docs = list(yaml.safe_load_all(text))
    except yaml.YAMLError:
        return Preset.SIDE
    for doc in docs:
        if isinstance(doc, dict) and "preset" in doc:
            try:
                return Preset(doc["preset"])
            except (ValueError, TypeError):
                return Preset.SIDE
    return Preset.SIDE


def _compute_eff(claude_dir: Path, window: int = 20) -> int:
    """cache_hit_pct from last N entries of metrics.jsonl. 0 if absent."""
    metrics = claude_dir / "observability" / "metrics.jsonl"
    try:
        lines = metrics.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    if not lines:
        return 0
    total = 0
    cached = 0
    for line in lines[-window:]:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        in_tok = int(entry.get("input_tokens", 0) or 0)
        cache_tok = int(entry.get("cache_read_tokens", 0) or 0)
        total += in_tok + cache_tok
        cached += cache_tok
    if total == 0:
        return 0
    return round(100 * cached / total)


def _compute_fresh(claude_dir: Path) -> int:
    """Days since newest mtime of refresh/raw-*.jsonl. 999 if absent."""
    refresh_dir = claude_dir / "observability" / "refresh"
    if not refresh_dir.is_dir():
        return 999
    files = list(refresh_dir.glob("raw-*.jsonl"))
    if not files:
        return 999
    newest = max(f.stat().st_mtime for f in files)
    return int((time.time() - newest) // 86400)


def _safe_compute_health(project_dir: Path, preset: Preset) -> int:
    try:
        return int(compute_health(project_dir, preset)["composite"])
    except Exception:  # noqa: BLE001 — never crash statusline
        return 0


def format_line(project: str, preset: Preset, eff: int, health: int, fresh: int) -> str:
    """Build the one-line statusline output."""
    return f"{project} | {preset.value} | 🪙{eff}% | 🎯{health} | 🔄{fresh}d"


def main() -> int:
    data = _read_stdin_json()
    cwd = _resolve_cwd(data)
    claude_dir = cwd / ".claude"
    project = cwd.name or "unknown"
    preset = _read_preset(claude_dir)
    eff = _compute_eff(claude_dir)
    fresh = _compute_fresh(claude_dir)
    health = _safe_compute_health(cwd, preset)
    print(format_line(project, preset, eff, health, fresh))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
