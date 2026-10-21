"""Phase 3 — `spec_machine check --all` returns the three verdicts spec Steps 4/4.5 read.

The point of the subcommand is that it ORCHESTRATES (PLAN ADR-003): every verdict must
come from `validate` / `cross_validate` / `evaluate_spec` unchanged. So the assertions
here are about *composition and attribution* — that all three blocks are present, that
the exit code is the disjunction, and that a cross-validate error is never silently
dropped on its way into the per-rule view. The rules themselves are already covered by
`test_spec_machine.py` and are deliberately not re-tested.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker.spec_machine import SCHEMA_VERSION, _attribute_cross_errors, main


def _pair(
    tmp_path: Path, *, ac_id: str = "AC-001", md_heading: str = "AC-001"
) -> tuple[Path, Path]:
    """A yaml/md pair that validates, so a failing assertion means a real defect."""
    yaml_path = tmp_path / "SPEC-x.machine.yaml"
    yaml_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": SCHEMA_VERSION,
                # Required from v3 (SPEC-ai-native-sdlc-vs-intent-world); [] = nothing irreversible.
                "irreversible_decisions": [],
                "spec_slug": "x",
                "verification_tier": 1,
                "mutation_threshold": 85,
                "paths_to_mutate": ["src/harness_maker/render.py"],
                "ac": [
                    {
                        "id": ac_id,
                        "title": "render emits content_hash",
                        "type": "mechanical",
                        "pending_test": True,
                        "executable_predicate": "'content_hash:' in render(answers())",
                        "oracle_source": "differential",
                        "oracle_evidence": "compared against the reference renderer golden",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    md_path = tmp_path / "SPEC-x.md"
    md_path.write_text(
        "---\ntier: 1\ntest_framework: pytest\n---\n\n"
        "## In-Scope Scenarios\n\n"
        "**Given** a config **When** rendered **Then** a content_hash appears.\n\n"
        f"### {md_heading}: render emits content_hash\n\nBody.\n",
        encoding="utf-8",
    )
    return yaml_path, md_path


def _run(
    tmp_path: Path, yaml_path: Path, md_path: Path, mode: str = "warn"
) -> tuple[int, dict[str, Any]]:
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(
            [
                "check",
                "--all",
                "--yaml",
                str(yaml_path),
                "--md",
                str(md_path),
                "--strictness",
                mode,
            ]
        )
    return rc, json.loads(buf.getvalue())


def test_one_call_returns_all_three_blocks(tmp_path: Path) -> None:
    """The whole reason this exists: three round-trips' worth of verdicts in one payload."""
    yaml_path, md_path = _pair(tmp_path, ac_id="AC-001", md_heading="AC-999")
    rc, payload = _run(tmp_path, yaml_path, md_path)
    assert set(payload) >= {"ok", "validate", "cross_validate", "quality"}
    assert payload["validate"]["ok"] is True
    assert "overall" in payload["quality"]
    # SPEC-hm-light-lane-s3c IRR-001: the dims that pull the score down, with their scores,
    # replace the full `scores` map.
    assert "low_dimensions" in payload["quality"]
    assert "scores" not in payload["quality"]
    assert rc == 1


@pytest.mark.parametrize(
    ("overall", "weak_dimensions", "compact"),
    [(88, [], True), (60, [], True), (59, [], False), (88, ["completeness"], False)],
)
def test_a_clean_pass_prints_one_short_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overall: int,
    weak_dimensions: list[str],
    compact: bool,
) -> None:
    """HM-LIGHT-LANE lever 4: every printed byte is re-read on each later turn of the session.

    A weak score (under 60, or any weak dimension) must still reach the spec stage as a warning.
    Since SPEC-hm-light-lane-s3c it does so on the same one line, which then names the weak and
    low dimensions; only a failed gate prints the full payload.
    """
    import contextlib
    import importlib
    import io

    # By name: an import here would count it as CLI-driven (test_cli_surfaces_are_driven).
    result_type = importlib.import_module("harness_maker.spec_quality").SpecQualityResult
    stub = result_type(
        overall=overall,
        scores={"completeness": overall},
        weak_dimensions=weak_dimensions,
        blocked=False,
        strictness="block",
    )
    monkeypatch.setattr("harness_maker.spec_quality.evaluate_spec", lambda *a, **k: stub)
    yaml_path, md_path = _pair(tmp_path)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(
            [
                "check",
                "--all",
                "--yaml",
                str(yaml_path),
                "--md",
                str(md_path),
                "--strictness",
                "warn",
            ]
        )
    out = buf.getvalue()
    assert rc == 0
    payload = json.loads(out)
    assert out.count("\n") == 1
    assert set(payload.pop("approval")) == {"state", "land", "gate"}  # SPEC-hm-cost-p2 AC-005
    if compact:
        # strictness comes from the quality result, as in the full payload.
        assert payload == {"ok": True, "overall": overall, "strictness": "block"}
    else:
        assert payload["weak_dimensions"] == weak_dimensions
        assert payload["low_dimensions"] == {
            d: s for d, s in {"completeness": overall}.items() if s < 60
        }
        assert "validate" not in payload


