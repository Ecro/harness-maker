"""Oracle gathering for the cross-model PIDA gate (REVIEW M1 — P0 remediation).

The `/hm:review` gate needs a test oracle, and the verifier that consumes it has no Bash. The
gathering therefore happens in the main loop — but the paths it runs the checks on come from
an EXTERNAL model's `file` field, which carries no schema constraint (`validate_payload`
inspects only `severity` and `message`, and antigravity's CLI-level schema is
best-effort — `--json-schema` exists, but `structured_output` can be absent on a
SUCCESS reply, so a `file` value can still arrive unconstrained). The control below
stands on that: sanitise the path regardless of which model produced it.

An earlier revision did the gathering in rendered PROSE that substituted those paths straight
into ``uv run pytest <paths>``. The shipped settings pre-approve ``Bash(uv run pytest:*)`` as a
prefix rule, so arbitrary trailing arguments run with no prompt — and a value beginning with
``-`` is consumed as an OPTION rather than a path, needing no shell metacharacter at all
(``pytest --basetemp=<dir>`` is documented to remove that directory; ``-p <module>`` imports
an arbitrary module).

"It is prose, not code" does not soften that: the taint path is real code and only the defence
was prose. `PLAN-second-opinion-invocation-and-slug-cap` ADR-001 already made this call once,
moving the second-opinion CLI invocations out of prose after four silent-skip bugs shipped
there. This module is the same move for the same reason.

Three responsibilities, all previously prose:
  * **path filtering** — reject option-shaped, absolute, traversing, metacharacter-bearing and
    off-diff paths BEFORE anything reaches argv;
  * **budget + visible truncation** — a traceback is unbounded, a subagent prompt is not;
  * **redaction** — value-shaped, reusing the repo's existing patterns, plus a stateful PEM
    mode. The keyword line-regex it replaces missed PEM bodies, credentialed URLs, JWTs and
    env dumps while firing on ordinary test names.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from harness_maker import command_registry

BUDGET_TOTAL = 4000
BUDGET_PER_COMMAND = 1500

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_PEM_BEGIN = re.compile(r"-----BEGIN[ A-Z]*-----")
_PEM_END = re.compile(r"-----END[ A-Z]*-----")

# Value-shaped, not keyword-shaped. `telemetry._SECRET_PATTERNS` is the existing set; the
# extras cover the shapes REVIEW M4 named as missed.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"sk_live_[A-Za-z0-9]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[A-Z0-9]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),
    # credentials embedded in a URL: scheme://user:pass@host
    re.compile(r"(?P<scheme>[a-zA-Z][\w+.-]*://)[^\s/:@]+:[^\s/@]+@"),
    # bare JWT
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+)?"),
)

_UNSAFE_CHARS = re.compile(r"[;&|`$<>\n\r\t\\*?\"']")


def safe_paths(candidates: Iterable[Any], allowed: set[str]) -> list[str]:
    """Return the candidates that are safe to place on an argv, in order, deduped.

    ``allowed`` is the changed-file set. Scoping to it is what stops a finding from steering
    the run at an arbitrary in-repo file; everything else here stops it from steering the
    *command* rather than the file.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        if not isinstance(raw, str):
            continue
        candidate = raw.strip()
        if not candidate or candidate in seen:
            continue
        if candidate.startswith("-"):  # an option, not a path — the P0
            continue
        if candidate.startswith("/") or candidate.startswith("~"):
            continue
        if ".." in Path(candidate).parts:
            continue
        if _UNSAFE_CHARS.search(candidate):
            continue
        if candidate not in allowed:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out


def redact(text: str) -> str:
    """Strip ANSI, redact value-shaped secrets, and blank whole PEM blocks.

    PEM handling is stateful on purpose: a line-wise keyword filter matches only the
    ``-----BEGIN`` line, so the key material on the following lines survived it.
    """
    text = _ANSI.sub("", text)
    out: list[str] = []
    in_pem = False
    for line in text.splitlines():
        if _PEM_BEGIN.search(line):
            in_pem = True
            out.append("[REDACTED-PEM-BLOCK]")
            continue
        if in_pem:
            if _PEM_END.search(line):
                in_pem = False
            continue
        for pattern in _SECRET_PATTERNS:
            line = pattern.sub("[REDACTED]", line)
        out.append(line)
    return "\n".join(out)


def truncate(text: str, budget: int) -> str:
    """Head-and-tail trim with a visible marker — a fragment must announce itself."""
    if len(text) <= budget:
        return text
    marker_room = 40
    keep = max(budget - marker_room, 0)
    head = keep // 2
    tail = keep - head
    dropped = len(text) - keep
    return f"{text[:head]}\n[… truncated {dropped} chars …]\n{text[len(text) - tail :]}"


