"""Check-suite verification cache — skip lint/mypy/test when input is unchanged.

Implements ADR-007, except for the env component, whose inverted policy this file
supersedes (2026-07-27 — see below). skip-key = sha256(project_root + HEAD sha + diff hash +
uv.lock hash + pyproject.toml hash + tool versions + env hash).

**Env policy is an ALLOWLIST** (`_ENV_ALLOW` / `_ENV_ALLOW_PATTERNS`): only variables
that can change what the checks CONCLUDE are hashed. This reverses the original
inverted policy, whose stated goal — "over-invalidate rather than risk a false PASS" —
turned out to be unachievable in this shape and to cost everything while buying
nothing:

  * Hashing the whole ambient environment made the key a property of the CONTEXT it
    was computed in, not of the code. A subagent's Bash exports a different set than
    the main loop's (measured 2026-07-27: 43 vars vs 42, differing in exactly one —
    `CLAUDE_EFFORT`), so a marker written by `/hm:verify` could not be read by
    `/hm:wrapup` and both re-ran the full suite forever.
  * It also made the cache depend on `DISCORD_BOT_TOKEN`, `JENKINS_TOKEN`,
    `PIPELINE_SLACK_WEBHOOK_URL`, `ZEPHYR_BASE`, `NVM_DIR` … — rotating a Slack
    webhook invalidated the Python test cache.
  * A permanently-cold cache is indistinguishable from a correctly-invalidated one,
    which is why this survived two rounds. This is instance 2 of
    `[fail:design] verification-cache-key-nondeterministic`; the allowlist is the
    remedy that entry named a round earlier and that instance 1 declined to take.

**Accepted cost of the flip:** a build-affecting variable nobody enumerated is not
hashed, so a stale PASS is now possible where it previously was not. That risk is
bounded by an enumerable set and is checked one-case-per-member by
`test_every_build_affecting_var_still_invalidates`, which catches allowlist SHRINKAGE
but cannot catch OMISSION. Adding a new env-driven toggle to this project means adding
it to `_ENV_ALLOW`.

Env VALUES are still scrubbed of per-invocation launcher paths (see
`_VOLATILE_VALUE_RE`): `PATH` and `VIRTUAL_ENV` are allowlisted and both carry uv's
throwaway build directory. Any change here must keep the key stable across two
invocations of the same command — `test_key_is_stable_across_ephemeral_launcher_envs`
and `test_the_key_is_identical_across_two_subprocess_invocations` are those fences.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker import command_registry

# ALLOWLIST (was a blocklist until 2026-07-27). Only variables that can change what
# `pytest` / `ruff` / `mypy` CONCLUDE are hashed. Everything else — agent identity,
# credentials, unrelated toolchains, desktop session plumbing — is excluded.
_ENV_ALLOW: frozenset[str] = frozenset(
    {
        # interpreter + package resolution (the PYTHON* family is pattern-matched below)
        "PATH",
        "VIRTUAL_ENV",
        "HOME",  # tool caches and config live under it
        "TMPDIR",
        # determinism / output shape
        "TZ",
        "LANG",
        "SOURCE_DATE_EPOCH",
        # test gating THIS repo actually reads. Enumerated from a grep of every
        # `getenv`/`environ.get` in `tests/` and `src/` — each one below decides whether
        # a test runs, or changes what it compares against:
        #   HM_RUN_PARALLEL_SESSION  module-level skipif in the two
        #                            tests/integration/test_*_parallel_session.py modules
        #   INSTALL_CMD_TEST         module-level skipif in
        #                            tests/integration/test_readme_install_commands.py
        #   HM_MAIN_CHECKOUT_PATH    tests/unit/conftest.py pins `_HARNESS_MAKER_PKG_ROOT`
        #                            with it, so it moves every snapshot comparison
        #   HARNESS_MAKER_FREEZE     cli.py pins the render clock with it, same effect
        # NOT a bare `HM_*` pattern: `HM_SESSION_ID` is per-Claude-session and would
        # re-introduce exactly the churn this policy exists to remove.
        # (`HYPOTHESIS_PROFILE` is deliberately NOT listed: the `HYPOTHESIS_*`
        #  pattern already covers it, and a doubly-covered member cannot be
        #  deletion-gated by the fence — one removal alone is a no-op.)
        "CI",
        "INTEGRATION",
        "HM_RUN_PARALLEL_SESSION",
        "HM_MAIN_CHECKOUT_PATH",
        "INSTALL_CMD_TEST",
        "HARNESS_MAKER_FREEZE",
    }
)

_ENV_ALLOW_PATTERNS: tuple[str, ...] = (
    "LC_*",
    "PYTHON*",
    "UV_*",
    "RUFF_*",
    "MYPY*",
    "PYTEST_*",
    "HYPOTHESIS_*",
)

# Carve-outs from the patterns above: matched by an allow pattern, but per-invocation
# bookkeeping rather than configuration. Admitting any of these re-introduces the
# permanently-cold cache this policy exists to fix.
#   UV_RUN_RECURSION_DEPTH  increments on every nested `uv run`, and every rendered
#                           harness command is invoked that way
#   PYTEST_CURRENT_TEST     pytest rewrites it per test function
#   PYTEST_XDIST_WORKER     differs per parallel worker
_ENV_ALLOW_EXCEPTIONS: frozenset[str] = frozenset(
    {
        "UV_RUN_RECURSION_DEPTH",
        "PYTEST_CURRENT_TEST",
        "PYTEST_XDIST_WORKER",
    }
)


def _is_hashed_env(key: str) -> bool:
    """True when this variable can change a verification verdict (allowlist policy).

    Inverted from the original blocklist on 2026-07-27. The blocklist hashed the whole
    ambient environment, which made the key depend on the CONTEXT it was computed in
    rather than on the code: a subagent's Bash exports a different set than the main
    loop's (measured: 43 vars vs 42, differing only in `CLAUDE_EFFORT`), so a marker
    written by `/hm:verify` was invisible to `/hm:wrapup` and both re-ran the full
    suite forever. It also meant rotating a Slack webhook invalidated the Python test
    cache. Second instance of `[fail:design] verification-cache-key-nondeterministic`;
    the allowlist is the remedy that entry named.
    """
    if key in _ENV_ALLOW_EXCEPTIONS:
        return False
    if key in _ENV_ALLOW:
        return True
    return any(fnmatch.fnmatch(key, pat) for pat in _ENV_ALLOW_PATTERNS)


# Path prefixes a launcher recreates on EVERY invocation. `uv run --with <pkg>` builds a
# throwaway environment per call under `~/.cache/uv/builds-v*/.tmpXXXXXX` and exports it
# through both PATH and VIRTUAL_ENV — and every rendered harness command is invoked that
# way, so hashing those values verbatim made the key change on every single call. The
# cache could never be fresh and `/hm:verify` + `/hm:wrapup` each re-ran the full suite
# forever, which is indistinguishable from correct invalidation (see
# `[fail:design] verification-cache-key-nondeterministic`).
#
# Scrubbed at the VALUE level rather than by ignoring the variable, for two reasons: a
# genuine PATH / VIRTUAL_ENV change still invalidates — both are allowlisted, so
# dropping the variable instead of scrubbing its value would stop detecting a real
# toolchain move — and a future launcher's throwaway directory is covered without
# having to name its variable.
# (This used to read "the inverted-policy safety property is preserved". That policy
# was retired on 2026-07-27; the property that survives is the one stated above.)
#
# `archive-v*` is deliberately NOT scrubbed: that path encodes the identity of the
# installed package, which is real signal.
_VOLATILE_VALUE_RE = re.compile(
    r"(?:[^\s:]*/\.cache/uv/(?:builds|environments)-v\d+"
    rf"|{re.escape(tempfile.gettempdir())})"
    r"/[^\s:]*"
)


def _scrub_volatile(value: str) -> str:
    return _VOLATILE_VALUE_RE.sub("<volatile>", value)


def _env_hash() -> str:
    """Hash only the allowlisted, build-affecting env vars — see `_is_hashed_env`.

    Values are still scrubbed of per-invocation launcher paths — `PATH` and
    `VIRTUAL_ENV` are allowlisted and both carry uv's throwaway build directory, so
    dropping the scrubber would restore the churn on its own.
    """
    items = sorted((k, _scrub_volatile(v)) for k, v in os.environ.items() if _is_hashed_env(k))
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()


def _file_hash(path: Path) -> str:
    """SHA-256 of file contents, or empty string if file doesn't exist."""
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_quiet(cmd: list[str], *, cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            cwd=cwd,
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _tool_versions(project_root: Path) -> dict[str, str]:
    """Collect semver strings for key tools."""
    versions: dict[str, str] = {}
    for name, cmd in [
        ("python", ["python3", "--version"]),
        ("ruff", ["ruff", "--version"]),
        ("mypy", ["mypy", "--version"]),
        ("pytest", ["python3", "-m", "pytest", "--version"]),
    ]:
        versions[name] = _run_quiet(cmd, cwd=project_root)
    return versions


def compute_skip_key(project_root: Path) -> str:
    """Compute the skip-key for a project's check suite.

    ADR-007: project_root_hash + HEAD sha + diff hash + uv.lock hash +
    pyproject.toml hash + tool versions + env hash (ALLOWLIST — see the module
    docstring; this supersedes ADR-007's inverted env sub-decision, 2026-07-27).
    """
    parts: list[str] = []

    parts.append(hashlib.sha256(str(project_root.resolve()).encode()).hexdigest())

    parts.append(_run_quiet(["git", "rev-parse", "HEAD"], cwd=project_root))

    diff_out = _run_quiet(["git", "diff", "HEAD"], cwd=project_root)
    staged_out = _run_quiet(["git", "diff", "--cached"], cwd=project_root)
    combined = diff_out + staged_out
    parts.append(hashlib.sha256(combined.encode()).hexdigest() if combined else "")

    parts.append(_file_hash(project_root / "uv.lock"))
    parts.append(_file_hash(project_root / "pyproject.toml"))

    tv = _tool_versions(project_root)
    parts.append(json.dumps(tv, sort_keys=True))

    parts.append(_env_hash())

    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


_DEFAULT_RELEVANT_PATTERNS: tuple[str, ...] = (
    "src/**",
    "tests/**",
    ".github/workflows/**",
    ".claude-verify.sh",
    "pyproject.toml",
    "uv.lock",
    "requirements*.txt",
    "package.json",
    "pnpm-lock.yaml",
    "package-lock.json",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "Makefile",
    "noxfile.py",
    "tox.ini",
)

_DEFAULT_IRRELEVANT_PATTERNS: tuple[str, ...] = (
    ".claude/memory/**",
    ".claude/observability/review-*.jsonl",
    "work-docs/**",
    "CHANGELOG.md",
)


def _match_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def is_relevant_path(path: str, *, docs_are_behavior: bool = False) -> bool:
    """Return True when a changed path can affect verification outcomes.

    The default policy intentionally treats wrapup-managed memory/work-docs
    edits as irrelevant so a post-verify PLAN status or memory append does not
    force another full regression suite. Unknown paths stay conservative.
    """
    normalized = path.replace("\\", "/")
    if docs_are_behavior and normalized.endswith((".md", ".rst", ".txt")):
        return True
    if _match_any(normalized, _DEFAULT_IRRELEVANT_PATTERNS):
        return False
    if _match_any(normalized, _DEFAULT_RELEVANT_PATTERNS):
        return True
    # Conservative fallback: unknown source-control changes might matter.
    return True


def _changed_paths(project_root: Path) -> list[str]:
    names = set[str]()
    for cmd in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        out = _run_quiet(cmd, cwd=project_root)
        if out:
            names.update(line.strip() for line in out.splitlines() if line.strip())
    return sorted(names)


def compute_relevant_skip_key(project_root: Path, *, docs_are_behavior: bool = False) -> str:
    """Compute a verification key that ignores wrapup-only document churn."""
    parts: list[str] = []
    root = project_root.resolve()
    parts.append(hashlib.sha256(str(root).encode()).hexdigest())
    parts.append(_run_quiet(["git", "rev-parse", "HEAD"], cwd=root))

    relevant_paths = [
        path
        for path in _changed_paths(root)
        if is_relevant_path(path, docs_are_behavior=docs_are_behavior)
    ]
    if relevant_paths:
        diff_parts: list[str] = []
        for path in relevant_paths:
            file_path = root / path
            diff_parts.append(path)
            diff_parts.append(_run_quiet(["git", "diff", "HEAD", "--", path], cwd=root))
            diff_parts.append(_run_quiet(["git", "diff", "--cached", "--", path], cwd=root))
            if file_path.is_file():
                diff_parts.append(_file_hash(file_path))
        parts.append(hashlib.sha256("\n".join(diff_parts).encode()).hexdigest())
    else:
        parts.append("")

    parts.append(_file_hash(root / "uv.lock"))
    parts.append(_file_hash(root / "pyproject.toml"))
    parts.append(json.dumps(_tool_versions(root), sort_keys=True))
    parts.append(_env_hash())
    parts.append("docs_are_behavior=1" if docs_are_behavior else "docs_are_behavior=0")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _cache_dir() -> Path:
    env_override = os.environ.get("HARNESS_MAKER_CACHE_DIR")
    if env_override:
        return Path(env_override) / "verify"
    return Path.home() / ".cache" / "harness-maker" / "verify"


def _marker_path(key: str) -> Path:
    return _cache_dir() / f"{key}.json"


def is_fresh(key: str) -> dict[str, Any] | None:
    """Check if a passing marker exists for this key.

    Returns the marker dict if fresh, None otherwise.
    """
    path = _marker_path(key)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("passed"):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def mark_passed(
    key: str,
    *,
    checks: list[str] | None = None,
    project_root: str = "",
    writer: str | None = None,
) -> Path:
    """Write a passing marker for the given key. Returns the marker path.

    `writer` is provenance: only `run` passes it, and only `run` trusts it. A marker written
    without one is a claim someone made, which `check` still honours for older harnesses.
    """
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)

    recorded = checks or ["lint", "mypy", "pytest"]
    marker: dict[str, Any] = {
        "passed": True,
        "passed_at": datetime.now(tz=UTC).isoformat(),
        "checks": recorded,
        "project_root": project_root,
        "key": key,
    }
    if writer is not None:
        marker["writer"] = writer
        marker["commands_sha256"] = _commands_hash(recorded)

    path = _marker_path(key)
    fd, tmp = tempfile.mkstemp(
        dir=str(cache),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(marker, f)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def _commands_hash(commands: list[str]) -> str:
    return hashlib.sha256(json.dumps(list(commands)).encode("utf-8")).hexdigest()


# ── run: the gate run and the marker in one process (SPEC-top-issues-2026-09 S5) ─

RUN_WRITER = "run"
DEFAULT_RUN_TIMEOUT_S = 540
"""Per command, and never more than what is left of `RUN_DEADLINE_S`."""

RUN_DEADLINE_S = 570
"""Whole-run default. Under Claude Code's 600 s FOREGROUND Bash cap, so running out of time is
reported by this process — with an exit code to branch on — rather than the host killing it with
none. A per-command cap alone does not do that: three gates at 400 s each are each "under" 540.
A real suite often needs longer (this repo's pytest gate alone took 425–702 s), so callers that
can run in the background pass `--deadline-s` / `--timeout-s` to lift both caps."""

EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_DEGRADED = 3
EXIT_TREE_CHANGED = 4
_TAIL_LINES = 60


def is_run_fresh(key: str, commands: list[str]) -> dict[str, Any] | None:
    """A marker `run` itself wrote for this key AND this exact command list, else None.

    Stricter than `is_fresh` on purpose: a marker from `mark-pass` records that someone said
    the suite passed — the 2026-09-20 route that landed an uncollectable test on main.
    """
    marker = is_fresh(key)
    if marker is None:
        return None
    if marker.get("writer") != RUN_WRITER:
        return None
    if marker.get("commands_sha256") != _commands_hash(commands):
        return None
    return marker


def _tail(text: str) -> str:
    return "\n".join(text.splitlines()[-_TAIL_LINES:])


REAP_TIMEOUT_S = 5
"""After killing a gate's group, how long to wait for its pipe to close. A descendant that left
the group (`setsid`) keeps the pipe open forever; an unbounded wait would outlive the deadline."""


def _kill_group(proc: subprocess.Popen[str]) -> None:
    """SIGKILL the gate's whole process group and reap it, in bounded time."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    try:
        proc.communicate(timeout=REAP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        if proc.stdout is not None:
            proc.stdout.close()
        proc.kill()
        proc.wait(timeout=REAP_TIMEOUT_S)


def _run_gate(cmd: str, root: Path, timeout_s: float) -> tuple[int, str]:
    """Run one gate in its own process group; on ANY abnormal exit, kill the whole group.

    `subprocess.run(timeout=)` kills only the direct child, and a gate is usually `uv run
    pytest`, whose workers would outlive it. The group is its own session, so a signal aimed at
    this process no longer reaches it — every exit that is not a normal return (timeout,
    Ctrl-C, the SIGTERM `run_gates` turns into an exception) must kill the group explicitly.
    """
    proc = subprocess.Popen(
        shlex.split(cmd),
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except BaseException:
        _kill_group(proc)
        raise
    return proc.returncode, out or ""


class _TerminatedError(Exception):
    """SIGTERM raised as an exception, so `_run_gate`'s cleanup runs before the process exits."""


def run_gates(
    root: Path,
    *,
    mode: str = "relevant",
    docs_are_behavior: bool = False,
    timeout_s: float = DEFAULT_RUN_TIMEOUT_S,
    deadline_s: float = RUN_DEADLINE_S,
) -> tuple[int, dict[str, Any]]:
    """Run the CI-derived primary gate commands and write the marker only on a clean pass.

    Stops at the first failure. A pass on a tree that changed while the gates ran is not a
    pass of the tree now on disk, so it writes nothing and says which paths moved.
    """
    from harness_maker.verification_plan import read_plan

    def key_now() -> str:
        if mode == "relevant":
            return compute_relevant_skip_key(root, docs_are_behavior=docs_are_behavior)
        return compute_skip_key(root)

    plan = read_plan(root.resolve())
    if plan.degraded:
        sys.stderr.write(f"[verify] degraded plan, nothing run: {plan.reason}\n")
        return EXIT_DEGRADED, {"cached": False, "commands": [], "reason": plan.reason}

    commands = plan.primary_commands()
    if not commands:
        # Every CI gate is non-blocking (continue-on-error). Nothing would run, and a marker
        # written here would record lint/mypy/pytest as passed — a pass nobody observed.
        sys.stderr.write("[verify] degraded plan, nothing run: CI declares no blocking gate\n")
        return EXIT_DEGRADED, {"cached": False, "commands": [], "reason": "no blocking gate"}
    for extra in plan.additional_commands():
        sys.stderr.write(f"[verify] not run (additional CI gate): {extra}\n")
    key_before = key_now()
    summary: dict[str, Any] = {"cached": False, "commands": commands, "key": key_before}
    if is_run_fresh(key_before, commands) is not None:
        return EXIT_PASSED, {**summary, "cached": True}

    results: list[dict[str, Any]] = []
    summary["results"] = results
    previous = _install_sigterm_bridge()
    try:
        code = _run_all(commands, root, timeout_s, results, deadline_s)
    finally:
        _restore_sigterm(previous)
    if code != EXIT_PASSED:
        return code, summary
    return _finish(root, key_now, key_before, commands, summary)


def _install_sigterm_bridge() -> Any:
    """Turn SIGTERM into `_TerminatedError` for the duration of the gate loop (main thread only)."""
    import threading

    if threading.current_thread() is not threading.main_thread():
        return None

    def _raise(_signum: int, _frame: Any) -> None:
        raise _TerminatedError

    return signal.signal(signal.SIGTERM, _raise)


def _restore_sigterm(previous: Any) -> None:
    if previous is not None:
        signal.signal(signal.SIGTERM, previous)


def _run_all(
    commands: list[str],
    root: Path,
    timeout_s: float,
    results: list[dict[str, Any]],
    deadline_s: float,
) -> int:
    deadline = time.monotonic() + deadline_s
    for cmd in commands:
        started = time.monotonic()
        budget = min(timeout_s, deadline - started)
        if budget <= 0:
            sys.stderr.write(
                f"[verify] timed out: the {deadline_s:g}s run deadline passed before {cmd}\n"
            )
            results.append({"cmd": cmd, "rc": None, "timed_out": True})
            return EXIT_FAILED
        try:
            rc, output = _run_gate(cmd, root, budget)
        except subprocess.TimeoutExpired:
            sys.stderr.write(f"[verify] timed out after {budget:g}s: {cmd}\n")
            results.append({"cmd": cmd, "rc": None, "timed_out": True})
            return EXIT_FAILED
        except (OSError, ValueError) as e:
            # ValueError: `shlex.split` on an unbalanced quote — still a failure to start.
            sys.stderr.write(f"[verify] could not start {cmd!r}: {e}\n")
            results.append({"cmd": cmd, "rc": None, "error": str(e)})
            return EXIT_FAILED
        results.append({"cmd": cmd, "rc": rc, "seconds": round(time.monotonic() - started, 1)})
        if rc != 0:
            sys.stderr.write(f"[verify] FAILED (rc={rc}): {cmd}\n")
            sys.stderr.write(_tail(output) + "\n")
            return EXIT_FAILED
    return EXIT_PASSED


def _finish(
    root: Path,
    key_now: Any,
    key_before: str,
    commands: list[str],
    summary: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    if key_now() != key_before:
        changed = _changed_paths(root)
        sys.stderr.write(
            "[verify] the tree changed while the gates ran — no marker written. "
            f"Changed or dirty paths: {', '.join(changed) or '(unknown)'}\n"
        )
        return EXIT_TREE_CHANGED, summary

    mark_passed(key_before, checks=commands, project_root=str(root.resolve()), writer=RUN_WRITER)
    return EXIT_PASSED, summary


def invalidate(key: str) -> bool:
    """Remove the marker for a key. Returns True if it existed."""
    path = _marker_path(key)
    if path.is_file():
        path.unlink()
        return True
    return False


def _compute_key_for_args(args: argparse.Namespace) -> str:
    root = Path(args.root)
    if args.mode == "relevant":
        return compute_relevant_skip_key(root, docs_are_behavior=args.docs_are_behavior)
    return compute_skip_key(root)


def main(argv: list[str] | None = None) -> int:
    _guard = command_registry.guard_or_none("observability.verification_cache", argv)
    if _guard is not None:
        return _guard
    parser = argparse.ArgumentParser(prog="verification-cache")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", default=".")
        p.add_argument("--mode", choices=("full", "relevant"), default="relevant")
        p.add_argument("--docs-are-behavior", action="store_true")

    key_p = sub.add_parser("key")
    add_common(key_p)

    check_p = sub.add_parser("check")
    add_common(check_p)

    mark_p = sub.add_parser("mark-pass")
    add_common(mark_p)
    mark_p.add_argument("--checks", default="lint,mypy,pytest")

    explain_p = sub.add_parser("explain")
    add_common(explain_p)

    run_p = sub.add_parser("run")
    add_common(run_p)
    run_p.add_argument("--timeout-s", type=float, default=DEFAULT_RUN_TIMEOUT_S)
    run_p.add_argument("--deadline-s", type=float, default=RUN_DEADLINE_S)

    args = parser.parse_args(argv)
    if args.command == "run":
        try:
            code, summary = run_gates(
                Path(args.root),
                mode=args.mode,
                docs_are_behavior=args.docs_are_behavior,
                timeout_s=args.timeout_s,
                deadline_s=args.deadline_s,
            )
        except _TerminatedError:
            sys.stderr.write(
                "[verify] terminated — the running gate's group was killed; no marker\n"
            )
            return EXIT_FAILED
        print(json.dumps({**summary, "exit": code}, sort_keys=True))
        return code
    key = _compute_key_for_args(args)

    if args.command == "key":
        print(key)
        return 0
    if args.command == "check":
        marker = is_fresh(key)
        if marker is None:
            print(json.dumps({"fresh": False, "key": key}))
            return 1
        print(json.dumps({"fresh": True, "key": key, "marker": marker}, sort_keys=True))
        return 0
    if args.command == "mark-pass":
        checks = [c.strip() for c in args.checks.split(",") if c.strip()]
        path = mark_passed(key, checks=checks, project_root=str(Path(args.root).resolve()))
        print(json.dumps({"marked": True, "key": key, "path": str(path)}, sort_keys=True))
        return 0
    if args.command == "explain":
        root = Path(args.root)
        changed = _changed_paths(root)
        relevant = [
            path
            for path in changed
            if is_relevant_path(path, docs_are_behavior=args.docs_are_behavior)
        ]
        print(
            json.dumps(
                {
                    "key": key,
                    "mode": args.mode,
                    "changed_paths": changed,
                    "relevant_paths": relevant,
                    "ignored_paths": [path for path in changed if path not in relevant],
                },
                sort_keys=True,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
