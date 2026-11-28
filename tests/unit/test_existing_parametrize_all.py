"""SPEC-existing-parametrize-all: every AC's cases join an existing parametrize of the same call.

After SPEC-test-shape-rules, t7-1 still lost maintainability on a new raising-case test that copied
`test_invalid` instead of extending its list; the counterfactual removed that evidence. The paste
rule covered only golden rows, so this pins a rule for every AC test, stated before the per-type
clauses.
"""

from __future__ import annotations

from tests.unit.test_behaviour_named_tests import EXECUTE_PHRASES
from tests.unit.test_hm_cost_p2_templates import _render
from tests.unit.test_test_shape_rules import EXTEND_PHRASES

ALL_AC_PHRASE = (
    "cases for a call a test there already parametrizes go into its list, not a new test"
)


def test_execute_puts_every_acs_cases_into_an_existing_parametrize() -> None:
    for is_codex in (False, True):
        text = _render("execute", is_codex=is_codex)
        assert ALL_AC_PHRASE in text, is_codex
        assert text.index(ALL_AC_PHRASE) < text.index("a mechanical AC asserts")
        for phrase in (*EXTEND_PHRASES, *EXECUTE_PHRASES):
            assert phrase in text, (is_codex, phrase)
