"""Review effect ledger: what the one review caught, what escaped later, and seeded recall."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import random
import re
import stat
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker import __version__, command_registry, ledger_exclusions
from harness_maker.delivery_metrics import _REMEDIATION_SUBJECT
from harness_maker.io_utils import append_atomic_line, atomic_write

LEDGER_REL = Path(".claude") / "observability" / "review-effect.jsonl"
SCHEMA_VERSION = 1

_SEVERE = frozenset({"P0", "P1"})
_SEVERITY_RE = re.compile(r"^(P[0-3])\b", re.IGNORECASE)
_DISPOSITION_RE = re.compile(r"^[a-z][a-z-]*")
_DECOR = "*`_ "
_COUNTED = ("parsed", "none")
_REASON_MAX = 200
_GIT_TIMEOUT = 30
#: The seed match window, in lines (SPEC AC-009).
WINDOW = 3


def _warn(message: str) -> None:
    print(f"review_effect: {message}", file=sys.stderr)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=False,
    )


def _base(root: Path) -> Path:
    # One resolver for every ledger: a linked worktree or nested repo must not grow its own copy.
    from harness_maker.second_opinion_invoke import resolve_base_root

    return resolve_base_root(Path(root).resolve())


def _row(event: str, slug: str, **fields: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event": event,
        "ts": _now(),
        "slug": slug,
        "harness_version": __version__,
        **fields,
    }


def read_rows(base: Path) -> list[dict[str, Any]]:
    path = base / LEDGER_REL
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue  # a torn line is skipped, never allowed to poison the read
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _kept_rows(base: Path) -> list[dict[str, Any]]:
    exclusions = ledger_exclusions.load(base / LEDGER_REL.parent)
    return [r for r in read_rows(base) if not ledger_exclusions.is_excluded(r, exclusions)]


def _append(base: Path, row: dict[str, Any]) -> Path:
    path = base / LEDGER_REL
    append_atomic_line(path, json.dumps(row, sort_keys=True, ensure_ascii=False))
    return path


# ── REVIEW table ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReviewParse:
    status: str
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    severe_accepted: int = 0
    unrecognized_n: int = 0


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def parse_review(text: str) -> ReviewParse:
    """Count findings by severity × disposition from the table execute Step 6 writes."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.rstrip() == "## Findings"), None)
    if start is None:
        return ReviewParse("unparseable")
    section: list[str] = []
    for ln in lines[start + 1 :]:
        if ln.startswith("## ") or ln.startswith("# "):
            break
        section.append(ln)
    body = [ln for ln in section if ln.strip()]
    if body and body[0].strip().lower().startswith("none"):
        return ReviewParse("none")
    table = [ln for ln in body if ln.lstrip().startswith("|")]
    if not table:
        return ReviewParse("unparseable")
    header = [c.lower() for c in _cells(table[0])]
    if "severity" not in header or "disposition" not in header:
        return ReviewParse("unparseable")
    si, di = header.index("severity"), header.index("disposition")
    counts: dict[str, dict[str, int]] = {}
    severe = unrecognized = 0
    odd: list[str] = []
    for ln in table[1:]:
        cells = _cells(ln)
        if _is_separator(cells):
            continue
        cells += [""] * (len(header) - len(cells))
        raw_sev = cells[si].strip(_DECOR)
        m = _SEVERITY_RE.match(raw_sev)
        sev = m.group(1).upper() if m else "unrecognized"
        if m is None:
            unrecognized += 1
            odd.append(raw_sev)
        dm = _DISPOSITION_RE.match(cells[di].strip(_DECOR).lower())
        disp = dm.group(0) if dm else "unknown"
        counts.setdefault(sev, {})
        counts[sev][disp] = counts[sev].get(disp, 0) + 1
        if sev in _SEVERE and disp == "accepted":
            severe += 1
    if odd:
        _warn(f"unrecognized severity {sorted(set(odd))!r}: counted as 'unrecognized'")
    return ReviewParse("parsed", counts, severe, unrecognized)


def _review_files(worktree: Path, slug: str) -> list[Path]:
    pattern = re.compile(rf"^REVIEW-{re.escape(slug)}-(\d{{4}}-\d{{2}}-\d{{2}})\.md$")
    docs = worktree / "work-docs"
    if not docs.is_dir():
        return []
    hits = [(m.group(1), p) for p in docs.iterdir() if (m := pattern.match(p.name))]
    return [p for _, p in sorted(hits)]


