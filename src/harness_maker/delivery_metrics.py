"""Opt-in local git delivery metrics — CFR + post-merge churn (PLAN-cfr-churn-metrics)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness_maker.models import DeliveryMetricsConfig

# Bump when detection heuristics change — part of the adjudication reuse key
# at the ledger layer (ADR-005), so stale verdicts never survive an algorithm
# change silently.
ALGO_VERSION = 1

# A fix-only tag re-spin (or an ambiguous tail fix) counts as remediation of
# the preceding release only within this horizon. Not config: it is part of
# the algorithm identity covered by ALGO_VERSION.
_RESPIN_WINDOW_SECONDS = 72 * 3600

_GIT_TIMEOUT = 60
_FIELD_SEP = "\x01"
_RECORD_SEP = "\x02"

_REMEDIATION_SUBJECT = re.compile(r'(?i)^(fix|hotfix)\b|^Revert "')
_REVERT_SUBJECT = re.compile(r'^Revert "')
_REVERT_TARGET = re.compile(r"This reverts commit (\w+)")


class DeliveryMetricsError(RuntimeError):
    """Raised when the target directory cannot be analyzed (CLI → exit 4)."""


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    subject: str
    ts: int
    parents: tuple[str, ...]
    body: str = ""


@dataclass(frozen=True)
class ReleaseInfo:
    ref: str
    sha: str
    ts: int
    unit: str
    commits: tuple[CommitInfo, ...]


@dataclass(frozen=True)
class CfrResult:
    failed: int = 0
    total: int = 0
    unit: str | None = None
    status: Literal["ok", "not_applicable"] = "ok"
    reason: str | None = None
    pending_adjudications: int = 0

    @property
    def release_unit(self) -> str | None:
        return self.unit


class AdjudicationStore(Protocol):
    """Verdict persistence boundary — in-memory in P2, JSONL ledger in P4."""

    def get(self, commit_sha: str, release_ref: str) -> str | None: ...

    def put(self, *, commit_sha: str, release_ref: str, verdict: str, reason: str) -> None: ...


class InMemoryAdjudicationStore:
    def __init__(self) -> None:
        self._verdicts: dict[tuple[str, str], str] = {}

    def get(self, commit_sha: str, release_ref: str) -> str | None:
        return self._verdicts.get((commit_sha, release_ref))

    def put(self, *, commit_sha: str, release_ref: str, verdict: str, reason: str) -> None:
        del reason  # persisted by the ledger store; irrelevant in memory
        self._verdicts[(commit_sha, release_ref)] = verdict


def _is_remediation_typed(subject: str) -> bool:
    return bool(_REMEDIATION_SUBJECT.match(subject.strip()))


def _revert_target(commit: CommitInfo) -> str | None:
    if not _REVERT_SUBJECT.match(commit.subject.strip()):
        return None
    m = _REVERT_TARGET.search(commit.body)
    return m.group(1) if m else None


# REVIEW security P1 (stored prompt-injection): a candidate's `subject` is git
# `%s` from any landed commit and is piped verbatim into the /hm:metrics session
# transcript for LLM adjudication. Bound it so a contributor cannot smuggle an
# oversized/crafted payload into the agent's context (the template also frames it
# as untrusted data). The full commit is still available via `git show <sha>`.
_CANDIDATE_SUBJECT_MAX = 200


@dataclass(frozen=True)
class AdjudicationCandidate:
    """An ambiguous fix commit awaiting an LLM verdict (ADR-006)."""

    commit_sha: str
    subject: str
    release_ref: str  # the release a `remediation` verdict would fail
    ts: int

    def __post_init__(self) -> None:
        if len(self.subject) > _CANDIDATE_SUBJECT_MAX:
            object.__setattr__(self, "subject", self.subject[:_CANDIDATE_SUBJECT_MAX] + "…")


def classify_cfr(
    releases: list[ReleaseInfo] | tuple[ReleaseInfo, ...],
    tail_commits: list[CommitInfo] | tuple[CommitInfo, ...],
    *,
    window_start: int,
    window_end: int,
    unit: str,
    store: AdjudicationStore | None = None,
) -> CfrResult:
    result, _ = classify_cfr_full(
        releases,
        tail_commits,
        window_start=window_start,
        window_end=window_end,
        unit=unit,
        store=store,
    )
    return result


def classify_cfr_full(
    releases: list[ReleaseInfo] | tuple[ReleaseInfo, ...],
    tail_commits: list[CommitInfo] | tuple[CommitInfo, ...],
    *,
    window_start: int,
    window_end: int,
    unit: str,
    store: AdjudicationStore | None = None,
) -> tuple[CfrResult, list[AdjudicationCandidate]]:
    """Pure CFR classification over pre-collected history.

    Failure signals (all attributed ONLY to in-window denominator releases —
    that guard is what makes the AC-005 window-outside invariance hold):
    - deterministic: a ``Revert "…"`` commit whose target belongs to a release;
    - deterministic (tag unit only): a fix-only release created within 72h of
      its nearest non-fix-only predecessor (tag re-spin);
    - ambiguous → adjudicated: a tail ``fix:`` commit within 72h of the newest
      denominator release, and (task-land unit) a fix-only land within 72h of
      its predecessor — land-granularity respins are routine work more often
      than tag re-spins, so they get LLM judgment instead of a hard rule.
    Fix commits *inside* a mixed release shipped with features are routine by
    definition and never counted. At most one failure per release (set-add).
    """
    ordered = sorted(releases, key=lambda r: (r.ts, r.ref))
    in_window = [r for r in ordered if window_start <= r.ts <= window_end]
    if not in_window:
        return (
            CfrResult(
                status="not_applicable",
                unit=unit,
                reason=(
                    f"no {unit} releases inside the window; "
                    + (
                        "tag a release (or check tag_pattern) to enable CFR"
                        if unit == "tag"
                        else "land a change on the default branch to enable CFR"
                    )
                ),
            ),
            [],
        )

    fix_only = {
        r.ref
        for r in in_window
        if r.commits and all(_is_remediation_typed(c.subject) for c in r.commits)
    }
    denominator = {r.ref for r in in_window if r.ref not in fix_only}

    sha_to_release: dict[str, str] = {}
    for r in ordered:
        for c in r.commits:
            sha_to_release.setdefault(c.sha, r.ref)

    failed: set[str] = set()
    candidates: list[AdjudicationCandidate] = []

    # Signal 1 — revert linkage (deterministic, both units).
    all_commits = [c for r in ordered for c in r.commits] + list(tail_commits)
    for c in all_commits:
        target = _revert_target(c)
        if target is None:
            continue
        ref = sha_to_release.get(target)
        if ref is not None and ref in denominator:
            failed.add(ref)

    # Signal 2 — fix-only release within the respin horizon of its nearest
    # non-fix-only predecessor. Tag unit: deterministic. Task-land unit:
    # ambiguous → candidate keyed (fix commit sha, predecessor ref).
    for idx, r in enumerate(in_window):
        if r.ref not in fix_only:
            continue
        pred: ReleaseInfo | None = None
        for earlier in reversed(in_window[:idx]):
            if earlier.ref in denominator:
                pred = earlier
                break
        if pred is None or (r.ts - pred.ts) > _RESPIN_WINDOW_SECONDS:
            continue
        if unit == "tag":
            failed.add(pred.ref)
        else:
            verdict = store.get(r.sha, pred.ref) if store is not None else None
            if verdict == "remediation":
                failed.add(pred.ref)
            elif verdict != "routine":
                subject = r.commits[0].subject if r.commits else r.ref
                candidates.append(
                    AdjudicationCandidate(
                        commit_sha=r.sha, subject=subject, release_ref=pred.ref, ts=r.ts
                    )
                )

    # Signal 3 — ambiguous tail fix commits shortly after the newest
    # denominator release (post-release firefighting vs routine work).
    newest_denom: ReleaseInfo | None = None
    for r in reversed(in_window):
        if r.ref in denominator:
            newest_denom = r
            break
    if newest_denom is not None:
        for c in tail_commits:
            if _revert_target(c) is not None or not _is_remediation_typed(c.subject):
                continue
            if not (0 <= c.ts - newest_denom.ts <= _RESPIN_WINDOW_SECONDS):
                continue
            verdict = store.get(c.sha, newest_denom.ref) if store is not None else None
            if verdict == "remediation":
                failed.add(newest_denom.ref)
            elif verdict != "routine":
                candidates.append(
                    AdjudicationCandidate(
                        commit_sha=c.sha,
                        subject=c.subject,
                        release_ref=newest_denom.ref,
                        ts=c.ts,
                    )
                )

    return (
        CfrResult(
            failed=len(failed),
            total=len(denominator),
            unit=unit,
            pending_adjudications=len(candidates),
        ),
        candidates,
    )


# ── churn (ADR-004: cohort-blame survival at the maturation boundary) ────────


@dataclass(frozen=True)
class ChurnEntry:
    """One (cohort commit, touched file) unit of churn measurement."""

    sha: str
    ts: int
    path: str
    added_w: int
    surviving: int


@dataclass(frozen=True)
class ChurnResult:
    churned_loc: int = 0
    added_loc: int = 0
    files_skipped: int = 0
    partial: bool = False
    status: Literal["ok", "not_applicable"] = "ok"
    reason: str | None = None

    @property
    def ratio(self) -> float | None:
        return (self.churned_loc / self.added_loc) if self.added_loc > 0 else None


def _entry_order(entry: ChurnEntry) -> tuple[int, str, str]:
    # Descending added-LOC, then stable sha/path tiebreak — the deterministic
    # cap ordering (ADR-004; Codex finding on non-deterministic ratios).
    return (-entry.added_w, entry.sha, entry.path)


def classify_churn(
    entries: list[ChurnEntry] | tuple[ChurnEntry, ...],
    *,
    cohort_start: int,
    cohort_end: int,
    file_cap: int,
) -> ChurnResult:
    """Pure churn aggregation over pre-resolved survival stats.

    Entries outside the mature cohort are ignored (AC-005 invariance); the
    first ``file_cap`` entries in deterministic order are counted, the rest
    are reported as skipped (partial snapshot — baseline deltas are
    suppressed downstream). Skipped entries stay out of BOTH numerator and
    denominator so the ratio never mixes measured and unmeasured files.
    Empty mature cohort ⇒ explicit not_applicable, never a silent 0%.
    """
    cohort = sorted(
        (e for e in entries if cohort_start <= e.ts <= cohort_end),
        key=_entry_order,
    )
    if not cohort:
        return ChurnResult(
            status="not_applicable",
            reason=(
                "no matured commits inside the churn cohort window; commits "
                "younger than the maturation window are not yet measurable"
            ),
        )
    processed = cohort[:file_cap]
    skipped = len(cohort) - len(processed)
    churned = sum(max(0, e.added_w - e.surviving) for e in processed)
    added = sum(e.added_w for e in processed)
    return ChurnResult(
        churned_loc=churned,
        added_loc=added,
        files_skipped=skipped,
        partial=skipped > 0,
    )


# ── git adapter ──────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # REVIEW consensus P1 (code-reviewer + security-reviewer): catch the
    # subprocess failure modes HERE so every call site inherits the DeliveryMetricsError
    # → CLI exit-4 contract, not just _require_repo. A blame/log timeout on a huge
    # repo must surface as structured `{"status":"error"}`, never a raw traceback.
    try:
        return subprocess.run(  # noqa: S603 — args-list, timeout, no shell
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeliveryMetricsError(f"git {' '.join(args)} failed in {root}: {exc}") from exc


def _require_repo(root: Path) -> None:
    probe = _git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        raise DeliveryMetricsError(f"not a git work tree: {root}")


def _default_branch(root: Path, config: DeliveryMetricsConfig) -> str | None:
    """ADR-001 precedence: config → origin/HEAD → main → master → None."""
    if config.default_branch is not None:
        probe = _git(
            root, "rev-parse", "--verify", "--quiet", f"refs/heads/{config.default_branch}"
        )
        return config.default_branch if probe.returncode == 0 else None
    sym = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if sym.returncode == 0:
        name = sym.stdout.strip().rsplit("/", 1)[-1]
        if name:
            return name
    for name in ("main", "master"):
        if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}").returncode == 0:
            return name
    return None


def _parse_commits(raw: str) -> list[CommitInfo]:
    commits: list[CommitInfo] = []
    for record in raw.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split(_FIELD_SEP)
        if len(parts) < 4:
            continue
        sha, ts_raw, parents_raw, subject = parts[0], parts[1], parts[2], parts[3]
        body = parts[4] if len(parts) > 4 else ""
        sha = sha.strip()
        if not sha:
            continue
        commits.append(
            CommitInfo(
                sha=sha,
                subject=subject,
                ts=int(ts_raw),
                parents=tuple(p for p in parents_raw.split() if p),
                body=body.strip(),
            )
        )
    return commits


_LOG_FORMAT = f"%H{_FIELD_SEP}%ct{_FIELD_SEP}%P{_FIELD_SEP}%s{_FIELD_SEP}%b{_RECORD_SEP}"


def _range_commits(root: Path, rev_range: str, *, first_parent: bool = True) -> list[CommitInfo]:
    args = ["log", f"--format={_LOG_FORMAT}"]
    if first_parent:
        args.append("--first-parent")
    args.append(rev_range)
    out = _git(root, *args)
    if out.returncode != 0:
        raise DeliveryMetricsError(f"git log failed for {rev_range}: {out.stderr.strip()}")
    return _parse_commits(out.stdout)


@dataclass(frozen=True)
class _TagInfo:
    name: str
    ts: int
    commit_sha: str


def _matching_tags(root: Path, pattern: str) -> list[_TagInfo]:
    out = _git(
        root,
        "tag",
        "--list",
        pattern,
        # for-each-ref formats support %09 (tab), not %xNN; tag names cannot
        # contain tabs so the split is unambiguous.
        "--format=%(refname:short)%09%(creatordate:unix)%09%(*objectname)%09%(objectname)",
    )
    if out.returncode != 0:
        raise DeliveryMetricsError(f"git tag --list failed: {out.stderr.strip()}")
    tags: list[_TagInfo] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        name, ts_raw, peeled, obj = parts
        if not ts_raw.strip().isdigit():
            continue
        tags.append(_TagInfo(name=name, ts=int(ts_raw), commit_sha=(peeled or obj)))
    tags.sort(key=lambda t: (t.ts, t.name))
    return tags


def _collect_tag_releases(
    root: Path, tags: list[_TagInfo]
) -> tuple[list[ReleaseInfo], list[CommitInfo]]:
    releases: list[ReleaseInfo] = []
    prev: _TagInfo | None = None
    for tag in tags:
        rev_range = f"{prev.commit_sha}..{tag.commit_sha}" if prev else tag.commit_sha
        commits = _range_commits(root, rev_range)
        releases.append(
            ReleaseInfo(
                ref=tag.name,
                sha=tag.commit_sha,
                ts=tag.ts,
                unit="tag",
                commits=tuple(commits),
            )
        )
        prev = tag
    tail: list[CommitInfo] = []
    if prev is not None:
        head = _git(root, "rev-parse", "HEAD")
        if head.returncode == 0 and head.stdout.strip() != prev.commit_sha:
            tail = _range_commits(root, f"{prev.commit_sha}..HEAD")
    return releases, tail


def _collect_land_releases(root: Path, branch: str, *, since_ts: int) -> list[ReleaseInfo]:
    # --since is an optimization with margin; the exact window filter is the
    # pure layer's job (keeps the invariance property honest).
    since_iso = datetime.fromtimestamp(since_ts, tz=UTC) - timedelta(days=2)
    commits = _range_commits_with_args(
        root,
        [
            "log",
            f"--format={_LOG_FORMAT}",
            "--first-parent",
            f"--since={since_iso.isoformat()}",
            branch,
        ],
    )
    return [
        ReleaseInfo(ref=c.sha[:12], sha=c.sha, ts=c.ts, unit="task-land", commits=(c,))
        for c in commits
    ]


def _range_commits_with_args(root: Path, args: list[str]) -> list[CommitInfo]:
    out = _git(root, *args)
    if out.returncode != 0:
        raise DeliveryMetricsError(f"git log failed: {out.stderr.strip()}")
    return _parse_commits(out.stdout)


def compute_cfr(
    repo: Path | str,
    window_days: int = 28,
    *,
    config: DeliveryMetricsConfig | None = None,
    now: datetime | None = None,
    store: AdjudicationStore | None = None,
) -> CfrResult:
    result, _ = compute_cfr_full(repo, window_days, config=config, now=now, store=store)
    return result


def compute_cfr_full(
    repo: Path | str,
    window_days: int = 28,
    *,
    config: DeliveryMetricsConfig | None = None,
    now: datetime | None = None,
    store: AdjudicationStore | None = None,
) -> tuple[CfrResult, list[AdjudicationCandidate]]:
    """CFR over the rolling window ending at ``now`` (ADR-001).

    Unit selection is sticky: any tag matching ``tag_pattern`` anywhere in
    history pins unit='tag' (out-of-window-only tags → not_applicable, never
    a flap to task-land counting). ``paths`` scoping applies to churn only —
    a release is repo-wide by definition.
    """
    cfg = config or DeliveryMetricsConfig(tag_pattern="v*")
    root = Path(repo)
    _require_repo(root)
    now_dt = now if now is not None else datetime.now(tz=UTC)
    window_end = int(now_dt.timestamp())
    window_start = window_end - window_days * 86_400

    tags = _matching_tags(root, cfg.tag_pattern)
    if tags:
        releases, tail = _collect_tag_releases(root, tags)
        return classify_cfr_full(
            releases,
            tail,
            window_start=window_start,
            window_end=window_end,
            unit="tag",
            store=store,
        )

    branch = _default_branch(root, cfg)
    if branch is None:
        return (
            CfrResult(
                status="not_applicable",
                unit=None,
                reason="no matching tags and no resolvable default branch",
            ),
            [],
        )
    land_releases = _collect_land_releases(root, branch, since_ts=window_start)
    return classify_cfr_full(
        land_releases,
        [],
        window_start=window_start,
        window_end=window_end,
        unit="task-land",
        store=store,
    )


# ── churn git adapter ────────────────────────────────────────────────────────

_BLAME_HEADER = re.compile(r"^[0-9a-f]{40} \d+ \d+")


@dataclass(frozen=True)
class _ChainNode:
    """One first-parent commit with its whitespace-insensitive numstat."""

    sha: str
    ts: int
    added: tuple[tuple[str, int], ...]  # (path, added>0) rows
    touched: frozenset[str]  # every text path the commit changed at all


def _collect_chain_numstat(
    root: Path, branch: str, paths: list[str], *, since_ts: int
) -> list[_ChainNode]:
    """ONE batched `git log --numstat -w` over the branch (newest-first).

    Replaces per-commit `git diff` calls — the 2000-commit perf budget dies on
    per-entry subprocess fan-out, not on parsing (P3 perf regression).
    """
    since_iso = (datetime.fromtimestamp(since_ts, tz=UTC) - timedelta(days=2)).isoformat()
    args = [
        "log",
        f"--format={_RECORD_SEP}%H{_FIELD_SEP}%ct",
        "--first-parent",
        "-w",
        "--numstat",
        f"--since={since_iso}",
        branch,
    ]
    if paths:
        args += ["--", *paths]
    out = _git(root, *args)
    if out.returncode != 0:
        raise DeliveryMetricsError(f"git log --numstat failed: {out.stderr.strip()}")
    nodes: list[_ChainNode] = []
    for record in out.stdout.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        lines = record.splitlines()
        header = lines[0].split(_FIELD_SEP)
        if len(header) != 2:
            continue
        sha, ts_raw = header
        added_rows: list[tuple[str, int]] = []
        touched: set[str] = set()
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) != 3 or parts[0] == "-":  # '-' = binary file
                continue
            touched.add(parts[2])
            added = int(parts[0])
            if added > 0:
                added_rows.append((parts[2], added))
        nodes.append(
            _ChainNode(sha=sha, ts=int(ts_raw), added=tuple(added_rows), touched=frozenset(touched))
        )
    return nodes


def _name_status(root: Path, from_sha: str, to_sha: str) -> dict[str, tuple[str, str]]:
    """path-at-from → (status letter, path-at-to) with rename detection."""
    if from_sha == to_sha:
        return {}
    out = _git(root, "diff", "--name-status", "-M", from_sha, to_sha)
    if out.returncode != 0:
        raise DeliveryMetricsError(f"git diff --name-status failed: {out.stderr.strip()}")
    mapping: dict[str, tuple[str, str]] = {}
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0]:
            continue
        status = parts[0][0]
        if status == "R" and len(parts) == 3:
            mapping[parts[1]] = ("R", parts[2])
        elif len(parts) >= 2:
            mapping[parts[1]] = (status, parts[1])
    return mapping


def _blame_attributed(root: Path, rev: str, file_path: str, *, sha: str, origin_path: str) -> int:
    """Lines in ``file_path`` at ``rev`` that blame attributes to (sha, origin_path).

    ``filename`` in --line-porcelain is the path in the ORIGIN commit, which is
    what keeps rename-follow and cross-file -C moves bucketed to the cohort
    commit's own touched file.
    """
    out = _git(root, "blame", "-w", "-M", "-C", "--line-porcelain", rev, "--", file_path)
    if out.returncode != 0:
        return 0  # file absent at rev (deleted) — zero survival
    count = 0
    current_sha = ""
    current_fn = ""
    for line in out.stdout.splitlines():
        if _BLAME_HEADER.match(line):
            current_sha = line.split(" ", 1)[0]
            # REVIEW defensive P2 (Codex): reset the filename at each header so a
            # block that (unexpectedly) omits its `filename ` line can never inherit
            # the prior block's origin path and overcount survival.
            current_fn = ""
        elif line.startswith("filename "):
            current_fn = line[len("filename ") :]
        elif line.startswith("\t") and current_sha == sha and current_fn == origin_path:
            count += 1
    return count


def _surviving_lines(
    root: Path,
    sha: str,
    path: str,
    added: int,
    boundary_sha: str,
    status_map_lazy: dict[tuple[str, str], dict[str, tuple[str, str]] | None],
    destinations: list[str],
) -> int:
    """Survival with lazy rename/delete resolution + same-commit -C destinations.

    Destination candidates are pre-computed by the caller from the batched
    numstat map: only files touched by a commit that ALSO touched ``path``
    qualify (single ``-C`` detects moves from files modified in the same
    commit) — this bounds blame fan-out to genuine move suspects instead of
    every file changed during maturation (the 41s perf regression).
    """
    surviving = _blame_attributed(root, boundary_sha, path, sha=sha, origin_path=path)
    if surviving >= added:
        return surviving
    # Own-path blame under-counted (or the file is gone) — resolve rename/delete.
    key = (sha, boundary_sha)
    status_map = status_map_lazy.get(key)
    if status_map is None:
        status_map = _name_status(root, sha, boundary_sha)
        status_map_lazy[key] = status_map
    status, mapped = status_map.get(path, ("M", path))
    if status == "D":
        surviving = 0
    elif mapped != path:
        surviving = _blame_attributed(root, boundary_sha, mapped, sha=sha, origin_path=path)
        if surviving >= added:
            return surviving
    for dest in destinations:
        if dest in {path, mapped}:
            continue
        surviving += _blame_attributed(root, boundary_sha, dest, sha=sha, origin_path=path)
        if surviving >= added:
            break
    return surviving


def compute_churn(
    repo: Path | str,
    window_days: int = 14,
    *,
    cohort_days: int | None = None,
    config: DeliveryMetricsConfig | None = None,
    now: datetime | None = None,
) -> ChurnResult:
    """Post-merge churn: cohort-blame survival at the maturation boundary.

    ``window_days`` is the MATURATION period (how long a commit ages before
    churn is judged); the cohort spans ``cohort_days`` before that boundary —
    two parameters by design (plan-validator advisory). Survival is evaluated
    at the last first-parent commit ≤ land_time + maturation, so rewrites
    after day-``window_days`` never count (SPEC "within 2 weeks").
    """
    cfg = config or DeliveryMetricsConfig()
    root = Path(repo)
    _require_repo(root)
    now_dt = now if now is not None else datetime.now(tz=UTC)
    now_ts = int(now_dt.timestamp())
    maturation_s = window_days * 86_400
    cohort_span_s = (cohort_days if cohort_days is not None else cfg.churn_cohort_days) * 86_400
    cohort_end = now_ts - maturation_s
    cohort_start = cohort_end - cohort_span_s

    branch = _default_branch(root, cfg)
    if branch is None:
        return ChurnResult(status="not_applicable", reason="no resolvable default branch")

    chain = _collect_chain_numstat(root, branch, cfg.paths, since_ts=cohort_start)  # newest-first
    cohort_nodes = [n for n in chain if cohort_start <= n.ts <= cohort_end]

    raw: list[tuple[_ChainNode, str, int]] = []
    for node in cohort_nodes:
        for path, added in node.added:
            raw.append((node, path, added))
    # Resolve survival only for the entries the cap will actually count —
    # same deterministic order as classify_churn, so the two layers agree.
    raw.sort(key=lambda t: (-t[2], t[0].sha, t[1]))
    status_cache: dict[tuple[str, str], dict[str, tuple[str, str]] | None] = {}
    boundary_cache: dict[str, tuple[str, int]] = {}
    entries: list[ChurnEntry] = []
    for node, path, added in raw[: cfg.blame_file_cap]:
        cached = boundary_cache.get(node.sha)
        if cached is None:
            boundary_ts = node.ts + maturation_s
            cached = next(
                ((c.sha, c.ts) for c in chain if c.ts <= boundary_ts), (node.sha, node.ts)
            )
            boundary_cache[node.sha] = cached
        boundary_sha, _ = cached
        # Same-commit -C destination candidates: files changed by any commit in
        # (node..boundary] that ALSO changed `path` in that same commit.
        destinations = sorted(
            {
                other
                for k in chain
                if node.ts < k.ts <= node.ts + maturation_s and path in k.touched
                for other in k.touched
                if other != path
            }
        )
        surviving = _surviving_lines(
            root, node.sha, path, added, boundary_sha, status_cache, destinations
        )
        entries.append(
            ChurnEntry(sha=node.sha, ts=node.ts, path=path, added_w=added, surviving=surviving)
        )
    for node, path, added in raw[cfg.blame_file_cap :]:
        entries.append(ChurnEntry(sha=node.sha, ts=node.ts, path=path, added_w=added, surviving=0))
    return classify_churn(
        entries, cohort_start=cohort_start, cohort_end=cohort_end, file_cap=cfg.blame_file_cap
    )


# ── ledger (ADR-005) ─────────────────────────────────────────────────────────

LEDGER_RELPATH = Path(".claude/observability/delivery-metrics.jsonl")
_REASON_MAX = 200
_SNAPSHOT_REASON_MAX = 300


class AdjudicationRow(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    event: Literal["adjudication"] = "adjudication"
    ts: str = Field(max_length=64)
    commit_sha: str = Field(max_length=64)
    release_ref: str = Field(max_length=200)
    verdict: Literal["remediation", "routine"]
    reason: str = Field(max_length=_REASON_MAX)
    algo_version: int
    config_hash: str = Field(max_length=32)


class SnapshotCfr(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    failed: int
    total: int
    unit: str | None = Field(default=None, max_length=20)
    status: str = Field(max_length=20)
    reason: str | None = Field(default=None, max_length=_SNAPSHOT_REASON_MAX)


class SnapshotChurn(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    churned_loc: int
    added_loc: int
    ratio: float | None = None
    files_skipped: int
    partial: bool
    status: str = Field(max_length=20)
    reason: str | None = Field(default=None, max_length=_SNAPSHOT_REASON_MAX)


class SnapshotRow(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    event: Literal["snapshot"] = "snapshot"
    ts: str = Field(max_length=64)
    window_days: int
    churn_maturation_days: int
    churn_cohort_days: int
    window_start: int
    window_end: int
    cfr: SnapshotCfr
    churn: SnapshotChurn
    baseline_cfr_delta: float | None = None
    baseline_churn_delta: float | None = None
    head_sha: str = Field(max_length=64)
    config_hash: str = Field(max_length=32)
    algo_version: int
    pending_adjudications: int


def _append_atomic_line(path: Path, line: str) -> None:
    """Single O_APPEND write ≤ PIPE_BUF (4096) — codex_ledger pattern (ADR-005)."""
    payload = line if line.endswith("\n") else line + "\n"
    encoded = payload.encode("utf-8")
    if len(encoded) > 4096:
        raise ValueError(
            f"ledger line {len(encoded)} bytes exceeds PIPE_BUF (4096); "
            "field max_length guards should have prevented this"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        view = memoryview(encoded)
        written = 0
        while written < len(view):
            n = os.write(fd, view[written:])
            if n == 0:
                raise OSError("os.write returned 0 on ledger append")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)


def _config_hash(cfg: DeliveryMetricsConfig) -> str:
    canonical = json.dumps(cfg.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _read_ledger_rows(ledger_path: Path) -> list[dict[str, object]]:
    if not ledger_path.is_file():
        return []
    rows: list[dict[str, object]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue  # malformed line — skip, never poison the whole read
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


class JsonlAdjudicationStore:
    """Ledger-backed verdict store keyed (commit_sha, release_ref, algo, config)."""

    def __init__(self, ledger_path: Path, *, algo_version: int, config_hash: str) -> None:
        self._path = ledger_path
        self._algo = algo_version
        self._cfg_hash = config_hash
        self._cache: dict[tuple[str, str], str] = {}
        for row in _read_ledger_rows(ledger_path):
            if (
                row.get("event") == "adjudication"
                and row.get("algo_version") == algo_version
                and row.get("config_hash") == config_hash
            ):
                sha = str(row.get("commit_sha", ""))
                ref = str(row.get("release_ref", ""))
                self._cache[(sha, ref)] = str(row.get("verdict", ""))

    def get(self, commit_sha: str, release_ref: str) -> str | None:
        return self._cache.get((commit_sha, release_ref))

    def put(self, *, commit_sha: str, release_ref: str, verdict: str, reason: str) -> None:
        if verdict not in ("remediation", "routine"):
            raise DeliveryMetricsError(f"invalid verdict: {verdict!r}")
        row = AdjudicationRow(
            ts=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            commit_sha=commit_sha[:64],
            release_ref=release_ref[:200],
            verdict=verdict,  # type: ignore[arg-type]
            reason=reason[:_REASON_MAX],
            algo_version=self._algo,
            config_hash=self._cfg_hash,
        )
        _append_atomic_line(self._path, json.dumps(row.model_dump(), ensure_ascii=False))
        self._cache[(commit_sha[:64], release_ref[:200])] = verdict


class _AssumeRoutineStore:
    """Overlay treating unresolved candidates as routine — headless compute only."""

    def __init__(self, inner: AdjudicationStore) -> None:
        self._inner = inner

    def get(self, commit_sha: str, release_ref: str) -> str | None:
        return self._inner.get(commit_sha, release_ref) or "routine"

    def put(self, *, commit_sha: str, release_ref: str, verdict: str, reason: str) -> None:
        raise DeliveryMetricsError("assume-routine overlay is read-only")


# ── CLI (ADR-006/007) ────────────────────────────────────────────────────────


def _load_cli_config(root: Path) -> DeliveryMetricsConfig | None:
    """None ⇒ feature disabled by the project harness (CLI exit 2, zero writes).

    A root WITHOUT harness.yaml proceeds with defaults: direct module
    invocation is explicit intent; the enable gate protects the rendered
    command/hook surface (AC-009).
    """
    import yaml

    harness_yaml = root / ".claude" / "harness.yaml"
    if not harness_yaml.is_file():
        return DeliveryMetricsConfig()
    from harness_maker.io_utils import load_harness_yaml

    try:
        data = load_harness_yaml(harness_yaml)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        # REVIEW P2 (round 1 + re-review): narrowed from bare `except Exception`
        # — a genuinely unreadable/corrupt/mis-encoded harness.yaml fails closed
        # (disabled), but a programming error inside load_harness_yaml now
        # propagates instead of masquerading as "feature disabled". UnicodeDecodeError
        # (a ValueError, not OSError) is the non-UTF8-file case re-review caught.
        return None
    raw = data.get("delivery_metrics")
    cfg = DeliveryMetricsConfig()
    if isinstance(raw, dict):
        clean = {k: v for k, v in raw.items() if k in DeliveryMetricsConfig.model_fields}
        try:
            cfg = DeliveryMetricsConfig.model_validate(clean)
        except ValidationError:
            cfg = DeliveryMetricsConfig()
    return cfg if cfg.enabled else None


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _print_json(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _ratio(failed: int, total: int) -> float | None:
    return (failed / total) if total > 0 else None


def _baseline_deltas(
    prior: list[dict[str, object]],
    cfr: CfrResult,
    churn: ChurnResult,
) -> tuple[float | None, float | None]:
    """Delta vs the newest prior OK snapshot; suppressed for partial/N-A runs."""
    cfr_delta: float | None = None
    churn_delta: float | None = None
    cur_cfr_ratio = _ratio(cfr.failed, cfr.total) if cfr.status == "ok" else None
    cur_churn_ratio = churn.ratio if (churn.status == "ok" and not churn.partial) else None
    for row in prior:  # prior is newest-first
        if row.get("event") != "snapshot":
            continue
        prev_cfr = row.get("cfr")
        if cfr_delta is None and cur_cfr_ratio is not None and isinstance(prev_cfr, dict):
            prev_ratio = _ratio(int(prev_cfr.get("failed", 0)), int(prev_cfr.get("total", 0)))
            if prev_cfr.get("status") == "ok" and prev_ratio is not None:
                cfr_delta = cur_cfr_ratio - prev_ratio
        prev_churn = row.get("churn")
        if churn_delta is None and cur_churn_ratio is not None and isinstance(prev_churn, dict):
            prev_cr = prev_churn.get("ratio")
            if (
                prev_churn.get("status") == "ok"
                and not prev_churn.get("partial", False)
                and isinstance(prev_cr, (int, float))
            ):
                churn_delta = cur_churn_ratio - float(prev_cr)
        if cfr_delta is not None and churn_delta is not None:
            break
    return cfr_delta, churn_delta


def _cmd_candidates(root: Path, cfg: DeliveryMetricsConfig, now: datetime) -> int:
    store = JsonlAdjudicationStore(
        root / LEDGER_RELPATH, algo_version=ALGO_VERSION, config_hash=_config_hash(cfg)
    )
    _, candidates = compute_cfr_full(root, cfg.cfr_window_days, config=cfg, now=now, store=store)
    _print_json(
        {
            "status": "ok",
            "candidates": [asdict(c) for c in candidates],
            "algo_version": ALGO_VERSION,
        }
    )
    return 0


def _cmd_adjudicate(root: Path, cfg: DeliveryMetricsConfig, args: argparse.Namespace) -> int:
    store = JsonlAdjudicationStore(
        root / LEDGER_RELPATH, algo_version=ALGO_VERSION, config_hash=_config_hash(cfg)
    )
    store.put(
        commit_sha=args.commit, release_ref=args.release, verdict=args.verdict, reason=args.reason
    )
    _print_json({"status": "recorded", "commit_sha": args.commit, "verdict": args.verdict})
    return 0


def _cmd_compute(
    root: Path, cfg: DeliveryMetricsConfig, now: datetime, *, assume_routine: bool
) -> int:
    ledger_path = root / LEDGER_RELPATH
    cfg_hash = _config_hash(cfg)
    store = JsonlAdjudicationStore(ledger_path, algo_version=ALGO_VERSION, config_hash=cfg_hash)
    cfr, candidates = compute_cfr_full(root, cfg.cfr_window_days, config=cfg, now=now, store=store)
    if candidates and not assume_routine:
        _print_json(
            {
                "status": "pending_adjudications",
                "candidates": [asdict(c) for c in candidates],
                "hint": "adjudicate each via the `adjudicate` subcommand, then re-run compute",
            }
        )
        return 3
    if candidates:
        overlay = _AssumeRoutineStore(store)
        cfr, _ = compute_cfr_full(root, cfg.cfr_window_days, config=cfg, now=now, store=overlay)
    churn = compute_churn(
        root,
        cfg.churn_maturation_days,
        cohort_days=cfg.churn_cohort_days,
        config=cfg,
        now=now,
    )
    prior = list(reversed(_read_ledger_rows(ledger_path)))  # newest-first
    cfr_delta, churn_delta = _baseline_deltas(prior, cfr, churn)
    head = _git(root, "rev-parse", "HEAD")
    now_ts = int(now.timestamp())
    row = SnapshotRow(
        ts=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_days=cfg.cfr_window_days,
        churn_maturation_days=cfg.churn_maturation_days,
        churn_cohort_days=cfg.churn_cohort_days,
        window_start=now_ts - cfg.cfr_window_days * 86_400,
        window_end=now_ts,
        cfr=SnapshotCfr(
            failed=cfr.failed,
            total=cfr.total,
            unit=cfr.unit,
            status=cfr.status,
            reason=(cfr.reason or None) and str(cfr.reason)[:_SNAPSHOT_REASON_MAX],
        ),
        churn=SnapshotChurn(
            churned_loc=churn.churned_loc,
            added_loc=churn.added_loc,
            ratio=churn.ratio,
            files_skipped=churn.files_skipped,
            partial=churn.partial,
            status=churn.status,
            reason=(churn.reason or None) and str(churn.reason)[:_SNAPSHOT_REASON_MAX],
        ),
        baseline_cfr_delta=cfr_delta,
        baseline_churn_delta=churn_delta,
        head_sha=head.stdout.strip()[:64] if head.returncode == 0 else "",
        config_hash=cfg_hash,
        algo_version=ALGO_VERSION,
        pending_adjudications=len(candidates),
    )
    payload = row.model_dump()
    _append_atomic_line(ledger_path, json.dumps(payload, ensure_ascii=False))
    _print_json(payload)
    return 0


def _cmd_trend(root: Path, limit: int) -> int:
    rows = _read_ledger_rows(root / LEDGER_RELPATH)
    snapshots = [r for r in reversed(rows) if r.get("event") == "snapshot"][:limit]
    _print_json({"status": "ok", "snapshots": snapshots})
    return 0


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m harness_maker.delivery_metrics")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", default=".", help="project root (resolved from any cwd)")

    p_cand = sub.add_parser("candidates", help="list ambiguous fix commits lacking verdicts")
    add_common(p_cand)
    p_cand.add_argument("--now", default=None, help="ISO instant for window math (testing)")

    p_adj = sub.add_parser("adjudicate", help="record an LLM verdict for a candidate")
    add_common(p_adj)
    p_adj.add_argument("--commit", required=True)
    p_adj.add_argument("--release", required=True)
    p_adj.add_argument("--verdict", required=True, choices=["remediation", "routine"])
    p_adj.add_argument("--reason", required=True)

    p_comp = sub.add_parser("compute", help="compute CFR+churn and append a snapshot")
    add_common(p_comp)
    p_comp.add_argument("--now", default=None)
    p_comp.add_argument(
        "--assume-routine",
        action="store_true",
        help="headless: treat unresolved candidates as routine (recorded, not hidden)",
    )

    p_trend = sub.add_parser("trend", help="print snapshot rows, newest first")
    add_common(p_trend)
    p_trend.add_argument("--limit", type=int, default=50)

    return parser


def main(argv: list[str] | None = None) -> int:
    from harness_maker import command_registry

    _guard = command_registry.guard_or_none("delivery_metrics", argv)
    if _guard is not None:
        return _guard
    args = _build_argparser().parse_args(argv)
    root = Path(args.root).resolve()
    cfg = _load_cli_config(root)
    if cfg is None:
        _print_json({"status": "disabled", "hint": "set delivery_metrics.enabled in harness.yaml"})
        return 2
    try:
        if args.command == "trend":
            return _cmd_trend(root, args.limit)
        _require_repo(root)
        if args.command == "candidates":
            return _cmd_candidates(root, cfg, _parse_now(args.now))
        if args.command == "adjudicate":
            return _cmd_adjudicate(root, cfg, args)
        if args.command == "compute":
            return _cmd_compute(root, cfg, _parse_now(args.now), assume_routine=args.assume_routine)
    except DeliveryMetricsError as exc:
        sys.stderr.write(json.dumps({"status": "error", "error": str(exc)}) + "\n")
        return 4
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
