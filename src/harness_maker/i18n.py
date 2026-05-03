"""Locale resolution and message lookup for user-facing strings."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml

from harness_maker.i18n_messages import MESSAGES
from harness_maker.models import Locale  # re-export for backward compat

__all__ = ["Locale", "resolve_locale", "t"]


def resolve_locale(project_dir: Path) -> Locale | None:
    """Read ``.claude/harness.yaml`` locale; return None if unset/missing/invalid."""
    yaml_path = project_dir / ".claude" / "harness.yaml"
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(raw, dict):
        return None
    data = cast(dict[str, object], raw)
    locale_str = data.get("locale")
    if not isinstance(locale_str, str):
        return None
    try:
        return Locale(locale_str)
    except ValueError:
        return None


def t(key: str, locale: Locale, **variables: object) -> str:
    """Look up ``key`` for ``locale`` and substitute ``variables`` via str.format."""
    catalog = MESSAGES.get(locale.value)
    if catalog is None:
        raise KeyError(f"unknown locale: {locale!r}")
    template = catalog.get(key)
    if template is None:
        raise KeyError(f"missing message key {key!r} for locale {locale.value!r}")
    return template.format(**variables) if variables else template.format()
