"""AC-003 — make --update never rewrites a hand-filled intent.

Property over arbitrary byte content (malformed YAML included): the write-if-absent operation
leaves an existing non-empty file byte-identical across two runs. The assertion is on the
bytes on disk, because the failure mode is silent deletion. `write_skeleton_if_absent` is the
one function `make` calls (PLAN P1 `cli.py` hook), so its invariance is the update's.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import intent

settings.register_profile("ci", derandomize=True, max_examples=60, deadline=None)
settings.register_profile("dev", max_examples=300, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))


# min_size=0 on purpose: a `touch`ed empty intent.yaml EXISTS and must not be clobbered either —
# write-if-absent is keyed on existence, never on content truthiness (A.5 round 1).
@given(content=st.binary(min_size=0, max_size=400))
def test_ac_003_existing_file_bytes_survive_two_runs(tmp_path_factory: Any, content: bytes) -> None:
    tmp_path: Path = tmp_path_factory.mktemp("intent")
    p = tmp_path / "intent.yaml"
    p.write_bytes(content)
    assert intent.write_skeleton_if_absent(p) is False
    assert p.read_bytes() == content
    assert intent.write_skeleton_if_absent(p) is False
    assert p.read_bytes() == content


def test_ac_003_make_hook_calls_the_write_if_absent_function() -> None:
    """The invariance above is only the update's if `make` routes through this function."""
    src = (Path(__file__).parents[2] / "src" / "harness_maker" / "cli.py").read_text(
        encoding="utf-8"
    )
    assert "write_skeleton_if_absent(" in src
