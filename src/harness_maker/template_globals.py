"""The names every Jinja environment in this package must expose to templates.

There is more than one `Environment(...)` in `src/` — `render`, `personalization_audit` and
`foreign_config` each build their own — and they render the SAME template files. A global
installed on one of them is therefore not installed at all: the template renders in one code
path and raises `UndefinedError` in another, which is how the review lens axis shipped broken
into `personalization_audit` the first time.

Two rules keep that from recurring. Every environment calls `install(env)`, and
`tests/structural/test_template_globals_installed.py` finds each `Environment(` construction by
AST rather than from a list in this docstring — a hand-maintained list of call sites is the
thing that was wrong.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from harness_maker import conditional_router, review_churn, strictness

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters at type-check time
    from jinja2 import Environment

_HM_SLASH_COMMAND = re.compile(r"(?<![\w./])(?:/hm:|@hm-)([a-z0-9][a-z0-9-]*|\*)")
_INLINE_CODE = re.compile(r"(`+)(.+?)\1")
_FENCE = re.compile(r"^\s*(?:>\s*)?(`{3,}|~{3,})([^\n]*)")


def _invocation_line(line: str) -> str:
    """Convert prose and inline prompt examples, never inline executable payloads."""
    parts: list[str] = []
    start = 0
    for match in _INLINE_CODE.finditer(line):
        parts.append(_HM_SLASH_COMMAND.sub(r"$hm-\1", line[start : match.start()]))
        code = match.group(2)
        if re.match(r"(?:/hm:|@hm-)", code):
            code = _HM_SLASH_COMMAND.sub(r"$hm-\1", code)
        parts.append(match.group(1) + code + match.group(1))
        start = match.end()
    parts.append(_HM_SLASH_COMMAND.sub(r"$hm-\1", line[start:]))
    return "".join(parts)


def stage_invocation(text: str, is_codex: bool) -> str:
    """Format owned Markdown guidance using Codex's ``$skill-name`` syntax.

    Also used on complete Codex documents before user-block merge and hashing.
    Executable fences and inline payloads stay literal: inserting dollar signs
    inside a shell string would introduce variable expansion. Text/Markdown fences
    contain prose; unlabelled fences convert only standalone invocation lines.
    Internal ``hm:stage`` IDs, paths and user blocks retain their original bytes.
    """
    if not is_codex:
        return text
    result: list[str] = []
    fence = ""
    prompt_fence = False
    prose_fence = False
    user_block = False
    for line in text.splitlines(keepends=True):
        if "<!-- @hm:user:" in line:
            user_block = True
        if user_block:
            result.append(line)
            if "<!-- @hm:/user:" in line:
                user_block = False
            continue
        marker = _FENCE.match(line)
        if marker:
            delimiter, info = marker.groups()
            if not fence:
                fence = delimiter
                prompt_fence = not info.strip()
                prose_fence = info.strip() in {"text", "markdown", "md"}
            elif delimiter[0] == fence[0] and len(delimiter) >= len(fence) and not info.strip():
                fence = ""
            result.append(line)
        elif fence:
            if prose_fence:
                line = _invocation_line(line)
            elif prompt_fence and re.match(r"\s*(?:/hm:|@hm-)", line):
                line = _HM_SLASH_COMMAND.sub(r"$hm-\1", line)
            result.append(line)
        else:
            result.append(_invocation_line(line))
    return "".join(result)


#: Exported as a callable rather than baked into each template as a literal list. The rendered
#: dispatch list and `hm lens_coverage check` must agree on the mandatory lens set; a literal
#: would let them disagree, and the symptom of that is not a visible drift but a review that can
#: never be approved, because the CLI names a lens the command never told anyone to run.
TEMPLATE_GLOBALS: dict[str, object] = {
    "lens_dispatch": conditional_router.lens_dispatch,
    # The unit of DISPATCH, which stopped being the unit of lens when the four core lenses
    # collapsed into one call. Both dispatch blocks in `review.md.j2` loop over this, so they
    # cannot drift from each other or from `lens_coverage`'s idea of what a result file covers.
    "lens_dispatch_groups": conditional_router.lens_dispatch_groups,
    "mandatory_lenses": conditional_router.mandatory_lenses,
    "routable_lenses": conditional_router.routable_lenses,
    # Same reason, different axis: the rendered gate branch and `resolve_churn_threshold`
    # must agree on what "absent key" means. A literal `0.20` in the template would let the
    # prose promise one threshold while the CLI applied another.
    "default_churn_ratio": review_churn.default_churn_ratio,
    # Rendered vocabulary, not content: `/hm:execute` is uncallable on Codex.
    "stage_invocation": stage_invocation,
    # SPEC-dev-mode-removal AC-001: templates never read `spec.strictness` themselves. Every
    # environment resolves through the one reader, so a config dump from ANY render path —
    # synthesize, personalization_audit, a test's bare `HarnessConfig().model_dump()` — gets
    # the same absent-case answer.
    "strictness_of": strictness.resolve_strictness,
    "explicit_strictness": strictness.explicit_strictness,
}


def install(env: Environment) -> Environment:
    """Add every shared global to `env`, in place. Returns it for call-site convenience."""
    env.globals.update(TEMPLATE_GLOBALS)
    return env
