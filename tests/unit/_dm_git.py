"""Deterministic git-fixture builder for delivery_metrics tests (PLAN P2).

Every commit's author/committer date is pinned relative to a fixed anchor so
CFR/churn window math is reproducible on any machine/TZ (Codex finding P2-11).
Not a conftest — imported explicitly by delivery-metrics test modules.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

ANCHOR = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)

_ENV_BASE = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "TZ": "UTC",
    "HOME": "/nonexistent-dm-home",
    "GIT_AUTHOR_NAME": "DM Fixture",
    "GIT_AUTHOR_EMAIL": "dm@fixture.test",
    "GIT_COMMITTER_NAME": "DM Fixture",
    "GIT_COMMITTER_EMAIL": "dm@fixture.test",
}


class DMRepo:
    """Scripted repo whose history is the hand-computed oracle for golden tests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.git("init", "-b", "main")

    def git(self, *args: str, days_ago: float | None = None, hours_ago: float | None = None) -> str:
        env = dict(_ENV_BASE)
        if days_ago is not None or hours_ago is not None:
            delta = timedelta(days=days_ago or 0, hours=hours_ago or 0)
            stamp = (ANCHOR - delta).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            env["GIT_AUTHOR_DATE"] = stamp
            env["GIT_COMMITTER_DATE"] = stamp
        proc = subprocess.run(  # noqa: S603 — fixture-only, args-list, no shell
            ["git", *args],
            cwd=self.root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.stdout.strip()

    def commit(
        self,
        subject: str,
        *,
        days_ago: float,
        files: dict[str, str] | None = None,
        body: str = "",
    ) -> str:
        for rel, content in (files or {f"f-{days_ago}.txt": subject}).items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        self.git("add", "-A")
        message = subject if not body else f"{subject}\n\n{body}"
        self.git("commit", "-m", message, "--allow-empty", days_ago=days_ago)
        return self.git("rev-parse", "HEAD")

    def revert_commit(self, target_sha: str, target_subject: str, *, days_ago: float) -> str:
        """Native `git revert` message shape without running an actual revert."""
        return self.commit(
            f'Revert "{target_subject}"',
            days_ago=days_ago,
            files={f"revert-{days_ago}.txt": target_sha},
            body=f"This reverts commit {target_sha}.",
        )

    def tag(self, name: str, *, days_ago: float, annotated: bool = True) -> None:
        if annotated:
            self.git("tag", "-a", name, "-m", name, days_ago=days_ago)
        else:
            self.git("tag", name, days_ago=days_ago)


def golden_tagged_repo(root: Path) -> DMRepo:
    """3 in-window releases; v0.2.0 failed via revert; v0.2.1 is fix-only.

    Hand-computed oracle (window = 28d before ANCHOR):
    - day 40: initial (outside window)
    - day 20: feat alpha  → tag v0.1.0
    - day 15: feat beta   → tag v0.2.0
    - day 12: Revert "feat: beta"  (target ∈ v0.2.0 → v0.2.0 FAILED)
    - day 10: fix: crash  → tag v0.2.1 (all commits fix-typed → FIX-ONLY,
              excluded from denominator; 5d after v0.2.0 = outside the 72h
              respin heuristic, so it retro-fails nothing — v0.2.0's single
              failure comes from the revert)
    - day  5: feat gamma  → tag v0.3.0 (lightweight — covers both tag types)
    ⇒ failed=1, total=3, unit='tag'.
    """
    r = DMRepo(root)
    r.commit("chore: initial", days_ago=40)
    r.commit("feat: alpha", days_ago=20)
    r.tag("v0.1.0", days_ago=20)
    beta = r.commit("feat: beta", days_ago=15)
    r.tag("v0.2.0", days_ago=15)
    r.revert_commit(beta, "feat: beta", days_ago=12)
    r.commit("fix: crash", days_ago=10)
    r.tag("v0.2.1", days_ago=10)
    r.commit("feat: gamma", days_ago=5)
    r.tag("v0.3.0", days_ago=5, annotated=False)
    return r


def golden_untagged_repo(root: Path) -> DMRepo:
    """No tags; 3 first-parent commits inside the window (+1 outside).

    ⇒ unit='task-land', total=3, failed=0.
    """
    r = DMRepo(root)
    r.commit("chore: initial", days_ago=40)
    r.commit("feat: one", days_ago=21)
    r.commit("feat: two", days_ago=9)
    r.commit("docs: three", days_ago=3)
    return r


def golden_empty_repo(root: Path) -> DMRepo:
    """History exists but nothing inside the window ⇒ not_applicable."""
    r = DMRepo(root)
    r.commit("chore: initial", days_ago=40)
    r.commit("feat: old", days_ago=35)
    return r


_BASE_LINES = [f"base-{i}" for i in range(5)]
_A_LINES = [f"alpha-{i}" for i in range(10)]


def golden_churn_repo(root: Path) -> DMRepo:
    """AC-004 oracle (maturation 14d, cohort [28d,14d] before ANCHOR).

    - day 40: base.py with 5 base lines (outside cohort)
    - day 20: commit A appends 10 alpha lines  → THE cohort commit, added_w=10
    - day 10: commit B rewrites alpha-0..3     → 4 churned (inside maturation)
    - day  8: commit C whitespace-pads alpha-4..6 → NOT churned (blame -w)
    - day  2: commit D rewrites alpha-7..8     → NOT churned (after the
              day-6 maturation boundary — boundary rev is C)
    ⇒ churned_loc=4, added_loc=10.
    """
    r = DMRepo(root)

    def write(lines: list[str]) -> dict[str, str]:
        return {"base.py": "\n".join(lines) + "\n"}

    r.commit("chore: initial", days_ago=40, files=write(_BASE_LINES))
    r.commit("feat: alpha block", days_ago=20, files=write(_BASE_LINES + _A_LINES))

    b_lines = list(_A_LINES)
    for i in range(4):
        b_lines[i] = f"beta-{i}"
    r.commit("refactor: rework alpha head", days_ago=10, files=write(_BASE_LINES + b_lines))

    c_lines = list(b_lines)
    for i in range(4, 7):
        c_lines[i] = c_lines[i] + "   "  # trailing whitespace only
    r.commit("style: pad alpha mid", days_ago=8, files=write(_BASE_LINES + c_lines))

    d_lines = list(c_lines)
    for i in range(7, 9):
        d_lines[i] = f"delta-{i}"
    r.commit("refactor: late rework", days_ago=2, files=write(_BASE_LINES + d_lines))
    return r


def perf_repo(root: Path, n_commits: int = 2000, span_days: int = 100) -> DMRepo:
    """~n_commits first-parent history via one fast-import stream (fast + pinned)."""
    r = DMRepo(root)
    epoch = int(ANCHOR.timestamp())
    step = span_days * 86_400 // n_commits
    chunks: list[str] = []
    for i in range(n_commits):
        ts = epoch - span_days * 86_400 + i * step
        path = f"src/mod_{i % 50}.py"
        content = "\n".join(f"line-{i}-{j}" for j in range(10)) + "\n"
        subject = f"feat: change {i}" if i % 7 else f"fix: patch {i}"
        msg = subject + "\n"
        chunks.append(
            f"blob\nmark :{2 * i + 1}\ndata {len(content.encode())}\n{content}\n"
            f"commit refs/heads/main\nmark :{2 * i + 2}\n"
            f"author DM Fixture <dm@fixture.test> {ts} +0000\n"
            f"committer DM Fixture <dm@fixture.test> {ts} +0000\n"
            f"data {len(msg.encode())}\n{msg}"
            + (f"from :{2 * i}\n" if i else "")
            + f"M 100644 :{2 * i + 1} {path}\n\n"
        )
    stream = "".join(chunks)
    subprocess.run(  # noqa: S603
        ["git", "fast-import", "--quiet"],
        cwd=r.root,
        env=_ENV_BASE,
        input=stream,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    subprocess.run(  # noqa: S603
        ["git", "checkout", "-q", "main"],
        cwd=r.root,
        env=_ENV_BASE,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return r
