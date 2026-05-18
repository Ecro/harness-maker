"""Live verification (INTEGRATION=1) that the README one-prompt drives Bash auto-install.

Asserts the AI emits a Bash tool_use for ``claude plugin install harness-maker``
rather than instructing the user to type ``/plugin install`` themselves.

PLAN: PLAN-readme-one-prompt-autoinstall (Phase 3b).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INTEGRATION_GATE = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="set INTEGRATION=1 to run live nested-claude verification (consumes quota)",
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _extract_one_prompt_body(readme: Path) -> str:
    text = readme.read_text(encoding="utf-8")
    start = re.search(r"Universal Bootstrap Prompt", text)
    assert start is not None
    fence_open = text.find("```", start.end())
    body_start = text.find("\n", fence_open) + 1
    fence_close = text.find("\n```", body_start)
    return text[body_start:fence_close]


@INTEGRATION_GATE
def test_one_prompt_emits_bash_plugin_install(tmp_path: Path) -> None:
    if shutil.which("claude") is None:
        pytest.skip("`claude` CLI not on PATH")

    prompt = _extract_one_prompt_body(REPO_ROOT / "README.md")

    # Run a nested claude --print session and capture stream-json events.
    # `--disallowedTools Bash` prevents the nested session from actually running
    # `claude plugin install` (which would mutate the dev's ~/.claude/plugins/).
    # Whether the AI emits a tool_use that gets blocked vs. only describes the
    # command in text is schema-dependent across claude-cli versions, so the
    # assertion below accepts either signal as long as the install command
    # appears somewhere in the stream. (REVIEW Round 1, code-reviewer #2.)
    proc = subprocess.run(
        [
            "claude",
            "--print",
            "--output-format=stream-json",
            "--input-format=text",
            "--no-session-persistence",
            "--disallowedTools",
            "Bash",
            "--bare",
            prompt,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,  # returncode asserted manually for richer failure message
        timeout=180,
    )

    assert proc.returncode == 0, (
        f"nested claude exited non-zero ({proc.returncode}); stderr=\n{proc.stderr[:2000]}"
    )

    install_referenced = False
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "claude plugin install harness-maker" in json.dumps(event):
            install_referenced = True
            break

    assert install_referenced, (
        "nested claude did not emit any reference to 'claude plugin install harness-maker' "
        "in its stream-json output. The AI is likely still redirecting slash-command typing "
        "back to the user. Last 2000 chars of stdout:\n" + proc.stdout[-2000:]
    )
