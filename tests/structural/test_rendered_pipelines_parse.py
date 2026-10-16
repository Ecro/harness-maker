"""Rendered producer pipelines must parse as the shell, not merely read correctly.

A P0 shipped through every existing gate because all of them inspect the rendered TEXT.
`--spec` was appended after `| tee <file>`, so the shell handed it to `tee`, which rejects an
unrecognised long option and exits 1 — on a spec-driven harness Step 4d produced no payload and
`review_consensus finalize` never received the flag whose absence silently disables AC-cited
rejections. The snapshot fixtures include spec-driven variants, but they compare body hashes, so
regenerating them after the change simply blessed the broken line.

CLAUDE.md 체크포인트 2 states the rule this file implements: a defect in what the CONSUMER does
with a rendered file cannot be found by reading that file, only by running the consumer. Here the
consumer is the shell, and `bash -n` plus an argv probe is the cheapest honest form of running it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_BASH = shutil.which("bash")

#: A producer whose stdout a later step consumes through a file. The flag that must reach it is
#: the one an earlier draft lost to `tee`.
_PRODUCERS = ("review_consensus finalize", "review_churn measure")


_FIXTURE = Path(__file__).parent.parent / "fixtures" / "prod-firmware"


def _rendered_review(tmp_path: Path, strictness: str) -> str:
    """The review command as a harness of this dev_mode actually receives it.

    Rendered to disk rather than read off the blueprint: the blueprint carries body hashes, and a
    hash is what let the snapshot fixtures bless this defect after regeneration.
    """
    prof = profile(_FIXTURE)
    answers = interview(prof, autoloop_mode=True).model_copy(update={"strictness": strictness})
    render(synthesize(prof, answers), tmp_path, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


def _substituted(line: str) -> str:
    """The line as the SHELL sees it, after the model fills in the placeholders.

    `<WT>`, `<FINALIZE-r{N}>` and friends are slots, not syntax — bash would read the angle
    brackets as redirections, so parsing the raw line tests the placeholder convention rather
    than the command. Substituting a plain token first is what makes `bash -n` answer the
    question actually being asked: does the command the operator runs parse?
    """
    script = line.lstrip("!").removeprefix('Bash("').removesuffix('")')
    script = re.sub(r"<[^<>]*>", "PLACEHOLDER", script)
    return re.sub(r"\{[^{}]*\}", "PLACEHOLDER", script)


def _pipeline_lines(body: str) -> list[str]:
    """Every rendered shell line that pipes a producer's stdout somewhere."""
    return [
        line for line in body.splitlines() if "|" in line and any(p in line for p in _PRODUCERS)
    ]








@pytest.mark.skipif(_BASH is None, reason="bash is the consumer under test")
def test_pipefail_actually_propagates_here() -> None:
    """The guarantee the assertion above depends on, measured rather than assumed."""
    masked = subprocess.run(
        [str(_BASH), "-c", "false | tee /dev/null"], capture_output=True, timeout=10
    )
    guarded = subprocess.run(
        [str(_BASH), "-c", "set -o pipefail; false | tee /dev/null"],
        capture_output=True,
        timeout=10,
    )
    assert masked.returncode == 0, "premise changed: a bare pipeline no longer masks failure"
    assert guarded.returncode != 0, "pipefail did not propagate the producer's status"
