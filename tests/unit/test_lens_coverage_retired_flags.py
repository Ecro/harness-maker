"""`--diff-files` / `--rev` are retired but still accepted, with a dated expiry.

PLAN-probe-envelope-contract ADR-004. The flags reach `lens_coverage check` from the
rendered `review.md`, so a harness rendered by 0.53.0 keeps passing them until its owner
re-renders. `argparse` exits 2 on an unknown argument, and that exit lands at `/hm:review`
Step 3 — every un-re-rendered Production harness would lose its review on the first run
after a package update. That is the same failure mode that forced the probe itself to
advisory before publication, so the flags are absorbed rather than removed.

Three arms, because each covers a different way to be wrongly green:

* accepting the flags — deleting the absorption breaks the old harness;
* the stderr line — deleting the warning leaves a silent no-op, which is the defect class
  this PLAN exists to remove, and arm 1 alone stays green through it;
* the expiry — without it the compatibility test *requires* the flags to stay, and
  preserves them forever. It is compared on parsed integer tuples, never on strings:
  ``"0.100.0" < "0.55.0"`` is True lexicographically, so a string arm would silently stop
  firing the moment the minor series reached three digits.

Phase A.4 (2026-08-22): arms 1 and 2 were RED at authoring, for the intended reasons —
the flags are still functional, so a nonexistent path exits 2, and no deprecation line
exists. Arm 3 passed, because 0.53.0 is genuinely before the sunset; a tripwire that fires
today would be the bug. Its red state was observed rather than assumed: setting
``_SUNSET`` to ``(0, 53, 0)`` turns it red against the shipped version.
"""

from __future__ import annotations

import json

import pytest

from harness_maker import __version__, lens_coverage

#: The release that must remove the flags. When `__version__` reaches it, arm 3 goes red.
_SUNSET = (0, 55, 0)


def _version_tuple(raw: str) -> tuple[int, ...]:
    return tuple(int(part) for part in raw.split(".")[:3])


@pytest.fixture
def one_round(tmp_path: pytest.TempPathFactory) -> tuple[str, str]:
    """A results directory holding one lens file, enough for a verdict to be produced."""
    from pathlib import Path

    base = Path(str(tmp_path))
    results = base / ".hm-lens-results"
    round_path = results / "slug" / "run1" / "1"
    round_path.mkdir(parents=True)
    (round_path / "design.json").write_text(
        json.dumps({"lens": "design", "run_id": "run1", "findings": []}), encoding="utf-8"
    )
    return str(results), str(base)


def test_the_retired_flags_are_still_accepted(
    one_round: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Arm 1 — an un-re-rendered harness still gets a verdict, not an argparse exit 2."""
    results, base = one_round
    rc = lens_coverage.main(
        [
            "check",
            "--results-dir",
            results,
            "--slug",
            "slug",
            "--round",
            "1",
            "--run-id",
            "run1",
            "--preset",
            "Production",
            "--diff-files",
            f"{base}/whatever-does-not-exist.txt",
            "--rev",
            "HEAD",
        ]
    )
    assert rc == 0, "the retired flags must not abort the run"
    payload = json.loads(capsys.readouterr().out)
    # `preset` predates this change and is not probe-related; the first draft of this pin
    # omitted it and failed against correct production code.
    assert set(payload) == {"blocks_approval", "exercised", "missing", "preset"}, (
        f"verdict shape drifted — `probe_failed` should be gone: {sorted(payload)}"
    )


def test_passing_them_says_so_on_stderr(
    one_round: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Arm 2 — silence would make the absorption indistinguishable from the flags working.

    Without this arm, deleting the warning keeps arm 1 green: the run still exits 0 and
    still prints a verdict. A user would keep passing a flag that does nothing and never
    learn to re-render.
    """
    results, base = one_round
    lens_coverage.main(
        [
            "check",
            "--results-dir",
            results,
            "--slug",
            "slug",
            "--round",
            "1",
            "--run-id",
            "run1",
            "--preset",
            "Production",
            "--diff-files",
            f"{base}/whatever-does-not-exist.txt",
            "--rev",
            "HEAD",
        ]
    )
    err = capsys.readouterr().err
    assert "--diff-files" in err, f"the line must name the flag that was passed: {err!r}"
    assert "retired" in err, f"the line must say the flag is retired, not just mention it: {err!r}"
    assert "harness-maker:make" in err, (
        f"the deprecation line must name the remedy, not just the problem: {err!r}"
    )


def test_the_absorption_expires() -> None:
    """Arm 3 — the sunset is enforced by the suite, not by anyone remembering.

    Arms 1 and 2 positively REQUIRE the flags to keep working, so on their own they would
    preserve two dead parameters indefinitely. This one turns red at the release that is
    supposed to remove them.
    """
    assert _version_tuple(__version__) < _SUNSET, (
        f"harness-maker is {__version__}, at or past the {_SUNSET} sunset ADR-004 set for "
        "`--diff-files`/`--rev`. Remove the two absorbed arguments from "
        "`lens_coverage.main`, delete this module, and drop the flags from review.md.j2."
    )


def test_omitting_them_is_silent(
    one_round: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """The absent case — a RE-rendered harness, which is the normal path after this change.

    Phase D.5's absent-case rule: this repair activates on optional flags, so the window it
    opens includes the call that passes neither. The three arms above all pass them, so
    without this one a `sys.stderr.write` moved outside the `if` would warn on every healthy
    review and every one of them would stay green.
    """
    results, _base = one_round
    rc = lens_coverage.main(
        [
            "check",
            "--results-dir",
            results,
            "--slug",
            "slug",
            "--round",
            "1",
            "--run-id",
            "run1",
            "--preset",
            "Production",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == "", (
        f"omitting the retired flags must be silent, not merely non-fatal: {captured.err!r}"
    )
    assert "probe" not in captured.out, f"the verdict still mentions the probe: {captured.out!r}"
