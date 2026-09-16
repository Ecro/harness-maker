"""AC-006 — `hm world objective new <ID>` writes a loadable INTENT skeleton (ADR-004).

The verb is exercised through the shipped CLI entrypoint (seam rule) and judged against the
loader's acceptance plus the Playbook's five section names, never against the verb's own output.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker import world
from tests.unit import world_fixture as fx

_PLAYBOOK_HEADINGS = (
    "## Problem",
    "## Proposed outcome",
    "## Affected users and systems",
    "## Constraints",
    "## Open questions",
)


def _new(root: Path, oid: str, *extra: str) -> tuple[int, str, str]:
    proc = fx.run_cli(
        [
            "--root",
            str(root),
            "objective",
            "new",
            oid,
            "--title",
            "One-round onboarding",
            "--hypothesis",
            "shorter onboarding keeps users",
            "--scope",
            "cut the interview to one round",
            "--scope",
            "keep the locale question",
            "--outcome",
            "onboarding_minutes",
            *extra,
        ],
        cwd=root,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_ac_006_objective_new_writes_a_loadable_skeleton(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    rc, out, err = _new(root, "OBJ-9", "--non-scope", "rewrite the renderer", "--json")
    assert rc == 0, err
    path = root / "work-docs" / "INTENT-OBJ-9.md"
    assert path.exists()
    w = world.load_world(root)
    assert "OBJ-9" not in w.broken
    rec = w.objectives["OBJ-9"]
    assert rec["state"] == "proposed"
    assert rec["approval"] is None
    assert rec["schema_version"] == 1
    assert rec["scope"] == ["cut the interview to one round", "keep the locale question"]
    assert rec["non_scope"] == ["rewrite the renderer"]
    assert rec["outcome_id"] == "onboarding_minutes"
    assert rec["created_at"].endswith("Z")
    body = w.bodies["OBJ-9"].decode("utf-8")
    assert all(h in body for h in _PLAYBOOK_HEADINGS)
    assert (
        fx.stdout_json(
            fx.run_cli(["--root", str(root), "objective", "show", "OBJ-9", "--json"], cwd=root)
        )["id"]
        == "OBJ-9"
    )
    assert "INTENT-OBJ-9.md" in out


def test_ac_006_a_second_new_is_refused_and_the_file_is_untouched(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    assert _new(root, "OBJ-9")[0] == 0
    path = root / "work-docs" / "INTENT-OBJ-9.md"
    path.write_bytes(path.read_bytes() + b"\nhand-written prose\n")
    before = path.read_bytes()
    rc, out, err = _new(root, "OBJ-9")
    assert rc != 0
    assert "OBJ-9" in out + err  # `main()` emits WorldError via _emit (stdout), rc 1
    assert path.read_bytes() == before


def test_ac_006_a_bad_id_is_refused_naming_the_rule_before_any_write(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    rc, out, err = _new(root, "obj-9")
    assert rc != 0
    assert "[A-Z0-9-]+" in out + err
    assert (
        not list((root / "work-docs").glob("INTENT-*")) if (root / "work-docs").exists() else True
    )


def test_ac_006_an_unknown_outcome_is_refused(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    proc = fx.run_cli(
        [
            "--root",
            str(root),
            "objective",
            "new",
            "OBJ-9",
            "--title",
            "t",
            "--hypothesis",
            "h",
            "--scope",
            "s",
            "--outcome",
            "ghost",
        ],
        cwd=root,
    )
    assert proc.returncode != 0
    assert "ghost" in proc.stdout + proc.stderr
    assert not (root / "work-docs" / "INTENT-OBJ-9.md").exists()


def test_ac_006_the_python_api_matches_the_cli(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    rec = world.new_objective(
        root,
        "OBJ-8",
        title="t",
        hypothesis="h",
        scope=["s"],
        outcome_id="onboarding_minutes",
    )
    assert rec["id"] == "OBJ-8"
    assert world.load_world(root).objectives["OBJ-8"] == rec
