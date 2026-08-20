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
from harness_maker.models import DevMode
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_BASH = shutil.which("bash")

#: A producer whose stdout a later step consumes through a file. The flag that must reach it is
#: the one an earlier draft lost to `tee`.
_PRODUCERS = ("review_consensus finalize", "review_churn measure")


_FIXTURE = Path(__file__).parent.parent / "fixtures" / "prod-firmware"


def _rendered_review(tmp_path: Path, dev_mode: DevMode) -> str:
    """The review command as a harness of this dev_mode actually receives it.

    Rendered to disk rather than read off the blueprint: the blueprint carries body hashes, and a
    hash is what let the snapshot fixtures bless this defect after regeneration.
    """
    prof = profile(_FIXTURE)
    answers = interview(prof, autoloop_mode=True).model_copy(update={"dev_mode": dev_mode})
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
@pytest.mark.parametrize("dev_mode", [DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN])
def test_producer_pipelines_are_syntactically_valid(tmp_path: Path, dev_mode: DevMode) -> None:
    body = _rendered_review(tmp_path, dev_mode)
    lines = _pipeline_lines(body)
    assert lines, "no producer pipeline rendered — the probe stopped matching"
    for line in lines:
        script = _substituted(line)
        result = subprocess.run(
            [str(_BASH), "-n", "-c", script], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"bash cannot parse:\n  {script}\n{result.stderr}"


@pytest.mark.parametrize("dev_mode", [DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN])
def test_every_flag_reaches_the_producer_not_the_pipe(tmp_path: Path, dev_mode: DevMode) -> None:
    """Nothing may sit between `|` and the end of the line except `tee` and its file.

    This is the exact defect: `--spec <path>` rendered after `| tee <file>` and became `tee`'s
    argv. Asserting on the text alone is what missed it, so assert on the STRUCTURE the shell
    sees — the segment after the pipe.
    """
    body = _rendered_review(tmp_path, dev_mode)
    for line in _pipeline_lines(body):
        after_pipe = line.split("|", 1)[1].strip()
        assert after_pipe.startswith("tee "), f"unexpected pipe target: {after_pipe}"
        tail = after_pipe.removeprefix("tee ").strip()
        assert not re.search(r"(^|\s)--", tail), (
            f"a flag landed on `tee` instead of the producer: {after_pipe!r}\n"
            "Flags belong before the pipe."
        )


@pytest.mark.parametrize("dev_mode", [DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN])
def test_producer_pipelines_do_not_mask_the_producer_exit_status(
    tmp_path: Path, dev_mode: DevMode
) -> None:
    """`a | tee f` reports `tee`'s status. The stage gates trust on the producer's exit 1.

    `review_churn measure` writes NOTHING to stdout when it fails, so without `pipefail` the
    round gets an empty file, `emit` reports it as unreadable, and the row's churn fields go null
    — indistinguishable on disk from a harness version that never measured churn, which is the
    one distinction the schema's null-vs-zero design exists to preserve.
    """
    body = _rendered_review(tmp_path, dev_mode)
    for line in _pipeline_lines(body):
        assert "set -o pipefail" in line, f"pipeline without pipefail:\n  {line}"


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
