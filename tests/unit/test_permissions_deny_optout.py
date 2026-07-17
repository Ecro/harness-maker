"""Permissions deny-list opt-out (user request 2026-05-31).

`rm`-like commands blocked by default in the main-session settings.json is too
inefficient for solo work. Default is now an EMPTY deny (solo-friendly); the
full destructive-pattern baseline is opt-in via harness.yaml
`permissions.deny_dangerous: true`. readiness.py's two deny signals must NOT
penalize the deliberate opt-out, but MUST enforce when opted in.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.models import HarnessConfig
from harness_maker.readiness import _dim_guardrails
from harness_maker.render import _make_env

SETTINGS_TEMPLATES = ("settings/Side.json.j2", "settings/Production.json.j2")


def _render_deny(template: str, deny_dangerous: bool) -> list[str]:
    cfg = HarnessConfig(permissions={"deny_dangerous": deny_dangerous}).model_dump(mode="json")
    # `harness_maker_src_path` became required when the settings templates gained
    # the `hooks` key (PLAN-permission-deny-and-hooks-wiring Phase 1) — the env
    # uses StrictUndefined, so omitting it raises rather than rendering empty.
    # Production always supplies it (synthesize.py's FileEntry context).
    out = (
        _make_env()
        .get_template(template)
        .render(preset="Side", config=cfg, harness_maker_src_path="/fake/src/path")
    )
    return list(json.loads(out)["permissions"]["deny"])


def test_deny_empty_by_default() -> None:
    for tpl in SETTINGS_TEMPLATES:
        assert _render_deny(tpl, False) == [], f"{tpl}: default deny must be empty (solo opt-out)"


def test_deny_full_baseline_when_opted_in() -> None:
    for tpl in SETTINGS_TEMPLATES:
        deny = _render_deny(tpl, True)
        assert "Bash(rm:*)" in deny
        assert "Bash(curl * | sh)" in deny
        assert any("/etc" in d for d in deny)
        assert any(".ssh" in d for d in deny)


def test_backcompat_old_harness_yaml_without_permissions_key() -> None:
    """Old harness.yaml lacking the permissions key parses → opted-out default."""
    cfg = HarnessConfig()
    assert cfg.permissions.deny_dangerous is False
    cfg2 = HarnessConfig.model_validate({"locale": "en"})
    assert cfg2.permissions.deny_dangerous is False


def test_deny_dangerous_round_trips_through_synthesize(tmp_path: Path) -> None:
    """REVIEW P1: a user's `permissions.deny_dangerous: true` must survive the
    real re-render path (load harness.yaml → answers_from_harness_yaml →
    synthesize), not just direct HarnessConfig construction. Before the fix the
    flag was dropped at InterviewAnswers and synthesize, so settings.json always
    rendered an empty deny regardless of harness.yaml."""
    from harness_maker.interview import answers_from_harness_yaml
    from harness_maker.profile import profile
    from harness_maker.synthesize import synthesize

    hy = tmp_path / "harness.yaml"
    hy.write_text("preset: Side\npermissions:\n  deny_dangerous: true\n")
    answers = answers_from_harness_yaml(hy)
    assert answers is not None
    # catches the answers_from_harness_yaml drop
    assert answers.permissions.deny_dangerous is True
    # catches the synthesize HarnessConfig-kwarg omission
    bp = synthesize(profile(Path("tests/fixtures/side-python-cli")), answers)
    assert bp.config.permissions.deny_dangerous is True


def _write_claude(tmp: Path, deny: list[str], harness_yaml_body: str) -> Path:
    claude = tmp / ".claude"
    claude.mkdir(parents=True)
    (claude / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [], "deny": deny}, "preset": "Side"})
    )
    (claude / "harness.yaml").write_text(harness_yaml_body)
    return tmp


def test_readiness_deny_signals_pass_when_opted_out(tmp_path: Path) -> None:
    """Empty deny + opted-out harness.yaml → both deny signals PASS, no action."""
    proj = _write_claude(tmp_path, deny=[], harness_yaml_body="preset: Side\n")
    by_id = {s.id: s for s in _dim_guardrails(proj).signals}
    assert by_id["permissions_deny_present"].passed is True
    assert by_id["deny_covers_dangerous"].passed is True
    assert by_id["permissions_deny_present"].action is None
    assert by_id["deny_covers_dangerous"].action is None


def test_readiness_deny_signals_enforce_when_opted_in(tmp_path: Path) -> None:
    """Opted IN but deny empty → both deny signals FAIL (asked-for guard missing)."""
    proj = _write_claude(
        tmp_path, deny=[], harness_yaml_body="permissions:\n  deny_dangerous: true\n"
    )
    by_id = {s.id: s for s in _dim_guardrails(proj).signals}
    assert by_id["permissions_deny_present"].passed is False
    assert by_id["deny_covers_dangerous"].passed is False
    assert by_id["permissions_deny_present"].action is not None
