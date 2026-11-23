"""SPEC-maker-digest-session-id: Maker's digest command holds no shell variable.

No `allowed-tools` rule matches a command that holds a shell variable or `$HOME`, so the Claude
variant takes the id from the host's `${CLAUDE_SESSION_ID}` substitution; Codex keeps its shell
variable. Since SPEC-maker-digest-bash-step the command is a bash block, not a `!` injection; the
test ids keep their "injection" names so that SPEC's `test_ids` still resolve.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.render import test_render_maker_front_door as front
from tests.unit import test_world_model_digest as digest_tests

_REPO = Path(__file__).resolve().parents[2]
_GOLDEN = json.loads(
    (_REPO / "specs/SPEC-maker-digest-session-id.golden.json").read_text(encoding="utf-8")
)
_TOKEN = "${CLAUDE_SESSION_ID}"
# `$name`, `${…}`, `$(…)`, `$[…]`, a positional or special parameter, or a backtick; the `$'`
# that ends grep's pattern is none of them.
_EXPANSION = re.compile(r"\$[A-Za-z_0-9{(\[?@#$*!-]|`")
# `uv run --no-project --with <src> hm <module> <args…>` served by this interpreter.
_UV_SHIM = '#!/bin/sh\nshift 5\nmod="$1"\nshift\nexec "{py}" -m "harness_maker.$mod" "$@"\n'


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def get(config: str) -> Path:
        if config not in cache:
            cache[config] = front._bootstrap(tmp_path_factory.mktemp(config), *front._args(config))
        return cache[config]

    return get


def _command(repo: Callable[[str], Path], config: str, runtime: str) -> str:
    return front._injected_command(front._maker(repo, config, runtime), runtime)


@pytest.mark.parametrize("config", ["en", "ko"], ids=["AC-001-0", "AC-001-1"])
def test_ac_001_claude_injection_has_no_shell_expansion(
    config: str, repo: Callable[[str], Path]
) -> None:
    text = front._maker(repo, config, "claude-code")
    cmd = front._injected_command(text, "claude-code")
    assert f'--session-id "{_TOKEN}"' in cmd, cmd
    assert _EXPANSION.findall(cmd.replace(_TOKEN, "")) == [], cmd
    # The test render pins the `$HOME` plugin ref, the shape of every plugin-cache install.
    assert " --with ~/" in cmd, cmd
    tools = str(front._frontmatter(text)["allowed-tools"])
    grant = re.search(r"Bash\(([^()]* world_model):\*\)", tools)
    assert grant is not None
    assert cmd.startswith(grant.group(1) + " "), (grant.group(1), cmd)


@pytest.mark.parametrize(
    "row", _GOLDEN["AC-002"], ids=[f"AC-002-{i}" for i in range(len(_GOLDEN["AC-002"]))]
)
def test_ac_002_codex_command_unchanged(row: dict[str, Any], repo: Callable[[str], Path]) -> None:
    text = front._maker(repo, row["input"]["config"], row["input"]["runtime"])
    hm = front._HM_MEANS.search(text)
    assert hm is not None
    # S3: Codex runs the command in a shell, so its plugin path keeps the `$HOME` form.
    assert " --with $HOME/" in hm.group(1), hm.group(1)
    cmd = front._injected_command(text, row["input"]["runtime"])
    assert cmd.replace(hm.group(1), "<hm>") == row["expected"]["command"]


@pytest.mark.parametrize(
    "row", _GOLDEN["AC-003"], ids=[f"AC-003-{i}" for i in range(len(_GOLDEN["AC-003"]))]
)
def test_ac_003_substituted_id_decides_other_session(
    row: dict[str, Any], repo: Callable[[str], Path], tmp_path: Path
) -> None:
    cmd = _command(repo, "en", "claude-code")
    substituted = row["input"]["substituted"]
    assert _TOKEN in cmd, cmd
    if substituted is not None:
        cmd = cmd.replace(_TOKEN, substituted)  # what the host does before the shell sees it
    base = digest_tests._base(tmp_path)
    digest_tests._task(base, "demo")
    digest_tests._write_spans(
        base,
        [digest_tests._span(base, "demo", "end", "hm:spec", row["input"]["newest_row_session"])],
    )
    shim = tmp_path / "bin"
    shim.mkdir()
    uv = shim / "uv"
    uv.write_text(_UV_SHIM.format(py=sys.executable), encoding="utf-8")
    uv.chmod(0o755)
    bash = shutil.which("bash")
    assert bash is not None
    res = subprocess.run(  # noqa: S603 - fixed argv; the command under test comes from our render
        [bash, "-c", cmd],
        cwd=base,
        env={"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert res.returncode == 0, (res.stdout, res.stderr)
    lines = res.stdout.splitlines()
    assert len(lines) == 1, res.stdout
    payload = json.loads(lines[0])
    assert "unavailable" not in payload, payload
    task = digest_tests._task_entry(payload, "demo")
    assert task["other_session"] is row["expected"]["other_session"]
