"""Live proof that agy's structured-output mode exists and works from a worktree cwd.

This is the only test class that can catch the defect this task fixes. Six sites in the
repo asserted "agy has NO `--output-schema`" — true as spelled, false as understood, since
the flag is `--json-schema` behind `--output-format json`. No render-grep and no mocked
unit test could have refuted that claim, because every one of them agreed with it by
construction (`[[wiki:architecture]] second-opinion-invoker`: an external contract a
rendered prompt executes must be exercisable by a test, or it will be wrong and report
success).

The cwd half matters independently: `/hm:` stages run inside `.worktrees/<slug>/`, and the
codex leg already shipped a bug where a cwd-relative schema path made `codex exec` exit 1
on the harness's NORMAL Production path while the degrade recorded `skipped`.

Gated behind `INTEGRATION=1` per CLAUDE.md; needs a logged-in `agy` on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from harness_maker import second_opinion_invoke as soi

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"), reason="live agy call; set INTEGRATION=1"
)


def _agy_available() -> bool:
    return shutil.which("agy") is not None


@pytest.mark.skipif(not _agy_available(), reason="agy not on PATH")
def test_agy_accepts_the_schema_flags_and_returns_a_usable_payload(tmp_path: Path) -> None:
    """The capability claim itself: schema flags accepted, payload usable.

    Asserts only what the invoker depends on. `structured_output` is deliberately NOT
    required to be present — it is best-effort (observed absent on a `status: SUCCESS`
    reply from another tier), and requiring it here would make this test assert a
    stronger contract than the production code does.
    """
    schema = soi._packaged_schema()
    try:
        argv = soi.build_agy_argv(
            prompt=(
                "This is a liveness check. Do not analyse anything. "
                "Return a finding list with an empty `findings` array."
            ),
            model=soi.DEFAULT_ANTIGRAVITY_MODEL,
            schema_path=schema,
        )
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=soi.AGY_TIMEOUT_S)
    finally:
        schema.unlink(missing_ok=True)

    assert proc.returncode == 0, (
        f"agy rejected the structured-output argv: {proc.stderr[-400:]}. "
        "If this is the '--json-schema can only be used when --output-format is json' "
        "error, the two flags have been decoupled in build_agy_argv."
    )
    envelope = json.loads(proc.stdout)
    assert envelope["status"] == "SUCCESS", envelope.get("response", "")[:300]
    # The invoker reads exactly one of these two; neither being usable is case 4b.
    structured = envelope.get("structured_output")
    assert isinstance(structured, dict) or isinstance(envelope.get("response"), str)


@pytest.mark.skipif(not _agy_available(), reason="agy not on PATH")
def test_invoke_succeeds_from_a_worktree_cwd(tmp_path: Path, monkeypatch) -> None:
    """The packaged schema is materialised into a temp file, so cwd cannot break it.

    Probed 2026-08-08 by hand from `.worktrees/<slug>/` with an absolute base-root path:
    rc=0 in ~10s with a valid `structured_output`. `--json-schema` is consumed by agy's
    own argument handling; `--sandbox` governs the tools exposed to the model, which is
    why an out-of-workspace schema path is not a sandbox violation.
    """
    base = tmp_path / "base"
    (base / ".claude").mkdir(parents=True)
    (base / ".claude" / "harness.yaml").write_text(
        "second_opinion:\n  models: ['antigravity']\n", encoding="utf-8"
    )
    worktree = base / ".worktrees" / "some-slug"
    worktree.mkdir(parents=True)
    monkeypatch.chdir(worktree)

    result = soi.invoke(
        model="antigravity",
        prompt=(
            "This is a liveness check. Do not analyse anything. "
            "Return a finding list with an empty `findings` array."
        ),
        slug="integration-probe",
        stage="health",
        base_root=base,
    )

    assert result["status"] == "invoked", result["reason"]
    assert result["findings"] == []
