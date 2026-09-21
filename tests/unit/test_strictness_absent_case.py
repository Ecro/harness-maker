"""AC-003 (SPEC-dev-mode-removal): an absent key resolves from the preset, with one named exception.

`models.py` used to document a deliberate three-way split for the absent case: bare
construction said strict, the reverse mapper and the advisory gates said relaxed, and
`spec_need`'s verify oracle failed closed. This file pins the replacement: every reader
derives from the preset, except the one exempt member, which keeps failing closed.

The exception is exercised through `spec_need waiver-check` — the public command
`/hm:verify` Check 6 reads — in a root with no waiver on disk, so its exit code is decided by
nothing but the relax rule: 0 means relaxed, 1 means enforced.

Phase A.4 — justified pass (1 of 12 items in this file):
  `test_ac_003_oracle_enforces_on_an_unreadable_config` passes before the implementation — an
  unreadable config enforces today. It is a backward-compat negative: it goes RED if the new
  oracle is implemented through the preset-deriving resolver (an unreadable file loads as `{}`,
  whose model-default preset is Side, which derives `warn`). RED positive sibling that forces
  the new relax path into existence: `test_ac_003_oracle_gate_stays_fail_closed[side-warn]`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker.models import Preset

# Hypothesis profile contract (spec-tetrad ADR-002): `ci` = reproducible gate,
# `dev` = broader local bug-finding. Select via HYPOTHESIS_PROFILE (default ci).
settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=200, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

_PRESET_DEFAULT = {Preset.PRODUCTION.value: "block", Preset.SIDE.value: "warn"}

# Arbitrary sibling keys a real `spec:` block may carry, never `strictness` itself.
_spec_siblings = st.dictionaries(
    st.text(min_size=1, max_size=12).filter(lambda k: k != "strictness"),
    st.one_of(st.text(max_size=12), st.integers(), st.booleans()),
    max_size=4,
)
_presets = st.sampled_from([p.value for p in Preset])
_malformed = st.one_of(
    st.text(max_size=12).filter(lambda s: s not in {"block", "warn"}),
    st.integers(),
    st.booleans(),
    st.none(),
    st.lists(st.text(max_size=4), max_size=2),
)


@given(preset=_presets, spec=_spec_siblings)
def test_ac_003_absent_key_resolves_from_preset(preset: str, spec: dict[str, Any]) -> None:
    from harness_maker.strictness import resolve_strictness

    assert resolve_strictness({"preset": preset, "spec": spec}) == _PRESET_DEFAULT[preset]
    # An absent `spec` block is the same absence, one level up.
    assert resolve_strictness({"preset": preset}) == _PRESET_DEFAULT[preset]


def test_ac_003_absent_key_resolves_from_preset_on_the_model() -> None:
    """The typed config and the raw mapping must agree — two entry shapes, one rule."""
    from harness_maker.models import HarnessConfig
    from harness_maker.strictness import resolve_strictness

    for preset in Preset:
        cfg = HarnessConfig(preset=preset)
        assert resolve_strictness(cfg) == _PRESET_DEFAULT[preset.value]


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(preset=_presets, value=_malformed)
def test_ac_003_malformed_strictness_fails_closed(
    preset: str, value: Any, caplog: pytest.LogCaptureFixture
) -> None:
    from harness_maker.strictness import resolve_strictness

    caplog.clear()
    caplog.set_level(logging.WARNING)
    # `block` even for Side: the malformed value was trying to override the preset default,
    # so falling through to that default would silently discard the user's intent.
    assert resolve_strictness({"preset": preset, "spec": {"strictness": value}}) == "block"
    assert any(repr(value) in r.getMessage() for r in caplog.records), (
        "the refusal must name the value it refused"
    )


def test_ac_003_a_config_with_no_preset_uses_the_model_default() -> None:
    """`{}` is what an unreadable or empty harness.yaml loads as. It must resolve the way
    `HarnessConfig()` would — Side, hence `warn` — not the other preset's value."""
    from harness_maker.models import HarnessConfig
    from harness_maker.strictness import resolve_strictness

    assert HarnessConfig().preset is Preset.SIDE  # sanity: this is the default being tracked
    assert resolve_strictness({}) == "warn"
    assert resolve_strictness({"spec": {}}) == "warn"


def test_ac_003_an_unrecognised_preset_fails_closed(caplog: pytest.LogCaptureFixture) -> None:
    """A preset outside the enum cannot pick a default, so it takes the strict one and says so —
    the same fail-closed rule the malformed-strictness case follows."""
    from harness_maker.strictness import resolve_strictness

    caplog.set_level(logging.WARNING)
    assert resolve_strictness({"preset": "Prod"}) == "block"
    assert any("Prod" in r.getMessage() for r in caplog.records)


def _root(tmp_path: Path, body: dict[str, Any]) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "harness.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")
    return tmp_path


def _oracle_relaxes(root: Path) -> bool:
    from harness_maker.spec_need import main

    rc = main(["waiver-check", "--root", str(root), "--slug", "some-task"])
    assert rc in (0, 1)
    return rc == 0


@pytest.mark.parametrize(
    ("body", "relaxes"),
    [
        # The divergence this exception exists for: the general rule says Side + absent → warn,
        # the oracle still enforces.
        ({"preset": "Side"}, False),
        ({"preset": "Production"}, False),
        ({"preset": "Side", "spec": {"strictness": "warn"}}, True),
        ({"preset": "Production", "spec": {"strictness": "warn"}}, True),
        ({"preset": "Side", "spec": {"strictness": "block"}}, False),
        ({"preset": "Side", "spec": {"strictness": "Warn"}}, False),
        # A legacy harness reaches the oracle through the loader's translation.
        ({"preset": "Production", "dev_mode": "task-driven"}, True),
    ],
    ids=[
        "side-absent",
        "prod-absent",
        "side-warn",
        "prod-warn",
        "side-block",
        "malformed",
        "legacy-task-driven",
    ],
)
def test_ac_003_oracle_gate_stays_fail_closed(
    body: dict[str, Any], relaxes: bool, tmp_path: Path
) -> None:
    from harness_maker.strictness import STRICTNESS_EXEMPT, resolve_strictness

    assert len(STRICTNESS_EXEMPT) == 1
    assert _oracle_relaxes(_root(tmp_path, body)) is relaxes
    if "dev_mode" not in body and "spec" not in body:
        # Pin the divergence explicitly: the resolver and the oracle disagree on purpose.
        assert (resolve_strictness(body) == "warn") is (body["preset"] == "Side")


def test_ac_003_oracle_enforces_on_an_unreadable_config(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "harness.yaml").write_text("spec: [unclosed\n", encoding="utf-8")
    assert _oracle_relaxes(tmp_path) is False