def _changed_files(root: Path) -> set[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def _run_checks(paths: list[str], root: Path) -> str:
    """Run the project's checks on the (already filtered) paths, argv-only, never a shell."""
    chunks: list[str] = []
    for cmd in (
        ["uv", "run", "pytest", "-q", *paths],
        ["uv", "run", "ruff", "check", *paths],
        ["uv", "run", "mypy", *paths],
    ):
        try:
            proc = subprocess.run(
                cmd, cwd=str(root), capture_output=True, text=True, timeout=300, check=False
            )
            body = (proc.stdout or "") + (proc.stderr or "")
            status = f"exit={proc.returncode}"
        except (OSError, subprocess.SubprocessError) as exc:
            body = f"[{cmd[2]} did not run: {type(exc).__name__}]"
            status = "exit=n/a"
        # The exit code is load-bearing, not decoration. `pytest <a source file>` collects
        # ZERO tests and prints "no tests ran" — which reads to the mode-B rubric exactly like
        # "an oracle block passing where the finding predicts failure", i.e. grounds to
        # `rejected`. `exit=5` (no tests collected) vs `exit=0` (really passed) is the only
        # thing that distinguishes them.
        chunks.append(
            f"$ {' '.join(cmd[:3])} [{status}]\n{truncate(redact(body), BUDGET_PER_COMMAND)}"
        )
    return "\n\n".join(chunks)


def gather(findings: list[dict[str, Any]], root: Path) -> str:
    """Build the labelled oracle blocks for a findings list.

    Grouped by path, not by finding. Cross-model findings cluster in the files a diff
    touched, so running the three checks once per FINDING issued 3·N subprocesses where 3·M
    (M = distinct paths) suffices — each with its own 300 s timeout, and most of the output
    discarded by the total budget afterwards. One block per path, labelled with every finding
    id that maps to it.
    """
    allowed = _changed_files(root)
    by_path: dict[str, list[str]] = {}
    no_oracle: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        fid = str(finding.get("id", "")) or "<no-id>"
        paths = safe_paths([finding.get("file")], allowed)
        if not paths:
            no_oracle.append(fid)
            continue
        for path in paths:
            by_path.setdefault(path, []).append(fid)

    # The no-oracle note is reserved out of the budget rather than appended after the
    # truncation, so the stated "≤ BUDGET_TOTAL total" is actually true of the output.
    tail = (
        f"\n\n### no oracle gathered for: {', '.join(no_oracle)}\n"
        "(no usable in-diff path; treat as `unresolved` territory, not refutation)"
        if no_oracle
        else ""
    )
    # Floored, not just clamped to 0: a long no-oracle list must never drive `room` to zero,
    # which would leave the blocks section as a bare truncation marker.
    room = max(BUDGET_TOTAL - len(tail), 800)

    blocks: list[str] = []
    used = 0
    items = list(by_path.items())
    for i, (path, ids) in enumerate(items):
        if used >= room:
            skipped = [fid for _, rest in items[i:] for fid in rest]
            # Name the ids, don't just count paths: a finding whose oracle was skipped for
            # budget is indistinguishable from one that got a clean run unless it is listed,
            # and the mode-B rubric reads an absent block as "less evidence", not refutation.
            blocks.append(f"### budget exhausted; oracle not run for id(s)={', '.join(skipped)}")
            break
        block = f"### oracle for id(s)={', '.join(ids)} (path: {path})\n{_run_checks([path], root)}"
        blocks.append(block)
        used += len(block) + 2
    body = "\n\n".join(blocks)
    if len(body) > room:
        body = truncate(body, room)
    return body + tail


def main(argv: list[str] | None = None) -> int:
    """CLI: ``hm second_opinion_oracle --findings-file <path> [--root <dir>]``.

    Always exits 0 — a missing oracle is less evidence, never a reason to fail the review.
    """
    guard = command_registry.guard_or_none("second_opinion_oracle", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(prog="second_opinion_oracle")
    parser.add_argument("--findings-file", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.findings_file.read_text(encoding="utf-8"))
        findings = payload.get("findings", payload) if isinstance(payload, dict) else payload
        if not isinstance(findings, list):
            raise TypeError(f"findings must be a list, got {type(findings).__name__}")
    except Exception as exc:
        sys.stderr.write(f"[second-opinion] no oracle gathered: {type(exc).__name__}: {exc}\n")
        return 0
    sys.stdout.write(gather(findings, args.root) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
