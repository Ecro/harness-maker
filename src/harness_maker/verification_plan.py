"""The gate commands a project's CI actually runs, read from CI instead of guessed.

Every stage that says "run the project's check suite" used to ship an EXAMPLE
(`mypy --strict src/`, `ruff check src/ tests/`). An example is a guess about
someone else's repository, and a guess that is wrong in the narrowing direction
is invisible: the local pass goes green over a subset while CI fails on the rest.
That is not hypothetical — this harness shipped two red commits in a row because
its own stages prescribed `mypy --strict src/` while its CI runs
`mypy --strict src tests`, so every type error in `tests/` was structurally
unreachable from the local gate.

So the plan is DERIVED. This reads `.github/workflows/*.yml`, keeps the workflows
that gate a commit (`push` / `pull_request`), and reports the runnable verification
commands it finds, each tagged with where it came from and whether CI treats it as
blocking.

Three properties are load-bearing, and each exists because its absence is a way to
be silently wrong:

- **Dropped commands are reported, never dropped silently.** A step this module
  cannot classify appears in `unclassified` with its command and reason. A reader
  that trims its own input and says nothing is how the original divergence hid.
- **`continue-on-error` is carried through.** Mirroring an advisory step as a
  blocking local gate is the same class of error in the opposite direction — it
  turns third-party drift into a failure of your change.
- **Degraded is explicit and non-empty.** No workflows, unparseable YAML, or zero
  classified commands all yield `degraded: true` with a reason, so the caller
  falls back to its own examples KNOWING it is guessing, rather than reading an
  empty gate list as "this project has no gates".
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from harness_maker import command_registry

#: Triggers that make a workflow gate a commit. A `schedule`/`tag` workflow (nightly,
#: release) may run the SAME commands, but it does not gate the push in front of you,
#: and treating a nightly's extra jobs as required locally would over-report.
_GATING_TRIGGERS = frozenset({"push", "pull_request"})

#: Command heads that are verification tools, mapped to the gate kind they represent.
#: Keyed on the token AFTER runner prefixes are stripped (`uv run`, `poetry run`, `npx`).
#:
#: Deliberately a small allowlist rather than a denylist of setup steps: an unknown
#: command is reported as `unclassified`, which is visible, whereas an unknown command
#: admitted as a gate would have the caller run `actions/checkout`-adjacent shell.
_TOOL_KINDS: dict[str, str] = {
    "pytest": "test",
    "mypy": "type",
    "ruff": "lint",
    "cargo": "test",
    "go": "test",
    "vitest": "test",
    "jest": "test",
    "eslint": "lint",
    "tsc": "type",
    "prettier": "format",
    "black": "format",
    "flake8": "lint",
    "pylint": "lint",
    "pyright": "type",
}

#: Prefixes that wrap a real command and carry no verification meaning of their own.
_RUNNER_PREFIXES = (
    ("uv", "run"),
    ("poetry", "run"),
    ("pipenv", "run"),
    ("pdm", "run"),
    ("hatch", "run"),
    ("npx",),
    ("pnpm", "exec"),
    ("yarn", "exec"),
    ("bunx",),
)


class WorkflowParseError(Exception):
    """A workflow file exists but could not be read as YAML.

    Carries the path so the caller can name the file rather than reporting a
    blanket "CI unreadable" that gives the user nothing to fix.
    """

    def __init__(self, path: Path, cause: str) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"{path}: {cause}")


@dataclass(frozen=True)
class Gate:
    """One verification command CI runs, with enough provenance to audit it."""

    kind: str
    cmd: str
    workflow: str
    job: str
    step: str
    blocking: bool
    #: The step's or job's `if:` expression, verbatim, when it has one. A conditional
    #: gate is still reported — the caller decides — but it must not look unconditional.
    condition: str | None = None


@dataclass
class VerificationPlan:
    """What CI runs, what this module could not classify, and whether it is trustworthy."""

    gates: list[Gate] = field(default_factory=list)
    unclassified: list[dict[str, str]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    #: Workflows that exist but do not gate a commit (schedule, tag, workflow_dispatch).
    #: Named, not hidden — a nightly running a stricter gate is worth knowing about.
    non_gating: list[str] = field(default_factory=list)
    degraded: bool = False
    reason: str | None = None

    def blocking_commands(self) -> list[str]:
        """Deduplicated blocking commands, first occurrence wins.

        Two workflows commonly run identical gates (this repo's `ci` and `nightly`
        both run `mypy --strict src tests`); the caller wants each command once.
        """
        seen: set[str] = set()
        out: list[str] = []
        for g in self.gates:
            if g.blocking and g.cmd not in seen:
                seen.add(g.cmd)
                out.append(g.cmd)
        return out

    def primary_commands(self) -> list[str]:
        """One blocking command per gate kind, in source order — what a stage should run.

        NOT every blocking command CI runs. Mirroring CI wholesale imports CI's
        environment with it: this repo's own workflow has a blocking job that first
        `npm install -g`s an external CLI, and running its tests on a machine without
        that CLI reports third-party absence as a failure of your change. The kind
        selection stays inside the tools the stage would otherwise have GUESSED —
        which is exactly the divergence this module exists to close — and everything
        it leaves out is listed by `additional_commands`, never dropped in silence.
        """
        chosen: dict[str, str] = {}
        for g in self.gates:
            if g.blocking and g.kind not in chosen:
                chosen[g.kind] = g.cmd
        return list(chosen.values())

    def additional_commands(self) -> list[str]:
        """Blocking CI commands the primary selection does NOT cover, so they stay visible."""
        primary = set(self.primary_commands())
        return [c for c in self.blocking_commands() if c not in primary]

    def to_json(self) -> dict[str, Any]:
        return {
            "gates": [asdict(g) for g in self.gates],
            "primary_commands": self.primary_commands(),
            "additional_commands": self.additional_commands(),
            "blocking_commands": self.blocking_commands(),
            "unclassified": self.unclassified,
            "sources": self.sources,
            "non_gating": self.non_gating,
            "degraded": self.degraded,
            "reason": self.reason,
        }


def _strip_runner_prefix(tokens: list[str]) -> list[str]:
    """Drop `uv run` / `npx` / … so the tool name is the head token.

    Loops because wrappers nest in the wild (`uv run poetry run pytest`).
    """
    changed = True
    while changed and tokens:
        changed = False
        for prefix in _RUNNER_PREFIXES:
            if len(tokens) > len(prefix) and tuple(tokens[: len(prefix)]) == prefix:
                tokens = tokens[len(prefix) :]
                changed = True
                break
    return tokens


def _classify(cmd: str) -> str | None:
    """Return the gate kind for a command, or None when it is not a verification tool."""
    tokens = cmd.split()
    if not tokens:
        return None
    tokens = _strip_runner_prefix(tokens)
    if not tokens:
        return None
    head = tokens[0].rsplit("/", 1)[-1]  # `./node_modules/.bin/eslint` → `eslint`
    kind = _TOOL_KINDS.get(head)
    if kind is None:
        return None
    verb = tokens[1] if len(tokens) > 1 else ""
    # `go build` / `cargo build` are not verification. Only the verbs that check.
    if head in ("go", "cargo") and verb not in ("test", "vet", "check"):
        return None
    # One binary, two gates: `ruff check` and `ruff format --check` are different kinds,
    # and collapsing them to the head token makes the format gate invisible behind the
    # lint one when the caller selects one command per kind.
    if head == "ruff":
        return "format" if verb == "format" else "lint"
    return kind


def _split_run_block(block: str) -> list[str]:
    """One `run:` value → its individual commands.

    Handles the `run: |` multi-line form and line continuations. Shell operators are
    NOT split on: `cargo test && cargo check` is one command the caller should run
    verbatim, and splitting it would drop the second half's dependence on the first.
    """
    out: list[str] = []
    buffer = ""
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            buffer += line[:-1].strip() + " "
            continue
        out.append((buffer + line).strip())
        buffer = ""
    if buffer.strip():
        out.append(buffer.strip())
    return out


def _workflow_triggers(doc: Mapping[Any, Any]) -> set[str]:
    """The trigger names of a workflow.

    `on` is the YAML 1.1 boolean `True` after `safe_load` — the notorious Norway
    problem in its most load-bearing form here, because reading the key as the
    string `"on"` finds nothing and every workflow silently becomes non-gating.
    """
    raw = doc.get("on", doc.get(True))
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {str(x) for x in raw}
    if isinstance(raw, dict):
        return {str(k) for k in raw}
    return set()


def _truthy(value: Any) -> bool:
    """`continue-on-error` may arrive as a bool or as an expression string."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "yes", "1")


