"""Phase 3: /hm:make (make.md.j2) renders the preview + git-disposition flow, no CLI-side commit."""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _render_make_md(tmp_path: Path) -> str:
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.SIDE, targets=[Target.CLAUDE_CODE]),
    )
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    make_md = next(f for f in tmp_path.rglob("commands/hm/make.md"))
    return make_md.read_text(encoding="utf-8")


def test_hm_make_renders_git_disposition_and_preview(tmp_path: Path) -> None:
    body = _render_make_md(tmp_path)
    assert "git-status" in body  # disposition detection call
    assert "git-ignore-roots" in body  # ignore action
    assert "--dry-run" in body  # preview-on-re-render branch
    assert "offer_stage" in body  # no-re-nag staging branch


def test_hm_make_git_framing_is_neutral(tmp_path: Path) -> None:
    body = _render_make_md(tmp_path)
    assert "(Recommended)" not in body  # neutral default (ADR-002)


def test_hm_make_no_cli_side_commit_or_prompt(tmp_path: Path) -> None:
    body = _render_make_md(tmp_path)
    # No CLI-dispatched make line may also run a commit or an interactive prompt.
    for line in body.splitlines():
        if "harness_maker.cli make" in line:
            assert "git commit" not in line, line
            assert "AskUserQuestion" not in line, line


def test_commands_make_md_source_has_git_section() -> None:
    # The meta-command source (not rendered) must carry the same last-mile flow.
    src = (_REPO_ROOT / "commands" / "make.md").read_text(encoding="utf-8")
    assert "### 6.5 Git disposition" in src
    assert "git-status" in src
    assert "git-ignore-roots" in src
    assert "--dry-run" in src
