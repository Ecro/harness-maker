"""Unit names for the long output style, per language.

`unit_name(unit, count, lang)` returns a count with its unit's name in `lang`:
unit_name("h", 2, "en") -> "2 hours", unit_name("h", 1, "en") -> "1 hour",
unit_name("h", 2, "ko") -> "2시간".
"""

from __future__ import annotations

# lang -> unit letter -> (singular, plural); Korean has one form.
NAMES: dict[str, dict[str, tuple[str, str]]] = {
    "en": {
        "d": ("day", "days"),
        "h": ("hour", "hours"),
        "m": ("minute", "minutes"),
        "s": ("second", "seconds"),
    },
    "ko": {"d": ("일", "일"), "h": ("시간", "시간"), "m": ("분", "분"), "s": ("초", "초")},
}
# How a count and a name are written together in each language.
_PHRASE = {"en": "{count} {name}", "ko": "{count}{name}"}


def unit_name(unit: str, count: int, lang: str) -> str:
    """Return `count` with the name of `unit` in `lang`, in that language's number form."""
    singular, plural = NAMES[lang][unit]
    return _PHRASE[lang].format(count=count, name=singular if count == 1 else plural)
