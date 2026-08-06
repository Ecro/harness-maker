"""The fresh-install fast path in `commands/make.md`, as a machine-checked contract.

`commands/make.md` is prose an LLM executes. It has no execution surface, so a test can only
read its text — and this repo has shipped four silent-skip bugs in exactly that shape
(CLAUDE.md, "외부 소비자 정합성 확인"). ADR-006 of PLAN-onboarding-interview-ux is the
response: assert the BRANCH STRUCTURE, not the presence of substrings.

Two defects are pinned:

* The conditional second-opinion offer is unreachable unless §4.4's "Looks right" branch is
  split. Before this work that line read `Jump to Section 4.6 (Preview) with smart defaults.`
  — a question added anywhere after it is dead prose (codex `88bc5ee332adccd6`).
* The disclosure table must be complete over the axes the fast path sets WITHOUT asking. A
  set derived from the dispatch argv drops `worktree.enabled` and `autonomy.persistent`,
  because the dispatch block passes neither — and `worktree.enabled` decides whether every
  later `/hm:` stage runs in `.worktrees/<slug>/` (codex `363c74e68a0f5112`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_MAKE = _ROOT / "commands" / "make.md"


# The disclosure table's contents are an explicit ALLOWLIST, not a derivation. Deriving them
# from `HarnessConfig` fields would drag in `delivery_metrics`, `work_docs`,
# `interview.deep_gate`, `schema_version` — internals nobody wants in an onboarding summary.
# Completeness is enforced separately, by `test_every_harness_config_axis_is_classified`.
_DISCLOSED_AXES: frozenset[str] = frozenset(
    {
        "second_opinion",
        "autonomy",
        "worktree",
        "targets",
        "dev_mode",
        "ref_folders",
        "sibling_repos",
        "second_brain",
        "wrapup_docs",
        "permissions",
    }
)

# Axes the fast path DOES put on screen already (make.md §4.3's five existing lines).
_ASKED_OR_SHOWN_AXES: frozenset[str] = frozenset({"preset", "reviewers", "locale"})

# Everything else: internal machinery, not an onboarding decision. `consensus` and `caching`
# are here deliberately — ADR-003 makes them silently preset-defaulted, and disclosing an
# axis with zero runtime effect is noise, not transparency. If ADR-003's follow-up ever
# retires the keys, this is the line that moves.
_INTERNAL_AXES: frozenset[str] = frozenset(
    {
        "adaptive",
        "agent_models",
        "anti_rot",
        "autoloop",
        "caching",
        "consensus",
        "context_lint",
        "dashboard",
        "default_model",
        "delegation",
        "delivery_metrics",
        "economics",
        "execution",
        "feedback",
        "hooks",
        "interview",
        "mcp_servers",
        "memory",
        "models",
        "project",
        "schema_version",
        "security",
        "spec",
        "work_docs",
    }
)


@pytest.fixture(scope="module")
def make_md() -> str:
    return _MAKE.read_text(encoding="utf-8")


def _section(text: str, heading: str, until: str) -> str:
    start = text.index(heading)
    end = text.index(until, start)
    return text[start:end]


def test_the_make_command_is_present() -> None:
    """Non-vacuity: every arm below slices this file, so an absent file must fail loudly."""
    assert _MAKE.is_file(), _MAKE
    assert len(_MAKE.read_text(encoding="utf-8")) > 5_000


def test_detect_tools_is_invoked_beside_the_profile_scan(make_md: str) -> None:
    """§4.1 must gather tool signals, or nothing downstream can branch on them."""
    scan = _section(make_md, "#### 4.1 Run profile scan", "#### 4.3")
    assert "detect-tools" in scan, scan[-800:]
    assert "--json" in scan


def test_the_fast_path_has_two_explicit_branches(make_md: str) -> None:
    """The whole point of codex finding 88bc5ee3.

    "Looks right" must NOT be a single unconditional jump — one branch asks when a model CLI
    was detected, the other goes straight to dispatch.
    """
    branch = _section(make_md, '**"Looks right"**', '**"Adjust a few things"**')
    lowered = branch.lower()
    assert "detect" in lowered, branch
    # Both outcomes named, and the negative one reaches the preview with no question.
    assert re.search(r"no(?:thing)?\s+detect|not\s+detected|neither", lowered), branch
    assert "4.6" in branch, branch


def test_the_fast_path_asks_at_most_one_conditional_question(make_md: str) -> None:
    """ADR-002 caps the fast path at one question, and it belongs to second opinion."""
    branch = _section(make_md, '**"Looks right"**', '**"Adjust a few things"**')
    asks = re.findall(r"AskUserQuestion", branch)
    assert len(asks) <= 1, f"{len(asks)} questions in the fast path: {branch}"
    if asks:
        assert "second opinion" in branch.lower() or "second-opinion" in branch.lower()


def test_the_conditional_answer_reaches_the_dispatch_flag(make_md: str) -> None:
    """A question whose answer goes nowhere is worse than no question."""
    branch = _section(make_md, '**"Looks right"**', '**"Adjust a few things"**')
    assert "--second-opinion-models" in branch or "SECOND_OPINION_MODELS" in branch, branch


def test_the_fast_path_never_promises_a_question_free_install(make_md: str) -> None:
    """The option label said "install with these settings" (antigravity `e8398d0f`)."""
    options = _section(make_md, "> - **Looks right**", "> - **Full setup**")
    assert re.search(r"detect|second opinion|one question", options, re.I), options


def test_adjust_a_few_things_offers_second_opinion_and_autopilot(make_md: str) -> None:
    """The detection-NEGATIVE user's only in-`make` path.

    Before this work the multi-select listed neither, so a user who installed a CLI a week
    later had nowhere to go inside `make` at all.
    """
    branch = _section(make_md, '**"Adjust a few things"**', '**"Full setup"**')
    lowered = branch.lower()
    assert "second_opinion" in lowered or "second opinion" in lowered, branch
    assert "autonomy" in lowered or "autopilot" in lowered, branch


def test_the_disclosure_table_covers_every_allowlisted_axis(make_md: str) -> None:
    """P0-4. Each axis the fast path sets without asking must appear on screen."""
    summary = _section(make_md, "#### 4.3", "#### 4.4")
    missing = sorted(axis for axis in _DISCLOSED_AXES if axis not in summary)
    assert missing == [], (
        f"§4.3 does not disclose: {missing}. These are set without being asked, so a user "
        f"taking the fast path never learns they exist."
    )


def test_the_disclosure_table_includes_the_axes_dispatch_argv_cannot_carry(
    make_md: str,
) -> None:
    """Named arms for the two axes an argv-derived test would silently drop.

    `commands/make.md`'s dispatch block passes 14 flags and carries neither `--worktree` nor
    `--autonomy-persistent`; both are derived inside the CLI. A test that compared the table
    against argv would go green while omitting the axis that decides where every later stage
    writes its files.
    """
    dispatch = _section(make_md, "#### Fresh install", "### 6. Report")
    assert "--worktree" not in dispatch, (
        "dispatch now carries --worktree; this arm's premise changed — re-derive it "
        "rather than deleting it"
    )
    summary = _section(make_md, "#### 4.3", "#### 4.4")
    assert "worktree" in summary
    assert re.search(r"autonomy|autopilot", summary, re.I)


def test_the_disclosed_autonomy_value_is_the_one_a_fresh_install_actually_renders() -> None:
    """Presence is not truth — and the first version of this gate only checked presence.

    The row shipped saying `gated` / off while `AutonomyConfig()` defaults to `auto_safe`
    with `autopilot_persistent=True`, which a SessionStart hook then re-arms every session.
    A transparency table that is WRONG about the highest-consequence silent axis is worse
    than no table, and both reviewers caught what this file did not. So the assertion reads
    the model, not the prose: whatever the default becomes, the table has to say it.
    """
    from harness_maker.models import AutonomyConfig

    summary = _section(_MAKE.read_text(encoding="utf-8"), "#### 4.3", "#### 4.4")
    row = next(
        (ln for ln in summary.splitlines() if re.search(r"autonomy|autopilot", ln, re.I)),
        "",
    )
    assert row, summary

    default = AutonomyConfig()
    assert default.level in row, (
        f"the disclosure row does not state the real default level {default.level!r}: {row}"
    )
    # Persistence is a bool; require the row to name its state either way.
    persisted = re.search(r"persist", row, re.I)
    assert persisted, f"the row says nothing about persistence: {row}"
    if default.autopilot_persistent:
        assert not re.search(r"persistan?ce\s*/?\s*off|persistent\s*`?false", row, re.I), row


def test_every_harness_config_axis_is_classified() -> None:
    """The drift arm: completeness without deriving the table's contents.

    A new `HarnessConfig` field must be consciously placed as asked / disclosed / internal.
    Left unclassified it fails here, which is the only thing that stops the disclosure table
    from quietly falling behind the schema (R3).
    """
    from harness_maker.models import HarnessConfig

    classified = _DISCLOSED_AXES | _ASKED_OR_SHOWN_AXES | _INTERNAL_AXES
    unclassified = sorted(set(HarnessConfig.model_fields) - classified)
    assert unclassified == [], (
        f"unclassified harness.yaml axes: {unclassified}. Add each to _DISCLOSED_AXES "
        f"(shown in the fresh-install summary), _ASKED_OR_SHOWN_AXES, or _INTERNAL_AXES."
    )


def test_the_classification_sets_do_not_overlap() -> None:
    """An axis in two buckets makes the drift arm above pass while meaning nothing."""
    assert not (_DISCLOSED_AXES & _INTERNAL_AXES)
    assert not (_DISCLOSED_AXES & _ASKED_OR_SHOWN_AXES)
    assert not (_INTERNAL_AXES & _ASKED_OR_SHOWN_AXES)
