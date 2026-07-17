"""`deny_covers_dangerous` must score the deny list the template actually ships.

The pre-0.40 failure: `_DANGEROUS_DENY_PATTERNS` scored `Write(/etc` and `curl`,
both unenforceable, so the signal reported "4/4 dangerous patterns covered" on a
deny list that stopped nothing. The health score and reality had no connection.

Two properties keep that from recurring:
  1. every scored pattern is a prefix of a rule the template renders (lockstep),
  2. every scored pattern names a MATCHABLE rule shape (not dead syntax).

Both are asserted against the real template output and the real signal, not
against a hand-copied list — a copy would drift with the thing it guards.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from harness_maker.models import HarnessConfig
from harness_maker.permission_syntax import is_matchable_rule
from harness_maker.readiness import (
    _DANGEROUS_DENY_PATTERNS,
    _DENY_COVERAGE_MIN,
    _dim_guardrails,
)
from harness_maker.render import _make_env

SETTINGS_TEMPLATES = ("settings/Side.json.j2", "settings/Production.json.j2")


def _render_deny(template: str, deny_dangerous: bool) -> list[str]:
    cfg = HarnessConfig(permissions={"deny_dangerous": deny_dangerous}).model_dump(mode="json")
    out = (
        _make_env()
        .get_template(template)
        .render(preset="Side", config=cfg, harness_maker_src_path="/fake/src/path")
    )
    return list(json.loads(out)["permissions"]["deny"])


def _signals(root: Path) -> dict[str, object]:
    return {s.id: s for s in _dim_guardrails(root).signals}


def _project(root: Path, *, deny_dangerous: bool, deny: list[str]) -> None:
    claude = root / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        yaml.safe_dump({"permissions": {"deny_dangerous": deny_dangerous}})
    )
    (claude / "settings.json").write_text(json.dumps({"permissions": {"allow": [], "deny": deny}}))


# --- lockstep: the two lists cannot drift apart silently -------------------


def test_every_scored_pattern_matches_a_rule_the_template_ships() -> None:
    """Makes readiness.py's 'kept in lockstep' comment true rather than aspirational."""
    for tpl in SETTINGS_TEMPLATES:
        deny_text = " ".join(_render_deny(tpl, True)).lower()
        for pattern in _DANGEROUS_DENY_PATTERNS:
            assert pattern.lower() in deny_text, (
                f"{tpl} ships no rule containing {pattern!r} — readiness scores a "
                f"pattern the template no longer renders, so the signal is unreachable"
            )


def test_every_scored_pattern_names_an_enforceable_rule_shape() -> None:
    """The pre-0.40 bug: `Write(/etc` and `curl` scored rules that never matched."""
    for tpl in SETTINGS_TEMPLATES:
        for rule in _render_deny(tpl, True):
            assert is_matchable_rule(rule), f"{tpl} scores unenforceable rule {rule!r}"


def test_coverage_threshold_cannot_become_all_required() -> None:
    """A hardcoded `>= 3` silently means 'all' once the list shrinks to 3."""
    assert len(_DANGEROUS_DENY_PATTERNS) > _DENY_COVERAGE_MIN
    assert _DENY_COVERAGE_MIN >= 1


# --- the signal, driven end-to-end ----------------------------------------


def test_opted_in_with_the_shipped_deny_list_passes(tmp_path: Path) -> None:
    """The path with no prior coverage: opted IN and deny non-empty."""
    _project(tmp_path, deny_dangerous=True, deny=_render_deny("settings/Side.json.j2", True))
    sig = _signals(tmp_path)["deny_covers_dangerous"]
    assert sig.passed is True, sig.evidence  # type: ignore[attr-defined]


def test_opted_in_with_the_old_dead_rules_now_fails(tmp_path: Path) -> None:
    """The regression that shipped: this exact list scored 4/4 before 0.40."""
    _project(
        tmp_path,
        deny_dangerous=True,
        deny=["Bash(rm:*)", "Bash(curl * | sh)", "Write(/etc/**)", "Write(~/.ssh/**)"],
    )
    sig = _signals(tmp_path)["deny_covers_dangerous"]
    assert sig.passed is False, (  # type: ignore[attr-defined]
        "the pre-0.40 deny list enforced only Bash(rm:*); health must not call it covered"
    )


def test_opted_out_is_not_a_finding(tmp_path: Path) -> None:
    """A deliberate config choice is not a defect (CLAUDE.md §보안/권한)."""
    _project(tmp_path, deny_dangerous=False, deny=[])
    sig = _signals(tmp_path)["deny_covers_dangerous"]
    assert sig.passed is True, sig.evidence  # type: ignore[attr-defined]
