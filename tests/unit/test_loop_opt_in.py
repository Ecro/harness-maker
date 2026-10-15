"""SPEC-loop-opt-in: `loop.enabled` gates the /hm:loop family (AC-001..AC-011).

Production symbols (`LoopConfig`, the `loop` answers/config field) are resolved at call
time rather than imported at module level, so each test goes RED for its own reason
instead of the whole module failing collection.
"""

from __future__ import annotations

import json
import os
import posixpath
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner

from harness_maker import models
from harness_maker.cli import app
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REPO = Path(__file__).resolve().parents[2]
_BASE_COMMIT = "055cce85"
# The commit that made loop opt-in and regenerated the (loop-off) snapshots. A path whose
# off-render changed after it was changed by later, unrelated work, so the pre-change pin at
# _BASE_COMMIT no longer describes it; such a path is judged against the current snapshot instead.
_OPT_IN_COMMIT = "18714dd1"

# Loop-sensitive paths a LATER task moved, re-captured deliberately (append; never silently
# overwrite). Value: the loop-ON body hash per snapshot fixture.
# - 2026-10-02, `world-model-name`: CLAUDE.md gained the `## World model` pointer. Verified
#   before capture that the loop-ON vs loop-OFF render of CLAUDE.md differs ONLY in the opt-in
#   loop sentence, i.e. the new pointer is loop-independent.
# - 2026-10-02, `world-model-followups`: the `## World model` pointer text was shortened
#   (max-length budget). Re-verified the loop-ON/OFF CLAUDE.md diff is still only the loop
#   sentence before re-capturing.
#   `help.md` re-captured too: it gained the router row; its loop-ON/OFF diff is still only the
#   `/hm:loop` table row and the chaining sentence.
# - 2026-10-03, `maker-front-door-improvements`: CLAUDE.md's `## World model` and
#   `## Project knowledge` pointers were rewritten (routing, decision capture, mid-stage aside)
#   and help.md's intent-layer / project-knowledge rows became `typed only`. Re-verified the
#   loop-ON/OFF diff of both files is still only the loop sentence / `/hm:loop` row.
# - 2026-10-14, `hm-light-lane-s2`: the six stage commands and their `stages/*.md` copies became
#   loop-sensitive (Gate 0, execute Step 0.2/Step 5, verify Check 5 render only with the loop on)
#   and moved for the stage's other cuts. Verified before capture that these twelve are the ONLY
#   paths whose loop-ON body differs from the regenerated loop-OFF snapshot in every fixture; the
#   loop-ON/OFF diff of each is pinned by tests/render/test_render_light_lane_s2.py (AC-002).
#   Re-captured again in the same task after `/hm:review` round 1 edited those twelve bodies.
# - 2026-10-14, `hm-light-lane-s2b`: the execute A.5, review auto-fix / confirmation and (when
#   delegated) wrapup / verify bodies moved to `.claude/hm/*.md`. Four of the twelve above
#   (`commands/hm` + `stages` copies of execute and review) were re-captured because their text
#   shrank to pointers; wrapup / verify keep their bytes at the default `delegation.stages: []`.
#   Two reference files are new and loop-sensitive (verify Check 5, review Step 0 confirmation
#   loop branches): `hm/verify-checks.md`, `hm/review-confirmation.md`; `commands/hm/loop.md`
#   moved too (Step 4 exemption for the reference files). Verified before capture
#   that no other loop-ON path moved; the loop-ON/OFF diff is pinned by
#   tests/render/test_render_light_lane_s2.py (AC-002, inventory spans command + refs).
#   Re-captured again in the same task after `/hm:review` round 1: the review pointers' stop clause
#   and the `confirm-1` wording changed `commands/hm/review.md`, `stages/review.md` and
#   `hm/review-confirmation.md`; the A.5 pointer condition and the verify preface changed
#   `commands/hm/execute.md`, `stages/execute.md` and `hm/verify-checks.md`; `loop` Step 3 gained
#   the reference-file exemption. wrapup / verify commands are unchanged at the default
#   `delegation.stages: []`, which is what these fixtures render.
# - 2026-10-14, `hm-autopilot-spec-advance`: spec Step 5's unapproved-SPEC sentence was reworded
#   (a missing approval does not end the stage; `auto_full` advances without one), moving
#   `commands/hm/spec.md` and `stages/spec.md`. Verified before capture that no other loop-ON
#   path moved. Re-captured again after the light review reworded the `auto_full` clause.
# - 2026-10-15, `hm-light-lane-s3a`: execute gained Step 4.2 (the light check; the Claude
#   command points at the new loop-insensitive `hm/execute-light-check.md`) and spec Step 5 stamps
#   a light SPEC with an empty irreversible list `exempt`, moving `commands/hm/execute.md`,
#   `stages/execute.md`, `commands/hm/spec.md` and `stages/spec.md`. Verified before capture
#   that no other loop-ON path moved; review / verify / wrapup / loop render byte-identical
#   (SPEC-hm-light-lane-s3a AC-011). Re-captured again the same day after the review of 3a
#   (items E, G, P): Step 5's exempt branch names its three conditions, the Step 4.2 stub names
#   loop mode and a missing reference file skips the check, and the stage-end banner names
#   wrapup after a passing light check. The same four paths; no other loop-ON path moved.
# - 2026-10-15, `hm-light-lane-s3c`: the six Claude stage commands point at the new
#   `hm/stage-preamble.md` for their preamble, spec Step 3.5/4 and execute Step 0/0.3 changed
#   (the minimal schema, the quiet check, the light PLAN; `hm/spec-machine-full.md` and
#   `hm/execute-plan.md` are new), moving `commands/hm/{research,spec,execute,review,verify,
#   wrapup}.md`, `stages/execute.md` and `stages/spec.md`. Verified before capture that no other
#   loop-ON path moved and that the three new reference files render the same with the loop on
#   and off (they take today's loop-OFF snapshot rows).
_LOOP_ON_RECAPTURES: dict[str, dict[str, str]] = {
    "commands/hm/execute.md": {
        "side-python-cli": "c5a186c8e2eba740ee615e5fde81ddf9de59673fb6454ccdff3afd43d4a8b21a",
        "side-tauri-app": "c5a186c8e2eba740ee615e5fde81ddf9de59673fb6454ccdff3afd43d4a8b21a",
        "prod-tauri-app": "b838588aaebcf0d001061453da98a32746bea5f2af649d151664f4f7225c8717",
        "prod-firmware": "b838588aaebcf0d001061453da98a32746bea5f2af649d151664f4f7225c8717",
    },
    "commands/hm/research.md": {
        "side-python-cli": "48f8e7daada31de0366f0c5117616f71f941546da272cef9d8e57a0170f28c52",
        "side-tauri-app": "48f8e7daada31de0366f0c5117616f71f941546da272cef9d8e57a0170f28c52",
        "prod-tauri-app": "d33f32151937e249cad3753156d05a660e798e7bd090875edf2210032c1342fb",
        "prod-firmware": "d33f32151937e249cad3753156d05a660e798e7bd090875edf2210032c1342fb",
    },
    "commands/hm/review.md": {
        "side-python-cli": "a2a9ecfbcab39eb3a854cb5f0fec8701a644ce93f120909bd14e88c285a9d646",
        "side-tauri-app": "a2a9ecfbcab39eb3a854cb5f0fec8701a644ce93f120909bd14e88c285a9d646",
        "prod-tauri-app": "e6f7e68f52f668e956d831b9e78fc91930e4322425ec2e9219e10a18bc358766",
        "prod-firmware": "e6f7e68f52f668e956d831b9e78fc91930e4322425ec2e9219e10a18bc358766",
    },
    "commands/hm/spec.md": {
        "side-python-cli": "e283d8e77724c2f1c11dde786c57f1fccdd10fc472ce962c121e18e64b2a84e1",
        "side-tauri-app": "e283d8e77724c2f1c11dde786c57f1fccdd10fc472ce962c121e18e64b2a84e1",
        "prod-tauri-app": "06cb25e785ef4e3c553f252db0c1a6cdd9a311e4bd7893523e2fe775a1c228b3",
        "prod-firmware": "06cb25e785ef4e3c553f252db0c1a6cdd9a311e4bd7893523e2fe775a1c228b3",
    },
    "commands/hm/verify.md": {
        "side-python-cli": "bd656c76809e4cd705dd263ee6842476084c5ab65282feceb15cad6fe7d5de58",
        "side-tauri-app": "bd656c76809e4cd705dd263ee6842476084c5ab65282feceb15cad6fe7d5de58",
        "prod-tauri-app": "5512494ca0eab8b9bb637fa0343ccc7ffa5051a62cd793e37fc3afff687d1181",
        "prod-firmware": "5512494ca0eab8b9bb637fa0343ccc7ffa5051a62cd793e37fc3afff687d1181",
    },
    "commands/hm/wrapup.md": {
        "side-python-cli": "e97dc9f40b8448c1e45c967d8a9954c1cad2ac62713f80c5829a21dbc22861c6",
        "side-tauri-app": "e97dc9f40b8448c1e45c967d8a9954c1cad2ac62713f80c5829a21dbc22861c6",
        "prod-tauri-app": "6626d689dee3798653130c9371b8648dc2ee3bb36a87d3c64057508d4aa3d84b",
        "prod-firmware": "6626d689dee3798653130c9371b8648dc2ee3bb36a87d3c64057508d4aa3d84b",
    },
    "stages/execute.md": {
        "side-python-cli": "14673d1f4b92f465de43f52804888befb96b31a3a1fe7044be5f0fb813a812c3",
        "side-tauri-app": "14673d1f4b92f465de43f52804888befb96b31a3a1fe7044be5f0fb813a812c3",
        "prod-tauri-app": "a63d32ebb146709ed7df395aca50d2936e2a64df6c8498ba48a1cd5aa26af41d",
        "prod-firmware": "a63d32ebb146709ed7df395aca50d2936e2a64df6c8498ba48a1cd5aa26af41d",
    },
    "stages/research.md": {
        "side-python-cli": "dd5801166e5918f5572251551018d07e13cb3a241d54772435764ae4bfa5d9ea",
        "side-tauri-app": "dd5801166e5918f5572251551018d07e13cb3a241d54772435764ae4bfa5d9ea",
        "prod-tauri-app": "72751dd68a5456f9c1b090f70c0045ca5b7102aba55dc065b863647f40591079",
        "prod-firmware": "72751dd68a5456f9c1b090f70c0045ca5b7102aba55dc065b863647f40591079",
    },
    "stages/review.md": {
        "side-python-cli": "b382e06fc6283cb5537a87855ba99baca4921becd409dfe37b9c384a1e1f0c4e",
        "side-tauri-app": "b382e06fc6283cb5537a87855ba99baca4921becd409dfe37b9c384a1e1f0c4e",
        "prod-tauri-app": "8a4c224829f18b6bf87c90a04108960e31ccc80b574201b7fef6bd74ee30828a",
        "prod-firmware": "8a4c224829f18b6bf87c90a04108960e31ccc80b574201b7fef6bd74ee30828a",
    },
    "stages/spec.md": {
        "side-python-cli": "19ced3b003da86b7da68e22b88c5446f235402237067f629501c8f1ec9e4d517",
        "side-tauri-app": "19ced3b003da86b7da68e22b88c5446f235402237067f629501c8f1ec9e4d517",
        "prod-tauri-app": "ca310437ad7a6878498986be7435c46230c2a450bad8f6288fd19d68d019a915",
        "prod-firmware": "ca310437ad7a6878498986be7435c46230c2a450bad8f6288fd19d68d019a915",
    },
    "stages/verify.md": {
        "side-python-cli": "60eb704f3ba7dcc593a2e0fdaffc6a3a16f62055672ca0de95fbd50bd5dd2c8a",
        "side-tauri-app": "60eb704f3ba7dcc593a2e0fdaffc6a3a16f62055672ca0de95fbd50bd5dd2c8a",
        "prod-tauri-app": "477543a2887a831d74dad0cfb82a28c47774651a6089bc6bac0ccb47502fe94a",
        "prod-firmware": "477543a2887a831d74dad0cfb82a28c47774651a6089bc6bac0ccb47502fe94a",
    },
    "stages/wrapup.md": {
        "side-python-cli": "d6ce375a80094c58627fcc59947dc9dade1e0e143f7c0d7112f37a7ce2f0b67c",
        "side-tauri-app": "d6ce375a80094c58627fcc59947dc9dade1e0e143f7c0d7112f37a7ce2f0b67c",
        "prod-tauri-app": "de359ec594c405ea1f7c6b4d63db8f703afc04b8c9cb53402141ab54a6313a24",
        "prod-firmware": "de359ec594c405ea1f7c6b4d63db8f703afc04b8c9cb53402141ab54a6313a24",
    },
    "commands/hm/help.md": {
        "side-python-cli": "1ec7c692208c633334d0443ab360d24ab6c5915a65de26a8233965bfe86c49c9",
        "side-tauri-app": "1ec7c692208c633334d0443ab360d24ab6c5915a65de26a8233965bfe86c49c9",
        "prod-tauri-app": "51b7ab6de6b2c52998cce575bc2d665ec81b4a602fb019cb74bf3b5bd5017664",
        "prod-firmware": "51b7ab6de6b2c52998cce575bc2d665ec81b4a602fb019cb74bf3b5bd5017664",
    },
    "../CLAUDE.md": {
        "side-python-cli": "8050ae7b0f3821d6bfa9a5961038194e7cbc8c52da6928e629a34f31cabccaa2",
        "side-tauri-app": "8050ae7b0f3821d6bfa9a5961038194e7cbc8c52da6928e629a34f31cabccaa2",
        "prod-tauri-app": "2255501bd4e2586c9ea9594157b8b443231fbbb4d411f1258e3c379064c75fdb",
        "prod-firmware": "2255501bd4e2586c9ea9594157b8b443231fbbb4d411f1258e3c379064c75fdb",
    },
    "hm/verify-checks.md": {
        "side-python-cli": "fc5d929270bbd4bbe8388cac4c68b4f4b7b807c98ab78e555c7f9db0df924d7b",
        "side-tauri-app": "fc5d929270bbd4bbe8388cac4c68b4f4b7b807c98ab78e555c7f9db0df924d7b",
        "prod-tauri-app": "2311f8f3e0743b17f0e006c1ebdcc81872a392215c31b185e2fabcdafb88a8d6",
        "prod-firmware": "2311f8f3e0743b17f0e006c1ebdcc81872a392215c31b185e2fabcdafb88a8d6",
    },
    "hm/review-confirmation.md": {
        "side-python-cli": "2b7a85e60afea4f53dec59dc56c87debd5d890740a3aaa8431886ef6a05355bf",
        "side-tauri-app": "2b7a85e60afea4f53dec59dc56c87debd5d890740a3aaa8431886ef6a05355bf",
        "prod-tauri-app": "fd4bf0e83eff999ef22877b5a5b980e2676402cfa6bfc4aef39cd8e47223cce7",
        "prod-firmware": "fd4bf0e83eff999ef22877b5a5b980e2676402cfa6bfc4aef39cd8e47223cce7",
    },
    "commands/hm/loop.md": {
        "side-python-cli": "9b406bb1361a01a39c39018810b087f6eac9b6dc69512deb9c382cd168ed46ab",
        "side-tauri-app": "9b406bb1361a01a39c39018810b087f6eac9b6dc69512deb9c382cd168ed46ab",
        "prod-tauri-app": "844f3bb89e1d3f540eed941ee12f12df1b1bfd10e4e7321a58df97a5ec7d2612",
        "prod-firmware": "844f3bb89e1d3f540eed941ee12f12df1b1bfd10e4e7321a58df97a5ec7d2612",
    },
}
# Loop-sensitive but never hash-compared below (`strip`), so a later key addition may move it.
_LOOP_SENSITIVE_HASH_EXEMPT = {"harness.yaml"}

