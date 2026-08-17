"""Tests for spec_need module (Phase 1 of PLAN-spec-requirement-gate).

Covers:
- prefilter: hit / miss / judgment-subject-path overlap / empty (no overlap) / malformed degrade
- record_spec_need: writes JSONL including not-evaluated; no-raise on bad path
- operation_satisfied: per-verdict + absent-case
- waiver: write+valid (same diff); stale after diff change; reasonless raises; missing → False
- marker: write→read→clear; fresh True / False (stale hash); one-shot (clear → read None)
- worktree: present .hm-spec-need-demo marker recognized by _is_harness_artifact
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker.spec_need import (
    _validate_slug,
    clear_marker,
    marker_fresh,
    marker_path,
    operation_satisfied,
    prefilter,
    read_marker,
    record_spec_need,
    waiver_valid,
    write_marker,
    write_waiver,
)

# ---------------------------------------------------------------------------
# Helpers to build machine YAML files
# ---------------------------------------------------------------------------


def _write_machine_yaml(
    path: Path, *, slug: str, paths_to_mutate: list[str], acs: list[dict[str, Any]]
) -> None:
    """Write a valid SPEC-*.machine.yaml to `path`."""
    data: dict[str, Any] = {
        "schema_version": 1,
        "spec_slug": slug,
        "verification_tier": 2,
        "paths_to_mutate": paths_to_mutate,
        "ac": acs,
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


def _write_machine_yaml_v2_judgment(
    path: Path,
    *,
    slug: str,
    paths_to_mutate: list[str],
    judgment_subject_paths: list[str],
) -> None:
    """Write a v2 judgment AC machine.yaml."""
    data: dict[str, Any] = {
        "schema_version": 2,
        "spec_slug": slug,
        "verification_tier": 1,
        "paths_to_mutate": paths_to_mutate,
        "ac": [
            {
                "id": "AC-001",
                "title": "judgment ac",
                "type": "judgment",
                "rubric_id": "test-rubric",
                "oracle_source": "rubric",
                "oracle_evidence": "independent reviewer",
                "judgment_subject_paths": judgment_subject_paths,
            }
        ],
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


def _mechanical_ac(ac_id: str = "AC-001") -> dict:  # type: ignore[type-arg]
    return {
        "id": ac_id,
        "title": "test ac",
        "type": "mechanical",
        "executable_predicate": "f() == 1",
        "test_ids": ["test_foo"],
    }


# ---------------------------------------------------------------------------
# prefilter
# ---------------------------------------------------------------------------


class TestPrefilter:
    def test_hit_paths_to_mutate(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        _write_machine_yaml(
            specs / "SPEC-foo.machine.yaml",
            slug="foo",
            paths_to_mutate=["src/foo.py", "src/bar.py"],
            acs=[_mechanical_ac()],
        )
        result = prefilter(specs, ["src/foo.py", "tests/other.py"])
        assert len(result) == 1
        assert result[0]["slug"] == "foo"
        assert "src/foo.py" in result[0]["overlap"]
        assert "tests/other.py" not in result[0]["overlap"]

    def test_miss_no_overlap(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        _write_machine_yaml(
            specs / "SPEC-foo.machine.yaml",
            slug="foo",
            paths_to_mutate=["src/foo.py"],
            acs=[_mechanical_ac()],
        )
        result = prefilter(specs, ["src/other.py"])
        assert result == []

    def test_empty_no_overlap_returns_empty_list(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        _write_machine_yaml(
            specs / "SPEC-foo.machine.yaml",
            slug="foo",
            paths_to_mutate=["src/alpha.py"],
            acs=[_mechanical_ac()],
        )
        # No changed files at all → no overlap
        result = prefilter(specs, [])
        assert result == []

    def test_judgment_subject_paths_overlap(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        _write_machine_yaml_v2_judgment(
            specs / "SPEC-bar.machine.yaml",
            slug="bar",
            paths_to_mutate=[],  # empty paths_to_mutate
            judgment_subject_paths=["src/judged.py"],
        )
        result = prefilter(specs, ["src/judged.py"])
        assert len(result) == 1
        assert result[0]["slug"] == "bar"
        assert "src/judged.py" in result[0]["overlap"]

    def test_malformed_yaml_skipped_no_raise(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        bad = specs / "SPEC-bad.machine.yaml"
        bad.write_text(": invalid: yaml: {{ broken", encoding="utf-8")
        # A valid one alongside it
        _write_machine_yaml(
            specs / "SPEC-good.machine.yaml",
            slug="good",
            paths_to_mutate=["src/x.py"],
            acs=[_mechanical_ac()],
        )
        # Must not raise; bad one is silently skipped
        result = prefilter(specs, ["src/x.py"])
        assert len(result) == 1
        assert result[0]["slug"] == "good"

    def test_absent_specs_dir_returns_empty(self, tmp_path: Path) -> None:
        result = prefilter(tmp_path / "no-such-specs", ["src/foo.py"])
        assert result == []

    def test_sorted_by_slug(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        for slug in ["zzz", "aaa", "mmm"]:
            _write_machine_yaml(
                specs / f"SPEC-{slug}.machine.yaml",
                slug=slug,
                paths_to_mutate=["shared.py"],
                acs=[_mechanical_ac()],
            )
        result = prefilter(specs, ["shared.py"])
        assert [r["slug"] for r in result] == ["aaa", "mmm", "zzz"]

    def test_union_paths_to_mutate_and_judgment_subject_paths(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        _write_machine_yaml_v2_judgment(
            specs / "SPEC-combo.machine.yaml",
            slug="combo",
            paths_to_mutate=["src/a.py"],
            judgment_subject_paths=["src/b.py"],
        )
        # Both are in the union; changing b.py should hit
        result = prefilter(specs, ["src/b.py"])
        assert len(result) == 1
        assert "src/b.py" in result[0]["overlap"]


# ---------------------------------------------------------------------------
# record_spec_need
# ---------------------------------------------------------------------------


class TestRecordSpecNeed:
    def test_writes_jsonl(self, tmp_path: Path) -> None:
        root = tmp_path
        record_spec_need("add", "my-feature", "added a contract", root)
        ledger = root / ".claude" / "observability" / "spec-need-my-feature.jsonl"
        assert ledger.is_file()
        event = json.loads(ledger.read_text(encoding="utf-8").strip())
        assert event["verdict"] == "add"
        assert event["target"] == "my-feature"
        assert event["rationale"] == "added a contract"
        assert "detected_at" in event

    def test_writes_not_evaluated(self, tmp_path: Path) -> None:
        record_spec_need("not-evaluated", "tgt", "uncertain", tmp_path)
        ledger = tmp_path / ".claude" / "observability" / "spec-need-tgt.jsonl"
        event = json.loads(ledger.read_text(encoding="utf-8").strip())
        assert event["verdict"] == "not-evaluated"

    def test_appends_multiple(self, tmp_path: Path) -> None:
        record_spec_need("add", "t", "r1", tmp_path)
        record_spec_need("change", "t", "r2", tmp_path)
        ledger = tmp_path / ".claude" / "observability" / "spec-need-t.jsonl"
        lines = [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln]
        assert len(lines) == 2
        assert json.loads(lines[0])["verdict"] == "add"
        assert json.loads(lines[1])["verdict"] == "change"

    def test_custom_audit_path(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom.jsonl"
        record_spec_need("none", "tgt", "", tmp_path, audit_path=custom)
        assert custom.is_file()

    def test_no_raise_on_bad_root(self, tmp_path: Path) -> None:
        # Pass a file where a dir is expected — must not raise
        bad_root = tmp_path / "file.txt"
        bad_root.write_text("x")
        # atomic_append will try to mkdir on bad_root/.claude/observability, which
        # may or may not succeed depending on OS; the key contract is no raise.
        record_spec_need("add", "t", "r", bad_root)  # must not raise

    def test_changed_files_hash_recorded(self, tmp_path: Path) -> None:
        record_spec_need("change", "t", "r", tmp_path, changed_files_hash="abc123")
        ledger = tmp_path / ".claude" / "observability" / "spec-need-t.jsonl"
        event = json.loads(ledger.read_text(encoding="utf-8").strip())
        assert event["changed_files_hash"] == "abc123"


# ---------------------------------------------------------------------------
# operation_satisfied
# ---------------------------------------------------------------------------


class TestOperationSatisfied:
    def test_add_exists_with_acs_returns_true(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        _write_machine_yaml(
            specs / "SPEC-feat.machine.yaml",
            slug="feat",
            paths_to_mutate=[],
            acs=[_mechanical_ac()],
        )
        assert operation_satisfied("add", "feat", tmp_path, []) is True

    def test_add_absent_returns_false(self, tmp_path: Path) -> None:
        (tmp_path / "specs").mkdir()
        assert operation_satisfied("add", "feat", tmp_path, []) is False

    def test_add_malformed_yaml_returns_false(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        bad = specs / "SPEC-feat.machine.yaml"
        bad.write_text("broken: {[}", encoding="utf-8")
        assert operation_satisfied("add", "feat", tmp_path, []) is False

    def test_add_exists_but_no_acs_returns_false(self, tmp_path: Path) -> None:
        specs = tmp_path / "specs"
        specs.mkdir()
        _write_machine_yaml(
            specs / "SPEC-feat.machine.yaml",
            slug="feat",
            paths_to_mutate=[],
            acs=[],  # zero ACs
        )
        assert operation_satisfied("add", "feat", tmp_path, []) is False

    def test_change_target_in_diff_returns_true(self, tmp_path: Path) -> None:
        changed = ["specs/SPEC-feat.machine.yaml", "src/other.py"]
        assert operation_satisfied("change", "feat", tmp_path, changed) is True

    def test_change_target_not_in_diff_returns_false(self, tmp_path: Path) -> None:
        changed = ["src/other.py"]
        assert operation_satisfied("change", "feat", tmp_path, changed) is False

    def test_delete_target_in_diff_returns_true(self, tmp_path: Path) -> None:
        changed = ["specs/SPEC-feat.machine.yaml"]
        assert operation_satisfied("delete", "feat", tmp_path, changed) is True

    def test_delete_target_not_in_diff_returns_false(self, tmp_path: Path) -> None:
        assert operation_satisfied("delete", "feat", tmp_path, []) is False

    def test_none_always_false(self, tmp_path: Path) -> None:
        changed = ["specs/SPEC-feat.machine.yaml"]
        assert operation_satisfied("none", "feat", tmp_path, changed) is False

    def test_not_evaluated_always_false(self, tmp_path: Path) -> None:
        changed = ["specs/SPEC-feat.machine.yaml"]
        assert operation_satisfied("not-evaluated", "feat", tmp_path, changed) is False

    def test_empty_target_returns_false(self, tmp_path: Path) -> None:
        assert operation_satisfied("add", "", tmp_path, []) is False

    def test_never_raises(self, tmp_path: Path) -> None:
        # Passing an invalid verdict / nonexistent root
        result = operation_satisfied("add", "x", tmp_path / "noexist", [])
        assert result is False


# ---------------------------------------------------------------------------
# Waiver helpers
# ---------------------------------------------------------------------------


def _make_real_files(root: Path, filenames: list[str]) -> list[str]:
    """Create real files under root and return relative paths for hashing."""
    for name in filenames:
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"content of {name}\n", encoding="utf-8")
    return filenames


class TestWaiver:
    def test_write_and_valid_same_diff(self, tmp_path: Path) -> None:
        files = _make_real_files(tmp_path, ["src/a.py", "src/b.py"])
        write_waiver(tmp_path, "feat", "add", "feat", "we need this contract", files)
        assert waiver_valid(tmp_path, "feat", files) is True

    def test_stale_after_diff_change(self, tmp_path: Path) -> None:
        files_v1 = _make_real_files(tmp_path, ["src/a.py"])
        write_waiver(tmp_path, "feat", "add", "feat", "good reason", files_v1)
        assert waiver_valid(tmp_path, "feat", files_v1) is True

        # Now diff changes: new file added
        files_v2 = _make_real_files(tmp_path, ["src/a.py", "src/b.py"])
        # Hash changes → waiver expired
        assert waiver_valid(tmp_path, "feat", files_v2) is False

    def test_reasonless_write_raises(self, tmp_path: Path) -> None:
        files = _make_real_files(tmp_path, ["src/a.py"])
        with pytest.raises(ValueError, match="rationale"):
            write_waiver(tmp_path, "feat", "add", "feat", "", files)

    def test_whitespace_only_rationale_raises(self, tmp_path: Path) -> None:
        files = _make_real_files(tmp_path, ["src/a.py"])
        with pytest.raises(ValueError, match="rationale"):
            write_waiver(tmp_path, "feat", "add", "feat", "   ", files)

    def test_missing_receipt_returns_false(self, tmp_path: Path) -> None:
        assert waiver_valid(tmp_path, "no-such-slug", []) is False

    def test_empty_receipt_file_returns_false(self, tmp_path: Path) -> None:
        path = tmp_path / ".claude" / "observability" / "spec-need-waiver-feat.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        files = _make_real_files(tmp_path, ["src/a.py"])
        assert waiver_valid(tmp_path, "feat", files) is False

    def test_waiver_valid_latest_receipt_used(self, tmp_path: Path) -> None:
        """Latest receipt wins; stale latest invalidates even if an older receipt was fresh."""
        files_v1 = _make_real_files(tmp_path, ["src/a.py"])
        files_v2 = _make_real_files(tmp_path, ["src/a.py", "src/b.py"])

        # First write for v1 diff
        write_waiver(tmp_path, "feat", "add", "feat", "reason v1", files_v1)
        # Second write for v2 diff
        write_waiver(tmp_path, "feat", "add", "feat", "reason v2", files_v2)

        # Latest is v2 — checking against v2 should be True
        assert waiver_valid(tmp_path, "feat", files_v2) is True
        # Checking against v1 should be False (latest receipt has v2 hash)
        assert waiver_valid(tmp_path, "feat", files_v1) is False

    def test_empty_changed_files_raises_on_write(self, tmp_path: Path) -> None:
        """write_waiver raises ValueError when changed_files is empty (hash raises)."""
        with pytest.raises(ValueError, match="cannot compute waiver hash"):
            write_waiver(tmp_path, "feat", "add", "feat", "some reason", [])

    def test_malformed_receipt_returns_false(self, tmp_path: Path) -> None:
        path = tmp_path / ".claude" / "observability" / "spec-need-waiver-feat.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken json\n", encoding="utf-8")
        files = _make_real_files(tmp_path, ["src/a.py"])
        assert waiver_valid(tmp_path, "feat", files) is False


# ---------------------------------------------------------------------------
# Marker state machine
# ---------------------------------------------------------------------------


class TestMarker:
    def test_write_read_roundtrip(self, tmp_path: Path) -> None:
        write_marker(tmp_path, "my-slug", "add", "target", "abc123", "hash456")
        data = read_marker(tmp_path, "my-slug")
        assert data is not None
        assert data["slug"] == "my-slug"
        assert data["verdict"] == "add"
        assert data["target"] == "target"
        assert data["base_sha"] == "abc123"
        assert data["changed_files_hash"] == "hash456"
        assert "detected_at" in data

    def test_read_absent_returns_none(self, tmp_path: Path) -> None:
        assert read_marker(tmp_path, "nonexistent") is None

    def test_clear_after_write(self, tmp_path: Path) -> None:
        write_marker(tmp_path, "s", "change", "t", "sha", "h")
        assert read_marker(tmp_path, "s") is not None
        clear_marker(tmp_path, "s")
        assert read_marker(tmp_path, "s") is None

    def test_clear_idempotent(self, tmp_path: Path) -> None:
        clear_marker(tmp_path, "nonexistent")  # must not raise

    def test_marker_fresh_matching_hash(self, tmp_path: Path) -> None:
        write_marker(tmp_path, "s", "add", "t", "sha", "myhash")
        assert marker_fresh(tmp_path, "s", "myhash") is True

    def test_marker_fresh_mismatching_hash_stale(self, tmp_path: Path) -> None:
        write_marker(tmp_path, "s", "add", "t", "sha", "oldhash")
        # Different hash = diff moved = stale
        assert marker_fresh(tmp_path, "s", "newhash") is False

    def test_marker_fresh_absent_returns_false(self, tmp_path: Path) -> None:
        assert marker_fresh(tmp_path, "noexist", "anyhash") is False

    def test_one_shot_semantics(self, tmp_path: Path) -> None:
        """After clear, read → None (one-shot)."""
        write_marker(tmp_path, "s", "add", "t", "sha", "h")
        clear_marker(tmp_path, "s")
        assert read_marker(tmp_path, "s") is None
        # And fresh is also False after clear
        assert marker_fresh(tmp_path, "s", "h") is False

    def test_marker_path_is_inside_dot_claude(self, tmp_path: Path) -> None:
        p = marker_path(tmp_path, "demo")
        assert ".claude" in p.parts
        assert p.name == ".hm-spec-need-demo"

    def test_read_malformed_json_returns_none(self, tmp_path: Path) -> None:
        p = marker_path(tmp_path, "bad")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("not json", encoding="utf-8")
        assert read_marker(tmp_path, "bad") is None


# ---------------------------------------------------------------------------
# worktree: _is_harness_artifact recognizes the marker prefix
# ---------------------------------------------------------------------------


class TestWorktreeArtifactRecognition:
    def test_spec_need_marker_is_harness_artifact(self, tmp_path: Path) -> None:
        """A present .hm-spec-need-* marker must NOT trip the create-time dirty-base guard."""
        from harness_maker.worktree import _is_harness_artifact

        # Simulate git status --porcelain lines for the marker file
        line = "?? .claude/.hm-spec-need-demo"
        assert _is_harness_artifact(line) is True

    def test_spec_need_marker_various_slugs(self) -> None:
        from harness_maker.worktree import _is_harness_artifact

        for slug in ["my-feature", "spec-foo-123", "a"]:
            line = f" M .claude/.hm-spec-need-{slug}"
            assert _is_harness_artifact(line) is True, f"should be artifact for slug={slug}"

    def test_unrelated_claude_file_not_artifact(self) -> None:
        from harness_maker.worktree import _is_harness_artifact

        # A user's custom file should NOT be recognized as harness churn
        line = "?? .claude/agents/my-agent.md"
        assert _is_harness_artifact(line) is False

    def test_spec_need_gitignore_pattern_in_harness_gitignore_patterns(self) -> None:
        from harness_maker.worktree import _HARNESS_GITIGNORE_PATTERNS

        assert ".claude/.hm-spec-need-*" in _HARNESS_GITIGNORE_PATTERNS


# ---------------------------------------------------------------------------
# FIX 3 (Codex-2): path-traversal validation (_validate_slug + entry points)
# ---------------------------------------------------------------------------


class TestValidateSlug:
    def test_valid_slugs(self) -> None:
        for slug in ["abc", "my-feature", "spec-123", "a.b_c", "UPPER"]:
            _validate_slug(slug)  # must not raise

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _validate_slug("")

    def test_slash_raises(self) -> None:
        with pytest.raises(ValueError, match="path separator"):
            _validate_slug("../evil")

    def test_backslash_raises(self) -> None:
        with pytest.raises(ValueError, match="path separator"):
            _validate_slug("evil\\path")

    def test_dotdot_component_raises(self) -> None:
        with pytest.raises(ValueError, match=r"'\.\.'|must not contain"):
            _validate_slug("..")

    def test_special_chars_raises(self) -> None:
        for bad in ["feat ure", "feat;evil", "feat$(cmd)", "feat&more"]:
            with pytest.raises(ValueError, match="must match"):
                _validate_slug(bad)


class TestPathTraversalEntryPoints:
    """Each public entry-point that takes a slug/target must reject traversal slugs."""

    _BAD_SLUGS = ["../evil", "/etc/passwd", ".."]

    def test_marker_path_rejects_traversal(self, tmp_path: Path) -> None:
        for bad in self._BAD_SLUGS:
            with pytest.raises(ValueError, match=r"path separator|non-empty|must match|'\.\.'"):
                marker_path(tmp_path, bad)

    def test_write_marker_rejects_traversal_slug(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match=r"path separator|non-empty|must match|'\.\.'"):
            write_marker(tmp_path, "../evil", "add", "target", "sha", "hash")

    def test_write_marker_rejects_traversal_target(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match=r"path separator|non-empty|must match|'\.\.'"):
            write_marker(tmp_path, "ok-slug", "add", "../evil", "sha", "hash")

    def test_write_waiver_rejects_traversal_slug(self, tmp_path: Path) -> None:
        files = _make_real_files(tmp_path, ["src/a.py"])
        with pytest.raises(ValueError, match=r"path separator|non-empty|must match|'\.\.'"):
            write_waiver(tmp_path, "../evil", "add", "target", "reason", files)

    def test_write_waiver_rejects_traversal_target(self, tmp_path: Path) -> None:
        files = _make_real_files(tmp_path, ["src/a.py"])
        with pytest.raises(ValueError, match=r"path separator|non-empty|must match|'\.\.'"):
            write_waiver(tmp_path, "ok-slug", "add", "../evil", "reason", files)

    def test_waiver_valid_rejects_traversal_slug(self, tmp_path: Path) -> None:
        # waiver_valid is fail-closed on bad slug — returns False, does not raise
        result = waiver_valid(tmp_path, "../evil", ["src/a.py"])
        assert result is False

    def test_operation_satisfied_rejects_traversal_target(self, tmp_path: Path) -> None:
        # operation_satisfied is fail-closed — returns False on bad target
        result = operation_satisfied("add", "../evil", tmp_path, [])
        assert result is False

    def test_record_spec_need_rejects_traversal_target(self, tmp_path: Path) -> None:
        # record_spec_need has no-raise contract — must not raise and must not write outside obs dir
        record_spec_need("add", "../evil", "reason", tmp_path)
        # The bad path must NOT have created any file outside the observability dir
        assert not (tmp_path / "evil").exists()

    def test_cli_record_rejects_traversal_target(self, tmp_path: Path) -> None:
        from harness_maker.spec_need import main as spec_need_main

        rc = spec_need_main(
            ["record", "--verdict", "add", "--target", "../evil", "--root", str(tmp_path)]
        )
        assert rc == 1

    def test_cli_marker_write_rejects_traversal_slug(self, tmp_path: Path) -> None:
        from harness_maker.spec_need import main as spec_need_main

        rc = spec_need_main(
            [
                "marker-write",
                "--root",
                str(tmp_path),
                "--slug",
                "../evil",
                "--verdict",
                "add",
                "--target",
                "ok",
                "--base-sha",
                "sha",
                "--changed-files-hash",
                "hash",
            ]
        )
        assert rc == 1

    def test_cli_waiver_set_rejects_traversal_slug(self, tmp_path: Path) -> None:
        from harness_maker.spec_need import main as spec_need_main

        rc = spec_need_main(
            [
                "waiver-set",
                "--root",
                str(tmp_path),
                "--slug",
                "../evil",
                "--verdict",
                "add",
                "--target",
                "ok",
                "--rationale",
                "reason",
            ]
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# PLAN-spec-optional-task-driven ADR-001: task-driven-confident short-circuit
# on the verify-oracle CLI commands (op-check, waiver-check) ONLY.
# Fail-closed: relax IFF a confident dev_mode == "task-driven" read. Every other
# input (spec-driven / missing / unreadable / malformed / wrong-root) hits the
# unchanged enforce path. All marker/record commands stay pass-through so the
# ADR-009 anti-loop machinery is untouched.
# ---------------------------------------------------------------------------


def _write_dev_mode_yaml(
    root: Path, dev_mode_line: str | None, *, provenance: bool = False
) -> None:
    """Write <root>/.claude/harness.yaml with an optional dev_mode line."""
    claude = root / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    body = "locale: en\n"
    if dev_mode_line is not None:
        body += dev_mode_line + "\n"
    if provenance:
        body = "generated_by: harness-maker\ncontent_hash: abc123\n---\n" + body
    (claude / "harness.yaml").write_text(body, encoding="utf-8")


def _op_check_argv(root: Path) -> list[str]:
    # verdict=add + no specs/SPEC-foo.machine.yaml → operation NOT satisfied on the
    # unchanged path (exit 1). Only the task-driven short-circuit forces exit 0.
    return ["op-check", "--verdict", "add", "--target", "foo", "--root", str(root)]


def _waiver_check_argv(root: Path) -> list[str]:
    # no waiver file → not valid on the unchanged path (exit 1).
    return ["waiver-check", "--root", str(root), "--slug", "foo"]


def test_op_check_task_driven_short_circuits(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from harness_maker.spec_need import main as spec_need_main

    _write_dev_mode_yaml(tmp_path, "dev_mode: task-driven")
    rc = spec_need_main(_op_check_argv(tmp_path))
    assert rc == 0  # relaxed despite operation genuinely NOT satisfied
    assert json.loads(capsys.readouterr().out.strip()) == {"satisfied": True}


def test_op_check_task_driven_provenance_multidoc_short_circuits(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from harness_maker.spec_need import main as spec_need_main

    # Real harness.yaml is a multi-doc stream (provenance + body) — must still read.
    _write_dev_mode_yaml(tmp_path, "dev_mode: task-driven", provenance=True)
    rc = spec_need_main(_op_check_argv(tmp_path))
    assert rc == 0
    assert json.loads(capsys.readouterr().out.strip()) == {"satisfied": True}


def test_op_check_spec_driven_unchanged(tmp_path: Path) -> None:
    from harness_maker.spec_need import main as spec_need_main

    _write_dev_mode_yaml(tmp_path, "dev_mode: spec-driven")
    assert spec_need_main(_op_check_argv(tmp_path)) == 1  # enforce (not satisfied)


def test_op_check_missing_dev_mode_key_unchanged(tmp_path: Path) -> None:
    from harness_maker.spec_need import main as spec_need_main

    _write_dev_mode_yaml(tmp_path, None)  # no dev_mode key
    assert spec_need_main(_op_check_argv(tmp_path)) == 1  # fail-closed → enforce


def test_op_check_missing_harness_yaml_unchanged(tmp_path: Path) -> None:
    from harness_maker.spec_need import main as spec_need_main

    assert spec_need_main(_op_check_argv(tmp_path)) == 1  # no yaml → enforce


def test_op_check_malformed_yaml_unchanged(tmp_path: Path) -> None:
    from harness_maker.spec_need import main as spec_need_main

    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    (claude / "harness.yaml").write_text("dev_mode: [unclosed\n a: b: c\n", encoding="utf-8")
    assert spec_need_main(_op_check_argv(tmp_path)) == 1  # unreadable → enforce, no silent PASS


def test_op_check_wrong_root_unchanged(tmp_path: Path) -> None:
    from harness_maker.spec_need import main as spec_need_main

    missing = tmp_path / "does-not-exist"
    assert spec_need_main(_op_check_argv(missing)) == 1  # nonexistent root → enforce


def test_waiver_check_task_driven_short_circuits(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from harness_maker.spec_need import main as spec_need_main

    _write_dev_mode_yaml(tmp_path, "dev_mode: task-driven")
    rc = spec_need_main(_waiver_check_argv(tmp_path))
    assert rc == 0  # relaxed despite no waiver file present
    assert json.loads(capsys.readouterr().out.strip()) == {"valid": True}


def test_waiver_check_spec_driven_unchanged(tmp_path: Path) -> None:
    from harness_maker.spec_need import main as spec_need_main

    _write_dev_mode_yaml(tmp_path, "dev_mode: spec-driven")
    assert spec_need_main(_waiver_check_argv(tmp_path)) == 1  # enforce (no valid waiver)


def test_marker_write_read_unchanged_under_task_driven(tmp_path: Path) -> None:
    """Anti-loop preservation: marker commands are NOT short-circuited."""
    from harness_maker.spec_need import main as spec_need_main

    _write_dev_mode_yaml(tmp_path, "dev_mode: task-driven")
    rc = spec_need_main(
        [
            "marker-write",
            "--root",
            str(tmp_path),
            "--slug",
            "foo",
            "--verdict",
            "add",
            "--target",
            "foo",
            "--base-sha",
            "sha",
            "--changed-files-hash",
            "hash",
        ]
    )
    assert rc == 0
    # The marker was actually written (machinery intact), not no-op'd.
    assert read_marker(tmp_path, "foo") is not None


def test_record_unchanged_under_task_driven(tmp_path: Path) -> None:
    """Anti-loop preservation: record still writes the verdict ledger."""
    from harness_maker.spec_need import main as spec_need_main

    _write_dev_mode_yaml(tmp_path, "dev_mode: task-driven")
    rc = spec_need_main(
        [
            "record",
            "--verdict",
            "add",
            "--target",
            "foo",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    ledger = tmp_path / ".claude" / "observability" / "spec-need-foo.jsonl"
    assert ledger.is_file()  # side-effect happened; not neutralized
