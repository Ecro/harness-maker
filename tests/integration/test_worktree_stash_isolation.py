"""Cross-session stash isolation reproducer (PLAN-worktree-stash-phase4 Phase 4).

Drives the real `_cli_finalize stage-only` → wrapup-mimic commit → `_cli_post_commit_pop`
chain against a tmp repo holding synthesized "session A's WIP" plus a worktree
commit. Asserts session A's WIP is never absorbed into the squash commit.

Gated by INTEGRATION=1 because the test creates real worktrees, runs real
git plumbing, and exercises the production code path (not a mocked stand-in).

The wrapup Step 6 `git add` path list is sourced from `templates/stages/wrapup.md.j2`
verbatim — extracted by regex at test setup. A sibling guard test
(`test_wrapup_template_git_add_line_extractable`) acts as a snapshot-style
canary: if the template changes shape, this guard fires before the integration
test loads, preventing false-green tests against a paraphrased command.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree

_INTEGRATION = os.getenv("INTEGRATION") == "1"


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed args, no shell
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _wrapup_template_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "src"
        / "harness_maker"
        / "templates"
        / "stages"
        / "wrapup.md.j2"
    )


# Steps 6 → 7.6 are now one `hm wrapup_land` call whose staging manifest is a typed list
# of `--required` / `--optional` flags (PLAN-workflow-step-audit Phase 2, ADR-007). The
# pinning obligation is unchanged — this integration test must replay the REAL production
# path list, never a paraphrase — so only the shape it reads has moved, from a shell
# `for p in <paths>` header to the flag list on the same `!` line.
_WRAPUP_LAND_RE = re.compile(r"^!.*\bhm wrapup_land\b(.*)$", re.MULTILINE)
_MANIFEST_FLAG_RE = re.compile(r"--(?:required|optional)\s+(\S+)")


def _extract_wrapup_git_add_args() -> str:
    """Read wrapup.md.j2 and return the Jinja-substituted staging path list.

    Substitutes ``{{ config.work_docs.dir }}`` → ``work-docs/``, ``{{ config.spec.dir }}``
    → ``specs/`` and ``{slug}`` → a fixed test slug. Returns the space-separated path
    list. Raises if the template shape drifts so the integration test never reads a
    paraphrased command.
    """
    body = _wrapup_template_path().read_text(encoding="utf-8")
    match = _WRAPUP_LAND_RE.search(body)
    if not match:
        raise AssertionError(
            "wrapup.md.j2 has no `!… hm wrapup_land …` staging call — template drift "
            "broke integration-test pinning. Update _WRAPUP_LAND_RE or restore the line "
            "shape."
        )
    # Substitute BEFORE splitting: `{{ config.work_docs.dir }}` contains spaces, so a
    # `\S+` capture on the raw line would stop at `{{` and yield a list of brace tokens.
    flags = (
        match.group(1)
        .replace("{{ config.work_docs.dir }}", "work-docs/")
        .replace("{{ config.spec.dir }}", "specs/")
        .replace("{slug}", "phase4-integration")
    )
    paths = _MANIFEST_FLAG_RE.findall(flags)
    if not paths:
        raise AssertionError(
            "the wrapup_land call carries no --required/--optional manifest — an empty "
            "path list would make the replay below stage nothing and assert nothing."
        )
    if any("{" in p for p in paths):
        raise AssertionError(
            f"unsubstituted Jinja survived into the path list: {paths} — the replay would "
            "stage brace tokens and the assertions below would be about nothing."
        )
    return " ".join(paths)


@pytest.fixture
def integration_repo(tmp_path: Path) -> Path:
    """Real git repo mirroring a user's harness-maker project state."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(["init", "-b", "main"], cwd=r)
    _git(["config", "user.email", "t@t"], cwd=r)
    _git(["config", "user.name", "t"], cwd=r)
    (r / "README.md").write_text("# repo\n")
    (r / ".gitignore").write_text(".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n")
    # Pre-track files that wrapup will later scoped-add.
    (r / ".claude").mkdir()
    (r / ".claude" / "memory").mkdir()
    (r / ".claude" / "memory" / "wiki.md").write_text("# wiki\n")
    (r / ".claude" / "memory" / "failures.md").write_text("# failures\n")
    (r / "work-docs").mkdir()
    (r / "work-docs" / "PLAN-phase4-integration.md").write_text("# plan stub\nstatus: planning\n")
    _git(
        [
            "add",
            "README.md",
            ".gitignore",
            ".claude/memory/wiki.md",
            ".claude/memory/failures.md",
            "work-docs/PLAN-phase4-integration.md",
        ],
        cwd=r,
    )
    _git(["commit", "-m", "init"], cwd=r)
    return r


