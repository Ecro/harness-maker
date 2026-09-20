"""AC-002 — the SPEC-need write preserves what is there and guarantees the key afterwards.

`verify.md.j2` Check 6 treats an ABSENT `spec_need_verdict` as `PASS (N-A)`. Both ways of
getting this wrong are therefore silent: a writer that no-ops leaves the gate permanently
green, and one that clobbers a verdict the DRI already recorded replaces a real decision
without any error. Neither shows up as a failure anywhere downstream.

**The unit is the PAIR.** Check 6 reads verdict and target together to pick which SPEC the
verdict applies to, so this property was once wrong in a way that looked right: it generated
the two prior keys INDEPENDENTLY and asserted the mix-and-match outcome as correct, which is
the `assertion-invariant-over-named-dimension` shape — it held for every value of each key
while being silent about the one dimension that matters, whether the two belong to the same
judgment. A preserved verdict beside a freshly-supplied target points an old decision at a
new subject.

The oracle is metamorphic, which is why it is a property and not an example: hold the writer
fixed and vary the *prior* frontmatter over arbitrary states. Preservation-and-presence must
hold for every one of them, so an implementation cannot satisfy it by being read — only by
actually preserving. SPEC AC-002, IRR-004.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harness_maker import command_registry, spec_need

_VERDICTS = list(spec_need._VALID_VERDICTS)

# Frontmatter keys a real PLAN carries, plus the two under test.
_OTHER_KEYS = st.sampled_from(
    ["type", "task_slug", "status", "created", "summary", "adrs", "interview_rounds"]
)
_SAFE_VALUE = (
    st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_ "),
        min_size=1,
        max_size=24,
    )
    .map(str.strip)
    .filter(lambda s: s and "#" not in s)
)
# `_validate_slug` admits [A-Za-z0-9._-]+ only, so the strategy generates exactly that — the
# rejection path belongs to the CLI's `_cli_validate_slug`, not to this property.
_SLUG = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=20)


def _write_plan(directory: Path, prior: dict[str, str]) -> Path:
    body = "".join(f"{k}: {v}\n" for k, v in prior.items())
    path = directory / "PLAN-probe.md"
    path.write_text(f"---\n{body}---\n\n# PLAN\n\nbody text\n", encoding="utf-8")
    return path


@given(
    prior=st.dictionaries(_OTHER_KEYS, _SAFE_VALUE, max_size=5),
    existing_verdict=st.one_of(st.none(), st.sampled_from(_VERDICTS)),
    existing_target=st.one_of(st.none(), _SLUG),
    verdict=st.sampled_from(_VERDICTS),
    target=_SLUG,
)
def test_ac_002_upsert_preserves_and_guarantees_presence(
    prior: dict[str, str],
    existing_verdict: str | None,
    existing_target: str | None,
    verdict: str,
    target: str,
) -> None:
    """Over ARBITRARY prior frontmatter: the key is present after, and never overwritten."""
    seeded = dict(prior)
    if existing_verdict is not None:
        seeded["spec_need_verdict"] = existing_verdict
    if existing_target is not None:
        seeded["spec_need_target"] = existing_target

    with tempfile.TemporaryDirectory() as tmp:
        plan = _write_plan(Path(tmp), seeded)
        before = plan.read_text(encoding="utf-8")

        result = spec_need.frontmatter_upsert(plan, verdict, target, root=Path(tmp))
        after = plan.read_text(encoding="utf-8")
        fm = _frontmatter(after)

        # Presence: the absent case is the whole reason Check 6 can fail open.
        assert "spec_need_verdict" in fm
        assert "spec_need_target" in fm

        # Preservation, and its unit. The verdict IS the decision, so it alone decides whether
        # one exists; the target only names the subject.
        if existing_verdict is not None:
            assert fm["spec_need_verdict"] == existing_verdict
            assert result["preserved_verdict"] is True
            # Target follows the verdict it belongs to. An absent one is repaired, loudly.
            if existing_target is not None:
                assert fm["spec_need_target"] == existing_target
                assert result["repaired"] is False
            else:
                assert fm["spec_need_target"] == target
                assert result["repaired"] is True
        else:
            # No recorded decision. Both keys come from THIS judgment — an orphan target is
            # replaced rather than paired with a verdict that never saw it.
            assert fm["spec_need_verdict"] == verdict
            assert fm["spec_need_target"] == target
            assert result["preserved_verdict"] is False
            assert result["preserved_target"] is False

        # Nothing else moved: every prior line survives verbatim.
        for line in before.splitlines():
            if not line.startswith(("spec_need_verdict:", "spec_need_target:")):
                assert line in after.splitlines()

        # The returned values are what is ON DISK, not what this call intended — the only way a
        # caller that lost a race can be told the truth about it.
        assert result["spec_need_verdict"] == fm["spec_need_verdict"]
        assert result["spec_need_target"] == fm["spec_need_target"]


@given(verdict=st.sampled_from(_VERDICTS), target=_SLUG)
def test_ac_002_upsert_is_idempotent(verdict: str, target: str) -> None:
    """A second call writes nothing — the first call's value is now the pre-existing one."""
    with tempfile.TemporaryDirectory() as tmp:
        plan = _write_plan(Path(tmp), {"type": "plan", "task_slug": "probe"})

        first = spec_need.frontmatter_upsert(plan, verdict, target, root=Path(tmp))
        snapshot = plan.read_text(encoding="utf-8")
        second = spec_need.frontmatter_upsert(plan, "not-evaluated", "other-slug", root=Path(tmp))

        assert first["wrote"] is True
        assert second["wrote"] is False
        assert plan.read_text(encoding="utf-8") == snapshot
        assert second["spec_need_verdict"] == verdict


