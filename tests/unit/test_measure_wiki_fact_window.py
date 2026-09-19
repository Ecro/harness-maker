"""ADR-005 (PLAN-mission-context-loop) — the pre-registered 28-day criterion is measured, not read.

SPEC-mission-context-loop pre-registers: 28 days from the release tag that ships S0, count the
`[wiki:fact]` headings dated inside the window — ≥5 files S1, 0 removes S0. The script that
`intent.yaml`'s `wiki_fact_entries_28d` outcome runs must therefore:

- refuse before a `v*` release tag contains the skill (exit 2) — no value is recorded early;
- refuse while the window is open (exit 3) — wrapup 5.7 runs `measure --all` every wrapup;
- count each slug by its EARLIEST dated heading across history, so a post-deadline correction
  (which re-dates the heading) and a late fold cannot change the decision after it fires.

Every expected count is derived from the fixture's own dated headings, never from the script.
The clock is injected; the real time is never read.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "measure_wiki_fact_window.py"
_SKILL = "src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2"
_WIKI = ".claude/memory/wiki.md"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("measure_wiki_fact_window", _SCRIPT)
    assert spec is not None, f"missing {_SCRIPT}"
    assert spec.loader is not None, f"missing {_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str, date: str | None = None) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True, timeout=30)


def _wiki(repo: Path, headings: list[str]) -> None:
    path = repo / _WIKI
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{h}\nbody" for h in headings)
    path.write_text(
        f"# Wiki Index\n\n<!-- @hm:user:entries -->\n{body}\n<!-- @hm:/user:entries -->\n",
        encoding="utf-8",
    )


def _commit(repo: Path, message: str, date: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message, date=date)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README").write_text("x\n", encoding="utf-8")
    _commit(repo, "init", "2026-09-01T10:00:00+00:00")
    skill = repo / _SKILL
    skill.parent.mkdir(parents=True)
    skill.write_text("skill\n", encoding="utf-8")
    _commit(repo, "add skill", "2026-09-19T10:00:00+00:00")
    return repo


def _tag(repo: Path, name: str, date: str) -> None:
    _git(repo, "tag", "-a", name, "-m", name, date=date)


def _run(repo: Path, now: datetime) -> tuple[int, str]:
    module = _load()
    code, out = module.measure(repo, now=now)
    return code, out


def test_no_release_tag_is_not_released(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _tag(repo, "rel-1", "2026-09-20T10:00:00+00:00")  # not a v* release tag
    code, out = _run(repo, datetime(2026, 12, 1, tzinfo=UTC))
    assert code == 2
    assert "not released" in out


def test_window_open_refuses_to_measure(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _tag(repo, "v0.58.0", "2026-09-20T10:00:00+00:00")
    code, out = _run(repo, datetime(2026, 10, 10, tzinfo=UTC))  # day 20 of 28
    assert code == 3
    assert "window open" in out


def test_counts_each_slug_by_its_earliest_in_window_date(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _wiki(repo, ["## [wiki:fact] before-release | 2026-09-10"])
    _commit(repo, "fact before the tag", "2026-09-10T10:00:00+00:00")
    _tag(repo, "v0.58.0", "2026-09-20T10:00:00+00:00")  # window 2026-09-20 .. 2026-10-18
    _wiki(
        repo,
        [
            "## [wiki:fact] before-release | 2026-09-10",
            "## [wiki:fact] staging-rate-limit | 2026-09-25",
            "## [wiki:fact] later-corrected | 2026-10-01",
            "## [wiki:architecture] not-a-fact | 2026-10-02",
        ],
    )
    _commit(repo, "facts in window", "2026-10-02T10:00:00+00:00")
    _wiki(
        repo,
        [
            "## [wiki:fact] before-release | 2026-09-10",
            "## [wiki:fact] staging-rate-limit | 2026-09-25",
            "## [wiki:fact] later-corrected | 2026-11-05",  # corrected after the deadline
            "## [wiki:architecture] not-a-fact | 2026-10-02",
            "## [wiki:fact] after-deadline | 2026-11-05",
        ],
    )
    _commit(repo, "post-deadline correction", "2026-11-05T10:00:00+00:00")
    # An uncommitted in-window capture still in the working tree (folded later) counts too.
    text = (repo / _WIKI).read_text(encoding="utf-8")
    (repo / _WIKI).write_text(
        text.replace(
            "<!-- @hm:/user:entries -->",
            "## [wiki:fact] uncommitted-capture | 2026-10-15\nbody\n<!-- @hm:/user:entries -->",
        ),
        encoding="utf-8",
    )
    in_window = {"staging-rate-limit", "later-corrected", "uncommitted-capture"}
    code, out = _run(repo, datetime(2026, 11, 20, tzinfo=UTC))
    assert code == 0
    assert out.strip().splitlines()[-1] == str(len(in_window))


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 10, 18, 23, 59, tzinfo=UTC), 3),  # last day of the window: still open
        (datetime(2026, 10, 19, 0, 0, tzinfo=UTC), 0),  # the day after: closed
    ],
    ids=["last-window-day", "day-after"],
)
def test_window_boundary(tmp_path: Path, now: datetime, expected: int) -> None:
    repo = _repo(tmp_path)
    _tag(repo, "v0.58.0", "2026-09-20T10:00:00+00:00")
    code, _ = _run(repo, now)
    assert code == expected


def test_anchors_on_the_first_add_of_the_skill(tmp_path: Path) -> None:
    """ADR-005 (1): add → remove → re-add; the window follows the FIRST add's release.

    First add ships in v0.58.0 (2026-09-20 → window closes after 2026-10-18); the re-add ships
    in v0.59.0 (2026-10-20 → would stay open until 2026-11-17). On 2026-10-25 the correct
    anchor measures (exit 0); anchoring on the re-add would still refuse (exit 3).
    """
    repo = _repo(tmp_path)
    _tag(repo, "v0.58.0", "2026-09-20T10:00:00+00:00")
    (repo / _SKILL).unlink()
    _commit(repo, "remove skill", "2026-10-05T10:00:00+00:00")
    (repo / _SKILL).write_text("skill again\n", encoding="utf-8")
    _commit(repo, "re-add skill", "2026-10-19T10:00:00+00:00")
    _tag(repo, "v0.59.0", "2026-10-20T10:00:00+00:00")
    code, _ = _run(repo, datetime(2026, 10, 25, tzinfo=UTC))
    assert code == 0


def test_picks_the_earliest_v_tag_by_creator_date(tmp_path: Path) -> None:
    """ADR-005 (2): name order and creation order disagree; creation order wins.

    `v0.58.1` is created 2026-09-25 (window closes after 2026-10-23); `v0.58.0` is created
    later, 2026-10-10 (would close after 2026-11-07). On 2026-10-30 the earliest-by-creator-date
    tag measures (exit 0); a lexical, version-sort or latest-created pick would refuse (exit 3).
    """
    repo = _repo(tmp_path)
    _tag(repo, "v0.58.1", "2026-09-25T10:00:00+00:00")
    _tag(repo, "v0.58.0", "2026-10-10T10:00:00+00:00")
    code, _ = _run(repo, datetime(2026, 10, 30, tzinfo=UTC))
    assert code == 0


def test_membership_includes_the_last_window_day_and_excludes_the_next(tmp_path: Path) -> None:
    """ADR-005 (3), amended: membership is `tag_day <= earliest <= tag_day + 28` on UTC dates."""
    repo = _repo(tmp_path)
    _tag(repo, "v0.58.0", "2026-09-20T10:00:00+00:00")  # tag_day 2026-09-20, last day 2026-10-18
    _wiki(
        repo,
        [
            "## [wiki:fact] on-the-last-day | 2026-10-18",
            "## [wiki:fact] the-day-after | 2026-10-19",
        ],
    )
    _commit(repo, "boundary facts", "2026-10-19T10:00:00+00:00")
    code, out = _run(repo, datetime(2026, 11, 1, tzinfo=UTC))
    assert code == 0
    assert out.strip().splitlines()[-1] == "1"


def test_tag_day_is_the_utc_date_of_the_creator_date(tmp_path: Path) -> None:
    """ADR-005 (3), amended: a tag created 2026-09-20 23:30 -05:00 is 2026-09-21 in UTC.

    Anchored on the UTC day the window runs through 2026-10-19, so on 2026-10-19 12:00Z it is
    still open (exit 3). Anchoring on the tag's local date (2026-09-20) would have closed it
    after 2026-10-18 and measured (exit 0).
    """
    repo = _repo(tmp_path)
    _tag(repo, "v0.58.0", "2026-09-20T23:30:00-05:00")
    code, out = _run(repo, datetime(2026, 10, 19, 12, 0, tzinfo=UTC))
    assert code == 3
    assert "window open (1 days left)" in out


def test_correction_before_the_first_fold_keeps_the_first_recorded_date(tmp_path: Path) -> None:
    """Codex P1 4444994ec2c7ab6f: capture in-window, never committed, corrected after the window.

    The correction re-dates the heading past the deadline and the original heading was never
    in any commit — only the `first recorded` date the correction carries forward still says
    the fact was captured inside the window. Without reading it, the count reads 0 and the
    pre-registered rule would remove a skill that was in fact used.
    """
    repo = _repo(tmp_path)
    _tag(repo, "v0.58.0", "2026-09-20T10:00:00+00:00")  # window 2026-09-20 .. 2026-10-18
    path = repo / _WIKI
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Wiki Index\n\n<!-- @hm:user:entries -->\n"
        "## [wiki:fact] staging-rate-limit | 2026-10-25\n"
        "Staging throttles at 20 req/s.\n"
        "Supersedes: staging throttles at 10 req/s (first recorded 2026-10-15)\n"
        "## [wiki:fact] later-only | 2026-10-26\n"
        "body\n"
        "<!-- @hm:/user:entries -->\n",
        encoding="utf-8",
    )
    code, out = _run(repo, datetime(2026, 11, 1, tzinfo=UTC))
    assert code == 0
    assert out.strip().splitlines()[-1] == "1"


def test_first_recorded_date_in_a_committed_version_counts(tmp_path: Path) -> None:
    """The carried-forward date is read from every committed version, not only added lines."""
    repo = _repo(tmp_path)
    _tag(repo, "v0.58.0", "2026-09-20T10:00:00+00:00")
    _wiki(repo, ["## [wiki:gotcha] unrelated | 2026-09-01"])
    _commit(repo, "seed", "2026-09-21T10:00:00+00:00")
    text = (
        (repo / _WIKI)
        .read_text(encoding="utf-8")
        .replace(
            "<!-- @hm:/user:entries -->",
            "## [wiki:fact] corrected-late | 2026-10-30\nnew truth\n"
            "Supersedes: old truth (first recorded 2026-09-25)\n<!-- @hm:/user:entries -->",
        )
    )
    (repo / _WIKI).write_text(text, encoding="utf-8")
    _commit(repo, "late correction folded", "2026-10-30T10:00:00+00:00")
    (repo / _WIKI).write_text(
        text.replace("Supersedes: old truth (first recorded 2026-09-25)\n", ""),
        encoding="utf-8",
    )
    code, out = _run(repo, datetime(2026, 11, 5, tzinfo=UTC))
    assert code == 0
    assert out.strip().splitlines()[-1] == "1"
