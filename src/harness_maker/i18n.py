"""Locale resolution and message lookup; English baseline with silent fallback."""

from __future__ import annotations

from pathlib import Path

import yaml

from harness_maker.i18n_messages import MESSAGES
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import Locale  # re-export for backward compat

__all__ = ["DEFAULT_LOCALE", "Locale", "resolve_locale", "t"]

DEFAULT_LOCALE = "en"


def resolve_locale(project_dir: Path) -> str:
    """Read ``.claude/harness.yaml`` locale tag; return English by default.

    Returns the raw string from yaml — any tag is accepted so user can request
    locales we don't yet have messages for. ``t()`` handles silent fallback.
    """
    yaml_path = project_dir / ".claude" / "harness.yaml"
    # Why load_harness_yaml (not yaml.safe_load): the rendered harness.yaml is a
    # multi-document stream (provenance frontmatter + body); a bare safe_load
    # raises ComposerError and silently degrades every non-English user to 'en'.
    try:
        data = load_harness_yaml(yaml_path)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return DEFAULT_LOCALE
    locale_str = data.get("locale")
    if not isinstance(locale_str, str) or not locale_str:
        return DEFAULT_LOCALE
    return locale_str


def t(key: str, locale: str | Locale, **variables: object) -> str:
    """Look up ``key`` for ``locale``; silent fallback to English.

    Why fallback in two stages: an unknown locale tag falls back to the English
    catalog wholesale; a known locale that simply lacks a key falls back per-key
    so partial translations don't crash the harness.
    """
    locale_str = locale.value if isinstance(locale, Locale) else locale
    catalog = MESSAGES.get(locale_str) or MESSAGES[DEFAULT_LOCALE]
    template = catalog.get(key) or MESSAGES[DEFAULT_LOCALE].get(key)
    if template is None:
        msg = f"missing message key {key!r}"
        raise KeyError(msg)
    return template.format(**variables) if variables else template
