"""The delegated wrapup's INPUT contract: derive it from the machine, validate, degrade.

Delegation puts the wrapup body behind a summarisation boundary, so the brief is the
only thing between "the agent had what it needed" and a silently shallower wrapup.
Two failure directions pull opposite ways (ADR-006): accepting a vacuous brief lets
the agent run on nothing, while RAISING on an incomplete one strands a crashed
session's recovery wrapup — a first-class supported path. Hence: reject precisely,
never raise.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .models import DELEGATABLE_STAGES, DelegationConfig
from .second_opinion_invoke import resolve_base_root

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
STAGE = "wrapup"
TASK_BRANCH_PREFIX = "hm/"

# Every field the agent cannot do its job without. `changed_files` and `diff_stat`
# are deliberately absent: an empty diff is a legitimate wrapup (docs already
# committed, or a re-run), and rejecting it would degrade a correct stage.
_REQUIRED: tuple[str, ...] = ("slug", "task_branch", "base_root", "worktree_root", "locale")


class WrapupBrief(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int
    stage: str
    slug: str
    task_branch: str
    base_root: str
    worktree_root: str
    locale: str
    changed_files: tuple[str, ...] = ()
    diff_stat: str = ""
    plan_path: str | None = None
    review_path: str | None = None


class BriefVerdict(BaseModel):
    """`missing` names the fields, because a count is not actionable in a warning."""

    model_config = ConfigDict(strict=True, extra="forbid")

    ok: bool
    missing: tuple[str, ...] = ()
    reason: str = ""


def is_delegated(stage: str, config: DelegationConfig) -> bool:
    return stage.strip().lower() in config.stages


# ------------------------------------------------------------------ validation


def validate_brief(brief: WrapupBrief) -> BriefVerdict:
    """Structure only — ADR-006 states plainly that a present-but-vacuous field passes.

    What it does catch is the set of ways a brief can be internally INCONSISTENT, each
    of which sends the agent's writes somewhere real and wrong.
    """
    missing: list[str] = []
    reasons: list[str] = []

    for field in _REQUIRED:
        value = getattr(brief, field)
        # `"   "` is truthy; a presence check that only tests truthiness accepts a
        # slug of three spaces.
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    if brief.stage not in DELEGATABLE_STAGES:
        # Generalised for verify (Phase 6) but NOT loosened to a free string: a brief
        # for a stage with no dispatch block is a caller bug, not a new feature.
        missing.append("stage")
        reasons.append(f"stage is {brief.stage!r}, expected one of {', '.join(DELEGATABLE_STAGES)}")

    if not missing:
        base = Path(brief.base_root)
        worktree = Path(brief.worktree_root)
        expected_wt = base / ".worktrees" / brief.slug
        if worktree != expected_wt:
            missing.append("worktree_root")
            reasons.append(
                f"worktree_root {brief.worktree_root!r} is not the base repo's "
                f".worktrees/{brief.slug} — expected {str(expected_wt)!r}"
            )
        if brief.task_branch != f"{TASK_BRANCH_PREFIX}{brief.slug}":
            missing.append("task_branch")
            reasons.append(
                f"task_branch {brief.task_branch!r} names a different task than slug {brief.slug!r}"
            )

    if missing:
        return BriefVerdict(
            ok=False,
            missing=tuple(missing),
            reason="; ".join(reasons) or f"underivable or empty: {', '.join(missing)}",
        )
    return BriefVerdict(ok=True)


# ------------------------------------------------------------------ derivation


def _git(args: list[str], cwd: Path) -> str | None:
    """None on ANY failure — no git, not a repo, or a non-zero exit."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _locale(base: Path) -> str:
    """A ko user's wrapup must not silently flip to English because a read failed."""
    path = base / ".claude" / "harness.yaml"
    if not path.is_file():
        return "en"
    try:
        from .io_utils import load_harness_yaml

        data = load_harness_yaml(path)
    except Exception:  # noqa: BLE001 - a broken harness.yaml must not strand the wrapup
        return "en"
    value = data.get("locale") if isinstance(data, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else "en"


def _changed_files(worktree: Path) -> tuple[str, ...]:
    out = _git(["status", "--porcelain", "-uall"], worktree)
    if not out:
        return ()
    names: list[str] = []
    for line in out.splitlines():
        if len(line) > 3:
            # Rename/copy entries are `R  old -> new`; the new path is what changed.
            names.append(line[3:].split(" -> ")[-1].strip())
    return tuple(names)


def _diff_stat(worktree: Path, changed: tuple[str, ...]) -> str:
    """`git diff --stat HEAD` alone is misleading here.

    It reports TRACKED modifications only, and a wrapup's changes are typically new
    files that were never added — so the agent's one view of change size reads empty
    on exactly the tasks that produced the most. Untracked paths are summarised
    explicitly rather than left out.
    """
    tracked = (_git(["diff", "--stat", "HEAD"], worktree) or "").strip()
    out = _git(["ls-files", "--others", "--exclude-standard"], worktree)
    untracked = [line.strip() for line in (out or "").splitlines() if line.strip()]
    if not untracked:
        return tracked
    listed = ", ".join(untracked[:20]) + (" …" if len(untracked) > 20 else "")
    summary = f"{len(untracked)} untracked file(s): {listed}"
    return f"{tracked}\n{summary}" if tracked else summary


def derive_brief(cwd: Path, *, stage: str = STAGE) -> tuple[WrapupBrief | None, BriefVerdict]:
    """Everything the machine knows, derived. Never raises — ADR-006's degraded path."""
    cwd = Path(cwd).resolve()
    toplevel = _git(["rev-parse", "--show-toplevel"], cwd)
    if not toplevel or not toplevel.strip():
        return None, BriefVerdict(
            ok=False,
            missing=("worktree_root",),
            reason=f"{cwd} is not inside a git repository — running the body inline",
        )
    worktree = Path(toplevel.strip()).resolve()

    branch = (_git(["rev-parse", "--abbrev-ref", "HEAD"], worktree) or "").strip()
    if not branch.startswith(TASK_BRANCH_PREFIX):
        # The standalone / recovered wrapup: no task branch, so no slug, so no
        # PLAN/REVIEW to resolve. Inline is the correct outcome, not an error.
        return None, BriefVerdict(
            ok=False,
            missing=("slug",),
            reason=(
                f"HEAD is {branch or '(detached)'!r}, not a {TASK_BRANCH_PREFIX}<slug> "
                "task branch — running the body inline"
            ),
        )
    slug = branch[len(TASK_BRANCH_PREFIX) :]
    base = resolve_base_root(cwd)

    def _doc(kind: str) -> str | None:
        rel = f"work-docs/{kind}-{slug}.md"
        return rel if (worktree / rel).is_file() else None

    changed = _changed_files(worktree)
    brief = WrapupBrief(
        schema_version=SCHEMA_VERSION,
        stage=stage,
        slug=slug,
        task_branch=branch,
        base_root=str(base),
        worktree_root=str(worktree),
        locale=_locale(base),
        changed_files=changed,
        diff_stat=_diff_stat(worktree, changed),
        plan_path=_doc("PLAN"),
        review_path=_doc("REVIEW"),
    )
    verdict = validate_brief(brief)
    if not verdict.ok:
        logger.warning(
            "[%s] brief incomplete (%s): %s — running the body inline",
            stage,
            ", ".join(verdict.missing),
            verdict.reason,
        )
        return None, verdict
    return brief, verdict


# ------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    """Always exit 0. A non-zero exit would turn ADR-006's degraded path into a halt."""
    parser = argparse.ArgumentParser(prog="python -m harness_maker.wrapup_brief")
    parser.add_argument("--root", default=".", help="cwd to derive from (a task worktree)")
    parser.add_argument("--stage", default=STAGE, help=f"one of {', '.join(DELEGATABLE_STAGES)}")
    ns = parser.parse_args(argv if argv is not None else sys.argv[1:])

    brief, verdict = derive_brief(Path(ns.root), stage=ns.stage)
    print(
        json.dumps(
            {
                "status": "ok" if verdict.ok else "degraded",
                "brief": brief.model_dump(mode="json") if brief is not None else None,
                "verdict": verdict.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
