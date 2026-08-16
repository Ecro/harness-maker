"""Phase 7 — AC-016: a hunk removed by one round and restored by a later one.

Oscillation means two rounds disagreed about the same code, which is a gap in the SPEC
rather than a defect in the diff — so the finding is `manual-only` by construction. If it
could reach the voting set it would make grade A unreachable for a review whose only
problem is that nobody wrote down which behaviour was wanted.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.review_churn import (
    HunkRecord,
    detect_oscillation,
    parse_hunks,
    record_oscillations,
)

_DIFF = """\
diff --git a/src/pkg/retry.py b/src/pkg/retry.py
--- a/src/pkg/retry.py
+++ b/src/pkg/retry.py
@@ -10,6 +10,7 @@ def send_with_retry(msg):
     for attempt in range(3):
         try:
             return _send(msg)
+        except TimeoutError:
+            continue
         except OSError:
             raise
"""


def three_round_fixture() -> list[HunkRecord]:
    """The documented R3-removes / R4-restores sequence, one oscillating hunk among three.

    The two non-oscillating neighbours are the point: a detector that flags every hunk
    touched more than once would report all three, and a suite with only the oscillating
    hunk in it could not tell that implementation from the correct one.
    """
    osc = ("src/pkg/retry.py", "hash-retry", "send_with_retry")
    kept = ("src/pkg/retry.py", "hash-kept", "send_with_retry")
    added = ("src/pkg/log.py", "hash-added", "emit")
    return [
        HunkRecord(round=2, path=osc[0], content_hash=osc[1], symbol=osc[2], present=True),
        HunkRecord(round=2, path=kept[0], content_hash=kept[1], symbol=kept[2], present=True),
        HunkRecord(round=3, path=osc[0], content_hash=osc[1], symbol=osc[2], present=False),
        HunkRecord(round=3, path=kept[0], content_hash=kept[1], symbol=kept[2], present=True),
        HunkRecord(round=3, path=added[0], content_hash=added[1], symbol=added[2], present=True),
        HunkRecord(round=4, path=osc[0], content_hash=osc[1], symbol=osc[2], present=True),
        HunkRecord(round=4, path=kept[0], content_hash=kept[1], symbol=kept[2], present=True),
        HunkRecord(round=4, path=added[0], content_hash=added[1], symbol=added[2], present=True),
    ]


def test_oscillating_hunk_emits_manual_only_spec_gap() -> None:
    findings = detect_oscillation(three_round_fixture())
    assert len(findings) == 1, f"expected only the oscillating hunk, got {findings}"
    finding = findings[0]
    assert finding.tag == "manual-only"
    assert finding.category == "spec_gap"
    assert finding.severity == "P1"
    assert finding.path == "src/pkg/retry.py"
    assert finding.symbol == "send_with_retry"
    assert finding.rounds == (2, 3, 4)


def test_oscillating_hunk_emits_manual_only_spec_gap_needs_a_restoration_not_just_a_removal() -> (
    None
):
    """A hunk removed and left removed is a fix, not an oscillation.

    Keying on "touched in two rounds" would report it — and every ordinary repair round
    touches something twice, so the report would be noise from its first run.
    """
    removed_for_good = [
        HunkRecord(round=2, path="a.py", content_hash="h", symbol="f", present=True),
        HunkRecord(round=3, path="a.py", content_hash="h", symbol="f", present=False),
        HunkRecord(round=4, path="a.py", content_hash="h", symbol="f", present=False),
    ]
    assert detect_oscillation(removed_for_good) == []


def test_oscillating_hunk_emits_manual_only_spec_gap_distinguishes_same_text_in_two_symbols() -> (
    None
):
    """Identical text in two functions is two hunks; the key carries the symbol for that.

    Keyed on (path, hash) alone, a removal in one function and an addition of the same
    line in another reads as a restoration — a false spec_gap raised against code that
    never oscillated.
    """
    records = [
        HunkRecord(round=2, path="a.py", content_hash="h", symbol="f", present=True),
        HunkRecord(round=3, path="a.py", content_hash="h", symbol="f", present=False),
        HunkRecord(round=3, path="a.py", content_hash="h", symbol="g", present=True),
    ]
    assert detect_oscillation(records) == []


def test_parse_hunks_keys_on_the_enclosing_symbol_from_the_hunk_header() -> None:
    hunks = parse_hunks(_DIFF, round_no=2)
    assert len(hunks) == 1
    assert hunks[0].path == "src/pkg/retry.py"
    assert hunks[0].symbol == "def send_with_retry(msg):"
    assert hunks[0].present is True
    assert hunks[0].content_hash


def test_parse_hunks_normalizes_whitespace_so_a_reindent_is_not_a_new_hunk() -> None:
    """Re-indenting restored code must still match its own removal.

    Without normalization the restoration hashes differently, the oscillation goes
    undetected, and the report silently covers less than it claims.
    """
    reindented = _DIFF.replace("+        except TimeoutError:", "+            except TimeoutError:")
    assert parse_hunks(_DIFF, round_no=2)[0].content_hash == (
        parse_hunks(reindented, round_no=3)[0].content_hash
    )


def test_oscillations_are_recorded_to_the_per_slug_jsonl(tmp_path: Path) -> None:
    findings = detect_oscillation(three_round_fixture())
    path = record_oscillations(tmp_path, "review-loop-empirics", findings)
    assert path.name == "review-oscillation-review-loop-empirics.jsonl"
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 1
    assert rows[0]["tag"] == "manual-only"
    assert rows[0]["rounds"] == [2, 3, 4]

    # Append-only: a second review of the same slug adds rows, never truncates.
    record_oscillations(tmp_path, "review-loop-empirics", findings)
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_recording_no_oscillations_writes_nothing(tmp_path: Path) -> None:
    """An empty run must not leave a file that reads as "a report was produced"."""
    path = record_oscillations(tmp_path, "slug", [])
    assert not path.exists()


# ── end to end over the endpoint refs Phase 5 pins ───────────────────────────


def _git(root: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def test_oscillating_hunk_emits_manual_only_spec_gap_end_to_end(tmp_path: Path) -> None:
    """The refs ARE the record — a round removed a guard, a later round put it back.

    Driven through the shipped entry point, because the detector is only useful if the
    stage's own pins feed it; a unit test on `detect_oscillation` proves the arithmetic
    and nothing about the wiring (this PLAN's round-1 P0, verbatim).
    """
    from harness_maker.review_churn import main, pin

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")

    with_guard = (
        "def send(msg):\n"
        "    for attempt in range(3):\n"
        "        try:\n"
        "            return _send(msg)\n"
        "        except TimeoutError:\n"
        "            continue\n"
        "        except OSError:\n"
        "            raise\n"
    )
    without_guard = with_guard.replace("        except TimeoutError:\n            continue\n", "")

    target = tmp_path / "retry.py"
    target.write_text(with_guard, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")

    # Round 2 removes the guard; round 3 puts it back.
    pin(tmp_path, "s", "r2-pre")
    target.write_text(without_guard, encoding="utf-8")
    pin(tmp_path, "s", "r2-post")
    pin(tmp_path, "s", "r3-pre")
    target.write_text(with_guard, encoding="utf-8")
    pin(tmp_path, "s", "r3-post")

    assert main(["oscillation", "--slug", "s", "--rounds", "2,3", "--root", str(tmp_path)]) == 0
    rows = [
        json.loads(ln)
        for ln in (tmp_path / ".claude" / "observability" / "review-oscillation-s.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if ln.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["tag"] == "manual-only"
    assert rows[0]["category"] == "spec_gap"
    assert rows[0]["path"] == "retry.py"
    assert rows[0]["symbol"]


def test_a_round_that_only_fixes_forward_reports_no_oscillation(tmp_path: Path) -> None:
    """Non-vacuity for the end-to-end path: two ordinary repair rounds must stay silent."""
    from harness_maker.review_churn import main, pin

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    target = tmp_path / "a.py"
    target.write_text("def f():\n    return 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")

    pin(tmp_path, "s", "r2-pre")
    target.write_text("def f():\n    return 2\n", encoding="utf-8")
    pin(tmp_path, "s", "r2-post")
    pin(tmp_path, "s", "r3-pre")
    target.write_text("def f():\n    return 3\n", encoding="utf-8")
    pin(tmp_path, "s", "r3-post")

    assert main(["oscillation", "--slug", "s", "--rounds", "2,3", "--root", str(tmp_path)]) == 0
    assert not (tmp_path / ".claude" / "observability" / "review-oscillation-s.jsonl").exists()


def test_the_rendered_stage_scans_for_oscillation_and_keeps_it_off_the_grade() -> None:
    """Wiring plus the one property that makes it safe to ship.

    A detector that could move the grade would block approval on a SPEC gap, so the
    render must state that it does not — and must actually be invoked, which the round-1
    P0 of this PLAN showed is a separate fact from the arithmetic being correct.
    """
    import tempfile

    from harness_maker.interview import interview
    from harness_maker.models import ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    profile = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    answers = interview(profile, autoloop_mode=True)
    answers.worktree["enabled"] = True
    answers.targets = [Target.CLAUDE_CODE, Target.CODEX]
    out = Path(tempfile.mkdtemp())
    render(synthesize(profile, answers), out, freeze_time=DEFAULT_FREEZE_TIME)

    bodies = {
        "claude": (out / "commands" / "hm" / "review.md").read_text(encoding="utf-8"),
        "codex": (out / ".." / ".agents" / "skills" / "hm-review" / "SKILL.md")
        .resolve()
        .read_text(encoding="utf-8"),
    }
    for variant, body in bodies.items():
        calls = [ln for ln in body.splitlines() if "hm review_churn oscillation " in ln]
        assert len(calls) == 1, f"{variant}: expected one oscillation scan, got {len(calls)}"
        assert "--rounds" in calls[0]
        assert "cd <WT> &&" in calls[0], f"{variant}: scan runs against the base repo"
        assert "never moves the grade" in body, f"{variant}: the grade exclusion is not stated"
        assert "manual-only" in body
