"""Settings from remind.cfg (INI), looked up in the home directory, then the current directory.

    [remind]
    file = ~/reminders.json
    tz = Europe/Berlin

The REMIND_FILE environment variable overrides `file`. Without `tz`, times typed in are UTC and
times shown are in the machine's local zone.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_FILE = "~/reminders.json"


def _config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read([Path.home() / "remind.cfg", Path.cwd() / "remind.cfg"], encoding="utf-8")
    return parser


def save_file() -> Path:
    env = os.environ.get("REMIND_FILE")
    if env:
        return Path(env).expanduser()
    return Path(_config().get("remind", "file", fallback=DEFAULT_FILE)).expanduser()


def zone() -> ZoneInfo | None:
    name = _config().get("remind", "tz", fallback="").strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown time zone: {name}") from exc
