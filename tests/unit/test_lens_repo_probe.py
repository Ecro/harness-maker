"""PLAN-bench-study-adoption Phase 4 — the repo-access canary.

Reviewers were given `Read`/`Grep`/`Glob`, and 2026-08-20's causation rule now *depends* on that
access: a defect the change triggers is reported at its cause, which is routinely a file the
diff never touched. Nothing verified the access is live. `Ecro/harness-bench`'s `STUDY-ko.md`
reports a one-minute canary catching three misdiagnoses where "the setting did not apply" and
"the model just behaves that way" were indistinguishable from outside.

The canary is one verbatim line from a file the diff does not touch, checked mechanically.

Three design facts the tests below pin, each because its absence was a finding in review:

* **Read the blob at the reviewed revision, never the working tree.** The path comes from model
  output. A tracked symlink satisfies `git ls-files` while resolving outside the repository, so
  "read that path on disk" makes the validator an arbitrary-file reader driven by the thing it
  is checking. `git show <rev>:<path>` cannot escape, and it also pins the check to the code
  under review rather than to whatever the tree holds now.

* **Side has a third state, and it is `None` — not `[]`.** ADR-005 renders no probe requirement
  on Side, so Side reviewers correctly emit none. An empty diff-file set is NOT the way to say
  that: with `[]` every path satisfies "not in the diff" and the check silently becomes a
  no-op, which is the absent-case black hole arriving through the parameter list.

* **A failed probe makes that lens `missing`.** It reuses the one blocking reason that already
  exists; `missing` already blocks approval and the Auto-Fix Loop already re-dispatches. A
  second independent gate would create a state needing both satisfied, for no more detection.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.lens_coverage import ProbeCheck, coverage_verdict, exercised_lenses

_RUN = "run-1"
_CAUSE = "src/pkg/cause.py"
_CAUSE_BODY = "import os\n\n\ndef reach(flag):\n    return os.sep if flag else None\n"


def _check(**over: object) -> ProbeCheck:
    """The happy-path context: one tracked out-of-diff file, one file in the diff."""
    kw: dict[str, object] = {
        "diff_files": frozenset({"src/pkg/touched.py"}),
        "tracked": frozenset({"src/pkg/touched.py", _CAUSE}),
        "read_blob": lambda path: _CAUSE_BODY if path == _CAUSE else None,
    }
    kw.update(over)
    return ProbeCheck(**kw)  # type: ignore[arg-type]


def _write(d: Path, lens: str, probe: object) -> None:
    d.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"lens": lens, "run_id": _RUN, "findings": []}
    if probe is not None:
        payload["repo_probe"] = probe
    (d / f"{lens}.json").write_text(json.dumps(payload), encoding="utf-8")


def _good_probe() -> dict[str, object]:
    return {"path": _CAUSE, "line": 4, "text": "def reach(flag):"}


# ── the happy path, so every negative below is a real contrast ──────────────


def test_a_verbatim_out_of_diff_quote_counts_the_lens_as_exercised(tmp_path: Path) -> None:
    _write(tmp_path, "design", _good_probe())
    assert exercised_lenses(tmp_path, _RUN, probe=_check()) == {"design"}


# ── the five invalidity modes ───────────────────────────────────────────────


def test_an_absent_probe_field_drops_the_lens(tmp_path: Path) -> None:
    """Mode 1, and the most likely: a reviewer that never had access cannot produce one."""
    _write(tmp_path, "design", None)
    assert exercised_lenses(tmp_path, _RUN, probe=_check()) == set()


def test_quoting_a_file_inside_the_diff_drops_the_lens(tmp_path: Path) -> None:
    """Mode 2. The diff is already in the brief — quoting it proves nothing about access."""
    _write(tmp_path, "design", {"path": "src/pkg/touched.py", "line": 1, "text": "x"})
    assert exercised_lenses(tmp_path, _RUN, probe=_check()) == set()


def test_quoting_an_untracked_path_drops_the_lens(tmp_path: Path) -> None:
    """Mode 3. A path git does not know is a path the reviewer did not read."""
    _write(tmp_path, "design", {"path": "src/pkg/invented.py", "line": 1, "text": "x"})
    assert exercised_lenses(tmp_path, _RUN, probe=_check()) == set()


def test_text_that_does_not_match_the_line_drops_the_lens(tmp_path: Path) -> None:
    """Mode 4 — the one that separates reading from guessing a plausible line."""
    _write(tmp_path, "design", {"path": _CAUSE, "line": 4, "text": "def reach(flag, extra):"})
    assert exercised_lenses(tmp_path, _RUN, probe=_check()) == set()


@pytest.mark.parametrize("bad", ["../../etc/passwd", "/etc/passwd", "src/../../escape.py"])
def test_a_path_escaping_the_repository_drops_the_lens(tmp_path: Path, bad: str) -> None:
    """Mode 5 — R11, and the fixture is the whole point.

    The attack shape ADR-003 names is a path that IS tracked (a symlink is in `git ls-files`)
    yet resolves outside the repository. So each bad path is put **into `tracked` and made
    readable with matching text** — every other rejection route is closed, and the only way
    this test can pass is a real containment check on the path itself.

    The first draft left them untracked, where mode 3 rejected them for free. It passed against
    a validator with zero path logic, which is precisely the R11 mitigation it claimed to
    cover. Phase A.5 round 1 caught that.
    """
    _write(tmp_path, "design", {"path": bad, "line": 1, "text": "secret"})
    hostile = _check(
        tracked=frozenset({"src/pkg/touched.py", _CAUSE, bad}),
        read_blob=lambda path: "secret\n" if path == bad else None,
    )
    assert exercised_lenses(tmp_path, _RUN, probe=hostile) == set()


# ── the escape, and its verification ────────────────────────────────────────


def test_the_no_out_of_diff_escape_is_accepted_only_when_it_is_true(tmp_path: Path) -> None:
    """A diff touching every tracked file leaves nothing to quote. That is real, and rare."""
    _write(tmp_path, "design", {"status": "no-out-of-diff-file"})
    every = _check(diff_files=frozenset({"a.py"}), tracked=frozenset({"a.py"}))
    assert exercised_lenses(tmp_path, _RUN, probe=every) == {"design"}


def test_the_escape_is_rejected_when_out_of_diff_files_do_exist(tmp_path: Path) -> None:
    """Never taken on the reviewer's word — otherwise it is a one-line opt-out of the canary."""
    _write(tmp_path, "design", {"status": "no-out-of-diff-file"})
    assert exercised_lenses(tmp_path, _RUN, probe=_check()) == set()