LOOP_CLAUDE = {".claude/commands/hm/loop.md", ".claude/commands/hm/loop-p5-batch.md"}
LOOP_CODEX = {".agents/skills/hm-loop/SKILL.md", ".agents/skills/hm-loop-p5-batch/SKILL.md"}
LISTING_SURFACES = (
    ".claude/commands/hm/help.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".cursor/rules/harness.mdc",
    # The Codex rendering of help.md (review finding cd14c78815a4027d surfaced it once
    # AC-009 compared real rendered bodies).
    ".agents/skills/hm-help/SKILL.md",
)
# SPEC-hm-light-lane-s2 AC-012 widens this by exactly the stage bodies that carry loop-only
# branches: the six stage commands, their `.claude/stages/*.md` copies and the six Codex stage
# skills. Nothing else may move with the flag.
_LIGHT_LANE_S2_STAGES = ("execute", "research", "review", "spec", "verify", "wrapup")
LOOP_GATED_STAGE_BODIES = (
    *(f".claude/commands/hm/{s}.md" for s in _LIGHT_LANE_S2_STAGES),
    *(f".claude/stages/{s}.md" for s in _LIGHT_LANE_S2_STAGES),
    *(f".agents/skills/hm-{s}/SKILL.md" for s in _LIGHT_LANE_S2_STAGES),
)
PREVIOUS_ALLOWED = {".claude/harness.yaml", *LISTING_SURFACES, *LOOP_GATED_STAGE_BODIES}
# SPEC-hm-light-lane-s2b widens it by exactly the two reference files that carry loop-only text.
_S2B_LOOP_REFS = {".claude/hm/verify-checks.md", ".claude/hm/review-confirmation.md"}
ALLOWED_BODY_DIFFS = PREVIOUS_ALLOWED | _S2B_LOOP_REFS
ALL_TARGETS = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


