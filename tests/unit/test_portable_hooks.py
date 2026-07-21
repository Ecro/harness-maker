"""PLAN-portable-hook-paths — rendered hook commands must embed a portable ($HOME) ref.

The install ref is home-prefixed and machine-specific; baked verbatim into committed
hook / command bodies it flip-flops across a team repo. These tests lock the two guards:
the render-time leak-check assert (ADR-005) and the actual rendered form across all three
IDE hook surfaces (settings.json / .cursor/hooks.json / .codex/hooks.json — ADR-002/003).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, _assert_portable_install_ref, render
from harness_maker.synthesize import synthesize

# ── ADR-005 render-time leak-check assert ────────────────────────────────────


def test_assert_raises_on_home_leaked_ref() -> None:
    """A ref under the render-machine home (substitution failed) → raise."""
    leaked = str(Path.home()) + "/.claude/plugins/cache/hm/0.42.0"
    with pytest.raises(ValueError, match="non-portable install ref"):
        _assert_portable_install_ref(leaked)


def test_assert_raises_on_home_exact() -> None:
    with pytest.raises(ValueError, match="non-portable install ref"):
        _assert_portable_install_ref(str(Path.home()))


def test_assert_passes_on_portable_ref() -> None:
    """$HOME-substituted, non-home system install, and PyPI name all pass."""
    _assert_portable_install_ref("$HOME/.claude/plugins/cache/hm/0.42.0")
    _assert_portable_install_ref("/opt/hm/0.42.0")
    _assert_portable_install_ref("harness-maker")


def test_assert_noop_on_none() -> None:
    """No ref in the context (non-hook render) → no-op, no raise."""
    _assert_portable_install_ref(None)


def test_assert_sibling_prefix_not_flagged() -> None:
    """Boundary safety: a sibling of home is NOT under home → passes (R4)."""
    _assert_portable_install_ref(str(Path.home()) + "-other/x")


# ── Rendered hook form across all three IDE surfaces (ADR-002/003) ───────────


def _hook_files(root: Path) -> list[Path]:
    """Every rendered settings.json + hooks.json under the render tree."""
    found: list[Path] = []
    for name in ("settings.json", "hooks.json"):
        found.extend(p for p in root.rglob(name) if p.is_file())
    # `.cursor/` and `.codex/` render as project-root siblings of `.claude/`.
    for sib in (".cursor", ".codex"):
        hooks = root.parent / sib / "hooks.json"
        if hooks.is_file():
            found.append(hooks)
    return found


def test_all_hook_surfaces_render_portable_home(tmp_path: Path) -> None:
    """settings.json + .cursor/hooks.json + .codex/hooks.json all embed --with "$HOME/.

    conftest pins _compute_install_ref to the portable `$HOME/harness-maker` form, so the
    rendered `--with` argument must be the double-quoted, shell-expanding `"$HOME/..."` —
    not single-quoted (blocks expansion) and not an absolute home path (flip-flops).
    """
    target_dir = tmp_path / ".claude"
    answers = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX],
    )
    render(
        synthesize(ProjectProfile(stack=["python"]), answers),
        target_dir,
        freeze_time=DEFAULT_FREEZE_TIME,
    )

    hook_files = _hook_files(target_dir)
    surfaces = {p.parent.name for p in hook_files}
    # At least the Claude settings.json + the cursor + codex hooks must be present.
    assert any(p.name == "settings.json" for p in hook_files), "no settings.json rendered"
    assert ".cursor" in surfaces, "no .cursor/hooks.json rendered"
    assert ".codex" in surfaces, "no .codex/hooks.json rendered"

    home = str(Path.home())
    for hf in hook_files:
        text = hf.read_text(encoding="utf-8")
        if "python -m harness_maker" not in text:
            continue
        # Portable double-quoted form present (JSON-escaped as \" inside the string).
        assert '--with \\"$HOME/' in text, f"{hf} lacks portable --with $HOME form"
        # No render-machine home leaked, and no single-quoted --with survived.
        assert home not in text, f"{hf} leaked render-machine home {home!r}"
        assert "--with '" not in text, f"{hf} still single-quotes --with (blocks $HOME expansion)"


def test_leaked_ref_raises_on_fresh_cursor_codex_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A home-prefixed leak must RAISE even for cursor/codex on a FRESH render.

    Fresh render (no existing hooks.json) routes .cursor/.codex hooks through
    `_render_pure_json`, not `_render_hooks_json_merged`. Regression lock for the
    guard-coverage gap (REVIEW P2): the assert must fire on that path too, so this
    only passes because `_render_pure_json` calls `_assert_portable_install_ref`.
    """
    import harness_maker.synthesize as _synth

    leaked = str(Path.home()) + "/.claude/plugins/cache/harness-maker/harness-maker/0.42.0"
    monkeypatch.setattr(_synth, "_compute_install_ref", lambda: leaked)
    answers = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CURSOR, Target.CODEX],
    )
    with pytest.raises(ValueError, match="non-portable install ref"):
        render(
            synthesize(ProjectProfile(stack=["python"]), answers),
            tmp_path / ".claude",
            freeze_time=DEFAULT_FREEZE_TIME,
        )
