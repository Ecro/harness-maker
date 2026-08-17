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
    tmp_path: Path, yaml_path: Path, md_path: Path, mode: str = "task-driven"
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
                "--dev-mode",
                mode,
            ]
        )
    return rc, json.loads(buf.getvalue())


def test_one_call_returns_all_three_blocks(tmp_path: Path) -> None:
    """The whole reason this exists: three round-trips' worth of verdicts in one payload."""
    rc, payload = _run(tmp_path, *_pair(tmp_path))
    assert set(payload) >= {"ok", "validate", "cross_validate", "quality"}
    assert payload["validate"]["ok"] is True
    assert payload["cross_validate"]["ok"] is True
    assert "overall" in payload["quality"]
    assert "scores" in payload["quality"]
    assert rc == 0
    assert payload["ok"] is True


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
    """`blocked` is spec-driven-only — task-driven must keep exiting 0 on a weak spec."""
    yaml_path, md_path = _pair(tmp_path)
    md_path.write_text("---\ntier: 1\n---\n\n### AC-001: render emits content_hash\n", "utf-8")
    rc, payload = _run(tmp_path, yaml_path, md_path, mode="task-driven")
    assert payload["quality"]["blocked"] is False
    assert rc == 0 or payload["cross_validate"]["ok"] is False


def test_the_subcommand_is_registered_so_the_misroute_guard_does_not_eat_it() -> None:
    from harness_maker import command_registry

    assert "check" in command_registry.MODULES["spec_machine"].subcommands


def test_all_is_required(tmp_path: Path) -> None:
    """`check` without `--all` must not silently mean something narrower."""
    yaml_path, md_path = _pair(tmp_path)
    with pytest.raises(SystemExit):
        main(["check", "--yaml", str(yaml_path), "--md", str(md_path)])
