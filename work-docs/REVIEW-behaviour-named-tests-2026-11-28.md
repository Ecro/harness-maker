---
type: review
task_slug: behaviour-named-tests
created: 2026-11-28
spec: "[[SPEC-behaviour-named-tests]]"
summary: One code-reviewer pass; 2 major and 7 minor findings fixed, 3 recorded.
---

# REVIEW — behaviour-named-tests

| id | severity | finding | disposition |
|---|---|---|---|
| F1 | major | `bind` only unioned ids, so a test renamed after the first bind left a stale id that mark-tested refused, with no CLI way out | accepted: `bind` replaces each named AC's list; test added |
| F2 | major | an unreadable `parametrize` shape (`BASE + NEW`, a call) made a behaviour-named SPEC report `golden: absent`, so a row edit passed | accepted: `+` of two lists resolves; an unreadable shape on a behaviour-named test (no JSON, no `load_golden_table`, not convention-named) is drift; test added |
| F3 | minor | a filtering or mapping comprehension resolved to its source constant | accepted: only `r` / `pytest.param(*r, ...)` with no `if`; test added |
| F4 | minor | the new path does not compare argnames with the SPEC keys | rejected: a reorder of SPEC keys changes the tuple order and drifts; a pure rename does not change what the test checks, and a test may name `expected` for its meaning (`seconds`, `text`) |
| F5 | minor | `in` uses `==`, so `1`, `1.0` and `True` matched | accepted: compared as printed literals; test added |
| F6 | minor | `write_named_rows` raised TypeError on `NAME = [1, 2]` | accepted: "taken"; test added |
| F7 | minor | a `NAME` assigned on one line was shadowed by a second block | accepted: any top-level assignment of `NAME` is "taken"; test added |
| F8 | minor | `--name` with no parametric AC printed "nothing written" and exited 0 | accepted: exits 1; test added |
| F9 | minor | `bind` accepted any top-level name and paths outside the tree | accepted: the last part must start with `test`, the file must be under the root; test added |
| F10 | minor | `_run_bind` printed a traceback on a broken yaml | accepted: every error is a refusal |
| F11 | minor | `inf`, `nan`, dates print unreadably | pre-existing (same as `repr`); recorded |
| F12 | minor | a constant reassigned later to a non-literal still resolved | accepted: the later assignment wins |
| F13 | info | bind vs Resume (`pending_test`) and 0.67.x compat | no defect |

Verification after fixes: tests/unit/test_behaviour_named_tests.py (14), plus the 71 unit test files that import spec_machine or check (exit 0), ruff, ruff format, mypy --strict.