def test_a_failed_gate_never_collapses_even_with_a_clean_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The compact line says `ok: true`; printing it over a failed gate would hide the failure."""
    import importlib

    result_type = importlib.import_module("harness_maker.spec_quality").SpecQualityResult
    stub = result_type(
        overall=88,
        scores={"completeness": 88},
        weak_dimensions=[],
        blocked=False,
        strictness="warn",
    )
    monkeypatch.setattr("harness_maker.spec_quality.evaluate_spec", lambda *a, **k: stub)
    yaml_path, md_path = _pair(tmp_path, ac_id="AC-001", md_heading="AC-999")
    rc, payload = _run(tmp_path, yaml_path, md_path)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["cross_validate"]["ok"] is False


def test_a_cross_validate_failure_is_attributed_to_its_rule_and_fails_the_call(
    tmp_path: Path,
) -> None:
    yaml_path, md_path = _pair(tmp_path, ac_id="AC-001", md_heading="AC-999")
    rc, payload = _run(tmp_path, yaml_path, md_path)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["cross_validate"]["ok"] is False
    assert payload["cross_validate"]["by_rule"]["rule-1"], "rule-1 error was not attributed"


def test_an_unloadable_yaml_reports_both_gates_rather_than_crashing(tmp_path: Path) -> None:
    yaml_path, md_path = _pair(tmp_path)
    yaml_path.write_text("{not: valid: yaml: at all\n", encoding="utf-8")
    rc, payload = _run(tmp_path, yaml_path, md_path)
    assert rc == 1
    assert payload["validate"]["ok"] is False
    assert payload["cross_validate"]["ok"] is False


def test_an_untagged_cross_error_lands_in_unattributed_not_nowhere(tmp_path: Path) -> None:
    """A per-rule view that drops the untagged `yaml load failed` would report six clean rules."""
    buckets = _attribute_cross_errors(["yaml load failed: boom", "rule-3: nope"])
    assert buckets["unattributed"] == ["yaml load failed: boom"]
    assert buckets["rule-3"] == ["rule-3: nope"]
    assert sum(len(v) for v in buckets.values()) == 2, "an error was dropped"


def test_task_driven_does_not_block_on_a_weak_score(tmp_path: Path) -> None:
    """`blocked` is block-only — warn must keep exiting 0 on a weak spec."""
    yaml_path, md_path = _pair(tmp_path)
    md_path.write_text("---\ntier: 1\n---\n\n### AC-001: render emits content_hash\n", "utf-8")
    rc, payload = _run(tmp_path, yaml_path, md_path, mode="warn")
    # No failed gate prints the one line, which never carries `blocked` (SPEC-hm-light-lane-s3c).
    assert payload.get("quality", {}).get("blocked", False) is False
    assert rc == 0 or payload["cross_validate"]["ok"] is False


def test_the_subcommand_is_registered_so_the_misroute_guard_does_not_eat_it() -> None:
    from harness_maker import command_registry

    assert "check" in command_registry.MODULES["spec_machine"].subcommands


def test_all_is_required(tmp_path: Path) -> None:
    """`check` without `--all` must not silently mean something narrower."""
    yaml_path, md_path = _pair(tmp_path)
    with pytest.raises(SystemExit):
        main(["check", "--yaml", str(yaml_path), "--md", str(md_path)])