def test_ac_002_verb_is_registered() -> None:
    """An unregistered subcommand is refused by the guard before it ever runs."""
    spec = command_registry.MODULES["spec_need"]
    assert "frontmatter-upsert" in spec.subcommands, (
        "frontmatter-upsert is not in spec_need's registry entry, so command_registry.guard "
        "rejects it and the rendered execute recipe silently fails"
    )


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("no frontmatter at all\n", "frontmatter fence"),
        ("---\ntype: plan\n", "unterminated"),
    ],
)
def test_ac_002_malformed_plan_raises_rather_than_silently_skipping(
    content: str, fragment: str
) -> None:
    """A PLAN without usable frontmatter is a loud error, never a quiet no-op."""
    with tempfile.TemporaryDirectory() as tmp:
        plan = Path(tmp) / "PLAN-broken.md"
        plan.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError, match=fragment):
            spec_need.frontmatter_upsert(plan, "add", "probe", root=Path(tmp))


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    assert lines[0] == "---"
    close = lines.index("---", 1)
    out: dict[str, str] = {}
    for line in lines[1:close]:
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def test_ac_002_an_orphan_target_never_survives_into_a_fresh_decision() -> None:
    """The mix this property used to bless, as a named example.

    A PLAN carrying `spec_need_target` with no verdict beside it holds no decision. Keeping that
    target and pairing it with a newly-judged verdict is how Check 6 ends up evaluating a fresh
    verdict against a stale SPEC.
    """
    with tempfile.TemporaryDirectory() as tmp:
        plan = _write_plan(Path(tmp), {"type": "plan", "spec_need_target": "stale-slug"})
        result = spec_need.frontmatter_upsert(plan, "add", "fresh-slug", root=Path(tmp))
        fm = _frontmatter(plan.read_text(encoding="utf-8"))

        assert fm["spec_need_target"] == "fresh-slug"
        assert fm["spec_need_verdict"] == "add"
        assert result["preserved_target"] is False
        assert plan.read_text(encoding="utf-8").count("spec_need_target:") == 1


def test_ac_002_a_plan_outside_the_root_is_refused() -> None:
    """`--root` is required, so the confinement check cannot be skipped by omitting it.

    Every other path-bearing verb in `spec_need` derives its path from a `_validate_slug`-checked
    component under `root`; this one takes a caller-supplied path, and the rendered recipe builds
    it from a model-filled slug. A guard with a default would be the absent-case black hole
    (count:8) — off for exactly the caller that forgot to turn it on.
    """
    with tempfile.TemporaryDirectory() as outer, tempfile.TemporaryDirectory() as root:
        plan = _write_plan(Path(outer), {"type": "plan"})
        with pytest.raises(ValueError, match="outside the project root"):
            spec_need.frontmatter_upsert(plan, "add", "probe", root=Path(root))
        assert "spec_need_verdict" not in plan.read_text(encoding="utf-8")


def test_ac_002_root_is_required_at_the_cli_too() -> None:
    """A recipe that forgets `--root` must fail loudly, not write unconfined."""
    import argparse

    with tempfile.TemporaryDirectory() as tmp:
        plan = _write_plan(Path(tmp), {"type": "plan"})
        with pytest.raises(SystemExit):
            spec_need.main(
                ["frontmatter-upsert", "--plan", str(plan), "--verdict", "add", "--target", "p"]
            )
        assert argparse  # the failure above is argparse's, i.e. the argument is required
