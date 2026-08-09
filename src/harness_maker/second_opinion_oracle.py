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

Four responsibilities, all previously prose:
  * **toolchain gating** — run the project's OWN checks, and run NOTHING on a file type no
    configured toolchain understands;
  * **path filtering** — reject option-shaped, absolute, traversing, metacharacter-bearing and
    off-diff paths BEFORE anything reaches argv;
  * **budget + visible truncation** — a traceback is unbounded, a subagent prompt is not;
  * **redaction** — value-shaped, reusing the repo's existing patterns, plus a stateful PEM
    mode. The keyword line-regex it replaces missed PEM bodies, credentialed URLs, JWTs and
    env dumps while firing on ordinary test names.

The first of those is the newest and the least obvious. This module used to issue a fixed set
of Python commands against every path in every project. On a TypeScript project that is not a
degraded oracle but a fabricated one: measured on a four-line `.tsx` file, `ruff` emits 3809
bytes of Python syntax errors at `exit=1` — indistinguishable in meaning from real lint
failures — while `pytest` exits 4 and `mypy` exits 2. Injected into mode B, that lands as
either a false `accepted` (the rubric reads "an oracle block demonstrates the failure") or,
once the per-command budget truncates it, a silent `unresolved` via the truncation rule. The
commands now come from `harness.yaml`'s root-level `toolchains`, and an uncovered extension
gets no block at all.
# @hm:oracle-command-surface — anchor for tests/structural/test_no_hardcoded_toolchain_claim.py.
# Discovery keys on this marker, NOT on the claim being removed: keying on the claim would
# empty the population the moment the fix lands, failing the non-vacuity guard.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from harness_maker import command_registry

BUDGET_TOTAL = 4000
BUDGET_PER_COMMAND = 1500
# Reserved for the blocks section so a long no-oracle tail cannot starve it. Also the amount
# the tail is capped BELOW BUDGET_TOTAL by, which is what keeps the total honest.
_BLOCKS_FLOOR = 800

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


# The historical hardcoded triple, kept ONLY as the absent-key default for Python paths
# (ADR-006). Every harness shipped to date has no `toolchains` key, so this is what makes the
# change a no-op for them. It is NOT a fallback for other languages — an uncovered extension
# gets no oracle at all, which is the entire point.
_DEFAULT_PYTHON_TOOLCHAIN: dict[str, Any] = {
    "name": "python",
    "extensions": [".py", ".pyi"],
    "commands": {
        "test": "uv run pytest -q {path}",
        "lint": "uv run ruff check {path}",
        "types": "uv run mypy {path}",
    },
}

_PATH_PLACEHOLDER = "{path}"

# argv[0] allowlist. Before commands came from config, argv[0] was one of three hardcoded
# literals; now it is whatever `harness.yaml` says. That matters more than it looks: the base
# checkout's `.claude/harness.yaml` is an explicitly permitted write target (`worktree_gate`
# allows the base repo, and no `deny` rule covers it), and the command that invokes this module
# is pre-approved by the shipped `Bash(uv run … hm *)` prefix rule. Without this gate, a single
# Write to that file turns into unprompted execution of an arbitrary program on the next review
# — no `shell=True` needed, because argv[0] IS the program. Anything outside this set is
# rejected fail-closed, the same shape as an unusable config.
_ALLOWED_RUNNERS: frozenset[str] = frozenset(
    {
        "uv",
        "uvx",
        "python",
        "python3",
        "pytest",
        "ruff",
        "mypy",
        "npx",
        "npm",
        "pnpm",
        "yarn",
        "bun",
        "node",
        "deno",
        "cargo",
        "rustc",
        "go",
        "gofmt",
        "dotnet",
        "dart",
        "flutter",
        "swift",
        "mvn",
        "gradle",
        "bundle",
        "rake",
        "composer",
        "mix",
        "sbt",
        "make",
        "cmake",
        "ctest",
        "ninja",
        "bazel",
    }
)


