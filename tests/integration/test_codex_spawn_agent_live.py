"""The shipped Codex dispatch instruction is one the Codex runtime actually executes.

Every other gate in this change proves the instruction is PRESENT and well-shaped. None of them
can prove Codex honours it — and "present but not honoured" is this defect's entire shape: the
old render carried `Task(` into Codex skills, every render test passed, and the runtime silently
improvised. So one live run, guarded by `INTEGRATION=1` (ADR-005): a third-party CLI, a login
and network are not allowed into the default quality gate.

**The oracle is runtime-emitted, not model-narrated.** `codex exec --json` emits
`{"type": "item.completed", "item": {"type": "collab_tool_call", "tool": "spawn_agent", …}}`
with the spawned thread's id and its reply in `agents_states`. A model that merely *says* it
delegated cannot produce those records. An assertion phrased any other way — "the output
mentions a sub-agent" — is satisfiable by an echo, which is exactly how the original bug
produced confident prose about work that never happened.

The event name was **measured, not assumed**. ADR-005 first specified
`collab_agent_spawn_begin` / `sub_agent_activity`, both of which appear in the binary's strings
and neither of which `codex exec --json` emits. Asserting on them would have been the same
class of defect this file exists to close. See `tests/manual/CODEX_SPAWN_AGENT_PROBE.md`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from harness_maker.models import DevMode, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"), reason="live codex CLI; set INTEGRATION=1"
)

_SENTINEL = "HM-DISPATCH-OK"
_TIMEOUT_S = 900
_DISPATCH_LINE = re.compile(r'^spawn_agent\(agent_type="(?P<agent>[^"]+)", message=".*$', re.M)


def _render_fixture(root: Path) -> None:
    """A real harness on disk, so `agent_type` resolves against real `.codex/agents/*.toml`.

    `target_dir` is the `.claude` directory; Codex outputs land in its parent, which is why the
    render is rooted one level down rather than at `root` itself.
    """
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE, Target.CODEX],
            dev_mode=DevMode.SPEC_DRIVEN,
        ),
    )
    render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)


def _shipped_instruction(root: Path) -> tuple[str, str]:
    """Pull the intent sentence and one dispatch line out of what we actually ship.

    Hand-writing the prompt here would test a prompt this project does not ship. Only the
    message payload is replaced, with a trivial instruction whose reply is checkable.
    """
    skill = (root / ".agents" / "skills" / "hm-review" / "SKILL.md").read_text(encoding="utf-8")
    match = _DISPATCH_LINE.search(skill)
    assert match, "no rendered spawn_agent dispatch found in hm-review — the render changed"
    agent = match.group("agent")
    intro_start = skill.index("This skill explicitly authorises sub-agent delegation")
    # End at the FENCE, not the first blank line. The Codex intent block is two paragraphs —
    # the delegation authorisation and the join contract ("spawn them all, then WAIT") — so a
    # `\n\n` slice silently cuts the second one out and this test then exercises a prompt the
    # project does not ship. It cannot go red for that: the missing text is the only thing
    # guaranteed absent. The join paragraph and this slice were added in the same round.
    intro = skill[intro_start : skill.index("\n```", intro_start)].strip()
    assert "WAIT for every one" in intro, (
        "the shipped intent block lost its join contract, or this slice stopped capturing it"
    )
    call = f'spawn_agent(agent_type="{agent}", message="Reply with exactly {_SENTINEL}")'
    return intro, call


def _collab_calls(stdout: str) -> tuple[list[dict[str, object]], int]:
    """Returns the collab items AND the count of lines that looked like JSON and were not.

    The unparseable count is returned rather than swallowed: a truncated final line drops the
    very record this test asserts on, and silently continuing turns "the stream was cut" into
    "Codex did not dispatch" — a verdict about the artifact drawn from a fact about the pipe.
    """
    items: list[dict[str, object]] = []
    unparseable = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            unparseable += 1
            continue
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "collab_tool_call":
            items.append(item)
    return items, unparseable


def test_codex_executes_the_shipped_dispatch_instruction() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _render_fixture(root)
        assert (root / ".codex" / "agents" / "code-reviewer.toml").is_file(), (
            "the fixture rendered no agent roles — `agent_type` would resolve against nothing "
            "and a failure here would say 'Codex ignored us' when the fixture was empty"
        )
        intro, call = _shipped_instruction(root)

        argv = [
            "codex",
            "exec",
            "--json",
            # `--skip-git-repo-check`: the fixture is a tmpdir, and Codex refuses to run
            # outside a trusted directory with "Not inside a trusted directory". Without it the
            # run exits 1 before the model sees the prompt, which reads as "Codex ignored the
            # instruction" when nothing was ever asked.
            "--skip-git-repo-check",
            # `read-only` is sufficient and therefore correct: the oracle is the runtime's own
            # spawn record plus the sub-agent's reply, neither of which needs a write. The
            # write-capable grant was chosen for the lens-result-file oracle that ADR-005's
            # "Scope narrowed" correction dropped, and a stale grant is a grant.
            "--sandbox",
            "read-only",
            f"{intro}\n\n{call}",
        ]
        try:
            proc = subprocess.run(
                argv,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_S,
                check=False,
                # NO `start_new_session=True`. It was added believing it would let a timeout
                # reap the sub-agents; it does the opposite. `subprocess.run`'s timeout path
                # calls `Popen.kill()`, which signals the direct child only — a new session
                # additionally puts the tree out of reach of a terminal SIGINT, so a hung run
                # would leave MORE orphans, not fewer. Killing the group properly needs
                # `Popen` + `os.killpg`, which is more machinery than a single opt-in test
                # warrants; the shared group at least keeps Ctrl-C working.
            )
        except FileNotFoundError:
            pytest.skip("codex CLI not installed — nothing was asked, so nothing was ignored")
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - environment-dependent
            pytest.fail(f"codex exec did not finish within {_TIMEOUT_S}s: {exc}")

    calls, unparseable = _collab_calls(proc.stdout)

    # Environment failures must NOT read as "the shipped instruction is not executable" — that
    # verdict is this file's entire product, and attributing an expired login or a truncated
    # stream to the artifact is the misattribution the change itself exists to stop.
    assert proc.returncode == 0, (
        f"codex exec failed before any verdict about the instruction (exit={proc.returncode}). "
        f"This is an ENVIRONMENT failure, not evidence about the dispatch.\n"
        f"stderr tail: {proc.stderr[-800:]}"
    )
    assert not unparseable, (
        f"{unparseable} JSON line(s) in the event stream did not parse — the stream was "
        "truncated, so a missing spawn record proves nothing."
    )

    spawns = [c for c in calls if c.get("tool") == "spawn_agent"]
    assert spawns, (
        "Codex ran cleanly but emitted no spawn_agent collab_tool_call for the shipped "
        f"dispatch instruction.\nstderr tail: {proc.stderr[-500:]}"
    )

    replies = [
        str(state.get("message") or "")
        for call_item in calls
        for state in (call_item.get("agents_states") or {}).values()  # type: ignore[union-attr]
        if isinstance(state, dict)
    ]
    assert any(_SENTINEL in reply for reply in replies), (
        f"a sub-agent was spawned but never returned the sentinel; replies={replies!r}"
    )