def read_plan(root: Path) -> VerificationPlan:
    """Derive the verification plan from the project's CI workflows.

    Never raises for a missing or malformed CI: those are `degraded` results with a
    reason, because the caller's fallback (its own example commands) is a legitimate
    path and an exception would turn a guessable situation into a stage failure.
    """
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return VerificationPlan(degraded=True, reason=f"no workflows directory at {wf_dir}")

    files = sorted(p for p in wf_dir.iterdir() if p.suffix in (".yml", ".yaml"))
    if not files:
        return VerificationPlan(degraded=True, reason=f"no workflow files in {wf_dir}")

    plan = VerificationPlan()
    unreadable: list[str] = []
    for path in files:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            unreadable.append(f"{path.name}: {exc.__class__.__name__}")
            continue
        if not isinstance(doc, dict):
            unreadable.append(f"{path.name}: not a mapping")
            continue

        if not (_workflow_triggers(doc) & _GATING_TRIGGERS):
            plan.non_gating.append(path.name)
            continue
        plan.sources.append(path.name)

        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            job_coe = _truthy(job.get("continue-on-error", False))
            job_if = job.get("if")
            steps = job.get("steps")
            if not isinstance(steps, list):
                continue
            for step in steps:
                if not isinstance(step, dict):
                    continue
                run = step.get("run")
                if not isinstance(run, str):
                    continue
                step_name = str(step.get("name") or "(unnamed step)")
                blocking = not (job_coe or _truthy(step.get("continue-on-error", False)))
                cond = step.get("if") or job_if
                for cmd in _split_run_block(run):
                    kind = _classify(cmd)
                    if kind is None:
                        plan.unclassified.append(
                            {
                                "cmd": cmd,
                                "workflow": path.name,
                                "job": str(job_name),
                                "step": step_name,
                                "reason": "not a recognised verification tool",
                            }
                        )
                        continue
                    plan.gates.append(
                        Gate(
                            kind=kind,
                            cmd=cmd,
                            workflow=path.name,
                            job=str(job_name),
                            step=step_name,
                            blocking=blocking,
                            condition=str(cond) if cond is not None else None,
                        )
                    )

    if unreadable:
        plan.degraded = True
        plan.reason = "unreadable workflow(s): " + "; ".join(unreadable)
    elif not plan.gates:
        plan.degraded = True
        plan.reason = "no verification command recognised in the commit-gating workflow(s): " + (
            ", ".join(plan.sources) or "none found"
        )
    return plan


def main(argv: list[str] | None = None) -> int:
    # Redirect a verb that belongs to a DIFFERENT module before argparse rejects it, so
    # the user is told where it lives instead of getting a bare "invalid choice".
    guard = command_registry.guard_or_none("verification_plan", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(prog="hm verification_plan")
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("show", help="print the CI-derived verification plan as JSON")
    show.add_argument("--root", default=".")
    cmds = sub.add_parser("commands", help="print blocking gate commands, one per line")
    cmds.add_argument("--root", default=".")

    opts = parser.parse_args(argv)
    plan = read_plan(Path(opts.root).resolve())

    if opts.cmd == "commands":
        for cmd in plan.primary_commands():
            sys.stdout.write(cmd + "\n")
        if plan.degraded:
            sys.stderr.write(f"[verification_plan] degraded: {plan.reason}\n")
            return 1
        return 0

    sys.stdout.write(json.dumps(plan.to_json(), sort_keys=True, indent=2) + "\n")
    return 1 if plan.degraded else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