def _resolve_config_root(root: Path) -> Path:
    """The BASE repo root, for reading config only — never for the diff.

    `--root` must stay the worktree: rooting the diff at base yields an empty changed-set and
    an all-`unresolved` degradation that looks exactly like a working run. But config must NOT
    be cwd-relative for the mirror-image reason `second_opinion_invoke.load_config` records —
    a worktree has no `.claude/` at all when the project gitignores it, so a cwd-relative read
    silently substitutes defaults while still reporting success.
    """
    from harness_maker.second_opinion_invoke import resolve_base_root

    return resolve_base_root(root)


def _load_toolchains(root: Path) -> list[Any] | None:
    """Configured entries, `[]` when the key is ABSENT, or `None` when it is UNUSABLE.

    The absent/unusable split is load-bearing and the two must never collapse. Absent means
    "this harness predates the key" — ADR-006's Python default applies and nothing changes for
    it. Unusable means the user tried to configure a toolchain and got it wrong; falling back
    to the Python default there would run `pytest` on their `.tsx` files, which is precisely
    the defect under repair. So unusable is **fail-closed**: no oracle at all, plus a loud line.

    Never raises: `main()` guards only the findings-file parse, so any exception escaping here
    would abort a review over a hand-edited config. The two likeliest failures are not
    `toolchains`-value errors at all — an unparseable `harness.yaml` and a failed base-root
    resolution both raise from the config *read*, outside any ValidationError handler, which is
    why this catches by breadth rather than by type.
    """
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.models import ToolchainConfig, _reject_overlapping_extensions

    try:
        path = _resolve_config_root(root) / ".claude" / "harness.yaml"
        if not path.exists():
            return []
        raw = load_harness_yaml(path).get("toolchains")
        if raw is None or (isinstance(raw, list) and not raw):
            return []
        if not isinstance(raw, list):
            raise TypeError(f"toolchains must be a list, got {type(raw).__name__}")
        entries = [ToolchainConfig.model_validate(e) for e in raw]
        _reject_overlapping_extensions(entries)
        live = [e for e in entries if not e.is_inert]
        if not live:
            raise ValueError("every toolchains entry is inert (empty extensions or commands)")
    except Exception as exc:  # noqa: BLE001 — breadth is the contract, not a shortcut
        sys.stderr.write(
            f"[second-opinion] toolchains config unusable ({type(exc).__name__}: {exc}); "
            "no oracle will be gathered.\n"
        )
        return None
    return live


def _toolchain_for(path: str, toolchains: list[Any] | None) -> Any | None:
    """The entry whose extensions claim this path, or None (→ no oracle).

    `toolchains is None` (unusable config) claims nothing at all. With an ABSENT key the
    Python default applies to `.py`/`.pyi` only; every other extension resolves to None. That
    asymmetry IS ADR-006.
    """
    from harness_maker.models import ToolchainConfig

    if toolchains is None:
        return None
    suffix = Path(path).suffix.lower()
    pool = toolchains or [ToolchainConfig.model_validate(_DEFAULT_PYTHON_TOOLCHAIN)]
    for entry in pool:
        if suffix in entry.extensions:
            return entry
    return None


def _substitute(template: str, path: str | None) -> list[str] | None:
    """Tokenise FIRST, then substitute within tokens — never the other way round.

    `safe_paths`'s `_UNSAFE_CHARS` does not reject a space, so substituting into the raw
    string would split one legal path into two argv entries. Every occurrence in every token
    is replaced, so `--file={path}` and `{path}.snap` both work without a second rule.
    """
    try:
        tokens = shlex.split(template)
    except ValueError:
        return None
    if not tokens:
        return None
    if tokens[0] not in _ALLOWED_RUNNERS:
        return None
    if path is None:
        return tokens
    return [t.replace(_PATH_PLACEHOLDER, path) for t in tokens]