def _norm(fe_path: Path) -> str:
    """Project-root-relative key, the same mapping reconcile._normalize_expected_path uses."""
    s = str(fe_path).replace("\\", "/")
    if s.startswith((".cursor/", ".codex/", ".agents/")) or s == "AGENTS.md":
        return s
    return posixpath.normpath(".claude/" + s)


def _answers(
    *,
    loop_enabled: bool,
    targets: list[Target] | None = None,
    preset: Preset | None = None,
    locale: str = "en",
) -> InterviewAnswers:
    a = interview(_profile(), autoloop_mode=True)
    update: dict[str, Any] = {
        "loop": models.LoopConfig(enabled=loop_enabled),
        "locale": locale,
    }
    if targets is not None:
        update["targets"] = targets
    if preset is not None:
        update["preset"] = preset
    return a.model_copy(update=update)


def _blueprint(**kw: Any) -> models.Blueprint:
    return synthesize(_profile(), _answers(**kw))


def normalized_paths(*, loop_enabled: bool, targets: list[str] | None = None) -> set[str]:
    tgt = [Target.CLAUDE_CODE] + [Target(t) for t in (targets or [])]
    return {_norm(f.path) for f in _blueprint(loop_enabled=loop_enabled, targets=tgt).files}


def _render_tree(root: Path, answers: InterviewAnswers) -> models.Blueprint:
    bp = synthesize(_profile(), answers)
    render(bp, root / ".claude", dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    return bp


def _rendered_body_hashes(root: Path, **kw: Any) -> dict[str, str]:
    """Post-render body hashes. `synthesize()` leaves `body_sha256` None until `render()`."""
    bp = _render_tree(root, _answers(**kw))
    hashes = {_norm(f.path): f.body_sha256 for f in bp.files}
    assert all(h for h in hashes.values()), "render() did not stamp every body hash"
    return {p: str(h) for p, h in hashes.items()}


def _read_yaml(root: Path) -> dict[str, Any]:
    """The user-data body; the rendered file carries a provenance document first."""
    return load_harness_yaml(root / ".claude" / "harness.yaml")


def _git_show(rev: str, rel: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(_REPO), "show", f"{rev}:{rel}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"base commit {rev} not reachable in this checkout: {proc.stderr.strip()}")
    return proc.stdout


def _legacy_yaml_variants() -> dict[str, dict[str, Any]]:
    """Pre-feature harness.yaml (this repo's own, at the base commit) in four shapes."""
    docs = list(yaml.safe_load_all(_git_show(_BASE_COMMIT, ".claude/harness.yaml")))
    base = [d for d in docs if isinstance(d, dict) and d.get("generated_by") != "harness-maker"][-1]
    assert "loop" not in base
    no_version = {k: v for k, v in base.items() if k != "schema_version"}
    v5 = {**base, "schema_version": 5}
    v6_no_key = {**base, "schema_version": 6}
    empty_block = {**base, "loop": {}}
    return {
        "no_version": no_version,
        "v5": v5,
        "v6_no_key": v6_no_key,
        "empty_loop_block": empty_block,
    }


@contextmanager
def _chdir(path: Path) -> Iterator[None]:
    before = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(before)


def _cli(repo: Path, *args: str) -> Any:
    with _chdir(repo):
        return CliRunner().invoke(app, ["make", str(repo), "--autoloop", *args])


def _bootstrap(tmp_path: Path, *extra: str) -> Path:
    repo = tmp_path / "proj"
    repo.mkdir(parents=True)
    res = _cli(repo, *extra)
    assert res.exit_code == 0, res.output
    return repo


def _write_yaml(repo: Path, data: dict[str, Any]) -> None:
    (repo / ".claude" / "harness.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def _tree(repo: Path) -> dict[str, bytes]:
    return {
        p.relative_to(repo).as_posix(): p.read_bytes()
        for p in sorted(repo.rglob("*"))
        if p.is_file()
    }


# ---------------------------------------------------------------------------
# AC-001 / AC-002
# ---------------------------------------------------------------------------


def test_ac001_disabled_renders_no_claude_loop_commands() -> None:
    assert not (LOOP_CLAUDE & normalized_paths(loop_enabled=False))
    assert normalized_paths(loop_enabled=True) >= LOOP_CLAUDE


def test_ac002_disabled_renders_no_codex_loop_skills() -> None:
    assert not (LOOP_CODEX & normalized_paths(loop_enabled=False, targets=["codex"]))
    assert normalized_paths(loop_enabled=True, targets=["codex"]) >= LOOP_CODEX


# ---------------------------------------------------------------------------
# AC-003 — enabled render == pre-change snapshot (reference read from git)
# ---------------------------------------------------------------------------

_SNAPSHOT_FIXTURES = ("side-python-cli", "side-tauri-app", "prod-tauri-app", "prod-firmware")


@pytest.fixture
def _isolate_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = tmp_path_factory.mktemp("hm-home")
    monkeypatch.setattr(Path, "home", lambda: fake_home)


@pytest.mark.usefixtures("_isolate_home")
@pytest.mark.parametrize("fixture", _SNAPSHOT_FIXTURES)
def test_ac003_enabled_matches_pre_change_snapshots(fixture: str, tmp_path: Path) -> None:
    sys.path.insert(0, str(_REPO / "tests" / "snapshot"))
    from regenerate import is_excluded, load_exclusions

    snapshot = f"tests/snapshot/{fixture}.expected.yaml"
    reference = yaml.safe_load(_git_show(_BASE_COMMIT, snapshot))
    base = {r["path"]: r["body_sha256"] for r in reference["files"]}
    at_opt_in = {
        r["path"]: r["body_sha256"]
        for r in yaml.safe_load(_git_show(_OPT_IN_COMMIT, snapshot))["files"]
    }
    now_rows = {
        r["path"]: r
        for r in yaml.safe_load((_REPO / snapshot).read_text(encoding="utf-8"))["files"]
    }
    now = {path: r["body_sha256"] for path, r in now_rows.items()}
    moved = {path for path in at_opt_in.keys() | now.keys() if at_opt_in.get(path) != now.get(path)}
    # Paths whose render depends on loop.enabled are the ones the opt-in commit itself changed.
    loop_sensitive = {
        path for path in base.keys() | at_opt_in.keys() if base.get(path) != at_opt_in.get(path)
    }
    # A moved loop-insensitive path renders the same with the loop on or off, so its loop-ON
    # expectation is today's loop-OFF snapshot. A moved loop-SENSITIVE path has no committed
    # loop-ON expectation at all: fail here so it is handled deliberately, never dropped silently.
    unhandled = (moved & loop_sensitive) - _LOOP_ON_RECAPTURES.keys() - _LOOP_SENSITIVE_HASH_EXEMPT
    assert not unhandled, sorted(unhandled)
    p = profile(_REPO / "tests" / "fixtures" / fixture)
    a = interview(p, autoloop_mode=True).model_copy(
        update={"loop": models.LoopConfig(enabled=True)}
    )
    bp = synthesize(p, a)
    render(bp, tmp_path, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    exclusions = load_exclusions()
    actual = sorted(
        (
            {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
            for f in bp.files
            if not is_excluded(str(f.path), exclusions)
        ),
        key=lambda x: x["path"] or "",
    )
    expected = sorted(
        (
            now_rows[r["path"]] if r["path"] in moved else r
            for r in reference["files"]
            if not (r["path"] in moved and r["path"] not in now_rows)
        ),
        key=lambda x: x["path"] or "",
    )
    expected += [now_rows[path] for path in sorted(moved - base.keys()) if path in now_rows]
    expected = [
        {**r, "body_sha256": _LOOP_ON_RECAPTURES[r["path"]][fixture]}
        if r["path"] in _LOOP_ON_RECAPTURES
        else r
        for r in expected
    ]
    expected.sort(key=lambda x: x["path"] or "")

    def strip(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in rows if r["path"] != "harness.yaml"]

    assert [r["path"] for r in actual] == [r["path"] for r in expected]
    assert strip(actual) == strip(expected)


# ---------------------------------------------------------------------------
# AC-004 — listing surfaces carry no loop advertisement, exactly one enable hint
# ---------------------------------------------------------------------------


def _enable_hint_count(text: str) -> int:
    """Lines naming the key and the re-render command in the host's spelling.

    The Codex render rewrites `/hm:<name>` to `$hm-<name>` (AGENTS.md), and Codex's
    re-render skill really is `hm-make`, so both spellings name the same command.
    """
    return sum(
        1
        for line in text.splitlines()
        if "loop.enabled: true" in line and ("/hm:make" in line or "$hm-make" in line)
    )


@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
@pytest.mark.parametrize("locale", ["en", "ko"])
def test_ac004_disabled_leaves_no_loop_advertisement(
    tmp_path: Path, preset: Preset, locale: str
) -> None:
    _render_tree(
        tmp_path,
        _answers(loop_enabled=False, targets=ALL_TARGETS, preset=preset, locale=locale),
    )
    for rel in LISTING_SURFACES:
        path = tmp_path / rel
        assert path.is_file(), f"{rel} was not rendered"
        text = path.read_text(encoding="utf-8")
        offenders = [
            line
            for line in text.splitlines()
            if ("hm:loop" in line or "hm-loop" in line) and "loop.enabled" not in line
        ]
        assert offenders == [], f"{rel} still advertises the loop: {offenders}"
        assert _enable_hint_count(text) == 1, f"{rel} must carry exactly one enable hint"


# ---------------------------------------------------------------------------
# AC-005 — an existing harness.yaml without the key keeps the loop
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", ["no_version", "v5", "v6_no_key", "empty_loop_block"])
def test_ac005_existing_absent_key_keeps_loop(tmp_path: Path, variant: str) -> None:
    data = _legacy_yaml_variants()[variant]
    src = tmp_path / "harness.yaml"
    src.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    answers = answers_from_harness_yaml(src)
    assert answers is not None
    assert answers.loop.enabled is True

    out = tmp_path / "out"
    bp = _render_tree(out, answers)
    assert _read_yaml(out)["loop"]["enabled"] is True
    assert {_norm(f.path) for f in bp.files} >= LOOP_CLAUDE


# ---------------------------------------------------------------------------
# AC-006 — no harness.yaml on disk → loop off, schema_version 6, disclosure row
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("preset_flag", ["Side", "Production"])
def test_ac006_no_harness_yaml_writes_loop_off(tmp_path: Path, preset_flag: str) -> None:
    repo = tmp_path / "proj"
    repo.mkdir()
    assert not (repo / ".claude" / "harness.yaml").exists()
    res = _cli(repo, "--preset", preset_flag)
    assert res.exit_code == 0, res.output
    data = _read_yaml(repo)
    assert data["loop"]["enabled"] is False
    assert data["schema_version"] == 6
    assert not (repo / ".claude" / "commands" / "hm" / "loop.md").exists()

    make_md = (_REPO / "commands" / "make.md").read_text(encoding="utf-8")
    disclosure = make_md.split("**Set for you", 1)[1].split("**Safety receipt preview", 1)[0]
    assert "| `loop.enabled` |" in disclosure


# ---------------------------------------------------------------------------
# AC-007 — turning the loop off sweeps pristine files, keeps edited ones
# ---------------------------------------------------------------------------


def test_ac007_disable_sweeps_pristine_keeps_edited(tmp_path: Path) -> None:
    repo = _bootstrap(tmp_path, "--targets", "claude-code,codex")
    data = _read_yaml(repo)
    data["loop"] = {"enabled": True}
    _write_yaml(repo, data)
    res = _cli(repo, "--update")
    assert res.exit_code == 0, res.output

    pristine = [".claude/commands/hm/loop.md", ".agents/skills/hm-loop/SKILL.md"]
    edited = [".claude/commands/hm/loop-p5-batch.md", ".agents/skills/hm-loop-p5-batch/SKILL.md"]
    for rel in pristine + edited:
        assert (repo / rel).is_file(), f"precondition: {rel} rendered while enabled"
    before: dict[str, bytes] = {}
    for rel in edited:
        path = repo / rel
        path.write_text(path.read_text(encoding="utf-8") + "\nuser note\n", encoding="utf-8")
        before[rel] = path.read_bytes()

    data = _read_yaml(repo)
    data["loop"] = {"enabled": False}
    _write_yaml(repo, data)
    res = _cli(repo, "--update")
    assert res.exit_code == 0, res.output

    assert not any((repo / rel).exists() for rel in pristine)
    assert all((repo / rel).read_bytes() == before[rel] for rel in edited)
    assert "orphan(s) kept" in res.output
    kept_rows = [
        json.loads(line)
        for log in (repo / ".claude" / "observability").glob("orphans-*.jsonl")
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    kept = {row["path"]: row["classification"] for row in kept_rows}
    for rel in edited:
        assert kept.get(rel) == "ours-modified", f"{rel} keep warning missing: {kept}"


# ---------------------------------------------------------------------------
# AC-008 — an explicit value survives re-render (property)
# ---------------------------------------------------------------------------


@settings(max_examples=8, derandomize=True, deadline=None)
@given(enabled=st.booleans(), preset=st.sampled_from([Preset.SIDE, Preset.PRODUCTION]))
def test_ac008_explicit_value_round_trips(enabled: bool, preset: Preset) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        first = Path(d) / "first"
        _render_tree(first, _answers(loop_enabled=enabled, preset=preset))
        assert _read_yaml(first)["loop"]["enabled"] is enabled
        reloaded = answers_from_harness_yaml(first / ".claude" / "harness.yaml")
        assert reloaded is not None
        second = Path(d) / "second"
        _render_tree(second, reloaded)
        assert _read_yaml(second)["loop"]["enabled"] is enabled


# ---------------------------------------------------------------------------
# AC-009 — disabling removes only the loop files
# ---------------------------------------------------------------------------


def test_ac009_disable_removes_only_loop_files(tmp_path: Path) -> None:
    enabled = _rendered_body_hashes(tmp_path / "on", loop_enabled=True, targets=ALL_TARGETS)
    disabled = _rendered_body_hashes(tmp_path / "off", loop_enabled=False, targets=ALL_TARGETS)
    assert set(enabled) - set(disabled) == LOOP_CLAUDE | LOOP_CODEX
    assert not (set(disabled) - set(enabled))
    changed = {p for p in disabled if disabled[p] != enabled[p]}
    assert changed <= ALLOWED_BODY_DIFFS, f"unexpected body changes: {changed - ALLOWED_BODY_DIFFS}"
    # The s2b widening is exact: both reference files really do move, and nothing else was added.
    assert ALLOWED_BODY_DIFFS - PREVIOUS_ALLOWED == _S2B_LOOP_REFS
    assert changed >= _S2B_LOOP_REFS, "an allowance for a file that no longer moves is dead"
    for p in disabled:
        if p in ALLOWED_BODY_DIFFS:
            continue
        if p.startswith(
            (".claude/agents/", ".claude/skills/", ".agents/skills/", ".codex/")
        ) or p in {
            ".claude/settings.json",
            ".cursor/hooks.json",
        }:
            assert disabled[p] == enabled[p], f"{p} changed"


# ---------------------------------------------------------------------------
# AC-010 — an existing harness.yaml keeps the loop on every re-render path
# ---------------------------------------------------------------------------


def test_ac010_preset_switch_keeps_existing_loop(tmp_path: Path) -> None:
    """Review finding f5610f47309c7a63: the `--preset` rebuild takes a field allowlist."""
    for preset_from, preset_to in (("Side", "Production"), ("Production", "Side")):
        for enabled in (True, False):
            repo = _bootstrap(tmp_path / f"{preset_from}-{enabled}", "--preset", preset_from)
            data = _read_yaml(repo)
            data["loop"] = {"enabled": enabled}
            _write_yaml(repo, data)
            res = _cli(repo, "--update", "--preset", preset_to)
            assert res.exit_code == 0, res.output
            assert _read_yaml(repo)["preset"] == preset_to
            assert _read_yaml(repo)["loop"]["enabled"] is enabled
            assert (repo / ".claude/commands/hm/loop.md").is_file() is enabled


def test_ac010_existing_yaml_keeps_loop_on_every_path(tmp_path: Path) -> None:
    loop_md = Path(".claude/commands/hm/loop.md")

    repo = _bootstrap(tmp_path / "reinterview")
    data = _read_yaml(repo)
    data.pop("loop", None)
    data["schema_version"] = 5
    _write_yaml(repo, data)
    res = _cli(repo, "--reinterview")
    assert res.exit_code == 0, res.output
    assert _read_yaml(repo)["loop"]["enabled"] is True
    assert (repo / loop_md).is_file()

    repo = _bootstrap(tmp_path / "fallback")
    data = _read_yaml(repo)
    data.pop("loop", None)
    data["preset"] = "NotAPreset"  # answers_from_harness_yaml returns None → interview()
    _write_yaml(repo, data)
    res = _cli(repo, "--update")
    assert res.exit_code == 0, res.output
    assert _read_yaml(repo)["loop"]["enabled"] is True
    assert (repo / loop_md).is_file()

    repo = _bootstrap(tmp_path / "undecodable")
    (repo / ".claude" / "harness.yaml").write_bytes(b"preset: Side\nlocale: \xff\xfe\n")
    res = _cli(repo, "--update")
    assert res.exit_code == 0, res.output
    assert _read_yaml(repo)["loop"]["enabled"] is True
    assert (repo / loop_md).is_file()

    repo = _bootstrap(tmp_path / "explicit-false")
    data = _read_yaml(repo)
    data["loop"] = {"enabled": False}
    _write_yaml(repo, data)
    res = _cli(repo, "--reinterview")
    assert res.exit_code == 0, res.output
    assert _read_yaml(repo)["loop"]["enabled"] is False


# ---------------------------------------------------------------------------
# AC-011 — a malformed loop value fails the render, nothing written or deleted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {"enabled": None},
        {"enabled": "false"},
        {"enabled": True, "extra": 1},
        {1: True},
        {"enabled": True, 1: False, "extra": False},
    ],
    ids=[
        "loop_null",
        "enabled_null",
        "enabled_str_false",
        "unknown_key",
        "int_key",
        "mixed_keys",
    ],
)
def test_ac011_malformed_loop_value_fails_render(tmp_path: Path, bad: object) -> None:
    repo = _bootstrap(tmp_path)
    data = _read_yaml(repo)
    data["loop"] = bad
    _write_yaml(repo, data)
    before = _tree(repo)
    res = _cli(repo, "--update")
    assert res.exit_code != 0
    assert "loop" in res.output
    assert _tree(repo) == before


# ---------------------------------------------------------------------------
# SPEC-hm-light-lane-s2 (concurrency review P1): a loop-off render drops execute Step 5,
# Gate 0 and verify Check 5, so turning the loop off under live loop residue is refused.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "residue",
    [".claude/.hm-loop-abc123", ".worktrees/execute-0f1e2d3c"],
    ids=["loop-marker", "execute-worktree"],
)
def test_turning_the_loop_off_is_refused_while_a_loop_is_live(tmp_path: Path, residue: str) -> None:
    repo = _bootstrap(tmp_path)
    data = _read_yaml(repo)
    data["loop"] = {"enabled": True}
    _write_yaml(repo, data)
    assert _cli(repo, "--update").exit_code == 0
    assert (repo / ".claude/commands/hm/loop.md").is_file()
    path = repo / residue
    if residue.startswith(".worktrees/"):
        path.mkdir(parents=True)
    else:
        path.write_text("claude_session_id: x\n", encoding="utf-8")
    data["loop"] = {"enabled": False}
    _write_yaml(repo, data)
    res = _cli(repo, "--update")
    assert res.exit_code == 1, res.output
    assert "refusing to turn the loop off" in res.output
    assert (repo / ".claude/commands/hm/loop.md").is_file()
    path.rmdir() if path.is_dir() else path.unlink()
    assert _cli(repo, "--update").exit_code == 0
    assert not (repo / ".claude/commands/hm/loop.md").is_file()
