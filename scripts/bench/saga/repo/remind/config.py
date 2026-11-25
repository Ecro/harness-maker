"""Settings from remind.cfg (INI), looked up in the current directory, then the home directory.

    [remind]
    file = ~/reminders.json

The REMIND_FILE environment variable overrides `file`.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

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
