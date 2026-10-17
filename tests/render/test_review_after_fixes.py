"""SPEC-review-after-fixes AC-001..002: the REVIEW is execute's completion record."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

#: The arms: both presets, worktree off and on, both runtimes.
ARMS = (("Side", ()), ("Production", ()), ("Side", ("--worktree",)))
_ARGS = ("--autoloop", "--targets", "claude-code,codex", "--locale", "en")
EXECUTE = (".claude/commands/hm/execute.md", ".agents/skills/hm-execute/SKILL.md")


@pytest.fixture(scope="module")
def execute_renders(tmp_path_factory: pytest.TempPathFactory) -> Callable[[], Iterator[str]]:
    texts: list[str] = []
    for i, (preset, extra) in enumerate(ARMS):
        base = tmp_path_factory.mktemp(f"raf-{i}")
        project = init_project(base / "proj")
        proc = run_make(
            project, (*_ARGS, "--preset", preset, *extra), src=HEAD_SRC, home=base / "home"
        )
        assert proc.returncode == 0, proc.stderr[-2000:]
        texts += [(project / rel).read_text("utf-8") for rel in EXECUTE]

    def get() -> Iterator[str]:
        return iter(texts)

    return get


def step6(text: str) -> str:
    return text[text.index("## Step 6") :]


def preamble(text: str) -> str:
    return text[: text.index("## Step 0")]


def review_after_fix_loop(step: str) -> bool:
    loop = step.index("review again")
    stop = step.rindex("then STOP")
    review = step.find("REVIEW-<slug>-<YYYY-MM-DD>.md", loop)
    return (
        "REVIEW-" not in step[:loop]
        and step.index("reviewers.max_review_rounds") < review
        and "the record that execute finished" in step[loop:]
        and "every round's findings" in step[loop:]
        # The final print names "the `hm check` result"; only a new invocation is forbidden.
        and "hm check --" not in step[review:stop]
    )


def resume_after_bind(head: str) -> bool:
    lines = [ln for ln in head.splitlines() if "every testable AC is `pending_test: false`" in ln]
    if len(lines) != 1:
        return False
    line = lines[0]
    rest = line[line.index("every testable AC is `pending_test: false`") :]
    return "rerun Bind's gate" in rest and "Step 4" in rest and "hm check --slug" not in line


def test_ac_001_review_written_after_fix_loop(
    execute_renders: Callable[[], Iterator[str]],
) -> None:
    assert all(review_after_fix_loop(step6(text)) for text in execute_renders())


def test_ac_002_resume_after_bind_skips_red(
    execute_renders: Callable[[], Iterator[str]],
) -> None:
    assert all(resume_after_bind(preamble(text)) for text in execute_renders())
