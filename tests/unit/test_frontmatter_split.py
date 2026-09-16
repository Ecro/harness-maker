"""`harness_maker.frontmatter.split_frontmatter` — the one byte-level fence splitter (ADR-009).

SPEC-playbook-alignment S1 needs three distinguishable failure shapes (no frontmatter, unterminated
or invalid YAML, a non-mapping) and S2 needs the body returned as the ORIGINAL bytes after the
closing fence, CRLF and BOM included. The fixture bodies below are chosen so a splitter that decodes
with universal newlines, strips a BOM into the mapping, or re-encodes the body fails on bytes.
"""

from __future__ import annotations

import pytest

from harness_maker.frontmatter import split_frontmatter

_MAPPING = b"id: OBJ-1\ntitle: t\n"


def test_ok_returns_the_mapping_and_the_exact_body_bytes() -> None:
    body = b"## Problem\n\ntext with `code` and trailing spaces   \n"
    split = split_frontmatter(b"---\n" + _MAPPING + b"---\n" + body)
    assert split.status == "ok"
    assert split.mapping == {"id": "OBJ-1", "title": "t"}
    assert split.body == body
    assert split.error is None


def test_crlf_fences_are_accepted_and_the_crlf_body_is_untouched() -> None:
    body = b"## Problem\r\n\r\nline two\r\n"
    data = b"---\r\nid: OBJ-1\r\ntitle: t\r\n---\r\n" + body
    split = split_frontmatter(data)
    assert split.status == "ok"
    assert split.mapping == {"id": "OBJ-1", "title": "t"}
    assert split.body == body


def test_a_utf8_bom_is_tolerated_and_never_leaks_into_the_mapping() -> None:
    data = b"\xef\xbb\xbf---\n" + _MAPPING + b"---\nbody\n"
    split = split_frontmatter(data)
    assert split.status == "ok"
    assert split.mapping == {"id": "OBJ-1", "title": "t"}
    assert split.body == b"body\n"


def test_an_empty_frontmatter_is_ok_with_an_empty_mapping() -> None:
    """S1: an empty mapping is a record with every required key missing — not a `file` error."""
    split = split_frontmatter(b"---\n---\nbody\n")
    assert split.status == "ok"
    assert split.mapping == {}
    assert split.body == b"body\n"


def test_missing_frontmatter_is_reported_with_the_whole_input_as_body() -> None:
    data = b"# just markdown\n"
    split = split_frontmatter(data)
    assert split.status == "missing"
    assert split.mapping is None
    assert split.body == data
    assert split.error


def test_unterminated_frontmatter_is_reported() -> None:
    split = split_frontmatter(b"---\nid: OBJ-1\nno closing fence\n")
    assert split.status == "unterminated"
    assert split.mapping is None


def test_invalid_yaml_is_reported_with_the_parser_message() -> None:
    split = split_frontmatter(b"---\n: : [\n---\nbody\n")
    assert split.status == "invalid_yaml"
    assert split.mapping is None
    assert split.error is not None
    assert "YAML" in split.error


@pytest.mark.parametrize("fm", [b"- a\n- b\n", b"just a scalar\n"])
def test_a_non_mapping_frontmatter_is_reported_with_the_post_fence_body(fm: bytes) -> None:
    """The fence was found; only the shape is wrong — the body is the prose after the fence,
    the same slice `ok` returns (review finding b3663bc9: the whole-input body leaked the old
    fence block into second_brain's append/patch paths)."""
    split = split_frontmatter(b"---\n" + fm + b"---\nbody\n")
    assert split.status == "non_mapping"
    assert split.mapping is None
    assert split.body == b"body\n"


@pytest.mark.parametrize(
    "data",
    [
        b"\xef\xbb\xbf# prose\r\n",
        b"\xef\xbb\xbf---\nid: 1\nnever closed\n",
        b"\xef\xbb\xbf---\n: : [\n---\nx\n",
    ],
    ids=["missing", "unterminated", "invalid_yaml"],
)
def test_a_bom_survives_on_every_whole_input_failure_path(data: bytes) -> None:
    """Review finding 7ca445f5: the BOM strip must not leak into the whole-input fallback."""
    split = split_frontmatter(data)
    assert split.status in ("missing", "unterminated", "invalid_yaml")
    assert split.body == data


def test_a_fence_inside_the_body_is_not_a_second_frontmatter() -> None:
    body = b"prose\n---\nnot: frontmatter\n---\n"
    split = split_frontmatter(b"---\n" + _MAPPING + b"---\n" + body)
    assert split.status == "ok"
    assert split.body == body


def test_second_brain_parse_frontmatter_keeps_its_contract() -> None:
    """The vault parser delegates and still returns `(dict, str)` — `({}, text)` on a miss."""
    from harness_maker.second_brain import parse_frontmatter

    mapping, body = parse_frontmatter("---\ntype: note\n---\nhello\n")
    assert mapping == {"type": "note"}
    assert body == "hello\n"
    assert parse_frontmatter("no fence\n") == ({}, "no fence\n")
    # Non-mapping frontmatter: empty dict AND the body after the fence — the pre-change
    # behaviour append_note / patch_note rely on (never the whole document).
    assert parse_frontmatter("---\n- a\n---\nhello\n") == ({}, "hello\n")