def record_review(worktree: Path, base: Path, slug: str) -> dict[str, Any]:
    """Append this task's one review row. Raises on any failure; the land hook catches it."""
    root = _base(base)
    head = _git(worktree, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {head.stderr.strip()}")
    commit = head.stdout.strip()
    for r in read_rows(root):
        if r.get("event") == "review" and r.get("slug") == slug and r.get("commit") == commit:
            return {"status": "exists", "row_status": r.get("status")}
    files = _review_files(worktree, slug)
    if files:
        latest = files[-1]
        parsed = parse_review(latest.read_text(encoding="utf-8"))
        if parsed.status == "unparseable":
            _warn(f"{latest.name} has no parseable '## Findings' table")
        review_file: str | None = latest.name
    else:
        parsed, review_file = ReviewParse("absent"), None
    row = _row(
        "review",
        slug,
        commit=commit,
        review_file=review_file,
        status=parsed.status,
        counts=parsed.counts,
        severe_accepted=parsed.severe_accepted,
        unrecognized_n=parsed.unrecognized_n,
    )
    path = _append(root, row)
    return {"status": "written", "row_status": parsed.status, "path": str(path)}


# ── escapes ──────────────────────────────────────────────────────────────────


def recorded_escape_commits(rows: Sequence[dict[str, Any]]) -> set[str]:
    return {str(r.get("commit")) for r in rows if r.get("event") == "escape"}


def _epoch(ts: str) -> float | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _hunks(diff: str, side: str) -> list[tuple[str, int, int]]:
    """(path, start, count) per hunk on the `old` or `new` side of a `-U0` diff.

    A `---`/`+++` line is a header only between `diff --git` and the first `@@`: inside a hunk
    it is a changed line whose text starts with `-- `/`++ `. Git appends a TAB to a header path
    that contains a space.
    """
    marker, prefix, field = ("--- ", "--- a/", 1) if side == "old" else ("+++ ", "+++ b/", 2)
    out: list[tuple[str, int, int]] = []
    path: str | None = None
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_header, path = True, None
        elif in_header and line.startswith(marker):
            path = line[len(prefix) :].rstrip("\t") if line.startswith(prefix) else None
        elif line.startswith("@@"):
            in_header = False
            if path is None:
                continue
            start, _, count = line.split(" ")[field][1:].partition(",")
            out.append((path, int(start), int(count) if count else 1))
    return out


def _hint_slugs(root: Path, fix: str) -> list[str]:
    if _git(root, "rev-parse", "--verify", "--quiet", f"{fix}^").returncode != 0:
        return []
    diff = _git(root, "diff", "-U0", "--no-color", f"{fix}^", fix)
    blamed: set[str] = set()
    for old_path, start, n in _hunks(diff.stdout, "old"):
        if n == 0:
            continue
        # --porcelain names boundary commits in full; `-l` prints them as ^ + 39 hex.
        out = _git(root, "blame", "--porcelain", "-L", f"{start},+{n}", f"{fix}^", "--", old_path)
        for bl in out.stdout.splitlines():
            m = re.match(r"([0-9a-f]{40}) \d+ \d+", bl)
            if m:
                blamed.add(m.group(1))
    slugs: set[str] = set()
    for sha in blamed:
        names = _git(root, "show", "--name-only", "--format=", sha).stdout.splitlines()
        for name in names:
            m = re.fullmatch(r"specs/SPEC-(.+)\.md", name.strip())
            if m:
                slugs.add(m.group(1))
    return sorted(slugs)


def escape_candidates(root: Path) -> list[dict[str, Any]]:
    """Remediation commits since measurement began that no escape row has judged yet."""
    base = _base(root)
    rows = _kept_rows(base)
    stamps = [r.get("ts") for r in rows if r.get("event") == "review"]
    epochs = [e for s in stamps if isinstance(s, str) and (e := _epoch(s)) is not None]
    if len(epochs) < len(stamps):
        _warn(f"{len(stamps) - len(epochs)} review row(s) with an unreadable ts were skipped")
    if not epochs:
        _warn("no review rows in the ledger yet — nothing to attribute")
        return []
    cutoff = min(epochs)
    done = recorded_escape_commits(read_rows(base))
    log = _git(base, "log", "--first-parent", "--reverse", "--format=%H%x00%ct%x00%s", "HEAD")
    out: list[dict[str, Any]] = []
    for line in log.stdout.splitlines():
        sha, ct, subject = line.split("\x00", 2)
        if int(ct) < cutoff or sha in done or not _REMEDIATION_SUBJECT.search(subject):
            continue
        out.append(
            {
                "commit": sha,
                "subject": subject,
                "committed_at": datetime.fromtimestamp(int(ct), UTC).isoformat(),
                "hint_slugs": _hint_slugs(base, sha),
            }
        )
    return out


def record_escape(
    root: Path,
    *,
    commit: str,
    verdict: str,
    introduced_by: str,
    flagged: str,
    reviewable: str,
    reason: str,
) -> Path:
    if not commit or len(commit) > 64:
        raise ValueError(f"--commit {commit!r} is not a commit id")
    if len(reason) > _REASON_MAX:
        raise ValueError(f"--reason is {len(reason)} chars; the limit is {_REASON_MAX}")
    base = _base(root)
    resolved = _git(base, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
    if resolved.returncode == 0:
        commit = resolved.stdout.strip()
    elif re.fullmatch(r"[0-9a-f]{40}", commit):
        _warn(f"{commit} is not in this clone; recorded as given")
    else:
        raise ValueError(f"--commit {commit!r} does not resolve to a commit here")
    if commit in recorded_escape_commits(read_rows(base)):
        raise FileExistsError(f"commit {commit} already has an escape row")
    row = _row(
        "escape",
        introduced_by,
        commit=commit,
        verdict=verdict,
        flagged=flagged,
        reviewable=reviewable,
        reason=reason,
    )
    return _append(base, row)


# ── seeded recall ────────────────────────────────────────────────────────────


class DirtyTreeError(RuntimeError):
    pass


_CMP_FLIP = {"<=": "<", "<": "<=", ">=": ">", ">": ">=", "==": "!=", "!=": "=="}
_CMP_TYPES = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)


def _added_lines(root: Path, base: str) -> dict[str, set[int]]:
    diff = _git(root, "diff", "-U0", "--no-color", base, "HEAD", "--", "*.py")
    if diff.returncode != 0:
        raise ValueError(f"git diff {base}..HEAD failed: {diff.stderr.strip()}")
    out: dict[str, set[int]] = {}
    for path, start, n in _hunks(diff.stdout, "new"):
        out.setdefault(path, set()).update(range(start, start + n))
    return out


def _gap(a: ast.expr, b: ast.expr, ln: int, text: bytes) -> tuple[int, int] | None:
    """The operator gap after `a` on line `ln`; it runs to end of line when `b` wraps."""
    if a.end_lineno != ln or a.end_col_offset is None:
        return None
    return a.end_col_offset, (b.col_offset if b.lineno == ln else len(text.rstrip(b"\r")))


def _options(
    tree: ast.AST, lines: list[bytes], wanted: set[int]
) -> dict[int, list[tuple[str, int, int, bytes]]]:
    """Per line: (operator, start byte, end byte, replacement) choices for one textual edit."""
    opts: dict[int, list[tuple[str, int, int, bytes]]] = {}
    for node in ast.walk(tree):
        ln = getattr(node, "lineno", None)
        if ln is None or ln not in wanted:
            continue
        text = lines[ln - 1]
        if isinstance(node, ast.Compare) and isinstance(node.ops[0], _CMP_TYPES):
            span = _gap(node.left, node.comparators[0], ln, text)
            if span is None:
                continue
            lo, hi = span
            gap = text[lo:hi].decode("utf-8")
            op = gap.strip()
            if op in _CMP_FLIP:
                opts.setdefault(ln, []).append(
                    ("cmp-flip", lo, hi, gap.replace(op, _CMP_FLIP[op], 1).encode("utf-8"))
                )
        elif isinstance(node, ast.BoolOp) and len(node.values) >= 2:
            span = _gap(node.values[0], node.values[1], ln, text)
            if span is None:
                continue
            lo, hi = span
            gap = text[lo:hi].decode("utf-8")
            word = gap.strip()
            if word in ("and", "or"):
                swap = "or" if word == "and" else "and"
                opts.setdefault(ln, []).append(
                    ("boolop-swap", lo, hi, gap.replace(word, swap, 1).encode("utf-8"))
                )
        elif (
            isinstance(node, ast.Constant)
            and type(node.value) is int
            and node.end_lineno == ln
            and node.end_col_offset is not None
        ):
            lo, hi = node.col_offset, node.end_col_offset
            opts.setdefault(ln, []).append(
                ("const-off-by-one", lo, hi, str(node.value + 1).encode("utf-8"))
            )
    return opts


def seed(root: Path, *, base: str, count: int, seed: int) -> list[dict[str, Any]]:
    """Plant up to `count` deterministic defects on the task diff's own executable lines."""
    root = Path(root).resolve()
    status = _git(root, "status", "--porcelain")
    if status.returncode != 0:
        raise ValueError(f"{root} is not a git checkout: {status.stderr.strip()}")
    if status.stdout.strip():
        dirty = sorted({ln[3:] for ln in status.stdout.splitlines()})
        raise DirtyTreeError(", ".join(dirty))
    choices: list[tuple[str, int, list[tuple[str, int, int, bytes]]]] = []
    sources: dict[str, list[bytes]] = {}
    for rel, wanted in sorted(_added_lines(root, base).items()):
        path = root / rel
        if path.is_symlink() or not path.is_file():
            continue
        raw = path.read_bytes()
        try:
            tree = ast.parse(raw)
        except SyntaxError:
            continue
        lines = raw.split(b"\n")
        sources[rel] = lines
        for ln, opts in sorted(_options(tree, lines, wanted).items()):
            choices.append((rel, ln, sorted(opts)))
    rng = random.Random(seed)
    picked = sorted(rng.sample(choices, min(count, len(choices))), key=lambda c: (c[0], c[1]))
    manifest: list[dict[str, Any]] = []
    for rel, ln, opts in picked:
        operator, lo, hi, repl = rng.choice(opts)
        original = sources[rel][ln - 1]
        mutated = original[:lo] + repl + original[hi:]
        sources[rel][ln - 1] = mutated
        manifest.append(
            {
                "file": rel,
                "line": ln,
                "operator": operator,
                "original": original.decode("utf-8").strip(),
                "mutated": mutated.decode("utf-8").strip(),
            }
        )
    for rel in sorted({m["file"] for m in manifest}):
        target = root / rel
        mode = target.stat().st_mode
        atomic_write(target, b"\n".join(sources[rel]))
        os.chmod(target, stat.S_IMODE(mode))  # atomic_write's temp file is 0600
    return manifest


def _norm(path: str) -> str:
    p = path.replace("\\", "/").strip()
    return p[2:] if p.startswith("./") else p


def _same_file(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def score(seeds: Sequence[dict[str, Any]], findings: Sequence[dict[str, Any]]) -> int:
    """Maximum bipartite matching of findings to seeds (one seed per finding, ±WINDOW lines)."""
    edges: list[list[int]] = []
    for f in findings:
        line = f.get("line")
        file = f.get("file")
        if not isinstance(line, int) or not isinstance(file, str):
            edges.append([])
            continue
        edges.append(
            [
                j
                for j, s in enumerate(seeds)
                if _same_file(file, str(s["file"])) and abs(line - int(s["line"])) <= WINDOW
            ]
        )
    owner: dict[int, int] = {}

    def _augment(i: int, seen: set[int]) -> bool:
        for j in edges[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in owner or _augment(owner[j], seen):
                owner[j] = i
                return True
        return False

    return sum(1 for i in range(len(findings)) if _augment(i, set()))


def record_recall(
    root: Path, *, slug: str, model: str, hits: int, seeded: int, manifest: bytes
) -> Path:
    base = _base(root)
    row = _row(
        "recall",
        slug,
        hits=hits,
        seeded=seeded,
        model=model,
        manifest_sha256=hashlib.sha256(manifest).hexdigest(),
    )
    return _append(base, row)


# ── report ───────────────────────────────────────────────────────────────────


def _binom_cdf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    # Log space: math.comb(n, i) * p**i overflows a float once n passes ~1000.
    lp, lq, lnf = math.log(p), math.log1p(-p), math.lgamma(n + 1)
    total = 0.0
    for i in range(k + 1):
        total += math.exp(lnf - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(1.0, total)


def _bisect(f: Any, increasing: bool) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if (f(mid) < 0) == increasing:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial interval; stdlib only (SPEC Constraints)."""
    if n <= 0:
        return 0.0, 1.0
    if not 0 <= k <= n:
        raise ValueError(f"k={k} outside 0..{n}")
    half = alpha / 2
    lo = 0.0 if k == 0 else _bisect(lambda p: (1 - _binom_cdf(k - 1, n, p)) - half, True)
    hi = 1.0 if k == n else _bisect(lambda p: _binom_cdf(k, n, p) - half, False)
    return lo, hi


def _rate(k: int, n: int) -> dict[str, Any]:
    lo, hi = clopper_pearson(k, n)
    return {"k": k, "n": n, "lo": round(lo, 4), "hi": round(hi, 4)}


def report(root: Path) -> dict[str, Any]:
    rows = _kept_rows(_base(root))
    latest: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("event") == "review":
            latest[str(r.get("slug"))] = r  # last row per slug wins
    reviews = list(latest.values())
    by_status: dict[str, int] = {}
    for r in reviews:
        by_status[str(r.get("status"))] = by_status.get(str(r.get("status")), 0) + 1
    counted = [r for r in reviews if r.get("status") in _COUNTED]
    counted_slugs = {str(r.get("slug")) for r in counted}
    severe = sum(1 for r in counted if int(r.get("severe_accepted") or 0) >= 1)
    escapes: dict[str, dict[str, Any]] = {}
    for r in rows:
        if (
            r.get("event") == "escape"
            and r.get("verdict") == "escape"
            and str(r.get("slug")) in counted_slugs
        ):
            escapes.setdefault(str(r.get("commit")), r)
    missed = sum(
        1 for e in escapes.values() if e.get("flagged") == "no" and e.get("reviewable") == "yes"
    )
    recalls = [r for r in rows if r.get("event") == "recall"]
    hits = sum(int(r.get("hits") or 0) for r in recalls)
    seeded = sum(int(r.get("seeded") or 0) for r in recalls)
    return {
        "reviews": {"total": len(reviews), "by_status": by_status},
        "unrecognized_n": sum(int(r.get("unrecognized_n") or 0) for r in reviews),
        "marginal_yield": _rate(severe, len(counted)),
        "escape_miss": _rate(missed, len(escapes)),
        "seeded_recall": _rate(hits, seeded),
    }


def _fmt(label: str, rate: dict[str, Any]) -> str:
    return f"{label}: {rate['k']}/{rate['n']} [{rate['lo']:.3f}, {rate['hi']:.3f}]"


def _report_text(rep: dict[str, Any]) -> str:
    statuses = ", ".join(f"{k} {v}" for k, v in sorted(rep["reviews"]["by_status"].items()))
    return "\n".join(
        [
            f"reviews recorded: {rep['reviews']['total']} ({statuses or 'none yet'}); "
            f"unrecognized severities: {rep['unrecognized_n']}",
            _fmt(
                "marginal yield (reviews with an accepted P0/P1 / parsed or none)",
                rep["marginal_yield"],
            ),
            _fmt(
                "escape miss (missed / escapes attributed to a counted review)", rep["escape_miss"]
            ),
            _fmt("seeded recall (hits / seeded)", rep["seeded_recall"]),
            "intervals: exact two-sided, confidence 0.95 (Clopper-Pearson)",
        ]
    )


# ── CLI ──────────────────────────────────────────────────────────────────────


def _load_json_list(path: str) -> tuple[list[dict[str, Any]], bytes]:
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if isinstance(data, dict) and isinstance(data.get("findings"), list):
        data = data["findings"]
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list")
    return [d for d in data if isinstance(d, dict)], raw


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    guard = command_registry.misroute_guard("review_effect", raw)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(
        prog="hm review_effect", description="measure what the review catches and misses"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    cand = sub.add_parser("escape-candidates", help="remediation commits awaiting a verdict")
    cand.add_argument("--root", default=".")
    cand.add_argument("--json", action="store_true")
    esc = sub.add_parser("escape", help="record one escape verdict")
    esc.add_argument("--root", default=".")
    esc.add_argument("--commit", required=True)
    esc.add_argument("--verdict", required=True, choices=("escape", "not-escape"))
    esc.add_argument("--introduced-by", required=True, help="slug, or unknown")
    esc.add_argument("--flagged", required=True, choices=("yes", "no", "not-reviewed", "unknown"))
    esc.add_argument("--reviewable", required=True, choices=("yes", "no", "unknown"))
    esc.add_argument("--reason", required=True)
    sd = sub.add_parser("seed", help="plant deterministic defects in a clean scratch tree")
    sd.add_argument("--root", default=".")
    sd.add_argument("--base", required=True)
    sd.add_argument("--count", type=int, required=True)
    sd.add_argument("--seed", type=int, default=0)
    sd.add_argument("--manifest", default=None, help="write the manifest here (default: stdout)")
    sc = sub.add_parser("score", help="match findings against a seed manifest")
    sc.add_argument("--root", default=".")
    sc.add_argument("--manifest", required=True)
    sc.add_argument("--findings", required=True)
    sc.add_argument("--record", action="store_true")
    sc.add_argument("--slug", default=None)
    sc.add_argument("--model", default=None)
    rp = sub.add_parser("report", help="counts with exact intervals")
    rp.add_argument("--root", default=".")
    rp.add_argument("--json", action="store_true")
    args = parser.parse_args(raw)
    root = Path(args.root)

    if args.cmd == "escape-candidates":
        found = escape_candidates(root)
        if args.json:
            print(json.dumps(found))
        else:
            for c in found:
                print(f"{c['commit']}  hints={','.join(c['hint_slugs']) or '-'}  {c['subject']}")
        return 0
    if args.cmd == "escape":
        try:
            record_escape(
                root,
                commit=args.commit,
                verdict=args.verdict,
                introduced_by=args.introduced_by,
                flagged=args.flagged,
                reviewable=args.reviewable,
                reason=args.reason,
            )
        except FileExistsError as exc:
            _warn(str(exc))
            return 1
        except ValueError as exc:
            _warn(str(exc))
            return 2
        return 0
    if args.cmd == "seed":
        try:
            manifest = seed(root, base=args.base, count=args.count, seed=args.seed)
        except DirtyTreeError as exc:
            _warn(
                f"refusing to seed a dirty tree ({exc}); your changes are untouched. Seed a "
                f"clean scratch worktree instead: `git -C {root} worktree add <dir> HEAD`, "
                "seed <dir>, and afterwards run `git checkout -- .` inside <dir> to restore it"
            )
            return 1
        except ValueError as exc:
            _warn(str(exc))
            return 2
        if len(manifest) < args.count:
            _warn(f"only {len(manifest)} candidate line(s) in the diff; seeded {len(manifest)}")
        text = json.dumps(manifest, indent=2)
        if args.manifest:
            atomic_write(Path(args.manifest), text + "\n")
        else:
            print(text)
        files = " ".join(sorted({m["file"] for m in manifest}))
        if files:
            _warn(f"restore after scoring: git -C {root} checkout -- {files}")
        return 0
    if args.cmd == "score":
        try:
            seeds, manifest_raw = _load_json_list(args.manifest)
            findings, _ = _load_json_list(args.findings)
            bad = [
                s
                for s in seeds
                if not isinstance(s.get("file"), str) or not isinstance(s.get("line"), int)
            ]
            if bad:
                raise ValueError(f"{args.manifest}: seed entry without file/line: {bad[0]!r}")
        except (OSError, ValueError) as exc:
            _warn(str(exc))
            return 2
        hits = score(seeds, findings)
        print(json.dumps({"hits": hits, "seeded": len(seeds)}))
        if args.record:
            if not args.slug or not args.model:
                _warn("--record needs --slug and --model")
                return 2
            record_recall(
                root,
                slug=args.slug,
                model=args.model,
                hits=hits,
                seeded=len(seeds),
                manifest=manifest_raw,
            )
        return 0
    rep = report(root)
    print(json.dumps(rep) if args.json else _report_text(rep))
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
