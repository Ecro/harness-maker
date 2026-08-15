"""AC-017 — the rendered /hm:review ships both brief prohibitions.

Why a render test and not an enforcement test: both clauses are prompt-level
guidance (SPEC Non-Goals). `tools:` and `settings.json` are the only enforcement
surfaces and neither can express "may run pytest, may not edit tests/**" for the
main loop that applies fixes. So the enforceable guarantee is that the rendered
artifact a consumer reads actually carries the instruction — and, critically,
that the test-edit ban carries its carve-out, without which the mandatory
`tests` lens raises findings the loop can never repair.
"""

from __future__ import annotations

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def review_body(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("rendered-briefs")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)
    render(synthesize(p, a), out, freeze_time=DEFAULT_FREEZE_TIME)
    f = out / "commands" / "hm" / "review.md"
    assert f.is_file(), f"missing rendered command file: {f}"
    return f.read_text(encoding="utf-8")


def _flowed(body: str) -> str:
    """Prose reflows across lines and blockquote markers; the instruction does not.

    Asserting on the raw text would make a purely cosmetic rewrap fail the gate —
    and, worse, would invite fixing that by putting the clause on one long line,
    which is a formatting rule the template has no reason to carry.
    """
    stripped = (line.lstrip().removeprefix("> ").removeprefix(">") for line in body.splitlines())
    return " ".join(" ".join(stripped).split()).lower()


def test_render_briefs_and_test_edit_carve_out(review_body: str) -> None:
    flowed = _flowed(review_body)

    # (1) every brief fixes the public contract as out of scope.
    assert "the public contract is fixed and out of scope" in flowed, (
        "the shared brief must state that the public contract is not up for "
        "revision — without it the reviewer proposes API changes, which is the "
        "reviewer answering a question we asked"
    )

    # (2) the fixer may run tests.
    assert "run the tests" in flowed

    # (3) the ban, and (4) its carve-out. The carve-out is load-bearing: the
    # `tests` lens is mandatory, so an unqualified ban leaves its findings
    # permanently `pending` -> one non-progressing round -> terminal
    # `no-progress` on a finding class the harness itself mandates.
    assert "must not edit a test file to resolve a finding whose target is not that test" in flowed
    assert "a finding whose own target is the test may be fixed" in flowed
