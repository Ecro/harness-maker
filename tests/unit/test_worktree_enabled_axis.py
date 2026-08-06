"""PLAN-worktree-side-defaults Phase 1 — the `worktree.enabled` render contract.

The `worktree:` block shipped four keys of which one had runtime effect, and two
(`scope`, `branch_prefix`) were hardcoded template literals a re-render silently
reverted (RESEARCH F1/V3). This module pins the collapsed contract:

- both presets render exactly one key, from `config.worktree`
- a hand-edited value round-trips through `--update` AND a `--preset` switch
- `_cli_create` reads the new key, so dropping `scope` cannot silently disable
  isolation on a freshly-rendered ON harness (validator critical #1 / R11)
- the Codex `AGENTS.md` states the mode matching the flag (R12)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from harness_maker import worktree
from harness_maker.interview import _preset_extras, answers_from_harness_yaml
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(
    tmp_path: Path,
    *,
    preset: Preset,
    worktree_dict: dict[str, object] | None = None,
    targets: list[Target] | None = None,
) -> Path:
    answers = InterviewAnswers(
        preset=preset,
        targets=targets or [Target.CLAUDE_CODE],
        worktree=worktree_dict if worktree_dict is not None else _preset_extras(preset)["worktree"],
    )
    bp = synthesize(ProjectProfile(), answers)
    tmp_path.mkdir(parents=True, exist_ok=True)
    render(bp, tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _block(root: Path) -> dict[str, object]:
    data = load_harness_yaml(root / ".claude" / "harness.yaml")
    wt = data.get("worktree")
    assert isinstance(wt, dict), wt
    return wt


# ── (a) both presets render exactly one key ──────────────────────────────────


def test_side_preset_default_is_disabled(tmp_path: Path) -> None:
    assert _preset_extras(Preset.SIDE)["worktree"] == {"enabled": False}


def test_production_preset_default_is_enabled(tmp_path: Path) -> None:
    assert _preset_extras(Preset.PRODUCTION)["worktree"] == {"enabled": True}


def test_side_renders_enabled_false(tmp_path: Path) -> None:
    assert _block(_render(tmp_path, preset=Preset.SIDE)) == {"enabled": False}


def test_production_renders_enabled_true(tmp_path: Path) -> None:
    assert _block(_render(tmp_path, preset=Preset.PRODUCTION)) == {"enabled": True}


# ── (b) the retired keys are gone ────────────────────────────────────────────


def test_rendered_block_has_no_retired_keys(tmp_path: Path) -> None:
    for preset in (Preset.SIDE, Preset.PRODUCTION):
        root = _render(tmp_path / preset.value, preset=preset)
        block = _block(root)
        assert "scope" not in block
        assert "branch_prefix" not in block
        assert "feature_branch_workflow" not in block


# ── (c) V3 round-trip: a hand-edit survives a re-render ──────────────────────


def test_hand_edited_enabled_survives_roundtrip(tmp_path: Path) -> None:
    """The original defect: `scope` was a template literal, so a hand-edit was
    silently reverted on every `make --update`. The replacement key must not be."""
    for preset, flipped in ((Preset.SIDE, True), (Preset.PRODUCTION, False)):
        root = _render(tmp_path / f"rt-{preset.value}", preset=preset)
        yaml_path = root / ".claude" / "harness.yaml"
        text = yaml_path.read_text(encoding="utf-8")
        yaml_path.write_text(
            text.replace(
                f"enabled: {str(not flipped).lower()}", f"enabled: {str(flipped).lower()}"
            ),
            encoding="utf-8",
        )
        answers = answers_from_harness_yaml(yaml_path)
        assert answers is not None
        assert answers.worktree == {"enabled": flipped}, preset
        # …and re-rendering from those answers keeps it
        bp = synthesize(ProjectProfile(), answers)
        render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        assert _block(root) == {"enabled": flipped}, preset


# ── (d) precedence cross-product: CLI flag > disk > preset default ───────────


def test_preset_switch_preserves_explicit_disk_value(tmp_path: Path) -> None:
    """The V5 mechanism, re-applied to the new key: `_apply_dimension_overrides`
    rebuilds the worktree dict from preset extras on a `--preset` switch, which is
    exactly how `feature_branch_workflow` was silently dropped."""
    from harness_maker.cli import _apply_dimension_overrides

    # a Side harness the user explicitly turned isolation ON for
    answers = InterviewAnswers(
        preset=Preset.SIDE, targets=[Target.CLAUDE_CODE], worktree={"enabled": True}
    )
    switched = _apply_dimension_overrides(
        answers,
        preset_override="Production",
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
    )
    assert switched.worktree == {"enabled": True}

    # and the other direction: an explicit OFF survives a switch to Production
    answers_off = InterviewAnswers(
        preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE], worktree={"enabled": False}
    )
    switched_off = _apply_dimension_overrides(
        answers_off,
        preset_override="Side",
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
    )
    assert switched_off.worktree == {"enabled": False}


def test_cli_flag_beats_disk(tmp_path: Path) -> None:
    from harness_maker.cli import _apply_dimension_overrides

    answers = InterviewAnswers(
        preset=Preset.SIDE, targets=[Target.CLAUDE_CODE], worktree={"enabled": False}
    )
    forced_on = _apply_dimension_overrides(
        answers,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
        worktree_override=True,
    )
    assert forced_on.worktree == {"enabled": True}

    forced_off = _apply_dimension_overrides(
        forced_on,
        preset_override="Production",
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
        worktree_override=False,
    )
    assert forced_off.worktree == {"enabled": False}


# ── R11: `_cli_create` must not read the retired `scope` ─────────────────────


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/\n")
    (repo / "README.md").write_text("x\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _repo_with_harness(tmp_path: Path, name: str, preset: Preset) -> Path:
    """Render a harness into a repo and commit it — the create-guard blocks on a
    dirty base, and the render writes CLAUDE.md into the repo root."""
    repo = _repo(tmp_path, name)
    _render(repo, preset=preset)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "harness"], repo)
    return repo


def test_cli_create_returns_a_real_path_on_fresh_on_render(tmp_path: Path, capsys: object) -> None:
    """R11 regression, asserted at RUNTIME — a grep cannot see this.

    `_cli_create` gated on `_scope_includes`. Once Phase 1 stops rendering `scope`,
    that gate returns False on a freshly-rendered **ON** harness, `worktree create
    execute` prints an empty line, and every rendered command reads empty output as
    "no isolation; operate in cwd" — total silent isolation loss on Production while
    every render/unit test in the PLAN still passes.
    """
    repo = _repo_with_harness(tmp_path, "on", Preset.PRODUCTION)
    rc = worktree._cli_create(["execute", str(repo)])
    assert rc == 0
    out = capsys.readouterr().out.strip()  # type: ignore[attr-defined]
    assert out, "ON harness must produce a worktree path, got empty output"
    assert Path(out).is_dir(), out


def test_cli_create_is_silent_on_fresh_off_render(tmp_path: Path, capsys: object) -> None:
    repo = _repo_with_harness(tmp_path, "off", Preset.SIDE)
    rc = worktree._cli_create(["execute", str(repo)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == ""  # type: ignore[attr-defined]


# ── R12: the Codex AGENTS.md must state the real mode ────────────────────────


def test_codex_agents_md_states_the_flag(tmp_path: Path) -> None:
    on = _render(
        tmp_path / "agents-on",
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE, Target.CODEX],
    )
    off = _render(
        tmp_path / "agents-off",
        preset=Preset.SIDE,
        targets=[Target.CLAUDE_CODE, Target.CODEX],
    )
    on_text = (on / "AGENTS.md").read_text(encoding="utf-8")
    off_text = (off / "AGENTS.md").read_text(encoding="utf-8")
    assert "Worktree isolation: enabled" in on_text
    assert "Worktree isolation: disabled" in off_text
    # the `is defined` fallback used to print the literal 'execute' regardless
    assert "worktree scope" not in off_text.lower()


# ── review round 1 regressions ───────────────────────────────────────────────


def test_disable_is_refused_while_a_task_worktree_is_live(tmp_path: Path) -> None:
    """ADR-003's guard, exercised through the probe rather than the CLI."""
    repo = _repo_with_harness(tmp_path, "guard", Preset.PRODUCTION)
    _git(["worktree", "add", "-b", "hm/foo", ".worktrees/foo"], repo)
    may, refusal = worktree.disable_preflight(repo)
    assert may is False
    assert refusal is not None
    assert "hm/foo" in refusal or "foo" in refusal