# ── malformed shapes ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "probe",
    [
        "a string",
        [],
        {"path": _CAUSE, "text": "def reach(flag):"},
        {"path": _CAUSE, "line": 0, "text": "def reach(flag):"},
        {"path": _CAUSE, "line": 999, "text": "def reach(flag):"},
        {"path": _CAUSE, "line": "4", "text": "def reach(flag):"},
        {"path": "", "line": 4, "text": "def reach(flag):"},
        {"status": "made-up-status"},
    ],
)
def test_a_malformed_probe_drops_the_lens(tmp_path: Path, probe: object) -> None:
    """Fail-closed on shape. "Cannot tell" must never resolve to "exercised"."""
    _write(tmp_path, "design", probe)
    assert exercised_lenses(tmp_path, _RUN, probe=_check()) == set()


# ── Side: the third state ───────────────────────────────────────────────────


def test_probe_none_skips_the_check_entirely(tmp_path: Path) -> None:
    """ADR-005's Side branch. A probe-less result file still counts as exercised.

    Without this, every Side review is permanently unapprovable: Side renders no probe
    requirement, so mode 1 fires on every lens, `missing` is the full mandatory set, and the
    Grade Gate takes the CHANGES_REQUESTED-at-round-cap branch every time.
    """
    _write(tmp_path, "design", None)
    assert exercised_lenses(tmp_path, _RUN, probe=None) == {"design"}


def test_an_empty_diff_file_set_cannot_be_constructed_at_all() -> None:
    """`[]` is refused where it is BUILT, because the matcher cannot catch it downstream.

    The first draft asserted this against `exercised_lenses` and did not discriminate: given an
    empty `diff_files`, a *correct* matcher has no way to know the quoted path was in the diff
    either, so the wrong implementation and the right one behave identically. Phase A.5 round 1
    caught the confound — the test failed for an unrelated unreadable-blob reason and looked
    green-for-the-right-reason.

    The contract is therefore structural: `[]` makes "not in the diff" true of every path, so a
    `ProbeCheck` holding it would be a check that silently checks nothing. Saying *do not check*
    is `probe=None`, and the error message has to say so — otherwise the next caller writes the
    empty set and gets exactly the no-op this refuses.
    """
    with pytest.raises(ValueError, match="probe=None"):
        _check(diff_files=frozenset())


# ── the verdict layer threads it through ────────────────────────────────────


def test_coverage_verdict_threads_the_probe_context(tmp_path: Path) -> None:
    """`coverage_verdict` calls `exercised_lenses` internally, so it needs the parameter too.

    A signature that stopped at `exercised_lenses` would leave every real caller — `main`, the
    rendered stage — unable to reach the check at all.
    """
    _write(tmp_path, "design", _good_probe())
    _write(tmp_path, "security", {"path": _CAUSE, "line": 4, "text": "WRONG"})
    v = coverage_verdict(tmp_path, _RUN, preset="Production", probe=_check())
    assert "design" in v["exercised"]  # type: ignore[operator]
    assert "security" in v["missing"]  # type: ignore[operator]
    assert v["blocks_approval"] is True


def test_a_failed_probe_produces_missing_and_not_a_new_blocking_reason(tmp_path: Path) -> None:
    """Contract Boundary: `blocks_approval` keeps exactly one meaning.

    Phase 4 widens what "usable result" means; it does not add a second reason. A verdict key
    naming the probe separately would be that second reason.
    """
    _write(tmp_path, "design", {"path": _CAUSE, "line": 4, "text": "WRONG"})
    v = coverage_verdict(tmp_path, _RUN, preset="Production", probe=_check())
    assert set(v) == {"exercised", "missing", "blocks_approval", "preset"}
