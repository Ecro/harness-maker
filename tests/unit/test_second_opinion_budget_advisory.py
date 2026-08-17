"""Budget-proximity advisory: a Python threshold, not a prose one.

`/hm:health`'s smoke says "do not analyse anything" and was measured at 117s against a
240s cap while every real call was failing outright. Green health at 49% margin coexisted
with 100% real-call failure for weeks. This narrows that gap by making the MARGIN visible
instead of only the binary outcome.

Why Python and not `health.md.j2`: `readiness.py` has zero references to
`second_opinion_invoke`, so the smoke is executed by the LLM reading the template. A
threshold written there would be an LLM-judged latency check with no execution surface —
the shape that shipped four silent-skip bugs in this exact subsystem.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import second_opinion_invoke as soi


@pytest.mark.parametrize(
    ("duration", "budget", "expected"),
    [
        (0.0, 240.0, False),
        (59.9, 240.0, False),  # just under 25%
        (60.0, 240.0, True),  # exactly at the threshold — boundary is inclusive
        (117.0, 240.0, True),  # the real 2026-08-08 smoke measurement
        (239.0, 240.0, True),
        (28.0, 240.0, False),  # the chosen model's real cost: comfortably quiet
    ],
    ids=["zero", "just-under", "at-boundary", "the-117s-smoke", "near-cap", "healthy"],
)
def test_threshold_fires_at_and_above_the_fraction(
    duration: float, budget: float, expected: bool
) -> None:
    assert soi.exceeds_budget_fraction(duration, budget=budget) is expected


def test_threshold_is_a_fraction_of_the_real_agy_budget() -> None:
    """The default budget must be agy's OWN timeout, not an invented number.

    If these drift apart the advisory measures the wrong cap and goes quiet exactly
    when the call is about to start timing out.
    """
    assert soi.BUDGET_ADVISORY_FRACTION == 0.25
    assert soi.exceeds_budget_fraction(soi.AGY_NATIVE_TIMEOUT_S * 0.25) is True
    assert soi.exceeds_budget_fraction(soi.AGY_NATIVE_TIMEOUT_S * 0.24) is False


def test_nonsense_budget_never_fires() -> None:
    """A zero/negative budget must not divide-by-zero or fire spuriously.

    The advisory is decoration on a health check; crashing it would be worse than the
    silence it replaces.
    """
    assert soi.exceeds_budget_fraction(10.0, budget=0.0) is False
    assert soi.exceeds_budget_fraction(10.0, budget=-1.0) is False


def test_advisory_message_names_both_numbers_and_the_remedy() -> None:
    text = soi.budget_advisory_message(117.0, budget=240.0, stage="health")
    assert "117" in text
    assert "240" in text
    assert "model" in text.lower(), "an operator needs to know WHICH knob to turn"


def test_invoke_returns_duration_so_it_crosses_the_process_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`duration_s` must be in the RESULT, not only in the ledger row.

    The health smoke runs the invoker as a subprocess and reads its one JSON line. A
    value that only reaches the ledger cannot be seen by the caller that has to decide
    whether to warn.
    """
    import json
    import subprocess

    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / "harness.yaml").write_text(
        "second_opinion:\n  models: ['antigravity']\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    def _fake(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        payload = {"findings": [], "summary": "s", "confidence": 1.0}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", _fake)
    result = soi.invoke(
        model="antigravity", prompt="p", slug="s", stage="health", base_root=tmp_path
    )
    assert result["status"] == "invoked", result["reason"]
    assert isinstance(result["duration_s"], float)
    assert result["duration_s"] >= 0.0


def test_message_wording_is_stage_dependent() -> None:
    """The inference differs by stage, so the sentence must too.

    On `health` the prompt is deliberately trivial, so nearing the cap means real calls
    are already failing. On `review`/`plan` the call just SUCCEEDED at that cost, so the
    honest claim is headroom. Emitting the smoke sentence there asserts a failure that
    did not happen — misattribution, in the module whose docstring names misattribution
    as the class it exists to remove.
    """
    health = soi.budget_advisory_message(117.0, budget=240.0, stage="health")
    review = soi.budget_advisory_message(117.0, budget=240.0, stage="review")

    assert "trivial smoke" in health
    assert "already failing" in health
    assert "trivial smoke" not in review
    assert "already failing" not in review
    assert "review" in review
    # Both must still name the knob — the whole point of the line.
    for text in (health, review):
        assert "second_opinion.antigravity.model" in text


def test_invoke_never_raises_when_root_resolution_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`Path.resolve()` sat outside the terminal guard — a raise escaped `invoke()`.

    That broke the never-raise contract AND wrote zero ledger rows, in the one function
    whose docstring promises neither can happen.
    """
    import json

    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / "harness.yaml").write_text(
        "second_opinion:\n  models: ['antigravity']\n", encoding="utf-8"
    )

    def _boom(_self: Any) -> Any:
        raise OSError("ELOOP: too many levels of symbolic links")

    monkeypatch.setattr(Path, "resolve", _boom)

    def _fake_run(argv: list[str], **_kw: Any) -> Any:
        import subprocess

        payload = {"findings": [], "summary": "s", "confidence": 1.0}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = soi.invoke(
        model="antigravity", prompt="p", slug="s", stage="review", base_root=tmp_path
    )
    assert isinstance(result, dict)
    assert result["status"] in {"invoked", "skipped", "failed"}


def test_unreadable_prompt_file_emits_a_ledger_row_and_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `main()` early-return used to bypass `_result` entirely.

    Two consequences it is worth pinning: skip-rate telemetry omitted this failure class
    (no row at all), and once `duration_s` joined the result contract this became the one
    path whose shape differed from every other.
    """
    import json

    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / "harness.yaml").write_text(
        "second_opinion:\n  models: ['antigravity']\n", encoding="utf-8"
    )
    missing = tmp_path / "does-not-exist.txt"

    rc = soi.main(
        [
            "--model",
            "antigravity",
            "--prompt-file",
            str(missing),
            "--slug",
            "s",
            "--stage",
            "review",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0

    ledger = tmp_path / ".claude" / "observability" / "second-opinion.jsonl"
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x]
    assert len(rows) == 1, "the unreadable-prompt class must not be invisible to skip-rate"
    assert rows[0]["status"] == "skipped"
    assert isinstance(rows[0]["duration_s"], float)


def test_packaged_schema_does_not_leak_when_the_write_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The unlink-on-raising-write had no discriminating test; this is it.

    `_packaged_schema` returns the path, so a raise between `mkstemp` and `return` leaves
    an empty temp file nobody owns. It is on the hot antigravity path now — every review.
    """
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    real_open = open

    def _boom(*args: Any, **kwargs: Any) -> Any:
        if args and isinstance(args[0], int):
            raise OSError("ENOSPC: no space left on device")
        return real_open(*args, **kwargs)

    monkeypatch.setattr("builtins.open", _boom)
    with pytest.raises(OSError, match="ENOSPC"):
        soi._packaged_schema()

    monkeypatch.undo()
    leaked = list(tmp_path.glob("hm-so-schema-*"))
    assert not leaked, f"temp schema leaked on a failed write: {leaked}"
