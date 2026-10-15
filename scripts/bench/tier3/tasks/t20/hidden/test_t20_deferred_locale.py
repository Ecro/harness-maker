"""Hidden tests for t20: session 2 finishes the long style with the rules session 1 deferred."""

import pytest
from timeparse import format_duration


def test_english_long_style() -> None:
    """Today: `style="long"` for English: each non-zero unit as count, space and name, singular
    for 1 and plural otherwise, joined by `", "`; zero is `"0 seconds"`; other styles raise
    ValueError.

    Source: session 1
    """
    for lang in ((), ("en",)):
        kwargs = {"lang": lang[0]} if lang else {}
        assert format_duration(5400, style="long", **kwargs) == "1 hour, 30 minutes"
        assert format_duration(90061, style="long", **kwargs) == "1 day, 1 hour, 1 minute, 1 second"
        assert format_duration(7200, style="long", **kwargs) == "2 hours"
        assert format_duration(0, style="long", **kwargs) == "0 seconds"


def test_other_styles_raise() -> None:
    """Today: `style="long"` for English: each non-zero unit as count, space and name, singular
    for 1 and plural otherwise, joined by `", "`; zero is `"0 seconds"`; other styles raise
    ValueError.

    Source: session 1
    """
    for style in ("short", "LONG", ""):
        with pytest.raises(ValueError):
            format_duration(5400, style=style)


def test_korean_uses_its_own_joiner() -> None:
    """Next session, after Dana lands `timeparse/locale.py`, the long style takes `lang`,
    defaulting to `en`: names come from `locale.unit_name(unit, count, lang)`, the joiner is
    `", "` for `en` and `" "` for `ko`, zero follows the same rule, and an unknown `lang` raises
    ValueError before anything is formatted.

    Source: session 1
    """
    assert format_duration(5400, style="long", lang="ko") == "1시간 30분"
    assert format_duration(90061, style="long", lang="ko") == "1일 1시간 1분 1초"
    assert format_duration(7200, style="long", lang="ko") == "2시간"


def test_zero_follows_the_same_rule_in_korean() -> None:
    """Next session, after Dana lands `timeparse/locale.py`, the long style takes `lang`,
    defaulting to `en`: names come from `locale.unit_name(unit, count, lang)`, the joiner is
    `", "` for `en` and `" "` for `ko`, zero follows the same rule, and an unknown `lang` raises
    ValueError before anything is formatted.

    Source: session 1
    """
    assert format_duration(0, style="long", lang="ko") == "0초"


def test_an_unknown_lang_raises_value_error() -> None:
    """Next session, after Dana lands `timeparse/locale.py`, the long style takes `lang`,
    defaulting to `en`: names come from `locale.unit_name(unit, count, lang)`, the joiner is
    `", "` for `en` and `" "` for `ko`, zero follows the same rule, and an unknown `lang` raises
    ValueError before anything is formatted.

    Source: session 1
    """
    for seconds in (5400, 0):
        with pytest.raises(ValueError):
            format_duration(seconds, style="long", lang="xx")


def test_the_compact_default_is_unchanged() -> None:
    """The compact output of `format_duration` (`1d1h1m1s`, `0s`) is a stable wire format: the
    scheduler stores `schedule.normalize` results and `config.save` writes it into config files
    that other tools read back, so the default output stays exactly as it is.

    Source: docs/DECISIONS.md
    """
    assert format_duration(5400) == "1h30m"
    assert format_duration(0) == "0s"
    assert format_duration(90061) == "1d1h1m1s"
