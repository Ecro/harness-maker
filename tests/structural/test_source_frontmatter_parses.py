"""Every source template's frontmatter must be loadable YAML.

The renderer merges a source template's frontmatter into the provenance block it
prepends. When `yaml.safe_load` cannot parse it, there is no error — the block is
silently left in the BODY, so the rendered asset ships with two `---` fences and the
IDE reads its `description` as the literal string `---`.

That is how `worktree-isolator`'s description became `---`: the text was changed from
`/hm:execute` to `/hm: stage`, and a YAML plain scalar cannot contain a colon followed
by a space. Nothing failed; the skill just stopped describing itself, which is the
field an IDE uses to decide whether to surface the skill at all.

Jinja is normalized away before parsing: a `{% ... %}` statement line renders to zero
or more whole lines (an `{% include %}` of a `model:` fragment, say) so the LINE is
dropped, while an inline `{{ ... }}` becomes a scalar. Neither is what this test is
about — it is about the literal YAML the author typed around them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

import harness_maker

_TEMPLATES = Path(harness_maker.__file__).parent / "templates"
_JINJA_EXPR = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_JINJA_STMT_LINE = re.compile(r"^[ \t]*\{%.*?%\}[ \t]*$\n?", re.DOTALL | re.MULTILINE)


def _frontmatter_sources() -> list[Path]:
    out: list[Path] = []
    for path in sorted(_TEMPLATES.rglob("*.md.j2")):
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n") and "\n---\n" in text[4:]:
            out.append(path)
    return out


@pytest.mark.parametrize(
    "path", _frontmatter_sources(), ids=lambda p: str(p.relative_to(_TEMPLATES))
)
def test_source_frontmatter_is_parseable_yaml(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    block = text[4:].split("\n---\n", 1)[0]
    # A statement line renders to whole lines of its own — drop it. An inline
    # expression is a value — substitute a scalar.
    block = _JINJA_STMT_LINE.sub("", block)
    block = _JINJA_EXPR.sub("x", block)
    try:
        loaded = yaml.safe_load(block)
    except yaml.YAMLError as exc:  # pragma: no cover - the failure message is the point
        pytest.fail(
            f"{path.relative_to(_TEMPLATES)} frontmatter is not parseable YAML, so the "
            f"renderer will silently leave it in the body:\n{exc}"
        )
    assert isinstance(loaded, dict), (
        f"{path.relative_to(_TEMPLATES)} frontmatter parsed to {type(loaded).__name__}, "
        "not a mapping"
    )
