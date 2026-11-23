---
type: review
task_slug: test-suite-speed
created: 2026-11-23
spec: "[[SPEC-test-suite-speed]]"
summary: One code-reviewer round, no P0-P2; codex second opinion skipped (CLI not installed).
---

# REVIEW — test-suite-speed

Round 1: `code-reviewer` over SPEC, PLAN, diff and tests. Second opinion: codex `skipped`
("CLI not installed: codex"), warn-and-proceed. RED: AC-002 and AC-003 failed for the intended
reason (44 formattings vs 9 hits; 4 launches vs 2); AC-001 waived `--green-ok` (behaviour-
preserving golden, green before by construction).

Measured: `test_no_imports_remain` 24.5 s → 1.8 s; `tests/e2e/test_plugin_live.py` with the real
`claude` 6 passed in 59 s wall (2 live sessions instead of 4).

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F-1 | P3 | tests/unit/test_test_suite_speed.py (seeded tree) | No `from . import x` (module=None) case in the golden tree | rejected | Reviewer's own trace shows identical behaviour on that path; adding a row means re-approving the SPEC for a P3 |
| F-2 | P3 | tests/e2e/test_plugin_live.py:115 | Under `--dist load` the module fixture could run once per worker | rejected | ci.yml:64 and test_runners.py:127 run pytest with `--dist loadfile`, which keeps one file on one worker |
| F-3 | P3 | tests/e2e/test_plugin_live.py:115 | A timeout in the shared run reports 3 setup errors, not 3 failures | rejected | Documented in the test comment; still red |
| F-4 | P3 | tests/unit/test_test_suite_speed.py:104 | `subprocess.run` without `check=True` | rejected | rc is asserted with the nested output as detail, which `check=True` would hide |
| F-5 | P3 | tests/unit/test_test_suite_speed.py:63 | AC-002 relies on `rglob`/`resolve` not calling `relative_to` | rejected | Holds on 3.12/3.13; a future change fails loudly, not silently |
| F-6 | P3 | tests/unit/test_test_suite_speed.py:104 | Nested run seeds e2e sandboxes | rejected | Seeding is idempotent and `exists()`-guarded (tests/e2e/conftest.py) |