def test_disable_is_refused_for_an_unlanded_branch_with_no_worktree(tmp_path: Path) -> None:
    """The durable unit of work is the BRANCH — `cleanup` removes the directory but
    never the branch, so a directory-only probe misses crash/prune leftovers."""
    repo = _repo_with_harness(tmp_path, "branchonly", Preset.PRODUCTION)
    _git(["branch", "hm/orphan"], repo)
    may, refusal = worktree.disable_preflight(repo)
    assert may is False
    assert refusal is not None
    assert "hm/orphan" in refusal


def test_disable_is_refused_on_a_detached_task_worktree(tmp_path: Path) -> None:
    """Fail-CLOSED: an unreadable branch (mid-rebase) must block, not wave through."""
    repo = _repo_with_harness(tmp_path, "detached", Preset.PRODUCTION)
    _git(["worktree", "add", "--detach", ".worktrees/det"], repo)
    blockers, _live = worktree._task_worktree_blockers(repo, "")
    assert any("detached" in b for b in blockers), blockers


def test_disable_allowed_on_a_clean_repo(tmp_path: Path) -> None:
    repo = _repo_with_harness(tmp_path, "clean", Preset.PRODUCTION)
    assert worktree.disable_preflight(repo) == (True, None)


def test_finalize_refuses_a_task_worktree_when_isolation_is_off(
    tmp_path: Path, capsys: object
) -> None:
    """The destructive-path P0: flag OFF + an `hm/*` worktree used to fall through to
    stash+merge+`worktree remove --force`, squashing an unlanded task branch into base."""
    repo = _repo_with_harness(tmp_path, "offfin", Preset.SIDE)  # Side ⇒ enabled: false
    _git(["worktree", "add", "-b", "hm/bar", ".worktrees/bar"], repo)
    rc = worktree.main(["finalize", str(repo / ".worktrees" / "bar"), "stage-only"])
    assert rc == 1
    err = capsys.readouterr().err  # type: ignore[attr-defined]
    assert "refusing" in err
    assert "task-land" in err
    # the branch and the directory both survive
    assert (repo / ".worktrees" / "bar").is_dir()
