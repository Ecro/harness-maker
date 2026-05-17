"""E2E — orphan-sweep deletes 0.12.x legacy command files on `make --update`.

Covers PLAN-health-consolidation ADR-005 across the three commands absorbed
into `/hm:health` (ai-readiness, refresh, personalization-audit) plus the R4
safety property (adaptive/overrides.jsonl is user telemetry; never swept) and
the theirs-fallback (user-edited file at a blueprint-orphaned path is KEPT
with a warning).

The fixture is built inline — no dependency on the committed sandbox trees,
no dependency on the now-deleted templates.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FAKE_VERSION = "0.12.0"


def _normalize_for_hash(body_text: str) -> str:
    """Match ``render.compute_body_hash`` normalization rules.

    Why: render.py records the manifest hash post-normalization. If the
    fixture writes raw bytes and the sweep recomputes via the production
    hasher, the two MUST agree — otherwise ours-clean detection misses.
    """
    text = body_text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    while text.endswith("\n\n"):
        text = text[:-1]
    return text


def _body_sha256(body_text: str) -> str:
    return hashlib.sha256(_normalize_for_hash(body_text).encode("utf-8")).hexdigest()


def _write_legacy_command(
    project: Path,
    name: str,
    *,
    body: str,
) -> tuple[Path, str]:
    """Write a legacy command file with our 0.12.x frontmatter shape.

    Returns ``(absolute_path, content_hash)``. The hash matches what
    ``render.py`` would have computed at the time — that's the value the
    sweep cross-checks against the manifest.
    """
    rel = Path(".claude") / "commands" / "hm" / f"{name}.md"
    abs_path = project / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    content_hash = _body_sha256(body)
    fm = "\n".join(
        [
            "---",
            "generated_by: harness-maker",
            f"harness_maker_version: {FAKE_VERSION}",
            f"source_template: commands/hm/{name}.md.j2",
            f"content_hash: {content_hash}",
            "generated_at: 2026-04-01T00:00:00+00:00",
            "---",
        ]
    )
    abs_path.write_text(fm + "\n" + body, encoding="utf-8")
    return abs_path, content_hash


def _write_manifest(
    project: Path,
    entries: Iterable[tuple[str, str]],
) -> Path:
    """Write a synthetic ``.hm-render-manifest.jsonl`` for the legacy files."""
    manifest_path = project / ".claude" / ".hm-render-manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for rel_path, content_hash in entries:
        rec = {
            "content_hash": content_hash,
            "path": rel_path,
            "timestamp": "2026-04-01T00:00:00+00:00",
        }
        lines.append(json.dumps(rec, sort_keys=True))
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def _seed_min_harness_yaml(project: Path) -> None:
    """Write a harness.yaml the CLI can replay via --update."""
    claude = project / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        [
            "---",
            "generated_by: harness-maker",
            f"harness_maker_version: {FAKE_VERSION}",
            "---",
            "locale: en",
            "preset: Side",
            "dev_mode: task-driven",
            "targets:",
            "  - claude-code",
            "recommended_model: claude-opus-4-7",
            "grade_threshold: B",
            "domains: []",
            "mechanical_checks: []",
            "fused_workflows:",
            "  exec-rev-wrap:",
            "    - execute",
            "    - review",
            "    - wrapup",
            "default_workflow: exec-rev-wrap",
            "reviewers:",
            "  enabled: [code]",
            "  caching: true",
            "  consensus: 1",
            "",
        ]
    )
    (claude / "harness.yaml").write_text(body, encoding="utf-8")


def _git_init(project: Path) -> None:
    subprocess.run(  # noqa: S603,S607
        ["git", "init", "-b", "main"],
        cwd=project,
        check=True,
        capture_output=True,
    )


def _inherited_env() -> dict[str, str]:
    return {
        k: os.environ[k]
        for k in ("PATH", "HOME", "USER", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")
        if k in os.environ
    }


def _run_make_update(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [
            "uv",
            "run",
            "python",
            "-m",
            "harness_maker.cli",
            "make",
            str(project),
            "--update",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env=_inherited_env(),
    )


def test_orphan_sweep_deletes_three_legacy_commands_preserves_user_assets(
    tmp_path: Path,
) -> None:
    """End-to-end: all three legacy commands swept, health present,
    adaptive/overrides.jsonl preserved, user-edited file KEPT + warned."""
    project = tmp_path / "proj-sweep"
    project.mkdir()
    _git_init(project)
    _seed_min_harness_yaml(project)

    # ── 1. Legacy "ours-clean" command files at 0.12.0-equivalent state.
    body_air = "# /hm:ai-readiness\n\nLegacy AI-readiness command body.\n"
    body_refresh = "# /hm:refresh\n\nLegacy refresh command body.\n"
    body_audit = "# /hm:personalization-audit\n\nLegacy personalization-audit body.\n"
    _, hash_air = _write_legacy_command(project, "ai-readiness", body=body_air)
    _, hash_refresh = _write_legacy_command(project, "refresh", body=body_refresh)
    _, hash_audit = _write_legacy_command(project, "personalization-audit", body=body_audit)

    # ── 2. R4: adaptive/overrides.jsonl (user telemetry; no frontmatter; not
    # in manifest). Must survive the sweep.
    adaptive_dir = project / ".claude" / "observability" / "adaptive"
    adaptive_dir.mkdir(parents=True, exist_ok=True)
    overrides_path = adaptive_dir / "overrides.jsonl"
    overrides_payload = json.dumps({"key": "preset", "old": "Side", "new": "Production"}) + "\n"
    overrides_path.write_text(overrides_payload, encoding="utf-8")

    # ── 3. "theirs" fixture — a legacy command whose body has been edited
    # by the user (content_hash on disk no longer matches manifest entry).
    # Sweep must KEEP and warn.
    user_edited_path, declared_hash = _write_legacy_command(
        project,
        "personalization-audit-userblob",
        body="Original body (declared hash will mismatch on next read).\n",
    )
    # Mutate the body without re-stamping the frontmatter — simulates a user
    # edit: declared content_hash stays the same, recomputed hash differs.
    text = user_edited_path.read_text(encoding="utf-8")
    fm_end = text.find("\n---\n", 4)
    assert fm_end > 0
    new_body = (
        text[: fm_end + len("\n---\n")]
        + "Original body (declared hash will mismatch on next read).\n"
        + "USER EDIT — this line breaks the recomputed hash.\n"
    )
    user_edited_path.write_text(new_body, encoding="utf-8")

    # ── 4. Manifest entries for all FOUR legacy paths so ours-classifier
    # can find them; only the three unmodified ones should hit ours-clean.
    _write_manifest(
        project,
        [
            (".claude/commands/hm/ai-readiness.md", hash_air),
            (".claude/commands/hm/refresh.md", hash_refresh),
            (".claude/commands/hm/personalization-audit.md", hash_audit),
            (".claude/commands/hm/personalization-audit-userblob.md", declared_hash),
        ],
    )

    # ── 5. Apply the current blueprint via `make --update`. The current
    # blueprint contains health.md and not the three legacy templates.
    cp = _run_make_update(project)
    # rc==0 means full path (render + verify) clean; rc==1 only signals a
    # downstream verify mismatch (unrelated to the sweep we're asserting).
    # The KEEP/DELETE state on disk is independent of CLI exit code — same
    # contract as test_dogfood_sandbox::test_reconcile_preserves_user_edits.
    assert cp.returncode in (0, 1), (
        f"make --update crashed: rc={cp.returncode}\nstdout={cp.stdout}\nstderr={cp.stderr}"
    )

    # ── 6. Assertions on disk.
    commands = project / ".claude" / "commands" / "hm"
    assert not (commands / "ai-readiness.md").exists(), (
        "ai-readiness.md should have been ours-clean-swept"
    )
    assert not (commands / "refresh.md").exists(), "refresh.md should have been ours-clean-swept"
    assert not (commands / "personalization-audit.md").exists(), (
        "personalization-audit.md should have been ours-clean-swept"
    )
    assert (commands / "health.md").is_file(), "blueprint-present health.md should be rendered"
    # R4 — adaptive/overrides.jsonl untouched.
    assert overrides_path.is_file(), "adaptive/overrides.jsonl must survive sweep"
    assert overrides_path.read_text(encoding="utf-8") == overrides_payload, (
        "adaptive/overrides.jsonl bytes mutated"
    )
    # theirs-fallback — user-edited legacy file KEPT.
    assert user_edited_path.is_file(), "user-modified legacy file must NOT be swept"
    # Stdout/stderr surfaces a warning for the kept file.
    combined = cp.stdout + cp.stderr
    assert "personalization-audit-userblob.md" in combined, (
        f"sweep should warn about kept-user-file; output:\n{combined}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
