"""PLAN-layer3-per-session-ownership Phase 2 / ADR-005 — producer render gate.

`post-commit-pop`'s safety is producer-gated: it pops any ref whose uuid is in the
supplied set, so the templates MUST source `HM_OWNED_SESSION_UUIDS` from the
per-session slug crumb (`owned-crumb-read`), never from the all-markers `owned-uuids`.
This gate fails if any rendered command re-introduces the vulnerable source — the
contamination would return for that shipped harness.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker import wrapup_land
from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_OWNED_LINE = re.compile(r"HM_OWNED_SESSION_UUIDS=.*?(?:\n|$)")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("rendered-owned-gate")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    render(
        synthesize(p, interview(p, autoloop_mode=True)),
        out,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return out


def _cmd(rendered: Path, name: str) -> str:
    return (rendered / "commands" / "hm" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["execute.md", "wrapup.md"])
def test_owned_session_uuids_sources_crumb_not_owned_uuids(rendered: Path, name: str) -> None:
    text = _cmd(rendered, name)
    owned_lines = _OWNED_LINE.findall(text)
    if not owned_lines:
        # `wrapup.md` stopped setting the env var when Steps 6→7.6 collapsed into
        # `hm wrapup_land` (PLAN-workflow-step-audit Phase 2). The ownership set is now
        # derived inside that module, so the guarded property MOVED — it did not go away,
        # and this gate follows it rather than being relaxed. `test_wrapup_land_derives_…`
        # below is the assertion that now carries it.
        assert "hm wrapup_land" in text, (
            f"{name} has no HM_OWNED_SESSION_UUIDS assignment and does not delegate to "
            "wrapup_land — the ownership source is unaccounted for"
        )
        return
    for line in owned_lines:
        assert "owned-crumb-read" in line, (
            f"{name}: HM_OWNED_SESSION_UUIDS must source from owned-crumb-read "
            f"(per-session), got: {line!r}"
        )
        assert "owned-uuids" not in line, (
            f"{name}: HM_OWNED_SESSION_UUIDS must NOT source from the all-markers "
            f"owned-uuids (ADR-005 contamination guard), got: {line!r}"
        )


def test_wrapup_land_derives_the_ownership_set_from_the_crumb_not_all_markers() -> None:
    """The template half of this gate moved into Python — so the gate moves with it.

    `wrapup_land` is now the only wrapup-side caller of `post_commit_pop`. If it sourced
    `_owned_session_uuids` (the all-markers reader) instead of `_owned_crumb_read`, the
    3×-recurring cross-session contamination would be back with every render still green,
    because no rendered command would mention `owned-uuids` at all.
    """
    src = Path(wrapup_land.__file__).read_text(encoding="utf-8")
    assert "_owned_crumb_read(base, args.slug)" in src
    assert "_owned_session_uuids" not in src, (
        "wrapup_land must not source the all-markers ownership set (ADR-005 guard)"
    )


def test_execute_writes_owned_crumb_at_finalize(rendered: Path) -> None:
    """The producer side: execute records the owned uuid into the slug crumb so a
    standalone/recovered wrapup can read it (ADR-001)."""
    assert "owned-crumb-add" in _cmd(rendered, "execute.md"), (
        "execute.md must record the owned uuid via owned-crumb-add after finalize"
    )


def test_no_envless_post_commit_pop_in_any_producer(rendered: Path) -> None:
    """REVIEW P2: EVERY rendered producer path (commands AND skills) that calls
    post-commit-pop must source HM_OWNED_SESSION_UUIDS — an env-less invocation
    after the guard change skips uuid'd refs and strands the owner's own stash."""
    targets = [
        rendered / "commands" / "hm" / "execute.md",
        rendered / "commands" / "hm" / "wrapup.md",
        rendered / "skills" / "worktree-isolator" / "SKILL.md",
    ]
    for t in targets:
        if not t.exists():
            continue
        for line in t.read_text(encoding="utf-8").splitlines():
            # Only actual CLI invocations (`worktree post-commit-pop`), not prose.
            if "worktree post-commit-pop" in line and "HM_OWNED_SESSION_UUIDS" not in line:
                raise AssertionError(
                    f"{t.name}: post-commit-pop invoked without HM_OWNED_SESSION_UUIDS "
                    f"(env-less → strands owner): {line!r}"
                )
