"""SPEC-maker-digest-bash-step: Maker runs its digest as a first Bash step, never a `!` injection.

Claude Code checks an injected `!` command against the skill's `allowed-tools` only, and ignores a
repository skill's grant when CLAUDE_CODE_IGNORE_PERSISTED_TRUST is set; the load then dies at 0
turns. A model-issued Bash call follows the session's permission mode instead.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.render import test_render_maker_front_door as front

_PHRASE = "Run this first on every call, whatever the route"
_DIGEST = "world_model digest"
_BLOCK = re.compile(r"([^\n]*)\n\n```bash\n(.*?)\n```", flags=re.S)


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def get(config: str) -> Path:
        if config not in cache:
            cache[config] = front._bootstrap(tmp_path_factory.mktemp(config), *front._args(config))
        return cache[config]

    return get


@pytest.mark.parametrize("config", ["en", "ko"], ids=["AC-001-0", "AC-001-1"])
def test_ac_001_digest_is_a_first_bash_step(config: str, repo: Callable[[str], Path]) -> None:
    for runtime in ("claude-code", "codex"):
        text = front._maker(repo, config, runtime)
        injected = [
            ln
            for ln in text.splitlines()
            if _DIGEST in ln and (ln.lstrip().startswith("!") or "!`" in ln)
        ]
        assert injected == [], (runtime, injected)
        blocks = [(intro, body) for intro, body in _BLOCK.findall(text) if _DIGEST in body]
        assert len(blocks) == 1, (runtime, blocks)
        assert sum(ln.count(_DIGEST) for ln in text.splitlines() if "--session-id" in ln) == 1
        assert _PHRASE in blocks[0][0], (runtime, blocks[0][0])