def _run_argv(argv: list[str], root: Path) -> str:
    """One command, argv-only, never a shell. `cwd` is the worktree (ADR-005).

    The exit code is emitted with the body and is load-bearing, not decoration. `pytest <a
    non-test source file>` collects ZERO tests and prints "no tests ran" — which reads to the
    mode-B rubric exactly like "an oracle block passing where the finding predicts failure",
    i.e. grounds for `rejected`. `exit=5` (nothing collected) vs `exit=0` (really passed) is
    the only thing that distinguishes them. The extension gate removes the *cross-language*
    case upstream of here; this covers the residual in-toolchain ones.
    """
    try:
        proc = subprocess.run(
            argv, cwd=str(root), capture_output=True, text=True, timeout=300, check=False
        )
        body = (proc.stdout or "") + (proc.stderr or "")
        status = f"exit={proc.returncode}"
    except (OSError, subprocess.SubprocessError) as exc:
        body = f"[{argv[0]} did not run: {type(exc).__name__}]"
        status = "exit=n/a"
    label = " ".join(argv[:3])
    return f"$ {label} [{status}]\n{truncate(redact(body), BUDGET_PER_COMMAND)}"


def gather(findings: list[dict[str, Any]], root: Path) -> str:
    """Build the labelled oracle blocks for a findings list.

    Grouped by path, not by finding. Cross-model findings cluster in the files a diff
    touched, so running the three checks once per FINDING issued 3·N subprocesses where 3·M
    (M = distinct paths) suffices — each with its own 300 s timeout, and most of the output
    discarded by the total budget afterwards. One block per path, labelled with every finding
    id that maps to it.
    """
    allowed = _changed_files(root)
    toolchains = _load_toolchains(root)

    by_path: dict[str, list[str]] = {}
    path_toolchain: dict[str, Any] = {}
    no_path: list[str] = []
    uncovered: list[tuple[str, str]] = []  # (finding id, extension)
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        fid = str(finding.get("id", "")) or "<no-id>"
        paths = safe_paths([finding.get("file")], allowed)
        if not paths:
            no_path.append(fid)
            continue
        for path in paths:
            entry = _toolchain_for(path, toolchains)
            if entry is None:
                # ADR-001: run NOTHING. Output from a tool that could not parse the subject
                # is not a degraded oracle, it is a fabricated one — and it reaches the
                # mode-B rubric as either a false `accepted` or, once truncated, a silent
                # `unresolved`.
                uncovered.append((fid, Path(path).suffix or "<no extension>"))
                continue
            by_path.setdefault(path, []).append(fid)
            path_toolchain[path] = entry

    # The no-oracle note is reserved out of the budget rather than appended after the
    # truncation, so the stated "≤ BUDGET_TOTAL total" is actually true of the output.
    # Grouped BY CAUSE: "we could not use your path" and "your toolchain does not cover this
    # file type" have different remedies, and the mode-B consumer cannot tell them apart from
    # one undifferentiated list.
    tail_parts: list[str] = []
    if no_path:
        tail_parts.append(
            f"\n\n### no oracle gathered for: {', '.join(no_path)}\n"
            "(no usable in-diff path; treat as `unresolved` territory, not refutation)"
        )
    if uncovered:
        detail = ", ".join(f"{fid} ({ext})" for fid, ext in uncovered)
        tail_parts.append(
            f"\n\n### no oracle gathered for: {detail}\n"
            "(no configured toolchain covers these file types, so NO check was run — "
            "treat as `unresolved` territory, not refutation)"
        )
    tail = "".join(tail_parts)
    # The tail is itself bounded before `room` is derived from it. Flooring `room` at 800 while
    # leaving `tail` unbounded made the stated "≤ BUDGET_TOTAL total" false: the tail grows by
    # one entry per pathless/uncovered finding, so a large diff could return 800 + an arbitrarily
    # long tail. Reserve the floor for the blocks, cap the tail with the rest, and the invariant
    # holds by construction rather than by hope.
    tail_max = BUDGET_TOTAL - _BLOCKS_FLOOR
    if len(tail) > tail_max:
        tail = truncate(tail, tail_max)
    # Floored, not just clamped to 0: a long no-oracle list must never drive `room` to zero,
    # which would leave the blocks section as a bare truncation marker.
    room = max(BUDGET_TOTAL - len(tail), _BLOCKS_FLOOR)

    blocks: list[str] = []
    labelled = 0
    used = 0
    items = list(by_path.items())
    # Repo-wide templates (no `{path}`) run ONCE per gather, and their output is deliberately
    # UNLABELLED: a repo-wide failure can come from a pre-existing error elsewhere in the tree,
    # so labelling it with every covered id would re-create the false-`accepted` path. The
    # consumer already has the rule that neutralises it — "an unlabelled block is not evidence
    # for anything" — so no rubric change is needed.
    repo_wide: dict[str, list[str]] = {}
    for i, (path, ids) in enumerate(items):
        entry = path_toolchain[path]
        for _role, template in entry.commands.declared():
            if _PATH_PLACEHOLDER not in template:
                repo_wide.setdefault(template, []).append(entry.name)
        if used >= room:
            skipped = [fid for _, rest in items[i:] for fid in rest]
            # Name the ids, don't just count paths: a finding whose oracle was skipped for
            # budget is indistinguishable from one that got a clean run unless it is listed,
            # and the mode-B rubric reads an absent block as "less evidence", not refutation.
            blocks.append(f"### budget exhausted; oracle not run for id(s)={', '.join(skipped)}")
            break
        # A template that cannot be turned into argv is REPORTED, not dropped. Silently
        # skipping it produced the worst available outcome: if a sibling role succeeded the
        # block looked healthy, `labelled` stayed non-zero so the coverage warning never
        # fired, and a configured check had simply never run. An unrunnable command is a
        # configuration defect the reader must see.
        chunks: list[str] = []
        for _role, template in entry.commands.declared():
            if _PATH_PLACEHOLDER not in template:
                continue
            argv = _substitute(template, path)
            if argv is None:
                chunks.append(
                    f"$ [{_role}] NOT RUN [exit=n/a]\n"
                    f"[unrunnable command template: unbalanced quoting, empty, or a program "
                    f"outside the allowed runner set — {template!r}]"
                )
                continue
            chunks.append(_run_argv(argv, root))
        if not chunks:
            continue
        # The `toolchain:` annotation is emitted only when the toolchain came from CONFIG.
        # On the absent-key default path the header stays byte-identical to the pre-change
        # implementation, which is what AC-002 asserts differentially against the pinned
        # baseline blob. Weakening that assertion to accommodate a cosmetic annotation would
        # be lowering the threshold instead of meeting it; the annotation is most useful
        # exactly where config exists, and a harness has one shape or the other, never both.
        label = f"(path: {path}, toolchain: {entry.name})" if toolchains else f"(path: {path})"
        block = f"### oracle for id(s)={', '.join(ids)} {label}\n" + "\n\n".join(chunks)
        blocks.append(block)
        labelled += 1
        used += len(block) + 2

    # Repo-wide blocks are charged against the SAME budget. They used to run after the
    # per-path `break`, so a budget-exhausted run still spawned a 300 s subprocess per
    # repo-wide template whose output was then thrown away by the final truncate — cost
    # incurred, evidence discarded.
    for template, names in repo_wide.items():
        if used >= room:
            break
        argv = _substitute(template, None)
        if not argv:
            continue
        block = (
            f"### project-wide context (toolchain: {', '.join(sorted(set(names)))}) — "
            "adjudicates NO individual finding\n" + _run_argv(argv, root)
        )
        blocks.append(block)
        used += len(block) + 2

    body = "\n\n".join(blocks)
    if len(body) > room:
        body = truncate(body, room)

    # Visibility (ADR-008). The trigger is an OUTPUT property, not a config property: an
    # all-repo-wide but non-empty config (a seeded Rust harness) satisfies every config-shaped
    # predicate — coverage non-zero, command set non-empty — while producing zero per-finding
    # evidence. That is the silent degradation this warning exists to remove, and a
    # config-shaped trigger would sit inside it.
    if labelled == 0:
        cause = (
            "toolchains config unusable"
            if toolchains is None
            else "toolchain declares no per-path command"
            if toolchains
            else "no toolchain covers these extensions"
        )
        sys.stderr.write(
            f"[second-opinion] oracle: 0 labelled block(s) for {len(findings)} finding(s) "
            f"({cause}); every finding will land `unresolved`. "
            "Set `toolchains` in .claude/harness.yaml.\n"
        )
    elif uncovered:
        sys.stderr.write(
            f"[second-opinion] oracle: {len(uncovered)} finding(s) had no toolchain for their "
            f"file type ({', '.join(sorted({ext for _, ext in uncovered}))}); "
            "those will land `unresolved`.\n"
        )
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