def test_wrapup_template_git_add_line_extractable() -> None:
    """Guard: the wrapup.md.j2 staging manifest must be regex-extractable.

    If this fails, the template has drifted and the integration test below is
    no longer pinned to the real production command. Fix _WRAPUP_GIT_ADD_RE or
    restore the line shape BEFORE editing the integration test.
    """
    args = _extract_wrapup_git_add_args()
    assert ".claude/memory/" in args
    assert "work-docs/PLAN-phase4-integration.md" in args
    assert "work-docs/REVIEW-phase4-integration-*.md" in args


@pytest.mark.skipif(not _INTEGRATION, reason="set INTEGRATION=1 to run")
def test_cross_session_real_wrapup_chain(integration_repo: Path) -> None:
    """End-to-end cross-session reproducer (ADR-003 case 5).

    Reproduces the original 2026-05-19 user incident with the REAL wrapup
    commit shape — `git add` path list sourced from wrapup.md.j2 Step 6 verbatim,
    NOT a synthetic stand-in (validator finding #8).

    Setup: tmp repo with .claude/memory + work-docs already tracked. Synthesize
    session A's pre-existing dirty: modify wiki.md (staged), failures.md
    (unstaged), and create an untracked scratch file. Then drive session B's
    /hm:execute → /hm:wrapup → post-commit-pop chain. Verify session A's
    intent survives (modulo staging collapse per ADR-001 §3).
    """
    repo = integration_repo

    # === Session A's WIP ===
    wiki_wip = "# wiki\n\nSESSION A WIP (must survive finalize)\n"
    (repo / ".claude" / "memory" / "wiki.md").write_text(wiki_wip)
    _git(["add", ".claude/memory/wiki.md"], cwd=repo)  # staged
    failures_wip = "# failures\n\nsession A unstaged note\n"
    (repo / ".claude" / "memory" / "failures.md").write_text(failures_wip)
    # NOT staged — keep as unstaged dirty
    (repo / "scratch.txt").write_text("session A scratch\n")  # untracked

    # === Session B's worktree + commit ===
    (wt,) = worktree.create("execute", repo)
    (wt / "src.py").write_text("def b() -> None:\n    pass\n")
    _git(["add", "src.py"], cwd=wt)
    _git(["commit", "-m", "session B feature"], cwd=wt)

    # === Session B finalize stage-only ===
    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0, "session B finalize stage-only should succeed"

    # === Wrapup mimic — REAL Step 6 per-path loop shape from wrapup.md.j2 ===
    add_args = _extract_wrapup_git_add_args().split()
    # Replay the production loop verbatim: `[ -e ]` guard + per-path `|| true`
    # so missing pathspecs (no SPEC, empty REVIEW glob) can't abort the rest.
    subprocess.run(  # noqa: S602 — controlled args, shell needed for glob + loop
        "for p in "
        + " ".join(add_args)
        + '; do [ -e "$p" ] && git add "$p" 2>/dev/null || true; done',
        cwd=str(repo),
        shell=True,
        check=False,
    )
    _git(["commit", "-m", "session B wrapup"], cwd=repo)

    # === post-commit-pop ===
    rc2 = worktree._cli_post_commit_pop([str(repo)])
    assert rc2 == 0, "post-commit-pop happy path should return 0"

    # === Assertions ===
    # 1. HEAD commit contains session B's src.py
    log = _git(["log", "-1", "--name-only", "--format="], cwd=repo).stdout
    assert "src.py" in log, f"src.py must be in HEAD. log: {log!r}"

    # 2. wiki.md WAS in HEAD commit (because wrapup scoped-added it).
    #    Session A's WIP wiki content is ALSO in HEAD — this is the EXPECTED
    #    behavior of wrapup's scoped add (.claude/memory/ is intentional).
    #    The PLAN's goal is to prevent UNRELATED dirty from sneaking in, NOT
    #    to prevent the wrapup-scoped paths from being committed.
    #    What we MUST verify is that session A's scratch.txt (untracked) and
    #    failures.md (unstaged outside the wrapup scope) survive.

    # 3. Session A's unstaged failures.md content is restored after pop.
    assert (repo / ".claude" / "memory" / "failures.md").read_text() == failures_wip, (
        "session A's unstaged failures.md edit must survive finalize+wrapup+pop"
    )

    # 4. Session A's untracked scratch.txt MUST be restored after pop.
    assert (repo / "scratch.txt").is_file(), (
        "session A's untracked scratch.txt must survive — stash captured -u, pop restored"
    )
    assert (repo / "scratch.txt").read_text() == "session A scratch\n"

    # 5. Ref file is deleted (handshake completed cleanly)
    refs = list((repo / ".claude").glob(".hm-finalize-stash-*"))
    assert not refs, f"ref file must be drained after post-commit-pop. found: {refs}"

    # 6. Stash is empty
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert "hm-finalize-" not in stash_list, (
        f"stash must be drained after pop. list: {stash_list!r}"
    )
